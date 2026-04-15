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
