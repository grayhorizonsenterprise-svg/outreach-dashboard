# TradingView Indicator Publication Guide
# Gray Horizons Enterprise — Publish all 3 before Thursday night

---

## STEP 1 — Open TradingView Pine Editor
1. Go to tradingview.com and sign in
2. Click any chart
3. At the bottom click "Pine Editor"
4. You will see a code window

---

## INDICATOR 1: GHE Edge Scanner
**File:** GHE_Edge_Scanner.pine
**Price:** $79 one-time (invite-only)
**Cover image:** indicators/GHE-Edge-Engine-Cover.png

**Paste this into Pine Editor:**
(copy full contents of GHE_Edge_Scanner.pine)

**Title to use:** GHE Edge Scanner
**Short description (for publish form):**
Scores momentum, volume, and trend confluence on a 0-100 scale. Fires LONG/SHORT labels when your threshold is hit. Built for active traders who want a clean single number instead of juggling 3 separate indicators.

**Long description:**
The GHE Edge Scanner combines three weighted components into one score: RSI momentum (0-40 pts), volume surge vs 20-bar average (0-30 pts), and EMA 9/21 confluence (0-30 pts). Total score 0-100. A signal fires when the score crosses your threshold (default 70). Direction labels show LONG, SHORT, or NEUTRAL on the signal bar. Background highlights the active signal zone. Works on any timeframe, any asset.

---

## INDICATOR 2: GHE Kelly Position Sizer
**File:** GHE_Kelly_Sizer.pine
**Price:** $79 one-time (invite-only, or bundle with Edge Scanner)
**Cover image:** indicators/GHE-Institutional-Flow-Cover.png

**Title to use:** GHE Kelly Position Sizer
**Short description:**
Calculates your exact share count and dollar risk based on Kelly Criterion and your real account stats. No more guessing position size. Inputs your account size, win rate, R multiples, and stop percentage. Table shows Full Kelly, Half-Kelly, risk amount, share count, and dollar risk in real time.

**Long description:**
Enter your account size, historical win rate, average win and loss R multiples, and stop loss percentage. The indicator calculates Full Kelly and Half-Kelly percentages, total dollar risk, share count, and total dollar risk per trade. Displayed as a clean table in the top right corner. Updates with every bar so sizing is always based on the current price. Works on stocks, futures, forex, and crypto.

---

## INDICATOR 3: GHE Congressional Tracker
**File:** GHE_Congressional_Tracker.pine
**Price:** $79 one-time (invite-only, or bundle)
**Cover image:** indicators/GHE-Institutional-Flow-Cover.png

**Title to use:** GHE Congressional Tracker
**Short description:**
Detects three institutional accumulation patterns: volume spike anomalies, quiet accumulation (high volume, small price move), and sustained elevation over a lookback window. Scores 0-100. Purple background on pattern detection. Label fires on new signals.

**Long description:**
Tracks three patterns tied to institutional and congressional-style accumulation: (1) Volume Spike: when volume exceeds X times the 30-bar average. (2) Quiet Accumulation: large volume paired with a small price move, the classic institutional masking pattern. (3) Sustained Elevation: volume elevated above 1.8x average for 3 or more bars in the lookback window. Composite score 0-100. Purple background marks quiet accumulation. Blue-purple marks full pattern confluence. Labels fire on new pattern detection only, not on every bar.

---

## HOW TO PUBLISH EACH ONE

1. Paste the Pine code into the editor
2. Click "Publish Script" (cloud icon with arrow, top right of Pine Editor)
3. Choose: "Invite-only script" (NOT free or open source)
4. Fill in title and description from above
5. Upload the cover image
6. Click Publish
7. After publishing: go to your published script page
8. Copy the script URL
9. In your Gumroad product for each indicator: paste the TradingView script URL in the delivery instructions

---

## PRICING ON GUMROAD (update after publishing)
- Each indicator: $79 one-time
- Bundle (all 3): $179 one-time
- Add to product description: "After purchase you will receive a TradingView invite link within 24 hours."

---

## WHOP APPROVAL TIMELINE
Whop Discover review: typically 3-7 business days after submission.
Your 5 products are already submitted. Check Whop dashboard for status.
Do NOT re-submit. Just wait. If over 7 days, use the in-app support chat.

---

## TWITTER $6.85 BALANCE NOTE
The $6.85 showing in your Twitter developer dashboard is your API credit balance.
The spend cap ($5.00) is a SEPARATE setting under Billing > Manage Spend Cap.
Thursday night: go to developer.twitter.com > your app > Billing > raise spend cap to $25.
Your $6.85 credits cover posting costs. The cap just needs to be raised.
