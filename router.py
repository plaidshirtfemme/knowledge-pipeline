from urllib.parse import urlparse
import requests
from exceptions import URLNotFoundError, UnsupportedSourceError
from config import UNSUPPORTED_VIDEO_HOSTS

KNOWN_VIDEO_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "vimeo.com", "www.vimeo.com",
    "rutube.ru", "www.rutube.ru",
    "vk.com", "www.vk.com",
}

def route(url: str) -> str:
    """Returns 'video' or 'article'. Raises URLNotFoundError or UnsupportedSourceError when appropriate."""
    host = urlparse(url).netloc.lower()

    if host in UNSUPPORTED_VIDEO_HOSTS:
        raise UnsupportedSourceError(
            f"Платформа {host} пока не поддерживается — субтитры/текст не извлекаются. "
            f"Пропускаю. Можно добавить поддержку позже через yt-dlp или отдельный экстрактор."
        )

    if host in KNOWN_VIDEO_HOSTS:
        return "video"

    content_type, status_code, html = _fetch_page(url)

    if status_code == 404:
        raise URLNotFoundError(f"URL вернул 404 — страница не существует: {url}")
    if status_code and status_code >= 400:
        raise URLNotFoundError(f"URL недоступен (HTTP {status_code}): {url}")

    if html:
        og_type = _get_og_type(html)
        if og_type:
            if og_type.startswith("video"):
                return "video"
            if og_type == "article":
                return "article"
        if _has_video_signals(html):
            return "video"

    if _yt_dlp_recognizes(url):
        return "video"

    return "article"


def _fetch_page(url: str) -> tuple[str, int | None, str | None]:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return r.headers.get("content-type", ""), r.status_code, r.text
    except Exception:
        return "", None, None


def _get_og_type(html: str) -> str | None:
    import re
    m = re.search(r'<meta[^>]+property=["\']og:type["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:type["\']', html, re.I)
    return m.group(1).strip() if m else None


def _has_video_signals(html: str) -> bool:
    # Only strong signals — og:video and twitter:player mean the page IS a video
    signals = ['property="og:video"', "property='og:video'", 'twitter:player']
    return any(s in html for s in signals)


def _yt_dlp_recognizes(url: str) -> bool:
    try:
        import yt_dlp
        ydl = yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "extract_flat": True})
        info = ydl.extract_info(url, download=False)
        # yt-dlp recognizes many pages; only trust it if it found a video extractor
        extractor = (info or {}).get("extractor", "")
        return bool(info) and extractor not in ("generic", "")
    except Exception:
        return False
