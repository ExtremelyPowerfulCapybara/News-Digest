# ─────────────────────────────────────────────
#  wordcloud_gen.py  —  Weekly word cloud
#  Generates a PNG from the week's headlines
#  and story bodies. Called on Fridays only.
# ─────────────────────────────────────────────

import os
import base64
from datetime import date, timedelta
from config import DIGEST_DIR, ARCHIVE_DIR

# Words to exclude from the cloud — bilingual (ES + EN).
# All entries are lowercase ASCII (no accents) because _strip_accents()
# normalises the text before the cloud is built, so matching is reliable.
STOPWORDS = {
    # ── Spanish articles ──────────────────────────────────────────────────
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    # ── Spanish prepositions ──────────────────────────────────────────────
    "de", "del", "al", "a", "en", "con", "por", "para", "sin", "sobre",
    "entre", "hasta", "desde", "hacia", "ante", "bajo", "contra", "durante",
    "mediante", "segun", "tras", "versus", "via",
    # ── Spanish conjunctions ──────────────────────────────────────────────
    "y", "e", "o", "u", "ni", "que", "pero", "sino", "aunque", "porque",
    "como", "cuando", "si", "donde", "mientras", "pues", "ya", "sea",
    # ── Spanish pronouns ──────────────────────────────────────────────────
    "yo", "tu", "el", "ella", "nosotros", "ellos", "ellas", "se", "le",
    "lo", "les", "nos", "su", "sus", "este", "esta", "estos", "estas",
    "ese", "esa", "esos", "esas", "aquel", "aquella", "ello",
    # ── Spanish auxiliaries & common verbs ───────────────────────────────
    "es", "son", "fue", "ser", "estar", "ha", "han", "hay", "habia",
    "tiene", "tienen", "tuvo", "tener", "hace", "hizo", "hacer",
    "puede", "pueden", "pudo", "poder", "dijo", "dice", "decir",
    "va", "van", "ir", "seria", "sera", "seran",
    # ── Spanish adverbs & fillers ─────────────────────────────────────────
    "mas", "muy", "bien", "tambien", "asi", "aun", "solo", "no", "si",
    "tan", "tanto", "menos", "mismo", "misma", "cada",
    "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras",
    "nuevo", "nueva", "nuevos", "nuevas",
    # ── Spanish time words ────────────────────────────────────────────────
    "ano", "anos", "mes", "dia", "dias", "semana", "hoy", "ayer",
    "lunes", "martes", "miercoles", "jueves", "viernes",
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    # ── English articles, prepositions & conjunctions ─────────────────────
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "into", "over", "after", "about",
    "than", "then", "when", "while", "amid", "against", "across",
    # ── English pronouns & determiners ───────────────────────────────────
    "it", "its", "they", "their", "them", "he", "she", "his", "her",
    "we", "our", "us", "you", "your", "i", "my", "me", "this", "that",
    "these", "those", "such", "each", "both", "all", "other",
    # ── English auxiliaries & common verbs ───────────────────────────────
    "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "said", "says", "say",
    # ── English adverbs & fillers ─────────────────────────────────────────
    "not", "no", "so", "up", "out", "more", "also", "what",
    "which", "who", "how", "new", "already", "nine", "sunday",
    # ── English time words ────────────────────────────────────────────────
    "week", "monday", "tuesday", "wednesday", "thursday", "friday",
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
    # ── Years ─────────────────────────────────────────────────────────────
    "2024", "2025", "2026",
}


def _strip_accents(text: str) -> str:
    """Normalize accented characters to ASCII so stopword matching works."""
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


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
            digest  = digest.get("es", digest)  # unwrap bilingual structure
            stories = digest.get("stories", [])
            for s in stories:
                text_parts.append(s.get("headline", ""))
                text_parts.append(s.get("body", ""))
            text_parts.append(digest.get("editor_note", ""))
        except Exception as e:
            print(f"  [wordcloud] Could not load {path}: {e}")

    return _strip_accents(" ".join(text_parts))


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
            min_word_length  = 3,
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
            min_word_length  = 3,
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
