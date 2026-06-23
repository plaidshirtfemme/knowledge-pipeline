# Knowledge Pipeline

A Python automation pipeline that ingests YouTube videos and web articles into structured Markdown notes in an Obsidian vault — with AI enrichment, semantic search, and smart filing.

Built as a personal knowledge management tool; demonstrated processing **704 URLs unattended** with automatic recovery from interruptions.

## What it does

1. **Ingests** a URL (YouTube video or article)
2. **Extracts** transcript via youtube-transcript-api / yt-dlp, or article text via trafilatura
3. **Enriches** via Claude Haiku API — generates title, summary, key concepts, actionable steps, insights, tags, and classifies into the right vault folder
4. **Writes** a structured Markdown note with YAML frontmatter into the correct Obsidian subfolder
5. **Stores** a vector embedding in DuckDB for future semantic search

## Key engineering decisions

**Prompt engineering for classification.** Claude classifies each note into one of ~40 folders using detailed descriptions and a `folder_examples.yml` file with YES/NOT examples — iterated based on real misclassifications observed in production. Few-shot examples are loaded dynamically per call.

**Resilient YouTube extraction.** YouTube aggressively rate-limits VPN IPs. Solved with a fallback chain: youtube-transcript-api (primary) → yt-dlp with Node.js n-challenge solving → description-only note with `needs_review: true` flag. IpBlocked exception surfaces a clear actionable message instead of crashing.

**Idempotent batch processing.** `--batch urls.txt --chunk-size 20 --pause 10` processes hundreds of URLs across hours. Already-processed URLs are skipped via `source_url` lookup in frontmatter — safe to restart after any interruption, including sleep or crash.

**Re-enrichment without re-ingestion.** `reenrich.py` re-runs Claude enrichment on existing notes to update classification, tags, and text fields — without re-fetching the source. Supports `--folder KEY` to target one folder and `--limit N` for testing.

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
source_type: youtube
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
- **Anthropic Claude Haiku** — AI enrichment (structured JSON extraction from unstructured text)
- **youtube-transcript-api + yt-dlp** — YouTube subtitle extraction with fallback chain
- **trafilatura** — article text extraction
- **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) — multilingual embeddings
- **DuckDB** — local vector store
- **PyYAML** — Obsidian-compatible frontmatter generation

## Project structure

```
knowledge-pipeline/
├── ingest.py              # CLI orchestrator, batch processing, logging
├── router.py              # URL type detection (youtube / article)
├── enrich.py              # Claude API enrichment, prompt engineering
├── note_writer.py         # Markdown + frontmatter generation, vault filing
├── store.py               # DuckDB vector storage
├── config.py              # Vault folder taxonomy (~40 folders), settings
├── extractors/
│   ├── video.py           # Transcript extraction with fallback chain (YouTube, Vimeo, Rutube, VK)
│   └── article.py         # Web article extraction (detects embedded videos, counts them)
├── folder_examples.yml    # Few-shot YES/NOT examples for Claude classification
├── reenrich.py            # Re-classify existing notes with updated prompts
├── fix_tags.py            # Normalize tags across vault
├── analyze_tags.py        # Tag distribution analysis
├── dashboard.py           # Streamlit dashboard: folders, tags, timeline, review queue
└── logs/                  # Per-run logs + ok/failed URL reports (gitignored)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and VAULT_PATH in .env
```

## Usage

```bash
# Single URL
python ingest.py https://youtube.com/watch?v=...

# Batch from file
python ingest.py --batch urls.txt --chunk-size 20 --pause 10

# Re-enrich existing notes (dry run first)
python reenrich.py --limit 5
python reenrich.py --apply

# Run tests
python -m pytest tests/

# Launch dashboard
streamlit run dashboard.py
```
