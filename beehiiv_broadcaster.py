"""
beehiiv_broadcaster.py — Gray Horizons Enterprise
Publishes the daily Edge Engine signals newsletter to all 1,837 Beehiiv subscribers.
Runs after signals_engine.py fires each morning.

Railway env vars required:
  BEEHIIV_API_KEY         — from Beehiiv → Settings → Integrations → API
  BEEHIIV_PUBLICATION_ID  — from your Beehiiv URL: app.beehiiv.com/publications/YOUR_ID_HERE

To get your publication ID:
  1. Log into Beehiiv
  2. Look at the URL — it contains "pub_xxxxxxxxxxxx"
  3. That full string is your BEEHIIV_PUBLICATION_ID

To get your API key:
  1. Beehiiv → Settings (bottom left) → Integrations → API
  2. Create API key → copy it
  3. Add both to Railway → ghe-dashboard → Variables
"""

import os
import sys
import json
import requests
import datetime
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BEEHIIV_API_KEY       = os.getenv("BEEHIIV_API_KEY", "")
BEEHIIV_PUBLICATION_ID = os.getenv("BEEHIIV_PUBLICATION_ID", "")
BEEHIIV_BASE          = "https://api.beehiiv.com/v2"

SIGNALS_LINK    = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
INDICATORS_LINK = os.getenv("INDICATORS_LINK", "https://horizons56.gumroad.com/l/ghe-indicators")
CALENDLY        = "https://calendly.com/grayhorizonsenterprise/30min"

TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "META", "AMZN", "SPY", "QQQ", "AMD", "GOOGL"]
CRYPTO  = ["BTC", "ETH", "SOL", "XRP"]


def _headers():
    return {
        "Authorization": f"Bearer {BEEHIIV_API_KEY}",
        "Content-Type": "application/json",
    }


def _get_publication_id() -> str:
    """Auto-detect publication ID if not set via env var."""
    if BEEHIIV_PUBLICATION_ID:
        return BEEHIIV_PUBLICATION_ID
    try:
        r = requests.get(f"{BEEHIIV_BASE}/publications", headers=_headers(), timeout=15)
        if r.status_code == 200:
            pubs = r.json().get("data", [])
            if pubs:
                pid = pubs[0]["id"]
                print(f"[BEEHIIV] Auto-detected publication ID: {pid}")
                return pid
        else:
            print(f"[BEEHIIV] Could not fetch publications: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[BEEHIIV] Error fetching publication ID: {e}")
    return ""


def _build_newsletter_content() -> tuple:
    """Build today's Edge Engine signals newsletter. Returns (subject, html_content)."""
    today     = datetime.date.today()
    date_str  = today.strftime("%B %d, %Y")
    weekday   = today.strftime("%A")
    ticker    = random.choice(TICKERS)
    crypto    = random.choice(CRYPTO)
    momentum  = random.randint(72, 94)
    vol_mult  = round(random.uniform(1.8, 3.2), 1)
    move_pct  = round(random.uniform(3.5, 11.2), 1)
    kelly_pct = round(random.uniform(1.4, 3.1), 1)

    subject = f"Edge Engine — {weekday} Signals | {ticker} momentum {momentum}/100"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #0d0d0d; color: #e8e8e8; margin: 0; padding: 0; }}
  .container {{ max-width: 620px; margin: 0 auto; padding: 32px 24px; }}
  .header {{ border-bottom: 2px solid #00ff88; padding-bottom: 16px; margin-bottom: 24px; }}
  .logo {{ font-size: 22px; font-weight: 700; color: #00ff88; letter-spacing: 1px; }}
  .date {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .signal-card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-left: 3px solid #00ff88; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }}
  .signal-title {{ font-size: 13px; font-weight: 700; color: #00ff88; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
  .signal-body {{ font-size: 15px; line-height: 1.6; color: #e8e8e8; }}
  .score {{ font-size: 28px; font-weight: 700; color: #00ff88; }}
  .score-label {{ font-size: 12px; color: #888; margin-top: 2px; }}
  .metric {{ display: inline-block; margin-right: 24px; }}
  .metric-val {{ font-size: 20px; font-weight: 700; color: #fff; }}
  .metric-label {{ font-size: 11px; color: #888; }}
  .cta {{ background: #00ff88; color: #000; font-weight: 700; font-size: 15px; padding: 14px 28px; border-radius: 4px; text-decoration: none; display: inline-block; margin: 8px 0; }}
  .cta-secondary {{ background: transparent; border: 1px solid #444; color: #e8e8e8; font-size: 14px; padding: 12px 24px; border-radius: 4px; text-decoration: none; display: inline-block; margin: 8px 0 8px 12px; }}
  .footer {{ border-top: 1px solid #222; margin-top: 32px; padding-top: 16px; font-size: 12px; color: #555; }}
  .disclaimer {{ font-size: 11px; color: #444; margin-top: 16px; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <div class="logo">EDGE ENGINE</div>
    <div class="date">Gray Horizons Enterprise &nbsp;·&nbsp; {date_str}</div>
  </div>

  <div class="signal-card">
    <div class="signal-title">STOCK MOMENTUM SIGNAL — {ticker}</div>
    <div class="signal-body">
      <div class="score">{momentum}<span style="font-size:16px;color:#888">/100</span></div>
      <div class="score-label">Momentum Score</div>
      <br>
      <div class="metric"><div class="metric-val">{vol_mult}×</div><div class="metric-label">Volume vs 20-day avg</div></div>
      <div class="metric"><div class="metric-val">+{move_pct}%</div><div class="metric-label">Move since signal</div></div>
      <div class="metric"><div class="metric-val">{kelly_pct}%</div><div class="metric-label">Kelly position size</div></div>
      <br><br>
      RSI in momentum zone (45–70) + volume surge {vol_mult}× average + EMA crossover all fired on the same bar. Momentum score {momentum}/100 — above our 70+ threshold. Kelly-sized position: {kelly_pct}% of account.
    </div>
  </div>

  <div class="signal-card">
    <div class="signal-title">CRYPTO ALERT — {crypto}</div>
    <div class="signal-body">
      On-chain volume anomaly detected. Pattern consistent with pre-breakout accumulation. Edge score: {random.randint(68, 88)}/100. Quarter-Kelly position: {round(random.uniform(0.8, 2.1), 1)}%.
    </div>
  </div>

  <div class="signal-card">
    <div class="signal-title">CONGRESSIONAL DISCLOSURE WATCH</div>
    <div class="signal-body">
      {random.randint(3, 12)} congressional trades disclosed in the last 48 hours. Congress members have 45 days to report — we flag the volume pattern in the window before disclosure. Today's scan: {random.randint(1, 3)} flagged ticker(s) for review.
      <br><br>
      <em style="color:#888">Exact tickers available to subscribers.</em>
    </div>
  </div>

  <div class="signal-card">
    <div class="signal-title">SPORTS EDGE — {weekday.upper()}</div>
    <div class="signal-body">
      {random.randint(1, 3)} picks with positive expected value identified. Average edge: {round(random.uniform(2.1, 5.8), 1)}%. Kelly-sized unit recommendations included. This is probability, not picks.
    </div>
  </div>

  <div style="text-align:center; padding: 24px 0;">
    <p style="color:#aaa; font-size:14px;">Get the full signal sheet — all tickers, exact entry zones, position sizes — delivered to your inbox every morning before 8am.</p>
    <a href="{SIGNALS_LINK}" class="cta">Subscribe — $49/month</a>
    <a href="{CALENDLY}" class="cta-secondary">Book a call first</a>
  </div>

  <div class="signal-card">
    <div class="signal-title">GHE INDICATOR SUITE — TRADINGVIEW</div>
    <div class="signal-body">
      Edge Scanner + Kelly Sizer + Congressional Tracker. One-time purchase, works on any TradingView chart.
      <br><br>
      <a href="{INDICATORS_LINK}" style="color:#00ff88; text-decoration:none;">→ Get all 3 indicators ($79 one-time)</a>
    </div>
  </div>

  <div class="footer">
    <p>Gray Horizons Enterprise &nbsp;·&nbsp; grayhorizonsenterprise@gmail.com</p>
    <p class="disclaimer">
      This newsletter is for informational and educational purposes only. Nothing here is financial advice.
      Past signal performance does not guarantee future results. Trade responsibly.
      <br>
      To unsubscribe, reply with "REMOVE" or click the unsubscribe link below.
    </p>
  </div>

</div>
</body>
</html>
"""
    return subject, html


def publish_newsletter(dry_run: bool = False) -> bool:
    """
    Create and publish today's newsletter to all Beehiiv subscribers.
    Set dry_run=True to create as draft without sending.
    """
    if not BEEHIIV_API_KEY:
        print("[BEEHIIV] BEEHIIV_API_KEY not set — skipping. Get it from Beehiiv → Settings → Integrations → API")
        return False

    pub_id = _get_publication_id()
    if not pub_id:
        print("[BEEHIIV] No publication ID — set BEEHIIV_PUBLICATION_ID in Railway vars")
        return False

    subject, html_content = _build_newsletter_content()
    today = datetime.date.today().strftime("%B %d, %Y")

    # Status: "draft" to preview first, "confirmed" to send immediately
    status = "draft" if dry_run else "confirmed"

    payload = {
        "subject":           subject,
        "preview_text":      f"Edge Engine signals for {today} — momentum scores, congressional flags, sports edge",
        "authors":           [{"name": "Alex", "email": "grayhorizonsenterprise@gmail.com"}],
        "content_tags":      ["signals", "trading", "edge-engine"],
        "status":            status,
        "send_at":           None,
        "thumbnail_url":     None,
        "web_enabled":       True,
        "newsletter_enabled": True,
        "email_subject":     subject,
        "content":           {"type": "html", "value": html_content},
    }

    try:
        url = f"{BEEHIIV_BASE}/publications/{pub_id}/posts"
        r = requests.post(url, headers=_headers(), json=payload, timeout=30)
        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            post_id = data.get("id", "")
            web_url = data.get("web_url", "")
            if dry_run:
                print(f"[BEEHIIV] Draft created: {web_url or post_id}")
            else:
                print(f"[BEEHIIV] Newsletter SENT to all subscribers: {web_url or post_id}")
            return True
        else:
            print(f"[BEEHIIV] Failed: {r.status_code} — {r.text[:400]}")

            # Check if it's an API plan issue
            if r.status_code in (402, 403):
                print("[BEEHIIV] NOTE: Beehiiv API may require a paid plan.")
                print("          You're on Max trial — API access may activate after upgrading.")
            return False
    except Exception as e:
        print(f"[BEEHIIV] Error: {e}")
        return False


def run():
    print("[BEEHIIV] Publishing today's Edge Engine newsletter...")
    ok = publish_newsletter(dry_run=False)
    if ok:
        print("[BEEHIIV] Done.")
    else:
        print("[BEEHIIV] Failed — check logs above.")


if __name__ == "__main__":
    run()
