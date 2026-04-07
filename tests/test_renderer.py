"""
Tests for renderer.py story card rendering.

Run from repo root:
  pytest tests/test_renderer.py
"""

from renderer import _story_block

STORY_WITH_CONTEXT = {
    "source": "Reuters",
    "headline": "Banxico mantiene tasa en 9.0%",
    "body": "Banxico mantuvo su tasa de referencia en 9.0% en reunión de marzo. La decisión fue unánime y señala una pausa ante la desaceleración del ciclo de recortes.",
    "url": "https://reuters.com/example",
    "tag": "Tasas",
    "context_note": {
        "es": "El dato de inflación de febrero, publicado la semana pasada, justifica la pausa.",
        "en": "February inflation data, released last week, justifies the pause."
    },
    "thread_tag": None,
}

STORY_WITHOUT_CONTEXT = {
    "source": "El Financiero",
    "headline": "Peso cierra en 17.20 por dólar",
    "body": "El peso cerró en 17.20 por dólar, su nivel más débil en seis semanas. La presión vino del fortalecimiento del dólar índice tras datos de empleo en EE.UU.",
    "url": "https://elfinanciero.com.mx/example",
    "tag": "FX",
    "thread_tag": None,
}

def test_context_note_not_in_email_card():
    """context_note text must NOT appear in the email story card."""
    html = _story_block(STORY_WITH_CONTEXT)
    assert "El dato de inflación de febrero" not in html, \
        "context_note ES text must not appear in email card"
    assert "February inflation data" not in html, \
        "context_note EN text must not appear in email card"

def test_headline_present_in_email_card():
    """Headline must still appear in the email story card."""
    html = _story_block(STORY_WITH_CONTEXT)
    assert "Banxico mantiene tasa en 9.0%" in html, \
        "Headline must be present in email card"

def test_body_present_in_email_card():
    """Body text must still appear in the email story card."""
    html = _story_block(STORY_WITH_CONTEXT)
    assert "Banxico mantuvo su tasa" in html, \
        "Body text must be present in email card"

def test_story_without_context_renders_cleanly():
    """Story with no context_note must render without errors."""
    html = _story_block(STORY_WITHOUT_CONTEXT)
    assert "Peso cierra en 17.20" in html, \
        "Story without context_note must render normally"

def test_thread_badge_rendered_when_thread_tag_present():
    """Thread badge must appear when thread_tag is a non-empty string."""
    story = dict(STORY_WITHOUT_CONTEXT)
    story["thread_tag"] = "Banxico: tasa"
    html = _story_block(story)
    assert "Banxico: tasa" in html, \
        "thread_tag text must appear in email card"
    assert "&#9679;" in html, \
        "thread badge bullet must be present"

if __name__ == "__main__":
    tests = [
        test_context_note_not_in_email_card,
        test_headline_present_in_email_card,
        test_body_present_in_email_card,
        test_story_without_context_renders_cleanly,
        test_thread_badge_rendered_when_thread_tag_present,
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
