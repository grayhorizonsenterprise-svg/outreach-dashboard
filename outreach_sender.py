"""
outreach_sender.py — Gray Horizons Enterprise
Sends a single email via Brevo (primary, free 300/day), SendGrid (secondary),
or Gmail SMTP fallback.
"""

import os
import re
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

_URL_RE = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)')

def _linkify(text: str) -> str:
    """Wrap bare URLs in anchor tags so they render as clean clickable links."""
    def _replace(m):
        url = m.group(1)
        if "calendly.com" in url:
            label = "Schedule a call"
        else:
            label = url
        return f'<a href="{url}" style="color:#0ea5e9;text-decoration:none;">{label}</a>'
    return _URL_RE.sub(_replace, text)

BREVO_KEY     = os.getenv("BREVO_API_KEY", "")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Gray Horizons Enterprise")
SMTP_PASSWORD = os.getenv("SENDER_APP_PASSWORD", "")


def send_email(to_email: str, subject: str, body: str) -> str:
    """Returns 'sent' on success or error string on failure."""

    paragraphs = body.strip().split("\n\n")
    html = "".join(
        f"<p style='margin:0 0 14px 0'>{_linkify(p.replace(chr(10), '<br>'))}</p>"
        for p in paragraphs
    )
    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{html}
<p style="color:#94a3b8;font-size:12px;margin-top:32px;">To opt out, reply "remove".</p>
</body></html>"""

    # ── Brevo (primary, free 300/day) ───────────────────────────────────────
    if BREVO_KEY:
        payload = {
            "sender":  {"email": FROM_EMAIL, "name": SENDER_NAME},
            "to":      [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
        }
        try:
            r = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
                json=payload, timeout=15,
            )
            if r.status_code in (200, 201):
                return "sent"
        except Exception:
            pass

    # ── SendGrid (secondary) ─────────────────────────────────────────────────
    if SENDGRID_KEY:
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from":    {"email": FROM_EMAIL, "name": SENDER_NAME},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }
        try:
            r = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
                json=payload, timeout=15,
            )
            if r.status_code in (200, 202):
                return "sent"
        except Exception:
            pass  # fall through to SMTP

    # ── Gmail SMTP (fallback) ────────────────────────────────────────────────
    if SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = FROM_EMAIL
            msg["To"]      = to_email
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(FROM_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return "sent"
        except Exception as e:
            return str(e)

    return "no credentials configured"
