"""
superpages_scraper.py — Gray Horizons Enterprise
Scrapes Superpages.com business directory — separate database from Yellow Pages.
No API key. Rotates user agents. Appends to prospects_raw.csv.
Deduplicates against existing data across all runs.
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

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

NICHE_SEARCHES = [
    ("hoa",         "HOA management"),
    ("hoa",         "community association management"),
    ("hoa",         "property management"),
    ("hvac",        "HVAC"),
    ("hvac",        "air conditioning repair"),
    ("hvac",        "heating cooling"),
    ("dental",      "dentist"),
    ("dental",      "dental office"),
    ("plumbing",    "plumber"),
    ("plumbing",    "plumbing company"),
    ("contractor",  "general contractor"),
    ("contractor",  "home remodeling contractor"),
    ("landscaping", "landscaping company"),
    ("landscaping", "lawn care service"),
    ("roofing",     "roofing contractor"),
    ("roofing",     "roofing company"),
]

LOCATIONS = [
    # Northeast
    "New York, NY", "Buffalo, NY", "Albany, NY", "Rochester, NY",
    "Boston, MA", "Worcester, MA",
    "Philadelphia, PA", "Pittsburgh, PA",
    "Newark, NJ", "Trenton, NJ",
    "Hartford, CT", "Providence, RI",
    "Baltimore, MD", "Washington, DC",
    # Southeast
    "Atlanta, GA", "Savannah, GA",
    "Miami, FL", "Orlando, FL", "Tampa, FL", "Jacksonville, FL", "Gainesville, FL",
    "Charlotte, NC", "Raleigh, NC", "Greensboro, NC",
    "Columbia, SC", "Charleston, SC",
    "Nashville, TN", "Memphis, TN", "Knoxville, TN",
    "Birmingham, AL", "Huntsville, AL",
    "Baton Rouge, LA", "New Orleans, LA",
    "Richmond, VA", "Virginia Beach, VA",
    "Louisville, KY", "Lexington, KY",
    "Little Rock, AR",
    # Midwest
    "Chicago, IL", "Springfield, IL",
    "Detroit, MI", "Grand Rapids, MI",
    "Columbus, OH", "Cleveland, OH", "Cincinnati, OH",
    "Indianapolis, IN", "Fort Wayne, IN",
    "Milwaukee, WI", "Madison, WI",
    "Minneapolis, MN",
    "Kansas City, MO", "St. Louis, MO",
    "Omaha, NE",
    "Des Moines, IA",
    "Wichita, KS",
    "Fargo, ND", "Sioux Falls, SD",
    # Southwest
    "Houston, TX", "Dallas, TX", "San Antonio, TX", "Austin, TX",
    "Fort Worth, TX", "El Paso, TX", "Lubbock, TX",
    "Phoenix, AZ", "Tucson, AZ", "Scottsdale, AZ",
    "Albuquerque, NM",
    "Oklahoma City, OK", "Tulsa, OK",
    "Las Vegas, NV", "Reno, NV",
    # West
    "Los Angeles, CA", "San Diego, CA", "San Francisco, CA",
    "Sacramento, CA", "Fresno, CA", "Oakland, CA",
    "Seattle, WA", "Spokane, WA",
    "Portland, OR", "Eugene, OR",
    "Denver, CO", "Colorado Springs, CO",
    "Salt Lake City, UT",
    "Boise, ID",
    "Billings, MT", "Bozeman, MT",
]

SKIP_DOMAINS = {
    "superpages.com", "yellowpages.com", "yelp.com", "facebook.com",
    "twitter.com", "instagram.com", "linkedin.com", "youtube.com",
    "google.com", "angi.com", "thumbtack.com", "homeadvisor.com",
    "bbb.org", "nextdoor.com", "reddit.com", "wikipedia.org",
}


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def extract_domain(url):
    if not url:
        return ""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "").split(":")[0]
    except Exception:
        return ""


def scrape_sp_page(search_term, location, page=1):
    """Scrape one page of Superpages results."""
    url = "https://www.superpages.com/search?" + urllib.parse.urlencode({
        "search_terms":    search_term,
        "geo_location_terms": location,
        "page":            page,
    })

    try:
        resp = requests.get(url, headers=get_headers(), timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    [SP] HTTP {resp.status_code} for '{search_term}' in {location}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Superpages uses similar structure to YP
        listings = (
            soup.find_all("div", class_=re.compile(r"\bresult\b", re.I))
            or soup.find_all("div", class_=re.compile(r"\blisting\b", re.I))
            or soup.find_all("li",  class_=re.compile(r"\bresult\b|\blisting\b", re.I))
        )

        if not listings:
            # Fallback: parse any business-name anchors directly
            name_links = soup.find_all("a", class_=re.compile(r"business-name|listing-name", re.I))
            results = []
            for a in name_links:
                name = a.get_text(strip=True)
                if name and len(name) >= 3:
                    results.append({"name": name, "website": "", "phone": "", "address": location})
            return results

        results = []
        for listing in listings:
            # Name
            name = ""
            for selector in [
                lambda el: el.find("a", class_=re.compile(r"business-name|listing-name", re.I)),
                lambda el: el.find(class_=re.compile(r"business-name|listing-name", re.I)),
                lambda el: el.find("h2"),
                lambda el: el.find("h3"),
            ]:
                tag = selector(listing)
                if tag:
                    name = tag.get_text(strip=True)
                    if name:
                        break

            if not name or len(name) < 3:
                continue

            # Website
            website = ""
            ws_tag = listing.find("a", class_=re.compile(r"track-visit-website|website-link|visit-website", re.I))
            if not ws_tag:
                # Try any external link in the listing
                for a in listing.find_all("a", href=True):
                    href = a.get("href", "")
                    if href.startswith("http") and "superpages.com" not in href:
                        domain = extract_domain(href)
                        if domain and domain not in SKIP_DOMAINS:
                            website = href
                            break
            else:
                href = ws_tag.get("href", "")
                if href.startswith("http") and "superpages.com" not in href:
                    website = href

            # Phone
            phone = ""
            ph_tag = listing.find(class_=re.compile(r"\bphones?\b|\bphone-number\b", re.I))
            if ph_tag:
                phone = re.sub(r"[^\d\-\(\)\+\s]", "", ph_tag.get_text(strip=True)).strip()

            # Address
            address = location
            for cls in [r"\blocality\b", r"\badr\b", r"\baddress\b", r"\bcity\b"]:
                addr_tag = listing.find(class_=re.compile(cls, re.I))
                if addr_tag:
                    txt = addr_tag.get_text(strip=True)
                    if txt:
                        address = txt
                        break

            results.append({
                "name":    name,
                "website": website,
                "phone":   phone,
                "address": address,
            })

        return results

    except Exception as exc:
        print(f"    [SP] Exception for '{search_term}' / {location}: {exc}")
        return []


def run():
    seen_domains = set()
    seen_emails  = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE).fillna("")
            for url in df_ex.get("website", pd.Series(dtype=str)).tolist():
                d = extract_domain(str(url))
                if d:
                    seen_domains.add(d)
            for e in df_ex.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
            print(f"[SP] {len(seen_domains)} existing domains loaded — will skip these")
        except Exception as exc:
            print(f"[SP] Could not load prospects_raw.csv: {exc}")

    if os.path.exists(OUTREACH_FILE):
        try:
            oq = pd.read_csv(OUTREACH_FILE).fillna("")
            for e in oq.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
        except Exception:
            pass

    searches_per_run = int(os.getenv("SP_SEARCHES_PER_RUN", "35"))
    all_combos = [
        (niche, term, loc)
        for niche, term in NICHE_SEARCHES
        for loc in LOCATIONS
    ]
    random.shuffle(all_combos)
    combos = all_combos[:searches_per_run]

    print(f"[SP] Running {len(combos)} searches ({len(all_combos)} total possible)...")

    all_new = []
    niche_counts: dict[str, int] = {}

    for niche, term, location in combos:
        print(f"  [SP:{niche.upper()}] '{term}' in {location}")

        for page in [1, 2]:
            listings = scrape_sp_page(term, location, page)
            if not listings:
                break

            added = 0
            for listing in listings:
                domain = extract_domain(listing["website"])

                if domain and domain in seen_domains:
                    continue
                if domain and domain in SKIP_DOMAINS:
                    continue
                if domain:
                    seen_domains.add(domain)

                all_new.append({
                    "company":          listing["name"],
                    "website":          listing["website"],
                    "email":            "",
                    "contact_page_url": "",
                    "location":         listing["address"],
                    "niche":            niche,
                    "phone":            listing["phone"],
                })
                niche_counts[niche] = niche_counts.get(niche, 0) + 1
                added += 1

            print(f"    page {page}: {len(listings)} results, {added} new")
            time.sleep(random.uniform(2.0, 3.5))

        time.sleep(random.uniform(1.0, 2.0))

    if not all_new:
        print("[SP] No new prospects found this run.")
        return

    df_new = pd.DataFrame(all_new)
    df_new = df_new[df_new["website"].str.strip() != ""].copy()
    df_new.drop_duplicates(subset=["website"], inplace=True)

    if os.path.exists(OUTPUT_FILE):
        try:
            df_existing = pd.read_csv(OUTPUT_FILE).fillna("")
            if "phone" not in df_existing.columns:
                df_existing["phone"] = ""
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=["website"], inplace=True)
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    df_combined.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[SP DONE] {len(df_new)} new prospects added | {len(df_combined)} total in file")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {c}")


if __name__ == "__main__":
    run()
