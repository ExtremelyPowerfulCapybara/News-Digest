# ---------------------------------------------
#  main.py  --  Entry point
# ---------------------------------------------

import os
import random
from concurrent.futures import ThreadPoolExecutor
from fetcher     import fetch_news
from summarizer  import summarize_news
from market_data import fetch_tickers, fetch_secondary_tickers, fetch_currency_table
from storage     import save_digest, get_week_stories, get_recent_urls, is_friday
from renderer    import build_html, build_plain
from delivery    import send_email
from archive     import save_pretty_issue
from config      import DIGEST_DIR, AUTHOR_NAMES, AUTHOR_TITLES, MOCK_MODE, SKIP_EMAIL
from mock_data   import load_mock
from wordcloud_gen import generate_wordcloud


def get_issue_number() -> int:
    """Count existing digests to auto-increment issue number."""
    if not os.path.exists(DIGEST_DIR):
        return 1
    return len([f for f in os.listdir(DIGEST_DIR) if f.endswith(".json")]) + 1


def run():
    print("=" * 50)
    print("  Mexico Finance Brief -- starting run")
    if MOCK_MODE:
        print("  *** MOCK MODE -- no NewsAPI or Anthropic calls ***")
    if SKIP_EMAIL:
        print("  *** SKIP EMAIL -- archive/preview only ***")
    print("=" * 50)

    # ── 1. Fetch market data (fast, no LLM needed) ──
    print("\n[1/5] Fetching market data...")
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_tickers   = pool.submit(fetch_tickers)
        fut_secondary = pool.submit(fetch_secondary_tickers)
        fut_currency  = pool.submit(fetch_currency_table)
        tickers           = fut_tickers.result()
        secondary_tickers = fut_secondary.result()
        currency          = fut_currency.result()

    # -- 2+3. Fetch news + summarize (or load mock) --
    if MOCK_MODE:
        print("\n[2-3/5] MOCK MODE -- loading saved digest...")
        mock     = load_mock()
        articles = mock["articles"]
        digest   = mock["digest"]
    else:
        print("\n[2/5] Fetching news articles...")
        prior_urls = get_recent_urls(days=5)
        print(f"  [dedup] Excluding {len(prior_urls)} URLs seen in the last 5 days")
        articles = fetch_news(prior_urls=prior_urls)
        if not articles:
            print("  No articles found. Check your NewsAPI key or topics.")
            return
        print(f"\n[3/5] Summarizing {len(articles)} articles with Claude...")
        digest = summarize_news(articles)

    digest_es = digest.get("es", digest)  # Spanish -- used in email
    digest_en = digest.get("en", digest)  # English -- used in archive toggle

    # -- 4. Save digest to disk --
    print("\n[4/5] Saving digest...")
    save_digest(digest, {"tickers": tickers, "currency": currency})

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
        secondary_tickers  = secondary_tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
    )
    plain = build_plain(digest_es, author=author)

    if SKIP_EMAIL:
        print("  [delivery] SKIP_EMAIL set — skipping send.")
    else:
        send_email(html, plain)

    # ── 6. Save pretty HTML to archive ─────────────────
    print("\n[6/6] Saving to archive...")
    save_pretty_issue(
        digest             = digest,
        tickers            = tickers,
        secondary_tickers  = secondary_tickers,
        currency           = currency,
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
