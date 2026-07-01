"""Orchestrátor: načte portfolio, spočítá ceny/P/L, vygeneruje briefing, odešle e-mail."""
import json
import os
import pathlib
import datetime
from zoneinfo import ZoneInfo

import config
import prices
import briefing
import emailer


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

    data = prices.enrich(holdings)
    subject, text = briefing.build_briefing(data, now)

    out_dir = pathlib.Path("briefings")
    out_dir.mkdir(exist_ok=True)
    fpath = out_dir / f"{now:%Y-%m-%d}.md"
    fpath.write_text(f"# {subject}\n\n{text}\n", encoding="utf-8")
    print(f"Briefing uložen: {fpath}")

    ok, msg = emailer.send_email(subject, text)
    print("E-mail odeslán ✓" if ok else f"E-mail neodeslán: {msg}")


if __name__ == "__main__":
    main()
