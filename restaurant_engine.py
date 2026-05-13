"""
restaurant_engine.py — Gray Horizons Enterprise
Standalone restaurant / food service outreach engine.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from email_registry import load_global_registry, register_sent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "restaurant_queue.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Alex")
CALENDLY      = "https://calendly.com/grayhorizonsenterprise/30min"
DAILY_LIMIT   = int(os.getenv("DAILY_LIMIT_NICHE", "500"))
REFILL_BELOW  = 200

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_PREFIXES = {
    'abuse','spam','report','complaints','privacy','legal','billing',
    'webmaster','postmaster','mailer','sales','marketing','hr',
    'careers','jobs','news','newsletter','press','media','helpdesk',
    'support','ticket','noreply','no-reply','donotreply',
}
SKIP_DOMAINS = {
    "reddit.com","twitter.com","facebook.com","instagram.com","linkedin.com",
    "youtube.com","google.com","yelp.com","wikipedia.org","opentable.com",
    "doordash.com","grubhub.com","ubereats.com","toasttab.com","yelp.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = [
    "independent restaurant owner email contact",
    "restaurant owner blog email contact",
    "restaurant group owner email contact",
    "chef owner restaurant email contact",
    "fine dining restaurant owner email",
    "casual dining restaurant owner email",
    "fast casual restaurant owner email contact",
    "food truck owner email contact",
    "catering company owner email contact",
    "catering business owner email contact",
    "private chef email contact",
    "ghost kitchen owner email contact",
    "virtual restaurant owner email contact",
    "restaurant franchise owner email contact",
    "pizzeria owner email contact",
    "sushi restaurant owner email contact",
    "BBQ restaurant owner email contact",
    "steakhouse owner email contact",
    "seafood restaurant owner email contact",
    "Mexican restaurant owner email contact",
    "Italian restaurant owner email contact",
    "Asian fusion restaurant owner email contact",
    "vegan restaurant owner email contact",
    "brunch restaurant owner email contact",
    "bar and grill owner email contact",
    "sports bar owner email contact",
    "pub owner email contact",
    "wine bar owner email contact",
    "coffee shop owner email contact",
    "bakery owner email contact",
    "deli owner email contact",
    "restaurant consultant email contact",
    "food business coach email contact",
    "restaurant marketing consultant email",
    "food service entrepreneur email contact",
    "restaurant investor email contact",
    "hospitality group director email contact",
    "restaurant manager blog email contact",
    "food entrepreneur blog email contact",
    "restaurant owner Texas email contact",
    "restaurant owner Florida email contact",
    "restaurant owner California email contact",
    "restaurant owner New York email contact",
    "restaurant owner Chicago email contact",
    "restaurant owner Atlanta email contact",
    "catering company Florida email contact",
    "restaurant owner Las Vegas email contact",
    "food truck owner email contact blog",
    "restaurant owner podcast email contact",
    "restaurant owner YouTube email contact",
]

SUBJECTS = [
    "Filling your slow nights without discounting",
    "How restaurants build a catering pipeline automatically",
    "Your no-show rate - what does it cost you monthly?",
    "Quick question about your email list",
    "One system that fills empty tables on slow nights",
]

MESSAGES = [
    """\
Hey,

Quick question - what do you do to fill the restaurant on a slow Tuesday night?

Most owners either discount (kills margin) or just accept it. There's a third option.

We build automated "table-fill" campaigns for independent restaurants - targeted messages to your past customers with a reason to come in on your slowest days. No app, no coupon, just a personal message that lands in their inbox at the right time.

One restaurant we work with went from 40% capacity on Tuesdays to 70% in 6 weeks.

Happy to show you how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Catering is usually the highest-margin revenue in any restaurant. Most restaurants get it through word of mouth and leave it at that.

We set up an automated catering outreach system: scrapes local corporate offices, event planners, and wedding venues - sends personalized pitches - books consultations directly to your calendar.

No cold calling. No extra staff. Just a system running in the background.

If that sounds interesting: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

If you're using OpenTable or any reservation system, you have a gold mine sitting in your guest database that almost no restaurant touches.

We set up automated guest re-engagement campaigns: anniversary reminders, birthday outreach, "we miss you" messages to guests who haven't been in 60+ days, and post-visit review requests.

Most restaurants see 15-25% increase in repeat visits within the first month.

Worth a quick call: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

No-shows cost restaurants an average of $100-150 per table per incident. At 5 no-shows a week, that's $26K+ a year walking out the door.

We set up automated confirmation and reminder sequences that cut no-show rates by 60-70% - personalized messages at 48 hours, 24 hours, and 2 hours before the reservation.

Simple to set up. Pays for itself in the first week.

Quick call to see how it works for your setup: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The restaurants doing the best right now have one thing the others don't: a direct line to their customers that doesn't depend on Yelp, DoorDash, or Instagram.

We help restaurants build that asset - an owned email list of loyal customers - and set up the automated campaigns to use it: weekly specials, event announcements, VIP nights, birthday offers.

Your list, your customers, zero platform fees.

If you want to see what it looks like: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]


def is_clean(email):
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith(('.png', '.jpg', '.gif', '.webp', '.svg')):
        return False
    prefix = e.split('@')[0]
    return not any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES)


def fetch_emails(url):
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=8, verify=False)
        if r.status_code != 200:
            return []
        text = r.text
        for a in BeautifulSoup(text, "html.parser").find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {a['href'][7:].split('?')[0]}"
        return list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())))
    except Exception:
        return []


def load_opt_outs():
    out = set()
    for f in [OPT_OUT_FILE, SENT_LOG]:
        if os.path.exists(f):
            try:
                df = pd.read_csv(f, dtype=str).fillna("")
                if "email" in df.columns:
                    out.update(df["email"].str.lower().str.strip())
            except Exception:
                pass
    return out


def scrape(seen, global_seen):
    from niche_lead_sourcer import get_leads
    return get_leads("restaurant", limit=max(REFILL_BELOW * 2, 300), seen=seen, global_seen=global_seen)


def send_one(email, subject, body):
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json={"personalizations": [{"to": [{"email": email}]}],
                  "from": {"email": FROM_EMAIL, "name": SENDER_NAME},
                  "subject": subject, "content": [{"type": "text/plain", "value": body}]},
            timeout=15)
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {e}"); return False


def run():
    if not SENDGRID_KEY:
        print("[RST ENGINE] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    global_seen = load_global_registry(exclude_queue="restaurant_queue.csv")

    if pending_count < REFILL_BELOW:
        new = scrape(seen, global_seen)
        df_combined = pd.concat([df_existing, pd.DataFrame(new)], ignore_index=True).drop_duplicates(subset=["email"]) if new and not df_existing.empty else (pd.DataFrame(new) if new else df_existing)
        if new:
            df_combined.to_csv(QUEUE_FILE, index=False)
    else:
        df_combined = df_existing

    if df_combined.empty:
        return

    indices = list(df_combined[df_combined["status"] == "pending"].index)
    random.shuffle(indices)
    sent = 0
    for idx in indices[:DAILY_LIMIT]:
        email = str(df_combined.loc[idx].get("email", "")).strip()
        if not email or email.lower() in global_seen:
            df_combined.at[idx, "status"] = "opted_out"; continue
        ok = send_one(email, random.choice(SUBJECTS), random.choice(MESSAGES).format(calendly=CALENDLY))
        df_combined.at[idx, "status"] = "sent" if ok else "failed"
        if ok:
            sent += 1
            global_seen.add(email.lower())
            register_sent(email, "restaurant")
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[RST ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
