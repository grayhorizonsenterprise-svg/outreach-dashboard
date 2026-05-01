"""
notify.py — all phone alerts via ntfy.sh (free, no account needed)

Phone setup (one time):
  1. Install 'ntfy' app (iOS App Store or Google Play — search "ntfy")
  2. Tap Subscribe → enter your NTFY_TOPIC from .env
  3. Done. Alerts arrive instantly.
"""

import requests
from config import NTFY_TOPIC

BASE = f"https://ntfy.sh/{NTFY_TOPIC}"


def _send(title: str, body: str, priority: str = "default", tags: str = "bell"):
    try:
        requests.post(BASE, data=body.encode(), headers={
            "Title": title, "Priority": priority, "Tags": tags
        }, timeout=8)
    except Exception:
        pass  # alerts are best-effort, never crash the scan


def alert_top_stock(ticker: str, score: float, price: float, note: str):
    _send(
        f"STOCK: {ticker} — Score {score:.0f}",
        f"Price: ${price:.2f}\n{note}\nOpen Robinhood",
        priority="high", tags="chart_with_upwards_trend,rocket"
    )


def alert_top_crypto(coin: str, symbol: str, score: float, price: float,
                     change_24h: float, note: str):
    _send(
        f"CRYPTO: {symbol} — Score {score:.0f}",
        f"${price:,.4f} ({change_24h:+.1f}% 24h)\n{note}\nCheck Coinbase / CashApp",
        priority="high", tags="coin,chart_with_upwards_trend"
    )


def alert_top_bet(game: str, bet_on: str, odds: int, book: str,
                  our_prob: float, edge: float, ev: float):
    sign = "+" if odds > 0 else ""
    _send(
        f"BET ALERT: {bet_on}",
        f"Game: {game}\nOdds: {sign}{odds} on {book}\n"
        f"Win prob: {our_prob:.0%} | Edge: +{edge:.1f}%\n"
        f"EV per $100: ${ev:+.2f}\nOpen DraftKings",
        priority="urgent", tags="money_with_wings,trophy"
    )


def alert_profit_pull(platform: str, current: float, baseline: float, profit: float):
    _send(
        f"PULL PROFITS — {platform}",
        f"Up ${profit:,.2f} this period!\n"
        f"Current: ${current:,.2f} | Base: ${baseline:,.2f}\n"
        f"TAKE PROFITS NOW",
        priority="urgent", tags="money_with_wings,rotating_light"
    )


def alert_daily_summary(stocks: int, cryptos: int, bets: int, top_pick: str):
    _send(
        "Daily Scan Complete",
        f"Stocks: {stocks} signals | Crypto: {cryptos} signals | Bets: {bets} signals\n"
        f"Top pick: {top_pick}",
        priority="default", tags="white_check_mark"
    )
