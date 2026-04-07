# Hero Image Candidate Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stub image candidate generation, Telegram photo delivery, editorial selection, safe file publish, and archive rerender — fully end-to-end, with real image provider stubbed via placeholder PNGs.

**Architecture:** A new `bot/generate_candidates.py` CLI script generates 3 PNG candidates per issue into `tmp_images/YYYY-MM-DD/`, updates the digest JSON, and sends the images to Telegram with selection buttons. `telegram_handler.py` gains `select` (copy-verify-rerender-cleanup) and `regenerate` (bounded, stateful) handlers. `pretty_renderer.py` is fixed to read `visual.hero_image` instead of the incorrectly-used `visual.hero_selected`.

**Tech Stack:** Python 3.10+, Pillow (already in requirements.txt), requests, json, shutil, pathlib

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `bot/image_candidates.py` | **Create** | `generate_image()` stub + `generate_image_candidates()` |
| `bot/generate_candidates.py` | **Create** | CLI entrypoint: load → generate → update digest → send Telegram photos |
| `bot/tests/__init__.py` | **Create** | Makes `bot/tests/` a Python package |
| `bot/tests/test_image_candidates.py` | **Create** | Unit tests for generation logic |
| `bot/tests/test_generate_candidates.py` | **Create** | Unit tests for guards and digest update |
| `bot/tests/test_telegram_handler.py` | **Create** | Unit tests for select/regenerate handlers |
| `docs/images/.gitkeep` | **Create** | Ensure published image dir exists in repo |
| `bot/telegram_bot.py` | **Modify** | Strip selection UI; keep lightweight run notification |
| `bot/telegram_handler.py` | **Modify** | Add `_handle_select()`, `_handle_regenerate()`, `_cleanup_tmp_candidates()` |
| `bot/pretty_renderer.py` | **Modify** | Use `hero_image` not `hero_selected` as img src (fix existing bug) |
| `bot/rerender.py` | **Modify** | Fix cosmetic log line (still prints `hero_selected`; should print `hero_image`) |
| `.gitignore` | **Modify** | Add `tmp_images/` |

---

## Task 1: Filesystem Setup

**Files:**
- Modify: `.gitignore`
- Create: `docs/images/.gitkeep`

- [ ] **Step 1: Add `tmp_images/` to .gitignore**

Open `.gitignore` and add two lines after the `bot/.telegram_offset` entry:

```
# ── Temporary image candidates ───────────────
tmp_images/
```

- [ ] **Step 2: Create `docs/images/.gitkeep`**

Create an empty file at `docs/images/.gitkeep` so the directory is tracked by git and present on the VPS after a clone.

```
(empty file)
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore docs/images/.gitkeep
git commit -m "chore: add tmp_images/ to gitignore, scaffold docs/images/"
```

---

## Task 2: `bot/image_candidates.py`

**Files:**
- Create: `bot/image_candidates.py`
- Create: `bot/tests/__init__.py`
- Create: `bot/tests/test_image_candidates.py`

- [ ] **Step 1: Write the failing tests**

Create `bot/tests/__init__.py` (empty file).

Create `bot/tests/test_image_candidates.py`:

```python
# bot/tests/test_image_candidates.py
import os
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from image_candidates import generate_image, generate_image_candidates


def test_generate_image_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "test.png")
        generate_image("test prompt", out)
        assert os.path.exists(out), "generate_image must create the output file"
        assert os.path.getsize(out) > 0, "Output file must not be empty"


def test_generate_image_candidates_creates_three_files():
    visual = {
        "hero_options": {
            "opt1": "prompt one",
            "opt2": "prompt two",
            "opt3": "prompt three",
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_image_candidates("2026-04-07", visual, tmp, round_num=1)
        assert set(result.keys()) == {"opt1", "opt2", "opt3"}
        for key, path in result.items():
            assert os.path.exists(path), f"{key} file must exist at {path}"
            assert os.path.basename(path) == f"r1_{key}.png"


def test_generate_image_candidates_creates_nested_directory():
    visual = {"hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"}}
    with tempfile.TemporaryDirectory() as tmp:
        project_root = os.path.join(tmp, "project_does_not_exist_yet")
        generate_image_candidates("2026-04-07", visual, project_root)
        expected = os.path.join(project_root, "tmp_images", "2026-04-07")
        assert os.path.isdir(expected)


def test_generate_image_candidates_round2_filenames():
    visual = {"hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"}}
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_image_candidates("2026-04-07", visual, tmp, round_num=2)
        for key, path in result.items():
            assert os.path.basename(path) == f"r2_{key}.png"


def test_generate_image_candidates_raises_on_missing_hero_options():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="hero_options"):
            generate_image_candidates("2026-04-07", {}, tmp)


def test_generate_image_candidates_raises_on_empty_hero_options():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="hero_options"):
            generate_image_candidates("2026-04-07", {"hero_options": {}}, tmp)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd bot && python -m pytest tests/test_image_candidates.py -v
```

Expected: `ModuleNotFoundError: No module named 'image_candidates'`

- [ ] **Step 3: Create `bot/image_candidates.py`**

```python
# bot/image_candidates.py
# ─────────────────────────────────────────────
#  Hero image candidate generation.
#
#  generate_image() is the provider stub.
#  Replace its body with a real API call when ready.
#  Signature (prompt, output_path) is stable — do not change.
#
#  generate_image_candidates() is the orchestrator.
#  It calls generate_image() 3 times and returns a
#  {opt1: path, opt2: path, opt3: path} mapping.
# ─────────────────────────────────────────────

import os


def generate_image(prompt: str, output_path: str) -> None:
    """
    Stub implementation: creates a solid-color placeholder PNG.

    TODO: Replace this body with a real provider call, e.g.:
        client = openai.OpenAI()
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        img_data = requests.get(image_url).content
        with open(output_path, "wb") as f:
            f.write(img_data)

    The signature (prompt: str, output_path: str) must remain unchanged.
    """
    from PIL import Image, ImageDraw

    # Use a different hue per filename so options are visually distinct in Telegram
    basename = os.path.basename(output_path)
    if "opt1" in basename:
        bg = (28, 45, 65)
    elif "opt2" in basename:
        bg = (28, 62, 52)
    else:
        bg = (65, 42, 28)

    img = Image.new("RGB", (1200, 630), color=bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 1160, 590], outline=(160, 160, 160), width=2)
    # PIL default font — always available, no path needed
    draw.text((60, 60), f"[stub] {basename}", fill=(200, 200, 200))
    draw.text((60, 100), prompt[:100], fill=(140, 140, 140))
    img.save(output_path, "PNG")
    print(f"  [image_candidates] Stub image saved: {output_path}")


def generate_image_candidates(
    issue_date: str,
    visual: dict,
    project_root: str,
    round_num: int = 1,
) -> dict:
    """
    Generate 3 candidate images for the given issue and round.

    Creates tmp_images/YYYY-MM-DD/ under project_root if it does not exist.

    Returns:
        {"opt1": "/abs/path/rN_opt1.png", "opt2": ..., "opt3": ...}

    Raises:
        ValueError: if hero_options is missing or empty in visual.
    """
    hero_options = visual.get("hero_options", {})
    if not hero_options:
        raise ValueError(
            f"No hero_options found in visual block for {issue_date}. "
            "Run main.py first to generate the digest."
        )

    out_dir = os.path.join(project_root, "tmp_images", issue_date)
    os.makedirs(out_dir, exist_ok=True)

    candidates = {}
    for key in ("opt1", "opt2", "opt3"):
        prompt = hero_options.get(key, "")
        if not prompt:
            continue
        filename = f"r{round_num}_{key}.png"
        output_path = os.path.join(out_dir, filename)
        generate_image(prompt, output_path)
        candidates[key] = output_path

    return candidates
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd bot && python -m pytest tests/test_image_candidates.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/image_candidates.py bot/tests/__init__.py bot/tests/test_image_candidates.py
git commit -m "feat: add image_candidates.py with placeholder PNG generation"
```

---

## Task 3: `bot/generate_candidates.py`

**Files:**
- Create: `bot/generate_candidates.py`
- Create: `bot/tests/test_generate_candidates.py`

- [ ] **Step 1: Write the failing tests**

Create `bot/tests/test_generate_candidates.py`:

```python
# bot/tests/test_generate_candidates.py
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _write_digest(digests_dir, issue_date, visual):
    """Helper: write a minimal digest JSON and return its path."""
    os.makedirs(digests_dir, exist_ok=True)
    data = {"digest": {"en": {"stories": []}, "es": {"stories": []}}, "visual": visual}
    path = os.path.join(digests_dir, f"{issue_date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def test_run_exits_cleanly_if_hero_image_already_set(capsys):
    from generate_candidates import _load_and_run

    with tempfile.TemporaryDirectory() as tmp:
        digests_dir = os.path.join(tmp, "digests")
        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_image": "/images/2026-04-07.png",
        }
        _write_digest(digests_dir, "2026-04-07", visual)

        _load_and_run("2026-04-07", digests_dir, tmp, token="", chat_id="")

        captured = capsys.readouterr()
        assert "already locked" in captured.out


def test_run_exits_cleanly_if_candidates_already_exist(capsys):
    from generate_candidates import _load_and_run

    with tempfile.TemporaryDirectory() as tmp:
        digests_dir = os.path.join(tmp, "digests")

        # Pre-create the candidate files
        cand_dir = os.path.join(tmp, "tmp_images", "2026-04-07")
        os.makedirs(cand_dir)
        for key in ("opt1", "opt2", "opt3"):
            open(os.path.join(cand_dir, f"r1_{key}.png"), "w").close()

        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_image": None,
            "hero_image_candidates": {
                "opt1": os.path.join(cand_dir, "r1_opt1.png"),
                "opt2": os.path.join(cand_dir, "r1_opt2.png"),
                "opt3": os.path.join(cand_dir, "r1_opt3.png"),
            },
            "hero_generation_round": 1,
        }
        _write_digest(digests_dir, "2026-04-07", visual)

        _load_and_run("2026-04-07", digests_dir, tmp, token="", chat_id="")

        captured = capsys.readouterr()
        assert "already generated" in captured.out


def test_run_updates_digest_with_candidates():
    from generate_candidates import _load_and_run

    with tempfile.TemporaryDirectory() as tmp:
        digests_dir = os.path.join(tmp, "digests")
        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
        }
        digest_path = _write_digest(digests_dir, "2026-04-07", visual)

        # No Telegram token — Telegram send is skipped cleanly
        _load_and_run("2026-04-07", digests_dir, tmp, token="", chat_id="")

        with open(digest_path, encoding="utf-8") as f:
            saved = json.load(f)

        v = saved["visual"]
        assert "hero_image_candidates" in v
        assert set(v["hero_image_candidates"].keys()) == {"opt1", "opt2", "opt3"}
        assert v["hero_generation_round"] == 1
        assert v["hero_regenerations_used"] == 0
        assert v["hero_image"] is None


def test_run_does_not_reset_existing_counters():
    """hero_regenerations_used must not reset to 0 if already > 0."""
    from generate_candidates import _load_and_run

    with tempfile.TemporaryDirectory() as tmp:
        digests_dir = os.path.join(tmp, "digests")
        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_generation_round": 2,
            "hero_regenerations_used": 1,
        }
        digest_path = _write_digest(digests_dir, "2026-04-07", visual)

        # Force-run (delete candidates guard by leaving hero_image_candidates absent)
        _load_and_run("2026-04-07", digests_dir, tmp, token="", chat_id="")

        with open(digest_path, encoding="utf-8") as f:
            saved = json.load(f)

        # Counters come from the existing state, not reset
        assert saved["visual"]["hero_generation_round"] == 2
        assert saved["visual"]["hero_regenerations_used"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd bot && python -m pytest tests/test_generate_candidates.py -v
```

Expected: `ModuleNotFoundError: No module named 'generate_candidates'`

- [ ] **Step 3: Create `bot/generate_candidates.py`**

```python
# bot/generate_candidates.py
# ─────────────────────────────────────────────
#  Generate hero image candidates for a given issue.
#
#  Usage (run from bot/):
#    python generate_candidates.py [--date YYYY-MM-DD]
#
#  Defaults to today's date.
#  Reads digest from digests/YYYY-MM-DD.json.
#  Writes candidates to tmp_images/YYYY-MM-DD/.
#  Sends photos + control message to Telegram.
#
#  Idempotent: exits cleanly if candidates already
#  exist for the current round, or if hero_image is set.
# ─────────────────────────────────────────────

import argparse
import json
import os
import sys
from datetime import date

import requests

from config import DIGEST_DIR
from image_candidates import generate_image_candidates

import pathlib
PROJECT_ROOT = str(pathlib.Path(DIGEST_DIR).parent)


# ── Telegram delivery ──────────────────────────

def _send_candidate_photos(token: str, chat_id: str, issue_date: str, candidates: dict) -> None:
    """Send 3 candidate photos to Telegram, each with an individual Select button."""
    labels = {"opt1": "Option 1", "opt2": "Option 2", "opt3": "Option 3"}

    for key in ("opt1", "opt2", "opt3"):
        path = candidates.get(key)
        if not path or not os.path.exists(path):
            print(f"  [generate_candidates] Skipping {key}: file not found at {path}")
            continue

        keyboard = {
            "inline_keyboard": [[
                {
                    "text": f"Select {labels[key].split()[-1]}",
                    "callback_data": f"select|{issue_date}|{key}",
                }
            ]]
        }

        try:
            with open(path, "rb") as photo_file:
                resp = requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={
                        "chat_id": chat_id,
                        "caption": labels[key],
                        "reply_markup": json.dumps(keyboard),
                    },
                    files={"photo": photo_file},
                    timeout=30,
                )
            if resp.ok:
                print(f"  [generate_candidates] Sent {key} photo.")
            else:
                print(f"  [generate_candidates] Failed {key}: {resp.status_code} {resp.text[:80]}")
        except Exception as exc:
            print(f"  [generate_candidates] Error sending {key} (non-fatal): {exc}")


def _send_control_message(token: str, chat_id: str, issue_date: str) -> None:
    """Send control message with Regenerate and Skip buttons."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "Regenerate", "callback_data": f"regenerate|{issue_date}"},
            {"text": "Skip",       "callback_data": f"skip|{issue_date}"},
        ]]
    }

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id":    chat_id,
                "text":       f"Which image do you want to use for {issue_date}?",
                "reply_markup": keyboard,
            },
            timeout=10,
        )
        if resp.ok:
            print("  [generate_candidates] Control message sent.")
        else:
            print(f"  [generate_candidates] Control message failed: {resp.status_code} {resp.text[:80]}")
    except Exception as exc:
        print(f"  [generate_candidates] Error sending control message (non-fatal): {exc}")


# ── Core logic (extracted for testability) ────

def _load_and_run(
    issue_date: str,
    digest_dir: str,
    project_root: str,
    token: str,
    chat_id: str,
) -> None:
    """Load digest, generate candidates, update digest, send to Telegram."""
    digest_path = os.path.join(digest_dir, f"{issue_date}.json")
    if not os.path.exists(digest_path):
        print(f"  [generate_candidates] No digest found for {issue_date} at {digest_path}")
        sys.exit(1)

    with open(digest_path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard 1: already locked
    if visual.get("hero_image"):
        print(f"  [generate_candidates] Issue {issue_date} already locked (hero_image set). Nothing to do.")
        return

    # Guard 2: candidates already exist for current round
    current_round = visual.get("hero_generation_round", 1)
    existing_candidates = visual.get("hero_image_candidates", {})
    if existing_candidates:
        round_files = {
            k: p for k, p in existing_candidates.items()
            if f"r{current_round}_" in os.path.basename(p)
        }
        if round_files and all(os.path.exists(p) for p in round_files.values()):
            print(
                f"  [generate_candidates] Candidates already exist for round {current_round}. "
                "Nothing to do. (Use regenerate flow to create new candidates.)"
            )
            return

    # Generate
    round_num = current_round
    new_candidates = generate_image_candidates(issue_date, visual, project_root, round_num)

    # Update visual block (init counters only if absent)
    visual["hero_image_candidates"] = new_candidates
    visual["hero_generation_round"] = visual.get("hero_generation_round", round_num)
    if "hero_regenerations_used" not in visual:
        visual["hero_regenerations_used"] = 0
    if "hero_image" not in visual:
        visual["hero_image"] = None
    data["visual"] = visual

    # Save digest
    with open(digest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [generate_candidates] Digest updated for {issue_date}.")

    # Send to Telegram (skip silently if credentials missing)
    if not token or not chat_id:
        print("  [generate_candidates] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set -- skipping Telegram send.")
        return

    _send_candidate_photos(token, chat_id, issue_date, new_candidates)
    _send_control_message(token, chat_id, issue_date)


# ── Entrypoint ────────────────────────────────

def run(issue_date: str) -> None:
    token   = os.environ.get("TELEGRAM_TOKEN",  "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    _load_and_run(issue_date, DIGEST_DIR, PROJECT_ROOT, token, chat_id)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate hero image candidates for a newsletter issue."
    )
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Issue date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    run(args.date)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd bot && python -m pytest tests/test_generate_candidates.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/generate_candidates.py bot/tests/test_generate_candidates.py
git commit -m "feat: add generate_candidates.py — CLI entrypoint for image candidate workflow"
```

---

## Task 4: Update `bot/telegram_bot.py`

Strip hero selection UI. Keep lightweight run notification.

**Files:**
- Modify: `bot/telegram_bot.py`

- [ ] **Step 1: Read the current file**

Open `bot/telegram_bot.py` and confirm the current content. It currently sends:
- headline, category, hero_options text previews (3 lines), archive URL, inline keyboard

- [ ] **Step 2: Replace the function body**

Replace the entire content of `bot/telegram_bot.py` with:

```python
# ─────────────────────────────────────────────
#  telegram_bot.py  —  Post-run issue notification
#
#  Sends a lightweight Telegram message after a successful run.
#  No selection buttons — visual candidate flow is handled by
#  generate_candidates.py.
#
#  Requires TELEGRAM_TOKEN and TELEGRAM_CHAT_ID env vars.
#  Skips silently if either is missing or the request fails.
# ─────────────────────────────────────────────

import os
import requests


def send_telegram_issue_notification(
    digest: dict,
    issue_date: str,
    archive_url: str | None = None,
) -> None:
    token   = os.environ.get("TELEGRAM_TOKEN",  "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("  [telegram] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set -- skipping.")
        return

    digest_en = digest.get("en", digest)
    stories   = digest_en.get("stories", [])
    headline  = stories[0].get("headline", "(no headline)") if stories else "(no headline)"
    visual    = digest.get("visual", {})
    category  = visual.get("hero_category", "")

    lines = [f"*The Opening Bell* — {issue_date}", ""]
    lines.append(f"*Lead:* {headline}")
    if category:
        lines.append(f"*Category:* {category}")
    if archive_url:
        lines.append("")
        lines.append(f"[Read today's issue]({archive_url})")
    lines.append("")
    lines.append("_Visual candidates: run generate\\_candidates.py_")

    text = "\n".join(lines)

    payload = {
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
        if resp.ok:
            print(f"  [telegram] Notification sent to chat {chat_id}.")
        else:
            print(f"  [telegram] Send failed: {resp.status_code} {resp.text[:120]}")
    except Exception as exc:
        print(f"  [telegram] Request error (non-fatal): {exc}")
```

- [ ] **Step 3: Verify the function signature is unchanged**

`main.py` calls `send_telegram_issue_notification(digest, issue_date, archive_url)`. The signature is identical — no changes to `main.py` needed.

- [ ] **Step 4: Commit**

```bash
git add bot/telegram_bot.py
git commit -m "feat: strip hero selection UI from main-run Telegram notification"
```

---

## Task 5: Fix `bot/pretty_renderer.py` and `bot/rerender.py`

Fix the existing bug: `hero_selected` is a key (`"opt2"`), not a URL. Only `hero_image` should be used as the image src.

**Files:**
- Modify: `bot/pretty_renderer.py` lines 305–313
- Modify: `bot/rerender.py` lines 78–79

- [ ] **Step 1: Fix `pretty_renderer.py`**

Find this block (lines 305–313):

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

Replace it with:

```python
    # ── Hero image (renders only when hero_image is set after selection) ──
    hero_html = ""
    if visual and visual.get("hero_image"):
        cat = visual.get("hero_category", "")
        src = visual["hero_image"]
        hero_html = f'''
<div class="hero-image">
  <img src="{src}" alt="{cat}">
</div>'''
```

- [ ] **Step 2: Fix `rerender.py`**

Find lines 78–81:

```python
    if visual and visual.get("hero_selected"):
        print(f"[rerender] Hero image: {visual['hero_selected']}")
    else:
        print("[rerender] No hero image (hero_selected is null -- set it in the digest JSON first)")
```

Replace with:

```python
    if visual and visual.get("hero_image"):
        print(f"[rerender] Hero image: {visual['hero_image']}")
    else:
        print("[rerender] No hero image (hero_image is null -- run generate_candidates.py and select an option)")
```

- [ ] **Step 3: Verify no other renderer reads `hero_selected` as a path**

```bash
grep -n "hero_selected" bot/pretty_renderer.py bot/rerender.py
```

Expected: zero matches (all references should be gone from renderer logic).

Also verify `bot/renderer.py` (email renderer) does not reference `hero_selected` or `hero_image` at all:

```bash
grep -n "hero_selected\|hero_image" bot/renderer.py 2>/dev/null || echo "not found -- correct"
```

Expected: `not found -- correct`

- [ ] **Step 4: Commit**

```bash
git add bot/pretty_renderer.py bot/rerender.py
git commit -m "fix: use visual.hero_image (not hero_selected) as img src in archive renderer"
```

---

## Task 6: Update `bot/telegram_handler.py`

Add `_handle_select()` (copy → verify → update digest → rerender → cleanup) and `_handle_regenerate()` (bounded, stateful). Replace the old `_set_hero_selected()`.

**Files:**
- Modify: `bot/telegram_handler.py`
- Create: `bot/tests/test_telegram_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `bot/tests/test_telegram_handler.py`:

```python
# bot/tests/test_telegram_handler.py
import os
import json
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_test_env(tmp):
    """Return (digest_dir, archive_dir, tmp_images_dir) under tmp."""
    digest_dir  = os.path.join(tmp, "digests")
    archive_dir = os.path.join(tmp, "docs")
    tmp_img_dir = os.path.join(tmp, "tmp_images")
    for d in (digest_dir, archive_dir, tmp_img_dir):
        os.makedirs(d, exist_ok=True)
    return digest_dir, archive_dir, tmp_img_dir


def _write_digest(digest_dir, issue_date, visual):
    data = {"digest": {}, "visual": visual}
    path = os.path.join(digest_dir, f"{issue_date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def _make_fake_png(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal fake PNG header


# ── _handle_select tests ──────────────────────

def test_handle_select_copies_file_and_updates_digest():
    from telegram_handler import _handle_select

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, tmp_img_dir = _make_test_env(tmp)

        cand_path = os.path.join(tmp_img_dir, "2026-04-07", "r1_opt2.png")
        _make_fake_png(cand_path)

        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_image_candidates": {
                "opt1": os.path.join(tmp_img_dir, "2026-04-07", "r1_opt1.png"),
                "opt2": cand_path,
                "opt3": os.path.join(tmp_img_dir, "2026-04-07", "r1_opt3.png"),
            },
            "hero_image": None,
        }
        digest_path = _write_digest(digest_dir, "2026-04-07", visual)

        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback"), \
             patch("telegram_handler.rerender"):
            _handle_select("tok", "cb123", "2026-04-07", "opt2")

        # Verify published image exists
        dst = os.path.join(archive_dir, "images", "2026-04-07.png")
        assert os.path.exists(dst), "Selected image must be copied to docs/images/"

        # Verify digest state
        with open(digest_path, encoding="utf-8") as f:
            saved = json.load(f)
        v = saved["visual"]
        assert v["hero_selected"] == "opt2"
        assert v["hero_image"] == "/images/2026-04-07.png"


def test_handle_select_rejects_already_locked():
    from telegram_handler import _handle_select

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, _ = _make_test_env(tmp)
        visual = {"hero_image": "/images/2026-04-07.png"}
        _write_digest(digest_dir, "2026-04-07", visual)

        mock_answer = MagicMock()
        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback", mock_answer):
            _handle_select("tok", "cb123", "2026-04-07", "opt2")

        mock_answer.assert_called_once_with("tok", "cb123", "Already locked.")


def test_handle_select_does_not_delete_src_before_copy_verified():
    """src file must still exist (not deleted) if copy fails."""
    from telegram_handler import _handle_select

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, tmp_img_dir = _make_test_env(tmp)

        cand_path = os.path.join(tmp_img_dir, "2026-04-07", "r1_opt1.png")
        _make_fake_png(cand_path)

        visual = {
            "hero_image_candidates": {"opt1": cand_path, "opt2": "missing.png", "opt3": "missing.png"},
            "hero_image": None,
        }
        _write_digest(digest_dir, "2026-04-07", visual)

        # Simulate copy failure by making archive_dir a file (not a dir)
        images_dst = os.path.join(archive_dir, "images")
        open(images_dst, "w").close()  # images is a file, makedirs will fail

        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback"):
            _handle_select("tok", "cb123", "2026-04-07", "opt1")

        # Source file must NOT have been deleted
        assert os.path.exists(cand_path), "Source tmp candidate must not be deleted if copy fails"


# ── _handle_regenerate tests ──────────────────

def test_handle_regenerate_increments_counters():
    from telegram_handler import _handle_regenerate

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, _ = _make_test_env(tmp)
        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_image": None,
            "hero_generation_round": 1,
            "hero_regenerations_used": 0,
            "hero_image_candidates": {},
        }
        digest_path = _write_digest(digest_dir, "2026-04-07", visual)

        mock_answer = MagicMock()
        mock_gen = MagicMock(return_value={"opt1": "/p/r2_opt1.png", "opt2": "/p/r2_opt2.png", "opt3": "/p/r2_opt3.png"})

        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback", mock_answer), \
             patch("telegram_handler.generate_image_candidates", mock_gen), \
             patch("telegram_handler._send_candidate_photos"), \
             patch("telegram_handler._send_control_message"):
            _handle_regenerate("tok", "cb123", "2026-04-07")

        with open(digest_path, encoding="utf-8") as f:
            saved = json.load(f)

        v = saved["visual"]
        assert v["hero_generation_round"] == 2
        assert v["hero_regenerations_used"] == 1


def test_handle_regenerate_blocks_at_limit():
    from telegram_handler import _handle_regenerate

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, _ = _make_test_env(tmp)
        visual = {
            "hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"},
            "hero_image": None,
            "hero_generation_round": 3,
            "hero_regenerations_used": 2,  # at limit
        }
        _write_digest(digest_dir, "2026-04-07", visual)

        mock_answer = MagicMock()
        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback", mock_answer):
            _handle_regenerate("tok", "cb123", "2026-04-07")

        mock_answer.assert_called_once_with("tok", "cb123", "No more regenerations allowed.")


def test_handle_regenerate_rejects_already_locked():
    from telegram_handler import _handle_regenerate

    with tempfile.TemporaryDirectory() as tmp:
        digest_dir, archive_dir, _ = _make_test_env(tmp)
        visual = {"hero_image": "/images/2026-04-07.png"}
        _write_digest(digest_dir, "2026-04-07", visual)

        mock_answer = MagicMock()
        with patch("telegram_handler.DIGEST_DIR", digest_dir), \
             patch("telegram_handler.ARCHIVE_DIR", archive_dir), \
             patch("telegram_handler._answer_callback", mock_answer):
            _handle_regenerate("tok", "cb123", "2026-04-07")

        mock_answer.assert_called_once_with("tok", "cb123", "Already locked.")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd bot && python -m pytest tests/test_telegram_handler.py -v
```

Expected: `ImportError` or `AttributeError` — `_handle_select` and `_handle_regenerate` don't exist yet.

- [ ] **Step 3: Replace `bot/telegram_handler.py`**

Replace the entire file with:

```python
# ─────────────────────────────────────────────
#  telegram_handler.py  —  Polls Telegram for
#  editorial callbacks and handles:
#    select|YYYY-MM-DD|optN   — copy, verify, publish, rerender
#    regenerate|YYYY-MM-DD    — new candidate batch (max 2)
#    skip|YYYY-MM-DD          — no-op acknowledgement
#
#  Usage (run from bot/):
#    python telegram_handler.py
#
#  Requires: TELEGRAM_TOKEN env var.
#  Offset between runs is persisted in:
#    bot/.telegram_offset
# ─────────────────────────────────────────────

import json
import os
import pathlib
import shutil

import requests

from config import DIGEST_DIR, ARCHIVE_DIR
from image_candidates import generate_image_candidates
from generate_candidates import _send_candidate_photos, _send_control_message
from rerender import rerender

_OFFSET_FILE = os.path.join(os.path.dirname(__file__), ".telegram_offset")

_MAX_REGENERATIONS = 2


# ── Offset persistence ────────────────────────

def _load_offset() -> int:
    if os.path.exists(_OFFSET_FILE):
        try:
            return int(open(_OFFSET_FILE).read().strip())
        except (ValueError, OSError):
            pass
    return 0


def _save_offset(offset: int) -> None:
    with open(_OFFSET_FILE, "w") as f:
        f.write(str(offset))


# ── Telegram helpers ──────────────────────────

def _answer_callback(token: str, callback_id: str, text: str = "") -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=5,
        )
    except Exception:
        pass


# ── Tmp candidate cleanup ─────────────────────

def _cleanup_tmp_candidates(issue_date: str, selected_key: str, candidates: dict) -> None:
    """Delete non-selected tmp candidate files. Non-fatal on any error."""
    for key, path in candidates.items():
        if key == selected_key:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"  [telegram_handler] Deleted tmp: {os.path.basename(path)}")
        except OSError as exc:
            print(f"  [telegram_handler] Could not delete {path}: {exc} (non-fatal)")


# ── Selection handler ─────────────────────────

def _handle_select(token: str, cb_id: str, issue_date: str, key: str) -> None:
    """
    Copy selected candidate to docs/images/, verify, update digest, rerender.
    Safe order: copy → verify → update state → save → rerender → cleanup.
    """
    path = os.path.join(DIGEST_DIR, f"{issue_date}.json")
    if not os.path.exists(path):
        _answer_callback(token, cb_id, "Issue not found.")
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard: already locked
    if visual.get("hero_image"):
        _answer_callback(token, cb_id, "Already locked.")
        return

    # Validate key
    candidates = visual.get("hero_image_candidates", {})
    if key not in candidates:
        _answer_callback(token, cb_id, "Candidate key not found.")
        return

    src_path = candidates[key]
    if not os.path.exists(src_path):
        _answer_callback(token, cb_id, "Candidate file missing on disk.")
        return

    # 1. Copy to published location
    images_dir = os.path.join(ARCHIVE_DIR, "images")
    try:
        os.makedirs(images_dir, exist_ok=True)
    except OSError as exc:
        print(f"  [telegram_handler] Could not create images dir: {exc}")
        _answer_callback(token, cb_id, "Server error creating images dir.")
        return

    dst_path = os.path.join(images_dir, f"{issue_date}.png")
    try:
        shutil.copy2(src_path, dst_path)
    except OSError as exc:
        print(f"  [telegram_handler] Copy failed: {exc}")
        _answer_callback(token, cb_id, "Copy failed.")
        return

    # 2. Verify destination
    if not os.path.exists(dst_path):
        print(f"  [telegram_handler] Verification failed: {dst_path} not found after copy.")
        _answer_callback(token, cb_id, "Verification failed.")
        return

    # 3. Update state
    visual["hero_selected"] = key
    visual["hero_image"] = f"/images/{issue_date}.png"
    data["visual"] = visual

    # 4. Save digest
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 5. Rerender archive
    try:
        rerender(issue_date)
    except Exception as exc:
        print(f"  [telegram_handler] Rerender error (non-fatal): {exc}")

    # 6. Cleanup non-selected tmp candidates
    _cleanup_tmp_candidates(issue_date, key, candidates)

    # 7. Answer
    _answer_callback(token, cb_id, f"Saved: {key}")
    print(f"  [telegram_handler] Selection complete: {key} for {issue_date}.")


# ── Regeneration handler ──────────────────────

def _handle_regenerate(token: str, cb_id: str, issue_date: str) -> None:
    """
    Generate a new round of candidates.
    Bounded by _MAX_REGENERATIONS. Counters are incremented, never reset.
    """
    path = os.path.join(DIGEST_DIR, f"{issue_date}.json")
    if not os.path.exists(path):
        _answer_callback(token, cb_id, "Issue not found.")
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard: already locked
    if visual.get("hero_image"):
        _answer_callback(token, cb_id, "Already locked.")
        return

    # Check limit
    regen_used = visual.get("hero_regenerations_used", 0)
    if regen_used >= _MAX_REGENERATIONS:
        _answer_callback(token, cb_id, "No more regenerations allowed.")
        return

    # Answer callback early — generation takes a moment
    _answer_callback(token, cb_id, "Generating new candidates...")

    # Increment counters
    current_round = visual.get("hero_generation_round", 1)
    new_round     = current_round + 1
    visual["hero_generation_round"]   = new_round
    visual["hero_regenerations_used"] = regen_used + 1

    # Generate new candidates
    project_root = str(pathlib.Path(DIGEST_DIR).parent)
    try:
        new_candidates = generate_image_candidates(issue_date, visual, project_root, new_round)
    except Exception as exc:
        print(f"  [telegram_handler] Candidate generation error: {exc}")
        return

    visual["hero_image_candidates"] = new_candidates
    data["visual"] = visual

    # Save digest
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Send new photos + control message
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if chat_id:
        _send_candidate_photos(token, chat_id, issue_date, new_candidates)
        _send_control_message(token, chat_id, issue_date)

    print(f"  [telegram_handler] Regeneration round {new_round} complete for {issue_date}.")


# ── Main poll function ────────────────────────

def process_telegram_updates() -> None:
    """
    Poll Telegram getUpdates once, process any pending callback_query updates,
    and persist the new offset so updates are not reprocessed.
    Non-fatal on all network errors.
    """
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        print("  [telegram_handler] TELEGRAM_TOKEN not set -- skipping.")
        return

    offset = _load_offset()

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={
                "offset":          offset,
                "timeout":         5,
                "allowed_updates": json.dumps(["callback_query"]),
            },
            timeout=15,
        )
        if not resp.ok:
            print(f"  [telegram_handler] getUpdates failed: {resp.status_code} {resp.text[:120]}")
            return
        updates = resp.json().get("result", [])
    except Exception as exc:
        print(f"  [telegram_handler] Request error (non-fatal): {exc}")
        return

    new_offset = offset
    for update in updates:
        update_id  = update["update_id"]
        new_offset = update_id + 1

        cb = update.get("callback_query")
        if not cb:
            continue

        cb_id  = cb["id"]
        cb_data = cb.get("data", "")
        parts  = cb_data.split("|")

        if len(parts) < 2:
            _answer_callback(token, cb_id)
            continue

        action     = parts[0]
        issue_date = parts[1]

        if action == "skip":
            _answer_callback(token, cb_id, "Skipped.")
            print(f"  [telegram_handler] Skip received for {issue_date}.")

        elif action == "select" and len(parts) == 3:
            _handle_select(token, cb_id, issue_date, parts[2])

        elif action == "regenerate":
            _handle_regenerate(token, cb_id, issue_date)

        else:
            _answer_callback(token, cb_id)

    _save_offset(new_offset)
    print(f"  [telegram_handler] Processed {len(updates)} update(s). Offset: {new_offset}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    process_telegram_updates()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd bot && python -m pytest tests/test_telegram_handler.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd bot && python -m pytest tests/ -v
```

Expected: all tests pass (image_candidates + generate_candidates + telegram_handler).

- [ ] **Step 6: Commit**

```bash
git add bot/telegram_handler.py bot/tests/test_telegram_handler.py
git commit -m "feat: add select/regenerate handlers to telegram_handler.py with safe copy-verify-rerender flow"
```

---

## Task 7: Final Verification + Full Commit

Smoke-test the end-to-end flow locally without Telegram credentials.

**Files:** none (verification only)

- [ ] **Step 1: Verify imports are clean**

```bash
cd bot && python -c "import image_candidates; import generate_candidates; import telegram_handler; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 2: Verify `pretty_renderer.py` no longer references `hero_selected` as image src**

```bash
grep -n "hero_selected" bot/pretty_renderer.py
```

Expected: zero output (the field no longer appears in the renderer).

- [ ] **Step 3: Verify `telegram_bot.py` has no `inline_keyboard` or `hero_options` preview code**

```bash
grep -n "inline_keyboard\|hero_options\|opt1\|opt2\|opt3" bot/telegram_bot.py
```

Expected: zero output.

- [ ] **Step 4: Smoke test generate_candidates.py with a real digest (no Telegram)**

If a digest exists for today or a recent date:

```bash
cd bot && python generate_candidates.py --date YYYY-MM-DD
```

With `TELEGRAM_TOKEN` unset, expected output:
```
  [image_candidates] Stub image saved: .../tmp_images/YYYY-MM-DD/r1_opt1.png
  [image_candidates] Stub image saved: .../tmp_images/YYYY-MM-DD/r1_opt2.png
  [image_candidates] Stub image saved: .../tmp_images/YYYY-MM-DD/r1_opt3.png
  [generate_candidates] Digest updated for YYYY-MM-DD.
  [generate_candidates] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set -- skipping Telegram send.
```

Verify the 3 PNG files exist under `tmp_images/YYYY-MM-DD/`.

- [ ] **Step 5: Smoke test idempotency**

Run the same command again immediately:

```bash
cd bot && python generate_candidates.py --date YYYY-MM-DD
```

Expected:
```
  [generate_candidates] Candidates already exist for round 1. Nothing to do. ...
```

- [ ] **Step 6: Run full test suite one final time**

```bash
cd bot && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: hero image candidate flow — stub generation, Telegram delivery, selection, rerender"
```

---

## Summary of Changed Behavior

| Before | After |
|--------|-------|
| `telegram_bot.py` sent text previews + selection buttons | Sends lightweight notification only; visual step is separate |
| `pretty_renderer.py` used `hero_selected` (a key) as img src — broken | Uses `hero_image` (a web path) — correct |
| No candidate image files existed | `generate_candidates.py` creates stub PNGs in `tmp_images/YYYY-MM-DD/` |
| `telegram_handler.py` only stored the key | Now copies file, verifies, updates `hero_image`, rerenders, cleans up |
| No regenerate flow | Bounded (max 2) stateful regenerate with counter increment |

## Notes for Real Provider Swap

When replacing the stub with DALL-E 3 or another provider, **only** `bot/image_candidates.py:generate_image()` needs to change. The function signature `(prompt: str, output_path: str) -> None` is stable. All downstream code (generate_candidates.py, telegram_handler.py) calls `generate_image_candidates()` which calls `generate_image()`.

Add the provider API key to `bot/.env` and `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` must already be present for the Telegram flow to work end-to-end.
