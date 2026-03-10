# ─────────────────────────────────────────────
#  storage.py  —  Save digests, build week recap
# ─────────────────────────────────────────────

import os
import json
from datetime import date, timedelta
from config import DIGEST_DIR, ARCHIVE_DIR


def save_digest(digest: dict, market: dict, weather: dict) -> None:
    os.makedirs(DIGEST_DIR, exist_ok=True)
    today = date.today().isoformat()
    payload = {
        "date":    today,
        "digest":  digest,
        "market":  market,
        "weather": weather,
    }
    path = os.path.join(DIGEST_DIR, f"{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  [storage] Saved digest to {path}")


def load_digest(target_date: str) -> dict | None:
    path = os.path.join(DIGEST_DIR, f"{target_date}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_week_stories() -> list[dict]:
    """
    Returns the top story from each day Mon-Thu of the current week.
    Called on Fridays to build the week-in-review timeline.
    Only returns days that have a saved digest.
    """
    today     = date.today()
    monday    = today - timedelta(days=today.weekday())
    day_names = ["Lun", "Mar", "Mié", "Jue", "Vie"]
    stories   = []

    for i in range(5):
        day        = monday + timedelta(days=i)
        day_str    = day.isoformat()
        day_label  = day_names[i]
        data       = load_digest(day_str)

        if not data:
            continue

        digest_obj = data.get("digest", {})
        digest_es  = digest_obj.get("es", digest_obj)  # bilingual fallback
        top_stories = digest_es.get("stories", [])
        if not top_stories:
            continue

        top = top_stories[0]
        # Mark as "active" (darker dot) if it was a high-impact day
        # Simple heuristic: non-neutral sentiment = active
        sentiment = digest_es.get("sentiment", {})
        active    = sentiment.get("label_es", sentiment.get("label", "Cauteloso")) != "Cauteloso"

        stories.append({
            "day":      day_label,
            "active":   active,
            "tag":      top.get("tag", "Macro"),
            "headline": top.get("headline", ""),
            "body":     top.get("body", "")[:160] + "...",
        })

    return stories


def is_friday() -> bool:
    return date.today().weekday() == 4
