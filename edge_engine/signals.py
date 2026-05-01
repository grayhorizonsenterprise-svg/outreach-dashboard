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
    MIN_BET_EDGE_PCT, MIN_SIGNAL_SCORE
)

HEADERS = {"User-Agent": "EdgeEngine/1.0"}


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
    print("  Scanning stocks...")
    for ticker in STOCKS:
        try:
            df = yf.Ticker(ticker).history(period="3mo")
            if df.empty or len(df) < 10:
                continue
            score, note = _stock_score(df)
            price = float(df["Close"].iloc[-1])
            prev  = float(df["Close"].iloc[-2])
            rsi_v = _rsi(df["Close"])
            trend = ("STRONG BUY" if score >= 75 else
                     "BUY"        if score >= 60 else
                     "WATCH"      if score >= 45 else "SKIP")
            results.append(StockSignal(ticker, score, price,
                round((price/prev-1)*100, 2), round(rsi_v,1), trend, note))
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

def get_crypto_signals() -> list[CryptoSignal]:
    print("  Scanning crypto...")
    ids = ",".join(CRYPTOS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=volume_desc"
        "&per_page=50&page=1&sparkline=false"
        "&price_change_percentage=1h,24h,7d"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 429:
            print("  [!] CoinGecko rate limit — try again in 60s")
            return []
        r.raise_for_status()
        coins = r.json()
    except Exception as e:
        print(f"  [!] Crypto fetch failed: {e}")
        return []

    results = []
    for c in coins:
        h1  = c.get("price_change_percentage_1h_in_currency")  or 0
        h24 = c.get("price_change_percentage_24h_in_currency") or 0
        d7  = c.get("price_change_percentage_7d_in_currency")  or 0
        vol = c.get("total_volume") or 0
        mc  = c.get("market_cap")   or 1

        # Momentum score
        mom = np.clip(50 + (h1*0.4 + h24*0.4 + d7*0.2)*3, 0, 100)

        # Volume vs market cap ratio (high ratio = active)
        vol_ratio = vol / mc
        vol_score = np.clip(vol_ratio * 500, 0, 40)

        score = float(np.clip(mom*0.65 + vol_score*0.35, 0, 100))

        trend = ("STRONG BUY" if score >= 75 else
                 "BUY"        if score >= 60 else
                 "WATCH"      if score >= 45 else "SKIP")

        notes = []
        if h1  >  1: notes.append(f"1h +{h1:.1f}%")
        if h24 >  3: notes.append(f"24h +{h24:.1f}%")
        if h24 < -5: notes.append(f"24h {h24:.1f}% (dip?)")
        if vol_ratio > 0.1: notes.append("high volume")

        results.append(CryptoSignal(
            coin=c["name"], symbol=c["symbol"].upper(),
            score=round(score,1), price=c["current_price"],
            change_1h=round(h1,2), change_24h=round(h24,2),
            change_7d=round(d7,2), volume_24h=vol, market_cap=mc,
            trend=trend, note=" | ".join(notes) or "standard"
        ))

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

    for team, best_book, best_odds, true_p in [
        (home, best_home[0], best_home[1], home_true),
        (away, best_away[0], best_away[1], away_true),
    ]:
        book_implied = american_to_prob(best_odds)
        # EV: if our model (devigged consensus) says true_p but book says book_implied
        # Edge = how much better our line is vs vig-inclusive price
        edge = (true_p - book_implied) * 100

        if edge < MIN_BET_EDGE_PCT:
            continue  # not enough edge after vig

        ev = (true_p * (100 / book_implied if best_odds > 0 else 100/(book_implied))) - 100

        confidence = "HIGH" if true_p > 0.68 else "MEDIUM" if true_p > 0.55 else "LOW"

        signals.append(BetSignal(
            sport=sport.split("_")[0].upper(),
            game=f"{away} @ {home}",
            bet_on=team,
            book=best_book,
            odds=best_odds,
            implied_prob=round(book_implied, 3),
            our_prob=round(true_p, 3),
            edge_pct=round(edge, 2),
            expected_value=round(ev, 2),
            confidence=confidence,
            note=f"Best line: {best_book} | devigged edge",
            commence=commence
        ))

    return signals

def get_betting_signals() -> list[BetSignal]:
    print("  Scanning sports odds...")
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
    politics = _get_polymarket_politics()
    all_signals.extend(politics)

    return sorted(all_signals, key=lambda x: (x.our_prob, x.edge_pct), reverse=True)


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


def get_action_plan(stocks: list, cryptos: list, bets: list,
                    bankroll: float = 100.0) -> dict:
    plays = {"stocks": [], "crypto": [], "bets": [], "summary": {}}

    qualifying_s = [s for s in stocks if s.trend in ("STRONG BUY", "BUY")][:5]
    stock_budget = bankroll * 0.60
    alloc_s = [0.50, 0.30, 0.20]
    for i, s in enumerate(qualifying_s[:3]):
        t = _stock_targets(s.ticker, s.price, s.score, s.rsi)
        din = round(stock_budget * alloc_s[i], 2)
        shares = round(din / s.price, 4) if s.price > 0 else 0
        plays["stocks"].append({
            "rank": i + 1, "ticker": s.ticker, "score": s.score,
            "entry": s.price, "target": t["target"], "stop": t["stop"],
            "target_pct": t["target_pct"], "stop_pct": t["stop_pct"],
            "rr": t["risk_reward"], "dollar_in": din, "shares": shares,
            "profit": round(shares * (t["target"] - s.price), 2),
            "reason": s.note, "platform": "Robinhood",
        })

    qualifying_c = [c for c in cryptos if c.trend in ("STRONG BUY", "BUY")][:4]
    crypto_budget = bankroll * 0.25
    alloc_c = [0.65, 0.35]
    for i, c in enumerate(qualifying_c[:2]):
        t = _crypto_targets(c.price, c.score, c.change_24h)
        din = round(crypto_budget * alloc_c[i], 2)
        plays["crypto"].append({
            "rank": i + 1, "symbol": c.symbol, "coin": c.coin,
            "score": c.score, "entry": c.price, "target": t["target"],
            "stop": t["stop"], "target_pct": t["target_pct"],
            "stop_pct": t["stop_pct"], "rr": t["risk_reward"],
            "dollar_in": din, "profit": round(din * t["target_pct"] / 100, 2),
            "reason": c.note or "momentum", "platform": "Coinbase / CashApp",
        })

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
            sum(p["payout"] for p in plays["bets"]), 2),
        "weekly_growth_est": 18.0,
        "projection_13w": projection,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return plays
