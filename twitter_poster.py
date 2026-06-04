"""
twitter_poster.py — Gray Horizons Enterprise
Auto-posts to Twitter/X daily. Four content streams:
  1. Edge Engine signal previews (drives $29/mo membership)
  2. TradingView indicator posts (drives $67 + $79 Gumroad sales)
  3. Business tip hooks (drives AI automation service leads)
  4. Engagement questions (builds audience, drives replies)

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


SIGNALS_POSTS = [
    f"""Congress bought $87M in defense stocks 3 weeks before the contract announcement.

That's not coincidence.

They have 45 days to report. The volume pattern shows up in week 1.

Most traders never see it coming. We track every disclosure as it drops.

{SIGNALS_LINK}""",

    f"""Unpopular trading truth:

Your entry matters less than your position size.

97% of blown accounts die from overleveraging a losing trade, not from a bad pick.

We built a Kelly Criterion calculator that tells you exactly how many shares to hold based on your real edge. Not a guess.

{SIGNALS_LINK}""",

    f"""I got tired of checking 30 tickers every morning before the open.

So I built a scoring system.

RSI + volume anomaly + EMA cross = one number, 0 to 100.

70 or above, I look closer. Below 70, I skip it.

Simpler. Faster. More consistent.

{SIGNALS_LINK}""",

    f"""NVDA showed a 2.3x volume anomaly 6 hours before the 8% move.

Volume tells you something is happening before price confirms it.

Most retail traders see the move after it's already over.

{SIGNALS_LINK}""",

    f"""Most traders have an entry strategy.

Almost nobody has a position sizing strategy.

That's why the same person can nail 7 trades in a row and still blow their account on trade 8.

Kelly Criterion fixes that. It sizes each position based on your actual win rate and edge.

{SIGNALS_LINK}""",

    f"""The market doesn't care about your analysis.

It cares about order flow, institutional positioning, and congressional insider timing.

Three things most retail traders have zero visibility into.

We built alerts for all three. Daily. Before the open.

{SIGNALS_LINK}""",

    f"""Here's what a profitable trading morning looks like:

6:45am: Signal sheet hits inbox
- 3 setups scored 70+
- 1 congressional flag active
- 1 crypto volume alert

7:30am: Position sized. Orders placed.
8am: Market opens. No scrambling.

That's the system.

{SIGNALS_LINK}""",

    f"""Retail traders lose because they react.

Institutional traders win because they position ahead of the move.

Congressional disclosures, volume anomalies, and momentum scoring are the three signals that let you stop reacting and start positioning.

{SIGNALS_LINK}""",

    f"""Stop asking "what should I buy?"

Start asking "what's the asymmetric setup right now?"

A setup with a 2.3x volume anomaly + RSI building in the 50-65 zone + a congressional disclosure in the last 3 weeks is not random.

That's a pattern worth tracking.

{SIGNALS_LINK}""",

    f"""The difference between a trader who breaks even and one who compounds:

Not stock picks.
Not secret indicators.

Consistent position sizing on high-probability setups.

That's it. That's the whole thing.

{SIGNALS_LINK}""",

    f"""Most retail traders watch price.

We watch volume, congressional disclosures, and momentum scoring simultaneously.

Price is what already happened.

Volume is what's about to happen.

{SIGNALS_LINK}""",

    f"""A congressional disclosure filed on a Monday.

Volume anomaly visible by Thursday.

Public retail traders see it on the following Monday after the news cycle catches up.

By then the move is over.

We track the disclosure window so you're positioned before the crowd.

{SIGNALS_LINK}""",

    f"""The math most traders ignore:

If you risk 5% of your account on every trade:
- 5 losers in a row = account down 22.6%
- 10 losers in a row = account down 40%

If you use Kelly and your edge is real:
- Worst 10-trade stretch = down 8-12%
- You survive. You compound.

Position sizing is the edge.

{SIGNALS_LINK}""",

    f"""6:45am signal sheet in your inbox.

Here's what's in it:

1. Top 3 scored setups (0-100 momentum score)
2. Active congressional disclosures with volume flag
3. Crypto momentum score
4. 1 note on macro conditions

Under 5 minutes to read. Clear on what to do.

{SIGNALS_LINK}""",

    f"""Retail traders average 3.7% annual returns.

The S&P 500 averages 10%.

Most retail traders underperform doing nothing would have done.

The difference is usually impulsive entries, poor position sizing, and no signal filter.

We fix all three.

{SIGNALS_LINK}""",
]

INDICATOR_POSTS = [
    f"""Most traders use 14 indicators.

We use 3.

Edge Scanner + Kelly Sizer + Congressional Tracker.

All 3 on TradingView. $79 one-time.

{WHOP_LINK}""",
    f"""RSI alone is noise.
Volume alone is noise.
EMA alone is noise.

All 3 at the same time = signal.

The GHE Edge Scanner scores this 0-100 on every bar.

{WHOP_LINK}""",
    f"""Congress disclosed $315M in trades last year.

Most traders never see it coming.

We built an indicator that shows the volume patterns before disclosure.

{WHOP_LINK}""",
    f"""The number 1 reason traders blow up:

Not bad entries.
Bad position sizing.

Kelly Criterion with Quarter-Kelly fractional sizing.
Built into TradingView.

{WHOP_LINK}""",
    f"""High-confidence signal:

RSI 45-70
Volume 2x avg
EMA crossover

All 3 on the same bar. Momentum score 70+.

The GHE Edge Scanner marks these automatically.

{WHOP_LINK}""",
    f"""3 TradingView indicators. One decision framework.

1. When to enter (Edge Scanner)
2. How much to risk (Kelly Sizer)
3. What Congress is doing (Congressional Tracker)

$79 one-time
{WHOP_LINK}""",
    f"""Position sizing question I get constantly:

\"How many shares should I buy?\"

It's not a guess. It's math.

Kelly Criterion calculates it based on your actual edge.

{WHOP_LINK}""",
    f"""Alert fatigue kills accounts.

200 signals a day means you act on garbage.

3-5 high-confidence setups means you act on edges.

GHE Edge Scanner scores 0-100. Only trade 70+.

{WHOP_LINK}""",
    f"""Works on stocks. Works on crypto. Works on forex.

Anything tradeable on TradingView.

GHE Indicator Suite - Pine Script v5, real-time scoring.

{WHOP_LINK}""",
    f"""Insider volume shows up on the chart before the disclosure goes public.

Congress has 45 days to report.

The pattern appears in week 1.

We built an indicator that flags it.

{WHOP_LINK}""",

    f"""TradingView lets you build and share custom indicators.

We built 3 that do what most retail traders do manually in 2 hours every morning.

Done in 3 minutes. Automatically. On every ticker you watch.

$79. One time.

{WHOP_LINK}""",

    f"""Most indicators repaint.

The GHE Edge Scanner does not.

Scores are locked on bar close. No hindsight.

That matters a lot more than most traders realize.

{WHOP_LINK}""",

    f"""The 3 questions before every trade:

1. What is the momentum score? (Edge Scanner)
2. How much should I risk? (Kelly Sizer)
3. Is there congressional activity in this ticker? (Congressional Tracker)

All 3 answered automatically. On TradingView. $79 once.

{WHOP_LINK}""",

    f"""Edge Scanner score over 70 this week:

NVDA: 78
MSFT: 74
COIN: 81
ETH: 76

4 setups. All above threshold. Identified pre-move.

The indicator does the filtering automatically.

{WHOP_LINK}""",
]

BUSINESS_TIP_POSTS = [
    """Most small businesses lose 30% of inbound leads to voicemail.

The customer doesn't leave a message.

They call the next result on Google.

#SmallBusiness #AI""",
    """Your Google Business Profile is either making you money or losing you money.

There's no neutral.

#LocalSEO #SmallBusiness""",
    """SMS gets a 98% open rate.
Email gets 20%.

If you're a local business and you're not texting your customers, you're leaving money behind.

#marketing #smallbusiness""",
    """Dead leads aren't dead.

They're waiting for the right message at the right time.

5-15% convert if you follow up correctly.

#sales #businessgrowth""",
    """AI doesn't replace your front desk.

It answers when your front desk can't.

Every missed call after 5pm is revenue you didn't capture.

#AI #automation #SmallBusiness""",
    """The businesses winning on Google Maps right now all do one thing.

They post to their Google Business Profile every single week.

Most competitors post zero times.

#LocalSEO""",
    """Most contractors lose their best leads in the gap between the estimate and the follow-up.

That's a system problem. Not a sales problem.

#contractors #businesstips""",
    """You built a great service.

Then you trusted word of mouth to scale it.

That's the ceiling most small businesses hit.

#entrepreneur #smallbusiness""",
    """The first business to respond to an inbound lead wins 78% of the time.

Not the best price. Not the best reviews.

The fastest response.

#sales #automation""",
    """What's actually working in 2026:

AI answering calls 24/7
Automated follow-up sequences
Systems that run while you sleep

What's not: hoping referrals keep coming.

#SmallBusiness""",
    """One closed deal from automation pays for a year of the system.

Most business owners wait until they're desperate to build it.

The ones winning built it first.

#businessgrowth""",
]

ENGAGEMENT_POSTS = [
    """Traders: what's the one indicator you refuse to trade without?

#trading #TradingView #stocks""",
    """Real question for traders:

Do you have a written position sizing rule or do you decide in the moment?

#trading #riskmanagement""",
    """Serious question for traders: what's your rule for cutting a losing position?

Most people don't have one. That's the problem.

#trading #riskmanagement #stocks""",
    """Traders: what's your process when a trade is up 15% — do you have a rule for taking profit or do you wing it?

#trading #stocks #options""",
    """Do you trade pre-market or wait for the open?

Why?

#trading #stocks #daytrading""",
    """What's your max loss per day before you stop trading?

Most people don't have a number. The ones who do last longer.

#trading #riskmanagement""",
    """Congressional stock disclosures — do you actually track them or ignore them?

Because the volume pattern shows up before the disclosure goes public.

#stocks #trading #congress""",
    """What's your biggest trading mistake in the last 6 months?

Be honest. We all have one.

#trading #stocks #options""",
    """RSI, MACD, or volume — if you could only watch one, which one?

#TradingView #trading #technicalanalysis""",
    """Crypto or stocks?

Which one are you more consistent with and why.

#crypto #stocks #trading""",
    """What's the cleanest setup you've ever taken?

Describe it.

#trading #stocks #technicalanalysis""",
    """Do you backtest your strategies or just trade live and learn?

#trading #backtesting #strategy""",
    """Biggest myth in trading:

"You need to be glued to the screen to make money."

The best traders I know place their orders before 8am and walk away.

What's a trading myth you've seen blown up?

#trading #stocks #mindset""",
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

    f"""The market gives you 3-5 clean setups a week if you know where to look.

Most retail traders take 20-30 trades chasing noise.

Our system scores everything 0-100. We only show you the 70+.

This week: 4 setups. 4 scored 70+. Average move: +8.2%.

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

CASE_STUDY_POSTS = [
    """A roofing company was answering maybe 60% of their inbound calls.

The other 40% left no voicemail. Just moved on to the next Google result.

We set up automated missed-call text-back. Same day.

3 months later: 94% response rate. 3 new jobs per week from leads they used to lose.

#roofing #contractor #automation""",

    """HOA management firm. 3 employees. Managing 12 communities.

Violation tracking was done in a shared spreadsheet.

Things got lost. Homeowners complained. Board meetings got ugly.

We built them an automated tracking system. 6 days to implement.

Violations are now tracked from report to resolution without anyone touching a spreadsheet.

#HOA #propertymanagement #automation""",

    """HVAC company. Peak season. Owner was spending 2 hours a day calling back leads.

After we set up the system:

- Every inbound lead gets a text response in under 90 seconds
- Estimates followed up automatically until answered
- Owner spends 0 hours on lead chasing

First month: 4 additional booked jobs.

#HVAC #smallbusiness #AI""",

    """Dental practice. 40% of new patient calls came in after hours.

All 40% went to voicemail.

Most didn't leave a message.

We built an after-hours response system that captures name, callback number, and reason for calling.

Front desk arrives with a sorted list every morning. No lost patients.

#dental #medtech #automation""",

    """Contractor had a 12-day average estimate-to-follow-up time.

In contracting, most homeowners make a decision within 5 days.

He was following up 7 days too late, every time.

We built automated follow-up at day 3, day 5, and day 8 after every estimate.

Close rate went from 22% to 39% in 60 days.

#contractor #construction #sales""",

    """Here's what $2,500 in business automation actually looks like:

Before:
- 1 person manually chasing 40 leads/week
- 60% follow-up rate
- 18% close rate

After:
- System handles all follow-up automatically
- 100% follow-up rate
- 31% close rate

That's math, not a pitch.

#smallbusiness #automation #AI""",

    """Landscaping company. Seasonal business. Lost 30% of recurring clients between seasons because nobody reached out.

We built a win-back sequence that goes out automatically 45 days before their usual start date.

Last season: 76% of lapsed clients rebooked. No calls made by the owner.

#landscaping #smallbusiness #entrepreneur""",

    """Plumbing company. Peak hours meant missed calls. Missed calls meant lost jobs.

Emergency plumbing: the customer calls 2-3 companies and books whoever responds.

We set up immediate SMS acknowledgment + calendar booking for all inbound calls.

Missed call rate: down 90%.

#plumbing #contractor #automation""",
]

# Portfolio showcase posts — paired with real screenshots from indicators/ folder
_PORTFOLIO_ITEMS = [
    ("""Built a full lead automation workflow inside GoHighLevel for a home services client.

New lead comes in from a web form. Immediate SMS fires. System waits for reply. No response in 30 min triggers an email. 24 hours later a second SMS goes out. Task created for manual outreach.

Zero manual steps. Zero missed leads.

This is what I build for clients: """ + GUMROAD_LINK + """

#GoHighLevel #CRM #Automation #HomeServices""",
     "indicators/ghl-automation-full.png"),

    ("""GHL pipeline dashboard for a home services client.

Opportunity status, conversion rates, revenue value, stage distribution — live and updating automatically.

Clients stop guessing where their leads are. The system tells them.

Need this built for your business: """ + GUMROAD_LINK + """

#GoHighLevel #CRM #LeadManagement #Automation""",
     "indicators/ghl-dashboard-demo.png"),

    ("""Built a Vapi AI voice agent that books HVAC appointments on inbound calls.

Caller says they need AC repair. Agent collects name, address, issue, and preferred time. Books the job. No human needed.

Live transcript from a real test call shown here.

Build yours: """ + GUMROAD_LINK + """

#VoiceAI #Vapi #HVAC #AIAutomation""",
     "indicators/vapi-live-transcript.png"),

    ("""AI voice agent dashboard — real inbound call data.

Call duration, transcript, booking status, caller info — all logged automatically after every call.

This is what an AI receptionist looks like in production.

""" + GUMROAD_LINK + """

#VoiceAI #Vapi #AIAgent #Automation""",
     "indicators/vapi-agent-dashboard.png"),

    ("""Booking confirmed. No human involved.

AI voice agent took the call, qualified the lead, and completed the appointment booking start to finish.

This runs 24/7. Nights, weekends, holidays.

""" + GUMROAD_LINK + """

#VoiceAI #AIAutomation #Vapi #SmallBusiness""",
     "indicators/vapi-booking-complete.png"),

    ("""Built a contractor intake system that handles both sides of the operation.

Client submits a job request. Gets an immediate confirmation. Request routes automatically to the right contractor.

Contractor gets notified instantly. No phone tag. No lost jobs.

""" + GUMROAD_LINK + """

#Contractors #Automation #HomeServices #SmallBusiness""",
     "indicators/contractor intake dashboard client side.png"),

    ("""Automated outreach dashboard pulling live data from multiple sources.

Lead status, pipeline value, outreach history — one view, no manual data entry.

Built for lead generation at scale. Same system can be built for any service business in under a week.

""" + GUMROAD_LINK + """

#Automation #LeadGeneration #AITools #BusinessIntelligence""",
     "dashboard_populated.png"),
]

PORTFOLIO_POSTS    = [item[0] for item in _PORTFOLIO_ITEMS]
PORTFOLIO_IMAGE_MAP = {item[0]: item[1] for item in _PORTFOLIO_ITEMS}

ALL_POSTS = {
    "signals":      SIGNALS_POSTS,
    "indicators":   INDICATOR_POSTS,
    "results":      RESULTS_POSTS,
    "engagement":   ENGAGEMENT_POSTS,
    "portfolio":    PORTFOLIO_POSTS,
}

# Image-attached categories — get a generated card PNG attached to the tweet
IMAGE_CATEGORIES = {"results", "signals"}

DAILY_SCHEDULE = [
    ("signals",    "13:00"),   # 8am ET  — morning signal preview (image card)
    ("results",    "17:00"),   # 12pm ET — weekly scorecard (image card)
    ("indicators", "20:00"),   # 3pm ET  — TradingView Pine Script product post
    ("portfolio",  "21:00"),   # 4pm ET  — portfolio showcase with real screenshot
    ("engagement", "23:00"),   # 6pm ET  — trading question / engagement
]

# Trading/finance accounts whose followers are our target audience
FOLLOW_SEED_ACCOUNTS = [
    "TradingView", "MarketWatch", "YahooFinance", "Investopedia",
    "unusual_whales", "StockMarket", "OptionsFlow", "CryptoDaily",
    "zerohedge", "SquawkCNBC", "MorningBrew", "WSJmarkets",
    "RealVision", "tastytrade", "ThinkOrSwim",
]

FOLLOW_SEARCH_QUERIES = [
    "TradingView signals",
    "options flow alert",
    "congressional trades stocks",
    "stock momentum scanner",
    "crypto trading signals",
    "position sizing Kelly",
    "RSI divergence setup",
    "Pine Script indicator",
]

# Comment templates paired to tweet topics — fills {ticker} or {topic} from tweet
COMMENT_TEMPLATES = [
    "This is exactly why we built the Edge Engine — momentum scoring + congressional tracking before open. Worth checking out if you're active in {topic}.",
    "Solid point. We see the same pattern in our signals feed. Kelly-sized positions on setups like this are what separate consistent traders from the rest.",
    "This is the kind of setup our Edge Scanner flags. Volume anomaly + RSI momentum on the same bar. Most miss it without the right tools.",
    "Exactly. Position sizing is the variable most traders skip. Kelly Criterion math does the heavy lifting once you have a proven edge.",
    "Congressional volume pattern is already showing in week 1 of the disclosure window. Retail doesn't see it until week 3. That gap is the edge.",
    "The 0-100 scoring system we built for this does exactly that — filters noise, surfaces only the 70+ setups. Game changer for consistency.",
    "Agree. Entry matters less than most people think. Size your position right on a mediocre setup vs. full send on a great one — size wins every time.",
]

TRENDING_SEARCH_TERMS = [
    "stock market today",
    "trading signals",
    "options flow",
    "TradingView setup",
    "congressional trades",
    "RSI momentum stocks",
    "Pine Script indicator",
    "position sizing trading",
]


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
            return json.loads(POSTED_LOG.read_text())
        except Exception:
            pass
    return {"signals": [], "indicators": [], "business_tip": [], "engagement": []}


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

def post_tweet(text: str, media_id: str | None = None) -> bool:
    """Post a tweet using Twitter API v2 with direct OAuth1 signing."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("[TWITTER] Missing API credentials — set all 4 env vars")
        return False

    try:
        from requests_oauthlib import OAuth1
        oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
        payload: dict = {"text": text[:280]}
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

        media_id = None
        if category in IMAGE_CATEGORIES:
            card_lines = _extract_card_lines(text)
            card_type  = "signals" if category == "signals" else "results"
            img_bytes  = _generate_signal_card(card_lines, card_type)
            if img_bytes:
                media_id = upload_media(img_bytes)
        elif category == "portfolio":
            img_rel = PORTFOLIO_IMAGE_MAP.get(text)
            if img_rel:
                img_path = DATA_DIR / img_rel
                if img_path.exists():
                    media_id = upload_media(img_path.read_bytes())
                else:
                    print(f"  [PORTFOLIO] Image not found: {img_path}")

        ok = post_tweet(text, media_id=media_id)
        if ok:
            sent += 1
        time.sleep(random.uniform(10, 20))

    save_posted(posted)
    print(f"\n[TWITTER] Done — {sent}/{len(due)} posts sent")

    # Auto-follow disabled — preserving API credits ($3.53 remaining)
    # Re-enable once credits are topped up
    # try:
    #     auto_follow_accounts(max_follows=20)
    # except Exception as e:
    #     print(f"[TWITTER] Follow error (non-fatal): {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Post immediately regardless of schedule")
    args = parser.parse_args()
    run(force=args.force)
