"""
Fix tags in existing vault notes: rename and remove according to new ALLOWED_TAGS.

Usage:
    python fix_tags.py          # dry run — показывает что изменится
    python fix_tags.py --apply  # применяет изменения
"""

import re
import argparse
from pathlib import Path
from config import VAULT_PATH

# Tags to remove entirely
REMOVE = {
    "design",
    "system-design",
}

# Tags to rename: old → new
RENAME = {
    "product-design":    "product_design",
    "motion-design":     "motion_design",
    "interview-prep":    "interview_prep",
    "others_AI":         "AI",
    "product-management":"product_management",
    "machine-learning":  "machine_learning",
    "web design":        "web_design",
    "web-design":        "web_design",
    "social-media":      "social_media",
    "cultural-identity": "cultural_identity",
    "personal-branding": "personal_branding",
    "trend analysis":    "trend_analysis",
    "design trends":     "design_trends",
    "creative-process":  "creative_process",
    "content-creation":  "content_creation",
    "video-production":  "video_production",
    "local-business":    "local_business",
    "consumer-behavior": "consumer_behavior",
    "instagram-marketing": "instagram_marketing",
}


def fix_note_tags(text: str) -> tuple[str, list[str]]:
    """Return (new_text, list_of_changes). If no changes, new_text == text."""
    # Find tags block in frontmatter
    fm_match = re.match(r'^(---\n)(.*?)(\n---\n)', text, re.DOTALL)
    if not fm_match:
        return text, []

    pre, fm, post = fm_match.group(1), fm_match.group(2), fm_match.group(3)
    body = text[fm_match.end():]

    tags_match = re.search(r'(tags:\n)((?:- .+\n?)+)', fm)
    if not tags_match:
        return text, []

    tags_header = tags_match.group(1)
    tags_block = tags_match.group(2)

    old_tags = []
    for line in tags_block.splitlines():
        tag = line.strip().lstrip("- ").strip().strip("'\"")
        if tag:
            old_tags.append(tag)

    new_tags = []
    changes = []
    seen = set()

    for tag in old_tags:
        if tag in REMOVE:
            changes.append(f"удалён: {tag}")
            continue
        new_tag = RENAME.get(tag, tag)
        if new_tag != tag:
            changes.append(f"переименован: {tag} → {new_tag}")
        if new_tag not in seen:
            new_tags.append(new_tag)
            seen.add(new_tag)

    if not changes:
        return text, []

    new_tags_block = "".join(f"- {t}\n" for t in new_tags)
    new_fm = fm[:tags_match.start()] + tags_header + new_tags_block + fm[tags_match.end():]
    new_text = pre + new_fm + post + body
    return new_text, changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    if args.apply:
        print("РЕЖИМ: применяем изменения\n")
    else:
        print("РЕЖИМ: dry run (добавь --apply чтобы применить)\n")

    notes = list(VAULT_PATH.rglob("*.md"))
    total_changed = 0

    for note in notes:
        try:
            text = note.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ✗ не удалось прочитать {note.name}: {e}")
            continue

        new_text, changes = fix_note_tags(text)
        if not changes:
            continue

        total_changed += 1
        rel = note.relative_to(VAULT_PATH)
        print(f"{rel}")
        for c in changes:
            print(f"  {c}")

        if args.apply:
            note.write_text(new_text, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Заметок {'изменено' if args.apply else 'изменится'}: {total_changed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
