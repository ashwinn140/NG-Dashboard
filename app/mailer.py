"""Send mail through Resend HTTPS or SMTP; credentials stay in environment variables."""
import os, smtplib, ssl, logging, json, http.client
from email.message import EmailMessage

log = logging.getLogger("mailer")
OUTBOX: list[dict] = []        # kept in memory so tests and the dev mode can read what would have been sent


def provider() -> str:
    return os.environ.get("MAIL_PROVIDER", "smtp").strip().lower()


def configured() -> bool:
    if provider() == "resend":
        return bool(os.environ.get("RESEND_API_KEY", "").strip() and os.environ.get("RESEND_FROM_EMAIL", "").strip())
    return provider() == "smtp" and bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def _send_resend(to: str, subject: str, text: str, html: str | None) -> bool:
    payload = {"from": os.environ["RESEND_FROM_EMAIL"].strip(), "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    conn = http.client.HTTPSConnection("api.resend.com", timeout=20, context=ssl.create_default_context())
    try:
        conn.request("POST", "/emails", body=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": "Bearer " + os.environ["RESEND_API_KEY"].strip(),
            "Content-Type": "application/json", "User-Agent": "PerformanceDashboard/1.0"})
        response = conn.getresponse()
        response.read(65536)
        if 200 <= response.status < 300:
            return True
        # Provider response bodies can contain email content; do not log them or credentials.
        log.error("Resend email delivery failed (HTTP %s); check the Resend dashboard for details.", response.status)
        return False
    finally:
        conn.close()


def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    OUTBOX.append(dict(to=to, subject=subject, text=text))
    del OUTBOX[:-50]
    if not configured():
        log.warning("Email provider is not configured; email to %s not sent. Subject: %s", to, subject)
        return False
    if provider() == "resend":
        try:
            return _send_resend(to, subject, text, html)
        except Exception as e:
            log.error("Resend email delivery failed (%s).", type(e).__name__)
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
