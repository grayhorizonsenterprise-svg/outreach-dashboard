"""
medspa_engine.py — Gray Horizons Enterprise
Standalone med spa / aesthetics outreach engine.
Scrapes owners → sends targeted pitch → tracks in medspa_queue.csv
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "medspa_queue.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Alex")
CALENDLY      = "https://calendly.com/grayhorizonsenterprise/30min"
DAILY_LIMIT   = int(os.getenv("MEDSPA_DAILY_LIMIT", "300"))
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
    "healthgrades.com","zocdoc.com","vitals.com","webmd.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

SEARCH_QUERIES = [
    "med spa owner contact email",
    "medical spa director email contact",
    "aesthetics clinic owner email site:.com",
    "cosmetic clinic owner email contact",
    "botox clinic owner email contact",
    "dermal filler clinic email contact",
    "laser hair removal clinic owner email",
    "body contouring spa email contact",
    "coolsculpting clinic owner email",
    "IV drip spa owner email contact",
    "weight loss clinic owner email",
    "hormone therapy clinic owner email",
    "anti-aging clinic director email contact",
    "aesthetic nurse practitioner email contact",
    "medical aesthetician email contact",
    "cosmetic dermatology practice owner email",
    "skin care clinic owner email contact",
    "medspa franchise owner email contact",
    "spa owner email newsletter contact",
    "day spa owner email contact",
    "wellness spa owner email",
    "holistic spa owner email contact",
    "float spa owner email contact",
    "cryotherapy center owner email contact",
    "infrared sauna studio owner email",
    "med spa marketing blog email contact",
    "aesthetics business coach email contact",
    "medspa consultant email contact",
    "cosmetic surgery center admin email",
    "plastic surgery practice manager email",
    "facial spa owner contact email",
    "esthetician spa owner email contact",
    "chemical peel clinic email contact",
    "microneedling spa owner email",
    "hydrafacial provider email contact",
    "PRP treatment clinic email contact",
    "vampire facial clinic email contact",
    "lip filler clinic owner email",
    "brow studio owner email contact",
    "lash extension studio owner email",
    "permanent makeup artist email contact",
    "tattoo removal clinic email contact",
    "vein treatment center email contact",
    "med spa Texas email contact",
    "med spa Florida email contact",
    "aesthetics clinic California email contact",
    "luxury med spa owner email",
    "boutique med spa owner email contact",
    "medspa startup founder email contact",
    "med spa Instagram owner email contact",
]

SUBJECTS = [
    "Filling your slow appointment slots automatically",
    "How top med spas handle no-shows without chasing clients",
    "Your consultation form is losing you bookings",
    "3 things top aesthetics clinics automate in 2025",
    "Quick question about your new patient flow",
]

MESSAGES = [
    """\
Hey,

Quick question - when someone fills out your consultation form at 9pm, what happens next?

If the answer is "we call them the next morning," research shows 60% of those leads have already booked somewhere else.

We set up an instant response system for med spas that replies within 2 minutes, qualifies the inquiry, and books directly to your calendar - even at 2am.

No software change. No extra staff. Setup takes a few hours.

Happy to walk you through how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The med spas doing $80K+ months aren't necessarily busier - they just plug the holes.

The two biggest holes we see: no-show rate above 12% and new inquiry response time over 10 minutes.

We fix both with automated confirmation sequences, smart reminders, and instant lead response - all tailored to your treatment menu.

15 minutes to see if this fits your practice: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Most aesthetics clinics we talk to are running Google Ads and getting decent traffic - but their consult-to-booking rate is under 30%.

The problem is almost always the follow-up gap. Someone inquires, gets a call the next day, already moved on.

We close that gap with AI-powered instant response and nurture sequences. Clients typically see 40-60% improvement in booking rate within the first month.

If that sounds relevant to what you're working on: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Reactivating old clients is the fastest revenue in aesthetics - they already trust you, already know your pricing, already know where you are.

We run automated reactivation campaigns to dormant clients (90+ days since last visit) with personalized messages based on their treatment history.

One clinic we work with added $18K in revenue in the first month just from clients they thought were gone.

If you'd like to see how it works for your specific services: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Your best clients will refer you - but most will never mention it unless you make it effortless.

We set up a fully automated referral and loyalty system for med spas: after every appointment, clients get a personalized message with their referral link, points balance, and next reward.

No app. No card. It runs in the background and compounds every month.

Curious how it would work for your practice: {calendly}

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
                         timeout=8, verify=False)
        if r.status_code != 200:
            return []
        text = r.text
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {a['href'][7:].split('?')[0]}"
        return list(dict.fromkeys(
            e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())
        ))
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


def scrape(seen: set) -> list:
    import urllib.parse
    queries = random.sample(SEARCH_QUERIES, min(50, len(SEARCH_QUERIES)))
    new = []
    ddgs = DDGS()
    for i, q in enumerate(queries):
        print(f"  [MED {i+1}/{len(queries)}] {q[:60]}")
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
                    new.append({
                        "email": email, "name": r.get("title", "")[:80],
                        "website": url, "source": q[:60],
                        "status": "pending", "niche": "medspa",
                    })
                    print(f"    [+] {email}")
                time.sleep(random.uniform(0.3, 0.6))
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"    [ERR] {e}")
            time.sleep(2)
    return new


def send_one(email, subject, body) -> bool:
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": email}]}],
                "from": {"email": FROM_EMAIL, "name": SENDER_NAME},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            }, timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {e}")
        return False


def run():
    if not SENDGRID_KEY:
        print("[MED ENGINE] SENDGRID_API_KEY not set")
        return

    seen = set()
    df_existing = pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0

    if pending_count < REFILL_BELOW:
        print(f"[MED ENGINE] Queue low ({pending_count}), scraping...")
        new = scrape(seen)
        if new:
            df_new = pd.DataFrame(new)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["email"]) if not df_existing.empty else df_new
            df_combined.to_csv(QUEUE_FILE, index=False)
        else:
            df_combined = df_existing
    else:
        df_combined = df_existing

    if df_combined.empty:
        print("[MED ENGINE] No leads")
        return

    opt_outs = load_opt_outs()
    pending = df_combined[df_combined["status"] == "pending"]
    indices = list(pending.index)
    random.shuffle(indices)
    sent = 0
    for idx in indices[:DAILY_LIMIT]:
        row = df_combined.loc[idx]
        email = str(row.get("email", "")).strip()
        if not email or email.lower() in opt_outs:
            df_combined.at[idx, "status"] = "opted_out"
            continue
        ok = send_one(email, random.choice(SUBJECTS),
                      random.choice(MESSAGES).format(calendly=CALENDLY))
        df_combined.at[idx, "status"] = "sent" if ok else "failed"
        if ok:
            sent += 1
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[MED ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
