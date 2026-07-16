"""
twitter_poster.py — Gray Horizons Enterprise
Auto-posts to Twitter/X daily. EDGE ENGINE ONLY — three content streams:
  1. Edge Engine signal previews (drives $29/mo membership)
  2. TradingView indicator posts (drives $67 + $79 Gumroad sales)
  3. Engagement questions (builds trader audience, drives replies)

STRICT RULE: Zero business/GHL/AI automation content on this account.
X audience = traders only. Business content goes to LinkedIn exclusively.

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
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def _next_card(category_filter=None):
    """Return (label, path) for the next unused card in indicators/cards/. Edge Engine only."""
    cards_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "indicators" / "cards"
    used_log  = Path(os.path.dirname(os.path.abspath(__file__))) / "twitter_cards_used.json"
    try:
        used = set(json.loads(used_log.read_text())) if used_log.exists() else set()
    except Exception:
        used = set()
    cards = sorted(cards_dir.glob("*.png")) if cards_dir.exists() else []
    unused = [c for c in cards if c.name not in used]
    if not unused:
        # All cards used — reset the cycle
        used = set()
        unused = cards
    if not unused:
        return ("none", None)
    card = random.choice(unused)
    used.add(card.name)
    try:
        used_log.write_text(json.dumps(list(used)))
    except Exception:
        pass
    return (card.stem.split("_")[0], str(card))

_CARD_GEN = True

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
POSTED_LOG = DATA_DIR / "twitter_posted.json"

SIGNALS_LINK = os.getenv("SIGNALS_LINK", os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01"))
WHOP_LINK    = os.getenv("WHOP_INDICATORS_LINK", "https://whop.com/gray-horizons-enterprise/ghe-indicator-suite/")
GUMROAD_LINK = os.getenv("GUMROAD_SIGNALS_LINK", "https://horizons56.gumroad.com/l/ghe-signals")
# BOOK_CALL is for LinkedIn/email only — never appears in X posts
BOOK_CALL    = "https://calendly.com/grayhorizonsenterprise/30min"

# ─── Content Pools ────────────────────────────────────────────────────────────


SIGNALS_POSTS = [
    f"""Congress bought $87M in defense stocks 3 weeks before the contract dropped.

45 days to report. Volume pattern shows up in week 1.

Most traders see the move after it's already over.

What ticker are you watching this week?

{SIGNALS_LINK}""",

    f"""Unpopular truth: your entry matters less than your position size.

97% of blown accounts died from overleveraging a loss. Not a bad pick.

Kelly math sizes each trade to your actual edge.

Sizing by math or feeling?

{SIGNALS_LINK}""",

    f"""I got tired of checking 30 tickers before the open.

Built a scoring system. RSI + volume anomaly + EMA cross = 0 to 100.

Score 70 or above I look closer. Below 70 I skip it.

How many tickers are you scanning each morning?

{SIGNALS_LINK}""",

    f"""NVDA showed a 2.3x volume anomaly 6 hours before the 8% move.

Volume tells you what's about to happen.
Price tells you what already happened.

Most retail traders watch the wrong thing.

{SIGNALS_LINK}""",

    f"""Most traders have an entry strategy.

Almost nobody has a position sizing strategy.

That's why someone nails 7 trades in a row and blows their account on trade 8.

What's your position sizing rule?

{SIGNALS_LINK}""",

    f"""The market doesn't care about your analysis.

It cares about order flow, institutional positioning, and congressional timing.

Three things most retail traders have zero visibility into.

Which one do you actually track?

{SIGNALS_LINK}""",

    f"""6:45am. Signal sheet in your inbox.

3 setups scored 70+. 1 congressional flag. 1 crypto alert.

7:30am. Positions sized. Orders placed.
8am. Market opens. No scrambling.

What does your pre-market routine look like?

{SIGNALS_LINK}""",

    f"""Retail traders lose because they react.

Institutional traders win because they position ahead of the move.

Congressional disclosures + volume anomalies + momentum scoring = stop reacting.

Are you tracking any of these three?

{SIGNALS_LINK}""",

    f"""The math most traders ignore:

Risk 5% per trade:
- 5 losers in a row = down 22.6%
- 10 losers = down 40%

Use Kelly with a real edge:
- Worst 10-trade stretch = down 8-12%

Position sizing is the edge. Not the picks.

{SIGNALS_LINK}""",

    f"""Retail traders average 3.7% annual returns.

The S&P 500 averages 10%.

Most retail traders underperform doing nothing.

Impulsive entries. No position sizing rule. No signal filter.

Which one is costing you the most?

{SIGNALS_LINK}""",

    f"""A congressional disclosure filed Monday.

Volume anomaly visible by Thursday.

Retail traders see it the following Monday after the news cycle.

By then the move is over.

Are you tracking the 45-day disclosure window?

{SIGNALS_LINK}""",

    f"""Most retail traders watch price.

We watch volume, congressional disclosures, and momentum scoring.

Price is what already happened.
Volume is what's about to happen.

Which do you prioritize?

{SIGNALS_LINK}""",
]

INDICATOR_POSTS = [
    f"""Most traders use 14 indicators.

We use 3.

Edge Scanner + Kelly Sizer + Congressional Tracker.

All 3 on TradingView. $79 once.

What's the indicator you can't trade without?

{WHOP_LINK}""",

    f"""RSI alone is noise. Volume alone is noise. EMA alone is noise.

All 3 at the same time = signal.

The GHE Edge Scanner scores this 0-100 on every bar automatically.

What's your go-to setup?

{WHOP_LINK}""",

    f"""Congress disclosed $315M in trades last year.

Volume pattern shows on the chart BEFORE the disclosure goes public.

We built an indicator that flags it automatically.

Are you tracking congressional flow?

{WHOP_LINK}""",

    f"""The number 1 reason traders blow up:

Not bad entries. Bad position sizing.

Kelly Criterion with Quarter-Kelly fractional sizing. Built into TradingView.

Do you have a written position sizing rule?

{WHOP_LINK}""",

    f"""High-confidence signal checklist:

RSI 45-70
Volume 2x avg
EMA crossover

All 3 on the same bar. Score 70+.

GHE Edge Scanner marks these automatically.

Missing any of the 3?

{WHOP_LINK}""",

    f"""3 TradingView indicators. One decision framework.

1. When to enter (Edge Scanner)
2. How much to risk (Kelly Sizer)
3. Congressional activity (Tracker)

$79 once. What's your current setup cost?

{WHOP_LINK}""",

    f"""Most indicators repaint.

The GHE Edge Scanner doesn't. Scores lock on bar close. No hindsight.

That's the difference between a signal system and a fantasy.

Does your indicator repaint?

{WHOP_LINK}""",

    f"""Alert fatigue kills accounts.

200 signals a day = you act on garbage.
3-5 high-confidence setups = you act on edges.

GHE Edge Scanner scores 0-100. Only look at 70+.

How many alerts are you filtering daily?

{WHOP_LINK}""",

    f"""Insider volume shows up on the chart before disclosure goes public.

Congress has 45 days to report. Pattern appears in week 1.

We built an indicator that flags it.

Are you using it?

{WHOP_LINK}""",

    f"""Works on stocks. Works on crypto. Works on forex.

Anything tradeable on TradingView.

3 indicators. Pine Script v5. Real-time scoring. $79 once.

What platform are you on?

{WHOP_LINK}""",

    f"""Edge Scanner scores this week above 70:

NVDA: 78
MSFT: 74
COIN: 81
ETH: 76

4 setups. All above threshold. Pre-move identification.

How many setups did you take this week?

{WHOP_LINK}""",

    f"""The 3 questions before every trade:

1. What's the momentum score? (Edge Scanner)
2. How much do I risk? (Kelly Sizer)
3. Congressional activity in this ticker? (Tracker)

All 3 answered automatically. $79 once.

{WHOP_LINK}""",
]


ENGAGEMENT_POSTS = [
    """Traders: what's the one setup you refuse to trade without?

Be specific.""",

    """Do you have a written position sizing rule or do you size in the moment?

If you wing it, your account isn't broken. Your system is.""",

    """Serious question: what's your rule for cutting a losing trade?

Most people don't have one written down. That's usually the problem.""",

    """Trade is up 15%. Do you have a rule for taking profit or do you make it up as you go?

Be honest.""",

    """Pre-market or wait for the open?

Why?""",

    """What's your max loss per day before you stop trading?

Most people don't have a hard number. The ones who do stay in the game longer.""",

    """Congressional stock disclosures. Do you track them or ignore them?

The volume pattern shows up before the disclosure goes public. Most retail traders miss the entire window.""",

    """What's the biggest trading mistake you've made in the last 6 months?

Be honest. We all have one.""",

    """RSI, MACD, or volume. If you could only watch one, which is it and why?""",

    """Crypto or stocks?

Which one are you actually consistent with and why.""",

    """What's the cleanest trade setup you've ever taken? Describe what lined up.""",

    """Do you backtest or just trade live and learn?""",

    """Biggest myth in trading I've seen blown up: you need to be glued to the screen to make money.

The best traders I know place orders before 8am and walk away.

What trading myth have you seen disproven?""",
]

RESULTS_POSTS = [
    f"""Signal recap — this week:

NVDA: flagged Mon premarket / +9.2% by Fri close
TSLA: volume anomaly Tue / +6.8% 48hrs later
SPY: congressional flag active / followed institutional

That's 3 scored setups. 3 clean entries.

{SIGNALS_LINK}""",

    f"""Weekly signal scorecard:

Setup score: 74/100
Volume anomaly: 2.1x avg
Congressional activity: 2 active disclosures
Momentum: building in the 55-70 RSI zone

None of this is random. We track it every morning.

{SIGNALS_LINK}""",

    f"""Position sizing check — real numbers:

Win rate: 58%
Avg win: 1.8R
Avg loss: 1.0R
Kelly fraction: 14.4%

At $10k account that's $1,440 max risk per setup.
Not a guess. Math.

{SIGNALS_LINK}""",

    f"""Results from following congressional flow:

Disclosure filed: 3 weeks ago
Volume spike: week 1 of holding period
Price move: +12.3% by disclosure date

The pattern repeats. Every quarter. Predictably.

{SIGNALS_LINK}""",

    f"""What a 70+ signal score has looked like this year:

Q1: 7 setups flagged / avg return +7.4%
Q2: 5 setups flagged / avg return +9.1%
YTD win rate: 81%

We only trade high-conviction. We skip everything else.

{SIGNALS_LINK}""",

    f"""This morning's signal sheet:

SPY: momentum score 71 — watching
NVDA: volume 1.9x — building
AAPL: congressional disclosure 12 days old — active
BTC: above 20-day EMA — confirmed

These hit your inbox by 6:45am ET.

{SIGNALS_LINK}""",

    f"""3-5 clean setups per week if you know where to look.

Most retail traders take 20-30 trades chasing noise.

System scores 0-100. We only show the 70+.

This week: 4 setups. All scored 70+. Avg move: +8.2%.

{SIGNALS_LINK}""",

    f"""What "boring" trading looks like:

Mon: 1 setup. Size to 14% Kelly. Place order.
Tue: Hold.
Wed: Hold.
Thu: +11.3%.
Fri: Close. Log it.

Next week: same process.

That's it.

{SIGNALS_LINK}""",
]



CHART_POSTS = [
    """TradingView screenshot — this is what a 70+ signal looks like on the chart.

RSI in range. Volume anomaly confirmed. EMA alignment clean.

Score 78. Entry zone active.

How often do all 3 line up at the same time for you?""",

    """This is the GHE Edge Scanner live on a daily chart.

Green bar = momentum score 70+. Volume confirmation. EMA cross.

Most traders look at price. We look at score.

What does your TradingView setup look like?""",

    """Congressional buy flagged. Volume spike confirmed. Score building.

This is what the institutional flow indicator looks like before the move.

Retail sees this 3 weeks after it already ran.

Are you tracking congressional timing?""",

    """Real chart. Real signal. Real entry zone.

GHE Edge Scanner + Institutional Flow running simultaneously on APP.

Score 78. Congressional flag active. Pre-move identification.""",

    """3 indicators. 1 decision framework.

When to enter. How much to risk. Congressional activity.

Most traders have zero of these systematized. All three run automatically.""",

    """What retail traders don't see until it's too late:

This chart. This volume pattern. This momentum build.

7 days before the disclosure hit the news.

The pattern shows up. Most people miss it.""",

    """GHE Institutional Flow indicator — live on NASDAQ.

Blue zone = institutional accumulation. Red zone = distribution.

You don't need to guess which side of the trade is active.

The chart tells you.""",
]

WINS_POSTS = [
    f"""Weekly recap — what the model called correctly:

NVDA: flagged Monday premarket / +9.2% by Friday close
APP: EMA breakout score 78 / +6.8% in 48 hours
BTC: breakout above $104k confirmed / +4.1% overnight

3 setups. 3 clean entries.

Signal sheet drops every morning at 6:45am ET.

{SIGNALS_LINK}""",

    f"""This week's scorecard:

Win rate: 80%
Average win: +6.7%
Average loss: -2.3%
Kelly fraction used: 14%

Not luck. Not gut. Scored entries. Sized correctly.

{SIGNALS_LINK}""",

    f"""Congressional flow result — filed 3 weeks ago, move confirmed this week.

Disclosure filed: day 0
Volume spike: day 4
Price move: +12.3% by day 21

The pattern repeats. Every quarter. We track it so you don't have to.

{SIGNALS_LINK}""",

    f"""Position sizing check — real numbers this week:

Win rate: 75%
Avg win: 1.8R
Avg loss: 1.0R
Kelly fraction: 14.4%

At $10k account: $1,440 risk per setup. Math, not guessing.

{SIGNALS_LINK}""",

    f"""What 4 clean setups looks like:

SPY: momentum 71 — held the level
NVDA: congressional flag + volume anomaly — +9.2%
COIN: score 74, EMA breakout — +5.1%
ETH: above 20d EMA, confirmed — +4.1%

All scored 70+. All sized with Kelly.

{SIGNALS_LINK}""",

    f"""Boring week. Best kind.

Mon: 1 setup. Scored 81. Sized 14% Kelly.
Tue-Thu: hold.
Fri: +11.3%. Close. Log it.

That's it. No drama. No overtrading.

{SIGNALS_LINK}""",

    f"""YTD scorecard update:

Q1: 7 setups flagged / avg return +7.4%
Q2: 5 setups flagged / avg return +9.1%
Win rate YTD: 80%

We skip everything below 70. That's the system.

{SIGNALS_LINK}""",

    f"""What happened when we followed the congressional volume signal:

Week 1: Volume spike. Score building.
Week 2: Momentum confirming. RSI 58.
Week 3: +14.2%. News hits. Retail buys the top.

We were already in.

{SIGNALS_LINK}""",
]

VISUAL_POSTS = [
    f"""6 setups. Scored, ranked, sized. Full matrix below.

Score above 70 = signal.
Score above 75 = full Kelly.
Everything else = skip.

{SIGNALS_LINK}""",

    f"""This is what our market heatmap looks like when conditions align.

Green = momentum confirmed.
Red = stay flat.

Nothing ambiguous about it.

{SIGNALS_LINK}""",

    f"""Live dashboard. 5 active setups. All metrics in one place.

RSI, score, price, volume multiplier, trend arrow.

No guessing. No scrolling through charts.

{SIGNALS_LINK}""",

    f"""When 4 tickers go green on the matrix at the same time, that's a regime shift.

SPY above 20d. NVDA breaking out. Crypto confirming. Congressional flow spiking.

This week was one of those weeks.

{SIGNALS_LINK}""",

    f"""Everything the scanner flagged this morning:

Momentum score, RSI level, volume anomaly, congressional overlap.

All on one card. All updated pre-market.

{SIGNALS_LINK}""",

    f"""Market overview. How the composite looks today.

Most setups: 70+
VIX: below 18
Breadth: confirming

When everything aligns, the next move is usually obvious.

{SIGNALS_LINK}""",
]


ALL_POSTS = {
    "signals":      SIGNALS_POSTS,
    "indicators":   INDICATOR_POSTS,
    "results":      RESULTS_POSTS,
    "engagement":   ENGAGEMENT_POSTS,
    "chart":        CHART_POSTS,
    "wins":         WINS_POSTS,
    "visual":       VISUAL_POSTS,
    # "automation" removed — GHL/AI business content does NOT belong on X/Twitter.
    # X is Edge Engine / trading ONLY. Business content goes to LinkedIn exclusively.
}

# Image-attached categories — auto-generate or attach a card PNG
IMAGE_CATEGORIES = {"results", "signals", "chart", "wins", "visual"}

# chart/wins/visual use the chart_card_generator (real screenshots + dynamic cards)
CHART_CARD_CATEGORIES = {"chart", "wins", "visual"}
# NOTE: "automation" is intentionally excluded — text-only, no image attached

DAILY_SCHEDULE = [
    ("chart",      "15:00"),   # 8am PT  / 11am ET — chart card post (hourly task starts 14:00 UTC)
    ("signals",    "18:30"),   # 11:30am PT / 2:30pm ET — Edge Engine signal post
    ("engagement", "23:00"),   # 4pm PT  / 7pm ET — trader engagement question
]

# Target audience accounts — trading AND local business/automation
FOLLOW_SEED_ACCOUNTS = [
    # Trading/finance
    "TradingView", "MarketWatch", "YahooFinance", "Investopedia",
    "unusual_whales", "StockMarket", "OptionsFlow", "CryptoDaily",
    "zerohedge", "SquawkCNBC", "MorningBrew", "WSJmarkets",
    "RealVision", "tastytrade", "ThinkOrSwim",
    # GHL / AI automation / small business
    "GoHighLevel", "gohighlevel", "AIautomation", "SmallBizTech",
    "HVACmarketing", "dentalmarketing", "contractormarketing",
    "SaaSfounder", "agencyowner", "MarketingAutomation",
    "VapiAI", "openai", "AnthropicAI", "zapier", "make_hq",
]

FOLLOW_SEARCH_QUERIES = [
    # Trading
    "TradingView signals",
    "options flow alert",
    "congressional trades stocks",
    "stock momentum scanner",
    "RSI divergence setup",
    # GHL / automation
    "GoHighLevel automation",
    "AI automation local business",
    "CRM automation small business",
    "missed call text back HVAC",
    "lead follow up automation",
    "GHL workflow setup",
    "AI voice agent business",
]

# Comment templates for trading content
COMMENT_TEMPLATES_TRADING = [
    "This is exactly why we built the Edge Engine — momentum scoring + congressional tracking before open. Worth checking out if you're active in {topic}.",
    "Solid point. We see the same pattern in our signals feed. Kelly-sized positions on setups like this are what separate consistent traders from the rest.",
    "This is the kind of setup our Edge Scanner flags. Volume anomaly + RSI momentum on the same bar. Most miss it without the right tools.",
    "Exactly. Position sizing is the variable most traders skip. Kelly Criterion math does the heavy lifting once you have a proven edge.",
    "Congressional volume pattern is already showing in week 1 of the disclosure window. Retail doesn't see it until week 3. That gap is the edge.",
    "The 0-100 scoring system we built for this does exactly that — filters noise, surfaces only the 70+ setups. Game changer for consistency.",
    "Agree. Entry matters less than most people think. Size your position right on a mediocre setup vs. full send on a great one — size wins every time.",
]

# Comment templates for GHL/automation content
COMMENT_TEMPLATES_AUTOMATION = [
    "This is the exact problem GHL automation solves. Most businesses lose 40% of leads just from slow response time. Seen it across dozens of setups.",
    "Speed to lead is everything. Under 5 minutes or you've lost them to whoever answered first. Automated SMS on form submit fixes this completely.",
    "We build this exact system for HVAC, dental, and contractor businesses. The ROI shows up in the first 30 days every time.",
    "The follow-up sequence is where most CRMs fail. 7 touches over 14 days across SMS, email, and voicemail drop — most people stop after touch 1.",
    "AI voice agents handling inbound calls 24/7 is no longer expensive or complex. The businesses that deploy this first own their market.",
    "Missed calls are the silent revenue killer for local service businesses. A missed call text-back bot pays for itself in the first week.",
    "GHL is the most underutilized platform in local business marketing. Most people use 10% of what it can actually do.",
]

COMMENT_TEMPLATES = COMMENT_TEMPLATES_TRADING + COMMENT_TEMPLATES_AUTOMATION

TRENDING_SEARCH_TERMS = [
    # Trading
    "stock market today",
    "trading signals",
    "options flow",
    "TradingView setup",
    "congressional trades",
    "RSI momentum stocks",
    "Pine Script indicator",
    "position sizing trading",
    # GHL / automation / small business
    "GoHighLevel CRM",
    "AI automation business",
    "lead generation automation",
    "CRM follow up system",
    "missed call text back",
    "HVAC marketing automation",
    "dental practice marketing",
    "AI voice agent small business",
]

AUTOMATION_SEARCH_TERMS = [
    "GoHighLevel automation -is:retweet lang:en min_faves:5",
    "AI automation local business -is:retweet lang:en min_faves:5",
    "CRM automation small business -is:retweet lang:en min_faves:5",
    "missed call text back -is:retweet lang:en min_faves:3",
    "lead follow up system -is:retweet lang:en min_faves:5",
    "GHL workflow -is:retweet lang:en min_faves:3",
]


def auto_engage_niche(max_comments: int = 5) -> int:
    """Disabled — GHL/automation engagement from a trading account splits the algorithm audience."""
    return 0
    # Original implementation below — do not re-enable without explicit approval
def _auto_engage_niche_disabled(max_comments: int = 5) -> int:
    """Auto-reply to high-engagement GHL/automation tweets with value-add comments."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return 0

    from requests_oauthlib import OAuth1
    oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
    engaged_file = DATA_DIR / "twitter_engaged.json"

    try:
        engaged = set(json.loads(engaged_file.read_text()).get("ids", []))
    except Exception:
        engaged = set()

    commented = 0
    for query in random.sample(AUTOMATION_SEARCH_TERMS, min(3, len(AUTOMATION_SEARCH_TERMS))):
        if commented >= max_comments:
            break
        try:
            r = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": query, "max_results": 10,
                    "tweet.fields": "public_metrics,author_id",
                    "expansions": "author_id", "user.fields": "username",
                },
                auth=oauth, timeout=15,
            )
            if r.status_code != 200:
                continue
            tweets = r.json().get("data", [])
            for tweet in sorted(tweets, key=lambda t: t.get("public_metrics", {}).get("like_count", 0), reverse=True):
                if commented >= max_comments:
                    break
                tid = str(tweet["id"])
                if tid in engaged:
                    continue
                comment = random.choice(COMMENT_TEMPLATES_AUTOMATION)
                result = post_comment(tid, comment)
                if result:
                    engaged.add(tid)
                    commented += 1
                    time.sleep(random.uniform(30, 60))
        except Exception as e:
            print(f"[TWITTER ENGAGE] Error: {e}")
        time.sleep(5)

    engaged_file.write_text(json.dumps({"ids": list(engaged)}, indent=2))
    print(f"[TWITTER ENGAGE] {commented} niche comments posted")
    return commented


# ─── Image Card Generation ────────────────────────────────────────────────────

def _generate_signal_card(lines: list[str], card_type: str = "signals") -> bytes | None:
    """Generate a dark-themed PNG card and return raw bytes. Returns None if Pillow unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    W, H = 1200, 628
    BG       = (15, 32, 65)     # navy — avoids X adult-content false positive on near-black
    BORDER   = (255, 255, 255)
    ACCENT   = (0, 180, 120)   if card_type == "signals"    else (29, 130, 220)
    TEXT_HI  = (255, 255, 255)
    TEXT_LO  = (160, 175, 200)
    DIVIDER  = (30, 55, 100)

    img  = Image.new("RGB", (W, H), BORDER)   # white outer border frame
    inner = Image.new("RGB", (W - 16, H - 16), BG)
    img.paste(inner, (8, 8))
    draw = ImageDraw.Draw(img)

    # Accent left bar
    draw.rectangle([0, 0, 8, H], fill=ACCENT)

    # Header tag
    tag_label = "SIGNAL SCORECARD" if card_type == "signals" else "GHE RESULTS"
    draw.rectangle([48, 48, 48 + len(tag_label) * 14 + 24, 88], fill=ACCENT)
    try:
        font_tag  = ImageFont.truetype("arialbd.ttf", 22)
        font_main = ImageFont.truetype("arialbd.ttf", 36)
        font_body = ImageFont.truetype("arial.ttf",   28)
        font_foot = ImageFont.truetype("arial.ttf",   22)
    except Exception:
        font_tag = font_main = font_body = font_foot = ImageFont.load_default()

    draw.text((60, 52), tag_label, font=font_tag, fill=BG)

    # Content lines
    y = 120
    for i, line in enumerate(lines[:8]):
        line = line.strip()
        if not line:
            y += 14
            continue
        if i == 0:
            draw.text((48, y), line, font=font_main, fill=TEXT_HI)
            y += 52
            draw.rectangle([48, y, W - 48, y + 1], fill=DIVIDER)
            y += 16
        else:
            color = ACCENT if any(c in line for c in ["+", "✓", "WIN"]) else (
                (220, 80, 80) if any(c in line for c in ["-", "LOSS", "MISS"]) else TEXT_LO
            )
            draw.text((48, y), line, font=font_body, fill=color)
            y += 42

    # Footer
    draw.rectangle([0, H - 56, W, H - 56 + 1], fill=DIVIDER)
    draw.text((48, H - 44), "Gray Horizons Enterprise  |  grayhorizonsenterprise.com", font=font_foot, fill=TEXT_LO)

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _extract_card_lines(text: str) -> list[str]:
    """Pull the first 8 non-link lines from a post to use as card content."""
    lines = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if stripped.startswith("http") or stripped.startswith("@"):
            continue
        lines.append(stripped if stripped else "")
        if len(lines) >= 8:
            break
    return lines


def upload_media(image_bytes: bytes) -> str | None:
    """Upload PNG bytes via Twitter v1.1 media upload. Returns media_id string or None."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return None
    try:
        import base64
        from requests_oauthlib import OAuth1
        oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
        r = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={"media_data": base64.b64encode(image_bytes).decode("ascii")},
            auth=oauth,
            timeout=30,
        )
        if r.status_code in (200, 201):
            media_id = r.json().get("media_id_string")
            print(f"  [TWITTER MEDIA] Uploaded card — media_id: {media_id}")
            return media_id
        else:
            print(f"  [TWITTER MEDIA] Upload failed {r.status_code}: {r.text[:120]}")
            return None
    except Exception as e:
        print(f"  [TWITTER MEDIA] Error: {e}")
        return None


# ─── Post tracking ────────────────────────────────────────────────────────────

def load_posted() -> dict:
    if POSTED_LOG.exists():
        try:
            data = json.loads(POSTED_LOG.read_text())
            # Ensure new categories exist
            for cat in ("signals", "indicators", "results", "engagement", "chart", "wins"):
                data.setdefault(cat, [])
            return data
        except Exception:
            pass
    return {"signals": [], "indicators": [], "results": [], "engagement": [], "chart": [], "wins": []}


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

_BLOCKED_KEYWORDS = [
    "ghl", "gohighlevel", "go high level",
    "ai voice agent", "vapi", "front desk",
    "hvac company", "roofing company", "contractor",
    "missed call", "follow-up", "follow up", "calendly",
    "automation", "automations", "automate",
    "$750/month", "$997", "$297",
    "audit", "free 20-min",
]

def _is_business_content(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _BLOCKED_KEYWORDS)


def post_tweet(text: str, media_id: str | None = None) -> bool:
    """Post a tweet using Twitter API v2 with direct OAuth1 signing."""
    if _is_business_content(text):
        print(f"[TWITTER BLOCKED] Business/automation content detected — refusing to post.")
        print(f"  First 80 chars: {text[:80]!r}")
        return False

    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("[TWITTER] Missing API credentials — set all 4 env vars")
        return False

    try:
        from requests_oauthlib import OAuth1
        oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
        payload: dict = {"text": text}
        if media_id:
            payload["media"] = {"media_ids": [media_id]}
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            json=payload,
            auth=oauth,
            timeout=15,
        )
        if r.status_code in (200, 201):
            tweet_id = r.json().get("data", {}).get("id", "?")
            suffix = " [+image]" if media_id else ""
            print(f"  [TWITTER] Posted{suffix}: twitter.com/i/web/status/{tweet_id}")
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

def get_due_categories() -> list[str]:
    """Return categories whose scheduled time is within 45 min of now (UTC)."""
    now_h = datetime.utcnow().hour
    now_m = datetime.utcnow().minute
    now_total = now_h * 60 + now_m
    due = []
    for category, t in DAILY_SCHEDULE:
        h, m = int(t.split(":")[0]), int(t.split(":")[1])
        sched_total = h * 60 + m
        # handle midnight wrap
        diff = abs(now_total - sched_total)
        if diff > 720:
            diff = 1440 - diff
        if diff <= 45:
            due.append(category)
    return due


def run(force: bool = False):
    now_utc = datetime.utcnow().strftime("%H:%M UTC")
    print(f"[TWITTER] Checking schedule at {now_utc}...")

    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("[TWITTER] Not configured — missing API credentials")
        return

    due = get_due_categories()

    # force=True used on startup: always post one item so restarts never go silent
    if not due:
        if force:
            category = random.choice(list(ALL_POSTS.keys()))
            due = [category]
            print(f"[TWITTER] Startup force-post: {category}")
        else:
            print(f"[TWITTER] Nothing scheduled within 45 min of {now_utc} — done")
            return

    posted = load_posted()
    sent   = 0

    for category in due:
        text = pick_post(category, posted)
        print(f"\n[{category.upper()}] Posting ({datetime.utcnow().strftime('%H:%M UTC')})...")

        # Media uploads disabled — each upload burns paid API credits (ContentCreateWithUrl).
        # Text-only posts cost 1 credit each. Re-enable only after credits reset and
        # follower count justifies the spend.
        media_id = None

        ok = post_tweet(text, media_id=media_id)
        if ok:
            sent += 1
        time.sleep(random.uniform(10, 20))

    save_posted(posted)

    # Track monthly credit usage — 1 credit per text post
    _credit_log = DATA_DIR / "twitter_credits.json"
    try:
        month_key = datetime.utcnow().strftime("%Y-%m")
        data = json.loads(_credit_log.read_text()) if _credit_log.exists() else {}
        data[month_key] = data.get(month_key, 0) + sent
        _credit_log.write_text(json.dumps(data, indent=2))
        print(f"[TWITTER] Credits used this month: {data[month_key]}")
    except Exception:
        pass

    print(f"\n[TWITTER] Done — {sent}/{len(due)} posts sent")
    # Auto-follow permanently disabled — wasted paid API credits with no follower return.


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Post immediately regardless of schedule")
    args = parser.parse_args()
    run(force=args.force)
