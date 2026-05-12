"""
review_generation.py, Gray Horizons Enterprise
Revenue niche: Review Generation & Reputation Management, $147/month per client
Scrapes local service businesses → pitches automated review collection system.
Separate queue: review_queue.csv / review_sent_log.csv
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
CALENDLY_URL  = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE    = os.path.join(DATA_DIR, "review_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "review_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "dentist", "chiropractor", "physical therapist", "optometrist",
    "plumber", "electrician", "HVAC", "roofer", "landscaper",
    "auto repair shop", "car dealership", "restaurant", "hotel",
    "moving company", "cleaning service", "med spa", "salon",
    "pest control", "pool service", "veterinarian",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Raleigh NC", "Denver CO",
    "Columbus OH", "San Antonio TX", "Fort Worth TX", "El Paso TX", "Seattle WA",
]

SUBJECTS = [
    "Your Google reviews are costing you clients",
    "Why {niche}s with 50+ reviews win 3x more calls",
    "The automated system that gets you 10+ reviews/month",
    "You're losing to competitors with more Google reviews",
    "One system got a {niche} from 12 to 94 reviews in 90 days",
    "More Google reviews = more calls. Simple math.",
]

MESSAGES = [
    """\
Hey,

When someone Googles "{niche} near me" they almost always call whoever has the most reviews.

Most businesses with under 30 reviews are invisible to new customers. The ones with 80+ own the market.

We built a simple system that automatically texts your customers after service asking for a Google review, with a direct link so they don't have to search for you. No extra work on your end.

One client went from 14 reviews to 78 in 8 weeks. Their call volume went up 40%.

$147/month. We set it up, you get the reviews. I can show you exactly how it works this week.

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Quick honest question, when did someone last leave you a Google review?

Most {niche}s do great work but never ask for reviews. The competitor across town asks every single time. That's why they show up first.

We automate the ask. After every job, your customer gets a text:

"Thanks for choosing us! If we did a great job, it means the world if you left us a quick review: [link]"

That's it. We set it up, it runs itself. 10-20+ new reviews every month.

$147/month. No contracts. I'll show you a demo anytime this week.

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Google ranks {niche}s with more recent reviews higher in local search. It's not complicated, more reviews = more calls.

We run a fully automated review collection system: text goes out after every job, customer clicks one link, review is posted. You never touch it.

Our clients average 8-12 new reviews per month. That's 100+ new reviews in a year while you're focused on the work.

$147/month, includes setup. Want me to pull your current Google ranking and show you the gap?

{calendly}

Alex
Gray Horizons Enterprise""",
]

FOLLOWUP = """\
Hey,

Following up from earlier, wanted to share one specific result.

We worked with a {niche} who had 11 Google reviews. Got them to 67 in 3 months using the same automated text system. They told us their phone stopped going quiet on Mondays.

$147/month. I can get it running for you in 48 hours.

{calendly}

Alex | Gray Horizons"""


def scrape_leads(target_count: int = 300) -> list[dict]:
    leads = []
    seen  = set()
    ddgs  = DDGS()

    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)

    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} email -indeed -linkedin -yelp"
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
        print("[REVIEW GEN] No SENDGRID_API_KEY, scraping only")

    print("[REVIEW GEN] Scraping review-hungry businesses...")
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

    print(f"[REVIEW GEN] Sending to {len(targets)} businesses...")
    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "Local Business")).strip()
        niche   = str(row.get("niche", "business")).strip()
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

    print(f"[REVIEW GEN] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $147 = ${int(sent * 0.02) * 147}/month")


if __name__ == "__main__":
    run()
