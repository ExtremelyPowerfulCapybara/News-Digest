"""
Tests for summarizer.py prompt content.

Run from repo root:
  pytest tests/test_summarizer_prompt.py
"""

import inspect
import summarizer

def test_body_prompt_two_sentence_contract():
    """The body instruction must specify exactly two sentences with distinct roles."""
    source = inspect.getsource(summarizer)
    assert "Exactamente dos oraciones" in source, \
        "Prompt must instruct Claude to write exactly two sentences"
    assert "Primera oraci" in source, \
        "Prompt must define the role of the first sentence"
    assert "Segunda oraci" in source, \
        "Prompt must define the role of the second sentence"
    assert "Sin resúmenes" in source, \
        "Prompt must forbid wire-service summaries"

def test_body_prompt_old_instruction_removed():
    """The old vague 2-3 sentence instruction must be gone."""
    source = inspect.getsource(summarizer)
    assert "2-3 oraciones en español. Incluye cifras" not in source, \
        "Old body instruction must be removed"

if __name__ == "__main__":
    tests = [test_body_prompt_two_sentence_contract, test_body_prompt_old_instruction_removed]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
