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
    import numpy as np
    from PIL import Image

    # Checkerboard pattern — alternating black/white pixels
    arr1 = np.zeros((64, 64, 3), dtype=np.uint8)
    for i in range(64):
        for j in range(64):
            if (i + j) % 2 == 0:
                arr1[i, j] = [255, 255, 255]
    p1 = str(tmp_path / "checker.png")
    Image.fromarray(arr1).save(p1)

    # Uniform gray — completely flat, structurally opposite of checkerboard
    arr2 = np.full((64, 64, 3), 128, dtype=np.uint8)
    p2 = str(tmp_path / "gray.png")
    Image.fromarray(arr2).save(p2)

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
