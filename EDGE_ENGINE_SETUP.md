# Edge Engine — Full Setup Guide
**Stocks + Crypto + Sports/Politics Bets + Phone Alerts**

Everything runs from one folder: `edge_engine/`
One command to scan everything: `python scan.py`

---

## What This System Does

Runs a daily scan across three verticals and sends your phone an alert:

| Vertical | Data Source | Key Needed |
|---|---|---|
| Stocks | Yahoo Finance + Reddit WSB + Congress trades | Free (QuiverQuant) |
| Crypto | CoinGecko live prices | No key needed |
| Sports bets | 40+ sportsbooks via The Odds API | Free (500 req/month) |
| Politics bets | Polymarket prediction market | No key needed |
| Phone alerts | ntfy.sh push notifications | No key needed |
| Profit tracker | Robinhood API | Your RH login |

---

## Before You Start — Prerequisites

You need Python installed. Check by opening a terminal and running:
```
python --version
```
If you see `Python 3.10` or higher, you're good.
If not, download from: **python.org/downloads** — install with "Add to PATH" checked.

---

## Step 1 — Open a Terminal in the Right Folder

1. Open File Explorer
2. Navigate to: `Downloads\First Agentic Workflows\edge_engine`
3. Click the address bar at the top, type `cmd`, press Enter
4. A black terminal window opens already in the right folder

---

## Step 2 — Install Dependencies

Paste this into the terminal and press Enter:
```
pip install yfinance pandas numpy requests python-dotenv robin_stocks pyotp
```
Wait for it to finish (takes about 60 seconds).

---

## Step 3 — Create Your .env File

The `.env` file holds your API keys. The system will not run without it.

1. In File Explorer, look for `.env.template` inside the `edge_engine` folder
2. Right-click it → Copy → Paste in the same folder → Rename the copy to `.env`
3. Open `.env` with Notepad

It looks like this:
```
NTFY_TOPIC=edge_picks_YOUR_UNIQUE_ID
ODDS_API_KEY=
QUIVERQUANT_KEY=
RH_USERNAME=
RH_PASSWORD=
```

Fill in each section using the steps below.

---

## Step 4 — Set Up Phone Alerts (Free, 5 Minutes)

You need the `ntfy` app on your phone. It sends push notifications for free.

**On your phone:**
1. Open the App Store (iPhone) or Google Play (Android)
2. Search: **ntfy**
3. Install the app by "Philipp Heckel"
4. Open the app → tap the **+** button → Subscribe to a topic
5. Type a unique topic name — make it something only you know, like: `ghe_edge_2026`
6. Tap Subscribe

**In your `.env` file:**
```
NTFY_TOPIC=ghe_edge_2026
```
Use the exact same topic name you typed in the app.

**Test it:** Run `python notify.py` — your phone should buzz within 5 seconds.

---

## Step 5 — Sports Odds API (Free, 3 Minutes)

This unlocks live odds from DraftKings, FanDuel, BetMGM, and 37 other books simultaneously.

1. Go to: **the-odds-api.com**
2. Click "Get API Key" — sign up with email (free, no credit card)
3. You get 500 requests per month free — enough for 16 daily scans
4. Copy your API key from the dashboard

**In your `.env` file:**
```
ODDS_API_KEY=paste_your_key_here
```

---

## Step 6 — Congress Trade Tracking (Free, 3 Minutes)

Tracks Nancy Pelosi and all of Congress. Their trades are legally public (STOCK Act).

1. Go to: **quiverquant.com/quiverapi**
2. Sign up free — takes 2 minutes
3. Copy your API token from the dashboard

**In your `.env` file:**
```
QUIVERQUANT_KEY=paste_your_token_here
```

---

## Step 7 — Robinhood Profit Tracker (Optional)

Automatically tracks your Robinhood balance and alerts your phone when you're up $500+.

**In your `.env` file:**
```
RH_USERNAME=your_robinhood_email@gmail.com
RH_PASSWORD=your_robinhood_password
```

**If you have 2-Factor Authentication on Robinhood:**
- Option A: Temporarily disable 2FA in Robinhood settings (Settings → Security → Two-Factor Auth)
- Option B: If you use an authenticator app, add `RH_MFA_CODE=` to `.env` with your live TOTP code each time you run

---

## Step 8 — Run Your First Scan

Double-click `run.bat` inside the `edge_engine` folder.

OR in the terminal:
```
python scan.py
```

The scan takes about 60-90 seconds. It will:
1. Print ranked stock picks with scores
2. Print crypto momentum rankings
3. Print best sports/politics bets with win probability and edge %
4. Check your Robinhood balance vs. your baseline
5. Send a summary alert to your phone

---

## Step 9 — Schedule Daily Auto-Run at 9 AM

Run this once — you never have to think about it again:

Double-click `schedule.bat` inside the `edge_engine` folder.

This registers a Windows Task Scheduler job that runs the scan every morning at 9:00 AM automatically, even if you don't open the app. Results are logged to `scan_log.txt`.

To verify it's registered:
- Press Win + S → search "Task Scheduler"
- Open it → look for "EdgeEngineDailyScan" in the list

To remove it later:
```
schtasks /delete /tn "EdgeEngineDailyScan" /f
```

---

## How to Read the Output

### Stocks
```
#1  ARM    score=68.8  $148.20  +1.2%  RSI=67.3  BUY   above EMAs | MACD bull
```
- **Score 75+** = Strong Buy, send alert
- **Score 60-74** = Buy, worth entering
- **Score 45-59** = Watch, wait for better entry
- **Below 45** = Skip
- **RSI 50-70** = healthy momentum (sweet spot)
- **RSI below 35** = oversold, potential bounce
- **RSI above 75** = overbought, risk of pullback
- **[CONGRESS]** = members of Congress bought this recently
- **[PELOSI]** = Nancy Pelosi specifically bought this

### Crypto
```
#1  APT    score=49.9  $6.42   +2.0% 1h  +5.1% 24h   WATCH
```
- Same score scale as stocks
- Look for 24h gains of 3%+ with score above 60 — that's a breakout
- **High volume** note means unusual activity vs market cap

### Bets
```
SPORT      BET              ODDS   BOOK        WIN%   EDGE    EV/$100
NFL        Kansas City ML   -180   DraftKings  72%   +4.2%   $+3.80
```
- **WIN%** = our probability estimate (devigged from all books)
- **EDGE** = how much better your actual odds are vs. the true probability
- **EV/$100** = expected profit per $100 wagered long-term
- Only bet when EV is **positive** — that's where you have a real edge
- Ignore bets with negative EV no matter how confident you feel

### How Much to Bet Per Game
| Your Bankroll | Max Per Bet | Why |
|---|---|---|
| $50 | $2-3 | Survival is the strategy |
| $100 | $3-5 | 3-5% Kelly rule |
| $250 | $7-12 | Same rule |
| $500 | $15-25 | Meaningful payouts start here |
| $1,000 | $30-50 | Professional range |

**Never bet more than 5% of your total bankroll on one game.** This is the rule that separates people who last from people who blow up.

---

## Coinbase / CashApp Crypto

The system gives you **signals** for crypto — you then manually place trades wherever you prefer.

**For Coinbase:**
1. Open Coinbase app
2. Search the coin ticker (e.g., SOL, APT, INJ)
3. Buy the amount you want
4. Set a price alert in Coinbase for +15-20% so you know when to take profit

**For CashApp:**
1. Tap the Investing tab (dollar sign icon)
2. Search Bitcoin or Ethereum (CashApp only supports BTC and ETH)
3. For other coins you'll need Coinbase or Kraken

**Profit rule:** When any crypto position is up 20%+, sell at least half. Lock in the gain.

---

## Profit Pull Alert

When your Robinhood balance is up $500 from your baseline, your phone buzzes with:
```
PULL PROFITS — Robinhood
Up $500.00 this period!
TAKE PROFITS NOW
```

When you get this alert:
1. Open Robinhood
2. Sell enough positions to pull the profit
3. Transfer to your bank account
4. The system resets the baseline automatically

The bi-weekly period resets every 14 days regardless.

---

## File Structure

```
edge_engine/
  config.py           All settings and watchlists (edit to add more tickers)
  signals.py          All signal logic — stocks, crypto, bets
  notify.py           Phone alert functions
  scan.py             Main runner — this is what you run daily
  run.bat             Double-click launcher (Windows)
  schedule.bat        Registers daily auto-run at 9 AM (run once)
  requirements.txt    Python dependencies
  .env.template       Copy this to .env and fill in keys
  .env                Your actual keys (never share this file)
  .portfolio_state.json   Auto-created — tracks your profit baseline
  report_YYYYMMDD.txt     Daily scan results saved here
  scan_log.txt            Auto-run log (when scheduled)
```

---

## Customizing Your Watchlists

Open `config.py` in any text editor to change what gets scanned:

```python
# Add any stock ticker here
STOCKS = [
    "NVDA","AMD","META","GOOGL","TSLA",
    "YOUR_TICKER_HERE",   # <-- just add to the list
]

# Add any CoinGecko coin ID here (find IDs at coingecko.com)
CRYPTOS = [
    "bitcoin","ethereum","solana",
    "your-coin-id",   # <-- lowercase, hyphens
]

# Change how much profit triggers a pull alert
PROFIT_ALERT_USD = 500   # change to 250 or 1000 as needed
```

---

## Troubleshooting

**"python is not recognized"**
Python is not installed or not in PATH. Reinstall from python.org, check "Add to PATH".

**"No module named..."**
Run: `pip install yfinance pandas numpy requests python-dotenv robin_stocks`

**Phone alerts not arriving**
- Confirm topic name in app exactly matches `NTFY_TOPIC` in `.env`
- Make sure ntfy notifications are allowed in your phone settings

**Robinhood login fails**
- Double-check email/password in `.env`
- If 2FA is on, disable it temporarily in Robinhood settings, run scan, re-enable

**Odds API returns nothing**
- Check `ODDS_API_KEY` is correct in `.env`
- Verify you haven't exceeded 500 requests at the-odds-api.com dashboard
- Some sports only have data during their season (NFL = Sept-Feb, NBA = Oct-Jun)

**Crypto scan slow or failing**
CoinGecko free tier rate-limits aggressively. Wait 60 seconds and retry.
If it keeps failing, the scan still works for stocks and bets.

---

## Quick Reference — Commands

```bash
# Run full scan (all three verticals)
python scan.py

# Run only specific sections
python scan.py --stocks-only
python scan.py --crypto-only
python scan.py --bets-only

# Test phone alert
python notify.py

# Run backtest on specific stocks
cd ../stock_engine
python backtester.py NVDA AMD META
```

---

## Summary Checklist

- [ ] Python installed (`python --version` works)
- [ ] `pip install` command ran successfully
- [ ] `.env.template` copied to `.env`
- [ ] `NTFY_TOPIC` set and ntfy app subscribed on phone
- [ ] `ODDS_API_KEY` added (the-odds-api.com)
- [ ] `QUIVERQUANT_KEY` added (quiverquant.com)
- [ ] Robinhood credentials added (optional)
- [ ] `python scan.py` ran successfully — phone buzzed
- [ ] `schedule.bat` run once — daily auto-scan registered

Once all boxes are checked, the system runs itself every day at 9 AM
and alerts your phone when anything worth acting on shows up.
