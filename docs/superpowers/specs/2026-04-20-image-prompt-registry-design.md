# Image Prompt Registry + Anti-Repetition System — Design Spec

**Date:** 2026-04-20
**Status:** Approved
**Problem:** When two top stories from different days share the same category, the generated prompts
are too similar. The image model produces near-identical visual outputs across weeks because
`CATEGORY_PRESETS` hardcodes one `main_subject`/`environment`/`composition`/`color_system` per
category, and the generator never rotates them.

**Goal:** Extend the existing system with a prompt registry and history-aware component selection
so that same-category images stay stylistically consistent but rotate concept, subject family, and
composition across issues.

**Constraints:**
- Do NOT rewrite the existing subsystem architecture
- Do NOT add heavy dependencies (no vector DBs, no embeddings)
- Keep `build_image_prompt()` signature unchanged
- All existing tests must continue to pass

---

## File Map

| File | Change |
|------|--------|
| `config/image_prompt_registry.yaml` | **New** — reusable building blocks |
| `lib/image_registry.py` | **New** — registry loader + `select_prompt_components()` |
| `lib/image_history_store.py` | **Modify** — add `subject_family` + `composition_preset` columns |
| `lib/image_prompt_builder.py` | **Modify** — registry-aware novelty; no signature changes |
| `lib/image_generator.py` | **Modify** — use registry selection; smarter retry rotation |
| `scripts/generate_editorial_image.py` | **Modify** — 3 new flags + extended dry-run |
| `README-image-generation.md` | **Update** — registry + accepted_prompt sections |

Files with **no changes**: `lib/image_similarity.py`, `lib/tests/*`, `generation_attempts` table.

---

## A. `config/image_prompt_registry.yaml`

Stores building blocks only — never full final prompts.

**Top-level keys:**

```
style_master:          string (reference only — not injected at runtime)
categories:            map[name -> CategoryEntry]
concept_templates:     map[name -> string]
subject_family_templates: map[name -> string]
composition_templates: map[name -> string]
novelty_templates:
  mild:   string
  medium: string
  strong: string
```

**CategoryEntry structure:**

```yaml
energy:
  default_color_system: "warm amber-rust tones on metal surfaces, cool gray background"
  allowed_concepts:
    - industrial_cluster
    - pipeline_infrastructure
    - offshore_platform
    - storage_facility
  allowed_subject_families:
    - refinery
    - pipeline
    - offshore_rig
    - storage_tanks
  allowed_compositions:
    - left_weighted
    - right_weighted
    - elevated_wide
    - close_foreground
```

Categories covered: `energy`, `shipping_geopolitics`, `trade_supply_chain`, `macro_inflation`,
`policy_institutional`, `markets_finance`.

Each category has 4–5 entries in each `allowed_*` list, giving 64–125 unique combinations per
category before repetition becomes necessary.

---

## B. `lib/image_registry.py` (new file)

### `load_registry(registry_path=None) -> dict`

- Default path: `config/image_prompt_registry.yaml` relative to repo root
- Caches parsed YAML in a module-level variable after first load
- Falls back to `{}` if PyYAML unavailable or file missing (non-fatal)
- `registry_path` override for tests

### `select_prompt_components(category, recent_history, concept_tag=None, subject_family=None, composition_preset=None, excluded_combos=None, force_novelty_level=None, registry_path=None) -> dict`

**Inputs:**
- `category` — string
- `recent_history` — list of dicts from `get_recent_by_category()` (last 8 used)
- `concept_tag`, `subject_family`, `composition_preset` — explicit overrides (respected as-is)
- `excluded_combos` — list of `(concept_tag, subject_family, composition_preset)` tuples to exclude from selection (used by the retry loop to prevent re-selecting a just-rejected combination)
- `force_novelty_level` — 0–3; passed through to novelty generation
- `registry_path` — override for tests

**Selection logic:**

1. Load registry; get `allowed_concepts`, `allowed_subject_families`, `allowed_compositions` for `category`
2. Extract `(concept_tag, subject_family, composition_preset)` tuples from the last 8 same-category records (filter out nulls)
3. For each candidate tuple in the cross-product of allowed pools:
   - Score = number of times this exact triple appears in recent 8 (lower = better)
   - Tiebreak: prefer tuples where at least 2 dimensions differ from the most recent image's triple
4. Select the lowest-scoring candidate; if tie, pick randomly among tied candidates
5. Honour explicit overrides: if caller passes `concept_tag=X`, keep X and rotate only the other two
6. Fall back to random selection if registry has no data for the category

**Returns dict:**

```python
{
    "concept_tag":         str,
    "subject_family":      str,
    "composition_preset":  str,
    "main_subject":        str,   # from subject_family_templates[subject_family]
    "composition":         str,   # from composition_templates[composition_preset]
    "color_system":        str,   # from category.default_color_system
    "novelty_request":     str | None,  # auto-generated if history warrants it
}
```

**Auto-novelty generation (within `select_prompt_components`):**

If the last 8 same-category records show any dimension appearing 3+ times:
- Build a novelty string naming the overused subjects/compositions to avoid
- Example: *"Avoid resemblance to the last 6 shipping_geopolitics images; do not use tanker as
  the dominant subject. Avoid elevated_wide composition."*

This novelty string is returned in the dict and appended by the generator. Manual `novelty_request`
from the caller always takes precedence over auto-generated novelty.

---

## C. Schema migration in `lib/image_history_store.py`

### New columns in `image_history`

| Column | Type | Notes |
|--------|------|-------|
| `subject_family` | TEXT | e.g. `tanker`, `refinery`, `skyline` |
| `composition_preset` | `TEXT` | e.g. `left_weighted`, `elevated_wide` |

**Migration strategy:** Idempotent `ALTER TABLE ADD COLUMN` calls inside `init_db()`, wrapped in
`try/except OperationalError` (SQLite raises this if the column already exists). Existing rows
receive `NULL` for the new columns — no backfill required.

### API changes

- `save_record()` — accepts `subject_family` and `composition_preset` in the record dict
- `update_record()` — adds `subject_family` and `composition_preset` to the `_allowed` set
- `get_recent_by_category()` — no change (already `SELECT *`)

---

## D. `lib/image_prompt_builder.py` changes

### `suggest_novelty_request()` — extended signature

```python
def suggest_novelty_request(
    category: str,
    recent_history: List[Dict],
    escalation_level: int = 1,
    concept_tag_freq: Optional[Dict[str, int]] = None,
    subject_family_freq: Optional[Dict[str, int]] = None,
    composition_freq: Optional[Dict[str, int]] = None,
) -> str:
```

The three new optional frequency dicts feed into the avoidance clauses:
- If `subject_family_freq` has any value ≥ 3: add *"do not use [subject] as dominant subject"*
- If `composition_freq` has any value ≥ 3: add *"avoid [composition] layout"*

At level 3, the novelty string also mentions the most recently used subject family and composition
explicitly to prevent repetition.

**`build_image_prompt()` signature is unchanged.**

---

## E. `lib/image_generator.py` changes

### New parameters on `generate_editorial_image()`

```python
subject_family: Optional[str] = None,
composition_preset: Optional[str] = None,
```

### Updated generation loop

```
Attempt 0:
  1. Call select_prompt_components(category, recent_category,
       concept_tag=caller_override, subject_family=caller_override,
       composition_preset=caller_override, excluded_combos=[])
     → get resolved main_subject, composition, color_system, auto_novelty
  2. Record selected triple as used_combo_0
  3. Use manual novelty_request if provided, else auto_novelty from registry
  4. Build prompt, generate, check similarity
  5. If accepted: save with subject_family + composition_preset

Retry 1 (composition rotation):
  6. Re-call select_prompt_components(..., excluded_combos=[used_combo_0])
     → selector avoids previous triple; prefers different composition_preset
  7. Escalate to novelty level 1

Retry 2 (subject_family rotation):
  8. Re-call select_prompt_components(..., excluded_combos=[used_combo_0, used_combo_1])
     → selector avoids both previous triples; prefers different subject_family
  9. Escalate to novelty level 2

Retry 3 (full rotation):
  10. Re-call select_prompt_components(..., excluded_combos=[used_combo_0..2])
      → selector avoids all previous triples; changes concept_tag if needed
  11. Escalate to novelty level 3
```

`excluded_combos` grows with each retry, so the selector never re-picks a combination already
tried in this run.

---

## F. `scripts/generate_editorial_image.py` changes

### New flags

| Flag | Description |
|------|-------------|
| `--subject-family` | Override registry-selected subject family (e.g. `tanker`) |
| `--composition-preset` | Override registry-selected composition preset (e.g. `elevated_wide`) |
| `--list-registry-options [CATEGORY]` | Print registry allowed values per category and exit |

### Extended dry-run output

```
-- Dry-run breakdown --------------------------------------------------

Category:                    shipping_geopolitics
Concept tag:                 maritime_passage    [registry-selected]
Subject family:              tanker              [registry-selected]
Composition preset:          split_frame         [registry-selected]
Color system:                muted blue-gray with deep green undertones
Novelty directive:           [auto] Avoid resemblance to last 4 ...
Same-category combos compared: 6
Excluded combos:             0

Full prompt (1243 chars):
...
```

---

## G. `README-image-generation.md` additions

Two new sections appended after the existing content:

### How the registry prevents repeated category images

Explains: registry stores building blocks → `select_prompt_components()` scores candidate
combinations by recency → lowest-penalty combo is chosen → retries rotate dimensions in order
(composition → subject_family → concept_tag).

### How `accepted_prompt`, `concept_tag`, `subject_family`, and `composition_preset` work together

Explains: `accepted_prompt` = revised_prompt when available (captures model rewrites for accurate
similarity comparison); the three semantic fields enable structured anti-repetition across the
combination space rather than relying on text similarity alone.

---

## Dependencies

`pyyaml` is added to `requirements.txt`. All other dependencies (`imagehash`, `scikit-learn`,
`Pillow`) are already present.

---

## What does NOT change

- `lib/image_similarity.py` — no changes
- `lib/tests/` — existing tests unmodified; new tests can be added separately
- `generation_attempts` table — no changes
- `STYLE_MASTER`, `CATEGORY_BLOCKS`, `COMPOSITION_PRESETS` (letter codes), `COLOR_PRESETS` — all preserved
- `build_image_prompt()` call signature — unchanged
- Variation code system (A-E / 1-4 / i-iv / alpha-epsilon) — unchanged
