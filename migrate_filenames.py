"""
Renames existing notes to the new format: [YYYY-MM-DD] [source] title.md
Reads data from frontmatter only — no API calls, no re-extraction.

Usage:
    python migrate_filenames.py          # dry run — shows what would change
    python migrate_filenames.py --apply  # actually renames files
"""

import re
import sys
import yaml
from pathlib import Path
from urllib.parse import urlparse
from config import VAULT_PATH


def _source_label(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    known = {
        "youtube.com": "youtube",
        "youtu.be": "youtube",
        "habr.com": "habr",
        "medium.com": "medium",
        "vimeo.com": "vimeo",
        "rutube.ru": "rutube",
    }
    if host in known:
        return known[host]
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else host


def _build_filename(published: str | None, url: str, title: str) -> str:
    if published and re.match(r"\d{4}-\d{2}-\d{2}", str(published)):
        date_part = f"[{str(published)[:10]}]"
    else:
        date_part = "[????-??-??]"

    source_part = f"[{_source_label(url)}]"

    name = re.sub(r'[\\/:*?"<>|]', "", title or "untitled").strip()
    name = name[:60].strip() or "untitled"

    return f"{date_part} {source_part} {name}"


def _already_new_format(name: str) -> bool:
    return bool(re.match(r"^\[(\d{4}-\d{2}-\d{2}|\?\?\?\?-\?\?-\?\?)\] \[", name))


def main(apply: bool) -> None:
    if not VAULT_PATH.exists():
        print(f"Vault не найден: {VAULT_PATH}")
        sys.exit(1)

    all_md = list(VAULT_PATH.rglob("*.md"))
    to_rename = [f for f in all_md if not _already_new_format(f.stem)]

    if not to_rename:
        print("Все заметки уже в новом формате.")
        return

    print(f"Заметок для переименования: {len(to_rename)}")
    if not apply:
        print("(dry run — передай --apply чтобы применить)\n")

    renamed = 0
    skipped = 0

    for path in to_rename:
        try:
            content = path.read_text(encoding="utf-8")
            parts = content.split("---", 2)
            if len(parts) < 3:
                print(f"ПРОПУСК (нет frontmatter): {path.name}")
                skipped += 1
                continue

            fm = yaml.safe_load(parts[1]) or {}
            url = fm.get("source_url", "")
            title = fm.get("title", "") or path.stem
            published = fm.get("published")

            if not url:
                print(f"ПРОПУСК (нет source_url): {path.name}")
                skipped += 1
                continue

            new_stem = _build_filename(published, url, title)
            new_path = path.parent / (new_stem + ".md")

            if new_path == path:
                skipped += 1
                continue

            print(f"{path.name}")
            print(f"  → {new_stem}.md")

            if apply:
                if new_path.exists():
                    print(f"  ! файл уже существует, пропускаю")
                    skipped += 1
                    continue
                path.rename(new_path)
                renamed += 1
            else:
                renamed += 1

        except Exception as e:
            print(f"ОШИБКА ({path.name}): {e}")
            skipped += 1

    print(f"\n{'='*50}")
    if apply:
        print(f"Переименовано: {renamed}, пропущено: {skipped}")
    else:
        print(f"Будет переименовано: {renamed}, пропущено: {skipped}")
        if renamed > 0:
            print("Запусти с --apply чтобы применить.")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(apply)
