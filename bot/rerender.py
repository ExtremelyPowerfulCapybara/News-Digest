#!/usr/bin/env python3
# bot/rerender.py
# ─────────────────────────────────────────────
#  Re-render a single archive issue from its
#  stored digest JSON. Useful after manually
#  setting visual.hero_selected.
#
#  Usage (run from bot/):
#    python rerender.py 2026-04-06
#
#  Reads:  digests/YYYY-MM-DD.json
#  Writes: docs/YYYY-MM-DD.html  (overwrites)
# ─────────────────────────────────────────────

import sys
import os
import json
from datetime import date

from pretty_renderer import build_pretty_html
from config          import DIGEST_DIR, ARCHIVE_DIR


def rerender(target_date: str) -> None:
    digest_path = os.path.join(DIGEST_DIR, f"{target_date}.json")
    if not os.path.exists(digest_path):
        print(f"[rerender] ERROR: no digest found at {digest_path}")
        sys.exit(1)

    with open(digest_path, encoding="utf-8") as f:
        stored = json.load(f)

    digest   = stored["digest"]
    market   = stored.get("market", {})
    visual   = stored.get("visual")
    tickers  = market.get("tickers", [])
    currency = market.get("currency", {})

    # Approximate issue number from digest count
    all_digests = sorted(f for f in os.listdir(DIGEST_DIR) if f.endswith(".json"))
    issue_num   = all_digests.index(f"{target_date}.json") + 1

    # Friday detection for the target date
    d      = date.fromisoformat(target_date)
    friday = d.weekday() == 4

    # Week stories: only meaningful if re-rendering a Friday issue
    week_stories = []
    if friday:
        from storage import get_week_stories
        week_stories = get_week_stories()

    # Word cloud: check if a PNG exists for that ISO week
    year, week, _ = d.isocalendar()
    wc_filename   = f"wordcloud-{year}-W{week:02d}.png"
    wc_path       = os.path.join(ARCHIVE_DIR, wc_filename)
    wordcloud_filename = wc_filename if os.path.exists(wc_path) else None

    html = build_pretty_html(
        digest             = digest,
        tickers            = tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = "",          # original author not stored; left blank
        secondary_tickers  = None,        # secondary_tickers are not persisted
        visual             = visual,
    )

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    out_path = os.path.join(ARCHIVE_DIR, f"{target_date}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[rerender] Written to {out_path}")
    if visual and visual.get("hero_selected"):
        print(f"[rerender] Hero image: {visual['hero_selected']}")
    else:
        print("[rerender] No hero image (hero_selected is null -- set it in the digest JSON first)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rerender.py YYYY-MM-DD")
        sys.exit(1)
    rerender(sys.argv[1])
