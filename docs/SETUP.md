# Engineering Documentation — The Opening Bell

> **Audience:** New developers joining the project.
> **Scope:** Architecture, VPS setup, cron jobs, nginx, Cloudflare Tunnel, debugging, manual operations.
>
> **Outdated (2026-10-13):** the VPS and cron parts of this guide are retired. Production now runs on the home server with Docker Compose and Windows Task Scheduler; nginx and the Cloudflare Tunnel are still used, as Docker services. Current reference: `PROJECT_STATE.md` and `docs/system_overview.md`.

---

## 1. System Overview

**The Opening Bell** (also *The Periphery* / *Mexico Finance Brief*) is a fully automated bilingual (ES/EN) financial newsletter focused on Latin American markets and macro intelligence.

Every weekday morning the pipeline:
1. Fetches recent articles from **NewsAPI** across configured Spanish-language topics.
2. Scrapes full article text, scores candidates by freshness/authority/relevance.
3. Sends the top articles to the **Anthropic Claude API**, which writes the editor note, selects stories, scores market sentiment, picks a quote, and produces bilingual output.
4. Pulls live market data (tickers, currency rates, weather) from **Yahoo Finance** and **Open-Meteo**.
5. Sends a **Gmail-safe HTML email** via SMTP to all subscribers.
6. Generates a **pretty HTML archive page** and saves it to `docs/`.
7. Sends a **Telegram notification** with the issue headline.
8. Runs a separate **hero image candidate generation** step: three AI-generated images are produced and sent to Telegram for editorial selection.
9. After an editor picks an image via Telegram, `telegram_handler.py` rerenders the archive page with the selected image and publishes it via `rsync` to the nginx web root.

### Main Components

| Component | Role |
|-----------|------|
| `main.py` | Orchestrates the full daily pipeline run |
| `generate_candidates.py` | Generates hero image candidates, sends to Telegram |
| `telegram_handler.py` | Polls Telegram for editorial callbacks (select/regenerate/skip) |
| `publish_site.py` | Rsyncs `docs/` to the nginx web root |
| `rerender.py` | Rerenders a single archive page from its stored digest |
| `archive.py` | Saves per-issue HTML pages and rebuilds `index.html` |
| `pretty_renderer.py` | Builds the full-featured archive HTML for each issue |
| `renderer.py` | Builds the Gmail-safe email HTML |
| `delivery.py` | Sends email via SMTP (Gmail, port 587 STARTTLS) |
| `summarizer.py` | Calls Claude API, returns structured bilingual JSON |
| `fetcher.py` | Fetches articles from NewsAPI with domain allowlist |
| `scorer.py` | Pre-scores and deduplicates articles before Claude |
| `scraper.py` | Scrapes full article text via BeautifulSoup |
| `market_data.py` | Yahoo Finance tickers, currency matrix, weather |
| `storage.py` | Reads/writes digest JSONs, computes weekly summaries |
| `wordcloud_gen.py` | Generates weekly word cloud image (Fridays only) |
| `image_gen.py` | Pure function: derives hero image prompt from lead story |
| `image_candidates.py` | Calls OpenAI Images API to generate 3 candidate PNGs |
| `config.py` | All settings and secrets (reads from env vars) |

### High-Level Architecture

```
Cron (VPS)
  └── main.py
        ├── fetcher.py  →  NewsAPI
        ├── scorer.py   →  ranked article list
        ├── summarizer.py → Anthropic Claude API
        ├── market_data.py → Yahoo Finance / Open-Meteo
        ├── storage.py  →  digests/YYYY-MM-DD.json
        ├── renderer.py + delivery.py → Gmail SMTP → subscribers
        ├── archive.py + pretty_renderer.py → docs/YYYY-MM-DD.html
        ├── telegram_bot.py → Telegram notification
        └── (next cron) generate_candidates.py
              ├── image_candidates.py → OpenAI Images API
              └── Telegram: 3 photo candidates + Select buttons

Editor picks image via Telegram
  └── (next poll) telegram_handler.py
        ├── rerender.py → docs/YYYY-MM-DD.html (updated)
        └── publish_site.py → rsync → /var/www/newsletter/

nginx serves /var/www/newsletter/
  └── Cloudflare Tunnel → newsletter.mustardhq.dev
```

---

## 2. Directory Structure

```
/home/adrian/project/
├── bot/                    # All Python source code
│   ├── main.py             # Pipeline entry point
│   ├── config.py           # All settings + secrets
│   ├── .env                # Local secrets (never committed)
│   └── .telegram_offset    # Persists Telegram polling offset between cron runs
│
├── docs/                   # Generated HTML (archive + index)
│   ├── index.html          # Auto-rebuilt archive index
│   ├── YYYY-MM-DD.html     # One file per issue
│   ├── images/             # Selected hero images (YYYY-MM-DD.png)
│   └── wordcloud-YYYY-Www.png  # Weekly word clouds
│
├── digests/                # Raw JSON per run (source of truth for rerenders)
│   └── YYYY-MM-DD.json     # One file per run; contains digest, market, visual data
│
├── tmp_images/             # Temporary hero image candidates (before editorial selection)
│   └── YYYY-MM-DD/         # Per-issue subfolder
│       ├── r1_opt1.png     # Round 1, option 1
│       ├── r1_opt2.png
│       └── r1_opt3.png
│
├── venv/                   # Python virtualenv (not committed)
├── requirements.txt
└── subscribers.csv         # Subscriber list (active column controls delivery)
```

**Key points:**
- `docs/` is the source for both nginx (via rsync) and GitHub Pages.
- `digests/` is the authoritative data store; all rerenders read from here.
- `tmp_images/` holds AI-generated candidates until one is selected; non-selected files are deleted automatically after selection.
- `bot/.telegram_offset` persists the Telegram update offset so callbacks are never reprocessed across cron runs.

---

## 3. Pipeline Flow

### 3.1 `main.py` — Daily newsletter run

Executed by cron every weekday morning. Steps:

1. **Duplicate guard** — if `digests/YYYY-MM-DD.json` already exists and `FORCE_RUN` is not set, exits immediately.
2. **Market data** (step 1/5) — fetches tickers, secondary tickers, and currency table in parallel via `ThreadPoolExecutor`.
3. **News fetch** (step 2/5) — `fetcher.py` queries NewsAPI for each configured topic. Deduplicates against articles seen in the last 5 days (`get_recent_urls`). Enforces domain allowlist, per-source caps, and the domain blocklist.
4. **Scoring** (step 2.5/5) — `scorer.py` scores each article on freshness (30%), source authority (25%), and topic relevance (25%), then runs a greedy headline deduplication pass. Returns the top `MAX_ARTICLES_FOR_CLAUDE` articles.
5. **Summarize** (step 3/5) — `summarizer.py` sends the ranked articles to Claude. Claude writes editor note, picks 4–6 stories, scores sentiment (0–100 position + label), selects a quote, and returns a bilingual JSON blob.
6. **Hero prompt** (step 3.5/5) — `image_gen.py` derives a visual metadata dict (category, hero prompt, option summaries) from the lead story. No API calls; pure function.
7. **Save digest** (step 4/5) — `storage.py` writes `digests/YYYY-MM-DD.json` containing `digest`, `market`, and `visual` blocks.
8. **Email** (step 5/5) — `renderer.py` builds Gmail-safe HTML; `delivery.py` sends via SMTP to all active subscribers in `subscribers.csv`.
9. **Archive** (step 6/6) — `archive.py` calls `pretty_renderer.py` to build the full HTML page, writes it to `docs/YYYY-MM-DD.html`, and rebuilds `docs/index.html`.
10. **Telegram notification** — `telegram_bot.py` sends a brief run summary (headline, category, archive URL) to the configured chat.

**Files written:**
- `digests/YYYY-MM-DD.json`
- `docs/YYYY-MM-DD.html`
- `docs/index.html`

### 3.2 `generate_candidates.py` — Hero image generation

Run by cron shortly after `main.py`. Steps:

1. Reads `digests/YYYY-MM-DD.json`.
2. **Guard 1:** if `visual.hero_image` is already set (image locked), exits cleanly.
3. **Guard 2:** if candidates for the current round already exist on disk, exits cleanly.
4. Calls `image_candidates.py` → OpenAI Images API → generates 3 PNG files in `tmp_images/YYYY-MM-DD/`.
5. Updates the digest JSON with candidate paths and round counters.
6. Sends 3 photos + Select buttons to Telegram, followed by a control message (Regenerate / Skip).

**Files written:**
- `tmp_images/YYYY-MM-DD/r{N}_opt{1,2,3}.png`
- `digests/YYYY-MM-DD.json` (updated `visual` block)

### 3.3 `telegram_handler.py` — Editorial callback processor

Run by cron every few minutes. Polls Telegram `getUpdates` once per execution. Handles three callback types:

| Callback | Action |
|----------|--------|
| `select\|YYYY-MM-DD\|optN` | Copies candidate PNG to `docs/images/YYYY-MM-DD.png`, updates digest JSON (`hero_image`, `hero_selected`), rerenders archive page via `rerender.py`, publishes via `publish_site.py`, cleans up non-selected tmp files. |
| `regenerate\|YYYY-MM-DD` | Increments round counter, generates a new batch of 3 candidates (max 2 regenerations total), sends new photos to Telegram. |
| `skip\|YYYY-MM-DD` | Acknowledges; no further action. |

Uses a **file lock** (`/tmp/telegram_handler.lock`) to prevent concurrent executions.
Persists polling offset in `bot/.telegram_offset`.

**Files written on selection:**
- `docs/images/YYYY-MM-DD.png` (copied from tmp)
- `digests/YYYY-MM-DD.json` (locked)
- `docs/YYYY-MM-DD.html` (rerendered)
- `/var/www/newsletter/` (synced via rsync)

### 3.4 `publish_site.py` — Site publishing

Called automatically by `telegram_handler.py` after a successful selection. Can also be called manually.

Runs:
```
rsync -a --delete <ARCHIVE_DIR>/ <PUBLISH_WEB_ROOT>
```

Skips silently if `PUBLISH_WEB_ROOT` is not set. All errors are logged but non-fatal.

---

## 4. Environment Setup

### 4.1 VPS

| Item | Value |
|------|-------|
| OS | Ubuntu (Hetzner VPS) |
| Project root | `/home/adrian/project/` |
| Python virtualenv | `/home/adrian/project/venv/` |
| nginx web root | `/var/www/newsletter/` |
| Public URL | `https://newsletter.mustardhq.dev` |

### 4.2 Python

```bash
# Activate virtualenv
source /home/adrian/project/venv/bin/activate

# Deactivate when done
deactivate
```

Python version: **3.11+** (required for `dict | None` type union syntax).

Dependencies are in `requirements.txt`. Install with:
```bash
pip install -r requirements.txt
```

### 4.3 `.env` file

Located at `bot/.env` — never committed. Loaded automatically by `main.py` via `python-dotenv`.

To apply manually for a shell session:
```bash
export $(grep -v '^#' /home/adrian/project/bot/.env | xargs)
```

### 4.4 Key Environment Variables

| Variable | Description |
|----------|-------------|
| `NEWS_API_KEY` | NewsAPI.org key for article fetching |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key for summarization |
| `OPENAI_API_KEY` | OpenAI key used by `image_candidates.py` for image generation |
| `EMAIL_SENDER` | Gmail address used as the sending account |
| `EMAIL_PASSWORD` | Gmail App Password (not the account password) |
| `SUBSCRIBERS` | Comma-separated fallback subscriber list if `subscribers.csv` is absent |
| `TELEGRAM_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID for editorial messages |
| `PUBLIC_ARCHIVE_BASE_URL` | Public base URL for archive links (e.g. `https://newsletter.mustardhq.dev`) |
| `PUBLISH_WEB_ROOT` | Destination for rsync publish (e.g. `/var/www/newsletter`) |
| `SKIP_EMAIL` | Set to `true` to skip SMTP delivery; archive is still generated |
| `MOCK` | Set to `true` to skip NewsAPI + Anthropic and load the latest saved digest |
| `FORCE_RUN` | Set to `true` to bypass the duplicate-run guard |
| `FORCE_FRIDAY` | Set to `true` to simulate a Friday run (word cloud + week review) |
| `BANXICO_API_KEY` | Banco de México API key (reserved for future use) |

---

## 5. Cron Jobs

Cron runs as the `adrian` user. View/edit with:
```bash
crontab -e
```

### Typical cron entries

```cron
# Main newsletter pipeline — 7:00 AM Mexico City (CST = UTC-6)
0 13 * * 1-5 cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python main.py >> /home/adrian/logs/newsletter.log 2>&1

# Hero image generation — 7:15 AM (after main.py finishes)
15 13 * * 1-5 cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python generate_candidates.py >> /home/adrian/logs/candidates.log 2>&1

# Telegram callback handler — every 2 minutes during business hours
*/2 13-22 * * 1-5 cd /home/adrian/project/bot && /home/adrian/project/venv/bin/python telegram_handler.py >> /home/adrian/logs/telegram_handler.log 2>&1
```

**Timezone note:** The VPS system clock runs in UTC. Mexico City Standard Time is UTC−6 (CST); UTC−5 during Daylight Saving Time (CDT, approximately March–November). Adjust cron times accordingly when DST changes.

**Log files:** Stored in `/home/adrian/logs/`. Check these first when debugging.

---

## 6. nginx + Publishing

### Why nginx does not serve from `docs/` directly

`docs/` lives inside the git repository at `/home/adrian/project/docs/`. Serving directly from a git repo working directory is risky:
- Git operations (pull, merge) can temporarily corrupt or replace files while nginx is reading them.
- The git index and object store are co-located; accidentally exposing `.git/` is a security risk.
- Permissions and ownership are cleaner when the web root is a dedicated directory.

Instead, the pipeline rsyncs the generated files to a separate, dedicated web root.

### nginx configuration

nginx serves from:
```
/var/www/newsletter/
```

Typical nginx server block (simplified):
```nginx
server {
    listen 80;
    server_name newsletter.mustardhq.dev;
    root /var/www/newsletter;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Publishing step

After generating or updating files in `docs/`, sync to nginx:
```bash
rsync -a --delete /home/adrian/project/docs/ /var/www/newsletter/
```

- `-a` preserves timestamps, permissions, symlinks.
- `--delete` removes files from the destination that no longer exist in the source.
- The trailing `/` on the source is critical — it copies the **contents** of `docs/`, not the directory itself.

This is called automatically by `publish_site.py` (triggered by `telegram_handler.py` after image selection). For manual rebuilds, run it explicitly.

---

## 7. Cloudflare Tunnel Setup

Cloudflare Tunnel exposes the local nginx server to the internet without opening any inbound ports on the VPS.

### Tunnel creation

```bash
cloudflared tunnel create newsletter
```

This generates a tunnel UUID and writes credentials to:
```
~/.cloudflared/<UUID>.json
```

### Config file

Located at `~/.cloudflared/config.yml`:

```yaml
tunnel: <UUID>
credentials-file: /home/adrian/.cloudflared/<UUID>.json

ingress:
  - hostname: newsletter.mustardhq.dev
    service: http://127.0.0.1:80
    originRequest:
      httpHostHeader: newsletter.mustardhq.dev
  - service: http_status:404
```

The `httpHostHeader` must match the nginx `server_name` so nginx routes the request correctly.

### Validate config

```bash
cloudflared tunnel validate
```

---

## 8. DNS Configuration

### CNAME record

In the Cloudflare dashboard, the DNS CNAME for `newsletter.mustardhq.dev` must point to:
```
<tunnel-UUID>.cfargotunnel.com
```

The UUID must exactly match the tunnel created in step 7. A wrong UUID causes a **502** or **1033** error at the Cloudflare edge.

### Creating the DNS record via CLI

```bash
cloudflared tunnel route dns newsletter newsletter.mustardhq.dev
```

This automatically creates the CNAME in Cloudflare DNS.

### Known DNS bugs encountered

| Error | Cause | Fix |
|-------|-------|-----|
| **502 Bad Gateway** | Wrong tunnel UUID in CNAME, or tunnel not running | Verify UUID matches; check `systemctl status cloudflared` |
| **530** | DNS record missing or not propagated | Run `dig newsletter.mustardhq.dev CNAME` and verify the record |
| **1033** | CNAME created via UI points to a different tunnel than the one running | Delete the UI-created record; recreate with `cloudflared tunnel route dns` |

**Key insight:** If curl and nginx logs show zero incoming requests even though the tunnel appears healthy, traffic is routing to the wrong tunnel (UUID mismatch). The Cloudflare dashboard request counter on the tunnel page will be zero.

---

## 9. Systemd Service

Running `cloudflared` as a systemd service ensures it restarts automatically on reboot or crash.

### Install

```bash
sudo cloudflared service install
```

This copies the current `~/.cloudflared/config.yml` into a system-level service unit.

### Commands

```bash
sudo systemctl start cloudflared
sudo systemctl stop cloudflared
sudo systemctl restart cloudflared
sudo systemctl status cloudflared
sudo systemctl enable cloudflared   # auto-start on boot
```

### Config path (after service install)

```
/etc/cloudflared/config.yml
```

If you edit the config after installing the service, edit `/etc/cloudflared/config.yml` (not `~/.cloudflared/config.yml`) and restart the service.

---

## 10. Debugging Guide

### Cloudflare errors

| Code | Meaning | What to check |
|------|---------|---------------|
| **502** | Tunnel is running but nginx is not responding | `sudo systemctl status nginx`, `curl http://127.0.0.1` |
| **530** | No DNS record or record points to nothing | `dig newsletter.mustardhq.dev CNAME` |
| **1033** | Tunnel UUID mismatch between CNAME and running tunnel | Check UUID in `/etc/cloudflared/config.yml` vs CNAME value |

### Key diagnostic commands

```bash
# Is nginx running and serving files?
sudo systemctl status nginx
curl -s http://127.0.0.1 | head -20

# Is the tunnel running?
sudo systemctl status cloudflared
journalctl -u cloudflared -n 50 --no-pager

# What does the CNAME resolve to?
dig newsletter.mustardhq.dev CNAME

# Is the config valid?
cloudflared tunnel validate

# nginx access and error logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Pipeline logs (from cron)
tail -f /home/adrian/logs/newsletter.log
tail -f /home/adrian/logs/candidates.log
tail -f /home/adrian/logs/telegram_handler.log
```

### Key diagnostic insight

If the Cloudflare dashboard shows **zero requests** on the tunnel even after multiple browser visits, traffic is not reaching the intended tunnel. This always means a UUID mismatch in the CNAME — not a code problem.

---

## 11. Running the System

### Activate virtualenv

```bash
source /home/adrian/project/venv/bin/activate
cd /home/adrian/project/bot
```

### Normal manual run

Runs the full pipeline for today if no digest exists yet:
```bash
python main.py
```

### Forced rerun (override duplicate guard)

Re-runs the pipeline even if today's digest already exists. **Overwrites** `docs/YYYY-MM-DD.html` and `digests/YYYY-MM-DD.json`:
```bash
FORCE_RUN=true python main.py
```

### Mock + skip email (UI/rendering changes only)

Skips NewsAPI and Anthropic calls; loads the latest saved digest. No email is sent:
```bash
MOCK=true SKIP_EMAIL=true python main.py
```

### Friday simulation (word cloud + week review)

```bash
FORCE_FRIDAY=true python main.py
```

### Generate image candidates manually

```bash
python generate_candidates.py
# or for a specific date:
python generate_candidates.py --date 2026-04-07
```

### Run Telegram handler manually

Polls once and processes any pending callbacks:
```bash
python telegram_handler.py
```

### Rerender a single issue

Reads the stored digest JSON and regenerates the HTML page. Useful after manually editing a digest or selecting a hero image:
```bash
python rerender.py 2026-04-07
```

---

## 12. Manual Maintenance / Rebuild Commands

Use these after code changes, chart updates, or any time the nginx web root needs to be brought in sync with `docs/`.

### A. Pull latest code

```bash
cd /home/adrian/project
git pull origin main
```

If testing from a feature branch:
```bash
git pull origin Dev-Nigg
```

Always confirm the active branch before pulling to avoid overwriting unintended state.

### B. Activate virtualenv

```bash
source /home/adrian/project/venv/bin/activate
```

Must be done before running any Python script.

### C. Rebuild archive index manually

Regenerates `docs/index.html` (the archive landing page with the sentiment timeline chart, issue list, and coverage map) from all existing digests in `digests/`. Does **not** touch individual issue pages.

```bash
cd /home/adrian/project/bot
python -c "import sys; sys.path.insert(0, '.'); from archive import rebuild_index; rebuild_index()"
```

Use this after:
- Changing the chart or layout in `archive.py`
- Adding or removing digests
- Updating the economic calendar in `config.py`

### D. Publish updated docs to nginx web root

Syncs the entire `docs/` directory to `/var/www/newsletter/`:

```bash
rsync -a --delete /home/adrian/project/docs/ /var/www/newsletter/
```

This is required any time files in `docs/` change and you want those changes to be live. The pipeline calls this automatically after image selection, but manual code changes require running it explicitly.

### E. All-in-one manual rebuild/publish sequence

Run this after any archive or index-level code change (e.g. updating the sentiment chart, changing `archive.py`):

```bash
cd /home/adrian/project
source venv/bin/activate
cd bot
python -c "import sys; sys.path.insert(0, '.'); from archive import rebuild_index; rebuild_index()"
rsync -a --delete /home/adrian/project/docs/ /var/www/newsletter/
```

After these two commands, the live site at `https://newsletter.mustardhq.dev` will reflect the changes immediately.

### F. Future helper scripts (recommended)

The manual sequence above should eventually be encapsulated in a helper to reduce errors and save typing. Recommended options:

- **`rebuild.sh`** — pulls latest, activates venv, rebuilds index, rsyncs.
- **`deploy.sh`** — same as above but also verifies nginx is responding after publish.
- **`Makefile`** targets — `make rebuild`, `make publish`, `make logs`.

Do not implement these ad-hoc; design them with proper error handling and exit codes so cron can also call them safely.

---

## 13. Known Improvements / TODO

| Area | Status | Notes |
|------|--------|-------|
| **Preview environment** | Partial | `PREVIEW_MODE=true` routes output to `docs/preview/` and `digests/preview/`. GitHub Actions workflow `newsletter-preview.yml` deploys to GitHub Pages. VPS preview publishing not yet wired up. |
| **Subscriber database** | Not started | Currently a flat `subscribers.csv`. A SQLite or Postgres-backed subscriber store with unsubscribe tokens and bounce tracking is needed before scaling. |
| **Monitoring / health checks** | Not started | `HEALTH_CHECK_URL` env var is reserved for a Healthchecks.io ping after each successful run. Add a ping in `main.py` at the end of `run()`. |
| **Helper scripts** | Not started | `rebuild.sh` / `deploy.sh` / `Makefile` to replace the manual multi-step sequence in section 12E. |
| **Dry-run / preview publishing** | Not started | A `--dry-run` flag for `publish_site.py` that shows what rsync would change without writing anything, for safer pre-flight checks. |
| **TEST_MODE** | Not started | A mode that runs the full pipeline but writes to isolated paths and sends to a single test address only, distinct from `MOCK_MODE`. |
| **VPS scheduling migration** | Planned | Cron on the VPS is the current scheduler. Consider migrating to a proper task queue (e.g. Celery + Redis, or systemd timers with proper dependency ordering). |
| **Substack integration** | 12-month horizon | Freemium commercial launch via Substack. Requires unsubscribe links, subscriber token system, and Resend/Mailgun migration for deliverability at scale. |
| **Full-text search on archive** | Planned | Lunr.js client-side search on `index.html` (search index already generated as JSON in `rebuild_index`). |
