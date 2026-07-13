"""
scrape_yelp_hot_leads.py — Gray Horizons Enterprise
Scrapes YellowPages for CA contractor businesses with phone numbers.
Yelp blocks all scraping (HTTP 403). YellowPages returns real results.

Output: hot_leads.csv — business name, phone, address, niche, source URL.

Usage:
  python scrape_yelp_hot_leads.py
"""

import os
import re
import csv
import sys
import time
import random
import requests
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT     = DATA_DIR / "hot_leads.csv"
FIELDNAMES = ["business_name", "email", "phone", "address", "source_url", "niche", "found_at", "status"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.yellowpages.com/",
}

PHONE_RE   = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")
EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# YellowPages search queries: (URL, niche)
SEARCHES = [
    ("https://www.yellowpages.com/los-angeles-ca/hvac-contractors",                 "hvac"),
    ("https://www.yellowpages.com/san-diego-ca/hvac-contractors",                   "hvac"),
    ("https://www.yellowpages.com/riverside-ca/hvac-contractors",                   "hvac"),
    ("https://www.yellowpages.com/orange-ca/hvac-contractors",                      "hvac"),
    ("https://www.yellowpages.com/los-angeles-ca/roofing-contractors",              "roofing"),
    ("https://www.yellowpages.com/san-diego-ca/roofing-contractors",                "roofing"),
    ("https://www.yellowpages.com/fresno-ca/roofing-contractors",                   "roofing"),
    ("https://www.yellowpages.com/los-angeles-ca/plumbers",                         "plumbing"),
    ("https://www.yellowpages.com/san-diego-ca/plumbers",                           "plumbing"),
    ("https://www.yellowpages.com/los-angeles-ca/solar-energy-contractors",         "solar"),
    ("https://www.yellowpages.com/san-diego-ca/solar-energy-contractors",           "solar"),
    ("https://www.yellowpages.com/los-angeles-ca/dentists",                         "dental"),
    ("https://www.yellowpages.com/orange-ca/dentists",                              "dental"),
    ("https://www.yellowpages.com/los-angeles-ca/general-contractors",              "contractor"),
    ("https://www.yellowpages.com/los-angeles-ca/landscaping",                      "landscaping"),
]


def _parse_listings(html: str, source_url: str, niche: str) -> list:
    rows = []

    # YellowPages wraps each listing in a div with class "result"
    # Business name is in <a class="business-name"> or h2.n
    name_blocks = re.findall(
        r'class="(?:business-name|listing-name)"[^>]*>\s*<span[^>]*>([^<]+)</span>',
        html
    )
    if not name_blocks:
        # alternate pattern
        name_blocks = re.findall(r'<a[^>]+class="business-name"[^>]*>([^<]+)</a>', html)

    phones = PHONE_RE.findall(html)

    # Address lines
    addresses = re.findall(
        r'<span[^>]+itemprop="streetAddress"[^>]*>([^<]+)</span>',
        html
    )

    for i, name in enumerate(name_blocks):
        phone   = phones[i] if i < len(phones) else ""
        address = addresses[i] if i < len(addresses) else ""
        if not name.strip():
            continue
        rows.append({
            "business_name": name.strip(),
            "email":         "",
            "phone":         phone.strip(),
            "address":       address.strip(),
            "source_url":    source_url,
            "niche":         niche,
            "found_at":      datetime.now().strftime("%Y-%m-%d"),
            "status":        "pending",
        })

    return rows


def run():
    existing = set()
    if OUTPUT.exists():
        with open(OUTPUT, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                existing.add(row.get("business_name", "").strip().lower())

    print(f"[LEADS] Scraping YellowPages for CA contractor leads")
    print(f"[LEADS] {len(existing)} businesses already on record\n")

    new_rows = []
    session  = requests.Session()
    session.headers.update(HEADERS)

    for url, niche in SEARCHES:
        print(f"  {niche.upper()} | {url}")
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200:
                print(f"    [SKIP] HTTP {r.status_code}")
                time.sleep(random.uniform(3, 6))
                continue

            listings = _parse_listings(r.text, url, niche)
            added = 0
            for row in listings:
                key = row["business_name"].lower()
                if key in existing:
                    continue
                new_rows.append(row)
                existing.add(key)
                added += 1

            print(f"    + {added} new | {len(listings)} on page")

        except Exception as e:
            print(f"    [ERR] {e}")

        time.sleep(random.uniform(4, 8))

    if new_rows:
        file_exists = OUTPUT.exists() and OUTPUT.stat().st_size > 0
        with open(OUTPUT, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)
        print(f"\n[LEADS] Done — {len(new_rows)} new businesses saved to {OUTPUT.name}")
    else:
        print("\n[LEADS] No new businesses found this run.")


if __name__ == "__main__":
    run()
