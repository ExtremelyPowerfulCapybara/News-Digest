# Display Hierarchy + Friday Sentiment Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lead story visual weight, narrative_thread pull quote (archive + email), enriched subject line, and a Gmail-safe table-based Friday sentiment chart.

**Architecture:** Four independent tasks touching `pretty_renderer.py` (archive display), `renderer.py` (email display + Friday chart), `delivery.py` + `main.py` (subject line wiring). `storage.get_week_sentiment()` already exists and returns `[{"day": str, "position": int, "label_en": str}, ...]`. `renderer._sentiment_chart()` exists but uses QuickChart.io (external PNG, not Gmail-safe) — Task 4 replaces it with a table-based implementation.

**Tech Stack:** Python 3, inline HTML/CSS (no new deps). All email HTML uses `<table>` + inline styles only. Archive HTML uses CSS classes.

---

## Files Changed

| File | Task | Change |
|------|------|--------|
| `bot/pretty_renderer.py` | 1 | Lead story label + larger headline; narrative_thread pull quote CSS + HTML |
| `bot/tests/test_pretty_renderer.py` | 1 | New test file: lead story + pull quote assertions |
| `bot/renderer.py` | 2, 4 | Rewrite `_narrative_thread()`; replace `_sentiment_chart()` with table-based `_sentiment_week_chart()` |
| `bot/tests/test_display_hierarchy.py` | 2, 4 | New test file: email pull quote + sentiment chart assertions |
| `bot/delivery.py` | 3 | Add `sentiment_label` param to `send_email()` |
| `bot/main.py` | 3 | Pass `label_en` from digest to `send_email()` |
| `bot/tests/test_subject_line.py` | 3 | New test: subject includes sentiment label |

---

## Task 1: Archive Lead Story + Narrative Thread Pull Quote (`pretty_renderer.py`)

**Files:**
- Modify: `bot/pretty_renderer.py:99-121` (CSS block)
- Modify: `bot/pretty_renderer.py:285-291` (narrative_html construction)
- Modify: `bot/pretty_renderer.py:330-373` (story loop)
- Create: `bot/tests/test_pretty_renderer.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_pretty_renderer.py`:

```python
"""
Tests for pretty_renderer.py display hierarchy changes.

Run from bot/ directory:
  python tests/test_pretty_renderer.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pretty_renderer import build_pretty_html

MINIMAL_DIGEST = {
    "es": {
        "editor_note": "Nota editorial.",
        "narrative_thread": "La Fed y el peso comparten protagonismo.",
        "sentiment": {"label_en": "Cautious", "label_es": "Cauteloso", "position": 50, "context_es": ""},
        "stories": [
            {"source": "Reuters",      "headline": "Fed mantiene tasas", "body": "La Fed no movió.", "url": "https://reuters.com/a", "tag": "Macro"},
            {"source": "El Financiero","headline": "Peso cierra estable","body": "El peso en 17.20.", "url": "https://elfinanciero.com/b", "tag": "FX"},
        ],
        "quote": {"text": "Test quote.", "attribution": "Author"},
    },
    "en": {}
}

def test_lead_story_label_present():
    """First story must have the LEAD STORY label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "LEAD STORY" in html, "Lead story label must appear for first story"

def test_lead_story_headline_larger():
    """First story headline must use the larger CSS class."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "story-headline-lead" in html, "First story must use story-headline-lead class"

def test_second_story_no_lead_label():
    """Second story must NOT have the lead label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    # LEAD STORY should appear exactly once
    assert html.count("LEAD STORY") == 1, "Only first story should have the lead label"

def test_narrative_thread_pull_quote_label():
    """Narrative thread must have HILO DEL DÍA label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "Hilo del" in html, "Narrative thread must have 'Hilo del día' label"

def test_narrative_thread_pull_quote_text():
    """Narrative thread text must appear inside nt-text class."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "nt-text" in html, "Narrative thread must use nt-text CSS class"
    assert "La Fed y el peso comparten protagonismo" in html, "Narrative thread text must appear"

def test_narrative_thread_no_left_border():
    """Old left-border style must be gone from narrative thread."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "border-left: 3px solid #1a1a1a" not in html.replace(" ",""), \
        "Old border-left style must not appear in narrative thread"

if __name__ == "__main__":
    tests = [
        test_lead_story_label_present,
        test_lead_story_headline_larger,
        test_second_story_no_lead_label,
        test_narrative_thread_pull_quote_label,
        test_narrative_thread_pull_quote_text,
        test_narrative_thread_no_left_border,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd bot && python tests/test_pretty_renderer.py
```
Expected: multiple FAIL lines (function may not exist yet or assertions fail).

- [ ] **Step 3: Update `pretty_renderer.py` CSS — replace `.narrative-thread` block and add new classes**

Find and replace in the CSS string (lines 114-121):

Old:
```python
  .narrative-thread {
    padding: 0 48px 20px;
  }
  .narrative-thread p {
    font-size: 11px; font-weight: 600; color: #555;
    border-left: 3px solid #1a1a1a; padding-left: 12px; line-height: 1.7;
    margin: 0;
  }
```

New (replace the whole block):
```python
  .narrative-thread { padding: 20px 48px; border-top: 1px solid #e4e9ec; border-bottom: 1px solid #e4e9ec; text-align: center; }
  .nt-label { font-size: 8px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #aab4bc; margin-bottom: 10px; }
  .nt-text { font-family: 'Playfair Display', serif; font-style: italic; font-size: 17px; color: #3a4a54; line-height: 1.65; margin: 0; }
```

Also insert after the `.story-headline` rule (line 99, right after `  .story-body { ... }`):
```python
  .story-headline-lead { font-size: 26px; }
  .lead-label { font-size: 8px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #aab4bc; margin-bottom: 6px; }
```

- [ ] **Step 4: Update `narrative_html` construction (lines 285-291)**

Old:
```python
    narrative_html = ""
    if narrative_es:
        narrative_html = f"""
<div class="narrative-thread">
  <div class="lang-es"><p>{narrative_es}</p></div>
  <div class="lang-en"><p>{narrative_en}</p></div>
</div>"""
```

New:
```python
    narrative_html = ""
    if narrative_es:
        narrative_html = f"""
<div class="narrative-thread">
  <div class="nt-label lang-es">Hilo del d&#237;a</div>
  <div class="nt-label lang-en">Today&#39;s thread</div>
  <p class="nt-text lang-es">{narrative_es}</p>
  <p class="nt-text lang-en">{narrative_en}</p>
</div>"""
```

- [ ] **Step 5: Update story loop to add lead story treatment (lines 330-373)**

Inside the `for i, story in enumerate(stories_es):` loop, add two variables before the `stories_html +=` line:

```python
        lead_label_html = (
            '<div class="lead-label">&#9679; LEAD STORY</div>'
            if i == 0 else ""
        )
        headline_class = "story-headline story-headline-lead" if i == 0 else "story-headline"
```

Then update the f-string template for the story div to use these variables. The current template (abbreviated):

```python
        stories_html += f"""
{DIVIDER}
<div class="story">
  {thread_badge}
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="lang-es">
    <div class="story-headline">{story['headline']}</div>
    <div class="story-body">{story['body']}</div>
    {ctx_es_html}
    <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
  </div>
  <div class="lang-en">
    <div class="story-headline">{story_en.get('headline', story['headline'])}</div>
    <div class="story-body">{story_en.get('body', story['body'])}</div>
    {ctx_en_html}
    <a href="{story['url']}" class="read-more">Read more &rarr;</a>
  </div>
</div>"""
```

Replace with:

```python
        stories_html += f"""
{DIVIDER}
<div class="story">
  {thread_badge}
  {lead_label_html}
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="lang-es">
    <div class="{headline_class}">{story['headline']}</div>
    <div class="story-body">{story['body']}</div>
    {ctx_es_html}
    <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
  </div>
  <div class="lang-en">
    <div class="{headline_class}">{story_en.get('headline', story['headline'])}</div>
    <div class="story-body">{story_en.get('body', story['body'])}</div>
    {ctx_en_html}
    <a href="{story['url']}" class="read-more">Read more &rarr;</a>
  </div>
</div>"""
```

- [ ] **Step 6: Run tests to confirm they pass**

```
cd bot && python tests/test_pretty_renderer.py
```
Expected: `6/6 passed`

- [ ] **Step 7: Commit**

```bash
git add bot/pretty_renderer.py bot/tests/test_pretty_renderer.py
git commit -m "feat: add lead story visual hierarchy and narrative thread pull quote to archive"
```

---

## Task 2: Email Narrative Thread Pull Quote (`renderer.py`)

**Files:**
- Modify: `bot/renderer.py:160-171` (`_narrative_thread()` function)
- Create: `bot/tests/test_display_hierarchy.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_display_hierarchy.py`:

```python
"""
Tests for display hierarchy changes in renderer.py.

Run from bot/ directory:
  python tests/test_display_hierarchy.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from renderer import _narrative_thread, FONT_SERIF, TEXT_LIGHT

def test_narrative_thread_empty_returns_empty():
    """Empty text must return empty string."""
    assert _narrative_thread("") == ""
    assert _narrative_thread(None) == ""

def test_narrative_thread_has_hilo_label():
    """Rendered output must include HILO DEL DÍA label."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "HILO DEL D" in html, "Must include 'HILO DEL DÍA' label"

def test_narrative_thread_uses_serif_font():
    """Pull quote text must use the serif font for italic style."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert FONT_SERIF in html, "Pull quote text must use FONT_SERIF"

def test_narrative_thread_centered():
    """Pull quote must be center-aligned."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "text-align:center" in html.replace(" ", ""), "Pull quote must be centered"

def test_narrative_thread_no_left_border():
    """Old border-left style must not appear."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "border-left" not in html, "Old border-left style must not appear"

def test_narrative_thread_text_present():
    """The supplied text must appear in the output."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "La Fed y el peso recalibran el ciclo." in html

if __name__ == "__main__":
    tests = [
        test_narrative_thread_empty_returns_empty,
        test_narrative_thread_has_hilo_label,
        test_narrative_thread_uses_serif_font,
        test_narrative_thread_centered,
        test_narrative_thread_no_left_border,
        test_narrative_thread_text_present,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd bot && python tests/test_display_hierarchy.py
```
Expected: FAIL on `test_narrative_thread_has_hilo_label`, `test_narrative_thread_centered`, `test_narrative_thread_no_left_border` (old style is present).

- [ ] **Step 3: Rewrite `_narrative_thread()` in `renderer.py` (lines 160-171)**

Old:
```python
def _narrative_thread(text: str) -> str:
    """Renders the day's dominant macro theme as a bold callout below the editor note."""
    if not text:
        return ""
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:0 48px 20px;">
      <p style="margin:0; font-family:{FONT_SANS}; font-size:11px; font-weight:bold; color:{TEXT_MID}; border-left:3px solid {TEXT_DARK}; padding-left:12px; line-height:1.7;">{text}</p>
    </td>
  </tr>
</table>"""
```

New:
```python
def _narrative_thread(text: str) -> str:
    """Renders the day's dominant macro theme as a centered pull quote below the editor note."""
    if not text:
        return ""
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER};">
  <tr>
    <td style="padding:20px 48px 4px; text-align:center;">
      <p style="margin:0; font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:3px; text-transform:uppercase; color:{TEXT_LIGHT};">HILO DEL D&Iacute;A</p>
    </td>
  </tr>
  <tr>
    <td style="padding:6px 48px 20px; text-align:center;">
      <p style="margin:0; font-family:{FONT_SERIF}; font-style:italic; font-size:15px; color:#3a4a54; line-height:1.65;">{text}</p>
    </td>
  </tr>
</table>"""
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd bot && python tests/test_display_hierarchy.py
```
Expected: `6/6 passed`

- [ ] **Step 5: Commit**

```bash
git add bot/renderer.py bot/tests/test_display_hierarchy.py
git commit -m "feat: rewrite email narrative_thread as centered pull quote"
```

---

## Task 3: Subject Line Enrichment (`delivery.py` + `main.py`)

**Files:**
- Modify: `bot/delivery.py:40-45` (`send_email()` signature + subject)
- Modify: `bot/main.py:111` (`send_email()` call site)
- Create: `bot/tests/test_subject_line.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_subject_line.py`:

```python
"""
Tests for delivery.py subject line enrichment.

Run from bot/ directory:
  python tests/test_subject_line.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import delivery

def test_send_email_accepts_sentiment_label():
    """send_email must accept a sentiment_label keyword argument."""
    import inspect
    sig = inspect.signature(delivery.send_email)
    assert "sentiment_label" in sig.parameters, \
        "send_email must have a sentiment_label parameter"

def test_sentiment_label_defaults_to_cautious():
    """sentiment_label must default to 'Cautious'."""
    import inspect
    sig = inspect.signature(delivery.send_email)
    default = sig.parameters["sentiment_label"].default
    assert default == "Cautious", \
        f"sentiment_label default must be 'Cautious', got {default!r}"

def test_subject_line_includes_sentiment():
    """Subject line construction must include the sentiment label."""
    source = inspect.getsource(delivery)
    assert "sentiment_label" in source, "delivery.py must reference sentiment_label"
    assert "NEWSLETTER_NAME" in source, "delivery.py must still include NEWSLETTER_NAME"

if __name__ == "__main__":
    tests = [
        test_send_email_accepts_sentiment_label,
        test_sentiment_label_defaults_to_cautious,
        test_subject_line_includes_sentiment,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd bot && python tests/test_subject_line.py
```
Expected: FAIL on `test_send_email_accepts_sentiment_label` and `test_sentiment_label_defaults_to_cautious`.

- [ ] **Step 3: Update `send_email()` in `delivery.py`**

Old (lines 40-45):
```python
def send_email(html: str, plain: str) -> None:
    today = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today_str   = f"{today.day} de {months_es[today.month]} de {today.year}"
    subject     = f"{NEWSLETTER_NAME} — {today_str}"
```

New:
```python
def send_email(html: str, plain: str, sentiment_label: str = "Cautious") -> None:
    today = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today_str   = f"{today.day} de {months_es[today.month]} de {today.year}"
    subject     = f"{sentiment_label} | {NEWSLETTER_NAME} — {today_str}"
```

- [ ] **Step 4: Update `send_email()` call in `main.py` (line 111)**

Old:
```python
        send_email(html, plain)
```

New:
```python
        sentiment_label = digest_es.get("sentiment", {}).get("label_en", "Cautious")
        send_email(html, plain, sentiment_label=sentiment_label)
```

- [ ] **Step 5: Run tests to confirm they pass**

```
cd bot && python tests/test_subject_line.py
```
Expected: `3/3 passed`

- [ ] **Step 6: Confirm existing renderer tests still pass**

```
cd bot && python tests/test_renderer.py
```
Expected: `5/5 passed`

- [ ] **Step 7: Commit**

```bash
git add bot/delivery.py bot/main.py bot/tests/test_subject_line.py
git commit -m "feat: enrich email subject line with sentiment label"
```

---

## Task 4: Table-Based Friday Sentiment Chart (`renderer.py` + `pretty_renderer.py`)

**Files:**
- Modify: `bot/renderer.py:328-412` (replace `_sentiment_chart()` with `_sentiment_week_chart()`)
- Modify: `bot/renderer.py:538-541` (update call site in `build_html()`)
- Modify: `bot/pretty_renderer.py:555-608` (replace inline QuickChart block with table-based chart)
- Modify: `bot/tests/test_display_hierarchy.py` (add chart tests)

- [ ] **Step 1: Add sentiment chart tests to `test_display_hierarchy.py`**

Append to `bot/tests/test_display_hierarchy.py` (before the `if __name__ == "__main__":` block):

```python
from renderer import _sentiment_week_chart

WEEK_DATA_TWO = [
    {"day": "Lun", "position": 28, "label_en": "Risk-Off"},
    {"day": "Mar", "position": 42, "label_en": "Cautious"},
]

WEEK_DATA_FIVE = [
    {"day": "Lun", "position": 28, "label_en": "Risk-Off"},
    {"day": "Mar", "position": 42, "label_en": "Cautious"},
    {"day": "Mié", "position": 35, "label_en": "Risk-Off"},
    {"day": "Jue", "position": 55, "label_en": "Cautious"},
    {"day": "Vie", "position": 72, "label_en": "Risk-On"},
]

def test_sentiment_chart_empty_for_one_entry():
    """Must return empty string when fewer than 2 data points."""
    assert _sentiment_week_chart([]) == ""
    assert _sentiment_week_chart([WEEK_DATA_TWO[0]]) == ""

def test_sentiment_chart_renders_day_labels():
    """Day abbreviations must appear in chart output."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "Lun" in html
    assert "Mar" in html

def test_sentiment_chart_riskoff_color():
    """Risk-Off entry must use red color #d4695a."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "#d4695a" in html, "Risk-Off color must appear in chart"

def test_sentiment_chart_cautious_color():
    """Cautious entry must use orange color #e8a030."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "#e8a030" in html, "Cautious color must appear in chart"

def test_sentiment_chart_riskon_color():
    """Risk-On entry must use green color #6abf7b."""
    html = _sentiment_week_chart(WEEK_DATA_FIVE)
    assert "#6abf7b" in html, "Risk-On color must appear in chart"

def test_sentiment_chart_no_external_url():
    """Chart must not reference quickchart.io or any external image URL."""
    html = _sentiment_week_chart(WEEK_DATA_FIVE)
    assert "quickchart.io" not in html, "Chart must not use quickchart.io"
    assert "<img" not in html, "Table-based chart must not use <img> tags"

def test_sentiment_chart_score_values_present():
    """Score values must appear in the chart."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "28" in html, "Score value 28 must appear"
    assert "42" in html, "Score value 42 must appear"
```

Also update the test runner list in `if __name__ == "__main__":` to include the new tests:

```python
if __name__ == "__main__":
    tests = [
        test_narrative_thread_empty_returns_empty,
        test_narrative_thread_has_hilo_label,
        test_narrative_thread_uses_serif_font,
        test_narrative_thread_centered,
        test_narrative_thread_no_left_border,
        test_narrative_thread_text_present,
        test_sentiment_chart_empty_for_one_entry,
        test_sentiment_chart_renders_day_labels,
        test_sentiment_chart_riskoff_color,
        test_sentiment_chart_cautious_color,
        test_sentiment_chart_riskon_color,
        test_sentiment_chart_no_external_url,
        test_sentiment_chart_score_values_present,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
```

- [ ] **Step 2: Run tests to confirm new chart tests fail**

```
cd bot && python tests/test_display_hierarchy.py
```
Expected: first 6 pass, new 7 chart tests FAIL with ImportError or AttributeError on `_sentiment_week_chart`.

- [ ] **Step 3: Replace `_sentiment_chart()` with `_sentiment_week_chart()` in `renderer.py`**

Replace the entire `_sentiment_chart()` function (lines 328-412) with:

```python
def _sentiment_week_chart(week_data: list[dict]) -> str:
    """
    Renders Mon-Fri sentiment as Gmail-safe table-based horizontal bars.
    Returns empty string if fewer than 2 entries.
    """
    if len(week_data) < 2:
        return ""

    _color = {"Risk-Off": "#d4695a", "Cautious": "#e8a030", "Risk-On": "#6abf7b"}
    _label_es = {"Risk-Off": "Aversión", "Cautious": "Cauteloso", "Risk-On": "Apetito"}

    rows = ""
    for entry in week_data:
        score    = entry.get("position", 50)
        label_en = entry.get("label_en", "Cautious")
        color    = _color.get(label_en, "#e8a030")
        label    = _label_es.get(label_en, label_en)
        w_pct    = max(4, int((score - 5) / 90 * 100))
        rows += f"""
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_LIGHT}; width:32px; white-space:nowrap; padding:0 8px 8px 0; vertical-align:middle;">{entry['day']}</td>
          <td style="padding:0 8px 8px 0; vertical-align:middle;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#e4e9ec; height:20px;">
              <tr>
                <td style="width:{w_pct}%; background:{color}; height:20px; padding:0 7px; vertical-align:middle;">
                  <span style="font-family:{FONT_SANS}; font-size:9px; font-weight:bold; color:#ffffff; letter-spacing:0.5px;">{score}</span>
                </td>
                <td style="background:#e4e9ec;">&nbsp;</td>
              </tr>
            </table>
          </td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:9px; font-weight:bold; color:{color}; white-space:nowrap; padding:0 0 8px 0; vertical-align:middle; width:80px;">{label}</td>
        </tr>"""

    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    label  = f"{monday.strftime('%d %b')}&#8211;{friday.strftime('%d %b, %Y')}"

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px 16px;">
      <p style="margin:0 0 14px 0; font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2.5px; text-transform:uppercase; color:{TEXT_LIGHT};">Sentimiento Semanal &middot; {label}</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        {rows}
      </table>
    </td>
  </tr>
</table>"""
```

- [ ] **Step 4: Update call site in `build_html()` (lines 538-541)**

Old:
```python
    sentiment_chart_html = ""
    if is_friday:
        from storage import get_week_sentiment
        sentiment_chart_html = _sentiment_chart(get_week_sentiment())
```

New:
```python
    sentiment_chart_html = ""
    if is_friday:
        from storage import get_week_sentiment
        sentiment_chart_html = _sentiment_week_chart(get_week_sentiment())
```

- [ ] **Step 5: Run tests to confirm chart tests pass**

```
cd bot && python tests/test_display_hierarchy.py
```
Expected: `13/13 passed`

- [ ] **Step 6: Replace inline QuickChart block in `pretty_renderer.py` (lines 555-608)**

Replace the block from `# ── Sentiment chart (Fridays only)` through the closing `"""` (lines 555-608):

Old:
```python
    # ── Sentiment chart (Fridays only) ───────────────────────────────────
    sentiment_chart_html = ""
    if is_friday:
        import json, urllib.parse
        from storage import get_week_sentiment
        week_sent = get_week_sentiment()
        if week_sent:
            sc_labels = [d["day"] for d in week_sent]
            sc_data   = [d["position"] for d in week_sent]
            sc_colors = [
                "#b84a3a" if d["position"] < 36 else
                ("#4a9e6a" if d["position"] > 64 else "#e8a030")
                for d in week_sent
            ]
            sc_config = {
                "type": "line",
                "data": {
                    "labels": sc_labels,
                    "datasets": [{
                        "data": sc_data,
                        "borderColor": "#3a4a54",
                        "borderWidth": 2,
                        "pointBackgroundColor": sc_colors,
                        "pointBorderColor":     sc_colors,
                        "pointRadius": 6,
                        "fill": False,
                        "tension": 0.3,
                    }],
                },
                "options": {
                    "responsive": False,
                    "plugins": {"legend": {"display": False}},
                    "scales": {
                        "y": {"min": 0, "max": 100, "ticks": {"display": False}, "grid": {"color": "#dde3e8"}},
                        "x": {"ticks": {"color": "#888888", "font": {"size": 11}}, "grid": {"display": False}},
                    },
                },
            }
            sc_url = (
                "https://quickchart.io/chart"
                f"?w=544&h=160&bkg=%23f0f3f5&f=png"
                f"&c={urllib.parse.quote(json.dumps(sc_config, separators=(',', ':')))}"
            )
            monday_sc = date.today() - timedelta(days=date.today().weekday())
            friday_sc = monday_sc + timedelta(days=4)
            sc_label  = f"{monday_sc.strftime('%b %d')}&ndash;{friday_sc.strftime('%d, %Y')}"
            sentiment_chart_html = f"""
{DIVIDER}
<div style="padding:24px 48px 8px;">
  <div class="section-title"
       data-es="Sentimiento Semanal &middot; {sc_label}"
       data-en="Weekly Sentiment &middot; {sc_label}">Sentimiento Semanal &middot; {sc_label}</div>
  <img src="{sc_url}" style="width:100%; border:1px solid #cdd4d9; margin-top:14px;" alt="Weekly sentiment chart"/>
</div>"""
```

New:
```python
    # ── Sentiment chart (Fridays only) ───────────────────────────────────
    sentiment_chart_html = ""
    if is_friday:
        from storage import get_week_sentiment
        week_sent = get_week_sentiment()
        if len(week_sent) >= 2:
            _sc_color    = {"Risk-Off": "#d4695a", "Cautious": "#e8a030", "Risk-On": "#6abf7b"}
            _sc_label_es = {"Risk-Off": "Aversión", "Cautious": "Cauteloso", "Risk-On": "Apetito"}
            sc_rows = ""
            for entry in week_sent:
                score    = entry.get("position", 50)
                label_en = entry.get("label_en", "Cautious")
                color    = _sc_color.get(label_en, "#e8a030")
                label_s  = _sc_label_es.get(label_en, label_en)
                w_pct    = max(4, int((score - 5) / 90 * 100))
                sc_rows += f"""
      <tr>
        <td class="sc-day">{entry['day']}</td>
        <td class="sc-track-cell">
          <div class="sc-track">
            <div class="sc-bar" style="width:{w_pct}%; background:{color};">
              <span class="sc-val">{score}</span>
            </div>
          </div>
        </td>
        <td class="sc-label" style="color:{color};">{label_s}</td>
      </tr>"""
            monday_sc = date.today() - timedelta(days=date.today().weekday())
            friday_sc = monday_sc + timedelta(days=4)
            sc_label  = f"{monday_sc.strftime('%b %d')}&ndash;{friday_sc.strftime('%d, %Y')}"
            sentiment_chart_html = f"""
{DIVIDER}
<div style="padding:24px 48px 16px;">
  <div class="section-title"
       data-es="Sentimiento Semanal &middot; {sc_label}"
       data-en="Weekly Sentiment &middot; {sc_label}">Sentimiento Semanal &middot; {sc_label}</div>
  <table class="sc-table" style="margin-top:14px;">
    <tbody>{sc_rows}
    </tbody>
  </table>
</div>"""
```

Also add the bar chart CSS rules to the CSS string in `pretty_renderer.py`. Insert after `.tl-body` (line 161, before `.calendar`):

```css
  .sc-table { width: 100%; border-collapse: collapse; }
  .sc-day { font-size: 8px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #aab4bc; width: 32px; white-space: nowrap; padding: 0 8px 8px 0; vertical-align: middle; }
  .sc-track-cell { padding: 0 8px 8px 0; vertical-align: middle; }
  .sc-track { background: #e4e9ec; height: 20px; width: 100%; }
  .sc-bar { height: 20px; display: flex; align-items: center; padding-left: 7px; min-width: 4%; }
  .sc-val { font-size: 9px; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
  .sc-label { font-size: 9px; font-weight: 700; white-space: nowrap; padding: 0 0 8px 0; vertical-align: middle; width: 80px; text-align: right; }
```

- [ ] **Step 7: Run all tests**

```
cd bot && python tests/test_display_hierarchy.py && python tests/test_pretty_renderer.py && python tests/test_renderer.py && python tests/test_subject_line.py && python tests/test_summarizer_prompt.py
```
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add bot/renderer.py bot/pretty_renderer.py bot/tests/test_display_hierarchy.py
git commit -m "feat: replace QuickChart sentiment chart with Gmail-safe table-based bars"
```

---

## Self-Review Checklist

Spec coverage:
- [x] Track A1: Lead story 26px headline + "● LEAD STORY" label at `i == 0` → Task 1
- [x] Track A1: `.narrative-thread` CSS pull quote → Task 1
- [x] Track A2: Email `_narrative_thread()` pull quote rewrite → Task 2
- [x] Track A2: Subject line `sentiment_label | NEWSLETTER_NAME — date` → Task 3
- [x] Track B: `_sentiment_week_chart()` table-based bars → Task 4
- [x] Track B: `build_html()` wiring for Friday → Task 4 (call site already existed, updated)
- [x] Backward compat: `send_email()` defaults to `"Cautious"` → Task 3
- [x] Gmail safety: all email changes use inline styles + tables → Tasks 2, 4
- [x] Language toggle: archive narrative thread uses `.lang-es` / `.lang-en` → Task 1

Storage note: `get_week_sentiment()` already exists in `storage.py` and returns `[{"day": str, "position": int, "label_en": str}]`. No storage.py changes needed.
