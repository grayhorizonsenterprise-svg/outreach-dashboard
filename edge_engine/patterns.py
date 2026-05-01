"""
Pattern detection engine.
Returns named chart patterns + bullish/bearish warnings for any price series.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class PatternResult:
    name: str
    type: str        # BULLISH / BEARISH / WARNING / NEUTRAL
    confidence: int  # 0-100
    note: str


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def _rsi(s: pd.Series, n: int = 14) -> float:
    d = s.diff()
    g = d.clip(lower=0).ewm(com=n - 1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=n - 1, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    return float((100 - 100 / (1 + rs)).iloc[-1])


def detect_patterns(df: pd.DataFrame) -> list[PatternResult]:
    """Run all pattern detectors on a price DataFrame. Returns list of PatternResult."""
    if len(df) < 60:
        return []

    results = []
    c = df["Close"]
    v = df["Volume"]

    ema20 = _ema(c, 20)
    ema50 = _ema(c, 50)
    ema200 = _ema(c, 200) if len(df) >= 200 else None

    price   = float(c.iloc[-1])
    e20     = float(ema20.iloc[-1])
    e50     = float(ema50.iloc[-1])
    rsi_val = _rsi(c)

    # ── Golden Cross ──────────────────────────────────────────────────────────
    if ema200 is not None:
        if float(ema50.iloc[-1]) > float(ema200.iloc[-1]) and float(ema50.iloc[-5]) <= float(ema200.iloc[-5]):
            results.append(PatternResult("Golden Cross", "BULLISH", 88,
                "50 EMA just crossed above 200 EMA — major bull signal"))
        elif float(ema50.iloc[-1]) < float(ema200.iloc[-1]) and float(ema50.iloc[-5]) >= float(ema200.iloc[-5]):
            results.append(PatternResult("Death Cross", "BEARISH", 88,
                "50 EMA just crossed below 200 EMA — major bear signal"))
        elif float(ema50.iloc[-1]) < float(ema200.iloc[-1]):
            results.append(PatternResult("Below 200 EMA", "WARNING", 70,
                "Price structure is bearish long-term — trade cautiously"))

    # ── Breakout on Volume ────────────────────────────────────────────────────
    recent_high = float(c.iloc[-30:-2].max())
    avg_vol     = float(v.iloc[-21:-1].mean())
    today_vol   = float(v.iloc[-1])
    if price > recent_high * 1.01 and today_vol > avg_vol * 1.5:
        results.append(PatternResult("Volume Breakout", "BULLISH", 82,
            f"Price broke 30-day high on {today_vol/avg_vol:.1f}x average volume"))

    # ── Bull Flag ─────────────────────────────────────────────────────────────
    run_5d  = (float(c.iloc[-6]) / float(c.iloc[-11]) - 1) * 100
    pull_3d = (float(c.iloc[-1]) / float(c.iloc[-4])  - 1) * 100
    if run_5d > 8 and -5 < pull_3d < 0:
        results.append(PatternResult("Bull Flag", "BULLISH", 74,
            f"Strong +{run_5d:.1f}% run followed by tight {pull_3d:.1f}% pullback — continuation likely"))

    # ── Cup and Handle ────────────────────────────────────────────────────────
    if len(df) >= 60:
        window = c.iloc[-60:]
        low_idx  = int(window.argmin())
        left_rim = float(window.iloc[0])
        cup_low  = float(window.min())
        right_rim = float(window.iloc[-1])
        recovery = (right_rim - cup_low) / (left_rim - cup_low + 0.0001)
        if 0.10 < low_idx / len(window) < 0.75 and recovery > 0.80:
            results.append(PatternResult("Cup and Handle", "BULLISH", 71,
                "U-shaped 60-day base — bullish continuation pattern"))

    # ── Double Bottom ─────────────────────────────────────────────────────────
    if len(df) >= 40:
        mid = c.iloc[-40:-20]
        recent = c.iloc[-20:]
        low1 = float(mid.min())
        low2 = float(recent.min())
        if abs(low1 - low2) / low1 < 0.03 and price > max(float(mid.max()), float(recent.max())) * 0.97:
            results.append(PatternResult("Double Bottom", "BULLISH", 76,
                "Two similar lows form a W — classic reversal signal"))

    # ── Head and Shoulders (bearish reversal) ─────────────────────────────────
    if len(df) >= 60:
        seg = c.iloc[-60:]
        third = len(seg) // 3
        left  = float(seg.iloc[:third].max())
        head  = float(seg.iloc[third:2*third].max())
        right = float(seg.iloc[2*third:].max())
        if head > left * 1.03 and head > right * 1.03 and abs(left - right) / head < 0.06:
            results.append(PatternResult("Head and Shoulders", "BEARISH", 72,
                "Triple peak pattern with higher middle — bearish reversal likely"))

    # ── Oversold Bounce Setup ─────────────────────────────────────────────────
    if rsi_val < 32 and price > e20:
        results.append(PatternResult("Oversold Bounce", "BULLISH", 68,
            f"RSI {rsi_val:.0f} — oversold with price holding above EMA20, bounce likely"))

    # ── Overbought Warning ────────────────────────────────────────────────────
    if rsi_val > 78:
        results.append(PatternResult("Overbought", "WARNING", 75,
            f"RSI {rsi_val:.0f} — elevated risk of pullback, tighten stops"))

    # ── Volume Dry-Up (weak rally) ────────────────────────────────────────────
    price_up = float(c.iloc[-1]) > float(c.iloc[-5])
    vol_5d_avg = float(v.iloc[-5:].mean())
    vol_20d_avg = float(v.iloc[-25:-5].mean())
    if price_up and vol_5d_avg < vol_20d_avg * 0.65:
        results.append(PatternResult("Volume Dry-Up", "WARNING", 66,
            "Price rising but volume is fading — rally may lack conviction"))

    # ── Consecutive Down Days ─────────────────────────────────────────────────
    last_5 = [float(c.iloc[i]) < float(c.iloc[i - 1]) for i in range(-4, 0)]
    if all(last_5):
        results.append(PatternResult("4-Day Slide", "BEARISH", 62,
            "Price down 4 consecutive days — downward momentum, wait for reversal"))

    # ── Below Both EMAs ───────────────────────────────────────────────────────
    if price < e20 and price < e50:
        results.append(PatternResult("Below Key EMAs", "BEARISH", 70,
            "Price below both EMA20 and EMA50 — no trend support, avoid"))

    # ── Momentum Squeeze ──────────────────────────────────────────────────────
    std20 = float(c.iloc[-20:].std())
    std60 = float(c.iloc[-60:].std()) if len(df) >= 60 else std20
    if std20 < std60 * 0.5 and rsi_val > 45:
        results.append(PatternResult("Momentum Squeeze", "BULLISH", 69,
            "Volatility contracting with neutral RSI — explosive move likely soon"))

    return results


def bad_stock_warnings(df: pd.DataFrame, ticker: str) -> list[str]:
    """Return a list of red-flag warning strings for a stock."""
    warnings = []
    if len(df) < 20:
        return warnings

    c = df["Close"]
    v = df["Volume"]
    rsi_val = _rsi(c)
    price   = float(c.iloc[-1])
    e20     = float(_ema(c, 20).iloc[-1])
    e50     = float(_ema(c, 50).iloc[-1])

    # Extreme RSI
    if rsi_val > 82:
        warnings.append(f"RSI {rsi_val:.0f} — dangerously overbought")
    if rsi_val < 22:
        warnings.append(f"RSI {rsi_val:.0f} — extreme oversold, high volatility risk")

    # Price in freefall
    drop_20d = (price / float(c.iloc[-21]) - 1) * 100 if len(df) >= 21 else 0
    if drop_20d < -25:
        warnings.append(f"Down {drop_20d:.1f}% in 20 days — potential death spiral")

    # Low price (penny stock risk)
    if price < 1.00:
        warnings.append(f"Penny stock (${price:.3f}) — extreme manipulation risk")
    elif price < 5.00:
        warnings.append(f"Low-price stock (${price:.2f}) — elevated volatility risk")

    # Volume collapse
    avg_vol = float(v.iloc[-21:].mean())
    if avg_vol < 100_000:
        warnings.append(f"Low liquidity ({avg_vol:,.0f} avg shares) — hard to exit positions")

    # EMA death zone
    if price < e20 and price < e50 and e20 < e50:
        warnings.append("EMA stack bearish — all moving averages point down")

    # Price at 52-week low
    low_52 = float(c.min())
    if price <= low_52 * 1.05:
        warnings.append("Near 52-week low — potential value trap, no floor confirmed")

    return warnings
