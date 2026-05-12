"""
manta_scraper.py — Gray Horizons Enterprise
Finds small/owner-operated businesses via DuckDuckGo search.
Replaced direct manta.com scraping (blocked by 403 on cloud IPs).
Appends to prospects_raw.csv.
"""

import pandas as pd
import re
import time
import random
import os
import sys
import urllib.parse
from duckduckgo_search import DDGS

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

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SKIP_DOMAINS = {
    "manta.com", "yellowpages.com", "superpages.com", "yelp.com",
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "youtube.com", "google.com", "angi.com", "thumbtack.com",
    "homeadvisor.com", "bbb.org", "nextdoor.com", "wikipedia.org",
    "indeed.com", "glassdoor.com", "mapquest.com",
}


def extract_domain(url):
    if not url:
        return ""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "").split(":")[0]
    except Exception:
        return ""


def run():
    seen_emails = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE).fillna("")
            seen_emails = set(df_ex.get("email", pd.Series(dtype=str)).str.lower().dropna())
        except Exception:
            pass
    if os.path.exists(OUTREACH_FILE):
        try:
            oq = pd.read_csv(OUTREACH_FILE).fillna("")
            seen_emails |= set(oq.get("email", pd.Series(dtype=str)).str.lower().dropna())
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

    print(f"[MT] Running {len(combos)} DuckDuckGo searches...")

    all_new: list[dict] = []
    niche_counts: dict[str, int] = {}
    ddgs = DDGS()

    for niche, term, location in combos:
        query = f"{term} {location} email contact -site:yelp.com -site:yellowpages.com"
        print(f"  [MT:{niche.upper()}] '{term}' in {location}")
        try:
            results = list(ddgs.text(query, max_results=6))
            for r in results:
                body = r.get("body", "")
                url  = r.get("href", "")
                name = r.get("title", "")[:60]
                domain = extract_domain(url)
                if domain in SKIP_DOMAINS:
                    continue
                emails = [e for e in EMAIL_RE.findall(body)
                          if not e.endswith((".png", ".jpg", ".gif"))]
                email = emails[0].lower() if emails else ""
                if not email or email in seen_emails:
                    continue
                seen_emails.add(email)
                all_new.append({
                    "company":          name,
                    "website":          url,
                    "email":            email,
                    "contact_page_url": "",
                    "location":         location,
                    "niche":            niche,
                    "phone":            "",
                })
                niche_counts[niche] = niche_counts.get(niche, 0) + 1
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as exc:
            print(f"    [MT] Error: {exc}")

    if not all_new:
        print("[MT] No new prospects this run.")
        return

    df_new = pd.DataFrame(all_new).drop_duplicates(subset=["email"])
    if os.path.exists(OUTPUT_FILE):
        try:
            df_existing = pd.read_csv(OUTPUT_FILE).fillna("")
            if "phone" not in df_existing.columns:
                df_existing["phone"] = ""
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=["email"], inplace=True)
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
