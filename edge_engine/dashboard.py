"""
dashboard.py — Web dashboard for the Edge Engine.
Serves a live investing dashboard at http://localhost:5050
v2026.05.03

Run:  python dashboard.py
Then open your browser to http://localhost:5050
"""

import sys, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd
import numpy as np

from flask import Flask, render_template, jsonify, request as flask_request
from config import (
    STOCKS, CRYPTOS, SPORTS, SPACEX_ECOSYSTEM, CATEGORIES,
    ODDS_KEY, QUIVER_KEY, MIN_SIGNAL_SCORE
)
from signals import (
    get_stock_signals, get_crypto_signals,
    get_betting_signals, get_congress_buys, StockSignal,
    get_action_plan, get_scout_picks, get_live_scores, get_smart_parlays,
    rescore_bets,
)
from patterns import detect_patterns, bad_stock_warnings

app = Flask(__name__)

# ── In-memory cache — refreshed every 15 minutes in background ────────────────
CACHE: dict = {
    "last_updated": None,
    "stocks": [],
    "spacex": [],
    "crypto": [],
    "bets": [],
    "warnings": [],
    "regime": "UNKNOWN",
    "action_plan": {},
    "scout_picks": [],      # tonight's high-confidence picks from full ensemble
    "live_scores": {},      # ESPN live + upcoming game scores (free, no key)
    "parlays": [],          # auto-built smart parlays from HIGH conf picks
    "loading": True,
}
CACHE_LOCK = threading.Lock()

# ── Odds API rate limiter — fetch at most twice a day (8am + 6pm) ─────────────
# Free tier = 500 requests/month. 7 sports × 2/day × 30 days = 420 calls/month.
_last_odds_fetch: datetime | None = None
_raw_bet_sigs: list = []   # preserved between stock/crypto refreshes
_ODDS_FETCH_HOURS = {8, 18}  # 8am and 6pm local server time


# ══════════════════════════════════════════════════════════════════════════════
# DATA BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _score_color(score: float) -> str:
    if score >= 72: return "green"
    if score >= 55: return "yellow"
    if score >= 40: return "orange"
    return "red"

def _trend_icon(trend: str) -> str:
    return {"STRONG BUY": "rocket", "BUY": "arrow-up", "WATCH": "eye",
            "SKIP": "x-circle"}.get(trend, "minus")

def build_stock_rows(signals: list[StockSignal], congress: dict,
                     category_tickers: list[str] | None = None) -> list[dict]:
    rows = []
    sig_map = {s.ticker: s for s in signals}
    tickers = category_tickers or [s.ticker for s in signals]

    for ticker in tickers:
        s = sig_map.get(ticker)
        if not s:
            continue

        # Pull extra data for patterns
        try:
            df = yf.Ticker(ticker).history(period="1y")
        except Exception:
            df = pd.DataFrame()

        patterns = detect_patterns(df) if not df.empty else []
        warnings = bad_stock_warnings(df, ticker) if not df.empty else []

        cong_score = congress.get(ticker, 0)
        final = round(s.score * 0.75 + cong_score * 0.25, 1)
        pelosi = cong_score >= 70

        # SpaceX context
        spacex_desc = SPACEX_ECOSYSTEM.get(ticker, "")

        rows.append({
            "ticker":    ticker,
            "score":     final,
            "color":     _score_color(final),
            "price":     s.price,
            "change_1d": s.change_1d,
            "rsi":       s.rsi,
            "trend":     s.trend,
            "icon":      _trend_icon(s.trend),
            "note":      s.note,
            "pelosi":    pelosi,
            "congress":  cong_score >= 40,
            "spacex":    spacex_desc,
            "patterns":  [{"name": p.name, "type": p.type, "note": p.note,
                           "conf": p.confidence} for p in patterns],
            "warnings":  warnings,
            "has_warning": len(warnings) > 0 or any(p.type in ("BEARISH","WARNING") for p in patterns),
        })

    return sorted(rows, key=lambda x: x["score"], reverse=True)


def build_crypto_rows(signals) -> list[dict]:
    rows = []
    for s in signals:
        rows.append({
            "symbol":    s.symbol,
            "coin":      s.coin,
            "score":     s.score,
            "color":     _score_color(s.score),
            "price":     s.price,
            "change_1h": s.change_1h,
            "change_24h": s.change_24h,
            "change_7d": s.change_7d,
            "trend":     s.trend,
            "note":      s.note,
        })
    return rows


def build_bet_rows(signals) -> list[dict]:
    rows = []
    for s in signals:
        o = s.odds
        decimal = (o / 100 + 1) if o > 0 else (100 / abs(o) + 1)
        def _pay(stake, d=decimal): return round(stake * (d - 1), 2)
        def _stk(target, d=decimal): return round(target / max(d - 1, 0.01), 2)
        rows.append({
            "sport":         s.sport,
            "game":          s.game,
            "bet_on":        s.bet_on,
            "book":          s.book,
            "odds":          s.odds,
            "odds_str":      (f"+{s.odds}" if s.odds > 0 else str(s.odds)),
            "win_pct":       round(s.our_prob * 100, 1),
            "edge":          s.edge_pct,
            "ev":            s.expected_value,
            "conf":          s.confidence,
            "commence":      s.commence,
            "color":         "green" if s.our_prob >= 0.65 else "yellow" if s.our_prob >= 0.55 else "orange",
            "warnings":      s.warnings,
            "rules":         s.rules,
            "scrubbed":      s.scrubbed,
            "model_prob":    round(s.model_prob * 100, 1),
            "model_factors": s.model_factors,
            "model_vs_book": s.model_vs_book,
            "micro_bet":     getattr(s, "micro_bet", False),
            "bet_type":      getattr(s, "bet_type", "VALUE"),
            "decimal":       round(decimal, 3),
            "pay20":  _pay(20),   "pay50":  _pay(50),
            "pay100": _pay(100),  "pay200": _pay(200),
            "stk500":  _stk(500),   "stk1k":   _stk(1000),
            "stk5k":   _stk(5000),  "stk10k":  _stk(10000),
            "stk50k":  _stk(50000), "stk100k": _stk(100000),
        })
    return rows


def market_regime_check() -> str:
    try:
        df = yf.Ticker("SPY").history(period="3mo")
        price = float(df["Close"].iloc[-1])
        ema50 = float(df["Close"].ewm(span=50, adjust=False).mean().iloc[-1])
        d = df["Close"].diff()
        g = d.clip(lower=0).ewm(com=13, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi = float((100 - 100 / (1 + g / l.replace(0, np.nan))).iloc[-1])
        if price > ema50 and rsi > 50:   return "BULL"
        elif price < ema50 and rsi < 45: return "BEAR"
        else:                            return "CHOP"
    except Exception:
        return "UNKNOWN"


def _should_fetch_odds() -> bool:
    """True only on first load or at 8am/6pm — keeps usage under 500 req/month."""
    global _last_odds_fetch
    now = datetime.now()
    if _last_odds_fetch is None:
        return True
    age_hours = (now - _last_odds_fetch).total_seconds() / 3600
    # Refresh if we're in a designated hour AND haven't fetched in the last hour
    if now.hour in _ODDS_FETCH_HOURS and age_hours >= 1:
        return True
    return False


def refresh_cache():
    """Full data refresh — stocks/crypto every 30 min; odds only at 8am + 6pm."""
    global _last_odds_fetch, _raw_bet_sigs
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"[{now_str}] Refreshing cache...")
    try:
        congress = get_congress_buys()
        all_signals = get_stock_signals()

        spacex_rows = build_stock_rows(all_signals, congress, CATEGORIES["SpaceX Ecosystem"])
        stock_rows  = build_stock_rows(all_signals, congress)

        all_warnings = []
        for row in stock_rows:
            if row["has_warning"]:
                all_warnings.append({
                    "ticker":   row["ticker"],
                    "price":    row["price"],
                    "warnings": row["warnings"],
                    "patterns": [p for p in row["patterns"] if p["type"] in ("BEARISH","WARNING")],
                })

        crypto_sigs = get_crypto_signals()

        # Odds API — rate-limited to 2x/day to stay under 500 req/month free tier
        if _should_fetch_odds():
            print(f"[{now_str}] Fetching fresh odds from API...")
            _raw_bet_sigs   = get_betting_signals()
            _last_odds_fetch = datetime.now()
        else:
            next_hour = min((h for h in sorted(_ODDS_FETCH_HOURS) if h > datetime.now().hour), default=min(_ODDS_FETCH_HOURS))
            print(f"[{now_str}] Reusing cached odds (next fetch at {next_hour}:00)")

        bet_rows    = build_bet_rows(_raw_bet_sigs)
        regime      = market_regime_check()
        action_plan = get_action_plan(all_signals, crypto_sigs, _raw_bet_sigs, bankroll=100.0)
        crypto_rows = build_crypto_rows(crypto_sigs)

        scout_picks = get_scout_picks()
        live_scores = get_live_scores()
        parlays     = get_smart_parlays(_raw_bet_sigs)

        with CACHE_LOCK:
            CACHE.update({
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stocks":      stock_rows[:40],
                "spacex":      spacex_rows,
                "crypto":      crypto_rows,
                "bets":        bet_rows,
                "warnings":    all_warnings,
                "regime":      regime,
                "action_plan": action_plan,
                "scout_picks": scout_picks,
                "live_scores": live_scores,
                "parlays":     parlays,
                "loading":     False,
            })
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache refreshed. "
              f"{len(stock_rows)} stocks | {len(crypto_rows)} crypto | "
              f"{len(bet_rows)} bets | {len(all_warnings)} warnings")
    except Exception as e:
        print(f"[ERROR] Cache refresh failed: {e}")
        with CACHE_LOCK:
            CACHE["loading"] = False


def _bet_scout_refresh():
    """
    Lightweight ESPN-only refresh — every 20 minutes during 7am-10pm.
    Updates live scores and scout picks using CACHED odds (no Odds API calls).
    Odds API is only called twice daily in refresh_cache() to preserve quota.
    """
    while True:
        time.sleep(1200)  # 20 minutes
        now = datetime.now()
        if 7 <= now.hour < 22:  # daytime only
            print(f"[{now.strftime('%H:%M:%S')}] Scout refresh: injuries + news + scores (no odds API call)...")
            try:
                # Re-score cached bets with fresh ESPN injury reports + news headlines
                # Catches late scratches, game-day decisions, suspensions between odds fetches
                rescored     = rescore_bets(_raw_bet_sigs)
                bet_rows     = build_bet_rows(rescored)
                scout_picks  = get_scout_picks()
                live_scores  = get_live_scores()
                parlays      = get_smart_parlays(rescored)
                with CACHE_LOCK:
                    CACHE["bets"]        = bet_rows
                    CACHE["scout_picks"] = scout_picks
                    CACHE["live_scores"] = live_scores
                    CACHE["parlays"]     = parlays
                print(f"[{now.strftime('%H:%M:%S')}] Scout done: {len(bet_rows)} bets rescored | "
                      f"{len(scout_picks)} picks | scores updated")
            except Exception as e:
                print(f"[SCOUT ERROR] {e}")


def background_refresh():
    """Background thread — full refresh every 30 minutes."""
    refresh_cache()
    while True:
        time.sleep(1800)  # 30 minutes
        refresh_cache()


# Start background thread when loaded by gunicorn
_started = False
def _ensure_started():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=background_refresh, daemon=True).start()
        threading.Thread(target=_bet_scout_refresh, daemon=True).start()

with app.app_context():
    _ensure_started()


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

NAV_LINKS = {
    "outreach": os.getenv("GHE_DASHBOARD_URL", ""),
    "grants":   os.getenv("GHE_GRANT_AGENT_URL", ""),
}

@app.route("/")
def index():
    is_demo = flask_request.args.get("demo") == "1"
    return render_template("index.html", nav=NAV_LINKS, is_demo=is_demo)

@app.route("/health")
def health():
    """Railway health check — returns immediately, never blocks."""
    return jsonify({"status": "ok", "loading": CACHE["loading"]}), 200

@app.route("/api/data")
def api_data():
    with CACHE_LOCK:
        return jsonify(dict(CACHE))

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    threading.Thread(target=refresh_cache, daemon=True).start()
    return jsonify({"status": "refreshing"})

@app.route("/api/scout")
def api_scout():
    """Tonight's high-confidence picks from the full ensemble model."""
    with CACHE_LOCK:
        return jsonify({"picks": CACHE.get("scout_picks", []),
                        "last_updated": CACHE.get("last_updated")})

@app.route("/api/scores")
def api_scores():
    """ESPN live + upcoming game scores across all major sports."""
    with CACHE_LOCK:
        return jsonify({"scores": CACHE.get("live_scores", {}),
                        "last_updated": CACHE.get("last_updated")})

@app.route("/api/parlays")
def api_parlays():
    """Auto-built smart parlays from HIGH confidence picks."""
    with CACHE_LOCK:
        return jsonify({"parlays": CACHE.get("parlays", []),
                        "last_updated": CACHE.get("last_updated")})

@app.route("/api/wins")
def api_wins():
    """Return wins/losses log from wins_log.json (root project dir or edge_engine/)."""
    import json as _json
    for p in [
        Path(__file__).parent.parent / "wins_log.json",
        Path(__file__).parent / "wins_log.json",
        Path("wins_log.json"),
    ]:
        if p.exists():
            try:
                return jsonify(_json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return jsonify({"picks": [], "overall": {"wins": 0, "losses": 0, "pushes": 0}})

@app.route("/api/wins/log", methods=["POST"])
def api_wins_log():
    """POST {pick, outcome, result, category, date} to append a result to wins_log.json."""
    import json as _json
    data = flask_request.get_json(silent=True) or {}
    wins_path = Path(__file__).parent.parent / "wins_log.json"
    if not wins_path.exists():
        wins_path = Path(__file__).parent / "wins_log.json"
    try:
        log = _json.loads(wins_path.read_text(encoding="utf-8")) if wins_path.exists() else {"picks": [], "overall": {"wins": 0, "losses": 0, "pushes": 0}}
        entry = {k: data.get(k, "") for k in ("pick", "outcome", "result", "category", "date")}
        entry["outcome"] = entry["outcome"].upper()
        log.setdefault("picks", []).append(entry)
        o = log.setdefault("overall", {"wins": 0, "losses": 0, "pushes": 0})
        key = {"WIN": "wins", "LOSS": "losses"}.get(entry["outcome"], "pushes")
        o[key] = o.get(key, 0) + 1
        wins_path.write_text(_json.dumps(log, indent=2), encoding="utf-8")
        return jsonify({"status": "ok", "entry": entry})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/ticker/<ticker>")
def api_ticker(ticker: str):
    """Single ticker deep dive — price history + all patterns."""
    try:
        t = ticker.upper()
        df = yf.Ticker(t).history(period="1y")
        info = yf.Ticker(t).info
        patterns = detect_patterns(df)
        warnings = bad_stock_warnings(df, t)
        return jsonify({
            "ticker":   t,
            "name":     info.get("longName",""),
            "sector":   info.get("sector",""),
            "industry": info.get("industry",""),
            "mktcap":   info.get("marketCap", 0),
            "pe":       info.get("trailingPE", 0),
            "short_pct":info.get("shortPercentOfFloat", 0),
            "spacex_role": SPACEX_ECOSYSTEM.get(t, ""),
            "patterns": [{"name": p.name, "type": p.type,
                          "conf": p.confidence, "note": p.note} for p in patterns],
            "warnings": warnings,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


MEMBER_KEY = os.getenv("MEMBER_KEY", "ghe2025")

@app.route("/member")
def member_dashboard():
    """Read-only subscriber dashboard — shows Today's Plays, Power Plays, Compound Growth Projection."""
    key = flask_request.args.get("key", "")
    if key != MEMBER_KEY:
        return """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>GHE Edge Engine — Member Access</title>
<style>body{background:#0a0e1a;color:#e5e7eb;font-family:'Segoe UI',system-ui,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}
.box{text-align:center;padding:40px;max-width:380px;}
h2{color:#06b6d4;margin-bottom:12px;}p{color:#6b7280;font-size:13px;}
input{background:#111827;border:1px solid #1f2937;color:#e5e7eb;padding:10px 14px;
border-radius:6px;width:100%;margin:16px 0 8px;font-size:14px;box-sizing:border-box;}
button{background:#06b6d4;color:#000;border:none;border-radius:6px;padding:10px 24px;
font-weight:700;cursor:pointer;font-size:14px;width:100%;}
</style></head><body><div class="box">
<h2>GHE Edge Engine</h2>
<p>Enter your subscriber access key to view today's signals.</p>
<form method="get">
<input type="text" name="key" placeholder="Access key" autofocus>
<button type="submit">Access Dashboard</button>
</form>
<p style="margin-top:20px;font-size:11px">Access key included in your Gumroad receipt.<br>
Questions? grayhorizonsenterprise@gmail.com</p>
</div></body></html>""", 401

    import json as _json
    with CACHE_LOCK:
        plan    = dict(CACHE.get("action_plan") or {})
        regime  = CACHE.get("regime", "UNKNOWN")
        updated = CACHE.get("last_updated", "")
        loading = CACHE.get("loading", True)
    plan_json = _json.dumps(plan)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="900">
<title>GHE Edge Engine — Member Dashboard</title>
<style>
:root{{--bg:#0a0e1a;--panel:#111827;--border:#1f2937;--text:#e5e7eb;--muted:#6b7280;
--green:#10b981;--yellow:#f59e0b;--orange:#f97316;--red:#ef4444;--blue:#3b82f6;
--purple:#8b5cf6;--cyan:#06b6d4;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;}}
.header{{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);border-bottom:1px solid var(--border);
padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;}}
.header h1{{font-size:18px;font-weight:700;letter-spacing:1px;color:#fff;}}
.header h1 span{{color:var(--cyan);}}
.badge{{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:1px;}}
.regime-BULL{{background:#064e3b;color:var(--green);border:1px solid var(--green);}}
.regime-BEAR{{background:#450a0a;color:var(--red);border:1px solid var(--red);}}
.regime-CHOP{{background:#451a03;color:var(--yellow);border:1px solid var(--yellow);}}
.regime-UNKNOWN{{background:#1f2937;color:var(--muted);border:1px solid var(--border);}}
.sub-badge{{background:#0c2a36;color:var(--cyan);border:1px solid var(--cyan);padding:4px 10px;
border-radius:20px;font-size:10px;font-weight:700;letter-spacing:1px;}}
.updated{{font-size:11px;color:var(--muted);}}
.action-center{{background:linear-gradient(135deg,#0d1f0d 0%,#0a1628 100%);
border-bottom:2px solid var(--green);padding:16px 24px;}}
.ac-title{{font-size:11px;font-weight:700;color:var(--green);text-transform:uppercase;
letter-spacing:2px;margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
.pulse-dot{{width:8px;height:8px;border-radius:50%;background:var(--green);
animation:pulse 1.5s ease-in-out infinite;}}
@keyframes pulse{{0%,100%{{opacity:.4}}50%{{opacity:1}}}}
.plays-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;}}
.play-card{{background:rgba(0,0,0,.4);border-radius:10px;padding:14px 16px;
border:1px solid rgba(255,255,255,.06);}}
.play-card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}}
.play-type{{font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--muted);}}
.play-ticker{{font-size:20px;font-weight:800;color:#fff;}}
.play-sub{{font-size:11px;color:var(--muted);margin-top:1px;}}
.play-action{{display:inline-block;padding:4px 10px;border-radius:6px;font-size:10px;font-weight:700;
background:var(--green);color:#000;}}
.play-action.crypto{{background:var(--purple);color:#fff;}}
.play-action.bet{{background:var(--yellow);color:#000;}}
.play-rows{{display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;}}
.play-stat-label{{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}}
.play-stat-value{{font-size:13px;font-weight:700;color:var(--text);margin-top:1px;}}
.play-stat-value.green{{color:var(--green);}}
.play-stat-value.red{{color:var(--red);}}
.play-stat-value.yellow{{color:var(--yellow);}}
.play-reason{{font-size:10px;color:var(--muted);margin-top:8px;
border-top:1px solid rgba(255,255,255,.05);padding-top:6px;}}
.proj-row{{font-size:11px;color:var(--muted);margin-top:6px;line-height:1.6;}}
.proj-val{{color:var(--green);font-weight:700;}}
.pp-header{{font-size:10px;font-weight:700;color:var(--yellow);text-transform:uppercase;
letter-spacing:1px;padding:8px 0 4px;border-top:1px solid var(--border);}}
.pp-badge{{display:inline-block;background:#451a03;color:var(--yellow);padding:2px 8px;
border-radius:4px;font-size:9px;font-weight:700;margin-bottom:6px;}}
.no-plays{{color:var(--muted);font-size:13px;padding:16px 0;}}
.footer{{text-align:center;padding:28px;color:var(--muted);font-size:11px;border-top:1px solid var(--border);}}
.loading-msg{{text-align:center;padding:60px;color:var(--muted);font-size:14px;}}
</style>
</head>
<body>

<div class="header">
  <h1>GRAY HORIZONS <span>EDGE ENGINE</span></h1>
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="badge regime-{regime}">{regime}</span>
    <span class="sub-badge">MEMBER</span>
    <span class="updated">Updated: {updated or 'loading...'}</span>
  </div>
</div>

<div class="action-center">
  <div class="ac-title">
    <div class="pulse-dot"></div>
    TODAY'S PLAYS — EXACT DOLLAR ACTIONS
    <span style="margin-left:auto;font-size:10px;color:var(--muted)" id="gen-time">
      {(plan.get('summary') or {}).get('generated', '')}
    </span>
  </div>
  <div class="plays-grid" id="plays-grid">
    {"<div class='loading-msg'>Signals loading — refresh in 2 minutes.</div>" if loading or not plan else ""}
  </div>
</div>

<div class="footer">
  Gray Horizons Edge Engine &mdash; Member Access &mdash; Page auto-refreshes every 15 min.<br>
  Not financial advice. AI-generated signals for informational purposes only.
</div>

<script>
const plan = {plan_json};

function renderPlays() {{
  const grid = document.getElementById('plays-grid');
  if (!plan || !plan.summary) return;
  let html = '';

  (plan.stocks || []).forEach((p, i) => {{
    const proj = p.proj || {{}};
    const projRow = (proj.profit_100 !== undefined) ? `
      <div class="proj-row">If you invest &rarr;
        <strong>$100</strong>: <span class="proj-val">+$${{(+proj.profit_100||0).toFixed(2)}}</span> &nbsp;|&nbsp;
        <strong>$500</strong>: <span class="proj-val">+$${{(+proj.profit_500||0).toFixed(2)}}</span> &nbsp;|&nbsp;
        <strong>$1,000</strong>: <span class="proj-val">+$${{(+proj.profit_1000||0).toFixed(2)}}</span>
        &mdash; ~${{proj.weeks_est||'?'}} wks
      </div>` : '';
    html += `<div class="play-card">
      <div class="play-card-header">
        <div>
          <div class="play-type">Stock #${{p.rank}} &bull; Robinhood</div>
          <div class="play-ticker">${{p.ticker}}</div>
          <div class="play-sub">Score ${{p.score}} &bull; Entry $${{(+p.entry||0).toFixed(2)}}</div>
        </div>
        <span class="play-action">BUY NOW</span>
      </div>
      <div class="play-rows">
        <div class="play-stat"><div class="play-stat-label">Invest</div>
          <div class="play-stat-value yellow">$${{p.dollar_in}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Target</div>
          <div class="play-stat-value green">$${{p.target}} (+${{p.target_pct}}%)</div></div>
        <div class="play-stat"><div class="play-stat-label">Stop Loss</div>
          <div class="play-stat-value red">$${{p.stop}} (-${{p.stop_pct}}%)</div></div>
        <div class="play-stat"><div class="play-stat-label">Risk/Reward</div>
          <div class="play-stat-value">${{p.rr}}:1</div></div>
        <div class="play-stat"><div class="play-stat-label">Profit at Target</div>
          <div class="play-stat-value green">+$${{p.profit}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Shares (~)</div>
          <div class="play-stat-value">${{p.shares}}</div></div>
      </div>
      <div class="play-reason">Signal: ${{p.reason}}</div>
      ${{projRow}}
    </div>`;
  }});

  (plan.crypto || []).forEach(p => {{
    html += `<div class="play-card">
      <div class="play-card-header">
        <div>
          <div class="play-type">Crypto #${{p.rank}} &bull; Coinbase / CashApp</div>
          <div class="play-ticker">${{p.symbol}}</div>
          <div class="play-sub">${{p.coin}} &bull; Entry $${{(+p.entry||0).toLocaleString()}}</div>
        </div>
        <span class="play-action crypto">BUY NOW</span>
      </div>
      <div class="play-rows">
        <div class="play-stat"><div class="play-stat-label">Invest</div>
          <div class="play-stat-value yellow">$${{p.dollar_in}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Target</div>
          <div class="play-stat-value green">+${{p.target_pct}}%</div></div>
        <div class="play-stat"><div class="play-stat-label">Stop Loss</div>
          <div class="play-stat-value red">-${{p.stop_pct}}%</div></div>
        <div class="play-stat"><div class="play-stat-label">Risk/Reward</div>
          <div class="play-stat-value">${{p.rr}}:1</div></div>
        <div class="play-stat"><div class="play-stat-label">Profit at Target</div>
          <div class="play-stat-value green">+$${{p.profit}}</div></div>
      </div>
      <div class="play-reason">Signal: ${{p.reason}}</div>
    </div>`;
  }});

  (plan.bets || []).forEach(p => {{
    html += `<div class="play-card">
      <div class="play-card-header">
        <div>
          <div class="play-type">Bet #${{p.rank}} &bull; ${{p.platform}}</div>
          <div class="play-ticker" style="font-size:14px">${{p.bet_on}}</div>
          <div class="play-sub">${{p.game}}</div>
        </div>
        <span class="play-action bet">BET</span>
      </div>
      <div class="play-rows">
        <div class="play-stat"><div class="play-stat-label">Wager</div>
          <div class="play-stat-value yellow">$${{p.wager}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Odds</div>
          <div class="play-stat-value">${{p.odds_str}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Win Probability</div>
          <div class="play-stat-value green">${{p.win_pct}}%</div></div>
        <div class="play-stat"><div class="play-stat-label">Payout if Win</div>
          <div class="play-stat-value green">+$${{p.payout}}</div></div>
        <div class="play-stat"><div class="play-stat-label">Edge</div>
          <div class="play-stat-value">+${{p.edge}}%</div></div>
        <div class="play-stat"><div class="play-stat-label">Confidence</div>
          <div class="play-stat-value">${{p.confidence}}</div></div>
      </div>
    </div>`;
  }});

  if (plan.power_plays && plan.power_plays.length) {{
    html += `<div style="grid-column:1/-1;margin-top:4px">
      <div class="pp-header">&#9889; Power Plays &mdash; Max Return Bets ($100-$200 in)</div>
    </div>`;
    plan.power_plays.forEach((pp, i) => {{
      const raw = +pp.payout || 0;
      const payFmt = raw >= 1000 ? '$' + (raw/1000).toFixed(1) + 'K' : '$' + raw.toFixed(2);
      html += `<div class="play-card" style="border-color:#f59e0b30">
        <div class="pp-badge">Power Play #${{i+1}}</div>
        <div class="play-card-header">
          <div>
            <div class="play-type">${{pp.sport||'BET'}} &bull; ${{pp.book||'Sportsbook'}}</div>
            <div class="play-ticker" style="font-size:15px;line-height:1.2">${{pp.bet_on}}</div>
            <div class="play-sub" style="max-width:220px;white-space:normal">${{pp.game}}</div>
          </div>
          <span class="play-action bet">BET $${{pp.wager}}</span>
        </div>
        <div class="play-rows">
          <div class="play-stat"><div class="play-stat-label">Entry Wager</div>
            <div class="play-stat-value yellow">$${{pp.wager}}</div></div>
          <div class="play-stat"><div class="play-stat-label">Potential Payout</div>
            <div class="play-stat-value" style="color:#fcd34d;font-size:20px;font-weight:800">${{payFmt}}</div></div>
          <div class="play-stat"><div class="play-stat-label">Odds</div>
            <div class="play-stat-value">${{pp.odds_str}}</div></div>
          <div class="play-stat"><div class="play-stat-label">Win %</div>
            <div class="play-stat-value green">${{pp.win_pct}}%</div></div>
          <div class="play-stat"><div class="play-stat-label">Confidence</div>
            <div class="play-stat-value">${{pp.confidence}}</div></div>
        </div>
      </div>`;
    }});
  }}

  if (!html) {{
    html = `<div class="no-plays">No high-confidence plays right now — signals refresh every 30 min. Check back after market open.</div>`;
  }}

  const s = plan.summary || {{}};
  const proj = s.projection_13w || [];
  html += `<div class="play-card" style="border-color:#06b6d430;background:rgba(6,182,212,.05);grid-column:1/-1">
    <div class="play-type" style="color:var(--cyan)">Compound Growth Projection (18% avg weekly gain)</div>
    <div class="play-rows" style="margin-top:10px">
      <div class="play-stat"><div class="play-stat-label">Bankroll</div>
        <div class="play-stat-value">$${{s.bankroll||'--'}}</div></div>
      <div class="play-stat"><div class="play-stat-label">Week 4</div>
        <div class="play-stat-value green">$${{(proj[3]||{{}}).balance||'--'}}</div></div>
      <div class="play-stat"><div class="play-stat-label">Week 8</div>
        <div class="play-stat-value green">$${{(proj[7]||{{}}).balance||'--'}}</div></div>
      <div class="play-stat"><div class="play-stat-label">Week 12</div>
        <div class="play-stat-value green">$${{(proj[11]||{{}}).balance||'--'}}</div></div>
      <div class="play-stat"><div class="play-stat-label">Max Upside Today</div>
        <div class="play-stat-value green">+$${{s.max_upside||'--'}}</div></div>
    </div>
    <div class="play-reason" style="margin-top:8px">
      Pull profits at $1,000+ milestone. Reinvest 70%, pocket 30%. Bi-weekly rebalance.
    </div>
  </div>`;

  grid.innerHTML = html;
}}

renderPlays();
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

PORT = int(os.getenv("PORT", 5050))


def start_background():
    t = threading.Thread(target=background_refresh, daemon=True)
    t.start()


if __name__ == "__main__":
    print("=" * 55)
    print("  EDGE ENGINE DASHBOARD")
    print("  Starting data refresh in background...")
    print(f"  Open browser to: http://localhost:{PORT}")
    print("  First load takes ~90 seconds (fetching data)")
    print("=" * 55)

    start_background()
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
