"""
tradingview_engine.py, Gray Horizons Enterprise
Finds and emails active traders about GHE TradingView indicators.
Targets: active traders, TradingView users, trading communities.
Writes to tradingview_queue.csv.
Indicators sell at $19-$39/month invite-only on TradingView.
"""

import requests
import pandas as pd
import os
import sys
import re
import time
import random
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE   = os.path.join(DATA_DIR, "tradingview_queue.csv")
LOG_FILE     = os.path.join(DATA_DIR, "tradingview_sent_log.csv")
UNSUB_FILE   = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT  = 150

EMAIL_RE  = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
JUNK      = ["noreply", "test@", "example", "support@", "admin@", "info@tradingview"]

DDG_QUERIES = [
    "stock trader blog contact email",
    "options trading blog contact email newsletter",
    "TradingView indicator review contact email",
    "technical analysis blog contact email",
    "swing trading blog contact email",
    "forex trader blog contact email",
    "crypto trading blog contact email",
    "day trader YouTube contact email",
    "stock market educator contact email",
    "trading coach contact email site:.com",
]

SUBJECTS = [
    "3 TradingView indicators built for edge",
    "The Congress tracker indicator, TradingView",
    "Kelly Criterion position sizer for TradingView",
    "New indicators: Edge Scanner + Congress Tracker",
    "Custom TradingView indicators, $29/month",
]

MESSAGES = [
    """\
Hey,

I build custom TradingView indicators and wanted to reach out specifically.

We just published 3 invite-only indicators:

1. GHE Edge Scanner ($29/month), momentum + volume surge + trend confluence. Labels high-confidence setups automatically.

2. GHE Kelly Position Sizer ($19/month), calculates exact position size and dollar risk for every trade based on your account size and win rate.

3. GHE Congressional Trade Tracker ($39/month), flags unusual volume patterns correlated with congressional disclosure windows. No other indicator does this.

All three have free 7-day trials. Happy to add you if you want to test them on your charts.

Gray Horizons Enterprise
grayhorizonsenterprise.com""",

    """\
Hey,

Quick one, we built a TradingView indicator that tracks congressional trading patterns.

It flags unusual volume anomalies that historically correlate with congressional disclosure windows. Politicians have to disclose trades within 45 days, this indicator helps you spot the pattern before the disclosure.

$39/month, invite-only. 7-day free trial.

We also have a momentum edge scanner ($29/mo) and Kelly criterion position sizer ($19/mo) if those are useful.

Worth a look?

Gray Horizons Enterprise""",

    """\
Hey,

We publish invite-only TradingView indicators for active traders.

The most popular one is our Kelly Criterion Position Sizer, you input your account size, win rate, and stop loss %, and it calculates exact position size and expected value for every trade in real time.

$19/month. Saves the math on every single trade.

Also have an Edge Scanner ($29/mo) and Congressional Trade Tracker ($39/mo) if either of those fit your style.

Happy to add you for a free trial week.

Gray Horizons Enterprise""",
]


def scrape_leads() -> list:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    leads = []
    with DDGS() as ddgs:
        for query in DDG_QUERIES:
            try:
                for r in ddgs.text(query, max_results=12):
                    body  = r.get("body", "")
                    title = r.get("title", "")
                    url   = r.get("href", "")
                    for email in EMAIL_RE.findall(body + " " + title):
                        e = email.lower()
                        if any(j in e for j in JUNK):
                            continue
                        if e.split("@")[-1] in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]:
                            continue  # skip personal emails, target business emails
                        leads.append({
                            "email":   e,
                            "company": title[:50],
                            "website": url,
                            "source":  "ddg_tradingview",
                        })
                time.sleep(1.5)
            except Exception:
                time.sleep(3)
    return leads


def build_html(message: str) -> str:
    paragraphs = message.strip().split("\n\n")
    body = "".join(f"<p style='margin:0 0 14px 0;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}
<p style="color:#64748b;font-size:12px;">To unsubscribe reply "remove".</p>
</body></html>"""


def send(email: str, name: str, subject: str, message: str) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
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
        print("[TV ENGINE] No SENDGRID_API_KEY")
        return

    print("[TV ENGINE] Scraping trader leads...")
    new_leads = scrape_leads()
    print(f"[TV ENGINE] Found {len(new_leads)} leads")

    df_new = pd.DataFrame(new_leads).fillna("") if new_leads else pd.DataFrame()

    if os.path.exists(QUEUE_FILE):
        df_existing = pd.read_csv(QUEUE_FILE).fillna("")
        if not df_new.empty:
            done = set(df_existing["email"].str.lower())
            df_new = df_new[~df_new["email"].str.lower().isin(done)]
            df_queue = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_queue = df_existing
    else:
        df_queue = df_new if not df_new.empty else pd.DataFrame()

    if not df_new.empty:
        df_queue.to_csv(QUEUE_FILE, index=False)

    if df_queue.empty:
        print("[TV ENGINE] No leads to send to yet")
        return

    sent_emails = set()
    if os.path.exists(LOG_FILE):
        sent_emails = set(pd.read_csv(LOG_FILE)["email"].str.lower())
    if os.path.exists(UNSUB_FILE):
        sent_emails |= set(pd.read_csv(UNSUB_FILE)["email"].str.lower())

    targets = df_queue[
        (df_queue["email"].str.strip() != "") &
        (~df_queue["email"].str.lower().isin(sent_emails))
    ].head(DAILY_LIMIT)

    print(f"[TV ENGINE] Sending to {len(targets)} traders...")

    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "")).strip()
        subject = random.choice(SUBJECTS)
        message = random.choice(MESSAGES)
        success = send(email, company, subject, message)
        log.append({"email": email, "company": company, "sent": success, "timestamp": datetime.now().strftime("%Y-%m-%d")})
        if success: sent += 1
        else: fail += 1
        time.sleep(0.15)

    if log:
        log_df = pd.DataFrame(log)
        if os.path.exists(LOG_FILE):
            log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)

    print(f"[TV ENGINE] Done, {sent} sent, {fail} failed")
    print(f"Expected subscribers at 2%: ~{int(sent * 0.02)} × avg $29 = ${int(sent * 0.02) * 29}/month")


if __name__ == "__main__":
    run()
