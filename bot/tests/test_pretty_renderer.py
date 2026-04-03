"""
Tests for pretty_renderer.py display hierarchy changes.

Run from bot/ directory:
  python tests/test_pretty_renderer.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pretty_renderer import build_pretty_html

MINIMAL_DIGEST = {
    "es": {
        "editor_note": "Nota editorial.",
        "narrative_thread": "La Fed y el peso comparten protagonismo.",
        "sentiment": {"label_en": "Cautious", "label_es": "Cauteloso", "position": 50, "context_es": ""},
        "stories": [
            {"source": "Reuters",      "headline": "Fed mantiene tasas", "body": "La Fed no movió.", "url": "https://reuters.com/a", "tag": "Macro"},
            {"source": "El Financiero","headline": "Peso cierra estable","body": "El peso en 17.20.", "url": "https://elfinanciero.com/b", "tag": "FX"},
        ],
        "quote": {"text": "Test quote.", "attribution": "Author"},
    },
    "en": {}
}

def test_lead_story_label_present():
    """First story must have the LEAD STORY label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "LEAD STORY" in html, "Lead story label must appear for first story"

def test_lead_story_headline_larger():
    """First story headline must use the larger CSS class."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "story-headline-lead" in html, "First story must use story-headline-lead class"

def test_second_story_no_lead_label():
    """Second story must NOT have the lead label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert html.count("LEAD STORY") == 1, "Only first story should have the lead label"

def test_narrative_thread_pull_quote_label():
    """Narrative thread must have HILO DEL DÍA label."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "Hilo del" in html, "Narrative thread must have 'Hilo del día' label"

def test_narrative_thread_pull_quote_text():
    """Narrative thread text must appear inside nt-text class."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "nt-text" in html, "Narrative thread must use nt-text CSS class"
    assert "La Fed y el peso comparten protagonismo" in html, "Narrative thread text must appear"

def test_narrative_thread_no_left_border():
    """Old left-border style must be gone from narrative thread."""
    html = build_pretty_html(MINIMAL_DIGEST, [], {}, [], 1, False, None, "Test Author")
    assert "border-left: 3px solid #1a1a1a" not in html.replace(" ",""), \
        "Old border-left style must not appear in narrative thread"

if __name__ == "__main__":
    tests = [
        test_lead_story_label_present,
        test_lead_story_headline_larger,
        test_second_story_no_lead_label,
        test_narrative_thread_pull_quote_label,
        test_narrative_thread_pull_quote_text,
        test_narrative_thread_no_left_border,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
