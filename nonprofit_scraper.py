"""
nonprofit_scraper.py — Gray Horizons Enterprise
Scrapes nonprofits and small businesses that qualify for grants.
Targets organizations that need grant writing help.
Adds to grant_queue.csv for outreach.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import sys
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "grant_queue.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
}


BAD_PREFIXES = {
    'abuse','spam','report','complaints','privacy','legal','billing',
    'webmaster','postmaster','mailer','sales','marketing','hr',
    'careers','jobs','news','newsletter','press','media','helpdesk',
    'support','ticket','hrprocessing','pressinquiries','donotreply',
    'noreply','no-reply',
}

def is_clean_email(email: str) -> bool:
    e = email.lower().strip()
    if e.endswith(('.png','.jpg','.gif','.webp','.svg')):
        return False
    prefix = e.split('@')[0] if '@' in e else e
    if any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES):
        return False
    return True

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Nonprofit directories to scrape
SEARCH_QUERIES = [
    "site:guidestar.org nonprofit contact email",
    "nonprofit organization contact email -insurance -bank -hospital",
    "small business development center contact email",
    "community foundation grant contact email",
    "arts organization nonprofit grant contact email",
    "veteran nonprofit organization contact email",
    "youth nonprofit organization contact email",
]

YELP_NONPROFIT_CATEGORIES = [
    ("nonprofits", "New York, NY"),
    ("nonprofits", "Los Angeles, CA"),
    ("nonprofits", "Chicago, IL"),
    ("nonprofits", "Houston, TX"),
    ("nonprofits", "Phoenix, AZ"),
    ("nonprofits", "Philadelphia, PA"),
    ("nonprofits", "San Antonio, TX"),
    ("nonprofits", "Dallas, TX"),
    ("nonprofits", "Atlanta, GA"),
    ("nonprofits", "Denver, CO"),
    ("communityservices", "Miami, FL"),
    ("communityservices", "Seattle, WA"),
    ("communityservices", "Boston, MA"),
    ("communityservices", "Portland, OR"),
    ("communityservices", "Nashville, TN"),
]


def scrape_yelp_nonprofits(category: str, location: str) -> list:
    results = []
    location_slug = location.replace(", ", "-").replace(" ", "-").lower()
    url = f"https://www.yelp.com/search?find_desc={category}&find_loc={location_slug}&start=0"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select('[class*="businessName"]')
        for card in cards[:20]:
            name = card.get_text(strip=True)
            if name:
                results.append({"company": name, "location": location, "source": "yelp_nonprofit"})
    except Exception as e:
        print(f"  [NONPROFIT] Yelp error {location}: {e}")
    return results


def search_nonprofit_emails() -> list:
    """Use DuckDuckGo to find nonprofit contact pages with emails."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    results = []
    queries = [
        "nonprofit organization \"contact us\" email site:.org",
        "community nonprofit \"info@\" OR \"director@\" OR \"executive@\" contact",
        "501c3 nonprofit small grants \"apply\" contact email",
        "\"community foundation\" grants contact email",
        "\"youth organization\" nonprofit contact email director",
    ]

    with DDGS() as ddgs:
        for query in queries:
            try:
                for r in ddgs.text(query, max_results=15):
                    url  = r.get("href", "")
                    body = r.get("body", "")
                    title = r.get("title", "")
                    emails = EMAIL_RE.findall(body + " " + title)
                    for email in emails:
                        e = email.lower()
                        if any(bad in e for bad in ["example", "test@", "noreply", "@sentry", "@github", "@google"]):
                            continue
                        if e.endswith((".org", ".net", ".com")):
                            results.append({
                                "company": title[:60] if title else "Nonprofit",
                                "email": e,
                                "website": url,
                                "source": "ddg_nonprofit",
                            })
                time.sleep(1.5)
            except Exception as e:
                print(f"  [NONPROFIT] DDG error: {e}")
                time.sleep(3)

    return results


def run():
    print("[NONPROFIT] Scraping nonprofits for grant outreach...")

    all_leads = []

    # DDG email search
    ddg_leads = search_nonprofit_emails()
    print(f"  [DDG] Found {len(ddg_leads)} leads with emails")
    all_leads.extend(ddg_leads)

    # Yelp nonprofit listings
    for category, location in YELP_NONPROFIT_CATEGORIES[:10]:
        leads = scrape_yelp_nonprofits(category, location)
        print(f"  [YELP] {location}: {len(leads)} results")
        all_leads.extend(leads)
        time.sleep(1)

    if not all_leads:
        print("[NONPROFIT] No leads found")
        return

    df_new = pd.DataFrame(all_leads).fillna("")
    df_new["status"] = "pending"
    df_new["niche"]  = "nonprofit"

    # Ensure required columns
    for col in ["company", "email", "website", "location", "source", "status", "niche"]:
        if col not in df_new.columns:
            df_new[col] = ""

    # Merge with existing
    if os.path.exists(OUT_FILE):
        df_existing = pd.read_csv(OUT_FILE).fillna("")
        done_emails = set(df_existing["email"].str.lower().tolist())
        df_new = df_new[~df_new["email"].str.lower().isin(done_emails)]
        df_out = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_out = df_new

    df_out.to_csv(OUT_FILE, index=False)
    print(f"[NONPROFIT] Done — {len(df_new)} new leads, {len(df_out)} total in grant_queue.csv")


if __name__ == "__main__":
    run()
