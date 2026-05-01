"""
scan.py — run this daily. Scans stocks, crypto, and sports/politics bets.
Sends phone alerts for top picks. Tracks weekly P&L baseline.

Usage:  python scan.py
        python scan.py --stocks-only
        python scan.py --bets-only
        python scan.py --crypto-only
"""

import sys
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 output so Unicode chars render on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import (
    MIN_SIGNAL_SCORE, PROFIT_ALERT_USD, BIWEEKLY_DAYS,
    RH_USER, RH_PASS
)
from signals import (
    get_stock_signals, get_crypto_signals,
    get_betting_signals, get_congress_buys
)
from notify import (
    alert_top_stock, alert_top_crypto, alert_top_bet,
    alert_profit_pull, alert_daily_summary
)

STATE_FILE = Path(__file__).parent / ".portfolio_state.json"
REPORT_FILE = Path(__file__).parent / f"report_{datetime.now().strftime('%Y%m%d')}.txt"

# ── Args ───────────────────────────────────────────────────────────────────────
args = set(sys.argv[1:])
run_stocks = "--bets-only" not in args and "--crypto-only" not in args
run_crypto = "--stocks-only" not in args and "--bets-only" not in args
run_bets   = "--stocks-only" not in args and "--crypto-only" not in args


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def _save_state(s: dict):
    STATE_FILE.write_text(json.dumps(s, indent=2))

def _hr(char="=", width=65):
    print(char * width)

def _section(title: str):
    _hr()
    print(f"  {title}")
    _hr()


# ── STOCKS ─────────────────────────────────────────────────────────────────────

def run_stock_scan(congress_scores: dict) -> list:
    _section(f"STOCKS  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    signals = get_stock_signals()
    alerts_sent = 0

    print(f"\n  {'#':>2}  {'Ticker':6}  {'Score':>6}  {'Price':>9}  "
          f"{'1D%':>6}  {'RSI':>5}  {'Trend':12}  Notes")
    print(f"  {'─'*60}")

    top_picks = []
    for i, s in enumerate(signals[:15], 1):
        cong = congress_scores.get(s.ticker, 0)
        cong_flag = " [CONGRESS]" if cong >= 40 else ""
        cong_flag += " [PELOSI]"  if cong >= 70 else ""

        final = round(s.score * 0.8 + cong * 0.2, 1)

        print(f"  {i:>2}  {s.ticker:6}  {final:>6.1f}  ${s.price:>8.2f}"
              f"  {s.change_1d:>+5.1f}%  {s.rsi:>5.1f}  {s.trend:12}  "
              f"{s.note}{cong_flag}")

        if final >= MIN_SIGNAL_SCORE and alerts_sent < 3:
            alert_top_stock(s.ticker, final, s.price, s.note + cong_flag)
            alerts_sent += 1
            top_picks.append(s)

    return top_picks


# ── CRYPTO ─────────────────────────────────────────────────────────────────────

def run_crypto_scan() -> list:
    _section(f"CRYPTO  |  CoinGecko live data")
    signals = get_crypto_signals()
    alerts_sent = 0

    print(f"\n  {'#':>2}  {'Symbol':8}  {'Score':>6}  {'Price':>12}  "
          f"{'1h%':>6}  {'24h%':>7}  {'7d%':>7}  {'Trend':12}  Notes")
    print(f"  {'─'*75}")

    top_picks = []
    for i, s in enumerate(signals[:12], 1):
        print(f"  {i:>2}  {s.symbol:8}  {s.score:>6.1f}  ${s.price:>11,.4f}"
              f"  {s.change_1h:>+5.1f}%  {s.change_24h:>+6.1f}%  "
              f"{s.change_7d:>+6.1f}%  {s.trend:12}  {s.note}")

        if s.score >= MIN_SIGNAL_SCORE and alerts_sent < 3:
            alert_top_crypto(s.coin, s.symbol, s.score,
                             s.price, s.change_24h, s.note)
            alerts_sent += 1
            top_picks.append(s)

    return top_picks


# ── SPORTS & POLITICS BETS ─────────────────────────────────────────────────────

def run_bet_scan() -> list:
    _section("SPORTS & POLITICS BETS  |  Best value across all books")
    signals = get_betting_signals()

    if not signals:
        print("\n  No signals found. Check ODDS_API_KEY in .env")
        print("  Get free key: the-odds-api.com (500 req/month)")
        print("  Polymarket politics: check above for any results")
        return []

    print(f"\n  LEGEND: Edge = (true prob) - (book's vig-inclusive implied prob)")
    print(f"  EV = expected value per $100 wagered. Bet only where EV > 0")
    print(f"  {'─'*70}")

    # Separate sports from politics
    sports_sigs = [s for s in signals if s.sport != "POLITICS"]
    politics_sigs = [s for s in signals if s.sport == "POLITICS"]

    top_picks = []
    alerts_sent = 0

    if sports_sigs:
        print(f"\n  {'SPORT':10}  {'BET':22}  {'ODDS':>6}  {'BOOK':18}  "
              f"{'WIN%':>5}  {'EDGE':>6}  {'EV/$100':>8}  {'CONF':8}  Game")
        print(f"  {'─'*100}")
        for s in sports_sigs[:10]:
            sign = "+" if s.odds > 0 else ""
            print(f"  {s.sport:10}  {s.bet_on[:22]:22}  {sign}{s.odds:>5}  "
                  f"{s.book[:18]:18}  {s.our_prob:>4.0%}  {s.edge_pct:>+5.1f}%"
                  f"  ${s.expected_value:>+7.2f}  {s.confidence:8}  "
                  f"{s.game[:30]}")
            if s.our_prob >= 0.60 and s.edge_pct >= MIN_BET_EDGE_PCT and alerts_sent < 2:
                alert_top_bet(s.game, s.bet_on, s.odds, s.book,
                              s.our_prob, s.edge_pct, s.expected_value)
                alerts_sent += 1
                top_picks.append(s)

    if politics_sigs:
        print(f"\n  POLITICS / EVENTS  (Polymarket — crypto prediction market)")
        print(f"  {'─'*70}")
        for s in politics_sigs[:8]:
            sign = "+" if s.odds > 0 else ""
            print(f"  {s.our_prob:>4.0%} win  {sign}{s.odds:>5}  "
                  f"{s.confidence:8}  {s.game}")
            if s.our_prob >= 0.65 and alerts_sent < 3:
                alert_top_bet(s.game, s.bet_on, s.odds, "Polymarket",
                              s.our_prob, s.edge_pct, s.expected_value)
                alerts_sent += 1
                top_picks.append(s)

    # ── Minimum investment recommendation ─────────────────────────────────────
    _section("RECOMMENDED BET  |  Highest probability, minimum $ in")
    if sports_sigs or politics_sigs:
        best = max(signals, key=lambda x: x.our_prob)
        sign = "+" if best.odds > 0 else ""
        payout_per_dollar = (
            100 / abs(best.odds) if best.odds < 0 else best.odds / 100
        )
        print(f"\n  PICK:     {best.bet_on}")
        print(f"  GAME:     {best.game}")
        print(f"  SOURCE:   {best.book}  |  {best.sport}")
        print(f"  ODDS:     {sign}{best.odds}  (Win prob: {best.our_prob:.0%})")
        print(f"  EDGE:     +{best.edge_pct:.1f}% above vig")
        print(f"  EV:       ${best.expected_value:+.2f} per $100 wagered")
        print(f"\n  $10 bet  → wins ${10 * payout_per_dollar:.2f}  "
              f"(prob: {best.our_prob:.0%})")
        print(f"  $25 bet  → wins ${25 * payout_per_dollar:.2f}")
        print(f"  $50 bet  → wins ${50 * payout_per_dollar:.2f}")
        print(f"\n  CONFIDENCE: {best.confidence}")
        print(f"  NOTE: Never bet more than 3-5% of your bankroll on any single game.")

    return top_picks


# ── PORTFOLIO / PROFIT CHECK ───────────────────────────────────────────────────

def check_profit_tracker():
    _section("WEEKLY PROFIT TRACKER")
    state = _load_state()
    now   = datetime.now()

    # Try Robinhood if credentials exist
    rh_balance = None
    if RH_USER and RH_PASS:
        try:
            import robin_stocks.robinhood as rh
            rh.login(username=RH_USER, password=RH_PASS, store_session=True)
            profile = rh.load_portfolio_profile()
            rh_balance = float(
                profile.get("extended_hours_equity") or profile.get("equity") or 0
            )
            print(f"\n  Robinhood portfolio: ${rh_balance:,.2f}")
        except Exception as e:
            print(f"  [!] Robinhood: {e}")

    # Manual balance fallback
    if rh_balance is None:
        if "manual_balance" in state:
            print(f"\n  Last recorded balance: ${state['manual_balance']:,.2f}")
            print(f"  Update manually: edit .portfolio_state.json → manual_balance")
        else:
            print(f"\n  No balance tracked yet.")
            print(f"  Add RH credentials to .env OR manually set:")
            print(f'  echo \'{{"manual_balance": 100.00}}\' > .portfolio_state.json')
        return

    current = rh_balance
    if "baseline_value" not in state:
        state["baseline_value"] = current
        state["baseline_date"]  = now.isoformat()
        _save_state(state)
        print(f"  Baseline set: ${current:,.2f}")
        return

    baseline = float(state["baseline_value"])
    start    = datetime.fromisoformat(state["baseline_date"])
    profit   = current - baseline
    days     = (now - start).days

    print(f"\n  Period:   {start.strftime('%b %d')} → today ({days}d)")
    print(f"  Baseline: ${baseline:,.2f}")
    print(f"  Current:  ${current:,.2f}")
    print(f"  P&L:      ${profit:+,.2f}  ({profit/baseline*100:+.1f}%)")

    if profit >= PROFIT_ALERT_USD:
        print(f"\n  *** ${profit:,.2f} PROFIT — PULL IT NOW ***")
        alert_profit_pull("Robinhood", current, baseline, profit)
        state["baseline_value"] = current
        state["baseline_date"]  = now.isoformat()
        _save_state(state)
    elif days >= BIWEEKLY_DAYS:
        print(f"\n  Period reset (14 days). New baseline: ${current:,.2f}")
        state["baseline_value"] = current
        state["baseline_date"]  = now.isoformat()
        _save_state(state)
    else:
        remaining = PROFIT_ALERT_USD - profit
        print(f"\n  ${remaining:,.2f} more profit to trigger pull alert.")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*65}")
    print(f"  EDGE ENGINE DAILY SCAN  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}\n")

    congress = {}
    top_stock_picks = []
    top_crypto_picks = []
    top_bet_picks = []

    if run_stocks:
        print("  Fetching congress trades...")
        congress = get_congress_buys()
        top_stock_picks = run_stock_scan(congress)
        print()

    if run_crypto:
        top_crypto_picks = run_crypto_scan()
        print()

    if run_bets:
        top_bet_picks = run_bet_scan()
        print()

    check_profit_tracker()
    print()

    # ── Summary ────────────────────────────────────────────────────────────────
    _section("TODAY'S SUMMARY")

    all_top = []
    if top_stock_picks:
        best = top_stock_picks[0]
        print(f"\n  STOCK:   {best.ticker}  score={best.score}  ${best.price:.2f}  {best.trend}")
        all_top.append(f"Stock: {best.ticker}")

    if top_crypto_picks:
        best = top_crypto_picks[0]
        print(f"  CRYPTO:  {best.symbol}  score={best.score}  ${best.price:,.4f}  {best.trend}")
        all_top.append(f"Crypto: {best.symbol}")

    if top_bet_picks:
        best = top_bet_picks[0]
        sign = "+" if best.odds > 0 else ""
        print(f"  BET:     {best.bet_on}  {sign}{best.odds}  {best.our_prob:.0%} win  "
              f"EV ${best.expected_value:+.2f}")
        all_top.append(f"Bet: {best.bet_on}")

    top_label = " | ".join(all_top) if all_top else "No high-confidence picks today"
    alert_daily_summary(
        len(top_stock_picks), len(top_crypto_picks),
        len(top_bet_picks), top_label
    )
    print(f"\n  Phone alert sent. Scan complete.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
