"""
ecommerce_engine.py — Gray Horizons Enterprise
Standalone e-commerce store owner outreach engine.
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from email_registry import load_global_registry, register_sent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, "ecommerce_queue.csv")
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
    "youtube.com","google.com","yelp.com","wikipedia.org","amazon.com",
    "shopify.com","etsy.com","ebay.com","walmart.com","target.com",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = [
    "Shopify store owner contact email",
    "e-commerce entrepreneur blog email contact",
    "online store owner email newsletter",
    "dropshipping store owner email contact",
    "print on demand seller email contact",
    "DTC brand founder email contact",
    "direct to consumer brand email contact",
    "WooCommerce store owner email contact",
    "BigCommerce store owner email contact",
    "Amazon FBA seller blog email contact",
    "Etsy shop owner email contact",
    "handmade product seller email contact",
    "private label seller Amazon email contact",
    "ecommerce brand founder email contact",
    "Shopify entrepreneur email newsletter",
    "ecommerce coach email contact",
    "ecommerce consultant email contact",
    "dropship mentor email contact",
    "product sourcing expert email contact",
    "ecommerce YouTube channel email contact",
    "ecommerce podcast host email contact",
    "Shopify Substack newsletter email contact",
    "online boutique owner email contact",
    "fashion ecommerce brand email contact",
    "beauty brand founder email contact",
    "supplement brand owner email contact",
    "pet brand ecommerce email contact",
    "baby product brand email contact",
    "fitness equipment brand email contact",
    "outdoor gear brand email contact",
    "home goods brand founder email contact",
    "candle maker email contact",
    "jewelry maker online store email contact",
    "art print seller email contact",
    "digital product seller email contact",
    "membership site owner email contact",
    "subscription box founder email contact",
    "ecommerce fulfillment company owner email",
    "3PL warehouse owner email contact",
    "ecommerce agency owner email contact",
    "conversion rate optimizer email contact",
    "email marketing specialist ecommerce email",
    "abandoned cart recovery specialist email",
    "Klaviyo email expert contact email",
    "Facebook ads ecommerce expert email contact",
    "Google Shopping ads expert email contact",
    "ecommerce SEO expert email contact",
    "influencer brand deal email contact",
    "UGC creator brand email contact",
    "ecommerce investor email contact",
]

SUBJECTS = [
    "Your cart abandonment rate is probably 70%+",
    "E-commerce brands doing $500K+/yr all have this",
    "Quick question about your post-purchase sequence",
    "How are you handling customers who don't come back?",
    "One email sequence that typically adds 15% revenue",
]

MESSAGES = [
    """\
Hey,

If you're running a Shopify or WooCommerce store and not doing automated abandoned cart recovery, you're leaving roughly 70% of your revenue on the table.

We build the full email and SMS sequence - cart abandonment, post-purchase upsell, browse abandonment, win-back - configured for your specific product catalog.

Most stores see 10-20% revenue lift in the first 30 days.

If you want to see what it looks like for your store: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

The e-commerce brands doing consistent $50K+ months all have one thing in common: a backend that runs while they sleep.

We're talking automated post-purchase sequences, loyalty programs, restock alerts, review requests, and VIP campaigns - all personalized, all running without your involvement.

We build this out in about a week. Happy to show you what it looks like for your specific brand: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Customer acquisition costs have gone up 60% in the last 3 years. The brands winning right now are the ones squeezing maximum lifetime value from every buyer.

We set up automated LTV systems: purchase-based segmentation, repeat purchase timing, cross-sell sequences, and win-back campaigns for buyers who haven't returned in 90+ days.

The math usually looks like this: same traffic, 30-40% more revenue.

Worth a quick call: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Most e-commerce store owners we talk to have their acquisition sorted - they're running ads and getting traffic. The problem is everything after the first purchase is manual or nonexistent.

We handle the backend: post-purchase thank you, product education, upsell timing, loyalty rewards, review collection, and referral asks - all automated and personalized.

One client went from 1.2x to 2.8x ROAS just by fixing the post-purchase sequence.

Quick call to look at your specific setup: {calendly}

Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

If you're doing any real volume, your customer list is your most valuable asset - and most brands barely use it.

We build automated email programs that generate 30-40% of total revenue without touching ads. Flows, campaigns, segmentation, deliverability optimization - the whole thing.

Takes 2-3 weeks to build. Runs forever.

If this sounds relevant to where you are: {calendly}

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
    return get_leads("ecommerce", limit=max(REFILL_BELOW * 2, 300), seen=seen, global_seen=global_seen)


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
        print("[ECO ENGINE] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    global_seen = load_global_registry(exclude_queue="ecommerce_queue.csv")

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
            register_sent(email, "ecommerce")
            print(f"  [OK] {email}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[ECO ENGINE DONE] {sent} sent today")


if __name__ == "__main__":
    run()
