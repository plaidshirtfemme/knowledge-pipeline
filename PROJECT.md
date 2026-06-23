# Knowledge Pipeline

A Python automation pipeline that ingests YouTube videos and web articles into structured Markdown notes in an Obsidian vault — with AI enrichment, semantic search, and smart filing.

## What it does

1. **Ingests** a URL (YouTube video or article)
2. **Extracts** transcript via youtube-transcript-api / yt-dlp, or article text via trafilatura
3. **Enriches** via Claude Haiku API — generates title, summary, key concepts, actionable steps, insights, tags, and classifies into the right folder
4. **Writes** a structured Markdown note into the correct Obsidian vault subfolder
5. **Stores** a vector embedding in DuckDB for future semantic search

## Stack

- **Python 3.13** — core pipeline
- **Anthropic Claude Haiku** — AI enrichment (JSON extraction from unstructured text)
- **youtube-transcript-api + yt-dlp** — YouTube subtitle extraction with Node.js n-challenge solving
- **trafilatura** — article text extraction
- **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) — multilingual embeddings
- **DuckDB** — local vector store
- **PyYAML** — Obsidian-compatible frontmatter generation

## Key engineering decisions

**Prompt engineering for classification.** Claude classifies each note into one of ~40 folders using detailed descriptions and a `folder_examples.yml` file with YES/NOT examples — iterated based on real misclassifications observed in production.

**Resilient YouTube extraction.** YouTube aggressively rate-limits VPN IPs (relevant: working from Russia). Solved with: cookies.txt auth, Node.js runtime for n-challenge solving, fallback chain (transcript API → yt-dlp → description-only note), IpBlocked exception handling, and chunked batch processing with configurable pauses between chunks.

**Batch processing with recovery.** `--batch urls.txt --chunk-size 20 --pause 10` processes 700+ URLs across 18+ hours. Already-processed URLs are skipped automatically via `source_url` lookup in frontmatter — safe to restart after interruption.

**Idempotent note writing.** Each note carries a `source_url` in YAML frontmatter. On re-run, the pipeline detects existing notes and skips them — unless flagged `needs_review: true`.

## Scale

Processed **704 YouTube URLs** in a single batch run:
- ✓ 258 new notes created
- → 97 skipped (already existed)
- ✗ 205 skipped (videos > 40 min, temporary limit)
- ✗ 96 IP blocks (VPN rate limiting, handled gracefully)
- ✗ 48 no extractable text (no subtitles + no description)

Total runtime: **18 hours 25 minutes** unattended, with automatic pauses and structured logs.

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

## Project structure

```
knowledge-pipeline/
├── ingest.py          # CLI orchestrator, batch processing, logging
├── router.py          # URL type detection (youtube / article)
├── enrich.py          # Claude API enrichment, prompt engineering
├── note_writer.py     # Markdown + frontmatter generation, vault filing
├── store.py           # DuckDB vector storage
├── config.py          # Vault folder taxonomy (~40 folders)
├── extractors/
│   ├── youtube.py     # Transcript extraction with fallback chain
│   └── article.py     # Web article extraction
├── folder_examples.yml  # Few-shot examples for Claude classification
├── reenrich.py        # Re-classify existing notes with updated prompts
├── fix_tags.py        # Normalize tags across vault
├── analyze_tags.py    # Tag distribution analysis
└── logs/              # Per-run logs + ok/failed URL reports
```
