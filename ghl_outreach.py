"""
ghl_outreach.py, Gray Horizons Enterprise
Finds and emails marketing agencies + small businesses about
Gray Horizons AI CRM (GoHighLevel white-label at $297/month).
Cost: $97/month GHL. Margin: $200/client. 25 clients = $5,000/month.

Run daily. Logs to ghl_blast_log.csv.
"""

import requests
import pandas as pd
import os
import sys
import time
import re
import random
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
CALENDLY     = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE   = os.path.join(DATA_DIR, "ghl_queue.csv")
LOG_FILE     = os.path.join(DATA_DIR, "ghl_blast_log.csv")
UNSUB_FILE   = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT  = 150

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SUBJECTS = [
    "CRM that pays for itself in 30 days, {company}",
    "Your clients are leaking revenue (here's the fix)",
    "All-in-one marketing platform for {company}",
    "We run the CRM, you keep the clients",
    "Replace 6 tools with one, $297/month",
]

MESSAGES = [
    """\
Hey,

Quick question, how are you currently handling follow-up for {company}?

Most agencies and small businesses we talk to are losing 20-30% of their leads because follow-up happens manually or not at all.

We set up an AI-powered CRM that handles it automatically:
- Email + SMS follow-up sequences that run 24/7
- Pipeline tracking so nothing falls through
- Automated appointment booking
- Reputation management (review requests sent automatically)

All under your brand if you want. $297/month flat, no setup fees, no contracts.

Worth a 15-minute demo?

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

We white-label a full marketing automation platform for businesses like {company}.

What's included at $297/month:
- CRM with unlimited contacts
- Email + SMS campaigns
- AI follow-up sequences (runs 24/7)
- Landing page builder
- Reputation management
- Automated review requests
- Calendar + booking system

Most clients replace 4-6 separate tools and cut their software spend in half.

If you want to see it running live I can do a quick walkthrough this week.

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Reaching out to {company} specifically, we work with businesses in your space on marketing automation.

The short version: we set up a system that follows up with every lead automatically, books appointments, requests reviews, and tracks your pipeline, all without you touching it.

$297/month. No contracts. Cancel anytime.

The average client saves 8 hours/week and closes 30% more leads in the first 60 days.

Happy to show you exactly how it works for your business specifically.

{calendly}

Alex
Gray Horizons Enterprise""",
]

TARGET_QUERIES = [
    "marketing agency contact email",
    "digital marketing agency small business email",
    "real estate agency contact email",
    "insurance agency contact email owner",
    "local marketing consultant contact email",
    "small business owner contact email entrepreneur",
    "restaurant owner contact email",
    "gym owner fitness studio contact email",
    "med spa owner contact email",
    "auto dealership contact email owner",
]


def scrape_leads() -> list:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    leads = []
    with DDGS() as ddgs:
        for query in TARGET_QUERIES[:6]:
            try:
                for r in ddgs.text(query, max_results=12):
                    body  = r.get("body", "")
                    title = r.get("title", "")
                    url   = r.get("href", "")
                    for email in EMAIL_RE.findall(body + " " + title):
                        e = email.lower()
                        if any(bad in e for bad in ["example", "test@", "noreply", "@google", "@yelp", "sentry"]):
                            continue
                        leads.append({
                            "company": title[:50],
                            "email":   e,
                            "website": url,
                            "source":  "ddg_ghl",
                        })
                time.sleep(1.5)
            except Exception:
                time.sleep(3)
    return leads


def build_html(company: str, message: str) -> str:
    paragraphs = message.strip().split("\n\n")
    body = "".join(f"<p style='margin:0 0 14px 0;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}
<p style="color:#64748b;font-size:12px;">To unsubscribe reply with "remove" in the subject.</p>
</body></html>"""


def send(email: str, name: str, subject: str, html: str) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
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
        print("[GHL] No SENDGRID_API_KEY")
        return

    print("[GHL] Scraping agency leads...")
    new_leads = scrape_leads()
    print(f"[GHL] Found {len(new_leads)} leads")

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
        df_queue = df_new

    if not df_new.empty:
        df_queue.to_csv(QUEUE_FILE, index=False)

    sent_emails = set()
    if os.path.exists(LOG_FILE):
        sent_emails = set(pd.read_csv(LOG_FILE)["email"].str.lower())
    if os.path.exists(UNSUB_FILE):
        sent_emails |= set(pd.read_csv(UNSUB_FILE)["email"].str.lower())

    targets = df_queue[
        (df_queue["email"].str.strip() != "") &
        (~df_queue["email"].str.lower().isin(sent_emails))
    ].head(DAILY_LIMIT)

    print(f"[GHL] Sending to {len(targets)} agency prospects...")
    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "")).strip() or "your business"
        subject = random.choice(SUBJECTS).format(company=company[:25])
        message = random.choice(MESSAGES).format(company=company, calendly=CALENDLY)
        html    = build_html(company, message)
        success = send(email, company, subject, html)
        log.append({"email": email, "company": company, "sent": success})
        if success: sent += 1
        else: fail += 1
        time.sleep(0.15)

    if log:
        log_df = pd.DataFrame(log)
        if os.path.exists(LOG_FILE):
            log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)

    print(f"[GHL] Done, {sent} sent, {fail} failed")
    print(f"Expected clients at 1% conversion: ~{max(1, int(sent * 0.01))}")
    print(f"Expected revenue: ~${max(1, int(sent * 0.01)) * 200}/month profit")


if __name__ == "__main__":
    run()
