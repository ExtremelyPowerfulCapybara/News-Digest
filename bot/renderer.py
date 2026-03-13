# ─────────────────────────────────────────────
#  renderer.py  —  Gmail-safe table-based layout
#  All layout uses <table> + inline styles.
#  No flexbox, no grid, no external CSS classes.
# ─────────────────────────────────────────────

from datetime import date, timedelta
from config import NEWSLETTER_NAME, NEWSLETTER_TAGLINE
from config import GITHUB_PAGES_URL, ASSET_BASE_URL
from config import EMAIL_CURRENCY_BASE, EMAIL_CURRENCY_QUOTES

# ── Shared style constants ────────────────────
BG_OUTER   = "#dde3e8"
BG_MAIN    = "#f0f3f5"
BG_DARK    = "#1a1a1a"
BG_QUOTE   = "#e8edf0"
BORDER     = "#cdd4d9"
BORDER_DIM = "#dde3e8"
TEXT_DARK  = "#1a1a1a"
TEXT_MID   = "#555555"
TEXT_LIGHT = "#aab4bc"
TEXT_CREAM = "#d4cfc8"
FONT_SANS  = "Arial, Helvetica, sans-serif"
FONT_SERIF = "Georgia, 'Times New Roman', serif"


def _divider() -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding: 0 48px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="height:1px; background:{BORDER}; font-size:0; line-height:0;">&nbsp;</td>
          <td style="width:34px; text-align:center; vertical-align:middle; padding:0 10px;">
            <svg width="14" height="14" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="7" y="0" width="4" height="4" fill="#b0bec8"/>
              <rect x="0" y="7" width="4" height="4" fill="#b0bec8"/>
              <rect x="14" y="7" width="4" height="4" fill="#b0bec8"/>
              <rect x="7" y="14" width="4" height="4" fill="#b0bec8"/>
            </svg>
          </td>
          <td style="height:1px; background:{BORDER}; font-size:0; line-height:0;">&nbsp;</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _header(issue_number: int) -> str:
    d = date.today()
    days_es   = ["LUNES","MARTES","MIÉRCOLES","JUEVES","VIERNES","SÁBADO","DOMINGO"]
    months_es = ["","ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                 "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"]
    today = f"{days_es[d.weekday()]}, {d.day:02d} DE {months_es[d.month]} DE {d.year}"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding: 36px 48px 28px; border-bottom: 2px solid {TEXT_DARK};">
      <p style="margin:0 0 10px 0; font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:3px; text-transform:uppercase; color:#999999;">{NEWSLETTER_TAGLINE}</p>
      <p style="margin:0 0 14px 0; font-family:{FONT_SERIF}; font-size:34px; font-weight:bold; color:{TEXT_DARK}; line-height:1.1;">{NEWSLETTER_NAME}</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:10px; color:#888888; letter-spacing:1px;">{today}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:10px; color:#888888; letter-spacing:1px;">EDICIÓN NO. {issue_number}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _ticker(tickers: list[dict]) -> str:
    cells = ""
    for i, t in enumerate(tickers):
        chg_color  = "#6abf7b" if t["direction"] == "up" else ("#d4695a" if t["direction"] == "down" else "#888888")
        left_border = "border-left:1px solid #2e2e2e;" if i > 0 else ""
        cells += f"""
        <td style="{left_border} padding:10px 16px; text-align:center; vertical-align:middle;">
          <span style="display:block; font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:2px; text-transform:uppercase; color:#555555; margin-bottom:4px;">{t['label']}</span>
          <span style="font-family:{FONT_SANS}; font-size:12px; color:{TEXT_CREAM};">{t['value']}</span>
          <span style="font-family:{FONT_SANS}; font-size:10px; color:{chg_color}; margin-left:4px;">{t['change']}</span>
        </td>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_DARK}; border-bottom:3px solid {BG_MAIN};">
  <tr>
    <td style="padding:2px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>{cells}
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _weather(w: dict) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_DARK}; margin-top:3px;">
  <tr>
    <td style="padding:10px 48px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:11px; font-weight:bold; color:#f5f2ed; white-space:nowrap;">{w['city']}</td>
          <td style="font-family:{FONT_SANS}; font-size:11px; color:#cccccc; padding-left:16px; white-space:nowrap;">{w['high_low']}</td>
          <td style="font-family:{FONT_SANS}; font-size:11px; color:#cccccc; padding-left:16px; white-space:nowrap;">{w['humidity']}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:10px; color:#666666; font-style:italic;">{w['desc']}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _editor_note(note: str, author: str = "") -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:28px 48px;">
      <p style="margin:0 0 12px 0; font-family:{FONT_SERIF}; font-style:italic; font-size:15px; color:#444444; line-height:1.8;">{note}</p>
      <p style="margin:0; font-family:{FONT_SANS}; font-size:10px; color:#999999; letter-spacing:1px; text-transform:uppercase;">&#8212; {author}</p>
    </td>
  </tr>
</table>"""


def _sentiment(s: dict) -> str:
    label_en = s.get("label_en", s.get("label", "Cautious"))
    label_es = s.get("label_es", s.get("label", "Cauteloso"))
    context  = s.get("context_es", s.get("context", ""))

    style_map = {
        "Aversión al Riesgo": ("background:#fde8e6; color:#b84a3a; border:1px solid #f0c0ba;", "#b84a3a"),
        "Cauteloso":          ("background:#fef3e2; color:#9a6a1a; border:1px solid #f0d8a0;", "#e8a030"),
        "Apetito por Riesgo": ("background:#e6f4ec; color:#2e7a4a; border:1px solid #b0d8c0;", "#4a9e6a"),
    }
    inactive_style = f"background:transparent; color:#bbc8d0; border:1px solid {BORDER_DIM};"
    inactive_dot   = "#cdd4d9"

    pills_html = ""
    for p in ["Aversión al Riesgo", "Cauteloso", "Apetito por Riesgo"]:
        pill_style, dot_color = style_map[p] if p == label_es else (inactive_style, inactive_dot)
        pills_html += f"""
          <td style="padding-right:8px; white-space:nowrap;">
            <span style="display:inline-block; {pill_style} padding:5px 14px; border-radius:20px; font-family:{FONT_SANS}; font-size:10px; font-weight:bold; letter-spacing:1px; text-transform:uppercase;">
              <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:{dot_color}; margin-right:5px; vertical-align:middle;"></span>{p}
            </span>
          </td>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px;">
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2px; text-transform:uppercase; color:{TEXT_LIGHT}; vertical-align:middle; padding-right:12px; white-space:nowrap;">Sentimiento del Día</td>
          {pills_html}
        </tr>
      </table>
      <p style="margin:14px 0 0 0; font-family:{FONT_SERIF}; font-style:italic; font-size:13px; color:{TEXT_MID}; line-height:1.7;">{context}</p>
    </td>
  </tr>
</table>"""


def _story_block(story: dict) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px;">
      <p style="margin:0 0 6px 0;">
        <span style="font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2px; text-transform:uppercase; color:#999999;">{story['source']}</span>
        <span style="font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_LIGHT}; border:1px solid {BORDER}; padding:2px 6px; margin-left:8px;">{story.get('tag','')}</span>
      </p>
      <p style="margin:0 0 10px 0; font-family:{FONT_SERIF}; font-size:20px; font-weight:bold; color:{TEXT_DARK}; line-height:1.3;">{story['headline']}</p>
      <p style="margin:0 0 10px 0; font-family:{FONT_SANS}; font-size:13px; color:{TEXT_MID}; line-height:1.75;">{story['body']}</p>
      <a href="{story['url']}" style="font-family:{FONT_SANS}; font-size:10px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_DARK}; text-decoration:none; border-bottom:1px solid {TEXT_DARK}; padding-bottom:1px;">Leer más &#8594;</a>
    </td>
  </tr>
</table>"""


def _currency_table(rows: list[dict]) -> str:
    th = f"font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_LIGHT}; padding:0 0 8px 0; border-bottom:1px solid {BORDER};"
    tbody = ""
    for r in rows:
        c1 = "#4a9e6a" if r['chg_1d']['cls'] == 'chg-up' else ("#b84a3a" if r['chg_1d']['cls'] == 'chg-down' else TEXT_LIGHT)
        c7 = "#4a9e6a" if r['chg_1w']['cls'] == 'chg-up' else ("#b84a3a" if r['chg_1w']['cls'] == 'chg-down' else TEXT_LIGHT)
        tbody += f"""
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:12px; font-weight:bold; color:{TEXT_DARK}; padding:9px 0; border-bottom:1px solid #e4e9ec;">{r['pair']}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:12px; color:#3a4a54; padding:9px 0; border-bottom:1px solid #e4e9ec;">{r['rate']}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:11px; color:{c1}; padding:9px 0 9px 12px; border-bottom:1px solid #e4e9ec;">{r['chg_1d']['text']}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:11px; color:{c7}; padding:9px 0 9px 12px; border-bottom:1px solid #e4e9ec;">{r['chg_1w']['text']}</td>
        </tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px;">
      <p style="margin:0 0 14px 0; font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2.5px; text-transform:uppercase; color:{TEXT_LIGHT};">Tipo de Cambio</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <th align="left"  style="{th}">Par</th>
          <th align="right" style="{th}">Tipo</th>
          <th align="right" style="{th} padding-left:12px;">1D</th>
          <th align="right" style="{th} padding-left:12px;">1S</th>
        </tr>
        {tbody}
      </table>
    </td>
  </tr>
</table>"""


def _quote(q: dict) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_QUOTE};">
  <tr>
    <td style="padding:28px 48px;">
      <p style="margin:0 0 4px 0; font-family:{FONT_SERIF}; font-size:52px; line-height:0.5; color:#c8d0d6;">&#8220;</p>
      <p style="margin:12px 0; font-family:{FONT_SERIF}; font-style:italic; font-size:15px; color:#3a4a54; line-height:1.75;">{q.get('text','')}</p>
      <p style="margin:0; font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:#8a9aa4;">{q.get('attribution','')}</p>
    </td>
  </tr>
</table>"""


def _week_review(stories: list[dict]) -> str:
    if not stories:
        return ""
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    label  = f"{monday.strftime('%b %d')}&#8211;{friday.strftime('%d, %Y')}"

    rows = ""
    for s in stories:
        dot_bg   = "#3a4a54" if s.get("active") else "#c8d0d6"
        dot_ring = "#3a4a54" if s.get("active") else "#c8d0d6"
        rows += f"""
        <tr>
          <td width="44" style="text-align:center; vertical-align:top; padding-bottom:20px;">
            <p style="margin:0 0 5px 0; font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:1px; text-transform:uppercase; color:{TEXT_LIGHT};">{s['day']}</p>
            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{dot_bg}; border:2px solid {BG_MAIN}; outline:1px solid {dot_ring};"></span>
          </td>
          <td style="padding-left:14px; padding-bottom:20px; vertical-align:top; border-left:1px solid {BORDER_DIM};">
            <p style="margin:0 0 5px 0;"><span style="font-family:{FONT_SANS}; font-size:8px; font-weight:bold; letter-spacing:1.5px; text-transform:uppercase; color:{TEXT_LIGHT}; border:1px solid {BORDER}; padding:2px 6px;">{s['tag']}</span></p>
            <p style="margin:0 0 4px 0; font-family:{FONT_SERIF}; font-size:14px; font-weight:bold; color:{TEXT_DARK}; line-height:1.35;">{s['headline']}</p>
            <p style="margin:0; font-family:{FONT_SANS}; font-size:12px; color:#777777; line-height:1.65;">{s['body']}</p>
          </td>
        </tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="padding:24px 48px;">
      <p style="margin:0 0 18px 0; font-family:{FONT_SANS}; font-size:9px; font-weight:bold; letter-spacing:2.5px; text-transform:uppercase; color:{TEXT_LIGHT};">Resumen Semanal &middot; {label}</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        {rows}
      </table>
    </td>
  </tr>
</table>"""


def _footer(issue_date: str = "", author: str = "") -> str:
    archive_link = ""
    if GITHUB_PAGES_URL and issue_date:
        archive_link = f'&nbsp;&middot;&nbsp;<a href="{GITHUB_PAGES_URL}/index.html" style="color:#666666; text-decoration:none; letter-spacing:1px;">Archivo</a>'
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_DARK};">
  <tr>
    <td style="padding:22px 48px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:{FONT_SERIF}; font-size:14px; color:#f5f2ed;">{NEWSLETTER_NAME}</td>
          <td align="right" style="font-family:{FONT_SANS}; font-size:10px; color:#666666; letter-spacing:1px;">por {author} &middot; Cancelar suscripción{archive_link}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


# ── Main builder ──────────────────────────────

def build_html(
    digest:             dict,
    tickers:            list[dict],
    currency:           dict,
    weather:            dict,
    week_stories:       list[dict],
    issue_number:       int = 1,
    is_friday:          bool = False,
    wordcloud_filename: str | None = None,
    author:             str = "",
) -> str:

    stories_html = ""
    for i, story in enumerate(digest.get("stories", [])):
        stories_html += _story_block(story)
        if i < len(digest["stories"]) - 1:
            stories_html += _divider()

    week_html = ""
    if is_friday and week_stories:
        week_html = _divider() + _week_review(week_stories)

    sentiment  = digest.get("sentiment", {})
    quote      = digest.get("quote", {})
    today_iso  = date.today().isoformat()

    preheader = ""
    if GITHUB_PAGES_URL:
        base        = GITHUB_PAGES_URL.rstrip("/")
        issue_url   = f"{base}/{today_iso}.html"
        archive_url = f"{base}/index.html"
        preheader = f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_OUTER};">
  <tr>
    <td align="center" style="padding:10px 16px 4px;">
      <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%;">
        <tr>
          <td style="font-family:{FONT_SANS}; font-size:10px; color:#888888;">
            <a href="{issue_url}" style="color:#555555; text-decoration:none;">Ver en navegador</a>
            &nbsp;&middot;&nbsp;
            <a href="{archive_url}" style="color:#555555; text-decoration:none;">Ver todos los números</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{NEWSLETTER_NAME}</title>
</head>
<body style="margin:0; padding:0; background:{BG_OUTER}; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%;">
{preheader}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_OUTER};">
  <tr>
    <td align="center" style="padding:8px 16px 32px;">
      <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%; background:{BG_MAIN}; border:1px solid {BORDER};">
        <tr><td>{_header(issue_number)}</td></tr>
        <tr><td>{_ticker(tickers)}</td></tr>
        <tr><td>{_weather(weather)}</td></tr>
        <tr><td>{_editor_note(digest.get('editor_note', ''), author)}</td></tr>
        <tr><td>{_divider()}</td></tr>
        <tr><td>{_sentiment(sentiment)}</td></tr>
        <tr><td>{_divider()}</td></tr>
        <tr><td>{stories_html}</td></tr>
        <tr><td>{_divider()}</td></tr>
        <tr><td>{_currency_table([r for r in currency.get('matrix', {}).get(EMAIL_CURRENCY_BASE, []) if any(r['pair'].endswith(f'/ {q}') for q in EMAIL_CURRENCY_QUOTES)])}</td></tr>
        <tr><td>{_divider()}</td></tr>
        <tr><td>{_quote(quote)}</td></tr>
        {'<tr><td>' + week_html + '</td></tr>' if week_html else ''}
        {'<tr><td><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="padding:24px 48px 8px;"><p style="margin:0 0 14px 0; font-family:Arial,sans-serif; font-size:9px; font-weight:bold; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc;">La Semana en Palabras</p><img src="' + ASSET_BASE_URL.rstrip("/") + "/" + wordcloud_filename + '" width="504" style="width:100%; max-width:504px; display:block;" alt=""/></td></tr></table></td></tr>' if wordcloud_filename else ''}
        <tr><td>{_footer(today_iso, author)}</td></tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

def build_plain(digest: dict, author: str = "") -> str:
    d = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today = f"{d.day} de {months_es[d.month]} de {d.year}"
    lines = [f"{NEWSLETTER_NAME} — {today}", "=" * 40, ""]

    note = digest.get("editor_note", "")
    if note:
        lines += [note, ""]

    sentiment = digest.get("sentiment", {})
    if sentiment:
        lines += [f"Sentimiento: {sentiment.get('label_es', sentiment.get('label',''))} — {sentiment.get('context_es', sentiment.get('context',''))}", ""]

    for s in digest.get("stories", []):
        lines += [
            f"[{s['source']}] {s['headline']}",
            s["body"],
            f"Leer más: {s['url']}",
            "",
        ]

    q = digest.get("quote", {})
    if q:
        lines += [f'"{q["text"]}"', f"— {q['attribution']}", ""]

    lines += [f"— {author}"]
    return "\n".join(lines)
