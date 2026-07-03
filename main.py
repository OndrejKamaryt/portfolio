"""Orchestrátor: načte portfolio, spočítá ceny/P/L, vygeneruje briefing, odešle e-mail."""
import json
import os
import pathlib
import re
import datetime
from zoneinfo import ZoneInfo

import config
import prices
import briefing
import emailer
import history
import glossary
import dashboard


def _load_decisions_log(path):
    """Vytáhne jen skutečné zápisy (nadpisy '## ') z decisions.md, mimo HTML komentáře
    (šablona/příklad v souboru jsou zabalené v <!-- --> a nemají se posílat jako fakt)."""
    if not path.exists():
        return ""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    # jen nadpisy se skutečným datem (RRRR-MM-DD) — vyloučí šablonu/placeholder v souboru
    entries = re.findall(r"^## \d{4}-\d{2}-\d{2}.*(?:\n(?!## ).*)*", text, flags=re.MULTILINE)
    return "\n\n".join(e.strip() for e in entries)


def main():
    now = datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    force = os.environ.get("FORCE_RUN") == "1"

    if not force:
        lo, hi = config.SEND_WINDOW
        # GitHub Actions cron je v UTC, spouští se ve dvou časech kvůli letnímu/zimnímu času,
        # a navíc umí naskočit se zpožděním v řádu hodin — okno místo přesné hodiny, aby
        # zpožděný běh briefing pořád poslal, místo aby ho tiše přeskočil.
        if not (lo <= now.hour <= hi):
            print(f"Teď je {now:%H:%M} {config.TIMEZONE}, okno je {lo}–{hi}:00 — končím "
                  f"(FORCE_RUN=1 pro okamžitý test).")
            return
        # Pojistka proti dvojímu odeslání, když oba (léto/zima) cron záznamy naskočí
        # zpožděné do stejného okna téhož dne.
        rows = history.all_rows()
        if rows and rows[-1][0] == now.date():
            print(f"Dnešní briefing ({now:%Y-%m-%d}) už proběhl, končím "
                  f"(FORCE_RUN=1 pro vynucení dalšího běhu).")
            return

    with open("holdings.json", encoding="utf-8") as f:
        holdings = json.load(f)

    decisions_log = _load_decisions_log(pathlib.Path("decisions.md"))

    data = prices.enrich(holdings)

    history.append(now.date(), data["total_czk"])
    perf_7d = history.performance(data["total_czk"], now, 7)
    perf_30d = history.performance(data["total_czk"], now, 30)
    spark = history.sparkline()

    glossary_terms = glossary.recent()
    subject, text, term = briefing.build_briefing(
        data, now, decisions_log, perf_7d, perf_30d, spark, glossary_terms
    )
    glossary.append(now.date(), term)

    out_dir = pathlib.Path("briefings")
    out_dir.mkdir(exist_ok=True)
    fpath = out_dir / f"{now:%Y-%m-%d}.md"
    fpath.write_text(f"# {subject}\n\n{text}\n", encoding="utf-8")
    print(f"Briefing uložen: {fpath}")

    ok, msg = emailer.send_email(subject, text)
    print("E-mail odeslán ✓" if ok else f"E-mail neodeslán: {msg}")

    dashboard.build(data, subject, text, now)
    print("Web (docs/index.html) aktualizován")


if __name__ == "__main__":
    main()
