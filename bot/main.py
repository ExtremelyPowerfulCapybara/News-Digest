# ─────────────────────────────────────────────
#  main.py  —  Entry point
# ─────────────────────────────────────────────

import os
import random
from fetcher     import fetch_news
from summarizer  import summarize_news
from market_data import fetch_tickers, fetch_currency_table, fetch_weather
from storage     import save_digest, get_week_stories, is_friday
from renderer    import build_html, build_plain
from delivery    import send_email
from archive     import save_pretty_issue
from config      import DIGEST_DIR, AUTHOR_NAMES, AUTHOR_TITLES
from wordcloud_gen import generate_wordcloud, wordcloud_as_base64


def get_issue_number() -> int:
    """Count existing digests to auto-increment issue number."""
    if not os.path.exists(DIGEST_DIR):
        return 1
    return len([f for f in os.listdir(DIGEST_DIR) if f.endswith(".json")]) + 1


def run():
    print("=" * 50)
    print("  Mexico Finance Brief — starting run")
    print("=" * 50)

    # ── 1. Fetch market data (fast, no LLM needed) ──
    print("\n[1/5] Fetching market data...")
    tickers  = fetch_tickers()
    currency = fetch_currency_table()
    weather  = fetch_weather()

    # ── 2. Fetch news articles ──────────────────────
    print("\n[2/5] Fetching news articles...")
    articles = fetch_news()
    if not articles:
        print("  No articles found. Check your NewsAPI key or topics.")
        return

    # ── 3. Summarize with Claude ────────────────────
    print(f"\n[3/5] Summarizing {len(articles)} articles with Claude...")
    digest    = summarize_news(articles)
    digest_es = digest.get("es", digest)  # Spanish — used in email
    digest_en = digest.get("en", digest)  # English — used in archive toggle

    # ── 4. Save digest to disk ──────────────────────
    print("\n[4/5] Saving digest...")
    save_digest(digest, {"tickers": tickers, "currency": currency}, weather)

    # ── 5. Build and send email ─────────────────────
    print("\n[5/5] Building and sending email...")
    friday       = is_friday()
    week_stories = get_week_stories() if friday else []
    issue_num    = get_issue_number()

    # Pick a random pen name + title — generated once so email and archive match
    author = f"{random.choice(AUTHOR_NAMES)}, {random.choice(AUTHOR_TITLES)}"
    print(f"  [author] Today's byline: {author}")

    # Generate word cloud on Fridays
    wordcloud_filename = None
    if friday:
        print("  [wordcloud] Generating weekly word cloud...")
        wordcloud_filename = generate_wordcloud()

    html  = build_html(
        digest             = digest_es,
        tickers            = tickers,
        currency           = currency,
        weather            = weather,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
    )
    plain = build_plain(digest_es, author=author)

    send_email(html, plain)

    # ── 6. Save pretty HTML to archive ─────────────────
    print("\n[6/6] Saving to archive...")
    save_pretty_issue(
        digest             = digest,
        tickers            = tickers,
        currency           = currency,
        weather            = weather,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
    )

    print("\n" + "=" * 50)
    print(f"  Done. Issue #{issue_num} delivered.")
    if friday:
        print("  Week-in-review included.")
    print("=" * 50)


if __name__ == "__main__":
    run()
