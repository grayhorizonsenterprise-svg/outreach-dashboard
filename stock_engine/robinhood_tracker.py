"""
Robinhood Portfolio Tracker
Uses robin_stocks (unofficial wrapper — works with standard RH accounts).
Tracks bi-weekly profit and triggers alert when profit > $500.

pip install robin_stocks pyotp
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

try:
    import robin_stocks.robinhood as rh
    RH_AVAILABLE = True
except ImportError:
    RH_AVAILABLE = False
    print("  [!] robin_stocks not installed. Run: pip install robin_stocks pyotp")

from alerts import alert_profit_pull, send_alert

STATE_FILE = Path(__file__).parent / "portfolio_state.json"
PROFIT_THRESHOLD = 500.00   # alert when bi-weekly gain exceeds this
BIWEEKLY_DAYS    = 14


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def rh_login() -> bool:
    if not RH_AVAILABLE:
        return False
    username = os.getenv("RH_USERNAME", "")
    password = os.getenv("RH_PASSWORD", "")
    mfa_code = os.getenv("RH_MFA_CODE", "")   # optional TOTP code if 2FA enabled

    if not username or not password:
        print("  [!] Set RH_USERNAME and RH_PASSWORD in .env")
        return False

    try:
        kwargs = {"username": username, "password": password, "store_session": True}
        if mfa_code:
            kwargs["mfa_code"] = mfa_code
        rh.login(**kwargs)
        return True
    except Exception as e:
        print(f"  [!] Robinhood login failed: {e}")
        return False


def get_portfolio_value() -> float | None:
    """Returns total portfolio equity in dollars."""
    if not RH_AVAILABLE:
        return None
    try:
        profile = rh.load_portfolio_profile()
        equity = float(profile.get("extended_hours_equity") or profile.get("equity") or 0)
        return equity
    except Exception as e:
        print(f"  [!] Could not fetch portfolio: {e}")
        return None


def get_positions() -> list[dict]:
    """Returns list of current holdings."""
    if not RH_AVAILABLE:
        return []
    try:
        positions = rh.get_open_stock_positions()
        result = []
        for p in positions:
            ticker = rh.get_symbol_by_url(p["instrument"])
            qty    = float(p["quantity"])
            avg    = float(p["average_buy_price"])
            quote  = rh.get_latest_price(ticker)
            price  = float(quote[0]) if quote else avg
            result.append({
                "ticker":   ticker,
                "qty":      qty,
                "avg_cost": avg,
                "price":    price,
                "value":    round(qty * price, 2),
                "gain_pct": round(((price - avg) / avg) * 100, 2) if avg > 0 else 0,
            })
        return result
    except Exception as e:
        print(f"  [!] Position fetch failed: {e}")
        return []


def check_profit_alert():
    """
    Compare current portfolio value to the bi-weekly baseline.
    Send alert + reset baseline if profit >= $500.
    """
    state   = _load_state()
    now     = datetime.now()
    current = get_portfolio_value()

    if current is None:
        print("  [!] Cannot read portfolio value.")
        return

    # First run: set baseline
    if "baseline_value" not in state:
        state["baseline_value"]  = current
        state["baseline_date"]   = now.isoformat()
        state["period_high"]     = current
        _save_state(state)
        print(f"  Baseline set: ${current:,.2f}")
        return

    baseline_date  = datetime.fromisoformat(state["baseline_date"])
    baseline_value = float(state["baseline_value"])
    profit         = current - baseline_value

    print(f"  Portfolio: ${current:,.2f} | Baseline: ${baseline_value:,.2f} | Gain: ${profit:+,.2f}")
    print(f"  Period started: {baseline_date.strftime('%Y-%m-%d')} ({(now - baseline_date).days}d ago)")

    # Alert threshold
    if profit >= PROFIT_THRESHOLD:
        print(f"\n  *** PROFIT THRESHOLD HIT — sending phone alert ***")
        alert_profit_pull(current, baseline_value, profit)
        # Reset baseline to current value for next period
        state["baseline_value"] = current
        state["baseline_date"]  = now.isoformat()
        _save_state(state)
        return

    # Auto-reset baseline every 14 days regardless (new period)
    days_elapsed = (now - baseline_date).days
    if days_elapsed >= BIWEEKLY_DAYS:
        msg = (
            f"Bi-weekly period complete.\n"
            f"Net change: ${profit:+,.2f}\n"
            f"New baseline: ${current:,.2f}"
        )
        send_alert("Period Reset", msg, tags=["calendar"])
        state["baseline_value"] = current
        state["baseline_date"]  = now.isoformat()
        _save_state(state)
        print(f"  Bi-weekly period reset. New baseline: ${current:,.2f}")


def print_positions():
    positions = get_positions()
    if not positions:
        print("  No open positions (or not logged in).")
        return
    print(f"\n{'='*60}")
    print(f"  CURRENT HOLDINGS")
    print(f"{'='*60}")
    total = sum(p["value"] for p in positions)
    for p in sorted(positions, key=lambda x: x["value"], reverse=True):
        print(
            f"  {p['ticker']:6s}  {p['qty']:.4f} shares  "
            f"avg=${p['avg_cost']:.2f}  now=${p['price']:.2f}  "
            f"val=${p['value']:,.2f}  ({p['gain_pct']:+.1f}%)"
        )
    print(f"  {'─'*50}")
    print(f"  Total value: ${total:,.2f}")


if __name__ == "__main__":
    if rh_login():
        print_positions()
        check_profit_alert()
    else:
        print("  Set RH_USERNAME + RH_PASSWORD in .env to enable Robinhood tracking.")
