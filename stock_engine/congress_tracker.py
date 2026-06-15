"""
Congress Trade Tracker
Primary: QuiverQuant API (free tier, QUIVERQUANT_KEY in .env)
Fallback: House Stock Watcher public S3 dataset (no key, always free)

Tracks BUYS (bullish signal) and SELLS (dump/short signal separately).
"""

import requests
import pandas as pd
import os
from datetime import datetime, timedelta

QUIVER_KEY = os.getenv("QUIVERQUANT_KEY", "")
BASE_URL   = "https://api.quiverquant.com/beta"

# Free, no-auth endpoints maintained by opensecrets community projects
HOUSE_DATA_URL  = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_DATA_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"

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


def _parse_house_data(lookback_days: int) -> tuple[list, list]:
    """
    Pull from House Stock Watcher free S3 endpoint — no key required.
    Returns (buy_records, sell_records).
    """
    cutoff = datetime.now() - timedelta(days=lookback_days)
    buy_records, sell_records = [], []
    try:
        r = requests.get(HOUSE_DATA_URL, timeout=20,
                         headers={"User-Agent": "StockEngine/1.0"})
        if r.status_code != 200:
            return [], []
        raw = r.json()
        if not isinstance(raw, list):
            return [], []
        for t in raw:
            ticker = str(t.get("ticker", "")).strip().upper()
            if not ticker or ticker in ("N/A", "--") or len(ticker) > 5 or not ticker.isalpha():
                continue
            date_raw = t.get("transaction_date", t.get("disclosure_date", ""))
            try:
                tx_date = datetime.strptime(str(date_raw)[:10], "%Y-%m-%d")
            except ValueError:
                continue
            if tx_date < cutoff:
                continue

            tx_type  = str(t.get("type", "")).lower()
            member   = str(t.get("representative", "")).strip()
            amount   = str(t.get("amount", ""))
            size_pts = SIZE_SCORE.get(amount, 1)
            days_ago  = (datetime.now() - tx_date).days
            recency_w = max(0.1, 1.0 - (days_ago / lookback_days))
            quality_w = 2.0 if any(h in member for h in HIGH_SIGNAL_MEMBERS) else 1.0
            rec = {
                "ticker": ticker, "member": member,
                "date": tx_date.strftime("%Y-%m-%d"), "amount": amount,
                "size_pts": size_pts, "recency_w": recency_w, "quality_w": quality_w,
                "raw_score": size_pts * recency_w * quality_w,
            }
            if "purchase" in tx_type or "buy" in tx_type:
                buy_records.append(rec)
            elif "sale" in tx_type or "sell" in tx_type:
                sell_records.append(rec)
        print(f"  [Congress] House Watcher: {len(buy_records)} buys, {len(sell_records)} sells ({lookback_days}d)")
    except Exception as e:
        print(f"  [!] House Stock Watcher fetch failed: {e}")
    return buy_records, sell_records


def get_congress_signals(lookback_days: int = 90) -> pd.DataFrame:
    """
    Returns DataFrame of tickers ranked by congress BUY activity (bullish signal).
    Tries QuiverQuant (if key set), then falls back to free House Stock Watcher data.
    NEVER uses hardcoded demo data — that causes stale, fake scores.
    """
    buy_records: list = []

    if QUIVER_KEY:
        cutoff = datetime.now() - timedelta(days=lookback_days)
        raw    = _quiver_get("live/congresstrading")
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
            buy_records.append({
                "ticker": ticker, "member": member,
                "date": tx_date.strftime("%Y-%m-%d"), "amount": amount,
                "size_pts": size_pts, "recency_w": recency_w, "quality_w": quality_w,
                "raw_score": size_pts * recency_w * quality_w,
            })
        print(f"  [Congress] QuiverQuant: {len(buy_records)} buy records")
    else:
        # Free fallback — no key needed
        print("  [Congress] No QUIVERQUANT_KEY — using House Stock Watcher (free)")
        buy_records, _ = _parse_house_data(lookback_days)

    return _aggregate(buy_records)


def get_congress_sells(lookback_days: int = 60) -> pd.DataFrame:
    """
    Returns tickers Congress members are SELLING — potential dump/short signals.
    High sell score = insiders exiting before bad news. Watch these for shorting.
    """
    sell_records: list = []

    if QUIVER_KEY:
        cutoff = datetime.now() - timedelta(days=lookback_days)
        raw    = _quiver_get("live/congresstrading")
        for t in raw:
            tx_type = str(t.get("Transaction", "")).lower()
            if "sale" not in tx_type and "sell" not in tx_type:
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
            quality_w = 2.5 if any(h in member for h in HIGH_SIGNAL_MEMBERS) else 1.0
            sell_records.append({
                "ticker": ticker, "member": member,
                "date": tx_date.strftime("%Y-%m-%d"), "amount": amount,
                "size_pts": size_pts, "recency_w": recency_w, "quality_w": quality_w,
                "raw_score": size_pts * recency_w * quality_w,
            })
    else:
        _, sell_records = _parse_house_data(lookback_days)

    return _aggregate_sells(sell_records)


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


def _aggregate_sells(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    agg = df.groupby("ticker").agg(
        dump_score=    ("raw_score",  "sum"),
        sell_count=    ("ticker",     "count"),
        unique_sellers=("member",     "nunique"),
        last_sell=     ("date",       "max"),
        pelosi_sold=   ("member", lambda x: any("Pelosi" in m for m in x)),
    ).reset_index()
    mx = agg["dump_score"].max()
    if mx > 0:
        agg["dump_score"] = (agg["dump_score"] / mx * 100).round(1)
    return agg.sort_values("dump_score", ascending=False).reset_index(drop=True)


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
