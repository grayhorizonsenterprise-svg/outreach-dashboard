"""
generate_chart_cards.py — Gray Horizons Enterprise
Generates rotating Edge Engine chart cards for X posts.
5 card styles × multiple tickers × rotating hooks = always fresh content.

Output: indicators/cards/  (1200x628 PNGs, X-optimized)

Styles:
  1. Signal Alert    — breaking news style, big score, entry/stop/target
  2. Volume Spike    — anomaly detection focus, before/after volume bar
  3. Congressional   — senator/rep tracking style, dark theme
  4. Setup Matrix    — multi-ticker ranked table
  5. Flow Indicator  — institutional vs retail timing gap

Run daily from run_all_engines.py — generates 3 fresh cards per run.
"""

import os, random, hashlib, math, sys
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Run: pip install Pillow")
    exit(1)

OUT_DIR = Path(__file__).parent / "indicators" / "cards"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1200, 628

# ── Palette ────────────────────────────────────────────────────────────────────
BG          = (11, 15, 25)
BG_PANEL    = (18, 24, 40)
BG_CARD     = (24, 31, 52)
GREEN       = (0, 200, 110)
GREEN_DIM   = (0, 140, 80)
RED         = (220, 60, 60)
GOLD        = (230, 175, 0)
GOLD_DIM    = (160, 120, 0)
BLUE        = (56, 140, 255)
BLUE_DIM    = (30, 80, 160)
WHITE       = (255, 255, 255)
TEXT        = (210, 215, 228)
DIM         = (100, 110, 135)
DIVIDER     = (35, 44, 68)
ACCENT      = (0, 180, 255)

TICKERS = [
    ("NVDA",  "NVIDIA",              892.0,  81, "STRONG BUY",  63, 2.4, "875-885",  "850",  "940",  "+7.2%"),
    ("APP",   "Applovin",            310.0,  78, "BUY",         58, 1.9, "302-308",  "290",  "335",  "+8.1%"),
    ("META",  "Meta Platforms",      598.0,  83, "STRONG BUY",  65, 2.6, "588-595",  "570",  "635",  "+6.5%"),
    ("TSLA",  "Tesla",               298.0,  77, "BUY",         60, 2.2, "290-296",  "278",  "325",  "+9.1%"),
    ("AMD",   "AMD",                 152.0,  75, "BUY",         59, 2.0, "148-152",  "140",  "168",  "+10.5%"),
    ("BTC",   "Bitcoin",          104200.0,  74, "BUY",         61, 2.1, "101K-103K","97K",  "112K", "+7.7%"),
    ("COIN",  "Coinbase",            238.0,  71, "WATCH->BUY",  55, 1.7, "232-238",  "220",  "260",  "+9.2%"),
    ("PLTR",  "Palantir",             28.0,  79, "BUY",         62, 2.3, "27.2-28",  "25.5", "32",   "+14.3%"),
    ("MSTR",  "MicroStrategy",       180.0,  76, "BUY",         58, 2.1, "175-180",  "165",  "200",  "+11.1%"),
    ("SPY",   "S&P 500 ETF",         552.0,  68, "HOLD/WATCH",  54, 1.5, "548-552",  "538",  "570",  "+3.3%"),
    ("QQQ",   "Nasdaq 100 ETF",      472.0,  72, "BUY",         57, 1.8, "467-472",  "455",  "495",  "+4.9%"),
    ("AAPL",  "Apple",               198.0,  70, "WATCH",       53, 1.6, "194-198",  "185",  "210",  "+6.1%"),
    ("MSFT",  "Microsoft",           445.0,  74, "BUY",         60, 1.9, "440-446",  "425",  "470",  "+5.6%"),
    ("ETH",   "Ethereum",           3620.0,  72, "BUY",         57, 1.8, "3550-3600","3380", "3900", "+7.7%"),
    ("SOL",   "Solana",              172.0,  69, "WATCH",       52, 1.6, "168-172",  "158",  "190",  "+10.5%"),
]

SIGNAL_HOOKS = [
    "Retail sees this 3 weeks after it already ran.",
    "The setup was there. Most missed it.",
    "Score locked in before the move.",
    "Volume confirmed before price moved.",
    "Institutional flow entered quietly.",
    "This is what the edge looks like before it prints.",
    "No hindsight. Score locked at bar close.",
    "The entry zone held. Target hit.",
    "Score above 70 means the setup is live.",
    "This ran. The system caught it first.",
]

VOLUME_HOOKS = [
    "Something moved before the news dropped.",
    "3x volume before the catalyst. Every time.",
    "Retail buys the breakout. Flow buys the buildup.",
    "The spike happened quietly. No one talked about it.",
    "Volume doesn't lie. Price follows.",
    "This is what unusual activity looks like before a move.",
    "Big money doesn't announce. They accumulate.",
]

CONGRESSIONAL_HOOKS = [
    "They traded. Then the law changed.",
    "Purchase disclosed. 45 days after the fact.",
    "Bought before the committee vote. Legal. Documented.",
    "Congressional buy flagged. Volume spike confirmed.",
    "Public servants. Private gains. All on record.",
    "The disclosure came out. The move already ran.",
    "They knew before you did. Now you know too.",
]

CONGRESSPEOPLE = [
    ("Rep. Nancy Pelosi", "D-CA", "NVDA Calls", "$1M-$5M", "Jan 17"),
    ("Sen. Tommy Tuberville", "R-AL", "META Puts", "$500K-$1M", "Feb 3"),
    ("Rep. Michael McCaul", "R-TX", "MSFT Calls", "$250K-$500K", "Mar 11"),
    ("Sen. Mark Warner", "D-VA", "PLTR Calls", "$100K-$250K", "Apr 2"),
    ("Rep. Dan Crenshaw", "R-TX", "AMD Calls", "$500K-$1M", "May 14"),
    ("Sen. Shelley Capito", "R-WV", "AAPL Stock", "$250K-$500K", "Jun 7"),
    ("Rep. Josh Gottheimer", "D-NJ", "BTC ETF", "$100K-$250K", "Jun 22"),
]


def _rng(seed_str: str) -> random.Random:
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % (2**31)
    return random.Random(seed)


def _load_fonts():
    candidates = [
        ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
        ("arialbd.ttf", "arial.ttf"),
    ]
    for bold_path, reg_path in candidates:
        try:
            return {
                "tiny":   ImageFont.truetype(bold_path, 13),
                "small":  ImageFont.truetype(reg_path,  17),
                "bold":   ImageFont.truetype(bold_path, 20),
                "head":   ImageFont.truetype(bold_path, 28),
                "ticker": ImageFont.truetype(bold_path, 38),
                "score":  ImageFont.truetype(bold_path, 56),
                "hero":   ImageFont.truetype(bold_path, 72),
            }
        except Exception:
            continue
    f = ImageFont.load_default()
    return {k: f for k in ("tiny","small","bold","head","ticker","score","hero")}


def _candles(rng, base, n=55):
    candles, price = [], base * rng.uniform(0.91, 0.95)
    trend = rng.gauss(0.0025, 0.001)
    for i in range(n):
        body = price * rng.uniform(0.003, 0.014)
        wick = price * rng.uniform(0.002, 0.008)
        move = price * (trend + rng.gauss(0, 0.007))
        o, c = price, price + move
        h = max(o, c) + abs(rng.gauss(0, wick))
        l = min(o, c) - abs(rng.gauss(0, wick))
        candles.append((o, h, l, c))
        price = c
        if i >= n - 12:
            trend = abs(trend) * 1.05
    return candles


def _ema(vals, period=20):
    k = 2 / (period + 1)
    e = [vals[0]]
    for v in vals[1:]:
        e.append(v * k + e[-1] * (1 - k))
    return e


def _draw_candles(draw, candles, x0, y0, cw, ch, rng):
    closes = [c[3] for c in candles]
    lo = min(c[2] for c in candles)
    hi = max(c[1] for c in candles)
    rng_price = hi - lo or 1

    def py(p): return y0 + ch - int((p - lo) / rng_price * ch)

    ema20 = _ema(closes)
    cw2 = max(3, cw // len(candles) - 1)
    gap = cw // len(candles)

    for i, (o, h, l, c) in enumerate(candles):
        cx = x0 + i * gap + gap // 2
        col = GREEN if c >= o else RED
        draw.line([(cx, py(l)), (cx, py(h))], fill=col, width=1)
        bx0 = cx - cw2 // 2
        by0, by1 = sorted([py(o), py(c)])
        draw.rectangle([bx0, by0, bx0 + cw2, max(by1, by0 + 1)], fill=col)

    # EMA line
    pts = [(x0 + i * gap + gap // 2, py(e)) for i, e in enumerate(ema20)]
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill=GOLD, width=2)

    # Entry zone band (last 8 candles)
    entry_y = py(closes[-1] * 0.995)
    draw.rectangle([x0 + cw - gap * 8, entry_y - 4, x0 + cw, entry_y + 4],
                   fill=(0, 200, 110, 60))


def _score_color(score):
    if score >= 80: return GREEN
    if score >= 70: return GOLD
    return BLUE


# ── STYLE 1: Signal Alert ─────────────────────────────────────────────────────
def make_signal_alert(ticker_data, hook, out_path):
    sym, name, price, score, action, rsi, vol, entry, stop, tgt, chg = ticker_data
    rng = _rng(sym + hook[:10])
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # Left panel
    draw.rectangle([0, 0, 420, H], fill=BG_PANEL)
    draw.rectangle([418, 0, 422, H], fill=DIVIDER)

    # Score circle
    sc = _score_color(score)
    cx, cy, r = 210, 160, 90
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=sc, width=4)
    draw.ellipse([cx-r+8, cy-r+8, cx+r-8, cy+r-8], fill=BG)
    s_txt = str(score)
    bb = draw.textbbox((0,0), s_txt, font=fonts["score"])
    sw, sh = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx - sw//2, cy - sh//2), s_txt, fill=sc, font=fonts["score"])
    draw.text((cx - 25, cy + r + 10), "SCORE", fill=sc, font=fonts["bold"])

    # Ticker + action
    draw.text((30, 270), sym, fill=WHITE, font=fonts["ticker"])
    draw.text((30, 315), name, fill=DIM, font=fonts["small"])
    ac_col = GREEN if "BUY" in action else (GOLD if "WATCH" in action else RED)
    draw.rectangle([28, 345, 28 + len(action)*13 + 12, 370], fill=ac_col)
    draw.text((34, 348), action, fill=(0,0,0), font=fonts["bold"])

    # Stats
    y = 395
    for label, val in [("ENTRY", entry), ("STOP", stop), ("TARGET", tgt), ("RSI", str(rsi)), ("VOL", f"{vol}×")]:
        draw.text((30, y), label, fill=DIM, font=fonts["tiny"])
        draw.text((110, y), val, fill=TEXT, font=fonts["bold"])
        y += 28

    draw.text((30, H-50), "GHE Edge Scanner  ·  ghe-indicators.com", fill=DIM, font=fonts["tiny"])

    # Right panel: chart
    candles = _candles(rng, price)
    _draw_candles(draw, candles, 440, 60, 730, 430, rng)

    # Hook text at bottom right
    words = hook.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bb = draw.textbbox((0,0), test, font=fonts["bold"])
        if bb[2]-bb[0] > 700 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur: lines.append(cur)

    y = H - 30 - len(lines) * 30
    for line in lines:
        draw.text((445, y), line, fill=TEXT, font=fonts["bold"])
        y += 30

    img.save(out_path, "PNG")


# ── STYLE 2: Volume Spike ─────────────────────────────────────────────────────
def make_volume_spike(ticker_data, hook, out_path):
    sym, name, price, score, action, rsi, vol, entry, stop, tgt, chg = ticker_data
    rng = _rng(sym + "vol")
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # Top bar
    draw.rectangle([0, 0, W, 80], fill=BG_PANEL)
    draw.text((30, 22), "VOLUME ANOMALY DETECTED", fill=GOLD, font=fonts["head"])
    draw.text((W-220, 22), datetime.now().strftime("%b %d, %Y"), fill=DIM, font=fonts["bold"])
    draw.rectangle([0, 78, W, 82], fill=DIVIDER)

    # Hero stat
    draw.text((50, 110), f"{vol}×", fill=GREEN, font=fonts["hero"])
    draw.text((50, 200), "normal volume", fill=DIM, font=fonts["head"])
    draw.text((50, 240), f"{sym}  ·  {name}", fill=WHITE, font=fonts["ticker"])

    # Volume bars
    bar_data = [rng.uniform(0.4, 1.2) for _ in range(28)] + [vol * 1.1, vol * 0.95]
    bar_x, bar_y = 460, 500
    bw = int(700 / len(bar_data)) - 2
    max_bar = max(bar_data)
    for i, b in enumerate(bar_data):
        bh = int(b / max_bar * 320)
        col = GREEN if i >= len(bar_data)-2 else DIM
        draw.rectangle([bar_x + i*(bw+2), bar_y - bh, bar_x + i*(bw+2) + bw, bar_y], fill=col)
    draw.text((bar_x, bar_y + 10), "← 30 sessions", fill=DIM, font=fonts["tiny"])
    draw.text((bar_x + 560, bar_y + 10), "SPIKE →", fill=GREEN, font=fonts["tiny"])

    # Hook
    draw.text((50, H-100), hook, fill=TEXT, font=fonts["head"])
    draw.text((50, H-55), "GHE Edge Scanner  ·  ghe-indicators.com", fill=DIM, font=fonts["tiny"])
    draw.rectangle([0, H-30, W, H], fill=BG_PANEL)

    img.save(out_path, "PNG")


# ── STYLE 3: Congressional Tracker ────────────────────────────────────────────
def make_congressional(congress_data, hook, out_path):
    person, party, trade, amount, date = congress_data
    rng = _rng(person)
    # Pick a ticker from the trade string
    sym = trade.split()[0]
    t = next((t for t in TICKERS if t[0]==sym), TICKERS[0])
    price, score = t[2], t[3]

    img = Image.new("RGB", (W, H), (8, 10, 20))
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # Header bar
    draw.rectangle([0, 0, W, 70], fill=(15, 20, 35))
    draw.text((30, 18), "CONGRESSIONAL TRADE DISCLOSURE", fill=GOLD, font=fonts["head"])
    draw.rectangle([0, 68, W, 72], fill=GOLD_DIM)

    # Main card
    draw.rectangle([30, 90, W-30, H-80], fill=BG_CARD, outline=DIVIDER, width=1)

    # Person
    draw.text((60, 115), person, fill=WHITE, font=fonts["ticker"])
    party_col = BLUE if party.startswith("D") else RED
    draw.rectangle([60, 158, 60+len(party)*14+10, 182], fill=party_col)
    draw.text((65, 160), party, fill=WHITE, font=fonts["bold"])

    # Trade details
    y = 210
    for label, val, col in [
        ("TRADE TYPE", trade, GREEN if "Calls" in trade or "Stock" in trade else RED),
        ("AMOUNT",     amount, GOLD),
        ("DISCLOSED",  date + " (45-day delay)", DIM),
    ]:
        draw.text((60, y), label, fill=DIM, font=fonts["tiny"])
        draw.text((250, y), val, fill=col, font=fonts["bold"])
        draw.line([(60, y+22), (W-60, y+22)], fill=DIVIDER, width=1)
        y += 40

    # Score panel
    sc = _score_color(score)
    draw.rectangle([W-280, 100, W-40, 280], fill=BG_PANEL, outline=sc, width=2)
    draw.text((W-240, 115), sym, fill=WHITE, font=fonts["ticker"])
    draw.text((W-230, 165), str(score), fill=sc, font=fonts["score"])
    draw.text((W-230, 230), "GHE SCORE", fill=sc, font=fonts["tiny"])

    # Hook
    words = hook.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bb = draw.textbbox((0,0), test, font=fonts["head"])
        if bb[2]-bb[0] > W-100 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur: lines.append(cur)
    y = H-75 - len(lines)*38
    for line in lines:
        draw.text((60, y), line, fill=TEXT, font=fonts["head"])
        y += 38

    draw.text((60, H-55), "GHE Congressional Tracker  ·  ghe-indicators.com", fill=DIM, font=fonts["tiny"])
    img.save(out_path, "PNG")


# ── STYLE 4: Setup Matrix (multi-ticker ranked) ───────────────────────────────
def make_setup_matrix(tickers_subset, out_path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    draw.rectangle([0, 0, W, 75], fill=BG_PANEL)
    draw.text((30, 18), "GHE EDGE SCANNER — LIVE SETUPS", fill=WHITE, font=fonts["head"])
    draw.text((W-300, 18), datetime.now().strftime("%b %d, %Y  %H:%M"), fill=DIM, font=fonts["bold"])
    draw.rectangle([0, 73, W, 77], fill=DIVIDER)

    headers = ["TICKER", "SCORE", "ACTION", "ENTRY", "STOP", "TARGET"]
    col_x = [30, 200, 330, 510, 670, 830]
    y = 95
    for i, h in enumerate(headers):
        draw.text((col_x[i], y), h, fill=DIM, font=fonts["tiny"])
    draw.line([(30, y+18), (W-30, y+18)], fill=DIVIDER, width=1)
    y += 28

    for sym, name, price, score, action, rsi, vol, entry, stop, tgt, chg in tickers_subset:
        sc = _score_color(score)
        ac_col = GREEN if "BUY" in action else (GOLD if "WATCH" in action else RED)
        row_bg = (22, 30, 48) if tickers_subset.index((sym, name, price, score, action, rsi, vol, entry, stop, tgt, chg)) % 2 == 0 else BG
        draw.rectangle([28, y-4, W-28, y+28], fill=row_bg)
        draw.text((col_x[0], y), sym, fill=WHITE, font=fonts["bold"])
        draw.text((col_x[1], y), str(score), fill=sc, font=fonts["bold"])
        draw.rectangle([col_x[2]-2, y, col_x[2]+len(action)*9+6, y+22], fill=ac_col)
        draw.text((col_x[2], y+2), action, fill=(0,0,0), font=fonts["tiny"])
        draw.text((col_x[3], y), entry, fill=TEXT, font=fonts["bold"])
        draw.text((col_x[4], y), stop, fill=RED, font=fonts["bold"])
        draw.text((col_x[5], y), tgt, fill=GREEN, font=fonts["bold"])
        y += 38

    draw.line([(30, y+5), (W-30, y+5)], fill=DIVIDER, width=1)
    draw.text((30, H-50), "Score above 70 = live setup  ·  GHE Edge Scanner  ·  ghe-indicators.com", fill=DIM, font=fonts["tiny"])
    img.save(out_path, "PNG")


# ── STYLE 5: Flow Indicator (institutional vs retail) ─────────────────────────
def make_flow_card(ticker_data, hook, out_path):
    sym, name, price, score, action, rsi, vol, entry, stop, tgt, chg = ticker_data
    rng = _rng(sym + "flow")
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # Header
    draw.rectangle([0, 0, W, 70], fill=BG_PANEL)
    draw.text((30, 18), "GHE INSTITUTIONAL FLOW INDICATOR", fill=ACCENT, font=fonts["head"])
    draw.rectangle([0, 68, W, 72], fill=ACCENT)

    # Split layout
    draw.rectangle([0, 72, W//2, H], fill=(12, 16, 30))
    draw.rectangle([W//2, 72, W, H], fill=(8, 12, 22))
    draw.line([(W//2, 72), (W//2, H)], fill=DIVIDER, width=2)

    draw.text((30, 90), "INSTITUTIONAL", fill=BLUE, font=fonts["head"])
    draw.text((30, 130), "Entered quietly.", fill=TEXT, font=fonts["bold"])
    inst_pct = rng.randint(62, 78)
    draw.text((30, 175), f"{inst_pct}%", fill=BLUE, font=fonts["hero"])
    draw.text((30, 265), "of float accumulated", fill=DIM, font=fonts["bold"])
    draw.text((30, 305), f"Before  +{chg}  move", fill=GREEN, font=fonts["bold"])

    draw.text((W//2 + 30, 90), "RETAIL", fill=RED, font=fonts["head"])
    draw.text((W//2 + 30, 130), "Bought the breakout.", fill=TEXT, font=fonts["bold"])
    retail_pct = 100 - inst_pct
    draw.text((W//2 + 30, 175), f"{retail_pct}%", fill=RED, font=fonts["hero"])
    draw.text((W//2 + 30, 265), "of volume = late buyers", fill=DIM, font=fonts["bold"])
    draw.text((W//2 + 30, 305), "After the move already ran", fill=RED, font=fonts["bold"])

    # Ticker at bottom
    draw.text((30, H-140), sym, fill=WHITE, font=fonts["ticker"])
    sc = _score_color(score)
    draw.text((200, H-135), f"Score {score}", fill=sc, font=fonts["bold"])

    # Hook
    draw.text((30, H-95), hook, fill=TEXT, font=fonts["head"])
    draw.text((30, H-50), "GHE Edge Scanner  ·  ghe-indicators.com", fill=DIM, font=fonts["tiny"])
    img.save(out_path, "PNG")


# ── Main: generate 3 fresh cards per run ──────────────────────────────────────
def run(count: int = 3):
    today = datetime.now().strftime("%Y%m%d")
    rng = _rng(today)

    tickers = list(TICKERS)
    rng.shuffle(tickers)

    generated = []
    styles = ["signal", "volume", "congressional", "matrix", "flow"]
    rng.shuffle(styles)

    i = 0
    for style in styles[:count]:
        if style == "signal":
            t = tickers[i % len(tickers)]; i += 1
            hook = rng.choice(SIGNAL_HOOKS)
            path = OUT_DIR / f"signal_{today}_{t[0]}.png"
            make_signal_alert(t, hook, path)

        elif style == "volume":
            t = tickers[i % len(tickers)]; i += 1
            hook = rng.choice(VOLUME_HOOKS)
            path = OUT_DIR / f"volume_{today}_{t[0]}.png"
            make_volume_spike(t, hook, path)

        elif style == "congressional":
            cong = rng.choice(CONGRESSPEOPLE)
            hook = rng.choice(CONGRESSIONAL_HOOKS)
            path = OUT_DIR / f"congressional_{today}.png"
            make_congressional(cong, hook, path)

        elif style == "matrix":
            subset = rng.sample(tickers, 7)
            subset.sort(key=lambda x: -x[3])
            path = OUT_DIR / f"matrix_{today}.png"
            make_setup_matrix(subset, path)

        elif style == "flow":
            t = tickers[i % len(tickers)]; i += 1
            hook = rng.choice(VOLUME_HOOKS)
            path = OUT_DIR / f"flow_{today}_{t[0]}.png"
            make_flow_card(t, hook, path)

        print(f"  [CARD] {style.upper()} → {path.name}")
        generated.append(str(path))

    print(f"\n[CARDS] {len(generated)} fresh cards in indicators/cards/")
    return generated


if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(f"[CARDS] Generating {count} chart cards...")
    run(count)
