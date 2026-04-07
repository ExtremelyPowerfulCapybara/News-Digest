# bot/tests/test_image_candidates.py
import os
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from image_candidates import generate_image, generate_image_candidates


def test_generate_image_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "test.png")
        generate_image("test prompt", out)
        assert os.path.exists(out), "generate_image must create the output file"
        assert os.path.getsize(out) > 0, "Output file must not be empty"


def test_generate_image_candidates_creates_three_files():
    visual = {
        "hero_options": {
            "opt1": "prompt one",
            "opt2": "prompt two",
            "opt3": "prompt three",
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_image_candidates("2026-04-07", visual, tmp, round_num=1)
        assert set(result.keys()) == {"opt1", "opt2", "opt3"}
        for key, path in result.items():
            assert os.path.exists(path), f"{key} file must exist at {path}"
            assert os.path.basename(path) == f"r1_{key}.png"


def test_generate_image_candidates_creates_nested_directory():
    visual = {"hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"}}
    with tempfile.TemporaryDirectory() as tmp:
        project_root = os.path.join(tmp, "project_does_not_exist_yet")
        generate_image_candidates("2026-04-07", visual, project_root)
        expected = os.path.join(project_root, "tmp_images", "2026-04-07")
        assert os.path.isdir(expected)


def test_generate_image_candidates_round2_filenames():
    visual = {"hero_options": {"opt1": "p1", "opt2": "p2", "opt3": "p3"}}
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_image_candidates("2026-04-07", visual, tmp, round_num=2)
        for key, path in result.items():
            assert os.path.basename(path) == f"r2_{key}.png"


def test_generate_image_candidates_raises_on_missing_hero_options():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="hero_options"):
            generate_image_candidates("2026-04-07", {}, tmp)


def test_generate_image_candidates_raises_on_empty_hero_options():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="hero_options"):
            generate_image_candidates("2026-04-07", {"hero_options": {}}, tmp)
