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
from congress_tracker import get_congress_signals, get_congress_sells, QUIVER_KEY
from social_sentiment import get_social_scores
from alerts          import alert_strong_signal, alert_market_regime, send_alert
from robinhood_tracker import rh_login, check_profit_alert

# Weights for final composite.
# Congress weight drops to 0 when no live data source is available —
# using stale/demo congress scores inflates garbage tickers and buries real tech setups.
_HAS_LIVE_CONGRESS = bool(QUIVER_KEY) or True   # House Watcher is always available
W_TECHNICAL  = 0.55 if not _HAS_LIVE_CONGRESS else 0.45
W_CONGRESS   = 0.00 if not _HAS_LIVE_CONGRESS else 0.35
W_SOCIAL     = 0.45 if not _HAS_LIVE_CONGRESS else 0.20


def master_scan():
    print(f"\n{'='*65}")
    print(f"  MASTER SCAN  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    # ── 1. Market regime ──────────────────────────────────────────────
    regime = market_regime()
    print(f"\n  REGIME: {regime}")
    alert_market_regime(regime)

    # ── 2. Congress signals (buys + sells) ───────────────────────────
    print("\n  Fetching congress trades (buys + sells)...")
    cdf = get_congress_signals(lookback_days=90)
    congress_map: dict[str, float] = {}
    if not cdf.empty:
        for _, row in cdf.iterrows():
            congress_map[row["ticker"]] = float(row["congress_score"])
        print(f"  Found {len(congress_map)} tickers with congress buys")
    else:
        print("  No congress buy data retrieved")

    # Sell/dump signals — separate tracking
    sell_df = get_congress_sells(lookback_days=60)
    dump_map: dict[str, float] = {}
    if not sell_df.empty:
        for _, row in sell_df.iterrows():
            dump_map[row["ticker"]] = float(row["dump_score"])
        print(f"  Found {len(dump_map)} tickers with congress SELLS (dump risk)")

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

        tech_score     = sig.score
        congress_score = congress_map.get(ticker, 0.0)
        social_score   = social_map.get(ticker, 0.0)
        dump_score     = dump_map.get(ticker, 0.0)

        # Composite — Congress weight only counts when we have real live data
        final = (
            tech_score     * W_TECHNICAL +
            congress_score * W_CONGRESS  +
            social_score   * W_SOCIAL
        )

        # Short signal: Congress selling + overbought RSI + price extended above EMA
        short_signal = (
            dump_score >= 40 and
            sig.rsi > 68 and
            sig.above_ema50  # extended, not near support
        )

        # Kelly-sized small bet for short plays ($25 base, 0.5x Kelly for high short score)
        short_bet_size = round(25 * min(1.0, dump_score / 100), 2) if short_signal else 0.0

        sources = []
        if tech_score >= 65:     sources.append(f"Tech={tech_score:.0f}")
        if congress_score >= 40: sources.append(f"Congress={congress_score:.0f}")
        if social_score >= 40:   sources.append(f"Social={social_score:.0f}")
        if dump_score >= 40:     sources.append(f"SELL={dump_score:.0f}")

        pelosi = cdf[cdf["ticker"] == ticker]["pelosi_bought"].any() if not cdf.empty else False
        pelosi_sold = sell_df[sell_df["ticker"] == ticker]["pelosi_sold"].any() if not sell_df.empty else False

        results.append({
            "ticker":          ticker,
            "final_score":     round(final, 1),
            "tech_score":      round(tech_score, 1),
            "congress_score":  round(congress_score, 1),
            "social_score":    round(social_score, 1),
            "dump_score":      round(dump_score, 1),
            "price":           sig.price,
            "change_pct":      sig.change_pct,
            "rsi":             sig.rsi,
            "above_ema50":     sig.above_ema50,
            "pelosi":          pelosi,
            "pelosi_sold":     pelosi_sold,
            "short_signal":    short_signal,
            "short_bet_size":  short_bet_size,
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

    # ── 6. SHORT / DUMP signals ────────────────────────────────────────
    shorts = df[df["short_signal"] == True] if "short_signal" in df.columns else pd.DataFrame()
    if not shorts.empty:
        print(f"\n{'='*65}")
        print(f"  CONGRESSIONAL DUMP SIGNALS — potential shorts")
        print(f"  Congress selling + RSI overbought + extended above EMA50")
        print(f"{'='*65}")
        print(f"  {'Ticker':6}  {'Dump':>5}  {'RSI':>5}  {'Price':>8}  {'Bet$':>6}  Notes")
        print(f"  {'─'*55}")
        for _, row in shorts.iterrows():
            pelosi_flag = " *** PELOSI SOLD" if row.get("pelosi_sold") else ""
            print(
                f"  {row['ticker']:6}  {row['dump_score']:>5.1f}  {row['rsi']:>5.1f}"
                f"  ${row['price']:>7.2f}  ${row['short_bet_size']:>5.2f}"
                f"  SHORT setup — congress exiting{pelosi_flag}"
            )
        print(f"\n  Action: Buy PUT options or sell short at market open.")
        print(f"  Small bet sizing shown — scale with Kelly when confidence >= 60%.")
    else:
        print(f"\n  No short/dump signals today.")

    # ── 7. Small bet sizing table (top long plays) ────────────────────
    print(f"\n{'='*65}")
    print(f"  SMALL BET SIZING — top 5 long plays ($25 base, Kelly-sized)")
    print(f"{'='*65}")
    print(f"  {'#':>2}  {'Ticker':6}  {'Score':>5}  {'Price':>8}  {'$25 play':>9}  {'$50 play':>9}  {'Win% est':>9}")
    print(f"  {'─'*65}")
    for i, (_, row) in enumerate(df.head(5).iterrows(), 1):
        score_pct  = min(row["final_score"] / 100, 0.85)
        kelly_frac = max(0.10, score_pct - 0.45)  # fractional Kelly
        bet_25  = round(25  * kelly_frac, 2)
        bet_50  = round(50  * kelly_frac, 2)
        win_est = round(50 + score_pct * 30, 1)   # rough win% estimate
        print(
            f"  {i:>2}  {row['ticker']:6}  {row['final_score']:>5.1f}"
            f"  ${row['price']:>7.2f}  ${bet_25:>8.2f}  ${bet_50:>8.2f}  {win_est:>8.1f}%"
        )

    # ── 8. Save output ─────────────────────────────────────────────────
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
