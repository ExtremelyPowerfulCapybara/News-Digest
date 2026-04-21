import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Repo root (for lib imports) and bot/ (for image_gen + prompt_map imports)
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_BOT  = os.path.join(_ROOT, "bot")
sys.path.insert(0, os.path.abspath(_ROOT))
sys.path.insert(0, os.path.abspath(_BOT))

from image_gen import generate_hero_image

MINIMAL_DIGEST = {
    "es": {
        "stories": [{"tag": "Macro", "headline": "Test headline"}],
        "sentiment": {"label_en": "Cautious"},
    },
    "en": {
        "stories": [{"tag": "Macro", "headline": "Test headline EN"}],
        "sentiment": {"label_en": "Cautious"},
    },
}


def test_skip_image_env_returns_visual_without_hero_image(tmp_path):
    """When SKIP_IMAGE=true, generation is skipped and hero_image is absent."""
    with patch.dict(os.environ, {"SKIP_IMAGE": "true"}):
        visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert "hero_image" not in visual
    assert visual["hero_category"] == "Macro"


def test_successful_generation_sets_hero_image_url(tmp_path):
    """On success, hero_image is set to the public URL."""
    fake_result = {
        "image_path": str(tmp_path / "2026-04-21_hero.png"),
        "prompt_sent": "prompt",
        "revised_prompt": None,
        "accepted_prompt": "prompt",
        "concept_tag": "institutional",
        "subject_family": None,
        "composition_preset": None,
        "variation_code": None,
        "novelty_request": None,
        "similarity": {},
        "regeneration_count": 0,
        "record_id": 1,
    }
    with patch.dict(os.environ, {"SKIP_IMAGE": "false"}):
        with patch("lib.image_generator.generate_editorial_image", return_value=fake_result):
            with patch("config.ASSET_BASE_URL", "https://raw.example.com/"):
                visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert visual.get("hero_image") == "https://raw.example.com/images/2026-04-21_hero.png"


def test_generation_exception_returns_visual_without_hero_image(tmp_path):
    """If generate_editorial_image raises, hero_image is absent but function does not crash."""
    with patch.dict(os.environ, {"SKIP_IMAGE": "false"}):
        with patch("lib.image_generator.generate_editorial_image", side_effect=RuntimeError("API down")):
            visual = generate_hero_image(MINIMAL_DIGEST, "2026-04-21", output_dir=str(tmp_path))
    assert "hero_image" not in visual
    assert "hero_category" in visual


def test_tag_to_preset_mapping(tmp_path):
    """Each story tag maps to the correct CATEGORY_PRESETS key."""
    expected = {
        "Energía":  "energy",
        "Política": "policy_institutional",
        "Mercados": "markets_finance",
        "Comercio": "trade_supply_chain",
        "Macro":    "macro_inflation",
        "FX":       "macro_inflation",
        "Tasas":    "macro_inflation",
        "México":   "macro_inflation",
        "Unknown":  "macro_inflation",
    }
    from image_gen import TAG_TO_PRESET
    for tag, preset_key in expected.items():
        assert TAG_TO_PRESET.get(tag, "macro_inflation") == preset_key, f"Failed for tag={tag}"
