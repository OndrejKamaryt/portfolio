"""Vygeneruje statickou stránku docs/index.html — tmavý dashboard (design 'Portfolio
Dashboard.dc.html', varianta 2a): KPI karty, graf hodnoty portfolia, tabulka pozic s
filtrem a postranní panel s posledním briefingem + archivem vysvětlených pojmů.

Na rozdíl od originálního návrhu (mockup s náhodnými daty) je tu VŠECHNO spočítané
z reálných dat — žádný fiktivní benchmark (S&P 500 srovnání) ani vymyšlené sparkliny
u jednotlivých pozic, protože bychom je museli fabrikovat. Grafy kreslí Chart.js přes
CDN, žádná nová Python závislost.
"""
import datetime
import html
import json
import pathlib

import markdown

import glossary
import history

OUT_DIR = pathlib.Path("docs")

GREEN = "#33d68f"
RED = "#ff5d6c"
MUTED = "#565e70"
TYPE_COLORS = ["#7aa2ff", "#4ad3a8", "#f0b35c", "#c792ea", "#ff8fa3", "#8fa7bd"]


def _fmt_czk(v):
    return f"{v:,.0f}".replace(",", " ") + " Kč"


def _fmt_pct(v, decimals=2):
    return f"{v:+.{decimals}f} %"


def _day_change(total_czk, now):
    """(rozdíl Kč, %) vs. nejbližší záznam starý aspoň 1 den, nebo (None, None)."""
    yesterday = now.date() - datetime.timedelta(days=1)
    candidates = [v for d, v in history.all_rows() if d <= yesterday]
    if not candidates or not candidates[-1]:
        return None, None
    prev = candidates[-1]
    return total_czk - prev, (total_czk / prev - 1) * 100


def _total_gain(positions):
    """Součet nerealizovaného zisku (jen pozice se živou cenou — ruční položky nemají
    kotvu na pořizovací cenu). Vrátí (součet, kolik pozic se počítalo, kolik jich je celkem)."""
    total, counted = 0.0, 0
    for p in positions:
        if p.get("mode") == "priced" and p.get("pl_czk") is not None:
            total += p["pl_czk"]
            counted += 1
    return total, counted, len(positions)


def _type_breakdown(positions):
    totals = {}
    for p in positions:
        t = p.get("type") or "Ostatní"
        totals[t] = totals.get(t, 0) + (p.get("value_czk") or 0)
    grand = sum(totals.values()) or 1
    items = sorted(totals.items(), key=lambda kv: -kv[1])
    return [(t, v, v / grand * 100) for t, v in items]


def _position_row(p):
    t = p.get("type") or "—"
    symbol = p.get("symbol") or "—"
    if p.get("mode") == "priced" and p.get("price") is not None:
        qty = f"{p['units']:g}"
        price_s = f"{p['price']:,.2f} {p.get('currency', '')}"
        value_s = _fmt_czk(p["value_czk"]) if p.get("value_czk") is not None else "—"
        day = p.get("day_change_pct")
        day_s, day_color = (_fmt_pct(day), GREEN if day >= 0 else RED) if day is not None else ("—", MUTED)
        tot = p.get("pl_pct")
        tot_s, tot_color = (_fmt_pct(tot, 1), GREEN if tot >= 0 else RED) if tot is not None else ("—", MUTED)
    elif p.get("mode") == "priced":
        qty, price_s = f"{p.get('units', 0):g}", "⚠️ cena N/A"
        value_s, day_s, tot_s = "—", "—", "—"
        day_color = tot_color = MUTED
    else:
        qty, price_s = "—", "—"
        value_s = _fmt_czk(p.get("value_czk") or 0)
        day_s, tot_s = "—", "—"
        day_color = tot_color = MUTED

    weight = p.get("alloc_pct")
    weight_s = f"{weight:.1f} %" if weight is not None else "—"
    weight_bar = min(max(weight or 0, 0), 100)

    return f"""<tr data-type="{html.escape(t)}">
  <td class="mono ticker">{html.escape(symbol)}</td>
  <td class="name">{html.escape(p.get('name', ''))}</td>
  <td class="mono muted small">{html.escape(t)}</td>
  <td class="mono right">{qty}</td>
  <td class="mono right">{price_s}</td>
  <td class="mono right bold">{value_s}</td>
  <td class="mono right"><span style="color:{day_color}">{day_s}</span></td>
  <td class="mono right"><span style="color:{tot_color}">{tot_s}</span></td>
  <td class="weight-cell"><div class="wbar"><div style="width:{weight_bar}%"></div></div><span class="mono">{weight_s}</span></td>
</tr>"""


def build(data, subject, text, now):
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / ".nojekyll").touch()

    positions = sorted(data["positions"], key=lambda p: -(p.get("value_czk") or 0))
    total_czk = data["total_czk"]

    day_diff, day_pct = _day_change(total_czk, now)
    day_html = (
        f'<span style="color:{GREEN if day_diff >= 0 else RED}">{_fmt_czk(day_diff)}&nbsp;&nbsp;{_fmt_pct(day_pct)} dnes</span>'
        if day_diff is not None else '<span class="muted">první den sledování</span>'
    )

    perf_7d = history.performance(total_czk, now, 7)
    perf_30d = history.performance(total_czk, now, 30)
    gain, gain_n, gain_total_n = _total_gain(positions)
    gain_color = GREEN if gain >= 0 else RED

    alloc = _type_breakdown(positions)
    alloc_bar = "".join(
        f'<div style="width:{pct:.2f}%;background:{TYPE_COLORS[i % len(TYPE_COLORS)]}"></div>'
        for i, (_, _, pct) in enumerate(alloc)
    )
    alloc_legend = "".join(
        f'<span><span style="color:{TYPE_COLORS[i % len(TYPE_COLORS)]}">●</span> {html.escape(t)} {pct:.1f} %</span>'
        for i, (t, _, pct) in enumerate(alloc)
    )

    types_present = list(dict.fromkeys(p.get("type") or "Ostatní" for p in positions))
    chips_html = '<button class="chip active" onclick="filterPos(this,\'Vše\')">Vše</button>' + "".join(
        f'<button class="chip" onclick="filterPos(this,\'{html.escape(t)}\')">{html.escape(t)}</button>'
        for t in types_present
    )
    rows_html = "".join(_position_row(p) for p in positions)

    hist = history.all_rows()
    hist_labels = json.dumps([d.isoformat() for d, _ in hist])
    hist_values = json.dumps([v for _, v in hist])

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
<title>Portfolio Dashboard</title>
<meta name="robots" content="noindex">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #12141a; color: #e8eaf0; font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
  .mono {{ font-family: 'IBM Plex Mono', monospace; }}
  .muted {{ color: #8b93a7; }}
  .wrap {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
  .hdr {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
  .hdr-label {{ font-size: 11px; letter-spacing: 0.14em; color: #8b93a7; }}
  .hdr-total {{ font-size: 28px; font-weight: 700; letter-spacing: -0.01em; }}
  .hdr-change {{ font-size: 13px; margin-top: 4px; }}
  .hdr-time {{ font-size: 10px; color: #565e70; text-align: right; }}
  .grid {{ display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }}
  .main {{ flex: 1; min-width: 320px; display: flex; flex-direction: column; gap: 12px; }}
  .rail {{ width: 412px; flex: none; background: #191c24; border: 1px solid #262a35; border-radius: 9px; padding: 16px; }}
  .card {{ background: #191c24; border: 1px solid #262a35; border-radius: 9px; padding: 14px; }}
  .kpis {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1.35fr; gap: 12px; }}
  .kpis .card {{ padding: 12px 14px; }}
  .kpi-label {{ font-size: 10.5px; color: #8b93a7; }}
  .kpi-val {{ font-size: 17px; font-weight: 600; margin-top: 4px; font-family: 'IBM Plex Mono', monospace; }}
  .kpi-sub {{ font-size: 11px; color: #8b93a7; margin-top: 2px; }}
  .alloc-bar {{ display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 8px 0 7px; }}
  .alloc-legend {{ display: flex; gap: 10px; flex-wrap: wrap; font-size: 10.5px; color: #8b93a7; }}
  .chart-hd {{ display: flex; gap: 8px; align-items: center; font-size: 11px; color: #8b93a7; margin-bottom: 6px; }}
  canvas {{ max-width: 100%; }}
  .pos-hd {{ display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }}
  .pos-title {{ font-size: 11px; letter-spacing: 0.12em; color: #8b93a7; margin-right: 4px; font-family: 'IBM Plex Mono', monospace; }}
  .chip {{ padding: 3px 10px; border-radius: 999px; cursor: pointer; font: 600 10.5px 'IBM Plex Sans', sans-serif; background: transparent; border: 1px solid #2a2f3c; color: #8b93a7; }}
  .chip.active {{ background: #7aa2ff; border-color: #7aa2ff; color: #10121a; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ width: 100%; min-width: 640px; border-collapse: collapse; font-size: 11.5px; }}
  th {{ text-align: left; font: 500 9.5px 'IBM Plex Mono', monospace; letter-spacing: 0.08em; color: #565e70; padding: 5px 8px; border-bottom: 1px solid #262a35; }}
  th.right {{ text-align: right; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #1e222c; vertical-align: middle; }}
  td.right {{ text-align: right; }}
  td.ticker {{ color: #7aa2ff; font-weight: 600; }}
  td.name {{ color: #8b93a7; font-size: 11px; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  td.small {{ font-size: 10px; }}
  td.bold {{ color: #e8eaf0; font-weight: 600; }}
  .weight-cell {{ display: flex; align-items: center; gap: 7px; min-width: 100px; }}
  .wbar {{ flex: 1; height: 4px; background: #232836; border-radius: 2px; }}
  .wbar div {{ height: 4px; background: #7aa2ff; border-radius: 2px; }}
  .rail-hd {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
  .rail-title {{ font-size: 13.5px; font-weight: 700; }}
  .rail-date {{ font-size: 10.5px; color: #565e70; font-family: 'IBM Plex Mono', monospace; margin-bottom: 14px; }}
  .briefing h1 {{ font-size: 14px; margin: 0 0 10px; }}
  .briefing h2 {{ font-size: 10px; letter-spacing: 0.14em; color: #8b93a7; font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; margin: 16px 0 7px; border-top: 1px solid #262a35; padding-top: 12px; }}
  .briefing h2:first-child {{ border-top: none; padding-top: 0; }}
  .briefing p, .briefing li {{ font-size: 11.5px; line-height: 1.55; color: #c6cbd8; }}
  .briefing strong {{ color: #e8eaf0; }}
  .briefing ul {{ padding-left: 18px; margin: 6px 0; }}
  footer {{ margin-top: 2.5rem; }}
  ul.terms {{ padding-left: 1.2rem; font-size: 12px; color: #c6cbd8; }}
  ul.terms time {{ color: #565e70; font-size: 10.5px; font-family: 'IBM Plex Mono', monospace; }}
  .disclaimer {{ font-size: 10.5px; color: #565e70; margin-top: 1.5rem; border-top: 1px solid #262a35; padding-top: 12px; }}
  @media (max-width: 900px) {{
    .grid {{ flex-direction: column; }}
    .rail {{ width: 100%; }}
    .kpis {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div>
    <div class="hdr-label">PORTFOLIO · CZK</div>
    <div style="display:flex;align-items:baseline;gap:14px;margin-top:4px">
      <div class="hdr-total mono">{_fmt_czk(total_czk)}</div>
      <div class="hdr-change mono">{day_html}</div>
    </div>
  </div>
  <div class="hdr-time mono">{now:%A %d. %m. %Y · %H:%M}</div>
</div>

<div class="grid">
  <div class="main">

    <div class="kpis">
      <div class="card">
        <div class="kpi-label">Nerealizovaný zisk</div>
        <div class="kpi-val" style="color:{gain_color}">{_fmt_czk(gain)}</div>
        <div class="kpi-sub">u {gain_n}/{gain_total_n} pozic se živou cenou</div>
      </div>
      <div class="card">
        <div class="kpi-label">Výkon 7 dní</div>
        <div class="kpi-val">{_fmt_pct(perf_7d) if perf_7d is not None else '—'}</div>
        <div class="kpi-sub">{'z historie hodnoty' if perf_7d is not None else 'zatím málo dat'}</div>
      </div>
      <div class="card">
        <div class="kpi-label">Výkon 30 dní</div>
        <div class="kpi-val">{_fmt_pct(perf_30d) if perf_30d is not None else '—'}</div>
        <div class="kpi-sub">{'z historie hodnoty' if perf_30d is not None else 'zatím málo dat'}</div>
      </div>
      <div class="card">
        <div class="kpi-label">Alokace</div>
        <div class="alloc-bar">{alloc_bar}</div>
        <div class="alloc-legend">{alloc_legend}</div>
      </div>
    </div>

    <div class="card">
      <div class="chart-hd"><span style="color:#7aa2ff">▪</span> Vývoj hodnoty portfolia</div>
      <canvas id="historyChart" height="80"></canvas>
    </div>

    <div class="card">
      <div class="pos-hd">
        <span class="pos-title">POZICE ({len(positions)})</span>
        {chips_html}
      </div>
      <div class="table-scroll">
      <table id="posTable">
        <thead><tr>
          <th>TICKER</th><th>NÁZEV</th><th>TŘÍDA</th><th class="right">KS</th><th class="right">CENA</th>
          <th class="right">HODNOTA</th><th class="right">DEN</th><th class="right">CELKEM</th><th>VÁHA</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      </div>
    </div>

  </div>

  <div class="rail">
    <div class="rail-hd"><div class="rail-title">Poslední briefing</div></div>
    <div class="rail-date mono">{html.escape(subject)}</div>
    <div class="briefing">{briefing_html}</div>
  </div>
</div>

<footer>
  <h2 style="font-size:13px">📚 Archiv vysvětlených pojmů</h2>
  <ul class="terms">{terms_html}</ul>
  <p class="disclaimer">⚠️ Nejsem finanční poradce; informativní shrnutí, ne investiční doporučení. Ceny orientační. „Nerealizovaný zisk" pokrývá jen pozice se živou cenou (ruční ETF a hotovost nemají v systému uloženou pořizovací cenu).</p>
</footer>

</div>
<script>
function filterPos(btn, type) {{
  document.querySelectorAll('#posTable tbody tr').forEach(function(tr) {{
    tr.style.display = (type === 'Vše' || tr.dataset.type === type) ? '' : 'none';
  }});
  document.querySelectorAll('.chip').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
}}

new Chart(document.getElementById('historyChart'), {{
  type: 'line',
  data: {{
    labels: {hist_labels},
    datasets: [{{
      label: 'Hodnota portfolia (Kč)',
      data: {hist_values},
      borderColor: '#7aa2ff',
      backgroundColor: 'rgba(122,162,255,0.09)',
      fill: true,
      tension: 0.2,
      pointRadius: 2,
    }}],
  }},
  options: {{
    scales: {{
      y: {{ beginAtZero: false, grid: {{ color: '#20242f' }}, ticks: {{ color: '#565e70', font: {{ family: 'IBM Plex Mono', size: 10 }} }} }},
      x: {{ grid: {{ color: '#20242f' }}, ticks: {{ color: '#565e70', font: {{ family: 'IBM Plex Mono', size: 10 }} }} }},
    }},
    plugins: {{ legend: {{ display: false }} }},
  }},
}});
</script>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")
