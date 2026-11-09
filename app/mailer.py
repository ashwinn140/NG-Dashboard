"""Send mail through Resend HTTPS or SMTP; credentials stay in environment variables."""
import base64
import http.client
import json
import logging
import mimetypes
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("mailer")
OUTBOX: list[dict] = []
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def provider() -> str:
    return os.environ.get("MAIL_PROVIDER", "smtp").strip().lower()


def configured() -> bool:
    if provider() == "resend":
        return bool(os.environ.get("RESEND_API_KEY", "").strip() and os.environ.get("RESEND_FROM_EMAIL", "").strip())
    return provider() == "smtp" and bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def _normalize_attachments(attachments):
    normalized, total = [], 0
    for item in attachments or []:
        if not isinstance(item, dict):
            raise ValueError("Invalid attachment.")
        filename, content = str(item.get("filename") or ""), item.get("content")
        if (not filename or len(filename) > 180 or "/" in filename or "\\" in filename
                or any(ord(ch) < 32 for ch in filename)):
            raise ValueError("Invalid attachment filename.")
        if not isinstance(content, bytes):
            raise ValueError("Attachment content must be bytes.")
        total += len(content)
        if total > MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachments exceed the 25 MB email limit.")
        content_type = str(item.get("content_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream")
        if "/" not in content_type:
            raise ValueError("Invalid attachment content type.")
        normalized.append({"filename": filename, "content": content, "content_type": content_type})
    return normalized


def _send_resend(to: str, subject: str, text: str, html: str | None, attachments=None) -> bool:
    payload = {"from": os.environ["RESEND_FROM_EMAIL"].strip(), "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    if attachments:
        payload["attachments"] = [{"filename": a["filename"], "content": base64.b64encode(a["content"]).decode("ascii")} for a in attachments]
    conn = http.client.HTTPSConnection("api.resend.com", timeout=20, context=ssl.create_default_context())
    try:
        conn.request("POST", "/emails", body=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": "Bearer " + os.environ["RESEND_API_KEY"].strip(),
            "Content-Type": "application/json", "User-Agent": "PerformanceDashboard/1.0"})
        response = conn.getresponse()
        response.read(65536)
        if 200 <= response.status < 300:
            return True
        log.error("Resend email submission failed (HTTP %s); check the provider dashboard for details.", response.status)
        return False
    finally:
        conn.close()


def send(to: str, subject: str, text: str, html: str | None = None, attachments=None) -> bool:
    """Submit one message. True means provider accepted the submission, not inbox delivery."""
    try:
        normalized = _normalize_attachments(attachments)
    except ValueError as e:
        log.error("Email attachment rejected: %s", type(e).__name__)
        return False
    OUTBOX.append(dict(to=to, subject=subject, text=text, attachments=[{"filename": a["filename"], "size": len(a["content"])} for a in normalized]))
    del OUTBOX[:-50]
    if not configured():
        log.warning("Email provider is not configured; email to %s not submitted. Subject: %s", to, subject)
        return False
    if provider() == "resend":
        try:
            return _send_resend(to, subject, text, html, normalized)
        except Exception as e:
            log.error("Resend email submission failed (%s).", type(e).__name__)
            return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    msg["To"], msg["Subject"] = to, subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    for a in normalized:
        maintype, subtype = a["content_type"].split("/", 1)
        msg.add_attachment(a["content"], maintype=maintype, subtype=subtype, filename=a["filename"])
    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=20) as smtp:
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                smtp.send_message(msg)
        return True
    except Exception as e:
        log.error("Email submission failed (%s).", type(e).__name__)
        return False
