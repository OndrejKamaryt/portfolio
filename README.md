# 📈 Portfolio Briefing

Osobní automat: každé ráno v **8:00 (Praha)** spočítá tvé portfolio z živých cen,
dohledá novinky a makro a pošle ti e-mailem briefing. Běží zdarma na **GitHub Actions**
(nezávisle na tvém počítači).

- **Po–ne:** krátký přehled (jen co se reálně hýbe + nadcházející earnings).
- **Pondělí:** týdenní deep-dive (plný rozbor + doporučení + watchlist).

## Jak to funguje

```
holdings.json  → prices.py (yfinance: ceny, kurzy, P/L)
               → briefing.py (Claude API + web search: novinky + text)
               → emailer.py (Resend: e-mail)  +  briefings/RRRR-MM-DD.md
main.py to spojuje, .github/workflows/briefing.yml to spouští cronem.
```

Čísla (ceny, P/L, alokace) počítá **Python z reálných cen** — Claude jen dohledává
novinky a píše text, takže nehalucinuje čísla.

## Nastavení (jednorázově, ~15 min)

### 1. Klíče
- **Anthropic API key** — https://console.anthropic.com → API Keys (`ANTHROPIC_API_KEY`).
  Web search v API je zpoplatněný per dotaz (pár centů/běh).
- **Resend API key** — https://resend.com → API Keys (`RESEND_API_KEY`). Free tier ~3000 mailů/měs.
  Pro odesílání na vlastní e-mail stačí `from` = `onboarding@resend.dev`; pro vlastní doménu ji ověř v Resend.

### 2. Lokální test
```bash
pip install -r requirements.txt
cp .env.example .env      # a doplň klíče
export $(grep -v '^#' .env | xargs)   # načte .env do prostředí
FORCE_RUN=1 python main.py            # pošle briefing hned
```

### 3. Nasazení na GitHub Actions
1. Vytvoř nový GitHub repo a nahraj tento obsah (`git init && git add . && git commit && git push`).
2. **Settings → Secrets and variables → Actions → New repository secret** a přidej:
   `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `EMAIL_TO`, `EMAIL_FROM`, (volitelně `MODEL`).
3. Hotovo — cron běží automaticky. Ruční test: **Actions → Portfolio briefing → Run workflow**.

## Úprava portfolia

Vše je v **`holdings.json`**:
- Dokoupil/prodal jsi? Uprav `units` a `avg_cost` u dané pozice.
- `mode: "priced"` = živá cena z yfinance (potřebuje `symbol`, `units`, `avg_cost`).
- `mode: "manual"` = jen ruční hodnota v CZK (XTB ETF, hotovost). Chceš i u nich živou cenu?
  Přidej `symbol` (např. `XDWT.DE`, `EUNL.DE`, `SXR8.DE`) + `units` a přepni na `priced`.
- **Watchlist**: uprav pole `watchlist` (tickery, které jen sleduješ).

## Rozhodovací deník (`decisions.md`)

Slouží jako druhý názor, ne autopilot: pondělní deep-dive u doporučení vždy uvádí i
**⚔️ nejsilnější protiargument**, ne jen obecné riziko. Do `decisions.md` si zapisuj
vlastní rozhodnutí (co jsi udělal/neudělal a proč) — briefing ho čte jako kontext a
navazuje na tvoje předchozí teze, aniž by je opakoval doslova. Formát a příklad je
přímo v souboru.

## Historie výkonu (`history.csv`)

Každý běh přidá řádek s dnešní celkovou hodnotou portfolia. Pondělní deep-dive pak dostane
jako **fakt z kódu** (ne odhad LLM) výkon za posledních 7 a 30 dní + textový trend
(mini-graf). `history.csv` se po každém běhu commituje zpátky do repa přes GitHub Actions —
runner je jinak po běhu smazaný a historie by se ztrácela. Necommituj/nemaž ho ručně.

## Poznámky / limity
- yfinance je zdarma, ale neoficiální — občas může u nějakého tickeru vrátit prázdno; kód to ošetří a označí.
- Plný auto-sync z brokerů (eToro atd.) není — holdings udržuješ ručně v `holdings.json`.
- Časy: GitHub cron je v UTC, proto dvě spouštění (6:00 a 7:00 UTC) + pojistka v `main.py`,
  aby briefing odešel přesně v 8:00 Praha po celý rok (léto i zima).

⚠️ Není to investiční poradenství — jen informativní shrnutí veřejných dat.
