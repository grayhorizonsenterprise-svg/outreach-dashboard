"""
ai_voice_receptionist.py, Gray Horizons Enterprise
Revenue niche: AI Voice Receptionist, $197/month per client
24/7 AI phone answering via Bland AI. Books appointments, handles FAQs, takes messages.
Separate queue: voice_queue.csv / voice_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "voice_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "voice_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "dentist", "chiropractor", "optometrist", "physical therapist",
    "med spa", "plastic surgeon", "HVAC contractor", "plumber", "electrician",
    "roofer", "attorney", "accountant", "real estate agent", "insurance agent",
    "mortgage broker", "veterinarian", "private school", "tutoring center",
    "car dealership", "moving company", "pest control", "appliance repair",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Denver CO", "Raleigh NC",
    "San Antonio TX", "Columbus OH", "Portland OR", "Louisville KY", "Memphis TN",
]

SUBJECTS = [
    "Your phones go unanswered after hours, here's the fix",
    "AI answers your phones 24/7, {niche}s are switching fast",
    "Missed calls = missed revenue. We fixed that for 3 {niche}s this month.",
    "Your front desk can't answer every call. This can.",
    "What happens when someone calls your {niche} at 8pm?",
    "24/7 AI receptionist, books appointments while you sleep",
]

MESSAGES = [
    """\
Hey,

When your phones go unanswered, after hours, during a busy appointment, at lunch, that caller moves on. They don't leave a voicemail. They call the next result on Google.

We set up an AI voice receptionist that answers every call, 24 hours a day. It sounds natural, handles your common questions, and books appointments directly to your calendar.

What it handles:
- "Are you accepting new patients?" → Yes, let me get you scheduled
- "What are your hours?" → Full accurate answer
- "I need to book an appointment" → Booked, confirmation sent
- After-hours calls → Handled, message sent to you

$197/month. We set it up in 48 hours. You keep your existing phone number.

Want to hear a 60-second demo call?

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Most {niche}s lose 20-30% of inbound calls to voicemail or just ringing. Those people don't call back, they call someone else.

We install an AI receptionist that picks up every call. Sounds like a real person. Books the appointment. Sends you a summary.

Setup takes 2 days. $197/month. No contracts.

I can send you a demo recording of exactly how it sounds for a {niche}, takes 30 seconds to listen to.

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Quick one, do your phones get answered every time they ring? After 5pm? On Saturdays?

Most don't. And that's fine, until you realize each unanswered call is a lost appointment.

We solved this with AI. It answers, talks naturally, books appointments, handles common questions. Runs 24/7 without a salary.

$197/month all-in. We handle the full setup.

{calendly}

Alex
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
            query = f"{niche} {city} phone appointment contact email"
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
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
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
        print("[VOICE] No SENDGRID_API_KEY, scraping only")
    print("[VOICE] Scraping appointment-heavy businesses...")
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
    print(f"[VOICE] Sending to {len(targets)} businesses...")
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
    print(f"[VOICE] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $197 = ${int(sent * 0.02) * 197}/month")

if __name__ == "__main__":
    run()
