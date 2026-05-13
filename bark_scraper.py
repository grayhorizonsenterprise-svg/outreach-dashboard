"""
bark_scraper.py — Gray Horizons Enterprise
National lead scraper: DDG search + page-fetch across 300+ US cities.
High-intent professional/service queries. Appends to prospects_raw.csv.
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
    ("hvac",         "HVAC technician"),
    ("hvac",         "air conditioning installation"),
    ("hvac",         "heat pump repair"),
    ("dental",       "orthodontist"),
    ("dental",       "dental implants"),
    ("dental",       "emergency dentist"),
    ("plumbing",     "plumbing repair"),
    ("plumbing",     "sewer line repair"),
    ("plumbing",     "water damage plumber"),
    ("contractor",   "roofing and siding"),
    ("contractor",   "deck builder"),
    ("contractor",   "addition contractor"),
    ("landscaping",  "lawn maintenance"),
    ("landscaping",  "hardscape contractor"),
    ("landscaping",  "sprinkler system"),
    ("roofing",      "storm damage roof"),
    ("roofing",      "metal roofing"),
    ("roofing",      "flat roof repair"),
    ("hoa",          "homeowners association management"),
    ("hoa",          "condo association"),
    ("chiropractic", "back pain chiropractor"),
    ("chiropractic", "wellness chiropractic"),
    ("auto",         "auto electrical repair"),
    ("auto",         "oil change service"),
    ("auto",         "brake repair"),
    ("electrician",  "residential electrician"),
    ("electrician",  "commercial electrician"),
    ("electrician",  "generator installation"),
    ("pest_control", "rodent control"),
    ("pest_control", "mosquito control"),
    ("salon",        "hair stylist"),
    ("salon",        "color specialist salon"),
    ("salon",        "lash studio"),
    ("veterinary",   "emergency vet"),
    ("veterinary",   "cat clinic"),
    ("optometry",    "contact lens fitting"),
    ("optometry",    "eye exam"),
    ("cleaning",     "carpet cleaning"),
    ("cleaning",     "pressure washing"),
    ("painting",     "deck staining"),
    ("painting",     "commercial painting"),
    ("realestate",   "listing agent"),
    ("realestate",   "buyer agent"),
    ("insurance",    "life insurance agent"),
    ("insurance",    "auto insurance agent"),
    ("mortgage",     "home loan specialist"),
    ("mortgage",     "refinance specialist"),
    ("gym",          "yoga studio"),
    ("gym",          "personal training studio"),
    ("restaurant",   "food truck"),
    ("medspa",       "botox clinic"),
    ("flooring",     "hardwood floor installation"),
    ("moving",       "local moving company"),
    ("storage",      "self storage facility"),
    ("tutoring",     "tutoring center"),
    ("photography",  "wedding photographer"),
]

# Third set of cities — suburb and mid-size markets underserved by competitors
LOCATIONS = [
    # Texas suburbs and mid-size
    "Sugar Land TX","Pearland TX","League City TX","Carrollton TX","Richardson TX",
    "Allen TX","Lewisville TX","Tyler TX","Beaumont TX","Wichita Falls TX",
    "San Angelo TX","Longview TX","Bryan TX","College Station TX","Temple TX",
    # Florida suburbs
    "Kissimmee FL","St Cloud FL","Sanford FL","Apopka FL","Altamonte Springs FL",
    "Clearwater FL","Largo FL","Brandon FL","Sarasota FL","Bradenton FL",
    "Lakeland FL","Winter Haven FL","Spring Hill FL","New Port Richey FL",
    "Deerfield Beach FL","Margate FL","Coral Gables FL","Hialeah Gardens FL",
    # Georgia suburbs
    "Marietta GA","Smyrna GA","Kennesaw GA","Canton GA","Lawrenceville GA",
    "Duluth GA","Peachtree City GA","Newnan GA","Douglasville GA","Carrollton GA",
    # North Carolina suburbs
    "Apex NC","Morrisville NC","Holly Springs NC","Garner NC","Durham NC",
    "Gastonia NC","Kannapolis NC","Huntersville NC","Mooresville NC","Statesville NC",
    # Virginia
    "Roanoke VA","Lynchburg VA","Charlottesville VA","Harrisonburg VA","Manassas VA",
    "Sterling VA","Woodbridge VA","Fredericksburg VA","Hampton VA","Newport News VA",
    # Pennsylvania suburbs
    "Allentown PA","Bethlehem PA","Reading PA","York PA","Lancaster PA",
    "Chester PA","Chester County PA","Montgomery County PA","Bucks County PA",
    # Ohio suburbs
    "Dublin OH","Westerville OH","Hilliard OH","Grove City OH","Delaware OH",
    "Medina OH","Mentor OH","Strongsville OH","Elyria OH","Findlay OH",
    # Michigan suburbs
    "Novi MI","Southfield MI","Pontiac MI","Rochester Hills MI","Macomb MI",
    "Kalamazoo MI","Battle Creek MI","Saginaw MI","Bay City MI","Midland MI",
    # Illinois suburbs
    "Schaumburg IL","Arlington Heights IL","Bolingbrook IL","Palatine IL","Skokie IL",
    "Waukegan IL","Cicero IL","Springfield IL","Champaign IL","Bloomington IL",
    # Indiana suburbs
    "Carmel IN","Fishers IN","Noblesville IN","Greenwood IN","Lawrence IN",
    "Anderson IN","Muncie IN","Terre Haute IN","Kokomo IN","Richmond IN",
    # Missouri suburbs
    "St Charles MO","O'Fallon MO","Florissant MO","Chesterfield MO","Ballwin MO",
    "Springfield MO","Independence MO","Lees Summit MO","Blue Springs MO",
    # Colorado suburbs
    "Arvada CO","Westminster CO","Thornton CO","Centennial CO","Highlands Ranch CO",
    "Parker CO","Castle Rock CO","Broomfield CO","Commerce City CO","Loveland CO",
    # Washington suburbs
    "Redmond WA","Sammamish WA","Bellevue WA","Kirkland WA","Kennewick WA",
    "Richland WA","Pasco WA","Yakima WA","Bellingham WA","Olympia WA",
    # Arizona suburbs
    "Avondale AZ","Goodyear AZ","Buckeye AZ","Maricopa AZ","Casa Grande AZ",
    "Yuma AZ","Flagstaff AZ","Prescott AZ","Sierra Vista AZ","Bullhead City AZ",
    # Nevada suburbs
    "Enterprise NV","Spring Valley NV","Paradise NV","Winchester NV",
    "Summerlin NV","Henderson NV","Boulder City NV",
    # California inland/suburbs
    "Temecula CA","Murrieta CA","Hemet CA","San Marcos CA","Carlsbad CA",
    "El Cajon CA","Chula Vista CA","National City CA","Vista CA","Escondido CA",
    "Ontario CA","Upland CA","Chino CA","Chino Hills CA","Pomona CA",
    "Victorville CA","Apple Valley CA","Hesperia CA","Redlands CA","Yucaipa CA",
    "Clovis CA","Madera CA","Turlock CA","Merced CA","Los Banos CA",
    "Roseville CA","Folsom CA","Elk Grove CA","Rancho Cordova CA","Citrus Heights CA",
    # New England / Mid-Atlantic
    "Nashua NH","Salem NH","Derry NH","Dover NH","Rochester NH",
    "Stamford CT","Greenwich CT","Danbury CT","Norwalk CT","Waterbury CT",
    "Edison NJ","Woodbridge NJ","Toms River NJ","Hamilton NJ","Clifton NJ",
    "Yonkers NY","White Plains NY","Mount Vernon NY","New Rochelle NY","Schenectady NY",
    # Kansas and Nebraska suburbs
    "Shawnee KS","Lenexa KS","Lawrence KS","Manhattan KS","Hutchinson KS",
    "Papillion NE","La Vista NE","Kearney NE","Fremont NE","Norfolk NE",
    # Tennessee suburbs
    "Brentwood TN","Hendersonville TN","Spring Hill TN","Mount Juliet TN","Smyrna TN",
    "Collierville TN","Germantown TN","Bartlett TN","Cookeville TN",
    # Kentucky
    "Elizabethtown KY","Owensboro KY","Bowling Green KY","Richmond KY","Florence KY",
    # Louisiana suburbs
    "Metairie LA","Kenner LA","Baton Rouge LA","Prairieville LA","Slidell LA",
    # South Carolina suburbs
    "Greer SC","Mauldin SC","Goose Creek SC","Summerville SC","Hanahan SC",
    # Alabama suburbs
    "Vestavia Hills AL","Hoover AL","Pelham AL","Alabaster AL","Prattville AL",
]

SKIP_DOMAINS = {
    "bark.com","yellowpages.com","superpages.com","yelp.com",
    "facebook.com","twitter.com","instagram.com","linkedin.com",
    "youtube.com","google.com","angi.com","thumbtack.com",
    "homeadvisor.com","bbb.org","nextdoor.com","wikipedia.org","indeed.com",
    "glassdoor.com","healthgrades.com","zocdoc.com","houzz.com","porch.com",
    "buildzoom.com","angieslist.com","thumbtack.com",
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

    print(f"[BARK] Running {len(combos)} DDG searches across {len(LOCATIONS)} cities...")
    all_new: dict[str, dict] = {}
    niche_counts: dict[str, int] = {}
    ddgs = DDGS()

    for niche, term, location in combos:
        query = f"{term} {location} email contact website"
        print(f"  [BK:{niche.upper()}] '{term}' in {location}")
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
            print(f"    [BK] Error: {e}"); time.sleep(2)

    if not all_new:
        print("[BARK] No new leads this run.")
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
    print(f"\n[BARK DONE] {len(df_new)} new | {len(df_combined)} total")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():14s}: {c}")


if __name__ == "__main__":
    run()
