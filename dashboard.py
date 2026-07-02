"""Vygeneruje statickou stránku docs/index.html — graf hodnoty portfolia, aktuální
alokace a archiv vysvětlených pojmů. Hostovaná zdarma přes GitHub Pages (Settings →
Pages → Deploy from branch → main /docs). Grafy kreslí Chart.js přes CDN, žádná nová
Python závislost.
"""
import html
import json
import pathlib

import markdown

import glossary
import history

OUT_DIR = pathlib.Path("docs")


def _alloc_data(positions):
    items = [(p["name"], p["alloc_pct"]) for p in positions if p.get("alloc_pct")]
    items.sort(key=lambda x: -x[1])
    return items


def build(data, subject, text, now):
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / ".nojekyll").touch()

    hist = history.all_rows()
    hist_labels = json.dumps([d.isoformat() for d, _ in hist])
    hist_values = json.dumps([v for _, v in hist])

    alloc = _alloc_data(data["positions"])
    alloc_labels = json.dumps([name for name, _ in alloc])
    alloc_values = json.dumps([pct for _, pct in alloc])

    terms = list(reversed(glossary.all_entries()))
    terms_html = "".join(
        f"<li><time>{html.escape(d)}</time> — {html.escape(t)}</li>" for d, t in terms
    ) or "<li>Zatím žádné.</li>"

    briefing_html = markdown.markdown(text, extensions=["extra", "sane_lists", "tables"])

    page = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portfolio Briefing</title>
<meta name="robots" content="noindex">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 900px;
          margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .updated {{ color: #888; font-size: 0.9rem; margin-bottom: 2rem; }}
  .total {{ font-size: 1.8rem; font-weight: 700; }}
  section {{ margin: 2.5rem 0; }}
  .chart-box {{ max-width: 100%; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.3rem 0.6rem; border-bottom: 1px solid #ddd; }}
  ul.terms {{ padding-left: 1.2rem; }}
  ul.terms time {{ color: #888; font-size: 0.85rem; }}
  .briefing {{ background: rgba(127,127,127,0.08); border-radius: 8px; padding: 1rem 1.5rem; }}
  .disclaimer {{ font-size: 0.85rem; color: #888; margin-top: 3rem; }}
</style>
</head>
<body>
<h1>📈 Portfolio Briefing</h1>
<p class="updated">Naposledy aktualizováno {now:%d.%m.%Y %H:%M} (Praha) · <span class="total">{data['total_czk']:,.0f} Kč</span></p>

<section>
  <h2>Vývoj hodnoty portfolia</h2>
  <div class="chart-box"><canvas id="historyChart"></canvas></div>
</section>

<section>
  <h2>Aktuální alokace</h2>
  <div class="chart-box" style="max-width:420px"><canvas id="allocChart"></canvas></div>
</section>

<section>
  <h2>{html.escape(subject)}</h2>
  <div class="briefing">{briefing_html}</div>
</section>

<section>
  <h2>📚 Archiv vysvětlených pojmů</h2>
  <ul class="terms">{terms_html}</ul>
</section>

<p class="disclaimer">⚠️ Nejsem finanční poradce; informativní shrnutí, ne investiční doporučení. Ceny orientační.</p>

<script>
new Chart(document.getElementById('historyChart'), {{
  type: 'line',
  data: {{
    labels: {hist_labels},
    datasets: [{{
      label: 'Hodnota portfolia (Kč)',
      data: {hist_values},
      borderColor: '#2b7fff',
      backgroundColor: 'rgba(43,127,255,0.1)',
      fill: true,
      tension: 0.2,
      pointRadius: 2,
    }}],
  }},
  options: {{ scales: {{ y: {{ beginAtZero: false }} }} }},
}});

new Chart(document.getElementById('allocChart'), {{
  type: 'doughnut',
  data: {{
    labels: {alloc_labels},
    datasets: [{{ data: {alloc_values} }}],
  }},
}});
</script>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")
