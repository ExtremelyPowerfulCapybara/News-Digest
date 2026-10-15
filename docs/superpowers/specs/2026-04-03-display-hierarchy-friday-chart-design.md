---
name: Display Hierarchy + Friday Sentiment Chart
description: Lead story visual weight, narrative_thread pull quote, enriched subject line, and a Gmail-safe Friday sentiment chart
type: project
---

# Design Spec: Display Hierarchy + Friday Sentiment Chart

**Date:** 2026-04-03
**Branch:** Dev-Nigg (never main)
**Tracks:** Three independent tracks — A (archive display), A2 (email display), B (Friday chart)

---

## Overview

Three tracks developed on `Dev-Nigg`:

1. **Track A1 — Archive display hierarchy:** Lead story visual weight + narrative_thread pull quote in `pretty_renderer.py`
2. **Track A2 — Email display + subject line:** Narrative_thread pull quote in `renderer.py` + enriched subject line in `delivery.py`
3. **Track B — Friday sentiment chart:** New `get_week_sentiment()` in `storage.py` + new `_sentiment_week_chart()` in `renderer.py`

Track C (economic calendar warning, source tier logging, Tier 1 source cap) is handled in a separate plan — no design needed.

---

## Track A1 — Archive Display Hierarchy (`bot/pretty_renderer.py`)

### Lead story treatment

The first story in the archive (index `i == 0` in the story loop) receives two changes:

1. **Headline size:** `font-size: 26px` instead of the standard `20px` applied to all other stories.
2. **Lead label:** A `"● LEAD STORY"` / `"● LEAD STORY"` label rendered above the source/tag line:
   ```html
   <div class="lead-label">&#9679; LEAD STORY</div>
   ```
   CSS: `font-size: 8px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #aab4bc; margin-bottom: 6px;`

No new digest fields required. Guard is a simple `if i == 0` in the existing story loop.

The lead label is language-neutral (it always reads "LEAD STORY" in both ES and EN views since it's a structural label, not editorial text).

### Narrative thread pull quote

The `.narrative-thread` block changes from:
```css
/* current */
font-size: 11px; font-weight: 600; color: #555; border-left: 3px solid #1a1a1a; padding-left: 12px;
```

To a centered pull quote:

```html
<div class="narrative-thread">
  <div class="nt-label">Hilo del día</div>  <!-- lang-es -->
  <div class="nt-label">Today's thread</div> <!-- lang-en -->
  <p class="nt-text lang-es">{narrative_thread_es}</p>
  <p class="nt-text lang-en">{narrative_thread_en}</p>
</div>
```

New CSS:
```css
.narrative-thread { padding: 20px 48px; border-top: 1px solid #e4e9ec; border-bottom: 1px solid #e4e9ec; text-align: center; }
.nt-label { font-size: 8px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #aab4bc; margin-bottom: 10px; }
.nt-text { font-family: 'Playfair Display', serif; font-style: italic; font-size: 17px; color: #3a4a54; line-height: 1.65; margin: 0; }
```

Same position as now (between editor note and first story). Language-toggle aware: `.lang-es` / `.lang-en` classes on `nt-text`, same pattern used elsewhere in the archive.

**Files touched:** `bot/pretty_renderer.py` only.

---

## Track A2 — Email Display + Subject Line

### Narrative thread pull quote in email (`bot/renderer.py`)

`_narrative_thread()` currently renders a small bold left-bordered paragraph. Replace with a Gmail-safe centered pull quote using inline styles:

```python
def _narrative_thread(text: str) -> str:
    if not text:
        return ""
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:0 48px 4px;">
      <p style="margin:0; font-family:{FONT_SANS}; font-size:8px; font-weight:bold;
         letter-spacing:3px; text-transform:uppercase; color:#aab4bc;
         text-align:center;">HILO DEL D&Iacute;A</p>
    </td>
  </tr>
  <tr>
    <td style="padding:6px 48px 20px;">
      <p style="margin:0; font-family:{FONT_SERIF}; font-style:italic; font-size:15px;
         color:#3a4a54; line-height:1.65; text-align:center;">{text}</p>
    </td>
  </tr>
</table>"""
```

**Files touched:** `bot/renderer.py` only.

### Subject line enrichment (`bot/delivery.py`)

Current:
```python
subject = f"{NEWSLETTER_NAME} — {today_str}"
```

New:
```python
subject = f"{sentiment_label_en} | {NEWSLETTER_NAME} — {today_str}"
```

Where `sentiment_label_en` is one of `"Risk-Off"`, `"Cautious"`, or `"Risk-On"`.

`send_email()` currently receives `html_content` and no digest data. Add a `sentiment_label: str = "Cautious"` parameter with a safe default so old call sites don't break. Update `main.py` to pass `digest["es"]["sentiment"]["label_en"]` when calling `send_email()`.

**Files touched:** `bot/delivery.py`, `bot/main.py`.

---

## Track B — Friday Sentiment Chart

### Data: `get_week_sentiment()` (`bot/storage.py`)

New function alongside `get_active_threads()`:

```python
def get_week_sentiment(n: int = 5) -> list[dict]:
    """
    Scans the last n daily digest files and returns sentiment entries
    ordered chronologically (oldest first), suitable for a Mon–Fri chart.

    Each entry: {"day": "LUN", "score": int, "label_es": str, "label_en": str}
    Days are derived from the digest filename date (YYYY-MM-DD.json).
    Returns an empty list if fewer than 2 digests are available.
    """
```

Day abbreviations (ES): `["LUN","MAR","MIÉ","JUE","VIE","SÁB","DOM"]` indexed by `date.weekday()`.

Returns empty list (not an error) if fewer than 2 entries found — the renderer handles this gracefully.

**Files touched:** `bot/storage.py`.

### Renderer: `_sentiment_week_chart()` (`bot/renderer.py`)

New function. Renders a Gmail-safe `<table>` with one row per day. Bar width is proportional to the sentiment score on a 5–95 scale: `width_pct = int((score - 5) / 90 * 100)`.

Color mapping (matches existing sentiment pill palette):
- `"Risk-Off"` / `"Aversión al Riesgo"` → `#d4695a`
- `"Cautious"` / `"Cauteloso"` → `#e8a030`
- `"Risk-On"` / `"Apetito por Riesgo"` → `#6abf7b`

Row structure (inline styles throughout):
```
[DAY label 32px] [colored bar, proportional width] [score] [label_es right-aligned]
```

Returns empty string if `week_data` has fewer than 2 entries.

**Placement in Friday email:** Inserted after the week timeline block (`_week_timeline()`) and before the currency table. Only called when `friday_mode=True`.

### Wiring in `main.py`

```python
if friday:
    week_sentiment = get_week_sentiment()
    # passed to build_html(..., week_sentiment=week_sentiment)
```

`build_html()` in `renderer.py` gains an optional `week_sentiment: list[dict] | None = None` parameter.

**Files touched:** `bot/main.py`, `bot/renderer.py`, `bot/storage.py`.

---

## Constraints

- **Branch:** All work on `Dev-Nigg`. Never touch `main`.
- **Gmail safety:** All email changes use inline styles and table-based layout only. No flexbox, no external CSS, no JavaScript.
- **No new dependencies:** No new Python packages.
- **Backward compatibility:** `send_email()` `sentiment_label` parameter defaults to `"Cautious"`. `get_week_sentiment()` returns `[]` gracefully if history is thin. `_sentiment_week_chart()` returns `""` if fewer than 2 data points.
- **Language toggle:** Archive narrative_thread uses `.lang-es` / `.lang-en` classes, consistent with existing pattern.

---

## Files Changed Summary

| File | Track | Change |
|------|-------|--------|
| `bot/pretty_renderer.py` | A1 | Lead story headline size + label; narrative_thread pull quote CSS |
| `bot/renderer.py` | A2 + B | `_narrative_thread()` rewrite; new `_sentiment_week_chart()` |
| `bot/delivery.py` | A2 | Add `sentiment_label` param to `send_email()` |
| `bot/main.py` | A2 + B | Pass sentiment label to delivery; pass week_sentiment on Fridays |
| `bot/storage.py` | B | New `get_week_sentiment()` function |
