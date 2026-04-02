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
        hours_old = max(hours_old, 0)  # guard against future-dated articles
    except Exception:
        return 0.1
    if hours_old < 6:   return 1.0
    if hours_old < 12:  return 0.7
    if hours_old < 24:  return 0.4
    return 0.1


def _authority_score(source_name: str) -> float:
    """1.0 for Tier 1 sources, 0.6 for Tier 2, 0.3 for unknown."""
    from config import SOURCE_TIERS
    name_lower = (source_name or "").lower()
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

    Scoring weights (sum to 0.80; max composite score is 0.80):
      Freshness  30%  — recency of publication
      Authority  25%  — source tier (config.SOURCE_TIERS)
      Relevance  25%  — keyword overlap with config.TOPICS

    Uniqueness is handled as a post-sort greedy filter (not a weight):
    articles with >60% headline word overlap against already-accepted
    articles are dropped. Overlap is measured from the candidate's perspective
    (len(candidate_words & accepted_words) / len(candidate_words)), so short
    headlines are filtered more aggressively than long ones — intentional.
    """
    from config import TOPICS, MAX_ARTICLES_FOR_CLAUDE
    if now is None:
        now = datetime.now(timezone.utc)

    # Score each article on the three weighted factors
    scored = []
    for article in articles:
        f = _freshness_score(article.get("publishedAt"), now) * 0.30
        a = _authority_score(article.get("source") or "")      * 0.25
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
