---
name: Content Intelligence + Reader Experience
description: Two parallel tracks — smarter story selection/richer Claude output, and email/archive design polish with new topic-threading sections
type: project
---

# Design Spec: Content Intelligence + Reader Experience

**Date:** 2026-04-02
**Branch:** Dev-Nigg (never main)
**Tracks:** Two parallel, non-overlapping workstreams

---

## Overview

Two independent tracks developed simultaneously on `Dev-Nigg`:

1. **Track 1 — Content Intelligence:** Pre-score articles before Claude sees them; expand Claude's output schema with narrative context and topic threading.
2. **Track 2 — Reader Experience:** Polish email and archive design; add a coverage map and topic thread index to the archive.

Neither track touches the same files, so they can be developed in parallel and merged together into `Dev-Nigg` before any promotion to `main`.

---

## Track 1: Content Intelligence

### 1A — Pre-Scoring Pipeline

**Goal:** Only the highest-signal articles reach Claude. Currently all matching articles are sent regardless of freshness, source quality, or redundancy.

**New module:** `bot/scorer.py`

Each article receives a composite score (0.0–1.0) from four factors:

| Factor | Weight | Logic |
|--------|--------|-------|
| Freshness | 30% | Published <6h = 1.0 / <12h = 0.7 / <24h = 0.4 / older = 0.1 |
| Source authority | 25% | Tier 1 = 1.0 / Tier 2 = 0.6 / other = 0.3 |
| Topic relevance | 25% | Normalized keyword overlap with configured topics |
| Uniqueness | 20% | Penalize if >60% headline word overlap with already-selected articles |

**Source tiers** defined in `config.py`:
- Tier 1: FT, Reuters, WSJ, Bloomberg Línea, El Financiero
- Tier 2: Expansion, El Economista, Reforma, Milenio
- Other: everything else in the domain allowlist

**Output:** `scorer.py` exposes a single function `rank_articles(articles) -> list[Article]` returning articles sorted by score descending. `main.py` slices the top N (configurable via `config.py`, default 12) before passing to `summarizer.py`.

**Files touched:**
- `bot/scorer.py` — new file
- `bot/config.py` — add `SOURCE_TIERS`, `MAX_ARTICLES_FOR_CLAUDE` (default 12)
- `bot/main.py` — call `rank_articles()` between fetching and summarizing
- `bot/fetcher.py` — ensure `publishedAt` is preserved on each article dict

---

### 1B — Richer Claude Output

**Goal:** Each story explains why it matters today and whether it continues a running macro theme.

**New per-story fields** (added to Claude's JSON schema):

```json
{
  "context_note": {
    "es": "Por qué importa hoy: ...",
    "en": "Why this matters today: ..."
  },
  "thread_tag": "Banxico: tasa"  // null if standalone
}
```

**New top-level digest fields:**

```json
{
  "narrative_thread": {
    "es": "El tema dominante del día en una oración.",
    "en": "The dominant macro theme of the day in one sentence."
  },
  "active_threads": ["Banxico: tasa", "Peso: volatilidad"]
}
```

**Thread context injection:** Before calling Claude, `storage.py` scans the last 5 daily digests and extracts all `thread_tag` values that appear ≥2 times. These are passed into the Claude prompt as context so it can recognize and tag continuations. New function: `storage.get_active_threads() -> list[str]`.

**Prompt changes in `summarizer.py`:**
- Add `context_note` and `thread_tag` to the per-story output schema
- Add `narrative_thread` and `active_threads` to top-level schema
- Inject `active_threads` into the prompt preamble: "The following topics have been recurring this week: [tags]. Tag continuing stories accordingly."

**Files touched:**
- `bot/summarizer.py` — prompt + schema update
- `bot/storage.py` — add `get_active_threads()`
- `bot/renderer.py` — render `context_note` and `thread_tag` (email)
- `bot/pretty_renderer.py` — render `context_note`, `thread_tag`, `narrative_thread` (archive)

---

## Track 2: Reader Experience

### 2A — Email Design Polish

**Goal:** Better visual hierarchy and richer story presentation in the Gmail-safe email. All changes are inline-style, table-based — no external CSS.

**Changes to `bot/renderer.py`:**

- **Color consolidation:** All hex values moved to a `COLORS` dict at the top of the file. No more duplicated strings throughout.
- **Story cards:**
  - Larger, bolder headline (18px, weight 600)
  - Source + date on one line with a `·` separator
  - Tighter body text spacing
- **Context note block:** Left-bordered callout (`border-left: 3px solid accent-color`) rendered below the story body when `context_note` is present
- **Thread tag badge:** Small pill (`● Banxico: tasa`) above the headline when `thread_tag` is present
- **Narrative thread:** New section below the editor note — one bold sentence framing the day's macro theme, rendered when `narrative_thread` is present
- **Sentiment pill:** Wider badge with background fill (not just border outline), more readable at a glance
- **Section dividers:** Styled spacer rows with more vertical breathing room (replaces thin `<hr>`)

**Files touched:** `bot/renderer.py` only

---

### 2B — Archive Design Polish + New Sections

**Goal:** Improve the reading experience on archive pages and add two new discovery sections to the index.

**Design polish (`bot/pretty_renderer.py`):**
- Improved typography scale: headline sizes, body line-height, consistent spacing
- Language toggle: CSS `transition: opacity 0.2s` instead of instant swap
- Thread tag badges matching email style
- Context note rendered as a styled `<aside>` block
- Narrative thread displayed prominently at the top of each issue, above stories

**New section 1 — Coverage Map (on `index.html`):**
A horizontal bar chart showing which `thread_tag` values have appeared most across all archived issues. Built from digest JSONs during index rebuild. Uses Chart.js (already loaded on the page). Only digests produced after 1B is deployed will have `thread_tag` values; older digests are simply skipped. Counts accumulate over time as new issues are published.

**New section 2 — Topic Thread Index (on `index.html`):**
A collapsible section grouping issues by recurring `thread_tag` values. Example entry:
> **Peso: volatilidad** — 7 stories across 5 issues *(links to each issue)*

Built incrementally: `archive.py` extracts `thread_tag` values from each new digest and writes/updates `docs/thread_index.json`. The index page loads `thread_index.json` client-side and renders the collapsible list. This avoids a full O(n) rebuild of the thread index on every run.

**`thread_index.json` shape:**
```json
{
  "Banxico: tasa": [
    {"date": "2026-04-01", "headline": "Banxico mantiene tasa en 9.5%"},
    {"date": "2026-03-28", "headline": "Analistas esperan pausa de Banxico"}
  ]
}
```

**Files touched:**
- `bot/pretty_renderer.py` — design polish + narrative thread + new fields
- `bot/archive.py` — extract thread tags, write/update `thread_index.json`
- `docs/thread_index.json` — new file (auto-generated, committed by workflow)

---

## Constraints

- **Branch:** All work on `Dev-Nigg`. Never touch `main`.
- **Gmail safety:** All email changes must use inline styles and table-based layout only.
- **No new dependencies:** Chart.js is already loaded. No new Python packages.
- **Backward compatibility:** New digest fields (`context_note`, `thread_tag`, `narrative_thread`) must be optional. Old digests without them render gracefully (fields simply absent, renderers check with `.get()`).

---

## Files Changed Summary

| File | Track | Type |
|------|-------|------|
| `bot/scorer.py` | 1A | New |
| `bot/config.py` | 1A | Modified |
| `bot/main.py` | 1A | Modified |
| `bot/fetcher.py` | 1A | Modified (minor) |
| `bot/summarizer.py` | 1B | Modified |
| `bot/storage.py` | 1B | Modified |
| `bot/renderer.py` | 1B + 2A | Modified |
| `bot/pretty_renderer.py` | 1B + 2B | Modified |
| `bot/archive.py` | 2B | Modified |
| `docs/thread_index.json` | 2B | New (auto-generated) |
