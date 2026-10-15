# Paid Tier & Topic Preferences — Design Spec

**Date:** 2026-05-06
**Project:** The Opening Bell / Mexico Finance Brief
**Status:** Approved

---

## Summary

This feature introduces a freemium subscription model to The Opening Bell. Free subscribers continue to receive the full daily digest unchanged. Paid subscribers unlock a personalized experience: they authenticate on a self-hosted preference portal, select editorial topic buckets, and receive a filtered digest containing only the categories they care about. A second paid tier offering deeper content is left as a future scope item.

The system is designed to run on the existing VPS alongside the newsletter bot, remain independent of Substack for delivery, and connect to Substack via a single webhook endpoint when payment integration is confirmed.

---

## Tiers

| Tier | What they get | How assigned |
|---|---|---|
| Free | Full digest, no customization | Default for all subscribers |
| Paid T1 | Filtered digest based on topic preferences | Manually via `admin.py` (Phase 1); Substack webhook (Phase 2) |
| Paid T2 | Deeper content, more analysis (future) | Out of scope for this spec |

---

## Topic Buckets

Subscribers choose from four editorial categories. These are user-facing labels that map internally to fetch topics and story categories assigned by Claude.

| Bucket | Internal key | Maps to |
|---|---|---|
| LatAm | `latam` | Mexico, finanzas, economia, LatAm sources |
| Global Markets | `markets` | mercados, comercio, Fed, commodities, DXY |
| Geopolitics | `geopolitics` | politica, tariffs, foreign policy, geopolitics |
| Crypto | `crypto` | criptomonedas, BTC/ETH/SOL |

If a paid subscriber selects all four buckets, they receive the full digest. If they select none (edge case), they fall back to the full digest so no subscriber ever receives an empty email.

---

## Architecture Overview

```
[Substack]          payments + free-tier broadcast (future)
     |
     | webhook (Phase 2)
     v
[Flask portal]      preference UI + magic link auth
     |
     v
[subscribers.db]    SQLite — source of truth for all subscriber data
     |
     v
[bot pipeline]      reads DB, filters stories per paid subscriber, sends filtered email
```

The Flask portal and the newsletter bot are separate processes on the same VPS. They share `subscribers.db` as their only integration point.

---

## Data Model

**File:** `subscribers.db` (SQLite, on VPS, not committed to repo)

### Table: `subscribers`

| column | type | notes |
|---|---|---|
| `email` | TEXT | Primary key |
| `tier` | TEXT | `"free"` or `"paid"` |
| `topics` | TEXT | JSON array, e.g. `["latam", "markets"]` |
| `active` | INTEGER | 1 = active, 0 = unsubscribed |
| `created_at` | TEXT | ISO 8601 datetime |

### Table: `auth_tokens`

| column | type | notes |
|---|---|---|
| `token` | TEXT | Primary key, UUID4 |
| `email` | TEXT | Foreign key → subscribers.email |
| `expires_at` | TEXT | ISO 8601, 1 hour from creation |
| `used` | INTEGER | 0 = valid, 1 = consumed |

### Migration

A one-time migration script converts existing `subscribers.csv` rows into the new DB on first run. All migrated subscribers default to `tier = "free"`.

---

## Components

### `bot/db.py` — Database module

Owns all reads and writes to `subscribers.db`. No raw SQL appears elsewhere in the codebase. Key functions:

- `get_subscribers(active_only=True) -> list[dict]`
- `get_subscriber(email) -> dict | None`
- `upsert_subscriber(email, tier, topics, active)`
- `create_auth_token(email) -> str`
- `consume_auth_token(token) -> str | None` — returns email if valid, None if expired/used/missing

### `bot/subscriber_filter.py` — Story filter

Pure function, no I/O, independently testable.

```python
def filter_stories(stories: list[dict], topics: list[str]) -> list[dict]:
    """
    Returns stories whose 'category' field is in topics.
    Falls back to full list if topics is empty or no stories match.
    """
```

### `bot/summarizer.py` — Claude schema change

Adds a `"category"` field to the per-story output schema. Claude assigns one of: `"latam"`, `"markets"`, `"geopolitics"`, `"crypto"`. The prompt instructs Claude to use `"latam"` as the default for ambiguous stories.

### `bot/delivery.py` — Per-subscriber render loop

Replaces the current single-render approach:

1. Load all active subscribers from `subscribers.db`
2. For each subscriber:
   - If `tier == "free"`: render full digest, send
   - If `tier == "paid"`: filter stories by `subscriber.topics`, render filtered digest, send
3. Dev mode override still applies (sends only to `DEV_RECIPIENT`)

### `bot/admin.py` — CLI tier management

```
python admin.py add <email>              # add subscriber (free tier)
python admin.py promote <email>          # free -> paid
python admin.py demote <email>           # paid -> free
python admin.py deactivate <email>       # set active = 0
python admin.py list                     # print all subscribers + tier + topics
```

### `web/` — Flask preference portal

New directory at repo root. Runs as a separate process on the VPS.

**Routes:**

| Route | Method | Auth required | Description |
|---|---|---|---|
| `GET /` | GET | No | Landing page with email input |
| `POST /auth/request` | POST | No | Generate + email magic link |
| `GET /auth/verify` | GET | No | Validate token, set session, redirect |
| `GET /preferences` | GET | Yes | Show topic checkboxes |
| `POST /preferences` | POST | Yes | Save topic selections |

**Auth flow:**
1. Subscriber enters email on landing page
2. If email exists in DB, a magic link is emailed using existing Gmail credentials
3. Link click validates token (UUID4, single-use, 1-hour TTL), sets a 7-day session cookie
4. Paid subscribers see 4 active topic checkboxes; free subscribers see locked checkboxes with upgrade prompt
5. No passwords are ever stored

---

## Phase 2 — Substack Integration (future, not built now)

When Substack payment integration is confirmed, one new route is added to the Flask app:

`POST /webhooks/substack` — receives payment events, calls `db.upsert_subscriber(email, tier="paid", ...)` automatically.

No other components change.

---

## Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| Paid subscriber selects no topics | Falls back to full digest |
| Story has no `category` field (legacy digest) | Treated as unfiltered, included for all subscribers |
| Magic link expired or already used | Returns 400 with "Link expired" message |
| Email not found in DB on auth request | Returns 200 silently (prevents email enumeration) |
| DB unavailable at send time | Pipeline raises exception, existing error handling in `main.py` catches it |

---

## What Does Not Change

- `renderer.py` and `pretty_renderer.py` — receive a stories list, don't care how it was filtered
- `fetcher.py`, `scraper.py`, `market_data.py` — no changes
- Archive HTML generation — always uses full digest regardless of tier
- Free subscriber experience — identical to today

---

## Out of Scope

- Paid T2 (deeper content) — future spec
- Unsubscribe token system — separate roadmap item
- Stripe or direct payment processing — Substack handles payments
- Domain and nginx configuration — infrastructure task, not a code task

---

## Build Phases

### Phase 1 (this spec)
- `bot/db.py` + migration from CSV
- `bot/subscriber_filter.py`
- `bot/summarizer.py` category field
- `bot/delivery.py` per-subscriber loop
- `bot/admin.py` CLI
- `web/` Flask portal (magic link auth + preference form)

### Phase 2 (future)
- Substack webhook endpoint
- Domain + nginx setup
