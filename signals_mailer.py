"""
signals_mailer.py — Gray Horizons Enterprise
Manages the $49/month Edge Engine signals subscription.
Sends daily picks to all subscribers via SendGrid.
Called by edge_engine/scan.py after daily scan completes.

Subscriber list stored in signals_subscribers.json
Railway env vars:
  SENDGRID_API_KEY
  FROM_EMAIL / SENDER_EMAIL
  STRIPE_SIGNALS_LINK  — separate Stripe subscription link for $49/mo
"""

import os
import json
import datetime
import requests

DATA_DIR         = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "signals_subscribers.json")
SENDGRID_KEY     = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL       = os.getenv("FROM_EMAIL", os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com"))
STRIPE_SIGNALS   = os.getenv("STRIPE_SIGNALS_LINK", "")


def _load_subscribers() -> list:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_subscribers(subs: list):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f, indent=2)


def add_subscriber(email: str, name: str = "", stripe_customer: str = "") -> bool:
    subs = _load_subscribers()
    emails = [s["email"].lower() for s in subs]
    if email.lower() in emails:
        print(f"[SIGNALS] {email} already subscribed")
        return False
    subs.append({
        "email": email.lower(),
        "name": name,
        "stripe_customer": stripe_customer,
        "joined": datetime.datetime.utcnow().isoformat(),
        "active": True,
    })
    _save_subscribers(subs)
    print(f"[SIGNALS] Added subscriber: {email}")
    return True


def remove_subscriber(email: str):
    subs = _load_subscribers()
    subs = [s for s in subs if s["email"].lower() != email.lower()]
    _save_subscribers(subs)
    print(f"[SIGNALS] Removed subscriber: {email}")


def get_active_subscribers() -> list:
    return [s for s in _load_subscribers() if s.get("active", True)]


def build_signals_email(signals: dict, date_str: str) -> str:
    stocks  = signals.get("stocks", [])
    crypto  = signals.get("crypto", [])
    bets    = signals.get("bets", [])

    def fmt_stock(s):
        ticker  = s.get("ticker", "")
        action  = s.get("action", "WATCH")
        conf    = s.get("confidence", 0)
        reason  = s.get("reason", "")
        price   = s.get("price", "")
        return f"""
        <tr>
          <td style="padding:10px 16px;font-weight:bold;color:#38bdf8;">{ticker}</td>
          <td style="padding:10px 16px;"><span style="background:{'#16a34a' if 'BUY' in action.upper() else '#dc2626'};color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;">{action}</span></td>
          <td style="padding:10px 16px;color:#94a3b8;">{f'${price}' if price else '—'}</td>
          <td style="padding:10px 16px;color:#e2e8f0;font-size:13px;">{reason}</td>
          <td style="padding:10px 16px;color:#22c55e;">{conf}%</td>
        </tr>"""

    def fmt_crypto(c):
        sym    = c.get("symbol", "")
        action = c.get("action", "WATCH")
        conf   = c.get("confidence", 0)
        reason = c.get("reason", "")
        return f"""
        <tr>
          <td style="padding:10px 16px;font-weight:bold;color:#f59e0b;">{sym}</td>
          <td style="padding:10px 16px;"><span style="background:{'#16a34a' if 'BUY' in action.upper() else '#dc2626'};color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;">{action}</span></td>
          <td style="padding:10px 16px;color:#e2e8f0;font-size:13px;">{reason}</td>
          <td style="padding:10px 16px;color:#22c55e;">{conf}%</td>
        </tr>"""

    def fmt_bet(b):
        game   = b.get("game", "")
        pick   = b.get("pick", "")
        odds   = b.get("odds", "")
        edge   = b.get("edge_pct", 0)
        kelly  = b.get("kelly_fraction", 0)
        return f"""
        <tr>
          <td style="padding:10px 16px;color:#e2e8f0;font-size:13px;">{game}</td>
          <td style="padding:10px 16px;font-weight:bold;color:#38bdf8;">{pick}</td>
          <td style="padding:10px 16px;color:#94a3b8;">{odds}</td>
          <td style="padding:10px 16px;color:#22c55e;">{edge:.1f}%</td>
          <td style="padding:10px 16px;color:#f59e0b;">{kelly:.1%} of bankroll</td>
        </tr>"""

    stock_rows  = "".join(fmt_stock(s) for s in stocks[:8])
    crypto_rows = "".join(fmt_crypto(c) for c in crypto[:6])
    bet_rows    = "".join(fmt_bet(b) for b in bets[:5])

    disclaimer = "<p style='color:#475569;font-size:11px;margin-top:24px;'>This is not financial or gambling advice. All signals are algorithmic and for informational purposes only. Past performance does not guarantee future results. Bet responsibly.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;">
<div style="max-width:680px;margin:32px auto;background:#1e293b;border-radius:12px;overflow:hidden;">
  <div style="background:#0f172a;padding:28px 36px;border-bottom:1px solid #334155;">
    <h1 style="margin:0;color:#38bdf8;font-size:20px;">Gray Horizons Edge Engine</h1>
    <p style="margin:6px 0 0;color:#64748b;font-size:13px;">Daily Signals Report — {date_str}</p>
  </div>
  <div style="padding:28px 36px;">

    {"" if not stocks else f'''
    <h2 style="color:#38bdf8;font-size:15px;margin:0 0 12px;border-bottom:1px solid #334155;padding-bottom:8px;">STOCK SIGNALS</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:28px;">
      <tr style="background:#0f172a;font-size:12px;color:#64748b;text-transform:uppercase;">
        <th style="padding:8px 16px;text-align:left;">Ticker</th><th style="padding:8px 16px;text-align:left;">Signal</th>
        <th style="padding:8px 16px;text-align:left;">Price</th><th style="padding:8px 16px;text-align:left;">Reason</th>
        <th style="padding:8px 16px;text-align:left;">Conf.</th>
      </tr>
      {stock_rows}
    </table>'''}

    {"" if not crypto else f'''
    <h2 style="color:#f59e0b;font-size:15px;margin:0 0 12px;border-bottom:1px solid #334155;padding-bottom:8px;">CRYPTO SIGNALS</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:28px;">
      <tr style="background:#0f172a;font-size:12px;color:#64748b;text-transform:uppercase;">
        <th style="padding:8px 16px;text-align:left;">Asset</th><th style="padding:8px 16px;text-align:left;">Signal</th>
        <th style="padding:8px 16px;text-align:left;">Reason</th><th style="padding:8px 16px;text-align:left;">Conf.</th>
      </tr>
      {crypto_rows}
    </table>'''}

    {"" if not bets else f'''
    <h2 style="color:#a855f7;font-size:15px;margin:0 0 12px;border-bottom:1px solid #334155;padding-bottom:8px;">SPORTS EDGE PICKS</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:28px;">
      <tr style="background:#0f172a;font-size:12px;color:#64748b;text-transform:uppercase;">
        <th style="padding:8px 16px;text-align:left;">Game</th><th style="padding:8px 16px;text-align:left;">Pick</th>
        <th style="padding:8px 16px;text-align:left;">Odds</th><th style="padding:8px 16px;text-align:left;">Edge</th>
        <th style="padding:8px 16px;text-align:left;">Size</th>
      </tr>
      {bet_rows}
    </table>'''}

    {disclaimer}
  </div>
  <div style="background:#0f172a;padding:16px 36px;text-align:center;color:#475569;font-size:12px;">
    Gray Horizons Edge Engine · $49/month subscription ·
    <a href="https://grayhorizonsenterprise.com/signals/unsubscribe" style="color:#475569;">Unsubscribe</a>
  </div>
</div>
</body>
</html>"""


def send_daily_signals(signals: dict):
    """Send today's signals to all active subscribers."""
    subs = get_active_subscribers()
    if not subs:
        print("[SIGNALS] No active subscribers — skipping send")
        return

    if not SENDGRID_KEY:
        print("[SIGNALS] No SendGrid key — skipping send")
        return

    date_str = datetime.date.today().strftime("%B %d, %Y")
    html     = build_signals_email(signals, date_str)

    success = fail = 0
    for sub in subs:
        payload = {
            "personalizations": [{"to": [{"email": sub["email"], "name": sub.get("name", "")}]}],
            "from": {"email": FROM_EMAIL, "name": "Gray Horizons Edge Engine"},
            "subject": f"Edge Engine Signals — {date_str}",
            "content": [{"type": "text/html", "value": html}],
        }
        try:
            r = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            if r.status_code in (200, 202):
                success += 1
            else:
                print(f"[SIGNALS] Failed to send to {sub['email']}: {r.status_code}")
                fail += 1
        except Exception as e:
            print(f"[SIGNALS] Error sending to {sub['email']}: {e}")
            fail += 1

    print(f"[SIGNALS] Daily send complete — {success} sent, {fail} failed, {len(subs)} total subscribers")


def send_welcome_email(email: str, name: str = ""):
    """Send confirmation email when someone subscribes."""
    if not SENDGRID_KEY:
        return
    first = name.split()[0] if name else "there"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;background:#1e293b;border-radius:12px;overflow:hidden;">
      <div style="background:#0f172a;padding:24px 32px;">
        <h1 style="color:#38bdf8;margin:0;font-size:18px;">You're in — Gray Horizons Edge Engine</h1>
      </div>
      <div style="padding:28px 32px;color:#e2e8f0;">
        <p>Hey {first},</p>
        <p>Your subscription is active. You'll receive daily signals every morning covering:</p>
        <ul>
          <li>Stock signals with entry points and confidence scores</li>
          <li>Crypto signals with trend analysis</li>
          <li>Sports edge picks with Kelly criterion sizing</li>
        </ul>
        <p>First report arrives tomorrow morning.</p>
        <p style="color:#94a3b8;font-size:13px;">Gray Horizons Enterprise</p>
      </div>
    </div>"""
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
        "subject": "You're subscribed — Edge Engine signals start tomorrow",
        "content": [{"type": "text/html", "value": html}],
    }
    try:
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        print(f"[SIGNALS] Welcome email sent to {email}")
    except Exception as e:
        print(f"[SIGNALS] Welcome email error: {e}")


if __name__ == "__main__":
    subs = get_active_subscribers()
    print(f"Active subscribers: {len(subs)}")
    for s in subs:
        print(f"  {s['email']} — joined {s['joined'][:10]}")
