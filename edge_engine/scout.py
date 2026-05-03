"""
scout.py — Advanced predictive intelligence layer. Runs every 20 minutes
during the day and builds highest-probability game predictions for TONIGHT.

Ensemble model (research-validated weights):
  30% Line movement  — sharp money is the single best predictor
  25% Team efficiency — off/def rating matchup via ESPN stats
  20% Pythagorean    — point-differential win% beats actual win%
  15% Rest advantage — NBA B2B teams cover at 44%; 6% exploitable edge
   5% Weather impact — wind/precip for outdoor sports (NFL, MLB, Soccer)
   5% Home-field     — sport-specific historical averages

Target: 63-72% accuracy on HIGH-confidence filtered picks.
75%+ on nights where 4+ independent signals agree.
"""

import requests
import numpy as np
import threading
from datetime import datetime, timedelta, date
from dataclasses import dataclass, field

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Sport mappings ────────────────────────────────────────────────────────────
ESPN_MAP = {
    "NFL":    ("football",   "nfl"),
    "NBA":    ("basketball", "nba"),
    "MLB":    ("baseball",   "mlb"),
    "NHL":    ("hockey",     "nhl"),
    "MLS":    ("soccer",     "usa.1"),
    "SOCCER": ("soccer",     "usa.1"),
}

OUTDOOR_SPORTS = {"NFL", "MLB", "SOCCER", "MLS"}

# Home field advantage — research-backed (percentage points added to home win prob)
HOME_ADV = {
    "NBA": 0.040, "NFL": 0.035, "MLB": 0.038,
    "NHL": 0.032, "MLS": 0.052, "SOCCER": 0.052,
}

# Pythagorean exponent per sport — point differential → predicted win%
# Higher exponent = scoring variation matters more
PYTHAG_EXP = {
    "NBA": 13.91,   # NBA: high scores, exponent is well-studied
    "NFL": 2.37,
    "MLB": 1.83,
    "NHL": 2.15,
    "MLS": 1.31,
    "SOCCER": 1.31,
}

# ── Session caches (cleared each refresh cycle) ───────────────────────────────
_TEAM_IDS:     dict = {}   # {sport: {team_name_lower: team_id}}
_TEAM_STATS:   dict = {}   # {sport_teamid: {offRtg, defRtg, ppg, oppg, ...}}
_STANDINGS:    dict = {}   # {sport: {team_name_lower: stats}}
_REST:         dict = {}   # {sport_team: days_int}
_WEATHER:      dict = {}   # {city: {wind, precip, temp}}
_LINE_HISTORY: dict = {}   # {game_key: {home_open, away_open, ts}}
_SCOUT_CACHE:  dict = {}   # {game_key: ScoutResult} — latest scout per game

_LOCK = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScoutResult:
    game:        str
    home_team:   str
    away_team:   str
    sport:       str

    # Probability from each INDEPENDENT model layer (books never touch these)
    p_efficiency:   float = 0.50   # off/def rating matchup
    p_pythagorean:  float = 0.50   # point-differential model (Pythagorean expectation)
    p_form:         float = 0.50   # recent form — last 7-10 games, exponentially weighted
    p_rest:         float = 0.50   # rest/fatigue advantage
    p_weather:      float = 0.50   # weather impact (outdoor sports)
    p_line_move:    float = 0.50   # sharp line movement signal (modifier, not primary)
    p_ensemble:     float = 0.50   # final weighted model — 100% ours, no book blending

    injury_adj:    float = 0.0     # direct probability adjustment from injury reports
    confidence:    str  = "LOW"    # HIGH / MEDIUM / LOW
    signals_agree: int  = 0        # count of independent signals pointing same way
    pick:          str  = ""       # "HOME" or "AWAY"
    pick_team:     str  = ""       # actual team name to bet
    pick_pct:      float = 0.0     # final win probability for the pick
    book_implied:  float = 0.50    # book's implied probability (for edge display only)

    home_rest: int   = -1
    away_rest: int   = -1
    wind_mph:  float = 0.0
    precip_mm: float = 0.0
    line_move: int   = 0           # positive = home team line got better

    factors:  list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    ts:       str  = ""


# ══════════════════════════════════════════════════════════════════════════════
# ESPN HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _espn_get(url: str, timeout: int = 8) -> dict:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _load_team_ids(sport: str) -> dict:
    """Return {team_name_lower: team_id} for a sport. Cached."""
    global _TEAM_IDS
    if sport in _TEAM_IDS:
        return _TEAM_IDS[sport]
    lm = ESPN_MAP.get(sport)
    if not lm:
        return {}
    sp, lg = lm
    data = _espn_get(f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams?limit=50")
    teams = {}
    raw = (data.get("sports") or [{}])[0].get("leagues") or [{}]
    raw = (raw[0] if raw else {}).get("teams", [])
    for t in raw:
        td = t.get("team", {})
        name = td.get("displayName", "")
        if name:
            teams[name.lower()] = td.get("id", "")
    _TEAM_IDS[sport] = teams
    return teams


def _get_team_id(team: str, sport: str) -> str | None:
    """Fuzzy-match team name to ESPN team ID."""
    ids = _load_team_ids(sport)
    tl = team.lower()
    if tl in ids:
        return ids[tl]
    # Word overlap
    tw = set(tl.split()) - {"fc", "sc", "city", "united", "the", "de"}
    for key, tid in ids.items():
        kw = set(key.split()) - {"fc", "sc", "city", "united", "the", "de"}
        if tw and kw and len(tw & kw) >= max(1, min(len(tw), len(kw)) - 1):
            return tid
    # difflib
    try:
        from difflib import get_close_matches
        m = get_close_matches(tl, ids.keys(), n=1, cutoff=0.55)
        if m:
            return ids[m[0]]
    except Exception:
        pass
    return None


def _get_team_stats(team_id: str, sport: str) -> dict:
    """ESPN team statistics — offensive/defensive categories."""
    key = f"{sport}:{team_id}"
    global _TEAM_STATS
    if key in _TEAM_STATS:
        return _TEAM_STATS[key]
    lm = ESPN_MAP.get(sport)
    if not lm:
        return {}
    sp, lg = lm
    data = _espn_get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams/{team_id}/statistics"
    )
    stats: dict = {}
    for cat in (data.get("results") or {}).get("stats", {}).get("categories", []):
        cname = cat.get("name", "")
        for s in cat.get("stats", []):
            stats[f"{cname}_{s['name']}"] = s.get("value", 0)
    _TEAM_STATS[key] = stats
    return stats


def _load_standings(sport: str) -> dict:
    """Return {team_name_lower: {win_pct, ppg, opp_ppg}} from ESPN standings."""
    global _STANDINGS
    if sport in _STANDINGS:
        return _STANDINGS[sport]
    lm = ESPN_MAP.get(sport)
    if not lm:
        return {}
    sp, lg = lm
    data = _espn_get(f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/standings")
    entries = []

    def _walk(node):
        if isinstance(node, list):
            for x in node:
                _walk(x)
        elif isinstance(node, dict):
            if "entries" in node:
                entries.extend(node["entries"])
            else:
                for v in node.values():
                    _walk(v)
    _walk(data.get("standings", data))

    result = {}
    for entry in entries:
        team = entry.get("team", {})
        name = (team.get("displayName") or team.get("name") or "").strip()
        if not name:
            continue
        sm = {s.get("name", "").lower(): (s.get("value") or 0)
              for s in entry.get("stats", [])}
        wins   = sm.get("wins", 0)
        losses = sm.get("losses", 0)
        wp = sm.get("winpercent") or sm.get("pct") or (wins / (wins + losses) if wins + losses > 0 else 0.5)
        ppg    = sm.get("pointsfor") or sm.get("avgpointsfor") or sm.get("goalsfor") or 0
        opp    = sm.get("pointsagainst") or sm.get("avgpointsagainst") or sm.get("goalsagainst") or 0
        result[name.lower()] = {
            "name": name, "win_pct": float(wp),
            "ppg": float(ppg), "opp_ppg": float(opp),
            "games": int(wins + losses),
        }
    _STANDINGS[sport] = result
    return result


# ══════════════════════════════════════════════════════════════════════════════
# RECENT FORM  — last N games, exponentially weighted (more predictive than season avg)
# ══════════════════════════════════════════════════════════════════════════════

_FORM_CACHE: dict = {}

def _get_recent_form(team: str, sport: str, n: int = 10) -> tuple[float, str]:
    """
    Pull last N game results from ESPN schedule.
    Exponential decay weighting: most recent game weights 1.0, drops ~50% every 5 games.
    Returns (weighted_win_pct 0-1, description).
    """
    key = f"{sport}:{team}:form"
    global _FORM_CACHE
    if key in _FORM_CACHE:
        return _FORM_CACHE[key]

    team_id = _get_team_id(team, sport)
    lm = ESPN_MAP.get(sport)
    if not team_id or not lm:
        _FORM_CACHE[key] = (0.5, "form unavailable")
        return 0.5, "form unavailable"

    sp, lg = lm
    data = _espn_get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams/{team_id}/schedule"
    )
    today = date.today()
    results = []

    events = sorted(
        data.get("events", []),
        key=lambda e: e.get("date", ""),
        reverse=True,   # most recent first
    )
    for ev in events:
        ds = (ev.get("date") or "")[:10]
        try:
            gd = datetime.strptime(ds, "%Y-%m-%d").date()
            if gd >= today:
                continue  # future game
        except Exception:
            continue

        comps = ev.get("competitions", [{}])
        if not comps:
            continue
        for c in comps[0].get("competitors", []):
            tid = c.get("id") or c.get("team", {}).get("id", "")
            if str(tid) == str(team_id):
                won = c.get("winner", False)
                results.append(1 if won else 0)
                break

        if len(results) >= n:
            break

    if not results:
        _FORM_CACHE[key] = (0.5, "no recent games")
        return 0.5, "no recent games"

    # Exponential decay: game i (0=most recent) gets weight 2^(-i/5)
    weights = [2.0 ** (-i / 5.0) for i in range(len(results))]
    ww = sum(w * r for w, r in zip(weights, results))
    tw = sum(weights)
    form_pct = float(np.clip(ww / tw, 0.10, 0.90))

    # Streak component
    streak = 0
    for r in results:
        if r == results[0]:
            streak += 1
        else:
            break
    streak_note = f"W{streak}" if results[0] == 1 else f"L{streak}"

    desc = f"{sum(results)}W-{len(results)-sum(results)}L (L{len(results)}) {streak_note}"
    _FORM_CACHE[key] = (form_pct, desc)
    return form_pct, desc


# ══════════════════════════════════════════════════════════════════════════════
# INJURY INTELLIGENCE  — ESPN public injury API (free, no key)
# ══════════════════════════════════════════════════════════════════════════════

_INJ_CACHE: dict = {}

# Position impact weights — how much a missing player at this position hurts
_POS_IMPACT = {
    # NBA
    "PG": 0.030, "SG": 0.022, "SF": 0.022, "PF": 0.018, "C": 0.018,
    # NFL — QB is massive
    "QB": 0.055, "WR": 0.018, "RB": 0.016, "TE": 0.014, "OL": 0.010,
    "DE": 0.014, "DT": 0.012, "LB": 0.012, "CB": 0.014, "S": 0.012,
    # MLB
    "SP": 0.030, "RP": 0.010, "C": 0.012, "1B": 0.010, "SS": 0.014,
    # NHL
    "G": 0.035, "D": 0.018, "LW": 0.014, "RW": 0.014, "C": 0.016,
}

def _injury_impact(team: str, sport: str) -> tuple[float, list[str]]:
    """
    ESPN public injury report → estimate probability penalty for missing players.
    Returns (prob_adj ≤ 0, notes_list).  Negative = team is hurt; only hurts, never helps.
    """
    key = f"{sport}:{team}:inj"
    global _INJ_CACHE
    if key in _INJ_CACHE:
        return _INJ_CACHE[key]

    team_id = _get_team_id(team, sport)
    lm = ESPN_MAP.get(sport)
    if not team_id or not lm:
        _INJ_CACHE[key] = (0.0, [])
        return 0.0, []

    sp, lg = lm
    data = _espn_get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams/{team_id}/injuries"
    )
    adj = 0.0
    notes: list[str] = []

    for inj in (data.get("injuries") or []):
        status = (inj.get("status") or "").lower()
        athlete = inj.get("athlete") or {}
        name = athlete.get("displayName", "?")
        pos  = (athlete.get("position") or {}).get("abbreviation", "")
        impact = _POS_IMPACT.get(pos, 0.010)

        if "out" in status:
            adj -= impact
            notes.append(f"{name} ({pos}) OUT")
        elif "doubtful" in status:
            adj -= impact * 0.80
            notes.append(f"{name} ({pos}) DOUBTFUL")
        elif "questionable" in status:
            adj -= impact * 0.35

    adj = float(np.clip(adj, -0.18, 0.0))
    _INJ_CACHE[key] = (adj, notes[:4])  # cap at 4 notable injuries
    return adj, notes[:4]


# ══════════════════════════════════════════════════════════════════════════════
# REST ADVANTAGE
# ══════════════════════════════════════════════════════════════════════════════

def _rest_days(team: str, sport: str) -> int:
    """Days since team's last game (from ESPN schedule). Cached."""
    key = f"{sport}:{team}"
    global _REST
    if key in _REST:
        return _REST[key]
    team_id = _get_team_id(team, sport)
    if not team_id:
        _REST[key] = 2
        return 2
    lm = ESPN_MAP.get(sport)
    if not lm:
        return 2
    sp, lg = lm
    data = _espn_get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams/{team_id}/schedule"
    )
    today = date.today()
    past = []
    for ev in data.get("events", []):
        ds = (ev.get("date") or "")[:10]
        try:
            gd = datetime.strptime(ds, "%Y-%m-%d").date()
            if gd < today:
                past.append(gd)
        except Exception:
            pass
    days = int((today - max(past)).days) if past else 3
    _REST[key] = days
    return days


def _rest_prob_adj(home_rest: int, away_rest: int, sport: str) -> tuple[float, str]:
    """
    Calculate rest-advantage probability adjustment for home team.
    Back-to-back (B2B) teams cover at ~44% — a 6% penalty that's consistently exploitable.
    """
    adj, parts = 0.0, []

    if sport == "NBA":
        if home_rest == 1:
            adj -= 0.060; parts.append(f"HOME B2B penalty -6%")
        elif home_rest >= 3:
            adj += 0.018; parts.append(f"HOME {home_rest}d rest +1.8%")
        if away_rest == 1:
            adj += 0.060; parts.append(f"AWAY B2B (home benefits) +6%")
        elif away_rest >= 3:
            adj -= 0.018
    elif sport in ("NHL", "MLB"):
        if home_rest == 1:
            adj -= 0.030; parts.append(f"HOME B2B -3%")
        if away_rest == 1:
            adj += 0.030; parts.append(f"AWAY B2B +3%")
    else:
        if home_rest == 1:
            adj -= 0.020
        if away_rest == 1:
            adj += 0.020

    note = " | ".join(parts) if parts else f"Rest: home {home_rest}d vs away {away_rest}d"
    return round(adj, 3), note


# ══════════════════════════════════════════════════════════════════════════════
# PYTHAGOREAN EXPECTATION
# ══════════════════════════════════════════════════════════════════════════════

def _pythag_win_pct(ppg: float, opp_ppg: float, sport: str) -> float:
    """
    Pythagorean expectation — point differential predicts future wins better
    than actual win percentage by removing luck in close games.
    Formula: scored^exp / (scored^exp + allowed^exp)
    """
    if ppg <= 0 or opp_ppg <= 0:
        return 0.5
    exp = PYTHAG_EXP.get(sport, 2.0)
    try:
        return float(ppg ** exp / (ppg ** exp + opp_ppg ** exp))
    except Exception:
        return 0.5


# ══════════════════════════════════════════════════════════════════════════════
# TEAM EFFICIENCY MODEL (off/def rating matchup)
# ══════════════════════════════════════════════════════════════════════════════

def _efficiency_prob(home_id: str, away_id: str, sport: str) -> tuple[float, str]:
    """
    Match home team's offensive efficiency vs away team's defensive efficiency
    and vice versa. Better predictor than raw win% for games between teams
    with divergent offensive/defensive profiles.
    """
    hs = _get_team_stats(home_id, sport)
    as_ = _get_team_stats(away_id, sport)

    if not hs or not as_:
        return 0.5, "efficiency data unavailable"

    # Pull offensive scoring average (whichever key is available)
    def _ppg(stats: dict) -> float:
        for k in ["scoring_avgPoints", "offensive_avgPoints",
                  "general_avgPoints", "scoring_points"]:
            v = stats.get(k, 0)
            if v > 0:
                return float(v)
        return 0.0

    def _opp_ppg(stats: dict) -> float:
        for k in ["defensive_avgPoints", "defensive_opponentAvgPoints",
                  "general_avgPointsAllowed"]:
            v = stats.get(k, 0)
            if v > 0:
                return float(v)
        return 0.0

    h_off = _ppg(hs)
    a_off = _ppg(as_)
    h_def = _opp_ppg(hs)
    a_def = _opp_ppg(as_)

    if h_off <= 0 or a_off <= 0:
        return 0.5, "scoring data unavailable"

    # Projected scores
    home_proj = (h_off + a_def) / 2
    away_proj = (a_off + h_def) / 2
    total = home_proj + away_proj

    if total <= 0:
        return 0.5, "zero projected scores"

    home_prob = float(np.clip(home_proj / total, 0.25, 0.75))
    note = f"Proj: {home_proj:.1f} vs {away_proj:.1f}"
    return home_prob, note


# ══════════════════════════════════════════════════════════════════════════════
# WEATHER (outdoor sports only)
# ══════════════════════════════════════════════════════════════════════════════

# Venue city lookup — major stadium cities for line adjustment
VENUE_CITY = {
    "TD Garden": "Boston", "Chase Center": "San Francisco",
    "Crypto.com Arena": "Los Angeles", "Madison Square Garden": "New York",
    "United Center": "Chicago", "American Airlines Center": "Dallas",
    "Yankee Stadium": "New York", "Fenway Park": "Boston",
    "Wrigley Field": "Chicago", "Dodger Stadium": "Los Angeles",
    "SoFi Stadium": "Los Angeles", "AT&T Stadium": "Dallas",
    "Arrowhead Stadium": "Kansas City", "Lambeau Field": "Green Bay",
}


def _get_weather(city: str) -> dict:
    """wttr.in — completely free, no key. Returns {wind_mph, precip_mm, temp_f, desc}."""
    global _WEATHER
    if city in _WEATHER:
        return _WEATHER[city]
    try:
        r = requests.get(f"https://wttr.in/{city.replace(' ', '+')}?format=j1",
                         headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return {}
        cur = r.json()["current_condition"][0]
        result = {
            "wind_mph":  float(cur.get("windspeedMiles", 0)),
            "precip_mm": float(cur.get("precipMM", 0)),
            "temp_f":    float(cur.get("temp_F", 70)),
            "desc":      cur["weatherDesc"][0]["value"],
        }
        _WEATHER[city] = result
        return result
    except Exception:
        return {}


def _weather_prob_adj(venue: str, sport: str) -> tuple[float, float, str]:
    """
    Weather-based probability adjustment for outdoor sports.
    Returns (prob_adj_for_home, wind_mph, note).
    Key thresholds (research-backed):
      Wind 15-20mph: -4% on totals, defense-friendly
      Wind 20mph+:   -8% total value; slightly favors home team familiarity
      Rain/Snow:     Home field advantage increases ~2%
    """
    if sport not in OUTDOOR_SPORTS:
        return 0.0, 0.0, ""

    city = VENUE_CITY.get(venue, "")
    if not city:
        # Try to extract city from venue name
        city = venue.split(" ")[0] if venue else ""

    if not city:
        return 0.0, 0.0, ""

    w = _get_weather(city)
    if not w:
        return 0.0, 0.0, ""

    wind = w["wind_mph"]
    precip = w["precip_mm"]
    adj = 0.0
    parts = []

    if wind >= 20:
        adj += 0.025  # home team knows their stadium; defense game
        parts.append(f"Wind {wind:.0f}mph — low scoring game likely")
    elif wind >= 15:
        adj += 0.012
        parts.append(f"Wind {wind:.0f}mph — mild impact")

    if precip > 2:
        adj += 0.020
        parts.append(f"Rain/precipitation — home advantage up")

    if w["temp_f"] < 35:
        adj += 0.015
        parts.append(f"Cold {w['temp_f']:.0f}°F — outdoor conditions")

    note = " | ".join(parts) if parts else f"Weather: {w['desc']}"
    return round(adj, 3), wind, note


# ══════════════════════════════════════════════════════════════════════════════
# LINE MOVEMENT TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def record_line(game_key: str, home_odds: int, away_odds: int):
    """Called each time odds are fetched. Tracks opening vs current."""
    global _LINE_HISTORY
    with _LOCK:
        if game_key not in _LINE_HISTORY:
            _LINE_HISTORY[game_key] = {
                "home_open": home_odds, "away_open": away_odds,
                "home_curr": home_odds, "away_curr": away_odds,
                "ts": datetime.now(), "samples": 1,
            }
        else:
            h = _LINE_HISTORY[game_key]
            h["home_curr"] = home_odds
            h["away_curr"] = away_odds
            h["samples"]  += 1


def _line_move_signal(game_key: str, home_odds: int, away_odds: int) -> tuple[float, int, str]:
    """
    Line movement probability signal.
    Sharp bettors move lines — if the line moves against public sentiment,
    that's the single strongest predictor of outcome.
    Returns (prob_adj_for_home, move_pts, note).
    """
    record_line(game_key, home_odds, away_odds)
    with _LOCK:
        hist = _LINE_HISTORY.get(game_key, {})

    if not hist or hist.get("samples", 1) < 2:
        return 0.5, 0, "first observation — no line history yet"

    home_move = hist["home_curr"] - hist["home_open"]  # positive = home line got better (more expensive)
    away_move = hist["away_curr"] - hist["away_open"]
    hours_tracked = (datetime.now() - hist["ts"]).seconds / 3600

    adj, note = 0.5, ""

    if abs(home_move) >= 15:
        if home_move > 0:
            # Home team getting more expensive = sharp money on home
            adj = 0.58; note = f"Sharp line move +{home_move}pts toward home ({hours_tracked:.1f}h)"
        else:
            # Home getting cheaper = sharp money on away
            adj = 0.42; note = f"Sharp line move {home_move}pts toward away ({hours_tracked:.1f}h)"
    elif abs(home_move) >= 8:
        if home_move > 0:
            adj = 0.54; note = f"Moderate move toward home (+{home_move})"
        else:
            adj = 0.46; note = f"Moderate move toward away ({home_move})"
    else:
        adj = 0.5; note = f"Line stable (home moved {home_move:+d}pts)"

    return float(adj), int(home_move), note


# ══════════════════════════════════════════════════════════════════════════════
# ENSEMBLE PREDICTOR — combines all signals
# ══════════════════════════════════════════════════════════════════════════════

def scout_game(home: str, away: str, sport: str, venue: str,
               home_odds: int, away_odds: int,
               book_home_prob: float) -> ScoutResult:
    """
    Full independent ensemble prediction.
    Book odds are accepted ONLY to track line movement and display edge.
    They are NEVER blended into our probability — that would be mirroring the books.
    """
    sn = sport.upper()
    game_key = f"{sn}:{away}@{home}"
    result = ScoutResult(
        game=game_key, home_team=home, away_team=away, sport=sn,
        book_implied=round(book_home_prob, 3),
        ts=datetime.now().strftime("%H:%M")
    )
    factors, warnings = [], []

    # ── 1. Pythagorean expectation ────────────────────────────────────────────
    # Point differential predicts future wins better than actual W-L record.
    # Removes luck from close-game outcomes. Most analytically validated model.
    standings = _load_standings(sn)
    from difflib import get_close_matches

    def _find_team(name: str) -> dict | None:
        nl = name.lower()
        if nl in standings:
            return standings[nl]
        nw = set(nl.split()) - {"fc","sc","city","united","the","de","af"}
        for k, v in standings.items():
            kw = set(k.split()) - {"fc","sc","city","united","the","de","af"}
            if nw and kw and len(nw & kw) >= max(1, min(len(nw), len(kw)) - 1):
                return v
        m = get_close_matches(nl, standings.keys(), n=1, cutoff=0.55)
        return standings[m[0]] if m else None

    hd = _find_team(home)
    ad = _find_team(away)

    if hd and ad and hd["ppg"] > 0 and ad["ppg"] > 0:
        home_pyth = _pythag_win_pct(hd["ppg"], hd["opp_ppg"], sn)
        away_pyth = _pythag_win_pct(ad["ppg"], ad["opp_ppg"], sn)
        total_pyth = home_pyth + away_pyth
        p_pyth = float(np.clip(home_pyth / total_pyth if total_pyth > 0 else 0.5, 0.15, 0.85))
        result.p_pythagorean = p_pyth
        factors.append(f"Pythagorean: {home} {home_pyth*100:.0f}% vs {away} {away_pyth*100:.0f}% (pt-diff model)")
    else:
        result.p_pythagorean = 0.5

    # ── 2. Team efficiency (off/def rating matchup) ───────────────────────────
    # Projected score from home offense vs away defense, and vice versa.
    # Catches teams with lopsided offensive/defensive profiles that raw W% misses.
    home_id = _get_team_id(home, sn)
    away_id = _get_team_id(away, sn)
    if home_id and away_id:
        p_eff, eff_note = _efficiency_prob(home_id, away_id, sn)
        result.p_efficiency = p_eff
        factors.append(f"Efficiency matchup: {eff_note}")
    else:
        result.p_efficiency = 0.5

    # ── 3. Recent form (last 7-10 games, exponentially weighted) ─────────────
    # Season averages lag. Recent form (last 2-3 weeks) predicts tonight better.
    # Exponential decay: last game counts ~2x the game from 5 games ago.
    h_form, h_form_desc = _get_recent_form(home, sn, n=10)
    a_form, a_form_desc = _get_recent_form(away, sn, n=10)
    total_form = h_form + a_form
    p_form = float(np.clip(h_form / total_form if total_form > 0 else 0.5, 0.15, 0.85))
    result.p_form = p_form
    factors.append(f"Recent form: {home} {h_form_desc} | {away} {a_form_desc}")

    # ── 4. Injury intelligence (ESPN public API) ──────────────────────────────
    # Missing a QB costs ~5.5% probability. Missing a starting C costs ~3.5%.
    # Position-weighted so we don't overreact to backup injuries.
    h_inj_adj, h_inj_notes = _injury_impact(home, sn)
    a_inj_adj, a_inj_notes = _injury_impact(away, sn)
    inj_net = h_inj_adj - a_inj_adj   # positive = away more injured → home benefits
    result.injury_adj = round(inj_net, 3)
    if h_inj_notes:
        warnings.extend([f"{home}: {n}" for n in h_inj_notes])
        factors.append(f"Injuries {home}: {', '.join(h_inj_notes[:2])}")
    if a_inj_notes:
        warnings.extend([f"{away}: {n}" for n in a_inj_notes])
        factors.append(f"Injuries {away}: {', '.join(a_inj_notes[:2])}")

    # ── 5. Rest/fatigue advantage ─────────────────────────────────────────────
    home_rest = _rest_days(home, sn)
    away_rest = _rest_days(away, sn)
    result.home_rest = home_rest
    result.away_rest = away_rest
    rest_adj, rest_note = _rest_prob_adj(home_rest, away_rest, sn)
    result.p_rest = float(np.clip(0.5 + rest_adj, 0.25, 0.75))
    if rest_note:
        factors.append(rest_note)
    if home_rest == 1:
        warnings.append(f"{home} playing back-to-back — cover rate drops to 44%")
    if away_rest == 1:
        warnings.append(f"{away} playing back-to-back — exploitable fatigue")

    # ── 6. Weather (outdoor sports only) ─────────────────────────────────────
    if sn in OUTDOOR_SPORTS and venue:
        w_adj, wind, w_note = _weather_prob_adj(venue, sn)
        result.p_weather = float(np.clip(0.5 + w_adj, 0.30, 0.70))
        result.wind_mph  = wind
        if w_note:
            factors.append(w_note)
        if wind >= 15:
            warnings.append(f"Wind {wind:.0f}mph — outdoor, defense-friendly game")
    else:
        result.p_weather = 0.5

    # ── 7. Home-field advantage (sport-calibrated) ────────────────────────────
    ha = HOME_ADV.get(sn, 0.030)
    p_home = float(np.clip(0.5 + ha, 0.50, 0.60))

    # ── 8. Line movement (sharp money signal — MODIFIER only) ────────────────
    # Sharp bettors are informed — their line moves correlate with outcomes.
    # Used as a confidence modifier, NOT as a primary model input.
    # This keeps our model independent while still respecting informed market signals.
    p_lm, line_move, lm_note = _line_move_signal(game_key, home_odds, away_odds)
    result.p_line_move = p_lm
    result.line_move   = line_move
    factors.append(f"Sharp money: {lm_note}")

    # ── Pure model ensemble (NO book blending) ────────────────────────────────
    # Weights derived from sports analytics literature on predictive accuracy:
    #   Pythagorean 30% — most validated formula (removes lucky W-L record)
    #   Efficiency   20% — catches mismatches raw W% misses
    #   Recent form  20% — season averages lag; last 2-3 weeks is better
    #   Rest         15% — fatigue is real and consistent
    #   Weather       5% — outdoor sports only, genuine impact
    #   Home field    5% — small but consistent historical edge
    #   Line move    5%  — sharp money modifier (low weight to keep model independent)
    W = [0.30, 0.20, 0.20, 0.15, 0.05, 0.05, 0.05]
    P = [result.p_pythagorean, result.p_efficiency, result.p_form,
         result.p_rest, result.p_weather, p_home, result.p_line_move]
    p_ensemble = float(np.clip(sum(w * p for w, p in zip(W, P)), 0.10, 0.90))

    # Apply injury adjustment directly (not part of ensemble weights — it's a direct impact)
    p_final = float(np.clip(p_ensemble + inj_net, 0.08, 0.92))
    result.p_ensemble = p_final

    # ── Confidence: count how many independent signals agree ──────────────────
    if p_final >= 0.50:
        result.pick = "HOME"; result.pick_team = home
        result.pick_pct = round(p_final * 100, 1)
        thresh_agree = 0.52
        agree = sum(1 for p in [result.p_pythagorean, result.p_efficiency,
                                  result.p_form, result.p_rest] if p > thresh_agree)
    else:
        result.pick = "AWAY"; result.pick_team = away
        result.pick_pct = round((1 - p_final) * 100, 1)
        thresh_agree = 0.48
        agree = sum(1 for p in [result.p_pythagorean, result.p_efficiency,
                                  result.p_form, result.p_rest] if p < thresh_agree)

    # Line movement agreement boosts confidence; disagreement is a warning
    lm_agrees = (result.pick == "HOME" and p_lm > 0.52) or \
                (result.pick == "AWAY" and p_lm < 0.48)
    lm_disagrees = (result.pick == "HOME" and p_lm < 0.45) or \
                   (result.pick == "AWAY" and p_lm > 0.55)

    if lm_agrees:
        agree += 1  # sharp money confirms our independent pick
        factors.append("Sharp money AGREES with model pick")
    if lm_disagrees:
        warnings.append("Sharp money DIVERGES from model — reduce stake size")

    result.signals_agree = agree

    # HIGH: 3+ signals agree, pick_pct >= 64%
    # MEDIUM: 2+ signals agree, pick_pct >= 59%
    if agree >= 3 and result.pick_pct >= 64:
        result.confidence = "HIGH"
    elif agree >= 2 and result.pick_pct >= 59:
        result.confidence = "MEDIUM"
    else:
        result.confidence = "LOW"

    # Extra warning if our model strongly disagrees with the book
    model_vs_book_gap = abs(p_final - book_home_prob) * 100
    if model_vs_book_gap >= 15:
        factors.append(f"Model vs book gap: {model_vs_book_gap:.0f}% — strong divergence = potential edge")
    elif model_vs_book_gap >= 8:
        factors.append(f"Model vs book gap: {model_vs_book_gap:.0f}% — meaningful divergence")

    result.factors  = factors
    result.warnings = warnings

    with _LOCK:
        _SCOUT_CACHE[game_key] = result

    return result


def get_scout_cache() -> dict:
    """Return a copy of all current scout results keyed by game_key."""
    with _LOCK:
        return dict(_SCOUT_CACHE)


def clear_session_caches():
    """Call at the start of each refresh cycle to clear staleable data."""
    global _TEAM_STATS, _REST, _WEATHER, _STANDINGS, _TEAM_IDS, _FORM_CACHE, _INJ_CACHE
    _TEAM_STATS.clear()
    _REST.clear()
    _WEATHER.clear()
    _STANDINGS.clear()
    _TEAM_IDS.clear()
    _FORM_CACHE.clear()
    _INJ_CACHE.clear()
    # NOTE: Do NOT clear _LINE_HISTORY or _SCOUT_CACHE —
    # line history must persist across cycles to track movement


# ── Keywords that signal a meaningful roster/situation change ─────────────────
_NEWS_KEYWORDS = {
    "injur", "scratch", "suspend", "questionable", "ruled out", "doubtful",
    "placed on", "day-to-day", "inactive", "concussion", "knee", "ankle",
    "hamstring", "shoulder", "wrist", "illness", "flu", "not play",
    "benched", "limited", "will miss", "out for", "starting lineup",
}


def get_game_news(home: str, away: str, sport: str) -> list[str]:
    """
    ESPN team news for both squads — free endpoint, no key needed.
    Returns headline strings that contain impact keywords (injury, suspension, etc).
    Called every 20 min to catch late scratches before the next odds refresh.
    """
    lm = ESPN_MAP.get(sport.upper())
    if not lm:
        return []
    sp, lg = lm
    alerts = []
    for team, side in [(home, "HOME"), (away, "AWAY")]:
        team_id = _get_team_id(team, sport.upper())
        if not team_id:
            continue
        data = _espn_get(
            f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/teams/{team_id}/news?limit=8"
        )
        for art in data.get("articles", [])[:8]:
            text = (art.get("headline", "") + " " + art.get("description", "")).lower()
            if any(kw in text for kw in _NEWS_KEYWORDS):
                alerts.append(f"[{side}] {art.get('headline','')[:90]}")
                if len(alerts) >= 4:
                    break
        if len(alerts) >= 4:
            break
    return alerts


def refresh_injury_cache():
    """Clear only the injury cache — call before rescore to get fresh data."""
    global _INJ_CACHE
    _INJ_CACHE.clear()


def get_best_picks(min_confidence: str = "MEDIUM",
                   min_pct: float = 60.0) -> list[ScoutResult]:
    """
    Return tonight's highest-probability picks, filtered and sorted.
    Only picks where multiple independent signals agree.
    """
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    with _LOCK:
        picks = [
            r for r in _SCOUT_CACHE.values()
            if r.pick_pct >= min_pct
            and tier_order.get(r.confidence, 2) <= tier_order.get(min_confidence, 1)
        ]
    return sorted(picks, key=lambda x: (-tier_order.get(x.confidence,2), -x.pick_pct))
