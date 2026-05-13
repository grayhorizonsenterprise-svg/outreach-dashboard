"""
signals_engine.py, Gray Horizons Enterprise
Full dedicated pipeline for Edge Engine signals subscription.
Scrapes traders/bettors → sends targeted pitch → follows up.
Completely separate from the main AI system pipeline.
Writes to signals_queue.csv, signals_sent_log.csv.
"""

import requests
import pandas as pd
import os
import sys
import time
import random
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SIGNALS_LINK     = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
INDICATORS_LINK  = os.getenv("INDICATORS_LINK", "https://horizons56.gumroad.com/l/ghe-indicators")
DRAFTKINGS_URL = os.getenv("DRAFTKINGS_AFFILIATE_URL", "")
FANDUEL_URL   = os.getenv("FANDUEL_AFFILIATE_URL", "")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "signals_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "signals_sent_log.csv")
FOLLOWUP_LOG  = os.path.join(DATA_DIR, "signals_followup_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 500

SUBJECTS = [
    "{ticker} setup fired at 8am, up 7.4% by 2pm",
    "Congress bought before it went public (we flagged it)",
    "How much should you have risked on {ticker}?",
    "Before market open: 3 setups scored 70+",
    "The volume anomaly nobody talked about yesterday",
    "Congressional trade detected, 48hr window",
    "Momentum score 82/100, did you see this setup?",
    "Kelly says risk 2.1% on this. Most risked 10%.",
    "Signal fired 8:03am. Asset up 7% by noon.",
    "What institutional volume looked like yesterday",
]

MESSAGES = [
    """\
Quick question ,

Last week the Edge Engine flagged a volume anomaly on {ticker} at 8:03am. By 2pm it was up 7.4%.

We track setups like this every morning before market open. RSI momentum + volume surge + congressional disclosure patterns, scored 0-100. You only act on the 70+ setups.

If you're active in the markets, this might be worth 5 minutes of your time:

{signals_link}

$49/month. Every morning before 8am.

Alex
Gray Horizons Enterprise""",

    """\
Something most traders don't know:

Congress members have up to 45 days to disclose their trades. During that window, unusual volume often appears on the ticker before it goes public.

We built a scanner that flags those patterns daily, and pairs it with momentum signals and Kelly criterion position sizing.

Yesterday's signal sheet: 2 stock setups, 1 crypto alert, 1 congressional flag.

$49/month to get it in your inbox every morning:

{signals_link}

Alex | Gray Horizons Enterprise""",

    """\
If you're sizing positions by gut feel, you're leaving money on the table.

Kelly Criterion with Quarter-Kelly fractional sizing, it's how institutional desks do it. We calculate exact share count based on your account size, win rate, and stop loss.

That's one of the three tools in our daily signal sheet. The others: momentum setups with 0-100 confidence scores, and congressional trade tracking.

{signals_link}

$49/month. Delivered before market open.

Alex | Gray Horizons""",
]

FOLLOWUP_1 = """\
Following up quickly ,

This week's signals included a {ticker} setup that fired Tuesday morning (confidence score 82/100) and a crypto alert that moved 11% by afternoon.

We send this every morning before 8am. If that's useful, here's the link:

{signals_link}

$49/month. Cancel anytime.

Alex"""

FOLLOWUP_2 = """\
Last one from me ,

Three things in every morning email:
1. Stock momentum setups (confidence scored, only 70+ get flagged)
2. Congressional disclosure tracking (we catch them within 48 hours)
3. Kelly-sized picks, exact position sizing, not just a direction

$49/month. Most traders say the congressional tracker alone is worth it.

{signals_link}

Alex | Gray Horizons

P.S. We also sell the TradingView indicators directly — Edge Scanner, Kelly Sizer, Congressional Tracker as Pine Script files. $49 one-time: {indicators_link}"""

SAMPLE_TICKERS = ["NVDA", "TSLA", "SPY", "META", "AAPL", "AMD", "MSFT", "AMZN"]


def build_html(message: str) -> str:
    affiliate_block = ""
    if DRAFTKINGS_URL or FANDUEL_URL:
        links = ""
        if DRAFTKINGS_URL:
            links += f'<a href="{DRAFTKINGS_URL}" style="background:#53d22c;color:#000;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:bold;margin-right:8px;">DraftKings Bonus</a>'
        if FANDUEL_URL:
            links += f'<a href="{FANDUEL_URL}" style="background:#1493ff;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:bold;">FanDuel Bonus</a>'
        affiliate_block = f'<p style="margin-top:20px;">{links}</p>'

    paragraphs = message.strip().split("\n\n")
    body = "".join(f"<p style='margin:0 0 14px 0;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}
{affiliate_block}
<p style="color:#64748b;font-size:12px;margin-top:24px;">Not financial advice. Algorithmic signals for informational purposes only. To unsubscribe reply "remove".</p>
</body></html>"""


def send(email: str, name: str, subject: str, message: str) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
        "subject": subject,
        "content": [{"type": "text/html", "value": build_html(message)}],
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


def run():
    if not SENDGRID_KEY:
        print("[SIGNALS ENGINE] No SENDGRID_API_KEY")
        return

    if not os.path.exists(QUEUE_FILE):
        print("[SIGNALS ENGINE] No signals_queue.csv, run signals_scraper.py first")
        return

    df = pd.read_csv(QUEUE_FILE).fillna("")

    sent_emails = set()
    if os.path.exists(LOG_FILE):
        sent_emails = set(pd.read_csv(LOG_FILE)["email"].str.lower())
    if os.path.exists(UNSUB_FILE):
        sent_emails |= set(pd.read_csv(UNSUB_FILE)["email"].str.lower())

    targets = df[
        (df["email"].str.strip() != "") &
        (~df["email"].str.lower().isin(sent_emails))
    ].head(DAILY_LIMIT)

    print(f"[SIGNALS ENGINE] Sending to {len(targets)} targeted traders/bettors...")

    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "")).strip()
        subject = random.choice(SUBJECTS)
        ticker  = random.choice(SAMPLE_TICKERS)
        message = random.choice(MESSAGES).format(
            signals_link=SIGNALS_LINK,
            indicators_link=INDICATORS_LINK,
            ticker=ticker,
        )

        success = send(email, company, subject, message)
        log.append({"email": email, "company": company, "sent": success, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")})

        if success: sent += 1
        else: fail += 1
        time.sleep(0.15)

    if log:
        log_df = pd.DataFrame(log)
        if os.path.exists(LOG_FILE):
            log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)

    print(f"[SIGNALS ENGINE] Done, {sent} sent, {fail} failed")
    print(f"Expected subscribers at 1%: ~{int(sent * 0.01)} × $49 = ${int(sent * 0.01) * 49}/month")


if __name__ == "__main__":
    run()
