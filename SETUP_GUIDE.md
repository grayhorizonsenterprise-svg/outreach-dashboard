# Gray Horizons — Complete Setup Guide
### Stock Trend Predictor + Crypto Scanner + Sports & Politics Betting Engine

---

## What You Built

Two systems live in this project folder. You will set up both.

```
First Agentic Workflows/
  stock_engine/     Original stock system — deep technicals, congress tracker, backtester
  edge_engine/      Unified system — stocks + crypto + sports bets + phone alerts
  SETUP_GUIDE.md    This file
```

**stock_engine** — Run this when you want a detailed technical breakdown of individual stocks.
Includes a backtester that shows historical performance and a position sizer based on Kelly Criterion.

**edge_engine** — Run this every day. Scans everything at once, sends your phone alerts,
tracks your bi-weekly profit, and shows the best bets across DraftKings/FanDuel/BetMGM,
Polymarket politics, and all crypto/stocks in one report.

Both are standalone. You can run either one independently.

---

## What Each System Covers

| Feature | stock_engine | edge_engine |
|---|---|---|
| Stock technical signals (RSI, MACD, EMA) | Yes | Yes |
| Congress trade tracking (Pelosi + all members) | Yes | Yes |
| WSB / Reddit social sentiment | Yes | Yes |
| Backtester (1-year historical validation) | Yes | No |
| Kelly Criterion position sizing | Yes | No |
| Crypto (Bitcoin, ETH, SOL, altcoins) | No | Yes |
| Sports betting odds (DraftKings, FanDuel, etc.) | No | Yes |
| Politics betting (Polymarket) | No | Yes |
| Phone push alerts | No | Yes |
| Robinhood profit tracker + pull alerts | Yes | Yes |
| Daily auto-schedule | Yes | Yes |
| Files to manage | 9 files | 5 files |

---

## SECTION 1 — Prerequisites (Do This First, Both Systems Need It)

### 1A — Install Python

Open a terminal (press `Win + R`, type `cmd`, press Enter) and run:
```
python --version
```

If you see `Python 3.10` or higher, skip to Step 1B.

If you get an error:
1. Go to **python.org/downloads**
2. Click "Download Python 3.x.x"
3. Run the installer
4. On the first screen, check the box that says **"Add Python to PATH"** — this is critical
5. Click Install Now
6. After install, close and reopen the terminal, run `python --version` again

### 1B — Verify pip Works
```
pip --version
```
You should see something like `pip 24.x`. If not, run:
```
python -m ensurepip --upgrade
```

### 1C — How to Open a Terminal in a Specific Folder

You will need to do this for each system:
1. Open File Explorer
2. Navigate to the folder (e.g., `Downloads\First Agentic Workflows\edge_engine`)
3. Click the address bar at the top of File Explorer
4. Type `cmd` and press Enter
5. The black terminal window opens already pointed at that folder

---

## SECTION 2 — Phone Alerts Setup (One Time, Used by Both Systems)

The phone alert system uses **ntfy.sh** — completely free, no account needed, works on iPhone and Android.

### Step 1 — Install the App on Your Phone
1. Open App Store (iPhone) or Google Play (Android)
2. Search: **ntfy**
3. Install the app by "Philipp Heckel" (it has a blue bell icon)

### Step 2 — Create Your Alert Topic
1. Open the ntfy app
2. Tap the **+** button (bottom right or top right depending on platform)
3. Tap "Subscribe to topic"
4. Type a unique topic name that only you know — example: `ghe_alerts_2026`
   - Use only letters, numbers, and underscores
   - Make it unique — anyone who knows your topic name can send to it
5. Tap Subscribe

Write your topic name down. You will use it in both systems.

### Step 3 — Allow Notifications
On your phone, go to Settings → Notifications → ntfy → make sure notifications are ON.

### Step 4 — Test It Right Now
In your terminal (from anywhere):
```
curl -d "Test alert" ntfy.sh/YOUR_TOPIC_NAME
```
Replace `YOUR_TOPIC_NAME` with what you chose. Your phone should buzz within 5 seconds.

If curl is not available:
```
python -c "import requests; requests.post('https://ntfy.sh/YOUR_TOPIC_NAME', data='Test'.encode())"
```

---

## SECTION 3 — API Keys (All Free, Get These Before Setup)

You need four API keys total. Get them all now before starting — takes about 10 minutes combined.

### Key 1 — The Odds API (Sports Bets) — Free
Used for: live odds from DraftKings, FanDuel, BetMGM, Caesars, and 36 other books

1. Go to **the-odds-api.com**
2. Click "Get API Key" in the top navigation
3. Sign up with your email — no credit card required
4. Check your email for the confirmation link
5. Log in to the dashboard
6. Copy the API key shown on the dashboard

Free tier gives you **500 requests per month** — that covers daily scans for the whole month.

Keep this key — you will paste it into both `.env` files.

### Key 2 — QuiverQuant (Congress Trades) — Free
Used for: tracking Nancy Pelosi and all of Congress's stock purchases in real time

1. Go to **quiverquant.com/quiverapi**
2. Click "Sign Up" or "Get API Token"
3. Register with your email
4. Check your email and confirm
5. Log in — your API token is on the main dashboard page

Free tier gives you **100 requests per day** — more than enough for daily scans.

Keep this token — you will paste it into both `.env` files.

### Key 3 — NewsAPI (Optional — Enhances Sentiment) — Free
Used for: pulling news headlines about stocks to score sentiment

1. Go to **newsapi.org**
2. Click "Get API Key"
3. Sign up with email
4. Your key appears immediately after registration

Free tier: 100 requests per day. Optional — the system works without it, but adds context.

### Key 4 — Coinbase (Optional — Only for Auto-Order Placement)
Used for: placing crypto orders automatically from the system

**Note:** The system gets crypto price data from CoinGecko for free without any key.
This Coinbase key is ONLY needed if you want the system to place trades automatically.
For manual trading via the Coinbase app, skip this.

If you want it:
1. Log in to Coinbase Advanced
2. Go to Settings → API
3. Create a new API key with "Trade" permission
4. Copy the key and secret

---

## SECTION 4 — Stock Engine Setup

The stock engine is the original system. It does deep technical analysis, runs historical backtests, and tracks congress trades with a detailed score breakdown.

### Step 1 — Navigate to the Folder
Open a terminal in: `Downloads\First Agentic Workflows\stock_engine`

### Step 2 — Install Dependencies
```
pip install yfinance pandas numpy requests robin_stocks pyotp python-dotenv
```
Wait for it to finish.

### Step 3 — Create the .env File
1. In the `stock_engine` folder, find `.env.template`
2. Right-click → Copy → Paste in the same folder
3. Rename the copy from `.env.template` to `.env`
4. Right-click `.env` → Open with Notepad

Paste your keys into the file:
```
NTFY_TOPIC=ghe_alerts_2026

QUIVERQUANT_KEY=your_quiverquant_token_here

RH_USERNAME=your_robinhood_email@gmail.com
RH_PASSWORD=your_robinhood_password

NEWS_API_KEY=your_newsapi_key_here
ALPHA_VANTAGE_KEY=
```

Save and close Notepad.

### Step 4 — Run the Stock Screener
In the terminal:
```
python screener.py
```

This scans the default watchlist of 25 stocks and prints ranked picks.
The first run takes about 90 seconds while it downloads price data.

Output looks like:
```
*** NVDA    score= 74.2  RSI= 62.5  STRONG_BUY
 *  ARM     score= 68.8  RSI= 67.3  BUY
     TSLA   score= 40.2  RSI= 48.9  NEUTRAL
```

### Step 5 — Run a Backtest
Test how the signal performed over the past year on specific tickers:
```
python backtester.py NVDA AMD META PLTR TSLA
```

Output shows:
- **Strat%** — what the system's signal returned over 1 year
- **B&H%** — what buy-and-hold returned (compare to see if signal adds value)
- **WinRate** — percentage of trading days the signal was correct
- **Sharpe** — risk-adjusted return (above 1.0 is good, above 1.5 is excellent)
- **Alpha** — how much better or worse the signal did vs. buy-and-hold

### Step 6 — Check Position Sizing
Before placing any trade, run the position sizer to know how much to put in:
```
python position_sizer.py
```

This uses Kelly Criterion to calculate the right bet size based on your account balance,
the signal score, and the current market regime (bull/bear/chop).

### Step 7 — Run the Full Master Scan (All Sources Combined)
```
python master_scan.py
```

This pulls from all four sources at once — technical signals, congress trades,
social sentiment, and WSB mentions — and produces a unified ranked list.
It also checks your Robinhood portfolio and sends the profit alert if threshold is hit.

### Step 8 — Schedule Stock Engine to Run Daily at 9 AM
Double-click `schedule_daily.bat` inside the `stock_engine` folder.

This registers the master scan to run every morning at 9 AM automatically.
You do not need to open anything — it runs in the background.

### Stock Engine File Reference
```
stock_engine/
  screener.py           Technical signal scan — run this for individual picks
  backtester.py         1-year historical validation — run before trusting a signal
  position_sizer.py     Kelly Criterion sizing — run before placing any trade
  congress_tracker.py   Congress trade data — run standalone to see congress picks
  social_sentiment.py   Reddit WSB + StockTwits trending — run for social signals
  master_scan.py        All sources combined — this is the main daily runner
  robinhood_tracker.py  Robinhood balance + profit alert checker
  run.bat               Double-click to run master scan
  schedule_daily.bat    Double-click once to register 9 AM auto-run
  requirements.txt      Python dependencies
  .env.template         Template — copy to .env and fill in keys
  .env                  Your actual keys (never share this file)
```

---

## SECTION 5 — Edge Engine Setup

The edge engine is the simplified unified system. One scan covers everything:
stocks, crypto, sports bets, politics bets, and profit tracking.
This is the one you run every day.

### Step 1 — Navigate to the Folder
Open a terminal in: `Downloads\First Agentic Workflows\edge_engine`

### Step 2 — Install Dependencies
```
pip install yfinance pandas numpy requests python-dotenv robin_stocks pyotp
```
(Skip if you already did this for stock_engine — same packages.)

### Step 3 — Create the .env File
1. In the `edge_engine` folder, find `.env.template`
2. Right-click → Copy → Paste in the same folder
3. Rename the copy to `.env`
4. Open `.env` with Notepad

Fill it in:
```
NTFY_TOPIC=ghe_alerts_2026

ODDS_API_KEY=your_theoddsapi_key_here

QUIVERQUANT_KEY=your_quiverquant_token_here

RH_USERNAME=your_robinhood_email@gmail.com
RH_PASSWORD=your_robinhood_password

COINBASE_API_KEY=
COINBASE_API_SECRET=
```

Save and close.

### Step 4 — Run Your First Full Scan
Double-click `run.bat` inside the `edge_engine` folder.

OR in the terminal:
```
python scan.py
```

The scan runs in this order:
1. Fetches congress buy data from QuiverQuant
2. Scans all stocks on your watchlist with composite scoring
3. Scans all cryptos on your watchlist via CoinGecko (no key needed)
4. Pulls live odds from 40+ sportsbooks and finds value bets
5. Pulls Polymarket politics markets and ranks by probability
6. Checks your Robinhood balance against your bi-weekly baseline
7. Sends a summary alert to your phone

Total time: 60-90 seconds.

### Step 5 — Schedule Daily Auto-Run at 9 AM
Double-click `schedule.bat` inside the `edge_engine` folder.

That's it. The scan runs at 9 AM every day from now on.

Results are saved to `scan_log.txt` in the same folder so you can review them later.

### Edge Engine File Reference
```
edge_engine/
  config.py           All settings — watchlists, thresholds, keys
  signals.py          All signal logic — stocks, crypto, bets, congress
  notify.py           Phone alert functions
  scan.py             Main daily runner — run this every day
  run.bat             Double-click launcher
  schedule.bat        Double-click once to register 9 AM auto-run
  requirements.txt    Python dependencies
  .env.template       Template — copy to .env and fill in keys
  .env                Your actual keys (never share this file)
  .portfolio_state.json   Auto-created — tracks profit baseline
  scan_log.txt            Auto-run output log
```

---

## SECTION 6 — Sports Betting (DraftKings / FanDuel)

The edge engine finds value bets — spots where the true win probability
is higher than what the sportsbook's odds imply. This is the only way to have
a long-term edge over the house.

### How It Works
1. The system pulls odds from every major book (DraftKings, FanDuel, BetMGM, etc.)
2. It calculates the "vig-free" true probability for each side by averaging and devigging all books
3. It compares that true probability to each book's vig-inclusive odds
4. It flags bets where the edge is 3% or more above the vig — meaning your bet has positive expected value

### Reading a Bet Signal
```
SPORT      BET                ODDS    BOOK          WIN%    EDGE     EV/$100   CONF
NFL        Kansas City ML     -180    DraftKings    72%    +4.2%    $+3.80    HIGH
NBA        Lakers +5.5        +110    FanDuel       61%    +3.8%    $+2.10    MEDIUM
```

- **ODDS** — what DraftKings is offering. Negative = favorite, positive = underdog
- **WIN%** — the true probability after removing the house's cut
- **EDGE** — how much value you're getting above the vig. Positive = good bet
- **EV/$100** — if you bet $100 on this, your long-run profit per bet
- **CONF** — HIGH means 65%+ win probability. MEDIUM is 55-65%

### What to Actually Bet

Only bet when ALL THREE are true:
1. EV is positive (the number after the $ sign is positive)
2. Edge is 3% or more
3. Confidence is MEDIUM or HIGH

Never bet negative EV plays regardless of how confident you feel.

### How Much to Bet — The Kelly Rule

| Bankroll | Conservative (3%) | Standard (5%) |
|---|---|---|
| $50 | $1.50 | $2.50 |
| $100 | $3.00 | $5.00 |
| $250 | $7.50 | $12.50 |
| $500 | $15.00 | $25.00 |
| $1,000 | $30.00 | $50.00 |

Start at 3% until you have 50+ bets logged and can verify your win rate.
Move to 5% after you've proven the system works for your picks.

Never go above 5% on a single game.

### Placing the Bet on DraftKings
1. Open DraftKings app
2. Go to the game the system flagged
3. Find the same bet (ML, spread, or total) the system recommended
4. Confirm the odds on DraftKings match or beat what the system showed
5. If the odds are worse (e.g., system showed -180 but DraftKings shows -200), recalculate or skip
6. Place the bet for the amount from the table above

### Seasons by Sport
- NFL: September through February
- NBA: October through June (playoffs into June)
- MLB: April through October
- NHL: October through June
- MMA: Year-round (UFC events every 2-3 weeks)
- College Football: August through January

Outside of season, the system will show no data for that sport — this is normal.

---

## SECTION 7 — Politics Betting (Polymarket)

Polymarket is a crypto-based prediction market where people bet on real-world outcomes.
Unlike sportsbooks, there is no vig built in — the market price IS the implied probability.
The edge here comes from finding markets where the crowd is wrong.

### How It Works
The system pulls the top 50 highest-volume markets from Polymarket daily,
filters out markets that are already basically decided (above 97% or below 3%),
and ranks the rest by how far they are from a coin flip.

Markets priced at 65-85% represent strong market consensus that is not yet certain.
These are the best risk/reward spots.

### How to Actually Bet on Polymarket
Polymarket requires a crypto wallet (not a bank account). Here's how:
1. Go to **polymarket.com** on desktop
2. Connect a crypto wallet — they support MetaMask and others
3. Fund with USDC (you can buy USDC on Coinbase then transfer)
4. Search for the market the system flagged
5. Buy "Yes" or "No" shares for the side the system recommends
6. Shares pay out $1.00 if you win. If you buy at $0.72, you profit $0.28 per share

Minimum meaningful bet: $10-25 (buying 10-25 shares at ~$0.70 = $7-17.50 profit if correct)

---

## SECTION 8 — Crypto (Coinbase / CashApp)

The system uses CoinGecko for live crypto data — no API key needed. It scores every coin
on your watchlist based on 1-hour momentum, 24-hour change, 7-day trend, and volume vs.
market cap. The output looks identical to the stock scanner.

### Reading a Crypto Signal
```
#1  SOL    score=71.2  $148.40   +1.2% 1h   +6.8% 24h   +12.1% 7d   BUY   high volume
```

- **Score 65+** = Strong momentum signal, consider entering
- **Score 50-64** = Watch, momentum building
- **Below 50** = Skip or wait
- **High volume** = unusual activity relative to market cap — confirms move is real

### Acting on It via Coinbase
1. Open the Coinbase app
2. Search the coin symbol (SOL, APT, ETH, etc.)
3. Tap Trade → Buy
4. Enter your dollar amount (suggested: no more than 10-15% of your total crypto budget per coin)
5. Set a price alert in Coinbase at +20% of your buy price — this is your take-profit trigger

### Acting on It via CashApp
CashApp only supports Bitcoin. For everything else use Coinbase.
1. Tap the $ icon at the bottom
2. Tap Investing → Bitcoin → Buy
3. Enter amount
4. Set a price alert

### Profit Rule for Crypto
- Up 20%: sell half your position, let the rest ride
- Up 50%: sell another quarter, keep 25% for potential further upside
- Down 15%: this is your stop loss — sell and preserve capital

Crypto moves fast. The system gives you the signal — you have to act on it.

---

## SECTION 9 — Robinhood Profit Tracker

The system tracks your Robinhood balance every time the scan runs.
When your portfolio is up $500 from your starting point this period,
your phone receives an urgent alert telling you to pull profits.

### How the Baseline Works
- First run: system records your current balance as the baseline
- Every scan after that: compares current balance to baseline
- When current balance is $500+ above baseline: sends urgent phone alert
- When you get the alert: go to Robinhood, sell enough to pull the profit, transfer to bank
- System automatically resets the baseline to your new balance after the alert
- Every 14 days: baseline resets regardless, starting a new period

### If Robinhood Login Fails
Robinhood requires credentials in `.env`:
```
RH_USERNAME=your_email@gmail.com
RH_PASSWORD=your_password
```

If you have two-factor authentication (2FA) enabled:
- Go to Robinhood → Profile → Settings → Security → Two-Factor Authentication
- Temporarily disable it, run the scan once to set the baseline, then re-enable
- OR keep 2FA enabled and skip the Robinhood tracker — track your balance manually

### Manual Balance Tracking (If You Skip Robinhood Integration)
You can track manually by editing `.portfolio_state.json` in the `edge_engine` folder:
```json
{
  "baseline_value": 100.00,
  "baseline_date": "2026-04-30T09:00:00"
}
```
Update `baseline_value` to your current balance whenever you reset after a profit pull.

---

## SECTION 10 — Daily Workflow (Once Everything Is Set Up)

This is how you use the system once it's running.

### The System Does Automatically (9 AM Daily)
- Scans all stocks on your watchlist
- Scans all crypto on your watchlist
- Pulls live sports odds from all books
- Checks Polymarket for politics opportunities
- Checks your Robinhood balance
- Sends your phone a summary notification

### What You Do When You Get the Morning Alert
1. Read the summary alert — it shows top stock, top crypto, and top bet
2. Open the full report: `edge_engine/report_YYYYMMDD.txt` to see the full ranked lists
3. Decide which signals to act on using the scoring guide below
4. Place trades/bets through Robinhood, Coinbase, DraftKings, or Polymarket manually

### When to Act vs. Wait
| Signal | Score | Action |
|---|---|---|
| Stock STRONG BUY | 75+ | Enter position, size per Kelly table |
| Stock BUY | 60-74 | Enter smaller position or add to existing |
| Stock WATCH | 45-59 | Put on watchlist, wait for score to improve |
| Stock SKIP | Below 45 | Do nothing |
| Crypto BUY | 65+ | Consider entry, set 20% take-profit alert in app |
| Crypto WATCH | 50-64 | Monitor, do not buy yet |
| Bet HIGH confidence | 65%+ win, EV positive | Place bet per Kelly table |
| Bet MEDIUM confidence | 55-65% win, EV positive | Smaller bet or skip |
| Any bet with negative EV | Any | Skip — no exceptions |

---

## SECTION 11 — Customizing Your Watchlists

Open `edge_engine/config.py` in Notepad to customize what gets scanned.

### Adding Stocks
```python
STOCKS = [
    "NVDA","AMD","META","GOOGL","MSFT","AAPL","AMZN","TSLA","AVGO","PLTR",
    "SMCI","RKLB","IONQ","ARM","CRWD","SHOP","MSTR","COIN","HOOD","SOFI",
    "YOUR_TICKER",    # add any valid stock ticker here
]
```

### Adding Cryptos
Find the correct CoinGecko ID at **coingecko.com** — search the coin, the ID is in the URL.
Example: bitcoin, ethereum, solana, avalanche-2, the-graph

```python
CRYPTOS = [
    "bitcoin","ethereum","solana","avalanche-2","chainlink",
    "your-coin-id",    # lowercase, use hyphens not spaces
]
```

### Changing the Profit Pull Threshold
```python
PROFIT_ALERT_USD = 500    # change to 250 for more frequent alerts
BIWEEKLY_DAYS    = 14     # change to 7 for weekly resets
```

### Changing the Minimum Signal Score for Alerts
```python
MIN_SIGNAL_SCORE = 65     # only alert picks above this score
MIN_BET_EDGE_PCT  = 3.0   # only alert bets with at least this % edge
```

For the stock engine, open `stock_engine/screener.py` and edit the `WATCHLIST` variable at the top.

---

## SECTION 12 — Troubleshooting

### "python is not recognized" or "'python' is not recognized"
Python is not in your PATH. Fix:
1. Open Windows search → "Environment Variables"
2. Click "Edit the system environment variables"
3. Click "Environment Variables"
4. Under "System variables", find "Path", click Edit
5. Click New → type the path to your Python install (usually `C:\Python311` or `C:\Users\YourName\AppData\Local\Programs\Python\Python311`)
6. Click OK three times, restart terminal

OR simply reinstall Python from python.org and check "Add to PATH" during install.

### "No module named 'yfinance'" (or any other module)
```
pip install yfinance pandas numpy requests python-dotenv robin_stocks pyotp
```

If pip itself fails:
```
python -m pip install yfinance pandas numpy requests python-dotenv robin_stocks pyotp
```

### Phone alerts not arriving
1. Open ntfy app — make sure you subscribed to the exact same topic name that is in `.env`
2. Go to your phone Settings → Notifications → ntfy → confirm notifications are ON
3. Try the curl test from Section 2 to verify the topic works
4. Topic names are case sensitive — `GHE_Alerts` and `ghe_alerts` are different topics

### Robinhood login fails
1. Double-check email and password in `.env` — no extra spaces
2. If 2FA is enabled: disable it temporarily in Robinhood → Settings → Security
3. If you recently changed your password, update `.env`
4. Try logging in to Robinhood.com in a browser first to confirm credentials work

### Odds API returns no data
1. Verify `ODDS_API_KEY` is correct — log in to the-odds-api.com dashboard to confirm
2. Check your request count — free tier allows 500/month
3. Some sports are out of season (NFL is only Sept-Feb) — normal to see no results
4. Run just the bets section to isolate: `python scan.py --bets-only`

### QuiverQuant / Congress data missing
1. Verify `QUIVERQUANT_KEY` in `.env`
2. Free tier allows 100 requests per day — if you ran scans many times, you may have hit the limit
3. The system falls back to demo data automatically — it will say "[DEMO MODE]" if key is missing or invalid

### Crypto scan fails or shows nothing
CoinGecko rate-limits free users. Wait 60 seconds between scans.
If it keeps failing: the stock and bets sections still work — the scan will skip crypto and continue.

### The scheduled task is not running at 9 AM
1. Press `Win + S` → search "Task Scheduler"
2. Look for "EdgeEngineDailyScan" or "StockEngineDailyScan"
3. Right-click → Run to test it manually
4. Check "Last Run Result" — a value of `0x0` means it ran successfully
5. If the task is missing, re-run `schedule.bat`

### ".env file not found" error
Make sure you named the file exactly `.env` (not `.env.txt` or `env`).
In File Explorer, go to View → Check "File name extensions" to see the real extension.
If it shows `.env.txt`, rename it and delete the `.txt` part.

---

## SECTION 13 — Quick Reference Commands

All commands are run from the terminal inside the relevant folder.

### Edge Engine (Daily Use)
```
python scan.py                  Full scan — stocks + crypto + bets + profit check
python scan.py --stocks-only    Only stocks
python scan.py --crypto-only    Only crypto
python scan.py --bets-only      Only sports and politics bets
python notify.py                Test phone alert
```

### Stock Engine (Deep Analysis)
```
python screener.py              Scan all stocks — technical signals
python master_scan.py           Full scan — all sources combined
python backtester.py NVDA AMD   Backtest signal on specific tickers over 1 year
python position_sizer.py        Calculate position size for your account
python congress_tracker.py      Show congress buy signals only
python social_sentiment.py      Show WSB + StockTwits trending only
```

---

## SECTION 14 — Master Setup Checklist

Work through this top to bottom. Check each box as you complete it.

### Prerequisites
- [ ] Python 3.10 or higher installed (`python --version` works in terminal)
- [ ] pip works (`pip --version` shows a version number)

### Phone Alerts
- [ ] ntfy app installed on phone
- [ ] Subscribed to a unique topic name in the ntfy app
- [ ] Topic name written down: `______________________________`
- [ ] Test alert received on phone (curl or python test from Section 2)

### API Keys — Collected
- [ ] The Odds API key obtained from the-odds-api.com
- [ ] QuiverQuant token obtained from quiverquant.com/quiverapi
- [ ] NewsAPI key obtained from newsapi.org (optional)

### Stock Engine Setup
- [ ] Terminal opened in `stock_engine` folder
- [ ] `pip install` command completed successfully
- [ ] `.env.template` copied to `.env` in `stock_engine` folder
- [ ] `NTFY_TOPIC` filled in `.env`
- [ ] `QUIVERQUANT_KEY` filled in `.env`
- [ ] `RH_USERNAME` and `RH_PASSWORD` filled in `.env`
- [ ] `python screener.py` ran successfully — saw ranked stock list
- [ ] `python backtester.py NVDA AMD META` ran successfully — saw backtest results
- [ ] `python master_scan.py` ran successfully — full output printed
- [ ] `schedule_daily.bat` double-clicked — stock scan registered for 9 AM

### Edge Engine Setup
- [ ] Terminal opened in `edge_engine` folder
- [ ] `pip install` command completed (or skipped if already done for stock engine)
- [ ] `.env.template` copied to `.env` in `edge_engine` folder
- [ ] `NTFY_TOPIC` filled in `.env` (same topic as stock engine)
- [ ] `ODDS_API_KEY` filled in `.env`
- [ ] `QUIVERQUANT_KEY` filled in `.env`
- [ ] `RH_USERNAME` and `RH_PASSWORD` filled in `.env`
- [ ] `python scan.py` ran successfully — full output printed
- [ ] Phone received summary alert during scan
- [ ] `schedule.bat` double-clicked — daily scan registered for 9 AM

### Final Checks
- [ ] Both systems produce output without errors
- [ ] Phone is receiving alerts
- [ ] Task Scheduler shows both tasks ("EdgeEngineDailyScan" and "StockEngineDailyScan")
- [ ] Understand the scoring guide (Section 10) before placing any trades or bets

---

## SECTION 15 — Important Reminders

**On Stocks:**
No system predicts the market with certainty. The scores show statistical edge,
not guaranteed winners. Always use position sizing from Section 10.
Never put more than 10-15% of your total account into any single stock.

**On Crypto:**
Higher volatility than stocks — moves faster in both directions.
Set price alerts in Coinbase or CashApp when you buy so you know when to take profit.
The 20% take-profit, 15% stop-loss rules exist to protect your capital.

**On Sports Betting:**
The house edge (vig) is 4.5-5% per bet. You only beat it long-term by finding positive EV spots.
The system finds those spots — but you still lose individual bets even when EV is positive.
Only bet what you can afford to lose entirely. Never chase losses.

**On Robinhood Profit Pulls:**
When you get the $500 alert — pull it. Do not leave profits in the market indefinitely.
Pulled profit is real profit. Unrealized gains disappear.

**Security:**
- Never share your `.env` files — they contain your account passwords
- Never commit `.env` to GitHub or any public service
- If you think credentials were exposed, change your passwords immediately
