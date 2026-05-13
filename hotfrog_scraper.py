"""
hotfrog_scraper.py — Gray Horizons Enterprise
National lead scraper: DDG search + page-fetch across 300+ US cities.
Appends to prospects_raw.csv. Targets small business owners across all niches.
"""

import pandas as pd
import re
import time
import random
import os
import sys
import urllib.parse
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

NICHE_SEARCHES = [
    ("hvac",         "hvac contractor"),
    ("hvac",         "air conditioning repair"),
    ("hvac",         "heating repair"),
    ("hvac",         "furnace repair"),
    ("hvac",         "AC installation"),
    ("dental",       "dentist office"),
    ("dental",       "dental clinic"),
    ("dental",       "family dentist"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing services"),
    ("plumbing",     "drain cleaning"),
    ("contractor",   "general contractor"),
    ("contractor",   "home remodeling"),
    ("contractor",   "home renovation"),
    ("landscaping",  "landscaping company"),
    ("landscaping",  "lawn care service"),
    ("landscaping",  "lawn mowing"),
    ("roofing",      "roofing contractor"),
    ("roofing",      "roof repair"),
    ("hoa",          "property management"),
    ("hoa",          "HOA management"),
    ("chiropractic", "chiropractor"),
    ("auto",         "auto repair shop"),
    ("auto",         "auto mechanic"),
    ("electrician",  "electrician"),
    ("electrician",  "electrical contractor"),
    ("pest_control", "pest control"),
    ("pest_control", "exterminator"),
    ("salon",        "hair salon"),
    ("salon",        "beauty salon"),
    ("veterinary",   "veterinarian"),
    ("veterinary",   "animal hospital"),
    ("optometry",    "optometrist"),
    ("cleaning",     "house cleaning"),
    ("cleaning",     "commercial cleaning"),
    ("painting",     "painting contractor"),
    ("painting",     "house painter"),
    ("realestate",   "real estate agent"),
    ("realestate",   "realtor"),
    ("insurance",    "insurance agent"),
    ("mortgage",     "mortgage broker"),
    ("gym",          "gym owner"),
    ("gym",          "personal trainer"),
    ("restaurant",   "restaurant owner"),
    ("medspa",       "med spa"),
]

# 300+ US cities covering all 50 states
LOCATIONS = [
    # Alabama
    "Birmingham AL","Montgomery AL","Huntsville AL","Mobile AL","Tuscaloosa AL",
    # Alaska
    "Anchorage AK","Fairbanks AK",
    # Arizona
    "Phoenix AZ","Tucson AZ","Mesa AZ","Scottsdale AZ","Chandler AZ","Gilbert AZ","Tempe AZ","Peoria AZ","Surprise AZ","Glendale AZ",
    # Arkansas
    "Little Rock AR","Fort Smith AR","Fayetteville AR","Springdale AR",
    # California
    "Los Angeles CA","San Diego CA","San Jose CA","San Francisco CA","Fresno CA","Sacramento CA","Long Beach CA","Oakland CA","Bakersfield CA","Anaheim CA","Santa Ana CA","Riverside CA","Stockton CA","Irvine CA","Fremont CA","San Bernardino CA","Modesto CA","Fontana CA","Moreno Valley CA","Glendale CA","Santa Clarita CA","Garden Grove CA","Rancho Cucamonga CA","Oceanside CA","Corona CA","Lancaster CA","Palmdale CA","Salinas CA","Hayward CA","Sunnyvale CA","Visalia CA","Elk Grove CA","Roseville CA","Torrance CA","Pomona CA","Escondido CA","Pasadena CA","Orange CA",
    # Colorado
    "Denver CO","Colorado Springs CO","Aurora CO","Fort Collins CO","Lakewood CO","Pueblo CO","Boulder CO","Greeley CO",
    # Connecticut
    "Bridgeport CT","New Haven CT","Hartford CT","Stamford CT","Waterbury CT",
    # Delaware
    "Wilmington DE","Dover DE",
    # Florida
    "Jacksonville FL","Miami FL","Tampa FL","Orlando FL","St Petersburg FL","Hialeah FL","Tallahassee FL","Fort Lauderdale FL","Port St Lucie FL","Cape Coral FL","Pembroke Pines FL","Hollywood FL","Miramar FL","Gainesville FL","Coral Springs FL","Clearwater FL","West Palm Beach FL","Lakeland FL","Pompano Beach FL","Davie FL","Boca Raton FL","Deltona FL","Palm Bay FL","Daytona Beach FL",
    # Georgia
    "Atlanta GA","Columbus GA","Augusta GA","Macon GA","Savannah GA","Athens GA","Sandy Springs GA","Roswell GA","Albany GA","Johns Creek GA",
    # Hawaii
    "Honolulu HI","Pearl City HI",
    # Idaho
    "Boise ID","Nampa ID","Meridian ID","Idaho Falls ID",
    # Illinois
    "Chicago IL","Aurora IL","Joliet IL","Naperville IL","Rockford IL","Springfield IL","Elgin IL","Peoria IL","Champaign IL","Waukegan IL",
    # Indiana
    "Indianapolis IN","Fort Wayne IN","Evansville IN","South Bend IN","Carmel IN","Fishers IN","Bloomington IN","Hammond IN","Gary IN",
    # Iowa
    "Des Moines IA","Cedar Rapids IA","Davenport IA","Sioux City IA","Iowa City IA",
    # Kansas
    "Wichita KS","Overland Park KS","Kansas City KS","Topeka KS","Olathe KS",
    # Kentucky
    "Louisville KY","Lexington KY","Bowling Green KY","Owensboro KY","Covington KY",
    # Louisiana
    "New Orleans LA","Baton Rouge LA","Shreveport LA","Metairie LA","Lafayette LA","Lake Charles LA",
    # Maine
    "Portland ME","Lewiston ME",
    # Maryland
    "Baltimore MD","Frederick MD","Rockville MD","Gaithersburg MD","Bowie MD",
    # Massachusetts
    "Boston MA","Worcester MA","Springfield MA","Cambridge MA","Lowell MA","Brockton MA","New Bedford MA","Quincy MA",
    # Michigan
    "Detroit MI","Grand Rapids MI","Warren MI","Sterling Heights MI","Ann Arbor MI","Lansing MI","Flint MI","Dearborn MI","Livonia MI","Troy MI",
    # Minnesota
    "Minneapolis MN","Saint Paul MN","Rochester MN","Duluth MN","Bloomington MN","Brooklyn Park MN","Plymouth MN",
    # Mississippi
    "Jackson MS","Gulfport MS","Southaven MS","Biloxi MS",
    # Missouri
    "Kansas City MO","St Louis MO","Springfield MO","Columbia MO","Independence MO","St Joseph MO",
    # Montana
    "Billings MT","Missoula MT","Great Falls MT",
    # Nebraska
    "Omaha NE","Lincoln NE","Bellevue NE",
    # Nevada
    "Las Vegas NV","Henderson NV","Reno NV","North Las Vegas NV","Sparks NV",
    # New Hampshire
    "Manchester NH","Nashua NH","Concord NH",
    # New Jersey
    "Newark NJ","Jersey City NJ","Paterson NJ","Elizabeth NJ","Trenton NJ","Edison NJ","Woodbridge NJ",
    # New Mexico
    "Albuquerque NM","Las Cruces NM","Rio Rancho NM","Santa Fe NM",
    # New York
    "New York NY","Buffalo NY","Rochester NY","Yonkers NY","Syracuse NY","Albany NY","New Rochelle NY","Mount Vernon NY","Schenectady NY","Utica NY",
    # North Carolina
    "Charlotte NC","Raleigh NC","Greensboro NC","Durham NC","Winston-Salem NC","Fayetteville NC","Cary NC","Wilmington NC","High Point NC","Concord NC",
    # North Dakota
    "Fargo ND","Bismarck ND","Grand Forks ND",
    # Ohio
    "Columbus OH","Cleveland OH","Cincinnati OH","Toledo OH","Akron OH","Dayton OH","Parma OH","Canton OH","Youngstown OH","Lorain OH",
    # Oklahoma
    "Oklahoma City OK","Tulsa OK","Norman OK","Broken Arrow OK","Lawton OK","Edmond OK",
    # Oregon
    "Portland OR","Salem OR","Eugene OR","Gresham OR","Hillsboro OR","Beaverton OR","Bend OR",
    # Pennsylvania
    "Philadelphia PA","Pittsburgh PA","Allentown PA","Erie PA","Reading PA","Scranton PA","Bethlehem PA","Lancaster PA","Harrisburg PA",
    # Rhode Island
    "Providence RI","Cranston RI","Warwick RI",
    # South Carolina
    "Columbia SC","Charleston SC","North Charleston SC","Mount Pleasant SC","Greenville SC","Spartanburg SC",
    # South Dakota
    "Sioux Falls SD","Rapid City SD",
    # Tennessee
    "Nashville TN","Memphis TN","Knoxville TN","Chattanooga TN","Clarksville TN","Murfreesboro TN","Franklin TN","Johnson City TN",
    # Texas
    "Houston TX","San Antonio TX","Dallas TX","Austin TX","Fort Worth TX","El Paso TX","Arlington TX","Corpus Christi TX","Plano TX","Laredo TX","Lubbock TX","Garland TX","Irving TX","Amarillo TX","Grand Prairie TX","Brownsville TX","Frisco TX","McKinney TX","Denton TX","Midland TX","Waco TX","Odessa TX","Killeen TX","Mesquite TX","Pasadena TX","Abilene TX","Round Rock TX","McAllen TX",
    # Utah
    "Salt Lake City UT","West Valley City UT","Provo UT","West Jordan UT","Orem UT","Sandy UT","Ogden UT",
    # Vermont
    "Burlington VT",
    # Virginia
    "Virginia Beach VA","Norfolk VA","Chesapeake VA","Richmond VA","Newport News VA","Alexandria VA","Hampton VA","Roanoke VA","Suffolk VA",
    # Washington
    "Seattle WA","Spokane WA","Tacoma WA","Vancouver WA","Bellevue WA","Kent WA","Everett WA","Renton WA","Federal Way WA","Kirkland WA",
    # West Virginia
    "Charleston WV","Huntington WV","Morgantown WV",
    # Wisconsin
    "Milwaukee WI","Madison WI","Green Bay WI","Kenosha WI","Racine WI","Appleton WI","Oshkosh WI",
    # Wyoming
    "Cheyenne WY","Casper WY",
]

SKIP_DOMAINS = {
    "hotfrog.com","yellowpages.com","superpages.com","yelp.com",
    "facebook.com","twitter.com","instagram.com","linkedin.com",
    "youtube.com","google.com","angi.com","thumbtack.com",
    "homeadvisor.com","bbb.org","nextdoor.com","wikipedia.org","indeed.com",
    "glassdoor.com","monster.com","ziprecruiter.com","careerbuilder.com",
    "healthgrades.com","zocdoc.com","vitals.com","ratemds.com",
    "angieslist.com","houzz.com","porch.com","buildzoom.com",
}

BAD_PREFIXES = {
    'abuse','spam','report','complaints','privacy','legal','billing',
    'webmaster','postmaster','mailer','sales','marketing','hr',
    'careers','jobs','news','newsletter','press','media','helpdesk',
    'support','ticket','hrprocessing','pressinquiries','donotreply',
    'noreply','no-reply',
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

def is_clean_email(email: str) -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith(('.png','.jpg','.gif','.webp','.svg')):
        return False
    prefix = e.split('@')[0] if '@' in e else e
    if any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES):
        return False
    return True

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def fetch_emails(url: str) -> list:
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=8, verify=False)
        if r.status_code != 200:
            return []
        text = r.text
        for a in BeautifulSoup(text, "html.parser").find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {a['href'][7:].split('?')[0]}"
        return list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text) if is_clean_email(e.lower())))
    except Exception:
        return []


def run():
    seen_emails = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE, dtype=str).fillna("")
            seen_emails = set(df_ex.get("email", pd.Series(dtype=str)).str.lower().dropna())
        except Exception:
            pass

    searches_per_run = int(os.getenv("SCRAPER_SEARCHES_PER_RUN", "100"))
    all_combos = [(n, t, loc) for n, t in NICHE_SEARCHES for loc in LOCATIONS]
    random.shuffle(all_combos)
    combos = all_combos[:searches_per_run]

    print(f"[HOTFROG] Running {len(combos)} DDG searches across {len(LOCATIONS)} cities...")
    all_new: dict[str, dict] = {}
    niche_counts: dict[str, int] = {}
    ddgs = DDGS()

    for niche, term, location in combos:
        query = f"{term} {location} email contact"
        print(f"  [HF:{niche.upper()}] '{term}' in {location}")
        try:
            results = list(ddgs.text(query, max_results=6))
            for r in results:
                url    = r.get("href", "")
                name   = r.get("title", "")[:60]
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS or not url:
                    continue
                for email in fetch_emails(url):
                    if email in seen_emails:
                        continue
                    seen_emails.add(email)
                    all_new[email] = {
                        "company": name, "website": url, "email": email,
                        "contact_page_url": "", "location": location,
                        "niche": niche, "phone": "",
                    }
                    niche_counts[niche] = niche_counts.get(niche, 0) + 1
                    print(f"    [+] {email}")
                time.sleep(random.uniform(0.3, 0.6))
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"    [HF] Error: {e}"); time.sleep(2)

    if not all_new:
        print("[HOTFROG] No new leads this run.")
        return

    df_new = pd.DataFrame(list(all_new.values()))
    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE, dtype=str).fillna("")
            for col in ["phone", "contact_page_url"]:
                if col not in df_ex.columns:
                    df_ex[col] = ""
            df_combined = pd.concat([df_ex, df_new], ignore_index=True).drop_duplicates(subset=["email"])
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    df_combined.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[HOTFROG DONE] {len(df_new)} new | {len(df_combined)} total")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():14s}: {c}")


if __name__ == "__main__":
    run()
