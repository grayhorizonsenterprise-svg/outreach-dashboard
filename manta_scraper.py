"""
manta_scraper.py — Gray Horizons Enterprise
Manta.com business directory — specifically indexes small/owner-operated businesses.
Different database from Yellow Pages and Superpages.
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
    ("hoa",          "hoa management"),
    ("hoa",          "property management"),
    ("hoa",          "community management"),
    ("hvac",         "hvac"),
    ("hvac",         "air conditioning"),
    ("hvac",         "heating cooling"),
    ("dental",       "dentist"),
    ("dental",       "dental office"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing"),
    ("contractor",   "general contractor"),
    ("contractor",   "remodeling"),
    ("landscaping",  "landscaping"),
    ("landscaping",  "lawn care"),
    ("roofing",      "roofing"),
    ("auto",         "auto repair"),
    ("auto",         "mechanic"),
    ("chiropractic", "chiropractor"),
    ("realestate",   "real estate"),
    ("salon",        "hair salon"),
    ("salon",        "spa"),
]

# Focus on mid-size and smaller cities — less saturated, more owner-operated
LOCATIONS = [
    # Small/mid markets where owner-operators dominate
    "Boise, ID", "Spokane, WA", "Eugene, OR", "Salem, OR", "Medford, OR",
    "Bozeman, MT", "Missoula, MT", "Billings, MT", "Great Falls, MT",
    "Cheyenne, WY", "Casper, WY",
    "Provo, UT", "Ogden, UT", "St. George, UT",
    "Flagstaff, AZ", "Prescott, AZ", "Yuma, AZ",
    "Las Cruces, NM", "Santa Fe, NM", "Albuquerque, NM",
    "Lubbock, TX", "Amarillo, TX", "Waco, TX", "Midland, TX", "Odessa, TX",
    "Tyler, TX", "Beaumont, TX", "Corpus Christi, TX", "Killeen, TX",
    "Sioux Falls, SD", "Rapid City, SD",
    "Fargo, ND", "Bismarck, ND",
    "Billings, MT", "Helena, MT",
    "Lincoln, NE", "Grand Island, NE",
    "Topeka, KS", "Wichita, KS", "Lawrence, KS",
    "Columbia, MO", "Springfield, MO", "Joplin, MO",
    "Fort Smith, AR", "Jonesboro, AR", "Fayetteville, AR",
    "Shreveport, LA", "Lafayette, LA", "Monroe, LA",
    "Jackson, MS", "Gulfport, MS", "Hattiesburg, MS",
    "Huntsville, AL", "Montgomery, AL", "Mobile, AL", "Tuscaloosa, AL",
    "Chattanooga, TN", "Knoxville, TN", "Clarksville, TN", "Murfreesboro, TN",
    "Wilmington, NC", "Fayetteville, NC", "Asheville, NC", "Greenville, NC",
    "Myrtle Beach, SC", "Spartanburg, SC", "Greenville, SC", "Anderson, SC",
    "Savannah, GA", "Augusta, GA", "Macon, GA", "Columbus, GA",
    "Gainesville, FL", "Pensacola, FL", "Tallahassee, FL", "Fort Myers, FL",
    "Lakeland, FL", "Daytona Beach, FL", "Palm Bay, FL",
    "Roanoke, VA", "Lynchburg, VA", "Charlottesville, VA",
    "Frederick, MD", "Hagerstown, MD",
    "Reading, PA", "Erie, PA", "Scranton, PA", "Harrisburg, PA",
    "Syracuse, NY", "Utica, NY", "Binghamton, NY", "Ithaca, NY",
    "Springfield, MA", "Lowell, MA", "New Bedford, MA",
    "Manchester, NH", "Nashua, NH", "Concord, NH",
    "Burlington, VT", "Rutland, VT",
    "Portland, ME", "Bangor, ME",
    "Fort Wayne, IN", "South Bend, IN", "Evansville, IN",
    "Green Bay, WI", "Appleton, WI", "Oshkosh, WI", "Racine, WI",
    "Duluth, MN", "Rochester, MN", "St. Cloud, MN",
    "Davenport, IA", "Cedar Rapids, IA", "Des Moines, IA", "Dubuque, IA",
    "Rockford, IL", "Peoria, IL", "Champaign, IL", "Springfield, IL",
    "Toledo, OH", "Akron, OH", "Dayton, OH", "Canton, OH", "Youngstown, OH",
    "Lansing, MI", "Flint, MI", "Kalamazoo, MI", "Traverse City, MI",
    # Also some mid-size metros
    "Colorado Springs, CO", "Pueblo, CO", "Fort Collins, CO", "Boulder, CO",
    "Reno, NV", "Henderson, NV", "Carson City, NV",
    "Bakersfield, CA", "Fresno, CA", "Stockton, CA", "Modesto, CA",
    "Oxnard, CA", "Ventura, CA", "Santa Barbara, CA",
    "Tacoma, WA", "Bellevue, WA", "Everett, WA", "Bellingham, WA",
]

SKIP_DOMAINS = {
    "manta.com", "yellowpages.com", "superpages.com", "yelp.com",
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "youtube.com", "google.com", "angi.com", "thumbtack.com",
    "homeadvisor.com", "bbb.org", "nextdoor.com", "wikipedia.org",
}

CORPORATE_NAME_SKIP = [
    "hospital", "health system", "insurance", "university", "college",
    "school district", "government", "department of", "city of", "county of",
    "nationwide", "national chain", "nonprofit", "foundation",
]


def get_headers():
    return {
        "User-Agent":              random.choice(USER_AGENTS),
        "Accept":                  "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":         "en-US,en;q=0.9",
        "Accept-Encoding":         "gzip, deflate, br",
        "Connection":              "keep-alive",
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


def scrape_manta_page(search_term, location, page=1):
    """Scrape one page of Manta results. Returns list of prospect dicts."""
    url = "https://www.manta.com/mb?" + urllib.parse.urlencode({
        "search_term": search_term,
        "location":    location,
        "pg":          page,
    })

    try:
        resp = requests.get(url, headers=get_headers(), timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    [MT] HTTP {resp.status_code} — '{search_term}' in {location}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Manta business cards — try multiple known selectors
        cards = (
            soup.find_all("div",     class_=re.compile(r"\bcard\b",     re.I))
            or soup.find_all("li",   class_=re.compile(r"\blisting\b",  re.I))
            or soup.find_all("div",  class_=re.compile(r"\bbusiness\b", re.I))
            or soup.find_all("article")
        )

        if not cards:
            return []

        results = []
        for card in cards:
            # Name
            name = ""
            for fn in [
                lambda el: el.find("a",  class_=re.compile(r"business-name|company-name|listing-name", re.I)),
                lambda el: el.find(      class_=re.compile(r"business-name|company-name|title",        re.I)),
                lambda el: el.find("h2"),
                lambda el: el.find("h3"),
            ]:
                tag = fn(card)
                if tag:
                    name = tag.get_text(strip=True)
                    if name:
                        break

            if not name or len(name) < 3:
                continue

            name_lower = name.lower()
            if any(p in name_lower for p in CORPORATE_NAME_SKIP):
                continue

            # Website
            website = ""
            for a in card.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "manta.com" not in href:
                    domain = extract_domain(href)
                    if domain and domain not in SKIP_DOMAINS:
                        website = href
                        break

            # Phone
            phone = ""
            ph = card.find(class_=re.compile(r"\bphone\b|\btel\b", re.I))
            if ph:
                phone = re.sub(r"[^\d\-\(\)\+\s]", "", ph.get_text(strip=True)).strip()

            # Address
            address = location
            addr = card.find(class_=re.compile(r"\baddress\b|\blocality\b|\badr\b", re.I))
            if addr:
                txt = addr.get_text(strip=True)
                if txt:
                    address = txt

            results.append({
                "name":    name,
                "website": website,
                "phone":   phone,
                "address": address,
            })

        return results

    except Exception as exc:
        print(f"    [MT] Exception — '{search_term}' / {location}: {exc}")
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
            print(f"[MT] {len(seen_domains)} existing domains loaded — skipping these")
        except Exception as exc:
            print(f"[MT] Could not load prospects_raw.csv: {exc}")

    if os.path.exists(OUTREACH_FILE):
        try:
            oq = pd.read_csv(OUTREACH_FILE).fillna("")
            for e in oq.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
        except Exception:
            pass

    searches_per_run = int(os.getenv("MT_SEARCHES_PER_RUN", "40"))
    all_combos = [
        (niche, term, loc)
        for niche, term in NICHE_SEARCHES
        for loc in LOCATIONS
    ]
    random.shuffle(all_combos)
    combos = all_combos[:searches_per_run]

    print(f"[MT] Running {len(combos)} searches ({len(all_combos)} total possible)...")

    all_new    = []
    niche_counts: dict[str, int] = {}

    for niche, term, location in combos:
        print(f"  [MT:{niche.upper()}] '{term}' in {location}")

        for page in [1, 2]:
            listings = scrape_manta_page(term, location, page)
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

            print(f"    page {page}: {len(listings)} found, {added} new")
            time.sleep(random.uniform(2.0, 4.0))

        time.sleep(random.uniform(1.5, 3.0))

    if not all_new:
        print("[MT] No new prospects this run.")
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
    print(f"\n[MT DONE] {len(df_new)} new | {len(df_combined)} total in file")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {c}")


if __name__ == "__main__":
    run()
