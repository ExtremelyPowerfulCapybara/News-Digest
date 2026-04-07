# Architecture — The Periphery / Mexico Finance Brief

## System Overview

The newsletter pipeline is a linear, single-process Python application triggered by GitHub Actions every weekday at ~7 AM Mexico City time. There is no web server, no database, and no persistent runtime state — all state is stored in flat files (`digests/YYYY-MM-DD.json`).

```
NewsAPI ──────────────────────────────────────────────────────────────┐
Yahoo Finance ────────────────────────────────────────────────────┐   │
Open-Meteo ──────────────────────────────────────────────────┐   │   │
                                                             │   │   │
                                                         main.py (orchestrator)
                                                             │
                                             ┌───────────────┴───────────────┐
                                         scorer.py                    summarizer.py
                                       (rank/dedup)               (Claude API → JSON)
                                             │                             │
                                             └──────────┬──────────────────┘
                                                        │
                                                   storage.py
                                                (digests/YYYY-MM-DD.json)
                                                        │
                                        ┌───────────────┴───────────────┐
                                    renderer.py                pretty_renderer.py
                                  (email HTML)                  (archive HTML)
                                        │                             │
                                   delivery.py                   archive.py
                                 (Gmail SMTP)          (docs/YYYY-MM-DD.html + index.html)
                                        │                             │
                                  Subscribers                  GitHub Pages
```

---

## Module Dependency Map

```
main.py
  ├── config.py           (imported by all modules)
  ├── fetcher.py
  │     └── scraper.py
  ├── scorer.py
  ├── summarizer.py
  ├── market_data.py
  ├── storage.py
  ├── renderer.py
  ├── pretty_renderer.py
  ├── archive.py
  │     └── storage.py    (reads digests for index rebuild)
  ├── delivery.py
  ├── mock_data.py         (only in MOCK=true runs)
  └── wordcloud_gen.py     (only on Fridays)
```

`config.py` is a passive singleton — every module imports it directly. There are no circular dependencies.

---

## Data Flow

### 1. Ingestion
- `fetcher.py` calls NewsAPI for each of 7 Spanish-language topics
- Articles are filtered by domain allowlist (14 outlets) and deduplicated against the last 5 days of digest URLs
- `scraper.py` extracts full article body text using per-domain CSS selectors (BeautifulSoup), with a generic `<p>` fallback; truncates at 3,000 characters

### 2. Scoring
- `scorer.py` assigns a composite score (freshness 30%, source authority 25%, topic relevance 25%) to each article
- A greedy uniqueness filter removes near-duplicates (>60% headline word overlap)
- Returns the top 12 articles for Claude

### 3. AI Processing
- `summarizer.py` sends all 12 articles + market data + thread history to Claude in a single Spanish-language prompt
- Claude returns a structured bilingual JSON blob with: 5–7 selected stories, editor note, narrative thread, sentiment score (5–95), quote, and per-story thread tags
- On JSON parse failure, the module retries once with a repair prompt

### 4. Persistence
- `storage.py` writes `digests/YYYY-MM-DD.json` containing the full bilingual digest, raw market data, and run metadata
- This file is the canonical record of that day's issue and the source of truth for the week-in-review, sentiment timeline, and thread tracking in `archive.py`

### 5. Email Rendering
- `renderer.py` assembles a Gmail-safe HTML email using only `<table>` elements and inline styles (no CSS classes, no flexbox)
- Sections: masthead, ticker bar, secondary market dashboard, editor note, narrative thread, sentiment gauge, story blocks, FX table, quote, weekly review (Fridays), sentiment chart (Fridays), economic calendar, footer

### 6. Archive Rendering
- `pretty_renderer.py` generates a full web-quality HTML page with Google Fonts, flexbox, CSS classes, and JavaScript
- Features: bilingual toggle (ES/EN), currency base switcher (MXN/USD/BRL/EUR/CNY), market tab strip, animated sentiment gauge, word cloud embed, responsive layout

### 7. Publishing
- `delivery.py` sends both HTML and plain-text parts via Gmail SMTP to all subscribers in `subscribers.csv`
- `archive.py` saves the pretty HTML to `docs/YYYY-MM-DD.html` and rebuilds `docs/index.html`, which includes a Chart.js sentiment timeline, story count chart, thread coverage map, and client-side search

### 8. Friday Extensions
- `wordcloud_gen.py` collects all text from the current week's digests, strips accents, filters stopwords, and generates a 1200×480 PNG at `docs/wordcloud-YYYY-WNN.png`
- The week-in-review section in both renderers shows Mon–Fri story summaries and a sentiment bar chart

---

## State & Persistence

| Artifact | Location | Written by | Read by |
|---|---|---|---|
| Daily digest JSON | `digests/YYYY-MM-DD.json` | `storage.py` | `storage.py`, `archive.py`, `mock_data.py`, `wordcloud_gen.py` |
| Pretty issue HTML | `docs/YYYY-MM-DD.html` | `archive.py` | GitHub Pages (static serve) |
| Archive index | `docs/index.html` | `archive.py` | GitHub Pages (static serve) |
| Thread index | `docs/thread_index.json` | `archive.py` | `archive.py` |
| Word cloud PNG | `docs/wordcloud-YYYY-WNN.png` | `wordcloud_gen.py` | `pretty_renderer.py`, `renderer.py` |
| Subscriber list | `subscribers.csv` | GitHub Actions (from secret) | `delivery.py` |

All files under `docs/` are committed and pushed by the workflow after each run, making GitHub Pages the delivery mechanism for the archive.

---

## Operating Modes

Three boolean flags in `config.py` (set via environment variables) control behavior:

| Flag | Effect |
|---|---|
| `MOCK=true` | Skips NewsAPI + Claude; loads latest digest from `digests/` via `mock_data.py` |
| `SKIP_EMAIL=true` | Skips SMTP delivery; archive is still generated and committed |
| `FORCE_FRIDAY=true` | Forces Friday mode (word cloud + week-in-review) regardless of actual day |

These can be combined. `MOCK=true SKIP_EMAIL=true` is the standard local development mode.

---

## Extension Points

### Image / Visual Generation Layer

The cleanest integration point is between steps 3 (AI Processing) and 5 (Email Rendering):

1. `summarizer.py` already returns per-story `tag` values (`Macro`, `FX`, `México`, `Comercio`, `Tasas`, `Mercados`, `Energía`, `Política`). A category-to-prompt mapping module could translate these tags into image generation prompts.
2. The generated image URL or base64 string could be added to the digest JSON as `story.image_url` or `story.image_b64`.
3. `renderer.py` and `pretty_renderer.py` both have individual story-block render functions (`_story_block()`) that could conditionally include an `<img>` tag when that field is present.

This means no existing module needs to change its interface — the image layer slots in as an optional enrichment step before rendering, reading from and writing to the digest JSON.

**Suggested new file:** `bot/image_gen.py` — called from `main.py` after `summarizer.py`, before `renderer.py`.

### Category-to-Prompt Mapping

A natural home is `config.py` (alongside `TOPICS`, tickers, and other configuration constants), or a dedicated `bot/prompt_map.py` if the mapping becomes complex. The tag taxonomy is already defined and stable.

### Issue Metadata Storage

The digest JSON at `digests/YYYY-MM-DD.json` is the correct place to store any per-issue metadata (image URLs, generation parameters, override flags). `archive.py` already reads all digest files to build the index — any new fields added there will automatically be available for future index features.

---

## Known Architectural Risks

1. **Single process, no retry loop.** If any external API fails mid-run (NewsAPI, Yahoo Finance, Claude), the whole run fails. There is a retry on Claude JSON parse errors, but no broader fault tolerance.

2. **Flat-file state.** All state lives in `digests/` JSON files. There is no integrity check, no schema validation, and no migration path if the digest structure changes. Old digests with a different schema will silently produce incorrect index data.

3. **GitHub Actions as the runtime.** The scheduler, secrets manager, compute environment, and deployment pipeline are all GitHub Actions. A VCS platform is doing the work of an application server. This is noted in the roadmap as a future VPS migration.

4. **`subscribers.csv` is runtime-generated.** The workflow writes this file from a GitHub secret before running. The committed version of the file should not be treated as authoritative — it may be stale or empty.

5. **No schema contract between `summarizer.py` and the renderers.** The renderers access digest JSON fields by key name with no validation. If Claude returns a malformed or incomplete structure, the error surfaces as a Python `KeyError` at render time, not at parse time.

6. **`pretty_renderer.py` and `renderer.py` share no code.** Both renderers implement the same logical sections independently. Behavioral divergence between the email and archive versions is likely to accumulate over time.
