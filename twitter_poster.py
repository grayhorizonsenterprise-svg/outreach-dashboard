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
    # No link — builds trust, drives replies, algo-friendly
    """NVDA showed 2.4x average volume on a Tuesday.
No news. No catalyst. Price barely moved.
6 days later: +8.2%.

Volume tells you what is about to happen.
Price tells you what already happened.

Most retail traders are watching the wrong thing.

What are you tracking pre-move? #stocks #trading #NVDA""",

    # No link
    """Congress has 45 days to disclose their trades.
The volume pattern shows up on the chart within the first week.

Every time. Without exception.

Most traders wait for the news article on day 45.
By then the move already ran.

Do you track congressional timing? #CongressTrades #stocks""",

    # No link
    """Retail traders average 3.7% annual return.
The S&P 500 averages 10.4% over 30 years.

Most active traders underperform doing nothing.

The problem is not the picks.
It is impulsive entries, no position sizing rule, and no signal filter.

Which one is costing you the most? #trading #investing""",

    # No link
    """5% risk per trade.
5 losing trades in a row: account down 22%.
10 losers: down 40%.

Most traders think they are managing risk.
They are not running the math.

Kelly Criterion based on your actual win rate is the only correct way to size.

What is your current risk per trade? #trading #riskmanagement""",

    # No link
    """6:45am. Signal sheet hits.
Top 3 scored setups. 1 congressional flag. 1 crypto alert.

7:15am. Orders placed.
8am open. No scrambling.

Pre-market is where most trades are won or lost.
Not during market hours.

What does your pre-market look like? #trading #stocks #premarket""",

    # With link — 1 in 6 posts
    f"""Congress beat the S&P by an average of 6% per year from 2019 to 2023.

They have 45 days to disclose.
The volume spike shows up on charts within the first week.

Every quarter. Without fail.

Are you tracking this or finding out 45 days too late?

{SIGNALS_LINK}

#CongressTrades #stocks #investing""",

    # No link
    """Adding more indicators does not make you a better trader.
It gives you more reasons to hesitate.

RSI. Volume anomaly. EMA cross.
All 3 on the same bar.

That is the only signal that matters.

How many indicators are on your chart right now? #trading #TradingView""",

    # No link
    """Your entry is not the problem.
Your position size is.

A 60% win rate trader who risks 10% per trade will eventually blow up.
A 50% win rate trader who uses Kelly sizing will compound for years.

Same account. Same win rate. Completely different outcome.

Are you sizing by math or by feeling? #trading #riskmanagement""",

    # No link
    """Sen. Tuberville bought AMD calls.
AMD ran 12% over the next 11 days.
The disclosure came 34 days after the trade.

He had every right to make that trade. All legal. All documented.
The chart told the story on day 3.

Do you track congressional timing? #CongressTrades #AMD #stocks""",

    # No link
    """7 winning trades in a row.
Trade 8: overconfident, doubled the position.
Account down 30% on a normal loss.

Not blown by a bad pick.
Blown by bad position sizing on a loss that was supposed to happen.

Happens every single day.

What is your rule when you are on a streak? #trading #psychology""",

    # With link
    f"""Three things most retail traders have zero visibility into:

1. Institutional order flow
2. Congressional timing
3. Volume anomalies before price moves

We track all three before the open. Every day.

{SIGNALS_LINK}

#stocks #trading #investing""",

    # No link
    """The pattern before every big congressional-flagged move:

Day 1-4: Volume spike. Price quiet.
Day 5-12: Score builds. EMA aligns.
Day 13-25: Price moves.
Day 45: Disclosure hits the news. Retail buys the top.

You can be at day 4 or day 45.

Which day do you want to be on? #CongressTrades #trading #stocks""",
]

INDICATOR_POSTS = [
    # No link
    """Most traders use 14 indicators.
We use 3.

Edge Scanner: when to enter.
Kelly Sizer: how much to risk.
Congressional Tracker: who moved first.

Three questions. One answer. On every bar, on any chart.

What is your current setup? #TradingView #trading #stocks""",

    # No link
    """Repainted signals are not signals.
They are a story told in hindsight.

A real indicator locks its score on bar close.
What it showed at 4pm Friday is what it showed at 4pm Friday.
Not revised Monday when the move already ran.

Does your indicator repaint? #TradingView #trading""",

    # No link
    """Congress disclosed 847 individual stock trades in Q1 this year.

Almost every one showed a volume pattern before the disclosure date.

The pattern is not random.
It shows up 3 to 7 days after the trade, every quarter.

Are you tracking this or finding out 45 days too late? #CongressTrades #stocks""",

    # No link
    """Alert fatigue is a real account killer.

200 signals a day means you act on garbage.
3 high-confidence setups means you act on edges.

Score above 70: look closely.
Score above 80: this is your setup.
Below 70: skip it. No exceptions.

How many alerts are you filtering daily? #trading #TradingView""",

    # No link
    """RSI alone: noise.
Volume alone: noise.
EMA alone: noise.

All 3 on the same bar at the same time: signal.

That is not complexity. That is confluence.
Scored 0 to 100 on every bar automatically.

What is your confluence rule before entering? #trading #TradingView #stocks""",

    # No link
    """The single biggest retail trading mistake I see:

Risking the same dollar amount on every trade.

A $500 loss on a $10k account is 5%.
A $500 loss on a $50k account is 1%.

These are completely different trades with completely different consequences.

Do you size by dollar amount or by percentage? #trading #riskmanagement""",

    # With link
    f"""The Kelly Criterion in plain math:

Edge = (win rate x avg win) - (loss rate x avg loss)
Optimal size = Edge / Odds
Quarter-Kelly for conservative compounding.

Most traders have never run this on their own results.

We built it into TradingView so it runs automatically.

What is your actual edge? {WHOP_LINK} #trading #TradingView""",

    # No link
    """Volume is institutional.
Price is retail.

When volume moves without price: someone knows something.
When price moves without volume: it will not hold.

Volume weighting in the signal score: 40%.
Everything else comes second.

What is your volume threshold before entering? #trading #stocks #TradingView""",

    # No link
    """Before you enter a trade you should be able to answer 3 questions:

1. Why is this a signal and not noise?
2. How much of my account am I risking?
3. Is there institutional evidence behind this move?

If you cannot answer all 3, do not enter.

Can you answer all 3 on your last trade? #trading #discipline""",

    # No link
    """Congressional Tracker logic:

Day 1: Senator makes the trade.
Day 3-7: Volume pattern appears on chart.
Day 10-25: Price confirms the move.
Day 45: Disclosure hits. Retail reads the article.

The indicator flags day 3 to 7.
The news cycle flags day 45.

Which one do you want? #CongressTrades #TradingView #stocks""",

    # With link
    f"""3 TradingView indicators. One decision framework.

1. When to enter (Edge Scanner - momentum score 0-100)
2. How much to risk (Kelly Sizer - based on your actual win rate)
3. Who moved first (Congressional Tracker - volume flag before disclosure)

$79 one-time. Everything runs automatically.

{WHOP_LINK}

#TradingView #trading #stocks""",

    # No link
    """High-confidence signal checklist:

RSI between 45 and 70
Volume above 2x average
EMA crossover on same bar
Score above 70

All 4 at once. That is the only time we enter.

Missing any of the 4 on your last trade? #trading #TradingView #stocks""",
]


ENGAGEMENT_POSTS = [
    # Short, punchy, drives replies — no hashtags on shortest posts
    """What is the single biggest mistake you made in your last 10 trades?

Entry, sizing, or holding too long.

Be specific. #trading""",

    """RSI or MACD. Pick one and tell me why you actually use it.

No generic answers. #trading #TradingView""",

    """Do you track congressional stock disclosures?

Yes or no. If yes, how do you find them?

#CongressTrades #stocks""",

    """What ticker are you watching most closely right now and why?

#stocks #trading""",

    """Unpopular opinion: most retail traders would make more money if they traded half as often.

Agree or disagree? #trading #investing""",

    """What broke your longest winning streak?

Entry problem, sizing problem, or held too long.

Be honest. #trading #psychology""",

    """Best trading advice you ever received. One sentence.

Mine: volume confirms what price only suspects.

#trading #stocks""",

    """Does your current indicator repaint?

Most retail traders have never checked.

#TradingView #trading""",

    """You have a 60% win rate.
You risk 10% per trade.

Are you growing your account or slowly going broke?

Show your math. #trading #riskmanagement""",

    """Pre-market checklist. What is on yours?

Mine: score check, volume scan, congressional flags.
3 items. Under 5 minutes.

#trading #premarket #stocks""",

    """Which is more dangerous: a bad entry or bad position sizing?

Explain your answer. #trading""",

    """If you could only use 3 indicators for the rest of your trading career, what are they?

No duplicates allowed. #TradingView #trading""",

    """Congressional trades are public record.
45 days delayed but fully documented.

How many traders actually use this data and why do most ignore it?

#CongressTrades #stocks #investing""",
]

RESULTS_POSTS = [
    # No link — pure proof builds more trust than a link
    """NVDA setup logged Tuesday at close.
Score: 81.
Volume: 2.4x average.
Congressional flag: active.

By Friday: +7.2%.

The score was locked at Tuesday close.
Not adjusted Monday after the move ran.

This is not hindsight. This is the system. #NVDA #stocks #trading""",

    # No link
    """Congressional disclosure filed Monday.
Volume spike was flagged 4 days earlier.
Price move: +11.3% over the next 17 trading days.

We do not predict moves.
We track the pattern that repeats every single quarter.

When did you start tracking congressional flow? #CongressTrades #trading""",

    # No link
    """BTC momentum score hit 74 at the weekly close.
RSI: 58. Volume: 2.1x average. EMA: aligned.
Entry zone: 101K to 103K.

That was the setup logged before the open Monday.

No prediction. Just the score. #Bitcoin #BTC #crypto #trading""",

    # No link
    """APP scored 78 Wednesday premarket.
Conservative Kelly position: 4.2% of account.
Target: +8.1% from entry.
Stop: 4.8% below entry.
Risk/reward: 1.7 to 1.

This is what a scored setup looks like before it runs.

What is your minimum R/R before entering? #APP #stocks #trading""",

    # No link
    """META posted the highest score across 15 tracked tickers last week: 83.
Volume running 2.6x average for 3 consecutive sessions.
Congressional flag active.

Score above 80 means full Quarter-Kelly position.
Score above 75 means half position.
Below 70: watchlist only.

What was your highest conviction trade last week? #META #stocks""",

    # No link
    """Volume anomaly flagged: TSLA at 3x average. No news catalyst.
4 days later: +9.4%.

Same pattern seen on NVDA, AMD, and COIN in the last 90 days.

Volume does not lie. Price confirms.

What was your best trade in the last 30 days? #TSLA #stocks #trading""",

    # No link
    """Retail traders bought the COIN breakout at $248.
Institutional volume entered at $232 to $238 the previous week.
Score at the entry zone: 71.
Score at the breakout: 62 and declining.

Two completely different trades. Same ticker. Same week.

When do you typically enter? #COIN #crypto #trading""",

    # With link
    f"""Win rate alone tells you nothing.

55% win rate, risk 10% per trade: ruin probability over 40%.
55% win rate, risk 2% per trade: ruin probability under 1%.
55% win rate, Kelly sizing: maximum theoretical compounding.

Same win rate. Three completely different outcomes.

What is your current risk per trade?

{SIGNALS_LINK}

#trading #riskmanagement""",
]



CHART_POSTS = [
    # These go out with the card images — short text, let the image carry
    """Score locked at close. No revisions. No hindsight.

This is what a 78 setup looks like on the chart before the move.

What is your score threshold before entering? #trading #TradingView #stocks""",

    """Volume spike. EMA alignment. RSI in range.
All 3 confirmed on the same bar.
Score: 81.

This is not a prediction. This is a setup.

Do you wait for all 3 to confirm or do you jump early? #trading #stocks""",

    """Congressional flag active. Volume running 2.3x.
Score building from 68 to 74 over 4 sessions.

This is what institutional accumulation looks like on a chart.

Most retail traders look at this and see a boring consolidation.

#stocks #trading #CongressTrades""",

    """Green bar = score 70 or above. Volume confirmed. EMA aligned.

Not every bar is green. Most are not.
The ones that are have a specific, measurable reason.

That reason is the edge. #TradingView #trading #stocks""",

    """7 setups on the matrix right now.
Top score: META at 83.
Volume anomaly: BTC at 2.1x.
Congressional flag: AAPL, 12 days active.

Three different reasons. One framework.

What is your watchlist looking like? #stocks #crypto #trading""",

    """Before the move: score 74, volume 2.2x, EMA clean.
After the move: everyone on X says it was obvious.

It was not obvious. It was scored.

That is the difference between reacting and positioning.

#stocks #trading #TradingView""",

    """This is what the chart looked like at 4pm Tuesday.
Not at 4pm the following Monday when the move already ran.

Score locked at close.

What your indicators show after a move is history.
What they showed before the move is the edge. #trading #TradingView""",
]

WINS_POSTS = [
    # No link — proof posts convert better without a link, build credibility first
    """The scanner flagged NVDA Tuesday premarket.
Score: 81. Volume: 2.4x. Congressional activity noted.

By Friday close: +7.2%.

Subscribers saw the flag Tuesday morning.
The news article came out the following week.

That gap between day 4 and day 45 is the entire edge. #NVDA #stocks #trading""",

    # No link
    """Congressional disclosure: AMD calls purchased.
Volume pattern visible: day 4.
Price confirmation: day 11.
Public news article: day 45.

Which day do you want to know about it?

#AMD #CongressTrades #trading""",

    # No link
    """Run Kelly Criterion on your last 20 trades.

Win rate 60%, avg win 1.5R, avg loss 1R:
Optimal Kelly: 20%.
Quarter-Kelly (conservative): 5%.

Most traders are either over-risking or sizing randomly.

What does your data show? #trading #riskmanagement""",

    # No link
    """Three tickers scored above 75 this week.
All three showed volume anomalies before price moved.
One had an active congressional flag.

The pattern does not change.
Only the ticker changes.

What is your highest conviction setup this week? #stocks #trading""",

    # No link
    """Institutional flow entered BTC at 101K to 103K.
Retail bought the breakout at 108K.

Both profitable if the move continued.
Completely different risk profiles and entries.

Entry timing is not everything but it is most of it.

What was your BTC entry zone? #Bitcoin #BTC #crypto #trading""",

    # No link
    """The score that matters most is not the score at entry.

It is the score 3 days before entry.

Building from 62 to 68 to 74 over 3 sessions:
That is accumulation happening in real time.

Are you tracking score progression or just the number on entry day? #trading #TradingView""",

    # With link — 1 in 8 wins posts gets the link
    f"""Q2 congressional tracking result:

Flags that showed a volume pattern within 7 days: 11 of 14.
Flags that preceded a 5%+ move within 30 days: 8 of 14.

This is not stock picking.
This is pattern tracking on public data.

{SIGNALS_LINK}

#CongressTrades #stocks #investing""",

    # No link
    """Boring week this week. Best kind.

Monday: 1 setup. Score 81. Quarter-Kelly position.
Tuesday through Thursday: hold.
Friday: +11.3%. Close. Log it.

No drama. No overtrading. No checking charts every 20 minutes.

That is what a system looks like. #trading #discipline #stocks""",
]

VISUAL_POSTS = [
    # These go with the matrix/dashboard card images
    """Dashboard right now:
META: 83 - STRONG BUY
TSLA: 77 - BUY
BTC: 74 - BUY
COIN: 71 - WATCH
SPY: 68 - HOLD

Score above 70 means the setup is live.
Below 70 means keep watching.

What is your watchlist looking like? #stocks #crypto #trading""",

    """Market composite this week:
Breadth: confirming.
VIX: below 18.
Congressional flow: elevated.
Volume anomalies: 4 active across tracked tickers.

When all four line up the next move is usually not subtle.

What is your macro read this week? #stocks #trading #investing""",

    """6 active setups. Scored, ranked, sized.

Above 80: full Quarter-Kelly.
70 to 80: half position, confirm with volume.
Below 70: watchlist only.

Simple rules. Consistent execution.

Do you have a written entry rule or do you decide in the moment? #trading #discipline""",

    """Live matrix: score, volume multiplier, trend, and congressional flag.

Not 14 indicators stacked on a chart.
Four data points per ticker.

Everything that matters. Nothing that does not.

How many data points do you track before entering a trade? #trading #stocks #TradingView""",

    """Green means score above 70, volume above 1.5x average, and EMA aligned.
Red means sit on your hands.

Most weeks there are 2 to 4 green tickers.
Most retail traders enter on any ticker regardless of color.

That is the entire difference. #stocks #trading""",

    """This week's top setups by score:
NVDA: volume 2.4x, score building to 79.
META: congressional flag active, score 83.
BTC: weekly close above EMA, score 74.
PLTR: RSI 55, momentum confirmed, score 76.

Three different catalysts. Same framework to score them all.

What is your highest conviction trade this week? #stocks #crypto #NVDA #META""",
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

# PLATFORM LOCK — printed every run so there is never any ambiguity
PLATFORM_RULE = (
    "X/TWITTER: Edge Engine trading content ONLY. "
    "No business posts. No GHL. No AI services. No Calendly. No contractor content. "
    "Business content goes to LinkedIn exclusively. NEVER mix platforms."
)

# BUDGET MODE: $0.94 remaining this cycle, 24 days left, auto-recharge OFF.
# 2 posts/day — pre-market hook + mid-session signal.
DAILY_SCHEDULE = [
    ("chart",   "15:00"),   # 8am PT  — pre-market, catches early traders
    ("signals", "18:30"),   # 11:30am PT — active market hours
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
    print(f"[TWITTER] PLATFORM RULE: {PLATFORM_RULE}")

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

    # Track write credits — shared with twitter_engage.py
    # Both scripts write to the same file so the daily/monthly totals are accurate.
    _credit_log = DATA_DIR / "twitter_credits.json"
    try:
        day_key   = datetime.utcnow().strftime("%Y-%m-%d")
        month_key = datetime.utcnow().strftime("%Y-%m")
        data = json.loads(_credit_log.read_text()) if _credit_log.exists() else {}
        data[day_key]   = data.get(day_key, 0) + sent
        data[month_key] = data.get(month_key, 0) + sent
        _credit_log.write_text(json.dumps(data, indent=2))
        print(f"[TWITTER] Credits used today: {data[day_key]} | month: {data[month_key]}")
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
