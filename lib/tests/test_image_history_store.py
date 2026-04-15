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
    assert count == 3  # image_history + generation_attempts + sqlite_sequence


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
