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

    # GitHub Actions cron je v UTC a spouští se ve dvou časech kvůli letnímu/zimnímu času;
    # tato pojistka pustí briefing jen když je v Praze cílová hodina.
    if not force and now.hour != config.SEND_HOUR:
        print(f"Teď je {now:%H:%M} {config.TIMEZONE}, cíl {config.SEND_HOUR}:00 — končím "
              f"(FORCE_RUN=1 pro okamžitý test).")
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


if __name__ == "__main__":
    main()
