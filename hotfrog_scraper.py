"""
hotfrog_scraper.py — Gray Horizons Enterprise
Hotfrog.com business directory — different database from YP/Superpages/Manta.
No API key. Rotates user agents. Appends to prospects_raw.csv.
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

NICHE_SEARCHES = [
    ("hvac",         "hvac contractor"),
    ("hvac",         "air conditioning"),
    ("hvac",         "heating repair"),
    ("dental",       "dentist"),
    ("dental",       "dental clinic"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing services"),
    ("contractor",   "general contractor"),
    ("contractor",   "home remodeling"),
    ("landscaping",  "landscaping"),
    ("landscaping",  "lawn mowing"),
    ("roofing",      "roofing contractor"),
    ("hoa",          "property management"),
    ("chiropractic", "chiropractor"),
    ("auto",         "auto mechanic"),
    ("pest_control", "pest control"),
    ("electrician",  "electrician"),
]

LOCATIONS = [
    "phoenix-az", "tucson-az", "mesa-az", "scottsdale-az",
    "denver-co", "colorado-springs-co", "aurora-co",
    "nashville-tn", "memphis-tn", "chattanooga-tn",
    "charlotte-nc", "raleigh-nc", "durham-nc",
    "atlanta-ga", "savannah-ga", "augusta-ga",
    "dallas-tx", "houston-tx", "san-antonio-tx", "fort-worth-tx",
    "orlando-fl", "tampa-fl", "miami-fl", "jacksonville-fl",
    "las-vegas-nv", "henderson-nv", "reno-nv",
    "indianapolis-in", "fort-wayne-in",
    "columbus-oh", "cleveland-oh", "cincinnati-oh",
    "albuquerque-nm", "santa-fe-nm",
    "boise-id", "nampa-id",
    "salt-lake-city-ut", "provo-ut",
    "omaha-ne", "lincoln-ne",
    "tulsa-ok", "oklahoma-city-ok",
    "louisville-ky", "lexington-ky",
    "wichita-ks", "overland-park-ks",
]

CORPORATE_BLOCKS = [
    "national", "corporate", "franchise", "holdings", "partners",
    "industries", "corporation", "international", "group inc",
    "service experts", "one hour", "mr. rooter",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.hotfrog.com/",
    }


def scrape_page(niche: str, term: str, location: str, page: int = 1) -> list:
    query = urllib.parse.quote_plus(term)
    url   = f"https://www.hotfrog.com/search/{location}/{query}/{page}"
    try:
        r = requests.get(url, headers=get_headers(), timeout=12)
        if r.status_code != 200:
            return []
        soup    = BeautifulSoup(r.text, "html.parser")
        results = []
        for card in soup.select(".search-result-item, .business-card, [class*='result']"):
            name_el = card.select_one("h2 a, h3 a, .business-name a, [class*='name'] a")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            name_lower = name.lower()
            if any(b in name_lower for b in CORPORATE_BLOCKS):
                continue

            website = ""
            web_el  = card.select_one("a[href*='http']:not([href*='hotfrog'])")
            if web_el:
                website = web_el.get("href", "")

            phone = ""
            ph_el = card.select_one("[class*='phone'], [itemprop='telephone']")
            if ph_el:
                phone = re.sub(r"[^\d]", "", ph_el.get_text())

            city_el = card.select_one("[class*='city'], [class*='location'], [itemprop='addressLocality']")
            location_str = city_el.get_text(strip=True) if city_el else location.replace("-", " ").title()

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
        print(f"[HOTFROG] Error {url}: {e}")
        return []


def run():
    existing  = pd.read_csv(OUTPUT_FILE).fillna("") if os.path.exists(OUTPUT_FILE) else pd.DataFrame()
    done_names = set(existing["company"].str.lower().tolist()) if len(existing) else set()

    new_rows = []
    total    = 0

    loc_sample = random.sample(LOCATIONS, min(20, len(LOCATIONS)))

    for niche, term in NICHE_SEARCHES:
        for location in loc_sample[:12]:
            for page in [1, 2]:
                rows = scrape_page(niche, term, location, page)
                for row in rows:
                    if row["company"].lower() in done_names:
                        continue
                    done_names.add(row["company"].lower())
                    new_rows.append(row)
                total += len(rows)
                time.sleep(random.uniform(1.5, 3.0))

    if not new_rows:
        print(f"[HOTFROG] No new leads (scraped {total} total, all duplicates)")
        return

    new_df = pd.DataFrame(new_rows)
    if "phone" not in existing.columns and len(existing):
        existing["phone"] = ""
    out = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"[HOTFROG] Done — {len(new_rows)} new leads added (total: {len(out)})")


if __name__ == "__main__":
    run()
