import os

# Modely: claude-sonnet-5 (výchozí), claude-opus-4-8, claude-haiku-4-5-20251001
MODEL = os.environ.get("MODEL", "claude-sonnet-5")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "Portfolio <onboarding@resend.dev>")

TIMEZONE = "Europe/Prague"
SEND_HOUR = 8          # lokální hodina, kdy má briefing odejít
BASE_CURRENCY = "CZK"
