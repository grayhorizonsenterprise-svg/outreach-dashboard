"""
Edge Engine — all settings in one place.
Copy .env.template → .env and fill in your keys.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# ── Phone alerts (free) ────────────────────────────────────────────────────────
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "ghe_edge_alerts")

# ── Congress trades (free tier) ────────────────────────────────────────────────
QUIVER_KEY = os.getenv("QUIVERQUANT_KEY", "")

# ── Sports & Politics odds ─────────────────────────────────────────────────────
ODDS_KEY = os.getenv("ODDS_API_KEY", "")

# ── Robinhood ──────────────────────────────────────────────────────────────────
RH_USER = os.getenv("RH_USERNAME", "")
RH_PASS = os.getenv("RH_PASSWORD", "")

# ── Coinbase ───────────────────────────────────────────────────────────────────
CB_KEY    = os.getenv("COINBASE_API_KEY", "")
CB_SECRET = os.getenv("COINBASE_API_SECRET", "")

# ── CoinGecko (optional — free demo key at coingecko.com/api/pricing) ──────────
COINGECKO_KEY = os.getenv("COINGECKO_KEY", "")

# ── Thresholds ─────────────────────────────────────────────────────────────────
PROFIT_ALERT_USD  = 1000
BIWEEKLY_DAYS     = 14
MIN_BET_EDGE_PCT  = -99.0  # show ALL games — frontend filters by category
MIN_SIGNAL_SCORE  = 65

# ══════════════════════════════════════════════════════════════════════════════
# WATCHLISTS
# ══════════════════════════════════════════════════════════════════════════════

# ── SpaceX Ecosystem ──────────────────────────────────────────────────────────
# SpaceX is private — these are the PUBLIC companies that supply, compete,
# partner with, or directly benefit from SpaceX/Starlink growth.
SPACEX_ECOSYSTEM = {
    # Pure-play space launch & spacecraft
    "RKLB":  "Rocket Lab — launch + spacecraft bus",
    "ASTS":  "AST SpaceMobile — direct-to-cell satellite (Starlink rival)",
    "PL":    "Planet Labs — Earth observation satellites",
    "SPIR":  "Spire Global — satellite data (weather, maritime, aviation)",
    "BKSY":  "BlackSky Technology — real-time satellite imagery",
    "IRDM":  "Iridium — global satellite communications",
    "GSAT":  "Globalstar — satellite broadband (Apple Emergency SOS partner)",
    "VSAT":  "Viasat — satellite internet (Starlink competitor)",
    "SPCE":  "Virgin Galactic / Galactic Holdings — space tourism",

    # Defense/aerospace primes with significant space contracts
    "LMT":   "Lockheed Martin — GPS III, space systems, NASA contracts",
    "NOC":   "Northrop Grumman — James Webb, space launch systems",
    "RTX":   "Raytheon Technologies — missile defense, satellite sensors",
    "BA":    "Boeing — Starliner, Space Launch System (SLS)",
    "GD":    "General Dynamics — space/defense electronics",
    "LHX":   "L3Harris (absorbed Aerojet Rocketdyne) — rocket propulsion",
    "SAIC":  "SAIC — space/defense IT & systems",
    "LDOS":  "Leidos — space systems engineering",
    "BAH":   "Booz Allen Hamilton — space intelligence & analytics",
    "KTOS":  "Kratos Defense — rocket engines, space vehicles",

    # Supply chain — components that go into rockets & spacecraft
    "MOG.A": "Moog Inc — precision motion control (flight controls, valves)",
    "TDG":   "TransDigm — highly engineered aerospace components",
    "HEI":   "HEICO — FAA-approved aerospace replacement parts",
    "DCO":   "Ducommun — aerospace structures & electronic systems",
    "MTRN":  "Materion — beryllium & specialty materials (thermal mgmt)",
    "MRCY":  "Mercury Systems — processing electronics for space/defense",
    "CW":    "Curtiss-Wright — defense electronics & testing systems",

    # Semiconductor & compute (Starlink terminals, satellite compute)
    "SWKS":  "Skyworks Solutions — RF chips in Starlink user terminals",
    "QCOM":  "Qualcomm — satellite-to-phone chips",
    "NVDA":  "NVIDIA — AI compute for autonomous spacecraft & simulation",

    # Ground infrastructure & tracking
    "MAXN":  "Maxeon Solar — solar panels used in satellites",
}

SPACEX_TICKERS = list(SPACEX_ECOSYSTEM.keys())

# ── High-momentum tech ────────────────────────────────────────────────────────
MOMENTUM_TECH = [
    "NVDA","AMD","META","GOOGL","MSFT","AAPL","AMZN","TSLA","AVGO","ARM",
    "SMCI","PLTR","IONQ","CRWD","SHOP","MSTR","COIN","HOOD","SOFI","SNOW",
    "NET","DDOG","ZS","PANW","MDB","GTLB","APP","TTWO","RBLX",
]

# ── Niche / high-alpha small & mid cap ───────────────────────────────────────
NICHE_STOCKS = [
    # Quantum computing
    "IONQ","RGTI","QUBT","QMCO",
    # AI infrastructure
    "SMCI","ARM","ALAB","ASML",
    # Biotech high-volatility
    "MRNA","CRSP","BEAM","EDIT","NTLA","RXRX","ARKG",
    # Clean energy
    "FSLR","ENPH","SEDG","BE","PLUG","CHPT","BLNK",
    # Defense emerging tech
    "KTOS","RCAT","JOBY","ACHR","LILM",
    # Fintech
    "UPST","AFRM","SOFI","HOOD","NU","COUR",
    # EV / autonomous
    "TSLA","RIVN","LCID","FSR","GOEV","NKLA",
    # Uranium / nuclear
    "CCJ","UEC","NXE","DNN","SMR","NNE",
]

# ── Full combined stock watchlist ─────────────────────────────────────────────
STOCKS = list(dict.fromkeys(
    SPACEX_TICKERS + MOMENTUM_TECH + NICHE_STOCKS
))

# ── Crypto watchlist (CoinGecko IDs — used when COINGECKO_KEY is set) ──────────
# CoinPaprika fallback covers top-100 by market cap automatically (no IDs needed)
CRYPTOS = [
    # Blue chips
    "bitcoin","ethereum","solana","binancecoin","ripple","cardano",
    "avalanche-2","polkadot","chainlink","litecoin","bitcoin-cash",
    "stellar","dogecoin","shiba-inu",
    # Layer 2 / modular
    "arbitrum","optimism","polygon","immutable-x","celestia","starknet",
    # AI / DePIN / DeFi
    "fetch-ai","render-token","the-graph","injective-protocol",
    "worldcoin-wld","near","sui","aptos","toncoin","hedera-hashgraph",
    "kaspa","sei-network","stacks","mantra-dao","ondo-finance",
    # High-momentum (meme + narrative)
    "pepe","bonk-2","dogwifcoin","floki","brett-based",
    # DeFi protocols
    "uniswap","aave","maker","curve-dao-token","lido-dao","jupiter-exchange-solana",
]

# ── Sports to scan daily ───────────────────────────────────────────────────────
SPORTS = [
    "americanfootball_nfl",
    "basketball_nba",
    "baseball_mlb",
    "icehockey_nhl",
    "soccer_usa_mls",
    "mma_mixed_martial_arts",
    "tennis_atp_french_open",
]

# ── Dashboard categories for UI grouping ──────────────────────────────────────
CATEGORIES = {
    "SpaceX Ecosystem": SPACEX_TICKERS,
    "Momentum Tech":    MOMENTUM_TECH[:15],
    "Niche / Alpha":    NICHE_STOCKS[:20],
}
