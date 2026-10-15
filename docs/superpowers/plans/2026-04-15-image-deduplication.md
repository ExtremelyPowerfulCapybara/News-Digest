# Image Generation Deduplication System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained image generation + deduplication subsystem to News-Digest that prevents repeated prompts and visually similar images across newsletter issues.

**Architecture:** Six focused modules in `lib/` handle prompt assembly, SQLite persistence, text/visual similarity, and generation orchestration. A CLI script in `scripts/` exposes the full pipeline. The subsystem is completely independent — it does not modify any existing `bot/` files.

**Tech Stack:** Python 3.10+, SQLite (stdlib), `imagehash` (phash), `scikit-learn` (TF-IDF cosine), `Pillow` (image loading), `openai` (already in requirements), `python-dotenv` (already in requirements).

---

## File Map

| File | Responsibility |
|------|----------------|
| `lib/__init__.py` | Empty package marker |
| `lib/tests/__init__.py` | Empty test package marker |
| `lib/image_prompt_builder.py` | `build_image_prompt()`, variation resolver, `suggest_novelty_request()` (levels 0–3, concept-aware), `infer_concept_tag()`, category presets |
| `lib/image_history_store.py` | SQLite CRUD: `init_db()` (two tables), `save_record()`, `update_record()`, `save_attempt_record()`, `update_attempt_parent()`, `get_recent_by_category()`, `get_recent_global()` |
| `lib/image_similarity.py` | `compute_phash()`, `phash_distance()`, `compute_text_similarity()`, `check_against_history()` (two-phase: category then global; image priority) |
| `lib/image_generator.py` | `generate_editorial_image()` — full pipeline orchestrator with deduplication loop, attempt tracking, accepted_prompt logic |
| `scripts/generate_editorial_image.py` | CLI entry point with argparse; enhanced dry-run; `--force-novelty-level`, `--show-similarity-debug`, `--concept-tag` |
| `lib/tests/test_image_prompt_builder.py` | Tests for prompt assembly, variation resolver, novelty suggestion, concept tag inference |
| `lib/tests/test_image_history_store.py` | Tests for both tables, CRUD, attempt tracking |
| `lib/tests/test_image_similarity.py` | Tests for phash, TF-IDF, two-phase comparison, image-priority logic |
| `lib/tests/test_image_generator.py` | Tests for generation pipeline with mocked OpenAI |
| `requirements.txt` | Add `imagehash`, `scikit-learn` |
| `README-image-generation.md` | Setup, usage, configuration guide |

---

## Task 1: Package Scaffolding + SQLite Schema

**Files:**
- Create: `lib/__init__.py`
- Create: `lib/tests/__init__.py`
- Create: `lib/image_history_store.py`
- Create: `lib/tests/test_image_history_store.py`

- [ ] **Step 1.1: Create package markers**

```python
# lib/__init__.py
# Image generation deduplication subsystem.
```

```python
# lib/tests/__init__.py
```

- [ ] **Step 1.2: Write failing tests for the history store**

Create `lib/tests/test_image_history_store.py`:

```python
# lib/tests/test_image_history_store.py
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lib.image_history_store import (
    init_db,
    save_record,
    update_record,
    save_attempt_record,
    update_attempt_parent,
    get_recent_by_category,
    get_recent_global,
)


@pytest.fixture
def tmp_db(tmp_path):
    db = str(tmp_path / "test_history.db")
    init_db(db)
    return db


def test_init_db_creates_image_history_table(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='image_history'"
        ).fetchall()
    assert len(rows) == 1


def test_init_db_creates_generation_attempts_table(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_attempts'"
        ).fetchall()
    assert len(rows) == 1


def test_init_db_is_idempotent(tmp_db):
    init_db(tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    assert count == 2  # image_history + generation_attempts


def test_save_record_returns_id(tmp_db):
    rid = save_record({
        "issue_date": "2026-04-15",
        "story_slug": "test-story",
        "category": "energy",
        "prompt_sent": "Test prompt",
    }, db_path=tmp_db)
    assert isinstance(rid, int) and rid > 0


def test_save_record_stores_accepted_prompt_and_concept_tag(tmp_db):
    save_record({
        "issue_date": "2026-04-15",
        "story_slug": "test-story",
        "category": "energy",
        "prompt_sent": "Original prompt",
        "accepted_prompt": "Revised and accepted prompt",
        "concept_tag": "industrial_cluster",
    }, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image_history").fetchone())
    assert row["accepted_prompt"] == "Revised and accepted prompt"
    assert row["concept_tag"] == "industrial_cluster"


def test_save_record_stores_all_fields(tmp_db):
    save_record({
        "issue_date": "2026-04-15",
        "story_slug": "test-story",
        "category": "energy",
        "prompt_master_version": "v1",
        "prompt_sent": "A long prompt",
        "revised_prompt": "A revised prompt",
        "accepted_prompt": "A revised prompt",
        "concept_tag": "pipeline_infrastructure",
        "variation_code": "B-2-ii-gamma",
        "novelty_request": "Avoid last 4 energy images",
        "image_path": "/tmp/test.png",
        "image_phash": "abcd1234",
        "similarity_score_text": 0.45,
        "similarity_score_image": 0.12,
        "regeneration_count": 1,
        "notes": "Test note",
    }, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image_history").fetchone())
    assert row["prompt_sent"] == "A long prompt"
    assert row["revised_prompt"] == "A revised prompt"
    assert row["accepted_prompt"] == "A revised prompt"
    assert row["concept_tag"] == "pipeline_infrastructure"
    assert row["variation_code"] == "B-2-ii-gamma"


def test_update_record_modifies_fields(tmp_db):
    rid = save_record({
        "issue_date": "2026-04-15",
        "story_slug": "test-story",
        "category": "energy",
        "prompt_sent": "Test prompt",
    }, db_path=tmp_db)
    update_record(rid, {"image_phash": "newphash", "regeneration_count": 2, "accepted_prompt": "final"}, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image_history WHERE id = ?", (rid,)).fetchone())
    assert row["image_phash"] == "newphash"
    assert row["regeneration_count"] == 2
    assert row["accepted_prompt"] == "final"


def test_get_recent_by_category_returns_records(tmp_db):
    for i in range(3):
        save_record({
            "issue_date": f"2026-04-{15 + i:02d}",
            "story_slug": f"story-{i}",
            "category": "energy",
            "prompt_sent": f"Prompt {i}",
        }, db_path=tmp_db)
    save_record({
        "issue_date": "2026-04-15",
        "story_slug": "other-story",
        "category": "markets_finance",
        "prompt_sent": "Other prompt",
    }, db_path=tmp_db)
    results = get_recent_by_category("energy", db_path=tmp_db)
    assert len(results) == 3
    assert all(r["category"] == "energy" for r in results)


def test_get_recent_global_returns_all(tmp_db):
    for cat in ("energy", "markets_finance", "macro_inflation"):
        save_record({
            "issue_date": "2026-04-15",
            "story_slug": f"slug-{cat}",
            "category": cat,
            "prompt_sent": f"Prompt for {cat}",
        }, db_path=tmp_db)
    results = get_recent_global(db_path=tmp_db)
    assert len(results) == 3


def test_get_recent_by_category_respects_limit(tmp_db):
    for i in range(10):
        save_record({
            "issue_date": f"2026-04-{i + 1:02d}",
            "story_slug": f"story-{i}",
            "category": "energy",
            "prompt_sent": f"Prompt {i}",
        }, db_path=tmp_db)
    results = get_recent_by_category("energy", limit=4, db_path=tmp_db)
    assert len(results) == 4


def test_save_attempt_record_returns_id(tmp_db):
    aid = save_attempt_record({
        "prompt_sent": "Test prompt",
        "accepted": False,
        "rejection_reason": "phash_too_close_category",
    }, db_path=tmp_db)
    assert isinstance(aid, int) and aid > 0


def test_save_attempt_record_stores_fields(tmp_db):
    aid = save_attempt_record({
        "prompt_sent": "A prompt",
        "revised_prompt": "Revised",
        "accepted": True,
        "rejection_reason": None,
        "image_phash": "abc123",
        "similarity_score_text": 0.5,
        "similarity_score_image": 0.2,
    }, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM generation_attempts WHERE id = ?", (aid,)).fetchone())
    assert row["prompt_sent"] == "A prompt"
    assert row["accepted"] == 1
    assert row["image_phash"] == "abc123"


def test_update_attempt_parent_sets_id(tmp_db):
    rid = save_record({
        "issue_date": "2026-04-15",
        "story_slug": "s",
        "category": "energy",
        "prompt_sent": "p",
    }, db_path=tmp_db)
    aid = save_attempt_record({"prompt_sent": "p", "accepted": True}, db_path=tmp_db)
    update_attempt_parent(aid, rid, db_path=tmp_db)
    with sqlite3.connect(tmp_db) as conn:
        val = conn.execute(
            "SELECT parent_image_id FROM generation_attempts WHERE id = ?", (aid,)
        ).fetchone()[0]
    assert val == rid
```

- [ ] **Step 1.3: Run to confirm failure**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_history_store.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.image_history_store'`

- [ ] **Step 1.4: Implement `lib/image_history_store.py`**

```python
# lib/image_history_store.py
# ─────────────────────────────────────────────
#  SQLite persistence for image generation history.
#
#  Tables:
#    image_history      — one row per accepted generation (final result)
#    generation_attempts — one row per API call (includes rejected ones)
#
#  All functions accept an optional db_path for testability.
#  Default DB path: data/image_history.db (repo root).
# ─────────────────────────────────────────────

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

_DEFAULT_DB = os.path.join(
    os.path.dirname(__file__), "..", "data", "image_history.db"
)


def _resolve_path(db_path: Optional[str]) -> str:
    path = db_path or os.environ.get("IMAGE_HISTORY_DB", _DEFAULT_DB)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


def init_db(db_path: Optional[str] = None) -> None:
    """Create both tables if they do not exist. Safe to call multiple times."""
    path = _resolve_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS image_history (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at             TEXT    NOT NULL,
            issue_date             TEXT    NOT NULL,
            story_slug             TEXT    NOT NULL,
            category               TEXT    NOT NULL,
            prompt_master_version  TEXT,
            prompt_sent            TEXT    NOT NULL,
            revised_prompt         TEXT,
            accepted_prompt        TEXT,
            variation_code         TEXT,
            novelty_request        TEXT,
            concept_tag            TEXT,
            image_path             TEXT,
            image_phash            TEXT,
            similarity_score_text  REAL,
            similarity_score_image REAL,
            regeneration_count     INTEGER DEFAULT 0,
            notes                  TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_attempts (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_image_id        INTEGER,
            created_at             TEXT    NOT NULL,
            prompt_sent            TEXT    NOT NULL,
            revised_prompt         TEXT,
            accepted               INTEGER NOT NULL DEFAULT 0,
            rejection_reason       TEXT,
            image_phash            TEXT,
            similarity_score_text  REAL,
            similarity_score_image REAL
        )
        """)
        conn.commit()


def save_record(record: Dict, db_path: Optional[str] = None) -> int:
    """
    Insert a new accepted generation record. Returns the new row id.
    Required keys: issue_date, story_slug, category, prompt_sent.
    accepted_prompt should be revised_prompt if available, else prompt_sent.
    """
    path = _resolve_path(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO image_history (
                created_at, issue_date, story_slug, category,
                prompt_master_version, prompt_sent, revised_prompt,
                accepted_prompt, variation_code, novelty_request, concept_tag,
                image_path, image_phash, similarity_score_text,
                similarity_score_image, regeneration_count, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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


def update_record(record_id: int, updates: Dict, db_path: Optional[str] = None) -> None:
    """
    Update specific fields on an existing image_history record.
    """
    _allowed = {
        "image_path", "image_phash", "similarity_score_text",
        "similarity_score_image", "regeneration_count",
        "revised_prompt", "accepted_prompt", "concept_tag", "notes",
    }
    fields = {k: v for k, v in updates.items() if k in _allowed}
    if not fields:
        return
    path = _resolve_path(db_path)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [record_id]
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"UPDATE image_history SET {set_clause} WHERE id = ?", values
        )
        conn.commit()


def save_attempt_record(attempt: Dict, db_path: Optional[str] = None) -> int:
    """
    Insert a generation attempt record (accepted or rejected).
    Required key: prompt_sent.
    """
    path = _resolve_path(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO generation_attempts (
                parent_image_id, created_at, prompt_sent, revised_prompt,
                accepted, rejection_reason, image_phash,
                similarity_score_text, similarity_score_image
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                attempt.get("parent_image_id"),
                attempt.get("created_at", now),
                attempt["prompt_sent"],
                attempt.get("revised_prompt"),
                1 if attempt.get("accepted") else 0,
                attempt.get("rejection_reason"),
                attempt.get("image_phash"),
                attempt.get("similarity_score_text"),
                attempt.get("similarity_score_image"),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def update_attempt_parent(
    attempt_id: int, parent_image_id: int, db_path: Optional[str] = None
) -> None:
    """Link an attempt to its parent image_history record once accepted."""
    path = _resolve_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE generation_attempts SET parent_image_id = ? WHERE id = ?",
            (parent_image_id, attempt_id),
        )
        conn.commit()


def get_recent_by_category(
    category: str, limit: int = 15, db_path: Optional[str] = None
) -> List[Dict]:
    """Return the most recent `limit` records for a given category, newest first."""
    path = _resolve_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM image_history WHERE category = ? ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_global(limit: int = 50, db_path: Optional[str] = None) -> List[Dict]:
    """Return the most recent `limit` records across all categories, newest first."""
    path = _resolve_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM image_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 1.5: Run tests to confirm they pass**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_history_store.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 1.6: Commit**

```bash
git add lib/__init__.py lib/tests/__init__.py lib/image_history_store.py lib/tests/test_image_history_store.py
git commit -m "feat: add image_history_store with image_history and generation_attempts tables"
```

---

## Task 2: Prompt Builder — Core Assembly + Concept Tagging

**Files:**
- Create: `lib/image_prompt_builder.py`
- Create: `lib/tests/test_image_prompt_builder.py`

- [ ] **Step 2.1: Write failing tests**

Create `lib/tests/test_image_prompt_builder.py`:

```python
# lib/tests/test_image_prompt_builder.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lib.image_prompt_builder import (
    build_image_prompt,
    resolve_variation_code,
    suggest_novelty_request,
    infer_concept_tag,
    PROMPT_MASTER_VERSION,
    CATEGORY_PRESETS,
)


# ── Prompt assembly ───────────────────────────────────────────────────────────

def test_build_image_prompt_contains_style_master_anchors():
    prompt = build_image_prompt(
        category="energy",
        main_subject="oil refinery towers",
        environment="flat industrial horizon",
        composition="wide establishing shot",
        color_system="warm amber-rust on metal",
    )
    assert "Premium editorial illustration" in prompt
    assert "hand-drawn ink and graphite" in prompt
    assert "no text, no logos, no watermark" in prompt


def test_build_image_prompt_inserts_subject():
    prompt = build_image_prompt(
        category="energy",
        main_subject="offshore drilling platform",
        environment="calm sea at dusk",
        composition="centered, symmetrical framing",
        color_system="steel blue accents",
    )
    assert "offshore drilling platform" in prompt
    assert "calm sea at dusk" in prompt
    assert "steel blue accents" in prompt


def test_build_image_prompt_includes_category_block():
    prompt = build_image_prompt(
        category="energy",
        main_subject="refinery towers",
        environment="horizon",
        composition="wide shot",
        color_system="amber",
    )
    assert "oil" in prompt.lower() or "industrial" in prompt.lower() or "refiner" in prompt.lower()


def test_build_image_prompt_appends_context():
    prompt = build_image_prompt(
        category="energy",
        main_subject="refinery towers",
        environment="horizon",
        composition="wide shot",
        color_system="amber",
        context="Pemex announces major output cut",
    )
    assert "Pemex announces major output cut" in prompt


def test_build_image_prompt_novelty_at_end():
    novelty = "Completely different direction required"
    prompt = build_image_prompt(
        category="energy",
        main_subject="refinery towers",
        environment="horizon",
        composition="wide shot",
        color_system="amber",
        novelty_request=novelty,
    )
    style_end_idx = prompt.index("no watermark")
    novelty_idx = prompt.index(novelty)
    assert novelty_idx > style_end_idx


def test_build_image_prompt_variation_code_appended():
    prompt = build_image_prompt(
        category="energy",
        main_subject="refinery towers",
        environment="horizon",
        composition="wide shot",
        color_system="amber",
        variation_code="B-2-ii-gamma",
    )
    assert "asymmetric" in prompt.lower() or "variation" in prompt.lower()


def test_build_image_prompt_no_optional_fields_leaves_no_placeholders():
    prompt = build_image_prompt(
        category="energy",
        main_subject="refinery towers",
        environment="horizon",
        composition="wide shot",
        color_system="amber",
    )
    assert "Editorial context:" not in prompt
    assert "Novelty directive:" not in prompt
    assert "Variation instructions:" not in prompt


def test_prompt_master_version_is_string():
    assert isinstance(PROMPT_MASTER_VERSION, str)
    assert len(PROMPT_MASTER_VERSION) > 0


# ── Variation code resolver ───────────────────────────────────────────────────

def test_resolve_variation_code_b_2_ii_gamma():
    result = resolve_variation_code("B-2-ii-gamma")
    assert result is not None
    assert "asymmetric" in result.lower()
    assert "two foreground" in result.lower() or "dual" in result.lower()
    assert "moderate" in result.lower()
    assert "desaturated" in result.lower()


def test_resolve_variation_code_returns_none_for_empty():
    assert resolve_variation_code("") is None
    assert resolve_variation_code(None) is None


def test_resolve_variation_code_returns_none_for_wrong_format():
    assert resolve_variation_code("B-2-ii") is None
    assert resolve_variation_code("B-2-ii-gamma-extra") is None


def test_resolve_variation_code_unknown_keys_skipped():
    result = resolve_variation_code("Z-2-ii-gamma")
    assert result is not None
    assert "moderate" in result.lower()


# ── Escalation levels 0–3 ─────────────────────────────────────────────────────

def test_suggest_novelty_level_0_is_mild():
    history = [{"category": "energy", "concept_tag": "industrial_cluster"} for _ in range(4)]
    result = suggest_novelty_request("energy", history, escalation_level=0)
    assert isinstance(result, str) and len(result) > 10


def test_suggest_novelty_level_3_is_strongest():
    history = [{"category": "energy", "concept_tag": "industrial_cluster"} for _ in range(8)]
    mild = suggest_novelty_request("energy", history, escalation_level=0)
    strong = suggest_novelty_request("energy", history, escalation_level=3)
    assert len(strong) > len(mild)


def test_suggest_novelty_empty_history():
    result = suggest_novelty_request("markets_finance", [], escalation_level=1)
    assert isinstance(result, str) and len(result) > 10


def test_suggest_novelty_concept_aware():
    """When a concept_tag is overused, the novelty request should mention it."""
    history = [
        {"category": "energy", "concept_tag": "industrial_cluster"}
        for _ in range(5)
    ]
    result = suggest_novelty_request(
        "energy",
        history,
        escalation_level=2,
        concept_tag_freq={"industrial_cluster": 5},
    )
    assert "industrial_cluster" in result or "industrial cluster" in result.lower()


def test_suggest_novelty_no_concept_freq_still_works():
    history = [{"category": "energy", "concept_tag": None} for _ in range(3)]
    result = suggest_novelty_request("energy", history, escalation_level=1)
    assert isinstance(result, str) and len(result) > 10


# ── Concept tag inference ─────────────────────────────────────────────────────

def test_infer_concept_tag_refinery():
    tag = infer_concept_tag("energy", "oil refinery towers at dusk")
    assert tag == "industrial_cluster"


def test_infer_concept_tag_pipeline():
    tag = infer_concept_tag("energy", "close-up of pipeline valves")
    assert tag == "pipeline_infrastructure"


def test_infer_concept_tag_container():
    tag = infer_concept_tag("shipping_geopolitics", "stacked containers at a port")
    assert tag == "container_logistics"


def test_infer_concept_tag_fallback():
    tag = infer_concept_tag("energy", "something completely unknown")
    assert tag == "energy_general"


def test_infer_concept_tag_returns_string():
    tag = infer_concept_tag("macro_inflation", "central bank exterior")
    assert isinstance(tag, str) and len(tag) > 0


# ── Category presets ──────────────────────────────────────────────────────────

def test_category_presets_cover_all_required_categories():
    required = {
        "energy", "shipping_geopolitics", "trade_supply_chain",
        "macro_inflation", "policy_institutional", "markets_finance",
    }
    assert required.issubset(set(CATEGORY_PRESETS.keys()))


def test_category_presets_have_required_keys():
    required_keys = {"main_subject", "environment", "composition", "color_system"}
    for cat, preset in CATEGORY_PRESETS.items():
        assert required_keys.issubset(set(preset.keys())), f"Preset for '{cat}' missing keys"
```

- [ ] **Step 2.2: Run to confirm failure**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_prompt_builder.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.image_prompt_builder'`

- [ ] **Step 2.3: Implement `lib/image_prompt_builder.py`**

```python
# lib/image_prompt_builder.py
# ─────────────────────────────────────────────
#  Builds image prompts for the editorial deduplication system.
#
#  Block assembly order (never reorder):
#    1. style_master  (fixed, stable)
#    2. category_block
#    3. context_block (if provided)
#    4. variation_block (if variation_code provided)
#    5. novelty_block (if novelty_request provided — always last)
# ─────────────────────────────────────────────

from collections import Counter
from typing import Dict, List, Optional

PROMPT_MASTER_VERSION = "v1"

STYLE_MASTER = (
    "Premium editorial illustration for a high-end financial and geopolitical newsletter, "
    "hand-drawn ink and graphite style with refined linework and subtle cross-hatching, "
    "expressive but controlled linework with slightly varied line weight and subtle human imperfection, "
    "monochrome base with controlled muted color accents (approximately 20-25%), "
    "slightly textured paper background, "
    "{MAIN_SUBJECT} placed in {ENVIRONMENT}, "
    "{COMPOSITION}, "
    "asymmetrical layout with intentional visual balance, "
    "main subject clearly dominant in the foreground, "
    "minimal and elegant composition with strong negative space, "
    "realistic proportions and believable detail, "
    "calm and sophisticated atmosphere with subtle economic or geopolitical tension, "
    "modern whitepaper-inspired editorial aesthetic with a distinctive contemporary edge, "
    "restrained and mature tone, "
    "color accents concentrated primarily on the main subject using {COLOR_SYSTEM}, "
    "background color extremely subdued and desaturated, "
    "background with moderate detail but softened edges and lower contrast using atmospheric perspective, "
    "subtle narrative quality suggesting broader context, "
    "soft grounded baseline anchoring the composition, "
    "not painterly, not cinematic, not glossy, not photorealistic, not 3D render, not infographic, "
    "no bright colors, no neon, no cyberpunk, no exaggerated lighting, no dramatic action, "
    "no explosions, no clutter, no text, no logos, no watermark."
)

CATEGORY_BLOCKS: Dict[str, str] = {
    "energy": (
        "Category domain: oil and gas infrastructure, refineries, pipelines, "
        "offshore platforms, or industrial energy facilities with physical gravitas"
    ),
    "shipping_geopolitics": (
        "Category domain: port infrastructure, container yards, cargo vessels, "
        "maritime chokepoints, or strategic waterways"
    ),
    "trade_supply_chain": (
        "Category domain: logistics hubs, customs checkpoints, warehouses, "
        "industrial transit corridors, or supply chain infrastructure"
    ),
    "macro_inflation": (
        "Category domain: central bank architecture, empty trading floors, "
        "institutional financial settings, or monetary symbols"
    ),
    "policy_institutional": (
        "Category domain: government buildings, legislative chambers, "
        "institutional facades, or state apparatus settings"
    ),
    "markets_finance": (
        "Category domain: financial district architecture, stock exchanges, "
        "data-driven trading environments, or capital market settings"
    ),
}

# ── Variation code components ─────────────────────────────────────────────────
# Format: [COMPOSITION]-[FOREGROUND]-[BACKGROUND]-[COLOR]
# Example: B-2-ii-gamma

COMPOSITION_PRESETS: Dict[str, str] = {
    "A": "centered symmetrical framing, subject anchored at the optical center",
    "B": "asymmetric left-weighted composition, subject offset to the left third, open space right",
    "C": "asymmetric right-weighted composition, subject offset to the right third, open space left",
    "D": "diagonal tension line through the frame, subject at the upper or lower intersection",
    "E": "split-frame composition, foreground element and background element in visual dialogue",
}

FOREGROUND_PRESETS: Dict[str, str] = {
    "1": "single dominant foreground subject, all other elements clearly subordinate",
    "2": "two foreground elements in visual tension, neither fully dominant, balanced dual weight",
    "3": "scattered foreground elements suggesting multiplicity or systemic complexity",
    "4": "foreground element framing a deeper secondary subject, frame-within-frame structure",
}

BACKGROUND_PRESETS: Dict[str, str] = {
    "i":   "minimal background, near-empty space with faint texture or horizon only",
    "ii":  "moderate background detail, recognizable environment softened by atmospheric perspective",
    "iii": "rich background, layered architectural or industrial elements receding into distance",
    "iv":  "complex background, multiple receding planes suggesting depth and systemic scale",
}

COLOR_PRESETS: Dict[str, str] = {
    "alpha":   "warm muted earth tones on the subject — ochre, rust, or aged-paper warmth",
    "beta":    "cool muted accents on the subject — slate blue, steel gray, or faded teal",
    "gamma":   "fully desaturated — no color accents, pure graphite and ink monochrome",
    "delta":   "sepia-tinted warm monochrome, aged document aesthetic with amber undertones",
    "epsilon": "graphite with single restrained accent — one hue only, used sparingly on key detail",
}

CATEGORY_PRESETS: Dict[str, Dict[str, str]] = {
    "energy": {
        "main_subject": "oil refinery towers and storage tanks with slow industrial exhaust rising",
        "environment":  "flat industrial horizon at dusk, overcast sky, distant gas flares",
        "composition":  "wide establishing shot, subject dominant left, open sky right",
        "color_system": "warm amber-rust tones on metal surfaces, cool gray background",
    },
    "shipping_geopolitics": {
        "main_subject": "stacked shipping containers at a deep-water port, crane silhouettes overhead",
        "environment":  "calm harbor water, low overcast sky, distant coastline",
        "composition":  "converging perspective lines leading to a distant cargo vessel",
        "color_system": "steel blue accents on container markings, muted rust on crane structures",
    },
    "trade_supply_chain": {
        "main_subject": "a deserted customs checkpoint or sealed cargo gate, barrier arm raised",
        "environment":  "long industrial road extending to horizon, flat terrain, harsh midday light",
        "composition":  "central vanishing point, subject slightly off-axis",
        "color_system": "muted ochre on road markings, cool gray on barrier and infrastructure",
    },
    "macro_inflation": {
        "main_subject": "central bank building exterior, stone columns and carved inscriptions",
        "environment":  "empty stone plaza, overcast sky, no figures",
        "composition":  "low angle, subject monumental in foreground, sky dominant in background",
        "color_system": "warm stone tones on architecture, cool gray sky and deep shadows",
    },
    "policy_institutional": {
        "main_subject": "government building facade with national flags, closed heavy ceremonial doors",
        "environment":  "empty plaza with long shadow geometry, overcast diffuse light",
        "composition":  "frontal near-symmetrical framing broken by slight camera offset",
        "color_system": "muted flag accent colors, predominantly graphite and stone gray",
    },
    "markets_finance": {
        "main_subject": "financial district tower atrium viewed from below, glass and steel geometry",
        "environment":  "interior architectural space, receding perspective, diffuse ambient light",
        "composition":  "upward diagonal vanishing point, strong perspective, open upper frame",
        "color_system": "cool steel blue on glass surfaces, warm amber on structural elements",
    },
}

# ── Concept tag inference ─────────────────────────────────────────────────────
# Maps (category, subject keyword) -> concept_tag.
# First matching keyword wins. Falls back to "{category}_general".

_CONCEPT_KEYWORD_MAP: Dict[str, Dict[str, str]] = {
    "energy": {
        "refinery": "industrial_cluster",
        "tower":    "industrial_cluster",
        "chimney":  "industrial_cluster",
        "flare":    "industrial_cluster",
        "pipeline": "pipeline_infrastructure",
        "valve":    "pipeline_infrastructure",
        "pipe":     "pipeline_infrastructure",
        "offshore": "offshore_platform",
        "platform": "offshore_platform",
        "rig":      "offshore_platform",
        "storage":  "storage_facility",
        "tank":     "storage_facility",
    },
    "shipping_geopolitics": {
        "container": "container_logistics",
        "crane":     "container_logistics",
        "vessel":    "maritime_passage",
        "ship":      "maritime_passage",
        "tanker":    "maritime_passage",
        "port":      "port_infrastructure",
        "harbor":    "port_infrastructure",
        "dock":      "port_infrastructure",
        "strait":    "maritime_chokepoint",
        "channel":   "maritime_chokepoint",
    },
    "trade_supply_chain": {
        "checkpoint": "restriction_barrier",
        "barrier":    "restriction_barrier",
        "gate":       "restriction_barrier",
        "customs":    "restriction_barrier",
        "warehouse":  "logistics_hub",
        "depot":      "logistics_hub",
        "road":       "transit_corridor",
        "highway":    "transit_corridor",
    },
    "macro_inflation": {
        "bank":        "institutional_facade",
        "central":     "institutional_facade",
        "column":      "institutional_facade",
        "inscription": "institutional_facade",
        "trading":     "trading_floor",
        "floor":       "trading_floor",
        "ticker":      "market_data_display",
        "screen":      "market_data_display",
    },
    "policy_institutional": {
        "government":  "government_building",
        "parliament":  "government_building",
        "congress":    "government_building",
        "flag":        "government_building",
        "chamber":     "legislative_chamber",
        "legislature": "legislative_chamber",
        "plaza":       "empty_plaza",
        "steps":       "monumental_steps",
    },
    "markets_finance": {
        "atrium":    "financial_atrium",
        "tower":     "financial_atrium",
        "exchange":  "exchange_floor",
        "trading":   "exchange_floor",
        "terminal":  "data_terminal",
        "screen":    "data_terminal",
        "district":  "capital_flow_map",
        "skyline":   "capital_flow_map",
    },
}


def infer_concept_tag(category: str, main_subject: str) -> str:
    """
    Derive a concept_tag from category + main_subject using keyword matching.
    Returns "{category}_general" if no keyword matches.
    """
    subject_lower = main_subject.lower()
    for keyword, tag in _CONCEPT_KEYWORD_MAP.get(category, {}).items():
        if keyword in subject_lower:
            return tag
    return f"{category}_general"


# ── Variation resolver ────────────────────────────────────────────────────────

def resolve_variation_code(code: Optional[str]) -> Optional[str]:
    """
    Translate a variation code like 'B-2-ii-gamma' into readable prompt instructions.
    Returns None for empty, None, or malformed codes.
    Unknown component keys are silently skipped.
    """
    if not code:
        return None
    parts = [p.strip() for p in code.split("-")]
    if len(parts) != 4:
        return None
    comp_key, fg_key, bg_key, color_key = parts
    instructions = []
    if comp_key in COMPOSITION_PRESETS:
        instructions.append(f"Composition: {COMPOSITION_PRESETS[comp_key]}")
    if fg_key in FOREGROUND_PRESETS:
        instructions.append(f"Foreground hierarchy: {FOREGROUND_PRESETS[fg_key]}")
    if bg_key in BACKGROUND_PRESETS:
        instructions.append(f"Background density: {BACKGROUND_PRESETS[bg_key]}")
    if color_key in COLOR_PRESETS:
        instructions.append(f"Color emphasis: {COLOR_PRESETS[color_key]}")
    return "; ".join(instructions) if instructions else None


# ── Novelty suggestion ────────────────────────────────────────────────────────

def suggest_novelty_request(
    category: str,
    recent_history: List[Dict],
    escalation_level: int = 1,
    concept_tag_freq: Optional[Dict[str, int]] = None,
) -> str:
    """
    Generate a novelty request. Escalation levels 0–3:

    0 = minor composition tweaks (auto-applied on first generation if no manual novelty set)
    1 = composition + hierarchy change (first retry)
    2 = subject arrangement + metaphor shift; concept-aware if freq provided (second retry)
    3 = full conceptual shift — new metaphor, new structure, new environment (third retry)
    """
    n = len(recent_history)
    label = category.replace("_", " ")

    # Build concept avoidance clause from overused tags (threshold: appearing 3+ times)
    concept_clause = ""
    if concept_tag_freq:
        overused = [tag for tag, count in concept_tag_freq.items() if count >= 3]
        if overused:
            tag_list = " or ".join(f'"{t.replace("_", " ")}"' for t in overused[:3])
            concept_clause = (
                f" Explicitly avoid repeating visual metaphors such as {tag_list}."
            )

    if escalation_level == 0:
        return (
            f"Apply minor compositional variation relative to recent {label} images. "
            "Adjust framing, subject placement, or implied depth — keep the general metaphor."
        )
    if escalation_level == 1:
        return (
            f"Avoid repeating visual metaphors from the last {min(n, 4)} {label} images. "
            "Introduce a different foreground subject and spatial relationship."
            + concept_clause
        )
    if escalation_level == 2:
        return (
            f"Avoid resemblance to the last {min(n, 6)} {label} images. "
            "Change foreground object count, composition balance, and dominant visual metaphor. "
            "Use a different environmental setting and implied time of day."
            + concept_clause
        )
    # Level 3+
    return (
        f"Strong novelty required: avoid any resemblance to the last {min(n, 8)} {label} images "
        "and the 4 most recent global images across all categories. "
        "Use a completely different foreground subject, opposite compositional balance, "
        "new spatial hierarchy, and a distinct environmental context. "
        "If recent images used exterior settings, use interior. "
        "If recent images used horizontal framing, use strong vertical emphasis."
        + concept_clause
    )


# ── Main assembler ────────────────────────────────────────────────────────────

def build_image_prompt(
    category: str,
    main_subject: str,
    environment: str,
    composition: str,
    color_system: str,
    context: Optional[str] = None,
    novelty_request: Optional[str] = None,
    variation_code: Optional[str] = None,
) -> str:
    """
    Assemble the final image prompt.

    Block order (fixed — do not reorder):
        1. style_master    — fixed visual identity, subject placeholders filled
        2. category_block  — domain anchor for the editorial category
        3. context_block   — optional editorial context (headline, event)
        4. variation_block — optional variation code instructions
        5. novelty_block   — optional novelty directive (always last)
    """
    prompt = STYLE_MASTER.format(
        MAIN_SUBJECT=main_subject,
        ENVIRONMENT=environment,
        COMPOSITION=composition,
        COLOR_SYSTEM=color_system,
    )

    category_hint = CATEGORY_BLOCKS.get(category, "")
    if category_hint:
        prompt += f" {category_hint}."

    if context:
        prompt += f" Editorial context: {context}."

    variation_text = resolve_variation_code(variation_code)
    if variation_text:
        prompt += f" Variation instructions: {variation_text}."

    if novelty_request:
        prompt += f" Novelty directive: {novelty_request}"

    return prompt
```

- [ ] **Step 2.4: Run tests to confirm they pass**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_prompt_builder.py -v
```

Expected: all 24 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add lib/image_prompt_builder.py lib/tests/test_image_prompt_builder.py
git commit -m "feat: add image_prompt_builder with concept tagging and 0-3 escalation levels"
```

---

## Task 3: Image Similarity — Two-Phase, Image-Priority

**Files:**
- Create: `lib/image_similarity.py`
- Create: `lib/tests/test_image_similarity.py`
- Modify: `requirements.txt`

- [ ] **Step 3.1: Add new dependencies to requirements.txt**

Full updated `requirements.txt`:

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
```

- [ ] **Step 3.2: Install new dependencies**

```bash
cd D:/GitHub/News-Digest
pip install imagehash scikit-learn
```

Expected: both packages install successfully.

- [ ] **Step 3.3: Write failing tests**

Create `lib/tests/test_image_similarity.py`:

```python
# lib/tests/test_image_similarity.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lib.image_similarity import (
    compute_phash,
    phash_distance,
    compute_text_similarity,
    check_against_history,
)


def _make_png(path: str, r: int = 128, g: int = 128, b: int = 128) -> None:
    from PIL import Image
    Image.new("RGB", (8, 8), (r, g, b)).save(path)


# ── phash ─────────────────────────────────────────────────────────────────────

def test_compute_phash_returns_string(tmp_path):
    p = str(tmp_path / "img.png")
    _make_png(p)
    assert isinstance(compute_phash(p), str)


def test_compute_phash_identical_images_zero_distance(tmp_path):
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    _make_png(p1, 100, 100, 100)
    _make_png(p2, 100, 100, 100)
    assert phash_distance(compute_phash(p1), compute_phash(p2)) == 0


def test_compute_phash_different_images_nonzero_distance(tmp_path):
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    _make_png(p1, 0, 0, 0)
    _make_png(p2, 255, 255, 255)
    assert phash_distance(compute_phash(p1), compute_phash(p2)) > 0


def test_compute_phash_returns_none_for_missing_file():
    assert compute_phash("/nonexistent/img.png") is None


def test_phash_distance_returns_64_for_bad_input():
    assert phash_distance("not_a_hash", "also_bad") == 64


# ── Text similarity ───────────────────────────────────────────────────────────

def test_text_similarity_identical_returns_high():
    prompt = "oil refinery towers at dusk with industrial exhaust"
    assert compute_text_similarity(prompt, [prompt]) > 0.95


def test_text_similarity_unrelated_returns_low():
    prompt = "oil refinery towers at dusk with industrial exhaust"
    corpus = [
        "central bank stone columns empty plaza overcast sky",
        "shipping containers harbor crane silhouette sunset",
    ]
    assert compute_text_similarity(prompt, corpus) < 0.5


def test_text_similarity_empty_corpus_returns_zero():
    assert compute_text_similarity("some prompt", []) == 0.0


def test_text_similarity_uses_accepted_prompt_field():
    """check_against_history should prefer accepted_prompt over prompt_sent."""
    prompt = "oil refinery towers at dusk with amber glow"
    history = [{"accepted_prompt": prompt, "prompt_sent": "ignored", "image_phash": None}]
    result = check_against_history(prompt, None, history, [], text_threshold=0.82)
    assert result["text_similarity"] > 0.82


# ── Two-phase check_against_history ──────────────────────────────────────────

def test_check_no_history_not_flagged(tmp_path):
    p = str(tmp_path / "img.png")
    _make_png(p)
    result = check_against_history("some prompt", p, [], [])
    assert result["flagged"] is False
    assert result["text_similarity"] == 0.0


def test_check_image_flagged_in_category_phase(tmp_path):
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    _make_png(p1, 100, 100, 100)
    _make_png(p2, 100, 100, 100)
    h1 = compute_phash(p1)
    category_records = [{"accepted_prompt": "unrelated", "image_phash": h1}]
    result = check_against_history(
        "completely different prompt", p2, category_records, [], phash_threshold=8
    )
    assert result["image_flagged"] is True
    assert result["flagged"] is True
    assert result["rejection_reason"] == "phash_too_close_category"


def test_check_image_flagged_in_global_phase(tmp_path):
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    _make_png(p1, 100, 100, 100)
    _make_png(p2, 100, 100, 100)
    h1 = compute_phash(p1)
    global_records = [{"accepted_prompt": "unrelated", "image_phash": h1}]
    result = check_against_history(
        "completely different prompt", p2, [], global_records, phash_threshold=8
    )
    assert result["image_flagged"] is True
    assert result["rejection_reason"] == "phash_too_close_global"


def test_check_text_risky_does_not_cause_rejection(tmp_path):
    """High text similarity marks text_risky=True but flagged stays False (image drives rejection)."""
    p = str(tmp_path / "img.png")
    _make_png(p, 0, 0, 0)
    prompt = "oil refinery towers at dusk with amber glow and industrial exhaust"
    category_records = [{"accepted_prompt": prompt, "image_phash": None}]
    result = check_against_history(prompt, p, category_records, [], text_threshold=0.82)
    assert result["text_similarity"] > 0.82
    assert result["text_risky"] is True
    assert result["flagged"] is False  # image is the only rejection criterion


def test_check_dissimilar_image_not_flagged(tmp_path):
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    _make_png(p1, 0, 0, 0)
    _make_png(p2, 255, 255, 255)
    h1 = compute_phash(p1)
    category_records = [{"accepted_prompt": "central bank stone building", "image_phash": h1}]
    result = check_against_history(
        "shipping containers harbor crane",
        p2, category_records, [], text_threshold=0.82, phash_threshold=8,
    )
    assert result["flagged"] is False


def test_check_returns_new_phash(tmp_path):
    p = str(tmp_path / "img.png")
    _make_png(p)
    result = check_against_history("a prompt", p, [], [])
    assert "new_phash" in result
    assert isinstance(result["new_phash"], str)


def test_check_returns_separate_category_and_global_distances(tmp_path):
    p1, p2, p3 = (str(tmp_path / f"{x}.png") for x in "abc")
    _make_png(p1, 100, 100, 100)
    _make_png(p2, 200, 200, 200)
    _make_png(p3, 100, 100, 100)
    cat_records = [{"accepted_prompt": "x", "image_phash": compute_phash(p1)}]
    glob_records = [{"accepted_prompt": "y", "image_phash": compute_phash(p2)}]
    result = check_against_history("some prompt", p3, cat_records, glob_records)
    assert "category_min_phash_distance" in result
    assert "global_min_phash_distance" in result
```

- [ ] **Step 3.4: Run to confirm failure**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_similarity.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.image_similarity'`

- [ ] **Step 3.5: Implement `lib/image_similarity.py`**

```python
# lib/image_similarity.py
# ─────────────────────────────────────────────
#  Text similarity: TF-IDF cosine via scikit-learn.
#  Image similarity: perceptual hashing (phash) via imagehash.
#
#  Two-phase comparison:
#    Phase 1 — recent CATEGORY records (last 15 by default)
#    Phase 2 — recent GLOBAL records (last 50 by default)
#
#  Rejection logic:
#    phash distance < threshold (either phase) → image_flagged = True → flagged = True
#    text similarity > threshold               → text_risky = True  (not a rejection)
#
#  accepted_prompt field is preferred for text comparison;
#  falls back to revised_prompt, then prompt_sent.
# ─────────────────────────────────────────────

from typing import Dict, List, Optional

import numpy as np

DEFAULT_TEXT_THRESHOLD: float = 0.82
DEFAULT_PHASH_THRESHOLD: int = 8


def compute_phash(image_path: str) -> Optional[str]:
    """Compute perceptual hash for an image. Returns hex string or None on failure."""
    try:
        import imagehash
        from PIL import Image
        return str(imagehash.phash(Image.open(image_path)))
    except Exception as exc:
        print(f"  [similarity] phash failed for '{image_path}': {exc}")
        return None


def phash_distance(hash_a: str, hash_b: str) -> int:
    """
    Hamming distance between two phash hex strings.
    0 = identical, 64 = maximally different. Returns 64 on parse failure.
    """
    try:
        import imagehash
        return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
    except Exception:
        return 64


def compute_text_similarity(prompt: str, corpus: List[str]) -> float:
    """
    Maximum TF-IDF cosine similarity between `prompt` and any text in `corpus`.
    Returns 0.0 if corpus is empty.
    """
    if not corpus:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
        documents = [prompt] + corpus
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform(documents)
        sims = sk_cosine(matrix[0:1], matrix[1:]).flatten()
        return float(np.max(sims))
    except Exception as exc:
        print(f"  [similarity] text similarity error: {exc}")
        return 0.0


def _best_text(record: Dict) -> str:
    """Extract best available prompt text from a history record."""
    return (
        record.get("accepted_prompt")
        or record.get("revised_prompt")
        or record.get("prompt_sent")
        or ""
    )


def _min_phash_vs_records(new_phash: str, records: List[Dict]) -> int:
    """Return minimum Hamming distance between new_phash and all stored hashes."""
    min_dist = 64
    for r in records:
        stored = r.get("image_phash")
        if stored:
            min_dist = min(min_dist, phash_distance(new_phash, stored))
    return min_dist


def check_against_history(
    prompt: str,
    image_path: Optional[str],
    category_records: List[Dict],
    global_records: List[Dict],
    text_threshold: float = DEFAULT_TEXT_THRESHOLD,
    phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
) -> Dict:
    """
    Two-phase similarity check.

    Phase 1: compare against category_records (same category, last 15)
    Phase 2: compare against global_records (all categories, last 50)

    IMAGE similarity is the sole rejection criterion (flagged = image_flagged).
    TEXT similarity above threshold sets text_risky=True but does NOT reject.

    Returns:
        text_similarity          float  — max cosine vs all records combined
        text_risky               bool   — True if text_similarity > text_threshold
        category_min_phash_distance  int
        global_min_phash_distance    int
        min_phash_distance       int    — min of both phases
        image_similarity         float  — 1 - (min_phash_distance / 64)
        image_flagged            bool   — True if min_phash_distance < threshold
        rejection_reason         str|None — "phash_too_close_category" | "phash_too_close_global" | None
        flagged                  bool   — True only if image_flagged
        new_phash                str    — phash of the new image (if computed)
    """
    result: Dict = {
        "text_similarity": 0.0,
        "text_risky": False,
        "category_min_phash_distance": 64,
        "global_min_phash_distance": 64,
        "min_phash_distance": 64,
        "image_similarity": 0.0,
        "image_flagged": False,
        "rejection_reason": None,
        "flagged": False,
    }

    # Text similarity — combined corpus (category + global)
    all_records = category_records + global_records
    corpus = [_best_text(r) for r in all_records if _best_text(r)]
    if corpus:
        text_sim = compute_text_similarity(prompt, corpus)
        result["text_similarity"] = text_sim
        result["text_risky"] = text_sim > text_threshold

    # Perceptual hash — two-phase
    if image_path:
        new_phash = compute_phash(image_path)
        if new_phash:
            result["new_phash"] = new_phash

            cat_dist = _min_phash_vs_records(new_phash, category_records)
            glob_dist = _min_phash_vs_records(new_phash, global_records)
            result["category_min_phash_distance"] = cat_dist
            result["global_min_phash_distance"] = glob_dist
            result["min_phash_distance"] = min(cat_dist, glob_dist)
            result["image_similarity"] = 1.0 - (result["min_phash_distance"] / 64.0)

            if cat_dist < phash_threshold:
                result["image_flagged"] = True
                result["rejection_reason"] = "phash_too_close_category"
            elif glob_dist < phash_threshold:
                result["image_flagged"] = True
                result["rejection_reason"] = "phash_too_close_global"

    result["flagged"] = result["image_flagged"]
    return result
```

- [ ] **Step 3.6: Run tests to confirm they pass**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_similarity.py -v
```

Expected: all 17 tests pass.

- [ ] **Step 3.7: Commit**

```bash
git add lib/image_similarity.py lib/tests/test_image_similarity.py requirements.txt
git commit -m "feat: add image_similarity with two-phase comparison and image-priority rejection"
```

---

## Task 4: Image Generator — Orchestrator

**Files:**
- Create: `lib/image_generator.py`
- Create: `lib/tests/test_image_generator.py`

- [ ] **Step 4.1: Write failing tests**

Create `lib/tests/test_image_generator.py`:

```python
# lib/tests/test_image_generator.py
import base64
import io
import os
import sys
import sqlite3
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lib.image_generator import generate_editorial_image, _openai_images_api


def _fake_png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_gen(prompt, output_path):
    with open(output_path, "wb") as f:
        f.write(_fake_png_bytes())
    return {"image_path": output_path, "revised_prompt": "Revised: " + prompt[:30]}


# ── _openai_images_api ────────────────────────────────────────────────────────

def test_openai_images_api_saves_file(tmp_path):
    from unittest.mock import MagicMock
    out = str(tmp_path / "out.png")
    item = MagicMock()
    item.b64_json = base64.b64encode(_fake_png_bytes()).decode()
    item.revised_prompt = None
    resp = MagicMock()
    resp.data = [item]
    with patch("openai.OpenAI") as MockClient:
        MockClient.return_value.images.generate.return_value = resp
        result = _openai_images_api("Test prompt", out)
    assert os.path.exists(out)
    assert result["image_path"] == out


def test_openai_images_api_captures_revised_prompt(tmp_path):
    from unittest.mock import MagicMock
    out = str(tmp_path / "out.png")
    item = MagicMock()
    item.b64_json = base64.b64encode(_fake_png_bytes()).decode()
    item.revised_prompt = "Enhanced prompt"
    resp = MagicMock()
    resp.data = [item]
    with patch("openai.OpenAI") as MockClient:
        MockClient.return_value.images.generate.return_value = resp
        result = _openai_images_api("Test prompt", out)
    assert result["revised_prompt"] == "Enhanced prompt"


# ── generate_editorial_image ──────────────────────────────────────────────────

def test_returns_expected_keys(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="flat horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    for key in ("image_path", "prompt_sent", "revised_prompt", "accepted_prompt",
                "concept_tag", "similarity", "regeneration_count", "record_id"):
        assert key in result, f"Missing key: {key}"


def test_accepted_prompt_is_revised_when_available(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="flat horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    # _fake_gen always returns a revised_prompt, so accepted_prompt should equal it
    assert result["accepted_prompt"] == result["revised_prompt"]


def test_accepted_prompt_falls_back_to_prompt_sent_when_no_revised(tmp_path):
    db = str(tmp_path / "test.db")
    def gen_no_revised(prompt, output_path):
        with open(output_path, "wb") as f:
            f.write(_fake_png_bytes())
        return {"image_path": output_path, "revised_prompt": None}

    with patch("lib.image_generator._generate_image", side_effect=gen_no_revised):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="flat horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    assert result["accepted_prompt"] == result["prompt_sent"]


def test_concept_tag_is_inferred_and_stored(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="oil refinery towers at dusk", environment="horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    # "refinery" → "industrial_cluster"
    assert result["concept_tag"] == "industrial_cluster"
    # Verify stored in DB
    with sqlite3.connect(db) as conn:
        val = conn.execute("SELECT concept_tag FROM image_history").fetchone()[0]
    assert val == "industrial_cluster"


def test_concept_tag_manual_override(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="horizon",
            composition="wide shot", color_system="amber",
            concept_tag="capital_flow_map",
            db_path=db, output_dir=str(tmp_path),
        )
    assert result["concept_tag"] == "capital_flow_map"


def test_saves_generation_attempt_record(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="flat horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM generation_attempts").fetchone()[0]
    assert count >= 1


def test_accepted_attempt_has_accepted_true(tmp_path):
    db = str(tmp_path / "test.db")
    with patch("lib.image_generator._generate_image", side_effect=_fake_gen):
        generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="flat horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    with sqlite3.connect(db) as conn:
        accepted = conn.execute(
            "SELECT accepted FROM generation_attempts"
        ).fetchone()[0]
    assert accepted == 1


def test_accepts_on_first_attempt_with_no_history(tmp_path):
    db = str(tmp_path / "test.db")
    call_count = {"n": 0}
    def counting_gen(prompt, output_path):
        call_count["n"] += 1
        return _fake_gen(prompt, output_path)
    with patch("lib.image_generator._generate_image", side_effect=counting_gen):
        result = generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="horizon",
            composition="wide shot", color_system="amber",
            db_path=db, output_dir=str(tmp_path),
        )
    assert call_count["n"] == 1
    assert result["regeneration_count"] == 0


def test_force_novelty_level_passed_through(tmp_path):
    """force_novelty_level should set escalation from the first attempt."""
    db = str(tmp_path / "test.db")
    seen_prompts = []
    def capture_gen(prompt, output_path):
        seen_prompts.append(prompt)
        return _fake_gen(prompt, output_path)
    with patch("lib.image_generator._generate_image", side_effect=capture_gen):
        generate_editorial_image(
            issue_date="2026-04-15", story_slug="energy-test", category="energy",
            main_subject="refinery towers", environment="horizon",
            composition="wide shot", color_system="amber",
            force_novelty_level=3,
            db_path=db, output_dir=str(tmp_path),
        )
    # Level 3 novelty should appear in the first prompt
    assert "Strong novelty required" in seen_prompts[0] or "novelty" in seen_prompts[0].lower()
```

- [ ] **Step 4.2: Run to confirm failure**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_generator.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.image_generator'`

- [ ] **Step 4.3: Implement `lib/image_generator.py`**

```python
# lib/image_generator.py
# ─────────────────────────────────────────────
#  Editorial image generation with deduplication.
#
#  Flow per attempt:
#    1. Build prompt (with current novelty + variation)
#    2. Generate via OpenAI (Responses API -> Images API fallback)
#    3. Compute accepted_prompt = revised_prompt or prompt_sent
#    4. Two-phase similarity check (category, then global)
#    5. Save attempt record (accepted or rejected)
#    6. If image_flagged: escalate novelty, increment regeneration_count, retry
#    7. On acceptance: save/update image_history record; link attempt to it
# ─────────────────────────────────────────────

import base64
import os
from collections import Counter
from typing import Any, Dict, Optional

from lib.image_prompt_builder import (
    PROMPT_MASTER_VERSION,
    build_image_prompt,
    infer_concept_tag,
    suggest_novelty_request,
)
from lib.image_history_store import (
    get_recent_by_category,
    get_recent_global,
    init_db,
    save_attempt_record,
    save_record,
    update_attempt_parent,
    update_record,
)
from lib.image_similarity import check_against_history

DEFAULT_MAX_RETRIES: int = 3
DEFAULT_TEXT_THRESHOLD: float = 0.82
DEFAULT_PHASH_THRESHOLD: int = 8
_DEFAULT_OUTPUT_DIR: str = "generated_images"


def _openai_responses_api(prompt: str, output_path: str) -> Dict[str, Any]:
    """Generate image via OpenAI Responses API. Captures revised_prompt."""
    import openai
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.responses.create(
        model=os.environ.get("OPENAI_RESPONSES_MODEL", "gpt-4o"),
        input=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        tools=[{
            "type": "image_generation",
            "size": os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024"),
            "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        }],
    )
    image_data = revised_prompt = None
    for item in response.output:
        if getattr(item, "type", None) == "image_generation_call":
            image_data = item.result
            revised_prompt = getattr(item, "revised_prompt", None)
            break
    if not image_data:
        raise RuntimeError("Responses API returned no image data.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_data))
    return {"image_path": output_path, "revised_prompt": revised_prompt}


def _openai_images_api(prompt: str, output_path: str) -> Dict[str, Any]:
    """Generate image via OpenAI Images API. revised_prompt available for dall-e-3."""
    import openai
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.images.generate(
        model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt,
        size=os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024"),
        quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        n=1,
        response_format="b64_json",
    )
    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("Images API returned empty image data.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(b64))
    return {
        "image_path": output_path,
        "revised_prompt": getattr(response.data[0], "revised_prompt", None),
    }


def _generate_image(prompt: str, output_path: str) -> Dict[str, Any]:
    """Try Responses API; fall back to Images API. Controlled by OPENAI_USE_RESPONSES_API."""
    if os.environ.get("OPENAI_USE_RESPONSES_API", "true").lower() == "true":
        try:
            return _openai_responses_api(prompt, output_path)
        except Exception as exc:
            print(f"  [image_generator] Responses API failed ({exc}); falling back.")
    return _openai_images_api(prompt, output_path)


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
    force_novelty_level: if set, applies that escalation level from attempt 0.

    Retries up to max_retries when image phash is too close to recent images.
    Text similarity above threshold marks text_risky but does NOT trigger retry.

    Returns: image_path, prompt_sent, revised_prompt, accepted_prompt, concept_tag,
             variation_code, novelty_request, similarity (dict),
             regeneration_count, record_id
    """
    init_db(db_path)
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # Resolve concept tag
    resolved_concept_tag = concept_tag or infer_concept_tag(category, main_subject)

    # Load recent history for deduplication
    recent_category = get_recent_by_category(category, limit=15, db_path=db_path)
    recent_global = get_recent_global(limit=50, db_path=db_path)

    # Compute concept tag frequency for concept-aware novelty
    concept_tag_freq = dict(
        Counter(r.get("concept_tag") for r in recent_category if r.get("concept_tag"))
    )

    current_novelty = novelty_request
    regeneration_count = 0
    record_id: Optional[int] = None

    # If force_novelty_level set and no manual novelty_request, pre-inject escalated directive
    if force_novelty_level is not None and current_novelty is None:
        current_novelty = suggest_novelty_request(
            category, recent_category,
            escalation_level=force_novelty_level,
            concept_tag_freq=concept_tag_freq,
        )

    for attempt in range(max_retries + 1):
        prompt = build_image_prompt(
            category=category,
            main_subject=main_subject,
            environment=environment,
            composition=composition,
            color_system=color_system,
            context=context,
            novelty_request=current_novelty,
            variation_code=variation_code,
        )

        slug_safe = story_slug.replace("/", "_").replace(" ", "_")[:60]
        attempt_suffix = f"_r{attempt}" if attempt > 0 else ""
        output_path = os.path.join(out_dir, f"{issue_date}_{slug_safe}{attempt_suffix}.png")

        print(f"  [image_generator] Attempt {attempt + 1}/{max_retries + 1}: {os.path.basename(output_path)}")

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
            escalation = min(attempt + 1, 3)
            current_novelty = suggest_novelty_request(
                category, recent_category, escalation, concept_tag_freq
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

            # Save or update image_history record
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
                    "variation_code": variation_code,
                    "novelty_request": current_novelty,
                    "image_path": image_path,
                    "image_phash": sim.get("new_phash"),
                    "similarity_score_text": sim["text_similarity"],
                    "similarity_score_image": sim["image_similarity"],
                    "regeneration_count": regeneration_count,
                }, db_path=db_path)
            else:
                update_record(record_id, {
                    "image_path": image_path,
                    "image_phash": sim.get("new_phash"),
                    "accepted_prompt": accepted_prompt,
                    "similarity_score_text": sim["text_similarity"],
                    "similarity_score_image": sim["image_similarity"],
                    "regeneration_count": regeneration_count,
                    "revised_prompt": revised_prompt,
                }, db_path=db_path)

            update_attempt_parent(attempt_id, record_id, db_path=db_path)

            return {
                "image_path": image_path,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "similarity": sim,
                "regeneration_count": regeneration_count,
                "record_id": record_id,
            }

        # Image too similar — escalate and retry
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
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "image_path": image_path,
                "image_phash": sim.get("new_phash"),
                "similarity_score_text": sim["text_similarity"],
                "similarity_score_image": sim["image_similarity"],
                "regeneration_count": regeneration_count,
            }, db_path=db_path)
            update_attempt_parent(attempt_id, record_id, db_path=db_path)

        escalation = min(attempt + 2, 3)
        current_novelty = suggest_novelty_request(
            category, recent_category, escalation, concept_tag_freq
        )
        regeneration_count += 1
        print(
            f"  [image_generator] Rejected ({sim['rejection_reason']}). "
            f"Escalating to level {escalation}."
        )

    raise RuntimeError("[image_generator] Generation loop exited unexpectedly.")
```

- [ ] **Step 4.4: Run tests to confirm they pass**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/test_image_generator.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add lib/image_generator.py lib/tests/test_image_generator.py
git commit -m "feat: add image_generator with accepted_prompt, concept_tag, attempt tracking, and 0-3 escalation"
```

---

## Task 5: CLI Script

**Files:**
- Create: `scripts/generate_editorial_image.py`

- [ ] **Step 5.1: Implement CLI**

```python
# scripts/generate_editorial_image.py
# ─────────────────────────────────────────────
#  CLI for the editorial image generation + deduplication subsystem.
#
#  Usage (from repo root):
#    python scripts/generate_editorial_image.py \
#      --issue-date 2026-04-15 \
#      --story-slug mexico-energy-reform \
#      --category energy \
#      --main-subject "oil refinery towers at dusk" \
#      --environment "flat industrial horizon, overcast sky" \
#      --composition "wide establishing shot, subject dominant left" \
#      --color-system "warm amber-rust tones on metal"
#
#  Optional flags:
#    --context             Editorial context (headline, event)
#    --novelty-request     Manual novelty directive
#    --variation-code      e.g. B-2-ii-gamma
#    --concept-tag         Override inferred concept tag
#    --force-novelty-level {0,1,2,3}  Apply escalation from first attempt
#    --max-retries         Default 3
#    --output-dir          Directory for generated PNGs
#    --db-path             SQLite DB path
#    --dry-run             Print full prompt breakdown; skip generation
#    --show-similarity-debug  Print per-phase similarity scores after generation
#    --list-presets        Print category presets and exit
# ─────────────────────────────────────────────

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def cmd_list_presets() -> None:
    from lib.image_prompt_builder import CATEGORY_PRESETS
    print("\n── Category presets ────────────────────────────────────────────────\n")
    for cat, preset in CATEGORY_PRESETS.items():
        print(f"[{cat}]")
        for k, v in preset.items():
            print(f"  --{k.replace('_', '-')}: {v}")
        print()


def cmd_dry_run(args) -> None:
    from lib.image_prompt_builder import (
        build_image_prompt,
        infer_concept_tag,
        resolve_variation_code,
        suggest_novelty_request,
    )
    from lib.image_history_store import get_recent_by_category

    resolved_concept_tag = args.concept_tag or infer_concept_tag(args.category, args.main_subject)
    variation_text = resolve_variation_code(args.variation_code)

    # Load comparison candidate count (if DB exists)
    candidate_count = 0
    try:
        db_path = args.db_path or None
        records = get_recent_by_category(args.category, limit=15, db_path=db_path)
        candidate_count = len(records)
    except Exception:
        pass

    # Resolve novelty: use manual if provided, else suggest at force_novelty_level
    novelty = args.novelty_request
    if novelty is None and args.force_novelty_level is not None:
        novelty = suggest_novelty_request(
            args.category, [], escalation_level=args.force_novelty_level
        )

    prompt = build_image_prompt(
        category=args.category,
        main_subject=args.main_subject,
        environment=args.environment,
        composition=args.composition,
        color_system=args.color_system,
        context=args.context,
        novelty_request=novelty,
        variation_code=args.variation_code,
    )

    print("\n── Dry-run breakdown ───────────────────────────────────────────────\n")
    print(f"Category:            {args.category}")
    print(f"Concept tag:         {resolved_concept_tag}")
    if variation_text:
        print(f"Variation resolved:  {variation_text}")
    if novelty:
        print(f"Novelty directive:   {novelty}")
    print(f"Comparison candidates (category): {candidate_count}")
    print(f"Text threshold:      {args.text_threshold}")
    print(f"Phash threshold:     {args.phash_threshold}")
    print(f"\nFull prompt ({len(prompt)} chars):\n")
    print(prompt)


def cmd_generate(args) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from lib.image_generator import generate_editorial_image

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
        force_novelty_level=args.force_novelty_level,
        max_retries=args.max_retries,
        text_threshold=args.text_threshold,
        phash_threshold=args.phash_threshold,
        output_dir=args.output_dir,
        db_path=args.db_path,
    )

    printable = {k: v for k, v in result.items() if k != "similarity"}
    print("\n── Result ──────────────────────────────────────────────────────────")
    print(json.dumps(printable, indent=2, ensure_ascii=False))

    if args.show_similarity_debug:
        sim = result["similarity"]
        print("\n── Similarity debug ────────────────────────────────────────────────")
        print(f"  text_similarity:              {sim['text_similarity']:.4f}")
        print(f"  text_risky:                   {sim['text_risky']}")
        print(f"  category_min_phash_distance:  {sim['category_min_phash_distance']}")
        print(f"  global_min_phash_distance:    {sim['global_min_phash_distance']}")
        print(f"  min_phash_distance:           {sim['min_phash_distance']}")
        print(f"  image_flagged:                {sim['image_flagged']}")
        print(f"  rejection_reason:             {sim.get('rejection_reason')}")
    else:
        sim = result["similarity"]
        print(
            f"\nSimilarity: text={sim['text_similarity']:.3f} "
            f"(risky={sim['text_risky']}), "
            f"phash_dist={sim['min_phash_distance']}, "
            f"image_flagged={sim['image_flagged']}"
        )

    print(f"Concept tag:          {result['concept_tag']}")
    print(f"Regenerations used:   {result['regeneration_count']}")
    print(f"Saved to:             {result['image_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deduplicated editorial image for a newsletter issue.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--list-presets", action="store_true",
                        help="Print category preset suggestions and exit.")

    # Required for generation
    parser.add_argument("--issue-date",   help="Issue date YYYY-MM-DD")
    parser.add_argument("--story-slug",   help="Short slug identifying the story")
    parser.add_argument("--category",     help="Category (energy, macro_inflation, etc.)")
    parser.add_argument("--main-subject", help="Main subject description")
    parser.add_argument("--environment",  help="Environment/setting description")
    parser.add_argument("--composition",  help="Composition instruction")
    parser.add_argument("--color-system", help="Color accent system description")

    # Optional generation parameters
    parser.add_argument("--context",               default=None)
    parser.add_argument("--novelty-request",       default=None)
    parser.add_argument("--variation-code",        default=None)
    parser.add_argument("--concept-tag",           default=None,
                        help="Override inferred concept tag")
    parser.add_argument("--force-novelty-level",   type=int, default=None,
                        choices=[0, 1, 2, 3],
                        help="Apply this escalation level from attempt 0")
    parser.add_argument("--max-retries",           type=int, default=3)
    parser.add_argument("--text-threshold",        type=float, default=0.82,
                        help="Text similarity threshold (default 0.82)")
    parser.add_argument("--phash-threshold",       type=int, default=8,
                        help="Phash distance threshold (default 8)")
    parser.add_argument("--output-dir",            default=None)
    parser.add_argument("--db-path",               default=None)
    parser.add_argument("--dry-run",               action="store_true",
                        help="Print full prompt breakdown; skip API call")
    parser.add_argument("--show-similarity-debug", action="store_true",
                        help="Print per-phase similarity scores after generation")

    args = parser.parse_args()

    if args.list_presets:
        cmd_list_presets()
        return

    # Fill defaults for dry-run if some required fields are missing
    if args.dry_run:
        args.category     = args.category     or "energy"
        args.main_subject = args.main_subject or "[MAIN SUBJECT]"
        args.environment  = args.environment  or "[ENVIRONMENT]"
        args.composition  = args.composition  or "[COMPOSITION]"
        args.color_system = args.color_system or "[COLOR SYSTEM]"
        cmd_dry_run(args)
        return

    required = ["issue_date", "story_slug", "category", "main_subject",
                "environment", "composition", "color_system"]
    missing = [f"--{r.replace('_', '-')}" for r in required if not getattr(args, r, None)]
    if missing:
        parser.error(f"Required: {', '.join(missing)}")

    cmd_generate(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.2: Smoke test dry-run**

```bash
cd D:/GitHub/News-Digest
python scripts/generate_editorial_image.py \
  --category energy \
  --main-subject "oil refinery towers at dusk" \
  --environment "flat industrial horizon" \
  --composition "wide establishing shot" \
  --color-system "amber-rust on metal" \
  --variation-code "B-2-ii-gamma" \
  --force-novelty-level 2 \
  --dry-run
```

Expected output sections: `Category`, `Concept tag`, `Variation resolved`, `Novelty directive`, `Comparison candidates`, `Text threshold`, `Phash threshold`, then `Full prompt`.

- [ ] **Step 5.3: Smoke test --list-presets**

```bash
cd D:/GitHub/News-Digest
python scripts/generate_editorial_image.py --list-presets
```

Expected: six blocks printed with `--main-subject`, `--environment`, etc.

- [ ] **Step 5.4: Commit**

```bash
git add scripts/generate_editorial_image.py
git commit -m "feat: add CLI with force-novelty-level, show-similarity-debug, and enhanced dry-run"
```

---

## Task 6: Full Test Suite + requirements.txt

- [ ] **Step 6.1: Run all lib tests**

```bash
cd D:/GitHub/News-Digest
python -m pytest lib/tests/ -v
```

Expected: ~65 tests pass across the four test files.

- [ ] **Step 6.2: Verify existing bot tests unaffected**

```bash
cd D:/GitHub/News-Digest
python -m pytest bot/tests/ -v 2>&1 | tail -10
```

Expected: same result as before this feature.

- [ ] **Step 6.3: Commit requirements.txt**

```bash
git add requirements.txt
git commit -m "chore: add imagehash and scikit-learn to requirements"
```

---

## Task 7: README

**Files:**
- Create: `README-image-generation.md`

- [ ] **Step 7.1: Create the README**

```markdown
# Editorial Image Generation — README

A self-contained subsystem for **The Opening Bell** newsletter that generates editorial images
with automatic deduplication across issues, using perceptual hashing and prompt similarity.

---

## Overview

The system prevents repeated images by:
1. **Concept tagging** — each image is tagged with a visual metaphor label (e.g. `industrial_cluster`). Overused tags are detected and avoided in novelty directives.
2. **Two-phase image similarity** — phash compared against recent same-category images (last 15) then all recent global images (last 50). Only image similarity triggers rejection.
3. **Text monitoring** — TF-IDF cosine similarity flags risky prompts but does not reject on its own. The `accepted_prompt` (revised_prompt when available) is always used for comparison.
4. **Automatic escalation** — levels 0–3. Level 0 = minor tweak; level 3 = full conceptual shift. Escalation advances on each failed attempt.
5. **Attempt tracking** — every API call is logged in `generation_attempts` with accepted/rejected status and rejection reason.

---

## File Structure

```
lib/
  image_prompt_builder.py   # Prompt assembly, variation resolver, concept tagging, escalation 0-3
  image_history_store.py    # SQLite: image_history + generation_attempts tables
  image_similarity.py       # Two-phase phash + TF-IDF comparison
  image_generator.py        # Full pipeline orchestrator
  tests/                    # ~65 tests

scripts/
  generate_editorial_image.py

data/
  image_history.db          # Auto-created on first run
```

---

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
```

Or use `bot/.env` (never commit):

```
OPENAI_API_KEY=sk-...
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | required | OpenAI key |
| `OPENAI_USE_RESPONSES_API` | `true` | Use Responses API (gpt-4o); `false` = Images API only |
| `OPENAI_RESPONSES_MODEL` | `gpt-4o` | Model for Responses API |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | Model for Images API fallback |
| `OPENAI_IMAGE_SIZE` | `1024x1024` | Image dimensions |
| `OPENAI_IMAGE_QUALITY` | `medium` | `low` / `medium` / `high` |
| `IMAGE_HISTORY_DB` | `data/image_history.db` | SQLite path |

---

## Usage

### Generate

```bash
python scripts/generate_editorial_image.py \
  --issue-date 2026-04-15 \
  --story-slug mexico-energy-reform \
  --category energy \
  --main-subject "oil refinery towers and storage tanks at dusk" \
  --environment "flat industrial horizon, overcast sky, distant gas flares" \
  --composition "wide establishing shot, subject dominant left, open sky right" \
  --color-system "warm amber-rust tones on metal surfaces, cool gray background"
```

### Dry-run (no API call)

```bash
python scripts/generate_editorial_image.py \
  --category energy \
  --main-subject "refinery towers" \
  --environment "flat horizon" \
  --composition "wide shot" \
  --color-system "amber" \
  --variation-code "B-2-ii-gamma" \
  --force-novelty-level 2 \
  --dry-run
```

Prints: category, concept tag, variation resolved, novelty directive, comparison candidate count, thresholds, and full prompt.

### Debug similarity scores

```bash
python scripts/generate_editorial_image.py ... --show-similarity-debug
```

Prints: `text_similarity`, `text_risky`, `category_min_phash_distance`, `global_min_phash_distance`, `image_flagged`, `rejection_reason`.

### List presets

```bash
python scripts/generate_editorial_image.py --list-presets
```

### Force novelty from the start

```bash
python scripts/generate_editorial_image.py ... --force-novelty-level 3
```

Level 3 = conceptual shift directive injected into the first prompt (no prior failure needed).

---

## Variation Codes

```
Format: [COMPOSITION]-[FOREGROUND]-[BACKGROUND]-[COLOR]

COMPOSITION: A=centered, B=asymmetric-left, C=asymmetric-right, D=diagonal, E=split-frame
FOREGROUND:  1=single dominant, 2=dual tension, 3=scattered, 4=frame-within-frame
BACKGROUND:  i=minimal, ii=moderate, iii=rich, iv=complex
COLOR:       alpha=warm earth, beta=cool steel, gamma=desaturated, delta=sepia, epsilon=graphite+one accent
```

---

## How Novelty and Regeneration Work

1. Prompt built from fixed style master + variable blocks (novelty/variation always last)
2. `accepted_prompt = revised_prompt or prompt_sent` — used for all text comparisons
3. Image compared against category history (phash) — if too close, rejected immediately
4. If still not rejected, image compared against global history (phash)
5. Text similarity is measured but only marks `text_risky = True`, never rejects
6. On rejection: escalate novelty level (0→1→2→3), regenerate, retry
7. Concept tags on overused metaphors are injected into the novelty directive at level 2+

---

## Thresholds

CLI flags: `--text-threshold 0.75 --phash-threshold 12`

Or in Python:

```python
from lib.image_generator import generate_editorial_image
result = generate_editorial_image(..., text_threshold=0.75, phash_threshold=12, max_retries=5)
```

---

## Database Schema

`image_history` — one row per accepted generation:

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Auto PK |
| created_at | TEXT | ISO 8601 UTC |
| issue_date | TEXT | YYYY-MM-DD |
| story_slug | TEXT | |
| category | TEXT | |
| prompt_master_version | TEXT | |
| prompt_sent | TEXT | Full assembled prompt |
| revised_prompt | TEXT | From API when available |
| accepted_prompt | TEXT | revised_prompt or prompt_sent |
| variation_code | TEXT | |
| novelty_request | TEXT | |
| concept_tag | TEXT | e.g. industrial_cluster |
| image_path | TEXT | |
| image_phash | TEXT | Hex string |
| similarity_score_text | REAL | Max TF-IDF cosine |
| similarity_score_image | REAL | Normalized (0-1) |
| regeneration_count | INTEGER | Retries before acceptance |
| notes | TEXT | |

`generation_attempts` — one row per API call (including rejected):

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Auto PK |
| parent_image_id | INTEGER | FK to image_history (nullable until accepted) |
| created_at | TEXT | |
| prompt_sent | TEXT | |
| revised_prompt | TEXT | |
| accepted | INTEGER | 0 or 1 |
| rejection_reason | TEXT | phash_too_close_category / phash_too_close_global / generation_error |
| image_phash | TEXT | |
| similarity_score_text | REAL | |
| similarity_score_image | REAL | |

---

## Why concept_tag improves long-term diversity

Without concept tags, the system can only detect visual similarity in already-generated images. With tags, it detects *semantic* repetition earlier: if `industrial_cluster` appears in 4 of the last 6 energy images, the novelty directive at level 2+ explicitly names it and instructs the model to avoid it — before generation even happens. This shifts diversity enforcement from reactive (reject after generation) to partially proactive (steer the prompt away from overused metaphors), reducing wasted API calls and improving visual variety across weeks of consecutive issues.

---

## Why Python?

Python is the right choice: all existing project code is Python, the key libraries (`imagehash`, `scikit-learn`, `Pillow`, `openai`) are mature with no meaningful TypeScript equivalents, and the subsystem integrates cleanly with the existing `bot/` pipeline when that time comes. SQLite + stdlib means zero new infrastructure.
```

- [ ] **Step 7.2: Commit**

```bash
git add README-image-generation.md
git commit -m "docs: add README for image generation deduplication subsystem"
```

---

## Self-Review Against Spec

| Requirement | Task |
|-------------|------|
| `accepted_prompt` field (DB + logic) | T1 schema, T4 generator |
| `concept_tag` field (DB + inference + manual) | T1, T2 `infer_concept_tag()`, T4 |
| `generation_attempts` secondary table | T1 |
| `save_attempt_record()` + `update_attempt_parent()` | T1 |
| Two-phase similarity (category 15, global 50) | T3 `check_against_history()` |
| Image similarity = primary rejection criterion | T3 `flagged = image_flagged` |
| Text similarity = risky only, not rejection | T3 `text_risky`, T4 |
| `accepted_prompt` used for text comparison | T3 `_best_text()` prefers `accepted_prompt` |
| Concept-aware `suggest_novelty_request()` | T2 `concept_tag_freq` param |
| Escalation levels 0–3 | T2 `suggest_novelty_request()`, T4 loop |
| `--force-novelty-level {0,1,2,3}` CLI flag | T5 |
| `--show-similarity-debug` CLI flag | T5 |
| `--max-retries` CLI flag | T5 |
| Enhanced dry-run output (7 fields) | T5 `cmd_dry_run()` |
| `accepted_prompt` at end of prompt | T2 block order unchanged |
| Configurable text + phash thresholds | T3 defaults, T4+T5 kwargs/flags |
| `rejection_reason` in attempt records | T1 schema, T3 return dict, T4 |
| No breaking changes to existing bot/ | T1–T5 (lib/ is fully isolated) |
| README | T7 |

**Placeholder scan:** None found.

**Type consistency:** `check_against_history(prompt, image_path, category_records, global_records, ...)` — signature consistent across T3 impl, T3 tests, T4 call site. `suggest_novelty_request(category, history, escalation_level, concept_tag_freq=None)` — consistent across T2 impl, T2 tests, T4 call sites. `save_attempt_record()` / `update_attempt_parent()` — consistent across T1 impl, T1 tests, T4 call sites.
