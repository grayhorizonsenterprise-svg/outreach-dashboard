"""
insurance_engine.py — Gray Horizons Enterprise
Standalone insurance agent / financial advisor outreach engine.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from email_registry import load_global_registry, register_sent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "insurance_queue.csv")
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
    "youtube.com","google.com","yelp.com","wikipedia.org","amazon.com",
    "nerdwallet.com","investopedia.com","bankrate.com","insurance.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = [
    "independent insurance agent email contact",
    "insurance broker personal blog email",
    "financial advisor email contact site:.com",
    "independent financial planner email contact",
    "life insurance agent email contact",
    "health insurance broker email contact",
    "Medicare insurance agent email contact",
    "auto insurance agent email blog",
    "home insurance agent independent email",
    "commercial insurance broker email contact",
    "property casualty insurance agent email",
    "business insurance broker email contact",
    "independent insurance agency owner email",
    "captive insurance agent email contact",
    "insurance agent coach email contact",
    "insurance marketing organization email",
    "annuity advisor email contact",
    "retirement planning advisor email contact",
    "wealth management advisor email blog",
    "fee-only financial planner email contact",
    "registered investment advisor email contact",
    "certified financial planner CFP email contact",
    "estate planning advisor email contact",
    "tax planning advisor email contact",
    "insurance agent YouTube channel email contact",
    "insurance agent Substack newsletter email",
    "insurance agent podcast email contact",
    "senior insurance agent email contact",
    "disability insurance specialist email contact",
    "long term care insurance agent email contact",
    "group benefits advisor email contact",
    "employee benefits broker email contact",
    "supplemental insurance agent email contact",
    "P&C insurance broker email contact",
    "surplus lines broker email contact",
    "wholesale insurance broker email contact",
    "insurance agent Florida email contact",
    "insurance agent Texas email contact",
    "insurance agent California email contact",
    "insurance agent New York email contact",
    "financial advisor newsletter email contact",
    "investment advisor blog email contact",
    "401k advisor email contact",
    "IRA advisor email contact blog",
    "insurance agent referral partner email",
    "insurance agent cross sell email contact",
    "multi-line insurance agent email",
    "insurance agency principal email contact",
    "independent marketing organization email contact",
    "financial services professional email contact",
]

SUBJECTS = [
    "Most agents lose leads in the first 10 minutes",
    "How are you following up with quote requests after hours?",
    "The referral system top agents run automatically",
    "Quick question about your client retention process",
    "How a simple automation added 8 policies last month",
]

MESSAGES = [
    """\
Hey,

When someone requests a quote on your site at 7pm, what does your follow-up look like?

If the answer is a call the next morning, you're probably losing 50% of those leads to whoever responds first.

We set up instant response systems for independent agents - automated quote follow-up, appointment booking, and client nurture - so you're always first in the door, even at midnight.

If you want to see how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The agents writing the most new business right now aren't necessarily better at selling - they just never let a lead go cold.

We build automated follow-up systems that contact every quote request within 60 seconds, follow up 3 times over 7 days, and hand off warm prospects to your calendar.

Takes about 2 hours to set up. Works across life, health, auto, home - any line you write.

15-minute call to see if it fits: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Most financial advisors and insurance agents sit on a goldmine: past clients who trust them but haven't heard from them in 12+ months.

We run automated client reactivation campaigns that reach out to dormant accounts with personalized check-ins - anniversary reviews, policy updates, life event triggers.

One advisor we work with added 11 new policies in 45 days just from existing clients.

Quick call to see if your book has the same opportunity: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Referrals are the best leads you'll ever get. Most agents leave them entirely to chance.

We set up automated referral systems that ask every satisfied client for a referral at exactly the right moment - right after a claim is handled, right after a policy saves them money.

Systematic, personal, and it runs without you having to think about it.

Happy to show you what it looks like: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Something I keep seeing with successful independent agents: the ones growing fastest have the best systems, not the biggest marketing budgets.

We help advisors and agents build the backend - automated outreach, CRM-free pipeline tracking, renewal reminders, cross-sell sequences - so more of your book stays active and profitable.

Worth a 15-minute conversation if you're looking to add capacity without adding headcount: {calendly}

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
    return not any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES)


def fetch_emails(url: str) -> list:
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)},
                         timeout=8, verify=False)
        if r.status_code != 200:
            return []
        text = r.text
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {a['href'][7:].split('?')[0]}"
        return list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())))
    except Exception:
        return []


def load_opt_outs() -> set:
    out = set()
    for f in [OPT_OUT_FILE, SENT_LOG]:
        if not os.path.exists(f):
            continue
        try:
            df = pd.read_csv(f, dtype=str).fillna("")
            if "email" in df.columns:
                out.update(df["email"].str.lower().str.strip())
        except Exception:
            pass
    return out


def scrape(seen: set, global_seen: set) -> list:
    import urllib.parse
    queries = random.sample(SEARCH_QUERIES, min(50, len(SEARCH_QUERIES)))
    new, ddgs = [], DDGS()
    for i, q in enumerate(queries):
        print(f"  [INS {i+1}/{len(queries)}] {q[:60]}")
        try:
            for r in list(ddgs.text(q, max_results=6)):
                url = r.get("href", "")
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS or not url:
                    continue
                for email in fetch_emails(url):
                    if email in seen or email in global_seen:
                        continue
                    seen.add(email)
                    new.append({"email": email, "name": r.get("title", "")[:80],
                                "website": url, "source": q[:60],
                                "status": "pending", "niche": "insurance"})
                    print(f"    [+] {email}")
                time.sleep(random.uniform(0.3, 0.6))
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"    [ERR] {e}"); time.sleep(2)
    return new


def send_one(email, subject, body) -> bool:
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
        print("[INS ENGINE] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    global_seen = load_global_registry(exclude_queue="insurance_queue.csv")

    if pending_count < REFILL_BELOW:
        new = scrape(seen, global_seen)
        if new:
            df_new = pd.DataFrame(new)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["email"]) if not df_existing.empty else df_new
            df_combined.to_csv(QUEUE_FILE, index=False)
        else:
            df_combined = df_existing
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
            register_sent(email, "insurance")
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[INS ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
