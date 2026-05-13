"""
chamberofcommerce_scraper.py — Gray Horizons Enterprise
National lead scraper: DDG search + page-fetch across 300+ US cities.
Complementary niche set to hotfrog_scraper. Appends to prospects_raw.csv.
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
    ("hvac",         "hvac company"),
    ("hvac",         "heating cooling"),
    ("hvac",         "duct cleaning"),
    ("dental",       "dental practice"),
    ("dental",       "cosmetic dentist"),
    ("dental",       "pediatric dentist"),
    ("plumbing",     "plumbing company"),
    ("plumbing",     "water heater repair"),
    ("plumbing",     "emergency plumber"),
    ("contractor",   "kitchen remodel"),
    ("contractor",   "bathroom remodel"),
    ("contractor",   "home builder"),
    ("landscaping",  "landscaper"),
    ("landscaping",  "irrigation company"),
    ("landscaping",  "tree service"),
    ("roofing",      "roofer"),
    ("roofing",      "roof replacement"),
    ("roofing",      "gutter company"),
    ("hoa",          "community management"),
    ("hoa",          "condominium management"),
    ("chiropractic", "chiropractic clinic"),
    ("chiropractic", "sports chiropractor"),
    ("auto",         "auto body shop"),
    ("auto",         "car repair"),
    ("auto",         "transmission repair"),
    ("electrician",  "electrical company"),
    ("electrician",  "lighting installation"),
    ("pest_control", "pest removal"),
    ("pest_control", "termite control"),
    ("salon",        "nail salon"),
    ("salon",        "day spa"),
    ("salon",        "barbershop"),
    ("veterinary",   "veterinary clinic"),
    ("veterinary",   "pet hospital"),
    ("optometry",    "eye doctor"),
    ("optometry",    "vision center"),
    ("cleaning",     "maid service"),
    ("cleaning",     "janitorial service"),
    ("painting",     "interior painter"),
    ("painting",     "exterior painting"),
    ("realestate",   "real estate broker"),
    ("realestate",   "property manager"),
    ("insurance",    "insurance broker"),
    ("mortgage",     "loan officer"),
    ("gym",          "fitness studio"),
    ("gym",          "CrossFit gym"),
    ("restaurant",   "catering company"),
    ("medspa",       "aesthetic clinic"),
    ("flooring",     "flooring company"),
    ("moving",       "moving company"),
]

# Different set of cities from hotfrog to maximize national coverage
LOCATIONS = [
    # Southeast focus
    "Pensacola FL","Fort Myers FL","Naples FL","Ocala FL","Melbourne FL","Palm Coast FL",
    "Macon GA","Valdosta GA","Warner Robins GA","Gainesville GA","Dalton GA",
    "Chattanooga TN","Murfreesboro TN","Franklin TN","Johnson City TN","Kingsport TN",
    "Huntsville AL","Dothan AL","Decatur AL","Florence AL","Auburn AL",
    "Gulfport MS","Biloxi MS","Hattiesburg MS","Meridian MS",
    "Shreveport LA","Lafayette LA","Lake Charles LA","Monroe LA","Alexandria LA",
    "Little Rock AR","Fort Smith AR","Springdale AR","Jonesboro AR","Conway AR",
    "Columbia SC","North Charleston SC","Greenville SC","Spartanburg SC","Rock Hill SC",
    # Northeast focus
    "Albany NY","Syracuse NY","Utica NY","Binghamton NY","Poughkeepsie NY",
    "Worcester MA","Springfield MA","Lowell MA","Cambridge MA","Brockton MA",
    "Providence RI","Cranston RI","Warwick RI","Pawtucket RI",
    "Bridgeport CT","New Haven CT","Hartford CT","Stamford CT","Waterbury CT",
    "Newark NJ","Jersey City NJ","Paterson NJ","Elizabeth NJ","Trenton NJ",
    "Allentown PA","Erie PA","Reading PA","Scranton PA","Bethlehem PA","Lancaster PA",
    "Wilmington DE","Dover DE",
    "Frederick MD","Rockville MD","Gaithersburg MD","Bowie MD","Hagerstown MD",
    "Portsmouth NH","Nashua NH","Concord NH","Manchester NH",
    "Burlington VT","Rutland VT",
    "Portland ME","Lewiston ME","Bangor ME",
    # Midwest focus
    "Rockford IL","Peoria IL","Springfield IL","Champaign IL","Elgin IL","Naperville IL",
    "Fort Wayne IN","Evansville IN","South Bend IN","Bloomington IN","Lafayette IN",
    "Cedar Rapids IA","Davenport IA","Sioux City IA","Iowa City IA","Waterloo IA",
    "Wichita KS","Topeka KS","Olathe KS","Overland Park KS","Salina KS",
    "Springfield MO","Columbia MO","Independence MO","St Joseph MO","Joplin MO",
    "Fargo ND","Bismarck ND","Grand Forks ND","Minot ND",
    "Sioux Falls SD","Rapid City SD","Aberdeen SD",
    "Omaha NE","Lincoln NE","Bellevue NE","Grand Island NE",
    "Green Bay WI","Kenosha WI","Racine WI","Appleton WI","Oshkosh WI","Janesville WI",
    "Duluth MN","Rochester MN","Bloomington MN","Brooklyn Park MN","Plymouth MN",
    "Toledo OH","Akron OH","Dayton OH","Parma OH","Canton OH","Youngstown OH",
    "Lansing MI","Flint MI","Ann Arbor MI","Sterling Heights MI","Dearborn MI","Troy MI",
    # Mountain West focus
    "Fort Collins CO","Lakewood CO","Pueblo CO","Boulder CO","Greeley CO","Arvada CO",
    "Boise ID","Nampa ID","Meridian ID","Idaho Falls ID","Pocatello ID",
    "Billings MT","Missoula MT","Great Falls MT","Bozeman MT","Butte MT",
    "Las Cruces NM","Rio Rancho NM","Roswell NM","Farmington NM",
    "Salt Lake City UT","West Valley City UT","Provo UT","Ogden UT","Sandy UT",
    "Casper WY","Cheyenne WY","Gillette WY",
    "Reno NV","North Las Vegas NV","Sparks NV","Elko NV",
    # Southwest focus
    "Chandler AZ","Gilbert AZ","Tempe AZ","Peoria AZ","Surprise AZ","Yuma AZ","Flagstaff AZ",
    "El Paso TX","Lubbock TX","Amarillo TX","Abilene TX","Odessa TX","Midland TX",
    "Waco TX","Killeen TX","Denton TX","Frisco TX","McKinney TX","Round Rock TX","McAllen TX",
    "Albuquerque NM","Santa Fe NM","Las Cruces NM",
    # Pacific Northwest / West
    "Spokane WA","Tacoma WA","Vancouver WA","Bellevue WA","Everett WA","Renton WA",
    "Salem OR","Eugene OR","Gresham OR","Hillsboro OR","Beaverton OR","Bend OR",
    "Fresno CA","Bakersfield CA","Stockton CA","Modesto CA","Visalia CA","Salinas CA",
    "Hayward CA","Fremont CA","Santa Clarita CA","Rancho Cucamonga CA","Fontana CA",
    "Honolulu HI","Pearl City HI","Kailua HI","Hilo HI",
    "Anchorage AK","Fairbanks AK","Juneau AK",
]

SKIP_DOMAINS = {
    "chamberofcommerce.com","yellowpages.com","superpages.com","yelp.com",
    "facebook.com","twitter.com","instagram.com","linkedin.com",
    "youtube.com","google.com","angi.com","thumbtack.com",
    "homeadvisor.com","bbb.org","nextdoor.com","wikipedia.org","indeed.com",
    "glassdoor.com","healthgrades.com","zocdoc.com","houzz.com","porch.com",
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

    print(f"[COC] Running {len(combos)} DDG searches across {len(LOCATIONS)} cities...")
    all_new: dict[str, dict] = {}
    niche_counts: dict[str, int] = {}
    ddgs = DDGS()

    for niche, term, location in combos:
        query = f"{term} {location} owner email contact small business"
        print(f"  [COC:{niche.upper()}] '{term}' in {location}")
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
            print(f"    [COC] Error: {e}"); time.sleep(2)

    if not all_new:
        print("[COC] No new leads this run.")
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
    print(f"\n[COC DONE] {len(df_new)} new | {len(df_combined)} total")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():14s}: {c}")


if __name__ == "__main__":
    run()
