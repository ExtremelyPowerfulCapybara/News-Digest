# ─────────────────────────────────────────────
#  pretty_renderer.py  —  Full-featured HTML
#  for the web archive. Uses Google Fonts,
#  flexbox, CSS classes, and the gauge.
#  Not used for email — only for web hosting.
# ─────────────────────────────────────────────

from datetime import date, timedelta
from config import NEWSLETTER_NAME, NEWSLETTER_TAGLINE
from config import GITHUB_PAGES_URL, ASSET_BASE_URL

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #dde3e8; font-family: 'DM Sans', sans-serif; padding: 40px 16px; }
  .wrap { max-width: 640px; margin: 0 auto; background: #f0f3f5; border: 1px solid #cdd4d9; }

  .header { padding: 40px 48px 28px; border-bottom: 2px solid #1a1a1a; }
  .pub-label { font-size: 9px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #999; margin-bottom: 10px; }
  .pub-name { font-family: 'Playfair Display', serif; font-size: 36px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 14px; }
  .pub-meta { display: flex; justify-content: space-between; font-size: 10px; color: #888; letter-spacing: 1px; }

  .ticker { background: #1a1a1a; padding: 10px 48px; border-bottom: 3px solid #f0f3f5; }
  .ticker-inner { display: flex; justify-content: space-between; }
  .tick-item { text-align: center; flex: 1; padding: 6px 8px; border-left: 1px solid #2e2e2e; }
  .tick-item:first-child { border-left: none; }
  .tick-label { display: block; font-size: 8px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #555; margin-bottom: 4px; }
  .tick-val { font-size: 12px; color: #d4cfc8; }
  .tick-up { color: #6abf7b; font-size: 10px; margin-left: 4px; }
  .tick-down { color: #d4695a; font-size: 10px; margin-left: 4px; }

  .weather { background: #1a1a1a; padding: 9px 48px; display: flex; gap: 20px; align-items: center; margin-top: 3px; }
  .weather-city { font-size: 11px; font-weight: 500; color: #f5f2ed; }
  .weather-temp { font-size: 11px; color: #ccc; }
  .weather-humidity { font-size: 11px; color: #ccc; }
  .weather-desc { font-size: 10px; color: #666; font-style: italic; margin-left: auto; }

  .editor-note { padding: 28px 48px; }
  .editor-note p { font-family: 'Playfair Display', serif; font-style: italic; font-size: 15px; color: #444; line-height: 1.8; }
  .editor-sig { margin-top: 12px; font-size: 10px; color: #999; letter-spacing: 1px; text-transform: uppercase; }

  .divider { display: flex; align-items: center; gap: 12px; padding: 0 48px; }
  .divider .line { flex: 1; height: 1px; background: #cdd4d9; }

  .sentiment { padding: 24px 48px; }
  .sentiment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .sentiment-label { font-size: 9px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #aab4bc; }
  .sentiment-reading { font-size: 11px; font-weight: 500; letter-spacing: 1px; text-transform: uppercase; }
  .sentiment-reading.risk-off { color: #b84a3a; }
  .sentiment-reading.cautious { color: #9a6a1a; }
  .sentiment-reading.risk-on  { color: #4a9e6a; }
  .gauge-track { height: 6px; border-radius: 3px; background: linear-gradient(90deg, #b84a3a, #e8a030, #4a9e6a); position: relative; margin: 0 7px; }
  .gauge-marker { position: absolute; top: 50%; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; background: #f0f3f5; box-shadow: 0 1px 5px rgba(0,0,0,0.2); }
  .gauge-marker.risk-off { border: 2px solid #b84a3a; }
  .gauge-marker.cautious { border: 2px solid #9a6a1a; }
  .gauge-marker.risk-on  { border: 2px solid #4a9e6a; }
  .gauge-ticks { display: flex; justify-content: space-between; margin-top: 7px; font-size: 8px; font-weight: 500; letter-spacing: 1px; text-transform: uppercase; color: #aab4bc; }
  .sentiment-context { margin-top: 12px; font-family: 'Playfair Display', serif; font-style: italic; font-size: 13.5px; color: #555; line-height: 1.7; }

  .story { padding: 24px 48px; }
  .story-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .story-source { font-size: 9px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #999; }
  .story-tag { font-size: 8px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #aab4bc; border: 1px solid #cdd4d9; padding: 2px 6px; }
  .story-headline { font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 700; color: #1a1a1a; line-height: 1.3; margin-bottom: 10px; }
  .story-body { font-size: 13.5px; color: #555; line-height: 1.75; margin-bottom: 10px; }
  .read-more { font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #1a1a1a; text-decoration: none; border-bottom: 1px solid #1a1a1a; padding-bottom: 1px; }
  .read-more:hover { color: #555; border-color: #555; }

  .currency { padding: 24px 48px; }
  .section-title { font-size: 9px; font-weight: 500; letter-spacing: 2.5px; text-transform: uppercase; color: #aab4bc; margin-bottom: 14px; }
  .currency-table { width: 100%; border-collapse: collapse; }
  .currency-table th { font-size: 9px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #aab4bc; text-align: left; padding: 0 0 8px; border-bottom: 1px solid #cdd4d9; }
  .currency-table th:not(:first-child) { text-align: right; }
  .currency-table td { font-size: 12.5px; color: #3a4a54; padding: 9px 0; border-bottom: 1px solid #e4e9ec; }
  .currency-table td:not(:first-child) { text-align: right; }
  .currency-table tr:last-child td { border-bottom: none; }
  .currency-table .pair { font-weight: 600; color: #1a1a1a; }

  .quote { padding: 28px 48px; background: #e8edf0; }
  .quote-mark { font-family: 'Playfair Display', serif; font-size: 52px; line-height: 0.5; color: #c8d0d6; display: block; margin-bottom: 8px; }
  .quote-text { font-family: 'Playfair Display', serif; font-style: italic; font-size: 15px; color: #3a4a54; line-height: 1.75; margin-bottom: 12px; }
  .quote-attr { font-size: 9px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #8a9aa4; }

  .week { padding: 24px 48px; }
  .timeline { display: flex; flex-direction: column; }
  .tl-row { display: flex; gap: 16px; }
  .tl-left { display: flex; flex-direction: column; align-items: center; width: 44px; flex-shrink: 0; }
  .tl-day { font-size: 8px; font-weight: 500; letter-spacing: 1px; text-transform: uppercase; color: #aab4bc; margin-bottom: 5px; }
  .tl-dot { width: 10px; height: 10px; border-radius: 50%; background: #c8d0d6; border: 2px solid #f0f3f5; outline: 1px solid #c8d0d6; }
  .tl-dot.active { background: #3a4a54; outline-color: #3a4a54; }
  .tl-line { width: 1px; flex: 1; background: #dde3e8; min-height: 16px; margin: 3px 0; }
  .tl-row:last-child .tl-line { display: none; }
  .tl-content { padding-bottom: 20px; flex: 1; }
  .tl-row:last-child .tl-content { padding-bottom: 0; }
  .tl-tag { font-size: 8px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #aab4bc; border: 1px solid #cdd4d9; padding: 2px 6px; display: inline-block; margin-bottom: 5px; }
  .tl-headline { font-family: 'Playfair Display', serif; font-size: 14px; font-weight: 700; color: #1a1a1a; line-height: 1.35; margin-bottom: 4px; }
  .tl-body { font-size: 12px; color: #777; line-height: 1.65; }

  .footer { background: #1a1a1a; padding: 22px 48px; display: flex; justify-content: space-between; align-items: center; }
  .footer-name { font-family: 'Playfair Display', serif; font-size: 14px; color: #f5f2ed; }
  .footer-by { font-size: 10px; color: #666; letter-spacing: 1px; }

  @media (max-width: 600px) {
    body { padding: 0; }
    .wrap { border: none; }
    .header { padding: 28px 20px 20px; }
    .pub-name { font-size: 26px; }
    .ticker { padding: 6px 8px; }
    .ticker-inner { flex-wrap: wrap; }
    .tick-item { flex: 1 1 45%; padding: 8px 4px; }
    .weather { padding: 9px 20px; flex-wrap: wrap; gap: 8px; }
    .weather-desc { margin-left: 0; width: 100%; }
    .editor-note { padding: 20px 20px; }
    .divider { padding: 0 20px; }
    .sentiment { padding: 20px 20px; }
    .story { padding: 20px 20px; }
    .currency { padding: 20px 20px; }
    .quote { padding: 20px 20px; }
    .week { padding: 20px 20px; }
    .footer { padding: 18px 20px; flex-direction: column; align-items: flex-start; gap: 6px; }
  }
"""

DIVIDER = """
<div class="divider">
  <div class="line"></div>
  <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
    <rect x="7" y="0" width="4" height="4" fill="#b0bec8"/>
    <rect x="0" y="7" width="4" height="4" fill="#b0bec8"/>
    <rect x="14" y="7" width="4" height="4" fill="#b0bec8"/>
    <rect x="7" y="14" width="4" height="4" fill="#b0bec8"/>
  </svg>
  <div class="line"></div>
</div>"""


def build_pretty_html(
    digest:             dict,
    tickers:            list[dict],
    currency:           list[dict],
    weather:            dict,
    week_stories:       list[dict],
    issue_number:       int = 1,
    is_friday:          bool = False,
    wordcloud_filename: str | None = None,
    author:             str = "",
) -> str:

    # Bilingual support: read from digest["es"] if present, fallback for old digests
    digest_es = digest.get("es", digest)

    today      = date.today().strftime("%A, %B %d, %Y").upper()
    issue_date = date.today().strftime("%B %d, %Y")

    # Ticker
    tick_items = ""
    for t in tickers:
        chg_cls = "tick-up" if t["direction"] == "up" else ("tick-down" if t["direction"] == "down" else "")
        tick_items += f"""
      <div class="tick-item">
        <span class="tick-label">{t['label']}</span>
        <span class="tick-val">{t['value']}</span>
        <span class="{chg_cls}">{t['change']}</span>
      </div>"""

    # Sentiment gauge
    s        = digest_es.get("sentiment", {})
    label_es = s.get("label_es", s.get("label", "Cauteloso"))
    label_en = s.get("label_en", s.get("label", "Cautious"))
    position = max(5, min(95, int(s.get("position", 50))))
    context  = s.get("context_es", s.get("context", ""))
    cls_map  = {"Risk-Off": "risk-off", "Cautious": "cautious", "Risk-On": "risk-on"}
    sent_cls = cls_map.get(label_en, "cautious")

    # Stories
    stories_html = ""
    for story in digest_es.get("stories", []):
        stories_html += f"""
{DIVIDER}
<div class="story">
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="story-headline">{story['headline']}</div>
  <div class="story-body">{story['body']}</div>
  <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
</div>"""

    # Currency table
    tbody = ""
    for r in currency:
        c1 = "up" if r['chg_1d']['cls'] == 'chg-up' else ("down" if r['chg_1d']['cls'] == 'chg-down' else "flat")
        c7 = "up" if r['chg_1w']['cls'] == 'chg-up' else ("down" if r['chg_1w']['cls'] == 'chg-down' else "flat")
        chg1_color = "#4a9e6a" if c1 == "up" else ("#b84a3a" if c1 == "down" else "#aab4bc")
        chg7_color = "#4a9e6a" if c7 == "up" else ("#b84a3a" if c7 == "down" else "#aab4bc")
        tbody += f"""
      <tr>
        <td class="pair">{r['pair']}</td>
        <td>{r['rate']}</td>
        <td style="color:{chg1_color}; text-align:right;">{r['chg_1d']['text']}</td>
        <td style="color:{chg7_color}; text-align:right;">{r['chg_1w']['text']}</td>
      </tr>"""

    # Quote
    q = digest_es.get("quote", {})

    # Week in review
    week_html = ""
    if is_friday and week_stories:
        monday = date.today() - timedelta(days=date.today().weekday())
        friday = monday + timedelta(days=4)
        wlabel = f"{monday.strftime('%b %d')}-{friday.strftime('%d, %Y')}"
        tl_items = ""
        for ws in week_stories:
            dot_cls = "active" if ws.get("active") else ""
            tl_items += f"""
      <div class="tl-row">
        <div class="tl-left">
          <div class="tl-day">{ws['day']}</div>
          <div class="tl-dot {dot_cls}"></div>
          <div class="tl-line"></div>
        </div>
        <div class="tl-content">
          <span class="tl-tag">{ws['tag']}</span>
          <div class="tl-headline">{ws['headline']}</div>
          <div class="tl-body">{ws['body']}</div>
        </div>
      </div>"""
        week_html = f"""
{DIVIDER}
<div class="week">
  <div class="section-title">Resumen Semanal &middot; {wlabel}</div>
  <div class="timeline">{tl_items}
  </div>
</div>"""

    # Wordcloud — use full hosted URL so it works in both dev and production
    wordcloud_html = ""
    if wordcloud_filename:
        wordcloud_url = f"{ASSET_BASE_URL.rstrip('/')}/{wordcloud_filename}"
        wordcloud_html = f"""
{DIVIDER}
<div style="padding:24px 48px 8px;">
  <div class="section-title">La Semana en Palabras</div>
  <img src="{wordcloud_url}" style="width:100%; border:1px solid #cdd4d9;" alt="Nube de palabras"/>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{NEWSLETTER_NAME} -- {issue_date}</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <div class="pub-label">{NEWSLETTER_TAGLINE}</div>
    <div class="pub-name">{NEWSLETTER_NAME}</div>
    <div class="pub-meta">
      <span>{today}</span>
      <span>EDICI&#211;N NO. {issue_number}</span>
    </div>
  </div>

  <div class="ticker">
    <div class="ticker-inner">{tick_items}
    </div>
  </div>

  <div class="weather">
    <span class="weather-city">{weather['city']}</span>
    <span class="weather-temp">{weather['high_low']}</span>
    <span class="weather-humidity">{weather['humidity']}</span>
    <span class="weather-desc">{weather['desc']}</span>
  </div>

  <div class="editor-note">
    <p>{digest_es.get('editor_note','')}</p>
    <div class="editor-sig">&mdash; {author}</div>
  </div>

  {DIVIDER}

  <div class="sentiment">
    <div class="sentiment-header">
      <span class="sentiment-label">Sentimiento del D&#237;a</span>
      <span class="sentiment-reading {sent_cls}">{label_es}</span>
    </div>
    <div class="gauge-track">
      <div class="gauge-marker {sent_cls}" style="left:{position}%;"></div>
    </div>
    <div class="gauge-ticks">
      <span>Avers. al Riesgo</span><span>Neutral</span><span>Apetito por Riesgo</span>
    </div>
    <div class="sentiment-context">{context}</div>
  </div>

  {stories_html}

  {DIVIDER}

  <div class="currency">
    <div class="section-title">Tipo de Cambio</div>
    <table class="currency-table">
      <thead>
        <tr>
          <th>Par</th><th>Tipo</th><th style="text-align:right;">1D</th><th style="text-align:right;">1S</th>
        </tr>
      </thead>
      <tbody>{tbody}
      </tbody>
    </table>
  </div>

  {DIVIDER}

  <div class="quote">
    <span class="quote-mark">&ldquo;</span>
    <div class="quote-text">{q.get('text','')}</div>
    <div class="quote-attr">{q.get('attribution','')}</div>
  </div>

  {week_html}

  {wordcloud_html}

  <div class="footer">
    <span class="footer-name">{NEWSLETTER_NAME}</span>
    <span class="footer-by">por {author}</span>
  </div>

</div>
</body>
</html>"""
