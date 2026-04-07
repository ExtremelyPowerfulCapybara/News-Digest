"""
Tests for display hierarchy changes in renderer.py.

Run from repo root:
  pytest tests/test_display_hierarchy.py
"""

from renderer import _narrative_thread, FONT_SERIF, TEXT_LIGHT

def test_narrative_thread_empty_returns_empty():
    """Empty text must return empty string."""
    assert _narrative_thread("") == ""
    assert _narrative_thread(None) == ""

def test_narrative_thread_has_hilo_label():
    """Rendered output must include HILO DEL DÍA label."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "HILO DEL D" in html, "Must include 'HILO DEL DÍA' label"

def test_narrative_thread_uses_serif_font():
    """Pull quote text must use the serif font for italic style."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert FONT_SERIF in html, "Pull quote text must use FONT_SERIF"

def test_narrative_thread_centered():
    """Pull quote must be center-aligned."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "text-align:center" in html.replace(" ", ""), "Pull quote must be centered"

def test_narrative_thread_no_left_border():
    """Old border-left style must not appear."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "border-left" not in html, "Old border-left style must not appear"

def test_narrative_thread_text_present():
    """The supplied text must appear in the output."""
    html = _narrative_thread("La Fed y el peso recalibran el ciclo.")
    assert "La Fed y el peso recalibran el ciclo." in html

from renderer import _sentiment_week_chart

WEEK_DATA_TWO = [
    {"day": "Lun", "position": 28, "label_en": "Risk-Off"},
    {"day": "Mar", "position": 42, "label_en": "Cautious"},
]

WEEK_DATA_FIVE = [
    {"day": "Lun", "position": 28, "label_en": "Risk-Off"},
    {"day": "Mar", "position": 42, "label_en": "Cautious"},
    {"day": "Mié", "position": 35, "label_en": "Risk-Off"},
    {"day": "Jue", "position": 55, "label_en": "Cautious"},
    {"day": "Vie", "position": 72, "label_en": "Risk-On"},
]

def test_sentiment_chart_empty_for_one_entry():
    """Must return empty string when fewer than 2 data points."""
    assert _sentiment_week_chart([]) == ""
    assert _sentiment_week_chart([WEEK_DATA_TWO[0]]) == ""

def test_sentiment_chart_renders_day_labels():
    """Day abbreviations must appear in chart output."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "Lun" in html
    assert "Mar" in html

def test_sentiment_chart_riskoff_color():
    """Risk-Off entry must use red color #d4695a."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "#d4695a" in html, "Risk-Off color must appear in chart"

def test_sentiment_chart_cautious_color():
    """Cautious entry must use orange color #e8a030."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "#e8a030" in html, "Cautious color must appear in chart"

def test_sentiment_chart_riskon_color():
    """Risk-On entry must use green color #6abf7b."""
    html = _sentiment_week_chart(WEEK_DATA_FIVE)
    assert "#6abf7b" in html, "Risk-On color must appear in chart"

def test_sentiment_chart_no_external_url():
    """Chart must not reference quickchart.io or any external image URL."""
    html = _sentiment_week_chart(WEEK_DATA_FIVE)
    assert "quickchart.io" not in html, "Chart must not use quickchart.io"
    assert "<img" not in html, "Table-based chart must not use <img> tags"

def test_sentiment_chart_score_values_present():
    """Score values must appear in the chart."""
    html = _sentiment_week_chart(WEEK_DATA_TWO)
    assert "28" in html, "Score value 28 must appear"
    assert "42" in html, "Score value 42 must appear"

if __name__ == "__main__":
    tests = [
        test_narrative_thread_empty_returns_empty,
        test_narrative_thread_has_hilo_label,
        test_narrative_thread_uses_serif_font,
        test_narrative_thread_centered,
        test_narrative_thread_no_left_border,
        test_narrative_thread_text_present,
        test_sentiment_chart_empty_for_one_entry,
        test_sentiment_chart_renders_day_labels,
        test_sentiment_chart_riskoff_color,
        test_sentiment_chart_cautious_color,
        test_sentiment_chart_riskon_color,
        test_sentiment_chart_no_external_url,
        test_sentiment_chart_score_values_present,
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
