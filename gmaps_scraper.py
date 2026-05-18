"""
gmaps_scraper.py - Gray Horizons Enterprise
Scrapes Google Maps search results for local businesses across all niches.
No API key needed. Finds real business websites then Hunter.io enriches emails.
Runs as part of the pipeline every 6 hours.
"""

import requests
import pandas as pd
import os
import sys
import time
import random
import json
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

SEARCHES = [
    ("hvac", "HVAC company"),
    ("hvac", "air conditioning repair"),
    ("hvac", "heating and cooling"),
    ("roofing", "roofing contractor"),
    ("roofing", "roofing company"),
    ("plumbing", "plumbing company"),
    ("plumbing", "plumber"),
    ("landscaping", "landscaping company"),
    ("landscaping", "lawn care service"),
    ("contractor", "general contractor"),
    ("contractor", "home remodeling"),
    ("dental", "dental practice"),
    ("dental", "dentist office"),
    ("auto", "auto repair shop"),
    ("auto", "mechanic shop"),
    ("hoa", "HOA management company"),
    ("hoa", "property management company"),
    ("pest_control", "pest control company"),
    ("electrician", "electrical contractor"),
    ("financial", "financial advisor"),
]

CITIES = [
    "Houston TX", "Dallas TX", "San Antonio TX", "Austin TX",
    "Jacksonville FL", "Miami FL", "Tampa FL", "Orlando FL",
    "Atlanta GA", "Phoenix AZ", "Charlotte NC", "Las Vegas NV",
    "Denver CO", "Nashville TN", "Columbus OH", "Chicago IL",
    "Los Angeles CA", "San Diego CA", "Seattle WA", "Detroit MI",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def search_google_maps(query: str, city: str) -> list:
    """Search Google Maps via the maps/search endpoint and extract business data."""
    results = []
    try:
        search_term = f"{query} in {city}"
        url = "https://www.google.com/maps/search/" + requests.utils.quote(search_term)
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        # Extract business data from the response
        text = r.text

        # Find website URLs in the page
        websites = re.findall(r'https?://(?!(?:www\.)?(?:google|facebook|instagram|twitter|yelp|youtube|linkedin|maps\.google)\.)([a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}(?:/[^\s"\'<>]*)?)', text)

        # Find business names near website URLs
        name_pattern = re.findall(r'"([^"]{3,60})"[^"]*?(?:hvac|roofing|plumbing|landscaping|dental|contractor|auto|HOA|property|pest|electric|financial|advisor|repair|service|company|group|inc|llc)', text, re.IGNORECASE)

        seen = set()
        for website in websites[:15]:
            domain = website.split("/")[0].replace("www.", "").lower()
            if domain in seen or len(domain) < 4:
                continue
            # Skip obvious non-business domains
            skip = ["google", "facebook", "yelp", "bbb.org", "yellowpages", "angi",
                    "homeadvisor", "thumbtack", "angieslist", "houzz", "nextdoor",
                    "bing", "yahoo", "apple", "microsoft", "amazon"]
            if any(s in domain for s in skip):
                continue
            seen.add(domain)
            results.append({
                "company": domain.split(".")[0].replace("-", " ").title(),
                "website": f"https://www.{domain}",
                "email": "",
                "location": city,
                "niche": "",
                "lead_type": "",
                "phone": "",
            })
            if len(results) >= 10:
                break

    except Exception as e:
        print(f"  [GMAPS] Error: {e}")
    return results


def run(max_new: int = 500):
    print("[GMAPS] Starting Google Maps scrape...")

    # Load existing domains to skip
    existing_domains: set = set()
    rows: list = []

    # Load from DB
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, sslmode="require")
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (e,) in cur.fetchall():
                    if e and "@" in str(e):
                        existing_domains.add(str(e).strip().lower().split("@")[-1])
            conn.close()
        except Exception:
            pass

    # Load existing prospects
    if os.path.exists(OUT_FILE):
        try:
            df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            for w in df_exist.get("website", pd.Series(dtype=str)).str.strip():
                if w:
                    d = w.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                    existing_domains.add(d)
            rows = df_exist.to_dict("records")
        except Exception:
            pass

    # Load sent_domains skip list
    skip_path = os.path.join(DATA_DIR, "sent_domains.csv")
    if os.path.exists(skip_path):
        try:
            import csv
            with open(skip_path, newline="") as f:
                for row in csv.DictReader(f):
                    d = row.get("domain", "").strip().lower()
                    if d:
                        existing_domains.add(d)
        except Exception:
            pass

    print(f"  Blocking {len(existing_domains)} already-contacted domains")

    new_count = 0
    searches = random.sample(SEARCHES, min(8, len(SEARCHES)))
    cities = random.sample(CITIES, min(5, len(CITIES)))

    for niche, query in searches:
        if new_count >= max_new:
            break
        for city in cities:
            if new_count >= max_new:
                break

            print(f"  [GMAPS] {niche.upper()} | {query} | {city}")
            results = search_google_maps(query, city)

            for r in results:
                if new_count >= max_new:
                    break
                website = r.get("website", "")
                domain = website.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                if not domain or domain in existing_domains:
                    continue
                existing_domains.add(domain)
                r["niche"] = niche
                rows.append(r)
                new_count += 1
                print(f"    [+] {r['company']} | {website}")

            time.sleep(random.uniform(3.0, 6.0))

    if not rows:
        print("[GMAPS] No new businesses found")
        return

    pd.DataFrame(rows).to_csv(OUT_FILE, index=False)
    print(f"\n[GMAPS] Done. +{new_count} new businesses. Total: {len(rows)}")
    print("  Hunter.io will enrich emails on next pipeline run")


if __name__ == "__main__":
    run()
