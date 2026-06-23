import re
import json
import trafilatura
import requests
from urllib.parse import urljoin
from markdownify import markdownify as md


def extract(url: str) -> dict:
    downloaded = trafilatura.fetch_url(url)

    if downloaded:
        preprocessed = _preprocess_html(downloaded, url)
        result_html = trafilatura.extract(
            preprocessed,
            output_format="html",
            include_images=True,
            include_links=True,
            favor_recall=True,
        )
        if result_html and len(result_html.strip()) > 200:
            meta = {}
            result_meta = trafilatura.extract(downloaded, output_format="json")
            if result_meta:
                meta = json.loads(result_meta)

            html_abs = _fix_graphic_tags(_make_urls_absolute_html(result_html, url))
            text = md(html_abs, heading_style="ATX", bullets="-").strip()
            text = _inject_missing_svgs(text, preprocessed, result_html)

            author = meta.get("author") or meta.get("authors")
            if isinstance(author, list):
                author = ", ".join(author)
            author = author or _find_author(downloaded)

            title = meta.get("title") or _og_value(downloaded, "og:title") or _h1(result_html)
            published = meta.get("date") or _og_date(downloaded)

            embedded_videos = _count_embedded_videos(downloaded)
            return {
                "title": title,
                "author": author,
                "published": published,
                "text": text,
                "needs_review": False,
                "embedded_video_count": embedded_videos,
            }

    # Fallback: Jina Reader
    raw = _jina_fallback(url)
    text = _strip_jina_headers(raw)
    return {
        "title": _og_value(downloaded or "", "og:title"),
        "author": _find_author(downloaded or ""),
        "published": _og_date(downloaded or ""),
        "text": text,
        "needs_review": len(text.strip()) < 200,
        "embedded_video_count": _count_embedded_videos(downloaded or ""),
    }


def _preprocess_html(html: str, base_url: str) -> str:
    """
    Fix issues before trafilatura extraction:
    1. Images inside <div class="figure"> are skipped by trafilatura — wrap them in <p>
    2. Make all img src absolute so trafilatura preserves the correct URL
    """
    # Convert <div class="figure"><img src="..."></div> → <p><img src="..."/></p>
    def unwrap_figure(m):
        inner = m.group(1)
        imgs = re.findall(r'<img[^>]+>', inner, re.I)
        if not imgs:
            return m.group(0)
        return "".join(f"<p>{img}</p>" for img in imgs)

    # class = 'figure ' — note spaces around = and possible trailing space in value
    html = re.sub(
        r'<div[^>]+class\s*=\s*["\'][^"\']*figure[^"\']*["\'][^>]*>(.*?)</div>',
        unwrap_figure,
        html,
        flags=re.I | re.DOTALL,
    )

    # Make img src absolute before trafilatura so it recognises the image
    def fix_src(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "//", "data:")):
            return m.group(0)
        return f'src="{urljoin(base_url, src)}"'

    html = re.sub(r'src\s*=\s*["\']([^"\']+)["\']', fix_src, html, flags=re.I)
    return html


def _make_urls_absolute_html(html: str, base_url: str) -> str:
    def fix_src(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "//", "data:")):
            return m.group(0)
        return f'src="{urljoin(base_url, src)}"'

    html = re.sub(r'src\s*=\s*["\']([^"\']+)["\']', fix_src, html, flags=re.I)
    return html


def _inject_missing_svgs(markdown: str, preprocessed_html: str, result_html: str) -> str:
    """Trafilatura drops SVG images. Find them in the preprocessed HTML and insert near the right position."""
    already_included = set(re.findall(r'src="([^"]+)"', result_html, re.I))

    # Split preprocessed HTML into <p> blocks to find SVGs with context
    blocks = re.split(r'(?=<p[\s>])', preprocessed_html, flags=re.I)
    for i, block in enumerate(blocks):
        img_m = re.search(r'<img[^>]+src="([^"]+\.svg[^"]*)"', block, re.I)
        if not img_m:
            continue
        svg_url = img_m.group(1)
        if svg_url in already_included:
            continue

        # Find the closest preceding paragraph with enough text to use as anchor
        anchor = None
        for j in range(i - 1, max(0, i - 6), -1):
            text = re.sub(r'<[^>]+>', '', blocks[j]).strip()
            if len(text) > 20:
                anchor = text[:100]
                break

        img_md = f"![]({svg_url})"
        if anchor and anchor in markdown:
            markdown = markdown.replace(anchor, anchor + f"\n\n{img_md}", 1)
        else:
            markdown += f"\n\n{img_md}"

    return markdown


def _fix_graphic_tags(html: str) -> str:
    """trafilatura outputs <graphic src="..."/> instead of <img src="...">, markdownify ignores it."""
    return re.sub(r'<graphic\s+src=(["\'])([^"\']+)\1\s*/?>', r'<img src=\1\2\1/>', html)


def _find_author(html: str) -> str | None:
    patterns = [
        # Meta tags
        r'name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\'][^>]+name=["\']author["\']',
        r'property=["\']og:article:author["\'][^>]+content=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\'][^>]+property=["\']og:article:author["\']',
        # Schema.org JSON-LD
        r'"author"\s*:\s*\{\s*[^}]*"name"\s*:\s*"([^"]+)"',
        r'"author"\s*:\s*"([^"]+)"',
        # rel="author" on links: <a href="..." rel="author">Name</a>
        r'rel\s*=\s*["\']author["\'][^>]*>([^<]{2,80})<',
        # Common HTML patterns: <span class="author">, <div class = 'author'>
        r'class\s*=\s*["\'][^"\']*author[^"\']*["\'][^>]*>\s*([^<]{2,80})<',
        r'class\s*=\s*["\'][^"\']*byline[^"\']*["\'][^>]*>\s*([^<]{2,80})<',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            val = m.group(1).strip()
            # Skip generic/empty values
            if val and len(val) < 100 and val.lower() not in ("author", "by", ""):
                return val
    return None


def _og_value(html: str, property: str) -> str | None:
    pat = rf'property=["\'{re.escape(property)}["\'][^>]+content=["\']([^"\']+)["\']'
    m = re.search(pat, html, re.I)
    if m:
        return m.group(1).strip()
    pat2 = rf'content=["\']([^"\']+)["\'][^>]+property=["\'{re.escape(property)}["\']'
    m = re.search(pat2, html, re.I)
    return m.group(1).strip() if m else None


def _h1(html: str) -> str | None:
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.DOTALL)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else None


def _og_date(html: str) -> str | None:
    patterns = [
        r'property=["\']og:article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\'][^>]+property=["\']og:article:published_time["\']',
        r'property=["\']og:article:modified_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\'][^>]+property=["\']og:article:modified_time["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            raw = m.group(1)[:10]
            if re.match(r"\d{4}-\d{2}-\d{2}", raw):
                return raw
    return None


def _strip_jina_headers(text: str) -> str:
    if "Markdown Content:" in text:
        return text.split("Markdown Content:", 1)[1].strip()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not any(line.startswith(p) for p in ("URL Source:", "Published Time:", "Warning:", "Title:")):
            return "\n".join(lines[i:]).strip()
    return text


def _count_embedded_videos(html: str) -> int:
    """Count embedded video elements on the page (iframes, video tags, YouTube embeds)."""
    patterns = [
        r'<iframe[^>]+(?:youtube\.com/embed|vimeo\.com/video|rutube\.ru)[^>]*>',
        r'<video[^>]*>',
        r'<iframe[^>]+src=["\'][^"\']*(?:youtube|vimeo|rutube|youtu\.be)[^"\']*["\']',
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, html, re.I):
            found.add(m.group(0)[:80])
    return len(found)


def _jina_fallback(url: str) -> str:
    try:
        r = requests.get(f"https://r.jina.ai/{url}", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        return r.text
    except Exception:
        return ""
