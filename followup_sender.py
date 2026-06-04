"""
followup_sender.py, Gray Horizons Enterprise
Sends follow-up emails to leads that never replied to the first outreach.
Follow-up 1: 3 days after first send
Follow-up 2: 7 days after first send
Follow-up 3: 14 days after first send (final)

Run daily via sync_to_railway.py or standalone.
Usage: python followup_sender.py
"""

import pandas as pd
import requests
import os
import sys
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
CALENDLY      = os.getenv(""https://calendly.com/grayhorizonsenterprise/30min"", "https://calendly.com/grayhorizonsenterprise/30min")
STRIPE_LINK   = os.getenv("STRIPE_PAYMENT_LINK", "https://calendly.com/grayhorizonsenterprise/30min")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "outreach_queue.csv")
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
FOLLOWUP_LOG  = os.path.join(DATA_DIR, "followup_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")

DAILY_LIMIT   = 300

FOLLOWUP_1 = {
    "days": 3,
    "subjects": [
        "Re: {original_subject}",
        "Following up, {company}",
        "Quick follow-up",
    ],
    "messages": [
        """\
Hey,

Just wanted to make sure my last message didn't get buried.

We built a system that handles {niche_pain} automatically. Most of our clients see results in the first week.

Worth a 15-minute call to see if it makes sense for you?

{calendly}

Gray Horizons Enterprise""",

        """\
Hey,

Circling back on this, didn't want it to slip through the cracks.

The system we set up for similar businesses has been handling {niche_pain} on autopilot. No ongoing work on their end.

If you have 15 minutes this week I can show you exactly how it works.

{calendly}

Gray Horizons Enterprise""",
    ]
}

FOLLOWUP_2 = {
    "days": 7,
    "subjects": [
        "Still worth a look, {company}",
        "Last thing on this",
        "One more thought, {company}",
    ],
    "messages": [
        """\
Hey,

I'll keep this short, we've helped businesses just like {company} stop losing time to {niche_pain}.

The system runs itself. Setup takes one week. Cost is a flat $997, no monthly fees.

If the timing isn't right, no worries at all. But if it is, here's a link to book a quick call:

{calendly}

Gray Horizons Enterprise""",

        """\
Hey,

Two things:

1. The system we built handles {niche_pain} fully automatically, no manual work after setup.
2. We're currently offering it at $997 flat, which covers everything.

If you want to see it in action before committing, I'm happy to do a quick demo this week.

{calendly}

Gray Horizons Enterprise""",
    ]
}

FOLLOWUP_3 = {
    "days": 14,
    "subjects": [
        "Closing the loop, {company}",
        "Last one, I promise",
        "Final follow-up, {company}",
    ],
    "messages": [
        """\
Hey,

Last follow-up, I don't want to keep filling your inbox.

If {niche_pain} is something you're dealing with and want fixed, we can have a system running for you within the week. $997 flat, no monthly fees, no contracts.

If the timing isn't right, no worries. I'll stop following up either way.

{calendly}

Gray Horizons Enterprise""",

        """\
Hey,

Last message from me on this.

We solve {niche_pain} for businesses like yours with a system that runs on its own after a one-week setup.

If that's useful, here's how to get started:

{calendly}

If not, I hope things are going well regardless.

Gray Horizons Enterprise""",
    ]
}


NICHE_PAIN = {
    "hoa":          "violation tracking and follow-up",
    "contractor":   "new client follow-up and job booking",
    "landscaping":  "quote follow-up and seasonal rebooking",
    "roofing":      "estimate follow-up and close tracking",
    "dental":       "new patient follow-up and appointment no-shows",
    "chiropractic": "patient reactivation and follow-up",
    "realestate":   "lead follow-up and listing inquiries",
    "auto":         "service reminder and customer follow-up",
    "salon":        "appointment reminders and rebooking",
    "plumbing":     "quote follow-up and emergency dispatch",
    "hvac":         "maintenance reminders and service follow-up",
}


def get_pain(niche: str) -> str:
    return NICHE_PAIN.get(niche.lower().strip(), "lead follow-up and client communication")


def build_html(message: str) -> str:
    paragraphs = message.strip().split("\n\n")
    body = "".join(
        f"<p style='margin:0 0 14px 0;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}
<p style="color:#64748b;font-size:12px;">To unsubscribe reply with "remove" in the subject.</p>
</body></html>"""


def send_email(email: str, name: str, subject: str, message: str) -> bool:
    html = build_html(message)
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def load_sent_dates() -> dict:
    """Returns {email: first_sent_date} from sent_log."""
    if not os.path.exists(SENT_LOG):
        return {}
    try:
        df = pd.read_csv(SENT_LOG).fillna("")
        result = {}
        for _, row in df.iterrows():
            email = str(row.get("email", "")).strip().lower()
            ts    = str(row.get("timestamp", "")).strip()
            if email and ts and email not in result:
                result[email] = ts[:10]  # just the date
        return result
    except Exception:
        return {}


def load_followup_log() -> dict:
    """Returns {email: max_followup_number_sent}."""
    if not os.path.exists(FOLLOWUP_LOG):
        return {}
    try:
        df = pd.read_csv(FOLLOWUP_LOG).fillna("")
        result = {}
        for _, row in df.iterrows():
            email = str(row.get("email", "")).strip().lower()
            num   = int(row.get("followup_num", 0))
            if email:
                result[email] = max(result.get(email, 0), num)
        return result
    except Exception:
        return {}


def log_followup(email: str, company: str, followup_num: int, success: bool):
    entry = pd.DataFrame([{
        "email": email,
        "company": company,
        "followup_num": followup_num,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "success": success,
    }])
    if os.path.exists(FOLLOWUP_LOG):
        entry = pd.concat([pd.read_csv(FOLLOWUP_LOG), entry], ignore_index=True)
    entry.to_csv(FOLLOWUP_LOG, index=False)


def days_since(date_str: str) -> int:
    try:
        sent = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return (datetime.now() - sent).days
    except Exception:
        return 0


def run():
    if not SENDGRID_KEY:
        print("[FOLLOWUP] No SENDGRID_API_KEY")
        return

    if not os.path.exists(QUEUE_FILE):
        print("[FOLLOWUP] No outreach_queue.csv")
        return

    import random

    df        = pd.read_csv(QUEUE_FILE).fillna("")
    sent_map  = load_sent_dates()
    fu_map    = load_followup_log()

    unsubs = set()
    if os.path.exists(UNSUB_FILE):
        unsubs = set(pd.read_csv(UNSUB_FILE)["email"].str.lower().tolist())

    # Only follow up on leads that were actually sent the first email
    sent_leads = df[df["status"] == "sent"].copy()

    total_sent = 0
    log_entries = []

    for _, row in sent_leads.iterrows():
        if total_sent >= DAILY_LIMIT:
            break

        email   = str(row.get("email", "")).strip().lower()
        company = str(row.get("company", "")).strip()
        niche   = str(row.get("niche", "hoa")).strip().lower()
        subject_orig = str(row.get("subject", "")).strip()

        if not email or email in unsubs:
            continue

        first_sent = sent_map.get(email, "")
        if not first_sent:
            continue

        age         = days_since(first_sent)
        fu_sent     = fu_map.get(email, 0)
        pain        = get_pain(niche)

        # Determine which follow-up to send
        followup = None
        fu_num   = 0

        if age >= FOLLOWUP_3["days"] and fu_sent < 3:
            followup = FOLLOWUP_3
            fu_num   = 3
        elif age >= FOLLOWUP_2["days"] and fu_sent < 2:
            followup = FOLLOWUP_2
            fu_num   = 2
        elif age >= FOLLOWUP_1["days"] and fu_sent < 1:
            followup = FOLLOWUP_1
            fu_num   = 1

        if not followup:
            continue

        subject = random.choice(followup["subjects"]).format(
            company=company[:30], original_subject=subject_orig
        )
        message = random.choice(followup["messages"]).format(
            company=company,
            niche_pain=pain,
            calendly=CALENDLY,
            stripe=STRIPE_LINK,
        )

        success = send_email(email, company, subject, message)
        log_entries.append({
            "email": email, "company": company,
            "followup_num": fu_num, "date": datetime.now().strftime("%Y-%m-%d"),
            "success": success,
        })

        if success:
            total_sent += 1

        time.sleep(0.15)

    if log_entries:
        new_log = pd.DataFrame(log_entries)
        if os.path.exists(FOLLOWUP_LOG):
            new_log = pd.concat([pd.read_csv(FOLLOWUP_LOG), new_log], ignore_index=True)
        new_log.to_csv(FOLLOWUP_LOG, index=False)

    print(f"[FOLLOWUP] Done, {total_sent} follow-ups sent today")


if __name__ == "__main__":
    run()
