"""Sestavení briefingu: čísla počítá Python, novinky a text dělá Claude přes web search."""
import datetime
from zoneinfo import ZoneInfo

import anthropic
import config

WEEKDAYS_CZ = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]

FORMAT_A = """### FORMÁT — Pondělní TÝDENNÍ DEEP-DIVE (markdown)
1. **Snímek portfolia** — celková hodnota, výkon za týden/měsíc (dodaná čísla, pokud jsou k dispozici) a trend, nálada týdne.
2. **Novinky k pozicím** — rozděl na 🟢 Táhnou nahoru / 🔴 Pod tlakem / ⚪ Ostatní; ke každé 1–2 věty (novinka + dopad, použij dodané P/L).
3. **Makro** — S&P 500, Fed/sazby, rizika, „co to znamená pro tebe".
4. **Krypto** — BTC, ETH.
5. **Doporučení (1–3 tituly s tezí)** — chytře podle portfolia (silně SaaS/tech, chybí AI hardware/diverzifikace). Ke každému: teze ve 2 větách + ⚔️ **Nejsilnější protiargument** (nejpřesvědčivější důvod, proč by tahle sázka mohla NEVYJÍT — ne obecné riziko jako "je to volatilní", ale konkrétní scénář/fakt, který tezi rozporuje). Klidně aktualizuj watchlist místo honění nových nápadů.
6. **Watchlist update** — kde stojí NVDA/AVGO/MU a jestli je něco blíž k akci.
7. **Co zvážit** — 2–4 postřehy (dry powder ~52k ladem, koncentrace do SaaS, konkrétní pozice k rozhodnutí).
8. **Swingový nápad** — {swing}"""

FORMAT_B = """### FORMÁT — KRÁTKÝ DENNÍ PŘEHLED (markdown, stručně)
1. **Nálada trhu** — 1–2 řádky (S&P 500, hlavní overnight pohyb, krypto).
2. **Co se hýbe u tebe** — JEN pozice/watchlist s významným pohybem (~3 %+ za den), zprávou nebo výsledky. Když je klid, napiš jedním řádkem „Klidné ráno, nic zásadního." a nevymýšlej obsah.
3. **Tento týden** — nadcházející earnings/události u tvých pozic, pokud jsou.
4. **Swingový nápad** — {swing}
Žádná jiná nová doporučení (ta jsou pondělní), leda watchlist trigger."""

SWING_INSTRUCTION = (
    'JEN pokud je opravdu přesvědčivý (konkrétní krátkodobý katalyzátor — čerstvé výsledky, '
    'technický setup, událost, silný news flow), ne evergreen investiční teze. Jinak napiš '
    'jedním řádkem „Žádný přesvědčivý swing setup" a nic nevymýšlej. Klidně mimo portfolio i '
    'watchlist. Když ho uvedeš: ticker, proč zrovna teď (1–2 věty), časový rámec (dny až pár '
    'týdnů), úroveň/scénář kdy by teze byla vyvrácená (invalidace), a ⚔️ **Nejsilnější '
    'protiargument**. Je to nápad k úvaze, ne pokyn k obchodu.'
)


def _final_text(content):
    """Vrátí jen poslední souvislý blok textu. Model si mezi tool voláními někdy
    'myslí nahlas' do viditelných textových bloků — ty před posledním tool blokem
    se zahodí, aby se do briefingu nedostalo nic jiného než finální odpověď."""
    texts = []
    for b in content:
        if getattr(b, "type", "") == "text":
            texts.append(b.text)
        else:
            texts = []
    return "".join(texts).strip()


def _format_positions(positions):
    lines = []
    for p in positions:
        if p.get("mode") == "priced":
            if p.get("price") is None:
                lines.append(f"- {p['name']} ({p.get('symbol')}): ⚠️ cenu se nepodařilo načíst")
                continue
            lines.append(
                f"- {p['name']} ({p['symbol']}): cena {p['price']} {p['currency']}, "
                f"den {p.get('day_change_pct')}%, hodnota {p.get('value_czk')} Kč, "
                f"P/L {p.get('pl_czk')} Kč ({p.get('pl_pct')}%), alokace {p.get('alloc_pct')}%"
            )
        else:
            note = f" [{p['note']}]" if p.get("note") else ""
            lines.append(
                f"- {p['name']} ({p.get('broker')}): hodnota {p.get('value_czk')} Kč, "
                f"alokace {p.get('alloc_pct')}% (ruční položka){note}"
            )
    return "\n".join(lines)


def build_briefing(data, now=None, decisions_log="", perf_7d=None, perf_30d=None, spark=""):
    now = now or datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    weekday = now.weekday()  # 0 = pondělí
    is_monday = weekday == 0
    day_name = WEEKDAYS_CZ[weekday]
    fmt = (FORMAT_A if is_monday else FORMAT_B).format(swing=SWING_INSTRUCTION)

    wl = ", ".join(
        f"{w['symbol']} ({w.get('price')}, den {w.get('day_change_pct')}%)" for w in data["watchlist"]
    )
    positions_block = _format_positions(data["positions"])

    decisions_block = ""
    if decisions_log.strip():
        decisions_block = f"""

Ondřejův rozhodovací deník (jeho vlastní minulé zápisy — NEOPAKUJ je, jen je zohledni, pokud jsou relevantní k dnešním novinkám, např. navazuj na dřívější tezi nebo uveď, že se něco změnilo):
{decisions_log.strip()}"""

    perf_bits = []
    if perf_7d is not None:
        perf_bits.append(f"za posledních 7 dní {perf_7d:+.2f} %")
    if perf_30d is not None:
        perf_bits.append(f"za posledních 30 dní {perf_30d:+.2f} %")
    if perf_bits:
        perf_block = "Výkon portfolia (spočítáno z historie, ber jako fakt): " + ", ".join(perf_bits) + "."
        if spark:
            perf_block += f" Trend hodnoty za posledních ~30 dní (nejstarší→nejnovější): {spark}"
    else:
        perf_block = "Historie výkonu zatím není k dispozici (jeden z prvních běhů nástroje) — nevymýšlej si výkon za období, drž se aktuálního snímku."

    prompt = f"""Jsi investiční asistent Ondřeje (25 let, dlouhý horizont, vysoká tolerance rizika → růstový profil). Napiš mu ranní portfolio v ČEŠTINĚ. Dnes je {day_name} {now:%d.%m.%Y}.

ČÍSLA NÍŽE JSOU SPOČÍTANÁ Z REÁLNÝCH CEN — ber je jako fakta, nepřepočítávej je ani si nevymýšlej ceny/P&L. Tvým úkolem je dohledat NOVINKY (web search) a napsat text.

Portfolio (celkem {data['total_czk']:.0f} Kč; kurz USD/CZK {data['usd_czk']}):
{positions_block}

{perf_block}

Watchlist (jen sleduj, nekupuj): {wl}{decisions_block}

Přes web search dohledej k jednotlivým akciím, krypto, watchlistu a makru (S&P 500, Fed, sazby) nejnovější zprávy (posledních ~24–72 h): výsledky, výhledy, analytická doporučení, velké pohyby, nadcházející katalyzátory. NIKDY si zprávy nevymýšlej — když k něčemu nic nenajdeš, napiš to. Máš omezený počet vyhledávání — až limit dosáhneš (nebo narazíš na chybu vyhledávání), NEPIŠ, že "vyhledávání selhalo" a nezahazuj, co už jsi našel: napiš briefing z těch výsledků, které se ti podařilo získat, a jen u témat, ke kterým jsi se nedostal, řekni, že jsi to nestihl ověřit.

{fmt}

Na konec vždy: „⚠️ Nejsem finanční poradce; informativní shrnutí, ne investiční doporučení. Ceny orientační." """

    # Pondělní deep-dive pokrývá víc témat (11 pozic + watchlist + makro + krypto) — nechává si
    # plný search budget; denní přehled cíleně hledá jen výrazné pohyby, stačí míň.
    max_uses = 8 if is_monday else 5
    max_tokens = 8000 if is_monday else 4000

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    kwargs = dict(
        model=config.MODEL, max_tokens=max_tokens,
        # Adaptivní thinking necháváme zapnutý (jen s nízkým effort) — bez něj model nemá
        # soukromý "scratchpad" pro rozhodování mezi search voláními a svoje průběžné úvahy
        # (“zkusím to po menších dávkách…”) píše rovnou do viditelného textu.
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        resp = client.messages.create(
            # Novější _20260209 varianta filtruje výsledky přes interní code_execution, který si
            # ale mezi koly neudrží stav — model si tak občas "zapomene" už stažené výsledky a
            # zbytečně narazí na limit vyhledávání. Jednodušší _20250305 (přímý search bez
            # meziskoku přes kód) je proto spolehlivější, i za cenu o něco vyšší spotřeby tokenů.
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
            **kwargs,
        )
    except Exception as e:
        print(f"web_search nedostupný ({e}) — píšu bez čerstvých novinek.")
        resp = client.messages.create(**kwargs)

    text = _final_text(resp.content)
    if not text:
        if resp.stop_reason == "max_tokens":
            print("Model doběhl na max_tokens bez finálního textu — zkouším bez web search.")
        else:
            print(f"Model nevrátil žádný text (stop_reason={resp.stop_reason}) — zkouším bez web search.")
        resp = client.messages.create(**kwargs)
        text = _final_text(resp.content)
    label = "deep-dive" if is_monday else "přehled"
    subject = f"📈 Portfolio {label} — {now.day}. {now.month}. {now.year}"
    return subject, text
