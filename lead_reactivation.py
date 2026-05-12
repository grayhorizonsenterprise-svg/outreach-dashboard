"""
lead_reactivation.py, Gray Horizons Enterprise
Revenue niche: Lead Reactivation Campaign, $497 one-time
Client uploads their dead lead list → we blast a win-back sequence.
High perceived value, zero recurring cost. Easiest close.
Separate queue: reactivation_queue.csv / reactivation_sent_log.csv
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
QUEUE_FILE    = os.path.join(DATA_DIR, "reactivation_queue.csv")
LOG_FILE      = os.path.join(DATA_DIR, "reactivation_sent_log.csv")
UNSUB_FILE    = os.path.join(DATA_DIR, "unsubscribe_list.csv")
DAILY_LIMIT   = 150

TARGET_NICHES = [
    "dentist", "chiropractor", "real estate agent", "insurance agent",
    "HVAC contractor", "roofing company", "landscaping company", "gym",
    "auto dealership", "mortgage broker", "financial advisor",
    "home remodeling", "solar company", "pest control", "moving company",
    "med spa", "weight loss clinic", "car repair shop",
]

CITIES = [
    "Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Tampa FL",
    "Las Vegas NV", "Nashville TN", "Austin TX", "Denver CO", "Columbus OH",
    "San Antonio TX", "Jacksonville FL", "Fort Worth TX", "Memphis TN", "El Paso TX",
]

SUBJECTS = [
    "Your old leads are worth $10k+, most businesses never touch them",
    "Dead leads in your CRM = money you never collected",
    "We turned 200 dead leads into 11 closed deals for a {niche}",
    "You already paid for these leads, let us work them one more time",
    "The fastest $10k in your business is sitting in your dead lead list",
    "We reactivate your old leads. You close the ones who respond.",
]

MESSAGES = [
    """\
Hey,

You've collected leads for years. Quotes requested, forms filled, calls that went nowhere.

Most businesses never go back to those leads. But 5-15% of dead leads will convert if you follow up with the right message at the right time.

We run a single reactivation campaign against your entire dead list:
- A 3-message email + SMS sequence written specifically for your business
- Sent over 10 days with optimal timing
- Every response lands directly in your inbox

One client ran this against 600 old {niche} leads and booked 11 appointments in two weeks.

$497 flat. We write everything, load it, send it. You just handle the responses.

Ready to run it this week?

{calendly}

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Most {niche}s are sitting on a goldmine they've already paid for, their old lead list.

People who requested a quote 8 months ago and went dark. Past clients who haven't come back. Referrals that never converted.

We run a win-back campaign against your full list. 3 emails over 10 days, written to sound personal and relevant, not a mass blast.

One campaign, $497. Most clients recover 5-10 clients from a list of 300+. At your margins, that's anywhere from $3,000 to $30,000 in recovered revenue.

If you want, send me your list size and I'll tell you what kind of response rate to expect.

{calendly}

Alex | Gray Horizons""",

    """\
Hey,

Quick question, do you have a list of leads or past customers who went cold?

Most {niche}s do. And most never touch it again, which means they paid to acquire those leads and got nothing.

We run a targeted reactivation campaign, 3 messages, 10 days, written specifically for your business and your customer type.

It takes us 48 hours to set up. $497 flat. You handle replies, we handle everything else.

{calendly}

Alex
Gray Horizons Enterprise""",
]


def scrape_leads(target_count: int = 250) -> list[dict]:
    leads = []
    seen  = set()
    ddgs  = DDGS()
    random.shuffle(TARGET_NICHES)
    random.shuffle(CITIES)
    for niche in TARGET_NICHES[:8]:
        for city in CITIES[:4]:
            query = f"{niche} {city} email owner contact"
            try:
                results = list(ddgs.text(query, max_results=5))
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
        print("[REACTIVATION] No SENDGRID_API_KEY, scraping only")
    print("[REACTIVATION] Scraping businesses with large customer histories...")
    leads = scrape_leads(250)
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
    print(f"[REACTIVATION] Sending to {len(targets)} businesses...")
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
    print(f"[REACTIVATION] Done, {sent} sent, {fail} failed")
    print(f"  At 2% close: ~{int(sent * 0.02)} clients × $497 = ${int(sent * 0.02) * 497} one-time")

if __name__ == "__main__":
    run()
