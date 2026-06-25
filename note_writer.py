import re
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
import yaml
from config import VAULT_PATH, VAULT_FOLDERS


# Force date-like strings to be quoted in YAML so Obsidian treats them as text,
# not as date properties that auto-link to daily notes.
class _Quoted(str):
    pass

def _quoted_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

yaml.add_representer(_Quoted, _quoted_representer)


def _q(value: str | None) -> _Quoted | None:
    return _Quoted(value) if value else None


def write_note(
    url: str,
    source_type: str,
    extracted: dict,
    enriched: dict,
) -> tuple[Path, str]:
    """
    Writes or updates a note in the vault.
    Returns (path, note_id).
    """
    note_id = _make_note_id()
    today = date.today().isoformat()

    channel = extracted.get("channel") if source_type == "video" else None

    if source_type == "video":
        title = extracted.get("title") or enriched.get("title") or url
        author = enriched.get("author") or channel
    else:
        title = extracted.get("title") or enriched.get("title") or url
        author = enriched.get("author") or extracted.get("author")

    published = enriched.get("published_date") or extracted.get("published")

    frontmatter = {
        "note_id": note_id,
        "title": title,
        "source_url": url,
        "source_type": source_type,
        "author": author,
        "channel": channel,
        "published": _q(published),
        "added": _q(today),
        "schema_version": 1,
        "tags": enriched.get("tags") or [],
        "concepts": enriched.get("concepts") or [],
        "entities": enriched.get("entities") or [],
        "relevance": "high",
        "cluster": None,
    }
    if extracted.get("needs_review"):
        frontmatter["needs_review"] = True
    if extracted.get("no_subtitles"):
        frontmatter["no_subtitles"] = True

    summary = enriched.get("summary", "")
    concepts_md = "\n".join(f"- {c}" for c in (enriched.get("concepts") or []))
    instructions_md = "\n".join(f"- {s}" for s in (enriched.get("instructions") or []))
    insights_md = "\n".join(f"- {s}" for s in (enriched.get("insights") or []))
    full_text = extracted.get("text", "")

    body = _build_body(url, today, summary, concepts_md, instructions_md, insights_md, full_text, source_type, extracted)

    existing = _find_existing(url)
    if existing:
        return _update_note(existing, url, source_type, enriched, extracted, today), _read_note_id(existing)

    folder_key = enriched.get("folder", "inbox")
    folder_rel = VAULT_FOLDERS.get(folder_key, VAULT_FOLDERS["inbox"])
    folder_path = VAULT_PATH / folder_rel
    folder_path.mkdir(parents=True, exist_ok=True)

    filename = _build_filename(published, url, title) + ".md"
    path = folder_path / filename

    content = f"---\n{yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)}---\n\n{body}"
    path.write_text(content, encoding="utf-8")
    return path, note_id


def _build_body(url: str, today: str, summary: str, concepts_md: str, instructions_md: str, insights_md: str, full_text: str, source_type: str, extracted: dict) -> str:
    sections = []

    sections.append(f"## Кратко\n{summary}")
    sections.append(f"## Ключевые мысли\n{concepts_md}")

    if insights_md:
        sections.append(f"## Инсайты\n{insights_md}")

    if instructions_md:
        sections.append(f"## Инструкции\n{instructions_md}")

    sections.append(f"## Источник\n[Оригинал]({url}) · добавлено {today}")

    if source_type == "video":
        description = extracted.get("description") or ""
        if description:
            sections.append(f"## Описание видео\n\n{description}")
        if full_text:
            sections.append(f"## Расшифровка\n\n{full_text}")
    else:
        if full_text:
            sections.append(f"## Полный текст\n\n{full_text}")

    return "\n\n".join(sections) + "\n"


def _update_note(path: Path, url: str, source_type: str, enriched: dict, extracted: dict, today: str) -> Path:
    content = path.read_text(encoding="utf-8")
    fm, _ = _split_frontmatter(content)

    channel = extracted.get("channel") if source_type == "video" else None
    author = (enriched.get("author") or channel) if source_type == "video" else (enriched.get("author") or extracted.get("author"))

    for k, v in {
        "concepts": enriched.get("concepts") or [],
        "entities": enriched.get("entities") or [],
        "tags": enriched.get("tags") or [],
        "schema_version": 1,
        "author": author,
        "channel": channel,
    }.items():
        fm[k] = v

    summary = enriched.get("summary", "")
    concepts_md = "\n".join(f"- {c}" for c in (enriched.get("concepts") or []))
    instructions_md = "\n".join(f"- {s}" for s in (enriched.get("instructions") or []))
    insights_md = "\n".join(f"- {s}" for s in (enriched.get("insights") or []))
    full_text = extracted.get("text", "")
    new_body = _build_body(url, today, summary, concepts_md, instructions_md, insights_md, full_text, source_type, extracted)

    content = f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n\n{new_body}"
    path.write_text(content, encoding="utf-8")
    return path


def _find_existing(url: str) -> Path | None:
    if not VAULT_PATH.exists():
        return None
    for f in VAULT_PATH.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        if f"source_url: {url}" in text or f'source_url: "{url}"' in text:
            return f
    return None


def _read_note_id(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    _, fm = content.split("---", 2)[:2]
    data = yaml.safe_load(fm)
    return data.get("note_id", "unknown")


def _split_frontmatter(content: str) -> tuple[dict, str]:
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    body = parts[2] if len(parts) > 2 else ""
    return fm, body


def _make_note_id() -> str:
    today = date.today().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:4]
    return f"{today}-{suffix}"


def _source_label(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    # Shorter labels for known hosts
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
    # Take the second-level domain (e.g. "vc.ru" → "vc", "smashingmagazine.com" → "smashingmagazine")
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else host


def _build_filename(published: str | None, url: str, title: str) -> str:
    if published and re.match(r"\d{4}-\d{2}-\d{2}", published):
        date_part = f"[{published[:10]}]"
    else:
        date_part = "[nodate]"

    source_part = f"[{_source_label(url)}]"

    name = re.sub(r'[\\/:*?"<>|]', "", title or "untitled").strip()
    # Truncate title so total filename stays reasonable
    name = name[:60].strip()
    name = name or "untitled"

    return f"{date_part} {source_part} {name}"


def _safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "", title or "untitled")
    name = name.strip().replace(" ", "-")[:80]
    return name or "untitled"
