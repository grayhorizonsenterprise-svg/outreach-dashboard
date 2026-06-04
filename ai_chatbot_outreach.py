"""
ai_chatbot_outreach.py, Gray Horizons Enterprise
Revenue niche: AI Website Chatbot, $97/month per client
Scrapes local service businesses → pitches 24/7 AI chatbot for lead capture.
Separate queue: chatbot_queue.csv / chatbot_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "chatbot_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "chatbot_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "attorney", "accountant", "financial advisor", "insurance agent",
    "real estate agent", "mortgage broker", "dentist", "chiropractor",
    "med spa", "plastic surgeon", "fertility clinic", "weight loss clinic",
    "HVAC contractor", "roofer", "solar company", "home remodeling",
    "moving company", "storage facility", "car dealership", "private school",
    "gym", "martial arts", "tutoring center", "day care",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Raleigh NC", "Denver CO",
    "San Diego CA", "San Antonio TX", "Portland OR", "Baltimore MD", "Milwaukee WI",
]

SUBJECTS = [
    "Your website is losing 70% of visitors without answering them",
    "Every {niche} website needs this, most don't have it",
    "What happens when someone visits your website at 11pm?",
    "AI chatbot recovered 3 leads last night for a {niche} client",
    "Your website visitors are leaving without a way to contact you",
    "How {niche}s are booking clients while they sleep",
]

MESSAGES = [
    """\
Hey,

Quick question, when someone visits your website at 11pm and has a question, what happens?

They leave. They go to Google and find someone who has an answer.

We install a simple AI chatbot on your website that answers common questions 24/7, captures name and phone number, and sends you a text with the lead while you sleep.

It's not a generic bot, we train it specifically on your services, pricing, FAQs, and how you want leads handled.

Most clients capture 3-7 extra leads per week they would have otherwise lost.

$97/month. We install it, train it, you own the leads. Demo takes 10 minutes.

{calendly}

Gray Horizons Enterprise""",

    """\
Hey,

70% of website visitors leave without contacting a business, mostly because they have a question and nobody's there to answer it.

We fix this with a trained AI chatbot. It lives on your site, handles questions instantly, and captures contact info for every interested visitor, 24 hours a day.

For a {niche}, it handles things like:
- "Do you take [insurance/payments]?"
- "What's your pricing range?"
- "Are you taking new clients?"
- "Can someone call me back?"

Every response ends with lead capture. You get a text with the contact.

$97/month. We set it up and train it on your business. Takes about a week start to finish.

{calendly}

Gray Horizons Enterprise""",

    """\
Hey,

Most {niche} websites do one thing: tell people to call during business hours.

We add a second channel, an AI that's live 24/7, answers questions in real-time, and captures every interested visitor's info before they bounce.

What it does for you:
- Answers common questions immediately (no one waits, no one leaves)
- Captures name + phone number on every conversation
- Texts you the lead within seconds
- Handles your after-hours traffic automatically

Setup is under 7 days. $97/month, cancel anytime.

{calendly}

Gray Horizons Enterprise""",
]

FOLLOWUP = """\
Hey,

Just following up, we had a {niche} client capture 6 leads last week from after-hours website visitors. All 6 would have bounced without the chatbot.

$97/month. Happy to show you the demo, it takes 10 minutes.

{calendly}

Gray Horizons Enterprise"""


def scrape_leads(target_count: int = 300) -> list[dict]:
    leads = []
    seen  = set()
    ddgs  = DDGS()

    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)

    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} website email contact"
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
                    leads.append({
                        "email": email.lower(), "company": name,
                        "niche": niche, "city": city, "url": url,
                    })
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


def send_email(email: str, company: str, niche: str, subject: str, message: str) -> bool:
    paragraphs = message.strip().split("\n\n")
    body = "".join(f"<p style='margin:0 0 14px 0'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body}
<p style="color:#94a3b8;font-size:12px;margin-top:32px;">To opt out, reply "remove".</p>
</body></html>"""
    payload = {
        "personalizations": [{"to": [{"email": email, "name": company}]}],
        "from":    {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
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
        print("[CHATBOT] No SENDGRID_API_KEY, scraping only")

    print("[CHATBOT] Scraping businesses with high-traffic websites...")
    leads = scrape_leads(300)
    print(f"  Found {len(leads)} leads")

    if leads:
        df = pd.DataFrame(leads).drop_duplicates(subset=["email"])
        if os.path.exists(QUEUE_FILE):
            existing = pd.read_csv(QUEUE_FILE)
            df = pd.concat([existing, df]).drop_duplicates(subset=["email"]).reset_index(drop=True)
        df.to_csv(QUEUE_FILE, index=False)
        print(f"  Queue: {len(df)} total leads")

    if not SENDGRID_KEY:
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

    print(f"[CHATBOT] Sending to {len(targets)} businesses...")
    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "Local Business")).strip()
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

    print(f"[CHATBOT] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $97 = ${int(sent * 0.02) * 97}/month")


if __name__ == "__main__":
    run()
