# Hero Image Candidate Flow — Design Spec
**Date:** 2026-04-07
**Status:** Approved

---

## Overview

Extend the visual workflow to generate, store, deliver, and publish hero image candidates
for each newsletter issue. The core pipeline (digest + archive + email) remains unchanged.
Image generation is a separate, independently invokable step.

---

## Architecture

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | Digest + archive + email + lightweight Telegram notification. No image generation. |
| `telegram_bot.py` | Lightweight run notification: date, headline, category, archive URL. No selection UI. |
| `image_candidates.py` | Pure image generation: `generate_image()` stub + `generate_image_candidates()`. No Telegram, no digest I/O. |
| `generate_candidates.py` | CLI entrypoint: load digest → generate candidates → update digest → send photos to Telegram. Idempotent per round. |
| `telegram_handler.py` | Poll getUpdates → handle `select`, `regenerate`, `skip` callbacks. Owns editorial selection state machine. |
| `pretty_renderer.py` | Reads `visual.hero_image` only. Never reads `hero_selected` or `hero_image_candidates`. |
| `rerender.py` | Single-issue archive re-render. Called by `telegram_handler.py` after confirmed selection. |

### End-to-End Flow

```
[main.py]
  → digest + archive + email
  → lightweight Telegram: date, headline, category, archive URL, note about visual step
  → no image generation, no selection buttons

[generate_candidates.py --date YYYY-MM-DD]  (manual / cron / n8n)
  → load digests/YYYY-MM-DD.json
  → guard: if hero_image set → print "already locked", exit
  → guard: if candidates already exist for current round → print "already generated", exit
  → generate_image_candidates() → tmp_images/YYYY-MM-DD/r1_opt1.png, r1_opt2.png, r1_opt3.png
  → update visual: hero_image_candidates, hero_generation_round, hero_regenerations_used
  → save digest
  → send 3 Telegram photos (one per option, each with individual Select button)
  → send control message (Regenerate + Skip)

[user taps Select 2 on phone]

[telegram_handler.py]  (cron or manual)
  → parse select|YYYY-MM-DD|opt2
  → guard: if hero_image set → answer "Already locked.", return
  → validate opt2 in hero_image_candidates
  → copy tmp_images/YYYY-MM-DD/r1_opt2.png → docs/images/YYYY-MM-DD.png
  → verify destination exists
  → set visual.hero_selected = "opt2"
  → set visual.hero_image = "/images/YYYY-MM-DD.png"
  → save digest
  → call rerender(YYYY-MM-DD)
  → delete remaining tmp candidates (non-selected files only)
  → answer callback "Saved: opt2"
```

---

## Visual Schema

Fields present in `digests/YYYY-MM-DD.json` under the `visual` key:

```json
{
  "hero_category": "FX",
  "hero_category_source": "lead_story",
  "hero_prompt_template": "...",
  "hero_prompt_version": "v1",
  "hero_prompt": "...",
  "hero_options": {
    "opt1": "...",
    "opt2": "...",
    "opt3": "..."
  },
  "hero_selected": null,
  "hero_image_candidates": {
    "opt1": "/home/adrian/project/tmp_images/2026-04-07/r1_opt1.png",
    "opt2": "/home/adrian/project/tmp_images/2026-04-07/r1_opt2.png",
    "opt3": "/home/adrian/project/tmp_images/2026-04-07/r1_opt3.png"
  },
  "hero_image": null,
  "hero_generation_round": 1,
  "hero_regenerations_used": 0
}
```

### Field Rules

| Field | Type | Notes |
|-------|------|-------|
| `hero_selected` | `str \| null` | Key only: `"opt1"`, `"opt2"`, `"opt3"`. Set on selection. |
| `hero_image_candidates` | `dict \| absent` | VPS-internal absolute filesystem paths. Ephemeral. Never used by any renderer. |
| `hero_image` | `str \| null` | Public web path only: `/images/YYYY-MM-DD.png`. The only field renderers may read. |
| `hero_generation_round` | `int` | Starts at 1. Incremented on regenerate. Never reset. |
| `hero_regenerations_used` | `int` | Starts at 0. Incremented on regenerate. Never reset. Max: 2. |

### State Transitions

| Field | After `main.py` | After `generate_candidates.py` | After selection |
|-------|----------------|-------------------------------|-----------------|
| `hero_options` | populated | unchanged | unchanged |
| `hero_selected` | `null` | `null` | `"opt2"` |
| `hero_image_candidates` | absent | populated (abs paths) | unchanged |
| `hero_image` | absent | `null` | `"/images/YYYY-MM-DD.png"` |
| `hero_generation_round` | absent | `1` | unchanged |
| `hero_regenerations_used` | absent | `0` | unchanged |

---

## Filesystem Layout

```
/home/adrian/project/
├── tmp_images/                        ← gitignored, VPS-internal
│   └── YYYY-MM-DD/
│       ├── r1_opt1.png
│       ├── r1_opt2.png
│       ├── r1_opt3.png
│       ├── r2_opt1.png                ← only if regenerated
│       ├── r2_opt2.png
│       └── r2_opt3.png
└── docs/
    └── images/                        ← committed to repo, served by GitHub Pages
        └── YYYY-MM-DD.png             ← only the final selected image
```

---

## Module Designs

### `bot/image_candidates.py`

```python
def generate_image(prompt: str, output_path: str) -> None:
    """
    Stub: creates a solid-color placeholder PNG.
    Replace body with real provider (e.g. OpenAI Images / DALL-E 3).
    Signature is stable — do not change prompt or output_path.
    """
    # TODO: real provider

def generate_image_candidates(
    issue_date: str,
    visual: dict,
    project_root: str,
    round_num: int = 1,
) -> dict:
    """
    Generates 3 candidate PNGs for the given round.
    Creates tmp_images/YYYY-MM-DD/ if absent.
    Returns: {"opt1": "/abs/path/r1_opt1.png", "opt2": ..., "opt3": ...}
    Raises ValueError if hero_options missing or empty.
    """
```

### `bot/generate_candidates.py`

CLI entrypoint. Usage: `python generate_candidates.py [--date YYYY-MM-DD]`

```
run(issue_date):
  1. load digest
  2. guard: hero_image set → "already locked", exit
  3. guard: candidates exist for current round → "already generated", exit
  4. determine round_num (hero_generation_round if present, else 1)
  5. generate_image_candidates() → candidate paths
  6. update visual: hero_image_candidates, hero_generation_round (init if absent),
     hero_regenerations_used (init if absent), hero_image = None (if absent)
  7. save digest
  8. send 3 Telegram photos (each with Select button)
  9. send control message (Regenerate + Skip)
```

### `bot/telegram_bot.py` (modified)

Strip: option preview lines, inline keyboard buttons.
Keep: issue date, lead headline, hero category, archive URL.
Add: passive note — `"Visual candidates: run generate_candidates.py"`

### `bot/telegram_handler.py` (modified)

New callback handlers:

**`select|YYYY-MM-DD|optN`:**
1. Guard: `hero_image` set → answer "Already locked.", return
2. Validate key in `hero_image_candidates`
3. Copy selected file → `docs/images/YYYY-MM-DD.png`
4. Verify destination exists
5. Set `hero_selected`, `hero_image = "/images/YYYY-MM-DD.png"`
6. Save digest
7. Call `rerender(issue_date)`
8. Delete remaining tmp candidates
9. Answer callback

**`regenerate|YYYY-MM-DD`:**
1. Guard: `hero_image` set → answer "Already locked.", return
2. Check `hero_regenerations_used < 2` → if limit reached: answer "No more regenerations.", return
3. Increment `hero_generation_round`, `hero_regenerations_used`
4. Call `generate_image_candidates()` for new round
5. Update `hero_image_candidates`
6. Save digest
7. Send 3 new photos + control message
8. Answer callback "New candidates sent."

**`skip|YYYY-MM-DD`:** unchanged

### `bot/pretty_renderer.py` (modified)

```python
# Replace:
if visual and visual.get("hero_selected"):
    src = visual["hero_selected"]

# With:
if visual and visual.get("hero_image"):
    src = visual["hero_image"]
    hero_html = f'<div class="hero-image"><img src="{src}" alt="Hero image"></div>'
```

---

## Selection File Operation Order (CRITICAL)

```
1. shutil.copy2(src_path, dst_path)          # copy first
2. assert os.path.exists(dst_path)           # verify destination
3. visual["hero_selected"] = key             # update state
4. visual["hero_image"] = "/images/..."      # public web path only
5. save digest JSON                          # persist
6. rerender(issue_date)                      # update archive HTML
7. delete non-selected tmp candidates        # cleanup last
```

Never delete tmp files before step 2 is verified.

---

## Telegram UX

**Per-image message:**
```
[photo]
Caption: "Option 1"
Button: [Select 1]  ← callback: select|YYYY-MM-DD|opt1
```
(repeated for opt2, opt3 as separate messages)

**Control message (text only):**
```
"Which image do you want to use for YYYY-MM-DD?"
Buttons: [Regenerate] [Skip]
```
Callbacks: `regenerate|YYYY-MM-DD`, `skip|YYYY-MM-DD`

---

## Constraints

- No external API integration in this phase (stub only)
- No database
- No webhooks
- No async framework
- No full bot framework
- No email renderer changes
- `docs/images/` must be created if absent (not gitignored)
- `tmp_images/` must be gitignored
- Backward compat: old digests without new fields handled with `.get()` throughout

---

## Placeholder / Stub Note

`generate_image()` currently creates a solid-color PNG using `Pillow`. This validates the
entire filesystem + Telegram + selection + rerender flow without any external API dependency.
When the real provider is ready, only the body of `generate_image()` needs to change.
The `Pillow` dependency is already in `requirements.txt` (used by `wordcloud_gen.py`).
