"""
dashboard.py — Web dashboard for the Edge Engine.
Serves a live investing dashboard at http://localhost:5050

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

from flask import Flask, render_template, jsonify
from config import (
    STOCKS, CRYPTOS, SPORTS, SPACEX_ECOSYSTEM, CATEGORIES,
    ODDS_KEY, QUIVER_KEY, MIN_SIGNAL_SCORE
)
from signals import (
    get_stock_signals, get_crypto_signals,
    get_betting_signals, get_congress_buys, StockSignal,
    get_action_plan, get_scout_picks, get_live_scores, get_smart_parlays
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


def refresh_cache():
    """Full data refresh — runs on startup and every 15 minutes."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing cache...")
    try:
        congress = get_congress_buys()
        all_signals = get_stock_signals()

        # Build per-category rows
        spacex_rows = build_stock_rows(all_signals, congress, CATEGORIES["SpaceX Ecosystem"])
        stock_rows  = build_stock_rows(all_signals, congress)

        # Warnings-only view
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
        bet_sigs    = get_betting_signals()
        crypto_rows = build_crypto_rows(crypto_sigs)
        bet_rows    = build_bet_rows(bet_sigs)
        regime      = market_regime_check()
        action_plan = get_action_plan(all_signals, crypto_sigs, bet_sigs, bankroll=100.0)

        scout_picks = get_scout_picks()
        live_scores = get_live_scores()
        parlays     = get_smart_parlays(bet_sigs)

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
    Lightweight bet-only refresh — every 20 minutes during 7am-10pm.
    Only re-fetches betting signals and scout picks; leaves stocks/crypto untouched.
    Captures line movement between cycles (that's where the edge builds up).
    """
    while True:
        time.sleep(1200)  # 20 minutes
        now = datetime.now()
        if 7 <= now.hour < 22:  # daytime only
            print(f"[{now.strftime('%H:%M:%S')}] Scout refresh (20-min cycle)...")
            try:
                bet_sigs    = get_betting_signals()
                bet_rows    = build_bet_rows(bet_sigs)
                scout_picks = get_scout_picks()
                live_scores = get_live_scores()
                parlays     = get_smart_parlays(bet_sigs)
                with CACHE_LOCK:
                    CACHE["bets"]        = bet_rows
                    CACHE["scout_picks"] = scout_picks
                    CACHE["live_scores"] = live_scores
                    CACHE["parlays"]     = parlays
                    # Update action plan bets portion
                    if CACHE.get("action_plan"):
                        from signals import get_action_plan as _gap
                        # lightweight: reuse cached stock/crypto signals
                        pass
                print(f"[{now.strftime('%H:%M:%S')}] Scout done: {len(bet_rows)} bets | "
                      f"{len(scout_picks)} picks")
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
    return render_template("index.html", nav=NAV_LINKS)

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
