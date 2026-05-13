"""
signals_scraper.py — Gray Horizons Enterprise
Finds active traders, investors, sports bettors, DFS players via DDG + page-fetch.
These are the people who actually buy the $49/month signals subscription.
Writes to signals_queue.csv.
"""

import requests
import pandas as pd
import os
import sys
import re
import time
import random
import urllib.parse
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE  = os.path.join(DATA_DIR, "signals_queue.csv")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SKIP_DOMAINS = {
    "reddit.com","twitter.com","facebook.com","instagram.com","linkedin.com",
    "youtube.com","google.com","yelp.com","wikipedia.org","seekingalpha.com",
    "motleyfool.com","investopedia.com","marketwatch.com","cnbc.com","bloomberg.com",
    "wsj.com","reuters.com","yahoo.com","finviz.com","stockanalysis.com",
    "tradingview.com","robinhood.com","etrade.com","schwab.com","fidelity.com",
    "thinkorswim.com","td.com","webull.com","tastyworks.com",
}

BAD_PREFIXES = {
    "abuse","spam","report","complaints","privacy","legal","billing",
    "webmaster","postmaster","mailer","sales","marketing","hr",
    "careers","jobs","news","newsletter","press","media","helpdesk",
    "support","ticket","noreply","no-reply","donotreply","admin","info",
}

# 60+ targeted queries — people who pay for stock/crypto/sports edges
DDG_QUERIES = [
    # Stock & options traders
    "stock trading newsletter contact email",
    "options trader blog contact email",
    "swing trader newsletter contact email",
    "day trading educator email contact",
    "momentum trader newsletter email contact",
    "small cap trader email contact blog",
    "penny stock trader email contact",
    "options flow newsletter contact email",
    "unusual options activity newsletter email",
    "theta gang options trader email contact",
    "covered calls investor email newsletter",
    "technical analysis trader email contact",
    "chartist trader email contact blog",
    "stock screener creator email contact",
    "trading alerts service email contact",
    "stock market educator YouTube email contact",
    "stock trading Discord server email contact",
    "trade ideas service email contact",
    "trading journal blogger email contact",
    "proprietary trading educator email contact",
    # Crypto traders
    "crypto trader newsletter contact email",
    "bitcoin trader blog email contact",
    "altcoin trader email contact",
    "crypto signals provider email contact",
    "DeFi investor email contact blog",
    "NFT trader email contact newsletter",
    "crypto YouTuber email contact",
    "crypto Twitter influencer email contact",
    "Web3 investor email contact",
    "crypto analyst blog email contact",
    # Sports betting & DFS
    "sports betting handicapper contact email",
    "sports betting blogger email contact",
    "NFL picks analyst email contact",
    "NBA betting analyst email contact",
    "MLB betting picks email contact",
    "college football betting blog email",
    "sports betting tipster contact email",
    "daily fantasy sports DFS analyst email",
    "DFS lineup optimizer email contact",
    "fantasy football expert email newsletter",
    "fantasy sports podcast email contact",
    "prop bet analyst email contact",
    "player props betting email contact",
    "sharps betting email newsletter contact",
    "contrarian betting blog email contact",
    # Investment / wealth
    "retail investor newsletter email contact",
    "dividend investor blog email contact",
    "value investing newsletter email contact",
    "growth stock investor email contact",
    "index fund investor blogger email",
    "financial independence blogger email contact",
    "FIRE investor email newsletter contact",
    "personal finance blogger email contact",
    "wealth building email newsletter contact",
    "investment club email contact newsletter",
    "stock market group email newsletter",
    "self-directed investor email contact",
    # Trading tools / community
    "trading community email contact",
    "stock market community email contact",
    "trading Substack newsletter email contact",
    "investing Substack email contact",
    "trading podcast host email contact",
    "stock market podcast email contact",
    "finance YouTube creator email contact",
    "fintwit influencer email contact",
]


def is_clean(email: str) -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
        return False
    prefix = e.split("@")[0]
    if any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES):
        return False
    domain = e.split("@")[-1]
    if domain in SKIP_DOMAINS:
        return False
    return True


def fetch_emails(url: str) -> list:
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(
            url, headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=8, verify=False
        )
        if r.status_code != 200:
            return []
        text = r.text
        for a in BeautifulSoup(text, "html.parser").find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {a['href'][7:].split('?')[0]}"
        return list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())))
    except Exception:
        return []


def run():
    print("[SIGNALS SCRAPER] Finding trader audience via DDG + page-fetch...")

    # Load existing to deduplicate
    existing_emails = set()
    if os.path.exists(OUT_FILE):
        try:
            df_ex = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            existing_emails = set(df_ex["email"].str.lower().str.strip())
        except Exception:
            pass

    # Load unsubscribes
    unsub_file = os.path.join(DATA_DIR, "unsubscribe_list.csv")
    if os.path.exists(unsub_file):
        try:
            ub = pd.read_csv(unsub_file, dtype=str).fillna("")
            existing_emails.update(ub["email"].str.lower().str.strip())
        except Exception:
            pass

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("[SIGNALS SCRAPER] duckduckgo_search not installed"); return

    leads = []
    seen  = set(existing_emails)

    queries = random.sample(DDG_QUERIES, min(40, len(DDG_QUERIES)))

    with DDGS() as ddgs:
        for i, query in enumerate(queries):
            print(f"  [SIG {i+1}/{len(queries)}] {query[:60]}")
            try:
                results = list(ddgs.text(query, max_results=8))
                for r in results:
                    url    = r.get("href", "")
                    title  = r.get("title", "")[:60]
                    domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                    if domain in SKIP_DOMAINS or not url:
                        continue
                    for email in fetch_emails(url):
                        if email in seen:
                            continue
                        seen.add(email)
                        leads.append({
                            "email":   email,
                            "company": title,
                            "website": url,
                            "niche":   "signals",
                            "source":  query[:60],
                            "status":  "pending",
                        })
                        print(f"    [+] {email}")
                    time.sleep(random.uniform(0.3, 0.6))
                time.sleep(random.uniform(0.8, 1.5))
            except Exception as e:
                print(f"    [ERR] {e}"); time.sleep(3)

    if not leads:
        print("[SIGNALS SCRAPER] No new leads this run")
        return

    df_new = pd.DataFrame(leads)
    if os.path.exists(OUT_FILE):
        try:
            df_existing = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            df_out = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["email"])
        except Exception:
            df_out = df_new
    else:
        df_out = df_new

    df_out.to_csv(OUT_FILE, index=False)
    print(f"[SIGNALS SCRAPER] Done — {len(leads)} new, {len(df_out)} total in signals_queue.csv")


if __name__ == "__main__":
    run()
