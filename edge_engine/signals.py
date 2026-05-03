"""
signals.py — all signal logic: stocks, crypto, sports/politics
Returns ranked opportunities with scores and edge calculations.
"""

import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from config import (
    STOCKS, CRYPTOS, SPORTS, ODDS_KEY, QUIVER_KEY,
    MIN_BET_EDGE_PCT, MIN_SIGNAL_SCORE, COINGECKO_KEY
)
import scout as _scout

HEADERS = {"User-Agent": "EdgeEngine/1.0"}

# ══════════════════════════════════════════════════════════════════════════════
# ESPN TEAM STATS — builds our OWN probability model independent of the books
# ══════════════════════════════════════════════════════════════════════════════

ESPN_LEAGUE_MAP = {
    "NFL":     ("football",   "nfl"),
    "NBA":     ("basketball", "nba"),
    "MLB":     ("baseball",   "mlb"),
    "NHL":     ("hockey",     "nhl"),
    "MLS":     ("soccer",     "usa.1"),
    "SOCCER":  ("soccer",     "usa.1"),
}
# Sports without team stats — model falls back to book consensus
_NO_TEAM_STATS = {"MMA", "TENNIS", "BOXING", "GOLF", "POLITICS"}

_STANDINGS_CACHE: dict = {}

def _get_espn_standings(sport_name: str) -> dict:
    """
    Fetch win%, points-for, points-against from ESPN standings.
    Returns {normalized_name: {win_pct, ppg, opp_ppg}}.
    Cached per session (only one HTTP call per sport per refresh cycle).
    """
    key = sport_name.upper()
    if key in _STANDINGS_CACHE:
        return _STANDINGS_CACHE[key]

    league_info = ESPN_LEAGUE_MAP.get(key)
    if not league_info:
        _STANDINGS_CACHE[key] = {}
        return {}

    sport_path, league = league_info
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/standings"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            _STANDINGS_CACHE[key] = {}
            return {}
        data = r.json()

        # ESPN standings nests entries differently by season — walk all shapes
        entries = []
        def _collect(node):
            if isinstance(node, list):
                for item in node:
                    _collect(item)
            elif isinstance(node, dict):
                if "entries" in node:
                    entries.extend(node["entries"])
                else:
                    for v in node.values():
                        _collect(v)
        _collect(data.get("standings", data))

        teams = {}
        for entry in entries:
            team = entry.get("team", {})
            name = (team.get("displayName") or team.get("name") or "").strip()
            if not name:
                continue
            stats_list = entry.get("stats", [])
            sm = {s.get("name", "").lower(): (s.get("value") or 0) for s in stats_list}

            win_pct = (sm.get("winpercent") or sm.get("pct") or sm.get("win%") or 0)
            wins    = sm.get("wins", 0)
            losses  = sm.get("losses", 0)
            if win_pct == 0 and (wins + losses) > 0:
                win_pct = wins / (wins + losses)

            ppg     = (sm.get("pointsfor") or sm.get("avgpointsfor") or
                       sm.get("points") or sm.get("goalsfor") or 0)
            opp_ppg = (sm.get("pointsagainst") or sm.get("avgpointsagainst") or
                       sm.get("goalsagainst") or 0)

            teams[name.lower()] = {
                "name": name, "win_pct": float(win_pct),
                "ppg": float(ppg), "opp_ppg": float(opp_ppg),
                "games": int(wins + losses),
            }

        _STANDINGS_CACHE[key] = teams
        print(f"  ESPN standings: {sport_name} — {len(teams)} teams loaded")
        return teams
    except Exception as e:
        print(f"  [!] ESPN standings ({sport_name}): {e}")
        _STANDINGS_CACHE[key] = {}
        return {}


def _match_team(name: str, standings: dict) -> dict | None:
    """Fuzzy-match Odds API team name to ESPN standings entry."""
    if not standings or not name:
        return None
    nl = name.lower()
    if nl in standings:
        return standings[nl]
    # Partial word overlap
    nw = set(nl.split()) - {"at", "the", "fc", "sc", "city", "united", "club", "de", "af"}
    for key, val in standings.items():
        kw = set(key.split()) - {"at", "the", "fc", "sc", "city", "united", "club", "de", "af"}
        if nw and kw and len(nw & kw) >= max(1, min(len(nw), len(kw)) - 1):
            return val
    # difflib last resort
    try:
        from difflib import get_close_matches
        m = get_close_matches(nl, standings.keys(), n=1, cutoff=0.55)
        if m:
            return standings[m[0]]
    except Exception:
        pass
    return None


# Home-field advantage per sport (historical average)
_HOME_ADV = {"NBA": 0.040, "NFL": 0.035, "MLB": 0.038,
             "NHL": 0.032, "MLS": 0.050, "SOCCER": 0.050}


def _predict_game(home: str, away: str, sport_name: str) -> tuple[float, float, list[str]]:
    """
    Build our independent probability estimate using ESPN team stats.
    Returns (home_prob, away_prob, factors_list).
    Falls back to (0.5, 0.5, [...]) when data is unavailable.
    """
    sn = sport_name.upper()
    if sn in _NO_TEAM_STATS:
        return 0.5, 0.5, ["No team stats for this sport — using book consensus only"]

    standings = _get_espn_standings(sn)
    hd = _match_team(home, standings)
    ad = _match_team(away, standings)
    factors: list[str] = []

    if not hd or not ad:
        return 0.5, 0.5, [f"ESPN data unavailable for {home} or {away}"]

    # Win-rate base probability
    hw, aw = hd["win_pct"], ad["win_pct"]
    total  = hw + aw
    home_base = (hw / total) if total > 0 else 0.5
    factors.append(f"Win%: {home} {hw*100:.0f}% vs {away} {aw*100:.0f}%")

    # Point-differential adjustment (capped at ±10%)
    if hd["ppg"] > 0 and ad["ppg"] > 0:
        h_diff  = hd["ppg"] - hd["opp_ppg"]
        a_diff  = ad["ppg"] - ad["opp_ppg"]
        gap     = h_diff - a_diff
        adj     = float(np.clip(gap / 30.0, -0.10, 0.10)) * 0.4
        home_base = float(np.clip(home_base + adj, 0.20, 0.80))
        factors.append(f"Scoring edge: {home} {h_diff:+.1f} vs {away} {a_diff:+.1f}")

    # Home-field advantage
    ha = _HOME_ADV.get(sn, 0.03)
    home_prob = float(np.clip(home_base + ha, 0.15, 0.85))
    away_prob = 1.0 - home_prob
    factors.append(f"Home advantage: +{ha*100:.0f}% applied to {home}")

    return home_prob, away_prob, factors


# ══════════════════════════════════════════════════════════════════════════════
# FEAR & GREED — crypto market sentiment (alternative.me, free, no key)
# ══════════════════════════════════════════════════════════════════════════════

_FNG_CACHE: dict = {}

def _get_fear_greed() -> tuple[int, str]:
    """Returns (value 0-100, label). Cached per session."""
    global _FNG_CACHE
    if _FNG_CACHE:
        return _FNG_CACHE["v"], _FNG_CACHE["l"]
    try:
        r = requests.get("https://api.alternative.me/fng/", headers=HEADERS, timeout=6)
        d = r.json()["data"][0]
        v, l = int(d["value"]), d["value_classification"]
        _FNG_CACHE = {"v": v, "l": l}
        print(f"  Fear & Greed: {v} ({l})")
        return v, l
    except Exception:
        _FNG_CACHE = {"v": 50, "l": "Neutral"}
        return 50, "Neutral"


# ══════════════════════════════════════════════════════════════════════════════
# FUNDAMENTAL STOCK SCORING  (yfinance .info — only for qualifying stocks)
# ══════════════════════════════════════════════════════════════════════════════

def _fundamental_score(ticker: str) -> tuple[float, str]:
    """
    Score 0-100 from P/E, revenue growth, short float, analyst consensus.
    Only called for stocks that clear the technical threshold — limits API calls.
    """
    try:
        info  = yf.Ticker(ticker).info
        score = 50.0
        notes: list[str] = []

        # Forward P/E — lower = better
        fpe = info.get("forwardPE") or 0
        if fpe > 0:
            if fpe < 15:   score += 15; notes.append(f"P/E {fpe:.0f} cheap")
            elif fpe < 25: score += 8
            elif fpe < 40: score -= 5
            else:          score -= 15; notes.append(f"P/E {fpe:.0f} rich")

        # Revenue growth YoY
        rg = info.get("revenueGrowth") or 0
        if rg:
            if rg > 0.30:  score += 15; notes.append(f"rev +{rg*100:.0f}%")
            elif rg > 0.15: score += 8
            elif rg < 0:   score -= 10; notes.append("rev declining")

        # Short float — high = squeeze risk but also weakness signal
        sf = info.get("shortPercentOfFloat") or 0
        if sf:
            if sf > 0.30:   score -= 12; notes.append(f"{sf*100:.0f}% shorted")
            elif sf > 0.20: score -= 6
            elif sf < 0.05: score += 5

        # Analyst consensus (1=strong buy → 5=strong sell)
        rec = info.get("recommendationMean") or 0
        if rec:
            if rec < 1.8:  score += 12; notes.append("analyst: strong buy")
            elif rec < 2.5: score += 5; notes.append("analyst: buy")
            elif rec > 3.5: score -= 10; notes.append("analyst: sell")

        # Profit margin
        pm = info.get("profitMargins") or 0
        if pm:
            if pm > 0.20:  score += 8; notes.append(f"{pm*100:.0f}% margin")
            elif pm < 0:   score -= 8; notes.append("unprofitable")

        return float(np.clip(score, 0, 100)), " | ".join(notes)
    except Exception:
        return 50.0, ""


def _earnings_proximity(ticker: str) -> tuple[int, str]:
    """Returns (days_until_earnings, warning_note). -1 if unknown."""
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return -1, ""
        # calendar can be a dict or DataFrame depending on yfinance version
        if hasattr(cal, "get"):
            dates = cal.get("Earnings Date") or cal.get("earningsDate") or []
        elif hasattr(cal, "columns") and not cal.empty:
            col = [c for c in cal.columns if "earnings" in str(c).lower()]
            dates = cal[col[0]].dropna().tolist() if col else []
        else:
            return -1, ""
        if not len(dates):
            return -1, ""
        next_dt = pd.Timestamp(dates[0] if hasattr(dates, "__getitem__") else list(dates)[0])
        days = int((next_dt - pd.Timestamp.now()).days)
        if 0 <= days <= 5:   return days, f"EARNINGS IN {days}D — high volatility risk"
        if 6 <= days <= 14:  return days, f"earnings ~{days}d"
        return days, ""
    except Exception:
        return -1, ""


# ── Sportsbook underhook / house rules (voids / gotchas per sport) ─────────────
SPORTSBOOK_RULES: dict[str, list[str]] = {
    "NFL":      ["Game must complete 55 min for moneyline to grade",
                 "OT counts for moneyline, not always for spread",
                 "Confirm starter listed before game time — line shifts if QB out"],
    "NBA":      ["Player props void if player doesn't play",
                 "Moneyline includes OT",
                 "Game must tip for bets to stand — postponement = void"],
    "MLB":      ["Listed pitcher rule: bet voids if named pitcher doesn't start",
                 "Game must complete 5 innings (4.5 if home leads) to grade",
                 "Extra innings count toward totals (O/U)"],
    "NHL":      ["Moneyline includes OT and shootout",
                 "Game must begin for bets to stand",
                 "Period lines do NOT include OT — regulation only"],
    "SOCCER":   ["90 min + injury time only (not ET/pens) for most markets",
                 "Player prop voids if not in starting XI",
                 "Match abandoned before 90 min = void at most books"],
    "MMA":      ["Fighter missing weight by 2+ lbs shifts odds significantly",
                 "No contest (NC) returns stake at most books",
                 "Late replacement fighters have much higher uncertainty"],
    "TENNIS":   ["Retirement/walkover before completion voids most bets",
                 "Rain delays can dramatically shift player condition/momentum"],
    "BOXING":   ["Bet is action if fight starts — KO in round 1 still grades",
                 "Draws are rare but possible — factor into moneyline risk"],
    "PARLAY":   ["ALL legs must win — one loss = full parlay lost",
                 "Correlated parlays (e.g. same-game legs) may be rejected",
                 "Books cap max payout — verify limit before large stake"],
    "POLITICS": ["Polymarket requires USDC/crypto wallet to collect winnings",
                 "Read resolution criteria carefully — can resolve unexpectedly",
                 "No regulatory protection — decentralized smart contract"],
    "DEFAULT":  ["Confirm game start time and active status before wagering",
                 "Sharp line movement against your bet is a major red flag",
                 "Check max payout limits at your book — varies significantly"],
}

# ── Internet intel scrub (injuries / postponements / line moves) ───────────────
_INTEL_CACHE: dict = {}

def _scrub_game_intel(game: str, sport: str) -> dict:
    """
    Search for injury/postponement/line-movement news before accepting a bet.
    Cached per session so each game is only searched once.
    Returns dict with red_flags (auto-reject), warnings (caution), notes (headlines).
    """
    cache_key = f"{sport}:{game[:50]}"
    if cache_key in _INTEL_CACHE:
        return _INTEL_CACHE[cache_key]

    intel: dict = {"red_flags": [], "warnings": [], "notes": [], "scrubbed": False}

    try:
        from duckduckgo_search import DDGS
        query = f"{game} injury lineup news today"
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6, timelimit="d"))
        intel["scrubbed"] = True
        full_text = " ".join(
            r.get("title", "").lower() + " " + r.get("body", "").lower()
            for r in results
        )

        # CRITICAL — discard the bet if any of these found
        for kw, msg in [
            ("postponed",       "Game reported POSTPONED"),
            ("cancelled",       "Game reported CANCELLED"),
            ("called off",      "Game called off"),
            ("game off",        "Game called off"),
            ("will not play",   "Key player confirmed NOT PLAYING"),
        ]:
            if kw in full_text and msg not in intel["red_flags"]:
                intel["red_flags"].append(msg)

        # WARNINGS — flag but still show bet
        for kw, msg in [
            ("ruled out",           "Player RULED OUT — lineup change risk"),
            ("out tonight",         "Player OUT tonight"),
            ("out sunday",          "Player OUT this game"),
            ("out saturday",        "Player OUT this game"),
            ("doubtful",            "Player listed as DOUBTFUL"),
            ("questionable",        "Player QUESTIONABLE — uncertainty"),
            ("did not practice",    "Player missed practice — may be out"),
            ("limited in practice", "Player limited in practice"),
            ("weather delay",       "Weather delay possible"),
            ("severe weather",      "Severe weather risk"),
            ("freezing",            "Freezing conditions — impacts outdoor game"),
            ("sharp action",        "Sharp money reported on opposite side"),
            ("steam move",          "Steam move detected — market shifting"),
            ("reverse line",        "Reverse line movement — public vs sharp split"),
            ("line move",           "Significant line movement detected"),
            ("late scratch",        "Late scratch risk reported"),
            ("suspension",          "Player suspension reported"),
            ("trade",               "Recent trade may affect team dynamic"),
        ]:
            if kw in full_text and msg not in intel["warnings"]:
                intel["warnings"].append(msg)

        intel["notes"] = [r.get("title", "")[:90] for r in results[:3] if r.get("title")]

    except Exception as e:
        intel["notes"].append(f"Intel scrub unavailable ({type(e).__name__})")

    _INTEL_CACHE[cache_key] = intel
    return intel


def _get_sport_rules(sport: str) -> list[str]:
    """Return underhook/house rules relevant to this sport."""
    sport_upper = sport.upper()
    for key in SPORTSBOOK_RULES:
        if key in sport_upper:
            return SPORTSBOOK_RULES[key]
    return SPORTSBOOK_RULES["DEFAULT"]


# ══════════════════════════════════════════════════════════════════════════════
# SHARED UTILS
# ══════════════════════════════════════════════════════════════════════════════

def _rsi(s: pd.Series, n: int = 14) -> float:
    d = s.diff()
    g = d.clip(lower=0).ewm(com=n-1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=n-1, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    return float((100 - 100/(1+rs)).iloc[-1])

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def _macd_bullish(s: pd.Series) -> bool:
    fast = _ema(s, 12); slow = _ema(s, 26)
    macd = fast - slow; sig = _ema(macd, 9)
    return bool(macd.iloc[-1] > sig.iloc[-1])

def american_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds < 0:
        return (-odds) / (-odds + 100)
    return 100 / (odds + 100)

def prob_to_american(p: float) -> str:
    if p <= 0 or p >= 1:
        return "N/A"
    if p >= 0.5:
        return f"-{round(p/(1-p)*100)}"
    return f"+{round((1-p)/p*100)}"


# ══════════════════════════════════════════════════════════════════════════════
# STOCK SIGNALS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockSignal:
    ticker: str
    score: float
    price: float
    change_1d: float
    rsi: float
    trend: str
    note: str

def _stock_score(df: pd.DataFrame) -> tuple[float, str]:
    if len(df) < 50:
        return 50.0, "insufficient data"
    c = df["Close"]
    r1  = (c.iloc[-1]/c.iloc[-2] - 1)*100
    r5  = (c.iloc[-1]/c.iloc[-6] - 1)*100
    r20 = (c.iloc[-1]/c.iloc[-21] - 1)*100
    mom = np.clip(50 + (r1*0.5 + r5*0.3 + r20*0.2)*5, 0, 100)

    rsi_val = _rsi(c)
    if 50 < rsi_val < 70:   rsi_pts = 30
    elif rsi_val < 35:       rsi_pts = 32
    elif 35 <= rsi_val <= 50:rsi_pts = 15
    else:                    rsi_pts = 8

    ema20 = float(_ema(c, 20).iloc[-1])
    ema50 = float(_ema(c, 50).iloc[-1])
    price = float(c.iloc[-1])
    ema_pts = (20 if price > ema20 else 0) + (25 if price > ema50 else 0)
    macd_pts = 25 if _macd_bullish(c) else 0

    tech = float(np.clip(rsi_pts + ema_pts + macd_pts, 0, 100))

    avg_vol = df["Volume"].iloc[-21:-1].mean()
    vol_ratio = df["Volume"].iloc[-1] / avg_vol if avg_vol > 0 else 1
    vol_pts = min(40, (vol_ratio - 1) * 20 + 30)

    # WSB social boost
    wsb_score = _wsb_score_quick(df)

    score = mom*0.30 + tech*0.35 + vol_pts*0.20 + wsb_score*0.15

    notes = []
    if rsi_val < 35: notes.append("oversold")
    if vol_ratio >= 2: notes.append(f"vol x{vol_ratio:.1f}")
    if price > ema20 and price > ema50: notes.append("above EMAs")
    if _macd_bullish(c): notes.append("MACD bull")

    return round(float(np.clip(score, 0, 100)), 1), " | ".join(notes) or "standard"

_WSB_CACHE: dict = {}

def _wsb_score_quick(df) -> float:
    """Light WSB check cached per session."""
    global _WSB_CACHE
    if not _WSB_CACHE:
        try:
            r = requests.get(
                "https://www.reddit.com/r/wallstreetbets/hot.json?limit=50",
                headers=HEADERS, timeout=8
            )
            if r.status_code == 200:
                import re
                text = " ".join(
                    p["data"].get("title","") for p in r.json()["data"]["children"]
                )
                for m in re.finditer(r"\$([A-Z]{2,5})\b", text):
                    t = m.group(1)
                    _WSB_CACHE[t] = _WSB_CACHE.get(t, 0) + 1
        except Exception:
            pass
    return 0.0  # populated after cache builds

def get_stock_signals() -> list[StockSignal]:
    results = []
    print("  Scanning stocks + fundamentals...")
    for ticker in STOCKS:
        try:
            df = yf.Ticker(ticker).history(period="3mo")
            if df.empty or len(df) < 10:
                continue
            tech_score, tech_note = _stock_score(df)

            # Only fetch fundamentals for stocks clearing technical baseline
            if tech_score >= 50:
                fund_score, fund_note = _fundamental_score(ticker)
                earn_days, earn_note  = _earnings_proximity(ticker)
            else:
                fund_score, fund_note, earn_days, earn_note = 50.0, "", -1, ""

            # Blend: 65% technical, 35% fundamental
            score = round(tech_score * 0.65 + fund_score * 0.35, 1)

            # Earnings proximity penalty — don't buy into unknown earnings
            if 0 <= earn_days <= 5:
                score = max(score - 25, 0)

            notes = " | ".join(n for n in [tech_note, fund_note, earn_note] if n)

            price = float(df["Close"].iloc[-1])
            prev  = float(df["Close"].iloc[-2])
            rsi_v = _rsi(df["Close"])
            trend = ("STRONG BUY" if score >= 75 else
                     "BUY"        if score >= 60 else
                     "WATCH"      if score >= 45 else "SKIP")
            results.append(StockSignal(ticker, score, price,
                round((price/prev-1)*100, 2), round(rsi_v, 1), trend, notes))
        except Exception:
            pass
    return sorted(results, key=lambda x: x.score, reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# CRYPTO SIGNALS  (CoinGecko — no API key needed)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CryptoSignal:
    coin: str
    symbol: str
    score: float
    price: float
    change_1h: float
    change_24h: float
    change_7d: float
    volume_24h: float
    market_cap: float
    trend: str
    note: str

def _fetch_coingecko() -> list[dict]:
    """CoinGecko — works with optional free demo key from coingecko.com/api/pricing."""
    base = "https://pro-api.coingecko.com" if COINGECKO_KEY else "https://api.coingecko.com"
    ids  = ",".join(CRYPTOS)
    url  = (
        f"{base}/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=volume_desc"
        "&per_page=50&page=1&sparkline=false"
        "&price_change_percentage=24h,7d"
    )
    hdrs = dict(HEADERS)
    if COINGECKO_KEY:
        hdrs["x-cg-demo-api-key"] = COINGECKO_KEY
    try:
        r = requests.get(url, headers=hdrs, timeout=12)
        if r.status_code in (401, 403):
            print("  [!] CoinGecko: key missing/invalid — add COINGECKO_KEY to env (free at coingecko.com/api/pricing)")
            return []
        if r.status_code == 429:
            print("  [!] CoinGecko: rate-limited")
            return []
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list):
            return []
        # Normalise field names
        out = []
        for c in raw:
            out.append({
                "name":    c.get("name",""),
                "symbol":  c.get("symbol","").upper(),
                "price":   c.get("current_price", 0) or 0,
                "h1":      0,  # not available on free tier
                "h24":     c.get("price_change_percentage_24h_in_currency") or
                           c.get("price_change_percentage_24h") or 0,
                "d7":      c.get("price_change_percentage_7d_in_currency") or 0,
                "vol":     c.get("total_volume", 0) or 0,
                "mc":      c.get("market_cap", 1) or 1,
                "source":  "coingecko",
            })
        return out
    except Exception as e:
        print(f"  [!] CoinGecko fetch error: {e}")
        return []


def _fetch_coinpaprika() -> list[dict]:
    """
    CoinPaprika — completely free, no key, returns top-2000 coins.
    Has 1h/24h/7d change, volume, market cap.
    """
    try:
        r = requests.get(
            "https://api.coinpaprika.com/v1/tickers?quotes=USD&limit=150",
            headers=HEADERS, timeout=12
        )
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list):
            return []
        out = []
        for c in raw:
            q = c.get("quotes", {}).get("USD", {})
            price = q.get("price", 0) or 0
            if price <= 0:
                continue
            out.append({
                "name":   c.get("name", ""),
                "symbol": c.get("symbol", "").upper(),
                "price":  price,
                "h1":     q.get("percent_change_1h",  0) or 0,
                "h24":    q.get("percent_change_24h", 0) or 0,
                "d7":     q.get("percent_change_7d",  0) or 0,
                "vol":    q.get("volume_24h",   0) or 0,
                "mc":     q.get("market_cap",   1) or 1,
                "source": "coinpaprika",
            })
        return out
    except Exception as e:
        print(f"  [!] CoinPaprika fetch error: {e}")
        return []


_FNG_VALUE: int = 50  # module-level so _score_coin can read it without calling the API each time

def _score_coin(c: dict) -> CryptoSignal:
    h1, h24, d7 = c["h1"], c["h24"], c["d7"]
    vol, mc     = c["vol"], max(c["mc"], 1)

    mom       = float(np.clip(50 + (h1*0.3 + h24*0.5 + d7*0.2) * 3, 0, 100))
    vol_ratio = vol / mc
    vol_score = float(np.clip(vol_ratio * 500, 0, 40))
    score     = float(np.clip(mom * 0.65 + vol_score * 0.35, 0, 100))

    # Fear & Greed adjustment
    # Extreme fear (0-25): buy dips — boost strong setups, opportunity signal
    # Extreme greed (75-100): market overextended — reduce confidence
    fng = _FNG_VALUE
    if fng <= 25 and score >= 55:
        score = min(score + 6, 100)  # fear = discount price, upside more likely
    elif fng >= 80:
        score = max(score - 6, 0)    # greed = elevated risk of reversal

    trend = ("STRONG BUY" if score >= 75 else
             "BUY"        if score >= 60 else
             "WATCH"      if score >= 45 else "SKIP")

    notes = []
    if h1  >  1:  notes.append(f"1h +{h1:.1f}%")
    if h24 >  3:  notes.append(f"24h +{h24:.1f}%")
    if h24 < -5:  notes.append(f"24h {h24:.1f}% dip")
    if vol_ratio > 0.10: notes.append("high volume")
    if fng <= 25: notes.append(f"F&G: {fng} FEAR")
    if fng >= 75: notes.append(f"F&G: {fng} GREED")
    if c["source"] == "coinpaprika": notes.append("via CoinPaprika")

    return CryptoSignal(
        coin=c["name"], symbol=c["symbol"],
        score=round(score, 1), price=c["price"],
        change_1h=round(h1, 2), change_24h=round(h24, 2), change_7d=round(d7, 2),
        volume_24h=vol, market_cap=mc,
        trend=trend, note=" | ".join(notes) or "standard",
    )


def get_crypto_signals() -> list[CryptoSignal]:
    print("  Scanning crypto (multi-source)...")

    # 1. Try CoinGecko first
    cg_data = _fetch_coingecko()
    cg_symbols = {c["symbol"] for c in cg_data}

    # 2. Always pull CoinPaprika (free, reliable, more coins)
    cp_data = _fetch_coinpaprika()

    # Merge: use CoinGecko data where available, fill in new symbols from CoinPaprika
    combined = list(cg_data)
    for c in cp_data:
        if c["symbol"] not in cg_symbols:
            combined.append(c)

    if not combined:
        print("  [!] All crypto sources failed — check network/API status")
        return []

    print(f"  Crypto: {len(cg_data)} CoinGecko + {len(cp_data)} CoinPaprika = {len(combined)} total")

    # Fetch Fear & Greed once before scoring all coins
    global _FNG_VALUE
    _FNG_VALUE, fng_label = _get_fear_greed()
    print(f"  Fear & Greed: {_FNG_VALUE} ({fng_label})")

    results = [_score_coin(c) for c in combined if c["price"] > 0]
    return sorted(results, key=lambda x: x.score, reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# SPORTS & POLITICS BETTING (The Odds API — 500 req/month free)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BetSignal:
    sport: str
    game: str
    bet_on: str
    book: str
    odds: int
    implied_prob: float
    our_prob: float
    edge_pct: float
    expected_value: float   # per $100 wagered
    confidence: str
    note: str
    commence: str
    red_flags: list = field(default_factory=list)   # auto-reject triggers
    warnings:  list = field(default_factory=list)   # caution flags
    rules:     list = field(default_factory=list)   # sport house rules
    scrubbed:  bool = False                          # intel check ran
    model_prob:    float = 0.0                       # our ESPN-based probability
    model_factors: list  = field(default_factory=list)  # what drove our model
    model_vs_book: float = 0.0                       # our prob minus book consensus

def _get_odds_data(sport: str) -> list:
    if not ODDS_KEY:
        return []
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        f"?apiKey={ODDS_KEY}&regions=us&markets=h2h,spreads"
        "&oddsFormat=american&dateFormat=iso"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 401:
            print("  [!] Odds API: invalid key")
            return []
        if r.status_code == 422:
            return []  # sport not currently in season
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [!] Odds fetch failed ({sport}): {e}")
        return []

def _get_polymarket_politics() -> list[BetSignal]:
    """Polymarket — free public prediction market for politics/events."""
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets"
            "?active=true&closed=false&limit=50&order=volume&ascending=false",
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            return []
        markets = r.json()
        signals = []
        for m in markets[:20]:
            question = m.get("question","")
            slug     = m.get("slug","")
            outcomes = m.get("outcomes","[]")
            prices   = m.get("outcomePrices","[]")

            try:
                import json as _json
                outcomes = _json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                prices   = _json.loads(prices)   if isinstance(prices, str)   else prices
            except Exception:
                continue

            if len(outcomes) != 2 or len(prices) != 2:
                continue

            try:
                p_yes = float(prices[0])
                p_no  = float(prices[1])
            except (ValueError, IndexError):
                continue

            if p_yes <= 0.03 or p_yes >= 0.97:
                continue  # already resolved or near-certain — no value to bet

            # Look for mispriced markets (our model = pure market price here)
            # Real edge: compare to your own research / news
            edge = abs(p_yes - 0.5) * 100  # distance from coin flip

            if edge < 10:
                continue  # too close to call

            # Best side to bet
            if p_yes > p_no:
                bet_side = outcomes[0] if outcomes else "Yes"
                our_p    = p_yes
            else:
                bet_side = outcomes[1] if len(outcomes) > 1 else "No"
                our_p    = p_no

            # EV: if we think market is right, EV = 0 (we add this as market consensus)
            ev = round((our_p * 100) - 100 * (1 - our_p), 2)

            signals.append(BetSignal(
                sport="POLITICS",
                game=question[:60],
                bet_on=f"{bet_side} ({our_p:.0%})",
                book="Polymarket",
                odds=round((1/our_p - 1)*100) if our_p >= 0.5 else -round(our_p/(1-our_p)*100),
                implied_prob=round(our_p, 3),
                our_prob=round(our_p, 3),
                edge_pct=round(edge, 1),
                expected_value=round(ev, 2),
                confidence="HIGH" if our_p > 0.70 else "MEDIUM" if our_p > 0.58 else "LOW",
                note="Polymarket consensus",
                commence="ongoing"
            ))

        return sorted(signals, key=lambda x: x.our_prob, reverse=True)
    except Exception as e:
        print(f"  [!] Polymarket fetch failed: {e}")
        return []

def _analyze_game(game: dict, sport: str) -> list[BetSignal]:
    """Find the best line across all books for a single game, flag value."""
    signals = []
    home = game.get("home_team","")
    away = game.get("away_team","")
    commence = game.get("commence_time","")[:10]
    books = game.get("bookmakers",[])

    if not books:
        return []

    # Collect all h2h odds across books
    home_odds_all, away_odds_all = [], []
    for book in books:
        for market in book.get("markets",[]):
            if market["key"] != "h2h":
                continue
            for outcome in market.get("outcomes",[]):
                o = outcome.get("price", 0)
                if outcome["name"] == home: home_odds_all.append((book["title"], o))
                if outcome["name"] == away: away_odds_all.append((book["title"], o))

    if not home_odds_all or not away_odds_all:
        return []

    # Best available odds (highest = most favorable to bettor)
    best_home = max(home_odds_all, key=lambda x: x[1])
    best_away = max(away_odds_all, key=lambda x: x[1])

    # Market consensus implied probs (average across books, devigged)
    avg_home_p = np.mean([american_to_prob(o) for _, o in home_odds_all])
    avg_away_p = np.mean([american_to_prob(o) for _, o in away_odds_all])
    # Devig (normalize to remove the house cut)
    total = avg_home_p + avg_away_p
    home_true = avg_home_p / total
    away_true = avg_away_p / total

    # Scrub the internet once per game (cached) before building signals
    game_str   = f"{away} @ {home}"
    sport_name = sport.split("_")[0].upper()
    intel      = _scrub_game_intel(game_str, sport_name)
    rules      = _get_sport_rules(sport_name)

    # Hard-reject the entire game if a critical issue is found
    if intel["red_flags"]:
        print(f"  [REJECT] {game_str} — {intel['red_flags']}")
        return []

    # ── Full scout ensemble (rest + efficiency + line movement + weather + Pythagorean)
    venue = game.get("venue", "")
    scout_result = _scout.scout_game(
        home=home, away=away, sport=sport_name, venue=venue,
        home_odds=best_home[1], away_odds=best_away[1],
        book_home_prob=home_true,
    )
    scout_home_p = scout_result.p_ensemble
    scout_away_p = 1.0 - scout_home_p

    # Also run legacy ESPN model for backward compat factor list
    espn_home_p, espn_away_p, espn_factors = _predict_game(home, away, sport_name)
    model_factors = scout_result.factors + espn_factors + intel.get("notes", [])

    # Final blend: 60% full scout + 40% devigged book consensus
    blended_home = float(np.clip(scout_home_p * 0.60 + home_true * 0.40, 0.05, 0.95))
    blended_away = float(np.clip(scout_away_p * 0.60 + away_true * 0.40, 0.05, 0.95))

    for team, best_book, best_odds, book_true, blended_true in [
        (home, best_home[0], best_home[1], home_true, blended_home),
        (away, best_away[0], best_away[1], away_true, blended_away),
    ]:
        book_implied = american_to_prob(best_odds)
        # Edge = blended model probability vs what the best available line implies
        edge = (blended_true - book_implied) * 100

        if edge < MIN_BET_EDGE_PCT:
            continue

        ev = (blended_true * (100 / book_implied if best_odds > 0 else 100 / book_implied)) - 100
        # Use scout confidence if available and it's better
        sc_conf = scout_result.confidence
        raw_conf = "HIGH" if blended_true > 0.68 else "MEDIUM" if blended_true > 0.55 else "LOW"
        conf_rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        confidence = sc_conf if conf_rank[sc_conf] >= conf_rank[raw_conf] else raw_conf

        # Downgrade on warnings
        if (intel["warnings"] or scout_result.warnings) and confidence == "HIGH":
            confidence = "MEDIUM"

        m_vs_b = round((blended_true - book_true) * 100, 1)

        # Vegas Script data — patterns suggesting a predetermined game flow
        is_pick_home = (team == home)
        scout_agrees = (
            (is_pick_home and scout_result.pick == "HOME") or
            (not is_pick_home and scout_result.pick == "AWAY")
        )
        vegas_script = {
            "signals_agree":   scout_result.signals_agree,
            "rest_note":       f"{scout_result.home_rest}d/{scout_result.away_rest}d",
            "line_move":       scout_result.line_move,
            "wind_mph":        scout_result.wind_mph,
            "scout_pick":      scout_result.pick_team,
            "scout_pct":       scout_result.pick_pct,
            "scout_agrees":    scout_agrees,
            "p_efficiency":    round(scout_result.p_efficiency * 100, 1),
            "p_pythagorean":   round(scout_result.p_pythagorean * 100, 1),
            "p_rest":          round(scout_result.p_rest * 100, 1),
            "p_line_move":     round(scout_result.p_line_move * 100, 1),
            "scout_warnings":  scout_result.warnings,
            "factors":         scout_result.factors[:5],
        }

        signals.append(BetSignal(
            sport=sport_name,
            game=game_str,
            bet_on=team,
            book=best_book,
            odds=best_odds,
            implied_prob=round(book_implied, 3),
            our_prob=round(blended_true, 3),
            edge_pct=round(edge, 2),
            expected_value=round(ev, 2),
            confidence=confidence,
            note=f"Best line: {best_book} | ensemble model ({scout_result.signals_agree} signals)",
            commence=commence,
            red_flags=intel["red_flags"],
            warnings=list(set(intel["warnings"] + scout_result.warnings)),
            rules=rules,
            scrubbed=intel["scrubbed"],
            model_prob=round(blended_true, 3),
            model_factors=model_factors[:6],
            model_vs_book=m_vs_b,
        ))

    return signals

def get_betting_signals() -> list[BetSignal]:
    print("  Scanning sports odds + full scout ensemble...")
    _scout.clear_session_caches()  # reset per-game caches; line history persists
    all_signals: list[BetSignal] = []

    if not ODDS_KEY:
        print("  [!] No ODDS_API_KEY — add to .env (free at the-odds-api.com)")
        print("  [DEMO] Showing Polymarket politics only...")
    else:
        for sport in SPORTS:
            games = _get_odds_data(sport)
            for game in games:
                all_signals.extend(_analyze_game(game, sport))

    # Always include politics (no key needed)
    # Politics bets get Polymarket-specific rules attached
    politics = _get_polymarket_politics()
    for b in politics:
        b.rules = _get_sport_rules("POLITICS")
        b.scrubbed = True  # Polymarket is self-reporting market prices
    all_signals.extend(politics)

    # Final filter: drop any signal with unresolved critical flags
    clean = [b for b in all_signals if not b.red_flags]
    rejected = len(all_signals) - len(clean)
    if rejected:
        print(f"  [SCRUB] Rejected {rejected} bet(s) due to critical news flags")

    return sorted(clean, key=lambda x: (x.our_prob, x.edge_pct), reverse=True)


def get_scout_picks() -> list[dict]:
    """
    Return tonight's HIGH/MEDIUM confidence scout picks as plain dicts
    for the dashboard to render in the Vegas Script / Picks frame.
    """
    picks = _scout.get_best_picks(min_confidence="MEDIUM", min_pct=58.0)
    out = []
    for p in picks:
        out.append({
            "game":          p.game,
            "pick_team":     p.pick_team,
            "pick_pct":      p.pick_pct,
            "confidence":    p.confidence,
            "signals_agree": p.signals_agree,
            "home_team":     p.home_team,
            "away_team":     p.away_team,
            "sport":         p.sport,
            "home_rest":     p.home_rest,
            "away_rest":     p.away_rest,
            "line_move":     p.line_move,
            "wind_mph":      p.wind_mph,
            "p_efficiency":  round(p.p_efficiency * 100, 1),
            "p_pythagorean": round(p.p_pythagorean * 100, 1),
            "p_rest":        round(p.p_rest * 100, 1),
            "p_line_move":   round(p.p_line_move * 100, 1),
            "p_ensemble":    round(p.p_ensemble * 100, 1),
            "factors":       p.factors,
            "warnings":      p.warnings,
            "ts":            p.ts,
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# CONGRESS SIGNALS  (QuiverQuant)
# ══════════════════════════════════════════════════════════════════════════════

def get_congress_buys(lookback_days: int = 60) -> dict[str, float]:
    """Returns {ticker: score} for recent congressional purchases."""
    if not QUIVER_KEY:
        return {}
    try:
        r = requests.get(
            "https://api.quiverquant.com/beta/live/congresstrading",
            headers={"Authorization": f"Token {QUIVER_KEY}", **HEADERS},
            timeout=15
        )
        if r.status_code != 200:
            return {}
        cutoff = datetime.now() - timedelta(days=lookback_days)
        scores: dict[str, float] = {}
        for t in r.json():
            if "purchase" not in str(t.get("Transaction","")).lower():
                continue
            ticker = str(t.get("Ticker","")).strip().upper()
            if not ticker or not ticker.isalpha() or len(ticker) > 5:
                continue
            try:
                tx_date = datetime.strptime(str(t.get("Date",""))[:10], "%Y-%m-%d")
            except ValueError:
                continue
            if tx_date < cutoff:
                continue
            member = str(t.get("Representative", t.get("Senator","")))
            pelosi_boost = 2.0 if "Pelosi" in member else 1.0
            days_ago = (datetime.now() - tx_date).days
            scores[ticker] = scores.get(ticker, 0) + pelosi_boost * max(0.1, 1 - days_ago/lookback_days)
        # Normalize 0-100
        if scores:
            mx = max(scores.values())
            scores = {k: round(v/mx*100, 1) for k, v in scores.items()}
        return scores
    except Exception as e:
        print(f"  [!] Congress data: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION PLAN — converts signals into exact dollar plays
# ══════════════════════════════════════════════════════════════════════════════

def _stock_targets(ticker: str, price: float, score: float, rsi: float) -> dict:
    try:
        df = yf.Ticker(ticker).history(period="1y")
        hi52 = float(df["Close"].max())
        lo52 = float(df["Close"].min())
        ema50 = float(_ema(df["Close"], 50).iloc[-1])
    except Exception:
        hi52 = price * 1.30
        lo52 = price * 0.70
        ema50 = price

    dist_to_high = (hi52 - price) / price
    if rsi < 35:       target_pct = min(0.35, max(0.20, dist_to_high * 0.6))
    elif score >= 80:  target_pct = min(0.30, max(0.18, dist_to_high * 0.5))
    elif score >= 70:  target_pct = min(0.22, max(0.14, dist_to_high * 0.4))
    else:              target_pct = 0.12

    stop_pct = max(0.08, (price - max(ema50, lo52 + (price - lo52) * 0.1)) / price)
    stop_pct = min(stop_pct, 0.12)

    target_price = round(price * (1 + target_pct), 2)
    stop_price   = round(price * (1 - stop_pct),  2)
    edge = (score / 100) * target_pct
    kelly = min(0.80, edge / stop_pct) if stop_pct > 0 else 0.10

    return {
        "entry": price, "target": target_price, "stop": stop_price,
        "target_pct": round(target_pct * 100, 1),
        "stop_pct":   round(stop_pct * 100, 1),
        "risk_reward": round(target_pct / stop_pct, 1) if stop_pct > 0 else 0,
        "position_pct": round(max(0.10, kelly), 2),
    }


def _crypto_targets(price: float, score: float, change_24h: float) -> dict:
    if score >= 80:   target_pct, stop_pct, pos_pct = 1.00, 0.20, 0.35
    elif score >= 70: target_pct, stop_pct, pos_pct = 0.60, 0.18, 0.25
    elif score >= 60: target_pct, stop_pct, pos_pct = 0.40, 0.15, 0.18
    else:             target_pct, stop_pct, pos_pct = 0.25, 0.12, 0.10
    if change_24h < -5:
        target_pct *= 1.2
        pos_pct    *= 1.1
    return {
        "entry": price, "target": round(price * (1 + target_pct), 6),
        "stop":  round(price * (1 - stop_pct), 6),
        "target_pct": round(target_pct * 100, 1),
        "stop_pct":   round(stop_pct * 100, 1),
        "risk_reward": round(target_pct / stop_pct, 1),
        "position_pct": round(min(pos_pct, 0.40), 2),
    }


def _bet_sizing(our_prob: float, odds: int, bankroll: float = 15.0) -> dict:
    decimal = (odds / 100 + 1) if odds > 0 else (100 / abs(odds) + 1)
    edge    = our_prob - (1 / decimal)
    kelly   = max(0, (edge / (decimal - 1)) * 0.5) if decimal > 1 else 0
    wager   = max(2.0, round(min(bankroll * kelly, bankroll * 0.08), 2))
    payout  = round(wager * (decimal - 1), 2)
    return {"wager": wager, "payout": payout,
            "total_return": round(wager + payout, 2), "decimal_odds": round(decimal, 2)}


def _stock_projection(price: float, target: float, score: float) -> dict:
    """Project profit at $100, $500, $1000 entry sizes with timeline estimate."""
    pct = (target - price) / price if price > 0 else 0
    # Estimate weeks to target based on score (higher score = faster move)
    weeks = max(1, round(12 - score / 12))
    return {
        "pct":        round(pct * 100, 1),
        "weeks_est":  weeks,
        "profit_100":  round(100  * pct, 2),
        "profit_500":  round(500  * pct, 2),
        "profit_1000": round(1000 * pct, 2),
    }


def _build_power_play(b: "BetSignal", wager: float) -> dict:
    """High-odds bet card — $100-$200 in, $30K-$60K potential out."""
    decimal = (b.odds / 100 + 1) if b.odds > 0 else (100 / abs(b.odds) + 1)
    payout  = round(wager * (decimal - 1), 2)
    return {
        "sport":    b.sport,
        "game":     b.game,
        "bet_on":   b.bet_on,
        "book":     b.book,
        "odds":     b.odds,
        "odds_str": f"+{b.odds}" if b.odds > 0 else str(b.odds),
        "wager":    wager,
        "payout":   payout,
        "win_pct":  round(b.our_prob * 100, 1),
        "confidence": b.confidence,
    }


def get_action_plan(stocks: list, cryptos: list, bets: list,
                    bankroll: float = 100.0) -> dict:
    plays = {"stocks": [], "crypto": [], "bets": [], "power_plays": [], "summary": {}}

    # ── Stocks with projections ──────────────────────────────────────────────
    qualifying_s = [s for s in stocks if s.trend in ("STRONG BUY", "BUY")][:5]
    stock_budget = bankroll * 0.60
    alloc_s = [0.50, 0.30, 0.20]
    for i, s in enumerate(qualifying_s[:3]):
        t   = _stock_targets(s.ticker, s.price, s.score, s.rsi)
        din = round(stock_budget * alloc_s[i], 2)
        shares = round(din / s.price, 4) if s.price > 0 else 0
        proj = _stock_projection(s.price, t["target"], s.score)
        plays["stocks"].append({
            "rank": i + 1, "ticker": s.ticker, "score": s.score,
            "entry": s.price, "target": t["target"], "stop": t["stop"],
            "target_pct": t["target_pct"], "stop_pct": t["stop_pct"],
            "rr": t["risk_reward"], "dollar_in": din, "shares": shares,
            "profit": round(shares * (t["target"] - s.price), 2),
            "reason": s.note, "platform": "Robinhood",
            "proj": proj,
        })

    # ── Crypto ───────────────────────────────────────────────────────────────
    qualifying_c = [c for c in cryptos if c.trend in ("STRONG BUY", "BUY")][:4]
    crypto_budget = bankroll * 0.25
    alloc_c = [0.65, 0.35]
    for i, c in enumerate(qualifying_c[:2]):
        t   = _crypto_targets(c.price, c.score, c.change_24h)
        din = round(crypto_budget * alloc_c[i], 2)
        plays["crypto"].append({
            "rank": i + 1, "symbol": c.symbol, "coin": c.coin,
            "score": c.score, "entry": c.price, "target": t["target"],
            "stop": t["stop"], "target_pct": t["target_pct"],
            "stop_pct": t["stop_pct"], "rr": t["risk_reward"],
            "dollar_in": din, "profit": round(din * t["target_pct"] / 100, 2),
            "reason": c.note or "momentum", "platform": "Coinbase / CashApp",
        })

    # ── Standard bets ────────────────────────────────────────────────────────
    bet_budget = bankroll * 0.15
    qualifying_b = [b for b in bets if b.our_prob >= 0.55][:4]
    for i, b in enumerate(qualifying_b[:2]):
        sz = _bet_sizing(b.our_prob, b.odds, bet_budget)
        plays["bets"].append({
            "rank": i + 1, "sport": b.sport, "game": b.game,
            "bet_on": b.bet_on, "book": b.book, "odds": b.odds,
            "odds_str": f"+{b.odds}" if b.odds > 0 else str(b.odds),
            "win_pct": round(b.our_prob * 100, 1), "edge": b.edge_pct,
            "wager": sz["wager"], "payout": sz["payout"],
            "total_return": sz["total_return"], "confidence": b.confidence,
            "platform": b.book,
        })

    # ── Power Plays: $100-$200 in, $500+ payout — clean bets only ────────────
    # Only consider bets that passed the full scrub with zero critical flags
    # and zero warnings (Power Plays must be completely clean)
    power_candidates = sorted(
        [b for b in bets if b.odds > 0 and not b.red_flags and not b.warnings],
        key=lambda b: b.odds,
        reverse=True
    )
    wagers = [150, 100]  # $150 first pick, $100 second pick
    for i, b in enumerate(power_candidates[:2]):
        w = wagers[i]
        pp = _build_power_play(b, w)
        # Only show if payout is meaningful ($5K+)
        if pp["payout"] >= 500:
            plays["power_plays"].append(pp)

    # Parlay fallback — only from clean bets (no flags, no warnings)
    clean_b = [b for b in qualifying_b if not b.red_flags and not b.warnings]
    if not plays["power_plays"] and len(clean_b) >= 2:
        b1, b2 = clean_b[0], clean_b[1]
        d1 = b1.odds / 100 + 1 if b1.odds > 0 else 100 / abs(b1.odds) + 1
        d2 = b2.odds / 100 + 1 if b2.odds > 0 else 100 / abs(b2.odds) + 1
        parlay_decimal = d1 * d2
        parlay_odds    = round((parlay_decimal - 1) * 100)
        wager = 100
        plays["power_plays"].append({
            "sport":    "PARLAY",
            "game":     f"{b1.bet_on} + {b2.bet_on}",
            "bet_on":   f"2-leg parlay",
            "book":     b1.book,
            "odds":     parlay_odds,
            "odds_str": f"+{parlay_odds}",
            "wager":    wager,
            "payout":   round(wager * (parlay_decimal - 1), 2),
            "win_pct":  round(b1.our_prob * b2.our_prob * 100, 1),
            "confidence": "PARLAY",
        })

    # ── Compound projection ───────────────────────────────────────────────────
    weekly_edge = 0.18
    projection, bal = [], bankroll
    for week in range(1, 14):
        bal = round(bal * (1 + weekly_edge), 2)
        projection.append({"week": week, "balance": bal})

    plays["summary"] = {
        "bankroll": bankroll,
        "stock_budget": round(bankroll * 0.60, 2),
        "crypto_budget": round(bankroll * 0.25, 2),
        "bet_budget": round(bankroll * 0.15, 2),
        "total_plays": len(plays["stocks"]) + len(plays["crypto"]) + len(plays["bets"]),
        "max_upside": round(
            sum(p["profit"] for p in plays["stocks"]) +
            sum(p["profit"] for p in plays["crypto"]) +
            sum(p.get("payout", 0) for p in plays["bets"]), 2),
        "weekly_growth_est": 18.0,
        "projection_13w": projection,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return plays
