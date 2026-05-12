"""
missed_call_textback.py, Gray Horizons Enterprise
Revenue niche: Missed Call Text-Back Automation, $97/month per client
Scrapes local service businesses → pitches missed call automation.
Separate queue: missed_call_queue.csv / missed_call_sent_log.csv
"""

import os
import sys
import time
import random
import requests
import pandas as pd
from datetime import datetime
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
CALENDLY_URL  = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "missed_call_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "missed_call_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "plumber", "electrician", "HVAC contractor", "roofer", "auto mechanic",
    "dentist", "chiropractor", "landscaper", "pest control", "carpet cleaner",
    "towing company", "appliance repair", "locksmith", "garage door repair",
    "pool service", "pressure washing", "handyman", "tree service",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Jacksonville FL", "Denver CO",
    "Memphis TN", "Louisville KY", "Oklahoma City OK", "Tucson AZ", "Fresno CA",
]

SUBJECTS = [
    "Every missed call costs you $200+",
    "You're losing clients every time you miss a call",
    "Missed calls = missed revenue, simple fix inside",
    "Your missed calls are going straight to a competitor",
    "Fix this and win back 30% of leads you're losing",
    "How {niche} owners stop losing jobs to voicemail",
]

MESSAGES = [
    """\
Hey,

Quick question, when someone calls your business and you don't pick up, what happens?

Most small businesses lose that lead. They don't call back, they don't leave a message, and they go straight to Google and call the next one.

We built a simple system that texts any missed call back within 60 seconds automatically. Something like:

"Hey, this is [Your Business]. Missed your call, what can we help with?"

That alone recovers 20-30% of missed leads. At your price point, that's real money.

Setup takes under 24 hours. $97/month. I'll set it up for you, you just forward your number.

Want to see it running before you commit? I can show you a live demo on a 10-min call this week.

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

If you're in {niche}, you know how it goes, job site, customer, phone rings, you can't answer.

That caller is gone. They moved on to whoever picked up.

We fix that automatically. Every missed call gets a text back within 60 seconds from your number:

"Hey, sorry we missed you, we're wrapping a job. What do you need?"

One of our clients booked 4 extra jobs last week from leads he would have lost. It runs completely on its own.

$97/month. No contracts. I can get it live for you in a day.

{calendly}

Alex | Gray Horizons Enterprise""",

    """\
Hey,

Straight to the point, you're losing jobs every time you miss a call.

Most contractors lose 25-40% of inbound leads to voicemail. Those people don't leave messages anymore, they just call the next Google result.

Our system sends a text from your number within 60 seconds of any missed call. Keeps them in your pipeline while you're on the job.

$97/month, fully set up for you, no tech required. I'll send you a sample text sequence if you want to see exactly what goes out.

{calendly}

Alex
Gray Horizons""",
]

FOLLOWUP = """\
Hey,

Just following up, wanted to make sure this landed.

Missed call text-back is probably the highest-ROI thing a {niche} can do. One recovered job covers the whole year.

Happy to set it up with a 2-week trial so you can see the numbers before you decide.

{calendly}

Alex | Gray Horizons Enterprise"""


def scrape_leads(target_count: int = 300) -> list[dict]:
    """Scrape local service businesses using DuckDuckGo."""
    leads = []
    seen  = set()
    ddgs  = DDGS()

    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)

    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} email contact site"
            try:
                results = list(ddgs.text(query, max_results=6))
                for r in results:
                    url  = r.get("href", "")
                    body = r.get("body", "")
                    name = r.get("title", "")[:60]

                    if not url or url in seen:
                        continue
                    seen.add(url)

                    import re
                    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body)
                    email  = emails[0] if emails else ""
                    if not email or email.endswith((".png", ".jpg", ".gif")):
                        continue

                    leads.append({
                        "email":   email.lower(),
                        "company": name,
                        "niche":   niche,
                        "city":    city,
                        "url":     url,
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
        "from":    {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
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
        print("[MISSED CALL] No SENDGRID_API_KEY, scraping leads only")

    # Scrape fresh leads
    print("[MISSED CALL] Scraping local service businesses...")
    leads = scrape_leads(300)
    print(f"  Found {len(leads)} leads")

    if leads:
        df = pd.DataFrame(leads).drop_duplicates(subset=["email"])
        if os.path.exists(QUEUE_FILE):
            existing = pd.read_csv(QUEUE_FILE)
            df = pd.concat([existing, df]).drop_duplicates(subset=["email"]).reset_index(drop=True)
        df.to_csv(QUEUE_FILE, index=False)
        print(f"  Queue: {len(df)} total leads")

    # Send outreach
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

    print(f"[MISSED CALL] Sending to {len(targets)} businesses...")
    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "Local Business")).strip()
        niche   = str(row.get("niche", "contractor")).strip()
        subject = random.choice(SUBJECTS).format(niche=niche)
        message = random.choice(MESSAGES).format(niche=niche, calendly=CALENDLY_URL)

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

    print(f"[MISSED CALL] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $97 = ${int(sent * 0.02) * 97}/month")


if __name__ == "__main__":
    run()
