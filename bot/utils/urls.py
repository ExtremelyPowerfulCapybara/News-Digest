# ─────────────────────────────────────────────
#  utils/urls.py  —  Public URL helpers
#
#  All public URLs are derived from PUBLIC_ARCHIVE_BASE_URL env var.
#  Example: PUBLIC_ARCHIVE_BASE_URL=http://123.45.67.89
# ─────────────────────────────────────────────

import os


def _base() -> str:
    return os.environ.get("PUBLIC_ARCHIVE_BASE_URL", "").rstrip("/")


def build_issue_url(date_str: str) -> str:
    """Return the public URL for a given issue date, e.g. http://<VPS>/2026-04-09.html"""
    base = _base()
    if not base:
        return ""
    return f"{base}/{date_str}.html"


def build_image_url(filename: str) -> str:
    """Return the public URL for an image asset, e.g. http://<VPS>/images/2026-04-09.png"""
    base = _base()
    if not base:
        return ""
    return f"{base}/images/{filename}"


def build_archive_index_url() -> str:
    """Return the public URL for the archive index page."""
    base = _base()
    if not base:
        return ""
    return f"{base}/index.html"
