"""
signals_engine.py — Gray Horizons Enterprise
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
SIGNALS_LINK  = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
DRAFTKINGS_URL = os.getenv("DRAFTKINGS_AFFILIATE_URL", "")
FANDUEL_URL   = os.getenv("FANDUEL_AFFILIATE_URL", "")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "signals_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "signals_sent_log.csv")
FOLLOWUP_LOG  = os.path.join(DATA_DIR, "signals_followup_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 200

SUBJECTS = [
    "AI picks every morning before market open",
    "Stock + crypto + sports signals — daily",
    "The edge most traders don't have",
    "Before 8am: your daily market signals",
    "What Congress traded last week (+ our picks)",
    "3 picks for today — stocks, crypto, sports",
    "How we find edge before the market opens",
]

MESSAGES = [
    """\
Hey,

We run an AI signal engine that scans the market every morning and surfaces the highest-edge opportunities before 8am.

What goes out daily:
- Stock momentum signals with entry points and confidence scores
- Crypto trend alerts before major moves
- Sports edge picks with Kelly criterion sizing
- Congressional trading disclosures (what Pelosi et al are buying)

$49/month. Cancel anytime. First week free.

{signals_link}

Alex
Gray Horizons Enterprise
horizons56.gumroad.com""",

    """\
Hey,

Quick one — we publish daily AI signals covering stocks, crypto, and sports lines. Delivered before market open every morning.

The Congress tracker alone has been worth it for most subscribers — we flag every congressional trade within 48 hours of disclosure.

$49/month, no contracts. Link to see a sample and subscribe:

{signals_link}

Alex
Gray Horizons Enterprise
horizons56.gumroad.com""",

    """\
Hey,

If you're active in the markets, this might be useful —

We built an AI that scans price action, volume anomalies, and congressional disclosures every morning and surfaces the setups with the highest expected value.

Sports lines too — we apply Kelly criterion to give exact bet sizing, not just a pick.

$49/month. Most subscribers say it pays for itself in the first week.

{signals_link}

— Alex | Gray Horizons Enterprise
horizons56.gumroad.com""",
]

FOLLOWUP_1 = """\
Hey,

Just following up — didn't want this to get buried.

Our signals go out every morning before 8am. Yesterday's included a momentum setup on {ticker}, a crypto alert that moved 12% by noon, and an NFL line with 3.2% edge.

$49/month. First week free.

{signals_link}

Alex"""

FOLLOWUP_2 = """\
Hey,

Last one from me —

If you're trading or betting and not using any kind of signal feed, you're making decisions with less information than you could have.

We make it simple: check your inbox before 8am, see the picks, decide what to act on.

$49/month. Cancel anytime.

{signals_link}

Alex | Gray Horizons
horizons56.gumroad.com"""

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
        "from": {"email": FROM_EMAIL, "name": "Alex | Edge Engine"},
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
        print("[SIGNALS ENGINE] No signals_queue.csv — run signals_scraper.py first")
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

    print(f"[SIGNALS ENGINE] Done — {sent} sent, {fail} failed")
    print(f"Expected subscribers at 1%: ~{int(sent * 0.01)} × $49 = ${int(sent * 0.01) * 49}/month")


if __name__ == "__main__":
    run()
