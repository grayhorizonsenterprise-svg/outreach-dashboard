"""
Stock Trend Prediction Engine
Composite scoring: momentum + volume + options flow + sentiment
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional


# ── Pure-pandas indicators (no pandas_ta / numba dependency) ──────────────────

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = _ema(series, fast) - _ema(series, slow)
    signal_line = _ema(macd_line, signal)
    return macd_line, signal_line

# ── Config ────────────────────────────────────────────────────────────────────

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")  # free tier: 25 req/day
NEWS_API_KEY      = os.getenv("NEWS_API_KEY", "")           # newsapi.org free tier

# Tickers to screen — expand this list
WATCHLIST = [
    # High-momentum tech
    "NVDA","AMD","META","GOOGL","MSFT","AAPL","AMZN","TSLA","AVGO","ARM",
    # Biotech (high volatility / options plays)
    "MRNA","CRSP","BEAM","EDIT","NTLA",
    # Small/mid cap momentum
    "SMCI","PLTR","RKLB","IONQ","JOBY",
    # ETFs for regime detection
    "SPY","QQQ","IWM","VIX",
]

@dataclass
class Signal:
    ticker: str
    score: float          # 0-100
    trend: str            # STRONG_BUY / BUY / NEUTRAL / SELL
    momentum_score: float
    volume_score: float
    technical_score: float
    sentiment_score: float
    price: float
    change_pct: float
    rsi: float
    above_ema20: bool
    above_ema50: bool
    entry_note: str


# ── Core Scoring Functions ─────────────────────────────────────────────────────

def score_momentum(df: pd.DataFrame) -> float:
    """Rate of change scoring: 1d, 5d, 20d momentum weighted."""
    if len(df) < 21:
        return 50.0
    closes = df["Close"]
    r1  = (closes.iloc[-1] / closes.iloc[-2]  - 1) * 100
    r5  = (closes.iloc[-1] / closes.iloc[-6]  - 1) * 100
    r20 = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100

    # Weighted: recent momentum matters more
    raw = (r1 * 0.5) + (r5 * 0.3) + (r20 * 0.2)
    # Normalise to 0-100 (clamp at ±10%)
    score = 50 + (raw * 5)
    return float(np.clip(score, 0, 100))


def score_volume(df: pd.DataFrame) -> float:
    """Volume vs 20-day average. Breakouts on high volume = bullish."""
    if len(df) < 21:
        return 50.0
    avg_vol = df["Volume"].iloc[-21:-1].mean()
    today_vol = df["Volume"].iloc[-1]
    ratio = today_vol / avg_vol if avg_vol > 0 else 1.0

    if ratio >= 3.0:   return 95.0
    if ratio >= 2.0:   return 80.0
    if ratio >= 1.5:   return 70.0
    if ratio >= 1.0:   return 55.0
    if ratio >= 0.7:   return 40.0
    return 25.0


def score_technicals(df: pd.DataFrame) -> tuple[float, dict]:
    """RSI, MACD, EMA stack."""
    if len(df) < 52:
        return 50.0, {}

    closes = df["Close"]
    rsi_series         = _rsi(closes)
    macd_line, sig_line = _macd(closes)
    ema20_series       = _ema(closes, 20)
    ema50_series       = _ema(closes, 50)

    rsi    = float(rsi_series.iloc[-1])
    macd   = float(macd_line.iloc[-1])
    signal = float(sig_line.iloc[-1])
    ema20  = float(ema20_series.iloc[-1])
    ema50  = float(ema50_series.iloc[-1])
    price  = float(closes.iloc[-1])

    points = 0
    # RSI sweet spot: 50-70 = bullish momentum, not overbought
    if 50 < rsi < 70:  points += 30
    elif 40 < rsi <= 50: points += 15
    elif rsi >= 70:    points += 10   # overbought — reduced score
    elif rsi < 30:     points += 35   # oversold bounce potential

    # MACD above signal line
    if macd > signal:  points += 25

    # Price above EMAs
    above_ema20 = price > ema20
    above_ema50 = price > ema50
    if above_ema20: points += 20
    if above_ema50: points += 25

    meta = {
        "rsi": round(float(rsi), 1),
        "macd_bullish": macd > signal,
        "above_ema20": above_ema20,
        "above_ema50": above_ema50,
    }
    return float(np.clip(points, 0, 100)), meta


def score_sentiment(ticker: str) -> float:
    """Basic news sentiment via NewsAPI (free). Returns 0-100."""
    if not NEWS_API_KEY:
        return 50.0  # neutral if no key

    try:
        url = (
            f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt"
            f"&pageSize=10&language=en&apiKey={NEWS_API_KEY}"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return 50.0
        articles = resp.json().get("articles", [])
        if not articles:
            return 50.0

        positive = ["surge", "beat", "rally", "growth", "record", "upgrade",
                    "strong", "profit", "bullish", "buy", "outperform"]
        negative = ["crash", "miss", "drop", "lawsuit", "downgrade", "loss",
                    "bearish", "sell", "warning", "probe", "recall"]

        pos_count = neg_count = 0
        for art in articles:
            text = ((art.get("title") or "") + " " + (art.get("description") or "")).lower()
            pos_count += sum(1 for w in positive if w in text)
            neg_count += sum(1 for w in negative if w in text)

        total = pos_count + neg_count
        if total == 0:
            return 50.0
        score = (pos_count / total) * 100
        return float(np.clip(score, 0, 100))
    except Exception:
        return 50.0


# ── Main Signal Generator ──────────────────────────────────────────────────────

def analyze_ticker(ticker: str) -> Optional[Signal]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        if df.empty or len(df) < 10:
            return None

        price      = float(df["Close"].iloc[-1])
        prev_price = float(df["Close"].iloc[-2])
        change_pct = ((price - prev_price) / prev_price) * 100

        mom_score  = score_momentum(df)
        vol_score  = score_volume(df)
        tech_score, tech_meta = score_technicals(df)
        sent_score = score_sentiment(ticker)

        # Composite: momentum 35%, technicals 35%, volume 20%, sentiment 10%
        composite = (
            mom_score  * 0.35 +
            tech_score * 0.35 +
            vol_score  * 0.20 +
            sent_score * 0.10
        )

        if composite >= 75:   trend = "STRONG_BUY"
        elif composite >= 60: trend = "BUY"
        elif composite >= 40: trend = "NEUTRAL"
        else:                 trend = "SELL"

        # Entry note
        notes = []
        if tech_meta.get("rsi", 50) < 35:
            notes.append("oversold bounce setup")
        if vol_score >= 80:
            notes.append("high-volume breakout")
        if tech_meta.get("above_ema20") and tech_meta.get("above_ema50"):
            notes.append("above both EMAs")
        if tech_meta.get("macd_bullish"):
            notes.append("MACD bullish cross")
        entry_note = " | ".join(notes) if notes else "standard trend"

        return Signal(
            ticker=ticker,
            score=round(composite, 1),
            trend=trend,
            momentum_score=round(mom_score, 1),
            volume_score=round(vol_score, 1),
            technical_score=round(tech_score, 1),
            sentiment_score=round(sent_score, 1),
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            rsi=tech_meta.get("rsi", 50),
            above_ema20=tech_meta.get("above_ema20", False),
            above_ema50=tech_meta.get("above_ema50", False),
            entry_note=entry_note,
        )
    except Exception as e:
        print(f"  [!] {ticker}: {e}")
        return None


def run_screen(tickers: list[str] = WATCHLIST) -> pd.DataFrame:
    print(f"\n{'='*60}")
    print(f"  STOCK TREND SCREENER  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"  Scanning {len(tickers)} tickers...\n")

    signals = []
    for t in tickers:
        if t in ("SPY", "QQQ", "IWM", "VIX"):
            continue  # regime tickers — skip from ranking
        sig = analyze_ticker(t)
        if sig:
            signals.append(sig)
            icon = {"STRONG_BUY": "***", "BUY": " * ", "NEUTRAL": "   ", "SELL": " - "}[sig.trend]
            print(f"  {icon} {t:6s}  score={sig.score:5.1f}  RSI={sig.rsi:5.1f}  {sig.trend}")

    if not signals:
        print("  No signals generated.")
        return pd.DataFrame()

    df_out = pd.DataFrame([vars(s) for s in signals])
    df_out = df_out.sort_values("score", ascending=False).reset_index(drop=True)
    df_out.index += 1  # 1-based rank

    print(f"\n{'='*60}")
    print(f"  TOP PICKS")
    print(f"{'='*60}")
    top = df_out[df_out["trend"].isin(["STRONG_BUY", "BUY"])].head(10)
    for _, row in top.iterrows():
        print(
            f"  #{int(row.name):2d} {row['ticker']:6s} | "
            f"Score {row['score']:5.1f} | "
            f"${row['price']:8.2f} ({row['change_pct']:+.1f}%) | "
            f"{row['trend']:12s} | {row['entry_note']}"
        )

    out_path = os.path.join(os.path.dirname(__file__), "signals.csv")
    df_out.to_csv(out_path)
    print(f"\n  Saved to {out_path}")
    return df_out


# ── Market Regime Check ────────────────────────────────────────────────────────

def market_regime() -> str:
    """SPY vs 50-day EMA. Bull/bear/chop context for position sizing."""
    try:
        spy   = yf.Ticker("SPY").history(period="3mo")
        price = float(spy["Close"].iloc[-1])
        ema50 = float(_ema(spy["Close"], 50).iloc[-1])
        rsi   = float(_rsi(spy["Close"]).iloc[-1])

        if price > ema50 and rsi > 50:
            return "BULL — full position sizing OK"
        elif price < ema50 and rsi < 45:
            return "BEAR — reduce size by 50%, prefer puts/inverse"
        else:
            return "CHOP — reduce size by 25%, tighten stops"
    except Exception:
        return "UNKNOWN — use conservative sizing"


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    regime = market_regime()
    print(f"\n  MARKET REGIME: {regime}\n")
    results = run_screen()
