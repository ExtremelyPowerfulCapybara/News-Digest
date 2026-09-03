# PROJECT_STATE.md — The Opening Bell / The Periphery
# Comprehensive agent reference — last updated 2026-09-03

> **Rule #1:** Always ask Adrian before making any changes to files, no matter the context.

---

## Identity

| Field | Value |
|---|---|
| Name | **The Opening Bell** (a.k.a. *The Periphery*, *Mexico Finance Brief*) |
| Tagline | *Context before the noise* |
| Type | Automated bilingual (ES/EN) financial newsletter |
| Focus | Emerging markets, LatAm macro, global trade, geopolitics |
| Archive | https://newsletter.mustardhq.dev |
| GitHub | https://github.com/ExtremelyPowerfulCapybara/News-Digest |
| GitHub Pages (dev preview) | https://extremelypowerfulcapybara.github.io/News-Digest/ |
| Issues published | 33+ (as of 2026-09-03) |

**Team:**
- **Adrian** — Mexico City. Technical lead, infrastructure, repo owner.
- **Alejandro** — Madrid. Editorial direction, economics coverage.
- **Juan** — Buenos Aires. Visual identity, trading and politics coverage.

**Goal:** Self-sustaining publication with a paying subscriber base (2-3 year horizon). Year one = audience building. Long-term model: freemium on Substack.

---

## Infrastructure (Current — as of 2026-09-03)

**Production runs on Mustard Server (Adrian's home server), NOT on a VPS or GitHub Actions.**

| Component | Details |
|---|---|
| Host | Mustard Server — Windows 10, `192.168.1.70` |
| Runtime | Docker Compose (`docker compose run --rm app python main.py`) |
| Scheduler | Windows Task Scheduler — `\MustardHQ\Newsletter Pipeline` |
| Schedule | Mon-Fri 07:30 CDMX |
| Run script | `scripts/run_newsletter.ps1` |
| Logs | `C:\Projects\logs\newsletter_YYYY-MM-DD.log` |
| Secrets | `bot/.env` (gitignored — never committed) |
| Archive serving | nginx container → Cloudflare Tunnel → `newsletter.mustardhq.dev` |
| GitHub Pages | Updated automatically after each run (auto-commit to `main`) |

**Docker Compose services:**
- `app` — pipeline (run on demand, not long-running)
- `nginx` — serves `docs/` as public archive
- `cloudflared` — Cloudflare Tunnel (UUID `a58b9fec-...`) to `newsletter.mustardhq.dev`

**To run the pipeline manually:**
```bash
cd C:/Projects/News-Digest
docker compose run --rm app python main.py

# Force re-run when today's digest already exists:
docker compose run --rm -e FORCE_RUN=true app python main.py

# Skip email (archive only):
docker compose run --rm -e SKIP_EMAIL=true app python main.py

# After code changes — rebuild image first:
docker compose build
docker compose run --rm app python main.py
```

---

## Pipeline — Step by Step

`bot/main.py` orchestrates the full run:

```
[1/5]   Fetch market data (parallel: tickers, secondary tickers, currency table)
[2/5]   Fetch news articles via NewsAPI (ES + EN topics, domain allowlist)
         → Deduplicate URLs seen in last 5 days
[2.5/5] Score and rank articles (scorer.py) → top 12 sent to Claude
[3/5]   Summarize with Claude (Anthropic API) → bilingual JSON digest (ES + EN)
[3.5/5] Generate hero image (OpenAI gpt-image-2, via lib/image_generator.py)
         → anti-repetition: pHash + TF-IDF two-phase rejection, 4 attempts max
         → saved to docs/images/YYYY-MM-DD_hero.png
[4/5]   Save digest JSON to digests/YYYY-MM-DD.json
[5/5]   Build and send email (Gmail SMTP STARTTLS:587)
         → Friday mode: includes word cloud + week-in-review timeline
[6/6]   Save pretty HTML archive to docs/YYYY-MM-DD.html + rebuild index.html
[7/7]   Send Telegram notification to Adrian's DM (chat_id: 6446426681)
```

After the pipeline, `run_newsletter.ps1` auto-commits `docs/` + `digests/` and pushes to `main`.

---

## Repo Structure

```
News-Digest/
├── .github/workflows/
│   ├── newsletter-adrian.yml   # Manual, Dev-Nigg branch, Adrian's test runs
│   ├── newsletter-dev.yml      # Manual, dev branch, shared dev
│   ├── newsletter-preview.yml  # Manual, preview mode → GitHub Pages
│   └── newsletter.yml.disabled # Old production workflow — DISABLED
│
├── bot/                        # All pipeline Python source
│   ├── main.py                 # Entry point — orchestrates full run
│   ├── config.py               # Settings + secrets (reads env vars)
│   ├── fetcher.py              # NewsAPI fetching, domain allowlist
│   ├── scraper.py              # Full article body extractor (BeautifulSoup)
│   ├── scorer.py               # Article ranking before Claude call
│   ├── summarizer.py           # Claude API → structured bilingual JSON
│   ├── market_data.py          # Yahoo Finance tickers, currency table
│   ├── storage.py              # Digest JSON save/load, week/thread logic
│   ├── renderer.py             # Gmail-safe HTML email (tables, inline styles)
│   ├── pretty_renderer.py      # Archive HTML (Google Fonts, gauge, bilingual toggle)
│   ├── archive.py              # Saves pretty issues, rebuilds index.html
│   ├── delivery.py             # Gmail SMTP sender (STARTTLS:587)
│   ├── image_gen.py            # Hero image orchestration → calls lib/image_generator.py
│   ├── telegram_bot.py         # Post-run Telegram notification
│   ├── telegram_handler.py     # Interactive Telegram bot (image candidate selection)
│   ├── generate_candidates.py  # Sends image candidates to Telegram for editorial pick
│   ├── wordcloud_gen.py        # Friday word cloud generator
│   ├── mock_data.py            # Mock digest for dry runs
│   ├── prompt_map.py           # Hero image prompt templates per story tag
│   ├── market_data.py          # Yahoo Finance + currency data
│   ├── scorer.py               # Article ranking
│   ├── rerender.py             # Re-render an existing digest JSON without re-fetching
│   ├── test_email.py           # Send test email with mock data
│   ├── test_preview_config.py  # Preview config test
│   ├── .env                    # Secrets (gitignored — never commit)
│   ├── .env.template           # Reference for all required env vars
│   └── utils/urls.py           # Issue URL builder
│
├── lib/                        # Image generation subsystem
│   ├── image_generator.py      # Full pipeline: registry, retry loop, DB persistence
│   │                           # Two API paths: Responses API → Images API fallback
│   ├── image_prompt_builder.py # Prompt assembly, category presets, novelty directives
│   ├── image_history_store.py  # SQLite: image_history + generation_attempts tables
│   ├── image_similarity.py     # pHash + TF-IDF two-phase rejection
│   └── image_registry.py       # Registry loader + history-aware component selection
│
├── config/
│   └── image_prompt_registry.yaml  # Per-category building blocks for image prompts
│
├── scripts/
│   ├── run_newsletter.ps1      # Task Scheduler entry point (pipeline + git push)
│   └── run_telegram.ps1        # Task Scheduler entry point (Telegram handler)
│
├── cloudflared/
│   └── config.yml              # Tunnel config (UUID a58b9fec, newsletter.mustardhq.dev)
│
├── docs/                       # GitHub Pages root + nginx-served archive
│   ├── index.html              # Auto-rebuilt archive index (sentiment chart, search)
│   ├── YYYY-MM-DD.html         # One file per issue (pretty, bilingual toggle)
│   └── images/                 # Hero images (YYYY-MM-DD_hero.png)
│
├── digests/                    # Raw digest JSON per issue
│   └── YYYY-MM-DD.json
│
├── data/                       # SQLite DBs (image history, generation attempts)
├── Dockerfile                  # python:3.12-slim + system deps
├── docker-compose.yml          # app + nginx + cloudflared services
├── nginx.conf                  # Serves docs/ from /var/www/newsletter
├── requirements.txt
├── TODO.md                     # Feature backlog
├── PROJECT_STATE.md            # This file
├── CLAUDE.md                   # Legacy agent context (outdated — use this file)
└── AGENTS.md                   # Legacy agent context (outdated — use this file)
```

---

## Environment Variables

All stored in `bot/.env` (gitignored). Reference: `bot/.env.template`.

| Variable | Value / Notes |
|---|---|
| `NEWS_API_KEY` | NewsAPI key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI key (image generation) |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` (gpt-image-1 retires Oct 23 2026) |
| `EMAIL_SENDER` | `openingbellbrief@gmail.com` |
| `EMAIL_PASSWORD` | Gmail App Password (16 chars, no spaces) |
| `SUBSCRIBERS` | Comma-separated subscriber emails |
| `TELEGRAM_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | `6446426681` (Adrian's personal DM with the bot) |
| `PUBLIC_ARCHIVE_BASE_URL` | `https://newsletter.mustardhq.dev` |
| `PUBLISH_WEB_ROOT` | Leave empty (nginx serves docs/ volume directly) |
| `SKIP_EMAIL` | `true` = render archive only, skip SMTP |
| `FORCE_RUN` | `true` = bypass duplicate-run guard |
| `MOCK` | `true` = skip NewsAPI + Anthropic, use saved digest |
| `SKIP_IMAGE` | `true` = skip OpenAI image generation |

---

## GitHub Actions Workflows (Dev/Test Only)

Production does NOT use GitHub Actions for scheduling. GH Actions is dev/test only.

| Workflow | Branch | Trigger | Email | Notes |
|---|---|---|---|---|
| `newsletter-adrian.yml` | `Dev-Nigg` | Manual | No (default) | Adrian's test runs |
| `newsletter-dev.yml` | `dev` | Manual | Yes | Shared dev (Alejandro/Juan) |
| `newsletter-preview.yml` | `Dev-Nigg` | Manual | No | Preview mode → GitHub Pages |
| `newsletter.yml.disabled` | — | Disabled | — | Old production workflow |

**GitHub Actions secrets** (still used by workflows above):
`NEWS_API_KEY`, `ANTHROPIC_API_KEY`, `EMAIL_SENDER`, `EMAIL_PASSWORD`,
`SUBSCRIBERS_CSV`, `DEV_SUBSCRIBERS_CSV`, `BANXICO_API_KEY`, `HEALTH_CHECK_URL`

---

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production. GitHub Pages served from here. Auto-committed after each run. |
| `Dev-Nigg` | Adrian's active development branch. All new features go here first. |
| `dev` | Alejandro/Juan's shared dev branch. |

---

## Key Configuration (`bot/config.py`)

- **Topics (ES):** finanzas, economía, México, comercio, mercados, política, criptomonedas
- **Topics (EN):** emerging markets, global trade, Federal Reserve, China economy, commodities, geopolitics, tariffs
- **Domain allowlist (20 outlets):** bloomberglinea.com, elfinanciero.com.mx, eleconomista.com.mx, expansion.mx, elpais.com, cincodias.elpais.com, ambito.com, reuters.com, apnews.com, infobae.com, lanacion.com.ar, eluniversal.com.mx, ft.com, wsj.com, bloomberg.com, economist.com, foreignpolicy.com, cnbc.com, axios.com, marketwatch.com
- **Max articles for Claude:** 12 (scored/ranked before submission)
- **Currency matrix:** MXN, USD, BRL, EUR, CNY, CAD, GBP, JPY (browser toggle); email = USD base, MXN/EUR/GBP/CNY
- **Main tickers:** DXY, 10Y UST, VIX, MSCI EM
- **Secondary tickers:** Global Equities (S&P 500, Nasdaq, Euro Stoxx, Nikkei), Commodities (Brent, Gold, Copper, Wheat), Crypto (BTC, ETH, SOL)
- **Rotating pen names:** 22 bylines + 27 titles, randomized per issue
- **Economic calendar:** Banxico, FOMC, INEGI CPI, BLS CPI dates through Dec 2026

---

## Email Content (Daily)

- Editor note (Claude-written, ES)
- 6-8 stories with headline, summary, source (bilingual ES/EN)
- Sentiment gauge + label
- Main macro ticker bar (DXY, 10Y UST, VIX, MSCI EM)
- Secondary market strips (Equities, Commodities, Crypto)
- Currency table
- Quote of the day
- Economic calendar (upcoming events)
- Hero image (OpenAI gpt-image-2, editorial illustration style)
- **Fridays only:** Word cloud + "This week in markets" stat block + week-in-review timeline

---

## Archive Site (newsletter.mustardhq.dev)

- Each issue has a full-featured HTML page with bilingual ES/EN toggle
- Sentiment gauge, market data, image, all sections
- `docs/index.html` — archive index with:
  - Sentiment timeline chart (all issues)
  - Stories-per-issue chart
  - Full-text search (client-side, no library needed)
  - Links to all issues

---

## Image Generation Subsystem

- **Status:** Fully wired into production (`bot/image_gen.py` → `lib/image_generator.py`)
- **Model:** `gpt-image-2` via OpenAI (requires org verification on OpenAI account)
- **API path:** Responses API first → Images API fallback
- **Anti-repetition:** pHash + TF-IDF two-phase rejection; up to 4 attempts per run
- **DB:** SQLite in `data/` — tracks image history + generation attempts
- **Registry:** `config/image_prompt_registry.yaml` — per-category building blocks
- **Output:** `docs/images/YYYY-MM-DD_hero.png` — committed to repo, served via nginx

---

## Telegram Bot

- **Post-run notification:** `bot/telegram_bot.py` — sends brief after each run (lead headline, category, archive URL)
- **Interactive handler:** `bot/telegram_handler.py` — accepts editorial commands
- **Image candidates:** `bot/generate_candidates.py` — sends image options to Telegram for editorial pick
- **Chat ID:** `6446426681` (Adrian's personal DM)
- **Run script:** `scripts/run_telegram.ps1` (Task Scheduler)

---

## Testing

```bash
# Full real run (force today):
docker compose run --rm -e FORCE_RUN=true app python main.py

# Mock run (no API calls, uses last saved digest):
docker compose run --rm -e MOCK=true app python main.py

# Skip email (archive only):
docker compose run --rm -e SKIP_EMAIL=true app python main.py

# Send test email only:
docker compose run --rm app python test_email.py

# Test Telegram notification:
docker compose run --rm app python -c "
from telegram_bot import send_telegram_issue_notification
send_telegram_issue_notification(
    {'en': {'stories': [{'headline': 'Test'}]}, 'visual': {}},
    '2026-09-03', 'https://newsletter.mustardhq.dev'
)"

# After code changes always rebuild first:
docker compose build
```

---

## Backlog (from TODO.md)

### In Progress
- [ ] Sentiment chart in Friday email
- [ ] Landing page → production (finalize branding, wire subscribe form to backend)

### Quick Wins
- [ ] RSS/Atom feed (`docs/feed.xml` generated after each run)
- [ ] Sector tags per story (Claude classifies by sector; enables archive filtering)
- [ ] Health monitoring (Healthchecks.io ping at end of each run)
- [ ] Global content expansion (add European/Asian English-language sources)

### Bigger Lift
- [ ] Paid tier + topic preferences (spec: `docs/superpowers/specs/2026-05-06-paid-tier-topic-preferences-design.md`)
- [ ] Market sections wired to subscription backend
- [ ] Unsubscribe links (unique token per subscriber)
- [ ] Resend/Mailgun migration (replace Gmail SMTP for scale)
- [ ] PWA + swipe navigation for mobile archive

### Someday
- Regulation watch section (DOF/SAT)
- Telegram/WhatsApp delivery
- Substack integration
- Portuguese expansion (Brazil)

---

## Known Gotchas

1. **Stale Docker image:** After any code change, run `docker compose build` before running the pipeline. The image COPYs source files at build time.
2. **Duplicate-run guard:** Pipeline skips if today's digest exists. Override with `FORCE_RUN=true`.
3. **Gmail App Password:** Google revokes these periodically. If SMTP auth fails (535), regenerate at myaccount.google.com → Security → App passwords.
4. **OpenAI org verification:** `gpt-image-2` requires verified organization on OpenAI account. If image gen fails with 403, this is why.
5. **Bloomberg/MarketWatch scraping:** These outlets return 403/401. Articles are fetched via NewsAPI metadata (title/description) but full body scraping fails — expected, non-fatal.
6. **FORCE_RUN=true:** Must be set as an env var override. Setting it in `.env` would skip every run.
7. **`docs/` volume mount:** Docker writes directly to the host `docs/` directory. Changes are visible immediately without rebuild.
8. **Branch risk:** All file edits land on whatever branch is active. Confirm branch before editing.
9. **Unicode in YAML:** Unicode box-drawing chars, em-dashes, etc. in YAML inline comments break the parser. Use ASCII only in workflow files.
