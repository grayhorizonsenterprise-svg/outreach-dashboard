"""
Master Scan — unified signal from all sources:
  1. Technical momentum (screener.py)
  2. Congress trades (congress_tracker.py)
  3. Social sentiment (social_sentiment.py)
  4. Robinhood profit check (robinhood_tracker.py)

Run this daily (or set up Task Scheduler to run it).
"""

import pandas as pd
import numpy as np
from datetime import datetime

from screener        import analyze_ticker, market_regime, WATCHLIST
from congress_tracker import get_congress_signals
from social_sentiment import get_social_scores
from alerts          import alert_strong_signal, alert_market_regime, send_alert
from robinhood_tracker import rh_login, check_profit_alert

# Weights for final composite (must sum to 1.0)
W_TECHNICAL  = 0.40
W_CONGRESS   = 0.35
W_SOCIAL     = 0.25


def master_scan():
    print(f"\n{'='*65}")
    print(f"  MASTER SCAN  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    # ── 1. Market regime ──────────────────────────────────────────────
    regime = market_regime()
    print(f"\n  REGIME: {regime}")
    alert_market_regime(regime)

    # ── 2. Congress signals ───────────────────────────────────────────
    print("\n  Fetching congress trades...")
    cdf = get_congress_signals(lookback_days=90)
    congress_map: dict[str, float] = {}
    if not cdf.empty:
        for _, row in cdf.iterrows():
            congress_map[row["ticker"]] = float(row["congress_score"])
        print(f"  Found {len(congress_map)} tickers with congress buys")
    else:
        print("  No congress data retrieved")

    # ── 3. Social sentiment ────────────────────────────────────────────
    print("\n  Fetching social sentiment...")
    # Combine watchlist + congress tickers to score
    all_tickers = list(set(WATCHLIST) | set(congress_map.keys()))
    social_map = get_social_scores(all_tickers)
    print(f"  Social scores for {len(social_map)} tickers")

    # ── 4. Technical scores ────────────────────────────────────────────
    # Pull from congress + expanded watchlist
    scan_tickers = list(set(WATCHLIST) | set(list(congress_map.keys())[:30]))
    regime_word  = regime.split()[0]  # BULL / BEAR / CHOP

    print(f"\n  Running technical scan on {len(scan_tickers)} tickers...")
    results = []
    for ticker in scan_tickers:
        if ticker in ("SPY", "QQQ", "IWM", "VIX"):
            continue
        sig = analyze_ticker(ticker)
        if not sig:
            continue

        tech_score    = sig.score
        congress_score = congress_map.get(ticker, 0.0)
        social_score   = social_map.get(ticker, 0.0)

        # Composite
        final = (
            tech_score     * W_TECHNICAL +
            congress_score * W_CONGRESS  +
            social_score   * W_SOCIAL
        )

        # Sources list for alert label
        sources = []
        if tech_score >= 65:     sources.append(f"Tech={tech_score:.0f}")
        if congress_score >= 40: sources.append(f"Congress={congress_score:.0f}")
        if social_score >= 40:   sources.append(f"Social={social_score:.0f}")

        pelosi = cdf[cdf["ticker"] == ticker]["pelosi_bought"].any() if not cdf.empty else False

        results.append({
            "ticker":          ticker,
            "final_score":     round(final, 1),
            "tech_score":      round(tech_score, 1),
            "congress_score":  round(congress_score, 1),
            "social_score":    round(social_score, 1),
            "price":           sig.price,
            "change_pct":      sig.change_pct,
            "rsi":             sig.rsi,
            "above_ema50":     sig.above_ema50,
            "pelosi":          pelosi,
            "entry_note":      sig.entry_note,
            "sources":         sources,
        })

    if not results:
        print("  No results.")
        return

    df = pd.DataFrame(results).sort_values("final_score", ascending=False).reset_index(drop=True)
    df.index += 1

    # ── 5. Print top picks ─────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  TOP UNIFIED PICKS  (regime: {regime_word})")
    print(f"{'='*65}")
    print(f"  {'#':>2}  {'Ticker':6}  {'Score':>6}  {'Tech':>5}  {'Cong':>5}  {'Soc':>5}  {'Price':>8}  {'RSI':>5}  Notes")
    print(f"  {'─'*60}")

    alerts_sent = 0
    for _, row in df.head(15).iterrows():
        pelosi_flag = " [PELOSI]" if row["pelosi"] else ""
        print(
            f"  {int(row.name):>2}  {row['ticker']:6}  {row['final_score']:>6.1f}"
            f"  {row['tech_score']:>5.1f}  {row['congress_score']:>5.1f}"
            f"  {row['social_score']:>5.1f}  ${row['price']:>7.2f}"
            f"  {row['rsi']:>5.1f}  {row['entry_note']}{pelosi_flag}"
        )
        # Phone alert for high-conviction picks
        if row["final_score"] >= 70 and alerts_sent < 3:
            alert_strong_signal(
                row["ticker"], row["final_score"],
                row["price"], row["sources"]
            )
            alerts_sent += 1

    # ── 6. Save output ─────────────────────────────────────────────────
    out = f"signals_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(out)
    print(f"\n  Saved: {out}")

    # ── 7. Robinhood profit check ─────────────────────────────────────
    print(f"\n{'='*65}")
    print("  ROBINHOOD PROFIT CHECK")
    print(f"{'='*65}")
    if rh_login():
        check_profit_alert()
    else:
        print("  Skipped (set RH_USERNAME + RH_PASSWORD in .env to enable)")

    print(f"\n  Scan complete: {datetime.now().strftime('%H:%M:%S')}")
    return df


if __name__ == "__main__":
    master_scan()
