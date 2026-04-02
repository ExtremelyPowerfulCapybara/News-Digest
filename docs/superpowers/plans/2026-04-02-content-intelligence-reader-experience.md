# Content Intelligence + Reader Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add article pre-scoring before Claude, enrich Claude's output with context notes and narrative threads, and surface those new fields in the email and archive with design polish.

**Architecture:** Two logical tracks share a sequential implementation. Track 1 (backend: scorer + prompt changes) has no HTML dependencies and can be built first. Track 2 (frontend: renderer + archive) applies design polish and wires in the new fields from Track 1. Both land on `Dev-Nigg` — never `main`.

**Tech Stack:** Python 3.11 (stdlib + existing deps), HTML/CSS (inline for email, class-based for archive), Chart.js (already loaded in archive), Claude Sonnet API (existing `anthropic` SDK)

---

## File Map

| File | Change |
|------|--------|
| `bot/fetcher.py` | Add `publishedAt` field to article dicts |
| `bot/config.py` | Add `SOURCE_TIERS`, `MAX_ARTICLES_FOR_CLAUDE` |
| `bot/scorer.py` | **New** — `rank_articles()` scoring + uniqueness filter |
| `bot/tests/test_scorer.py` | **New** — unit tests for scorer |
| `bot/main.py` | Call scorer between fetch and summarize; pass `active_threads` to summarizer |
| `bot/storage.py` | Add `get_active_threads()` |
| `bot/summarizer.py` | Expanded prompt schema + `active_threads` injection |
| `bot/renderer.py` | New `_narrative_thread()` block; updated `_story_block()` with thread badge + context note |
| `bot/pretty_renderer.py` | New CSS classes; updated story HTML with thread badge + context note (bilingual) |
| `bot/archive.py` | Write/update `docs/thread_index.json`; add Coverage Map + Thread Index to `index.html` |
| `docs/thread_index.json` | **New** — auto-generated, committed by workflow |

---

## Task 1: Add `publishedAt` to article dicts in fetcher.py

**Files:**
- Modify: `bot/fetcher.py:59-64`

- [ ] **Step 1: Read current article dict construction**

Open `bot/fetcher.py`. The article dict is built at line 59:
```python
all_articles.append({
    "title":   a.get("title", "").strip(),
    "content": content,
    "source":  source_name,
    "url":     article_url,
})
```

- [ ] **Step 2: Add `publishedAt` field**

Replace that block with:
```python
all_articles.append({
    "title":       a.get("title", "").strip(),
    "content":     content,
    "source":      source_name,
    "url":         article_url,
    "publishedAt": a.get("publishedAt", ""),
})
```

- [ ] **Step 3: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/fetcher.py
git commit -m "feat: preserve publishedAt in article dicts for scoring"
```

---

## Task 2: Add scoring constants to config.py

**Files:**
- Modify: `bot/config.py`

- [ ] **Step 1: Add SOURCE_TIERS and MAX_ARTICLES_FOR_CLAUDE after the domain blocklist block**

Find the comment `# ── Domain blocklist` in `config.py`. After the `NEWS_DOMAIN_BLOCKLIST` block, add:

```python
# ── Article scoring ───────────────────────────
# Source name substrings for authority scoring (case-insensitive match).
SOURCE_TIERS = {
    "tier1": ["Financial Times", "Reuters", "Wall Street Journal", "Bloomberg"],
    "tier2": ["Expansion", "El Economista", "Reforma", "Milenio"],
}

# Maximum number of articles passed to Claude after scoring.
MAX_ARTICLES_FOR_CLAUDE = 12
```

- [ ] **Step 2: Commit**

```bash
git add bot/config.py
git commit -m "feat: add SOURCE_TIERS and MAX_ARTICLES_FOR_CLAUDE to config"
```

---

## Task 3: Create scorer.py

**Files:**
- Create: `bot/scorer.py`

- [ ] **Step 1: Write the failing test first** (see Task 4 — write test file before implementation)

Skip to Task 4, write the tests, verify they fail (NameError on import), then return here.

- [ ] **Step 2: Create bot/scorer.py**

```python
# ─────────────────────────────────────────────
#  scorer.py  —  Pre-score articles before Claude
#
#  rank_articles() returns the top MAX_ARTICLES_FOR_CLAUDE
#  articles sorted by a composite score of freshness,
#  source authority, and topic relevance. A greedy
#  uniqueness filter removes near-duplicate headlines.
# ─────────────────────────────────────────────

from datetime import datetime, timezone


def _freshness_score(published_at: str | None, now: datetime) -> float:
    """0.1–1.0 based on hours since publication."""
    if not published_at:
        return 0.1
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        hours_old = (now - pub).total_seconds() / 3600
    except Exception:
        return 0.1
    if hours_old < 6:   return 1.0
    if hours_old < 12:  return 0.7
    if hours_old < 24:  return 0.4
    return 0.1


def _authority_score(source_name: str) -> float:
    """1.0 for Tier 1 sources, 0.6 for Tier 2, 0.3 for unknown."""
    from config import SOURCE_TIERS
    name_lower = source_name.lower()
    if any(t.lower() in name_lower for t in SOURCE_TIERS["tier1"]):
        return 1.0
    if any(t.lower() in name_lower for t in SOURCE_TIERS["tier2"]):
        return 0.6
    return 0.3


def _relevance_score(article: dict, topics: list[str]) -> float:
    """Normalized keyword overlap between article text and configured topics."""
    text = (article.get("title", "") + " " + article.get("content", "")).lower()
    matches = sum(1 for t in topics if t.lower() in text)
    return min(matches / max(len(topics), 1), 1.0)


def rank_articles(articles: list[dict], now: datetime | None = None) -> list[dict]:
    """
    Score and rank articles. Returns at most MAX_ARTICLES_FOR_CLAUDE articles.

    Scoring weights:
      Freshness  30%  — recency of publication
      Authority  25%  — source tier (config.SOURCE_TIERS)
      Relevance  25%  — keyword overlap with config.TOPICS

    A greedy uniqueness pass removes articles with >60% headline word
    overlap against already-accepted articles (applied after initial sort).
    """
    from config import TOPICS, MAX_ARTICLES_FOR_CLAUDE
    if now is None:
        now = datetime.now(timezone.utc)

    # Score each article on the three weighted factors
    scored = []
    for article in articles:
        f = _freshness_score(article.get("publishedAt"), now) * 0.30
        a = _authority_score(article.get("source", ""))        * 0.25
        r = _relevance_score(article, TOPICS)                  * 0.25
        scored.append((f + a + r, article))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Greedy uniqueness pass
    accepted: list[dict] = []
    accepted_words: list[set] = []

    for _, article in scored:
        headline_words = set(article.get("title", "").lower().split())
        if headline_words and accepted_words:
            max_overlap = max(
                len(headline_words & existing) / len(headline_words)
                for existing in accepted_words
            )
            if max_overlap >= 0.6:
                continue
        accepted.append(article)
        accepted_words.append(headline_words)
        if len(accepted) >= MAX_ARTICLES_FOR_CLAUDE:
            break

    return accepted
```

- [ ] **Step 3: Run the tests (from Task 4) and verify they pass**

```bash
cd D:/GitHub/mexico-finance-brief/bot
python tests/test_scorer.py
```

Expected output: `All tests passed.`

- [ ] **Step 4: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/scorer.py
git commit -m "feat: add scorer.py with rank_articles() — freshness, authority, relevance, uniqueness"
```

---

## Task 4: Write and run scorer tests

**Files:**
- Create: `bot/tests/__init__.py`
- Create: `bot/tests/test_scorer.py`

- [ ] **Step 1: Create the tests directory and empty init**

```bash
mkdir -p D:/GitHub/mexico-finance-brief/bot/tests
touch D:/GitHub/mexico-finance-brief/bot/tests/__init__.py
```

- [ ] **Step 2: Write bot/tests/test_scorer.py**

```python
"""
Tests for scorer.py

Run from bot/ directory:
  python tests/test_scorer.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone, timedelta
from scorer import _freshness_score, _authority_score, _relevance_score, rank_articles

NOW = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)


def test_freshness_very_recent():
    pub = (NOW - timedelta(hours=2)).isoformat()
    assert _freshness_score(pub, NOW) == 1.0, "Article 2h old should score 1.0"


def test_freshness_semi_recent():
    pub = (NOW - timedelta(hours=9)).isoformat()
    assert _freshness_score(pub, NOW) == 0.7, "Article 9h old should score 0.7"


def test_freshness_day_old():
    pub = (NOW - timedelta(hours=20)).isoformat()
    assert _freshness_score(pub, NOW) == 0.4, "Article 20h old should score 0.4"


def test_freshness_old():
    pub = (NOW - timedelta(hours=30)).isoformat()
    assert _freshness_score(pub, NOW) == 0.1, "Article 30h old should score 0.1"


def test_freshness_none():
    assert _freshness_score(None, NOW) == 0.1, "Missing publishedAt should score 0.1"


def test_freshness_malformed():
    assert _freshness_score("not-a-date", NOW) == 0.1, "Malformed date should score 0.1"


def test_authority_tier1_reuters():
    assert _authority_score("Reuters") == 1.0


def test_authority_tier1_ft():
    assert _authority_score("Financial Times") == 1.0


def test_authority_tier2():
    assert _authority_score("Expansion") == 0.6


def test_authority_unknown():
    assert _authority_score("SomeBlog.mx") == 0.3


def test_relevance_multiple_matches():
    article = {"title": "México economía mercados", "content": ""}
    topics = ["México", "economía", "mercados", "finanzas", "política", "comercio", "criptomonedas"]
    score = _relevance_score(article, topics)
    assert score > 0.3, f"Expected > 0.3, got {score}"


def test_relevance_no_match():
    article = {"title": "Weather in Paris", "content": "sunny day"}
    topics = ["México", "economía", "mercados", "finanzas", "política", "comercio", "criptomonedas"]
    score = _relevance_score(article, topics)
    assert score == 0.0


def test_rank_uniqueness_filter():
    """Near-duplicate headlines should not both appear in results."""
    articles = [
        {"title": "Peso cae frente al dólar hoy", "source": "Reuters",
         "publishedAt": (NOW - timedelta(hours=1)).isoformat(), "content": ""},
        {"title": "Peso cae frente al dólar ahora", "source": "Reuters",
         "publishedAt": (NOW - timedelta(hours=2)).isoformat(), "content": ""},
        {"title": "Banxico sube tasas de interés", "source": "El Financiero",
         "publishedAt": (NOW - timedelta(hours=3)).isoformat(), "content": ""},
    ]
    result = rank_articles(articles, now=NOW)
    headlines = [a["title"] for a in result]
    assert not (
        "Peso cae frente al dólar hoy" in headlines
        and "Peso cae frente al dólar ahora" in headlines
    ), "Near-duplicate peso headlines should not both appear"
    assert "Banxico sube tasas de interés" in headlines, "Distinct article should appear"


def test_rank_respects_max():
    """Output should not exceed MAX_ARTICLES_FOR_CLAUDE."""
    articles = [
        {"title": f"Story about topic {i}", "source": "Reuters",
         "publishedAt": NOW.isoformat(), "content": ""}
        for i in range(30)
    ]
    result = rank_articles(articles, now=NOW)
    from config import MAX_ARTICLES_FOR_CLAUDE
    assert len(result) <= MAX_ARTICLES_FOR_CLAUDE, f"Got {len(result)}, expected <= {MAX_ARTICLES_FOR_CLAUDE}"


def test_rank_empty_input():
    assert rank_articles([], now=NOW) == []


def test_rank_freshness_preferred():
    """A very recent article from an unknown source should rank above a stale Tier 1 article."""
    articles = [
        {"title": "Stale FT story about rates", "source": "Financial Times",
         "publishedAt": (NOW - timedelta(hours=36)).isoformat(), "content": ""},
        {"title": "Breaking news on Mexico economy", "source": "SomeBlog",
         "publishedAt": (NOW - timedelta(hours=1)).isoformat(), "content": "México economía"},
    ]
    result = rank_articles(articles, now=NOW)
    # Both should be returned (only 2 articles, no max violation)
    assert len(result) == 2
    # Fresh unknown-source should outrank stale Tier 1
    assert result[0]["title"] == "Breaking news on Mexico economy"


if __name__ == "__main__":
    tests = [
        test_freshness_very_recent, test_freshness_semi_recent, test_freshness_day_old,
        test_freshness_old, test_freshness_none, test_freshness_malformed,
        test_authority_tier1_reuters, test_authority_tier1_ft,
        test_authority_tier2, test_authority_unknown,
        test_relevance_multiple_matches, test_relevance_no_match,
        test_rank_uniqueness_filter, test_rank_respects_max,
        test_rank_empty_input, test_rank_freshness_preferred,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
```

- [ ] **Step 3: Run tests before scorer.py exists — verify they fail**

```bash
cd D:/GitHub/mexico-finance-brief/bot
python tests/test_scorer.py
```

Expected: `ModuleNotFoundError: No module named 'scorer'`

Now go implement Task 3, then return here.

- [ ] **Step 4: Run tests after scorer.py is written — verify they pass**

```bash
cd D:/GitHub/mexico-finance-brief/bot
python tests/test_scorer.py
```

Expected output ends with: `All 16 tests passed.`

- [ ] **Step 5: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/tests/
git commit -m "test: add scorer unit tests (freshness, authority, relevance, uniqueness, max cap)"
```

---

## Task 5: Wire scorer into main.py

**Files:**
- Modify: `bot/main.py`

- [ ] **Step 1: Add scorer import and call after fetch, before summarize**

In `main.py`, find this block (around line 53–61):
```python
        articles = fetch_news(prior_urls=prior_urls)
        if not articles:
            print("  No articles found. Check your NewsAPI key or topics.")
            return
        print(f"\n[3/5] Summarizing {len(articles)} articles with Claude...")
        digest = summarize_news(articles)
```

Replace with:
```python
        articles = fetch_news(prior_urls=prior_urls)
        if not articles:
            print("  No articles found. Check your NewsAPI key or topics.")
            return
        print(f"\n[2.5/5] Scoring and ranking {len(articles)} articles...")
        from scorer import rank_articles
        articles = rank_articles(articles)
        print(f"  [scorer] {len(articles)} articles selected for Claude.")
        from storage import get_active_threads
        active_threads = get_active_threads()
        if active_threads:
            print(f"  [threads] Active threads this week: {active_threads}")
        print(f"\n[3/5] Summarizing {len(articles)} articles with Claude...")
        digest = summarize_news(articles, active_threads=active_threads)
```

- [ ] **Step 2: Also update the mock path to pass empty active_threads**

Find the mock block (around line 47–51):
```python
    if MOCK_MODE:
        print("\n[2-3/5] MOCK MODE -- loading saved digest...")
        mock     = load_mock()
        articles = mock["articles"]
        digest   = mock["digest"]
```

Replace with:
```python
    if MOCK_MODE:
        print("\n[2-3/5] MOCK MODE -- loading saved digest...")
        mock     = load_mock()
        articles = mock["articles"]
        digest   = mock["digest"]
        active_threads = []
```

- [ ] **Step 3: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/main.py
git commit -m "feat: wire scorer into main pipeline; pass active_threads to summarizer"
```

---

## Task 6: Add get_active_threads() to storage.py

**Files:**
- Modify: `bot/storage.py`

- [ ] **Step 1: Add function after get_recent_urls()**

In `storage.py`, after the `get_recent_urls()` function (around line 93), add:

```python
def get_active_threads() -> list[str]:
    """
    Returns thread_tag values that appeared >=2 times across the last 5 daily digests.
    Used to inject recurring weekly themes into the Claude prompt.
    Only tags from digests that have the new thread_tag field are counted.
    """
    today = date.today()
    tag_counts: dict[str, int] = {}

    for i in range(1, 6):
        data = load_digest((today - timedelta(days=i)).isoformat())
        if not data:
            continue
        digest_es = data.get("digest", {}).get("es", data.get("digest", {}))
        for story in digest_es.get("stories", []):
            tag = story.get("thread_tag")
            if tag and isinstance(tag, str):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return [tag for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]) if count >= 2]
```

- [ ] **Step 2: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/storage.py
git commit -m "feat: add get_active_threads() to scan last 5 digests for recurring thread tags"
```

---

## Task 7: Update summarizer.py — expanded schema + active_threads injection

**Files:**
- Modify: `bot/summarizer.py`

- [ ] **Step 1: Update summarize_news signature to accept active_threads**

Change the function signature from:
```python
def summarize_news(articles: list[dict]) -> dict:
```

To:
```python
def summarize_news(articles: list[dict], active_threads: list[str] | None = None) -> dict:
```

- [ ] **Step 2: Add thread context injection block after the docstring**

After the `parts = []` block and before `prompt = f"""...`, add:
```python
    active_threads = active_threads or []
    thread_context = ""
    if active_threads:
        tags_str = ", ".join(f'"{t}"' for t in active_threads)
        thread_context = f"\nLos siguientes temas han aparecido recurrentemente esta semana: {tags_str}. Si una historia continúa alguno de estos temas, usa el mismo tag exacto en el campo thread_tag.\n"
```

- [ ] **Step 3: Update the prompt**

Replace the existing `prompt = f"""...` with the expanded version below. The key changes are:
1. Insert `{thread_context}` after the opening paragraph
2. Expand each story object in the schema to include `context_note` and `thread_tag`
3. Add `narrative_thread` to the top-level of both `es` and `en` blocks

```python
    prompt = f"""Eres un editor de noticias financieras produciendo un briefing matutino diario para una audiencia hispanohablante sofisticada. Voz: directa, seca, ocasionalmente sardónica — como un editor de mercados veterano que ha visto cada ciclo y encuentra el actual tanto alarmante como vagamente entretenido.
{thread_context}
Analiza los artículos a continuación y devuelve un objeto JSON con EXACTAMENTE esta estructura:

{{
  "es": {{
    "editor_note": "2-3 oraciones abriendo el briefing del día. Siempre abre con 'Estimados humanos,' como las primeras dos palabras. Voz: directa, seca, ocasionalmente sardónica. Referencia la historia dominante. Primera persona. NO incluyas firma — se agrega por separado. Sin relleno.",

    "narrative_thread": "Una oración en español describiendo el tema macro dominante del día — el hilo conductor que conecta las historias más importantes.",

    "sentiment": {{
      "label_es": "Aversión al Riesgo" | "Cauteloso" | "Apetito por Riesgo",
      "label_en": "Risk-Off" | "Cautious" | "Risk-On",
      "position": <entero 5-95 donde 5=aversión extrema, 50=neutral, 95=apetito extremo>,
      "context_es": "Una oración explicando el sentimiento de hoy en español.",
      "context_en": "One sentence explaining today's sentiment in English."
    }},

    "stories": [
      {{
        "source": "Nombre de la fuente",
        "headline": "Titular conciso y específico en español",
        "body": "2-3 oraciones en español. Incluye cifras específicas, nombres, y por qué importa. Termina naturalmente.",
        "url": "URL original del artículo",
        "tag": "Uno de: Macro | FX | México | Comercio | Tasas | Mercados | Energía | Política",
        "context_note": {{
          "es": "Una oración explicando por qué esta historia importa HOY — conecta con condiciones de mercado actuales, datos recientes, o eventos de la semana.",
          "en": "One sentence explaining why this story matters TODAY — connect to current market conditions, recent data, or this week's events."
        }},
        "thread_tag": "Si esta historia continúa un tema recurrente de la semana, escribe el tag exacto (e.g. 'Banxico: tasa'). Si es independiente, escribe null."
      }}
    ],

    "quote": {{
      "text": "Una cita financiera o económica relevante que conecte temáticamente con las noticias de hoy. Debe ser real y verificable. Puede estar en español o inglés.",
      "attribution": "Nombre completo, fuente, año"
    }}
  }},

  "en": {{
    "editor_note": "Faithful English translation of the editor_note above. Keep the same voice and tone.",

    "narrative_thread": "Faithful English translation of the narrative_thread above.",

    "sentiment": {{
      "label_es": "<same as above>",
      "label_en": "<same as above>",
      "position": <same integer as above>,
      "context_es": "<same as above>",
      "context_en": "<same as above>"
    }},

    "stories": [
      {{
        "source": "Same source name",
        "headline": "Faithful English translation of the headline",
        "body": "Faithful English translation of the body",
        "url": "Same original URL",
        "tag": "Same tag",
        "context_note": {{
          "es": "<same as above>",
          "en": "Faithful English translation of context_note"
        }},
        "thread_tag": "<same as above or null>"
      }}
    ],

    "quote": {{
      "text": "<same quote as above>",
      "attribution": "<same attribution as above>"
    }}
  }}
}}

Reglas:
- Selecciona 5-7 historias, ordenadas por importancia
- Diversidad temática obligatoria: cada historia debe cubrir un tema distinto. Si varios artículos tratan el mismo evento o tema central (e.g. múltiples artículos sobre el conflicto Irán/petróleo, o sobre aranceles Trump), selecciona SOLO el más completo e informativo — descarta los demás sin excepción
- Nunca incluyas dos historias donde la pregunta central sea la misma, aunque provengan de fuentes distintas o tengan ángulos ligeramente diferentes
- stories debe incluir la URL original de la lista de artículos
- Responde ÚNICAMENTE con el objeto JSON, sin preámbulo, sin markdown fences
- sentiment.position debe ser consistente con el label: Aversión al Riesgo = 5-35, Cauteloso = 36-64, Apetito por Riesgo = 65-95
- El bloque "en" es una traducción fiel del bloque "es" — mismas historias, mismas URLs, mismo sentimiento
- context_note debe ser sustantivo: no repitas el cuerpo de la historia, aporta contexto nuevo
- thread_tag debe ser null si la historia es independiente; solo usa tags de la lista de temas recurrentes si aplica

Artículos:
{news_text}
"""
```

- [ ] **Step 4: Increase max_tokens to 8000** (new fields add ~30% more output)

Find: `max_tokens=6000`
Replace with: `max_tokens=8000`

Also update the repair prompt call:
Find the second `max_tokens=6000` (in the repair_message block)
Replace with: `max_tokens=8000`

- [ ] **Step 5: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/summarizer.py
git commit -m "feat: expand Claude schema with context_note, thread_tag, narrative_thread; inject active_threads"
```

---

## Task 8: Update renderer.py — new fields + email design polish

**Files:**
- Modify: `bot/renderer.py`

- [ ] **Step 1: Add _narrative_thread() function**

After the `_editor_note()` function (around line 157), add:

```python
def _narrative_thread(text: str) -> str:
    """Renders the day's dominant macro theme as a bold callout below the editor note."""
    if not text:
        return ""
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:0 48px 20px;">
      <p style="margin:0; font-family:{FONT_SANS}; font-size:11px; font-weight:bold; color:{TEXT_MID}; border-left:3px solid {TEXT_DARK}; padding-left:12px; line-height:1.7;">{text}</p>
    </td>
  </tr>
</table>"""
```

- [ ] **Step 2: Update _story_block() to render thread_tag badge and context_note**

Replace the entire `_story_block()` function (lines 201–215) with:

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

    context_note = story.get("context_note", {})
    context_es = context_note.get("es", "") if isinstance(context_note, dict) else ""
    context_html = ""
    if context_es:
        context_html = (
            f'<p style="margin:10px 0 10px 0; font-family:{FONT_SANS}; font-size:12px; '
            f'color:{TEXT_MID}; border-left:3px solid {BORDER}; padding-left:10px; '
            f'line-height:1.7; font-style:italic;">{context_es}</p>'
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
      <p style="margin:0 0 10px 0; font-family:{FONT_SANS}; font-size:13px; color:{TEXT_MID}; line-height:1.75;">{story['body']}</p>
      {context_html}
      <a href="{story['url']}" style="font-family:{FONT_SANS}; font-size:10px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_DARK}; text-decoration:none; border-bottom:1px solid {TEXT_DARK}; padding-bottom:1px;">Leer m&aacute;s &#8594;</a>
    </td>
  </tr>
</table>"""
```

- [ ] **Step 3: Wire narrative_thread into build_html()**

In `build_html()`, find this line (around line 559):
```python
        <tr><td>{_editor_note(digest.get('editor_note', ''), author)}</td></tr>
        <tr><td>{_divider()}</td></tr>
```

Replace with:
```python
        <tr><td>{_editor_note(digest.get('editor_note', ''), author)}</td></tr>
        {('<tr><td>' + _narrative_thread(digest.get('narrative_thread', '')) + '</td></tr>') if digest.get('narrative_thread') else ''}
        <tr><td>{_divider()}</td></tr>
```

- [ ] **Step 4: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/renderer.py
git commit -m "feat: add narrative thread, thread tag badge, and context note to email renderer"
```

---

## Task 9: Update pretty_renderer.py — new fields + archive design polish

**Files:**
- Modify: `bot/pretty_renderer.py`

- [ ] **Step 1: Add CSS for new elements**

In the `CSS = """` block, after the `.story-body` rule (around line 100), add:

```css
  .thread-badge {
    display: inline-block;
    font-size: 8px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;
    background: #1a1a1a; color: #f5f2ed; padding: 3px 9px; border-radius: 2px;
    margin-bottom: 8px;
  }
  .context-note {
    font-size: 12.5px; color: #777; line-height: 1.7; font-style: italic;
    border-left: 3px solid #cdd4d9; padding-left: 10px;
    margin: 10px 0;
  }
  .narrative-thread {
    padding: 0 48px 20px;
  }
  .narrative-thread p {
    font-size: 11px; font-weight: 600; color: #555;
    border-left: 3px solid #1a1a1a; padding-left: 12px; line-height: 1.7;
    margin: 0;
  }
```

- [ ] **Step 2: Add narrative_thread rendering after editor note**

In `build_pretty_html()`, find where `digest_es.get("editor_note")` is used in the HTML template (search for `editor-note` in the function). After the editor-note block in the returned HTML, add the narrative_thread block. The current HTML template has:

```html
<div class="editor-note">
  <div class="lang-es"><p>{digest_es.get('editor_note', '')}</p>...</div>
  <div class="lang-en">...</div>
</div>
```

After this `</div>` closing the editor-note div, insert:

```python
narrative_es = digest_es.get("narrative_thread", "")
narrative_en = digest_en.get("narrative_thread", narrative_es)
narrative_html = ""
if narrative_es:
    narrative_html = f"""
<div class="narrative-thread">
  <div class="lang-es"><p>{narrative_es}</p></div>
  <div class="lang-en"><p>{narrative_en}</p></div>
</div>"""
```

Then include `{narrative_html}` in the HTML where the editor-note ends.

- [ ] **Step 3: Update story HTML to include thread_tag badge and context_note (bilingual)**

In `build_pretty_html()`, find the stories loop (around line 301):
```python
    stories_html = ""
    for i, story in enumerate(stories_es):
        story_en = stories_en[i] if i < len(stories_en) else story
        stories_html += f"""
{DIVIDER}
<div class="story">
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="lang-es">
    <div class="story-headline">{story['headline']}</div>
    <div class="story-body">{story['body']}</div>
    <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
  </div>
  <div class="lang-en">
    <div class="story-headline">{story_en.get('headline', story['headline'])}</div>
    <div class="story-body">{story_en.get('body', story['body'])}</div>
    <a href="{story['url']}" class="read-more">Read more &rarr;</a>
  </div>
</div>"""
```

Replace with:
```python
    stories_html = ""
    for i, story in enumerate(stories_es):
        story_en = stories_en[i] if i < len(stories_en) else story

        thread_tag = story.get("thread_tag")
        thread_badge = (
            f'<span class="thread-badge">&#9679; {thread_tag}</span>'
            if thread_tag and isinstance(thread_tag, str) else ""
        )

        ctx_es = ""
        ctx_en = ""
        cn = story.get("context_note", {})
        if isinstance(cn, dict):
            ctx_es = cn.get("es", "")
            ctx_en = cn.get("en", "")
        cn_en = story_en.get("context_note", {})
        if isinstance(cn_en, dict) and cn_en.get("en"):
            ctx_en = cn_en.get("en", ctx_en)

        ctx_es_html = f'<div class="context-note">{ctx_es}</div>' if ctx_es else ""
        ctx_en_html = f'<div class="context-note">{ctx_en}</div>' if ctx_en else ""

        stories_html += f"""
{DIVIDER}
<div class="story">
  {thread_badge}
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="lang-es">
    <div class="story-headline">{story['headline']}</div>
    <div class="story-body">{story['body']}</div>
    {ctx_es_html}
    <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
  </div>
  <div class="lang-en">
    <div class="story-headline">{story_en.get('headline', story['headline'])}</div>
    <div class="story-body">{story_en.get('body', story['body'])}</div>
    {ctx_en_html}
    <a href="{story['url']}" class="read-more">Read more &rarr;</a>
  </div>
</div>"""
```

- [ ] **Step 4: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/pretty_renderer.py
git commit -m "feat: add thread badge, context note, and narrative thread to archive renderer"
```

---

## Task 10: Update archive.py — thread_index.json + Coverage Map + Thread Index sections

**Files:**
- Modify: `bot/archive.py`

- [ ] **Step 1: Add _update_thread_index() function**

After the `_load_all_digests()` function, add:

```python
def _update_thread_index(digest: dict, date_str: str) -> None:
    """
    Reads docs/thread_index.json, merges in new thread_tag entries from today's digest,
    and writes it back. Called once per run so the index grows incrementally.
    """
    index_path = os.path.join(ARCHIVE_DIR, "thread_index.json")

    # Load existing index or start fresh
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            try:
                thread_index = json.load(f)
            except json.JSONDecodeError:
                thread_index = {}
    else:
        thread_index = {}

    digest_es = digest.get("es", digest)
    for story in digest_es.get("stories", []):
        tag = story.get("thread_tag")
        if not tag or not isinstance(tag, str):
            continue
        entry = {
            "date":     date_str,
            "headline": story.get("headline", ""),
        }
        if tag not in thread_index:
            thread_index[tag] = []
        # Avoid duplicates (in case run is re-executed for same date)
        existing_dates = {e["date"] for e in thread_index[tag]}
        if date_str not in existing_dates:
            thread_index[tag].append(entry)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(thread_index, f, ensure_ascii=False, indent=2)
    print(f"  [archive] Thread index updated ({len(thread_index)} tags).")
```

- [ ] **Step 2: Call _update_thread_index() in save_pretty_issue()**

In `save_pretty_issue()`, after `with open(filepath, ...) as f: f.write(html)`, add:

```python
    _update_thread_index(digest, today)
```

- [ ] **Step 3: Add Coverage Map and Thread Index to rebuild_index()**

In `rebuild_index()`, after the `charts_html` block (around line 242), add the following two new HTML sections. They go inside the `index_html` string, between the charts and the search input.

First, build the data for both sections at the top of `rebuild_index()`, after the `digest_data` load:

```python
    # ── Coverage Map: count thread_tag appearances ─────────────────────────
    tag_counts: dict[str, int] = {}
    thread_index_path = os.path.join(ARCHIVE_DIR, "thread_index.json")
    thread_index_data: dict = {}
    if os.path.exists(thread_index_path):
        with open(thread_index_path, encoding="utf-8") as f:
            try:
                thread_index_data = json.load(f)
            except json.JSONDecodeError:
                thread_index_data = {}
        for tag, entries in thread_index_data.items():
            tag_counts[tag] = len(entries)

    # Sort by count desc, top 10
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
```

Then, build the Coverage Map HTML:

```python
    coverage_map_html = ""
    if top_tags:
        max_count = top_tags[0][1] if top_tags else 1
        bars = ""
        for tag, count in top_tags:
            pct = int((count / max_count) * 100)
            bars += f"""
      <div style="margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <span style="font-family:Arial,sans-serif; font-size:10px; color:#3a4a54; font-weight:500;">{tag}</span>
          <span style="font-family:Arial,sans-serif; font-size:9px; color:#aab4bc;">{count}</span>
        </div>
        <div style="height:6px; background:#dde3e8; border-radius:3px;">
          <div style="height:6px; background:#3a4a54; border-radius:3px; width:{pct}%;"></div>
        </div>
      </div>"""
        coverage_map_html = f"""
  <div style="background:#f0f3f5; border:1px solid #cdd4d9; padding:24px 28px; margin-bottom:24px;">
    <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:16px;">Coverage Map — Top Threads</p>
    {bars}
  </div>"""
```

Then, build the Thread Index HTML:

```python
    thread_index_html = ""
    if thread_index_data:
        thread_sections = ""
        for tag, entries in sorted(thread_index_data.items(), key=lambda x: -len(x[1])):
            if len(entries) < 2:
                continue
            links = ""
            for entry in sorted(entries, key=lambda e: e["date"], reverse=True)[:5]:
                links += f"""
          <a href="{entry['date']}.html" style="display:block; text-decoration:none; padding:8px 0; border-bottom:1px solid #e4e9ec; font-family:Georgia,serif; font-size:13px; color:#1a1a1a; line-height:1.4;">
            <span style="font-family:Arial,sans-serif; font-size:9px; color:#aab4bc; display:block; margin-bottom:2px;">{entry['date']}</span>
            {entry['headline']}
          </a>"""
            thread_sections += f"""
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer; font-family:Arial,sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#3a4a54; padding:10px 0; border-bottom:1px solid #cdd4d9; list-style:none; display:flex; justify-content:space-between;">
          {tag}
          <span style="color:#aab4bc; font-weight:400;">{len(entries)} stories</span>
        </summary>
        <div style="padding-top:4px;">{links}</div>
      </details>"""
        if thread_sections:
            thread_index_html = f"""
  <div style="background:#f0f3f5; border:1px solid #cdd4d9; padding:24px 28px; margin-bottom:24px;">
    <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:16px;">Topic Threads</p>
    {thread_sections}
  </div>"""
```

- [ ] **Step 4: Insert both sections into index_html**

In the `index_html = f"""..."""` string, after `{charts_html}` and before the search-wrap div, add:

```python
  {coverage_map_html}
  {thread_index_html}
```

- [ ] **Step 5: Commit**

```bash
cd D:/GitHub/mexico-finance-brief
git add bot/archive.py
git commit -m "feat: add thread_index.json generation, Coverage Map, and Topic Threads to archive index"
```

---

## Task 11: End-to-end verification with mock mode

**Files:** None (verification only)

- [ ] **Step 1: Run the bot in mock mode with skip email**

```bash
cd D:/GitHub/mexico-finance-brief/bot
MOCK=true SKIP_EMAIL=true python main.py
```

Expected output contains:
- `[scorer]` lines (may not run in mock mode — scorer only runs in live mode, which is correct)
- `[summarizer]` loaded from mock
- `[archive]` Saved pretty issue
- `[archive]` Thread index updated
- `[archive]` Index rebuilt

- [ ] **Step 2: Open the generated archive HTML in a browser**

Open `D:/GitHub/mexico-finance-brief/docs/YYYY-MM-DD.html` (today's date).

Verify:
- Narrative thread block appears below editor note (only if digest has `narrative_thread` — old mock digest won't have it, which is correct and expected)
- No errors in console

- [ ] **Step 3: Open docs/index.html in browser**

Verify:
- Coverage Map section appears (may be empty if thread_index.json is empty — expected for first run)
- Topic Threads section appears (same caveat)
- Existing sentiment chart and issue cards still render correctly

- [ ] **Step 4: Final commit with branch note**

```bash
cd D:/GitHub/mexico-finance-brief
git status
git add -A
git commit -m "chore: end-to-end verification pass — all features wired on Dev-Nigg"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ 1A Pre-scoring: Tasks 1, 2, 3, 4, 5
- ✅ 1B Richer Claude output: Tasks 6, 7
- ✅ 2A Email design polish: Task 8
- ✅ 2B Archive design + Coverage Map + Thread Index: Tasks 9, 10
- ✅ Backward compatibility: all new fields use `.get()` with fallbacks
- ✅ Branch constraint: `Dev-Nigg` everywhere, `main` never touched

**Placeholder check:** No TBDs, all code blocks are complete.

**Type consistency:**
- `rank_articles()` defined in Task 3, called in Task 5 ✅
- `get_active_threads()` defined in Task 6, called in Task 5 ✅
- `summarize_news(articles, active_threads=active_threads)` — Task 7 adds the parameter, Task 5 passes it ✅
- `_narrative_thread(text)` defined in Task 8, called in Task 8's build_html update ✅
- `_update_thread_index(digest, today)` defined in Task 10, called in Task 10 ✅
- `thread_index_data` built in Task 10 step 3, used in same step ✅
