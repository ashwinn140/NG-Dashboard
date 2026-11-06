"""Sends email through any SMTP account (Gmail with an app password to start). Without SMTP settings nothing is sent and the text is logged instead."""
import os, smtplib, ssl, logging
from email.message import EmailMessage

log = logging.getLogger("mailer")
OUTBOX: list[dict] = []        # kept in memory so tests and the dev mode can read what would have been sent


def configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    OUTBOX.append(dict(to=to, subject=subject, text=text))
    del OUTBOX[:-50]
    if not configured():
        log.warning("SMTP is not configured; email to %s not sent. Subject: %s", to, subject)
        return False
    msg = EmailMessage(); msg["From"] = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]; msg["To"] = to; msg["Subject"] = subject
    msg.set_content(text)
    if html: msg.add_alternative(html, subtype="html")
    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
        else:
            with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context()); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
        return True
    except Exception as e:             # a mail problem must never break the app
        log.error("Email to %s failed: %s", to, e)
        return False
