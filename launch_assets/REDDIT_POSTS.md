# Reddit Posts — GHE Indicator Suite Launch

Post these across different subs. Space them out — 1 per day, different subs.
DO NOT post the same text in multiple subs. Each version is customized.

---

## POST 1 — r/algotrading
**Title:** Built a momentum confluence indicator that scores setups 0-100 — happy to share the logic

**Body:**
Been building TradingView indicators for our internal trading desk for the past year. The one we use the most is what we call the Edge Scanner — it doesn't just give buy/sell signals, it assigns a 0-100 momentum score to every bar.

The score combines:
- RSI component (40% weight)
- Volume surge vs 20-bar average (40% weight)  
- EMA trend alignment (20% weight)

We only act on signals where the score hits 70+ AND we have a volume surge AND an EMA crossover all at the same time. The triple-confirmation kills most false signals.

The Kelly Position Sizer is attached to it — tells you exact share count based on your account size, win rate, and stop distance. No more "how many shares should I buy" paralysis.

Happy to answer questions about the logic. We also packaged it up for anyone who wants to use it directly without building from scratch — link in my profile if interested.

---

## POST 2 — r/TradingView
**Title:** Made a Congressional Trade Tracker indicator — detects pre-disclosure volume anomalies

**Body:**
One of the more interesting edges I've been working on: congress members have to disclose trades, but there's a window between when the trade happens and when it gets reported. During that window, the volume and price action often show unusual patterns.

I built an indicator that flags these anomalies — it looks for volume > mean + (stdev × 2.0) combined with price moves > 0.5% on the same bar. Those two together on a daily chart are surprisingly predictive.

It's not foolproof obviously, but it's an interesting filter to layer on top of your normal analysis — especially for names where congress has been active (NVDA, defense stocks, biotech).

The indicator is in Pine Script v5, overlay=true. Works best on daily/weekly.

If anyone wants the invite link to use it directly on TradingView (it's invite-only, we sell access), DM me or check my profile. $49/month for the full suite including the Edge Scanner and Kelly Sizer.

Sharing the concept free — the packaged tool is paid.

---

## POST 3 — r/Daytrading
**Title:** The position sizing problem that was killing my returns (and how I fixed it)

**Body:**
For two years I had decent signal accuracy but was still net negative. Took me a while to figure out it wasn't my entries — it was my sizing.

I'd risk 5% on high-conviction trades and 2% on everything else, but I was guessing what "high-conviction" meant. Started applying Kelly Criterion with a 0.25 fractional multiplier and my drawdowns dropped significantly.

Built it into a TradingView indicator so it updates live:
- Input your account size, historical win rate, avg win/loss ratio, and stop %
- It outputs exact share count and dollar risk
- Uses Quarter-Kelly (institutional standard — full Kelly is too volatile for most)

It's part of a 3-indicator suite we built for our desk. The other two are a momentum Edge Scanner and a Congressional Trade Tracker.

Anyone doing real size should have the math automated. Happy to answer questions about the Kelly formula if useful.

(Packaged tool is available — see my profile. Sharing the concept here because it genuinely helped my P&L.)

---

## POST 4 — r/stocks
**Title:** How we scan for high-probability setups before market open (3-factor confluence)

**Body:**
Every morning before open we run the same scan: RSI range, volume vs average, EMA alignment. Nothing exotic — but all three have to confirm at the same time.

The filtering logic:
1. RSI between 45-70 (bullish momentum but not extended)
2. Volume > 2× the 20-bar average (institutional participation)
3. Fast EMA (9) crossed above slow EMA (21) on this bar

When all three hit simultaneously, we treat it as a high-probability long setup. For shorts it's the mirror.

We built this into a TradingView indicator that scores it 0-100 and only labels the high-confidence ones (70+). Cuts the noise dramatically — instead of 50 alerts a day you get 3-5 that actually mean something.

Also built a Kelly-based position sizer alongside it so we never have to manually calculate share count.

Not a financial advisor, not advice — just sharing what our system looks like. If anyone builds something similar in Pine Script, the volume surge component is the most important one to get right.

(We packaged the full suite — link in bio if you want it pre-built rather than DIY.)

---

## POST 5 — r/wallstreetbets
**Title:** Built the nerd version of WSB DD — an indicator that detects when congress is loading up before disclosure

**Body:**
Y'all know about congress trading. Nancy Pelosi options, etc. Everyone knows — but nobody has a clean way to see it on a chart in real time.

I built a TradingView indicator that detects pre-disclosure accumulation patterns. Basically: volume spikes 2+ standard deviations above average + unusual price movement = alert zone on the chart.

These patterns show up on daily/weekly charts before a lot of the famous congressional trades got disclosed. Not every time, but often enough to be useful as a filter.

Paired it with a momentum scorer and a Kelly position sizer. The whole suite is $49/month or $79 one-time on TradingView invite.

Not financial advice, congress is just playing a different game than us and leaving footprints.

Link: [your Whop URL here]

---

## POSTING SCHEDULE
- Day 1 (today): Post #2 to r/TradingView
- Day 2: Post #1 to r/algotrading  
- Day 3: Post #3 to r/Daytrading
- Day 4: Post #4 to r/stocks
- Day 5: Post #5 to r/wallstreetbets

## REPLY STRATEGY
After posting, come back in 2-3 hours and reply to every comment — even just "good question, the formula is X." Engagement keeps the post visible.
