"""
targeted_outreach.py — Gray Horizons Enterprise
Demo-first targeted outreach. 50 verified prospects/day via SendGrid.
Prioritizes HOA, contractor, HVAC — highest-pain niches.
Tracks REAL sends only (not queue generation).

Usage:
  python targeted_outreach.py              # dry run
  python targeted_outreach.py --send       # live send (50/day cap)
  python targeted_outreach.py --send --limit 20
"""

import os, csv, sys, json, random, time, requests
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(encoding="utf-8")
except ImportError:
    pass

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME  = "Gray Horizons Enterprise"
CALENDLY     = "https://calendly.com/grayhorizonsenterprise/30min"
LOOM_DEMO    = os.getenv("LOOM_DEMO_URL", "")

DATA_DIR      = Path(os.path.dirname(os.path.abspath(__file__)))
PROSPECTS_CSV = DATA_DIR / "prospects_raw.csv"
SENT_LOG      = DATA_DIR / "targeted_sent_log.json"
DAILY_CAP     = 50

PRIORITY_NICHES = ["hoa", "contractor", "hvac", "plumbing", "roofing", "electrician", "dental"]

TEMPLATES = {
    "hoa": {
        "subjects": [
            "60-second demo for {company}",
            "HOA violation tracking — built this for teams like yours",
            "Quick question about your violation workflow",
        ],
        "body": """\
Hey,

I built an AI system that handles HOA violations from report to resolution automatically. Every step tracked, documented, and escalated without staff chasing it.

I recorded a 60-second walkthrough showing exactly what it looks like running for a community management team.{demo_line}

If that is relevant, I can walk you through a version built for {company} specifically. Takes 20 minutes.

{calendly}

Gray Horizons Enterprise
"""
    },
    "contractor": {
        "subjects": [
            "Your after-hours leads — quick question",
            "60-second demo for {company}",
            "Contractor intake system — built this for teams your size",
        ],
        "body": """\
Hey,

I built a system that calls back every lead that fills out your form automatically, within 60 seconds, at any hour.

Most contractors lose 30-40 percent of after-hours inquiries because nobody calls back fast enough. This closes that gap entirely.

Short demo showing the agent on a real call:{demo_line}

Happy to build a version for {company} if it looks useful. 20 minutes.

{calendly}

Gray Horizons Enterprise
"""
    },
    "hvac": {
        "subjects": [
            "HVAC after-hours calls — built a fix for this",
            "60-second demo for {company}",
            "Quick question about your missed calls",
        ],
        "body": """\
Hey,

The average HVAC company loses $45K-$120K per year to after-hours calls that go unanswered. Most owners do not realize it because there is no system tracking what is being lost.

I built an AI voice agent that handles those calls, qualifies the lead, captures job details, and logs everything before you get to the office.

Short demo showing it handle a real HVAC inquiry:{demo_line}

Happy to show you a version built for {company}. Twenty minutes.

{calendly}

Gray Horizons Enterprise
"""
    },
    "plumbing": {
        "subjects": [
            "Emergency plumbing calls after hours — built a fix",
            "60-second demo for {company}",
            "After-hours leads — quick question",
        ],
        "body": """\
Hey,

Emergency plumbing jobs go to whoever answers first. After hours that is almost never the smaller shop because the phone just rings.

I built an AI agent that picks up every call, qualifies the job, and sends you a text summary so you can decide if you want to respond.

Short demo:{demo_line}

Happy to walk you through what it looks like for {company}. Twenty minutes.

{calendly}

Gray Horizons Enterprise
"""
    },
    "roofing": {
        "subjects": [
            "Storm season lead capture — built this for roofers",
            "Post-storm call volume — quick question",
            "60-second demo for {company}",
        ],
        "body": """\
Hey,

After a storm, call volume spikes and most roofing companies lose a third of those leads to voicemail.

I built a system that handles every inbound call automatically. Captures the address, damage type, and urgency, then logs it for your team.

Short demo showing it in action:{demo_line}

Twenty minutes to walk you through a version built for {company}.

{calendly}

Gray Horizons Enterprise
"""
    },
    "electrician": {
        "subjects": [
            "Electrician after-hours calls — built a fix",
            "60-second demo for {company}",
            "Lead response time — quick question",
        ],
        "body": """\
Hey,

Emergency electrical calls that hit voicemail almost always end with the customer calling the next number on Google.

I built an AI agent that answers every call, captures the job details, and texts you a summary instantly.

Short demo:{demo_line}

Twenty minutes to show you what it looks like for {company}.

{calendly}

Gray Horizons Enterprise
"""
    },
    "dental": {
        "subjects": [
            "New patient after-hours — built a fix",
            "Patient inquiry response time — quick question",
            "60-second demo for {company}",
        ],
        "body": """\
Hey,

When a new patient submits your intake form at 8pm, what happens to that request?

If it sits until morning, research shows 78 percent of those patients have already booked elsewhere by the time anyone calls.

I built an automated system that responds instantly and captures the appointment.

Short demo:{demo_line}

Twenty minutes to show you how it works for a practice like {company}.

{calendly}

Gray Horizons Enterprise
"""
    },
    "default": {
        "subjects": [
            "Built something for {company}",
            "60-second demo — quick question",
        ],
        "body": """\
Hey,

I built an AI system that handles inbound calls and lead follow-up automatically. Works 24/7 without adding staff.

Short demo:{demo_line}

Happy to walk you through a version built for {company}. Twenty minutes.

{calendly}

Gray Horizons Enterprise
"""
    }
}


def _load_sent() -> set:
    if not SENT_LOG.exists():
        return set()
    try:
        data = json.loads(SENT_LOG.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict):
            emails = set()
            for v in data.values():
                if isinstance(v, list):
                    emails.update(v)
            return emails
    except Exception:
        return set()
    return set()


def _record_sent(email: str):
    sent = _load_sent()
    sent.add(email.lower().strip())
    SENT_LOG.write_text(json.dumps(sorted(sent), indent=2), encoding="utf-8")


def _build_email(company: str, niche: str) -> tuple:
    tmpl = TEMPLATES.get(niche, TEMPLATES["default"])
    subject = random.choice(tmpl["subjects"]).replace("{company}", company)
    demo_line = f"\n{LOOM_DEMO}" if LOOM_DEMO else "\n[Reply and I will send the demo link directly]"
    body = tmpl["body"].format(company=company, demo_line=demo_line, calendly=CALENDLY)
    return subject, body.strip()


def _send_via_sendgrid(to_email: str, subject: str, body: str) -> bool:
    if not SENDGRID_KEY:
        return False
    paragraphs = body.split("\n\n")
    html = "".join(
        f"<p style='margin:0 0 14px 0;font-family:Arial,sans-serif;color:#1e293b;line-height:1.7;'>"
        f"{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )
    html_body = (
        "<!DOCTYPE html><html><body style='max-width:520px;margin:32px auto;'>"
        + html
        + "<p style='color:#94a3b8;font-size:12px;margin-top:32px;'>To opt out, reply REMOVE.</p>"
        + "</body></html>"
    )
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": SENDER_NAME},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def load_prospects() -> list:
    if not PROSPECTS_CSV.exists():
        return []
    rows = []
    with open(PROSPECTS_CSV, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            email   = row.get("email", "").strip()
            niche   = row.get("niche", "").strip().lower()
            company = row.get("company", "").strip()
            if not email or "@" not in email:
                continue
            if niche not in PRIORITY_NICHES:
                continue
            rows.append({"email": email, "company": company or "your team", "niche": niche})
    rows.sort(key=lambda r: PRIORITY_NICHES.index(r["niche"]) if r["niche"] in PRIORITY_NICHES else 99)
    return rows


def run(do_send: bool = False, limit: int = DAILY_CAP):
    sent_emails = _load_sent()
    prospects   = load_prospects()
    eligible    = [p for p in prospects if p["email"].lower() not in sent_emails]

    print(f"\n[OUTREACH] {len(prospects)} prospects | {len(eligible)} not yet contacted")
    print(f"[OUTREACH] Mode: {'LIVE SEND' if do_send else 'DRY RUN'} | Cap: {limit}/day")
    if not LOOM_DEMO and do_send:
        print("[WARN] LOOM_DEMO_URL not set in .env. Add it after recording your Vapi demo.")
    print()

    sent_count = 0
    for p in eligible:
        if sent_count >= limit:
            break
        subject, body = _build_email(p["company"], p["niche"])
        print(f"  [{p['niche'].upper():12}] {p['email'][:45]:45} | {subject[:40]}")

        if do_send:
            ok = _send_via_sendgrid(p["email"], subject, body)
            if ok:
                _record_sent(p["email"])
                sent_count += 1
                time.sleep(1.5)
            else:
                print(f"    [FAIL] {p['email']}")
        else:
            sent_count += 1

    action = "Would send" if not do_send else "Sent"
    print(f"\n[OUTREACH] {action} {sent_count} emails.")
    if not do_send:
        print("[OUTREACH] Run with --send to execute.")


if __name__ == "__main__":
    args    = sys.argv[1:]
    do_send = "--send" in args
    limit   = DAILY_CAP
    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 < len(args):
            limit = int(args[idx + 1])
    run(do_send=do_send, limit=limit)
