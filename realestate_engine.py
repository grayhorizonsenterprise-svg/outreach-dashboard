"""
realestate_engine.py — Gray Horizons Enterprise
Standalone real estate outreach engine.
Scrapes investors, agents, property managers → sends targeted pitch.
Runs independently — no dashboard required.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from email_registry import load_global_registry, register_sent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "realestate_queue.csv")
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
    "youtube.com","google.com","yelp.com","wikipedia.org","zillow.com",
    "realtor.com","trulia.com","redfin.com","loopnet.com","costar.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

SEARCH_QUERIES = [
    "real estate investor blog contact email",
    "real estate wholesaler contact email site:.com",
    "fix and flip investor email contact",
    "real estate syndication founder email",
    "multifamily investor blog contact email",
    "apartment investor email contact newsletter",
    "real estate coach email contact",
    "rental property investor blog email",
    "BRRRR investor email contact blog",
    "short term rental investor blog email",
    "Airbnb investor contact email",
    "real estate agent personal blog email contact",
    "independent real estate agent email newsletter",
    "real estate team leader email contact",
    "real estate broker personal site email",
    "property management company owner email",
    "boutique property management email contact",
    "independent property manager email site",
    "commercial real estate broker email contact",
    "industrial real estate investor email",
    "office building investor email contact blog",
    "self storage investor email contact",
    "mobile home park investor email blog",
    "land investor email contact",
    "note investor real estate email contact",
    "real estate private equity email contact",
    "real estate fund manager contact email",
    "passive real estate investor blog email",
    "out of state real estate investor email contact",
    "real estate YouTube channel contact email",
    "real estate podcast host email contact",
    "real estate Substack newsletter email",
    "real estate investor meetup organizer email",
    "real estate mentor email contact",
    "top producing agent blog email contact",
    "luxury real estate agent contact email",
    "first time home buyer coach email",
    "real estate flipper contractor email contact",
    "turnkey rental provider email contact",
    "real estate virtual assistant email contact",
    "hard money lender real estate email contact",
    "private money lender real estate email",
    "real estate attorney blog email contact",
    "title company owner real estate email",
    "real estate CPA email contact",
    "1031 exchange advisor email contact",
    "real estate auctioneer email contact",
    "estate sale company email contact",
    "real estate developer small email contact",
    "new construction builder email contact",
]

SUBJECTS = [
    "Quick question about your follow-up process",
    "Most agents lose 40% of leads in the first 5 minutes",
    "How are you handling leads when you're showing a property?",
    "Your next 3 deals might already be in your database",
    "One system our clients use to close more without more leads",
]

MESSAGES = [
    """\
Hey,

Quick question - when a lead comes in while you're in a showing, what happens to it?

Most agents we work with said the same thing: by the time they follow up, the prospect already talked to someone else.

We built a system that responds instantly, qualifies the lead, and books a call - without you lifting a finger.

Takes 20 minutes to set up. Happy to show you exactly how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The agents closing the most deals right now aren't working more hours - they're working a better system.

We help real estate professionals set up AI-powered follow-up that contacts every lead within 60 seconds, nurtures the ones who aren't ready, and flags the hot ones for immediate action.

No CRM overhaul. No new software to learn. Just more deals closed from the leads you're already getting.

If you want to see how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Something most agents don't realize - your old database is probably worth $20K+ in deals you haven't closed yet.

We run a reactivation sequence on dormant contacts and consistently turn 2-5% of them into active conversations within 30 days.

Took one client from 0 deals in a slow month to 3 closings just from contacts they'd stopped following up on.

15-minute call to see if this applies to your situation: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Property managers and investors we work with used to spend hours chasing down late rent, maintenance requests, and lease renewals manually.

We automate all of it - tenant communication, payment reminders, renewal outreach - so you can manage more doors without more headaches.

Currently helping operators with portfolios ranging from 10 to 200+ units. Curious if it applies to your setup: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Real estate is a volume game and most of that volume falls through the cracks between spreadsheets, text threads, and sticky notes.

We build the backend system that makes sure nothing gets missed - every lead followed up, every deal tracked, every client nurtured automatically.

You close. The system handles everything else.

See what it looks like for your specific situation: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]


def is_clean(email: str) -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith(('.png', '.jpg', '.gif', '.webp', '.svg')):
        return False
    prefix = e.split('@')[0]
    if any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES):
        return False
    return True


def fetch_emails(url: str) -> list:
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)},
                         timeout=8, verify=False, allow_redirects=True)
        if r.status_code != 200:
            return []
        text = r.text
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                addr = a["href"][7:].split("?")[0].strip()
                if addr:
                    text += f" {addr}"
        found = [e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())]
        return list(dict.fromkeys(found))
    except Exception:
        return []


def load_opt_outs() -> set:
    out = set()
    for f in [OPT_OUT_FILE, SENT_LOG]:
        if not os.path.exists(f):
            continue
        try:
            df = pd.read_csv(f, dtype=str).fillna("")
            col = "email" if "email" in df.columns else None
            if col:
                out.update(df[col].str.lower().str.strip())
        except Exception:
            pass
    return out


def scrape(seen: set, global_seen: set) -> list:
    from niche_lead_sourcer import get_leads
    return get_leads("realestate", limit=max(REFILL_BELOW * 2, 300), seen=seen, global_seen=global_seen)


def send_one(email, subject, body) -> bool:
    try:
        payload = {
            "personalizations": [{"to": [{"email": email}]}],
            "from": {"email": FROM_EMAIL, "name": SENDER_NAME},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {e}")
        return False


def run():
    if not SENDGRID_KEY:
        print("[RE ENGINE] SENDGRID_API_KEY not set")
        return

    seen = set()
    df_existing = pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = len(df_existing[df_existing.get("status", pd.Series()) == "pending"]) if not df_existing.empty else 0

    global_seen = load_global_registry(exclude_queue="realestate_queue.csv")

    if pending_count < REFILL_BELOW:
        print(f"[RE ENGINE] Queue low ({pending_count}), scraping fresh leads...")
        new = scrape(seen, global_seen)
        if new:
            df_new = pd.DataFrame(new)
            if not df_existing.empty:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["email"])
            else:
                df_combined = df_new
            df_combined.to_csv(QUEUE_FILE, index=False)
            print(f"[RE ENGINE] {len(new)} new leads added")
        else:
            df_combined = df_existing
    else:
        df_combined = df_existing

    if df_combined.empty:
        print("[RE ENGINE] No leads to send")
        return

    pending = df_combined[df_combined["status"] == "pending"]
    indices = list(pending.index)
    random.shuffle(indices)

    sent = 0
    for idx in indices[:DAILY_LIMIT]:
        row = df_combined.loc[idx]
        email = str(row.get("email", "")).strip()
        if not email or email.lower() in global_seen:
            df_combined.at[idx, "status"] = "opted_out"
            continue
        subject = random.choice(SUBJECTS)
        body = random.choice(MESSAGES).format(calendly=CALENDLY)
        ok = send_one(email, subject, body)
        df_combined.at[idx, "status"] = "sent" if ok else "failed"
        if ok:
            sent += 1
            global_seen.add(email.lower())
            register_sent(email, "realestate")
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[RE ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
