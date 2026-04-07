# tests/test_visual.py
import pytest
from image_gen import generate_hero_prompt
from prompt_map import PROMPT_TEMPLATES

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_DIGEST = {
    "es": {
        "stories": [
            {
                "tag": "Energía",
                "headline": "El petróleo supera los 106 dólares",
                "body": "Cuerpo.",
                "url": "https://example.com/1",
                "source": "El Financiero",
            }
        ],
        "sentiment": {
            "label_es": "Aversión al Riesgo",
            "label_en": "Risk-Off",
            "position": 22,
            "context_es": "Contexto.",
            "context_en": "Context.",
        },
        "editor_note": "Nota.",
        "narrative_thread": "Hilo.",
        "quote": {"text": "Quote.", "attribution": "Author, 2026"},
    },
    "en": {
        "stories": [
            {
                "tag": "Energía",
                "headline": "Oil surpasses $106",
                "body": "Body.",
                "url": "https://example.com/1",
                "source": "El Financiero",
            }
        ],
        "sentiment": {
            "label_es": "Aversión al Riesgo",
            "label_en": "Risk-Off",
            "position": 22,
            "context_es": "Contexto.",
            "context_en": "Context.",
        },
        "editor_note": "Note.",
        "narrative_thread": "Thread.",
        "quote": {"text": "Quote.", "attribution": "Author, 2026"},
    },
}

# ── generate_hero_prompt ──────────────────────────────────────────────────────

def test_returns_all_required_fields():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert set(result.keys()) == {
        "hero_category",
        "hero_category_source",
        "hero_prompt_template",
        "hero_prompt_version",
        "hero_prompt",
        "hero_selected",
    }

def test_uses_lead_story_tag():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_category"] == "Energía"

def test_category_source_is_lead_story():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_category_source"] == "lead_story"

def test_prompt_version_is_v1():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_prompt_version"] == "v1"

def test_hero_selected_is_none():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_selected"] is None

def test_prompt_contains_headline():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert "106 dólares" in result["hero_prompt"]

def test_prompt_contains_sentiment_from_en_block():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert "Risk-Off" in result["hero_prompt"]

def test_uses_en_block_for_sentiment_not_es():
    # EN block has Risk-On, ES block has Risk-Off — must use EN
    digest = {
        "es": {
            "stories": [{"tag": "Macro", "headline": "test"}],
            "sentiment": {"label_en": "Risk-Off"},
        },
        "en": {
            "stories": [{"tag": "Macro", "headline": "test"}],
            "sentiment": {"label_en": "Risk-On"},
        },
    }
    result = generate_hero_prompt(digest)
    assert "Risk-On" in result["hero_prompt"]

def test_unknown_tag_uses_macro_template():
    digest = {
        "es": {"stories": [{"tag": "XYZ", "headline": "test"}], "sentiment": {}},
        "en": {"sentiment": {"label_en": "Cautious"}},
    }
    result = generate_hero_prompt(digest)
    assert result["hero_category"] == "XYZ"
    assert result["hero_prompt_template"] == PROMPT_TEMPLATES["Macro"]

def test_empty_stories_defaults_to_macro():
    digest = {"es": {"stories": [], "sentiment": {}}, "en": {"sentiment": {"label_en": "Cautious"}}}
    result = generate_hero_prompt(digest)
    assert result["hero_category"] == "Macro"

def test_missing_en_block_falls_back_to_es_sentiment():
    digest = {
        "es": {
            "stories": [{"tag": "FX", "headline": "test"}],
            "sentiment": {"label_en": "Risk-Off"},
        },
        # no "en" key
    }
    result = generate_hero_prompt(digest)
    assert "Risk-Off" in result["hero_prompt"]

def test_template_stored_in_result():
    result = generate_hero_prompt(MOCK_DIGEST)
    assert result["hero_prompt_template"] == PROMPT_TEMPLATES["Energía"]
