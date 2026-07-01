"""Odeslání briefingu e-mailem přes Resend API."""
import requests
import markdown
import config


def md_to_html(md_text):
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists", "tables"])
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:680px;'
        'line-height:1.5;color:#1a1a1a">' + body + "</div>"
    )


def send_email(subject, md_text):
    if not (config.RESEND_API_KEY and config.EMAIL_TO):
        return False, "Chybí RESEND_API_KEY nebo EMAIL_TO — přeskakuji e-mail."
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
        json={
            "from": config.EMAIL_FROM,
            "to": [config.EMAIL_TO],
            "subject": subject,
            "html": md_to_html(md_text),
        },
        timeout=30,
    )
    return resp.ok, resp.text
