"""
linkedin_poster.py — Gray Horizons Enterprise
Posts daily content to LinkedIn using the official API.
Posts 1x/day: alternates between signals pitch, AI automation pitch, indicators pitch.

Setup (one time, 10 minutes):
  1. Go to linkedin.com/developers → Create app
  2. Add "Share on LinkedIn" product to your app
  3. Go to OAuth tools → Generate access token with scope: w_member_social,r_liteprofile
  4. Copy the access token
  5. Add to Railway: LINKEDIN_ACCESS_TOKEN=<token>

Token lasts 60 days — regenerate monthly.
"""

import requests
import os
import sys
import json
import random
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR     = Path(os.path.dirname(os.path.abspath(__file__)))
POSTED_FILE  = DATA_DIR / "linkedin_posted.json"
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
SIGNALS_LINK = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
INDICATORS_LINK = os.getenv("INDICATORS_LINK", "https://horizons56.gumroad.com/l/ghe-indicators")
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/grayhorizonsenterprise")

POSTS = [
    # Signals pitch
    f"""Most traders react to the market.

Edge Engine subscribers see it before it moves.

We track 3 things every morning before 8am:
- Congressional disclosure patterns (45-day window)
- Volume anomalies vs 20-day average
- RSI + EMA momentum scores (0-100)

You only act on setups scored 70+.

$49/month. Every morning before open.

{SIGNALS_LINK}""",

    # AI automation pitch
    f"""Most small businesses lose 30% of inbound leads to voicemail.

The customer doesn't leave a message.
They call the next result on Google.

We build AI systems that answer, qualify, and follow up automatically — 24/7.

One system. One week to build. Pays for itself in the first closed deal.

If you're losing leads to voicemail, let's talk:
{CALENDLY_LINK}""",

    # Indicators pitch
    f"""Congress members have 45 days to disclose their trades.

The volume patterns show up on the chart before disclosure goes public.

We built a TradingView indicator that flags it — plus momentum scoring and Kelly position sizing.

$49 for all 3 indicators:
{INDICATORS_LINK}""",

    # Authority/education
    """The #1 reason traders blow up isn't bad entries.

It's bad position sizing.

Kelly Criterion says: risk a percentage of your bankroll proportional to your edge.

Most traders risk 10% on a coin flip.
Kelly says risk 0%.

Built this into a TradingView indicator so you never have to do the math again.""",

    # HOA/contractor pitch
    f"""Most HOA teams track violations in spreadsheets.

Board asks for a status update.
Manager spends 45 minutes pulling it together.

We built a system that handles tracking, follow-ups, and board reports automatically.

If your team is still doing this manually, I can show you what we set up for similar HOAs this week:
{CALENDLY_LINK}""",

    # Social proof / momentum
    """What's working in 2026 for small businesses:

1. AI answering inbound calls 24/7
2. Automated follow-up sequences (not just email)
3. Systems that work while you sleep

What's not working:
- Hoping referrals keep coming
- Manually tracking everything in spreadsheets
- Paying for ads before fixing the conversion problem

The businesses winning right now built the systems first.""",
]

HASHTAGS = [
    "#trading #stockmarket #EdgeEngine #signals #TradingView",
    "#SmallBusiness #AI #automation #businessgrowth",
    "#investing #stocks #crypto #momentum #Kelly",
    "#HOA #propertymanagement #AI #automation",
    "#entrepreneur #startup #sales #growth",
]


def load_posted() -> set:
    if POSTED_FILE.exists():
        try:
            return set(json.loads(POSTED_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_posted(posted: set):
    POSTED_FILE.write_text(json.dumps(list(posted)))


def get_my_id() -> str:
    """Get LinkedIn member URN."""
    r = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json().get("sub", "")
    print(f"[LINKEDIN] Could not get user ID: {r.status_code} {r.text[:100]}")
    return ""


def post_to_linkedin(text: str) -> bool:
    """Post a text update to LinkedIn."""
    member_id = get_my_id()
    if not member_id:
        return False

    hashtag = random.choice(HASHTAGS)
    full_text = f"{text}\n\n{hashtag}"

    payload = {
        "author": f"urn:li:person:{member_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_text[:3000]},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json=payload,
        timeout=15,
    )

    if r.status_code in (200, 201):
        post_id = r.headers.get("x-restli-id", "?")
        print(f"  [LINKEDIN] Posted: {post_id}")
        return True
    else:
        print(f"  [LINKEDIN] Error {r.status_code}: {r.text[:200]}")
        return False


def run():
    if not ACCESS_TOKEN:
        print("[LINKEDIN] LINKEDIN_ACCESS_TOKEN not set.")
        print("  1. Go to linkedin.com/developers → Create app")
        print("  2. Add 'Share on LinkedIn' product")
        print("  3. OAuth Tools → Generate token with w_member_social scope")
        print("  4. Add LINKEDIN_ACCESS_TOKEN to Railway vars")
        return

    posted = load_posted()
    today  = datetime.utcnow().strftime("%Y-%m-%d")

    if today in posted:
        print(f"[LINKEDIN] Already posted today ({today}) — skipping")
        return

    # Pick a post not used recently
    available = [p for p in POSTS if p[:40] not in posted]
    if not available:
        posted = set()
        available = POSTS

    post_text = random.choice(available)
    print("[LINKEDIN] Posting...")
    ok = post_to_linkedin(post_text)

    if ok:
        posted.add(today)
        posted.add(post_text[:40])
        save_posted(posted)
        print("[LINKEDIN] Done — posted 1 update today")
    else:
        print("[LINKEDIN] Post failed — check token or app permissions")


if __name__ == "__main__":
    run()
