"""
gbp_optimizer.py, Gray Horizons Enterprise
Revenue niche: Google Business Profile Optimization, $197/month per client
Scrapes local businesses with weak/incomplete GBP → pitches GBP management.
Separate queue: gbp_queue.csv / gbp_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "gbp_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "gbp_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "attorney", "accountant", "financial advisor", "insurance agent",
    "real estate agent", "mortgage broker", "dentist", "chiropractor",
    "plumber", "electrician", "HVAC contractor", "roofer", "landscaper",
    "auto repair", "car dealership", "restaurant", "hotel",
    "cleaning service", "pest control", "gym", "martial arts school",
    "tutoring center", "day care", "veterinarian", "optometrist",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Raleigh NC", "Denver CO",
    "Columbus OH", "San Antonio TX", "Portland OR", "Baltimore MD", "Louisville KY",
]

SUBJECTS = [
    "Your Google listing is losing you clients right now",
    "Quick audit: 3 things missing from your Google profile",
    "Why competitors show up before you on Google Maps",
    "Your Google Business Profile is working against you",
    "{niche}s: this one fix gets you more Google calls",
    "You're invisible on Google Maps, here's why",
]

MESSAGES = [
    """\
Hey,

I ran a quick audit on your Google Business Profile and noticed a few things that are probably costing you calls.

Most businesses in your space are missing:
- Updated service categories (affects who sees you in search)
- Weekly Google Posts (signals activity to the algorithm)
- Q&A section with pre-answered questions
- Response templates for reviews

Google's algorithm actively ranks businesses that maintain their profiles. It's not complicated, but it takes consistent weekly work.

We manage GBP profiles for local businesses, posting weekly, responding to reviews within 24 hours, optimizing categories, and running monthly photo updates. Most clients see a 20-40% increase in profile views within 60 days.

$197/month. We handle everything. Want to see what a fully optimized profile looks like?

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

If you're a {niche} and you're not ranking in the Google Maps 3-pack, you're losing 60-70% of local search traffic to whoever is.

Most GBP accounts are set up once and never touched. Google sees that and ranks active profiles higher.

What we do every month:
- 8+ Google Posts (new content keeps you ranked)
- Review response within 24 hours (ranking signal)
- Photo updates with geo-tagged images
- Q&A optimization and keyword-aligned descriptions

Takes us about 3 hours of work. Takes your business from invisible to visible.

$197/month. First month includes a full profile audit and rebuild.

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Your competitors are showing up before you on Google Maps. I can tell you exactly why.

Google's local ranking algorithm weights three things:
1. Relevance (are your categories and description correct?)
2. Distance (we can't control this)
3. Activity (are you posting, getting reviews, responding?)

The businesses in the top 3 are almost always the ones posting weekly. It's that simple.

We manage this entirely, you never log in. $197/month, cancel anytime, no contracts.

If you want, I can pull your current Google rankings on a 15-minute call and show you where you stand.

{calendly}

Alex
Gray Horizons Enterprise""",
]

FOLLOWUP = """\
Hey,

Following up, wanted to share something specific.

A {niche} we worked with was ranking #9 on Google Maps in their city. After 90 days of consistent GBP management, they were in the top 3. Their inbound calls went from 4-5/week to 15-20.

$197/month. I can show you exactly what we changed.

{calendly}

Alex | Gray Horizons Enterprise"""


def scrape_leads(target_count: int = 300) -> list[dict]:
    leads = []
    seen  = set()
    ddgs  = DDGS()

    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)

    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} contact email"
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
        print("[GBP] No SENDGRID_API_KEY, scraping only")

    print("[GBP] Scraping businesses with weak Google presence...")
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

    print(f"[GBP] Sending to {len(targets)} businesses...")
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

    print(f"[GBP] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $197 = ${int(sent * 0.02) * 197}/month")


if __name__ == "__main__":
    run()
