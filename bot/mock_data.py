# ---------------------------------------------
#  mock_data.py  --  Fixture loader for test runs
#
#  When MOCK=true, main.py calls load_mock()
#  instead of hitting NewsAPI or Anthropic.
#  Loads the most recent bilingual digest from
#  the digests/ folder and synthesises a fake
#  articles list from the stored stories so the
#  rest of the pipeline (renderer, archive,
#  delivery) runs exactly as in production.
# ---------------------------------------------

import os
import json
from config import DIGEST_DIR


def load_mock() -> dict:
    """
    Returns {"articles": [...], "digest": {...}}
    using the most recent bilingual digest on disk.
    Raises FileNotFoundError if no suitable digest exists.
    """
    path = _find_latest_bilingual_digest()
    print(f"  [mock] Loading fixture: {path}")

    with open(path, encoding="utf-8") as f:
        saved = json.load(f)

    digest = saved.get("digest", saved)

    # Validate bilingual structure
    if "es" not in digest:
        raise ValueError(f"[mock] Digest at {path} is not bilingual (missing 'es' key).")

    # Synthesise a minimal articles list from the ES stories
    # so any code that inspects `articles` doesn't blow up.
    articles = []
    for story in digest.get("es", {}).get("stories", []):
        articles.append({
            "title":   story.get("headline", ""),
            "content": story.get("body", ""),
            "source":  story.get("source", ""),
            "url":     story.get("url", ""),
        })

    print(f"  [mock] Loaded {len(articles)} stories from fixture.")
    return {"articles": articles, "digest": digest}


def _find_latest_bilingual_digest() -> str:
    """
    Scans DIGEST_DIR for .json files, returns the path of the
    most recent one that has a bilingual (es/en) structure.
    """
    if not os.path.exists(DIGEST_DIR):
        raise FileNotFoundError(f"[mock] Digest directory not found: {DIGEST_DIR}")

    candidates = sorted(
        [f for f in os.listdir(DIGEST_DIR) if f.endswith(".json")],
        reverse=True,  # most recent first (YYYY-MM-DD sort works lexically)
    )

    for filename in candidates:
        path = os.path.join(DIGEST_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            digest = data.get("digest", data)
            if "es" in digest and "en" in digest:
                return path
        except Exception:
            continue

    raise FileNotFoundError(
        "[mock] No bilingual digest found in digests/. "
        "Run a real issue first to generate a fixture."
    )
