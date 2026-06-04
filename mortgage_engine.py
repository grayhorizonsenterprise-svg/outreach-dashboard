"""
mortgage_engine.py — Gray Horizons Enterprise
Standalone mortgage broker / lender outreach engine.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from email_registry import load_global_registry, register_sent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "mortgage_queue.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Gray Horizons Enterprise")
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
    "youtube.com","google.com","yelp.com","wikipedia.org","bankrate.com",
    "nerdwallet.com","lendingtree.com","zillow.com","realtor.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = [
    "mortgage broker independent email contact",
    "mortgage loan officer email contact blog",
    "independent mortgage lender email contact",
    "mortgage broker personal site email",
    "residential mortgage broker email contact",
    "commercial mortgage broker email contact",
    "hard money lender email contact",
    "private money lender email contact",
    "jumbo loan specialist email contact",
    "FHA loan specialist email contact",
    "VA loan specialist email contact",
    "USDA loan specialist email contact",
    "construction loan lender email contact",
    "bridge loan lender email contact",
    "DSCR loan lender email contact",
    "non-QM lender email contact",
    "mortgage broker coach email contact",
    "mortgage marketing consultant email contact",
    "loan officer blog email contact",
    "mortgage broker YouTube channel email contact",
    "mortgage broker podcast email contact",
    "mortgage broker Substack email contact",
    "mortgage broker Florida email contact",
    "mortgage broker Texas email contact",
    "mortgage broker California email contact",
    "mortgage broker New York email contact",
    "mortgage broker Georgia email contact",
    "mortgage broker Arizona email contact",
    "mortgage broker Colorado email contact",
    "mortgage broker Nevada email contact",
    "refinance specialist email contact",
    "home equity loan specialist email contact",
    "HELOC specialist email contact",
    "reverse mortgage specialist email contact",
    "fix and flip lender email contact",
    "real estate investment lender email contact",
    "mortgage team leader email contact",
    "mortgage branch manager email contact",
    "mortgage company owner email contact",
    "community bank mortgage officer email contact",
    "credit union mortgage officer email contact",
    "mortgage broker referral partner email",
    "mortgage marketing expert email contact",
    "lead generation for mortgage email contact",
    "mortgage broker networking email contact",
    "real estate agent mortgage partner email",
    "mortgage advisor blog email contact",
    "home loan consultant email contact",
    "mortgage planner email contact",
    "mortgage strategist email contact",
]

SUBJECTS = [
    "How are you capturing rate-shopping leads before they disappear?",
    "Most LOs miss 60% of their leads after hours",
    "The follow-up system top producers run automatically",
    "Quick question about your past client refi pipeline",
    "One automation that consistently adds 2-3 loans/month",
]

MESSAGES = [
    """\
Hey,

When a borrower fills out a rate inquiry on your site at 8pm on a Friday, what happens?

If the answer is "we call them Monday," you've already lost them. Rate shoppers contact 3-5 lenders simultaneously and go with whoever responds first.

We build instant response systems for mortgage brokers and LOs - automated rate inquiry acknowledgment, pre-qual questionnaire, and calendar booking - so you're always first in the door.

Happy to walk you through it: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Your past clients are your best source of referrals and refis - and most LOs communicate with them maybe once a year.

We build automated past-client pipelines: rate drop alerts when their current rate looks refinanceable, annual mortgage review outreach, birthday messages, and referral asks timed to the right moment in the relationship.

Top producers we work with generate 2-4 deals per month purely from past client automation.

15-minute call to see if this applies to your book: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Here's a stat that usually gets mortgage professionals' attention: the average loan officer follows up with a lead an average of 1.3 times. The average customer needs 7 touchpoints before they're ready to move forward.

We close that gap with automated nurture sequences - educational content, market updates, rate alerts - that keep you top of mind until the borrower is ready, without you having to manually track everyone.

Worth a quick conversation: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Referral partnerships with real estate agents are still the highest-quality lead source in mortgage. Most LOs leave them entirely to chance.

We build automated agent nurture systems: weekly market updates to your agent list, co-marketing campaigns, closed loan celebration messages, and timely check-ins during slow markets.

You stay top of mind with every agent in your network without manually managing the relationship.

Quick call to see what this looks like in practice: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The brokers closing the most volume right now aren't necessarily working more leads - they're working a better system.

We help mortgage professionals set up the backend that most never build: lead response automation, nurture sequences, agent outreach, past client reactivation, and referral systems.

It takes about a week to build. After that it runs and compounds.

If you're looking to add consistent volume without adding headcount: {calendly}

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
    return get_leads("mortgage", limit=max(REFILL_BELOW * 2, 300), seen=seen, global_seen=global_seen)


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
        print("[MTG ENGINE] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    global_seen = load_global_registry(exclude_queue="mortgage_queue.csv")

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
            register_sent(email, "mortgage")
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[MTG ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
