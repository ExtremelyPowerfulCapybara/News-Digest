# The Periphery — Mexico Finance Brief

A bilingual (Spanish/English) automated financial newsletter focused on emerging markets and macro intelligence. Every weekday at ~7 AM Mexico City time, a scheduled job on a VPS fetches news, pulls live market data, writes a bilingual digest with Claude, sends an email to subscribers, and publishes a full HTML archive to GitHub Pages.

**Live archive:** https://extremelypowerfulcapybara.github.io/News-Digest/

---

## 1. Project Overview

**The Periphery** (also branded as *The Opening Bell*) is a self-hosted newsletter pipeline that produces two outputs per run:

1. A **Gmail-safe HTML email** sent to subscribers via SMTP
2. A **full web archive page** committed to GitHub Pages

Each issue contains: a bilingual editor note, 5–7 curated stories with context notes, a macro sentiment score, a market data panel (equities, commodities, crypto, FX), a quote of the day, and an economic calendar. On Fridays it also includes a week-in-review timeline, a sentiment bar chart, and a word cloud generated from the week's headlines.

The pipeline has no web server and no database. All persistent state is flat JSON files in `digests/`. The production runtime is a VPS running a scheduled cron job; secrets are loaded from `bot/.env`. GitHub Actions is retained for optional dev/test runs.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Single process, no async |
| Scheduling | VPS cron job | Mon–Fri ~7 AM CST; GitHub Actions retained for dev/test |
| News data | NewsAPI v2 | 7 Spanish-language topics, 14 curated outlets |
| Market data | Yahoo Finance JSON API | Raw `requests` — no `yfinance` package |
| AI summarization | Anthropic Claude API | Structured bilingual JSON output |
| Article extraction | BeautifulSoup4 + lxml | Per-domain CSS selectors + `<p>` fallback |
| Email delivery | Gmail SMTP (App Password) | `MIMEMultipart`, one connection per run |
| Archive hosting | GitHub Pages | Served from `docs/` on `main` |
| Word cloud | `wordcloud` + Pillow | Fridays only; soft dependency |

**Python dependencies** (`requirements.txt`): `anthropic`, `requests`, `beautifulsoup4`, `lxml`, `wordcloud`, `Pillow`

---

## 3. Repository Structure

```
mexico-finance-brief/
│
├── .github/workflows/
│   ├── newsletter.yml           # Production: cron Mon-Fri, runs on main, sends email
│   ├── newsletter-dev.yml       # Shared dev: manual, runs on dev branch
│   └── newsletter-adrian.yml   # Adrian's test: manual, runs on Dev-Nigg, skip_email=true
│
├── bot/                         # All Python source — the pipeline lives here
│   ├── main.py                  # Entry point; orchestrates all modules in sequence
│   ├── config.py                # Central config: branding, secrets, topics, tickers, calendar
│   ├── fetcher.py               # NewsAPI client; per-topic fetch, domain allowlist, dedup
│   ├── scraper.py               # BeautifulSoup article body extractor (per-domain selectors)
│   ├── scorer.py                # Composite scorer: freshness + authority + relevance
│   ├── summarizer.py            # Claude API call; returns bilingual structured digest JSON
│   ├── market_data.py           # Yahoo Finance tickers + FX cross-rate matrix
│   ├── storage.py               # Digest persistence; week recap; thread tracking
│   ├── renderer.py              # Gmail-safe email HTML (tables + inline styles only)
│   ├── pretty_renderer.py       # Full web HTML (Google Fonts, flexbox, JS, bilingual toggle)
│   ├── archive.py               # Writes issue pages; rebuilds docs/index.html
│   ├── delivery.py              # Gmail SMTP sender
│   ├── mock_data.py             # Loads latest digest from disk for dry runs
│   ├── wordcloud_gen.py         # Generates weekly PNG word cloud (Fridays only)
│   └── test_email.py            # Sends a test email with hardcoded mock data; run manually
│
├── docs/                        # GitHub Pages output — DO NOT edit manually
│   ├── index.html               # Archive landing page; rebuilt on every run
│   ├── YYYY-MM-DD.html          # One page per issue
│   ├── thread_index.json        # Thread tag accumulator; read and written by archive.py
│   └── wordcloud-YYYY-WNN.png   # Weekly word cloud images
│
├── digests/                     # Raw JSON per run — source of truth for archive + index
│   └── YYYY-MM-DD.json
│
├── engineering/                 # Developer documentation
│   ├── architecture.md          # System diagram, module graph, data flow, extension points
│   ├── pipeline.md              # Stage-by-stage walkthrough with JSON shapes
│   └── project-structure.md    # File-by-file reference, generated vs. editable files
│
├── subscribers.csv              # Runtime-generated from GitHub secret — not authoritative
├── requirements.txt
├── TODO.md
└── CLAUDE.md                    # Instructions for AI assistants working in this repo
```

---

## 4. How the Pipeline Works

### Execution order (`main.py`)

```
1.  Fetch market data          → market_data.py   (parallel: tickers, secondary, FX)
2.  Fetch news articles        → fetcher.py + scraper.py
2.5 Score and rank articles    → scorer.py         (skipped in MOCK mode)
3.  Summarize with Claude      → summarizer.py
4.  Save digest to disk        → storage.py        → digests/YYYY-MM-DD.json
5.  Build email HTML           → renderer.py
    Send email                 → delivery.py       (skipped if SKIP_EMAIL=true)
6.  Build archive HTML         → pretty_renderer.py
    Save issue + rebuild index → archive.py        → docs/YYYY-MM-DD.html + docs/index.html
    (Fridays) Generate word cloud → wordcloud_gen.py → docs/wordcloud-YYYY-WNN.png
```

After step 6, the pipeline (or the VPS cron wrapper) runs `git add docs/ digests/` and commits + pushes to the branch, triggering a GitHub Pages redeploy.

### Data ingestion

`fetcher.py` queries NewsAPI's `v2/everything` endpoint once per topic (7 topics × up to 14 domains). It enforces a domain allowlist, caps 1 article per source per topic, and deduplicates against URLs seen in the last 5 daily digests. For each article, `scraper.py` extracts the body text using per-domain CSS selectors, falls back to all `<p>` tags, requires a 100-character minimum, and truncates at 3,000 characters.

### Scoring

`scorer.py` assigns a composite score to each article:

```
score = (freshness × 0.30) + (authority × 0.25) + (relevance × 0.25)
```

A greedy uniqueness filter then removes articles whose headlines share >60% word overlap with any already-accepted article. The top 12 go to Claude.

### AI summarization

`summarizer.py` sends all 12 articles plus live market data and active thread history to Claude in a single Spanish-language prompt. Claude returns a structured bilingual JSON blob containing:

- 5–7 selected stories with headlines, body, context notes, source, and thread tags
- A bilingual editor note and narrative thread
- A market sentiment score (5–95 scale: Risk-Off / Cautious / Risk-On)
- A quote with attribution

On JSON parse failure, the module retries once with a repair prompt. On API overload errors, it retries with exponential backoff.

### HTML generation

Two independent renderers produce the same logical content for different delivery targets:

| Renderer | File | Constraints | Features |
|---|---|---|---|
| Email | `renderer.py` | Tables + inline styles only; no CSS classes, no JS, no external fonts | Gmail/Outlook/Apple Mail safe |
| Archive | `pretty_renderer.py` | No email constraints | Bilingual toggle, FX base switcher, market tab strip, animated gauge, responsive layout |

The renderers share no code. Behavioral divergence between them accumulates over time — this is a known tech debt item.

### Output and publication

- Email is sent via Gmail SMTP as a `MIMEMultipart` message (HTML + plain text parts)
- Archive page is written to `docs/YYYY-MM-DD.html`
- `docs/index.html` is fully regenerated from all digest JSONs on every run (no incremental update)
- `docs/thread_index.json` is updated with new thread tags
- All of `docs/` and `digests/` are committed back to the branch by the workflow

---

## 5. Environment Setup (VPS)

The production runtime is a VPS at `/home/adrian/project`. Secrets are stored in `bot/.env` and loaded automatically via `python-dotenv` when the pipeline starts. GitHub Actions is no longer the primary runtime — it is retained only for optional dev/test runs.

### Creating `bot/.env`

```bash
cd /home/adrian/project/bot
cp .env.example .env   # if an example file exists, or create from scratch
nano .env
```

Minimum required content:

```
NEWS_API_KEY=your-newsapi-key
ANTHROPIC_API_KEY=your-anthropic-key
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"
SUBSCRIBERS=subscriber@example.com
```

### Notes

- Values containing spaces **must be quoted**: `EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"`
- `bot/.env` is listed in `.gitignore` — it will never be committed accidentally
- `load_dotenv()` in `main.py` loads the file automatically; no `export` step needed
- On the VPS, cron entries in `crontab -e` drive the full daily workflow (see below)
- GitHub Actions workflows (`newsletter.yml`, etc.) inject secrets via the GitHub Actions secrets store and do not depend on `bot/.env`

### VPS cron configuration

Create the log directory once:

```bash
mkdir -p /home/adrian/project/logs
```

Then add to `crontab -e`:

```cron
CRON_TZ=America/Mexico_City

# Morning issue run — weekdays at 7:00 AM
0 7 * * 1-5 cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python main.py >> /home/adrian/project/logs/main.log 2>&1

# Candidate generation — weekdays at 7:06 AM (after main.py finishes)
6 7 * * 1-5 cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python generate_candidates.py >> /home/adrian/project/logs/candidates.log 2>&1

# Telegram handler — every 2 minutes
*/2 * * * * cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python telegram_handler.py >> /home/adrian/project/logs/telegram_handler.log 2>&1
```

Environment variables are loaded via `load_dotenv()` inside each entrypoint — no `source .env` needed in cron.

---

## 6. Running Locally

### Installation

```bash
cd bot
pip install -r ../requirements.txt
```

### Environment variables

Create `bot/.env` (never committed — automatically loaded by `load_dotenv()` at startup):

```
NEWS_API_KEY=your-newsapi-key
ANTHROPIC_API_KEY=your-anthropic-key
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"
SUBSCRIBERS=you@example.com,other@example.com
SKIP_EMAIL=false
TELEGRAM_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
PUBLIC_ARCHIVE_BASE_URL=https://extremelypowerfulcapybara.github.io/News-Digest
```

> **Quoting:** values that contain spaces (e.g. Gmail App Passwords) must be quoted.
> **Security:** never commit `bot/.env`. It is already in `.gitignore`.

All variables read by the pipeline:

| Variable | Required | Description |
|---|---|---|
| `NEWS_API_KEY` | Yes | NewsAPI key (free tier: 100 req/day) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic Claude API key |
| `EMAIL_SENDER` | Yes | Gmail address to send from |
| `EMAIL_PASSWORD` | Yes | Gmail App Password (not your login password) |
| `SUBSCRIBERS` | Yes | Comma-separated recipient emails |
| `SKIP_EMAIL` | No | `true` to skip SMTP; archive HTML is still generated |
| `TELEGRAM_TOKEN` | No | Telegram bot token for post-run notifications |
| `TELEGRAM_CHAT_ID` | No | Telegram chat/channel ID for notifications |
| `PUBLIC_ARCHIVE_BASE_URL` | No | Base URL for archive links in Telegram messages |
| `MOCK` | No | `true` to skip NewsAPI + Claude; loads latest digest from `digests/` |
| `FORCE_FRIDAY` | No | `true` to simulate Friday mode (word cloud + week-in-review) |
| `GITHUB_RAW_URL` | Dev only | Asset URL override for word cloud images on non-Pages branches |
| `SUBSCRIBERS_CSV` | GH Actions only | Newline-separated list; written to `subscribers.csv` by the workflow |
| `DEV_SUBSCRIBERS_CSV` | GH Actions only | Same format; used by `newsletter-dev.yml` and `newsletter-adrian.yml` |
| `HEALTH_CHECK_URL` | No | Healthchecks.io ping URL (not yet implemented) |
| `BANXICO_API_KEY` | No | Reserved for future Banxico API integration |

Missing required variables are caught by `config.py` returning empty strings; the pipeline will fail at the first API call that needs the key and log the error clearly.

### Run commands

With `bot/.env` in place, `load_dotenv()` loads it automatically:

```bash
cd bot
python main.py
```

Dry run — no API calls, no email, archive HTML generated from saved digest:

```bash
cd bot
MOCK=true SKIP_EMAIL=true python main.py
```

Simulate a Friday run:

```bash
cd bot
MOCK=true SKIP_EMAIL=true FORCE_FRIDAY=true python main.py
```

Send a test email using hardcoded mock data (no pipeline):

```bash
cd bot
python test_email.py
```

### Local preview

After running `main.py`, open the generated HTML file directly in a browser:

```
docs/YYYY-MM-DD.html
```

GitHub Pages reflects `main` only. To preview `Dev-Nigg` output, open the file from disk.

---

## 7. Output Format

### Email

Subject line: `{sentiment_label} | {NEWSLETTER_NAME} — {date_es}`

Structure (top to bottom): masthead → ticker bar → secondary market dashboard → editor note → narrative thread → sentiment gauge → story blocks → FX table → quote → (Fridays: week-in-review, sentiment chart, weekly markets) → economic calendar → footer.

### Archive pages

Each issue is saved as `docs/YYYY-MM-DD.html`. The archive page adds: bilingual ES/EN toggle (persisted in `localStorage`), currency base switcher (MXN/USD/BRL/EUR/CNY), animated sentiment gauge, secondary market tab strip, and word cloud embed on Fridays.

### Digest JSON

`digests/YYYY-MM-DD.json` is the canonical record of each run. Shape:

```json
{
  "date": "2026-04-06",
  "digest": {
    "es": {
      "editor_note": "...",
      "narrative_thread": "...",
      "sentiment": { "score": 42, "label": "Cauteloso", "context": "..." },
      "stories": [
        {
          "headline": "...",
          "body": "...",
          "source": "El Financiero",
          "url": "https://...",
          "tag": "Tasas",
          "thread_tag": "Politica Monetaria",
          "context_note": "..."
        }
      ],
      "quote": { "text": "...", "attribution": "..." }
    },
    "en": { "...": "identical structure in English" }
  },
  "market": {
    "tickers": [...],
    "currency": { "...": "FX cross-rate matrix" }
  }
}
```

**Note:** `secondary_tickers` (equities, commodities, crypto) are fetched at runtime and passed directly to the renderers but are **not** persisted to the digest JSON. They cannot be reconstructed from historical digests.

The archive index (`docs/index.html`) is rebuilt from all digest files on every run. Do not delete old digest files — they are the only source of historical data for the sentiment timeline and thread tracking.

---

## 8. Editing Guide

### Safe to edit

| File | What to change |
|---|---|
| `bot/config.py` | Newsletter name, topics, domain allowlist, tickers, currency pairs, economic calendar, pen names |
| `bot/renderer.py` | Email layout and copy. Test in Gmail, Outlook, Apple Mail before merging. |
| `bot/pretty_renderer.py` | Archive web layout and styling. No email compatibility constraints here. |
| `bot/scraper.py` | Add CSS selectors for new news outlets |
| `bot/scorer.py` | Adjust authority tiers or scoring weights |
| `bot/summarizer.py` | Edit the Claude prompt or expected JSON structure |
| `.github/workflows/*.yml` | Workflow triggers, secrets, branch targeting |
| `requirements.txt` | Add new Python dependencies |
| `engineering/*.md` | Developer documentation |

### Do not edit directly

| File / Folder | Reason |
|---|---|
| `docs/index.html` | Rebuilt by `archive.py` on every run — manual edits will be overwritten |
| `docs/YYYY-MM-DD.html` | Written once by `archive.py`; never edited after creation |
| `docs/thread_index.json` | Appended by `archive.py`; manual edits corrupt thread history |
| `docs/wordcloud-*.png` | Written by `wordcloud_gen.py` |
| `digests/YYYY-MM-DD.json` | Treat as append-only; deleting breaks the archive index |
| `subscribers.csv` | Runtime-generated by the workflow; the committed copy is not authoritative |

### Adding a news source

1. Add the domain to `NEWS_DOMAIN_ALLOWLIST` in `config.py`
2. Add a CSS selector entry in `scraper.py`'s selector dict (key: domain string, value: CSS selector for the article body container)
3. Optionally adjust the authority tier in `scorer.py`

### Adding a ticker

1. Add the Yahoo Finance symbol to the appropriate list in `config.py` (`TICKER_SYMBOLS` or `SECONDARY_TICKER_GROUPS`)
2. No renderer changes needed unless the display format changes

### Adding an economic calendar event

Edit `config.py` — the `ECONOMIC_CALENDAR` list. Each entry needs `date`, `event`, `institution`, and `importance` fields. Events are sorted at read time by `storage.get_upcoming_calendar()`.

---

## 9. Planned Extension Points

### Visual / image generation layer

The cleanest integration point is between `summarizer.py` (step 3) and the renderers (step 5). Each story already carries a `tag` field (`Macro`, `FX`, `México`, `Comercio`, `Tasas`, `Mercados`, `Energía`, `Política`). The intended approach:

1. **New file: `bot/image_gen.py`** — called from `main.py` after `summarizer.py`, before `renderer.py`
2. Maps story tags to image generation prompts (mapping lives in `config.py` or a dedicated `bot/prompt_map.py`)
3. Generates or selects an image per story; adds `story["image_url"]` or `story["image_b64"]` to the digest dict
4. Both `renderer.py` and `pretty_renderer.py` conditionally include an `<img>` tag in `_story_block()` when that field is present

This approach requires no changes to existing module interfaces — the image layer slots in as an optional enrichment step.

### Issue metadata layer

`digests/YYYY-MM-DD.json` is the correct place to store per-issue metadata (image URLs, generation parameters, override flags). `archive.py` already reads all digest files to rebuild the index — any new fields added to the digest JSON are automatically available for future index features without structural changes.

### Other planned additions

See `TODO.md` for the current task list. Key items:

- **Health monitoring** — Healthchecks.io ping at end of each run (`HEALTH_CHECK_URL` env var is already wired in `config.py`)
- **Unsubscribe tokens** — per-subscriber token system for GDPR-friendly unsubscribes
- **Resend/Mailgun migration** — replace Gmail SMTP for deliverability at scale (needed beyond ~20 subscribers)
- **VPS migration** — ~~move off GitHub Actions~~ **done**; pipeline runs on a VPS
- **Substack integration** — freemium commercial launch on a ~12-month horizon

---

## 10. Known Limitations & Tech Debt

1. **Single process, no fault isolation.** If any external API call fails mid-run (NewsAPI, Yahoo Finance, Claude), the entire run fails. The only retry logic is in `summarizer.py` (Claude JSON repair + overload backoff). Everything else is fail-fast.

2. **No schema contract between summarizer and renderers.** The renderers access digest JSON fields by key name with no validation. If Claude returns a malformed or incomplete structure, the error surfaces as a Python `KeyError` at render time, not at parse time. There is no schema version in the digest files.

3. **Flat-file state with no migration path.** All state is in `digests/` JSON files. If the digest structure changes, old digests will silently produce incorrect index data. There is no schema version, no integrity check, and no migration tooling.

4. **`renderer.py` and `pretty_renderer.py` share no code.** Both implement the same logical sections independently. Behavioral divergence between the email and archive outputs is likely to accumulate over time.

5. **`secondary_tickers` are not persisted.** The secondary market panel (equities, commodities, crypto) is fetched fresh on every run and passed directly to the renderers. It is not saved to the digest JSON, so it cannot be reconstructed from historical data.

6. **Full index rebuild on every run.** `archive.py` regenerates `docs/index.html` from all digest files on every run. As the digest count grows, this will become progressively slower.

7. **Git push still required for GitHub Pages.** The VPS runs the pipeline and generates `docs/`, but GitHub Pages still requires a push to `main` to redeploy. The cron wrapper handles this with `git push`, which keeps a coupling to GitHub's platform for archive hosting.

8. **Branch divergence.** As of April 2026, `Dev-Nigg` is significantly ahead of `main` in features. Production is running old code. Merging is a listed quick-win in `TODO.md`.

9. **`scorer.py` is loaded lazily in `main.py`.** The import happens inside the `else` block that skips mock mode. In mock runs, articles are loaded pre-scored from the saved digest and the scorer never executes. This is intentional but could confuse someone reading the imports at the top of `main.py`.

10. **Domain-specific CSS selectors in `scraper.py` require manual maintenance.** New outlets need a custom selector or they fall back to all `<p>` tags, which often captures navigation, ads, and boilerplate.

---

## 11. Developer Documentation

The `engineering/` folder contains detailed technical references:

- **[engineering/architecture.md](./engineering/architecture.md)** — system diagram, module dependency map, full data flow, state and persistence table, extension points, architectural risks
- **[engineering/pipeline.md](./engineering/pipeline.md)** — stage-by-stage walkthrough with intermediate artifact shapes and example JSON
- **[engineering/project-structure.md](./engineering/project-structure.md)** — annotated file tree, file-by-file module reference, generated vs. editable files, how-to guides for adding sources and tickers

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Production. GitHub Pages is served from here. Workflow YAMLs must live here. |
| `Dev-Nigg` | Adrian's active development branch. All new features start here. |
| `dev` | Alejandro/Juan's shared dev branch. |

**Always confirm your active branch in GitHub Desktop before editing files.** Writing to `main` when `Dev-Nigg` is intended is a recurring risk.

---

## Cost

| Service | Cost |
|---|---|
| GitHub Actions | Free (~5 min/run, well within the 2,000 min/month free tier) |
| GitHub Pages | Free |
| NewsAPI | Free (100 req/day) |
| Claude API | ~$0.05–0.08/run (~$25/year) |
| Yahoo Finance | Free, no key required |
| Gmail SMTP | Free |
