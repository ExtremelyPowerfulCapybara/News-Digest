# ─────────────────────────────────────────────
#  pretty_renderer.py  —  Full-featured HTML
#  for the web archive. Uses Google Fonts,
#  flexbox, CSS classes, and the gauge.
#  Not used for email — only for web hosting.
#
#  Bilingual toggle: ES/EN pill in the header
#  swaps all translatable content via JS.
#  lang-es blocks visible by default;
#  lang-en blocks hidden until toggled.
# ─────────────────────────────────────────────

import locale
from datetime import date, timedelta
from config import NEWSLETTER_NAME, NEWSLETTER_TAGLINE
from config import GITHUB_PAGES_URL, ASSET_BASE_URL

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except Exception:
    pass

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #dde3e8; font-family: 'DM Sans', sans-serif; padding: 40px 16px; }
  .wrap { max-width: 640px; margin: 0 auto; background: #f0f3f5; border: 1px solid #cdd4d9; }

  .header { padding: 40px 48px 28px; border-bottom: 2px solid #1a1a1a; }
  .pub-label { font-size: 9px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #999; margin-bottom: 10px; }
  .pub-name { font-family: 'Playfair Display', serif; font-size: 36px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 14px; }
  .pub-meta { display: flex; justify-content: space-between; align-items: center; font-size: 10px; color: #888; letter-spacing: 1px; }

  /* ── Language toggle ── */
  .lang-toggle { display: flex; gap: 0; border: 1px solid #cdd4d9; border-radius: 3px; overflow: hidden; flex-shrink: 0; }
  .lang-btn {
    font-family: 'DM Sans', sans-serif; font-size: 9px; font-weight: 600;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 4px 10px; cursor: pointer; border: none; outline: none;
    background: transparent; color: #aab4bc; transition: background 0.15s, color 0.15s;
  }
  .lang-btn.active { background: #1a1a1a; color: #f5f2ed; }
  .lang-btn:not(.active):hover { background: #e4e9ec; color: #3a4a54; }

  .lang-en { display: none; }

  .ticker { background: #1a1a1a; padding: 10px 48px; border-bottom: 3px solid #f0f3f5; }
  .ticker-inner { display: flex; justify-content: space-between; }
  .tick-item { text-align: center; flex: 1; padding: 6px 8px; border-left: 1px solid #2e2e2e; }
  .tick-item:first-child { border-left: none; }
  .tick-label { display: block; font-size: 8px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #555; margin-bottom: 4px; }
  .tick-val { font-size: 12px; color: #d4cfc8; }
  .tick-up { color: #6abf7b; font-size: 10px; margin-left: 4px; }
  .tick-down { color: #d4695a; font-size: 10px; margin-left: 4px; }

  /* ── Secondary market strip (tabbed) ── */
  .mkt-strip { background: #1a1a1a; }
  .mkt-tab-nav { display: flex; padding: 0 48px; border-bottom: 1px solid #222; }
  .mkt-tab-btn {
    font-family: 'DM Sans', sans-serif; font-size: 8px; font-weight: 600;
    letter-spacing: 2px; text-transform: uppercase;
    padding: 7px 14px 6px; cursor: pointer; border: none; background: transparent;
    color: #444; border-bottom: 2px solid transparent; margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
  }
  .mkt-tab-btn[data-group="eq"].active { color: #a8c8a0; border-bottom-color: #a8c8a0; }
  .mkt-tab-btn[data-group="co"].active { color: #d4b87a; border-bottom-color: #d4b87a; }
  .mkt-tab-btn[data-group="cr"].active { color: #b49ed4; border-bottom-color: #b49ed4; }
  .mkt-tab-btn:not(.active):hover { color: #777; }
  .mkt-panel { display: none; padding: 0 48px; }
  .mkt-panel.visible { display: flex; }
  .mkt-panel .tick-item { padding: 9px 8px; }

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
  .currency-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .currency-toggle { display: flex; gap: 0; border: 1px solid #cdd4d9; border-radius: 3px; overflow: hidden; flex-shrink: 0; }
  .currency-btn {
    font-family: 'DM Sans', sans-serif; font-size: 9px; font-weight: 600;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 4px 8px; cursor: pointer; border: none; outline: none;
    background: transparent; color: #aab4bc; transition: background 0.15s, color 0.15s;
  }
  .currency-btn.active { background: #1a1a1a; color: #f5f2ed; }
  .currency-btn:not(.active):hover { background: #e4e9ec; color: #3a4a54; }
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

  .calendar { padding: 24px 48px; }
  .cal-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #e4e9ec; }
  .cal-row:last-child { border-bottom: none; }
  .cal-date { font-size: 10px; color: #555; min-width: 46px; flex-shrink: 0; }
  .cal-badge { font-size: 7.5px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 2px 5px; border: 1px solid; min-width: 50px; text-align: center; flex-shrink: 0; }
  .cal-label { font-size: 12px; color: #1a1a1a; flex: 1; }
  .cal-days { font-size: 9px; color: #aab4bc; white-space: nowrap; flex-shrink: 0; }

  .weekly-mkt { background: #1a1a1a; padding: 16px 48px 14px; }
  .wm-title { font-size: 9px; font-weight: 500; letter-spacing: 2.5px; text-transform: uppercase; color: #555; margin-bottom: 2px; }
  .wm-subtitle { font-size: 8px; color: #444; margin-bottom: 12px; }
  .wm-table { width: 100%; border-collapse: collapse; }
  .wm-table th { font-size: 8px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #444; text-align: left; padding: 0 0 8px; border-bottom: 1px solid #2a2a2a; }
  .wm-table th:not(:first-child) { text-align: right; }
  .wm-table td { font-size: 11px; padding: 8px 0; border-bottom: 1px solid #2a2a2a; }
  .wm-table tr:last-child td { border-bottom: none; }
  .wm-label { font-size: 9px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #555; }
  .wm-val { color: #d4cfc8; text-align: right; padding-left: 12px; }
  .wm-chg { text-align: right; font-size: 10px; padding-left: 12px; }

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
    .mkt-tab-nav { padding: 0 12px; }
    .mkt-panel { padding: 0 8px; flex-wrap: wrap; }
    .mkt-panel .tick-item { flex: 1 1 45%; }
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

LANG_TOGGLE_JS = """
<script>
  function setLang(lang) {
    document.querySelectorAll('.lang-es').forEach(el => el.style.display = lang === 'es' ? '' : 'none');
    document.querySelectorAll('.lang-en').forEach(el => el.style.display = lang === 'en' ? ''  : 'none');
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    // swap static labels
    document.querySelectorAll('[data-es]').forEach(el => {
      el.textContent = lang === 'es' ? el.dataset.es : el.dataset.en;
    });
    localStorage.setItem('nlLang', lang);
  }
  (function(){
    var saved = localStorage.getItem('nlLang') || 'es';
    setLang(saved);
  })();

  function setCurrencyBase(base) {
    document.querySelectorAll('.currency-view').forEach(el => {
      el.style.display = el.dataset.base === base ? '' : 'none';
    });
    document.querySelectorAll('.currency-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.base === base);
    });
    localStorage.setItem('nlCurrencyBase', base);
  }
  (function(){
    var savedBase = localStorage.getItem('nlCurrencyBase') || 'MXN';
    setCurrencyBase(savedBase);
  })();

  function setMktTab(group) {
    document.querySelectorAll('.mkt-panel').forEach(function(p) { p.classList.remove('visible'); });
    var panel = document.getElementById('mkt-' + group);
    if (panel) panel.classList.add('visible');
    document.querySelectorAll('.mkt-tab-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.group === group);
    });
  }
  (function(){ setMktTab('eq'); })();
</script>
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
    digest:              dict,
    tickers:             list[dict],
    currency:            list[dict],
    week_stories:        list[dict],
    issue_number:        int = 1,
    is_friday:           bool = False,
    wordcloud_filename:  str | None = None,
    author:              str = "",
    secondary_tickers:   list[dict] | None = None,
) -> str:

    # Bilingual support: unwrap es/en, fallback for old flat digests
    digest_es = digest.get("es", digest)
    digest_en = digest.get("en", digest_es)  # fall back to ES if no EN

    today      = date.today().strftime("%A, %B %d, %Y").upper()
    issue_date = date.today().strftime("%B %d, %Y")

    # ── Ticker (language-neutral) ─────────────────────────────────────────
    tick_items = ""
    if not tickers:
        for label in ["DXY", "10Y UST", "VIX", "MSCI EM"]:
            tick_items += f"""
      <div class="tick-item">
        <span class="tick-label">{label}</span>
        <span class="tick-val">—</span>
        <span class=""></span>
      </div>"""
    else:
        for t in tickers:
            chg_cls = "tick-up" if t["direction"] == "up" else ("tick-down" if t["direction"] == "down" else "")
            tick_items += f"""
      <div class="tick-item">
        <span class="tick-label">{t['label']}</span>
        <span class="tick-val">{t['value']}</span>
        <span class="{chg_cls}">{t['change']}</span>
      </div>"""

    # ── Sentiment gauge ───────────────────────────────────────────────────
    s          = digest_es.get("sentiment", {})
    label_es   = s.get("label_es", s.get("label", "Cauteloso"))
    label_en   = s.get("label_en", s.get("label", "Cautious"))
    position   = max(5, min(95, int(s.get("position", 50))))
    context_es = s.get("context_es", s.get("context", ""))
    context_en = s.get("context_en", context_es)
    cls_map    = {"Risk-Off": "risk-off", "Cautious": "cautious", "Risk-On": "risk-on"}
    sent_cls   = cls_map.get(label_en, "cautious")

    # ── Stories (both languages) ──────────────────────────────────────────
    stories_es = digest_es.get("stories", [])
    stories_en = digest_en.get("stories", stories_es)

    stories_html = ""
    for i, story in enumerate(stories_es):
        story_en = stories_en[i] if i < len(stories_en) else story
        stories_html += f"""
{DIVIDER}
<div class="story">
  <div class="story-meta">
    <span class="story-source">{story['source']}</span>
    <span class="story-tag">{story.get('tag','')}</span>
  </div>
  <div class="lang-es">
    <div class="story-headline">{story['headline']}</div>
    <div class="story-body">{story['body']}</div>
    <a href="{story['url']}" class="read-more">Leer m&aacute;s &rarr;</a>
  </div>
  <div class="lang-en">
    <div class="story-headline">{story_en.get('headline', story['headline'])}</div>
    <div class="story-body">{story_en.get('body', story['body'])}</div>
    <a href="{story['url']}" class="read-more">Read more &rarr;</a>
  </div>
</div>"""

    # ── Currency table (base-toggle, language-neutral) ───────────────────
    # currency is now a dict: {bases: [...], matrix: {base: [rows]}}
    currency_bases  = currency.get("bases", ["MXN"])
    currency_matrix = currency.get("matrix", {})

    def build_tbody(rows):
        tbody = ""
        for r in rows:
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
        return tbody

    currency_tables_html = ""
    for i, base in enumerate(currency_bases):
        rows  = currency_matrix.get(base, [])
        tbody = build_tbody(rows)
        display = "" if i == 0 else "display:none;"
        currency_tables_html += f"""
    <div class="currency-view" data-base="{base}" style="{display}">
      <table class="currency-table">
        <thead>
          <tr>
            <th data-es="Par" data-en="Pair">Par</th>
            <th data-es="Tipo" data-en="Rate">Tipo</th>
            <th style="text-align:right;">1D</th>
            <th style="text-align:right;">1W</th>
          </tr>
        </thead>
        <tbody>{tbody}
        </tbody>
      </table>
    </div>"""

    currency_btns_html = ""
    for i, base in enumerate(currency_bases):
        active = "active" if i == 0 else ""
        currency_btns_html += f'<button class="currency-btn {active}" data-base="{base}" onclick="setCurrencyBase(\'{base}\')">{base}</button>'

    # ── Weekly markets (Fridays only) ────────────────────────────────────
    weekly_mkt_html = ""
    if is_friday and tickers:
        monday_wm = date.today() - timedelta(days=date.today().weekday())
        friday_wm = monday_wm + timedelta(days=4)
        wm_label  = f"{monday_wm.strftime('%b %d')}&ndash;{friday_wm.strftime('%d, %Y')}"
        wm_rows = ""
        for t in tickers:
            c_d = "tick-up" if t["direction"]                == "up" else ("tick-down" if t["direction"]                == "down" else "")
            c_w = "tick-up" if t.get("direction_1w","flat") == "up" else ("tick-down" if t.get("direction_1w","flat") == "down" else "")
            wm_rows += f"""
        <tr>
          <td class="wm-label">{t['label']}</td>
          <td class="wm-val">{t['value']}</td>
          <td class="wm-chg {c_d}">{t['change']}</td>
          <td class="wm-chg {c_w}">{t.get('chg_1w','&mdash;')}</td>
        </tr>"""
        weekly_mkt_html = f"""
{DIVIDER}
<div class="weekly-mkt">
  <div class="wm-title" data-es="La Semana en Mercados &middot; {wm_label}" data-en="Week in Markets &middot; {wm_label}">La Semana en Mercados &middot; {wm_label}</div>
  <div class="wm-subtitle" data-es="1D = var. diaria &nbsp;&middot;&nbsp; 1S = var. semanal" data-en="1D = daily change &nbsp;&middot;&nbsp; 1W = weekly change">1D = var. diaria &nbsp;&middot;&nbsp; 1S = var. semanal</div>
  <table class="wm-table">
    <thead>
      <tr>
        <th data-es="Indicador" data-en="Indicator">Indicador</th>
        <th style="text-align:right;" data-es="Valor" data-en="Value">Valor</th>
        <th style="text-align:right;">1D</th>
        <th style="text-align:right;" data-es="1S" data-en="1W">1S</th>
      </tr>
    </thead>
    <tbody>{wm_rows}
    </tbody>
  </table>
</div>"""

    # ── Economic calendar ─────────────────────────────────────────────────
    from storage import get_upcoming_calendar
    _months_cal = ["","ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    _cal_colors = {"banxico": "#4a9e6a", "fed": "#5a8abf", "mx-data": "#c8943a", "us-data": "#7a9aaa"}
    _cal_badges = {"banxico": "BANXICO", "fed": "FED",     "mx-data": "INEGI",   "us-data": "BLS"}

    cal_rows = ""
    for event_date, label_ev, etype, delta in get_upcoming_calendar(n=5):
        color    = _cal_colors.get(etype, "#aab4bc")
        badge    = _cal_badges.get(etype, etype.upper())
        date_fmt = f"{event_date.day:02d} {_months_cal[event_date.month].upper()}"
        days_str = "Hoy" if delta == 0 else ("Ma\u00f1ana" if delta == 1 else f"{delta}d")
        cal_rows += f"""
      <div class="cal-row">
        <span class="cal-date">{date_fmt}</span>
        <span class="cal-badge" style="color:{color}; border-color:{color};">{badge}</span>
        <span class="cal-label">{label_ev}</span>
        <span class="cal-days">{days_str}</span>
      </div>"""

    calendar_html = f"""
{DIVIDER}
<div class="calendar">
  <div class="section-title"
       data-es="Pr&oacute;ximas Fechas Clave"
       data-en="Key Upcoming Dates">Pr&oacute;ximas Fechas Clave</div>
  {cal_rows}
</div>"""

    # ── Quote (both languages) ────────────────────────────────────────────
    q_es = digest_es.get("quote", {})
    q_en = digest_en.get("quote", q_es)

    # ── Week in review (both languages) ───────────────────────────────────
    week_html = ""
    if is_friday and week_stories:
        monday = date.today() - timedelta(days=date.today().weekday())
        friday = monday + timedelta(days=4)
        wlabel = f"{monday.strftime('%b %d')}&ndash;{friday.strftime('%d, %Y')}"
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
          <span class="tl-tag">{ws.get('tag','')}</span>
          <div class="lang-es">
            <div class="tl-headline">{ws.get('headline','')}</div>
            <div class="tl-body">{ws.get('body','')}</div>
          </div>
          <div class="lang-en">
            <div class="tl-headline">{ws.get('headline_en', ws.get('headline',''))}</div>
            <div class="tl-body">{ws.get('body_en', ws.get('body',''))}</div>
          </div>
        </div>
      </div>"""
        week_html = f"""
{DIVIDER}
<div class="week">
  <div class="section-title"
       data-es="Resumen Semanal &middot; {wlabel}"
       data-en="Week in Review &middot; {wlabel}">Resumen Semanal &middot; {wlabel}</div>
  <div class="timeline">{tl_items}
  </div>
</div>"""

    # ── Secondary tickers (tabbed strip) ─────────────────────────────────
    tabbed_strip_html = ""
    if secondary_tickers:
        tab_btns = ""
        panels   = ""
        for g in secondary_tickers:
            gid = g["group"]
            tab_btns += (
                f'<button class="mkt-tab-btn" data-group="{gid}"'
                f' onclick="setMktTab(\'{gid}\')">{g["label"]}</button>'
            )
            items = ""
            for t in g["tickers"]:
                chg_cls = "tick-up" if t["direction"] == "up" else ("tick-down" if t["direction"] == "down" else "")
                items += f"""
        <div class="tick-item">
          <span class="tick-label">{t['label']}</span>
          <span class="tick-val">{t['value']}</span>
          <span class="{chg_cls}">{t['change']}</span>
        </div>"""
            panels += f'\n    <div class="mkt-panel" id="mkt-{gid}">{items}\n    </div>'
        tabbed_strip_html = f"""
  <div class="mkt-strip">
    <div class="mkt-tab-nav">{tab_btns}</div>{panels}
  </div>"""

    # ── Sentiment chart (Fridays only) ───────────────────────────────────
    sentiment_chart_html = ""
    if is_friday:
        import json, urllib.parse
        from storage import get_week_sentiment
        week_sent = get_week_sentiment()
        if week_sent:
            sc_labels = [d["day"] for d in week_sent]
            sc_data   = [d["position"] for d in week_sent]
            sc_colors = [
                "#b84a3a" if d["position"] < 36 else
                ("#4a9e6a" if d["position"] > 64 else "#e8a030")
                for d in week_sent
            ]
            sc_config = {
                "type": "line",
                "data": {
                    "labels": sc_labels,
                    "datasets": [{
                        "data": sc_data,
                        "borderColor": "#3a4a54",
                        "borderWidth": 2,
                        "pointBackgroundColor": sc_colors,
                        "pointBorderColor":     sc_colors,
                        "pointRadius": 6,
                        "fill": False,
                        "tension": 0.3,
                    }],
                },
                "options": {
                    "responsive": False,
                    "plugins": {"legend": {"display": False}},
                    "scales": {
                        "y": {"min": 0, "max": 100, "ticks": {"display": False}, "grid": {"color": "#dde3e8"}},
                        "x": {"ticks": {"color": "#888888", "font": {"size": 11}}, "grid": {"display": False}},
                    },
                },
            }
            sc_url = (
                "https://quickchart.io/chart"
                f"?w=544&h=160&bkg=%23f0f3f5&f=png"
                f"&c={urllib.parse.quote(json.dumps(sc_config, separators=(',', ':')))}"
            )
            monday_sc = date.today() - timedelta(days=date.today().weekday())
            friday_sc = monday_sc + timedelta(days=4)
            sc_label  = f"{monday_sc.strftime('%b %d')}&ndash;{friday_sc.strftime('%d, %Y')}"
            sentiment_chart_html = f"""
{DIVIDER}
<div style="padding:24px 48px 8px;">
  <div class="section-title"
       data-es="Sentimiento Semanal &middot; {sc_label}"
       data-en="Weekly Sentiment &middot; {sc_label}">Sentimiento Semanal &middot; {sc_label}</div>
  <img src="{sc_url}" style="width:100%; border:1px solid #cdd4d9; margin-top:14px;" alt="Weekly sentiment chart"/>
</div>"""

    # ── Wordcloud ─────────────────────────────────────────────────────────
    wordcloud_html = ""
    if wordcloud_filename:
        wordcloud_url = f"{ASSET_BASE_URL.rstrip('/')}/{wordcloud_filename}"
        wordcloud_html = f"""
{DIVIDER}
<div style="padding:24px 48px 8px;">
  <div class="section-title"
       data-es="La Semana en Palabras"
       data-en="The Week in Words">La Semana en Palabras</div>
  <img src="{wordcloud_url}" style="width:100%; border:1px solid #cdd4d9;" alt="Word cloud"/>
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
      <div class="lang-toggle">
        <button class="lang-btn active" data-lang="es" onclick="setLang('es')">ES</button>
        <button class="lang-btn"        data-lang="en" onclick="setLang('en')">EN</button>
      </div>
      <span>NO. {issue_number}</span>
    </div>
  </div>

  <div class="ticker">
    <div class="ticker-inner">{tick_items}
    </div>
  </div>

  {tabbed_strip_html}

  <div class="editor-note">
    <div class="lang-es"><p>{digest_es.get('editor_note','')}</p></div>
    <div class="lang-en"><p>{digest_en.get('editor_note', digest_es.get('editor_note',''))}</p></div>
    <div class="editor-sig">&mdash; {author}</div>
  </div>

  {DIVIDER}

  <div class="sentiment">
    <div class="sentiment-header">
      <span class="sentiment-label"
            data-es="Sentimiento del D&#237;a"
            data-en="Market Sentiment">Sentimiento del D&#237;a</span>
      <span class="sentiment-reading {sent_cls} lang-es">{label_es}</span>
      <span class="sentiment-reading {sent_cls} lang-en">{label_en}</span>
    </div>
    <div class="gauge-track">
      <div class="gauge-marker {sent_cls}" style="left:{position}%;"></div>
    </div>
    <div class="gauge-ticks">
      <span data-es="Avers. al Riesgo" data-en="Risk-Off">Avers. al Riesgo</span>
      <span data-es="Neutral"          data-en="Neutral">Neutral</span>
      <span data-es="Apetito de Riesgo" data-en="Risk-On">Apetito de Riesgo</span>
    </div>
    <div class="sentiment-context lang-es">{context_es}</div>
    <div class="sentiment-context lang-en">{context_en}</div>
  </div>

  {stories_html}

  {DIVIDER}

  <div class="currency">
    <div class="currency-header">
      <div class="section-title"
           data-es="Tipo de Cambio"
           data-en="Exchange Rates">Tipo de Cambio</div>
      <div class="currency-toggle">{currency_btns_html}</div>
    </div>
    {currency_tables_html}
  </div>

  {weekly_mkt_html}

  {calendar_html}

  {DIVIDER}

  <div class="quote">
    <span class="quote-mark">&ldquo;</span>
    <div class="lang-es">
      <div class="quote-text">{q_es.get('text','')}</div>
      <div class="quote-attr">{q_es.get('attribution','')}</div>
    </div>
    <div class="lang-en">
      <div class="quote-text">{q_en.get('text', q_es.get('text',''))}</div>
      <div class="quote-attr">{q_en.get('attribution', q_es.get('attribution',''))}</div>
    </div>
  </div>

  {week_html}

  {sentiment_chart_html}

  {wordcloud_html}

  <div class="footer">
    <span class="footer-name">{NEWSLETTER_NAME}</span>
    <span class="footer-by lang-es">por {author}</span>
    <span class="footer-by lang-en">by {author}</span>
  </div>

</div>
{LANG_TOGGLE_JS}
</body>
</html>"""
