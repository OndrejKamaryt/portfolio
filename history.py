"""Historie celkové hodnoty portfolia (CSV) — výkon za týden/měsíc a trend pro deep-dive.

history.csv se commituje zpátky do repa (viz .github/workflows/briefing.yml), jinak by
na GitHub Actions po každém běhu zmizel spolu s ephemeral runnerem.
"""
import csv
import datetime
import math
import pathlib

PATH = pathlib.Path("history.csv")
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def append(date, total_czk):
    # Nezapisuj NaN/inf — jinak by se do CSV dostal řádek "…,nan", který pak shodí
    # graf i sparkline (viz _rows/sparkline). Prázdná/nevalidní hodnota = běh se
    # jen nepřidá do historie, ale briefing se odešle normálně.
    if total_czk is None or not math.isfinite(total_czk):
        print(f"history: přeskakuji zápis, celková hodnota není číslo ({total_czk!r}).")
        return
    is_new = not PATH.exists()
    with PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["date", "total_czk"])
        w.writerow([date.isoformat(), round(total_czk, 2)])


def _rows():
    if not PATH.exists():
        return []
    out = []
    with PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                val = float(row["total_czk"])
            except (KeyError, ValueError):
                continue
            if not math.isfinite(val):   # přeskoč případný starší "nan" řádek
                continue
            try:
                out.append((datetime.date.fromisoformat(row["date"]), val))
            except (KeyError, ValueError):
                continue
    return sorted(out)


def all_rows():
    """Všechny záznamy (date, total_czk), od nejstaršího — pro graf na webu."""
    return _rows()


def performance(current_total, now, days):
    """% změna current_total vůči nejbližšímu záznamu starému aspoň `days` dní, nebo None."""
    target = now.date() - datetime.timedelta(days=days)
    candidates = [v for d, v in _rows() if d <= target]
    if not candidates or not candidates[-1]:
        return None
    return round((current_total / candidates[-1] - 1) * 100, 2)


def sparkline(days=30):
    """Textový mini-graf hodnoty portfolia za posledních `days` dní (nejstarší → nejnovější)."""
    values = [v for _, v in _rows()[-days:]]
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK_CHARS[0] * len(values)
    return "".join(SPARK_CHARS[int((v - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))] for v in values)
