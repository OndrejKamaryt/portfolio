import os

# `os.environ.get(k, default)` vrací default JEN když proměnná chybí úplně — ale GitHub Actions
# u nenastaveného (volitelného) secretu pošle prázdný string "", ne nic, takže default by se
# nikdy nepoužil. `or` fallback funguje i pro prázdný string.

# Modely: claude-sonnet-5 (výchozí), claude-opus-4-8, claude-haiku-4-5-20251001
MODEL = os.environ.get("MODEL") or "claude-sonnet-5"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM") or "Portfolio <onboarding@resend.dev>"

TIMEZONE = "Europe/Prague"
SEND_HOUR = 8           # cílová lokální hodina, kdy má briefing odejít
# GitHub Actions "schedule" triggery umí naskočit se zpožděním v řádu hodin (běžné
# u free tieru zvlášť u méně vytížených repozitářů) — okno místo přesné hodiny,
# aby zpožděný běh briefing pořád poslal místo tichého přeskočení.
SEND_WINDOW = (6, 13)   # (od, do) lokální hodiny, kdy je běh ještě v pořádku
BASE_CURRENCY = "CZK"
