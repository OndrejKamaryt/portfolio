"""Sestavení briefingu: čísla počítá Python, novinky a text dělá Claude přes web search."""
import datetime
import re
from zoneinfo import ZoneInfo

import anthropic
import config

WEEKDAYS_CZ = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]

FORMAT_A = """### FORMÁT — Pondělní TÝDENNÍ DEEP-DIVE (markdown)
1. **Snímek portfolia** — celková hodnota, výkon za týden/měsíc (dodaná čísla, pokud jsou k dispozici) a trend, nálada týdne.
2. **Novinky k pozicím** — rozděl na 🟢 Táhnou nahoru / 🔴 Pod tlakem / ⚪ Ostatní; ke každé 1–2 věty (novinka + dopad, použij dodané P/L). {entry_exit}
3. **Makro — polopaticky** — {macro}
4. **Krypto** — BTC, ETH.
5. **Doporučení (1–3 tituly s tezí)** — chytře podle portfolia (silně SaaS/tech, chybí AI hardware/diverzifikace). Ke každému: teze ve 2 větách + ⚔️ **Nejsilnější protiargument** (nejpřesvědčivější důvod, proč by tahle sázka mohla NEVYJÍT — ne obecné riziko jako "je to volatilní", ale konkrétní scénář/fakt, který tezi rozporuje). Klidně aktualizuj watchlist místo honění nových nápadů.
6. **Watchlist update** — kde stojí NVDA/AVGO/MU a jestli je něco blíž k akci.
7. **Co zvážit** — 2–4 postřehy (dry powder ~52k ladem, koncentrace do SaaS, konkrétní pozice k rozhodnutí).
8. **📚 Pojem k tématu** — {edu}"""

FORMAT_B = """### FORMÁT — KRÁTKÝ DENNÍ PŘEHLED (markdown, stručně)
1. **Makro — polopaticky** — {macro}
2. **Co se hýbe u tebe** — JEN pozice/watchlist s významným pohybem (~3 %+ za den), zprávou nebo výsledky. Když je klid, napiš jedním řádkem „Klidné ráno, nic zásadního." a nevymýšlej obsah. {entry_exit}
3. **Tento týden** — nadcházející earnings/události u tvých pozic, pokud jsou.
4. **📚 Pojem k tématu** — {edu}
Žádná doporučení k nákupu nových titulů (ta jsou pondělní), leda watchlist trigger."""

MACRO_INSTRUCTION = (
    'Vysvětli, JAK trh dnes vnímáš (býčí / medvědí / nejistý / rotace…) a hlavně PROČ — '
    'polopaticky, jako bys to vysvětloval kamarádovi bez ekonomického vzdělání. Ne jen "Fed je '
    'jestřábí", ale i co to prakticky znamená (např. "vyšší sazby = dražší půjčky = tlak na '
    'růstové akcie, protože jejich zisky jsou daleko v budoucnu"). Ukotvi to v konkrétních '
    'dnešních zprávách/číslech (S&P 500, sazby, výnosy, hlavní overnight pohyb, krypto) a na '
    'konec 1 větou „co to znamená pro tebe" vzhledem k jeho portfoliu (silně tech/SaaS + krypto).'
)

ENTRY_EXIT_INSTRUCTION = (
    'U pozice, kde to dnešní pohyb ceny činí relevantním (velký skok/propad, průraz úrovně, '
    'reakce na výsledky), přidej krátkou poznámku **⏳ Vstup/výstup**: je teď vhodný čas z ní '
    'vystoupit, nebo naopak dokoupit? Vždy uveď PROČ ano i PROČ ne (obě strany), ať se rozhodne '
    'sám — např. „výstup: bereš +64 %, ale prodáváš vítěze; držení: teze pořád platí, jen roste '
    'riziko koncentrace". Přidej to JEN tam, kde to má na základě pohybu ceny smysl, ne ke každé '
    'pozici. Není to pokyn k obchodu, jen podklad k rozhodnutí.'
)

EDU_INSTRUCTION = (
    'Vyber JEDEN konkrétní pojem/koncept, který se dnes v textu výše opravdu objevil (ne '
    'náhodná definice odjinud) — např. "forward P/E", "buyback", "guidance", "short interest", '
    '"dry powder", "market cap"... Vysvětli ho jednoduše, jako úplnému začátečníkovi, ve 2–4 '
    'větách, a pokud to jde, ukaž ho na konkrétním čísle/situaci z Ondřejova portfolia z dnešního '
    'textu. Nepoužívej pojem ze seznamu už vysvětlených níže — vyber jiný, i kdyby byl míň '
    'zřejmý.'
)

TERM_MARKER_RE = re.compile(r"^\s*TERM_USED:\s*(.+?)\s*$", re.MULTILINE)


def _extract_term(text):
    """Vytáhne a odstraní řádek 'TERM_USED: ...', který si model přidá na konec pro evidenci
    (glossary.py), aby se ho v e-mailu nezobrazil doslova."""
    m = TERM_MARKER_RE.search(text)
    if not m:
        return text.strip(), None
    return TERM_MARKER_RE.sub("", text).strip(), m.group(1).strip()


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


def build_briefing(data, now=None, decisions_log="", perf_7d=None, perf_30d=None, spark="",
                    glossary_terms=""):
    now = now or datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    weekday = now.weekday()  # 0 = pondělí
    is_monday = weekday == 0
    day_name = WEEKDAYS_CZ[weekday]
    fmt = (FORMAT_A if is_monday else FORMAT_B).format(
        macro=MACRO_INSTRUCTION, entry_exit=ENTRY_EXIT_INSTRUCTION, edu=EDU_INSTRUCTION
    )

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

    glossary_block = ""
    if glossary_terms.strip():
        glossary_block = f"\n\nUž vysvětlené pojmy (v sekci „Pojem k tématu“ NEOPAKUJ, vyber jiný): {glossary_terms.strip()}"

    prompt = f"""Jsi investiční asistent Ondřeje (25 let, dlouhý horizont, vysoká tolerance rizika → růstový profil). Napiš mu ranní portfolio v ČEŠTINĚ. Dnes je {day_name} {now:%d.%m.%Y}.

ČÍSLA NÍŽE JSOU SPOČÍTANÁ Z REÁLNÝCH CEN — ber je jako fakta, nepřepočítávej je ani si nevymýšlej ceny/P&L. Tvým úkolem je dohledat NOVINKY (web search) a napsat text.

Portfolio (celkem {data['total_czk']:.0f} Kč; kurz USD/CZK {data['usd_czk']}):
{positions_block}

{perf_block}

Watchlist (jen sleduj, nekupuj): {wl}{decisions_block}{glossary_block}

Přes web search dohledej k jednotlivým akciím, krypto, watchlistu a makru (S&P 500, Fed, sazby) nejnovější zprávy (posledních ~24–72 h): výsledky, výhledy, analytická doporučení, velké pohyby, nadcházející katalyzátory. NIKDY si zprávy nevymýšlej — když k něčemu nic nenajdeš, napiš to. Máš omezený počet vyhledávání — až limit dosáhneš (nebo narazíš na chybu vyhledávání), NEPIŠ, že "vyhledávání selhalo" a nezahazuj, co už jsi našel: napiš briefing z těch výsledků, které se ti podařilo získat, a jen u témat, ke kterým jsi se nedostal, řekni, že jsi to nestihl ověřit.

Tvoje ÚPLNĚ POSLEDNÍ zpráva (ta, co se pošle jako e-mail) musí začínat rovnou nadpisem/obsahem briefingu — žádné meta-komentáře k procesu jako "mám dost materiálu, píšu briefing" nebo "teď to sepíšu".

{fmt}

Na konec vždy: „⚠️ Nejsem finanční poradce; informativní shrnutí, ne investiční doporučení. Ceny orientační."

A za úplný samotný konec, na nový řádek, napiš přesně ve formátu
`TERM_USED: <pojem z bodu „Pojem k tématu“, 1–4 slova, bez uvozovek>` — tenhle řádek je jen pro
interní evidenci, systém ho z e-mailu automaticky odstraní."""

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
    text, term = _extract_term(text)
    label = "deep-dive" if is_monday else "přehled"
    subject = f"📈 Portfolio {label} — {now.day}. {now.month}. {now.year}"
    return subject, text, term
