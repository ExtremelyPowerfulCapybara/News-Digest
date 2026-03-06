# ─────────────────────────────────────────────
#  fetcher.py  —  News articles from NewsAPI
# ─────────────────────────────────────────────

import requests
from scraper import scrape_article
from config import (
    NEWS_API_KEY, TOPICS, LANGUAGE,
    MAX_ARTICLES_PER_TOPIC, MAX_ARTICLE_CHARS,
    MAX_ARTICLES_PER_SOURCE
)


def fetch_news() -> list[dict]:
    seen_urls    = set()
    all_articles = []

    for topic in TOPICS:
        print(f"  [fetcher] Topic: {topic}")
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={topic}&language={LANGUAGE}"
            f"&sortBy=publishedAt&pageSize={MAX_ARTICLES_PER_TOPIC}"
            f"&apiKey={NEWS_API_KEY}"
        )
        try:
            data = requests.get(url, timeout=10).json()
        except Exception as e:
            print(f"  [fetcher] Error: {e}")
            continue

        # ── Per-source cap is per topic loop, not global ──
        topic_source_count = {}

        for a in data.get("articles", []):
            article_url = a.get("url", "")
            if not article_url or article_url in seen_urls:
                continue
            if "[Removed]" in a.get("title", ""):
                continue

            source_name = a.get("source", {}).get("name", "Unknown")
            if topic_source_count.get(source_name, 0) >= MAX_ARTICLES_PER_SOURCE:
                continue

            seen_urls.add(article_url)

            full_text = scrape_article(article_url, max_chars=MAX_ARTICLE_CHARS)
            content   = full_text if full_text else a.get("description", "")
            if not content:
                continue

            topic_source_count[source_name] = topic_source_count.get(source_name, 0) + 1
            all_articles.append({
                "title":   a.get("title", "").strip(),
                "content": content,
                "source":  source_name,
                "url":     article_url,
            })

        topic_sources = list(topic_source_count.keys())
        print(f"  [fetcher] '{topic}': {sum(topic_source_count.values())} articles from {len(topic_sources)} sources: {topic_sources}")

    print(f"  [fetcher] {len(all_articles)} articles collected total")
    return all_articles
