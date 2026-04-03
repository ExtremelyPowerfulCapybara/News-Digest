---
name: Editorial Voice + Email Density
description: Two-sentence story card contract (factual + interpretive) to sharpen editorial POV; remove raw scraped body from email; keep both layers in archive.
type: project
---

# Design Spec: Editorial Voice + Email Density

**Date:** 2026-04-03
**Branch:** Dev-Nigg (never main)

---

## Problem Statement

Two related issues with the current story card:

1. **Wire-summary tone** — Claude's `body` field reads like a neutral news summary rather than an editorial take. There is no enforced separation between reporting and analysis.
2. **Text density in email** — Each story card shows both the raw scraped article body and Claude's summary. The scraped text is redundant; Claude's output already captures the substance.

---

## Design

### Change 1 — Two-sentence body contract (`bot/summarizer.py`)

The `body` field instruction in the Claude prompt changes from:

> "2-3 oraciones en español. Incluye cifras específicas, nombres, y por qué importa. Termina naturalmente."

To:

> "Exactamente dos oraciones en español. Primera oración: hecho concreto — qué ocurrió, con un número o nombre específico. Segunda oración: qué significa — quién gana, quién pierde, o qué hay que observar a continuación. Sin resúmenes de agencia."

Same change applied to the English translation instruction.

No schema changes. The `body` field remains a single string. The `context_note` field is unchanged — it answers *why today*, which is complementary to the interpretive second sentence, not redundant.

---

### Change 2 — Remove raw scraped body from email (`bot/renderer.py`)

The raw scraped article excerpt is removed from the email story card.

Current card structure:
```
[thread badge]  Headline
[scraped body excerpt]
[Claude body — 2-3 sentences]
[context note]
```

New card structure:
```
[thread badge]  Headline
[Claude body — 2 sentences]
[context note]
```

Each story card becomes ~30–40% shorter. No other layout changes.

---

### Change 3 — Archive keeps both layers (`bot/pretty_renderer.py`)

The archive is the full reading experience and is not Gmail-constrained. Both layers remain visible:

```
[thread badge]  Headline
[Claude body — 2 sentences]
[context note]
[scraped article excerpt]
[Read full article →]
```

The "Read full article" link is promoted to a clearly visible styled link (not just an inline anchor) since the card is now a complete unit of analysis — the link is an invitation to go deeper, not a source citation buried in the text.

---

## Files Changed

| File | Change |
|------|--------|
| `bot/summarizer.py` | Update `body` prompt instruction (ES + EN) |
| `bot/renderer.py` | Remove scraped body from story card |
| `bot/pretty_renderer.py` | Promote "read full article" link; confirm scraped + Claude ordering |

---

## Constraints

- **Branch:** All work on `Dev-Nigg`. Never touch `main`.
- **Gmail safety:** All email changes use inline styles and table-based layout only.
- **No schema changes:** `body` field format is unchanged; only the prompt instruction changes.
- **Backward compatibility:** Old digests render correctly — the renderer change only affects what is displayed, not what is stored.
