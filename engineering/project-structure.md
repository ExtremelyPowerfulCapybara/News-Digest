# Project Structure — The Periphery / Mexico Finance Brief

## Repository Tree

```
mexico-finance-brief/
│
├── .github/
│   └── workflows/
│       ├── newsletter.yml          # Production schedule (Mon-Fri 7 AM CST, main branch)
│       ├── newsletter-dev.yml      # Shared dev workflow (manual, dev branch)
│       └── newsletter-adrian.yml  # Adrian's personal test (manual, Dev-Nigg branch)
│
├── bot/                            # All Python source — the pipeline lives here
│   ├── main.py                     # Entry point; orchestrates all modules
│   ├── config.py                   # Central config: secrets, branding, topics, tickers, calendar
│   ├── fetcher.py                  # NewsAPI client; per-topic fetch + dedup
│   ├── scraper.py                  # BeautifulSoup article body extractor
│   ├── scorer.py                   # Freshness/authority/relevance scorer + uniqueness filter
│   ├── summarizer.py               # Claude API call; returns bilingual structured digest JSON
│   ├── market_data.py              # Yahoo Finance tickers, FX matrix, Open-Meteo weather
│   ├── storage.py                  # Digest persistence; week recap; thread tracking reads
│   ├── renderer.py                 # Gmail-safe email HTML (tables + inline styles only)
│   ├── pretty_renderer.py          # Full web HTML (Google Fonts, flexbox, JS, bilingual toggle)
│   ├── archive.py                  # Saves issue pages; rebuilds docs/index.html
│   ├── delivery.py                 # Gmail SMTP sender
│   ├── mock_data.py                # Loads latest digest from disk for dry runs
│   ├── wordcloud_gen.py            # Generates weekly PNG word cloud (Fridays only)
│   └── test_email.py               # Manual test runner with hardcoded mock data
│
├── docs/                           # Served by GitHub Pages (DO NOT manually edit)
│   ├── index.html                  # Auto-rebuilt by archive.py on every run
│   ├── thread_index.json           # Thread tag accumulator; read and written by archive.py
│   ├── wordcloud-YYYY-WNN.png      # Weekly word cloud images
│   └── YYYY-MM-DD.html             # One archive page per issue
│
├── digests/                        # Raw JSON per run — source of truth for the archive index
│   └── YYYY-MM-DD.json
│
├── engineering/                    # Developer documentation (this folder)
│   ├── architecture.md             # System architecture, data flow, extension points, risks
│   ├── pipeline.md                 # Step-by-step pipeline walkthrough with data models
│   └── project-structure.md        # This file
│
├── subscribers.csv                 # Written at runtime by the workflow from the SUBSCRIBERS_CSV secret
├── requirements.txt                # Python dependencies
├── mockup-ticker.html              # Static HTML mockup for ticker bar design experiments
├── TODO.md                         # Roadmap and open tasks
├── CLAUDE.md                       # Instructions for AI assistants working in this repo
├── AGENTS.md                       # Agent-specific instructions
├── .gitignore
├── .gitattributes
└── README.md
```

---

## File-by-File Reference

### Workflows

| File | Purpose | Trigger | Branch | Sends Email |
|---|---|---|---|---|
| `newsletter.yml` | Production run | Cron: Mon–Fri 11:30 UTC (~7 AM CST) | `main` | Yes |
| `newsletter-dev.yml` | Shared dev test | Manual | `dev` | No (default) |
| `newsletter-adrian.yml` | Adrian's personal test | Manual | `Dev-Nigg` | No (`skip_email: true`) |

All three workflows follow the same job structure: checkout → install deps → set secrets → run `bot/main.py` → commit generated files back to the branch.

**Important:** Workflow YAML files must exist on `main` to appear in the GitHub Actions tab, even if the workflow runs code from a different branch.

### Bot Modules

#### `main.py`
The sole entry point. Calls every other module in sequence. 137 lines.

Execution order:
1. Fetch market data (tickers, currency, weather) — parallelizable in principle, sequential in practice
2. Load articles (live via `fetcher.py` or mock via `mock_data.py`)
3. Score and filter via `scorer.py`
4. Summarize via `summarizer.py`
5. Save digest via `storage.py`
6. Build email HTML via `renderer.py`
7. Build archive HTML via `pretty_renderer.py`
8. Optionally send email via `delivery.py`
9. Save and publish archive via `archive.py`
10. Optionally generate word cloud via `wordcloud_gen.py` (Fridays)

#### `config.py`
Imported by every module. Acts as a passive singleton — no classes, just module-level constants and env var reads. Contains:
- Branding: newsletter name, tagline, language, author pen names and titles
- Secrets: API keys, email credentials (all from env vars — never committed)
- Topics: 7 Spanish-language news topics for NewsAPI
- Domain allowlist: 14 outlets; domain blocklist (empty by default)
- Tickers: 4 primary + 3 secondary groups (equities, commodities, crypto)
- Currency pairs: 5 base × 8 quote currencies
- Economic calendar: hardcoded through Dec 2026 (Banxico, Fed, INEGI, BLS events)
- Paths: `DIGESTS_DIR`, `DOCS_DIR`
- Mode flags: `MOCK_MODE`, `SKIP_EMAIL`, `FORCE_FRIDAY`

**Safe to edit.** All configuration lives here. Do not scatter settings into other modules.

#### `fetcher.py`
Handles the NewsAPI integration. One request per topic per run. Enforces the domain allowlist and per-source cap before passing articles to `scraper.py`. Returns plain-text article dicts.

#### `scraper.py`
Pure extraction logic. Stateless — takes a URL, returns a text string. Domain-specific CSS selectors are defined inline; adding a new outlet requires a new entry in the selector dict.

#### `scorer.py`
Stateless ranking function. Takes a list of article dicts, returns a shorter sorted list. The authority tier lists are defined inline — they should arguably live in `config.py` for consistency.

#### `summarizer.py`
The most complex module. Manages prompt construction, Claude API calls, JSON parsing, retry logic, and output validation. The prompt is a long Spanish-language f-string. If the structure of the expected JSON output needs to change, this is the file to edit.

#### `market_data.py`
Three independent fetch functions for Yahoo Finance data. Currency formatting logic (decimal places by currency) is defined inline. The `fetch_currency_table()` function computes all cross-rates client-side from the raw quote prices — it does not request cross-rates directly from Yahoo.

#### `storage.py`
File I/O wrapper for `digests/`. All functions return Python dicts or lists; no objects. The week logic (`get_week_stories()`, `get_week_sentiment()`) scans backward from today to find Mon–Fri files. This will silently return incomplete data on days with missing digests (e.g., holidays, failed runs).

#### `renderer.py`
607 lines. Produces one long HTML string via string concatenation. No templating engine. Each logical section is a private function. The 600px constraint and inline-style-only rule are hard requirements for email client compatibility — do not introduce CSS classes or external resources here.

**Safe to edit** for layout and copy changes. Test all changes in actual email clients (Gmail, Outlook) before merging.

#### `pretty_renderer.py`
733 lines. Same logical structure as `renderer.py` but with no email constraints. Contains ~800 lines of embedded CSS and several blocks of embedded JavaScript (language toggle, currency toggle, tab strip). No templating engine — all HTML is f-strings.

**Safe to edit** for web-specific styling. Changes here do not affect the email.

#### `archive.py`
476 lines. Two responsibilities: (1) write individual issue pages, (2) rebuild the index. The index rebuild is a full regeneration from all digests on every run — there is no incremental update mechanism. As the digest count grows, this will become slower.

#### `delivery.py`
Thin SMTP wrapper. The subscriber list is resolved at send time: `subscribers.csv` first, `SUBSCRIBERS` env var fallback. One connection per run; sends sequentially to all recipients.

#### `mock_data.py`
Reads the most recent file from `digests/` by lexicographic sort (YYYY-MM-DD filenames sort correctly). Synthesizes a fake articles list with URLs matching the stored stories so `fetcher.py`'s dedup logic behaves correctly.

#### `wordcloud_gen.py`
Has a soft dependency on the `wordcloud` library — wraps its import in a try/except and returns `None` if unavailable, allowing the rest of the pipeline to continue. The accent-normalization step (`unicodedata.normalize('NFD', ...)`) is required because `wordcloud` strips accents before stopword matching.

#### `test_email.py`
Contains hardcoded mock data (tickers, currency table, a full bilingual digest dict). Useful for testing rendering changes without any API calls. Not called by the production workflow — run manually from the command line.

---

## Generated vs. Editable Files

| File / Folder | Status | Notes |
|---|---|---|
| `docs/index.html` | Generated | Rebuilt by `archive.py` on every run. Manual edits will be overwritten. |
| `docs/YYYY-MM-DD.html` | Generated | Written once per issue by `archive.py`. Never edited after creation. |
| `docs/thread_index.json` | Generated | Appended by `archive.py`. Do not edit manually. |
| `docs/wordcloud-*.png` | Generated | Written by `wordcloud_gen.py`. |
| `digests/YYYY-MM-DD.json` | Generated | Written by `storage.py`. Treat as append-only. |
| `subscribers.csv` | Runtime-generated | Written by the workflow from a GitHub secret. The committed copy is not authoritative. |
| `bot/*.py` | Editable | All source files. Edit freely; test with `MOCK=true SKIP_EMAIL=true`. |
| `config.py` | Editable | Primary configuration surface. |
| `.github/workflows/*.yml` | Editable | Must live on `main` branch to appear in Actions tab. |
| `requirements.txt` | Editable | Add dependencies here; they are installed by the workflow. |

---

## Data Directory Conventions

### `digests/`
One JSON file per run, named `YYYY-MM-DD.json`. These are the canonical records of each issue. `archive.py` reads all of them to build the index. Do not delete old files — they are the only source of historical data for the sentiment timeline and thread index.

### `docs/`
Static files served directly by GitHub Pages from the `main` branch root. The folder contains:
- `index.html` — the archive landing page with charts and search
- Per-issue HTML files
- Word cloud PNGs
- `thread_index.json` (not served to users; read by `archive.py`)

Do not use `docs/` for anything other than GitHub Pages output. Developer documentation lives in `engineering/`.

---

## Adding a New News Source

1. Add the domain to `NEWS_DOMAIN_ALLOWLIST` in `config.py`
2. Add a CSS selector entry in `scraper.py`'s selector dict (key: domain string, value: CSS selector targeting the article body container)
3. Optionally adjust the authority tier in `scorer.py` (`TIER_1_DOMAINS` or `TIER_2_DOMAINS`)

## Adding a New Ticker

1. Add the Yahoo Finance symbol to the appropriate list in `config.py` (`TICKERS`, `SECONDARY_TICKER_GROUPS`)
2. If it's a new ticker type (not equity/commodity/crypto), add formatting logic to `market_data.py`
3. The renderers read tickers from the market data dict — no renderer changes needed unless the display format changes

## Adding a New Economic Calendar Event

Edit `config.py` — the `ECONOMIC_CALENDAR` list. Each entry is a dict with `date`, `event`, `institution`, and `importance` fields. Events are sorted at read time by `storage.get_upcoming_calendar()`.
