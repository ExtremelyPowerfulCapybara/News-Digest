# Visual Layer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hero image prompt generation to each pipeline run, store the prompt in the digest JSON, and render the hero image in the archive HTML when `hero_selected` is set manually.

**Architecture:** Two new pure-Python modules (`prompt_map.py`, `image_gen.py`) generate a hero prompt from the lead story tag and sentiment. The prompt is stored as a top-level `visual` block in `digests/YYYY-MM-DD.json`. `save_digest` merges new visual data with any existing data so manually-set `hero_selected` values survive reruns. The archive renderer conditionally renders a hero `<img>` only when `hero_selected` is not null. A standalone `rerender.py` script allows re-rendering a single issue HTML after manually setting `hero_selected`.

**Tech Stack:** Python stdlib only. No new dependencies. `pytest` for tests (dev only, `pip install pytest`).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `bot/prompt_map.py` | Create | `PROMPT_TEMPLATES` dict: tag → prompt template string |
| `bot/image_gen.py` | Create | `generate_hero_prompt(digest)` → visual dict |
| `bot/rerender.py` | Create | CLI script: load digest JSON, rebuild single archive HTML |
| `tests/conftest.py` | Create | Add `bot/` to `sys.path` for all tests |
| `tests/test_visual.py` | Create | Unit tests for `image_gen` and storage merge behavior |
| `bot/storage.py` | Modify | `save_digest` gains `visual` param; merges with existing on rerun |
| `bot/main.py` | Modify | Import + call `generate_hero_prompt`; thread `visual` to save + archive |
| `bot/archive.py` | Modify | `save_pretty_issue` gains `visual` param; passes to renderer |
| `bot/pretty_renderer.py` | Modify | `build_pretty_html` gains `visual` param; renders hero block conditionally |

---

## Task 1: `bot/prompt_map.py` — Prompt templates

**Files:**
- Create: `bot/prompt_map.py`

- [ ] **Step 1: Create `bot/prompt_map.py`**

```python
# bot/prompt_map.py
# ─────────────────────────────────────────────
#  Prompt templates for hero image generation.
#  Each template corresponds to one of the 8
#  Claude story tags. Fill {headline} and
#  {sentiment} at generation time via .format().
# ─────────────────────────────────────────────

_BASE = (
    "Premium editorial illustration for a high-end financial and geopolitical newsletter, "
    "hand-drawn ink and graphite style with refined linework and subtle cross-hatching, "
    "monochrome base with controlled muted color accents (20–25%), "
    "slightly textured paper background, "
    "{subject}, "
    "inspired by: {headline}, overall tone: {sentiment}, "
    "minimal composition, strong negative space, realistic proportions, "
    "calm but tense atmosphere, modern whitepaper-inspired editorial aesthetic, "
    "not photorealistic, not cinematic, no text, no logos."
)

PROMPT_TEMPLATES = {
    "Macro": _BASE.format(
        subject="a sparse government chamber or empty boardroom, muted light through tall windows",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "FX": _BASE.format(
        subject="rows of currency exchange ticker boards, numbers blurred, deep architectural perspective",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "México": _BASE.format(
        subject="Mexico City skyline at dusk, Torre Mayor silhouette, low clouds, empty boulevard below",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Comercio": _BASE.format(
        subject="stacked shipping containers at a port, cranes overhead, calm water, no figures",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Tasas": _BASE.format(
        subject="central bank building exterior, stone columns, overcast sky, empty stone steps",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Mercados": _BASE.format(
        subject="stock exchange trading floor, screens with data, long perspective shot, no people",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Energía": _BASE.format(
        subject="oil refinery towers and storage tanks at dusk, slow smoke rising, flat horizon",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Política": _BASE.format(
        subject="government building facade, national flags, dramatic clouds, empty plaza below",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
}
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd bot && python -c "from prompt_map import PROMPT_TEMPLATES; print(list(PROMPT_TEMPLATES.keys()))"
```

Expected output:
```
['Macro', 'FX', 'México', 'Comercio', 'Tasas', 'Mercados', 'Energía', 'Política']
```

- [ ] **Step 3: Verify template substitution works**

```bash
cd bot && python -c "
from prompt_map import PROMPT_TEMPLATES
t = PROMPT_TEMPLATES['Energía']
print(t.format(headline='Oil at 106 dollars', sentiment='Risk-Off'))
"
```

Expected: a single prompt string containing "Oil at 106 dollars" and "Risk-Off" with no remaining `{...}` placeholders.

---

## Task 2: `bot/image_gen.py` — Hero prompt generator

**Files:**
- Create: `bot/image_gen.py`

- [ ] **Step 1: Create `bot/image_gen.py`**

```python
# bot/image_gen.py
# ─────────────────────────────────────────────
#  Generates a hero image prompt for an issue.
#  Pure function — no API calls, no side effects.
#
#  Inputs:  digest dict (bilingual, from summarizer)
#  Outputs: visual metadata dict for digest JSON
# ─────────────────────────────────────────────

from prompt_map import PROMPT_TEMPLATES

TEMPLATE_VERSION = "v1"


def generate_hero_prompt(digest: dict) -> dict:
    """
    Derive hero image metadata from the lead story.

    Tag and headline come from digest["es"]["stories"][0].
    Sentiment label comes from digest["en"]["sentiment"]["label_en"]
    to keep English content in the English block.
    Falls back at each step.
    """
    digest_es = digest.get("es", {})
    digest_en = digest.get("en", digest_es)

    stories  = digest_es.get("stories", [])
    lead     = stories[0] if stories else {}

    tag      = lead.get("tag", "Macro")
    headline = lead.get("headline", "")

    # Sentiment: read label_en from EN block; fall back to ES block; then default
    sent_en  = digest_en.get("sentiment", {})
    sent_es  = digest_es.get("sentiment", {})
    mood     = sent_en.get("label_en") or sent_es.get("label_en") or "Cautious"

    template = PROMPT_TEMPLATES.get(tag, PROMPT_TEMPLATES["Macro"])
    prompt   = template.format(headline=headline, sentiment=mood)

    return {
        "hero_category":        tag,
        "hero_category_source": "lead_story",
        "hero_prompt_template": template,
        "hero_prompt_version":  TEMPLATE_VERSION,
        "hero_prompt":          prompt,
        "hero_selected":        None,
    }
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd bot && python -c "from image_gen import generate_hero_prompt; print('OK')"
```

Expected: `OK`

---

## Task 3: Tests for `prompt_map` and `image_gen`

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_visual.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
# tests/conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
```

- [ ] **Step 2: Create `tests/test_visual.py` with fixtures and image_gen tests**

```python
# tests/test_visual.py
import pytest
from image_gen import generate_hero_prompt
from prompt_map import PROMPT_TEMPLATES

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_DIGEST = {
    "es": {
        "stories": [
            {
                "tag": "Energía",
                "headline": "El petróleo supera los 106 dólares",
                "body": "Cuerpo.",
                "url": "https://example.com/1",
                "source": "El Financiero",
            }
        ],
        "sentiment": {
            "label_es": "Aversión al Riesgo",
            "label_en": "Risk-Off",
            "position": 22,
            "context_es": "Contexto.",
            "context_en": "Context.",
        },
        "editor_note": "Nota.",
        "narrative_thread": "Hilo.",
        "quote": {"text": "Quote.", "attribution": "Author, 2026"},
    },
    "en": {
        "stories": [
            {
                "tag": "Energía",
                "headline": "Oil surpasses $106",
                "body": "Body.",
                "url": "https://example.com/1",
                "source": "El Financiero",
            }
        ],
        "sentiment": {
            "label_es": "Aversión al Riesgo",
            "label_en": "Risk-Off",
            "position": 22,
            "context_es": "Contexto.",
            "context_en": "Context.",
        },
        "editor_note": "Note.",
        "narrative_thread": "Thread.",
        "quote": {"text": "Quote.", "attribution": "Author, 2026"},
    },
}

# ── generate_hero_prompt ──────────────────────────────────────────────────────

def test_returns_all_required_fields():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert set(result.keys()) == {
        "hero_category",
        "hero_category_source",
        "hero_prompt_template",
        "hero_prompt_version",
        "hero_prompt",
        "hero_selected",
    }

def test_uses_lead_story_tag():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_category"] == "Energía"

def test_category_source_is_lead_story():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_category_source"] == "lead_story"

def test_prompt_version_is_v1():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_prompt_version"] == "v1"

def test_hero_selected_is_none():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_selected"] is None

def test_prompt_contains_headline():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert "106 dólares" in result["hero_prompt"]

def test_prompt_contains_sentiment_from_en_block():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert "Risk-Off" in result["hero_prompt"]

def test_uses_en_block_for_sentiment_not_es():
    # EN block has Risk-On, ES block has Risk-Off — must use EN
    digest = {
        "es": {
            "stories": [{"tag": "Macro", "headline": "test"}],
            "sentiment": {"label_en": "Risk-Off"},
        },
        "en": {
            "stories": [{"tag": "Macro", "headline": "test"}],
            "sentiment": {"label_en": "Risk-On"},
        },
    }
    result = generate_hero_prompt(digest)
    assert "Risk-On" in result["hero_prompt"]

def test_unknown_tag_uses_macro_template():
    digest = {
        "es": {"stories": [{"tag": "XYZ", "headline": "test"}], "sentiment": {}},
        "en": {"sentiment": {"label_en": "Cautious"}},
    }
    result = generate_hero_prompt(digest)
    assert result["hero_category"] == "XYZ"
    assert result["hero_prompt_template"] == PROMPT_TEMPLATES["Macro"]

def test_empty_stories_defaults_to_macro():
    digest = {"es": {"stories": [], "sentiment": {}}, "en": {"sentiment": {"label_en": "Cautious"}}}
    result = generate_hero_prompt(digest)
    assert result["hero_category"] == "Macro"

def test_missing_en_block_falls_back_to_es_sentiment():
    digest = {
        "es": {
            "stories": [{"tag": "FX", "headline": "test"}],
            "sentiment": {"label_en": "Risk-Off"},
        },
        # no "en" key
    }
    result = generate_hero_prompt(digest)
    assert "Risk-Off" in result["hero_prompt"]

def test_template_stored_in_result():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_prompt_template"] == PROMPT_TEMPLATES["Energía"]
```

- [ ] **Step 3: Run the tests (expect all to pass)**

```bash
cd bot && pip install pytest -q && python -m pytest ../tests/test_visual.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd ..  # back to repo root
git add bot/prompt_map.py bot/image_gen.py tests/conftest.py tests/test_visual.py
git commit -m "feat: add prompt_map and image_gen modules with tests"
```

---

## Task 4: `bot/storage.py` — `save_digest` with merge

**Files:**
- Modify: `bot/storage.py` (lines 11–22 — `save_digest` function)

- [ ] **Step 1: Add storage merge tests to `tests/test_visual.py`**

Append this block to the end of `tests/test_visual.py`:

```python
# ── storage merge ────────────────────────────────────────────────────────────

import json, os
from datetime import date

def test_save_digest_persists_visual(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    visual = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "original prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual)

    today = date.today().isoformat()
    with open(os.path.join(str(tmp_path), f"{today}.json")) as f:
        stored = json.load(f)

    assert stored["visual"]["hero_category"] == "Energía"
    assert stored["visual"]["hero_selected"] is None


def test_save_digest_preserves_hero_selected_on_rerun(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    today = date.today().isoformat()
    path  = os.path.join(str(tmp_path), f"{today}.json")

    visual_first = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "first prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual_first)

    # Simulate manual edit: set hero_selected
    with open(path) as f:
        stored = json.load(f)
    stored["visual"]["hero_selected"] = "https://cdn.example.com/hero.png"
    with open(path, "w") as f:
        json.dump(stored, f)

    # Rerun with updated prompt — hero_selected must survive
    visual_second = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "updated prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual_second)

    with open(path) as f:
        final = json.load(f)

    assert final["visual"]["hero_selected"] == "https://cdn.example.com/hero.png"
    assert final["visual"]["hero_prompt"] == "updated prompt"


def test_save_digest_without_visual_omits_key(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}})

    today = date.today().isoformat()
    with open(os.path.join(str(tmp_path), f"{today}.json")) as f:
        stored = json.load(f)

    assert "visual" not in stored
```

- [ ] **Step 2: Run the new storage tests (expect them to FAIL — storage.py not yet modified)**

```bash
cd bot && python -m pytest ../tests/test_visual.py::test_save_digest_persists_visual -v
```

Expected: FAIL — `save_digest() got an unexpected keyword argument 'visual'`

- [ ] **Step 3: Modify `save_digest` in `bot/storage.py`**

Replace the current `save_digest` function (lines 11–22) with:

```python
def save_digest(digest: dict, market: dict, visual: dict | None = None) -> None:
    os.makedirs(DIGEST_DIR, exist_ok=True)
    today = date.today().isoformat()
    path  = os.path.join(DIGEST_DIR, f"{today}.json")

    # Preserve any existing visual data so hero_selected survives reruns.
    # Existing values win — new values only fill missing keys.
    if visual is not None and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing_visual = json.load(f).get("visual", {})
        visual = {**visual, **existing_visual}

    payload = {
        "date":   today,
        "digest": digest,
        "market": market,
    }
    if visual is not None:
        payload["visual"] = visual

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  [storage] Saved digest to {path}")
```

- [ ] **Step 4: Run all storage tests**

```bash
cd bot && python -m pytest ../tests/test_visual.py -v -k "save_digest"
```

Expected: 3 storage tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
cd bot && python -m pytest ../tests/test_visual.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd ..
git add bot/storage.py tests/test_visual.py
git commit -m "feat: save_digest accepts visual param with hero_selected merge"
```

---

## Task 5: `bot/main.py` — Wire up visual generation

**Files:**
- Modify: `bot/main.py`

- [ ] **Step 1: Add the import at the top of `bot/main.py`**

Current imports block ends at line 17. Add one line:

```python
from image_gen   import generate_hero_prompt
```

Full imports section after change:

```python
from fetcher     import fetch_news
from summarizer  import summarize_news
from market_data import fetch_tickers, fetch_secondary_tickers, fetch_currency_table
from storage     import save_digest, get_week_stories, get_recent_urls, is_friday
from renderer    import build_html, build_plain
from delivery    import send_email
from archive     import save_pretty_issue
from config      import DIGEST_DIR, AUTHOR_NAMES, AUTHOR_TITLES, MOCK_MODE, SKIP_EMAIL
from mock_data   import load_mock
from wordcloud_gen import generate_wordcloud
from image_gen   import generate_hero_prompt
```

- [ ] **Step 2: Add `visual` generation after the if/else block converges**

Current line 72: `digest_es = digest.get("es", digest)`

Insert after line 73 (`digest_en = digest.get("en", digest)`):

```python
    # ── Visual metadata (hero prompt) ───────────────────────────────────────
    print("\n[3.5/5] Generating hero image prompt...")
    visual = generate_hero_prompt(digest)
    print(f"  [visual] Category: {visual['hero_category']} | Sentiment: {visual['hero_prompt'].split('overall tone: ')[1].split(',')[0]}")
```

- [ ] **Step 3: Pass `visual` to `save_digest`**

Current line 77:
```python
    save_digest(digest, {"tickers": tickers, "currency": currency})
```

Replace with:
```python
    save_digest(digest, {"tickers": tickers, "currency": currency}, visual=visual)
```

- [ ] **Step 4: Pass `visual` to `save_pretty_issue`**

Current `save_pretty_issue` call (lines 116–126). Replace with:

```python
    save_pretty_issue(
        digest             = digest,
        tickers            = tickers,
        secondary_tickers  = secondary_tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
        visual             = visual,
    )
```

- [ ] **Step 5: Verify the file parses without errors**

```bash
cd bot && python -c "import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd ..
git add bot/main.py
git commit -m "feat: wire generate_hero_prompt into main pipeline"
```

---

## Task 6: `bot/archive.py` — Thread `visual` through `save_pretty_issue`

**Files:**
- Modify: `bot/archive.py` (lines 14–48 — `save_pretty_issue` function)

- [ ] **Step 1: Add `visual` parameter to `save_pretty_issue`**

Replace the function signature (line 14):

```python
def save_pretty_issue(
    digest:             dict,
    tickers:            list[dict],
    currency:           list[dict],
    week_stories:       list[dict],
    issue_number:       int,
    is_friday:          bool = False,
    wordcloud_filename: str | None = None,
    author:             str = "",
    secondary_tickers:  list[dict] | None = None,
    visual:             dict | None = None,
) -> str:
```

- [ ] **Step 2: Pass `visual` through to `build_pretty_html`**

Replace the `build_pretty_html(...)` call (lines 30–40):

```python
    html = build_pretty_html(
        digest             = digest,
        tickers            = tickers,
        secondary_tickers  = secondary_tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_number,
        is_friday          = is_friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
        visual             = visual,
    )
```

- [ ] **Step 3: Verify the file parses without errors**

```bash
cd bot && python -c "import archive; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd ..
git add bot/archive.py
git commit -m "feat: thread visual param through save_pretty_issue"
```

---

## Task 7: `bot/pretty_renderer.py` — Render hero block

**Files:**
- Modify: `bot/pretty_renderer.py`

- [ ] **Step 1: Add `.hero-image` CSS to the `CSS` string**

In `pretty_renderer.py`, the `CSS` string ends at line 212. The last block is a `@media (max-width: 600px)` rule that closes at line 211. Insert the hero CSS **before** the `@media` block (i.e., after line 190, before line 192). The surrounding context is:

```python
  .footer-by { font-size: 10px; color: #666; letter-spacing: 1px; }

  /* ── Hero image ── */
  .hero-image { line-height: 0; border-bottom: 1px solid #cdd4d9; }
  .hero-image img { width: 100%; display: block; }

  @media (max-width: 600px) {
```

- [ ] **Step 2: Add `visual` parameter to `build_pretty_html`**

Current signature (line 272):

```python
def build_pretty_html(
    digest:              dict,
    tickers:             list[dict],
    currency:            list[dict],
    week_stories:        list[dict],
    issue_number:        int = 1,
    is_friday:           bool = False,
    wordcloud_filename:  str | None = None,
    author:              str = "",
    secondary_tickers:   list[dict] | None = None,
) -> str:
```

Replace with:

```python
def build_pretty_html(
    digest:              dict,
    tickers:             list[dict],
    currency:            list[dict],
    week_stories:        list[dict],
    issue_number:        int = 1,
    is_friday:           bool = False,
    wordcloud_filename:  str | None = None,
    author:              str = "",
    secondary_tickers:   list[dict] | None = None,
    visual:              dict | None = None,
) -> str:
```

- [ ] **Step 3: Build the hero HTML block**

After the `narrative_html` block is assembled (around line 298), add:

```python
    # ── Hero image (renders only when hero_selected is set manually) ──────
    hero_html = ""
    if visual and visual.get("hero_selected"):
        cat = visual.get("hero_category", "")
        src = visual["hero_selected"]
        hero_html = f'''
<div class="hero-image">
  <img src="{src}" alt="{cat}">
</div>'''
```

- [ ] **Step 4: Insert `{hero_html}` into the return template**

In the large f-string returned at the end of `build_pretty_html`, find:

```python
  {narrative_html}

  {DIVIDER}
```

Replace with:

```python
  {narrative_html}

  {hero_html}

  {DIVIDER}
```

- [ ] **Step 5: Verify the file parses without errors**

```bash
cd bot && python -c "import pretty_renderer; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Add renderer tests to `tests/test_visual.py`**

Append to `tests/test_visual.py`:

```python
# ── pretty_renderer hero block ────────────────────────────────────────────────

from pretty_renderer import build_pretty_html

_MINIMAL_TICKERS   = []
_MINIMAL_CURRENCY  = {"bases": ["MXN"], "matrix": {"MXN": []}}
_MINIMAL_SECONDARY = None


def test_hero_block_absent_when_visual_is_none():
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = None,
    )
    assert 'class="hero-image"' not in html


def test_hero_block_absent_when_hero_selected_is_none():
    visual = {
        "hero_category": "Energía",
        "hero_selected": None,
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    assert 'class="hero-image"' not in html


def test_hero_block_present_when_hero_selected_is_set():
    visual = {
        "hero_category": "Energía",
        "hero_selected": "https://cdn.example.com/hero.png",
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    assert 'class="hero-image"' in html
    assert 'src="https://cdn.example.com/hero.png"' in html
    assert 'alt="Energía"' in html


def test_hero_block_position_before_sentiment():
    """Hero image must appear before the sentiment gauge in the document."""
    visual = {
        "hero_category": "FX",
        "hero_selected": "https://cdn.example.com/hero.png",
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    hero_pos      = html.index('class="hero-image"')
    sentiment_pos = html.index('class="sentiment"')
    assert hero_pos < sentiment_pos
```

- [ ] **Step 7: Run the renderer tests**

```bash
cd bot && python -m pytest ../tests/test_visual.py -v -k "hero"
```

Expected: all 4 hero renderer tests pass.

- [ ] **Step 8: Run the full test suite**

```bash
cd bot && python -m pytest ../tests/test_visual.py -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
cd ..
git add bot/pretty_renderer.py tests/test_visual.py
git commit -m "feat: render hero image block in archive HTML when hero_selected is set"
```

---

## Task 8: `bot/rerender.py` — Standalone rerender script

**Files:**
- Create: `bot/rerender.py`

- [ ] **Step 1: Create `bot/rerender.py`**

```python
#!/usr/bin/env python3
# bot/rerender.py
# ─────────────────────────────────────────────
#  Re-render a single archive issue from its
#  stored digest JSON. Useful after manually
#  setting visual.hero_selected.
#
#  Usage (run from bot/):
#    python rerender.py 2026-04-06
#
#  Reads:  digests/YYYY-MM-DD.json
#  Writes: docs/YYYY-MM-DD.html  (overwrites)
# ─────────────────────────────────────────────

import sys
import os
import json
from datetime import date

from pretty_renderer import build_pretty_html
from config          import DIGEST_DIR, ARCHIVE_DIR


def rerender(target_date: str) -> None:
    digest_path = os.path.join(DIGEST_DIR, f"{target_date}.json")
    if not os.path.exists(digest_path):
        print(f"[rerender] ERROR: no digest found at {digest_path}")
        sys.exit(1)

    with open(digest_path, encoding="utf-8") as f:
        stored = json.load(f)

    digest   = stored["digest"]
    market   = stored.get("market", {})
    visual   = stored.get("visual")
    tickers  = market.get("tickers", [])
    currency = market.get("currency", {})

    # Approximate issue number from digest count
    all_digests = sorted(f for f in os.listdir(DIGEST_DIR) if f.endswith(".json"))
    issue_num   = all_digests.index(f"{target_date}.json") + 1

    # Friday detection for the target date
    d      = date.fromisoformat(target_date)
    friday = d.weekday() == 4

    # Week stories: only meaningful if re-rendering a Friday issue
    week_stories = []
    if friday:
        from storage import get_week_stories
        week_stories = get_week_stories()

    # Word cloud: check if a PNG exists for that ISO week
    year, week, _ = d.isocalendar()
    wc_filename   = f"wordcloud-{year}-W{week:02d}.png"
    wc_path       = os.path.join(ARCHIVE_DIR, wc_filename)
    wordcloud_filename = wc_filename if os.path.exists(wc_path) else None

    html = build_pretty_html(
        digest             = digest,
        tickers            = tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = "",          # original author not stored; left blank
        secondary_tickers  = None,        # secondary_tickers are not persisted
        visual             = visual,
    )

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    out_path = os.path.join(ARCHIVE_DIR, f"{target_date}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[rerender] Written to {out_path}")
    if visual and visual.get("hero_selected"):
        print(f"[rerender] Hero image: {visual['hero_selected']}")
    else:
        print("[rerender] No hero image (hero_selected is null — set it in the digest JSON first)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rerender.py YYYY-MM-DD")
        sys.exit(1)
    rerender(sys.argv[1])
```

- [ ] **Step 2: Verify it parses and shows usage correctly**

```bash
cd bot && python rerender.py
```

Expected: `Usage: python rerender.py YYYY-MM-DD`

- [ ] **Step 3: Smoke test against the most recent digest**

```bash
cd bot && python rerender.py 2026-04-03
```

Expected: `[rerender] Written to .../docs/2026-04-03.html` with no Python exception.

- [ ] **Step 4: Commit**

```bash
cd ..
git add bot/rerender.py
git commit -m "feat: add rerender.py for single-issue re-render after hero_selected is set"
```

---

## Task 9: Integration verification

- [ ] **Step 1: Run a full mock pipeline**

```bash
cd bot && MOCK=true SKIP_EMAIL=true python main.py
```

Expected output includes:
```
[3.5/5] Generating hero image prompt...
  [visual] Category: <tag> | Sentiment: <label>
```

No Python exceptions.

- [ ] **Step 2: Verify the visual block is in the digest JSON**

```bash
cd bot && python -c "
import json, os
from config import DIGEST_DIR
from datetime import date
path = os.path.join(DIGEST_DIR, date.today().isoformat() + '.json')
with open(path) as f:
    d = json.load(f)
import pprint; pprint.pprint(d.get('visual'))
"
```

Expected: a dict with all 6 keys (`hero_category`, `hero_category_source`, `hero_prompt_template`, `hero_prompt_version`, `hero_prompt`, `hero_selected`). `hero_selected` is `null`.

- [ ] **Step 3: Verify hero block is absent from archive HTML (hero_selected is still null)**

```bash
cd bot && python -c "
from datetime import date; import os
from config import ARCHIVE_DIR
path = os.path.join(ARCHIVE_DIR, date.today().isoformat() + '.html')
html = open(path).read()
print('hero-image present:', 'hero-image' in html)
"
```

Expected: `hero-image present: False`

- [ ] **Step 4: Simulate manual hero_selected — set it and rerender**

```bash
cd bot && python -c "
import json, os
from config import DIGEST_DIR
from datetime import date
path = os.path.join(DIGEST_DIR, date.today().isoformat() + '.json')
with open(path) as f:
    d = json.load(f)
d['visual']['hero_selected'] = 'https://placehold.co/640x360/1a1a1a/f0f3f5?text=Hero'
with open(path, 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('hero_selected set')
"
```

Then re-render:

```bash
cd bot && python rerender.py $(python -c "from datetime import date; print(date.today().isoformat())")
```

- [ ] **Step 5: Verify hero block is now present in archive HTML**

```bash
cd bot && python -c "
from datetime import date; import os
from config import ARCHIVE_DIR
path = os.path.join(ARCHIVE_DIR, date.today().isoformat() + '.html')
html = open(path).read()
print('hero-image present:', 'hero-image' in html)
print('placehold.co present:', 'placehold.co' in html)
"
```

Expected:
```
hero-image present: True
placehold.co present: True
```

- [ ] **Step 6: Verify hero_selected survives a second mock run**

```bash
cd bot && MOCK=true SKIP_EMAIL=true python main.py
```

Then:

```bash
cd bot && python -c "
import json, os
from config import DIGEST_DIR
from datetime import date
path = os.path.join(DIGEST_DIR, date.today().isoformat() + '.json')
with open(path) as f:
    d = json.load(f)
print('hero_selected after rerun:', d['visual']['hero_selected'])
"
```

Expected: `hero_selected after rerun: https://placehold.co/640x360/1a1a1a/f0f3f5?text=Hero` (not null).

- [ ] **Step 7: Run full test suite one final time**

```bash
cd bot && python -m pytest ../tests/test_visual.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Final commit**

```bash
cd ..
git add -A
git commit -m "feat: visual layer v1 — hero prompt generation, storage, archive render, rerender script"
```

---

## Manual Workflow (post-implementation)

After a pipeline run:
1. Open `digests/YYYY-MM-DD.json`
2. Copy `visual.hero_prompt` — use it in Midjourney, DALL-E, or any image tool
3. Host the resulting image (CDN, GitHub raw, etc.)
4. Set `visual.hero_selected` to the image URL in the JSON file
5. Run `cd bot && python rerender.py YYYY-MM-DD`
6. Commit the updated `docs/YYYY-MM-DD.html` and `digests/YYYY-MM-DD.json`
