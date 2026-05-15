"""
twitter_poster.py — Gray Horizons Enterprise
Auto-posts to Twitter/X daily. Three content streams:
  1. Shadow Clans lore drops + episode teasers (builds audience/IP brand)
  2. Edge Engine signal previews (drives Signals subscriptions)
  3. Business tip hooks (drives AI System / service engine leads)

Setup (one-time, 10 minutes):
  1. Go to developer.twitter.com → Sign in → Create Project → Create App
  2. Set App Permissions to "Read and Write"
  3. Under "Keys and Tokens" generate:
     - API Key + API Secret
     - Access Token + Access Token Secret
  4. Add all 4 values to Railway env vars (see ENV VARS below)

Railway env vars to add:
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_SECRET

Schedule: Add to sync_to_railway.py OR run separately via Task Scheduler.
"""

import os
import sys
import json
import random
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
POSTED_LOG = DATA_DIR / "twitter_posted.json"

SIGNALS_LINK = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
GUMROAD_LINK = "https://horizons56.gumroad.com"
WHOP_LINK    = os.getenv("WHOP_INDICATORS_LINK", "https://horizons56.gumroad.com/l/ghe-indicators")

# ─── Content Pools ────────────────────────────────────────────────────────────

SHADOW_CLANS_POSTS = [
    "RAIZEN didn't choose exile. He chose something harder.\n\nHonor.\n\n#ShadowClans #darkfantasy #lore",
    "Three factions. One gate. And the one thing none of them will say out loud.\n\nThey all know what's on the other side.\n\n#ShadowClans #WorldBuilding",
    "KURO doesn't fight wars.\n\nHe ends them before they start.\n\n#ShadowClans #RavenOrder #darkfantasy",
    "The Hollow Gate wasn't built to be opened.\n\nVARN opened it anyway.\n\n#ShadowClans #GorillaTitans #lore",
    "Episode drops this week. The night RAIZEN walked away from everything.\n\n#ShadowClans #cinematic #fantasy",
    "Wolf Clan. Raven Order. Gorilla Titans.\n\nThree wars. One cause. And one man who knows the truth.\n\n#ShadowClans",
    "KURO has never lost a war.\n\nBecause he's never fought one.\n\n#ShadowClans #RavenOrder",
    "The gate is open. The question isn't what came through.\n\nIt's what VARN gave to open it.\n\n#ShadowClans #HollowGate",
    "Episode 1 drops soon. Follow before the lore starts.\n\n#ShadowClans #darkfantasy #anime #cinematic",
    "Honor means nothing if you don't have anyone left to protect.\n\nRAIZEN learned that the hard way.\n\n#ShadowClans #WolfClan",
    "The Raven Order doesn't leave footprints.\n\nThey leave questions.\n\n#ShadowClans #lore #fantasy",
    "VARN was the strongest warrior in the world.\n\nThe gate changed that definition entirely.\n\n#ShadowClans",
]

SIGNALS_POSTS = [
    f"AI scanned the market before you woke up.\n\nTop setups, Congress trades, Kelly-sized picks.\n\nDelivered by 8am daily.\n\n{SIGNALS_LINK}",
    f"This week: NVDA momentum signal fired before the 8% move.\n\nWe track every setup before market open.\n\n$49/month → {SIGNALS_LINK}",
    f"Congress disclosed 14 trades this week.\n\nWe flagged all of them within 48 hours. Subscribers saw it first.\n\n{SIGNALS_LINK}",
    f"Sports edge this week: 3 picks, 2.8% average edge, Kelly-sized.\n\nNot picks. Probability.\n\n{SIGNALS_LINK}",
    f"Before 8am today:\n→ 2 stock setups\n→ 1 crypto alert\n→ 1 congressional disclosure\n→ 1 sports line with edge\n\nEvery morning. $49/month.\n{SIGNALS_LINK}",
    f"Most traders use the same information as everyone else.\n\nOur subscribers don't.\n\nEdge Engine → {SIGNALS_LINK}",
    f"Crypto alert went out at 7:42am.\n\nAsset moved 14% by noon.\n\nThat's why people subscribe.\n\n{SIGNALS_LINK}",
]

INDICATOR_POSTS = [
    f"Most traders use 14 indicators.\n\nWe use 3.\n\nEdge Scanner + Kelly Sizer + Congressional Tracker.\n\nAll 3 on TradingView. $79 one-time.\n\n{WHOP_LINK}",
    f"RSI alone is noise.\nVolume alone is noise.\nEMA alone is noise.\n\nAll 3 at the same time = signal.\n\nThe GHE Edge Scanner scores this 0-100 on every bar.\n\n{WHOP_LINK}",
    f"Congress disclosed $315M in trades last year.\n\nMost traders never see it coming.\n\nWe built an indicator that shows the volume patterns before disclosure.\n\n{WHOP_LINK}",
    f"The #1 reason traders blow up:\n\nNot bad entries.\nBad position sizing.\n\nKelly Criterion with Quarter-Kelly fractional sizing.\nBuilt into TradingView.\n\n{WHOP_LINK}",
    f"High-confidence signal = RSI 45-70 + Volume >2× avg + EMA crossover all on the same bar.\n\nMomentum score: 70+.\n\nThe GHE Edge Scanner labels only these.\n\n{WHOP_LINK}",
    f"3 TradingView indicators that cover the full trade:\n\n1. When to enter (Edge Scanner)\n2. How much to risk (Kelly Sizer)\n3. What insiders are doing (Congressional Tracker)\n\n$79 one-time: {WHOP_LINK}",
    f"Pine Script v5. Overlay charts. Real-time momentum scoring.\n\nWorks on stocks, crypto, forex — any asset on TradingView.\n\nGHE Indicator Suite: {WHOP_LINK}",
    f"Position sizing question I see constantly:\n\"How many shares should I buy?\"\n\nThe answer is math, not gut feeling.\n\nKelly Criterion. $79 one-time for the full suite.\n\n{WHOP_LINK}",
    f"Alert fatigue is real.\n\n200 signals a day → you act on garbage.\n3-5 high-confidence signals a day → you act on edges.\n\nThe GHE Edge Scanner scores 0-100. You only trade 70+.\n\n{WHOP_LINK}",
    f"Launched the GHE Indicator Suite on Whop.\n\n$49/month or $79 lifetime for all 3 TradingView indicators.\n\nEdge Scanner • Kelly Sizer • Congressional Tracker\n\n{WHOP_LINK}",
]

BUSINESS_TIP_POSTS = [
    "Most small businesses lose 30% of inbound calls to voicemail.\n\nThe customer doesn't leave a message.\n\nThey call the next result on Google.\n\n#SmallBusiness #automation",
    "Your Google Business Profile is either making you money or losing you money.\n\nThere's no neutral.\n\n#LocalSEO #smallbusiness",
    "SMS gets a 98% open rate.\nEmail gets 20%.\n\nIf you're a local business and you're not texting your customers, you're leaving money on the table.\n\n#marketing #smallbusiness",
    "Dead leads aren't dead.\n\nThey're just waiting for the right message at the right time.\n\n5-15% will convert if you follow up correctly.\n\n#sales #businesstips",
    "Every hour your website takes to load on mobile = 20% more visitors leave.\n\nMost business owners don't know their load time.\n\n#SEO #webdesign",
    f"We wrote 5 books for small business owners.\n\nAll free this week.\n\n→ {GUMROAD_LINK}\n\n#SmallBusiness #entrepreneur",
    "The businesses winning on Google Maps this year all have one thing in common.\n\nThey post to their Google Business Profile every single week.\n\n#LocalSEO #Google",
    "AI doesn't replace your front desk.\n\nIt answers when your front desk can't.\n\n#AI #automation #SmallBusiness",
    "3 posts a week on Instagram and Facebook.\n\nThat's the difference between the businesses people discover and the ones they forget.\n\n#SocialMedia #LocalBusiness",
    "Most contractors lose their best leads in the gap between the estimate and the follow-up.\n\nThat's a system problem. Not a sales problem.\n\n#contractors #businesstips",
]

ALL_POSTS = {
    "shadow_clans": SHADOW_CLANS_POSTS,
    "signals":      SIGNALS_POSTS,
    "indicators":   INDICATOR_POSTS,
    "business_tip": BUSINESS_TIP_POSTS,
}

DAILY_SCHEDULE = [
    ("shadow_clans", "08:00"),
    ("indicators",   "10:00"),
    ("signals",      "13:00"),
    ("business_tip", "17:00"),
    ("indicators",   "20:00"),
]

# Finance/trading/small-biz accounts whose followers are our target audience
FOLLOW_SEED_ACCOUNTS = [
    "TradingView", "CNBC", "MarketWatch", "YahooFinance",
    "Investopedia", "StockMarket", "CryptoDaily",
    "SmallBizTrends", "entrepreneurmag", "ForbesSmallBiz",
]

FOLLOW_SEARCH_QUERIES = [
    "stock trading tips site:twitter.com",
    "TradingView signals",
    "options trading alert",
    "crypto signal",
    "small business owner tips",
]

# Comment templates paired to tweet topics — fills {ticker} or {topic} from tweet
COMMENT_TEMPLATES = [
    "This is exactly why we built the Edge Engine — momentum scoring + congressional tracking before open. Worth checking out if you're active in {topic}.",
    "Solid point. We see the same pattern in our signals feed. Kelly-sized positions on setups like this are what separate consistent traders from the rest.",
    "Great read. For anyone who wants data-backed signals on {topic} before 8am daily — that's what we do at Gray Horizons.",
    "This is the kind of setup our Edge Scanner flags. Volume anomaly + RSI momentum on the same bar. Most miss it without the right tools.",
    "Exactly. Position sizing is the variable most traders skip. Kelly Criterion math does the heavy lifting once you have a proven edge.",
    "100%. Automation is what separates 7-figure operators from the grind. Happy to share what we've built for local businesses if you're curious.",
    "Well said. The businesses using AI for follow-up and lead capture are running laps around the ones still doing it manually.",
]

TRENDING_SEARCH_TERMS = [
    "stock market today",
    "trading signals",
    "options flow",
    "small business automation",
    "entrepreneur growth",
    "TradingView setup",
    "congressional trades",
]


# ─── Post tracking ────────────────────────────────────────────────────────────

def load_posted() -> dict:
    if POSTED_LOG.exists():
        try:
            return json.loads(POSTED_LOG.read_text())
        except Exception:
            pass
    return {"shadow_clans": [], "signals": [], "business_tip": []}


def save_posted(data: dict):
    POSTED_LOG.write_text(json.dumps(data, indent=2))


def pick_post(category: str, posted: dict) -> str:
    pool = ALL_POSTS[category]
    used = set(posted.get(category, []))
    unused = [p for p in pool if p not in used]
    if not unused:
        posted[category] = []  # reset cycle
        unused = pool[:]
    pick = random.choice(unused)
    posted.setdefault(category, []).append(pick)
    return pick


# ─── Twitter API ──────────────────────────────────────────────────────────────

def post_tweet(text: str) -> bool:
    """Post a tweet using Twitter API v2 with direct OAuth1 signing."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("[TWITTER] Missing API credentials — set all 4 env vars")
        return False

    try:
        from requests_oauthlib import OAuth1
        oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            json={"text": text[:280]},
            auth=oauth,
            timeout=15,
        )
        if r.status_code in (200, 201):
            tweet_id = r.json().get("data", {}).get("id", "?")
            print(f"  [TWITTER] Posted: twitter.com/i/web/status/{tweet_id}")
            return True
        else:
            err = r.text
            print(f"  [TWITTER] Error {r.status_code}: {err}")
            billing_keywords = ["payment", "billing", "credit", "funds", "balance", "insufficient", "usage limit"]
            if any(k in err.lower() for k in billing_keywords):
                _send_low_credits_alert(err)
            return False
    except Exception as e:
        print(f"  [TWITTER] Error: {e}")
        return False


ALERT_FLAG = DATA_DIR / "twitter_credits_alert_sent.flag"

def _send_low_credits_alert(error_detail: str):
    """Email a one-time alert when Twitter API billing errors are detected."""
    if ALERT_FLAG.exists():
        return  # already alerted — don't spam
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
    sender_email = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
    if not sendgrid_key:
        print("[TWITTER ALERT] No SendGrid key — cannot send credit alert email")
        return
    import requests as _req
    body = (
        "Hey,\n\n"
        "Your Twitter/X API credits are running low or exhausted. "
        "Posts are failing.\n\n"
        "Add credits at: https://developer.twitter.com/en/portal/dashboard\n\n"
        f"Error detail: {error_detail}\n\n"
        "- GHE Automation"
    )
    try:
        r = _req.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {sendgrid_key}",
                     "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": sender_email}]}],
                "from": {"email": sender_email, "name": "GHE Automation"},
                "subject": "ACTION NEEDED: Twitter credits running low",
                "content": [{"type": "text/plain", "value": body}],
            }, timeout=10,
        )
        if r.status_code in (200, 202):
            ALERT_FLAG.write_text("alert sent")
            print("[TWITTER ALERT] Credit alert emailed to", sender_email)
    except Exception as ex:
        print(f"[TWITTER ALERT] Failed to send alert: {ex}")


# ─── Auto-Follow ──────────────────────────────────────────────────────────────

FOLLOW_LOG = DATA_DIR / "twitter_follows.json"


def _load_followed() -> set:
    if FOLLOW_LOG.exists():
        try:
            return set(json.loads(FOLLOW_LOG.read_text()).get("followed", []))
        except Exception:
            pass
    return set()


def _save_followed(followed: set):
    FOLLOW_LOG.write_text(json.dumps({"followed": list(followed)}, indent=2))


def auto_follow_accounts(max_follows: int = 20) -> int:
    """
    Follow trading/finance/small-biz accounts to grow our audience.
    Caps at max_follows per run (~20/day is safe on free tier).
    Returns count of new follows.
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return 0

    from requests_oauthlib import OAuth1
    oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
    my_id = TWITTER_ACCESS_TOKEN.split("-")[0]  # user ID is before the dash

    followed = _load_followed()
    new_follows = 0

    try:
        query = random.choice(TRENDING_SEARCH_TERMS) + " -is:retweet lang:en"
        r = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params={"query": query, "max_results": 10, "expansions": "author_id", "user.fields": "id,username"},
            auth=oauth, timeout=15,
        )
        if r.status_code != 200:
            print(f"[TWITTER FOLLOW] Search error {r.status_code}: {r.text[:100]}")
        else:
            data = r.json()
            users = data.get("includes", {}).get("users", [])
            random.shuffle(users)
            for user in users:
                if new_follows >= max_follows:
                    break
                uid = str(user["id"])
                if uid in followed:
                    continue
                try:
                    fr = requests.post(
                        f"https://api.twitter.com/2/users/{my_id}/following",
                        json={"target_user_id": uid},
                        auth=oauth, timeout=15,
                    )
                    if fr.status_code in (200, 201):
                        followed.add(uid)
                        new_follows += 1
                        print(f"  [TWITTER FOLLOW] +followed @{user.get('username','?')}")
                        time.sleep(random.uniform(3, 6))
                    elif fr.status_code == 429:
                        print("  [TWITTER FOLLOW] Rate limit — stopping")
                        break
                    else:
                        print(f"  [TWITTER FOLLOW] Skip {uid}: {fr.status_code}")
                except Exception as fe:
                    print(f"  [TWITTER FOLLOW] Error: {fe}")
    except Exception as e:
        print(f"[TWITTER FOLLOW] Error: {e}")

    _save_followed(followed)
    print(f"[TWITTER FOLLOW] {new_follows} new follows (total tracked: {len(followed)})")
    return new_follows


# ─── Comment Suggestions ──────────────────────────────────────────────────────

SUGGESTIONS_FILE = DATA_DIR / "twitter_comment_suggestions.json"


def fetch_comment_suggestions() -> list:
    """
    Search for high-engagement finance/trading tweets and generate smart
    comment suggestions. Saved to twitter_comment_suggestions.json for
    the dashboard to display.
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return []
    try:
        import tweepy
    except ImportError:
        return []

    suggestions = []
    from requests_oauthlib import OAuth1
    oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)

    for term in random.sample(TRENDING_SEARCH_TERMS, min(3, len(TRENDING_SEARCH_TERMS))):
        try:
            query = f"{term} -is:retweet lang:en min_faves:10"
            r = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": query, "max_results": 10,
                    "tweet.fields": "public_metrics,author_id,text",
                    "expansions": "author_id", "user.fields": "username",
                },
                auth=oauth, timeout=15,
            )
            if r.status_code != 200:
                print(f"[TWITTER SUGGEST] {r.status_code} for '{term}'")
                continue
            data = r.json()
            tweets = data.get("data", [])
            users_map = {str(u["id"]): u.get("username", "unknown")
                         for u in data.get("includes", {}).get("users", [])}

            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                likes    = metrics.get("like_count", 0)
                retweets = metrics.get("retweet_count", 0)
                author   = users_map.get(str(tweet.get("author_id", "")), "unknown")
                topic    = term.replace("today", "").strip()
                comment  = random.choice(COMMENT_TEMPLATES).replace("{topic}", topic).replace("{ticker}", "this")
                suggestions.append({
                    "tweet_id":          str(tweet["id"]),
                    "tweet_text":        tweet["text"][:200],
                    "author":            author,
                    "likes":             likes,
                    "retweets":          retweets,
                    "tweet_url":         f"https://twitter.com/{author}/status/{tweet['id']}",
                    "suggested_comment": comment,
                    "fetched_at":        datetime.utcnow().isoformat(),
                })
        except Exception as e:
            print(f"[TWITTER SUGGEST] Error for '{term}': {e}")
        time.sleep(2)

    # Sort by engagement
    suggestions.sort(key=lambda x: x["likes"] + x["retweets"] * 3, reverse=True)
    top = suggestions[:10]

    SUGGESTIONS_FILE.write_text(json.dumps(top, indent=2))
    print(f"[TWITTER SUGGEST] {len(top)} comment opportunities saved")
    return top


def post_comment(tweet_id: str, comment_text: str) -> bool:
    """Reply to a specific tweet with comment_text. Called from dashboard."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return False
    try:
        from requests_oauthlib import OAuth1
        oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            json={"text": comment_text[:280], "reply": {"in_reply_to_tweet_id": tweet_id}},
            auth=oauth, timeout=15,
        )
        if r.status_code in (200, 201):
            print(f"  [TWITTER COMMENT] Posted reply to {tweet_id}")
            return True
        print(f"  [TWITTER COMMENT] Failed {r.status_code}: {r.text[:100]}")
        return False
    except Exception as e:
        print(f"  [TWITTER COMMENT] Failed: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    print("[TWITTER] Starting daily post cycle...")

    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("[TWITTER] Not configured. To activate:")
        print("  1. Go to developer.twitter.com → Create App")
        print("  2. Set permissions to 'Read and Write'")
        print("  3. Generate API Key, API Secret, Access Token, Access Token Secret")
        print("  4. Add to Railway env vars:")
        print("     TWITTER_API_KEY / TWITTER_API_SECRET / TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET")
        print("\n[TWITTER] Printing today's posts (would post when keys are set):")
        posted = load_posted()
        for category, _ in DAILY_SCHEDULE:
            text = pick_post(category, posted)
            print(f"\n  [{category.upper()}]")
            print("  " + text.replace("\n", "\n  "))
        save_posted(posted)
        return

    posted  = load_posted()
    sent    = 0

    for category, scheduled_time in DAILY_SCHEDULE:
        text = pick_post(category, posted)
        print(f"\n[{category.upper()}] Posting...")
        ok = post_tweet(text)
        if ok:
            sent += 1
        time.sleep(random.uniform(60, 180))  # space posts out to avoid rate limits

    save_posted(posted)
    print(f"\n[TWITTER] Done — {sent}/{len(DAILY_SCHEDULE)} posts sent today")

    # Auto-follow relevant accounts to grow audience (20/run, safe for free tier)
    try:
        auto_follow_accounts(max_follows=20)
    except Exception as e:
        print(f"[TWITTER] Follow error (non-fatal): {e}")

    # Fetch comment opportunities for dashboard display
    try:
        fetch_comment_suggestions()
    except Exception as e:
        print(f"[TWITTER] Suggestion fetch error (non-fatal): {e}")


if __name__ == "__main__":
    run()
