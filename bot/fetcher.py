# ─────────────────────────────────────────────
#  fetcher.py  —  News articles from NewsAPI
# ─────────────────────────────────────────────

import requests
from scraper import scrape_article
from config import (
    NEWS_API_KEY, TOPICS, LANGUAGE,
    MAX_ARTICLES_PER_TOPIC, MAX_ARTICLE_CHARS,
    NEWS_DOMAINS_STR
)


def fetch_news() -> list[dict]:
    seen_urls = set()
    all_articles = []

    for topic in TOPICS:
        print(f"  [fetcher] Topic: {topic}")
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={topic}&language={LANGUAGE}"
            f"&sortBy=publishedAt&pageSize={MAX_ARTICLES_PER_TOPIC}"
            f"&domains={NEWS_DOMAINS_STR}"
            f"&apiKey={NEWS_API_KEY}"
        )
        print(f"  [fetcher] Filtering to {len(NEWS_DOMAINS_STR.split(','))} whitelisted domains")
        try:
            data = requests.get(url, timeout=10).json()
        except Exception as e:
            print(f"  [fetcher] Error: {e}")
            continue

        for a in data.get("articles", []):
            article_url = a.get("url", "")
            if not article_url or article_url in seen_urls:
                continue
            if "[Removed]" in a.get("title", ""):
                continue
            seen_urls.add(article_url)

            full_text = scrape_article(article_url, max_chars=MAX_ARTICLE_CHARS)
            content   = full_text if full_text else a.get("description", "")
            if not content:
                continue

            all_articles.append({
                "title":   a.get("title", "").strip(),
                "content": content,
                "source":  a.get("source", {}).get("name", "Unknown"),
                "url":     article_url,
            })

    print(f"  [fetcher] {len(all_articles)} articles collected")
    return all_articles
