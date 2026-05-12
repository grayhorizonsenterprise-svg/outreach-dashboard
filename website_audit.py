"""
website_audit.py, Gray Horizons Enterprise
Revenue niche: Website SEO & Speed Audit + Fix, $297 one-time + $97/month
Targets businesses with slow or poorly-ranking websites.
Separate queue: website_queue.csv / website_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "website_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "website_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "attorney", "dentist", "chiropractor", "accountant", "financial advisor",
    "insurance agent", "real estate agent", "mortgage broker", "HVAC company",
    "roofer", "plumber", "electrician", "landscaping company", "pest control",
    "med spa", "fitness studio", "private school", "tutoring center",
    "veterinarian", "optometrist", "dermatologist", "plastic surgeon",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Denver CO", "Raleigh NC",
    "Columbus OH", "San Antonio TX", "Louisville KY", "Oklahoma City OK", "Tucson AZ",
]

SUBJECTS = [
    "I ran your website through Google's speed test, here's what I found",
    "Your website is probably losing you 40% of mobile visitors",
    "Quick audit: 3 things your website is doing wrong right now",
    "Google ranks slow websites lower, yours might be affected",
    "{niche}s with fast websites get 3x more form submissions",
    "Your website has an issue that's costing you Google ranking",
]

MESSAGES = [
    """\
Hey,

I ran your website through Google's PageSpeed Insights and there are a few technical issues that are likely hurting your search ranking.

The three most common problems we find:
1. Load time over 4 seconds on mobile (Google drops your ranking for this)
2. Missing or incorrect meta titles and descriptions
3. No schema markup (Google can't understand what your business does)

These aren't design problems, they're technical fixes that take a few hours and directly affect how high you show up when someone searches for a {niche} in your area.

We do a full audit ($297 one-time) and fix everything we find. Then $97/month to keep it maintained and monitor rankings.

If you want, I can pull your actual PageSpeed score right now and send it to you, takes 30 seconds.

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

One thing that consistently hurts local {niche} websites: load speed on mobile.

Google confirmed in 2021 that page speed is a ranking factor. If your site takes more than 3 seconds to load on a phone, Google shows you lower in search results, even if everything else is right.

We run a full technical audit: speed, mobile responsiveness, local SEO signals, meta data, schema markup. Then we fix everything in the same week.

$297 audit + fix. $97/month ongoing monitoring. Most clients see a ranking improvement within 30-60 days.

I can pull your site's score without any login or access on your end, want me to send it over?

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Quick question about your website, when someone searches for a {niche} in your area, do you know where you rank?

Most business owners don't. And most are ranking lower than they should because of fixable technical issues, slow load times, missing local signals, no schema, outdated meta.

We audit the full site and fix what's broken. $297 one-time, includes the fixes. Then $97/month to maintain rankings and catch new issues.

I can show you exactly where you're ranking for your top 5 search terms in a 10-minute call.

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
            query = f"{niche} {city} website email contact -yelp -yellowpages"
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
        print("[WEBSITE] No SENDGRID_API_KEY, scraping only")
    print("[WEBSITE] Scraping businesses with likely outdated websites...")
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
    print(f"[WEBSITE] Sending to {len(targets)} businesses...")
    log = []
    sent = fail = 0
    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        company = str(row.get("company", "")).strip()
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
    print(f"[WEBSITE] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $297 = ${int(sent * 0.02) * 297} one-time")

if __name__ == "__main__":
    run()
