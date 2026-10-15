# Image Prompt Registry + Anti-Repetition System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the image generation pipeline with a YAML registry of per-category building blocks and history-aware component selection so that same-category images rotate subject, composition, and concept across issues instead of always using the same hardcoded preset.

**Architecture:** A new `lib/image_registry.py` module loads `config/image_prompt_registry.yaml` and exposes `select_prompt_components()`, which scores every candidate `(concept_tag, subject_family, composition_preset)` triple against the last 8 same-category records and picks the lowest-penalty combo. The generator calls this at every attempt (with a growing `excluded_combos` list) and saves the selected fields to two new DB columns. `suggest_novelty_request()` is extended with subject-family and composition frequency arguments to produce richer avoidance clauses.

**Tech Stack:** Python 3.11, SQLite (existing), PyYAML (new), pytest (existing), `itertools.product` for combo enumeration.

**Spec:** `docs/superpowers/specs/2026-04-20-image-prompt-registry-design.md`

---

## File Map

| File | Action |
|------|--------|
| `requirements.txt` | Add `pyyaml` |
| `config/image_prompt_registry.yaml` | **Create** — building blocks for all 6 categories |
| `lib/image_registry.py` | **Create** — `load_registry()` + `select_prompt_components()` |
| `lib/tests/test_image_registry.py` | **Create** — tests for both registry functions |
| `lib/image_history_store.py` | **Modify** — add `subject_family` + `composition_preset` columns |
| `lib/image_prompt_builder.py` | **Modify** — extend `suggest_novelty_request()` signature |
| `lib/image_generator.py` | **Modify** — registry-aware selection + retry rotation |
| `scripts/generate_editorial_image.py` | **Modify** — 3 new flags + extended dry-run |
| `README-image-generation.md` | **Modify** — two new sections at end |

---

## Task 1: Add pyyaml dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pyyaml to requirements.txt**

Open `requirements.txt`. It currently ends with `scikit-learn`. Add `pyyaml` on a new line:

```
anthropic
openai
requests
beautifulsoup4
lxml
wordcloud
Pillow
python-dotenv
imagehash
scikit-learn
pyyaml
```

- [ ] **Step 2: Install and verify**

```bash
pip install pyyaml
python -c "import yaml; print('pyyaml ok')"
```

Expected: `pyyaml ok`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pyyaml dependency for image prompt registry"
```

---

## Task 2: Create config/image_prompt_registry.yaml

**Files:**
- Create: `config/image_prompt_registry.yaml`

- [ ] **Step 1: Create the config directory if it doesn't exist**

```bash
mkdir -p config
```

- [ ] **Step 2: Write the registry file**

Create `config/image_prompt_registry.yaml` with the full content below:

```yaml
# config/image_prompt_registry.yaml
# ─────────────────────────────────────────────────────────────────────────────
# Image prompt building blocks for the editorial image generation system.
# Stores reusable components only — never full assembled prompts.
# ─────────────────────────────────────────────────────────────────────────────

style_master: "stable-reference-v1"  # reference only — not injected at runtime

categories:

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

  shipping_geopolitics:
    default_color_system: "steel blue accents on container markings, muted rust on crane structures"
    allowed_concepts:
      - container_logistics
      - maritime_passage
      - port_infrastructure
      - maritime_chokepoint
    allowed_subject_families:
      - container_port
      - cargo_vessel
      - tanker
      - harbor_cranes
    allowed_compositions:
      - converging_perspective
      - split_frame
      - elevated_wide
      - left_weighted

  trade_supply_chain:
    default_color_system: "muted ochre on road markings, cool gray on barrier and infrastructure"
    allowed_concepts:
      - restriction_barrier
      - logistics_hub
      - transit_corridor
    allowed_subject_families:
      - customs_gate
      - warehouse_depot
      - highway_corridor
      - cargo_depot
    allowed_compositions:
      - central_vanishing
      - right_weighted
      - close_foreground
      - elevated_wide

  macro_inflation:
    default_color_system: "warm stone tones on architecture, cool gray sky and deep shadows"
    allowed_concepts:
      - institutional_facade
      - trading_floor_empty
      - market_data_display
    allowed_subject_families:
      - central_bank_exterior
      - empty_trading_floor
      - stone_plaza
      - institutional_columns
    allowed_compositions:
      - low_angle_monumental
      - frontal_symmetric
      - elevated_wide
      - close_foreground

  policy_institutional:
    default_color_system: "muted flag accent colors, predominantly graphite and stone gray"
    allowed_concepts:
      - government_building
      - legislative_chamber
      - empty_plaza
      - monumental_steps
    allowed_subject_families:
      - parliament_facade
      - government_exterior
      - government_plaza
      - ceremonial_doors
    allowed_compositions:
      - frontal_symmetric
      - left_weighted
      - low_angle_monumental
      - close_foreground

  markets_finance:
    default_color_system: "cool steel blue on glass surfaces, warm amber on structural elements"
    allowed_concepts:
      - financial_atrium
      - exchange_floor
      - data_terminal
      - capital_flow_map
    allowed_subject_families:
      - glass_tower_atrium
      - trading_floor_interior
      - financial_district_exterior
      - exchange_building_exterior
    allowed_compositions:
      - upward_diagonal
      - split_frame
      - elevated_wide
      - right_weighted

# ── Subject family descriptions (filled into MAIN_SUBJECT in STYLE_MASTER) ───

subject_family_templates:

  refinery: "oil refinery towers and storage tanks with slow industrial exhaust rising"
  pipeline: "industrial pipeline network traversing open terrain, valve stations visible"
  offshore_rig: "offshore drilling platform with functional superstructure against open sea"
  storage_tanks: "cylindrical storage tanks in a flat industrial yard, orderly arrangement"

  container_port: "stacked shipping containers at a deep-water port, crane silhouettes overhead"
  cargo_vessel: "ocean-going cargo vessel navigating open water, visible cargo decks"
  tanker: "large oil tanker navigating a maritime passage, smooth hull and deck infrastructure"
  harbor_cranes: "port gantry cranes over a container terminal, crane arms extended"

  customs_gate: "sealed customs checkpoint gate with barrier arm and inspection booth"
  warehouse_depot: "large warehouse building with loading docks and freight vehicles waiting"
  highway_corridor: "industrial highway extending to a flat horizon, roadway markings visible"
  cargo_depot: "enclosed cargo depot with organized freight stacks and vehicle access lanes"

  central_bank_exterior: "central bank building exterior, stone columns and carved inscriptions"
  empty_trading_floor: "empty trading floor with silent workstations and curved data screens"
  stone_plaza: "empty stone plaza in front of an institutional facade, long shadow geometry"
  institutional_columns: "monumental columns of an institutional building seen in close perspective"

  parliament_facade: "parliament or government building facade, flag poles and ceremonial details"
  government_exterior: "government ministry exterior, formal facade and sealed entrance"
  government_plaza: "empty government plaza with long shadow geometry and subdued ambient light"
  ceremonial_doors: "heavy ceremonial doors of a government building, closed and imposing"

  glass_tower_atrium: "financial district tower atrium viewed from below, glass and steel geometry"
  trading_floor_interior: "trading floor with workstations and ceiling infrastructure, empty or sparse"
  financial_district_exterior: "financial district exterior, towers and stone paving, low-angle view"
  exchange_building_exterior: "stock exchange building exterior, classical or modern facade"

# ── Composition descriptions (filled into COMPOSITION in STYLE_MASTER) ────────

composition_templates:

  left_weighted: "asymmetric left-weighted composition, subject offset to the left third, open space right"
  right_weighted: "asymmetric right-weighted composition, subject offset to the right third, open space left"
  elevated_wide: "wide establishing shot from elevated angle, subject dominant, expansive background"
  close_foreground: "close foreground emphasis, subject large and immediate, background receding"
  converging_perspective: "converging perspective lines leading to a focal point, subject at convergence"
  split_frame: "split-frame composition, foreground element and background element in visual dialogue"
  central_vanishing: "central vanishing point composition, subject slightly off-axis"
  low_angle_monumental: "low camera angle, subject monumental in foreground, sky dominant in background"
  frontal_symmetric: "frontal near-symmetrical framing, slight camera offset breaks symmetry"
  upward_diagonal: "upward diagonal vanishing point, strong perspective, open upper frame"

# ── Concept templates (reference descriptions for infer_concept_tag) ──────────

concept_templates:

  industrial_cluster: "oil refinery towers and industrial chimneys with slow exhaust rising"
  pipeline_infrastructure: "industrial pipeline network traversing open terrain, valves and junctions"
  offshore_platform: "offshore drilling platform rising from open sea, functional superstructure"
  storage_facility: "cylindrical storage tanks in a flat industrial yard, orderly rows"
  container_logistics: "stacked shipping containers at a terminal, crane silhouettes overhead"
  maritime_passage: "cargo vessel or tanker navigating a maritime passage, open water"
  port_infrastructure: "deep-water port infrastructure, dock cranes and quay walls"
  maritime_chokepoint: "strategic waterway with vessel traffic, narrow channel geography"
  restriction_barrier: "customs checkpoint or sealed cargo gate, barrier arm raised"
  logistics_hub: "warehouse complex or depot with loading docks and freight vehicles"
  transit_corridor: "industrial road or rail corridor extending to horizon"
  institutional_facade: "central bank exterior, stone columns and carved inscriptions"
  trading_floor_empty: "empty trading floor with silent terminals and curved workstations"
  market_data_display: "data screens and ticker displays in an institutional financial setting"
  government_building: "government building facade with national flags, ceremonial doors"
  legislative_chamber: "legislative chamber interior, tiered seating and symbolic architecture"
  empty_plaza: "empty stone plaza with long shadow geometry, no figures"
  monumental_steps: "wide monumental steps ascending to an institutional entrance"
  financial_atrium: "financial district tower atrium viewed from below, glass and steel geometry"
  exchange_floor: "stock exchange floor with trading stations, high-ceilinged hall"
  data_terminal: "financial data terminals in an institutional setting, screens and workstations"
  capital_flow_map: "financial district skyline viewed from elevated perspective"

# ── Novelty templates (reference strings for suggest_novelty_request) ─────────

novelty_templates:
  mild: "Apply minor compositional variation. Adjust framing, subject placement, or implied depth — keep the general metaphor."
  medium: "Introduce a different foreground subject and spatial relationship. Avoid repeating visual metaphors from recent images."
  strong: "Strong novelty required. Use a completely different foreground subject, opposite compositional balance, new spatial hierarchy, and a distinct environmental context."
```

- [ ] **Step 3: Verify the YAML parses without error**

```bash
python -c "import yaml; data = yaml.safe_load(open('config/image_prompt_registry.yaml')); print('categories:', list(data['categories'].keys()))"
```

Expected:
```
categories: ['energy', 'shipping_geopolitics', 'trade_supply_chain', 'macro_inflation', 'policy_institutional', 'markets_finance']
```

- [ ] **Step 4: Commit**

```bash
git add config/image_prompt_registry.yaml
git commit -m "feat: add image prompt registry YAML with 6 categories and building blocks"
```

---

## Task 3: Write tests for lib/image_registry.py

**Files:**
- Create: `lib/tests/test_image_registry.py`

- [ ] **Step 1: Write the test file**

Create `lib/tests/test_image_registry.py`:

```python
# lib/tests/test_image_registry.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _YAML_AVAILABLE, reason="pyyaml not installed")


MINIMAL_REGISTRY = {
    "categories": {
        "energy": {
            "default_color_system": "warm amber",
            "allowed_concepts": ["industrial_cluster", "pipeline_infrastructure"],
            "allowed_subject_families": ["refinery", "pipeline"],
            "allowed_compositions": ["left_weighted", "right_weighted"],
        }
    },
    "subject_family_templates": {
        "refinery": "oil refinery towers at dusk",
        "pipeline": "pipeline network traversing open terrain",
    },
    "composition_templates": {
        "left_weighted": "subject offset to left third, open space right",
        "right_weighted": "subject offset to right third, open space left",
    },
    "concept_templates": {
        "industrial_cluster": "oil refinery towers and industrial chimneys",
        "pipeline_infrastructure": "industrial pipeline network",
    },
}


@pytest.fixture
def registry_file(tmp_path):
    import yaml
    path = str(tmp_path / "registry.yaml")
    with open(path, "w") as f:
        yaml.dump(MINIMAL_REGISTRY, f)
    return path


# ── load_registry ─────────────────────────────────────────────────────────────

def test_load_registry_returns_dict(registry_file):
    from lib.image_registry import load_registry
    data = load_registry(registry_file)
    assert isinstance(data, dict)
    assert "categories" in data


def test_load_registry_missing_file_returns_empty_dict():
    from lib.image_registry import load_registry
    data = load_registry("/nonexistent/path/registry.yaml")
    assert data == {}


def test_load_registry_parses_categories(registry_file):
    from lib.image_registry import load_registry
    data = load_registry(registry_file)
    assert "energy" in data["categories"]
    energy = data["categories"]["energy"]
    assert energy["allowed_concepts"] == ["industrial_cluster", "pipeline_infrastructure"]
    assert energy["allowed_subject_families"] == ["refinery", "pipeline"]
    assert energy["allowed_compositions"] == ["left_weighted", "right_weighted"]


# ── select_prompt_components — return shape ──────────────────────────────────

def test_select_returns_required_keys(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("energy", [], registry_path=registry_file)
    for key in (
        "concept_tag", "subject_family", "composition_preset",
        "main_subject", "composition", "color_system", "novelty_request",
    ):
        assert key in result, f"Missing key: {key}"


def test_select_picks_from_allowed_pools(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("energy", [], registry_path=registry_file)
    assert result["concept_tag"] in ["industrial_cluster", "pipeline_infrastructure"]
    assert result["subject_family"] in ["refinery", "pipeline"]
    assert result["composition_preset"] in ["left_weighted", "right_weighted"]


def test_select_resolves_subject_family_template(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components(
        "energy", [],
        subject_family="refinery",
        registry_path=registry_file,
    )
    assert result["main_subject"] == "oil refinery towers at dusk"


def test_select_resolves_composition_template(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components(
        "energy", [],
        composition_preset="left_weighted",
        registry_path=registry_file,
    )
    assert result["composition"] == "subject offset to left third, open space right"


def test_select_returns_color_system(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("energy", [], registry_path=registry_file)
    assert result["color_system"] == "warm amber"


# ── select_prompt_components — explicit overrides ────────────────────────────

def test_concept_tag_override_respected(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components(
        "energy", [],
        concept_tag="pipeline_infrastructure",
        registry_path=registry_file,
    )
    assert result["concept_tag"] == "pipeline_infrastructure"


def test_subject_family_override_respected(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components(
        "energy", [],
        subject_family="pipeline",
        registry_path=registry_file,
    )
    assert result["subject_family"] == "pipeline"


def test_composition_preset_override_respected(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components(
        "energy", [],
        composition_preset="right_weighted",
        registry_path=registry_file,
    )
    assert result["composition_preset"] == "right_weighted"


# ── select_prompt_components — excluded_combos ───────────────────────────────

def test_excluded_combos_avoided(registry_file):
    from lib.image_registry import select_prompt_components
    from itertools import product
    # All combos: 2 concepts x 2 subjects x 2 comps = 8
    all_combos = list(product(
        ["industrial_cluster", "pipeline_infrastructure"],
        ["refinery", "pipeline"],
        ["left_weighted", "right_weighted"],
    ))
    # Exclude all but one
    target = ("pipeline_infrastructure", "refinery", "right_weighted")
    excluded = [c for c in all_combos if c != target]
    result = select_prompt_components(
        "energy", [],
        excluded_combos=excluded,
        registry_path=registry_file,
    )
    assert (result["concept_tag"], result["subject_family"], result["composition_preset"]) == target


def test_excluded_combos_relaxed_when_all_excluded(registry_file):
    from lib.image_registry import select_prompt_components
    from itertools import product
    # Exclude all possible combos — function should not raise
    all_combos = list(product(
        ["industrial_cluster", "pipeline_infrastructure"],
        ["refinery", "pipeline"],
        ["left_weighted", "right_weighted"],
    ))
    result = select_prompt_components(
        "energy", [],
        excluded_combos=all_combos,
        registry_path=registry_file,
    )
    # Should return something valid despite all excluded
    assert result["concept_tag"] in ["industrial_cluster", "pipeline_infrastructure"]


# ── select_prompt_components — anti-repetition scoring ───────────────────────

def test_scoring_avoids_most_recent_combo(registry_file):
    from lib.image_registry import select_prompt_components
    # If one combo appeared 5 times in recent history, avoid it
    overused_triple = {
        "concept_tag": "industrial_cluster",
        "subject_family": "refinery",
        "composition_preset": "left_weighted",
    }
    recent_history = [overused_triple.copy() for _ in range(5)]
    # Run 30 trials; overused combo should be selected rarely
    results = [
        select_prompt_components("energy", recent_history, registry_path=registry_file)
        for _ in range(30)
    ]
    overused_count = sum(
        1 for r in results
        if r["concept_tag"] == "industrial_cluster"
        and r["subject_family"] == "refinery"
        and r["composition_preset"] == "left_weighted"
    )
    # With 8 alternatives equally scored at 0, the overused combo (score=5) should rarely appear
    assert overused_count < 5


def test_no_history_returns_valid_result(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("energy", [], registry_path=registry_file)
    assert result["concept_tag"]
    assert result["subject_family"]
    assert result["composition_preset"]


# ── select_prompt_components — auto-novelty ──────────────────────────────────

def test_auto_novelty_generated_when_subject_family_overused(registry_file):
    from lib.image_registry import select_prompt_components
    # 3+ appearances of same subject_family in last 8 triggers auto novelty
    recent_history = [
        {"concept_tag": "industrial_cluster", "subject_family": "refinery", "composition_preset": "left_weighted"},
        {"concept_tag": "industrial_cluster", "subject_family": "refinery", "composition_preset": "right_weighted"},
        {"concept_tag": "pipeline_infrastructure", "subject_family": "refinery", "composition_preset": "left_weighted"},
    ]
    # Force selection of a non-refinery subject to guarantee overuse is detectable
    result = select_prompt_components(
        "energy", recent_history,
        subject_family="pipeline",  # force non-refinery selection
        registry_path=registry_file,
    )
    # novelty_request should mention avoiding "refinery"
    assert result["novelty_request"] is not None
    assert "refinery" in result["novelty_request"]


def test_no_auto_novelty_when_history_empty(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("energy", [], registry_path=registry_file)
    assert result["novelty_request"] is None


def test_no_auto_novelty_when_no_overuse(registry_file):
    from lib.image_registry import select_prompt_components
    # Only 2 appearances of same combo — below threshold of 3
    recent_history = [
        {"concept_tag": "industrial_cluster", "subject_family": "refinery", "composition_preset": "left_weighted"},
        {"concept_tag": "industrial_cluster", "subject_family": "refinery", "composition_preset": "left_weighted"},
    ]
    result = select_prompt_components("energy", recent_history, registry_path=registry_file)
    assert result["novelty_request"] is None


# ── select_prompt_components — unknown category fallback ─────────────────────

def test_unknown_category_returns_valid_result(registry_file):
    from lib.image_registry import select_prompt_components
    result = select_prompt_components("unknown_category", [], registry_path=registry_file)
    # Should not raise; must return the required keys
    for key in ("concept_tag", "subject_family", "composition_preset", "main_subject",
                 "composition", "color_system", "novelty_request"):
        assert key in result


def test_empty_registry_returns_valid_result():
    from lib.image_registry import select_prompt_components
    import tempfile, os
    import yaml
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({}, f)
        path = f.name
    try:
        result = select_prompt_components("energy", [], registry_path=path)
        for key in ("concept_tag", "subject_family", "composition_preset", "main_subject",
                     "composition", "color_system", "novelty_request"):
            assert key in result
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests and confirm they fail (module doesn't exist yet)**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_registry.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` for `lib.image_registry` — confirms tests are wired correctly before implementation.

- [ ] **Step 3: Commit the test file**

```bash
git add lib/tests/test_image_registry.py
git commit -m "test: add failing tests for image_registry module"
```

---

## Task 4: Implement lib/image_registry.py

**Files:**
- Create: `lib/image_registry.py`

- [ ] **Step 1: Write the implementation**

Create `lib/image_registry.py`:

```python
# lib/image_registry.py
# ─────────────────────────────────────────────
#  Registry loader and history-aware component selector.
#
#  Functions:
#    load_registry(registry_path=None) -> dict
#    select_prompt_components(...) -> dict
# ─────────────────────────────────────────────

import os
import random
from collections import Counter
from itertools import product
from typing import Dict, List, Optional, Tuple

_REGISTRY_CACHE: Optional[dict] = None
_DEFAULT_REGISTRY = os.path.join(
    os.path.dirname(__file__), "..", "config", "image_prompt_registry.yaml"
)


def load_registry(registry_path: Optional[str] = None) -> dict:
    """
    Load and cache the image prompt registry YAML.
    Falls back to {} if PyYAML is unavailable or the file is missing.
    registry_path overrides the default path (used in tests).
    """
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None and registry_path is None:
        return _REGISTRY_CACHE

    path = registry_path or _DEFAULT_REGISTRY
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        data = {}

    if registry_path is None:
        _REGISTRY_CACHE = data
    return data


def _score_combo(
    combo: Tuple[str, str, str],
    recent_triples: List[Tuple[str, str, str]],
    most_recent_triple: Optional[Tuple[str, str, str]],
) -> Tuple[int, int]:
    """
    Score a (concept_tag, subject_family, composition_preset) triple.
    Lower score = better candidate.
    Primary score: how many times this exact triple appears in recent_triples.
    Tiebreak: 0 if 2+ dimensions differ from most_recent_triple, else 1.
    """
    recency_count = sum(1 for t in recent_triples if t == combo)
    if most_recent_triple is None:
        tiebreak = 0
    else:
        dims_same = sum(1 for a, b in zip(combo, most_recent_triple) if a == b)
        tiebreak = 0 if dims_same <= 1 else 1
    return (recency_count, tiebreak)


def _build_auto_novelty(
    category: str,
    recent_triples: List[Tuple[str, str, str]],
) -> Optional[str]:
    """
    Build an auto-novelty directive if any subject_family or composition_preset
    appears 3+ times in recent_triples. Returns None if no overuse detected.
    """
    if not recent_triples:
        return None

    sf_freq = Counter(t[1] for t in recent_triples)
    cp_freq = Counter(t[2] for t in recent_triples)
    overused_sf = [sf for sf, cnt in sf_freq.items() if cnt >= 3]
    overused_cp = [cp for cp, cnt in cp_freq.items() if cnt >= 3]

    if not overused_sf and not overused_cp:
        return None

    label = category.replace("_", " ")
    n = len(recent_triples)
    parts = [f"Avoid resemblance to the last {n} {label} images"]
    if overused_sf:
        sf_list = " or ".join(f'"{s.replace("_", " ")}"' for s in overused_sf[:2])
        parts.append(f"do not use {sf_list} as the dominant subject")
    if overused_cp:
        cp_list = " or ".join(f'"{c.replace("_", " ")}"' for c in overused_cp[:2])
        parts.append(f"avoid {cp_list} composition")
    return "; ".join(parts) + "."


def select_prompt_components(
    category: str,
    recent_history: List[Dict],
    concept_tag: Optional[str] = None,
    subject_family: Optional[str] = None,
    composition_preset: Optional[str] = None,
    excluded_combos: Optional[List[Tuple[str, str, str]]] = None,
    force_novelty_level: Optional[int] = None,
    registry_path: Optional[str] = None,
) -> dict:
    """
    Select (concept_tag, subject_family, composition_preset) for the given category
    by scoring candidates against the last 8 same-category history records.

    Explicit overrides (concept_tag, subject_family, composition_preset) are
    respected as-is; only the other two dimensions are rotated.

    excluded_combos: triples already tried in this retry run — excluded from selection.

    Returns dict with keys:
        concept_tag, subject_family, composition_preset,
        main_subject, composition, color_system, novelty_request
    """
    registry = load_registry(registry_path)
    excluded = set(map(tuple, excluded_combos or []))

    cat_data = (registry.get("categories") or {}).get(category, {})
    allowed_concepts = cat_data.get("allowed_concepts") or []
    allowed_subjects = cat_data.get("allowed_subject_families") or []
    allowed_comps = cat_data.get("allowed_compositions") or []
    color_system = cat_data.get("default_color_system", "")

    subject_templates = registry.get("subject_family_templates") or {}
    composition_templates = registry.get("composition_templates") or {}

    # Extract recent triples (last 8) — skip rows missing any field
    recent_8 = recent_history[:8]
    recent_triples: List[Tuple[str, str, str]] = []
    for r in recent_8:
        ct = r.get("concept_tag")
        sf = r.get("subject_family")
        cp = r.get("composition_preset")
        if ct and sf and cp:
            recent_triples.append((ct, sf, cp))

    most_recent_triple = recent_triples[0] if recent_triples else None

    # Fall back to simple random selection if registry has no data for this category
    if not (allowed_concepts and allowed_subjects and allowed_comps):
        ct = concept_tag or f"{category}_general"
        sf = subject_family or category
        cp = composition_preset or "left_weighted"
        main_subject = subject_templates.get(sf, sf.replace("_", " "))
        composition = composition_templates.get(cp, cp.replace("_", " "))
        return {
            "concept_tag": ct,
            "subject_family": sf,
            "composition_preset": cp,
            "main_subject": main_subject,
            "composition": composition,
            "color_system": color_system,
            "novelty_request": None,
        }

    # Build candidate pool (respect explicit overrides)
    concept_pool = [concept_tag] if concept_tag else allowed_concepts
    subject_pool = [subject_family] if subject_family else allowed_subjects
    comp_pool = [composition_preset] if composition_preset else allowed_comps

    candidates = [
        (ct, sf, cp)
        for ct, sf, cp in product(concept_pool, subject_pool, comp_pool)
        if (ct, sf, cp) not in excluded
    ]

    # Relax exclusion if all combos are excluded
    if not candidates:
        candidates = list(product(concept_pool, subject_pool, comp_pool))

    # Score and select
    scored = [
        (combo, _score_combo(combo, recent_triples, most_recent_triple))
        for combo in candidates
    ]
    scored.sort(key=lambda x: x[1])
    best_score = scored[0][1]
    tied = [combo for combo, score in scored if score == best_score]
    chosen_ct, chosen_sf, chosen_cp = random.choice(tied)

    main_subject = subject_templates.get(chosen_sf, chosen_sf.replace("_", " "))
    composition = composition_templates.get(chosen_cp, chosen_cp.replace("_", " "))

    # Auto-novelty: detect overused dimensions (only when no forced escalation)
    novelty_request = None
    if force_novelty_level is None:
        novelty_request = _build_auto_novelty(category, recent_triples)

    return {
        "concept_tag": chosen_ct,
        "subject_family": chosen_sf,
        "composition_preset": chosen_cp,
        "main_subject": main_subject,
        "composition": composition,
        "color_system": color_system,
        "novelty_request": novelty_request,
    }
```

- [ ] **Step 2: Run tests**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_registry.py -v
```

Expected: all tests pass. If any fail, fix before continuing.

- [ ] **Step 3: Run all existing tests to confirm no regressions**

```bash
python -m pytest lib/tests/ -v
```

Expected: all tests pass (new + existing).

- [ ] **Step 4: Commit**

```bash
git add lib/image_registry.py lib/tests/test_image_registry.py
git commit -m "feat: add image_registry module with load_registry and select_prompt_components"
```

---

## Task 5: Migrate lib/image_history_store.py

Add `subject_family` and `composition_preset` columns to `image_history` via idempotent `ALTER TABLE`.

**Files:**
- Modify: `lib/image_history_store.py:31-71` (init_db)
- Modify: `lib/image_history_store.py:74-114` (save_record)
- Modify: `lib/image_history_store.py:117-141` (update_record)

- [ ] **Step 1: Run existing store tests to establish baseline**

```bash
python -m pytest lib/tests/test_image_history_store.py -v
```

Expected: all 12 tests pass.

- [ ] **Step 2: Add migration to `init_db()`**

In `lib/image_history_store.py`, find `init_db()`. After the `conn.commit()` at line 71, add the migration block:

Replace:
```python
        conn.commit()
```

With:
```python
        conn.commit()
        # Idempotent column migrations
        for col, coltype in [
            ("subject_family", "TEXT"),
            ("composition_preset", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE image_history ADD COLUMN {col} {coltype}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
```

- [ ] **Step 3: Update `save_record()` to include new columns**

Replace the INSERT statement in `save_record()` (lines 83-114):

```python
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO image_history (
                created_at, issue_date, story_slug, category,
                prompt_master_version, prompt_sent, revised_prompt,
                accepted_prompt, variation_code, novelty_request, concept_tag,
                subject_family, composition_preset,
                image_path, image_phash, similarity_score_text,
                similarity_score_image, regeneration_count, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.get("created_at", now),
                record["issue_date"],
                record["story_slug"],
                record["category"],
                record.get("prompt_master_version"),
                record["prompt_sent"],
                record.get("revised_prompt"),
                record.get("accepted_prompt"),
                record.get("variation_code"),
                record.get("novelty_request"),
                record.get("concept_tag"),
                record.get("subject_family"),
                record.get("composition_preset"),
                record.get("image_path"),
                record.get("image_phash"),
                record.get("similarity_score_text"),
                record.get("similarity_score_image"),
                record.get("regeneration_count", 0),
                record.get("notes"),
            ),
        )
        conn.commit()
        return cursor.lastrowid
```

- [ ] **Step 4: Add new fields to `update_record()` `_allowed` set**

In `update_record()`, replace:
```python
    _allowed = {
        "image_path", "image_phash", "similarity_score_text",
        "similarity_score_image", "regeneration_count",
        "revised_prompt", "accepted_prompt", "concept_tag", "notes",
    }
```

With:
```python
    _allowed = {
        "image_path", "image_phash", "similarity_score_text",
        "similarity_score_image", "regeneration_count",
        "revised_prompt", "accepted_prompt", "concept_tag",
        "subject_family", "composition_preset", "notes",
    }
```

- [ ] **Step 5: Write new tests for the migration and new fields**

Add these tests to `lib/tests/test_image_history_store.py`:

```python
def test_init_db_adds_subject_family_column(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(image_history)").fetchall()]
    assert "subject_family" in cols


def test_init_db_adds_composition_preset_column(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(image_history)").fetchall()]
    assert "composition_preset" in cols


def test_init_db_migration_is_idempotent(tmp_db):
    # Call init_db a second time — should not raise even though columns exist
    init_db(tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(image_history)").fetchall()]
    assert "subject_family" in cols
    assert "composition_preset" in cols


def test_save_record_stores_subject_family_and_composition_preset(tmp_db):
    rid = save_record({
        "issue_date": "2026-04-15",
        "story_slug": "test-story",
        "category": "energy",
        "prompt_sent": "Test prompt",
        "subject_family": "refinery",
        "composition_preset": "left_weighted",
    }, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image_history WHERE id = ?", (rid,)).fetchone())
    assert row["subject_family"] == "refinery"
    assert row["composition_preset"] == "left_weighted"


def test_update_record_can_set_subject_family(tmp_db):
    rid = save_record({
        "issue_date": "2026-04-15",
        "story_slug": "s",
        "category": "energy",
        "prompt_sent": "p",
    }, db_path=tmp_db)
    update_record(rid, {"subject_family": "pipeline", "composition_preset": "right_weighted"}, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image_history WHERE id = ?", (rid,)).fetchone())
    assert row["subject_family"] == "pipeline"
    assert row["composition_preset"] == "right_weighted"
```

- [ ] **Step 6: Run all tests**

```bash
python -m pytest lib/tests/test_image_history_store.py -v
```

Expected: all tests pass (original 12 + new 5).

- [ ] **Step 7: Commit**

```bash
git add lib/image_history_store.py lib/tests/test_image_history_store.py
git commit -m "feat: add subject_family and composition_preset columns to image_history"
```

---

## Task 6: Extend suggest_novelty_request() in lib/image_prompt_builder.py

**Files:**
- Modify: `lib/image_prompt_builder.py:256-310`

- [ ] **Step 1: Run existing prompt builder tests to establish baseline**

```bash
python -m pytest lib/tests/test_image_prompt_builder.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Write new tests for the extended signature**

Add these to `lib/tests/test_image_prompt_builder.py`:

```python
def test_suggest_novelty_subject_family_freq_avoids_overused():
    from lib.image_prompt_builder import suggest_novelty_request
    result = suggest_novelty_request(
        "energy", [],
        escalation_level=2,
        subject_family_freq={"refinery": 4, "pipeline": 1},
    )
    assert "refinery" in result


def test_suggest_novelty_composition_freq_avoids_overused():
    from lib.image_prompt_builder import suggest_novelty_request
    result = suggest_novelty_request(
        "energy", [],
        escalation_level=2,
        composition_freq={"left_weighted": 3, "right_weighted": 1},
    )
    assert "left weighted" in result or "left_weighted" in result


def test_suggest_novelty_level3_mentions_most_recent_subject():
    from lib.image_prompt_builder import suggest_novelty_request
    recent = [
        {"subject_family": "refinery", "composition_preset": "left_weighted"},
        {"subject_family": "pipeline", "composition_preset": "right_weighted"},
    ]
    result = suggest_novelty_request(
        "energy", recent,
        escalation_level=3,
        subject_family_freq={"refinery": 3},
        composition_freq={"left_weighted": 3},
    )
    # Level 3 + overuse should produce a rich avoidance string
    assert "refinery" in result or "left" in result


def test_suggest_novelty_new_params_are_optional():
    from lib.image_prompt_builder import suggest_novelty_request
    # Old call signature should still work unchanged
    result = suggest_novelty_request("energy", [], escalation_level=1)
    assert isinstance(result, str) and len(result) > 0
```

- [ ] **Step 3: Run new tests to confirm they fail**

```bash
python -m pytest lib/tests/test_image_prompt_builder.py -k "subject_family_freq or composition_freq or new_params" -v
```

Expected: the `subject_family_freq` and `composition_freq` tests will PASS vacuously since `**kwargs` swallows unknown params in Python — but the assertion on content will FAIL for the avoidance tests. Confirm failure.

- [ ] **Step 4: Update `suggest_novelty_request()` signature and body**

In `lib/image_prompt_builder.py`, replace the `suggest_novelty_request` function (lines 256-310) with:

```python
def suggest_novelty_request(
    category: str,
    recent_history: List[Dict],
    escalation_level: int = 1,
    concept_tag_freq: Optional[Dict[str, int]] = None,
    subject_family_freq: Optional[Dict[str, int]] = None,
    composition_freq: Optional[Dict[str, int]] = None,
) -> str:
    """
    Generate a novelty request. Escalation levels 0-3:

    0 = minor composition tweaks (auto-applied on first generation if no manual novelty set)
    1 = composition + hierarchy change (first retry)
    2 = subject arrangement + metaphor shift; concept/subject/composition-aware (second retry)
    3 = full conceptual shift — new metaphor, new structure, new environment (third retry)

    Frequency dicts (concept_tag_freq, subject_family_freq, composition_freq) add avoidance
    clauses for any value appearing 3+ times.
    """
    n = len(recent_history)
    label = category.replace("_", " ")

    # Build concept avoidance clause (overused concept tags, threshold: 3+)
    concept_clause = ""
    if concept_tag_freq:
        overused = [tag for tag, count in concept_tag_freq.items() if count >= 3]
        if overused:
            tag_list = " or ".join(f'"{t.replace("_", " ")}"' for t in overused[:3])
            concept_clause = f" Explicitly avoid repeating visual metaphors such as {tag_list}."

    # Build subject avoidance clause (overused subject families, threshold: 3+)
    subject_clause = ""
    if subject_family_freq:
        overused_sf = [sf for sf, count in subject_family_freq.items() if count >= 3]
        if overused_sf:
            sf_list = " or ".join(f'"{s.replace("_", " ")}"' for s in overused_sf[:2])
            subject_clause = f" Do not use {sf_list} as the dominant subject."

    # Build composition avoidance clause (overused compositions, threshold: 3+)
    comp_clause = ""
    if composition_freq:
        overused_cp = [cp for cp, count in composition_freq.items() if count >= 3]
        if overused_cp:
            cp_list = " or ".join(f'"{c.replace("_", " ")}"' for c in overused_cp[:2])
            comp_clause = f" Avoid {cp_list} layout."

    # At level 3, also mention the most recently used subject_family and composition_preset
    most_recent_clause = ""
    if escalation_level >= 3 and recent_history:
        latest = recent_history[0]
        latest_sf = latest.get("subject_family")
        latest_cp = latest.get("composition_preset")
        parts = []
        if latest_sf:
            parts.append(f'"{latest_sf.replace("_", " ")}" as main subject')
        if latest_cp:
            parts.append(f'"{latest_cp.replace("_", " ")}" composition')
        if parts:
            most_recent_clause = f" Most recent image used {' and '.join(parts)} — use neither."

    if escalation_level == 0:
        return (
            f"Apply minor compositional variation relative to recent {label} images. "
            "Adjust framing, subject placement, or implied depth — keep the general metaphor."
        )
    if escalation_level == 1:
        return (
            f"Avoid repeating visual metaphors from the last {min(n, 4)} {label} images. "
            "Introduce a different foreground subject and spatial relationship."
            + concept_clause + subject_clause + comp_clause
        )
    if escalation_level == 2:
        return (
            f"Avoid resemblance to the last {min(n, 6)} {label} images. "
            "Change foreground object count, composition balance, and dominant visual metaphor. "
            "Use a different environmental setting and implied time of day."
            + concept_clause + subject_clause + comp_clause
        )
    # Level 3+
    return (
        f"Strong novelty required: avoid any resemblance to the last {min(n, 8)} {label} images "
        "and the 4 most recent global images across all categories. "
        "Use a completely different foreground subject, opposite compositional balance, "
        "new spatial hierarchy, and a distinct environmental context. "
        "If recent images used exterior settings, use interior. "
        "If recent images used horizontal framing, use strong vertical emphasis."
        + concept_clause + subject_clause + comp_clause + most_recent_clause
    )
```

- [ ] **Step 5: Run all prompt builder tests**

```bash
python -m pytest lib/tests/test_image_prompt_builder.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add lib/image_prompt_builder.py lib/tests/test_image_prompt_builder.py
git commit -m "feat: extend suggest_novelty_request with subject_family_freq and composition_freq params"
```

---

## Task 7: Update lib/image_generator.py with registry-aware pipeline

**Files:**
- Modify: `lib/image_generator.py`

- [ ] **Step 1: Run existing generator tests to establish baseline**

```bash
python -m pytest lib/tests/test_image_generator.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Add imports at the top of `image_generator.py`**

Find the imports block at line 20. Add `select_prompt_components` to the imports:

Replace:
```python
from lib.image_prompt_builder import (
    PROMPT_MASTER_VERSION,
    build_image_prompt,
    infer_concept_tag,
    suggest_novelty_request,
)
```

With:
```python
from lib.image_prompt_builder import (
    PROMPT_MASTER_VERSION,
    build_image_prompt,
    infer_concept_tag,
    suggest_novelty_request,
)
from lib.image_registry import select_prompt_components
```

- [ ] **Step 3: Update `generate_editorial_image()` signature**

Replace the function signature (lines 104-122):

```python
def generate_editorial_image(
    issue_date: str,
    story_slug: str,
    category: str,
    main_subject: str,
    environment: str,
    composition: str,
    color_system: str,
    context: Optional[str] = None,
    novelty_request: Optional[str] = None,
    variation_code: Optional[str] = None,
    concept_tag: Optional[str] = None,
    subject_family: Optional[str] = None,
    composition_preset: Optional[str] = None,
    force_novelty_level: Optional[int] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    text_threshold: float = DEFAULT_TEXT_THRESHOLD,
    phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full editorial image generation pipeline with automatic deduplication.

    accepted_prompt = revised_prompt if available, else prompt_sent.
    concept_tag: passed explicitly or inferred from category + main_subject.
    subject_family: override registry-selected subject family.
    composition_preset: override registry-selected composition preset.
    force_novelty_level: if set, applies that escalation level from attempt 0.

    Retries up to max_retries when image phash is too close to recent images.
    Text similarity above threshold marks text_risky but does NOT trigger retry.

    Returns: image_path, prompt_sent, revised_prompt, accepted_prompt, concept_tag,
             subject_family, composition_preset, variation_code, novelty_request,
             similarity (dict), regeneration_count, record_id
    """
```

- [ ] **Step 4: Replace the function body with registry-aware implementation**

Replace everything from `init_db(db_path)` (line 137) through the end of the function with:

```python
    init_db(db_path)
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # Load recent history for deduplication and scoring
    recent_category = get_recent_by_category(category, limit=15, db_path=db_path)
    recent_global = get_recent_global(limit=50, db_path=db_path)

    # Compute frequency dicts for novelty directives
    concept_tag_freq = dict(
        Counter(r.get("concept_tag") for r in recent_category if r.get("concept_tag"))
    )
    subject_family_freq = dict(
        Counter(r.get("subject_family") for r in recent_category if r.get("subject_family"))
    )
    composition_freq = dict(
        Counter(r.get("composition_preset") for r in recent_category if r.get("composition_preset"))
    )

    current_novelty = novelty_request
    regeneration_count = 0
    record_id: Optional[int] = None
    excluded_combos = []

    for attempt in range(max_retries + 1):
        # Registry-aware component selection (rotates combo, avoids excluded triples)
        components = select_prompt_components(
            category=category,
            recent_history=recent_category,
            concept_tag=concept_tag,
            subject_family=subject_family,
            composition_preset=composition_preset,
            excluded_combos=excluded_combos,
            force_novelty_level=force_novelty_level if attempt == 0 else None,
        )

        resolved_main_subject = components.get("main_subject") or main_subject
        resolved_composition = components.get("composition") or composition
        resolved_color_system = components.get("color_system") or color_system
        resolved_concept_tag = (
            components.get("concept_tag")
            or concept_tag
            or infer_concept_tag(category, main_subject)
        )
        resolved_subject_family = components.get("subject_family")
        resolved_composition_preset = components.get("composition_preset")
        auto_novelty = components.get("novelty_request")

        used_combo = (
            resolved_concept_tag,
            resolved_subject_family or "",
            resolved_composition_preset or "",
        )

        # Determine effective novelty for this attempt
        if attempt == 0:
            if current_novelty is None:
                if force_novelty_level is not None:
                    current_novelty = suggest_novelty_request(
                        category, recent_category,
                        escalation_level=force_novelty_level,
                        concept_tag_freq=concept_tag_freq,
                        subject_family_freq=subject_family_freq,
                        composition_freq=composition_freq,
                    )
                else:
                    current_novelty = auto_novelty
        # else: current_novelty was already set by escalation logic at end of previous iteration

        prompt = build_image_prompt(
            category=category,
            main_subject=resolved_main_subject,
            environment=environment,
            composition=resolved_composition,
            color_system=resolved_color_system,
            context=context,
            novelty_request=current_novelty,
            variation_code=variation_code,
        )

        slug_safe = story_slug.replace("/", "_").replace(" ", "_")[:60]
        attempt_suffix = f"_r{attempt}" if attempt > 0 else ""
        output_path = os.path.join(out_dir, f"{issue_date}_{slug_safe}{attempt_suffix}.png")

        print(
            f"  [image_generator] Attempt {attempt + 1}/{max_retries + 1}: "
            f"{os.path.basename(output_path)} "
            f"[{resolved_subject_family}/{resolved_composition_preset}]"
        )

        try:
            gen = _generate_image(prompt, output_path)
        except Exception as exc:
            print(f"  [image_generator] Generation error: {exc}")
            save_attempt_record({
                "prompt_sent": prompt,
                "accepted": False,
                "rejection_reason": "generation_error",
            }, db_path=db_path)
            if attempt == max_retries:
                raise
            excluded_combos.append(used_combo)
            escalation = min(attempt + 1, 3)
            current_novelty = suggest_novelty_request(
                category, recent_category, escalation,
                concept_tag_freq=concept_tag_freq,
                subject_family_freq=subject_family_freq,
                composition_freq=composition_freq,
            )
            regeneration_count += 1
            continue

        image_path = gen["image_path"]
        revised_prompt = gen.get("revised_prompt")
        accepted_prompt = revised_prompt or prompt

        sim = check_against_history(
            prompt=accepted_prompt,
            image_path=image_path,
            category_records=recent_category,
            global_records=recent_global,
            text_threshold=text_threshold,
            phash_threshold=phash_threshold,
        )

        is_accepted = not sim["flagged"] or attempt == max_retries

        # Save attempt record
        attempt_id = save_attempt_record({
            "prompt_sent": prompt,
            "revised_prompt": revised_prompt,
            "accepted": is_accepted,
            "rejection_reason": sim.get("rejection_reason") if not is_accepted else None,
            "image_phash": sim.get("new_phash"),
            "similarity_score_text": sim["text_similarity"],
            "similarity_score_image": sim["image_similarity"],
        }, db_path=db_path)

        if is_accepted:
            if sim["flagged"]:
                print("  [image_generator] Warning: max retries reached. Accepting despite similarity.")
            else:
                print(
                    f"  [image_generator] Accepted on attempt {attempt + 1}. "
                    f"phash_dist={sim['min_phash_distance']}, "
                    f"text_risky={sim['text_risky']}"
                )

            shared_record = {
                "issue_date": issue_date,
                "story_slug": story_slug,
                "category": category,
                "prompt_master_version": PROMPT_MASTER_VERSION,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "image_path": image_path,
                "image_phash": sim.get("new_phash"),
                "similarity_score_text": sim["text_similarity"],
                "similarity_score_image": sim["image_similarity"],
                "regeneration_count": regeneration_count,
            }

            if record_id is None:
                record_id = save_record(shared_record, db_path=db_path)
            else:
                update_record(record_id, {
                    "image_path": image_path,
                    "image_phash": sim.get("new_phash"),
                    "accepted_prompt": accepted_prompt,
                    "revised_prompt": revised_prompt,
                    "subject_family": resolved_subject_family,
                    "composition_preset": resolved_composition_preset,
                    "similarity_score_text": sim["text_similarity"],
                    "similarity_score_image": sim["image_similarity"],
                    "regeneration_count": regeneration_count,
                }, db_path=db_path)

            update_attempt_parent(attempt_id, record_id, db_path=db_path)

            return {
                "image_path": image_path,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "similarity": sim,
                "regeneration_count": regeneration_count,
                "record_id": record_id,
            }

        # Image too similar — save record for tracking, then escalate
        if record_id is None:
            record_id = save_record({
                "issue_date": issue_date,
                "story_slug": story_slug,
                "category": category,
                "prompt_master_version": PROMPT_MASTER_VERSION,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "image_path": image_path,
                "image_phash": sim.get("new_phash"),
                "similarity_score_text": sim["text_similarity"],
                "similarity_score_image": sim["image_similarity"],
                "regeneration_count": regeneration_count,
            }, db_path=db_path)
            update_attempt_parent(attempt_id, record_id, db_path=db_path)

        excluded_combos.append(used_combo)
        escalation = min(attempt + 2, 3)
        current_novelty = suggest_novelty_request(
            category, recent_category, escalation,
            concept_tag_freq=concept_tag_freq,
            subject_family_freq=subject_family_freq,
            composition_freq=composition_freq,
        )
        regeneration_count += 1
        print(
            f"  [image_generator] Rejected ({sim['rejection_reason']}). "
            f"Escalating to level {escalation}. excluded_combos={len(excluded_combos)}"
        )

    raise RuntimeError("[image_generator] Generation loop exited unexpectedly.")
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest lib/tests/ -v
```

Expected: all tests pass. The generator tests mock `_generate_image` and will pick up the new params gracefully since they have defaults.

- [ ] **Step 6: Commit**

```bash
git add lib/image_generator.py
git commit -m "feat: integrate registry-aware component selection into generation pipeline"
```

---

## Task 8: Update scripts/generate_editorial_image.py

**Files:**
- Modify: `scripts/generate_editorial_image.py`

- [ ] **Step 1: Add `cmd_list_registry_options()` function**

After the existing `cmd_list_presets()` function (after line 46), add:

```python
def cmd_list_registry_options(category_filter: Optional[str] = None) -> None:
    from lib.image_registry import load_registry
    registry = load_registry()
    categories = (registry.get("categories") or {})
    if category_filter:
        if category_filter not in categories:
            print(f"Unknown category: {category_filter}. Known: {list(categories.keys())}")
            return
        categories = {category_filter: categories[category_filter]}
    print("\n-- Registry options --------------------------------------------------\n")
    for cat, cat_data in categories.items():
        print(f"[{cat}]")
        print(f"  default_color_system: {cat_data.get('default_color_system', '')}")
        print(f"  allowed_concepts:         {cat_data.get('allowed_concepts', [])}")
        print(f"  allowed_subject_families: {cat_data.get('allowed_subject_families', [])}")
        print(f"  allowed_compositions:     {cat_data.get('allowed_compositions', [])}")
        print()
```

Also add the missing `Optional` import — find the `import argparse` block at the top:

Replace:
```python
import argparse
import json
import os
import sys
```

With:
```python
import argparse
import json
import os
import sys
from typing import Optional
```

- [ ] **Step 2: Update `cmd_dry_run()` to show registry-selected components**

Replace the entire `cmd_dry_run()` function (lines 49-99) with:

```python
def cmd_dry_run(args) -> None:
    from lib.image_prompt_builder import (
        build_image_prompt,
        infer_concept_tag,
        resolve_variation_code,
        suggest_novelty_request,
    )
    from lib.image_history_store import get_recent_by_category
    from lib.image_registry import select_prompt_components

    # Load recent history for registry selection
    db_path = args.db_path or None
    recent_history = []
    candidate_count = 0
    try:
        recent_history = get_recent_by_category(args.category, limit=15, db_path=db_path)
        candidate_count = len(recent_history)
    except Exception:
        pass

    # Registry-aware component selection
    components = select_prompt_components(
        category=args.category,
        recent_history=recent_history,
        concept_tag=args.concept_tag,
        subject_family=getattr(args, "subject_family", None),
        composition_preset=getattr(args, "composition_preset", None),
        excluded_combos=[],
    )

    # Use registry values, fall back to explicit CLI args
    resolved_main_subject = components.get("main_subject") or args.main_subject
    resolved_composition = components.get("composition") or args.composition
    resolved_color_system = components.get("color_system") or args.color_system
    resolved_concept_tag = (
        components.get("concept_tag")
        or args.concept_tag
        or infer_concept_tag(args.category, args.main_subject)
    )
    resolved_subject_family = components.get("subject_family")
    resolved_composition_preset = components.get("composition_preset")
    auto_novelty = components.get("novelty_request")

    variation_text = resolve_variation_code(args.variation_code)

    # Determine novelty source
    novelty = args.novelty_request
    novelty_source = "[manual]"
    if novelty is None:
        if args.force_novelty_level is not None:
            novelty = suggest_novelty_request(
                args.category, recent_history, escalation_level=args.force_novelty_level
            )
            novelty_source = f"[forced level {args.force_novelty_level}]"
        elif auto_novelty:
            novelty = auto_novelty
            novelty_source = "[auto]"
        else:
            novelty_source = "[none]"

    # Use registry subject/composition in prompt
    prompt = build_image_prompt(
        category=args.category,
        main_subject=resolved_main_subject,
        environment=args.environment,
        composition=resolved_composition,
        color_system=resolved_color_system,
        context=args.context,
        novelty_request=novelty,
        variation_code=args.variation_code,
    )

    print("\n-- Dry-run breakdown --------------------------------------------------\n")
    print(f"Category:                    {args.category}")
    sf_source = "[override]" if getattr(args, "subject_family", None) else "[registry-selected]"
    cp_source = "[override]" if getattr(args, "composition_preset", None) else "[registry-selected]"
    ct_source = "[override]" if args.concept_tag else "[registry-selected]"
    print(f"Concept tag:                 {resolved_concept_tag}  {ct_source}")
    print(f"Subject family:              {resolved_subject_family or '(none)'}  {sf_source}")
    print(f"Composition preset:          {resolved_composition_preset or '(none)'}  {cp_source}")
    print(f"Color system:                {resolved_color_system}")
    if novelty:
        print(f"Novelty directive:           {novelty_source} {novelty}")
    if variation_text:
        print(f"Variation resolved:          {variation_text}")
    print(f"Same-category combos compared: {candidate_count}")
    print(f"Excluded combos:             0")
    print(f"Text threshold:              {args.text_threshold}")
    print(f"Phash threshold:             {args.phash_threshold}")
    print(f"\nFull prompt ({len(prompt)} chars):\n")
    print(prompt)
```

- [ ] **Step 3: Update `cmd_generate()` to pass new params to the generator**

In `cmd_generate()`, replace the `generate_editorial_image(...)` call to add the new params:

```python
    result = generate_editorial_image(
        issue_date=args.issue_date,
        story_slug=args.story_slug,
        category=args.category,
        main_subject=args.main_subject,
        environment=args.environment,
        composition=args.composition,
        color_system=args.color_system,
        context=args.context,
        novelty_request=args.novelty_request,
        variation_code=args.variation_code,
        concept_tag=args.concept_tag,
        subject_family=getattr(args, "subject_family", None),
        composition_preset=getattr(args, "composition_preset", None),
        force_novelty_level=args.force_novelty_level,
        max_retries=args.max_retries,
        text_threshold=args.text_threshold,
        phash_threshold=args.phash_threshold,
        output_dir=args.output_dir,
        db_path=args.db_path,
    )
```

Also update the result print block to show new fields. After `print(f"Concept tag:          {result['concept_tag']}")`, add:

```python
    print(f"Subject family:       {result.get('subject_family', '(none)')}")
    print(f"Composition preset:   {result.get('composition_preset', '(none)')}")
```

- [ ] **Step 4: Add new argument flags to `main()`**

In `main()`, after the `--concept-tag` argument (line 181-182), add:

```python
    parser.add_argument("--subject-family", default=None,
                        help="Override registry-selected subject family (e.g. tanker)")
    parser.add_argument("--composition-preset", default=None,
                        help="Override registry-selected composition preset (e.g. elevated_wide)")
    parser.add_argument("--list-registry-options", nargs="?", const="",
                        metavar="CATEGORY",
                        help="Print registry allowed values per category and exit")
```

- [ ] **Step 5: Add the `--list-registry-options` dispatch in `main()`**

After the `args = parser.parse_args()` line, add (before the `if args.list_presets:` block):

```python
    if args.list_registry_options is not None:
        cmd_list_registry_options(args.list_registry_options or None)
        return
```

- [ ] **Step 6: Test the new flags with dry-run**

```bash
cd D:/GitHub/News-Digest
python scripts/generate_editorial_image.py --dry-run --category energy --main-subject "refinery at dusk"
```

Expected: dry-run breakdown prints with `Subject family:` and `Composition preset:` rows showing registry-selected values.

```bash
python scripts/generate_editorial_image.py --list-registry-options energy
```

Expected: prints `[energy]` with allowed_concepts, allowed_subject_families, allowed_compositions.

```bash
python scripts/generate_editorial_image.py --list-registry-options
```

Expected: prints all 6 categories.

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_editorial_image.py
git commit -m "feat: add --subject-family, --composition-preset, --list-registry-options CLI flags"
```

---

## Task 9: Update README-image-generation.md

**Files:**
- Modify: `README-image-generation.md`

- [ ] **Step 1: Append two new sections to the end of README-image-generation.md**

Read the file first to find its current end, then append after the last existing content:

```markdown

---

## How the registry prevents repeated category images

The `config/image_prompt_registry.yaml` file stores per-category building blocks: a list of
`allowed_concepts`, `allowed_subject_families`, and `allowed_compositions`. Each category has
4–5 entries per list, giving 64–125 unique `(concept_tag, subject_family, composition_preset)`
triples before any repeat is necessary.

**Selection flow:**

1. `select_prompt_components()` (in `lib/image_registry.py`) loads the registry and fetches the
   last 8 same-category history records.
2. Every candidate triple in the cross-product of the allowed pools is scored by how many times
   it appears in the recent 8. Lower count = better.
3. Tiebreak: prefer triples where 2+ dimensions differ from the most recent image's triple.
4. The lowest-penalty triple is selected; ties are broken randomly.

**Retry rotation:**

Each rejected attempt adds its triple to `excluded_combos`. On the next attempt,
`select_prompt_components()` is called again with the updated exclusion list, ensuring:

- Retry 1: different `composition_preset` preferred
- Retry 2: different `subject_family` preferred
- Retry 3: different `concept_tag` if needed

**Auto-novelty:**

If any `subject_family` or `composition_preset` appears 3+ times in the last 8 same-category
records, a novelty directive is automatically generated naming what to avoid. This is injected at
attempt 0 when no manual `--novelty-request` is provided.

---

## How `accepted_prompt`, `concept_tag`, `subject_family`, and `composition_preset` work together

Every accepted generation stores four semantic fields in `image_history`:

| Field | What it stores | Used for |
|-------|----------------|----------|
| `accepted_prompt` | `revised_prompt` if the model rewrote the prompt, else `prompt_sent` | Text similarity comparison — always the prompt the model *actually used* |
| `concept_tag` | Visual metaphor label inferred or overridden at generation time (e.g. `maritime_passage`) | Concept-frequency tracking for novelty directives |
| `subject_family` | Registry subject family chosen at generation time (e.g. `tanker`) | Anti-repetition scoring across same-category runs |
| `composition_preset` | Registry composition preset chosen at generation time (e.g. `elevated_wide`) | Anti-repetition scoring across same-category runs |

Using `accepted_prompt` for text similarity (rather than `prompt_sent`) ensures that if the image
model rewrites the prompt — which OpenAI models frequently do — similarity comparisons are made
against the version that actually influenced the image.

The three semantic fields together define the combination space. By tracking them across issues,
`select_prompt_components()` can avoid repeating not just the same words in a prompt, but the same
*visual concept*, *subject category*, and *framing approach* — the three dimensions most responsible
for images looking identical.
```

- [ ] **Step 2: Verify the file ends correctly**

```bash
python -c "
content = open('README-image-generation.md').read()
assert 'How the registry prevents repeated category images' in content
assert 'accepted_prompt' in content.split('How \`accepted_prompt\`')[1]
print('README OK')
"
```

Expected: `README OK`

- [ ] **Step 3: Commit**

```bash
git add README-image-generation.md
git commit -m "docs: add registry anti-repetition and accepted_prompt sections to README"
```

---

## Final Verification

- [ ] **Run the full test suite**

```bash
python -m pytest lib/tests/ -v
```

Expected: all tests pass with 0 failures.

- [ ] **Smoke test: dry-run with full registry**

```bash
python scripts/generate_editorial_image.py \
  --dry-run \
  --category shipping_geopolitics \
  --main-subject "cargo vessel in strait" \
  --environment "open water, misty morning" \
  --composition "converging lines" \
  --color-system "steel blue"
```

Expected: dry-run output shows `Subject family:` and `Composition preset:` rows with registry-selected values from `shipping_geopolitics`.

- [ ] **Smoke test: list-registry-options**

```bash
python scripts/generate_editorial_image.py --list-registry-options
```

Expected: all 6 categories printed with their allowed pools.

- [ ] **Smoke test: registry YAML parses cleanly**

```bash
python -c "
import yaml
data = yaml.safe_load(open('config/image_prompt_registry.yaml'))
cats = list(data['categories'].keys())
assert cats == ['energy','shipping_geopolitics','trade_supply_chain','macro_inflation','policy_institutional','markets_finance'], cats
for cat, cd in data['categories'].items():
    assert len(cd['allowed_concepts']) >= 3, f'{cat} too few concepts'
    assert len(cd['allowed_subject_families']) >= 3, f'{cat} too few subjects'
    assert len(cd['allowed_compositions']) >= 3, f'{cat} too few compositions'
    combo_count = len(cd['allowed_concepts']) * len(cd['allowed_subject_families']) * len(cd['allowed_compositions'])
    assert combo_count >= 27, f'{cat} only {combo_count} combos'
print('Registry YAML OK — all 6 categories valid')
"
```

Expected: `Registry YAML OK — all 6 categories valid`

- [ ] **Final commit tag**

```bash
git log --oneline -9
```

You should see 9 commits since the start of this plan. All 7 files changed, tests passing.
