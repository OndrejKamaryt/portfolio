"""Načtení živých cen (yfinance) a výpočet hodnoty + P/L v CZK."""
import math
from functools import lru_cache
import yfinance as yf


def _clean(x):
    """Vrátí kladné konečné číslo, jinak None. yfinance občas vrátí NaN místo None
    a `if x:` NaN propustí (NaN je pravdivé) — to pak zamoří výpočty i history.csv."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def _last_price(symbol):
    t = yf.Ticker(symbol)
    try:
        p = _clean(t.fast_info.get("last_price"))
        if p is not None:
            return p
    except Exception:
        pass
    try:
        h = t.history(period="5d")
        if not h.empty:
            return _clean(h["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _prev_close(symbol):
    try:
        h = yf.Ticker(symbol).history(period="5d")
        if len(h) >= 2:
            return _clean(h["Close"].iloc[-2])
    except Exception:
        pass
    return None


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
