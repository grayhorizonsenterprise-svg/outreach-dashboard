"""
intelligence.py — Enhanced predictive data layer.
Pulls free real-time feeds: fear/greed, earnings, economic events,
crypto whale activity, injury reports, weather, line movement.
All feeds are free, no additional API keys required.
"""

import requests
import json
from datetime import datetime, timedelta
from functools import lru_cache
import yfinance as yf

HEADERS = {"User-Agent": "EdgeEngine/1.0"}


# ══════════════════════════════════════════════════════════════════════════════
# MARKET INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

def get_fear_greed() -> dict:
    """
    CNN Fear & Greed Index via alternative.me (free, no key).
    0-24 = Extreme Fear (BUY signal), 75-100 = Extreme Greed (SELL signal).
    """
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=3", timeout=8)
        data = r.json()["data"]
        now   = data[0]
        prev  = data[1] if len(data) > 1 else data[0]
        value = int(now["value"])
        label = now["value_classification"]
        prev_v = int(prev["value"])
        direction = "rising" if value > prev_v else "falling" if value < prev_v else "flat"

        # Trading signal from fear/greed
        if value <= 24:
            signal = "STRONG BUY — Extreme Fear = market oversold"
        elif value <= 45:
            signal = "BUY — Fear present, historically good entry zone"
        elif value <= 55:
            signal = "NEUTRAL — balanced sentiment"
        elif value <= 75:
            signal = "WATCH — Greed building, tighten stops"
        else:
            signal = "CAUTION — Extreme Greed, risk of correction"

        return {
            "value":     value,
            "label":     label,
            "direction": direction,
            "signal":    signal,
            "prev":      prev_v,
        }
    except Exception:
        return {"value": 50, "label": "Neutral", "direction": "flat",
                "signal": "NEUTRAL", "prev": 50}


def get_crypto_fear_greed() -> dict:
    """Same endpoint but context is crypto-specific."""
    return get_fear_greed()  # alternative.me is crypto-focused


def get_earnings_this_week() -> list[dict]:
    """Upcoming earnings from Yahoo Finance for watchlist tickers."""
    from config import STOCKS
    events = []
    now = datetime.now()
    week_end = now + timedelta(days=7)
    for ticker in STOCKS[:40]:  # limit to avoid rate limits
        try:
            cal = yf.Ticker(ticker).calendar
            if cal is None or cal.empty:
                continue
            # calendar returns a DataFrame with earnings date
            for col in cal.columns:
                val = cal[col].get("Earnings Date")
                if val is not None:
                    try:
                        ed = datetime.strptime(str(val)[:10], "%Y-%m-%d")
                        if now <= ed <= week_end:
                            events.append({
                                "ticker": ticker,
                                "date":   ed.strftime("%a %b %d"),
                                "note":   "Earnings — expect volatility",
                            })
                    except Exception:
                        pass
        except Exception:
            pass
    return sorted(events, key=lambda x: x["date"])


def get_economic_calendar() -> list[dict]:
    """
    Key economic events this week from Forex Factory public feed.
    High-impact events move the whole market.
    """
    try:
        # Forex Factory provides a public JSON feed
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            timeout=10, headers=HEADERS
        )
        if r.status_code != 200:
            return _fallback_economic_events()
        events = r.json()
        high_impact = [
            {
                "date":    e.get("date",""),
                "time":    e.get("time",""),
                "country": e.get("country",""),
                "event":   e.get("title",""),
                "impact":  e.get("impact",""),
            }
            for e in events
            if e.get("impact","").lower() in ("high",) and e.get("country","") == "USD"
        ]
        return high_impact[:10]
    except Exception:
        return _fallback_economic_events()


def _fallback_economic_events() -> list[dict]:
    return [{"date": "N/A", "time": "", "country": "USD",
             "event": "Check federalreserve.gov for FOMC dates", "impact": "high"}]


def get_sector_rotation() -> list[dict]:
    """
    Check sector ETF momentum to identify where money is flowing.
    Strong sector = tailwind for stocks in that sector.
    """
    sectors = {
        "XLK":  "Technology",
        "XLF":  "Financials",
        "XLE":  "Energy",
        "XLV":  "Healthcare",
        "XLI":  "Industrials",
        "XLY":  "Consumer Disc.",
        "XLC":  "Communication",
        "XLB":  "Materials",
        "XLRE": "Real Estate",
        "XLU":  "Utilities",
        "XLP":  "Consumer Staples",
    }
    results = []
    for etf, name in sectors.items():
        try:
            df = yf.Ticker(etf).history(period="1mo")
            if df.empty:
                continue
            ret_1m = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
            ret_1w = (df["Close"].iloc[-1] / df["Close"].iloc[-5] - 1) * 100
            results.append({
                "etf":    etf,
                "sector": name,
                "ret_1w": round(ret_1w, 2),
                "ret_1m": round(ret_1m, 2),
                "trend":  "INFLOW" if ret_1w > 1 else "OUTFLOW" if ret_1w < -1 else "FLAT",
            })
        except Exception:
            pass
    return sorted(results, key=lambda x: x["ret_1w"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# CRYPTO INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

def get_crypto_trending() -> list[dict]:
    """CoinGecko trending search — what retail is hunting right now."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            timeout=10, headers=HEADERS
        )
        if r.status_code != 200:
            return []
        coins = r.json().get("coins", [])
        return [
            {
                "symbol": c["item"]["symbol"].upper(),
                "name":   c["item"]["name"],
                "rank":   c["item"]["market_cap_rank"],
                "score":  c["item"].get("score", 0),
            }
            for c in coins[:10]
        ]
    except Exception:
        return []


def get_crypto_global() -> dict:
    """Global crypto market stats — dominance, total cap, volume."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=10, headers=HEADERS
        )
        if r.status_code != 200:
            return {}
        d = r.json().get("data", {})
        btc_dom = d.get("market_cap_percentage", {}).get("btc", 0)
        eth_dom = d.get("market_cap_percentage", {}).get("eth", 0)
        total_cap = d.get("total_market_cap", {}).get("usd", 0)
        volume_24h = d.get("total_volume", {}).get("usd", 0)

        # Alt season signal: BTC dominance dropping = alts pumping
        if btc_dom > 58:
            alt_signal = "BTC DOMINANT — alts may lag, favor BTC"
        elif btc_dom < 45:
            alt_signal = "ALT SEASON — diversify into top alts"
        else:
            alt_signal = "MIXED — BTC + selective alts"

        return {
            "btc_dominance": round(btc_dom, 1),
            "eth_dominance": round(eth_dom, 1),
            "total_cap_b":   round(total_cap / 1e9, 0),
            "volume_24h_b":  round(volume_24h / 1e9, 0),
            "alt_signal":    alt_signal,
        }
    except Exception:
        return {}


def get_defi_pulse() -> list[dict]:
    """Top DeFi protocols by TVL change — early signal for DeFi token moves."""
    try:
        r = requests.get(
            "https://api.llama.fi/protocols",
            timeout=10, headers=HEADERS
        )
        if r.status_code != 200:
            return []
        protocols = r.json()
        return [
            {
                "name":     p["name"],
                "symbol":   p.get("symbol","").upper(),
                "tvl_b":    round(p.get("tvl",0)/1e9, 2),
                "change_1d": round(p.get("change_1d",0), 2),
            }
            for p in sorted(protocols, key=lambda x: abs(x.get("change_1d",0)), reverse=True)
            if p.get("symbol") and p.get("tvl",0) > 100_000_000
        ][:10]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# SPORTS BETTING INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

def get_nfl_injuries() -> list[dict]:
    """ESPN public API — injury reports for current NFL/NBA rosters."""
    results = []
    leagues = {
        "nfl": "americanfootball/nfl",
        "nba": "basketball/nba",
        "mlb": "baseball/mlb",
    }
    for sport, path in leagues.items():
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/injuries"
            r = requests.get(url, timeout=8, headers=HEADERS)
            if r.status_code != 200:
                continue
            data = r.json()
            teams = data.get("injuries", [])
            for team in teams[:6]:
                team_name = team.get("team", {}).get("displayName","")
                for player in team.get("injuries", [])[:3]:
                    status = player.get("status","").upper()
                    if status in ("OUT","DOUBTFUL","QUESTIONABLE"):
                        results.append({
                            "sport":  sport.upper(),
                            "team":   team_name,
                            "player": player.get("athlete",{}).get("displayName",""),
                            "status": status,
                            "pos":    player.get("athlete",{}).get("position",{}).get("abbreviation",""),
                            "note":   player.get("shortComment",""),
                        })
        except Exception:
            pass
    return results


def get_line_movement(game_id: str = "") -> dict:
    """
    Placeholder — real line movement data requires a paid feed.
    Sharp money indicator: when the line moves OPPOSITE to public betting %,
    that's sharp (professional) money coming in. Always bet with the sharps.
    """
    return {
        "note": "Line movement tracking requires Action Network or Pinnacle feed.",
        "rule": "If 70%+ of public bets on Team A but line moves to favor Team B, bet Team B.",
    }


def score_bet_with_intelligence(
    our_prob: float,
    injuries: list[dict],
    home_team: str,
    away_team: str,
) -> tuple[float, list[str]]:
    """
    Adjust bet probability based on injury intelligence.
    Returns (adjusted_probability, list_of_factors).
    """
    adj = our_prob
    factors = []

    for inj in injuries:
        team = inj["team"]
        status = inj["status"]
        pos = inj.get("pos","")
        player = inj.get("player","")

        is_relevant = (home_team in team or away_team in team)
        if not is_relevant:
            continue

        # Key position impacts
        if pos in ("QB", "SP"):  # quarterback or starting pitcher
            if status == "OUT":
                adj -= 0.08
                factors.append(f"MAJOR: {player} ({pos}) OUT for {team}")
            elif status == "DOUBTFUL":
                adj -= 0.04
                factors.append(f"KEY: {player} ({pos}) doubtful for {team}")
        elif pos in ("RB", "WR1", "C", "PG", "SG"):
            if status == "OUT":
                adj -= 0.03
                factors.append(f"{player} ({pos}) OUT")

    return round(min(0.98, max(0.02, adj)), 3), factors


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE DAILY BRIEF
# ══════════════════════════════════════════════════════════════════════════════

def get_daily_intelligence() -> dict:
    """
    Single call that returns all intelligence data.
    Called once per cache refresh cycle.
    """
    print("  Fetching intelligence layer (fear/greed, earnings, crypto global, injuries)...")
    return {
        "fear_greed":       get_fear_greed(),
        "crypto_global":    get_crypto_global(),
        "crypto_trending":  get_crypto_trending(),
        "defi_movers":      get_defi_pulse(),
        "injuries":         get_nfl_injuries(),
        "economic_events":  get_economic_calendar(),
        "sector_rotation":  get_sector_rotation(),
        "earnings_week":    get_earnings_this_week(),
        "generated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
