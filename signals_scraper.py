"""
signals_scraper.py — Gray Horizons Enterprise
Scrapes TARGETED audience for Edge Engine signals subscription.
Targets: active traders, sports bettors, investors, fantasy players.
These are NOT contractors — they actually want stock/crypto/sports picks.
Writes to signals_queue.csv.
"""

import requests
import pandas as pd
import os
import sys
import re
import time
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "signals_queue.csv")
HEADERS    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_DOMAINS = ["example.com", "test.com", "sentry.io", "github.com", "google.com",
                "w3.org", "schema.org", "jquery.com", "cloudflare.com"]

DDG_QUERIES = [
    # Sports betting audience
    "sports betting blog contact email",
    "sports betting handicapper contact email",
    "fantasy sports analyst contact email newsletter",
    "DFS player contact email site:.com",
    "sports betting tipster contact email",
    # Trading/investing audience
    "stock trading newsletter contact email",
    "options trader blog contact email",
    "swing trader contact email site:.com",
    "day trading community contact email",
    "crypto trader newsletter contact email",
    "financial newsletter editor contact email",
    # Fantasy/DFS
    "fantasy football analyst email newsletter",
    "fantasy sports expert contact email",
    "daily fantasy sports content creator email",
    # Investment clubs
    "investment club contact email",
    "stock market group contact email newsletter",
    "retail investor community email",
]

YELP_QUERIES = [
    ("financialadvising", "New York, NY"),
    ("financialadvising", "Los Angeles, CA"),
    ("financialadvising", "Chicago, IL"),
    ("financialadvising", "Houston, TX"),
    ("financialadvising", "Dallas, TX"),
    ("sportsbetting",     "Las Vegas, NV"),
    ("sportsbetting",     "New Jersey, NJ"),
    ("sportsbetting",     "Colorado, CO"),
]


def ddg_search() -> list:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    leads = []
    with DDGS() as ddgs:
        for query in DDG_QUERIES:
            try:
                for r in ddgs.text(query, max_results=15):
                    body  = r.get("body", "")
                    title = r.get("title", "")
                    url   = r.get("href", "")
                    for email in EMAIL_RE.findall(body + " " + title):
                        e = email.lower()
                        domain = e.split("@")[-1]
                        if any(j in domain for j in JUNK_DOMAINS):
                            continue
                        if any(bad in e for bad in ["noreply", "test@", "example", "support@", "admin@"]):
                            continue
                        leads.append({
                            "email":   e,
                            "company": title[:50],
                            "website": url,
                            "niche":   "signals",
                            "source":  "ddg_signals",
                        })
                time.sleep(1.5)
            except Exception:
                time.sleep(3)
    return leads


def scrape_trading_directories() -> list:
    """Scrape financial/trading blog directories for contact emails."""
    leads = []
    urls = [
        "https://stockanalysis.com",
        "https://finviz.com",
    ]
    # These are reference points — we search their link structures
    # Main value comes from DDG above
    return leads


def run():
    print("[SIGNALS SCRAPER] Building targeted signals audience...")

    leads = ddg_search()
    print(f"  [DDG] {len(leads)} leads with emails found")

    if not leads:
        print("[SIGNALS SCRAPER] No leads found this run")
        return

    df_new = pd.DataFrame(leads).fillna("")
    df_new = df_new.drop_duplicates(subset=["email"])
    df_new["status"] = "pending"

    for col in ["email", "company", "website", "niche", "source", "status"]:
        if col not in df_new.columns:
            df_new[col] = ""

    # Merge with existing
    if os.path.exists(OUT_FILE):
        df_existing = pd.read_csv(OUT_FILE).fillna("")
        done = set(df_existing["email"].str.lower())
        df_new = df_new[~df_new["email"].str.lower().isin(done)]
        df_out = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_out = df_new

    df_out.to_csv(OUT_FILE, index=False)
    print(f"[SIGNALS SCRAPER] Done — {len(df_new)} new leads, {len(df_out)} total in signals_queue.csv")


if __name__ == "__main__":
    run()
