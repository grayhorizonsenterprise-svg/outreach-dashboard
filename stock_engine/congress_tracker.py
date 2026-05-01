"""
Congress Trade Tracker — QuiverQuant API (free tier)

Setup (one-time, 2 minutes):
  1. Go to quiverquant.com/quiverapi → sign up (free)
  2. Copy your API token
  3. Add to .env: QUIVERQUANT_KEY=your_token_here

QuiverQuant free tier: 100 requests/day — more than enough for daily scans.
Covers ALL of Congress: House + Senate, including Nancy Pelosi.
"""

import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from collections import defaultdict

QUIVER_KEY = os.getenv("QUIVERQUANT_KEY", "")
BASE_URL   = "https://api.quiverquant.com/beta"

HEADERS = lambda key: {
    "Accept":        "application/json",
    "Authorization": f"Token {key}",
    "User-Agent":    "StockEngine/1.0",
}

# Members with historically strong signal (buy these when they buy)
HIGH_SIGNAL_MEMBERS = {
    "Nancy Pelosi", "Paul Pelosi",
    "Dan Crenshaw", "Michael McCaul",
    "Brian Mast",   "Josh Gottheimer",
    "Ro Khanna",    "Pete Sessions",
    "Mark Green",   "Tim Walberg",
}

SIZE_SCORE = {
    "$1,001 - $15,000":      1,
    "$15,001 - $50,000":     2,
    "$50,001 - $100,000":    3,
    "$100,001 - $250,000":   4,
    "$250,001 - $500,000":   5,
    "$500,001 - $1,000,000": 6,
    "Over $1,000,000":       7,
}


def _quiver_get(endpoint: str) -> list:
    if not QUIVER_KEY:
        return []
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS(QUIVER_KEY), timeout=15)
        if r.status_code == 401:
            print("  [!] QuiverQuant: invalid API key — check QUIVERQUANT_KEY in .env")
            return []
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [!] QuiverQuant fetch failed: {e}")
        return []


def get_congress_signals(lookback_days: int = 90) -> pd.DataFrame:
    """
    Returns DataFrame of tickers ranked by congress buy activity.
    Score = weighted: recency + size + member quality.
    """
    if not QUIVER_KEY:
        print("  [!] No QUIVERQUANT_KEY — add it to .env for congress data.")
        print("      Get free key at: quiverquant.com/quiverapi")
        return _demo_signals()

    cutoff = datetime.now() - timedelta(days=lookback_days)
    raw    = _quiver_get("live/congresstrading")

    records = []
    for t in raw:
        tx_type = str(t.get("Transaction", "")).lower()
        if "purchase" not in tx_type and "buy" not in tx_type:
            continue

        ticker = str(t.get("Ticker", "")).strip().upper()
        if not ticker or len(ticker) > 5 or not ticker.isalpha():
            continue

        date_raw = t.get("Date", t.get("TransactionDate", ""))
        try:
            tx_date = datetime.strptime(str(date_raw)[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if tx_date < cutoff:
            continue

        member   = str(t.get("Representative", t.get("Senator", ""))).strip()
        amount   = str(t.get("Range", t.get("Amount", "")))
        size_pts = SIZE_SCORE.get(amount, 1)

        days_ago  = (datetime.now() - tx_date).days
        recency_w = max(0.1, 1.0 - (days_ago / lookback_days))
        quality_w = 2.0 if any(h in member for h in HIGH_SIGNAL_MEMBERS) else 1.0

        records.append({
            "ticker":    ticker,
            "member":    member,
            "date":      tx_date.strftime("%Y-%m-%d"),
            "amount":    amount,
            "size_pts":  size_pts,
            "recency_w": recency_w,
            "quality_w": quality_w,
            "raw_score": size_pts * recency_w * quality_w,
        })

    return _aggregate(records)


def _aggregate(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    agg = df.groupby("ticker").agg(
        congress_score=("raw_score",  "sum"),
        buy_count=     ("ticker",     "count"),
        unique_members=("member",     "nunique"),
        last_buy=      ("date",       "max"),
        pelosi_bought= ("member", lambda x: any("Pelosi" in m for m in x)),
    ).reset_index()

    mx = agg["congress_score"].max()
    if mx > 0:
        agg["congress_score"] = (agg["congress_score"] / mx * 100).round(1)

    return agg.sort_values("congress_score", ascending=False).reset_index(drop=True)


def _demo_signals() -> pd.DataFrame:
    """
    Placeholder data so the rest of the system runs without a key.
    Based on historically frequent Pelosi/Congress buys — for demo only.
    Replace with live data once QUIVERQUANT_KEY is set.
    """
    demo = [
        {"ticker": "NVDA", "congress_score": 88, "buy_count": 12, "unique_members": 7, "last_buy": "2025-04-01", "pelosi_bought": True},
        {"ticker": "MSFT", "congress_score": 74, "buy_count": 9,  "unique_members": 5, "last_buy": "2025-03-28", "pelosi_bought": False},
        {"ticker": "GOOGL","congress_score": 70, "buy_count": 8,  "unique_members": 6, "last_buy": "2025-03-20", "pelosi_bought": True},
        {"ticker": "AAPL", "congress_score": 65, "buy_count": 7,  "unique_members": 5, "last_buy": "2025-03-15", "pelosi_bought": False},
        {"ticker": "AMZN", "congress_score": 60, "buy_count": 6,  "unique_members": 4, "last_buy": "2025-03-10", "pelosi_bought": False},
    ]
    print("  [DEMO MODE] Add QUIVERQUANT_KEY to .env for live congress data.")
    return pd.DataFrame(demo)


def print_congress_top(n: int = 20):
    print(f"\n{'='*65}")
    print(f"  CONGRESS TRADE SIGNALS  |  last 90 days")
    print(f"  Source: QuiverQuant {'(LIVE)' if QUIVER_KEY else '(DEMO — get free key at quiverquant.com)'}")
    print(f"{'='*65}")
    df = get_congress_signals()
    if df.empty:
        return df
    for _, r in df.head(n).iterrows():
        pelosi_flag = " *** PELOSI" if r["pelosi_bought"] else ""
        print(
            f"  {r['ticker']:6s} | score={r['congress_score']:5.1f} | "
            f"buys={int(r['buy_count']):3d} | members={int(r['unique_members']):2d} | "
            f"last={r['last_buy']}{pelosi_flag}"
        )
    return df


if __name__ == "__main__":
    print_congress_top()
