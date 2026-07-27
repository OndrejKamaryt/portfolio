"""Načtení živých cen (Yahoo Finance chart API) a výpočet hodnoty + P/L v CZK.

Dřív jsme používali knihovnu `yfinance`, ale ta se opakovaně rozbíjí, když Yahoo změní
autentizaci (crumb/cookie) — vrací pak prázdné (NaN) ceny, i když Yahoo data reálně má.
Voláme proto Yahoo chart API napřímo přes `requests`: je to stabilnější, rychlejší
(jeden dotaz na ticker) a `requests` už jako závislost máme.
"""
import math
from functools import lru_cache

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TIMEOUT = 15
# Yahoo má dva hosty — když jeden vrátí chybu, zkusíme druhý.
_HOSTS = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")


def _clean(x):
    """Vrátí kladné konečné číslo, jinak None. Yahoo občas vrátí null/NaN a `if x:`
    by NaN propustil (NaN je pravdivé) — to pak zamoří výpočty i history.csv."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


@lru_cache(maxsize=None)
def _quote(symbol):
    """Vrátí (last_price, prev_close) z Yahoo chart API, nebo (None, None) při chybě.
    Cachováno, aby se každý ticker stáhl jen jednou za běh."""
    for host in _HOSTS:
        try:
            url = f"{host}/v8/finance/chart/{symbol}?range=5d&interval=1d"
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            meta = res["meta"]
            last = _clean(meta.get("regularMarketPrice"))
            if last is None:  # fallback: poslední platná close hodnota z 5denní řady
                closes = res.get("indicators", {}).get("quote", [{}])[0].get("close") or []
                for c in reversed(closes):
                    last = _clean(c)
                    if last is not None:
                        break
            prev = _clean(meta.get("previousClose")) or _clean(meta.get("chartPreviousClose"))
            if last is not None:
                return last, prev
        except Exception:
            continue
    return None, None


def _last_price(symbol):
    return _quote(symbol)[0]


def _prev_close(symbol):
    return _quote(symbol)[1]


@lru_cache(maxsize=None)
def fx_to_czk(currency):
    """Kurz měna→CZK. Yahoo nemá všechny přímé páry (např. HKDCZK), proto křížem přes USD."""
    if currency == "CZK":
        return 1.0
    usdczk = _last_price("USDCZK=X")
    if currency == "USD":
        return usdczk
    usd_x = _last_price(f"USD{currency}=X")   # USD/měna (např. USDHKD=X, USDEUR=X)
    if usdczk and usd_x:
        return usdczk / usd_x                 # měna→CZK = (USD→CZK) / (USD→měna)
    return None


def enrich(holdings):
    """Vrátí pozice doplněné o cenu, hodnotu v CZK, P/L a alokaci + kurz a watchlist."""
    positions = []
    for raw in holdings["positions"]:
        pos = dict(raw)
        if raw.get("mode") == "priced":
            price = _last_price(raw["symbol"])
            prev = _prev_close(raw["symbol"])
            fx = fx_to_czk(raw["currency"]) or 0
            if price and fx:
                value_native = raw["units"] * price
                cost_native = raw["units"] * raw["avg_cost"]
                pos["price"] = round(price, 4)
                pos["day_change_pct"] = round((price / prev - 1) * 100, 2) if prev else None
                pos["value_czk"] = round(value_native * fx, 2)
                pos["pl_czk"] = round((value_native - cost_native) * fx, 2)
                pos["pl_pct"] = round((price / raw["avg_cost"] - 1) * 100, 2)
            else:
                pos["price"] = None  # nepodařilo se načíst cenu/kurz
        positions.append(pos)

    total = sum((p.get("value_czk") or 0) for p in positions)
    for p in positions:
        v = p.get("value_czk")
        p["alloc_pct"] = round(v / total * 100, 2) if (v and total) else None

    watchlist = []
    for sym in holdings.get("watchlist", []):
        pr, pv = _last_price(sym), _prev_close(sym)
        watchlist.append({
            "symbol": sym,
            "price": round(pr, 2) if pr else None,
            "day_change_pct": round((pr / pv - 1) * 100, 2) if (pr and pv) else None,
        })

    return {
        "positions": positions,
        "total_czk": round(total, 2),
        "usd_czk": fx_to_czk("USD"),
        "watchlist": watchlist,
    }
