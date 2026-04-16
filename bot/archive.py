# ─────────────────────────────────────────────
#  archive.py  —  Saves pretty HTML issues and
#  rebuilds index.html with a full dashboard:
#  sentiment timeline, volatility, story count,
#  and issue cards.
# ─────────────────────────────────────────────

import os
import json
from datetime import date, datetime
from pretty_renderer import build_pretty_html
from config import NEWSLETTER_NAME, AUTHOR_NAME, DIGEST_DIR, ARCHIVE_DIR

def save_pretty_issue(
    digest:             dict,
    tickers:            list[dict],
    currency:           list[dict],
    week_stories:       list[dict],
    issue_number:       int,
    is_friday:          bool = False,
    wordcloud_filename: str | None = None,
    author:             str = "",
    secondary_tickers:  list[dict] | None = None,
    visual:             dict | None = None,
) -> str:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    today    = date.today().isoformat()
    filename = f"{today}.html"
    filepath = os.path.join(ARCHIVE_DIR, filename)

    html = build_pretty_html(
        digest             = digest,
        tickers            = tickers,
        secondary_tickers  = secondary_tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_number,
        is_friday          = is_friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
        visual             = visual,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [archive] Saved pretty issue to {filepath}")
    _update_thread_index(digest, today)
    rebuild_index()
    return filepath


def _load_all_digests() -> list[dict]:
    entries = []
    if not os.path.exists(DIGEST_DIR):
        return entries

    for filename in sorted(os.listdir(DIGEST_DIR)):
        if not filename.endswith(".json"):
            continue
        date_str = filename.replace(".json", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        with open(os.path.join(DIGEST_DIR, filename), encoding="utf-8") as f:
            data = json.load(f)

        digest    = data.get("digest", {})
        digest_es = digest.get("es", digest)
        sentiment = digest_es.get("sentiment", {})
        stories   = digest_es.get("stories", [])
        headline  = stories[0].get("headline", "") if stories else ""

        label_es = sentiment.get("label_es", sentiment.get("label", "Cautious"))
        label_en = sentiment.get("label_en", sentiment.get("label", "Cautious"))

        text_parts = [digest_es.get("editor_note", ""), headline]
        for s in stories:
            text_parts += [s.get("headline", ""), s.get("body", ""), s.get("source", ""), s.get("tag", "")]

        entries.append({
            "date":        date_str,
            "label":       label_en,
            "label_es":    label_es,
            "position":    int(sentiment.get("position", 50)),
            "story_count": len(stories),
            "headline":    headline,
            "search_text": " ".join(text_parts).lower(),
        })

    return entries


def _update_thread_index(digest: dict, date_str: str) -> None:
    """
    Reads docs/thread_index.json, merges in new thread_tag entries from today's digest,
    and writes it back. Called once per run so the index grows incrementally.
    """
    index_path = os.path.join(ARCHIVE_DIR, "thread_index.json")

    # Load existing index or start fresh
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            try:
                thread_index = json.load(f)
            except json.JSONDecodeError:
                thread_index = {}
    else:
        thread_index = {}

    digest_es = digest.get("es", digest)
    for story in digest_es.get("stories", []):
        tag = story.get("thread_tag")
        if not tag or not isinstance(tag, str):
            continue
        entry = {
            "date":     date_str,
            "headline": story.get("headline", ""),
        }
        if tag not in thread_index:
            thread_index[tag] = []
        # Avoid duplicates (in case run is re-executed for same date)
        existing_dates = {e["date"] for e in thread_index[tag]}
        if date_str not in existing_dates:
            thread_index[tag].append(entry)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(thread_index, f, ensure_ascii=False, indent=2)
    print(f"  [archive] Thread index updated ({len(thread_index)} tags).")


def rebuild_index() -> None:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    digest_data    = _load_all_digests()
    digest_by_date = {d["date"]: d for d in digest_data}

    chart_dates    = [d["date"]        for d in digest_data]
    chart_position = [d["position"]    for d in digest_data]
    chart_labels   = [d["label"]       for d in digest_data]

    point_colors = [
        "#b84a3a" if l == "Risk-Off" else ("#4a9e6a" if l == "Risk-On" else "#e8a030")
        for l in chart_labels
    ]

    # -- Load thread index for Coverage Map and Thread Index sections -----------
    tag_counts: dict[str, int] = {}
    thread_index_data: dict = {}
    thread_index_path = os.path.join(ARCHIVE_DIR, "thread_index.json")
    if os.path.exists(thread_index_path):
        with open(thread_index_path, encoding="utf-8") as f:
            try:
                thread_index_data = json.load(f)
            except json.JSONDecodeError:
                thread_index_data = {}
        for tag, entries in thread_index_data.items():
            tag_counts[tag] = len(entries)

    # Sort by count desc, top 10
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]

    coverage_map_html = ""
    if top_tags:
        max_count = top_tags[0][1] if top_tags else 1
        bars = ""
        for tag, count in top_tags:
            pct = int((count / max_count) * 100)
            bars += f"""
      <div style="margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <span style="font-family:Arial,sans-serif; font-size:10px; color:#3a4a54; font-weight:500;">{tag}</span>
          <span style="font-family:Arial,sans-serif; font-size:9px; color:#aab4bc;">{count}</span>
        </div>
        <div style="height:6px; background:#dde3e8; border-radius:3px;">
          <div style="height:6px; background:#3a4a54; border-radius:3px; width:{pct}%;"></div>
        </div>
      </div>"""
        coverage_map_html = f"""
  <div style="background:#f0f3f5; border:1px solid #cdd4d9; padding:24px 28px; margin-bottom:24px;">
    <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:16px;">Coverage Map -- Top Threads</p>
    {bars}
  </div>"""

    thread_index_html = ""
    if thread_index_data:
        thread_sections = ""
        for tag, entries in sorted(thread_index_data.items(), key=lambda x: -len(x[1])):
            if len(entries) < 2:
                continue
            links = ""
            for entry in sorted(entries, key=lambda e: e["date"], reverse=True)[:5]:
                links += f"""
          <a href="{entry['date']}.html" style="display:block; text-decoration:none; padding:8px 0; border-bottom:1px solid #e4e9ec; font-family:Georgia,serif; font-size:13px; color:#1a1a1a; line-height:1.4;">
            <span style="font-family:Arial,sans-serif; font-size:9px; color:#aab4bc; display:block; margin-bottom:2px;">{entry['date']}</span>
            {entry['headline']}
          </a>"""
            thread_sections += f"""
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer; font-family:Arial,sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#3a4a54; padding:10px 0; border-bottom:1px solid #cdd4d9; list-style:none; display:flex; justify-content:space-between;">
          {tag}
          <span style="color:#aab4bc; font-weight:400;">{len(entries)} stories</span>
        </summary>
        <div style="padding-top:4px;">{links}</div>
      </details>"""
        if thread_sections:
            thread_index_html = f"""
  <div style="background:#f0f3f5; border:1px solid #cdd4d9; padding:24px 28px; margin-bottom:24px;">
    <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:16px;">Topic Threads</p>
    {thread_sections}
  </div>"""

    issues = sorted(
        [f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".html") and f != "index.html"],
        reverse=True,
    )

    cards = ""
    for i, filename in enumerate(issues):
        issue_date_str = filename.replace(".html", "")
        try:
            dt    = datetime.strptime(issue_date_str, "%Y-%m-%d")
            label = dt.strftime("%A, %B %d, %Y")
        except ValueError:
            label = issue_date_str

        issue_num   = len(issues) - i
        d           = digest_by_date.get(issue_date_str, {})
        headline    = d.get("headline", "")
        label_en    = d.get("label", "")
        label_es    = d.get("label_es", "")
        story_count = d.get("story_count", 0)

        sent_color = {"Risk-Off": "#b84a3a", "Cautious": "#9a6a1a", "Risk-On": "#4a9e6a"}.get(label_en, "#aab4bc")
        sent_pill  = f'<span style="font-size:9px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:{sent_color}; padding:3px 10px; border:1px solid {sent_color}; border-radius:20px;">{label_es}</span>' if label_es else ""
        count_html = f'<span style="font-size:9px; color:#aab4bc; margin-left:10px;">{story_count} stories</span>' if story_count else ""

        cards += f"""
    <a href="{filename}" style="display:block; text-decoration:none; background:#f0f3f5; border:1px solid #cdd4d9; padding:20px 28px; margin-bottom:10px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span style="font-family:Arial,sans-serif; font-size:9px; font-weight:600; letter-spacing:2px; text-transform:uppercase; color:#aab4bc;">ISSUE #{issue_num} &middot; {label}</span>
        <span>{sent_pill}{count_html}</span>
      </div>
      <div style="font-family:Georgia,serif; font-size:17px; font-weight:700; color:#1a1a1a; line-height:1.35;">{headline or "View issue &rarr;"}</div>
    </a>"""

    search_index = [
        {
            "date":     d["date"],
            "filename": f"{d['date']}.html",
            "text":     d["search_text"],
            "label":    d["label"],
        }
        for d in digest_data
    ]

    search_index_js = json.dumps(search_index)
    dates_js    = json.dumps(chart_dates)
    position_js = json.dumps(chart_position)
    colors_js   = json.dumps(point_colors)

    charts_html = ""
    if digest_data:
        charts_html = f"""
  <div style="background:#f0f3f5; border:1px solid #cdd4d9; padding:28px 32px; margin-bottom:24px;">
    <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:16px;">Sentiment Timeline</p>
    <div style="position:relative; height:200px;">
      <canvas id="sentimentChart"></canvas>
    </div>
  </div>

  <script>
    const dates    = {dates_js};
    const position = {position_js};
    const colors   = {colors_js};

    const _zones = {{
      id: 'zones',
      beforeDraw(chart) {{
        const {{ ctx, chartArea: {{ left, right }}, scales: {{ y }} }} = chart;
        [
          {{ min: 0,  max: 40,  color: 'rgba(212,105,90,0.26)'  }},
          {{ min: 40, max: 60,  color: 'rgba(232,160,48,0.22)'  }},
          {{ min: 60, max: 100, color: 'rgba(106,191,123,0.26)' }},
        ].forEach(({{ min, max, color }}) => {{
          ctx.save();
          ctx.fillStyle = color;
          ctx.fillRect(left, y.getPixelForValue(max), right - left, y.getPixelForValue(min) - y.getPixelForValue(max));
          ctx.restore();
        }});
      }}
    }};

    const _faintGrid = {{
      id: 'faintGrid',
      beforeDraw(chart) {{
        const {{ ctx, chartArea: {{ left, right }}, scales: {{ y }} }} = chart;
        ctx.save();
        ctx.strokeStyle = 'rgba(140,158,170,0.65)';
        ctx.lineWidth = 0.5;
        for (let v = 5; v < 100; v += 5) {{
          if ([25, 50, 75].includes(v)) continue;
          const py = y.getPixelForValue(v);
          ctx.beginPath(); ctx.moveTo(left, py); ctx.lineTo(right, py); ctx.stroke();
        }}
        ctx.restore();
      }}
    }};

    const _zoneLabels = {{
      id: 'zoneLabels',
      afterDraw(chart) {{
        const {{ ctx, chartArea: {{ right }}, scales: {{ y }} }} = chart;
        [
          {{ mid: 20,  label: 'RISK-OFF', color: '#d4695a' }},
          {{ mid: 50,  label: 'CAUTIOUS', color: '#c8922a' }},
          {{ mid: 80,  label: 'RISK-ON',  color: '#4fa868' }},
        ].forEach(({{ mid, label, color }}) => {{
          ctx.save();
          ctx.font = '700 7.5px Arial';
          ctx.fillStyle = color;
          ctx.textAlign = 'left';
          ctx.fillText(label, right + 10, y.getPixelForValue(mid) + 3);
          ctx.restore();
        }});
      }}
    }};

    const _midline = {{
      id: 'midline',
      beforeDraw(chart) {{
        const {{ ctx, chartArea: {{ left, right }}, scales: {{ y }} }} = chart;
        const py = y.getPixelForValue(50);
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = 'rgba(58,74,84,0.25)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(left, py); ctx.lineTo(right, py); ctx.stroke();
        ctx.restore();
      }}
    }};

    new Chart(document.getElementById('sentimentChart'), {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [{{
          data: position,
          borderColor: '#3a4a54',
          borderWidth: 2,
          pointBackgroundColor: colors,
          pointBorderColor: colors,
          pointRadius: 5,
          pointHoverRadius: 7,
          fill: false,
          tension: 0.3,
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        layout: {{ padding: {{ right: 72 }} }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: '#3a4a54',
            titleFont: {{ family: 'Arial', size: 9 }},
            bodyFont: {{ family: 'Arial', size: 9 }},
            callbacks: {{
              label: (ctx) => {{
                const v = ctx.raw;
                const labels = {json.dumps(chart_labels)};
                return ' ' + v + ' \u00b7 ' + labels[ctx.dataIndex];
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            ticks: {{ font: {{ family: 'Arial', size: 8 }}, color: '#aab4bc', maxRotation: 45, autoSkip: true, maxTicksLimit: 10 }},
            grid: {{ display: false }},
            border: {{ display: false }},
          }},
          y: {{
            min: 0, max: 100,
            afterBuildTicks(scale) {{
              scale.ticks = [0, 25, 50, 75, 100].map(v => ({{ value: v }}));
            }},
            ticks: {{ font: {{ family: 'Arial', size: 8 }}, color: '#8a9aa4' }},
            grid: {{ color: '#8fa4b4', lineWidth: 1 }},
            border: {{ display: false }},
          }}
        }}
      }},
      plugins: [_zones, _faintGrid, _zoneLabels, _midline]
    }});
  </script>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{NEWSLETTER_NAME} -- Archive</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#dde3e8; font-family:'DM Sans',sans-serif; padding:40px 16px; }}
    .wrap {{ max-width:640px; margin:0 auto; }}
    .masthead {{ background:#1a1a1a; padding:32px 36px; margin-bottom:24px; display:flex; justify-content:space-between; align-items:flex-end; }}
    .masthead-name {{ font-family:'Playfair Display',serif; font-size:28px; color:#f5f2ed; margin-bottom:4px; }}
    .masthead-sub {{ font-size:10px; letter-spacing:2px; text-transform:uppercase; color:#555; }}
    .masthead-count {{ font-size:11px; color:#444; letter-spacing:1px; text-align:right; }}
    a {{ color:inherit; }}
    .search-wrap {{ position:relative; margin-bottom:16px; }}
    .search-input {{
      width:100%; padding:12px 40px 12px 16px;
      background:#f0f3f5; border:1px solid #cdd4d9;
      font-family:'DM Sans',sans-serif; font-size:13px; color:#1a1a1a;
      outline:none; box-sizing:border-box;
    }}
    .search-input:focus {{ border-color:#3a4a54; }}
    .search-input::placeholder {{ color:#aab4bc; }}
    .search-clear {{
      position:absolute; right:12px; top:50%; transform:translateY(-50%);
      cursor:pointer; font-size:16px; color:#aab4bc; display:none;
      background:none; border:none; padding:0;
    }}
    .search-clear:hover {{ color:#1a1a1a; }}
    .search-count {{ font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:#aab4bc; margin-bottom:14px; }}
    .no-results {{ color:#aab4bc; font-size:13px; font-style:italic; padding:20px 0; }}
    @media (max-width:600px) {{
      body {{ padding:16px 0; }}
      .wrap {{ padding:0 12px; }}
      .masthead {{ padding:24px 20px; flex-direction:column; align-items:flex-start; gap:8px; }}
    }}
  </style>
</head>
<body>
<div class="wrap">

  <div class="masthead">
    <div>
      <div class="masthead-name">{NEWSLETTER_NAME}</div>
      <div class="masthead-sub">Archive -- by {AUTHOR_NAME}</div>
    </div>
    <div class="masthead-count">{len(issues)} issue{"s" if len(issues) != 1 else ""}</div>
  </div>

  {charts_html}

  {coverage_map_html}
  {thread_index_html}

  <div class="search-wrap">
    <input class="search-input" id="searchInput" type="text" placeholder="Search issues...">
    <button class="search-clear" id="searchClear" onclick="clearSearch()">x</button>
  </div>
  <div class="search-count" id="searchCount"></div>

  <p style="font-family:Arial,sans-serif; font-size:9px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#aab4bc; margin-bottom:14px;" id="allIssuesLabel">All Issues</p>

  <div id="cardsContainer">
  {cards if cards else '<p style="color:#aab4bc; font-size:13px;">No issues yet.</p>'}
  </div>

  <script>
    const searchIndex = {search_index_js};
    const input     = document.getElementById('searchInput');
    const clearBtn  = document.getElementById('searchClear');
    const container = document.getElementById('cardsContainer');
    const countEl   = document.getElementById('searchCount');
    const labelEl   = document.getElementById('allIssuesLabel');
    const allCards  = Array.from(container.querySelectorAll('a'));

    input.addEventListener('input', () => {{
      const q = input.value.trim().toLowerCase();
      clearBtn.style.display = q ? 'block' : 'none';
      if (!q) {{
        allCards.forEach(c => c.style.display = 'block');
        countEl.textContent = '';
        labelEl.textContent = 'All Issues';
        return;
      }}
      const tokens  = q.split(/\\s+/).filter(Boolean);
      const matches = searchIndex.filter(item => tokens.every(t => item.text.includes(t)));
      const matchDates = new Set(matches.map(m => m.date));
      let shown = 0;
      allCards.forEach(card => {{
        const date = card.getAttribute('href').replace('.html','');
        if (matchDates.has(date)) {{ card.style.display = 'block'; shown++; }}
        else card.style.display = 'none';
      }});
      labelEl.textContent = shown > 0 ? 'Matching Issues' : '';
      countEl.textContent = shown > 0 ? shown + ' result' + (shown !== 1 ? 's' : '') + ' for "' + input.value.trim() + '"' : '';
      if (shown === 0) {{
        if (!document.getElementById('noResults')) {{
          const msg = document.createElement('p');
          msg.id = 'noResults'; msg.className = 'no-results';
          msg.textContent = 'No issues found for "' + input.value.trim() + '"';
          container.appendChild(msg);
        }}
      }} else {{
        const msg = document.getElementById('noResults');
        if (msg) msg.remove();
      }}
    }});

    function clearSearch() {{
      input.value = '';
      input.dispatchEvent(new Event('input'));
      input.focus();
    }}
  </script>

</div>
</body>
</html>"""

    index_path = os.path.join(ARCHIVE_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"  [archive] Index rebuilt with {len(issues)} issue(s).")
