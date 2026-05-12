"""
reddit_monitor.py — GHE Indicator Suite promotion engine
Monitors Reddit for trading indicator discussions and queues reply drafts.

Setup:
1. pip install praw
2. Create a Reddit app at https://www.reddit.com/prefs/apps (script type)
3. Set env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_USERNAME, REDDIT_PASSWORD
4. Set WHOP_URL env var to your Whop listing URL
5. Run: python reddit_monitor.py
"""

import praw
import os
import json
import time
from datetime import datetime, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────
REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "GHE_Monitor/1.0")
REDDIT_USERNAME      = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD      = os.getenv("REDDIT_PASSWORD", "")
WHOP_URL             = os.getenv("WHOP_URL", "https://whop.com/your-listing")

QUEUE_FILE = "reddit_reply_queue.json"
LOG_FILE   = "reddit_monitor_log.txt"

# Subreddits to monitor
TARGET_SUBS = [
    "algotrading",
    "TradingView",
    "Daytrading",
    "stocks",
    "wallstreetbets",
    "investing",
    "StockMarket",
    "options",
    "Forex",
    "CryptoCurrency",
]

# Keywords that indicate someone is looking for indicators/tools
TRIGGER_KEYWORDS = [
    "tradingview indicator",
    "pine script",
    "best indicator",
    "momentum indicator",
    "position sizing",
    "kelly criterion",
    "volume indicator",
    "congress trading",
    "congressional trading",
    "how to size positions",
    "how many shares",
    "signal indicator",
    "entry indicator",
    "what indicator",
    "recommend indicator",
    "good indicator",
    "indicator for",
    "looking for indicator",
]

# Reply templates — varied to avoid spam detection
REPLY_TEMPLATES = [
    """Good timing on this question — we just released a suite that handles exactly this.

The GHE Edge Scanner scores every bar 0-100 using RSI, volume surge (>2× avg), and EMA confluence. Only labels the 70+ setups. Dramatically less noise.

Also comes with a Kelly Criterion position sizer and a Congressional Trade Tracker.

$49/month or $79 lifetime: {url}

Not trying to spam — genuinely think the position sizer alone is worth it for anyone doing real size.""",

    """The volume component is what most indicators miss.

We built one that requires volume > 2× the 20-bar average before any signal fires — institutional participation threshold. Pairs it with RSI range (45-70 for longs) and EMA crossover.

Scores 0-100 on every bar. You only act on 70+.

Full suite (3 indicators) here if useful: {url}""",

    """Kelly Criterion with Quarter-Kelly fractional sizing. That's the institutional standard.

We built it into a TradingView indicator — input your account size, win rate, and stop %, it outputs exact share count in real time.

Part of a 3-indicator suite we sell. Congressional Trade Tracker is the other interesting one.

{url} — $79 one-time if you want it pre-built.""",

    """The congressional trading angle is underrated.

There's a 45-day disclosure window where unusual volume accumulation happens before the trade goes public. Built a TradingView indicator that flags these patterns (volume anomaly + price movement threshold).

Works best on daily charts for names congress has been active in.

Full suite here: {url}""",
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []


def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)


def load_seen_ids():
    seen_file = "reddit_seen_ids.json"
    if os.path.exists(seen_file):
        with open(seen_file, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen):
    with open("reddit_seen_ids.json", "w") as f:
        json.dump(list(seen), f)


def contains_trigger(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in TRIGGER_KEYWORDS)


def pick_reply(index=0):
    template = REPLY_TEMPLATES[index % len(REPLY_TEMPLATES)]
    return template.format(url=WHOP_URL)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def run():
    if not REDDIT_CLIENT_ID:
        print("ERROR: Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD env vars.")
        print("Create a Reddit app at: https://www.reddit.com/prefs/apps")
        return

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
    )

    seen_ids = load_seen_ids()
    queue    = load_queue()
    template_idx = 0

    log(f"Starting Reddit monitor. Watching {len(TARGET_SUBS)} subreddits.")
    log(f"Whop URL: {WHOP_URL}")

    while True:
        try:
            for sub_name in TARGET_SUBS:
                sub = reddit.subreddit(sub_name)

                # Scan new posts
                for post in sub.new(limit=25):
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)

                    text = (post.title + " " + post.selftext).lower()
                    if contains_trigger(text):
                        reply_text = pick_reply(template_idx)
                        template_idx += 1

                        item = {
                            "type":        "post",
                            "id":          post.id,
                            "subreddit":   sub_name,
                            "title":       post.title[:100],
                            "url":         f"https://reddit.com{post.permalink}",
                            "reply_draft": reply_text,
                            "queued_at":   datetime.now().isoformat(),
                            "posted":      False,
                        }
                        queue.append(item)
                        log(f"QUEUED POST reply: r/{sub_name} — {post.title[:60]}")

                # Scan new comments
                for comment in sub.comments(limit=50):
                    if comment.id in seen_ids:
                        continue
                    seen_ids.add(comment.id)

                    if contains_trigger(comment.body):
                        reply_text = pick_reply(template_idx)
                        template_idx += 1

                        item = {
                            "type":        "comment",
                            "id":          comment.id,
                            "subreddit":   sub_name,
                            "body":        comment.body[:150],
                            "url":         f"https://reddit.com{comment.permalink}",
                            "reply_draft": reply_text,
                            "queued_at":   datetime.now().isoformat(),
                            "posted":      False,
                        }
                        queue.append(item)
                        log(f"QUEUED COMMENT reply: r/{sub_name} — {comment.body[:60]}")

                time.sleep(2)  # avoid rate limits between subs

            save_queue(queue)
            save_seen_ids(seen_ids)

            pending = [q for q in queue if not q["posted"]]
            log(f"Scan complete. {len(pending)} replies queued and waiting for review.")

            # Sleep 15 minutes between full scans
            time.sleep(900)

        except KeyboardInterrupt:
            log("Stopped by user.")
            break
        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(60)


if __name__ == "__main__":
    run()
