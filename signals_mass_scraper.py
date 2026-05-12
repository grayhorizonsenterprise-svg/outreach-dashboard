"""
signals_mass_scraper.py — Gray Horizons Enterprise
Targets INDIVIDUALS: traders, bettors, sports handicappers, crypto holders, investors.
Goal: 10,000+ leads every 2 days. Runs standalone — no dashboard needed.
Writes to signals_queue.csv
"""

import pandas as pd
import re
import time
import random
import os
import sys
import urllib.parse
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "signals_queue.csv")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

BAD_PREFIXES = {
    'abuse','spam','report','complaints','privacy','legal','billing',
    'webmaster','postmaster','mailer','sales','marketing','hr',
    'careers','jobs','news','newsletter','press','media','helpdesk',
    'support','ticket','noreply','no-reply','donotreply',
}

SKIP_DOMAINS = {
    "reddit.com","twitter.com","facebook.com","instagram.com","linkedin.com",
    "youtube.com","google.com","yelp.com","wikipedia.org","amazon.com",
    "investopedia.com","seekingalpha.com","marketwatch.com","bloomberg.com",
    "cnbc.com","wsj.com","forbes.com","businessinsider.com","yahoo.com",
}

# 200+ targeted search queries hitting individuals not businesses
SEARCH_QUERIES = [
    # ── Stock traders / investors ──────────────────────────────────────────────
    "stock trader personal blog contact email",
    "swing trader newsletter contact email site:.com",
    "day trader blog email subscribe",
    "options trader contact email newsletter",
    "retail investor blog email contact",
    "stock picks newsletter email contact",
    "value investor blog contact email",
    "growth investor newsletter subscribe email",
    "stock market analyst personal site email",
    "momentum trader blog email",
    "dividend investor newsletter email contact",
    "penny stock trader blog email contact",
    "small cap investor newsletter email",
    "stock trading coach contact email",
    "trading mentor email contact",
    "stock market educator email newsletter",
    "chart analyst blog contact email",
    "technical analyst newsletter email",
    "fundamental analyst blog email contact",
    "stock screener creator email contact",

    # ── Crypto ────────────────────────────────────────────────────────────────
    "crypto trader blog contact email",
    "bitcoin trader newsletter email contact",
    "ethereum investor blog email",
    "altcoin trader contact email newsletter",
    "crypto analyst personal site email",
    "defi investor blog contact email",
    "nft collector blog email contact",
    "crypto coach email contact newsletter",
    "blockchain investor personal email",
    "crypto youtuber contact email newsletter",
    "bitcoin newsletter editor email",
    "crypto signals creator contact email",
    "web3 investor blog email",
    "crypto portfolio manager email contact",
    "digital asset investor contact email",

    # ── Sports betting ─────────────────────────────────────────────────────────
    "sports betting tipster contact email",
    "sports handicapper personal blog email",
    "NFL betting picks newsletter email",
    "NBA betting analyst contact email",
    "MLB handicapper email contact",
    "college football picks email newsletter",
    "soccer betting tipster contact email",
    "sports betting blogger email",
    "sharp bettor newsletter contact email",
    "sports picks service email contact",
    "sports betting consultant email",
    "football handicapper blog email",
    "basketball picks newsletter email contact",
    "hockey betting tips email contact",
    "tennis betting analyst email",
    "boxing picks newsletter email",
    "UFC betting tips contact email",
    "esports betting analyst email contact",
    "horse racing handicapper email contact",
    "golf betting picks newsletter email",

    # ── Fantasy sports / DFS ──────────────────────────────────────────────────
    "fantasy football expert contact email",
    "DFS player blog email newsletter",
    "fantasy sports analyst contact email",
    "daily fantasy sports creator email",
    "fantasy baseball expert email contact",
    "fantasy basketball analyst newsletter email",
    "FanDuel DraftKings expert email contact",
    "fantasy sports coach email newsletter",
    "fantasy football podcast email contact",
    "fantasy sports YouTuber email contact",
    "dynasty fantasy football expert email",
    "best ball fantasy analyst email contact",

    # ── Options trading ────────────────────────────────────────────────────────
    "options trader newsletter email contact",
    "options flow analyst blog email",
    "0DTE options trader email contact",
    "covered call strategy newsletter email",
    "options income trader blog email contact",
    "options trading educator email",
    "iron condor trader newsletter email",
    "options mentor contact email",
    "theta gang blog email contact",
    "LEAPS investor newsletter email",

    # ── Forex ─────────────────────────────────────────────────────────────────
    "forex trader blog contact email",
    "forex signal provider email contact",
    "currency trader newsletter email",
    "forex mentor email contact",
    "forex analyst blog email",
    "price action trader email contact",
    "forex coach newsletter email",
    "currency investor blog email contact",

    # ── Investment clubs / groups ──────────────────────────────────────────────
    "investment club contact email",
    "stock market club email contact",
    "investor meetup group email contact",
    "trading club newsletter email",
    "investment group blog email",
    "stock investing group email contact",
    "retail investor community email contact",
    "trading community email newsletter",
    "investment circle contact email",
    "stock market group email",

    # ── Financial content creators ─────────────────────────────────────────────
    "personal finance blogger contact email",
    "financial independence blogger email",
    "FIRE movement blog contact email",
    "passive income blogger email contact",
    "wealth building blog email",
    "investing for beginners blog email contact",
    "financial freedom blogger email",
    "money blog contact email",
    "frugal investor blog email",
    "early retirement blog email contact",
    "financial literacy creator email",
    "money management blog email contact",
    "budget investing blog email",
    "wealth mindset blog email contact",

    # ── Poker / casino / gambling adjacent ────────────────────────────────────
    "poker player blog contact email",
    "professional poker player email contact",
    "poker coach email contact newsletter",
    "poker training site email",
    "casino strategy blog email contact",
    "blackjack advantage player email",
    "poker content creator email contact",
    "card player newsletter email contact",
    "live poker player blog email",

    # ── Specific platforms / communities ──────────────────────────────────────
    "StockTwits top contributor email contact",
    "TradingView script creator email contact",
    "Robinhood investor blog email",
    "Webull trader blog email contact",
    "TD Ameritrade active trader email",
    "E*TRADE power trader email contact",
    "Interactive Brokers trader blog email",
    "tastytrade community member email contact",
    "thinkorswim trader email contact",

    # ── Newsletter / Substack ─────────────────────────────────────────────────
    "Substack stock market newsletter email",
    "Substack options trading newsletter email",
    "Substack crypto newsletter email contact",
    "Substack sports betting newsletter email",
    "trading newsletter creator email contact",
    "investing newsletter founder email",
    "sports picks Substack email contact",
    "financial newsletter writer email",
    "market analysis newsletter email contact",
    "weekly stock picks email newsletter contact",

    # ── YouTube / podcast ─────────────────────────────────────────────────────
    "stock trading YouTube channel email contact",
    "crypto YouTube channel contact email",
    "sports betting podcast email contact",
    "investing podcast host email",
    "trading podcast email contact",
    "financial YouTube creator email",
    "stock picks YouTube email contact",
    "options trading podcast email",
    "day trading YouTube email contact",
    "sports handicapper podcast email",

    # ── Reddit-adjacent / forum users ─────────────────────────────────────────
    "wallstreetbets style trader blog email",
    "stocks subreddit contributor blog email",
    "investing forum member blog email contact",
    "trading discord server owner email",
    "stock market discord admin email",
    "crypto telegram group owner email",
    "trading signal discord email contact",
    "investing Slack group owner email",

    # ── Location + niche combos ────────────────────────────────────────────────
    "stock trader New York email contact blog",
    "options trader Chicago email contact",
    "day trader Los Angeles blog email",
    "crypto trader Miami email contact",
    "forex trader Texas email blog",
    "sports bettor Las Vegas email contact",
    "sports handicapper Florida email contact",
    "investor Atlanta blog email contact",
    "trader Boston email contact blog",
    "investor Seattle blog email contact",
    "trader Austin email contact",
    "sports bettor New Jersey email contact",

    # ── High net worth / serious investors ────────────────────────────────────
    "accredited investor blog email contact",
    "angel investor personal blog email",
    "venture investing blog email contact",
    "high net worth investor blog email",
    "family office investor blog email",
    "hedge fund blog contact email",
    "quantitative trader blog email contact",
    "algo trader blog email contact",
    "systematic trader email contact blog",
    "quant investor newsletter email",
]


def is_clean_email(email: str) -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith(('.png', '.jpg', '.gif', '.webp', '.svg')):
        return False
    prefix = e.split('@')[0]
    if any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES):
        return False
    return True


def run():
    seen_emails = set()
    if os.path.exists(OUT_FILE):
        try:
            df_ex = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            seen_emails = set(df_ex["email"].str.lower().dropna())
            print(f"[SIGNALS] Loaded {len(seen_emails)} existing leads")
        except Exception:
            pass

    searches_per_run = int(os.getenv("SIGNALS_SEARCHES_PER_RUN", "150"))
    queries = random.sample(SEARCH_QUERIES, min(searches_per_run, len(SEARCH_QUERIES)))

    print(f"[SIGNALS] Running {len(queries)} searches targeting traders/bettors/investors...")

    all_new = []
    ddgs = DDGS()

    for i, query in enumerate(queries):
        print(f"  [{i+1}/{len(queries)}] {query[:60]}")
        try:
            results = list(ddgs.text(query, max_results=8))
            for r in results:
                body   = r.get("body", "")
                url    = r.get("href", "")
                name   = r.get("title", "")[:80]
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS:
                    continue
                for email in EMAIL_RE.findall(body):
                    email = email.lower()
                    if email in seen_emails or not is_clean_email(email):
                        continue
                    seen_emails.add(email)
                    all_new.append({
                        "email":   email,
                        "name":    name,
                        "website": url,
                        "source":  query[:60],
                        "status":  "pending",
                        "niche":   "signals",
                    })
            time.sleep(random.uniform(0.4, 1.0))
        except Exception as e:
            print(f"    [ERR] {e}")
            time.sleep(2)

    if not all_new:
        print("[SIGNALS] No new leads this run.")
        return

    df_new = pd.DataFrame(all_new)
    if os.path.exists(OUT_FILE):
        try:
            df_ex = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            df_combined = pd.concat([df_ex, df_new], ignore_index=True).drop_duplicates(subset=["email"])
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    df_combined.to_csv(OUT_FILE, index=False)
    print(f"\n[SIGNALS DONE] {len(all_new)} new leads | {len(df_combined)} total in signals_queue.csv")


if __name__ == "__main__":
    run()
