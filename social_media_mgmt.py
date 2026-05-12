"""
social_media_mgmt.py, Gray Horizons Enterprise
Revenue niche: Social Media Management, $297/month per client
Fully managed: 3 posts/week to Facebook + Instagram + Google.
Separate queue: social_queue.csv / social_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "social_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "social_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "restaurant", "bar", "salon", "barbershop", "nail salon",
    "gym", "yoga studio", "CrossFit gym", "martial arts school",
    "pet groomer", "dog trainer", "boutique clothing store",
    "jewelry store", "bakery", "coffee shop", "food truck",
    "med spa", "skincare clinic", "chiropractor", "dentist",
    "real estate agent", "mortgage broker", "insurance agent",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Miami FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Denver CO", "Seattle WA",
    "Portland OR", "Boston MA", "Chicago IL", "Houston TX", "San Diego CA",
]

SUBJECTS = [
    "Your competitors are posting every day, you're not",
    "3 posts/week on Instagram and Facebook, we handle all of it",
    "Why {niche}s with active social media get 30% more walk-ins",
    "Your social media hasn't been updated in a while",
    "We run your social media while you run your business",
    "Facebook + Instagram posts 3x/week, $297/month, we do everything",
]

MESSAGES = [
    """\
Hey,

Quick honest observation, most {niche}s have a Facebook and Instagram page that hasn't been updated in months.

That sends a bad signal. New customers check social before they visit. An empty page = a business that looks like it's struggling or barely open.

We manage social media for local businesses, 3 posts a week, custom graphics and captions, posted across Facebook and Instagram. You never log in.

Content we post: promotions, before/after, team highlights, reviews, service spotlights, whatever fits your business.

$297/month. No contracts. I can show you examples from a similar {niche} we're managing right now.

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

3 posts a week on Facebook and Instagram. That's the difference between businesses people discover and businesses people forget about.

We handle it completely, write the captions, design the graphics, schedule the posts, respond to comments. You just approve the first batch and we go from there.

For a {niche}, we typically post:
- 1 promotional post (current offer or service)
- 1 educational/helpful post (tips, FAQs)
- 1 social proof post (review, result, before/after)

$297/month. First month includes a full profile cleanup and bio optimization.

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Your social media is a storefront. Most people check Facebook or Instagram before they call a new {niche}.

We manage it all, 3 posts/week, custom content, engagement, for $297/month. Everything is done for you, 100%.

Results we've seen: 20-40% more profile visits, more DMs, better local search visibility.

Happy to send you examples from similar businesses we're running right now.

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
            query = f"{niche} {city} email facebook instagram contact"
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
        print("[SOCIAL] No SENDGRID_API_KEY, scraping only")
    print("[SOCIAL] Scraping local consumer-facing businesses...")
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
    print(f"[SOCIAL] Sending to {len(targets)} businesses...")
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
    print(f"[SOCIAL] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $297 = ${int(sent * 0.02) * 297}/month")

if __name__ == "__main__":
    run()
