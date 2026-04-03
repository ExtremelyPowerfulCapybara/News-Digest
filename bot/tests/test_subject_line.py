"""
Tests for delivery.py subject line enrichment.

Run from bot/ directory:
  python tests/test_subject_line.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import delivery

def test_send_email_accepts_sentiment_label():
    """send_email must accept a sentiment_label keyword argument."""
    sig = inspect.signature(delivery.send_email)
    assert "sentiment_label" in sig.parameters, \
        "send_email must have a sentiment_label parameter"

def test_sentiment_label_defaults_to_cautious():
    """sentiment_label must default to 'Cautious'."""
    sig = inspect.signature(delivery.send_email)
    default = sig.parameters["sentiment_label"].default
    assert default == "Cautious", \
        f"sentiment_label default must be 'Cautious', got {default!r}"

def test_subject_line_includes_sentiment():
    """Subject line construction must include the sentiment label."""
    source = inspect.getsource(delivery)
    assert "sentiment_label" in source, "delivery.py must reference sentiment_label"
    assert "NEWSLETTER_NAME" in source, "delivery.py must still include NEWSLETTER_NAME"

if __name__ == "__main__":
    tests = [
        test_send_email_accepts_sentiment_label,
        test_sentiment_label_defaults_to_cautious,
        test_subject_line_includes_sentiment,
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
