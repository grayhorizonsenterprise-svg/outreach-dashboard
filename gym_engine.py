"""
gym_engine.py — Gray Horizons Enterprise
Standalone gym / fitness studio outreach engine.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "gym_queue.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Alex")
CALENDLY      = "https://calendly.com/grayhorizonsenterprise/30min"
DAILY_LIMIT   = int(os.getenv("GYM_DAILY_LIMIT", "300"))
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
    "youtube.com","google.com","yelp.com","wikipedia.org","bodybuilding.com",
    "menshealth.com","womenshealthmag.com","shape.com","self.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = [
    "gym owner email contact",
    "fitness studio owner email contact",
    "boutique gym owner email contact",
    "CrossFit gym owner email contact",
    "personal training studio owner email",
    "yoga studio owner email contact",
    "Pilates studio owner email contact",
    "martial arts gym owner email contact",
    "boxing gym owner email contact",
    "MMA gym owner email contact",
    "spin studio owner email contact",
    "barre studio owner email contact",
    "boot camp fitness owner email contact",
    "HIIT studio owner email contact",
    "Orange Theory franchise owner email contact",
    "F45 franchise owner email contact",
    "independent gym owner email contact",
    "fitness center director email contact",
    "gym owner coach email contact",
    "fitness business mentor email contact",
    "gym marketing expert email contact",
    "personal trainer email contact site:.com",
    "certified personal trainer email blog contact",
    "online personal trainer email contact",
    "fitness coach email newsletter contact",
    "strength coach email contact",
    "powerlifting coach email contact",
    "weightlifting coach email contact",
    "nutrition coach email contact",
    "wellness coach email contact",
    "fitness YouTuber email contact",
    "fitness podcast host email contact",
    "gym owner Substack email contact",
    "fitness entrepreneur email contact",
    "gym startup founder email contact",
    "fitness app founder email contact",
    "fitness influencer business email contact",
    "gym owner Texas email contact",
    "gym owner Florida email contact",
    "fitness studio California email contact",
    "gym owner New York email contact",
    "gym owner Chicago email contact",
    "fitness studio Atlanta email contact",
    "gym owner Phoenix email contact",
    "fitness studio Dallas email contact",
    "gym management consultant email contact",
    "fitness business consultant email contact",
    "gym owner mastermind email contact",
    "fitness franchise owner email contact",
    "athletic performance center email contact",
]

SUBJECTS = [
    "Your free trial members - what converts them?",
    "Most gyms lose 40% of new members in month 2",
    "Quick question about your member retention process",
    "How top studios are filling classes automatically",
    "The retention system top gyms run in the background",
]

MESSAGES = [
    """\
Hey,

Quick question - when someone signs up for a free trial at your gym, what does the follow-up look like for the next 30 days?

For most gyms, the answer is "not much." And that's why month-2 churn is the industry's biggest problem.

We build automated onboarding and retention sequences that check in with new members, celebrate milestones, fill empty class spots, and flag members who are showing cancellation signals - before they cancel.

Happy to show you what it looks like for your specific setup: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The gyms with the best retention numbers aren't doing anything magical - they just communicate consistently and personally with every member.

We automate that communication: welcome sequences, progress check-ins, birthday messages, class reminders, referral asks at the right moment, and win-back campaigns for members who've gone quiet.

All personalized. All automated. Zero extra staff hours.

15-minute call to see how it fits your operation: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

If your gym has 200 members and 20% churn annually, you're replacing 40 members just to stay flat.

The math changes completely when you plug those holes. Dropping churn from 20% to 12% is often worth more than doubling your new member acquisition.

We build the retention system - automated re-engagement, milestone celebrations, accountability check-ins - that makes members feel seen and stay longer.

Worth 15 minutes to see if the numbers make sense for you: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Slow Tuesday afternoons and empty Thursday morning classes are pure profit left on the table.

We set up automated class-fill campaigns that go out to members based on their attendance patterns - nudging the right people to book the right classes at the right time.

One studio we work with went from 60% average class capacity to 84% within 6 weeks.

Quick call to see what's possible for your location: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Most personal trainers and studio owners are incredible at what they do - but the business side (follow-up, client communication, referrals, upsells) runs on sticky notes and good intentions.

We build the system that handles all of it automatically: client check-ins, package renewal reminders, referral requests, reactivation of lapsed clients.

You focus on coaching. The system handles the rest.

If this sounds like something worth exploring: {calendly}

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


def scrape(seen):
    import urllib.parse
    queries = random.sample(SEARCH_QUERIES, min(50, len(SEARCH_QUERIES)))
    new, ddgs = [], DDGS()
    for i, q in enumerate(queries):
        print(f"  [GYM {i+1}/{len(queries)}] {q[:60]}")
        try:
            for r in list(ddgs.text(q, max_results=6)):
                url = r.get("href", "")
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS or not url:
                    continue
                for email in fetch_emails(url):
                    if email in seen:
                        continue
                    seen.add(email)
                    new.append({"email": email, "name": r.get("title", "")[:80],
                                "website": url, "source": q[:60],
                                "status": "pending", "niche": "gym"})
                    print(f"    [+] {email}")
                time.sleep(random.uniform(0.3, 0.6))
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"    [ERR] {e}"); time.sleep(2)
    return new


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
        print("[GYM ENGINE] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    if pending_count < REFILL_BELOW:
        new = scrape(seen)
        df_combined = pd.concat([df_existing, pd.DataFrame(new)], ignore_index=True).drop_duplicates(subset=["email"]) if new and not df_existing.empty else (pd.DataFrame(new) if new else df_existing)
        if new:
            df_combined.to_csv(QUEUE_FILE, index=False)
    else:
        df_combined = df_existing

    if df_combined.empty:
        return

    opt_outs = load_opt_outs()
    indices = list(df_combined[df_combined["status"] == "pending"].index)
    random.shuffle(indices)
    sent = 0
    for idx in indices[:DAILY_LIMIT]:
        email = str(df_combined.loc[idx].get("email", "")).strip()
        if not email or email.lower() in opt_outs:
            df_combined.at[idx, "status"] = "opted_out"; continue
        ok = send_one(email, random.choice(SUBJECTS), random.choice(MESSAGES).format(calendly=CALENDLY))
        df_combined.at[idx, "status"] = "sent" if ok else "failed"
        if ok:
            sent += 1; print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[GYM ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
