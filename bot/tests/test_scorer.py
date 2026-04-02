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
    assert len(result) == 2
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
