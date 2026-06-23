from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, IpBlocked
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import re
import tempfile
import os
from exceptions import VideoTooLongError, IPBlockedError
from config import MAX_DURATION_MINUTES

MAX_DURATION_SECONDS = MAX_DURATION_MINUTES * 60

# cookies.txt in project root — optional, reduces IP blocking
_COOKIES_PATH = Path(__file__).parent.parent / "cookies.txt"


def _cookies_file() -> str | None:
    return str(_COOKIES_PATH) if _COOKIES_PATH.exists() else None


def _ydl_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True}
    cookies = _cookies_file()
    if cookies:
        opts["cookiefile"] = cookies
    return opts


def extract(url: str) -> dict:
    video_id = _get_video_id(url)
    if not video_id:
        raise ValueError(f"Не удалось извлечь video_id из {url}")

    title, channel, published, description, duration = _get_metadata(url)

    if duration and duration > MAX_DURATION_SECONDS:
        mins = duration // 60
        raise VideoTooLongError(f"Видео длиннее {MAX_DURATION_MINUTES} минут ({mins} мин) — пропускаю: {title or url}")

    # Method 1: youtube-transcript-api (hits /api/timedtext — different rate limits than CDN)
    try:
        transcript = _get_transcript_api(video_id)
        return {
            "title": title,
            "channel": channel,
            "published": published,
            "description": description,
            "text": transcript,
            "needs_review": False,
            "fallback_used": False,
        }
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    except IpBlocked as e:
        raise IPBlockedError(
            "YouTube заблокировал IP (IpBlocked). Смени сервер VPN и обнови cookies.txt."
        ) from e
    except Exception as e:
        err = str(e)
        if "429" in err or "Too Many Requests" in err:
            raise IPBlockedError(
                "YouTube заблокировал запрос (IP-блок). Смени сервер VPN или подожди 30-60 мин."
            ) from e
        # Other errors — try yt-dlp next

    # Method 2: yt-dlp subtitle download
    try:
        transcript = _get_transcript_ytdlp(url)
        return {
            "title": title,
            "channel": channel,
            "published": published,
            "description": description,
            "text": transcript,
            "needs_review": False,
            "fallback_used": False,
        }
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    except Exception as e:
        err = str(e)
        if "no subtitles" in err.lower() or "no transcript" in err.lower():
            pass
        elif "HTTP Error 429" in err or "429" in err or "blocked" in err.lower():
            raise IPBlockedError(
                "YouTube заблокировал запрос (IP-блок). Смени сервер VPN или подожди 30-60 мин."
            ) from e
        else:
            raise RuntimeError(f"Ошибка получения субтитров: {type(e).__name__}: {e}") from e

    # No subtitles found — return metadata only, ingest.py will create note from description
    return {
        "title": title,
        "channel": channel,
        "published": published,
        "description": description,
        "text": "",
        "needs_review": True,
        "no_subtitles": True,
    }


def _get_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.search(r"/embed/([^/?]+)", parsed.path)
    return m.group(1) if m else None


def _get_transcript_api(video_id: str) -> str:
    """Primary method: youtube-transcript-api via /api/timedtext endpoint."""
    yta = YouTubeTranscriptApi()
    for langs in (["ru"], ["en"], None):
        try:
            if langs:
                fetched = yta.fetch(video_id, languages=langs)
            else:
                fetched = yta.fetch(video_id)
            return " ".join(s.text for s in fetched if s.text.strip())
        except NoTranscriptFound:
            continue
    raise NoTranscriptFound(video_id, [], {})


def _get_transcript_ytdlp(url: str) -> str:
    """Download subtitles via yt-dlp CLI subprocess — avoids Python API format-processing issues."""
    import subprocess
    import sys

    with tempfile.TemporaryDirectory() as tmp:
        outtmpl = os.path.join(tmp, "sub")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", "ru,en",
            "--sub-format", "vtt",
            "--skip-download",
            "--no-check-formats",
            "--quiet",
            "--no-warnings",
            "-o", outtmpl,
        ]
        cookies = _cookies_file()
        if cookies:
            cmd += ["--cookies", cookies]
        cmd.append(url)

        subprocess.run(cmd, check=False, capture_output=True)

        sub_files = list(Path(tmp).glob("*.vtt"))
        if not sub_files:
            raise NoTranscriptFound([], [], {})

        # Prefer Russian, then English
        chosen = None
        for lang in ("ru", "en"):
            for f in sub_files:
                if f".{lang}." in f.name or f"-{lang}." in f.name:
                    chosen = f
                    break
            if chosen:
                break
        if not chosen:
            chosen = sub_files[0]

        return _parse_vtt(chosen.read_text(encoding="utf-8"))


def _parse_json3(text: str) -> str:
    import json
    data = json.loads(text)
    words = []
    for event in data.get("events", []):
        for seg in event.get("segs", []):
            w = seg.get("utf8", "").strip()
            if w and w != "\n":
                words.append(w)
    return " ".join(words)


def _parse_vtt(vtt: str) -> str:
    """Extract plain text from WebVTT subtitle file."""
    lines = []
    for line in vtt.splitlines():
        line = line.strip()
        # Skip header, timestamps, empty lines, and NOTE blocks
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE") or "-->" in line:
            continue
        # Skip lines that are only numbers (cue identifiers)
        if line.isdigit():
            continue
        # Remove VTT tags like <00:00:01.000>, <c>, </c>
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            lines.append(line)

    # Deduplicate consecutive identical lines (VTT often repeats)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return " ".join(deduped)


def _get_metadata(url: str) -> tuple[str | None, str | None, str | None, str | None, int | None]:
    try:
        import yt_dlp
        ydl = yt_dlp.YoutubeDL(_ydl_opts())
        info = ydl.extract_info(url, download=False, process=False)
        published = None
        if info.get("upload_date"):
            d = info["upload_date"]
            published = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        return info.get("title"), info.get("uploader"), published, info.get("description"), info.get("duration")
    except Exception:
        return None, None, None, None, None


def _whisper_fallback(url: str) -> str:
    import yt_dlp
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.mp3")
        ydl_opts = _ydl_opts() | {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path + ".mp3", beam_size=5)
        return " ".join(s.text for s in segments)
