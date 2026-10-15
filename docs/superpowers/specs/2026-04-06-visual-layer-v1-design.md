# Visual Layer v1 — Design Spec
**Date:** 2026-04-06
**Project:** The Periphery / Mexico Finance Brief
**Scope:** Semiautomated hero image prompt generation; archive renderer integration

---

## Overview

Add a minimal visual metadata layer to each issue. The pipeline auto-generates a hero image prompt from the lead story tag and sentiment. The prompt is stored in the digest JSON. A human manually sets `hero_selected` to an image URL when ready. The archive renderer optionally displays the hero image — only when `hero_selected` is not null. Email renderer is unchanged.

---

## Architecture

### New files
- `bot/prompt_map.py` — category-to-prompt template dict
- `bot/image_gen.py` — hero prompt generator; pure function, no API calls

### Modified files
- `bot/storage.py` — `save_digest` gains optional `visual` param
- `bot/main.py` — calls `generate_hero_prompt(digest)`, threads `visual` through to save and archive
- `bot/archive.py` — `save_pretty_issue()` gains `visual` param, passes to renderer
- `bot/pretty_renderer.py` — `build_pretty_html()` gains `visual` param, renders hero block conditionally

### Data flow

```
summarize_news() → digest
                      ↓
         image_gen.generate_hero_prompt(digest)
                      ↓  returns visual dict
         save_digest(digest, market, visual)
                      ↓  stored in digests/YYYY-MM-DD.json
         save_pretty_issue(..., visual)
                      ↓
         build_pretty_html(..., visual)
                      ↓  renders <img> only if visual["hero_selected"] is not null
```

---

## Digest JSON Extension

`visual` is a new top-level key in the stored JSON, alongside `date`, `digest`, and `market`. It is issue-level metadata — not bilingual, not part of the Claude-generated content.

```json
{
  "date": "2026-04-06",
  "digest": { "es": {...}, "en": {...} },
  "market": { "tickers": [...], "currency": {...} },
  "visual": {
    "hero_category": "Energía",
    "hero_prompt": "Editorial photograph: Trump threatens Iran...",
    "hero_selected": null
  }
}
```

`hero_selected` starts as `null` from every pipeline run. It is set exclusively by manual edit of the digest JSON file. The renderer guard (`if visual and visual.get("hero_selected")`) ensures no visual change occurs until a human sets that field.

---

## Components

### `bot/prompt_map.py`

Single module-level dict `PROMPT_TEMPLATES`. Keys are the 8 Claude story tags:
`Macro`, `FX`, `México`, `Comercio`, `Tasas`, `Mercados`, `Energía`, `Política`.

Each value is a prompt string with two placeholders:
- `{headline}` — lead story headline (Spanish, from `digest["es"]["stories"][0]["headline"]`)
- `{sentiment}` — English sentiment label (`Risk-Off`, `Cautious`, or `Risk-On`)

Template structure (consistent across all tags):
```
"Editorial photograph: {headline}. Mood: {sentiment}.
<category-specific visual anchor>.
Dark editorial palette, cinematic lighting, no text, no people, photorealistic, 16:9."
```

Category-specific visual anchors (one per tag):
- `Macro` — central bank interior, marble columns, empty trading floor at dawn
- `FX` — currency exchange board, blurred figures, neon reflections on wet pavement
- `México` — Mexico City skyline at dusk, Torre Mayor, grey-orange sky
- `Comercio` — shipping containers at a port, cranes silhouetted at sunset
- `Tasas` — Federal Reserve or Banxico exterior, stone facade, overcast sky
- `Mercados` — stock exchange floor, screens with red/green numbers, motion blur
- `Energía` — oil refinery or offshore platform at dusk, dramatic sky, smoke stacks
- `Política` — government building exterior, flags, dramatic clouds

### `bot/image_gen.py`

```python
from prompt_map import PROMPT_TEMPLATES

def generate_hero_prompt(digest: dict) -> dict:
    digest_es = digest.get("es", digest)
    stories   = digest_es.get("stories", [])
    sentiment = digest_es.get("sentiment", {})

    tag       = stories[0].get("tag", "Macro") if stories else "Macro"
    headline  = stories[0].get("headline", "") if stories else ""
    mood      = sentiment.get("label_en", "Cautious")

    template  = PROMPT_TEMPLATES.get(tag, PROMPT_TEMPLATES["Macro"])
    prompt    = template.format(headline=headline, sentiment=mood)

    return {
        "hero_category": tag,
        "hero_prompt":   prompt,
        "hero_selected": None,
    }
```

One public function. No side effects. No external calls. Under 25 lines.

### `bot/storage.py`

`save_digest` signature change:
```python
def save_digest(digest: dict, market: dict, visual: dict | None = None) -> None:
```

Payload construction:
```python
payload = {
    "date":   today,
    "digest": digest,
    "market": market,
}
if visual is not None:
    payload["visual"] = visual
```

No other changes to `storage.py`.

### `bot/main.py`

One import added at the top of the file. One call added after the mock/live if-else block converges (after line 72, `digest_es = digest.get(...)`):

```python
# top of file
from image_gen import generate_hero_prompt

# after the if MOCK_MODE / else block, before save_digest
visual = generate_hero_prompt(digest)
```

This works for both mock and live mode with a single call — no duplication inside the branches.

Updated `save_digest` call:
```python
save_digest(digest, {"tickers": tickers, "currency": currency}, visual=visual)
```

Updated `save_pretty_issue` call:
```python
save_pretty_issue(..., visual=visual)
```

`generate_hero_prompt` runs in both live and mock mode — it is pure text with no API calls.

### `bot/archive.py`

`save_pretty_issue()` signature change:
```python
def save_pretty_issue(..., visual: dict | None = None) -> None:
```

Passes `visual` through to `build_pretty_html()`. No other logic changes.

### `bot/pretty_renderer.py`

`build_pretty_html()` signature change:
```python
def build_pretty_html(..., visual: dict | None = None) -> str:
```

Hero block inserted after the narrative thread section, before the first story divider:

```python
hero_html = ""
if visual and visual.get("hero_selected"):
    cat = visual.get("hero_category", "")
    src = visual["hero_selected"]
    hero_html = f'''
<div class="hero-image">
  <img src="{src}" alt="{cat}">
</div>'''
```

CSS addition to the `CSS` string (inside the existing block):
```css
.hero-image { line-height: 0; border-bottom: 1px solid #cdd4d9; }
.hero-image img { width: 100%; display: block; }
```

---

## Error Handling & Backward Compatibility

| Scenario | Behavior |
|---|---|
| Old digest (no `visual` key) | Renderer skips hero block silently via `.get()` guard |
| `hero_selected` is null | Renderer skips hero block; no visual change |
| Unknown tag from Claude | Falls back to `PROMPT_TEMPLATES["Macro"]` |
| Empty stories list | `generate_hero_prompt` defaults to tag=`"Macro"`, headline=`""` |
| Mock mode | `generate_hero_prompt` runs normally; digest loaded from disk is still valid input |

No new Python dependencies. No changes to `requirements.txt`.

---

## Out of Scope for v1

- Image API integration (DALL-E, Midjourney, Stable Diffusion)
- Email renderer hero image (`renderer.py` unchanged)
- Automated `hero_selected` population
- Per-story images (hero is issue-level only)
- Admin UI for image selection

---

## Manual Workflow (post-v1 run)

1. Run the pipeline (live or mock)
2. Open `digests/YYYY-MM-DD.json`
3. Find `visual.hero_prompt`
4. Generate an image externally (Midjourney, DALL-E, etc.) using that prompt
5. Host or reference the image URL
6. Set `visual.hero_selected` to that URL
7. Re-run with `MOCK=true` to regenerate the archive HTML with the hero image rendered

Step 7 is necessary because the archive HTML is written once at run time. A future improvement could allow re-rendering a single issue from its stored JSON without a full pipeline run.
