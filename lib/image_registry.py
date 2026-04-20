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

    excluded_combos: triples already tried in this retry run -- excluded from selection.

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

    # Extract recent triples (last 8) -- skip rows missing any field
    recent_8 = recent_history[:8]
    recent_triples: List[Tuple[str, str, str]] = []
    for r in recent_8:
        ct = r.get("concept_tag")
        sf = r.get("subject_family")
        cp = r.get("composition_preset")
        if ct and sf and cp:
            recent_triples.append((ct, sf, cp))

    most_recent_triple = recent_triples[0] if recent_triples else None

    # Fall back to simple selection if registry has no data for this category
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
