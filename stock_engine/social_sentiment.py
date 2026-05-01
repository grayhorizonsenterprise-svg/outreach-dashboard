"""
Social Sentiment Scanner
Sources: Reddit WallStreetBets (public JSON) + StockTwits (free API)
No API key required for basic use.
"""

import requests
import re
import json
from collections import Counter
from datetime import datetime


WSB_URL       = "https://www.reddit.com/r/wallstreetbets/hot.json?limit=100"
STOCKTWITS_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"

HEADERS = {"User-Agent": "StockEngine/1.0 (educational use)"}

# Filter out common false positives
IGNORE = {
    "A", "I", "FOR", "ARE", "BE", "IT", "OR", "ON", "IN", "TO",
    "AT", "IS", "SO", "DO", "MY", "BY", "IF", "UP", "GO", "OK",
    "ALL", "NEW", "NOW", "THE", "AND", "BUT", "NOT", "YET", "FED",
    "CEO", "IPO", "ETF", "SEC", "AI", "DD", "OG", "IV", "PE", "EPS",
    "WSB", "LOL", "IMO", "ITM", "OTM", "ATM", "YTD", "EOD", "EOW",
    # Common false positives (games, abbreviations, non-tickers)
    "GTA", "NBA", "NFL", "USA", "GPU", "CPU", "RAM", "SSD", "DCA",
    "YOLO", "FOMO", "HODL", "MOON", "APE", "RIP", "GOD", "CUM",
    "WIFE", "LOSS", "GAIN", "CASH", "WEEK", "YEAR", "BACK",
    "CALL", "PUT", "WAR", "LAW", "TAX", "IRS", "IMF", "GDP",
}


def _extract_tickers_from_text(text: str) -> list[str]:
    found = re.findall(r"\b\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b", text)
    tickers = []
    for a, b in found:
        t = a or b
        if t and t not in IGNORE and len(t) >= 2:
            tickers.append(t)
    return tickers


def get_wsb_trending() -> dict[str, int]:
    """Returns ticker -> mention_count from top WSB posts."""
    try:
        r = requests.get(WSB_URL, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        posts = r.json()["data"]["children"]
        counts: Counter = Counter()
        for post in posts:
            data = post["data"]
            text = f"{data.get('title', '')} {data.get('selftext', '')}"
            for t in _extract_tickers_from_text(text):
                counts[t] += 1
        return dict(counts.most_common(50))
    except Exception as e:
        print(f"  [!] WSB fetch failed: {e}")
        return {}


def get_stocktwits_trending() -> list[str]:
    """Returns list of trending tickers from StockTwits."""
    try:
        r = requests.get(STOCKTWITS_URL, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        symbols = r.json().get("response", {}).get("symbols", [])
        return [s["symbol"] for s in symbols if "symbol" in s]
    except Exception as e:
        print(f"  [!] StockTwits fetch failed: {e}")
        return []


def get_social_scores(tickers: list[str] | None = None) -> dict[str, float]:
    """
    Returns ticker -> social_score (0-100) for given tickers.
    If tickers=None, returns scores for all trending tickers found.
    """
    wsb    = get_wsb_trending()
    st_top = get_stocktwits_trending()

    # Combine signals
    all_tickers = set(wsb.keys()) | set(st_top)
    if tickers:
        all_tickers = all_tickers | set(tickers)

    max_mentions = max(wsb.values()) if wsb else 1
    scores = {}
    for t in all_tickers:
        wsb_score = (wsb.get(t, 0) / max_mentions) * 60    # WSB: 60% weight
        st_score  = 40.0 if t in st_top else 0.0           # StockTwits: 40% weight
        scores[t] = round(min(100.0, wsb_score + st_score), 1)

    return scores


def print_social_top(n: int = 20):
    print(f"\n{'='*55}")
    print(f"  SOCIAL SENTIMENT  |  WSB + StockTwits")
    print(f"{'='*55}")
    scores = get_social_scores()
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]
    for ticker, score in top:
        bar = "#" * int(score / 5)
        print(f"  {ticker:6s}  {score:5.1f}  {bar}")
    return dict(top)


if __name__ == "__main__":
    print_social_top()
