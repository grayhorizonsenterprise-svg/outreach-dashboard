"""
Simple vectorised backtester.
Tests the composite signal against historical price data.
Usage: python backtester.py NVDA AMD TSLA
"""

import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from screener import _rsi, _ema, _macd


def backtest(ticker: str, period: str = "1y") -> dict:
    df = yf.Ticker(ticker).history(period=period)
    if len(df) < 60:
        return {}

    df = df.copy()
    closes          = df["Close"]
    df["RSI"]       = _rsi(closes)
    df["EMA20"]     = _ema(closes, 20)
    df["EMA50"]     = _ema(closes, 50)
    macd_l, macd_s  = _macd(closes)
    df["MACD"]      = macd_l
    df["MACD_SIG"]  = macd_s

    # Signal: buy when RSI 40-70, above both EMAs, MACD bullish
    df["signal"] = 0
    df.loc[
        (df["RSI"] > 40) &
        (df["RSI"] < 70) &
        (df["Close"] > df["EMA20"]) &
        (df["Close"] > df["EMA50"]) &
        (df["MACD"] > df["MACD_SIG"]),
        "signal"
    ] = 1

    df["daily_ret"] = df["Close"].pct_change()
    df["strat_ret"] = df["daily_ret"] * df["signal"].shift(1)

    total_ret  = (1 + df["strat_ret"].dropna()).prod() - 1
    bh_ret     = (df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1
    win_days   = (df["strat_ret"] > 0).sum()
    trade_days = (df["strat_ret"] != 0).sum()
    win_rate   = win_days / trade_days if trade_days > 0 else 0
    sharpe     = (df["strat_ret"].mean() / df["strat_ret"].std()) * np.sqrt(252) if df["strat_ret"].std() > 0 else 0

    return {
        "ticker":       ticker,
        "period":       period,
        "strat_return": round(total_ret * 100, 2),
        "buy_hold":     round(bh_ret * 100, 2),
        "win_rate":     round(win_rate * 100, 1),
        "sharpe":       round(sharpe, 2),
        "trade_days":   int(trade_days),
    }


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["NVDA", "AMD", "META"]
    print(f"\n{'='*65}")
    print(f"  BACKTEST RESULTS  |  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*65}")
    print(f"  {'Ticker':8} {'Strat%':>8} {'B&H%':>8} {'WinRate':>9} {'Sharpe':>8} {'TradeDays':>11}")
    print(f"  {'-'*55}")
    for t in tickers:
        r = backtest(t)
        if r:
            alpha = r["strat_return"] - r["buy_hold"]
            print(
                f"  {r['ticker']:8} {r['strat_return']:>7.1f}% {r['buy_hold']:>7.1f}%"
                f"  {r['win_rate']:>7.1f}%  {r['sharpe']:>7.2f}  {r['trade_days']:>9}"
                f"   alpha={alpha:+.1f}%"
            )
    print()
