"""
Re-run Claude enrichment on existing vault notes.

Usage:
    python reenrich.py [--apply] [--folder FOLDER_KEY] [--limit N]

    --apply          Actually apply changes (default: dry run)
    --folder KEY     Only process notes in this folder key (e.g. portfolio)
    --limit N        Process at most N notes (useful for testing)

What it updates:
    - tags          → английский, snake_case, по новым правилам
    - folder        → по обновлённым описаниям и folder_examples.yml
    - title         → на русском
    - summary       → на русском
    - concepts      → на русском
    - instructions  → на русском
    - insights      → на русском
    + обновляет соответствующие блоки в теле заметки

What it does NOT touch:
    source_url, published, author, channel, note_id, schema_version,
    needs_review, no_subtitles, added — эти поля не меняются.
"""

import re
import sys
import time
import random
import argparse
import yaml
from pathlib import Path

from config import VAULT_PATH, VAULT_FOLDERS
from enrich import enrich


def _read_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]
    return fm, body


def _write_frontmatter(fm: dict, body: str) -> str:
    yml = yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{yml}---\n{body}"


def _extract_text_for_enrich(body: str) -> str:
    """Pull the most informative sections from note body for re-enrichment."""
    sections = []
    for header in ("## Расшифровка", "## Кратко", "## Ключевые мысли",
                   "## Инсайты", "## Описание видео", "## Summary", "## Key concepts"):
        m = re.search(rf'{re.escape(header)}\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
        if m:
            sections.append(m.group(1).strip())
    return "\n\n".join(sections)[:12000]


def _update_body_section(body: str, header: str, new_content: str) -> str:
    """Replace content under a markdown header."""
    pattern = rf'({re.escape(header)}\n)(.*?)(?=\n## |\Z)'
    replacement = rf'\g<1>{new_content}\n'
    new_body, count = re.subn(pattern, replacement, body, flags=re.DOTALL)
    return new_body if count else body


def _list_to_md(items: list) -> str:
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)


def _folder_path(key: str) -> Path:
    rel = VAULT_FOLDERS.get(key, VAULT_FOLDERS["inbox"])
    return VAULT_PATH / rel


def _current_folder_key(note_path: Path) -> str:
    current_dir = note_path.parent
    return next(
        (k for k, v in VAULT_FOLDERS.items() if VAULT_PATH / v == current_dir),
        "inbox"
    )


def reenrich_note(note_path: Path, apply: bool) -> tuple[str, str]:
    """
    Returns (status, description):
        status: "changed", "moved", "skipped", "error"
    """
    try:
        text = note_path.read_text(encoding="utf-8")
        fm, body = _read_frontmatter(text)

        if not fm.get("note_id"):
            return "skipped", "нет note_id — не наша заметка"

        enrich_text = _extract_text_for_enrich(body)
        if not enrich_text.strip():
            return "skipped", "нет текста для обогащения"

        hint_title = fm.get("title") or note_path.stem
        enriched = enrich(enrich_text, hint_title=hint_title)

        new_tags         = enriched.get("tags") or []
        new_folder_key   = enriched.get("folder") or "inbox"
        new_title        = enriched.get("title") or hint_title
        new_summary      = enriched.get("summary") or ""
        new_concepts     = enriched.get("concepts") or []
        new_instructions = enriched.get("instructions") or []
        new_insights     = enriched.get("insights") or []

        old_tags       = fm.get("tags") or []
        old_folder_key = _current_folder_key(note_path)

        # Detect changes
        changes = []
        if sorted(new_tags) != sorted(old_tags):
            changes.append(f"теги")
        if new_folder_key != old_folder_key:
            changes.append(f"папка: {old_folder_key} → {new_folder_key}")
        if new_title != fm.get("title"):
            changes.append("title")
        if new_summary != fm.get("summary", ""):
            changes.append("summary")
        if new_concepts != fm.get("concepts", []):
            changes.append("concepts")
        if new_instructions != fm.get("instructions", []):
            changes.append("instructions")
        if new_insights != fm.get("insights", []):
            changes.append("insights")

        if not changes:
            return "skipped", f"без изменений (папка: {old_folder_key})"

        if apply:
            # Update frontmatter fields
            fm["tags"]         = new_tags
            fm["title"]        = new_title
            fm["summary"]      = new_summary
            fm["concepts"]     = new_concepts
            fm["instructions"] = new_instructions
            fm["insights"]     = new_insights

            # Update body sections
            if new_summary:
                body = _update_body_section(body, "## Кратко", new_summary)
            if new_concepts:
                body = _update_body_section(body, "## Ключевые мысли", _list_to_md(new_concepts))
            if new_instructions:
                body = _update_body_section(body, "## Как применить", _list_to_md(new_instructions))
            if new_insights:
                body = _update_body_section(body, "## Инсайты", _list_to_md(new_insights))

            new_text = _write_frontmatter(fm, body)

            if new_folder_key != old_folder_key:
                new_dir = _folder_path(new_folder_key)
                new_dir.mkdir(parents=True, exist_ok=True)
                new_path = new_dir / note_path.name
                note_path.write_text(new_text, encoding="utf-8")
                note_path.rename(new_path)
                return "moved", " | ".join(changes)
            else:
                note_path.write_text(new_text, encoding="utf-8")
                return "changed", " | ".join(changes)
        else:
            return "ok", " | ".join(changes)  # dry run

    except Exception as e:
        return "error", str(e)


def main():
    parser = argparse.ArgumentParser(description="Re-run Claude enrichment on vault notes")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    parser.add_argument("--folder", metavar="KEY", help="Only process notes in this folder key")
    parser.add_argument("--limit", type=int, default=0, help="Max notes to process")
    args = parser.parse_args()

    if args.apply:
        print("РЕЖИМ: применяем изменения\n")
    else:
        print("РЕЖИМ: dry run (добавь --apply чтобы применить)\n")

    if args.folder:
        folder_rel = VAULT_FOLDERS.get(args.folder)
        if not folder_rel:
            print(f"Неизвестный ключ папки: {args.folder}")
            sys.exit(1)
        search_path = VAULT_PATH / folder_rel
        notes = list(search_path.rglob("*.md"))
        print(f"Папка: {folder_rel} — {len(notes)} заметок")
    else:
        notes = list(VAULT_PATH.rglob("*.md"))
        print(f"Весь vault: {len(notes)} заметок")

    if args.limit:
        notes = notes[:args.limit]
        print(f"Ограничение: первые {args.limit}\n")

    stats = {"moved": 0, "changed": 0, "skipped": 0, "error": 0, "would_change": 0}

    for i, note in enumerate(notes, 1):
        print(f"[{i}/{len(notes)}] {note.name[:70]}")
        status, desc = reenrich_note(note, apply=args.apply)

        if status == "skipped":
            print(f"  → пропуск: {desc}")
            stats["skipped"] += 1
        elif status == "error":
            print(f"  ✗ ошибка: {desc}")
            stats["error"] += 1
        elif status == "ok":
            print(f"  ~ изменится: {desc}")
            stats["would_change"] += 1
        elif status == "moved":
            print(f"  ✓ перемещена: {desc}")
            stats["moved"] += 1
        elif status == "changed":
            print(f"  ✓ обновлена: {desc}")
            stats["changed"] += 1

        if i < len(notes):
            time.sleep(random.uniform(1, 2))

    print(f"\n{'='*60}")
    if args.apply:
        print(f"Перемещено в новую папку:  {stats['moved']}")
        print(f"Обновлено (без переноса):  {stats['changed']}")
        print(f"Пропущено:                 {stats['skipped']}")
        print(f"Ошибок:                    {stats['error']}")
    else:
        print(f"Изменится при --apply:     {stats['would_change']}")
        print(f"Пропущено:                 {stats['skipped']}")
        print(f"Ошибок:                    {stats['error']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
