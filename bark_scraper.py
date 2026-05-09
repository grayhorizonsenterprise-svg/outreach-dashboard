"""
bark_scraper.py — Gray Horizons Enterprise
Bark.com professional services directory — unique lead source, US businesses.
Pros list themselves with contact info. High owner-operator concentration.
No API key. Appends to prospects_raw.csv.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import random
import os
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Bark service category slugs → niche mapping
BARK_CATEGORIES = [
    ("hvac",         "hvac-engineers"),
    ("hvac",         "air-conditioning-engineers"),
    ("plumbing",     "plumbers"),
    ("electrician",  "electricians"),
    ("contractor",   "general-builders"),
    ("contractor",   "kitchen-fitters"),
    ("landscaping",  "gardeners"),
    ("landscaping",  "landscapers"),
    ("roofing",      "roofers"),
    ("chiropractic", "chiropractors"),
    ("dental",       "dentists"),
    ("salon",        "hairdressers"),
    ("auto",         "mechanics"),
    ("pest_control", "pest-controllers"),
    ("veterinary",   "vets"),
    ("optometry",    "opticians"),
    ("cleaning",     "house-cleaners"),
    ("realestate",   "estate-agents"),
]

US_CITIES = [
    "new-york-ny", "los-angeles-ca", "chicago-il", "houston-tx", "phoenix-az",
    "philadelphia-pa", "san-antonio-tx", "san-diego-ca", "dallas-tx", "san-jose-ca",
    "austin-tx", "jacksonville-fl", "fort-worth-tx", "columbus-oh", "charlotte-nc",
    "indianapolis-in", "san-francisco-ca", "seattle-wa", "denver-co", "washington-dc",
    "nashville-tn", "oklahoma-city-ok", "el-paso-tx", "boston-ma", "portland-or",
    "las-vegas-nv", "memphis-tn", "louisville-ky", "baltimore-md", "milwaukee-wi",
    "albuquerque-nm", "tucson-az", "fresno-ca", "sacramento-ca", "mesa-az",
    "kansas-city-mo", "atlanta-ga", "omaha-ne", "colorado-springs-co", "raleigh-nc",
    "miami-fl", "virginia-beach-va", "tampa-fl", "new-orleans-la", "cleveland-oh",
    "aurora-co", "anaheim-ca", "honolulu-hi", "corpus-christi-tx", "riverside-ca",
]

CORPORATE_BLOCKS = [
    "national", "corporate", "franchise", "holdings", "partners",
    "industries", "corporation", "international",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.bark.com/",
    }


def scrape_bark(niche: str, category: str, city: str) -> list:
    url = f"https://www.bark.com/en/us/{category}/{city}/"
    try:
        r = requests.get(url, headers=get_headers(), timeout=14)
        if r.status_code == 429:
            time.sleep(30)
            return []
        if r.status_code != 200:
            return []

        soup    = BeautifulSoup(r.text, "html.parser")
        results = []

        for card in soup.select(".provider-card, .profile-card, [class*='provider'], [class*='seller']"):
            name_el = card.select_one("h2, h3, .provider-name, .seller-name, [class*='name']")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            if any(b in name.lower() for b in CORPORATE_BLOCKS):
                continue

            website = ""
            web_el  = card.select_one("a[href*='http']:not([href*='bark.com'])")
            if web_el:
                website = web_el.get("href", "")

            loc_el = card.select_one("[class*='location'], [class*='city'], [class*='address']")
            location_str = loc_el.get_text(strip=True)[:60] if loc_el else city.replace("-", " ").title()

            results.append({
                "company":          name,
                "website":          website,
                "email":            "",
                "contact_page_url": "",
                "location":         location_str,
                "niche":            niche,
                "lead_type":        "READY",
                "phone":            "",
            })

        return results
    except Exception as e:
        print(f"[BARK] Error {url}: {e}")
        return []


def run():
    existing   = pd.read_csv(OUTPUT_FILE).fillna("") if os.path.exists(OUTPUT_FILE) else pd.DataFrame()
    done_names = set(existing["company"].str.lower().tolist()) if len(existing) else set()

    new_rows     = []
    city_sample  = random.sample(US_CITIES, min(15, len(US_CITIES)))

    for niche, category in BARK_CATEGORIES:
        for city in city_sample[:8]:
            rows = scrape_bark(niche, category, city)
            for row in rows:
                if row["company"].lower() in done_names:
                    continue
                done_names.add(row["company"].lower())
                new_rows.append(row)
            time.sleep(random.uniform(2.0, 4.5))

    if not new_rows:
        print("[BARK] No new leads found")
        return

    new_df = pd.DataFrame(new_rows)
    if "phone" not in existing.columns and len(existing):
        existing["phone"] = ""
    out = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"[BARK] Done — {len(new_rows)} new leads added (total: {len(out)})")


if __name__ == "__main__":
    run()
