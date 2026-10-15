# Editorial Voice + Email Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sharpen each story card to a two-sentence editorial take (factual lead + interpretive read), and reduce email text density by moving `context_note` to archive-only.

**Architecture:** Three targeted edits — one prompt change in `summarizer.py`, one rendering removal in `renderer.py`, one styling promotion in `pretty_renderer.py`. No schema changes; all digest fields remain as-is. Old digests render gracefully.

**Tech Stack:** Python 3, f-string HTML templates, plain `python tests/test_*.py` test runner (no pytest required).

---

## Clarification: What "raw scraped body" means in practice

The email renderer never stored or displayed raw scraped article text — that content is consumed by Claude and discarded. The actual text-density issue is the `context_note` block (left-bordered italic callout) appearing below the `body` in each email story card. The plan removes `context_note` from the email only; the archive keeps both.

---

## File Map

| File | Change |
|------|--------|
| `bot/summarizer.py` | Change `body` prompt instruction: 2-sentence contract (factual + interpretive) |
| `bot/renderer.py` | Remove `context_note` rendering from `_story_block` |
| `bot/pretty_renderer.py` | Promote `.read-more` link to a more visible style |
| `bot/tests/test_renderer.py` | New: tests for `_story_block` output |

---

## Task 1: Tighten the Claude body prompt

**Files:**
- Modify: `bot/summarizer.py:51`

### Context

The `body` field instruction currently asks for "2-3 oraciones" with no constraint on what each sentence should do. We replace it with a two-sentence contract: sentence 1 = concrete fact with a number or name, sentence 2 = interpretation (who wins, who loses, what to watch).

- [ ] **Step 1: Write the failing test**

Create `bot/tests/test_summarizer_prompt.py`:

```python
"""
Tests for summarizer.py prompt content.

Run from bot/ directory:
  python tests/test_summarizer_prompt.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    assert "Sin res" in source, \
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
```

- [ ] **Step 2: Run to confirm FAIL**

```
cd bot
python tests/test_summarizer_prompt.py
```

Expected output:
```
  FAIL  test_body_prompt_two_sentence_contract: Prompt must instruct Claude to write exactly two sentences
  PASS  test_body_prompt_old_instruction_removed
```

- [ ] **Step 3: Update the body instruction in `summarizer.py`**

In `bot/summarizer.py`, find line 51. Replace:

```python
        "body": "2-3 oraciones en español. Incluye cifras específicas, nombres, y por qué importa. Termina naturalmente.",
```

With:

```python
        "body": "Exactamente dos oraciones en español. Primera oración: hecho concreto — qué ocurrió, con un número o nombre específico. Segunda oración: qué significa — quién gana, quién pierde, o qué hay que observar a continuación. Sin resúmenes de agencia.",
```

- [ ] **Step 4: Run tests to confirm PASS**

```
cd bot
python tests/test_summarizer_prompt.py
```

Expected output:
```
  PASS  test_body_prompt_two_sentence_contract
  PASS  test_body_prompt_old_instruction_removed

2/2 passed
```

- [ ] **Step 5: Commit**

```bash
git add bot/summarizer.py bot/tests/test_summarizer_prompt.py
git commit -m "feat: tighten story body to two-sentence editorial contract (factual + interpretive)"
```

---

## Task 2: Remove context_note from email story card

**Files:**
- Modify: `bot/renderer.py:215-252`
- Create: `bot/tests/test_renderer.py`

### Context

`_story_block` in `renderer.py` currently renders an italic left-bordered callout for `context_note.es` below the story body. This creates two stacked blocks of Claude text per card. Removing it from the email keeps only the tight 2-sentence body. The `context_note` continues to render in the archive (`pretty_renderer.py` — unchanged).

- [ ] **Step 1: Write the failing test**

Create `bot/tests/test_renderer.py`:

```python
"""
Tests for renderer.py story card rendering.

Run from bot/ directory:
  python tests/test_renderer.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

if __name__ == "__main__":
    tests = [
        test_context_note_not_in_email_card,
        test_headline_present_in_email_card,
        test_body_present_in_email_card,
        test_story_without_context_renders_cleanly,
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
```

- [ ] **Step 2: Run to confirm FAIL**

```
cd bot
python tests/test_renderer.py
```

Expected output:
```
  FAIL  test_context_note_not_in_email_card: context_note ES text must not appear in email card
  PASS  test_headline_present_in_email_card
  PASS  test_body_present_in_email_card
  PASS  test_story_without_context_renders_cleanly
```

- [ ] **Step 3: Remove context_note from `_story_block` in `renderer.py`**

In `bot/renderer.py`, find `_story_block` (line 215). Replace the entire function with:

```python
def _story_block(story: dict) -> str:
    thread_tag = story.get("thread_tag")
    thread_html = ""
    if thread_tag and isinstance(thread_tag, str):
        thread_html = (
            f'<p style="margin:0 0 8px 0;">'
            f'<span style="font-family:{FONT_SANS}; font-size:8px; font-weight:bold; '
            f'letter-spacing:1.5px; text-transform:uppercase; background:{TEXT_DARK}; '
            f'color:#f5f2ed; padding:3px 9px; border-radius:2px;">&#9679; {thread_tag}</span>'
            f'</p>'
        )

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px;">
      {thread_html}
      <p style="margin:0 0 6px 0;">
        <span style="font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2px; text-transform:uppercase; color:#999999;">{story['source']}</span>
        <span style="font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_LIGHT}; border:1px solid {BORDER}; padding:2px 6px; margin-left:8px;">{story.get('tag','')}</span>
      </p>
      <p style="margin:0 0 10px 0; font-family:{FONT_SERIF}; font-size:20px; font-weight:bold; color:{TEXT_DARK}; line-height:1.3;">{story['headline']}</p>
      <p style="margin:0 0 14px 0; font-family:{FONT_SANS}; font-size:13px; color:{TEXT_MID}; line-height:1.75;">{story['body']}</p>
      <a href="{story['url']}" style="font-family:{FONT_SANS}; font-size:10px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_DARK}; text-decoration:none; border-bottom:1px solid {TEXT_DARK}; padding-bottom:1px;">Leer m&aacute;s &#8594;</a>
    </td>
  </tr>
</table>"""
```

- [ ] **Step 4: Run tests to confirm PASS**

```
cd bot
python tests/test_renderer.py
```

Expected output:
```
  PASS  test_context_note_not_in_email_card
  PASS  test_headline_present_in_email_card
  PASS  test_body_present_in_email_card
  PASS  test_story_without_context_renders_cleanly

4/4 passed
```

- [ ] **Step 5: Run the full existing test suite to confirm no regressions**

```
cd bot
python tests/test_scorer.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add bot/renderer.py bot/tests/test_renderer.py
git commit -m "feat: remove context_note from email story card — body-only for tighter email density"
```

---

## Task 3: Promote "read more" link in archive

**Files:**
- Modify: `bot/pretty_renderer.py:101-102`

### Context

The archive now carries the full context_note callout (unchanged). Since the story card is a complete unit — factual lead, interpretive take, and why-it-matters note — the "read more" link should read as an invitation to go deeper, not an afterthought. Promote it from a small underlined text link to a clearly visible styled link with padding and a right arrow.

No tests for a CSS class change. Verify visually by opening a generated archive HTML file.

- [ ] **Step 1: Update `.read-more` CSS in `pretty_renderer.py`**

In `bot/pretty_renderer.py`, find lines 101-102 (the `.read-more` CSS rules). Replace:

```css
  .read-more { font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #1a1a1a; text-decoration: none; border-bottom: 1px solid #1a1a1a; padding-bottom: 1px; }
  .read-more:hover { color: #555; border-color: #555; }
```

With:

```css
  .read-more { display: inline-block; font-size: 9px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #1a1a1a; text-decoration: none; border: 1px solid #1a1a1a; padding: 6px 14px; margin-top: 6px; }
  .read-more:hover { background: #1a1a1a; color: #f5f2ed; }
```

- [ ] **Step 2: Generate a local preview to verify visually**

```bash
cd bot
MOCK=true SKIP_EMAIL=true python main.py
```

Then open `docs/<today's date>.html` in a browser. Confirm:
- Each story card shows `context_note` callout (left-bordered italic block)
- "Leer más →" / "Read more →" appears as a small bordered button, not a plain underlined link

- [ ] **Step 3: Commit**

```bash
git add bot/pretty_renderer.py
git commit -m "feat: promote read-more link to bordered button in archive story card"
```

---

## Final check

- [ ] **Run all tests**

```
cd bot
python tests/test_scorer.py
python tests/test_renderer.py
python tests/test_summarizer_prompt.py
```

All should pass with no failures.

- [ ] **Run a mock end-to-end**

```bash
cd bot
MOCK=true SKIP_EMAIL=true python main.py
```

Open `docs/<today>.html`. Confirm:
- Stories have two-sentence bodies (tighter, more opinionated)
- Archive shows `context_note` callout per story
- "Leer más" link is a visible bordered button

- [ ] **Verify email card in browser**

Open `docs/<today>.html` locally and toggle the language. Also open `bot/test_email.py` output if you want to preview the Gmail version. Confirm each story card has no `context_note` block — just headline, 2-sentence body, and "Leer más →".
