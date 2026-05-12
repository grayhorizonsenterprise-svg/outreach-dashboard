"""
signals_sender.py — Gray Horizons Enterprise
Standalone Signals engine sender. Reads signals_queue.csv, sends emails via SendGrid.
Runs completely independently — no dashboard required.
Schedule: run daily via Task Scheduler or Railway cron.
"""

import os
import sys
import random
import pandas as pd
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(DATA_DIR, "signals_queue.csv")

SENDGRID_KEY   = os.getenv("SENDGRID_API_KEY", "")
SENDER_EMAIL   = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME    = os.getenv("SENDER_NAME", "Alex at GHE")
SIGNALS_LINK   = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
DAILY_LIMIT    = int(os.getenv("SIGNALS_DAILY_LIMIT", "500"))

SUBJECTS = [
    "Before market open tomorrow",
    "Something you might actually use",
    "The edge most traders don't have",
    "Quick question about your trading",
    "What's in your inbox at 7:45am?",
    "Congress just disclosed 9 trades",
    "AI scanned the market before you woke up",
    "Sports + stocks + crypto — one daily email",
]

MESSAGES = [
    """\
Hey,

Every morning before 8am our AI scans the market, flags the top setups, tracks every congressional stock disclosure, and pulls the sports lines with real edge.

It all lands in one email. $49/month.

If you want to see what it looks like: {link}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Most traders are working with the same information as everyone else.

We track congressional trades within 48 hours of disclosure, flag momentum setups before they move, and add sports/crypto edge on top.

Daily email, before market open. $49/month: {link}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Quick question — when a stock on your watchlist breaks out, do you usually catch it before or after the move?

We built a system that flags those setups daily before 8am alongside congressional disclosures and sports lines with positive expected value.

$49/month: {link}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Congress disclosed 14 trades last week. Most people didn't see them until the news covered it days later.

Our subscribers had all 14 within 48 hours — before the price moved.

Daily edge for traders: stocks, crypto, sports. $49/month: {link}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Three things hit our subscribers' inboxes this morning:

1. Two stock setups with strong momentum signals
2. One crypto alert with 48-hour window
3. Two sports lines with positive expected value

That's every morning at 7:45am for $49/month: {link}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]


def send_sendgrid(to_email, subject, body):
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
        msg = Mail(
            from_email=(SENDER_EMAIL, SENDER_NAME),
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        r = sg.client.mail.send.post(request_body=msg.get())
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {e}")
        return False


def run():
    if not SENDGRID_KEY:
        print("[SIGNALS SENDER] SENDGRID_API_KEY not set — exiting")
        return

    if not os.path.exists(QUEUE_FILE):
        print("[SIGNALS SENDER] No signals_queue.csv found — run signals_mass_scraper.py first")
        return

    df = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
    pending = df[df["status"] == "pending"]
    print(f"[SIGNALS SENDER] {len(pending)} pending leads, sending up to {DAILY_LIMIT} today")

    sent = 0
    indices = list(pending.index)
    random.shuffle(indices)

    for idx in indices[:DAILY_LIMIT]:
        row    = df.loc[idx]
        email  = str(row.get("email", "")).strip()
        if not email:
            continue

        subject = random.choice(SUBJECTS)
        body    = random.choice(MESSAGES).format(link=SIGNALS_LINK)

        ok = send_sendgrid(email, subject, body)
        if ok:
            df.at[idx, "status"] = "sent"
            sent += 1
            print(f"  [OK] {email}")
        else:
            df.at[idx, "status"] = "failed"

        if sent % 50 == 0:
            df.to_csv(QUEUE_FILE, index=False)

        time.sleep(random.uniform(0.3, 0.8))

    df.to_csv(QUEUE_FILE, index=False)
    print(f"\n[SIGNALS SENDER DONE] {sent} emails sent today")


if __name__ == "__main__":
    run()
