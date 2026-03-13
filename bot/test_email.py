# ─────────────────────────────────────────────
#  test_email.py  —  Send a test email with
#  mock data without running the full pipeline.
#  Usage: python test_email.py
# ─────────────────────────────────────────────

from renderer import build_html, build_plain
from delivery import send_email
from archive  import save_pretty_issue

# ── Mock data ─────────────────────────────────

MOCK_TICKERS = [
    {"label": "USD/MXN",   "value": "17.10", "change": "▼ 0.9%", "direction": "down"},
    {"label": "S&P 500",   "value": "6,910",  "change": "▲ 0.4%", "direction": "up"},
    {"label": "CETES 28D", "value": "9.85%",  "change": "",        "direction": "flat"},
    {"label": "IPC BMV",   "value": "71,436", "change": "▲ 0.8%", "direction": "up"},
]

MOCK_CURRENCY = [
    {"pair": "MXN / USD", "rate": "0.0560", "chg_1d": {"text": "▼ 1.21%", "cls": "chg-down"}, "chg_1w": {"text": "▼ 2.04%", "cls": "chg-down"}},
    {"pair": "MXN / EUR", "rate": "0.0516", "chg_1d": {"text": "▼ 0.88%", "cls": "chg-down"}, "chg_1w": {"text": "▼ 1.45%", "cls": "chg-down"}},
    {"pair": "MXN / CAD", "rate": "0.0763", "chg_1d": {"text": "▲ 0.32%", "cls": "chg-up"},   "chg_1w": {"text": "— 0.00%", "cls": "chg-flat"}},
    {"pair": "MXN / CNY", "rate": "0.4068", "chg_1d": {"text": "▼ 0.55%", "cls": "chg-down"}, "chg_1w": {"text": "▲ 0.21%", "cls": "chg-up"}},
]

MOCK_WEATHER = {
    "city":     "Ciudad de México",
    "high_low": "22°C / 14°C",
    "humidity": "Humedad 65%",
    "desc":     "Mañana despejada, nubes por la tarde",
}

# Bilingual digest — mirrors the structure returned by summarizer.py
MOCK_DIGEST = {
    "es": {
        "editor_note": "Estimados humanos, mal día para el peso. Las minutas de la Fed llegaron más agresivas de lo esperado y los mercados no lo tomaron bien. Tres cosas merecen su atención hoy, empezando por lo que la SHCP no dijo en su comunicado matutino.",

        "sentiment": {
            "label_es":   "Aversión al Riesgo",
            "label_en":   "Risk-Off",
            "position":   20,
            "context_es": "Las minutas hawkish de la Fed y la debilidad del peso dominan la narrativa de hoy. Los mercados descuentan menos recortes en el primer semestre.",
            "context_en": "Hawkish Fed minutes and peso weakness dominate today's narrative. Markets are pricing in fewer rate cuts through H1.",
        },

        "stories": [
            {
                "source":   "Reuters",
                "tag":      "Macro",
                "headline": "La Fed señala una pausa prolongada mientras la inflación se mantiene elevada",
                "body":     "La Reserva Federal indicó que mantendrá las tasas sin cambios durante el primer trimestre tras dos meses consecutivos de IPC por encima de lo esperado. Los funcionarios citaron la inflación persistente en servicios como la principal preocupación, retrasando las expectativas de recortes a mediados de año.",
                "url":      "https://reuters.com",
            },
            {
                "source":   "Bloomberg",
                "tag":      "FX",
                "headline": "El peso cede 1.2% ante la reaparición de amenazas arancelarias de EE.UU.",
                "body":     "El MXN se depreció frente al dólar después de que la Casa Blanca renovara sus amenazas de aranceles sobre importaciones mexicanas vinculadas a la política fronteriza. Los analistas esperan volatilidad a corto plazo pero ven un impacto limitado a largo plazo si las negociaciones se reanudan pronto.",
                "url":      "https://bloomberg.com",
            },
            {
                "source":   "El Financiero",
                "tag":      "México",
                "headline": "La SHCP proyecta un crecimiento del PIB de 3.2% pese a los vientos externos",
                "body":     "La Secretaría de Hacienda mantuvo su pronóstico de crecimiento para 2026 en 3.2%, citando la inversión en nearshoring y el consumo interno como factores compensatorios. La proyección fue recibida con escepticismo por varios economistas independientes.",
                "url":      "https://elfinanciero.com.mx",
            },
        ],

        "quote": {
            "text":        "La inflación es siempre y en todo lugar un fenómeno monetario, en el sentido de que sólo puede ser producida por un aumento más rápido de la cantidad de dinero que de la producción.",
            "attribution": "Milton Friedman, A Monetary History of the United States, 1963",
        },
    },

    "en": {
        "editor_note": "Fellow humans, rough day for the peso. Fed minutes came in more hawkish than expected and markets didn't love it. Three things worth your attention today, starting with what the SHCP didn't say in this morning's press release.",

        "sentiment": {
            "label_es":   "Aversión al Riesgo",
            "label_en":   "Risk-Off",
            "position":   20,
            "context_es": "Las minutas hawkish de la Fed y la debilidad del peso dominan la narrativa de hoy. Los mercados descuentan menos recortes en el primer semestre.",
            "context_en": "Hawkish Fed minutes and peso weakness dominate today's narrative. Markets are pricing in fewer rate cuts through H1.",
        },

        "stories": [
            {
                "source":   "Reuters",
                "tag":      "Macro",
                "headline": "Fed Signals Extended Pause as Inflation Proves Sticky",
                "body":     "The Federal Reserve indicated it will hold rates steady through Q1 after CPI came in above expectations for the second consecutive month. Officials cited persistent services inflation as the main concern, pushing back market expectations for the next cut to mid-year.",
                "url":      "https://reuters.com",
            },
            {
                "source":   "Bloomberg",
                "tag":      "FX",
                "headline": "Peso Slips 1.2% as US Tariff Threats Resurface",
                "body":     "The MXN weakened against the dollar after the White House renewed threats of tariffs on Mexican imports tied to border policy. Analysts expect volatility to persist short-term but see limited long-term impact if negotiations resume quickly.",
                "url":      "https://bloomberg.com",
            },
            {
                "source":   "El Financiero",
                "tag":      "Mexico",
                "headline": "SHCP Projects 3.2% GDP Growth Despite External Headwinds",
                "body":     "Mexico's Finance Ministry maintained its 2026 growth forecast at 3.2%, citing strong nearshoring investment and domestic consumption as offsetting factors. The projection was met with skepticism by several independent economists.",
                "url":      "https://elfinanciero.com.mx",
            },
        ],

        "quote": {
            "text":        "Inflation is always and everywhere a monetary phenomenon in the sense that it is and can be produced only by a more rapid increase in the quantity of money than in output.",
            "attribution": "Milton Friedman, A Monetary History of the United States, 1963",
        },
    },
}

MOCK_WEEK_STORIES = [
    {"day": "Lun", "active": True,  "tag": "Macro",    "headline": "La Fed señala pausa prolongada en recortes",          "body": "Las minutas hawkish retrasaron las expectativas de recortes a mediados de año. El peso tocó mínimos de 3 meses."},
    {"day": "Mar", "active": False, "tag": "México",   "headline": "La SHCP mantiene el pronóstico de PIB en 3.2%",       "body": "Hacienda sostuvo su perspectiva pese a los vientos externos. Los economistas independientes se muestran escépticos."},
    {"day": "Mié", "active": True,  "tag": "FX",       "headline": "Amenazas arancelarias de EE.UU. regresan, MXN cede 1.2%", "body": "La Casa Blanca renovó la presión arancelaria vinculada a política fronteriza. Se espera volatilidad a corto plazo."},
    {"day": "Jue", "active": False, "tag": "Tasas",    "headline": "Minutas de Banxico revelan división sobre el próximo movimiento", "body": "Dos miembros favorecieron una pausa, tres apoyaron un recorte de 25pb. Mayor incertidumbre en tasas mexicanas."},
    {"day": "Vie", "active": True,  "tag": "Comercio", "headline": "Inversión en nearshoring marca récord en el primer trimestre", "body": "Nuevos anuncios en Monterrey y Saltillo llevaron los compromisos a un récord. El punto positivo de la semana."},
]

# ── Build and send ────────────────────────────

if __name__ == "__main__":
    print("Building test email...")

    # Set FRIDAY=True to also include the week-in-review section
    FRIDAY = False

    # Mock author byline
    AUTHOR = "Drew Downing, Director of Gradually Alarming Developments"

    digest_es = MOCK_DIGEST["es"]

    html  = build_html(
        digest         = digest_es,
        tickers        = MOCK_TICKERS,
        currency       = MOCK_CURRENCY,
        weather        = MOCK_WEATHER,
        week_stories   = MOCK_WEEK_STORIES if FRIDAY else [],
        issue_number   = 1,
        is_friday      = FRIDAY,
        wordcloud_b64  = None,
        author         = AUTHOR,
    )
    plain = build_plain(digest_es, author=AUTHOR)

    send_email(html, plain)

    save_pretty_issue(
        digest             = MOCK_DIGEST,
        tickers            = MOCK_TICKERS,
        currency           = MOCK_CURRENCY,
        weather            = MOCK_WEATHER,
        week_stories       = MOCK_WEEK_STORIES if FRIDAY else [],
        issue_number       = 1,
        is_friday          = FRIDAY,
        wordcloud_filename = None,
        author             = AUTHOR,
    )
    print("Done. Check your inbox and archive/index.html.")
