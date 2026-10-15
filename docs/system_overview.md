# System Overview — The Opening Bell / Mexico Finance Brief

> **Audience:** Technical collaborators new to this system.
> **Updated:** 2026-10-12
> **Source of truth:** `PROJECT_STATE.md` in the repo root has the full detail (env vars, backlog, gotchas). If this page and that file disagree, trust `PROJECT_STATE.md`.

---

## Section 1 — What the System Does

The Opening Bell (also called The Periphery / Mexico Finance Brief) is a fully automated, bilingual (ES/EN) newsletter pipeline. It runs every weekday morning on Adrian's home server and needs no manual input to produce and deliver the issue.

Every morning the system:

1. Fetches the day's financial news from a domain allowlist of Spanish- and English-language outlets
2. Scores the articles (with a cap per outlet) and sends the top 18 to Claude, together with today's date, upcoming calendar events, the market snapshot and recently used quotes. Claude writes a bilingual digest: stories, editor note, narrative thread, sentiment score, quote
3. Pulls live market data: currencies, equity indices, commodities, crypto
4. Generates a hero image with OpenAI (`gpt-image-2`), with an anti-repetition check against past images
5. Builds two outputs: a **Gmail-compatible HTML email** sent to subscribers, and a **web archive page** in `docs/`
6. Sends a Telegram notification and pushes the digest to the morning dashboard
7. Commits `docs/` and `digests/` to `main` (this also updates GitHub Pages)

Image candidates can additionally be reviewed through a Telegram bot (select / regenerate / skip). See Section 2.

---

## Section 2 — Where Things Run

There is **no VPS** any more. Production is one Windows PC (the server). Development happens on a second PC. The repo exists on both, at different paths.

| | **Server PC (production)** | **Main PC (development)** |
|---|---|---|
| Repo path | `C:\Projects\News-Digest` | `D:\GitHub\News-Digest` |
| Purpose | Daily scheduled run, public archive, email | Writing and testing changes |
| Branch | `main` | `Dev-Nigg` |
| Scheduled? | Yes, Windows Task Scheduler | No |

### On the server

```
Task Scheduler (\MustardHQ\)
  ├─ Newsletter Pipeline   Mon-Fri 06:30  → scripts/run_newsletter.ps1
  │     docker compose run --rm app python main.py
  │     git add docs/ digests/ → commit "Issue: YYYY-MM-DD" → push to main
  └─ Telegram Handler      every 5 min    → scripts/run_telegram.ps1
        docker compose run --rm app python telegram_handler.py
        commits/pushes any image selection

Docker Compose (docker-compose.yml)
  ├─ app          run on demand, never long-running (image news-digest-app:latest)
  ├─ nginx        serves ./docs read-only
  └─ cloudflared  Cloudflare Tunnel → newsletter.mustardhq.dev → nginx

morning-dashboard (separate project, same server)
  └─ receives the digest via POST to :5050/api/digest-push at the end of each run
```

The `app` container mounts `docs/`, `digests/`, `data/`, `tmp_images/` and `bot/.telegram_offset` from the host, so everything the pipeline writes lands directly in the repo folder and is served by nginx immediately.

### On the main PC

Same code, run manually. Use `MOCK=true` and/or `SKIP_EMAIL=true` for tests so no real subscribers get an email. The server pushes new issues to `main`, so pull before working.

---

## Section 3 — End-to-End Pipeline

`bot/main.py` is the single entry point and runs as one Python process.

| Step | What happens |
|---|---|
| Guard | Exits if `digests/YYYY-MM-DD.json` already exists, unless `FORCE_RUN=true` |
| 1. Market data | Yahoo Finance prices fetched in parallel: primary tickers, secondary tickers, FX table |
| 2. News | NewsAPI queried over Spanish and English topics, filtered to the domain allowlist, deduplicated against the last 5 days |
| 2.5. Score | `scorer.py` ranks by freshness, source authority, topic relevance and finance keywords, with a cap of 3 per outlet; top 18 go to Claude |
| 3. Summarize | `summarizer.py` returns a structured bilingual JSON digest |
| 3.5. Hero image | `image_gen.py` → `lib/image_generator.py` generates the image (Responses API, Images API fallback), with pHash + TF-IDF rejection of look-alikes, max 4 attempts. `SKIP_IMAGE=true` skips it |
| 4. Save | Digest JSON written to `digests/YYYY-MM-DD.json` |
| 4.5. Audio | The day's pen-name byline is picked, then `tts_module.py` narrates the English digest with OpenAI `gpt-4o-mini-tts` and saves `docs/audio/YYYY-MM-DD.mp3`. Skipped if `AUDIO_*` is unset or `MOCK=true`; fail-soft |
| 5. Email | `renderer.py` builds the Gmail-safe HTML, with a link to the audio when it exists; `delivery.py` sends it via Gmail SMTP (STARTTLS on 587 by default). Fridays add a word cloud (ES in the email, ES + EN in the archive), a "How markets moved" chart and a week-in-review. The chart is built from market data, so a missed issue does not lose it: every run catches up any recent week that has none |
| 6. Archive | `archive.py` writes `docs/YYYY-MM-DD.html` and rebuilds `docs/index.html` and `docs/thread_index.json` |
| 7. Telegram | A short notification with the lead headline and archive link |
| 7b. Dashboard | `push_to_dashboard()` POSTs the digest to `DASHBOARD_PUSH_URL` (non-fatal, skipped if unset) |

After `main.py` exits, `run_newsletter.ps1` commits and pushes `docs/` + `digests/`.

### Telegram handler

`telegram_handler.py` runs every 5 minutes and is stateless between runs (it keeps its Telegram offset in `bot/.telegram_offset`). It handles three button actions on image candidates:

- **Select** — copies the chosen image into `docs/images/`, updates the digest, re-renders the archive page (`rerender.py`) and cleans up the other candidates
- **Regenerate** — generates a fresh set of candidates (limited number of rounds per issue)
- **Skip** — records the skip; the issue publishes without a candidate-picked image

`generate_candidates.py` and `image_candidates.py` produce and send the candidates.

---

## Section 4 — Folder Structure

```
News-Digest/
├── bot/            Pipeline source (main.py, fetcher, scorer, summarizer, renderers, delivery, archive, Telegram)
├── lib/            Image generation subsystem (generator, prompt builder, history store, similarity, registry)
├── config/         image_prompt_registry.yaml
├── scripts/        run_newsletter.ps1, run_telegram.ps1 (Task Scheduler entry points) + helpers
├── cloudflared/    Tunnel config (credentials JSON is gitignored)
├── docs/           Public archive: index.html, YYYY-MM-DD.html, images/, thread_index.json, word clouds (ES + EN), weekly markets charts
├── digests/        One JSON per issue; the source of truth for the archive
├── data/           SQLite image history (gitignored, per machine)
├── tmp_images/     Candidate images awaiting selection (gitignored, per machine)
├── engineering/    Developer docs (architecture, pipeline, project structure)
└── tests/          Renderer, scorer, summarizer-prompt and visual tests
```

| Folder | Written by |
|---|---|
| `digests/` | `main.py` (and updated by the Telegram flow) |
| `docs/` | `main.py` / `archive.py`; re-rendered after an image selection |
| `docs/images/` | Hero image generation and Telegram selection |
| `tmp_images/` | Candidate generation; cleaned up after selection |
| `C:\Projects\logs\` (server only, outside the repo) | Task Scheduler scripts |

---

## Section 5 — Environment Variables

Secrets live in `bot/.env` on each machine and are never committed. The full variable list, with meanings, is in `PROJECT_STATE.md` (Environment Variables). The ones that change behaviour:

| Variable | Effect |
|---|---|
| `SKIP_EMAIL=true` | Build the archive but do not send email |
| `MOCK=true` | Reuse the latest saved digest instead of calling NewsAPI + Claude |
| `FORCE_RUN=true` | Bypass the duplicate-run guard (set it only as a one-off override, never in `.env`) |
| `FORCE_FRIDAY=true` | Simulate Friday mode |
| `SKIP_IMAGE=true` | Skip hero image generation |
| `DASHBOARD_PUSH_URL` | Server only; where the digest is pushed after each run |
| `AUDIO_OUTPUT_DIR` + `AUDIO_BASE_URL` | Both set = daily audio on (`docs/audio`, `https://newsletter.mustardhq.dev/audio`); `AUDIO_KEEP_DAYS` (default 30) controls pruning |

---

## Section 6 — Running and Debugging

On the server (`C:\Projects\News-Digest`):

```powershell
# Full run (what Task Scheduler does)
docker compose run --rm app python main.py

# Re-run today even though a digest exists
docker compose run --rm -e FORCE_RUN=true app python main.py

# Archive only, no email
docker compose run --rm -e SKIP_EMAIL=true app python main.py

# After ANY code change, rebuild first (the image copies source at build time)
docker compose build
```

Logs: `C:\Projects\logs\newsletter_YYYY-MM-DD.log` and `telegram_YYYY-MM-DD.log`.

| Symptom | Where to look |
|---|---|
| No email / no archive page | Check for `digests/YYYY-MM-DD.json` and `newsletter_*.log`. Task Scheduler reports result 0 even if Docker was down and the run never started (the log shows "Docker Desktop is unable to start"). Recover with `scripts\run_newsletter.ps1`; no pull or rebuild needed unless code changed |
| Audio link missing from the email | Look for `[audio] Generation failed` in the log (missing `OPENAI_API_KEY`, API error, or `AUDIO_*` unset) |
| Regenerated MP3 still plays the old audio | Cloudflare cached the old file; purge that URL in the dashboard |
| Email fails with SMTP 535 | Gmail App Password was revoked; regenerate it and update `bot/.env` |
| Image generation fails with 403 | OpenAI organization verification for `gpt-image-2` |
| Archive not updating | `docker ps` should show `news-digest-nginx-1` and `news-digest-cloudflared-1` up; check `docs/` has the new file |
| Dashboard not updated | Look for `[dashboard] Push` lines in the log; check the `morning-dashboard` container |
| Telegram selection ignored | `telegram_*.log`; confirm the `Telegram Handler` task is running |

---

## Section 7 — Safety and Invariants

| Rule | Reason |
|---|---|
| Do not delete files from `digests/` | `docs/index.html` is rebuilt from every digest on each run; deleting one removes that issue from the historical record |
| `docs/index.html` and `docs/YYYY-MM-DD.html` are generated | Manual edits are overwritten |
| `docs/images/` is the source of truth for published images | Archive HTML references them by path |
| `tmp_images/` can be deleted | Candidates only; the selected image is already in `docs/images/` |
| Do not run the pipeline with a real `.env` on the main PC without `SKIP_EMAIL=true` or `MOCK=true` | It would email real subscribers |
| Rebuild the Docker image after code changes | Otherwise the server keeps running old code |

---

## Section 8 — Audio Edition (TTS)

Step 4.5 of `main.py` narrates the English digest with OpenAI `gpt-4o-mini-tts` (voice `ash`) and saves `docs/audio/YYYY-MM-DD.mp3` (about 5.7 MB). The narration opens in the day's pen name ("Phil Ation here this morning, Chief Correspondent, Bureau of Things Already Priced In. It's Tuesday, October 13.") and then reads the editor note, market mood, narrative thread, stories and quote. nginx serves the file under `/audio/`, and the email links to it with a bilingual AI-voice disclosure (archive pages do not link it yet). First issue with audio: #55 on 2026-10-13. It is optional and fail-soft: if it errors or the audio env vars are unset, the issue goes out without the audio link. MP3s are not committed to git and are pruned after 30 days. See `PROJECT_STATE.md` for the settings. Fuller documentation is **to be written**.
