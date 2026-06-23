import sys
import time
import random
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from router import route
from extractors import article, video
from enrich import enrich
from note_writer import write_note, _find_existing
from store import save
from exceptions import VideoTooLongError, IPBlockedError, NoTextError, URLNotFoundError, UnsupportedSourceError

# ── Logging setup ────────────────────────────────────────────────────────────

def _setup_logging() -> Path:
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M')}_log.txt"

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    return log_path


def log(msg: str) -> None:
    logging.info(msg)


# ── Error categories ──────────────────────────────────────────────────────────

ERR_TOO_LONG    = "too_long"
ERR_NO_SUBS     = "no_subtitles"
ERR_IP_BLOCK    = "ip_block"
ERR_PRIVATE     = "private_video"
ERR_NO_TEXT     = "no_text"
ERR_JSON        = "json_error"
ERR_NOT_FOUND   = "not_found"
ERR_UNSUPPORTED = "unsupported"
ERR_OTHER       = "other"

error_counts: dict[str, list[str]] = defaultdict(list)

# (url, title) for reporting
ok_items:     list[tuple[str, str]] = []
failed_items: list[tuple[str, str, str]] = []  # (url, title, category)
embedded_video_urls_found: list[tuple[str, int]] = []  # (article_url, video_count)


def _categorize_error(exc: Exception) -> str:
    if isinstance(exc, VideoTooLongError):
        return ERR_TOO_LONG
    if isinstance(exc, IPBlockedError):
        return ERR_IP_BLOCK
    if isinstance(exc, NoTextError):
        return ERR_NO_TEXT
    if isinstance(exc, URLNotFoundError):
        return ERR_NOT_FOUND
    if isinstance(exc, UnsupportedSourceError):
        return ERR_UNSUPPORTED
    msg = str(exc).lower()
    if "субтитры недоступны" in msg or "notranscriptfound" in msg or "transcriptsdisabled" in msg:
        return ERR_NO_SUBS
    if "private" in msg or "приватное" in msg:
        return ERR_PRIVATE
    if "expecting" in msg or "unterminated" in msg or "delimiter" in msg:
        return ERR_JSON
    return ERR_OTHER


# ── Core processing ───────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}с"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}м {s}с"
    h, m = divmod(m, 60)
    return f"{h}ч {m}м {s}с"


def run(url: str) -> tuple:
    """Process one URL. Returns ("ok", title), ("skipped", title), or ("error", title, msg)."""
    t_start = time.monotonic()

    # Skip if already processed (unless needs_review)
    existing = _find_existing(url)
    if existing:
        content = existing.read_text(encoding="utf-8")
        if "needs_review: true" not in content:
            # Extract title from existing note filename for reporting
            title = existing.stem
            log(f"  → уже есть: {existing.name}, пропускаю")
            return "skipped", title

    hint_title = None
    try:
        log(f"\n─── {url}")

        log(f"[1/5] Роутер: определяю тип...")
        source_type = route(url)
        log(f"      → {source_type}")

        log(f"[2/5] Извлечение текста...")
        if source_type == "video":
            extracted = video.extract(url)
        else:
            extracted = article.extract(url)
            # Note if the article page contains embedded videos we don't process
            if extracted.get("embedded_video_count", 0) > 0:
                n = extracted["embedded_video_count"]
                log(f"      ℹ статья содержит {n} встроенных видео — они не обрабатываются (только текст статьи)")
                embedded_video_urls_found.append((url, n))

        hint_title = extracted.get("title") or url

        text = extracted.get("text", "")
        if not text.strip():
            if source_type == "youtube" and extracted.get("description"):
                extracted["text"] = ""
                extracted["needs_review"] = True
                log(f"      ⚠ субтитры недоступны, создаём заметку только по описанию")
            else:
                log(f"ОШИБКА: текст не извлечён.")
                return "error", hint_title, "текст не извлечён"

        if extracted.get("needs_review"):
            log("      ⚠ мало текста — заметка будет помечена needs_review")
        else:
            log(f"      → {len(text)} символов")

        log(f"[3/5] Обогащение через Claude...")
        enrich_text = text or extracted.get("description", "")
        enriched = enrich(enrich_text, hint_title=hint_title)
        usage = enriched.pop("_usage", {})
        log(f"      → папка: {enriched.get('folder')} | теги: {enriched.get('tags')} | токены: {usage.get('input_tokens', 0)}→{usage.get('output_tokens', 0)}")

        title = enriched.get("title") or hint_title

        log(f"[4/5] Запись заметки в vault...")
        path, note_id = write_note(url, source_type, extracted, enriched)
        log(f"      → {path}")

        log(f"[5/5] Сохранение в БД (эмбеддинг)...")
        save(
            note_id=note_id,
            url=url,
            source_type=source_type,
            published=enriched.get("published_date") or extracted.get("published"),
            entities=enriched.get("entities") or [],
            text=enrich_text,
        )

        elapsed = time.monotonic() - t_start
        log(f"ГОТОВО за {_fmt_duration(elapsed)}: {title}")
        return "ok", title, usage

    except Exception as e:
        elapsed = time.monotonic() - t_start
        log(f"ОШИБКА за {_fmt_duration(elapsed)}: {e}")
        return "error", hint_title or url, e


# ── Batch ─────────────────────────────────────────────────────────────────────

def expand_playlist(url: str) -> list[str]:
    """If URL is a playlist or channel, return list of video URLs. Otherwise return [url]."""
    try:
        import yt_dlp
        ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True})
        info = ydl.extract_info(url, download=False)
        if info and info.get("_type") in ("playlist", "channel"):
            entries = info.get("entries") or []
            urls = []
            for e in entries:
                if not e:
                    continue
                video_url = e.get("webpage_url") or e.get("url")
                if not video_url or not video_url.startswith("http"):
                    vid_id = e.get("id")
                    if vid_id:
                        video_url = f"https://www.youtube.com/watch?v={vid_id}"
                if video_url and video_url.startswith("http"):
                    urls.append(video_url)
            log(f"Плейлист: {len(urls)} видео")
            return urls
    except Exception as e:
        log(f"Ошибка при разборе плейлиста: {e}")
    return [url]


def run_batch(urls: list[str], chunk_size: int = 100, pause_minutes: int = 15) -> None:
    total = len(urls)
    started_at = datetime.now()
    log(f"\nСтарт: {started_at.strftime('%d.%m.%Y %H:%M:%S')} · всего URL: {total}")
    if chunk_size < total:
        chunks = (total + chunk_size - 1) // chunk_size
        log(f"Режим порций: {chunks} порции по ~{chunk_size} видео, пауза {pause_minutes} мин между ними")

    t_batch = time.monotonic()
    ok = 0
    skipped = 0
    active_seconds = 0.0
    pause_seconds = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    for i, url in enumerate(urls, 1):
        log(f"\n[{i}/{total}]")
        t_url = time.monotonic()
        result = run(url)
        active_seconds += time.monotonic() - t_url

        status = result[0]
        title = result[1] if len(result) > 1 else url

        if status == "ok":
            ok += 1
            ok_items.append((url, title))
            usage = result[2] if len(result) > 2 else {}
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
        elif status == "skipped":
            skipped += 1
            ok_items.append((url, title))
        elif status == "error":
            exc = result[2] if len(result) > 2 else Exception()
            cat = _categorize_error(exc)
            error_counts[cat].append(url)
            failed_items.append((url, title, cat))
        else:
            error_counts[ERR_NO_TEXT].append(url)
            failed_items.append((url, url, ERR_NO_TEXT))

        # Pause between chunks to avoid YouTube IP blocking
        if i < total and i % chunk_size == 0:
            pause_sec = pause_minutes * 60
            pause_seconds += pause_sec
            resume_at = datetime.fromtimestamp(time.time() + pause_sec)
            log(f"\n{'─'*60}")
            log(f"Порция {i // chunk_size} из {(total + chunk_size - 1) // chunk_size} завершена.")
            log(f"Пауза {pause_minutes} мин. чтобы не словить IP-блок YouTube.")
            log(f"Продолжение в {resume_at.strftime('%H:%M:%S')} ...")
            log(f"{'─'*60}")
            for remaining in range(pause_sec, 0, -30):
                time.sleep(30)
                log(f"  ещё {_fmt_duration(remaining - 30)}...")
            log("Продолжаю...")
        elif i < total:
            delay = random.uniform(2, 5)
            pause_seconds += delay
            time.sleep(delay)

    elapsed = time.monotonic() - t_batch
    stamp = started_at.strftime("%Y-%m-%d_%H-%M")
    logs_dir = Path(__file__).parent / "logs"
    _write_url_report(logs_dir / f"{stamp}_ok.txt", ok_items, columns=("URL", "Название"))
    _write_url_report(logs_dir / f"{stamp}_failed.txt", failed_items, columns=("URL", "Название", "Причина"))
    _print_summary(started_at, elapsed, active_seconds, pause_seconds, ok, skipped, total, total_input_tokens, total_output_tokens)


def _write_url_report(path: Path, rows: list[tuple], columns: tuple) -> None:
    if not rows:
        return
    # Calculate column widths
    col_widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    url_col = min(col_widths[0], 80)  # cap URL column width

    def fmt_row(row):
        parts = []
        for i, cell in enumerate(row):
            w = url_col if i == 0 else col_widths[i]
            parts.append(str(cell).ljust(w))
        return "  ".join(parts)

    header = fmt_row(columns)
    separator = "  ".join("-" * (url_col if i == 0 else col_widths[i]) for i in range(len(columns)))

    lines = [header, separator]
    for row in rows:
        lines.append(fmt_row(row))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"  → {path.name} ({len(rows)} записей)")


def _print_summary(started_at: datetime, elapsed: float, active_seconds: float, pause_seconds: float, ok: int, skipped: int, total: int, input_tokens: int = 0, output_tokens: int = 0) -> None:
    err_total = sum(len(v) for v in error_counts.values())

    log(f"\n{'='*60}")
    log(f"Старт:    {started_at.strftime('%d.%m.%Y %H:%M:%S')}")
    log(f"Финиш:    {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    log(f"Время wall-clock:   {_fmt_duration(elapsed)}")
    log(f"  — активная обработка: {_fmt_duration(active_seconds)}")
    log(f"  — запланированные паузы: {_fmt_duration(pause_seconds)}")
    log(f"{'─'*60}")
    log(f"Всего URL:            {total}")
    log(f"✓ Успешно обработано: {ok}")
    log(f"→ Пропущено (уже есть): {skipped}")
    log(f"✗ Ошибок:             {err_total}")

    if error_counts:
        log(f"{'─'*60}")
        log("Разбивка ошибок:")
        labels = {
            ERR_TOO_LONG:    "Видео > 40 минут",
            ERR_NO_SUBS:     "Нет субтитров",
            ERR_IP_BLOCK:    "IP-блок YouTube",
            ERR_PRIVATE:     "Приватное видео",
            ERR_NO_TEXT:     "Не удалось извлечь текст",
            ERR_JSON:        "Ошибка JSON от Claude",
            ERR_NOT_FOUND:   "URL не найден (404)",
            ERR_UNSUPPORTED: "Неподдерживаемая платформа",
            ERR_OTHER:       "Прочие ошибки",
        }
        for cat, urls_list in sorted(error_counts.items(), key=lambda x: -len(x[1])):
            label = labels.get(cat, cat)
            log(f"  {label}: {len(urls_list)}")
        log(f"{'─'*60}")
        log("URL с ошибками:")
        for cat, urls_list in error_counts.items():
            if cat in (ERR_TOO_LONG,):
                continue  # не печатаем — их слишком много и они ожидаемы
            for u in urls_list:
                log(f"  [{cat}] {u}")
    if input_tokens or output_tokens:
        # Claude Haiku pricing: $0.80/M input, $4.00/M output (as of 2025)
        cost_usd = (input_tokens / 1_000_000 * 0.80) + (output_tokens / 1_000_000 * 4.00)
        log(f"{'─'*60}")
        log(f"Токены Claude: {input_tokens:,} input + {output_tokens:,} output ≈ ${cost_usd:.4f}")

    if embedded_video_urls_found:
        total_embedded = sum(n for _, n in embedded_video_urls_found)
        log(f"{'─'*60}")
        log(f"ℹ Статьи с встроенными видео (видео не обрабатывались): {len(embedded_video_urls_found)} статей, {total_embedded} видео")
    log(f"{'='*60}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="URL или --batch")
    parser.add_argument("--batch", metavar="FILE", help="Файл со списком URL")
    parser.add_argument("--chunk-size", type=int, default=100,
                        help="Кол-во видео в одной порции (default: 100)")
    parser.add_argument("--pause", type=int, default=15,
                        help="Пауза между порциями в минутах (default: 15)")
    args = parser.parse_args()

    log_path = _setup_logging()
    log(f"Лог сохраняется в: {log_path}")

    if args.batch:
        try:
            with open(args.batch, encoding="utf-16") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except UnicodeDecodeError:
            with open(args.batch, encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        run_batch(urls, chunk_size=args.chunk_size, pause_minutes=args.pause)
    elif args.target:
        urls = expand_playlist(args.target)
        if len(urls) > 1:
            run_batch(urls, chunk_size=args.chunk_size, pause_minutes=args.pause)
        else:
            run(args.target)
    else:
        parser.print_help()
        sys.exit(1)
