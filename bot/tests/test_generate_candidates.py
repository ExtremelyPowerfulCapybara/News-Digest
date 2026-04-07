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

        # Pre-create the candidate files on disk
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

        # Force-run (no hero_image_candidates in digest, so guard 2 is bypassed)
        _load_and_run("2026-04-07", digests_dir, tmp, token="", chat_id="")

        with open(digest_path, encoding="utf-8") as f:
            saved = json.load(f)

        # Counters come from the existing state, not reset
        assert saved["visual"]["hero_generation_round"] == 2
        assert saved["visual"]["hero_regenerations_used"] == 1
