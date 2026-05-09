"""
yelp_scraper.py — Gray Horizons Enterprise
Yelp Fusion API scraper — returns business name, phone, website, address.
Free tier: 500 calls/day. Requires YELP_API_KEY env var.
Get a free key at https://www.yelp.com/developers/v3/manage_app
Appends to prospects_raw.csv with dedup.
"""

import requests
import pandas as pd
import time
import random
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")
YELP_KEY    = os.getenv("YELP_API_KEY", "")
YELP_URL    = "https://api.yelp.com/v3/businesses/search"

NICHE_TERMS = [
    ("hvac",         "hvac"),
    ("hvac",         "heating cooling"),
    ("hvac",         "air conditioning repair"),
    ("dental",       "dentist"),
    ("dental",       "dental office"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing"),
    ("contractor",   "general contractor"),
    ("contractor",   "remodeling"),
    ("landscaping",  "landscaping"),
    ("landscaping",  "lawn care"),
    ("roofing",      "roofing"),
    ("hoa",          "property management"),
    ("chiropractic", "chiropractor"),
    ("salon",        "hair salon"),
    ("salon",        "day spa"),
    ("auto",         "auto repair"),
    ("auto",         "mechanic"),
    ("pest_control", "pest control"),
    ("electrician",  "electrician"),
    ("veterinary",   "veterinarian"),
    ("optometry",    "optometrist"),
]

LOCATIONS = [
    "Phoenix, AZ", "Tucson, AZ", "Mesa, AZ",
    "Denver, CO", "Colorado Springs, CO", "Aurora, CO",
    "Nashville, TN", "Memphis, TN", "Knoxville, TN",
    "Charlotte, NC", "Raleigh, NC", "Greensboro, NC",
    "Atlanta, GA", "Augusta, GA", "Savannah, GA",
    "Dallas, TX", "Houston, TX", "San Antonio, TX", "Austin, TX",
    "Orlando, FL", "Tampa, FL", "Jacksonville, FL",
    "Indianapolis, IN", "Fort Wayne, IN", "Evansville, IN",
    "Columbus, OH", "Cleveland, OH", "Cincinnati, OH",
    "Las Vegas, NV", "Reno, NV", "Henderson, NV",
    "Albuquerque, NM", "Santa Fe, NM",
    "Boise, ID", "Nampa, ID",
    "Salt Lake City, UT", "Provo, UT",
    "Omaha, NE", "Lincoln, NE",
    "Wichita, KS", "Overland Park, KS",
    "Tulsa, OK", "Oklahoma City, OK",
    "Louisville, KY", "Lexington, KY",
]

CORPORATE_BLOCKS = [
    "llc group", "national", "corporate", "franchise", "holdings",
    "partners", "industries", "corporation", "inc.", "international",
    "management group", "service experts", "ars rescue", "one hour",
    "mr. rooter", "merry maids", "servicemaster",
]

PHONE_BLACKLIST = {"", "none", "n/a"}


def search_yelp(term: str, location: str, offset: int = 0) -> list:
    if not YELP_KEY:
        return []
    headers = {"Authorization": f"Bearer {YELP_KEY}"}
    params  = {
        "term": term,
        "location": location,
        "limit": 50,
        "offset": offset,
        "categories": "",
    }
    try:
        r = requests.get(YELP_URL, headers=headers, params=params, timeout=12)
        if r.status_code == 200:
            return r.json().get("businesses", [])
        elif r.status_code == 429:
            print("[YELP] Rate limit hit — sleeping 60s")
            time.sleep(60)
        else:
            print(f"[YELP] {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[YELP] Error: {e}")
    return []


def parse_business(biz: dict, niche: str) -> dict | None:
    name = biz.get("name", "").strip()
    if not name:
        return None

    name_lower = name.lower()
    if any(b in name_lower for b in CORPORATE_BLOCKS):
        return None
    if biz.get("is_claimed") is False:
        return None

    phone   = biz.get("phone", "").replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    website = biz.get("url", "")
    loc     = biz.get("location", {})
    city    = loc.get("city", "")
    state   = loc.get("state", "")
    location_str = f"{city}, {state}" if city else ""

    if website and "yelp.com" in website:
        website = ""

    return {
        "company":          name,
        "website":          website,
        "email":            "",
        "contact_page_url": "",
        "location":         location_str,
        "niche":            niche,
        "lead_type":        "READY",
        "phone":            phone,
    }


def run():
    if not YELP_KEY:
        print("[YELP] No YELP_API_KEY set — skipping. Get a free key at yelp.com/developers")
        return

    existing = pd.read_csv(OUTPUT_FILE).fillna("") if os.path.exists(OUTPUT_FILE) else pd.DataFrame()
    done_names = set(existing["company"].str.lower().tolist()) if len(existing) else set()

    new_rows = []
    calls    = 0

    for niche, term in NICHE_TERMS:
        loc_sample = random.sample(LOCATIONS, min(8, len(LOCATIONS)))
        for location in loc_sample:
            for offset in [0, 50]:
                if calls >= 480:
                    print(f"[YELP] Approaching daily limit ({calls} calls) — stopping")
                    break
                results = search_yelp(term, location, offset)
                calls  += 1
                for biz in results:
                    row = parse_business(biz, niche)
                    if not row:
                        continue
                    if row["company"].lower() in done_names:
                        continue
                    done_names.add(row["company"].lower())
                    new_rows.append(row)
                time.sleep(random.uniform(0.3, 0.8))
            if calls >= 480:
                break

    if not new_rows:
        print("[YELP] No new leads found")
        return

    new_df = pd.DataFrame(new_rows)
    if len(existing):
        # Add phone column to existing if missing
        if "phone" not in existing.columns:
            existing["phone"] = ""
        out = pd.concat([existing, new_df], ignore_index=True)
    else:
        out = new_df

    out.to_csv(OUTPUT_FILE, index=False)
    print(f"[YELP] Done — {len(new_rows)} new leads added (total: {len(out)})")


if __name__ == "__main__":
    run()
