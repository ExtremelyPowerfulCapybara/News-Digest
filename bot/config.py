# ─────────────────────────────────────────────
#  config.py  —  Settings + secrets
#
#  Secrets are read from environment variables
#  so they're never committed to the repo.
#  On GitHub Actions they come from repo secrets.
#  Locally, create a .env file or export them
#  in your terminal before running.
# ─────────────────────────────────────────────

import os

# ── Secrets (never commit these) ─────────────
NEWS_API_KEY      = os.environ.get("NEWS_API_KEY",      "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMAIL_SENDER      = os.environ.get("EMAIL_SENDER",      "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD",    "")

# Subscribers — comma-separated in the env var
# e.g. SUBSCRIBERS="you@gmail.com,friend@gmail.com"
_subs_env   = os.environ.get("SUBSCRIBERS", EMAIL_SENDER)
SUBSCRIBERS = [s.strip() for s in _subs_env.split(",") if s.strip()]

# ── Newsletter identity (safe to commit) ─────
NEWSLETTER_NAME    = "The Opening Bell"
NEWSLETTER_TAGLINE = "Context before the noise"
AUTHOR_NAME        = "Los 3"

# ── Rotating pen names ────────────────────────
AUTHOR_NAMES = [
    "Drew Downing",
    "Cora Lation",
    "Russell Bearings",
    "Hal F. Life",
    "Carrie Trade",
    "Bea Rish",
    "Buck N. Yields",
    "Ray Tio",
    "Stan Dard Deviation",
    "Cliff N. Overhang",
    "Mort I. Fication",
    "Barry Cade",
    "Rex Cession",
    "Hugh Liquidity",
    "Art Bitrage",
    "Bill Ateral",
    "Mac Roeconomics",
    "Lev Erage",
    "Cal Lateral",
    "Phil Ation",
    "Chip Deflation",
    "Vera Tility",
]

AUTHOR_TITLES = [
    "Director of Mildly Concerning Developments",
    "Senior Fellow, Bureau of Controlled Panic",
    "Chairman of the Committee on 'It's Fine'",
    "Principal Strategist, Gradual Decay",
    "Global Head of Conditional Optimism",
    "Custodian of Forward Guidance and Other Myths",
    "Deputy Undersecretary of Controlled Descent",
    "Executive Director of Fragile Equilibrium",
    "Chief Architect of Confident Uncertainty",
    "Senior Fellow, Institute of Permanent Volatility",
    "Visiting Scholar, Department of Inevitable Outcomes",
    "Head of Preemptive Disappointment",
    "Chief Correspondent, Bureau of Things Already Priced In",
    "Director of Soft Landings (Emeritus)",
    "Senior Analyst, Office of Delayed Consequences",
    "Minister of Transitory Phenomena",
    "Head of Quantitative Vibes",
    "Assistant to the Regional Hegemon",
    "Chief of Staff, Monetary Policy Theater",
    "Commissioner of Yield Curve Interpretive Dance",
    "Secretary General of the Ad Hoc Liquidity Committee",
    "Distinguished Chair of Optimism Suppression",
    "Lead Correspondent, The Structural Adjustment Beat",
    "Director of Things That Are Technically Not a Crisis",
    "Senior Vice President of Premature Conclusions",
    "Keeper of the Dot Plot",
    "Ambassador-at-Large for Unintended Consequences",
]

# ── News preferences ──────────────────────────
TOPICS                 = ["finanzas", "economía", "México", "comercio", "mercados", "política", "criptomonedas"]
LANGUAGE               = "es"
MAX_ARTICLES_PER_TOPIC  = 5
MAX_ARTICLES_PER_SOURCE = 1   # cap per outlet across all topics
MAX_ARTICLE_CHARS       = 3000

# ── Domain allowlist ─────────────────────────
# NewsAPI accepts up to 20 domains as a comma-separated string.
# Only articles from these outlets will be fetched.
NEWS_DOMAINS = [
    # Primary: LatAm & Mexico financial
    "bloomberglinea.com",
    "elfinanciero.com.mx",
    "eleconomista.com.mx",
    "expansion.mx",
    # Primary: Global Spanish financial
    "elpais.com",
    "cincodias.elpais.com",
    "ambito.com",
    # Primary: Wire services
    "reuters.com",
    "apnews.com",
    # Secondary: Regional depth
    "infobae.com",
    "lanacion.com.ar",
    "eluniversal.com.mx",
    # Secondary: English signal layer
    "ft.com",
    "wsj.com",
]
NEWS_DOMAINS_STR = ",".join(NEWS_DOMAINS)

# ── Domain blocklist ──────────────────────────
# URLs whose domain matches any entry here are dropped before scraping.
# Use this to quickly suppress low-signal or consistently broken sources
# without touching the NewsAPI allowlist above.
# All entries should be lowercase without "www." prefix.
NEWS_DOMAIN_BLOCKLIST: set[str] = {
    # Add domains here as needed, e.g.:
    # "example-aggregator.com",
}

# ── Market tickers (Yahoo Finance symbols) ────
# Main ticker bar: global macro conditions
TICKER_SYMBOLS = [
    ("DXY",     "DX-Y.NYB"),
    ("10Y UST", "^TNX"),
    ("VIX",     "^VIX"),
    ("MSCI EM", "EEM"),
]

# Secondary ticker groups: equities, commodities, crypto
# Used in tabbed strip (archive) and 3-column dashboard (email)
SECONDARY_TICKER_GROUPS = [
    {
        "group": "eq",
        "label": "Global Equities",
        "tickers": [
            ("S&P 500",    "^GSPC"),
            ("Nasdaq",     "^IXIC"),
            ("Euro Stoxx", "^STOXX50E"),
            ("Nikkei",     "^N225"),
        ],
    },
    {
        "group": "co",
        "label": "Commodities",
        "tickers": [
            ("Brent",  "BZ=F"),
            ("Gold",   "GC=F"),
            ("Copper", "HG=F"),
            ("Wheat",  "ZW=F"),
        ],
    },
    {
        "group": "cr",
        "label": "Crypto",
        "tickers": [
            ("Bitcoin",  "BTC-USD"),
            ("Ethereum", "ETH-USD"),
            ("Solana",   "SOL-USD"),
        ],
    },
]
# ── Currency table ────────────────────────────
# Base currencies available as toggle options in the browser version.
CURRENCY_BASES = ["MXN", "USD", "BRL", "EUR", "CNY"]

# All currencies included in the cross-rate matrix.
CURRENCY_PAIRS = ["MXN", "USD", "BRL", "EUR", "CNY", "CAD", "GBP", "JPY"]

# Email version: always USD as base, these four quote currencies only.
EMAIL_CURRENCY_BASE   = "USD"
EMAIL_CURRENCY_QUOTES = ["MXN", "EUR", "GBP", "CNY"]

# Mock mode: set MOCK=true to skip NewsAPI + Anthropic calls.
MOCK_MODE = os.environ.get("MOCK", "false").lower() == "true"

# Skip email delivery (preview/archive only).
SKIP_EMAIL = os.environ.get("SKIP_EMAIL", "false").lower() == "true"

# ── Economic calendar ─────────────────────────
# Upcoming key dates for Banxico, Fed, and macro data releases.
# Verify and update at: banxico.org.mx, federalreserve.gov, inegi.org.mx, bls.gov
# Each entry: (date_str, label, event_type)
# event_type: "banxico" | "fed" | "mx-data" | "us-data"
ECONOMIC_CALENDAR = [
    ("2026-03-26", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-04-09", "INEGI \u2014 CPI M\u00e9xico (feb)",    "mx-data"),
    ("2026-04-10", "BLS \u2014 CPI EE.UU. (mar)",           "us-data"),
    ("2026-04-29", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-05-12", "BLS \u2014 CPI EE.UU. (abr)",           "us-data"),
    ("2026-05-14", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-06-09", "INEGI \u2014 CPI M\u00e9xico (may)",    "mx-data"),
    ("2026-06-10", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-06-11", "BLS \u2014 CPI EE.UU. (may)",           "us-data"),
    ("2026-06-25", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-07-14", "BLS \u2014 CPI EE.UU. (jun)",           "us-data"),
    ("2026-07-29", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-08-06", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-08-12", "BLS \u2014 CPI EE.UU. (jul)",           "us-data"),
    ("2026-09-10", "BLS \u2014 CPI EE.UU. (ago)",           "us-data"),
    ("2026-09-16", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-09-24", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-10-13", "BLS \u2014 CPI EE.UU. (sep)",           "us-data"),
    ("2026-10-28", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-11-05", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
    ("2026-11-12", "BLS \u2014 CPI EE.UU. (oct)",           "us-data"),
    ("2026-12-09", "FOMC \u2014 Decisi\u00f3n Fed",         "fed"),
    ("2026-12-10", "BLS \u2014 CPI EE.UU. (nov)",           "us-data"),
    ("2026-12-17", "Banxico \u2014 Decisi\u00f3n de tasa",  "banxico"),
]

# ── Storage paths ─────────────────────────────
# Paths are relative to the repo root, not bot/
# so digests and archive are committed together.
import pathlib
REPO_ROOT   = pathlib.Path(__file__).parent.parent
DIGEST_DIR  = str(REPO_ROOT / "digests")
ARCHIVE_DIR = str(REPO_ROOT / "docs")

# ── Archive / asset URLs ───────────────────────
# GITHUB_PAGES_URL: always the rendered GitHub Pages site.
# Used for navigation links (preheader, footer, archive index).
GITHUB_PAGES_URL = "https://extremelypowerfulcapybara.github.io/News-Digest"

# ASSET_BASE_URL: used only for asset src attributes (e.g. wordcloud PNG).
# In dev runs, GITHUB_RAW_URL is injected by the workflow so assets
# are served from the dev branch without needing a Pages deploy.
ASSET_BASE_URL = os.environ.get(
    "GITHUB_RAW_URL",
    "https://extremelypowerfulcapybara.github.io/News-Digest/"
)
