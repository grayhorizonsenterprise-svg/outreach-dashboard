"""
sms_marketing.py, Gray Horizons Enterprise
Revenue niche: SMS Broadcast Marketing, $147/month per client
Monthly promotional SMS to client's customer list via Twilio.
High retention, clients see direct response immediately after each blast.
Separate queue: sms_queue.csv / sms_sent_log.csv
"""

import os
import sys
import time
import random
import re
import requests
import pandas as pd
from datetime import datetime
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
"https://calendly.com/grayhorizonsenterprise/30min"  = os.getenv(""https://calendly.com/grayhorizonsenterprise/30min"", "https://calendly.com/grayhorizonsenterprise/30min")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "sms_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "sms_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "restaurant", "pizza shop", "barbershop", "salon", "nail salon",
    "car wash", "auto detailing", "gym", "yoga studio", "massage spa",
    "pet groomer", "dry cleaner", "oil change shop", "tire shop",
    "dentist", "chiropractor", "medical spa", "weight loss clinic",
    "clothing boutique", "jewelry store", "coffee shop", "bakery",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Miami FL",
    "Las Vegas NV", "Nashville TN", "Houston TX", "Denver CO", "Memphis TN",
    "San Antonio TX", "Columbus OH", "Portland OR", "Baltimore MD", "Tucson AZ",
]

SUBJECTS = [
    "SMS marketing gets 98% open rates, email gets 20%",
    "Your customers read texts. They ignore emails.",
    "Fill slow days with one text to your customer list",
    "We send 4 texts/month to your customer list, $147/month",
    "{niche}s are using SMS to fill their slowest days instantly",
    "One text to 500 customers filled up a {niche}'s entire week",
]

MESSAGES = [
    """\
Hey,

Text messages get a 98% open rate. Email gets about 20%.

If you're sending promotions, special offers, or slow-day fills by email, most of your customers never see them.

We run monthly SMS campaigns for local businesses, 4 texts per month to your existing customer list. Promotions, appointment reminders, loyalty offers, flash deals.

One {niche} sent a single "Tuesday slow day special" text to 400 customers and was fully booked by noon.

$147/month. We write every text, handle all compliance and opt-outs. You just send us your customer list once.

{calendly}

Gray Horizons Enterprise""",

    """\
Hey,

Every {niche} has slow days. The fastest fix is a text message to your existing customers.

We set up and manage your SMS list, collect numbers from new customers, send monthly promos, handle replies. Done.

4 messages per month:
- Week 1: Promo or special offer
- Week 2: Appointment reminder or tip
- Week 3: Loyalty reward or referral offer
- Week 4: Reactivation for customers who haven't been in

$147/month, includes Twilio fees for up to 500 contacts.

{calendly}

Gray Horizons Enterprise""",

    """\
Hey,

Quick question, when you have a slow Tuesday or empty appointment slots, how do you fill them?

Most {niche}s just wait. The ones beating them send a text.

We manage your entire SMS marketing, build the list, write the messages, handle opt-outs, send 4x/month.

98% open rate. Immediate responses. Works same-day.

$147/month. No contracts.

{calendly}

Gray Horizons Enterprise""",
]


def scrape_leads(target_count: int = 300) -> list[dict]:
    leads = []
    seen  = set()
    ddgs  = DDGS()
    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)
    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} email contact owner"
            try:
                results = list(ddgs.text(query, max_results=6))
                for r in results:
                    url  = r.get("href", "")
                    body = r.get("body", "")
                    name = r.get("title", "")[:60]
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body)
                    email  = emails[0] if emails else ""
                    if not email or email.endswith((".png", ".jpg")):
                        continue
                    leads.append({"email": email.lower(), "company": name,
                                  "niche": niche, "city": city, "url": url})
                    if len(leads) >= target_count:
                        break
                time.sleep(0.4)
            except Exception:
                pass
            if len(leads) >= target_count:
                break
        if len(leads) >= target_count:
            break
    return leads


def send_email(email, company, niche, subject, message) -> bool:
    paragraphs = message.strip().split("\n\n")
    body = "".join(f"<p style='margin:0 0 14px 0'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}<p style="color:#94a3b8;font-size:12px;margin-top:32px;">To opt out, reply "remove".</p>
</body></html>"""
    payload = {
        "personalizations": [{"to": [{"email": email, "name": company}]}],
        "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    try:
        r = requests.post("https://api.sendgrid.com/v3/mail/send",
                          headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=15)
        return r.status_code in (200, 202)
    except Exception:
        return False


def run():
    if not SENDGRID_KEY:
        print("[SMS] No SENDGRID_API_KEY, scraping only")
    print("[SMS] Scraping repeat-customer businesses...")
    leads = scrape_leads(300)
    print(f"  Found {len(leads)} leads")
    if leads:
        df = pd.DataFrame(leads).drop_duplicates(subset=["email"])
        if os.path.exists(QUEUE_FILE):
            df = pd.concat([pd.read_csv(QUEUE_FILE), df]).drop_duplicates(subset=["email"]).reset_index(drop=True)
        df.to_csv(QUEUE_FILE, index=False)
        print(f"  Queue: {len(df)} total")
    if not SENDGRID_KEY:
        return
    df = pd.read_csv(QUEUE_FILE).fillna("")
    sent_emails = set()
    if os.path.exists(LOG_FILE):
        sent_emails = set(pd.read_csv(LOG_FILE)["email"].str.lower())
    if os.path.exists(UNSUB_FILE):
        sent_emails |= set(pd.read_csv(UNSUB_FILE)["email"].str.lower())
    targets = df[(df["email"].str.strip() != "") & (~df["email"].str.lower().isin(sent_emails))].head(DAILY_LIMIT)
    print(f"[SMS] Sending to {len(targets)} businesses...")
    log = []
    sent = fail = 0
    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "")).strip()
        niche   = str(row.get("niche", "business")).strip()
        subject = random.choice(SUBJECTS).format(niche=niche)
        message = random.choice(MESSAGES).format(niche=niche, calendly="https://calendly.com/grayhorizonsenterprise/30min")
        ok = send_email(email, company, niche, subject, message)
        log.append({"email": email, "company": company, "niche": niche, "sent": ok,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")})
        if ok: sent += 1
        else:  fail += 1
        time.sleep(0.15)
    if log:
        log_df = pd.DataFrame(log)
        if os.path.exists(LOG_FILE):
            log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)
    print(f"[SMS] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $147 = ${int(sent * 0.02) * 147}/month")

if __name__ == "__main__":
    run()
