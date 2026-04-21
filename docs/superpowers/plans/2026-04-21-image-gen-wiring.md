# Image Generation Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `lib/image_generator.py`'s `generate_editorial_image()` into the daily run by adding `generate_hero_image()` to `bot/image_gen.py`, saving the PNG to `docs/images/`, and populating `visual["hero_image"]` so the archive renderer displays it.

**Architecture:** A new `generate_hero_image()` function in `bot/image_gen.py` wraps the existing `generate_hero_prompt()` call and then calls `generate_editorial_image()` from `lib/`. It maps the story tag (e.g. "Energía") to a `CATEGORY_PRESETS` key for fallback field values, saves the PNG to `docs/images/`, and sets `visual["hero_image"]` to the public URL. `main.py` replaces the two existing lines with one call. The archive renderer already reads `visual["hero_image"]` — no renderer changes needed.

**Tech Stack:** Python, `lib/image_generator.py` (OpenAI), `lib/image_prompt_builder.CATEGORY_PRESETS`, `bot/config.py` (`ARCHIVE_DIR`, `ASSET_BASE_URL`), pytest + unittest.mock.

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `docs/images/.gitkeep` | Create | Tracks the new image directory in git |
| `bot/config.py` | Modify | Add `SKIP_IMAGE` env var |
| `bot/image_gen.py` | Modify | Add `TAG_TO_PRESET` mapping + `generate_hero_image()` |
| `lib/tests/test_image_gen.py` | Create | pytest tests for `generate_hero_image()` |
| `bot/main.py` | Modify | Replace `generate_hero_prompt()` call with `generate_hero_image()` |

---

## Task 1: Create `docs/images/` directory and add `SKIP_IMAGE` to config

**Files:**
- Create: `docs/images/.gitkeep`
- Modify: `bot/config.py`

- [ ] **Step 1: Create the images directory**

From repo root:
```bash
mkdir -p docs/images
touch docs/images/.gitkeep
```

- [ ] **Step 2: Add `SKIP_IMAGE` to `bot/config.py`**

In `bot/config.py`, find the block of boolean env var flags (around the `MOCK_MODE` / `SKIP_EMAIL` lines). Add immediately after `SKIP_EMAIL`:

```python
SKIP_IMAGE   = os.environ.get("SKIP_IMAGE",   "false").lower() in {"true", "1", "yes"}
```

- [ ] **Step 3: Commit**

```bash
git add docs/images/.gitkeep bot/config.py
git commit -m "feat: add docs/images/ dir and SKIP_IMAGE config flag"
```

---

## Task 2: Write failing tests for `generate_hero_image()`

**Files:**
- Create: `lib/tests/test_image_gen.py`

Note on `sys.path`: `bot/image_gen.py` imports from `prompt_map` (a `bot/` module), so the test must add both the repo root and `bot/` to `sys.path`.

- [ ] **Step 1: Create the test file**

Create `lib/tests/test_image_gen.py`:

```python
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Repo root (for lib imports) and bot/ (for image_gen + prompt_map imports)
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_BOT  = os.path.join(_ROOT, "bot")
sys.path.insert(0, os.path.abspath(_ROOT))
sys.path.insert(0, os.path.abspath(_BOT))

from image_gen import generate_hero_image

MINIMAL_DIGEST = {
    "es": {
        "stories": [{"tag": "Macro", "headline": "Test headline"}],
        "sentiment": {"label_en": "Cautious"},
    },
    "en": {
        "stories": [{"tag": "Macro", "headline": "Test headline EN"}],
        "sentiment": {"label_en": "Cautious"},
    },
}


def test_skip_image_env_returns_visual_without_hero_image(tmp_path):
    """When SKIP_IMAGE=true, generation is skipped and hero_image is absent."""
    with patch.dict(os.environ, {"SKIP_IMAGE": "true"}):
        visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert "hero_image" not in visual
    assert visual["hero_category"] == "Macro"


def test_successful_generation_sets_hero_image_url(tmp_path):
    """On success, hero_image is set to the public URL."""
    fake_result = {
        "image_path": str(tmp_path / "2026-04-21_hero.png"),
        "prompt_sent": "prompt",
        "revised_prompt": None,
        "accepted_prompt": "prompt",
        "concept_tag": "institutional",
        "subject_family": None,
        "composition_preset": None,
        "variation_code": None,
        "novelty_request": None,
        "similarity": {},
        "regeneration_count": 0,
        "record_id": 1,
    }
    with patch.dict(os.environ, {"SKIP_IMAGE": "false"}):
        with patch("lib.image_generator.generate_editorial_image", return_value=fake_result):
            with patch("config.ASSET_BASE_URL", "https://raw.example.com/"):
                visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert visual.get("hero_image") == "https://raw.example.com/images/2026-04-21_hero.png"


def test_generation_exception_returns_visual_without_hero_image(tmp_path):
    """If generate_editorial_image raises, hero_image is absent but function does not crash."""
    with patch.dict(os.environ, {"SKIP_IMAGE": "false"}):
        with patch("lib.image_generator.generate_editorial_image", side_effect=RuntimeError("API down")):
            visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert "hero_image" not in visual
    assert "hero_category" in visual


def test_tag_to_preset_mapping(tmp_path):
    """Each story tag maps to the correct CATEGORY_PRESETS key."""
    expected = {
        "Energía":  "energy",
        "Política": "policy_institutional",
        "Mercados": "markets_finance",
        "Comercio": "trade_supply_chain",
        "Macro":    "macro_inflation",
        "FX":       "macro_inflation",
        "Tasas":    "macro_inflation",
        "México":   "macro_inflation",
        "Unknown":  "macro_inflation",
    }
    from image_gen import TAG_TO_PRESET
    for tag, preset_key in expected.items():
        assert TAG_TO_PRESET.get(tag, "macro_inflation") == preset_key, f"Failed for tag={tag}"
```

- [ ] **Step 2: Run tests to verify they all fail**

Run from repo root:
```bash
pytest lib/tests/test_image_gen.py -v
```

Expected: 4 errors — `ImportError: cannot import name 'generate_hero_image'` and `ImportError: cannot import name 'TAG_TO_PRESET'` (the function and mapping don't exist yet).

---

## Task 3: Implement `generate_hero_image()` in `bot/image_gen.py`

**Files:**
- Modify: `bot/image_gen.py`

- [ ] **Step 1: Add `TAG_TO_PRESET` and `generate_hero_image()` to `bot/image_gen.py`**

Append to the bottom of `bot/image_gen.py` (after the existing `generate_hero_prompt()` function):

```python
# Maps Claude story tags to CATEGORY_PRESETS keys in lib/image_prompt_builder.py.
# Unknown tags fall back to "macro_inflation".
TAG_TO_PRESET: dict = {
    "Macro":    "macro_inflation",
    "FX":       "macro_inflation",
    "México":   "macro_inflation",
    "Tasas":    "macro_inflation",
    "Comercio": "trade_supply_chain",
    "Mercados": "markets_finance",
    "Energía":  "energy",
    "Política": "policy_institutional",
}


def generate_hero_image(digest: dict, issue_date: str, output_dir: str) -> dict:
    """
    Extends generate_hero_prompt() to actually produce a PNG via OpenAI.

    Saves image to output_dir/{issue_date}_hero.png.
    Sets visual["hero_image"] to the public URL on success.
    On SKIP_IMAGE=true or any generation error, returns visual without hero_image.
    """
    import os
    from lib.image_generator import generate_editorial_image
    from lib.image_prompt_builder import CATEGORY_PRESETS
    from config import ASSET_BASE_URL

    visual = generate_hero_prompt(digest)

    if os.environ.get("SKIP_IMAGE", "false").lower() in {"true", "1", "yes"}:
        return visual

    tag = visual.get("hero_category", "Macro")
    preset_key = TAG_TO_PRESET.get(tag, "macro_inflation")
    preset = CATEGORY_PRESETS[preset_key]

    digest_es = digest.get("es", digest)
    stories = digest_es.get("stories", [])
    context = stories[0].get("headline", "") if stories else ""

    try:
        generate_editorial_image(
            issue_date=issue_date,
            story_slug="hero",
            category=preset_key,
            main_subject=preset["main_subject"],
            environment=preset["environment"],
            composition=preset["composition"],
            color_system=preset["color_system"],
            context=context,
            output_dir=output_dir,
        )
        visual["hero_image"] = f"{ASSET_BASE_URL.rstrip('/')}/images/{issue_date}_hero.png"
    except Exception as exc:
        print(f"  [image_gen] Hero image generation failed: {exc}")

    return visual
```

- [ ] **Step 2: Run tests — all four should now pass**

```bash
pytest lib/tests/test_image_gen.py -v
```

Expected output:
```
PASSED lib/tests/test_image_gen.py::test_skip_image_env_returns_visual_without_hero_image
PASSED lib/tests/test_image_gen.py::test_successful_generation_sets_hero_image_url
PASSED lib/tests/test_image_gen.py::test_generation_exception_returns_visual_without_hero_image
PASSED lib/tests/test_image_gen.py::test_tag_to_preset_mapping
4 passed
```

- [ ] **Step 3: Run the full existing test suite to check for regressions**

```bash
pytest lib/tests/ -v
```

Expected: all 97 previously passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add bot/image_gen.py lib/tests/test_image_gen.py
git commit -m "feat: add generate_hero_image() to image_gen.py with TAG_TO_PRESET mapping"
```

---

## Task 4: Update `main.py` to call `generate_hero_image()`

**Files:**
- Modify: `bot/main.py`

- [ ] **Step 1: Update the import line in `main.py`**

Find:
```python
from image_gen   import generate_hero_prompt
```

Replace with:
```python
from image_gen   import generate_hero_image
```

- [ ] **Step 2: Replace the step 3.5 block in `main.py`**

Find:
```python
    # ── Visual metadata (hero prompt) ───────────────────────────────────────
    print("\n[3.5/5] Generating hero image prompt...")
    visual = generate_hero_prompt(digest)
    print(f"  [visual] Category: {visual['hero_category']} | Sentiment: {visual['hero_prompt'].split('overall tone: ')[1].split(',')[0]}")
```

Replace with:
```python
    # ── Visual metadata (hero image) ────────────────────────────────────────
    print("\n[3.5/5] Generating hero image...")
    from config import ARCHIVE_DIR
    _image_dir = os.path.join(ARCHIVE_DIR, "images")
    visual = generate_hero_image(digest, today_str, output_dir=_image_dir)
    print(f"  [visual] Category: {visual['hero_category']} | image: {'yes' if visual.get('hero_image') else 'skipped'}")
```

- [ ] **Step 3: Verify `os` is already imported in `main.py`**

Check the top of `main.py` — `import os` should already be on line 6. If not, add it.

- [ ] **Step 4: Smoke test with SKIP_IMAGE=true and MOCK=true**

From `bot/`:
```bash
MOCK=true SKIP_EMAIL=true SKIP_IMAGE=true FORCE_RUN=true python main.py
```

Expected in output:
```
[3.5/5] Generating hero image...
  [visual] Category: <tag> | image: skipped
```

No errors. The run completes and writes a digest + archive HTML.

- [ ] **Step 5: Commit**

```bash
git add bot/main.py
git commit -m "feat: wire generate_hero_image() into main.py run"
```

---

## Task 5: Update TODO.md

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Mark wire image generation as done in `TODO.md`**

Find:
```
- [ ] **Wire image generation into main.py** — `lib/` pipeline is fully built; call `generate_editorial_image()` per story after summarizer, inject `image_path` into digest dict, add conditional `<img>` in both renderers.
```

Replace with:
```
- [x] **Wire image generation into main.py** — `generate_hero_image()` in `bot/image_gen.py` calls `lib/image_generator.py`, saves PNG to `docs/images/`, sets `visual["hero_image"]` for the archive renderer.
```

- [ ] **Step 2: Commit**

```bash
git add TODO.md
git commit -m "docs: mark image gen wiring as done in TODO"
```
