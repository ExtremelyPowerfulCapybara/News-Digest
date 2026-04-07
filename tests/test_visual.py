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

# ── storage merge ────────────────────────────────────────────────────────────

import json, os
from datetime import date

def test_save_digest_persists_visual(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    visual = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "original prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual)

    today = date.today().isoformat()
    with open(os.path.join(str(tmp_path), f"{today}.json"), encoding="utf-8") as f:
        stored = json.load(f)

    assert stored["visual"]["hero_category"] == "Energía"
    assert stored["visual"]["hero_selected"] is None


def test_save_digest_preserves_hero_selected_on_rerun(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    today = date.today().isoformat()
    path  = os.path.join(str(tmp_path), f"{today}.json")

    visual_first = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "first prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual_first)

    # Simulate manual edit: set hero_selected
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    stored["visual"]["hero_selected"] = "https://cdn.example.com/hero.png"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stored, f)

    # Rerun with updated prompt — hero_selected must survive
    visual_second = {
        "hero_category": "Energía",
        "hero_category_source": "lead_story",
        "hero_prompt_template": "template",
        "hero_prompt_version": "v1",
        "hero_prompt": "updated prompt",
        "hero_selected": None,
    }
    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}}, visual=visual_second)

    with open(path, encoding="utf-8") as f:
        final = json.load(f)

    assert final["visual"]["hero_selected"] == "https://cdn.example.com/hero.png"
    assert final["visual"]["hero_prompt"] == "updated prompt"


def test_save_digest_without_visual_omits_key(tmp_path, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "DIGEST_DIR", str(tmp_path))

    storage.save_digest(MOCK_DIGEST, {"tickers": [], "currency": {}})

    today = date.today().isoformat()
    with open(os.path.join(str(tmp_path), f"{today}.json"), encoding="utf-8") as f:
        stored = json.load(f)

    assert "visual" not in stored

# ── pretty_renderer hero block ────────────────────────────────────────────────

from pretty_renderer import build_pretty_html

_MINIMAL_TICKERS   = []
_MINIMAL_CURRENCY  = {"bases": ["MXN"], "matrix": {"MXN": []}}
_MINIMAL_SECONDARY = None


def test_hero_block_absent_when_visual_is_none():
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = None,
    )
    assert 'class="hero-image"' not in html


def test_hero_block_absent_when_hero_selected_is_none():
    visual = {
        "hero_category": "Energía",
        "hero_selected": None,
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    assert 'class="hero-image"' not in html


def test_hero_block_present_when_hero_selected_is_set():
    visual = {
        "hero_category": "Energía",
        "hero_selected": "https://cdn.example.com/hero.png",
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    assert 'class="hero-image"' in html
    assert 'src="https://cdn.example.com/hero.png"' in html
    assert 'alt="Energía"' in html


def test_hero_block_position_before_sentiment():
    """Hero image must appear before the sentiment gauge in the document."""
    visual = {
        "hero_category": "FX",
        "hero_selected": "https://cdn.example.com/hero.png",
    }
    html = build_pretty_html(
        digest            = MOCK_DIGEST,
        tickers           = _MINIMAL_TICKERS,
        currency          = _MINIMAL_CURRENCY,
        week_stories      = [],
        secondary_tickers = _MINIMAL_SECONDARY,
        visual            = visual,
    )
    hero_pos      = html.index('class="hero-image"')
    sentiment_pos = html.index('class="sentiment"')
    assert hero_pos < sentiment_pos
