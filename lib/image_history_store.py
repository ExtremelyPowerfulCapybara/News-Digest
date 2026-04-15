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
