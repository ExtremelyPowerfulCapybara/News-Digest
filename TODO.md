# Mexico Finance Brief — To-Do List

Track of features to build, roughly in order of priority.

---

## In Progress

- [ ] Sentiment chart in Friday email

---

## Quick Wins

- [ ] **Health monitoring** — free Healthchecks.io ping at the end of each run. If the bot doesn't check in, you get an email alert. Catches silent failures.
- [ ] **Merge Dev-Nigg → main** — all features built since March 2026 are still on Dev-Nigg. Production runs old code.

---

## Bigger Lift

- [ ] **Unsubscribe links** — each subscriber gets a unique token. Unsubscribe link removes them from the list automatically.
- [ ] **Resend/Mailgun migration** — replace Gmail SMTP with a proper email service for better deliverability and open/click tracking. Needed if subscriber list grows beyond ~20.
- [ ] **VPS migration** — move off GitHub Actions to a dedicated server (e.g. Hetzner, DigitalOcean) for more control, faster runs, and no GitHub dependency.
- [ ] **PWA + swipe navigation** — mobile reading experience on the archive site. Add to home screen, offline support, swipe between issues.

---

## Ideas / Someday

- [ ] Regulation watch section (DOF/SAT publications)
- [ ] Telegram or WhatsApp delivery option alongside email
- [ ] Subscriber growth / Substack integration

---

## Done

- [x] Core bot — fetch, summarize, send email
- [x] Gmail-safe email renderer (tables, inline styles)
- [x] Global macro ticker bar (DXY, 10Y UST, VIX, MSCI EM)
- [x] Secondary market data strips (Global Equities, Commodities, Crypto)
- [x] Weather block removed (replaced by secondary market data)
- [x] Sentiment pills + gauge
- [x] Currency table with base toggle (MXN, USD, BRL, EUR, CNY)
- [x] Quote of the day
- [x] Friday week-in-review timeline
- [x] "This week in markets" stat block (Fridays — weekly % moves for macro indicators)
- [x] Economic calendar block (Banxico, Fed, INEGI CPI, BLS CPI through Dec 2026)
- [x] Word cloud (Fridays — generated from week's headlines)
- [x] Pretty HTML archive renderer (Google Fonts, gauge, bilingual toggle)
- [x] Archive index with sentiment timeline chart and full-text search
- [x] Sentiment timeline + stories-per-issue charts on archive index
- [x] Full-text search on archive index (client-side, no Lunr.js needed)
- [x] GitHub Actions automatic daily runs
- [x] GitHub Pages archive site
- [x] Auto-commit archive after each run
- [x] Secrets via environment variables (never committed)
- [x] Domain allowlist (NewsAPI) + domain blocklist (fetcher)
- [x] Cross-day URL deduplication (skips stories already covered in last 5 issues)
- [x] Scraper domain selectors (per-outlet CSS selectors to target article body)
- [x] Parallel market data fetching (ThreadPoolExecutor)
- [x] Code audit — bugs, efficiency, and quality pass across all bot/ files
