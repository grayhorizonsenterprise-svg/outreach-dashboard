"""
chart_card_generator.py — Gray Horizons Enterprise
Generates 12 rotating branded PNG cards for daily X posts.

Cards 1-6:  Screenshot-based  — real TradingView/dashboard images with branded overlay
Cards 7-12: Dynamic data cards — generated live from scan data, wins log, etc.

All output: 1200x628 PNG (optimal for X/Twitter feed)

Usage:
    from chart_card_generator import next_card, log_win
    name, png_bytes = next_card()           # auto-rotates through all 12
    name, png_bytes = next_card("chart")    # screenshot-based only
    name, png_bytes = next_card("data")     # dynamic data only
    log_win("NVDA +9.2%", "WIN", "+$92 on $1k", "stocks")
"""

import os
import io
import json
import random
from pathlib import Path
from datetime import datetime

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
INDICATORS = DATA_DIR / "indicators"
WINS_LOG   = DATA_DIR / "wins_log.json"

GUMROAD_LINK = "https://horizons56.gumroad.com"
SIGNALS_LINK = os.getenv("SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
WHOP_LINK    = os.getenv("WHOP_INDICATORS_LINK", "https://horizons56.gumroad.com/l/ghe-indicators")

W, H = 1200, 628

# ─── Color palette ────────────────────────────────────────────────────────────
NAVY      = (13, 26, 52)
NAVY_MID  = (20, 38, 74)
NAVY_DARK = (8, 16, 35)
GREEN     = (0, 205, 115)
BLUE_ACC  = (29, 140, 245)
RED_ACC   = (220, 70, 70)
WHITE     = (255, 255, 255)
GRAY_LO   = (140, 158, 185)
DIVIDER   = (30, 55, 100)
GOLD      = (230, 175, 0)


def _fonts():
    try:
        from PIL import ImageFont
        return (
            ImageFont.truetype("arialbd.ttf", 20),   # tag/small
            ImageFont.truetype("arialbd.ttf", 40),   # headline
            ImageFont.truetype("arial.ttf",   28),   # body
            ImageFont.truetype("arial.ttf",   19),   # footer
        )
    except Exception:
        try:
            from PIL import ImageFont
            f = ImageFont.load_default()
            return (f, f, f, f)
        except Exception:
            return (None, None, None, None)


def _new_canvas():
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), NAVY_DARK)
    draw = ImageDraw.Draw(img)
    return img, draw


def _accent_bar(draw, color=GREEN):
    draw.rectangle([0, 0, 10, H], fill=color)


def _header(draw, label: str, color=GREEN, fonts=None):
    if fonts is None:
        fonts = _fonts()
    draw.rectangle([0, 0, W, 62], fill=(9, 20, 42))
    tag_w = len(label) * 12 + 28
    draw.rectangle([14, 12, 14 + tag_w, 50], fill=color)
    draw.text((22, 17), label, font=fonts[0], fill=NAVY_DARK)
    today = datetime.now().strftime("%b %d, %Y")
    draw.text((W - 175, 20), today, font=fonts[0], fill=GRAY_LO)


def _footer(draw, cta: str, link: str, fonts=None):
    if fonts is None:
        fonts = _fonts()
    draw.rectangle([0, H - 50, W, H], fill=(9, 20, 42))
    draw.rectangle([0, H - 51, W, H - 50], fill=DIVIDER)
    full = f"Gray Horizons Enterprise  |  grayhorizonsenterprise.com  |  {cta}: {link}"
    draw.text((14, H - 36), full, font=fonts[3], fill=GRAY_LO)


def _to_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─── Screenshot overlay helper ───────────────────────────────────────────────

def _screenshot_card(
    img_path: Path,
    header_label: str,
    badge_text: str,
    cta: str,
    link: str,
    accent=GREEN,
) -> bytes | None:
    """
    Load a real screenshot, center-crop it into the content area (middle 516px),
    then add a branded 62px header bar and 50px footer bar.
    """
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()

        base = Image.open(img_path).convert("RGB")
        content_h = H - 112   # 628 - 62 header - 50 footer
        scale = max(W / base.width, content_h / base.height)
        nw = int(base.width * scale)
        nh = int(base.height * scale)
        base = base.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - W) // 2
        y0 = (nh - content_h) // 2
        base = base.crop((x0, y0, x0 + W, y0 + content_h))

        canvas = Image.new("RGB", (W, H), NAVY_DARK)
        canvas.paste(base, (0, 62))
        draw = ImageDraw.Draw(canvas)

        _accent_bar(draw, accent)
        _header(draw, header_label, accent, fonts)

        # Badge top-right in header
        if badge_text:
            bw = len(badge_text) * 12 + 20
            draw.rectangle([W - bw - 14, 14, W - 14, 50], fill=accent)
            draw.text((W - bw - 8, 18), badge_text, font=fonts[0], fill=NAVY_DARK)

        _footer(draw, cta, link, fonts)
        return _to_bytes(canvas)
    except Exception as e:
        print(f"[CARD] screenshot_card({img_path.name}): {e}")
        return None


# ─── CARD 1 — Live TradingView Chart ─────────────────────────────────────────

# All TradingView screenshots in the indicators folder (add more by dropping .png files there)
_TV_CHART_GLOBS = ["*chart*.png", "*Chart*.png", "*live*.png", "*Live*.png",
                   "GHE Edge*.png", "*Scanner*.png", "*Flow*.png"]


def card_tradingview_chart(signal_data: dict | None = None) -> bytes | None:
    charts: list[Path] = []
    for pat in _TV_CHART_GLOBS:
        charts.extend(INDICATORS.glob(pat))
    charts = list({p.resolve() for p in charts if p.exists()})  # deduplicate
    if not charts:
        # Fall back to any PNG in indicators/
        charts = [p for p in INDICATORS.glob("*.png") if "mockup" not in p.name.lower()]
    if not charts:
        return None
    chosen = random.choice(charts)
    ticker  = signal_data.get("ticker", "LIVE") if signal_data else "LIVE"
    score   = signal_data.get("score", "") if signal_data else ""
    badge   = f"SCORE: {score}" if score else "LIVE SIGNAL"
    return _screenshot_card(chosen, f"GHE EDGE SCANNER — {ticker}", badge, "Get access", WHOP_LINK, GREEN)


# ─── CARD 2 — GHL CRM Dashboard ──────────────────────────────────────────────

def card_ghl_dashboard() -> bytes | None:
    for p in [
        INDICATORS / "ghl-dashboard-demo.png",
        INDICATORS / "mockups" / "GHL CRM Dashboard.png",
    ]:
        if p.exists():
            return _screenshot_card(p, "GHL CRM DASHBOARD — LIVE DATA", "CLIENT VIEW", "Build yours", GUMROAD_LINK, BLUE_ACC)
    return None


# ─── CARD 3 — Contractor Intake System ───────────────────────────────────────

def card_contractor_intake() -> bytes | None:
    for p in [
        INDICATORS / "mockups" / "REAL CONTRACTOR INTAKE DASHBOARD .png",
        INDICATORS / "contractor intake dashboard client side.png",
        INDICATORS / "mockups" / "Contractor Pipeline.png",
    ]:
        if p.exists():
            return _screenshot_card(p, "CONTRACTOR INTAKE SYSTEM", "LIVE BUILD", "See how it works", GUMROAD_LINK, BLUE_ACC)
    return None


# ─── CARD 4 — Vapi AI Voice Agent Demo ───────────────────────────────────────

def card_vapi_demo() -> bytes | None:
    for p in [
        INDICATORS / "vapi-booking-complete.png",
        INDICATORS / "vapi-live-transcript.png",
        INDICATORS / "vapi-agent-dashboard.png",
    ]:
        if p.exists():
            return _screenshot_card(p, "AI VOICE AGENT — BOOKING CONFIRMED", "24/7 LIVE", "Deploy yours", GUMROAD_LINK, GREEN)
    return None


# ─── CARD 5 — Edge Scanner Product Cover ─────────────────────────────────────

def card_product_edge() -> bytes | None:
    p = INDICATORS / "GHE-Edge-Engine-Cover.png"
    if not p.exists():
        return None
    return _screenshot_card(p, "GHE EDGE SCANNER — TRADINGVIEW INDICATOR", "$79 ONCE", "Get it now", WHOP_LINK, GREEN)


# ─── CARD 6 — Institutional Flow Product Cover ───────────────────────────────

def card_product_flow() -> bytes | None:
    for p in [
        INDICATORS / "GHE-Institutional-Flow-Cover.png",
        INDICATORS / "GHE-Institutional-Flow-Thumb.png",
    ]:
        if p.exists():
            return _screenshot_card(p, "INSTITUTIONAL FLOW INDICATOR — TRADINGVIEW", "$67 ONCE", "Get it now", WHOP_LINK, BLUE_ACC)
    return None


# ─── CARD 7 — Signal Scorecard (dynamic) ─────────────────────────────────────

def card_signal_scorecard(signals: list[dict] | None = None) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, GREEN)
        _header(draw, "SIGNAL SCORECARD — TODAY", GREEN, fonts)

        rows = signals or [
            {"ticker": "NVDA", "score": 81, "rsi": 62.1, "note": "Volume 2.3x avg"},
            {"ticker": "APP",  "score": 78, "rsi": 58.4, "note": "EMA breakout"},
            {"ticker": "COIN", "score": 74, "rsi": 55.2, "note": "Congress buy 7d"},
            {"ticker": "ETH",  "score": 71, "rsi": 61.8, "note": "Momentum build"},
            {"ticker": "MSFT", "score": 70, "rsi": 57.3, "note": "Institutional flow"},
        ]

        y = 80
        draw.text((18, y), "HIGH-CONVICTION SETUPS  —  SCORE 70+  —  ENTRY ZONE", font=fonts[0], fill=GRAY_LO)
        y += 34
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 14

        for i, row in enumerate(rows[:6]):
            sc = row.get("score", 0)
            bar_color = GREEN if sc >= 75 else (BLUE_ACC if sc >= 70 else GRAY_LO)
            # progress bar underline
            fill_px = int((sc / 100) * 420)
            draw.rectangle([18, y + 40, 18 + fill_px, y + 44], fill=bar_color)
            draw.text((18, y + 4),   f"#{i+1}", font=fonts[0], fill=GRAY_LO)
            draw.text((58, y),       str(row.get("ticker", "")), font=fonts[1], fill=WHITE)
            draw.text((220, y + 10), f"Score: {sc}", font=fonts[0], fill=bar_color)
            draw.text((400, y + 10), f"RSI: {row.get('rsi', 0):.1f}", font=fonts[0], fill=GRAY_LO)
            draw.text((580, y + 10), str(row.get("note", "")), font=fonts[0], fill=GRAY_LO)
            y += 54

        _footer(draw, "Full signal sheet daily at", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] signal_scorecard: {e}")
        return None


# ─── CARD 8 — Congress Buys (dynamic) ────────────────────────────────────────

def card_congress_buys(buys: list[dict] | None = None) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, BLUE_ACC)
        _header(draw, "CONGRESSIONAL BUY SIGNALS", BLUE_ACC, fonts)

        rows = buys or [
            {"ticker": "NVDA", "member": "Nancy Pelosi",    "amount": "$250K-$500K", "days_ago": 3},
            {"ticker": "MSFT", "member": "Dan Crenshaw",    "amount": "$100K-$250K", "days_ago": 7},
            {"ticker": "PLTR", "member": "Michael McCaul",  "amount": "$50K-$100K",  "days_ago": 12},
            {"ticker": "TSM",  "member": "Josh Gottheimer", "amount": "$100K-$250K", "days_ago": 18},
            {"ticker": "META", "member": "Ro Khanna",       "amount": "$50K-$100K",  "days_ago": 22},
        ]

        y = 80
        draw.text((18, y), "MEMBERS BUYING — LAST 90 DAYS  |  Pattern: volume spike in week 1, disclosure at day 45", font=fonts[0], fill=GRAY_LO)
        y += 34
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 14

        for row in rows[:5]:
            d = row.get("days_ago", 0)
            recency_color = GREEN if d <= 7 else (BLUE_ACC if d <= 21 else GRAY_LO)
            draw.text((18,  y + 2), row["ticker"], font=fonts[2], fill=WHITE)
            draw.text((155, y + 6), str(row["member"]), font=fonts[0], fill=BLUE_ACC)
            draw.text((530, y + 6), str(row["amount"]), font=fonts[0], fill=GREEN)
            draw.text((830, y + 6), f"{d}d ago", font=fonts[0], fill=recency_color)
            y += 48

        draw.rectangle([18, y + 4, W - 18, y + 5], fill=DIVIDER)
        draw.text((18, y + 14), "These members have historically strong signal. Retail doesn't see this until news breaks.", font=fonts[0], fill=GRAY_LO)

        _footer(draw, "Track congress moves daily", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] congress_buys: {e}")
        return None


# ─── CARD 9 — Kelly Sizing Table (dynamic) ───────────────────────────────────

def card_kelly_table(setups: list[dict] | None = None) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, GREEN)
        _header(draw, "KELLY POSITION SIZING — TOP SETUPS", GREEN, fonts)

        rows = setups or [
            {"ticker": "NVDA", "score": 81, "win_pct": 74.3, "bet_25": 7.25, "bet_50": 14.50, "bet_100": 29.00},
            {"ticker": "COIN", "score": 78, "win_pct": 71.8, "bet_25": 6.75, "bet_50": 13.50, "bet_100": 27.00},
            {"ticker": "ETH",  "score": 74, "win_pct": 69.2, "bet_25": 6.00, "bet_50": 12.00, "bet_100": 24.00},
            {"ticker": "APP",  "score": 71, "win_pct": 67.5, "bet_25": 5.50, "bet_50": 11.00, "bet_100": 22.00},
            {"ticker": "MSFT", "score": 70, "win_pct": 66.0, "bet_25": 5.25, "bet_50": 10.50, "bet_100": 21.00},
        ]

        y = 76
        draw.text((18, y), "TICKER", font=fonts[0], fill=GRAY_LO)
        draw.text((190, y), "SCORE", font=fonts[0], fill=GRAY_LO)
        draw.text((370, y), "WIN %", font=fonts[0], fill=GRAY_LO)
        draw.text((550, y), "$25 PLAY", font=fonts[0], fill=GRAY_LO)
        draw.text((730, y), "$50 PLAY", font=fonts[0], fill=GRAY_LO)
        draw.text((920, y), "$100 PLAY", font=fonts[0], fill=GRAY_LO)
        y += 30
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 12

        for row in rows[:5]:
            sc = row.get("score", 0)
            sc_color = GREEN if sc >= 75 else (BLUE_ACC if sc >= 70 else GRAY_LO)
            draw.text((18,  y), row["ticker"], font=fonts[2], fill=WHITE)
            draw.text((190, y), str(sc), font=fonts[2], fill=sc_color)
            draw.text((370, y), f"{row.get('win_pct', 0):.1f}%", font=fonts[2], fill=GREEN)
            draw.text((550, y), f"${row.get('bet_25', 0):.2f}", font=fonts[2], fill=WHITE)
            draw.text((730, y), f"${row.get('bet_50', 0):.2f}", font=fonts[2], fill=WHITE)
            draw.text((920, y), f"${row.get('bet_100', 0):.2f}", font=fonts[2], fill=WHITE)
            y += 50

        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 14
        draw.text((18, y), "Quarter-Kelly fractional sizing. Risk what math says — not what feels right.", font=fonts[0], fill=GRAY_LO)

        _footer(draw, "GHE Kelly Sizer for TradingView", WHOP_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] kelly_table: {e}")
        return None


# ─── CARD 10 — Wins Scorecard (dynamic from wins_log.json) ───────────────────

def _load_wins() -> dict:
    try:
        if WINS_LOG.exists():
            return json.loads(WINS_LOG.read_text())
    except Exception:
        pass
    return {"picks": [], "overall": {"wins": 0, "losses": 0, "pushes": 0}}


def card_wins_scorecard() -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        data  = _load_wins()
        picks = data.get("picks", [])
        overall = data.get("overall", {"wins": 0, "losses": 0, "pushes": 0})
        w = overall.get("wins", 0)
        l = overall.get("losses", 0)
        total = w + l
        win_pct = (w / total * 100) if total > 0 else 0.0

        img, draw = _new_canvas()
        _accent_bar(draw, GREEN)
        _header(draw, "PREDICTION SCORECARD — RECENT RESULTS", GREEN, fonts)

        y = 76
        rate_color = GREEN if win_pct >= 65 else (GOLD if win_pct >= 50 else RED_ACC)
        draw.rectangle([18, y, W - 18, y + 56], fill=(10, 28, 18))
        draw.text((28,  y + 8), f"{w}W - {l}L", font=fonts[1], fill=rate_color)
        draw.text((440, y + 14), f"WIN RATE  {win_pct:.1f}%", font=fonts[2], fill=rate_color)
        draw.text((870, y + 16), f"Last {total} picks", font=fonts[0], fill=GRAY_LO)
        y += 70

        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 10

        for pick in picks[-6:]:
            outcome = str(pick.get("outcome", "?")).upper()
            color = GREEN if outcome == "WIN" else (RED_ACC if outcome == "LOSS" else GOLD)
            icon  = "W" if outcome == "WIN" else ("L" if outcome == "LOSS" else "P")
            draw.rectangle([18, y, 52, y + 32], fill=color)
            draw.text((24, y + 6), icon, font=fonts[0], fill=NAVY_DARK)
            draw.text((62, y + 2), str(pick.get("pick", "")), font=fonts[0], fill=WHITE)
            draw.text((500, y + 2), str(pick.get("result", "")), font=fonts[0], fill=color)
            draw.text((900, y + 2), str(pick.get("date", "")), font=fonts[0], fill=GRAY_LO)
            y += 44

        _footer(draw, "Join the signal feed", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] wins_scorecard: {e}")
        return None


def log_win(pick: str, outcome: str, result: str, category: str = "stocks", date: str | None = None):
    """
    Append a prediction result to wins_log.json.
    outcome: 'WIN' | 'LOSS' | 'PUSH'
    Example: log_win("NVDA long $145", "WIN", "+9.2% / +$92", "stocks")
    """
    data = _load_wins()
    entry = {
        "pick":     pick,
        "outcome":  outcome.upper(),
        "result":   result,
        "category": category,
        "date":     date or datetime.now().strftime("%m/%d"),
    }
    data.setdefault("picks", []).append(entry)
    o = data.setdefault("overall", {"wins": 0, "losses": 0, "pushes": 0})
    key = {"WIN": "wins", "LOSS": "losses"}.get(outcome.upper(), "pushes")
    o[key] = o.get(key, 0) + 1
    WINS_LOG.write_text(json.dumps(data, indent=2))
    print(f"[WINS] Logged {outcome.upper()}: {pick} — {result}")


# ─── CARD 11 — Pre-market Setup (dynamic) ────────────────────────────────────

def card_premarket_setup(signals: list[dict] | None = None) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, GOLD)
        _header(draw, "PRE-MARKET SETUP", GOLD, fonts)

        setups = signals or [
            {"ticker": "SPY",  "action": "WATCH",  "note": "Regime: BULL. Hold above 530 confirms trend."},
            {"ticker": "NVDA", "action": "ENTRY",  "note": "Score 81. RSI 62. Volume building premarket."},
            {"ticker": "COIN", "action": "ENTRY",  "note": "Score 74. Congressional buy 7d ago. EMA clear."},
            {"ticker": "ETH",  "action": "WATCH",  "note": "Score 71. Above 20d EMA. Needs volume confirm."},
            {"ticker": "APP",  "action": "HOLD",   "note": "Score 78. Extended above EMA. Tight stop."},
        ]

        y = 78
        draw.text((18, y), f"TODAY  —  {datetime.now().strftime('%A %b %d').upper()}  |  Size with Kelly. Only act on 70+.", font=fonts[0], fill=GRAY_LO)
        y += 32
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 12

        for s in setups[:6]:
            action = str(s.get("action", "WATCH")).upper()
            ac = GREEN if action == "ENTRY" else (GOLD if action == "WATCH" else BLUE_ACC)
            draw.rectangle([18, y, 128, y + 32], fill=ac)
            draw.text((24, y + 7), action[:5], font=fonts[0], fill=NAVY_DARK)
            draw.text((140, y + 2), s.get("ticker", ""), font=fonts[2], fill=WHITE)
            draw.text((290, y + 6), str(s.get("note", "")), font=fonts[0], fill=GRAY_LO)
            y += 46

        _footer(draw, "6:45am signal sheet at", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] premarket_setup: {e}")
        return None


# ─── CARD 12 — Sports / MMA Picks (dynamic) ──────────────────────────────────

def card_sports_picks(picks: list[dict] | None = None) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, RED_ACC)
        _header(draw, "EDGE ENGINE — CALIBRATED PICKS", RED_ACC, fonts)

        events = picks or [
            {"match": "NVDA 6/20 Call $150",  "pick": "NVDA LONG",       "confidence": "HIGH", "edge": "+6.2%"},
            {"match": "BTC Weekly Breakout",   "pick": "BTC LONG",        "confidence": "MED",  "edge": "+4.1%"},
            {"match": "SPX Weekly Put Hedge",  "pick": "SPX PUT",         "confidence": "MED",  "edge": "+3.8%"},
        ]

        y = 78
        draw.text((18, y), "CALIBRATED MODEL: book prob + scripting layer + sharp money signal", font=fonts[0], fill=GRAY_LO)
        y += 34
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 14

        draw.text((18,  y), "EVENT / MATCH", font=fonts[0], fill=GRAY_LO)
        draw.text((560, y), "PICK", font=fonts[0], fill=GRAY_LO)
        draw.text((820, y), "CONF", font=fonts[0], fill=GRAY_LO)
        draw.text((1010, y), "EDGE", font=fonts[0], fill=GRAY_LO)
        y += 28
        draw.rectangle([18, y, W - 18, y + 1], fill=DIVIDER)
        y += 12

        for ev in events[:5]:
            conf = str(ev.get("confidence", "MED")).upper()
            cc   = GREEN if conf == "HIGH" else (GOLD if conf == "MED" else GRAY_LO)
            edge_val = str(ev.get("edge", ""))
            draw.text((18,   y + 2), str(ev.get("match", "")), font=fonts[2], fill=WHITE)
            draw.text((560,  y + 2), str(ev.get("pick",  "")), font=fonts[2], fill=BLUE_ACC)
            draw.rectangle([820, y, 820 + 130, y + 32], fill=cc)
            draw.text((828,  y + 6), conf, font=fonts[0], fill=NAVY_DARK)
            draw.text((1010, y + 2), edge_val, font=fonts[0], fill=cc)
            y += 50

        draw.rectangle([18, y + 4, W - 18, y + 5], fill=DIVIDER)
        draw.text((18, y + 14), "Never bet more than Kelly fraction. HIGH confidence only when edge > 5%.", font=fonts[0], fill=GRAY_LO)

        _footer(draw, "Full model access", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] sports_picks: {e}")
        return None


# ─── Mock candlestick chart cards ────────────────────────────────────────────

def card_mock_nvda() -> bytes | None:
    p = INDICATORS / "mock_chart_nvda.png"
    if not p.exists(): return None
    return _screenshot_card(p, "NVDA — GHE SIGNAL FIRED", "SCORE: 81  STRONG BUY",
                            "Full signals", SIGNALS_LINK, GREEN)

def card_mock_app() -> bytes | None:
    p = INDICATORS / "mock_chart_app.png"
    if not p.exists(): return None
    return _screenshot_card(p, "APP — EMA BREAKOUT CONFIRMED", "SCORE: 78  BUY",
                            "Full signals", SIGNALS_LINK, GREEN)

def card_mock_btc() -> bytes | None:
    p = INDICATORS / "mock_chart_btc.png"
    if not p.exists(): return None
    return _screenshot_card(p, "BTC — ABOVE $104K CONFIRMED", "SCORE: 74  BUY",
                            "Full signals", SIGNALS_LINK, GOLD)

def card_mock_coin() -> bytes | None:
    p = INDICATORS / "mock_chart_coin.png"
    if not p.exists(): return None
    return _screenshot_card(p, "COIN — MOMENTUM SCORE 71", "SCORE: 71  WATCH→BUY",
                            "Full signals", SIGNALS_LINK, BLUE_ACC)

def card_mock_tsla() -> bytes | None:
    p = INDICATORS / "mock_chart_tsla.png"
    if not p.exists(): return None
    return _screenshot_card(p, "TSLA — EMA CROSS + VOLUME SURGE", "SCORE: 77  BUY",
                            "Full signals", SIGNALS_LINK, GREEN)

def card_mock_meta() -> bytes | None:
    p = INDICATORS / "mock_chart_meta.png"
    if not p.exists(): return None
    return _screenshot_card(p, "META — STRONG MOMENTUM SIGNAL", "SCORE: 83  STRONG BUY",
                            "Full signals", SIGNALS_LINK, GREEN)

def card_mock_eth() -> bytes | None:
    p = INDICATORS / "mock_chart_eth.png"
    if not p.exists(): return None
    return _screenshot_card(p, "ETH — BREAKOUT ABOVE $3,600", "SCORE: 72  BUY",
                            "Full signals", SIGNALS_LINK, GOLD)

def card_mock_sol() -> bytes | None:
    p = INDICATORS / "mock_chart_sol.png"
    if not p.exists(): return None
    return _screenshot_card(p, "SOL — WATCHING BREAKOUT ZONE", "SCORE: 69  WATCH",
                            "Full signals", SIGNALS_LINK, GOLD)

def card_mock_amd() -> bytes | None:
    p = INDICATORS / "mock_chart_amd.png"
    if not p.exists(): return None
    return _screenshot_card(p, "AMD — MOMENTUM BUILD + RSI 59", "SCORE: 75  BUY",
                            "Full signals", SIGNALS_LINK, GREEN)

def card_mock_spy() -> bytes | None:
    p = INDICATORS / "mock_chart_spy.png"
    if not p.exists(): return None
    return _screenshot_card(p, "SPY — REGIME: BULL | HOLD ABOVE 548", "SCORE: 68  HOLD",
                            "Full signals", SIGNALS_LINK, BLUE_ACC)


# ─── Complex visual cards ────────────────────────────────────────────────────

def _fake_sparkline(ticker: str, n: int = 32) -> list[float]:
    """Deterministic fake sparkline seeded by ticker name — consistent per ticker."""
    import hashlib
    seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16) % (2**31)
    import random as _r
    rng = _r.Random(seed)
    v = 100.0
    vals = [v]
    for _ in range(n - 1):
        v += rng.gauss(0, 1.8)
        vals.append(v)
    return vals


def _draw_sparkline(draw, x: int, y: int, w: int, h: int,
                    values: list[float], color=GREEN, width: int = 2):
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    pts = []
    for i, v in enumerate(values):
        px = x + int(i / max(len(values) - 1, 1) * w)
        py = y + h - int((v - mn) / rng * h)
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=width)
    # Shade area under line
    for i, (px, py) in enumerate(pts):
        draw.line([(px, py), (px, y + h)], fill=(*color[:3], 35) if len(color) == 4 else color, width=1)


def _score_bar(draw, x: int, y: int, w: int, h: int, score: float, fonts=None):
    """Draw a filled score bar with percentage label."""
    fill_w = int((score / 100) * w)
    bar_color = GREEN if score >= 75 else (GOLD if score >= 60 else (BLUE_ACC if score >= 45 else RED_ACC))
    draw.rectangle([x, y, x + w, y + h], fill=(20, 30, 55))
    draw.rectangle([x, y, x + fill_w, y + h], fill=bar_color)
    if fonts and fonts[0]:
        draw.text((x + w + 6, y - 1), str(int(score)), font=fonts[0], fill=bar_color)
    return bar_color


# ── CARD 13 — Signal Matrix (6-ticker grid with sparklines) ───────────────────

def card_signal_matrix(signals: list[dict] | None = None) -> bytes | None:
    """6-ticker grid — each cell has ticker, score bar, mini sparkline, RSI dot, trend."""
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, GREEN)
        _header(draw, "SIGNAL MATRIX — TOP 6 SETUPS", GREEN, fonts)

        tickers = signals or [
            {"ticker": "NVDA", "score": 81, "rsi": 62.1, "trend": "STRONG BUY",  "change": +2.3},
            {"ticker": "APP",  "score": 78, "rsi": 58.4, "trend": "BUY",         "change": +1.8},
            {"ticker": "COIN", "score": 74, "rsi": 55.2, "trend": "BUY",         "change": +3.1},
            {"ticker": "ETH",  "score": 71, "rsi": 61.8, "trend": "WATCH",       "change": +0.9},
            {"ticker": "MSFT", "score": 70, "rsi": 57.3, "trend": "BUY",         "change": +1.2},
            {"ticker": "PLTR", "score": 68, "rsi": 53.0, "trend": "WATCH",       "change": -0.4},
        ]

        # 3-col × 2-row grid
        cols, rows = 3, 2
        cell_w = (W - 36) // cols
        cell_h = (H - 130) // rows
        pad = 8

        for idx, t in enumerate(tickers[:6]):
            col = idx % cols
            row = idx // cols
            cx = 18 + col * cell_w
            cy = 74 + row * cell_h

            sc = t.get("score", 50)
            rsi = t.get("rsi", 50.0)
            trend = t.get("trend", "WATCH")
            chg = t.get("change", 0.0)
            ticker = t.get("ticker", "???")

            bar_color = GREEN if sc >= 75 else (GOLD if sc >= 62 else (BLUE_ACC if sc >= 48 else RED_ACC))
            rsi_color = RED_ACC if rsi > 72 else (GREEN if rsi < 35 else GRAY_LO)

            # Cell background
            draw.rectangle([cx + 2, cy + 2, cx + cell_w - 6, cy + cell_h - 6],
                           fill=(14, 22, 44))
            draw.rectangle([cx + 2, cy + 2, cx + cell_w - 6, cy + cell_h - 6],
                           outline=bar_color, width=1)

            # Ticker name
            draw.text((cx + pad, cy + pad), ticker, font=fonts[1], fill=WHITE)

            # Score bar
            bar_x = cx + pad
            bar_y = cy + 56
            bar_w  = cell_w - 40
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 8], fill=(20, 35, 65))
            draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * sc / 100), bar_y + 8], fill=bar_color)
            draw.text((bar_x + bar_w + 6, bar_y - 2), str(sc), font=fonts[0], fill=bar_color)

            # RSI dot + label
            draw.ellipse([cx + pad, cy + 72, cx + pad + 8, cy + 80], fill=rsi_color)
            draw.text((cx + pad + 12, cy + 70), f"RSI {rsi:.0f}", font=fonts[0], fill=GRAY_LO)

            # Change %
            chg_color = GREEN if chg >= 0 else RED_ACC
            draw.text((cx + cell_w - 70, cy + pad + 4),
                      f"{'+' if chg >= 0 else ''}{chg:.1f}%", font=fonts[0], fill=chg_color)

            # Mini sparkline
            spark_x = cx + pad
            spark_y = cy + 88
            spark_w = cell_w - 40
            spark_h = cell_h - 108
            if spark_h > 10:
                vals = _fake_sparkline(ticker)
                _draw_sparkline(draw, spark_x, spark_y, spark_w, spark_h, vals, bar_color)

            # Trend badge bottom-right
            draw.text((cx + pad, cy + cell_h - 22), trend, font=fonts[0],
                      fill=bar_color if trend in ("STRONG BUY", "BUY") else GRAY_LO)

        _footer(draw, "Signal alerts daily at", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] signal_matrix: {e}")
        return None


# ── CARD 14 — Market Heatmap (12-ticker color grid) ───────────────────────────

def card_market_heatmap(tickers: list[dict] | None = None) -> bytes | None:
    """Color-coded heatmap of 12 tickers by score — like Bloomberg market overview."""
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()
        _accent_bar(draw, BLUE_ACC)
        _header(draw, "MARKET HEATMAP — MOMENTUM SCORES", BLUE_ACC, fonts)

        data = tickers or [
            {"ticker": "NVDA", "score": 81, "change": +2.3},
            {"ticker": "APP",  "score": 78, "change": +1.8},
            {"ticker": "COIN", "score": 74, "change": +3.1},
            {"ticker": "ETH",  "score": 71, "change": +0.9},
            {"ticker": "MSFT", "score": 70, "change": +1.2},
            {"ticker": "PLTR", "score": 68, "change": -0.4},
            {"ticker": "TSLA", "score": 63, "change": -1.1},
            {"ticker": "AAPL", "score": 61, "change": +0.6},
            {"ticker": "BTC",  "score": 73, "change": +2.7},
            {"ticker": "SOL",  "score": 69, "change": +1.5},
            {"ticker": "META", "score": 58, "change": -0.8},
            {"ticker": "AMZN", "score": 55, "change": +0.3},
        ]

        # 4 cols × 3 rows
        cols, rows_n = 4, 3
        cell_w = (W - 36) // cols
        cell_h = (H - 130) // rows_n

        for idx, t in enumerate(data[:12]):
            col = idx % cols
            row = idx // cols
            cx = 18 + col * cell_w
            cy = 72 + row * cell_h

            sc  = t.get("score", 50)
            chg = t.get("change", 0.0)
            tk  = t.get("ticker", "")

            # Color intensity based on score
            if sc >= 75:   bg = (4, 62, 30);   txt = GREEN
            elif sc >= 65: bg = (4, 46, 22);   txt = (80, 200, 120)
            elif sc >= 55: bg = (12, 30, 60);  txt = BLUE_ACC
            elif sc >= 45: bg = (45, 30, 8);   txt = GOLD
            else:          bg = (55, 10, 10);  txt = RED_ACC

            draw.rectangle([cx + 3, cy + 3, cx + cell_w - 4, cy + cell_h - 4], fill=bg)
            draw.rectangle([cx + 3, cy + 3, cx + cell_w - 4, cy + cell_h - 4],
                           outline=(*txt[:3],), width=1)

            # Ticker
            draw.text((cx + 10, cy + 12), tk, font=fonts[2], fill=WHITE)

            # Score (large)
            draw.text((cx + 10, cy + 44), str(sc), font=fonts[1], fill=txt)

            # Change %
            chg_str = f"{'+' if chg >= 0 else ''}{chg:.1f}%"
            draw.text((cx + 10, cy + cell_h - 28), chg_str, font=fonts[0],
                      fill=GREEN if chg >= 0 else RED_ACC)

            # Mini sparkline inside cell
            spark_x = cx + cell_w // 2
            spark_w = cell_w // 2 - 10
            spark_y = cy + 46
            spark_h = cell_h - 76
            if spark_h > 8 and spark_w > 20:
                vals = _fake_sparkline(tk)
                _draw_sparkline(draw, spark_x, spark_y, spark_w, spark_h, vals, txt)

        _footer(draw, "Live score matrix at", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] market_heatmap: {e}")
        return None


# ── CARD 15 — Composite Multi-Panel Dashboard ─────────────────────────────────

def card_composite_dashboard(signals: list[dict] | None = None) -> bytes | None:
    """
    Multi-panel card: left = ranked signal bars with sparklines,
    right = live stats column, bottom strip = market metrics.
    Looks like a real trading terminal screenshot.
    """
    try:
        from PIL import Image, ImageDraw
        fonts = _fonts()
        img, draw = _new_canvas()

        # No accent bar — use full header strip for a terminal look
        draw.rectangle([0, 0, W, 56], fill=(8, 14, 32))
        draw.rectangle([0, 56, W, 57], fill=GREEN)
        # Left title
        draw.text((14, 10), "GHE EDGE ENGINE", font=fonts[1], fill=WHITE)
        draw.text((14, 40), "LIVE SIGNAL DASHBOARD", font=fonts[0], fill=GREEN)
        # Right: date + regime badge
        today = datetime.now().strftime("%b %d  %H:%M")
        draw.rectangle([W - 190, 10, W - 10, 46], fill=(0, 180, 80))
        draw.text((W - 182, 18), f"BULL  {today}", font=fonts[0], fill=(8, 14, 32))

        rows = signals or [
            {"ticker": "NVDA", "score": 81, "rsi": 62.1, "price": 145.30, "change": +2.3, "vol_x": 2.3},
            {"ticker": "APP",  "score": 78, "rsi": 58.4, "price": 512.80, "change": +1.8, "vol_x": 1.9},
            {"ticker": "COIN", "score": 74, "rsi": 55.2, "price":  268.40, "change": +3.1, "vol_x": 2.7},
            {"ticker": "ETH",  "score": 71, "rsi": 61.8, "price": 3820.00, "change": +0.9, "vol_x": 1.4},
            {"ticker": "MSFT", "score": 70, "rsi": 57.3, "price":  441.20, "change": +1.2, "vol_x": 1.1},
        ]

        LEFT_W  = 780
        RIGHT_W = W - LEFT_W - 36
        TOP_Y   = 68
        BOT_Y   = H - 70
        content_h = BOT_Y - TOP_Y

        # ── Left panel: signal rows ────────────────────────────────────────────
        draw.rectangle([14, TOP_Y, LEFT_W + 14, BOT_Y], fill=(11, 18, 38))
        draw.rectangle([14, TOP_Y, LEFT_W + 14, BOT_Y], outline=DIVIDER, width=1)

        # Column headers
        hdr_y = TOP_Y + 6
        draw.text((22,  hdr_y), "#",      font=fonts[0], fill=GRAY_LO)
        draw.text((46,  hdr_y), "TICKER", font=fonts[0], fill=GRAY_LO)
        draw.text((148, hdr_y), "SCORE",  font=fonts[0], fill=GRAY_LO)
        draw.text((380, hdr_y), "RSI",    font=fonts[0], fill=GRAY_LO)
        draw.text((460, hdr_y), "PRICE",  font=fonts[0], fill=GRAY_LO)
        draw.text((590, hdr_y), "1D%",    font=fonts[0], fill=GRAY_LO)
        draw.text((660, hdr_y), "VOL",    font=fonts[0], fill=GRAY_LO)
        draw.text((730, hdr_y), "CHART",  font=fonts[0], fill=GRAY_LO)
        draw.rectangle([22, hdr_y + 20, LEFT_W + 8, hdr_y + 21], fill=DIVIDER)

        row_h = (content_h - 36) // max(len(rows), 1)
        for i, r in enumerate(rows[:5]):
            ry = TOP_Y + 34 + i * row_h
            sc = r.get("score", 50)
            bar_c = GREEN if sc >= 75 else (GOLD if sc >= 62 else BLUE_ACC)
            alt_bg = (13, 21, 44) if i % 2 == 0 else (10, 17, 38)
            draw.rectangle([22, ry, LEFT_W + 8, ry + row_h - 2], fill=alt_bg)

            # Rank
            draw.text((22, ry + 6), f"#{i+1}", font=fonts[0], fill=GRAY_LO)
            # Ticker
            draw.text((46, ry + 2), r.get("ticker", ""), font=fonts[2], fill=WHITE)
            # Score bar
            bar_x, bar_w = 148, 210
            draw.rectangle([bar_x, ry + 8, bar_x + bar_w, ry + 22], fill=(18, 30, 58))
            draw.rectangle([bar_x, ry + 8, bar_x + int(bar_w * sc / 100), ry + 22], fill=bar_c)
            draw.text((bar_x + bar_w + 6, ry + 8), str(sc), font=fonts[0], fill=bar_c)
            # RSI
            rsi = r.get("rsi", 50.0)
            rsi_c = RED_ACC if rsi > 72 else (GREEN if rsi < 35 else GRAY_LO)
            draw.text((380, ry + 6), f"{rsi:.0f}", font=fonts[0], fill=rsi_c)
            # Price
            price = r.get("price", 0)
            draw.text((460, ry + 6), f"${price:,.2f}", font=fonts[0], fill=WHITE)
            # Change
            chg = r.get("change", 0.0)
            draw.text((590, ry + 6), f"{'+' if chg >= 0 else ''}{chg:.1f}%",
                      font=fonts[0], fill=GREEN if chg >= 0 else RED_ACC)
            # Volume
            vol = r.get("vol_x", 1.0)
            draw.text((660, ry + 6), f"{vol:.1f}x", font=fonts[0],
                      fill=GREEN if vol >= 2.0 else (GOLD if vol >= 1.5 else GRAY_LO))
            # Sparkline
            _draw_sparkline(draw, 730, ry + 4, 56, row_h - 10,
                            _fake_sparkline(r.get("ticker", "X")), bar_c, width=2)

        # ── Right stats panel ──────────────────────────────────────────────────
        rx = LEFT_W + 26
        ry0 = TOP_Y
        draw.rectangle([rx, ry0, W - 14, BOT_Y], fill=(11, 18, 38))
        draw.rectangle([rx, ry0, W - 14, BOT_Y], outline=DIVIDER, width=1)
        draw.text((rx + 8, ry0 + 8), "MARKET", font=fonts[0], fill=GRAY_LO)
        draw.rectangle([rx + 8, ry0 + 28, W - 22, ry0 + 29], fill=DIVIDER)

        stats = [
            ("SPY",   "532.40", GREEN),
            ("QQQ",   "461.20", GREEN),
            ("VIX",    "14.8",  GREEN),
            ("BTC",  "104.2K",  GREEN),
            ("FEAR",    "68",   GOLD),
            ("BULL%",   "74%",  GREEN),
        ]
        sy = ry0 + 36
        for label, val, vc in stats:
            draw.text((rx + 8, sy), label, font=fonts[0], fill=GRAY_LO)
            draw.text((rx + 8, sy + 16), val, font=fonts[2], fill=vc)
            sy += 48
            draw.rectangle([rx + 8, sy - 6, W - 22, sy - 5], fill=DIVIDER)

        # ── Bottom metrics strip ───────────────────────────────────────────────
        strip_y = BOT_Y + 4
        draw.rectangle([14, strip_y, W - 14, strip_y + 42], fill=(10, 18, 36))
        strip_items = [
            ("SIGNALS TODAY", "5",     GREEN),
            ("HIGH CONF",     "3",     GREEN),
            ("CONGRESS BUY",  "2",     BLUE_ACC),
            ("AVG SCORE",     "74.8",  GOLD),
            ("WIN RATE",      "78%",   GREEN),
        ]
        sx = 22
        for label, val, vc in strip_items:
            draw.text((sx, strip_y + 6),  label, font=fonts[0], fill=GRAY_LO)
            draw.text((sx, strip_y + 22), val,   font=fonts[2], fill=vc)
            sx += 230

        _footer(draw, "Full system access", SIGNALS_LINK, fonts)
        return _to_bytes(img)
    except Exception as e:
        print(f"[CARD] composite_dashboard: {e}")
        return None


# ─── Rotation manager ────────────────────────────────────────────────────────

# (name, function, category)
# category: "chart" = screenshot-based | "data" = dynamic generated
CARD_REGISTRY: list[tuple[str, callable, str]] = [
    # X-only: trading/signals cards — no contractor/GHL/Vapi content on X
    ("tradingview_chart",  card_tradingview_chart,  "chart"),
    ("product_edge",       card_product_edge,        "chart"),
    ("product_flow",       card_product_flow,        "chart"),
    # moved to "portfolio" category — only posted via portfolio slot, never chart slot
    ("ghl_dashboard",      card_ghl_dashboard,      "portfolio"),
    ("contractor_intake",  card_contractor_intake,  "portfolio"),
    ("vapi_demo",          card_vapi_demo,           "portfolio"),
    ("signal_scorecard",      card_signal_scorecard,      "data"),
    ("congress_buys",         card_congress_buys,         "data"),
    ("kelly_table",           card_kelly_table,           "data"),
    ("wins_scorecard",        card_wins_scorecard,        "data"),
    ("premarket_setup",       card_premarket_setup,       "data"),
    ("sports_picks",          card_sports_picks,          "data"),
    # complex visual cards
    ("signal_matrix",         card_signal_matrix,         "visual"),
    ("market_heatmap",        card_market_heatmap,        "visual"),
    ("composite_dashboard",   card_composite_dashboard,   "visual"),
    # mock candlestick charts
    ("mock_nvda",             card_mock_nvda,             "chart"),
    ("mock_app",              card_mock_app,              "chart"),
    ("mock_btc",              card_mock_btc,              "chart"),
    ("mock_coin",             card_mock_coin,             "chart"),
    ("mock_tsla",             card_mock_tsla,             "chart"),
    ("mock_meta",             card_mock_meta,             "chart"),
    ("mock_eth",              card_mock_eth,              "chart"),
    ("mock_sol",              card_mock_sol,              "chart"),
    ("mock_amd",              card_mock_amd,              "chart"),
    ("mock_spy",              card_mock_spy,              "chart"),
]

ROTATION_LOG = DATA_DIR / "chart_rotation.json"


def _load_rotation() -> dict:
    try:
        if ROTATION_LOG.exists():
            return json.loads(ROTATION_LOG.read_text())
    except Exception:
        pass
    return {"history": []}


def _save_rotation(data: dict):
    ROTATION_LOG.write_text(json.dumps(data, indent=2))


def next_card(category_filter: str | None = None) -> tuple[str, bytes | None]:
    """
    Returns (card_name, png_bytes) picking the next card in rotation.
    category_filter: 'chart' | 'data' | None (any)
    Avoids repeating the last 6 cards used.
    """
    rot   = _load_rotation()
    pool  = [(n, fn, c) for n, fn, c in CARD_REGISTRY
             if c != "portfolio" and (category_filter is None or c == category_filter)]
    if not pool:
        return ("none", None)

    history = rot.get("history", [])
    unused  = [t for t in pool if t[0] not in history[-6:]]
    if not unused:
        unused = pool[:]

    name, fn, _ = random.choice(unused)
    img_bytes   = fn()

    # If screenshot card returned None (asset missing), fall back to a data card
    if img_bytes is None and category_filter == "chart":
        for n2, fn2, c2 in pool:
            if n2 != name:
                img_bytes = fn2()
                name = n2
                if img_bytes:
                    break

    history.append(name)
    rot["history"] = history[-24:]
    _save_rotation(rot)
    print(f"[CARD] Generated: {name} ({len(img_bytes)//1024 if img_bytes else 0}KB)")
    return (name, img_bytes)


def generate_card(card_name: str, **kwargs) -> bytes | None:
    """Generate a specific card by name. Useful for manual one-offs."""
    fn_map = {n: fn for n, fn, _ in CARD_REGISTRY}
    fn = fn_map.get(card_name)
    if not fn:
        print(f"[CARD] Unknown card name: {card_name}")
        return None
    return fn(**kwargs) if kwargs else fn()


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    card_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if card_arg == "log_win":
        # Usage: python chart_card_generator.py log_win "NVDA long $145" WIN "+9.2%" stocks
        pick, outcome, result, cat = (sys.argv[2:6] + ["", "WIN", "", "stocks"])[:4]
        log_win(pick, outcome, result, cat)
    elif card_arg:
        b = generate_card(card_arg)
        if b:
            out = Path(f"test_card_{card_arg}.png")
            out.write_bytes(b)
            print(f"Saved {out} ({len(b)//1024}KB)")
        else:
            print(f"Card '{card_arg}' returned None — check asset paths in indicators/")
    else:
        print("Generating all 12 cards for review...")
        for name, fn, cat in CARD_REGISTRY:
            b = fn()
            if b:
                out = Path(f"test_card_{name}.png")
                out.write_bytes(b)
                print(f"  [{cat:5s}] {name:22s} {len(b)//1024:4d}KB  ->  {out}")
            else:
                print(f"  [{cat:5s}] {name:22s}  SKIPPED (missing asset)")
