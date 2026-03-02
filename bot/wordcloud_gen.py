# ─────────────────────────────────────────────
#  wordcloud_gen.py  —  Weekly word cloud
#  Generates a PNG from the week's headlines
#  and story bodies. Called on Fridays only.
# ─────────────────────────────────────────────

import os
import base64
from datetime import date, timedelta
from config import DIGEST_DIR, ARCHIVE_DIR

# Words to exclude from the cloud
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "that",
    "this", "these", "those", "it", "its", "it's", "they", "their", "them",
    "he", "she", "his", "her", "we", "our", "us", "you", "your", "i",
    "my", "me", "not", "no", "so", "if", "up", "out", "about", "into",
    "over", "after", "more", "also", "than", "then", "when", "what",
    "which", "who", "how", "all", "both", "each", "such", "other", "new",
    "said", "says", "say", "while", "amid", "week", "monday", "tuesday",
    "wednesday", "thursday", "friday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "2024", "2025", "2026",
}


def _collect_week_text() -> str:
    """Collects all headlines and story bodies from Mon-Fri digests."""
    import json
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    text_parts = []

    for i in range(5):
        day     = monday + timedelta(days=i)
        path    = os.path.join(DIGEST_DIR, f"{day.isoformat()}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            digest  = data.get("digest", {})
            stories = digest.get("stories", [])
            for s in stories:
                text_parts.append(s.get("headline", ""))
                text_parts.append(s.get("body", ""))
            text_parts.append(digest.get("editor_note", ""))
        except Exception as e:
            print(f"  [wordcloud] Could not load {path}: {e}")

    return " ".join(text_parts)


def generate_wordcloud() -> str | None:
    """
    Generates a word cloud PNG from the week's content.
    Saves to docs/wordcloud-YYYY-WNN.png
    Returns the filename (not full path) or None on failure.
    """
    try:
        from wordcloud import WordCloud
        from PIL import Image
        import numpy as np
    except ImportError:
        print("  [wordcloud] wordcloud or Pillow not installed — skipping")
        return None

    text = _collect_week_text()
    if not text.strip():
        print("  [wordcloud] No text found for this week — skipping")
        return None

    # ── Colour palette matching newsletter design ──
    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        palette = [
            "#1a1a1a",  # dark
            "#3a4a54",  # mid
            "#4a9e6a",  # green
            "#b84a3a",  # red
            "#9a6a1a",  # amber
            "#aab4bc",  # light
        ]
        import random
        # Bias larger words toward darker colours
        if font_size > 40:
            return random.choice(palette[:2])
        elif font_size > 20:
            return random.choice(palette[1:4])
        else:
            return random.choice(palette[3:])

    # ── Week label for filename ──
    today      = date.today()
    week_num   = today.isocalendar()[1]
    year       = today.year
    filename   = f"wordcloud-{year}-W{week_num:02d}.png"
    filepath   = os.path.join(ARCHIVE_DIR, filename)

    try:
        wc = WordCloud(
            width            = 1200,
            height           = 480,
            background_color = "#f0f3f5",
            stopwords        = STOPWORDS,
            color_func       = color_func,
            max_words        = 80,
            min_font_size    = 10,
            max_font_size    = 90,
            prefer_horizontal= 0.85,
            collocations     = False,
            margin           = 8,
        ).generate(text)

        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        wc.to_file(filepath)
        print(f"  [wordcloud] Saved to {filepath}")
        return filename

    except Exception as e:
        print(f"  [wordcloud] Generation failed: {e}")
        return None


def wordcloud_as_base64() -> str | None:
    """
    Generates the word cloud and returns it as a base64 data URI
    for embedding directly in HTML — no external file needed for email.
    """
    try:
        from wordcloud import WordCloud
        import io
    except ImportError:
        return None

    text = _collect_week_text()
    if not text.strip():
        return None

    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        palette = ["#1a1a1a", "#3a4a54", "#4a9e6a", "#b84a3a", "#9a6a1a", "#aab4bc"]
        import random
        if font_size > 40:
            return random.choice(palette[:2])
        elif font_size > 20:
            return random.choice(palette[1:4])
        else:
            return random.choice(palette[3:])

    try:
        wc = WordCloud(
            width            = 1200,
            height           = 480,
            background_color = "#f0f3f5",
            stopwords        = STOPWORDS,
            color_func       = color_func,
            max_words        = 80,
            min_font_size    = 10,
            max_font_size    = 90,
            prefer_horizontal= 0.85,
            collocations     = False,
            margin           = 8,
        ).generate(text)

        buf = io.BytesIO()
        wc.to_image().save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    except Exception as e:
        print(f"  [wordcloud] Base64 generation failed: {e}")
        return None
