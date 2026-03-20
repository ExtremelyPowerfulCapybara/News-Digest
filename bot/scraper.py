# ─────────────────────────────────────────────
#  scraper.py  —  Full article text extractor
# ─────────────────────────────────────────────

import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Per-domain CSS selectors targeting the article body specifically.
# Tried before the generic <p> scan to avoid nav/sidebar/related boilerplate.
# Attribute-contains selectors (*=) are robust against minified class names.
_DOMAIN_SELECTORS = {
    "bloomberglinea.com":   "[class*='article-body'], [class*='ArticleBody']",
    "reuters.com":          "[class*='article-body__content'], [class*='ArticleBody']",
    "expansion.mx":         "[class*='article-body'], [class*='ArticleContent']",
    "infobae.com":          ".article-body, [class*='article-body']",
    "elfinanciero.com.mx":  ".nota-cuerpo, [class*='article-body'], [class*='nota-body']",
    "eleconomista.com.mx":  "[class*='article-body'], [class*='nota-content']",
    "ambito.com":           "[class*='article-body'], [class*='content-body']",
    "elpais.com":           ".a_c, [class*='article-body']",
    "cincodias.elpais.com": ".a_c, [class*='article-body']",
    "ft.com":               "[class*='article-body'], .article__content",
    "wsj.com":              "[class*='article-content'], [class*='WSJTheme--article']",
    "apnews.com":           ".article-body, [class*='RichTextStoryBody']",
    "lanacion.com.ar":      "[class*='article-body'], .article__body",
    "eluniversal.com.mx":   "[class*='field-body'], [class*='article-body']",
}


def scrape_article(url: str, max_chars: int = 3000) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "figure"]):
            tag.decompose()

        # Try domain-specific selector first
        text   = ""
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        sel    = _DOMAIN_SELECTORS.get(domain)
        if sel:
            container = soup.select_one(sel)
            if container:
                text = " ".join(p.get_text(separator=" ") for p in container.find_all("p"))
                text = " ".join(text.split())

        # Fall back to generic <p> scan
        if len(text) < 100:
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text(separator=" ") for p in paragraphs)
            text = " ".join(text.split())

        if len(text) < 100:
            return None
        return text[:max_chars]
    except Exception as e:
        print(f"  [scraper] Could not fetch {url}: {e}")
        return None
