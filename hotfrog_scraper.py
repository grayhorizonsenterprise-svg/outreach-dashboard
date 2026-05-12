"""
hotfrog_scraper.py — Gray Horizons Enterprise
Finds local service businesses via DuckDuckGo (replaced direct Hotfrog scraping — 403 blocked on cloud IPs).
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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

NICHE_SEARCHES = [
    ("hvac",         "hvac contractor"),
    ("hvac",         "air conditioning"),
    ("hvac",         "heating repair"),
    ("dental",       "dentist"),
    ("dental",       "dental clinic"),
    ("plumbing",     "plumber"),
    ("plumbing",     "plumbing services"),
    ("contractor",   "general contractor"),
    ("contractor",   "home remodeling"),
    ("landscaping",  "landscaping"),
    ("landscaping",  "lawn mowing"),
    ("roofing",      "roofing contractor"),
    ("hoa",          "property management"),
    ("chiropractic", "chiropractor"),
    ("auto",         "auto mechanic"),
    ("pest_control", "pest control"),
    ("electrician",  "electrician"),
]

LOCATIONS = [
    "Phoenix AZ", "Tucson AZ", "Mesa AZ", "Scottsdale AZ",
    "Denver CO", "Colorado Springs CO", "Aurora CO",
    "Nashville TN", "Memphis TN", "Chattanooga TN",
    "Charlotte NC", "Raleigh NC", "Durham NC",
    "Atlanta GA", "Savannah GA", "Augusta GA",
    "Dallas TX", "Houston TX", "San Antonio TX", "Fort Worth TX",
    "Orlando FL", "Tampa FL", "Miami FL", "Jacksonville FL",
    "Las Vegas NV", "Henderson NV", "Reno NV",
    "Indianapolis IN", "Fort Wayne IN",
    "Columbus OH", "Cleveland OH", "Cincinnati OH",
    "Albuquerque NM", "Santa Fe NM",
    "Boise ID", "Salt Lake City UT", "Provo UT",
    "Omaha NE", "Lincoln NE",
    "Tulsa OK", "Oklahoma City OK",
    "Louisville KY", "Lexington KY",
]

SKIP_DOMAINS = {
    "hotfrog.com", "yellowpages.com", "superpages.com", "yelp.com",
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "youtube.com", "google.com", "angi.com", "thumbtack.com",
    "homeadvisor.com", "bbb.org", "nextdoor.com", "wikipedia.org", "indeed.com",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def run():
    seen_emails = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE).fillna("")
            seen_emails = set(df_ex.get("email", pd.Series(dtype=str)).str.lower().dropna())
        except Exception:
            pass

    searches_per_run = int(os.getenv("SCRAPER_SEARCHES_PER_RUN", "35"))
    all_combos = [(n, t, loc) for n, t in NICHE_SEARCHES for loc in LOCATIONS]
    random.shuffle(all_combos)
    combos = all_combos[:searches_per_run]

    print(f"[HOTFROG] Running {len(combos)} DDG searches...")
    all_new: dict[str, dict] = {}
    niche_counts: dict[str, int] = {}
    ddgs = DDGS()

    for niche, term, location in combos:
        query = f"{term} {location} email contact"
        print(f"  [HF:{niche.upper()}] '{term}' in {location}")
        try:
            results = list(ddgs.text(query, max_results=6))
            for r in results:
                body   = r.get("body", "")
                url    = r.get("href", "")
                name   = r.get("title", "")[:60]
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS:
                    continue
                for email in EMAIL_RE.findall(body):
                    email = email.lower()
                    if email in seen_emails or email.endswith((".png", ".jpg", ".gif")):
                        continue
                    seen_emails.add(email)
                    all_new[email] = {
                        "company": name, "website": url, "email": email,
                        "contact_page_url": "", "location": location,
                        "niche": niche, "phone": "",
                    }
                    niche_counts[niche] = niche_counts.get(niche, 0) + 1
            time.sleep(random.uniform(0.5, 1.2))
        except Exception as e:
            print(f"    [HF] Error: {e}")

    if not all_new:
        print("[HOTFROG] No new leads this run.")
        return

    df_new = pd.DataFrame(list(all_new.values()))
    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE).fillna("")
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
