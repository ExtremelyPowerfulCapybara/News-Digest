# Design: Wire Image Generation into main.py

**Date:** 2026-04-21
**Status:** Approved
**Scope:** Archive-only hero image per issue; no email changes.

---

## Goal

Call `lib/image_generator.py`'s `generate_editorial_image()` during each production run to produce
a real PNG hero image, save it to `docs/images/`, and surface it in the archive renderer.
The archive renderer (`pretty_renderer.py`) already has the hero image block — it just needs
`visual["hero_image"]` populated with a URL.

---

## Data Flow

```
main.py
  └─ generate_hero_image(digest, today_str, output_dir)   ← new fn in image_gen.py
       ├─ generate_hero_prompt(digest)                     ← existing, unchanged
       ├─ SKIP_IMAGE=true → return visual (no hero_image)  ← early exit
       └─ generate_editorial_image(...)                    ← lib/image_generator.py
            └─ PNG → docs/images/YYYY-MM-DD-hero.png
                 └─ visual["hero_image"] = full URL
                      └─ pretty_renderer reads hero_image  ← no change needed
```

---

## File Changes

### `bot/image_gen.py` — add `generate_hero_image()`

New public function below the existing `generate_hero_prompt()`:

```python
def generate_hero_image(digest: dict, issue_date: str, output_dir: str = "../docs/images") -> dict:
```

Logic:
1. Call `generate_hero_prompt(digest)` → `visual`
2. Check `os.environ.get("SKIP_IMAGE", "false").lower()` — if truthy, return `visual` as-is
3. Extract `category = visual["hero_category"]` and `context` = lead story headline
4. Map `hero_category` (story tag e.g. "Macro", "Energia") to a `CATEGORY_PRESETS` key
   (e.g. `"macro_inflation"`, `"energy"`); fall back to `"macro_inflation"` for unmapped tags.
   Use the preset dict as fallback values for `main_subject`, `environment`, `composition`,
   `color_system`. The registry resolves `main_subject`/`composition`/`color_system` at
   generation time, but `environment` is always caller-supplied — the preset ensures it is
   always a meaningful string, never empty.
5. Call `generate_editorial_image(issue_date, "hero", category, ..., output_dir=output_dir)`
   passing the four preset fields as fallbacks
   - `context`: lead story headline (enriches prompt)
6. On success: `visual["hero_image"] = f"{ASSET_BASE_URL.rstrip('/')}/images/{issue_date}-hero.png"`
7. On any exception: log `[image_gen] Hero image generation failed: {exc}` and return `visual` without `hero_image`
8. Return `visual`

### `main.py` — update step 3.5

Replace:
```python
visual = generate_hero_prompt(digest)
print(f"  [visual] Category: ...")
```

With:
```python
visual = generate_hero_image(digest, today_str, output_dir="../docs/images")
print(f"  [visual] Category: {visual['hero_category']} | image: {'yes' if visual.get('hero_image') else 'skipped'}")
```

Update import: `from image_gen import generate_hero_image`

### `config.py` — add `SKIP_IMAGE`

```python
SKIP_IMAGE = os.environ.get("SKIP_IMAGE", "false").lower() in {"true", "1", "yes"}
```

(Read inside `image_gen.py` via `os.environ` directly, consistent with how other skip flags work.)

### `docs/images/` — new directory

Add `.gitkeep` so git tracks the directory before the first image is generated.

### No changes to

- `pretty_renderer.py` — already reads `visual.get("hero_image")`
- `renderer.py` — email out of scope
- `archive.py`, `storage.py`, `summarizer.py` — untouched

---

## URL Construction

Follows the existing wordcloud pattern exactly:

```python
visual["hero_image"] = f"{ASSET_BASE_URL.rstrip('/')}/images/{issue_date}-hero.png"
```

`ASSET_BASE_URL` is set to `GITHUB_RAW_URL` in dev (serves from `Dev-Nigg/docs/`) and
`PUBLIC_ARCHIVE_BASE_URL` in production — already handles both environments.

---

## Error Handling

`generate_hero_image()` wraps the `generate_editorial_image()` call in a try/except.
On failure: logs the error, returns `visual` without `hero_image`. The archive issue
renders without a hero image — same as today. The full run is never blocked.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_IMAGE` | `false` | Skip OpenAI image generation (mock runs, CI) |
| `OPENAI_API_KEY` | — | Required when `SKIP_IMAGE` is not set |
| `OPENAI_IMAGE_SIZE` | `1024x1024` | Already supported by `image_generator.py` |
| `OPENAI_IMAGE_QUALITY` | `medium` | Already supported by `image_generator.py` |

---

## Out of Scope

- Per-story images
- Email embedding (archive-only for now)
- Image display in the email renderer
- Backfilling images for past archive issues
