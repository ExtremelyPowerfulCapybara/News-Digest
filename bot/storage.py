# ─────────────────────────────────────────────
#  storage.py  —  Save digests, build week recap
# ─────────────────────────────────────────────

import os
import json
from datetime import date, timedelta
from config import DIGEST_DIR, ARCHIVE_DIR


def save_digest(digest: dict, market: dict, visual: dict | None = None) -> None:
    os.makedirs(DIGEST_DIR, exist_ok=True)
    today = date.today().isoformat()
    path  = os.path.join(DIGEST_DIR, f"{today}.json")

    # Preserve any existing visual data so hero_selected survives reruns.
    # New values win except where the existing value is non-None and the
    # incoming value is None (e.g. hero_selected set by a manual edit).
    if visual is not None and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing_visual = json.load(f).get("visual", {})
        visual = {
            k: (existing_visual[k] if (k in existing_visual and existing_visual[k] is not None and visual.get(k) is None) else v)
            for k, v in visual.items()
        }

    payload = {
        "date":   today,
        "digest": digest,
        "market": market,
    }
    if visual is not None:
        payload["visual"] = visual

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


def get_recent_urls(days: int = 5) -> set[str]:
    """
    Returns all article URLs that appeared in the last N digests.
    Used by the fetcher to skip stories already covered this week.
    """
    urls  = set()
    today = date.today()
    for i in range(1, days + 1):
        data = load_digest((today - timedelta(days=i)).isoformat())
        if not data:
            continue
        digest_es = data.get("digest", {})
        digest_es = digest_es.get("es", digest_es)
        for story in digest_es.get("stories", []):
            url = story.get("url", "")
            if url:
                urls.add(url)
    return urls


def get_active_threads() -> list[str]:
    """
    Returns thread_tag values that appeared >=2 times across the last 5 daily digests.
    Injected into the Claude prompt so it can tag continuing story threads.
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


def get_week_sentiment() -> list[dict]:
    """
    Returns sentiment data for each available day Mon-Fri of the current week.
    Used on Fridays to render the weekly sentiment chart.
    Each entry: { day, position, label_en }
    """
    today     = date.today()
    monday    = today - timedelta(days=today.weekday())
    day_names = ["Lun", "Mar", "Mi\u00e9", "Jue", "Vie"]
    result    = []

    for i in range(5):
        day  = monday + timedelta(days=i)
        data = load_digest(day.isoformat())
        if not data:
            continue
        digest_es = data.get("digest", {})
        digest_es = digest_es.get("es", digest_es)
        sentiment = digest_es.get("sentiment", {})
        result.append({
            "day":      day_names[i],
            "position": int(sentiment.get("position", 50)),
            "label_en": sentiment.get("label_en", sentiment.get("label", "Cautious")),
        })

    return result


def get_upcoming_calendar(n: int = 5) -> list[tuple]:
    """Returns the next N upcoming economic calendar events from today."""
    from config import ECONOMIC_CALENDAR
    today    = date.today()
    upcoming = []
    for date_str, label, etype in ECONOMIC_CALENDAR:
        event_date = date.fromisoformat(date_str)
        delta = (event_date - today).days
        if delta >= 0:
            upcoming.append((event_date, label, etype, delta))
    upcoming.sort(key=lambda x: x[0])
    return upcoming[:n]


def is_friday() -> bool:
    return date.today().weekday() == 4
