# CLAUDE.md — The Periphery / Mexico Finance Brief

This file provides context for AI assistants working in this repository.
**Always ask Adrian before making any changes to files, no matter the context.**

---

## Project Overview

**The Periphery** (also referred to as *The Opening Bell* or *Mexico Finance Brief*) is a bilingual
(Spanish/English) automated financial newsletter focused on emerging markets and macro intelligence.

**Team:**
- **Adrian** — Mexico City. Technical infrastructure, product lead, owner of this repo.
- **Alejandro** — Madrid. Editorial direction and economics coverage.
- **Juan** — Buenos Aires. Visual identity, trading and politics coverage.

**Goal:** A self-sustaining publication with a paying subscriber base, built over 2-3 years.
Year one is audience building. Long-term model: freemium on Substack.

**Repo:** https://github.com/extremelypowerfulcapybara/News-Digest
**Archive (GitHub Pages):** https://extremelypowerfulcapybara.github.io/News-Digest/

---

## How It Works

Every weekday at ~7 AM Mexico City time, a GitHub Actions workflow:

1. Fetches articles from **NewsAPI** across configured Spanish-language topics
2. Pulls live market data from **Yahoo Finance** and weather from **Open-Meteo**
3. Sends everything to the **Anthropic Claude API**, which writes the editor note, picks stories,
   scores sentiment, selects a quote, and produces bilingual (ES/EN) output
4. Sends a **Gmail-safe HTML email** to all subscribers
5. Saves a **pretty HTML archive page** to `docs/`
6. **Auto-commits** docs + digests back to the repo so GitHub Pages updates

---

## Repo Structure

```
mexico-finance-brief/
├── .github/
│   └── workflows/
│       ├── newsletter.yml          # Production: scheduled Mon-Fri, runs on main
│       ├── newsletter-dev.yml      # Dev workflow: manual only, runs on `dev` branch
│       └── newsletter-adrian.yml  # Adrian's personal test: manual, runs on Dev-Nigg
│
├── bot/                            # All Python source
│   ├── main.py                     # Entry point -- orchestrates the full run
│   ├── config.py                   # All settings + secrets (reads from env vars)
│   ├── fetcher.py                  # NewsAPI fetching + domain allowlist
│   ├── scraper.py                  # Full article text extractor (BeautifulSoup)
│   ├── summarizer.py               # Claude API call -> structured bilingual JSON
│   ├── market_data.py              # Yahoo Finance tickers, currency table, weather
│   ├── storage.py                  # Saves/loads daily digest JSONs, week logic
│   ├── renderer.py                 # Gmail-safe email HTML (tables, inline styles)
│   ├── pretty_renderer.py          # Full-featured archive HTML (Google Fonts, etc.)
│   ├── archive.py                  # Saves pretty issues, rebuilds index.html
│   ├── delivery.py                 # Gmail SMTP sender
│   ├── mock_data.py                # Mock digest for dry runs
│   ├── wordcloud_gen.py            # Weekly word cloud generator (Fridays only)
│   └── test_email.py               # Sends test email with mock data
│
├── lib/                            # Image generation subsystem (standalone; not wired into main.py yet)
│   ├── image_generator.py          # Full pipeline: registry selection, retry loop, DB persistence
│   ├── image_prompt_builder.py     # Prompt assembly, variation codes, novelty directives
│   ├── image_history_store.py      # SQLite: image_history + generation_attempts tables
│   ├── image_similarity.py         # pHash + TF-IDF two-phase rejection
│   ├── image_registry.py           # Registry loader + history-aware select_prompt_components()
│   └── tests/                      # pytest suite (97 tests)
│
├── config/
│   └── image_prompt_registry.yaml  # Per-category building blocks: concepts, subjects, compositions
│
├── scripts/
│   └── generate_editorial_image.py # CLI for standalone image generation
│
├── docs/                           # Served by GitHub Pages
│   ├── index.html                  # Auto-rebuilt archive index
│   └── YYYY-MM-DD.html             # One file per issue
│
├── digests/                        # Raw JSON per run (for future dashboard)
│   └── YYYY-MM-DD.json
│
├── subscribers.csv                 # Subscriber list (written at runtime by workflow)
├── requirements.txt
├── TODO.md
└── README.md
```

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production. GitHub Pages is served from here. Workflow YAMLs must live here to appear in the Actions tab. |
| `Dev-Nigg` | Adrian's active development branch. All new features go here first. |
| `dev` | Alejandro/Juan's shared dev branch (used by `newsletter-dev.yml`). |

**Critical:** GitHub Desktop determines which branch file writes land on. Always confirm the active
branch in GitHub Desktop **before** any file edit. Accidentally writing to `main` when `Dev-Nigg`
is intended is a recurring risk.

**GitHub Pages vs. local preview:** Pages only reflects `main`. To preview `Dev-Nigg` output,
open the generated HTML files directly from disk (`docs/YYYY-MM-DD.html`).

---

## Workflows

### `newsletter.yml` — Production
- **Trigger:** Scheduled `cron: "30 11 * * 1-5"` (~7 AM Mexico City / CST) + manual dispatch
- **Branch:** `main`
- **Subscribers:** `SUBSCRIBERS_CSV` secret
- **Sends email:** Yes
- **Commits to:** `main`

### `newsletter-dev.yml` — Shared Dev
- **Trigger:** Manual only
- **Branch:** `dev`
- **Inputs:** `friday_mode`
- **Subscribers:** `DEV_SUBSCRIBERS_CSV` secret
- **Commits to:** `dev`

### `newsletter-adrian.yml` — Adrian's Personal Test
- **Trigger:** Manual only
- **Branch:** `Dev-Nigg`
- **Inputs:** `friday_mode`, `mock_mode`, `skip_email` (default: `true`)
- **Subscribers:** `DEV_SUBSCRIBERS_CSV` secret
- **Commits to:** `Dev-Nigg`
- **Note:** `skip_email` defaults to `true` to prevent accidental sends during test runs.

---

## Environment Variables & Secrets

All secrets are injected at runtime via GitHub Actions secrets or a local `.env` file. **Never committed.**

| Variable | Description |
|----------|-------------|
| `NEWS_API_KEY` | NewsAPI key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `EMAIL_SENDER` | Gmail sender address |
| `EMAIL_PASSWORD` | Gmail App Password |
| `SUBSCRIBERS` / `SUBSCRIBERS_CSV` | Comma-separated subscriber emails |
| `DEV_SUBSCRIBERS_CSV` | Dev-only subscriber list |
| `BANXICO_API_KEY` | Banco de Mexico API (reserved for future use) |
| `HEALTH_CHECK_URL` | Healthchecks.io ping URL |
| `MOCK` | `true` to skip NewsAPI + Anthropic, use saved digest |
| `SKIP_EMAIL` | `true` to render archive only, skip email delivery |
| `SKIP_IMAGE` | `true` to skip OpenAI image generation (mock runs, CI without `OPENAI_API_KEY`) |
| `FORCE_FRIDAY` | `true` to simulate Friday mode (word cloud + week review) |
| `GITHUB_RAW_URL` | Asset base URL override (used in `newsletter-adrian.yml` to serve assets from `Dev-Nigg`) |

**Local development:** Create a `.env` file in `bot/` (never committed) and load with:
```bash
export $(cat .env | xargs) && python main.py
```

---

## Testing Conventions

- **Mock mode** (`MOCK=true`): Skips NewsAPI and Anthropic API calls, loads latest saved digest JSON.
  Use for UI/rendering changes that don't need fresh data.
- **Skip email** (`SKIP_EMAIL=true`): Runs the full pipeline but skips SMTP delivery.
  Archive HTML is still generated and committed. Default in `newsletter-adrian.yml`.
- **Local preview:** Run `python main.py` from `bot/`, then open `docs/YYYY-MM-DD.html` in browser.
- **Test email:** Run `python test_email.py` to send a mock email without a full pipeline run.

---

## APIs & Dependencies

| Service | Used for | Cost |
|---------|----------|------|
| NewsAPI | Article fetching | Free (100 req/day) |
| Anthropic Claude API | Bilingual summarization, editor note, sentiment | ~$0.05-0.08/run |
| Yahoo Finance | Market tickers + currency rates | Free |
| Open-Meteo | Weather block | Free |
| Gmail SMTP | Email delivery | Free |
| GitHub Actions | Scheduling + CI | Free (~5 min/run) |
| GitHub Pages | Archive hosting | Free |

**Python dependencies** (`requirements.txt`):
`anthropic`, `requests`, `beautifulsoup4`, `lxml`, `wordcloud`, `Pillow`, `imagehash`, `scikit-learn`, `pyyaml`

---

## Key Configuration (`config.py`)

- **Newsletter name:** `The Opening Bell` / **Tagline:** `Context before the noise`
- **Topics (ES):** finanzas, economia, Mexico, comercio, mercados, politica, criptomonedas
- **Language:** Spanish (`es`) for email; English (`en`) available as archive toggle
- **Domain allowlist:** 14 curated outlets (Bloomberg Linea, El Financiero, Reuters, FT, WSJ, etc.)
- **Currency matrix:** MXN, USD, BRL, EUR, CNY, CAD, GBP, JPY (browser toggle); email uses USD base only
- **Tickers:** S&P 500, IBEX 35, Euro Stoxx, DAX
- **Weather:** Currently configured for Madrid (`WEATHER_LAT/LON/CITY` in `config.py`)
- **Rotating pen names:** 22 fake bylines + 27 fake titles, randomized per run
- **Archive output:** `docs/` (GitHub Pages root); `digests/` for raw JSON

---

## Known Gotchas

1. **Unicode in YAML comments:** Unicode characters (arrows, box-drawing chars, em-dashes) in YAML
   inline comments cause parser failures. Use ASCII only in workflow files.

2. **`edit_file` with box-drawing characters:** The Filesystem MCP `edit_file` tool fails silently
   when `oldText` contains Unicode box-drawing characters. Workaround: target ASCII-only anchor
   strings, or rewrite the entire section.

3. **WordCloud accent stripping:** The `wordcloud` library strips accents before stopword matching.
   Accented stopwords must be normalized to ASCII before passing to WordCloud.

4. **Workflow YAMLs must live on `main`:** Even if the workflow uses `ref: Dev-Nigg` to run code
   from the dev branch, the YAML itself must exist on `main` to appear in the GitHub Actions tab.

5. **`write_file` to create, `edit_file` to modify:** `edit_file` requires a pre-existing file and
   cannot create new ones from scratch.

6. **`GITHUB_RAW_URL` for asset serving:** In `newsletter-adrian.yml`, this is set to the raw
   GitHub URL for `Dev-Nigg/docs/` so that word cloud images resolve correctly without a Pages
   deploy on the dev branch.

7. **`subscribers.csv` is runtime-generated:** The workflow writes this file from the
   `SUBSCRIBERS_CSV` secret before running the bot. Do not rely on the committed version for
   production subscriber data.

---

## File Editing Rules

- **Always ask Adrian before making any changes to files, no matter the context.**
- Read all relevant files before planning any edit (`read_multiple_files` to map dependencies).
- **Full rewrites** preferred over many surgical edits when changes are pervasive.
- **`edit_file`** for targeted, unambiguous single-location changes.
- Always confirm the active branch in GitHub Desktop before writing files.

---

## Roadmap

- [x] VPS migration -- pipeline runs on VPS cron; GitHub Actions retained for dev/test only
- [x] Image generation subsystem -- `lib/` fully built with registry, anti-repetition, similarity checks
- [ ] Wire image generation into `main.py` -- call `generate_editorial_image()` per story after summarizer, inject `image_path` into digest dict, add conditional `<img>` in both renderers
- [ ] Health monitoring (Healthchecks.io)
- [ ] Substack integration + freemium commercial launch (~12 month horizon)
- [ ] Unsubscribe links + subscriber token system
- [ ] Resend/Mailgun migration for deliverability at scale
- [ ] Global content expansion -- expand `NEWS_DOMAINS` and `TOPICS` beyond Spanish LatAm press
