🇷🇺 [Русская версия](README_RU.md)

# Knowledge Pipeline

A Python automation pipeline that ingests YouTube videos and web articles into structured Markdown notes in an Obsidian vault — with AI enrichment, a vector database for semantic search, and smart filing.

Built as a personal knowledge management tool; demonstrated processing **704 URLs unattended** with automatic recovery from interruptions.

## What it does

1. **Ingests** a URL (YouTube video or article; Vimeo / Rutube / VK — experimental, via yt-dlp fallback)
2. **Routes** by source type (video / article) — router.py
3. **Extracts** transcript via youtube-transcript-api / yt-dlp, or article text via trafilatura
4. **Enriches** via Claude Haiku API — model returns structured JSON:
   - `summary` — brief synopsis
   - `concepts` — key ideas (foundation for semantic search)
   - `instructions` — action steps (for tutorial content)
   - `insights` — ideas worth special attention
   - `entities` — specific people, tools, algorithms (for filtering and graphs)
   - `tags` — tags (for filtering and graphs)
   - `folder` — model **determines** the right vault folder (~50 folders)
5. **Writes** a structured Markdown note with YAML frontmatter into the correct Obsidian subfolder
6. **Stores** a vector embedding in DuckDB — vector database for future semantic search

## Key engineering decisions

**Prompt engineering for classification.** Claude classifies each note into one of ~50 folders using detailed descriptions and a `folder_examples.yml` file with classification examples (YES/NOT) — iterated based on real misclassifications observed in production. Examples are loaded dynamically per call.

**Resilient YouTube extraction.** YouTube aggressively rate-limits VPN IPs (especially from Russia). Solved with a fallback chain: youtube-transcript-api (primary) → yt-dlp (subtitle download) → if no text at all, note is built from description only and flagged `needs_review: true` for manual review. The `IpBlocked` exception surfaces a clear actionable message instead of crashing. cookies.txt is technically optional, but in practice (especially from Russia via VPN) without it YouTube blocks almost all requests — needed for real batches.

**Idempotent batch processing.** `--batch urls.txt --chunk-size 20 --pause 10` processes hundreds of URLs across hours. Already-processed URLs are skipped via `source_url` lookup in frontmatter — safe to restart after any interruption, including sleep or crash.

**Parallel article processing.** `--parallel N` runs articles through `ThreadPoolExecutor` (3–5 threads recommended). Videos always run sequentially — YouTube blocks parallel requests from one IP. Results are written thread-safe via a shared lock.

**Re-enrichment without re-ingestion.** `scripts/reenrich.py` re-runs Claude enrichment on existing notes to update classification, tags, and text fields — without re-fetching the source. Supports `--folder KEY` to target one folder and `--limit N` for testing.

## Scale

Processed **704 YouTube URLs** in a single unattended batch run:
- ✓ 258 new notes created
- → 97 skipped (already existed — idempotency working)
- ✗ 205 skipped (videos > 40 min, configurable limit)
- ✗ 96 IP blocks (VPN rate limiting, handled gracefully with structured logs)
- ✗ 48 no extractable text (no subtitles + no description)

## Output example

Each note is a Markdown file with YAML frontmatter:

```yaml
---
note_id: 20260618-4508
title: 'UI паттерны: стандартизированные элементы интерфейса'
source_url: https://www.youtube.com/watch?v=4mVJvM1gqHs
source_type: video
published: "2019-02-27"
tags:
- ux_ui_design
- ui_patterns
- interaction_design
- dark_patterns
---

## Кратко
Введение в UI паттерны — стандартизированные решения типовых задач проектирования интерфейсов.

## Ключевые мысли
- UI паттерн — переиспользуемое решение для типовой задачи...

## Инсайты
- Dark patterns существуют потому что работают краткосрочно...
```

## Stack

- **Python 3.13** — core pipeline
- **router.py** — URL type detection (video / article)
- **trafilatura** — article text extraction
- **youtube-transcript-api + yt-dlp** — video subtitle extraction with fallback chain
- **Anthropic Claude Haiku** — AI enrichment (structured JSON extraction from unstructured text)
- **PyYAML** — Obsidian-compatible frontmatter generation
- **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) — multilingual embeddings
- **DuckDB** — local vector store

## Project structure

```
knowledge-pipeline/
├── ingest.py              # CLI orchestrator, batch processing, logging
├── router.py              # URL type detection (video / article)
├── extractors/
│   ├── video.py           # Transcript extraction with fallback chain (YouTube; Vimeo/Rutube/VK — experimental)
│   └── article.py         # Web article text extraction
├── enrich.py              # Claude API enrichment, prompt engineering
├── note_writer.py         # Markdown + frontmatter generation, vault filing
├── store.py               # DuckDB vector storage
├── config.py              # Vault folder taxonomy (~50 folders), settings
├── exceptions.py          # Typed exceptions (IPBlockedError, VideoTooLongError, etc.)
├── folder_examples.yml    # Classification examples (YES/NOT) for Claude folder selection
├── scripts/
│   ├── reenrich.py        # Re-classify existing notes with updated prompts
│   ├── fix_tags.py        # Normalize tags across vault
│   ├── analyze_tags.py    # Tag distribution analysis
│   ├── migrate_filenames.py   # Rename notes to [YYYY-MM-DD] [source] format
│   └── update_dates.py    # Fill in missing publication dates
├── tests/
│   ├── test_enrich.py
│   └── test_note_writer.py
├── requirements.txt
├── .env.example
└── logs/                  # Per-run logs + ok/failed URL reports (gitignored)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and VAULT_PATH in .env
```

### cookies.txt (for YouTube)

YouTube blocks requests from VPN IPs. To mitigate this, place a `cookies.txt` file in the project root in Netscape format (exported via a browser extension such as "Get cookies.txt" while logged into YouTube). The file is in `.gitignore` — do not commit it. Technically optional, but in practice without it a batch will hit IP blocks on almost every request.

### urls.txt (for batch processing)

A list of URLs to process — one per line:

```
https://www.youtube.com/watch?v=XXXXXXXXXXX
https://www.youtube.com/watch?v=YYYYYYYYYYY
https://habr.com/ru/articles/123456/
```

## Usage

```bash
# Single URL
python ingest.py https://youtube.com/watch?v=...

# Batch from file (sequential)
python ingest.py --batch urls.txt --chunk-size 20 --pause 10

# Batch with parallel article processing (3-5 threads recommended)
python ingest.py --batch urls.txt --chunk-size 20 --pause 10 --parallel 4

# Re-enrich existing notes (dry run first)
python scripts/reenrich.py --limit 5
python scripts/reenrich.py --apply

# Run tests
python -m pytest tests/
```

## Roadmap

- Semantic search over notes (on top of the already-built DuckDB vector store)
- Note clustering and visual connection graph between materials
- Explicit support for Vimeo / Rutube / VK (currently experimental via yt-dlp)
- Chunking long videos (> 40 min) instead of the current skip
