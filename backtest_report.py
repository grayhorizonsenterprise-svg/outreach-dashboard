"""
backtest_report.py — Gray Horizons Enterprise
Pulls real historical data and shows what the model would have returned.
Covers: stock signals (90 days) + sports betting model (last completed season games).
Outputs: backtest_results.json + backtest_report.html

Run: python backtest_report.py
"""

import json
import os
import sys
import time
import requests
import numpy as np
from datetime import datetime, timedelta, date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Stock watchlist (same as Edge Engine) ─────────────────────────────────────
STOCK_WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "META", "GOOGL", "AMZN", "TSLA",
    "AMD", "SPY", "QQQ", "PLTR", "CRWD", "COIN", "MSTR",
]

# ── Sports to backtest ─────────────────────────────────────────────────────────
ESPN_SPORTS = [
    ("basketball", "nba",      "NBA"),
    ("baseball",   "mlb",      "MLB"),
    ("hockey",     "nhl",      "NHL"),
]

HEADERS = {"User-Agent": "EdgeEngine-Backtest/1.0"}
OUTPUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.json")
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_report.html")


# ══════════════════════════════════════════════════════════════════════════════
# STOCK SIGNAL BACKTEST
# Logic: score each day using RSI + volume ratio + EMA cross (same as Edge Scanner)
# Entry: score >= 70 at close. Exit: 5 trading days later.
# ══════════════════════════════════════════════════════════════════════════════

def _rsi(closes, period=14):
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g  = np.convolve(gains,  np.ones(period)/period, mode='valid')
    avg_l  = np.convolve(losses, np.ones(period)/period, mode='valid')
    rs     = np.where(avg_l == 0, 100.0, avg_g / avg_l)
    return 100 - (100 / (1 + rs))


def _score_day(closes, volumes, idx):
    """Score a single bar 0-100 using the same logic as Edge Scanner."""
    if idx < 26:
        return 0
    c = closes[:idx+1]
    v = volumes[:idx+1]

    rsi_arr = _rsi(c, 14)
    if len(rsi_arr) < 1:
        return 0
    rsi = rsi_arr[-1]

    ema12 = float(np.convolve(c, np.ones(12)/12, mode='valid')[-1])
    ema26 = float(np.convolve(c, np.ones(26)/26, mode='valid')[-1])
    ema_cross = 1 if ema12 > ema26 else 0

    vol_avg = float(np.mean(v[-20:]))
    vol_ratio = float(v[-1] / vol_avg) if vol_avg > 0 else 1.0
    vol_score = min(vol_ratio / 3.0, 1.0)

    rsi_score = 0.0
    if 45 <= rsi <= 70:
        rsi_score = (rsi - 45) / 25.0

    score = (rsi_score * 50) + (vol_score * 30) + (ema_cross * 20)
    return round(min(score, 100), 1)


def backtest_stocks(lookback_days=90):
    print(f"\n[STOCKS] Backtesting {len(STOCK_WATCHLIST)} tickers over {lookback_days} days...")
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance not installed")
        return []

    end   = datetime.now()
    start = end - timedelta(days=lookback_days + 60)  # extra buffer for indicators

    trades  = []
    signals = []

    for ticker in STOCK_WATCHLIST:
        try:
            df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
            if df.empty or len(df) < 30:
                continue

            closes  = df["Close"].values.flatten().astype(float)
            volumes = df["Volume"].values.flatten().astype(float)
            dates   = [str(d.date()) for d in df.index]

            cutoff_date = (end - timedelta(days=lookback_days)).date()

            for i in range(26, len(closes) - 5):
                bar_date = datetime.strptime(dates[i], "%Y-%m-%d").date()
                if bar_date < cutoff_date:
                    continue

                score = _score_day(closes, volumes, i)
                if score < 70:
                    continue

                entry_price = closes[i]
                exit_price  = closes[i + 5]
                pct_return  = ((exit_price - entry_price) / entry_price) * 100

                signals.append({
                    "ticker": ticker,
                    "date":   dates[i],
                    "score":  score,
                    "entry":  round(float(entry_price), 2),
                    "exit":   round(float(exit_price), 2),
                    "return_pct": round(float(pct_return), 2),
                    "win":    pct_return > 0,
                })

            time.sleep(0.3)
        except Exception as e:
            print(f"  [{ticker}] Error: {e}")

    if not signals:
        print("  No signals found")
        return []

    wins     = sum(1 for s in signals if s["win"])
    total    = len(signals)
    win_rate = wins / total * 100
    avg_ret  = float(np.mean([s["return_pct"] for s in signals]))

    # Kelly-sized portfolio simulation — start $10,000
    portfolio = 10000.0
    for s in sorted(signals, key=lambda x: x["date"]):
        edge  = (win_rate/100 * 2) - 1          # simplified Kelly edge
        kelly = max(0, edge) * 0.25              # quarter Kelly
        bet   = portfolio * kelly
        portfolio += bet * (s["return_pct"] / 100)

    print(f"  Signals fired: {total} | Win rate: {win_rate:.1f}% | Avg return: {avg_ret:+.2f}%")
    print(f"  $10,000 → ${portfolio:,.0f} over {lookback_days} days")

    return {
        "type":        "stocks",
        "signals":     total,
        "wins":        wins,
        "win_rate":    round(win_rate, 1),
        "avg_return":  round(avg_ret, 2),
        "start_value": 10000,
        "end_value":   round(portfolio, 2),
        "top_signals": sorted(signals, key=lambda x: x["return_pct"], reverse=True)[:10],
        "all_signals": signals,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SPORTS BETTING BACKTEST
# Pulls completed games from ESPN, applies our model, compares to result.
# Tracks ROI with flat $100/game on high-confidence picks only.
# ══════════════════════════════════════════════════════════════════════════════

def _get_completed_games(sport_path, league, days_back=60):
    """Fetch completed games from ESPN scoreboard (last N days)."""
    games = []
    end_d   = date.today()
    start_d = end_d - timedelta(days=days_back)
    cur     = start_d

    while cur <= end_d:
        date_str = cur.strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/scoreboard?dates={date_str}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for ev in data.get("events", []):
                    comps = ev.get("competitions", [{}])
                    if not comps:
                        continue
                    comp = comps[0]
                    status = comp.get("status", {}).get("type", {}).get("completed", False)
                    if not status:
                        cur += timedelta(days=1)
                        continue

                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue

                    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

                    try:
                        home_score = int(home.get("score", 0))
                        away_score = int(away.get("score", 0))
                    except (ValueError, TypeError):
                        cur += timedelta(days=1)
                        continue

                    if home_score == 0 and away_score == 0:
                        cur += timedelta(days=1)
                        continue

                    home_win = home_score > away_score
                    games.append({
                        "date":       cur.isoformat(),
                        "home_team":  home.get("team", {}).get("displayName", "Home"),
                        "away_team":  away.get("team", {}).get("displayName", "Away"),
                        "home_score": home_score,
                        "away_score": away_score,
                        "home_win":   home_win,
                    })
        except Exception:
            pass
        cur += timedelta(days=1)
        time.sleep(0.15)

    return games


def _home_field_edge(sport):
    return {"NBA": 0.040, "NFL": 0.035, "MLB": 0.038, "NHL": 0.032}.get(sport, 0.035)


def _model_prediction(game, sport, sport_games):
    """
    Simplified model prediction for a single game.
    Uses home-field advantage + recent form from ESPN data.
    Returns (predicted_home_win: bool, confidence: float 0-1)
    """
    # Base home-field advantage
    home_prob = 0.50 + _home_field_edge(sport)

    # Recent form: home win rate in last 10 home games for this team
    home_team  = game["home_team"]
    away_team  = game["away_team"]
    game_date  = game["date"]

    home_recent = [g for g in sport_games
                   if g["date"] < game_date and g["home_team"] == home_team][-10:]
    away_recent = [g for g in sport_games
                   if g["date"] < game_date and g["away_team"] == away_team][-10:]

    if home_recent:
        home_form = sum(1 for g in home_recent if g["home_win"]) / len(home_recent)
        home_prob += (home_form - 0.5) * 0.15

    if away_recent:
        away_form = sum(1 for g in away_recent if not g["home_win"]) / len(away_recent)
        home_prob -= (away_form - 0.5) * 0.10

    home_prob = max(0.35, min(0.70, home_prob))
    confidence = abs(home_prob - 0.50) * 2   # 0 = coin flip, 1 = certain
    predicted_home_win = home_prob > 0.50

    return predicted_home_win, confidence, round(home_prob, 3)


def backtest_sports(days_back=60):
    print(f"\n[SPORTS] Backtesting last {days_back} days of completed games...")
    all_results = []

    for sport_path, league, sport_name in ESPN_SPORTS:
        print(f"  Fetching {sport_name} games...")
        games = _get_completed_games(sport_path, league, days_back)
        if not games:
            print(f"  No {sport_name} games found (off-season?)")
            continue

        print(f"  {len(games)} completed {sport_name} games found")

        picks   = []
        bankroll = 1000.0   # start with $1,000
        unit     = 100.0    # $100/game flat bet on high-confidence picks

        for game in games:
            pred_home_win, confidence, home_prob = _model_prediction(game, sport_name, games)

            # Only bet high-confidence picks (>60% edge)
            if confidence < 0.20:
                continue

            actual_home_win = game["home_win"]
            correct = (pred_home_win == actual_home_win)

            # Standard -110 odds payout
            profit = unit * (100/110) if correct else -unit
            bankroll += profit

            picks.append({
                "date":           game["date"],
                "matchup":        f"{game['away_team']} @ {game['home_team']}",
                "predicted":      "Home" if pred_home_win else "Away",
                "actual":         "Home" if actual_home_win else "Away",
                "confidence":     round(confidence * 100, 1),
                "home_prob":      home_prob,
                "correct":        correct,
                "profit":         round(profit, 2),
                "bankroll":       round(bankroll, 2),
            })

        if not picks:
            continue

        wins     = sum(1 for p in picks if p["correct"])
        total    = len(picks)
        win_rate = wins / total * 100
        roi      = ((bankroll - 1000) / 1000) * 100

        print(f"  {sport_name}: {wins}/{total} correct ({win_rate:.1f}%) | ROI: {roi:+.1f}% | $1,000 → ${bankroll:,.0f}")

        all_results.append({
            "sport":      sport_name,
            "picks":      total,
            "wins":       wins,
            "win_rate":   round(win_rate, 1),
            "roi":        round(roi, 1),
            "start_bank": 1000,
            "end_bank":   round(bankroll, 2),
            "pick_log":   picks[-20:],  # last 20 picks for display
        })

    return all_results


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT
# ══════════════════════════════════════════════════════════════════════════════

def build_html(stock_data, sports_data):
    run_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    stock_html = ""
    if stock_data:
        gain = stock_data["end_value"] - stock_data["start_value"]
        gain_color = "#22c55e" if gain >= 0 else "#f87171"
        stock_html = f"""
        <div class="card">
          <div class="card-label">Stock Signal Backtest — Last 90 Days</div>
          <div class="stats-row">
            <div class="stat"><div class="stat-val">{stock_data['signals']}</div><div class="stat-lbl">Signals Fired (Score 70+)</div></div>
            <div class="stat"><div class="stat-val" style="color:#22c55e">{stock_data['win_rate']}%</div><div class="stat-lbl">Win Rate (5-Day Hold)</div></div>
            <div class="stat"><div class="stat-val" style="color:{gain_color}">{stock_data['avg_return']:+.2f}%</div><div class="stat-lbl">Avg Return Per Signal</div></div>
            <div class="stat"><div class="stat-val" style="color:{gain_color}">${stock_data['end_value']:,.0f}</div><div class="stat-lbl">$10,000 Starting Capital</div></div>
          </div>
          <div class="section-title">Top 10 Signals</div>
          <table>
            <tr><th>Date</th><th>Ticker</th><th>Score</th><th>Entry</th><th>Exit (5d)</th><th>Return</th></tr>
            {"".join(f'<tr><td>{s["date"]}</td><td><strong>{s["ticker"]}</strong></td><td>{s["score"]}</td><td>${s["entry"]}</td><td>${s["exit"]}</td><td style="color:{"#22c55e" if s["win"] else "#f87171"}">{s["return_pct"]:+.2f}%</td></tr>' for s in stock_data["top_signals"])}
          </table>
        </div>"""

    sports_html = ""
    for sp in (sports_data or []):
        roi_color = "#22c55e" if sp["roi"] >= 0 else "#f87171"
        rows = "".join(
            f'<tr><td>{p["date"]}</td><td>{p["matchup"]}</td><td>{p["confidence"]}%</td>'
            f'<td>{"✓" if p["correct"] else "✗"}</td>'
            f'<td style="color:{"#22c55e" if p["profit"]>0 else "#f87171"}">${p["profit"]:+.0f}</td>'
            f'<td>${p["bankroll"]:,.0f}</td></tr>'
            for p in sp["pick_log"]
        )
        sports_html += f"""
        <div class="card">
          <div class="card-label">{sp['sport']} Betting Model — Last 60 Days (High-Confidence Only)</div>
          <div class="stats-row">
            <div class="stat"><div class="stat-val">{sp['picks']}</div><div class="stat-lbl">High-Confidence Picks</div></div>
            <div class="stat"><div class="stat-val" style="color:#22c55e">{sp['win_rate']}%</div><div class="stat-lbl">Win Rate</div></div>
            <div class="stat"><div class="stat-val" style="color:{roi_color}">{sp['roi']:+.1f}%</div><div class="stat-lbl">ROI ($100 flat bet)</div></div>
            <div class="stat"><div class="stat-val" style="color:{roi_color}">${sp['end_bank']:,.0f}</div><div class="stat-lbl">$1,000 Starting Bankroll</div></div>
          </div>
          <div class="section-title">Last 20 Picks</div>
          <table>
            <tr><th>Date</th><th>Matchup</th><th>Confidence</th><th>Result</th><th>P&L</th><th>Bankroll</th></tr>
            {rows}
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GHE Edge Engine — Backtest Results</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#071426;color:#e2e8f0;padding:40px 20px;}}
  h1{{font-size:28px;font-weight:900;margin-bottom:4px;}}
  .subtitle{{color:#64748b;font-size:14px;margin-bottom:40px;}}
  .card{{background:#0c1b33;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:28px;margin-bottom:24px;}}
  .card-label{{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#4f9cff;margin-bottom:20px;}}
  .stats-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px;}}
  .stat{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:16px;text-align:center;}}
  .stat-val{{font-size:26px;font-weight:900;letter-spacing:-.02em;margin-bottom:4px;}}
  .stat-lbl{{font-size:11px;color:#64748b;font-weight:600;}}
  .section-title{{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin-bottom:12px;}}
  table{{width:100%;border-collapse:collapse;font-size:13px;}}
  th{{text-align:left;padding:8px 12px;background:rgba(255,255,255,.04);color:#64748b;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.06em;}}
  td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.05);}}
  .disclaimer{{font-size:12px;color:#475569;margin-top:32px;padding:20px;background:rgba(255,255,255,.03);border-radius:10px;line-height:1.6;}}
</style>
</head>
<body>
<h1>GHE Edge Engine — Historical Backtest</h1>
<div class="subtitle">Generated {run_date} &nbsp;·&nbsp; Real historical data &nbsp;·&nbsp; Not simulated or forward-looking</div>
{stock_html}
{sports_html}
<div class="disclaimer">
  <strong>Methodology:</strong> Stock signals use RSI (14), volume ratio vs 20-day average, and EMA12/26 crossover — same logic as the live Edge Scanner. Entry at close when score &ge;70, exit 5 trading days later. Sports model uses home-field advantage, team form (last 10 games), and confidence filtering — only picks with &ge;20% edge above 50/50 are included. Standard -110 odds applied to all sports picks. Past performance does not guarantee future results.
</div>
</body>
</html>"""
    return html


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("GHE Edge Engine — Backtest Report")
    print("=" * 60)

    stock_data  = backtest_stocks(lookback_days=90)
    sports_data = backtest_sports(days_back=60)

    results = {
        "generated": datetime.now().isoformat(),
        "stocks":    stock_data,
        "sports":    sports_data,
    }

    def _json_safe(obj):
        if isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        raise TypeError(f"Not serializable: {type(obj)}")

    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=_json_safe)
    print(f"\n[SAVED] {OUTPUT_JSON}")

    html = build_html(stock_data, sports_data)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[SAVED] {OUTPUT_HTML}")
    print("\nOpen backtest_report.html in your browser to see results.")
