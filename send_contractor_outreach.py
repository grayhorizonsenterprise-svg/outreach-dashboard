"""
send_contractor_outreach.py — Gray Horizons Enterprise
Sends ROI-framed Autonomous Front Desk outreach to contractor_prospects.csv.

Pitch framework from research (12 YouTube videos analyzed):
- Lead with the OUTCOME (time, money, focus) — never the tech
- 47-hour industry stat = the opener
- Demo line as primary CTA — let the AI sell itself
- ROI math: one recovered job pays for the system 2-3x over

Usage:
  python send_contractor_outreach.py --dry-run
  python send_contractor_outreach.py
"""

import os
import sys
import csv
import time
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = "grayhorizonsenterprise@gmail.com"
FROM_NAME    = "Curtis Gardner"

CSV_PATH  = os.path.join(os.path.dirname(__file__), "contractor_prospects.csv")
DEMO_LINE = "+1 (903) 627-8040"
CALENDLY  = "https://calendly.com/grayhorizonsenterprise/30min"


MESSAGES = {
    "hvac": {
        "subject": "HVAC contractors and the 47-hour problem",
        "body": """The average HVAC company takes 47 hours to respond to a new lead.

After 5 minutes, your chance of closing that lead drops by 80%.

That means if someone's AC goes out on a Saturday afternoon and they call you, they've already booked with your competitor by Sunday morning.

I built a system that gets your response time down to 15 seconds. It answers every call, texts back every missed call, and routes every lead automatically. No staff needed. It runs 24/7.

One recovered emergency job pays for the entire system twice over.

Call this number right now to hear exactly what it sounds like when someone calls your business after hours: {demo_line}

That's a live demo. Takes 90 seconds. It will answer like a real receptionist.

If you want to know how to get yours set up, here is a link to book 20 minutes with me: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "plumbing": {
        "subject": "Plumbing calls and the 47-hour response gap",
        "body": """Emergency plumbing calls are the fastest deal in home services.

The customer calls 2-3 companies. Books whoever responds first. Every time.

The average plumbing company takes 47 hours to follow up on a new inquiry. By then the job is gone.

I built a system that responds to every missed call in under 15 seconds — day or night, weekend or holiday. No extra staff. Fully automated.

One recovered emergency job pays for the system. Most clients see 2-3 in the first month.

Call this number right now to hear what your new front desk sounds like: {demo_line}

Takes 90 seconds. It will answer like a real receptionist for your business.

To schedule 20 minutes to see how it works for you: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "roofing": {
        "subject": "Roofing leads and the window you're missing",
        "body": """After a storm, homeowners call 3 roofing companies. They book the first one that responds.

The average roofing contractor takes 47 hours to follow up on an inbound lead.

Storm jobs run $8,000 to $25,000. Two recovered jobs per month is $16,000 to $50,000 your system is currently walking away from.

I built an automated front desk that responds to every lead in under 15 seconds, 24/7. It handles the first call, texts back missed calls, and keeps every lead warm until you can close.

Call this number right now and hear exactly what callers will experience: {demo_line}

That's a working demo. 90 seconds. It answers like a real receptionist.

To see how we'd set this up for your business in 5 days: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "solar": {
        "subject": "Solar leads and the 47-hour follow-up gap",
        "body": """A homeowner reaches out about solar. They've already reached out to 3 companies.

The first one to respond with a real voice — not a form, not a voicemail — wins the appointment almost every time.

The average solar company takes 47 hours to respond to a new inquiry. The homeowner has already booked a site visit with your competitor.

I built a system that answers every inbound solar inquiry in under 15 seconds, qualifies them by bill size, and routes them straight to your calendar. No staff. Runs 24/7.

One additional close per month on solar pays for this system 5-10x over.

Call this number right now to hear it in action: {demo_line}

Real demo, 90 seconds. It will greet you like a real receptionist.

To talk through building this for your team: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "dental": {
        "subject": "Dental offices and the missed call problem",
        "body": """The average dental office misses 22 calls a week.

Most go to voicemail. Nobody calls back until the next morning. By then the patient has already booked with the office down the street.

New patient average value: $1,400. At a 30% conversion rate, 22 missed calls a week is $9,240 walking out the door every seven days.

I built a system that answers every inbound call in under 15 seconds, qualifies the patient, and books them directly to your calendar. No front desk staff needed for after-hours calls. It runs 24/7.

Call this number right now to hear exactly what it sounds like: {demo_line}

Takes 90 seconds. It answers like a real receptionist.

One recovered new patient per week pays for the system. Most offices see 3 to 5 in the first month.

To see how we'd set this up for your practice: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "landscaping": {
        "subject": "Landscaping bookings and the follow-up gap",
        "body": """Landscaping is a repeat business. But most landscapers lose 20-30% of recurring clients each off-season — not because of the work, but because nobody reached out.

And for new jobs? The first company to respond wins. Most landscaping companies average 47 hours on inbound responses.

I built a system that responds to every inquiry in under 15 seconds and automatically reaches back out to lapsed clients before the season starts. No manual calls. No staff. It runs by itself.

Call this number right now to hear what a 24/7 automated front desk sounds like: {demo_line}

Takes 90 seconds. It will answer like a real receptionist.

To see how this gets set up for your business: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "construction": {
        "subject": "Construction bids and the follow-up problem",
        "body": """You send out estimates. Some close. Most go silent.

Not because the price was wrong. Because the follow-up was slow or inconsistent.

The average contractor loses 40-50% of potential jobs purely in the gap between estimate and close. Most follow up once, maybe twice, then stop.

I built a system that follows up automatically on every estimate — day 3, day 5, day 8 — until they respond. No staff. No manual tracking. Just closed jobs.

Call this number right now to hear what a 24/7 automated front desk sounds like: {demo_line}

Real demo. 90 seconds.

To talk through how this would work for your jobs: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "property_management": {
        "subject": "Quick question about your response process",
        "body": """When a tenant or homeowner reports an issue, how long does it typically take to acknowledge and route it?

The gap between a report coming in and someone actually owning it is where most property management headaches start.

I built a system that acknowledges every incoming request immediately, routes it to the right person automatically, and tracks it through to resolution. Nothing falls through the cracks.

Call this number right now to hear a live demo of what automated intake sounds like: {demo_line}

Takes 90 seconds. It answers like a real receptionist.

To see how this would work for your team: {calendly}

Curtis Gardner
Gray Horizons Enterprise
grayhorizonsenterprise.com

To opt out, reply REMOVE.""",
    },

    "other": {
        "subject": "The 47-hour response gap costing service businesses",
        "body": """The average service business takes 47 hours to respond to a new inbound lead.

After 5 minutes, the probability of closing that lead drops by 80%.

I built a system that responds in 15 seconds — 24 hours a day, 7 days a week — without adding staff. It handles the first call, texts back missed calls, and keeps every inquiry warm.

One recovered job in month one pays for the system.

Call this number right now to hear a live demo: {demo_line}

Takes 90 seconds. It answers like a real receptionist.

To schedule 20 minutes to talk about your business: {calendly}

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


def run(dry_run: bool = False):
    if not SENDGRID_KEY and not dry_run:
        print("[ERROR] SENDGRID_API_KEY not set")
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    pending = [r for r in rows if r.get("status", "").strip().lower() == "pending"]
    print(f"[CONTRACTOR OUTREACH] {len(pending)} pending of {len(rows)} total")

    if dry_run:
        print("\n[DRY RUN] First 3 per niche that would be sent:\n")
        shown = {}
        for row in pending:
            niche = row.get("niche", "other")
            if shown.get(niche, 0) >= 1:
                continue
            template = MESSAGES.get(niche, MESSAGES["other"])
            body = template["body"].format(demo_line=DEMO_LINE, calendly=CALENDLY)
            print(f"  TO: {row['email']} | NICHE: {niche}")
            print(f"  SUBJECT: {template['subject']}")
            print(f"  BODY: {body[:300]}...")
            print()
            shown[niche] = shown.get(niche, 0) + 1
        print("[DRY RUN] Remove --dry-run to send.")
        return

    sent = 0
    errors = 0

    for row in rows:
        if row.get("status", "").strip().lower() != "pending":
            continue

        niche = row.get("niche", "other")
        email = row.get("email", "").strip()
        if not email or "@" not in email:
            row["status"] = "skipped_no_email"
            continue

        template = MESSAGES.get(niche, MESSAGES["other"])
        body = template["body"].format(demo_line=DEMO_LINE, calendly=CALENDLY)
        subject = template["subject"]

        ok = _send(email, subject, body)
        if ok:
            row["status"] = "sent"
            sent += 1
            print(f"  [{sent}] {email} ({niche})")
        else:
            row["status"] = "error"
            errors += 1
            print(f"  [ERR] {email}")

        time.sleep(1.2)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[CONTRACTOR OUTREACH] Done — Sent: {sent} | Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
