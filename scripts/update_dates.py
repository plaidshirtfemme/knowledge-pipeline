"""
Scans vault for notes with [????-??-??] in filename,
tries to re-fetch the published date from the source URL,
then renames the file and updates only `published` in frontmatter.

Usage:
    python scripts/update_dates.py          # dry run — shows what would change
    python scripts/update_dates.py --apply  # actually rename + update
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import yaml
from config import VAULT_PATH
from note_writer import _Quoted, _q


def _read_frontmatter(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    return fm, body


def _write_frontmatter(path: Path, fm: dict, body: str) -> None:
    content = f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n{body}"
    path.write_text(content, encoding="utf-8")


def _fetch_date(url: str) -> str | None:
    """Try to get published date from the source URL."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        if "youtube" in host or "youtu.be" in host:
            return _date_from_youtube(url)
        else:
            return _date_from_article(url)
    except Exception as e:
        print(f"      ошибка при получении даты: {e}")
        return None


def _date_from_youtube(url: str) -> str | None:
    try:
        import yt_dlp
        ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
        info = ydl.extract_info(url, download=False, process=False)
        d = (info or {}).get("upload_date")
        if d:
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    except Exception:
        pass
    return None


def _date_from_article(url: str) -> str | None:
    try:
        import trafilatura, json
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            result = trafilatura.extract(downloaded, output_format="json")
            if result:
                data = json.loads(result)
                return data.get("date")
    except Exception:
        pass
    return None


def _new_filename(old_name: str, new_date: str) -> str:
    return re.sub(r"\[\?\?\?\?-\?\?-\?\?\]", f"[{new_date}]", old_name, count=1)


def main(apply: bool) -> None:
    if not VAULT_PATH.exists():
        print(f"Vault не найден: {VAULT_PATH}")
        sys.exit(1)

    candidates = [f for f in VAULT_PATH.rglob("*.md") if "[????-??-??]" in f.name]

    if not candidates:
        print("Заметок с неизвестной датой не найдено.")
        return

    print(f"Найдено заметок с [????-??-??]: {len(candidates)}")
    if not apply:
        print("(dry run — передай --apply чтобы применить изменения)\n")

    updated = 0
    skipped = 0

    for path in candidates:
        fm, body = _read_frontmatter(path)
        url = fm.get("source_url", "")
        print(f"\n{path.name}")
        print(f"  URL: {url or '(нет)'}")

        date = _fetch_date(url)
        if not date:
            print("  → дата не найдена, пропускаю")
            skipped += 1
            continue

        print(f"  → найдена дата: {date}")
        new_name = _new_filename(path.name, date)
        new_path = path.parent / new_name

        if apply:
            fm["published"] = _q(date)
            _write_frontmatter(path, fm, body)
            path.rename(new_path)
            print(f"  ✓ переименовано: {new_name}")
        else:
            print(f"  будет: {new_name}")

        updated += 1

    print(f"\n{'='*50}")
    print(f"Итого: {updated} обновятся, {skipped} без даты")
    if not apply and updated > 0:
        print("Запусти с --apply чтобы применить.")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(apply)
