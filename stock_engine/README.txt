STOCK TREND PREDICTION ENGINE
==============================
Standalone — no connection to outreach agents, email system, or other tools.

FILES:
  screener.py      — runs the composite signal scan across your watchlist
  backtester.py    — validates signal quality against 1yr historical data
  position_sizer.py— Kelly-criterion position sizing calculator
  run.bat          — one-click: installs deps, runs screener + backtest

QUICK START:
  1. Double-click run.bat
     OR
  2. pip install -r requirements.txt
     python screener.py

OPTIONAL (free APIs to unlock sentiment scoring):
  Set env vars before running:
    set NEWS_API_KEY=your_key_from_newsapi.org
    set ALPHA_VANTAGE_KEY=your_key_from_alphavantage.co

OUTPUT:
  signals.csv — ranked tickers with composite scores saved here

INTERPRETATION:
  Score 75-100  STRONG_BUY — high conviction, size per position_sizer.py
  Score 60-74   BUY        — moderate conviction
  Score 40-59   NEUTRAL    — skip or watch
  Below 40      SELL       — avoid or consider puts

RISK REMINDER:
  No system predicts the market with certainty.
  Never risk more than you can afford to lose entirely.
  Use position_sizer.py to keep any single trade under 25% of capital.
