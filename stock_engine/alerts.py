"""
Phone Alert System via ntfy.sh (100% free, no account needed).

SETUP (one time):
  1. Install 'ntfy' app on your phone (iOS App Store or Google Play)
  2. Open app → Subscribe to topic: your NTFY_TOPIC from .env
  3. That's it — you'll get push notifications instantly.

ntfy.sh is open-source, free, no rate limits for personal use.
"""

import requests
import os
from datetime import datetime

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "grayhorizons_stocks")
NTFY_URL   = f"https://ntfy.sh/{NTFY_TOPIC}"


def send_alert(
    title: str,
    message: str,
    priority: str = "default",   # min / low / default / high / urgent
    tags: list[str] | None = None,
) -> bool:
    """Send push notification to phone via ntfy.sh."""
    try:
        headers = {
            "Title":    title,
            "Priority": priority,
            "Tags":     ",".join(tags or []),
        }
        r = requests.post(NTFY_URL, data=message.encode("utf-8"), headers=headers, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"  [!] Alert failed: {e}")
        return False


def alert_profit_pull(current_value: float, baseline_value: float, profit: float):
    """Call this when bi-weekly profit crosses $500."""
    send_alert(
        title="PROFIT PULL ALERT",
        message=(
            f"Portfolio up ${profit:,.2f} this period!\n"
            f"Current: ${current_value:,.2f} | Base: ${baseline_value:,.2f}\n"
            f"PULL YOUR PROFIT NOW via Robinhood."
        ),
        priority="high",
        tags=["money_with_wings", "chart_with_upwards_trend"],
    )


def alert_strong_signal(ticker: str, score: float, price: float, sources: list[str]):
    """Alert for high-conviction buy signal."""
    source_str = " + ".join(sources)
    send_alert(
        title=f"SIGNAL: {ticker}",
        message=(
            f"Score: {score:.1f}/100\n"
            f"Price: ${price:.2f}\n"
            f"Sources: {source_str}\n"
            f"Open Robinhood to review."
        ),
        priority="high" if score >= 80 else "default",
        tags=["bell", "rocket"] if score >= 80 else ["bell"],
    )


def alert_market_regime(regime: str):
    send_alert(
        title="Market Regime Update",
        message=regime,
        priority="default",
        tags=["chart_with_upwards_trend" if "BULL" in regime else "warning"],
    )


def test_alert():
    ok = send_alert(
        title="Stock Engine Connected",
        message=f"Alert system is live. Topic: {NTFY_TOPIC}",
        tags=["white_check_mark"],
    )
    print(f"  Alert test: {'SENT' if ok else 'FAILED'}")
    print(f"  Subscribe in ntfy app to topic: {NTFY_TOPIC}")


if __name__ == "__main__":
    test_alert()
