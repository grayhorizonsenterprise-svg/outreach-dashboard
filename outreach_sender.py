"""
outreach_sender.py — Gray Horizons Enterprise
Sends a single email via Brevo (primary, free 300/day), SendGrid (secondary),
or Gmail SMTP fallback.

Run directly to send today's batch:
  python outreach_sender.py           (50 emails)
  python outreach_sender.py --limit 100
"""

import os
import re
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def log_sent_date(queue_csv: str, email: str) -> None:
    """Stamp sent_date on the row after successful send so vapi_agent can time follow-up calls."""
    import csv
    from datetime import datetime
    from pathlib import Path

    path = Path(queue_csv)
    if not path.exists():
        return

    rows, fieldnames = [], []
    with open(path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "sent_date" not in fieldnames:
        fieldnames.append("sent_date")

    for row in rows:
        if row.get("email", "").strip().lower() == email.lower() and not row.get("sent_date", "").strip():
            row["sent_date"] = datetime.now().isoformat()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    import csv as _csv
    import sys as _sys
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    _limit = 50
    for i, arg in enumerate(_sys.argv[1:]):
        if arg == "--limit" and i + 1 < len(_sys.argv) - 1:
            try:
                _limit = int(_sys.argv[i + 2])
            except ValueError:
                pass

    _queue = _Path(os.path.dirname(os.path.abspath(__file__))) / "outreach_queue.csv"
    if not _queue.exists():
        print("[ERROR] outreach_queue.csv not found")
        _sys.exit(1)

    _rows = list(_csv.DictReader(open(_queue, encoding="utf-8", errors="ignore")))
    _fields = list(_rows[0].keys()) if _rows else []
    if "status" not in _fields:
        _fields.append("status")

    import re as _re
    _SKIP_RE = _re.compile(
        r'^(info|contact|noreply|no-reply|donotreply|support|admin|webmaster|postmaster'
        r'|sales|hello|mail|office|team|help|service|enquiries|enquiry|billing'
        r'|someone|you|test|xxx|guest|data|forwarding)@'
        r'|@(web|someplace|example|domain|test)\.com$'
        r'|[a-f0-9]{20,}@'
        r'|@stderr\.|@stacks\.|uce\.com$|vk-portal',
        _re.I
    )

    _pending = [r for r in _rows if r.get("status", "").strip().lower() not in ("sent", "skipped")]

    # Auto-skip garbage addresses before counting
    for _r in _pending:
        if _SKIP_RE.search(_r.get("email", "")):
            _r["status"] = "skipped"
    _pending = [r for r in _pending if r.get("status", "").strip().lower() == "pending"]

    print(f"[OUTREACH] {len(_pending)} clean pending — sending up to {_limit} now")

    _sent = 0
    _failed = 0
    for _row in _pending[:_limit]:
        _email = _row.get("email", "").strip()
        _subject = _row.get("subject", "").strip()
        _message = _row.get("message", "").strip()

        if not _email or not _subject or not _message:
            _row["status"] = "skipped"
            continue

        _result = send_email(_email, _subject, _message)
        if _result == "sent":
            _row["status"] = "sent"
            _sent += 1
            print(f"  [SENT] {_email}")
        else:
            _row["status"] = "failed"
            _failed += 1
            print(f"  [FAIL] {_email} — {_result}")

    with open(_queue, "w", newline="", encoding="utf-8") as _f:
        _w = _csv.DictWriter(_f, fieldnames=_fields)
        _w.writeheader()
        _w.writerows(_rows)

    print(f"\n[DONE] Sent: {_sent} | Failed: {_failed} | Remaining: {len(_pending) - _limit if len(_pending) > _limit else 0}")
