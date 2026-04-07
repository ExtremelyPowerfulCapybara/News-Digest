# Pipeline Walkthrough — The Periphery / Mexico Finance Brief

## Entry Point

All runs start from `bot/main.py`. There is no CLI argument parsing — behavior is controlled entirely by environment variables read through `config.py`.

```bash
cd bot
python main.py
```

---

## Stage 1 — Market Data Ingestion

**File:** `bot/market_data.py`
**Intermediate artifact:** Python dicts passed in memory to later stages

Three parallel data pulls:

| Data | Source | Function |
|---|---|---|
| Primary tickers (DXY, 10Y UST, VIX, MSCI EM) | Yahoo Finance | `fetch_tickers()` |
| Secondary tickers (equities, commodities, crypto) | Yahoo Finance | `fetch_secondary_tickers()` |
| FX cross-rate matrix (MXN, USD, BRL, EUR, CNY, CAD, GBP, JPY) | Yahoo Finance | `fetch_currency_table()` |
| Weather | Open-Meteo (no key required) | inline in `main.py` |

Each ticker returns 1-day and 1-week percentage change alongside the spot value. The FX matrix produces all cross-rates from 5 base currencies × 8 quote currencies.

---

## Stage 2 — News Fetching

**File:** `bot/fetcher.py` → `bot/scraper.py`
**Intermediate artifact:** `list[dict]` — raw articles

```python
# Shape of a fetched article
{
    "title": "Banxico mantiene tasa de interes en 9.5%",
    "content": "...(up to 3000 chars of extracted body text)...",
    "source": "El Financiero",
    "url": "https://...",
    "publishedAt": "2026-04-06T10:30:00Z"
}
```

**Fetcher logic:**
1. Loops over 7 topics (finanzas, economía, México, comercio, mercados, política, criptomonedas)
2. Calls NewsAPI `v2/everything` filtered to the domain allowlist (14 outlets)
3. Caps articles per source per topic at 1 (`MAX_ARTICLES_PER_SOURCE`)
4. Deduplicates against URLs seen in the last 5 daily digests (`storage.get_recent_urls()`)
5. For each article, calls `scraper.py` to extract full body text

**Scraper logic:**
1. Tries per-domain CSS selectors first (e.g., `[class*='article-body']` for specific outlets)
2. Falls back to all `<p>` tags on the page
3. Strips nav, footer, script, style, figure, aside, header elements
4. Requires minimum 100 chars; truncates at 3,000 chars
5. Falls back to the NewsAPI description field if scraping fails

**Mock mode:** When `MOCK=true`, `fetcher.py` is skipped entirely. `mock_data.py` loads the most recent digest from `digests/` and synthesizes a fake articles list with matching URLs so the downstream pipeline runs identically.

---

## Stage 3 — Scoring & Deduplication

**File:** `bot/scorer.py`
**Intermediate artifact:** sorted, filtered `list[dict]` — at most 12 articles

Composite score formula:

```
score = (freshness × 0.30) + (authority × 0.25) + (relevance × 0.25)
```

| Component | Range | Criteria |
|---|---|---|
| Freshness | 1.0 / 0.7 / 0.4 / 0.1 | <6h / <12h / <24h / older |
| Authority | 1.0 / 0.6 / 0.3 | Tier 1 (FT, Reuters, WSJ, Bloomberg) / Tier 2 (Expansion, El Economista, Reforma) / unknown |
| Relevance | 0.0–1.0 | Normalized keyword overlap with `config.TOPICS` |

After scoring, a greedy uniqueness filter removes articles whose headlines share >60% word overlap with any already-accepted article. Returns top `MAX_ARTICLES_FOR_CLAUDE` (12).

---

## Stage 4 — AI Summarization

**File:** `bot/summarizer.py`
**Intermediate artifact:** bilingual JSON digest dict

This is the most consequential stage. All 12 articles plus market data and thread history are sent to Claude in a single Spanish-language prompt.

**Claude's responsibilities:**
- Select 5–7 stories with mandatory topic diversity
- Write a bilingual editor note (ES + EN)
- Write a narrative thread (the day's macro theme)
- Score market sentiment on a 5–95 scale:
  - 5–35: "Aversión al Riesgo" (Risk-Off)
  - 36–64: "Cauteloso" (Cautious)
  - 65–95: "Apetito por Riesgo" (Risk-On)
- Write bilingual context notes per story (why it matters today)
- Select a quote with attribution
- Assign thread tags per story (`Macro`, `FX`, `México`, `Comercio`, `Tasas`, `Mercados`, `Energía`, `Política`)

**Digest JSON shape (abbreviated):**

```json
{
  "es": {
    "editor_note": "...",
    "narrative_thread": "...",
    "sentiment": {
      "score": 42,
      "label": "Cauteloso",
      "context": "..."
    },
    "stories": [
      {
        "headline": "Banxico recorta tasa a 9.0%",
        "body": "...",
        "source": "El Financiero",
        "url": "https://...",
        "tag": "Tasas",
        "thread_tag": "Politica Monetaria",
        "context_note": "..."
      }
    ],
    "quote": {
      "text": "...",
      "attribution": "..."
    }
  },
  "en": {
    "editor_note": "...",
    "narrative_thread": "...",
    "sentiment": { "score": 42, "label": "Cautious", "context": "..." },
    "stories": [ ... ],
    "quote": { "text": "...", "attribution": "..." }
  }
}
```

**Error handling:** On `overload` API errors, the module retries with exponential backoff. If the returned JSON is malformed, it retries once with a "repair this JSON" prompt.

---

## Stage 5 — Persistence

**File:** `bot/storage.py`
**Output artifact:** `digests/YYYY-MM-DD.json`

```json
{
  "date": "2026-04-06",
  "digest": { "es": {...}, "en": {...} },
  "market": {
    "tickers": [...],
    "secondary": {...},
    "currency_table": {...},
    "weather": {...}
  }
}
```

`storage.py` also provides read functions used by downstream stages:
- `get_recent_urls()` — last 5 days of article URLs (used by `fetcher.py` for dedup)
- `get_week_stories()` — top story per day Mon–Fri (used by renderers for week-in-review)
- `get_week_sentiment()` — daily sentiment scores Mon–Fri (used by renderers for the chart)
- `get_active_threads()` — tags appearing ≥2× in the last 5 digests (used by renderers for thread badges)
- `get_upcoming_calendar()` — next N events from `config.ECONOMIC_CALENDAR`

---

## Stage 6 — Email Rendering

**File:** `bot/renderer.py`
**Output artifact:** HTML string + plain text string (in memory, passed to `delivery.py`)

`renderer.py` builds a 600px-wide table-based HTML email using only inline styles. No CSS classes, no external fonts, no JavaScript — all must survive aggressive email client sanitization (Gmail, Outlook, Apple Mail).

**Section assembly order (inside `build_html()`):**

1. `_header()` — masthead: newsletter name, date, edition number, tagline
2. `_ticker()` — dark bar: DXY, 10Y UST, VIX, MSCI EM with 1D/1W change arrows
3. `_secondary_dashboard()` — 3-column table: equities, commodities, crypto
4. `_editor_note()` — italic paragraph + pen name byline
5. `_narrative_thread()` — centered pull quote (the day's macro theme)
6. `_sentiment()` — pill buttons + gauge bar + context sentence
7. `_story_block()` × N — source, tag badge, headline (20px bold), 2-sentence body, read-more link, thread tag
8. `_currency_table()` — 4 FX pairs from USD base (email uses USD only)
9. `_quote()` — large decorative quote mark + text + attribution
10. `_week_review()` — Mon–Fri timeline (Fridays only)
11. `_sentiment_week_chart()` — Mon–Fri horizontal sentiment bars (Fridays only)
12. `_economic_calendar()` — next 5 macro events with institution badges
13. `_weekly_markets()` — 1D/1W market table (Fridays only)
14. `_footer()` — newsletter name, author, archive link, unsubscribe placeholder

`build_plain()` produces a simple text version with the same content hierarchy.

---

## Stage 7 — Archive Rendering

**File:** `bot/pretty_renderer.py`
**Output artifact:** HTML string (in memory, passed to `archive.py`)

The archive renderer produces a full web HTML page using Google Fonts (Inter), CSS classes, flexbox, and JavaScript. It is structurally parallel to `renderer.py` but with no email compatibility constraints.

**Additional features not in the email:**
- Bilingual toggle (ES/EN buttons) — swaps `.lang-es`/`.lang-en` divs, persisted in `localStorage`
- Currency base toggle (MXN/USD/BRL/EUR/CNY) — shows/hides corresponding FX sub-tables
- Secondary tickers tabbed strip — Equities / Commodities / Crypto with JS tab handler
- Word cloud PNG embed (from `docs/wordcloud-YYYY-WNN.png`)
- Animated sentiment gauge marker
- Responsive layout (flex wrapping for mobile)

---

## Stage 8 — Email Delivery

**File:** `bot/delivery.py`
**Triggered:** only when `SKIP_EMAIL=false`

1. `load_subscribers()` reads `subscribers.csv`; falls back to `SUBSCRIBERS` env var if file not found
2. Connects to `smtp.gmail.com:465` (SSL) using `EMAIL_SENDER` + `EMAIL_PASSWORD`
3. Subject line: `{sentiment_label} | {NEWSLETTER_NAME} — {date_es}`
4. Sends one `MIMEMultipart` message per recipient with both plain-text and HTML parts

---

## Stage 9 — Archive Publishing

**File:** `bot/archive.py`
**Output artifacts:** `docs/YYYY-MM-DD.html`, `docs/index.html`, `docs/thread_index.json`

`save_pretty_issue()` writes the HTML from `pretty_renderer.py` to `docs/YYYY-MM-DD.html`, then calls `rebuild_index()`.

`rebuild_index()`:
1. Loads all `digests/YYYY-MM-DD.json` files via `_load_all_digests()`
2. Updates `docs/thread_index.json` with new thread tags via `_update_thread_index()`
3. Generates a Chart.js sentiment timeline (line chart, all issues)
4. Generates a Chart.js story count bar chart (all issues)
5. Builds a coverage map (top 10 threads by total mention count)
6. Builds a collapsible thread index (recent stories grouped by thread tag)
7. Builds an issue card grid (date, sentiment pill, story count, lead headline)
8. Implements client-side search (tokenized AND matching against title + body text)
9. Writes the complete `docs/index.html`

After `archive.py` completes, the GitHub Actions workflow runs `git add docs/ digests/` and commits + pushes to `main`, which triggers GitHub Pages to redeploy.

---

## Stage 10 — Friday Extensions (conditional)

**File:** `bot/wordcloud_gen.py`
**Triggered:** when `storage.is_friday()` returns `True`, or `FORCE_FRIDAY=true`

1. Collects all text (headlines + body) from Mon–Fri digests via `storage.get_week_stories()`
2. Normalizes Unicode accents to ASCII (required for `wordcloud` stopword matching)
3. Filters 70+ Spanish/English stopwords
4. Generates a 1200×480 PNG with a bias toward dark shades for high-frequency words
5. Saves to `docs/wordcloud-YYYY-WNN.png`

The week-in-review section (`_week_review()`) and sentiment bar chart (`_sentiment_week_chart()`) are also included in both renderers on Fridays.

---

## Intermediate Artifacts Summary

| Artifact | Format | Location | Committed? |
|---|---|---|---|
| Fetched + scraped articles | `list[dict]` in memory | — | No |
| Scored + filtered articles | `list[dict]` in memory | — | No |
| Bilingual digest JSON | `dict` in memory | — | No |
| Saved digest | JSON file | `digests/YYYY-MM-DD.json` | Yes |
| Email HTML | string in memory | — | No |
| Pretty HTML | string in memory | — | No |
| Issue archive page | HTML file | `docs/YYYY-MM-DD.html` | Yes |
| Archive index | HTML file | `docs/index.html` | Yes |
| Thread index | JSON file | `docs/thread_index.json` | Yes |
| Word cloud | PNG file | `docs/wordcloud-YYYY-WNN.png` | Yes (Fridays) |
