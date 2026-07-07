"""
send_followup_outreach.py — Gray Horizons Enterprise
Sends a one-line follow-up to contractor prospects 7+ days after initial outreach.

Run daily via run_all_engines.py Phase 5b.

Logic:
  - Reads contractor_prospects.csv
  - Finds rows where status="sent" and note date is 7+ days ago
  - Sends a short follow-up email
  - Updates status to "followed_up"
"""

import os
import sys
import csv
import time
import requests
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = "grayhorizonsenterprise@gmail.com"
FROM_NAME    = "Curtis Gardner"

CSV_PATH  = os.path.join(os.path.dirname(__file__), "contractor_prospects.csv")
DEMO_LINE = "+1 (903) 627-8040"
FOLLOWUP_DAYS = 7

FOLLOWUPS = {
    "hvac": {
        "subject": "Quick follow-up — the 47-hour gap",
        "body": """Sent you a note last week about the 47-hour response gap costing HVAC businesses leads every day.

Did you get a chance to call the demo line? {demo_line}

It's a 90-second call. Just want to know what you thought.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
    "roofing": {
        "subject": "Quick follow-up — storm leads",
        "body": """Sent you a note about roofing companies missing storm leads while homeowners book with whoever responds first.

If you had a chance to call {demo_line}, I'd like to know what you thought. If not — takes 90 seconds.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
    "solar": {
        "subject": "Quick follow-up — solar inquiry response time",
        "body": """Sent you a note about the gap between when a homeowner requests solar info and when they actually hear back.

Did you call the demo line? {demo_line}

90 seconds to hear what your competition is now doing. Worth a listen.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
    "plumbing": {
        "subject": "Quick follow-up — emergency calls",
        "body": """Sent you a note about plumbing emergency calls going to whoever responds first.

Did you get a chance to call {demo_line}?

90 seconds to hear what a 24/7 automated front desk sounds like. Just want your honest reaction.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
    "dental": {
        "subject": "Quick follow-up — missed calls",
        "body": """Sent you a note about dental offices missing 22+ calls a week and the revenue walking out the door.

Did you call the demo line? {demo_line}

90 seconds. It answers like a real receptionist. Curious what you thought.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
    "other": {
        "subject": "Quick follow-up",
        "body": """Sent you a note last week about the missed-call problem in service businesses.

Did you get a chance to call the demo line? {demo_line}

90 seconds. It answers like a real receptionist.

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },
}


def _to_html(text: str) -> str:
    paragraphs = text.strip().split("\n\n")
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        lines = p.split("\n")
        parts.append("<br>".join(lines))
    body = "".join(
        f"<p style='margin:0 0 14px 0;font-family:Arial,sans-serif;font-size:15px;line-height:1.7;color:#1e293b;'>{part}</p>"
        for part in parts
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="max-width:520px;margin:32px auto;">
{body}
<p style="color:#94a3b8;font-size:12px;margin-top:32px;">To opt out, reply REMOVE.</p>
</body></html>"""


def _send(to_email: str, subject: str, body: str) -> bool:
    html = _to_html(body)
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "reply_to": {"email": FROM_EMAIL},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": body},
            {"type": "text/html",  "value": html},
        ],
    }
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    return r.status_code in (200, 202)


def _days_since(date_str: str) -> int:
    try:
        sent_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        return (date.today() - sent_date).days
    except Exception:
        return -1


def run():
    if not SENDGRID_KEY:
        print("[ERROR] SENDGRID_API_KEY not set")
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    eligible = [
        r for r in rows
        if r.get("status", "").strip().lower() == "sent"
        and _days_since(r.get("note", "")) >= FOLLOWUP_DAYS
    ]
    print(f"[FOLLOWUP] {len(eligible)} prospects due for follow-up (7+ days since initial)")

    if not eligible:
        print("[FOLLOWUP] Nothing to do today.")
        return

    sent = 0
    errors = 0

    for row in rows:
        if row.get("status", "").strip().lower() != "sent":
            continue
        if _days_since(row.get("note", "")) < FOLLOWUP_DAYS:
            continue

        email = row.get("email", "").strip()
        if not email or "@" not in email:
            row["status"] = "skipped_no_email"
            continue

        niche = row.get("niche", "other")
        template = FOLLOWUPS.get(niche, FOLLOWUPS["other"])
        body = template["body"].format(demo_line=DEMO_LINE)
        subject = template["subject"]

        ok = _send(email, subject, body)
        if ok:
            row["status"] = "followed_up"
            sent += 1
            print(f"  [{sent}] {email} ({niche})")
        else:
            row["status"] = "followup_error"
            errors += 1
            print(f"  [ERR] {email}")

        time.sleep(1.2)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[FOLLOWUP] Done — Sent: {sent} | Errors: {errors}")


if __name__ == "__main__":
    run()
