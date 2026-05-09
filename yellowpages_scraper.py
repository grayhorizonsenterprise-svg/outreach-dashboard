"""
yellowpages_scraper.py — Gray Horizons Enterprise
Scrapes Yellow Pages business directory for leads across all niches + US cities.
No API key. Rotates user agents. Appends to prospects_raw.csv.
Deduplicates against existing data so nothing is re-scraped.
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
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# (niche_tag, yellow_pages_search_term)
NICHE_SEARCHES = [
    ("hoa",         "HOA management"),
    ("hoa",         "homeowners association management"),
    ("hoa",         "community association management"),
    ("hoa",         "property management company"),
    ("hvac",        "HVAC"),
    ("hvac",        "air conditioning"),
    ("hvac",        "heating cooling"),
    ("hvac",        "furnace repair"),
    ("dental",      "dentist"),
    ("dental",      "dental office"),
    ("dental",      "dental practice"),
    ("plumbing",    "plumber"),
    ("plumbing",    "plumbing company"),
    ("plumbing",    "drain cleaning"),
    ("contractor",  "general contractor"),
    ("contractor",  "home remodeling"),
    ("contractor",  "construction company"),
    ("landscaping",  "landscaping"),
    ("landscaping",  "lawn care"),
    ("roofing",      "roofing company"),
    ("roofing",      "roofer"),
    ("auto",         "auto repair shop"),
    ("auto",         "mechanic"),
    ("auto",         "automotive service"),
    ("chiropractic", "chiropractor"),
    ("chiropractic", "chiropractic office"),
    ("realestate",   "real estate agency"),
    ("realestate",   "realty company"),
    ("salon",        "hair salon"),
    ("salon",        "day spa"),
    ("salon",        "nail salon"),
]

LOCATIONS = [
    # Northeast
    "New York, NY", "Brooklyn, NY", "Buffalo, NY", "Albany, NY", "Rochester, NY",
    "Boston, MA", "Worcester, MA", "Springfield, MA",
    "Philadelphia, PA", "Pittsburgh, PA", "Allentown, PA",
    "Newark, NJ", "Jersey City, NJ",
    "Hartford, CT", "New Haven, CT",
    "Providence, RI", "Manchester, NH",
    "Baltimore, MD", "Washington, DC",
    # Southeast
    "Atlanta, GA", "Savannah, GA", "Augusta, GA",
    "Miami, FL", "Orlando, FL", "Tampa, FL", "Jacksonville, FL", "Tallahassee, FL",
    "Charlotte, NC", "Raleigh, NC", "Greensboro, NC", "Durham, NC",
    "Columbia, SC", "Charleston, SC",
    "Nashville, TN", "Memphis, TN", "Knoxville, TN", "Chattanooga, TN",
    "Birmingham, AL", "Montgomery, AL", "Huntsville, AL", "Mobile, AL",
    "Jackson, MS", "Baton Rouge, LA", "New Orleans, LA", "Shreveport, LA",
    "Richmond, VA", "Virginia Beach, VA",
    "Louisville, KY", "Lexington, KY",
    "Little Rock, AR",
    # Midwest
    "Chicago, IL", "Springfield, IL", "Rockford, IL",
    "Detroit, MI", "Grand Rapids, MI", "Lansing, MI",
    "Columbus, OH", "Cleveland, OH", "Cincinnati, OH", "Toledo, OH",
    "Indianapolis, IN", "Fort Wayne, IN",
    "Milwaukee, WI", "Madison, WI", "Green Bay, WI",
    "Minneapolis, MN", "St. Paul, MN",
    "Kansas City, MO", "St. Louis, MO",
    "Omaha, NE", "Lincoln, NE",
    "Des Moines, IA",
    "Wichita, KS",
    "Sioux Falls, SD", "Fargo, ND",
    # Southwest
    "Houston, TX", "Dallas, TX", "San Antonio, TX", "Austin, TX",
    "Fort Worth, TX", "El Paso, TX", "Lubbock, TX", "Amarillo, TX", "Waco, TX",
    "Phoenix, AZ", "Tucson, AZ", "Mesa, AZ", "Scottsdale, AZ",
    "Albuquerque, NM",
    "Oklahoma City, OK", "Tulsa, OK",
    "Las Vegas, NV", "Reno, NV",
    # West
    "Los Angeles, CA", "San Diego, CA", "San Francisco, CA", "San Jose, CA",
    "Sacramento, CA", "Fresno, CA", "Bakersfield, CA", "Oakland, CA",
    "Seattle, WA", "Spokane, WA", "Tacoma, WA",
    "Portland, OR", "Eugene, OR", "Salem, OR",
    "Denver, CO", "Colorado Springs, CO",
    "Salt Lake City, UT", "Provo, UT",
    "Boise, ID",
    "Billings, MT", "Missoula, MT", "Bozeman, MT",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


def extract_domain(url):
    if not url:
        return ""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "").split(":")[0]
    except Exception:
        return ""


SKIP_DOMAINS = {
    "yellowpages.com", "yelp.com", "facebook.com", "twitter.com",
    "instagram.com", "linkedin.com", "youtube.com", "google.com",
    "angi.com", "thumbtack.com", "homeadvisor.com", "bbb.org",
    "nextdoor.com", "reddit.com", "wikipedia.org", "mapquest.com",
}


def scrape_yp_page(search_term, location, page=1):
    """Scrape one page of Yellow Pages results. Returns list of prospect dicts."""
    url = "https://www.yellowpages.com/search?" + urllib.parse.urlencode({
        "search_terms":    search_term,
        "geo_location_terms": location,
        "page":            page,
    })

    try:
        resp = requests.get(url, headers=get_headers(), timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    [YP] HTTP {resp.status_code} for '{search_term}' in {location}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # YP wraps each result in a div with class containing "result"
        listings = (
            soup.find_all("div", class_="result")
            or soup.find_all("div", class_=re.compile(r"\bv-card\b"))
            or soup.find_all("article", class_=re.compile(r"listing|result", re.I))
        )

        if not listings:
            # Fallback: find all .business-name links as anchors
            name_links = soup.find_all("a", class_="business-name")
            if not name_links:
                return []
            results = []
            for a in name_links:
                name = a.get_text(strip=True)
                if name and len(name) >= 3:
                    results.append({"name": name, "website": "", "phone": "", "address": location})
            return results

        results = []
        for listing in listings:
            # Name — try multiple selectors
            name = ""
            for sel in [
                lambda el: el.find("a", class_="business-name"),
                lambda el: el.find(class_=re.compile(r"business-name|listing-name|n\s", re.I)),
                lambda el: el.find("h2"),
                lambda el: el.find("h3"),
            ]:
                tag = sel(listing)
                if tag:
                    name = tag.get_text(strip=True)
                    if name:
                        break

            if not name or len(name) < 3:
                continue

            # Website link — YP uses "track-visit-website" class
            website = ""
            ws_tag = (
                listing.find("a", class_=re.compile(r"track-visit-website|website", re.I))
                or listing.find("a", attrs={"data-listing-id": True, "href": re.compile(r"http")})
            )
            if ws_tag:
                href = ws_tag.get("href", "")
                # YP sometimes wraps in a redirect URL — extract actual site
                if "yellowpages.com" in href and "url=" in href:
                    try:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        website = qs.get("url", [href])[0]
                    except Exception:
                        website = href
                elif href.startswith("http") and "yellowpages.com" not in href:
                    website = href

            # Phone
            phone = ""
            ph_tag = listing.find(class_=re.compile(r"\bphones?\b|\bphone\b", re.I))
            if ph_tag:
                phone = re.sub(r"[^\d\-\(\) ]", "", ph_tag.get_text(strip=True)).strip()

            # Address / locality
            address = location
            for addr_cls in [r"\blocality\b", r"\badr\b", r"\baddress\b"]:
                addr_tag = listing.find(class_=re.compile(addr_cls, re.I))
                if addr_tag:
                    address = addr_tag.get_text(strip=True) or location
                    break

            results.append({
                "name":    name,
                "website": website,
                "phone":   phone,
                "address": address,
            })

        return results

    except Exception as exc:
        print(f"    [YP] Exception for '{search_term}' / {location}: {exc}")
        return []


def run():
    seen_domains = set()
    seen_emails  = set()

    # Load existing domains + emails to avoid re-scraping
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
            print(f"[YP] {len(seen_domains)} existing domains loaded — will skip these")
        except Exception as exc:
            print(f"[YP] Could not load prospects_raw.csv: {exc}")

    if os.path.exists(OUTREACH_FILE):
        try:
            oq = pd.read_csv(OUTREACH_FILE).fillna("")
            for e in oq.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
        except Exception:
            pass

    # Rotate which searches we run each cycle so we cover new ground every time
    searches_per_run = int(os.getenv("YP_SEARCHES_PER_RUN", "55"))
    all_combos = [
        (niche, term, loc)
        for niche, term in NICHE_SEARCHES
        for loc in LOCATIONS
    ]
    random.shuffle(all_combos)
    combos = all_combos[:searches_per_run]

    print(f"[YP] Running {len(combos)} searches ({len(all_combos)} total possible)...")

    all_new = []
    niche_counts: dict[str, int] = {}

    for niche, term, location in combos:
        print(f"  [YP:{niche.upper()}] '{term}' in {location}")

        for page in [1, 2]:
            listings = scrape_yp_page(term, location, page)
            if not listings:
                break

            added_this_page = 0
            for listing in listings:
                domain = extract_domain(listing["website"])

                # Skip if we already know this domain
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
                added_this_page += 1

            print(f"    page {page}: {len(listings)} results, {added_this_page} new")
            time.sleep(random.uniform(2.0, 4.0))

        time.sleep(random.uniform(1.0, 2.5))

    if not all_new:
        print("[YP] No new prospects found this run.")
        return

    df_new = pd.DataFrame(all_new)

    # Keep everything — phone-only leads go to Bland.ai call track
    df_with_site    = df_new[df_new["website"].str.strip() != ""].copy()
    df_without_site = df_new[df_new["website"].str.strip() == ""].copy()
    df_without_site = df_without_site[df_without_site["phone"].str.strip() != ""].copy()
    df_without_site["lead_type"] = "PHONE_ONLY"
    df_with_site.drop_duplicates(subset=["website"], inplace=True)
    df_new = pd.concat([df_with_site, df_without_site], ignore_index=True)
    print(f"[YP] {len(df_with_site)} with website, {len(df_without_site)} phone-only (Bland.ai call track)")

    # Append to existing prospects_raw.csv
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
    print(f"\n[YP DONE] {len(df_new)} new prospects added | {len(df_combined)} total in file")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {c}")


if __name__ == "__main__":
    run()
