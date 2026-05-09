"""
chamberofcommerce_scraper.py — Gray Horizons Enterprise
Scrapes chamberofcommerce.com — excellent source for owner-operated local businesses.
Members are vetted, real businesses with real owners. Different DB from all other scrapers.
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
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

NICHE_SEARCHES = [
    ("hvac",         "hvac"),
    ("hvac",         "air+conditioning"),
    ("hvac",         "heating+cooling"),
    ("dental",       "dentist"),
    ("dental",       "dental"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing"),
    ("contractor",   "contractor"),
    ("contractor",   "remodeling"),
    ("landscaping",  "landscaping"),
    ("roofing",      "roofing"),
    ("hoa",          "property+management"),
    ("chiropractic", "chiropractor"),
    ("auto",         "auto+repair"),
    ("pest_control", "pest+control"),
    ("electrician",  "electrician"),
    ("salon",        "salon"),
    ("veterinary",   "veterinarian"),
    ("optometry",    "optometrist"),
]

STATES = [
    "TX", "FL", "GA", "NC", "TN", "AZ", "CO", "NV", "OH",
    "IN", "KY", "OK", "KS", "NE", "NM", "ID", "UT", "SC", "AL", "MO",
]

CORPORATE_BLOCKS = [
    "national", "corporate", "franchise", "holdings", "partners",
    "industries", "corporation", "international", "management group",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.chamberofcommerce.com/",
    }


def scrape_page(niche: str, keyword: str, state: str, page: int = 1) -> list:
    url = f"https://www.chamberofcommerce.com/united-states/{state.lower()}/{keyword}?page={page}"
    try:
        r = requests.get(url, headers=get_headers(), timeout=14)
        if r.status_code == 429:
            print("[COC] Rate limited — sleeping 45s")
            time.sleep(45)
            return []
        if r.status_code != 200:
            return []

        soup    = BeautifulSoup(r.text, "html.parser")
        results = []

        for card in soup.select(".business-listing, .result-card, [class*='listing'], [class*='result-item']"):
            name_el = card.select_one("h2, h3, .business-name, [class*='name']")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            if any(b in name.lower() for b in CORPORATE_BLOCKS):
                continue

            website = ""
            web_el  = card.select_one("a[href*='http']:not([href*='chamberofcommerce'])")
            if web_el:
                website = web_el.get("href", "")

            phone = ""
            ph_el = card.select_one("[class*='phone'], [itemprop='telephone'], [class*='tel']")
            if ph_el:
                phone = re.sub(r"[^\d]", "", ph_el.get_text())

            addr_el  = card.select_one("[class*='address'], [itemprop='address'], [class*='location']")
            location_str = addr_el.get_text(strip=True)[:60] if addr_el else state

            results.append({
                "company":          name,
                "website":          website,
                "email":            "",
                "contact_page_url": "",
                "location":         location_str,
                "niche":            niche,
                "lead_type":        "READY",
                "phone":            phone,
            })

        return results
    except Exception as e:
        print(f"[COC] Error {url}: {e}")
        return []


def run():
    existing   = pd.read_csv(OUTPUT_FILE).fillna("") if os.path.exists(OUTPUT_FILE) else pd.DataFrame()
    done_names = set(existing["company"].str.lower().tolist()) if len(existing) else set()

    new_rows   = []
    state_sample = random.sample(STATES, min(10, len(STATES)))

    for niche, keyword in NICHE_SEARCHES:
        for state in state_sample:
            for page in [1, 2, 3]:
                rows = scrape_page(niche, keyword, state, page)
                for row in rows:
                    if row["company"].lower() in done_names:
                        continue
                    done_names.add(row["company"].lower())
                    new_rows.append(row)
                if not rows:
                    break
                time.sleep(random.uniform(2.0, 4.0))

    if not new_rows:
        print("[COC] No new leads found")
        return

    new_df = pd.DataFrame(new_rows)
    if "phone" not in existing.columns and len(existing):
        existing["phone"] = ""
    out = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"[COC] Done — {len(new_rows)} new leads added (total: {len(out)})")


if __name__ == "__main__":
    run()
