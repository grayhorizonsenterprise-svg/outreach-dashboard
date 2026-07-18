"""
twitter_engage.py — Gray Horizons Enterprise
Aggressive FinTwit growth engine. Runs every hour via Task Scheduler.

STRATEGY (in order of priority):
  1. Reply to posts from high-follower trading accounts — gets GHE visible
     to audiences of 100K-2M+ followers in the exact niche (FinTwit/CongressTrades)
  2. Like and quote-note trending congressional trade / signal posts
  3. Follow accounts that engage with the target community
  4. Reply to @GEnterprise6470 mentions
  5. Reply to comments on own posts

TARGET ACCOUNTS (reply to their recent posts within 2h for max visibility):
  unusual_whales: 2M+ followers, congressional trades, options flow
  QuiverQuant:    institutional + congressional data
  TradingView:    official TV account, massive trading audience
  senatestockwatcher: congressional trade tracking
  RaynerTeo:      TradingView educator, 500K+ following
  tastytrade:     options education, active trader community
  zerohedge:      macro + market commentary
  StockMarket:    broad market audience

PLATFORM RULE: X/Twitter = Edge Engine trading content ONLY.
               No business, no GHL, no contractor content. Ever.
"""

import os
import sys
import json
import time
import random
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

DATA_DIR     = Path(os.path.dirname(os.path.abspath(__file__)))
ENGAGE_LOG   = DATA_DIR / "twitter_engage_log.json"
CREDITS_LOG  = DATA_DIR / "twitter_credits.json"   # shared with twitter_poster.py

GHE_HANDLE   = "GEnterprise6470"
SIGNALS_LINK = os.getenv("SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
WHOP_LINK    = os.getenv("WHOP_INDICATORS_LINK", "https://whop.com/gray-horizons-enterprise/ghe-indicator-suite/")

# ── Write budget ───────────────────────────────────────────────────────────────
# Every posted tweet / reply costs 1 write credit.
# Liking and following are GET/POST to different endpoints — they do NOT count
# against the tweet write quota. Only actual tweet creation burns credits.
#
# Budget split:
#   twitter_poster.py:  4 posts/day (chart, signals, results, engagement)
#   twitter_engage.py:  DAILY_ENGAGE_BUDGET replies/day max
#
# Total across both scripts must stay under MONTHLY_WRITE_BUDGET / 30 per day.
# X Basic plan: 3,000 writes/month = 100/day max.
# We stay at 10/day total (4 poster + 6 engage) to leave headroom.

MONTHLY_WRITE_BUDGET = int(os.getenv("TWITTER_MONTHLY_BUDGET", "3000"))
DAILY_POSTER_RESERVE = 1    # 1 post/day — BUDGET MODE ($0.94 remaining this cycle)
DAILY_ENGAGE_BUDGET  = 0    # replies DISABLED — likes/follows only (free API calls)


def _credits_used_today() -> int:
    """Return total write credits used today across poster + engage."""
    try:
        data = json.loads(CREDITS_LOG.read_text()) if CREDITS_LOG.exists() else {}
        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        return data.get(day_key, 0)
    except Exception:
        return 0


def _credits_used_month() -> int:
    try:
        data = json.loads(CREDITS_LOG.read_text()) if CREDITS_LOG.exists() else {}
        month_key = datetime.utcnow().strftime("%Y-%m")
        return data.get(month_key, 0)
    except Exception:
        return 0


def _log_credit(n: int = 1):
    """Record n write credits used by the engage script."""
    try:
        data = json.loads(CREDITS_LOG.read_text()) if CREDITS_LOG.exists() else {}
        day_key   = datetime.utcnow().strftime("%Y-%m-%d")
        month_key = datetime.utcnow().strftime("%Y-%m")
        data[day_key]   = data.get(day_key, 0) + n
        data[month_key] = data.get(month_key, 0) + n
        CREDITS_LOG.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _engage_budget_remaining() -> int:
    """How many reply credits the engage script can still use today."""
    used_today = _credits_used_today()
    # Poster reserves DAILY_POSTER_RESERVE; engage gets DAILY_ENGAGE_BUDGET on top
    engage_used = max(0, used_today - DAILY_POSTER_RESERVE)
    return max(0, DAILY_ENGAGE_BUDGET - engage_used)

# ── High-value target accounts to reply to ────────────────────────────────────
# These are the accounts whose reply sections = free exposure to ideal audience.
# Priority: unusual_whales and QuiverQuant for congressional angle (our hook).
# Replies show up in their thread and get seen by their follower base.

TARGET_REPLY_ACCOUNTS = [
    # Congressional trade angle — our strongest hook
    "unusual_whales",       # 2M+ followers, congressional + options flow
    "QuiverQuant",          # institutional + congressional data platform
    "senatestockwatcher",   # dedicated congressional tracker
    "HouseStockWatcher",    # House-specific tracker
    # Trading education — large active audiences
    "TradingView",          # official TradingView account
    "tastytrade",           # active trader community, options focus
    "RaynerTeo",            # TradingView educator, 500K+
    "Investopedia",         # broad finance, high engagement
    # Market commentary — FinTwit mainstream
    "zerohedge",            # macro + bearish commentary, very active
    "MarketWatch",          # mainstream finance news
    "SquawkCNBC",           # CNBC traders, active audience
    # Niche signal / scanner community
    "OptionsFlow",          # options flow alerts
    "unusual_activity_",    # options flow tracking
    "StockMoe",             # retail trader with large following
]

# Accounts to follow (do NOT follow back every random account — target these)
TARGET_FOLLOW_ACCOUNTS = [
    "unusual_whales",
    "QuiverQuant",
    "senatestockwatcher",
    "HouseStockWatcher",
    "TradingView",
    "tastytrade",
    "RaynerTeo",
    "OptionsFlow",
    "Investopedia",
    "zerohedge",
    "StockMoe",
    "SquawkCNBC",
    "MarketWatch",
]

# ── Reply pools — context-aware, trading only, no links in replies ─────────────

# Used when replying to congressional trade posts from target accounts
CONGRESSIONAL_REPLIES = [
    "The volume pattern shows up on the chart within the first week of the trade. The disclosure comes on day 45. Most retail traders learn about it on day 50 from a news article.",
    "45 days to report. The chart does not wait 45 days. Volume anomaly is visible in week 1 every single quarter.",
    "Congress has a 45-day disclosure window. The volume spike shows up in days 3-7. That gap between day 4 and day 45 is the entire edge.",
    "Every quarter. Same pattern. Volume moves before the disclosure goes public. Retail buys the top after the article drops.",
    "The congressional tracker flags volume anomalies before disclosure. Not predicting. Just reading what the chart already shows.",
    "Institutional accumulation shows before disclosure. Volume does not lie. The chart has it on day 4. The SEC filing has it on day 45.",
    "Legal, documented, and trackable. The volume pattern shows on the chart before the 45-day window closes. Most traders miss the entire setup.",
]

# Used when replying to options flow / unusual activity posts
OPTIONS_FLOW_REPLIES = [
    "Volume anomaly shows up on the chart 4-6 days before the move confirms. By the time the flow report hits, the position is already sized.",
    "Unusual volume before price moves is the tell. Congressional flow adds a second confirmation. When both align on the same ticker the score hits 75+.",
    "This is exactly the pattern. Volume front-runs price. Score the setup 0-100, only act on 70 and above. Everything else is noise.",
    "Options flow and congressional timing overlap more than most people realize. Same accumulation pattern. Same volume signature before price.",
    "Institutional flow shows in volume before price confirms. Retail buys the breakout. The entry at the volume spike is the actual edge.",
]

# Used when replying to TradingView / indicator posts
INDICATOR_REPLIES = [
    "RSI alone is noise. Volume alone is noise. EMA alone is noise. All three on the same bar is a signal. Scoring them 0-100 removes the interpretation entirely.",
    "Repainted signals are not signals. If it does not lock on bar close it is just a story told in hindsight. Separate issue from most people's setups.",
    "The scoring removes discretion. 0-100 per bar based on RSI, volume anomaly, and EMA alignment. Score 70 or above: look. Below 70: skip. Simple rule.",
    "The number of indicators does not matter. What matters is whether they measure different things. RSI is momentum. Volume is participation. EMA is trend. That is all you need.",
    "Alert fatigue is a real account killer. 200 signals a day trains you to ignore alerts. 3-5 scored setups above 70 trains you to act on edges.",
]

# Used when replying to general market / trading posts
MARKET_REPLIES = [
    "Position sizing is where most accounts die. Not the picks. A 60 percent win rate with 10 percent risk per trade still blows up. Kelly math fixes that.",
    "The pre-market window is where the trade is made. By open, the order should already be sized and placed. No scrambling, no reacting.",
    "Retail traders average 3.7 percent annual return. The S&P averages 10.4 percent over 30 years. The gap is not the picks. It is impulsive entries and bad position sizing.",
    "Boring trading is good trading. One scored setup. Sized correctly. Held until target or stop. No FOMO. No overtrading. That is the whole game.",
    "Most traders spend 90 percent of their time picking stocks. Institutional desks spend 90 percent on timing and sizing. Same stock. Different outcome.",
    "Volume is institutional. Price is retail. When volume moves without price, someone knows something. When price moves without volume, it will not hold.",
    "The best trade is the one where the setup, the timing, and the position size all make sense before you enter. Not after. Before.",
]

def pick_reply(text_lower: str) -> str:
    if any(w in text_lower for w in ["congress", "pelosi", "disclosure", "senator", "tuberville", "representative", "stock act", "house", "senate"]):
        return random.choice(CONGRESSIONAL_REPLIES)
    if any(w in text_lower for w in ["options flow", "unusual", "dark pool", "sweep", "call", "put", "flow alert"]):
        return random.choice(OPTIONS_FLOW_REPLIES)
    if any(w in text_lower for w in ["rsi", "ema", "tradingview", "indicator", "scanner", "pine script", "backtest", "macd"]):
        return random.choice(INDICATOR_REPLIES)
    return random.choice(MARKET_REPLIES)


# ── Search queries for liking trending posts ───────────────────────────────────
LIKE_SEARCH_TERMS = [
    "congress stock trade disclosure -is:retweet lang:en",
    "congressional trades stocks -is:retweet lang:en",
    "unusual options flow alert -is:retweet lang:en",
    "volume anomaly stocks setup -is:retweet lang:en",
    "TradingView setup RSI breakout -is:retweet lang:en",
    "position sizing Kelly criterion trading -is:retweet lang:en",
    "institutional flow stocks signal -is:retweet lang:en",
    "stock market pre market setup -is:retweet lang:en",
    "momentum score trading signal -is:retweet lang:en",
    "congressional stock watcher -is:retweet lang:en",
]

MAX_LOG_ENTRIES = 800   # prune liked/replied lists to avoid log bloat


# ── API helpers ────────────────────────────────────────────────────────────────

def _oauth():
    from requests_oauthlib import OAuth1
    return OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET,
                  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)


def _has_creds() -> bool:
    return all([TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET])


def load_log() -> dict:
    if ENGAGE_LOG.exists():
        try:
            return json.loads(ENGAGE_LOG.read_text())
        except Exception:
            pass
    return {"replied_to": [], "liked": [], "followed": [], "my_user_id": ""}


def save_log(log: dict):
    # Prune to prevent log from growing unboundedly
    log["liked"]      = list(log.get("liked", []))[-MAX_LOG_ENTRIES:]
    log["replied_to"] = list(log.get("replied_to", []))[-MAX_LOG_ENTRIES:]
    ENGAGE_LOG.write_text(json.dumps(log, indent=2))


def get_my_user_id(log: dict) -> str:
    if log.get("my_user_id"):
        return log["my_user_id"]
    try:
        r = requests.get("https://api.twitter.com/2/users/me", auth=_oauth(), timeout=15)
        if r.status_code == 200:
            uid = r.json().get("data", {}).get("id", "")
            log["my_user_id"] = uid
            return uid
    except Exception as e:
        print(f"[X ENGAGE] get_my_user_id error: {e}")
    return ""


def get_user_id_by_handle(handle: str) -> str:
    try:
        r = requests.get(
            f"https://api.twitter.com/2/users/by/username/{handle}",
            auth=_oauth(), timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("id", "")
    except Exception:
        pass
    return ""


def follow_user(my_user_id: str, target_user_id: str) -> bool:
    try:
        r = requests.post(
            f"https://api.twitter.com/2/users/{my_user_id}/following",
            json={"target_user_id": target_user_id},
            auth=_oauth(), timeout=15,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[X FOLLOW] Error: {e}")
        return False


def like_tweet(tweet_id: str, user_id: str) -> bool:
    try:
        r = requests.post(
            f"https://api.twitter.com/2/users/{user_id}/likes",
            json={"tweet_id": tweet_id},
            auth=_oauth(), timeout=15,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[X LIKE] Error: {e}")
        return False


def post_reply(text: str, reply_to_id: str) -> bool:
    try:
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            json={"text": text[:280], "reply": {"in_reply_to_tweet_id": reply_to_id}},
            auth=_oauth(), timeout=15,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[X REPLY] Error: {e}")
        return False


def get_user_recent_tweets(user_id: str, max_results: int = 5, within_hours: int = 3) -> list[dict]:
    """Get the most recent tweets from a user, only within the last N hours."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            params={
                "max_results": max_results,
                "start_time": since,
                "tweet.fields": "public_metrics,created_at,text",
                "exclude": "retweets,replies",
            },
            auth=_oauth(), timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        print(f"[X USER TWEETS] Error: {e}")
    return []


def get_mentions(user_id: str, since_hours: int = 6) -> list[dict]:
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/mentions",
            params={
                "max_results": 20,
                "start_time": since,
                "tweet.fields": "author_id,text,conversation_id",
            },
            auth=_oauth(), timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        print(f"[X MENTIONS] Error: {e}")
    return []


def get_my_recent_tweets(user_id: str, max_results: int = 10) -> list[dict]:
    try:
        r = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            params={
                "max_results": max_results,
                "tweet.fields": "public_metrics,conversation_id",
                "exclude": "retweets,replies",
            },
            auth=_oauth(), timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        print(f"[X MY TWEETS] Error: {e}")
    return []


def get_replies_to_tweet(conv_id: str) -> list[dict]:
    try:
        r = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params={
                "query": f"conversation_id:{conv_id} is:reply -from:{GHE_HANDLE}",
                "max_results": 10,
                "tweet.fields": "author_id,text",
            },
            auth=_oauth(), timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        print(f"[X REPLIES] Error: {e}")
    return []


# ── Core engagement functions ──────────────────────────────────────────────────

def reply_to_target_accounts(user_id: str, log: dict, max_replies: int = 4) -> int:
    """
    The #1 growth driver: reply to recent posts from high-follower accounts.
    Our reply shows in their thread = free exposure to their audience (100K-2M+).
    Only reply to posts within the last 3 hours for maximum visibility.
    Budget-gated: each reply costs 1 write credit.
    """
    budget = _engage_budget_remaining()
    if budget <= 0:
        print(f"  [X TARGET] Daily engage budget exhausted — skipping replies")
        return 0
    max_replies = min(max_replies, budget)

    replied = 0
    replied_set = set(log.get("replied_to", []))

    # Shuffle so we don't always hit the same account first
    accounts = list(TARGET_REPLY_ACCOUNTS)
    random.shuffle(accounts)

    for handle in accounts:
        if replied >= max_replies:
            break

        target_uid = get_user_id_by_handle(handle)
        if not target_uid:
            print(f"  [X TARGET] Could not resolve @{handle} — skipping")
            time.sleep(1)
            continue

        recent_tweets = get_user_recent_tweets(target_uid, max_results=3, within_hours=3)
        if not recent_tweets:
            print(f"  [X TARGET] @{handle}: no posts in last 3h")
            time.sleep(1)
            continue

        # Pick the most-engaged recent tweet
        recent_tweets.sort(
            key=lambda t: t.get("public_metrics", {}).get("like_count", 0) +
                          t.get("public_metrics", {}).get("retweet_count", 0) * 3,
            reverse=True,
        )
        tweet = recent_tweets[0]
        tid = str(tweet["id"])

        if tid in replied_set:
            print(f"  [X TARGET] @{handle}: already replied to {tid}")
            continue

        text_lower = tweet.get("text", "").lower()
        reply_text = pick_reply(text_lower)

        ok = post_reply(reply_text, tid)
        if ok:
            replied_set.add(tid)
            replied += 1
            _log_credit(1)
            print(f"  [X TARGET REPLY] @{handle} tweet {tid}: {reply_text[:70]}...")
            time.sleep(random.uniform(20, 40))
        else:
            print(f"  [X TARGET REPLY FAIL] @{handle} tweet {tid}")
            time.sleep(5)

    log["replied_to"] = list(replied_set)
    return replied


def follow_target_accounts(my_user_id: str, log: dict, max_follows: int = 3) -> int:
    """
    Follow the high-value target accounts that are not already followed.
    Targeted follows only — not bulk following randoms.
    Max 3 per run to stay well within API limits.
    """
    followed = set(log.get("followed", []))
    count = 0

    not_yet_followed = [h for h in TARGET_FOLLOW_ACCOUNTS if h not in followed]
    random.shuffle(not_yet_followed)

    for handle in not_yet_followed[:max_follows]:
        target_uid = get_user_id_by_handle(handle)
        if not target_uid:
            continue
        ok = follow_user(my_user_id, target_uid)
        if ok:
            followed.add(handle)
            count += 1
            print(f"  [X FOLLOW] @{handle}")
            time.sleep(random.uniform(5, 10))

    log["followed"] = list(followed)
    return count


def search_and_like_trending(user_id: str, log: dict, max_likes: int = 12) -> int:
    """Like recent high-engagement trading posts in the target niche."""
    liked = 0
    liked_set = set(log.get("liked", []))

    # Use 2 different queries per run to hit more of the community
    queries = random.sample(LIKE_SEARCH_TERMS, min(2, len(LIKE_SEARCH_TERMS)))

    for query in queries:
        if liked >= max_likes:
            break
        try:
            r = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": query,
                    "max_results": 15,
                    "tweet.fields": "public_metrics,author_id",
                },
                auth=_oauth(), timeout=15,
            )
            if r.status_code != 200:
                print(f"  [X LIKE SEARCH] {r.status_code}: {r.text[:80]}")
                continue

            tweets = r.json().get("data", [])
            # Sort by engagement — like the posts gaining traction
            tweets.sort(
                key=lambda t: t.get("public_metrics", {}).get("like_count", 0) +
                              t.get("public_metrics", {}).get("retweet_count", 0) * 2,
                reverse=True,
            )

            for tweet in tweets:
                if liked >= max_likes:
                    break
                tid = str(tweet["id"])
                if tid in liked_set:
                    continue
                if tweet.get("author_id") == user_id:
                    continue

                ok = like_tweet(tid, user_id)
                if ok:
                    liked_set.add(tid)
                    liked += 1
                    print(f"  [X LIKED] {tid} | {query[:45]}")
                    time.sleep(random.uniform(2, 4))
                else:
                    time.sleep(2)
        except Exception as e:
            print(f"  [X LIKE SEARCH] Error: {e}")

    log["liked"] = list(liked_set)
    return liked


def process_mentions(user_id: str, log: dict, max_replies: int = 3) -> int:
    """Reply to recent @mentions of our account. Budget-gated."""
    budget = _engage_budget_remaining()
    if budget <= 0:
        print("  [X MENTIONS] Budget exhausted — skipping")
        return 0
    max_replies = min(max_replies, budget)

    replied = 0
    replied_set = set(log.get("replied_to", []))
    mentions = get_mentions(user_id, since_hours=12)

    if not mentions:
        print("[X ENGAGE] No new mentions in last 12h")
        return 0

    print(f"[X ENGAGE] Found {len(mentions)} recent mentions")
    for mention in mentions:
        if replied >= max_replies:
            break
        tid = str(mention["id"])
        if tid in replied_set:
            continue
        text_lower = mention.get("text", "").lower()
        if len(text_lower.strip()) < 20:
            continue

        reply_text = pick_reply(text_lower)
        ok = post_reply(reply_text, tid)
        if ok:
            replied_set.add(tid)
            replied += 1
            _log_credit(1)
            print(f"  [X REPLIED] mention {tid}: {reply_text[:60]}...")
            time.sleep(random.uniform(15, 25))

    log["replied_to"] = list(replied_set)
    return replied


def process_post_replies(user_id: str, log: dict, max_replies: int = 2) -> int:
    """Reply to comments on own tweets — nurture engagement. Budget-gated."""
    budget = _engage_budget_remaining()
    if budget <= 0:
        print("  [X POST REPLIES] Budget exhausted — skipping")
        return 0
    max_replies = min(max_replies, budget)

    replied = 0
    replied_set = set(log.get("replied_to", []))
    my_tweets = get_my_recent_tweets(user_id, max_results=5)

    for tweet in my_tweets:
        if replied >= max_replies:
            break
        conv_id = tweet.get("conversation_id", str(tweet["id"]))
        replies = get_replies_to_tweet(conv_id)

        for reply in replies:
            if replied >= max_replies:
                break
            rid = str(reply["id"])
            if rid in replied_set:
                continue
            text_lower = reply.get("text", "").lower()
            response = pick_reply(text_lower)
            ok = post_reply(response, rid)
            if ok:
                replied_set.add(rid)
                replied += 1
                _log_credit(1)
                print(f"  [X REPLIED TO REPLY] {rid}: {response[:60]}...")
                time.sleep(random.uniform(15, 25))

    log["replied_to"] = list(replied_set)
    return replied


# ── Main ──────────────────────────────────────────────────────────────────────

def run(max_replies: int = 5, max_likes: int = 12, max_follows: int = 3):
    print("[X ENGAGE] PLATFORM RULE: Edge Engine trading content ONLY on X. No business/GHL content.")

    if not _has_creds():
        print("[X ENGAGE] Missing Twitter credentials — skipping")
        return

    log     = load_log()
    user_id = get_my_user_id(log)
    if not user_id:
        print("[X ENGAGE] Could not get user ID — check credentials")
        save_log(log)
        return

    replied_count  = len(log.get("replied_to", []))
    liked_count    = len(log.get("liked", []))
    followed_count = len(log.get("followed", []))
    used_today     = _credits_used_today()
    used_month     = _credits_used_month()
    engage_left    = _engage_budget_remaining()
    print(f"[X ENGAGE] @{GHE_HANDLE} | Replied: {replied_count} | Liked: {liked_count} | Followed: {followed_count}")
    print(f"[X ENGAGE] BUDGET: {used_today} used today | {used_month}/{MONTHLY_WRITE_BUDGET} this month | {engage_left} engage credits left today")
    if engage_left == 0:
        print("[X ENGAGE] Daily engage budget exhausted. Likes and follows only (free). No replies.")
    elif engage_left <= 2:
        print(f"[X ENGAGE] WARNING: Only {engage_left} reply credit(s) left today — being conservative.")

    # 1. HIGHEST PRIORITY: reply to posts from big FinTwit accounts
    #    This is the #1 growth driver — gets GHE visible to 100K-2M+ audiences
    print("\n[X ENGAGE] Step 1: Reply to target account posts (growth priority)")
    target_replies = reply_to_target_accounts(user_id, log, max_replies=max_replies)
    print(f"[X ENGAGE] Replied to {target_replies} target account posts")
    time.sleep(3)

    # 2. Follow target accounts not yet followed
    print("\n[X ENGAGE] Step 2: Follow high-value target accounts")
    follows = follow_target_accounts(user_id, log, max_follows=max_follows)
    if follows:
        print(f"[X ENGAGE] Followed {follows} new accounts")
    else:
        print("[X ENGAGE] All target accounts already followed")
    time.sleep(3)

    # 3. Like trending trading posts in the community
    print("\n[X ENGAGE] Step 3: Like trending trading posts")
    likes = search_and_like_trending(user_id, log, max_likes)
    print(f"[X ENGAGE] Liked {likes} trending posts")
    time.sleep(3)

    # 4. Reply to @mentions of GHE account
    print("\n[X ENGAGE] Step 4: Reply to @mentions")
    mentions_replied = process_mentions(user_id, log, max_replies=3)
    print(f"[X ENGAGE] Replied to {mentions_replied} mentions")
    time.sleep(3)

    # 5. Reply to comments on own posts
    print("\n[X ENGAGE] Step 5: Reply to comments on own posts")
    post_replies = process_post_replies(user_id, log, max_replies=3)
    print(f"[X ENGAGE] Replied to {post_replies} comments on own posts")

    save_log(log)
    print(f"\n[X ENGAGE] Done — target replies: {target_replies} | likes: {likes} | follows: {follows}")


if __name__ == "__main__":
    run()
