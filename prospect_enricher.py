import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import time
import random
import os
import sys

# Force UTF-8 output so Unicode company names don't crash on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

# =========================
# ROTATING USER AGENTS
# =========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

JUNK_PATTERNS = [
    "png", "jpg", "jpeg", "gif", "webp", "svg", "css", ".js",
    "example", "test", "noreply", "no-reply", "sentry", "wixpress",
    "pinterest", "youtube", "twitter", "linkedin", "facebook",
    "first.last", "name@email", "user@email", "user@domain",
    "your@email", "email@email", "info@example", "craigslist",
    "rocketreach", "360training", "support@rocketreach",
]

EMAIL_REGEX = re.compile(r"[\w.\-]+@[\w.\-]+\.[a-zA-Z]{2,}")

# Expanded list of contact page paths to try
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus",
    "/about", "/about-us", "/aboutus",
    "/team", "/our-team", "/management-team", "/staff",
    "/people", "/leadership", "/executives",
    "/reach-us", "/get-in-touch", "/connect",
    "/info", "/office", "/locations",
]

# =========================
# WEBSITE FINDER (fallback if no website in data)
# =========================
def find_website(company):
    try:
        query = company + " property management official website"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        res = requests.get(url, headers=get_headers(), timeout=8)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "url?q=" in href:
                clean = href.split("url?q=")[1].split("&")[0]
                if "google" not in clean and "youtube" not in clean:
                    return clean
    except:
        pass
    return ""


# =========================
# EMAIL EXTRACTOR
# =========================
def extract_emails_from_url(url):
    emails = []
    try:
        res = requests.get(url, headers=get_headers(), timeout=8)
        found = EMAIL_REGEX.findall(res.text)
        for e in found:
            if not any(p in e.lower() for p in JUNK_PATTERNS):
                emails.append(e)
    except:
        pass
    return emails


# =========================
# MAIN
# =========================
def run():
    df = pd.read_csv(INPUT_FILE)

    if "email" not in df.columns:
        df["email"] = ""
    if "website" not in df.columns:
        df["website"] = ""
    if "lead_type" not in df.columns:
        df["lead_type"] = ""

    for i, row in df.iterrows():

        email_val = str(row.get("email", "")).strip()
        if email_val not in ["", "nan", "None"]:
            df.at[i, "lead_type"] = "READY"
            continue

        company = str(row.get("company", "")).strip()
        if not company:
            df.at[i, "lead_type"] = "INVALID"
            continue

        # Use existing website, or fall back to Google search
        site = str(row.get("website", "")).strip()
        if site in ("", "nan", "None"):
            print(f"\n[SEARCH] {company}")
            site = find_website(company)

        if not site:
            print(f"\n[NO WEBSITE] {company}")
            df.at[i, "lead_type"] = "NO_DATA"
            continue

        print(f"\n[ENRICH] {company}")
        print(f"  [SITE] {site}")
        df.at[i, "website"] = site

        all_emails = []

        # 1. Scrape the main page
        all_emails += extract_emails_from_url(site)
        time.sleep(random.uniform(0.5, 1.2))

        # 2. Try the contact_page_url found by prospect_finder
        contact_page = str(row.get("contact_page_url", "")).strip()
        if contact_page and contact_page not in ("", "nan", "None"):
            all_emails += extract_emails_from_url(contact_page)
            time.sleep(random.uniform(0.5, 1.0))

        # 3. Try common contact paths with multiple user agents
        base = site.rstrip("/")
        for path in CONTACT_PATHS:
            all_emails += extract_emails_from_url(base + path)
            if all_emails:
                break  # stop once we find something
            time.sleep(random.uniform(0.3, 0.8))

        all_emails = list(dict.fromkeys(all_emails))  # dedupe, preserve order

        if all_emails:
            df.at[i, "email"] = all_emails[0]
            df.at[i, "lead_type"] = "READY"
            print(f"  [EMAIL] {all_emails[0]}")
        else:
            df.at[i, "lead_type"] = "WEBSITE_ONLY"
            print(f"  [WEBSITE ONLY]")

        # Save progress every 10 records so a crash doesn't wipe all work
        if i % 10 == 0:
            df.to_csv(INPUT_FILE, index=False)

    df.to_csv(INPUT_FILE, index=False)
    print("\n[DONE] CLASSIFIED LEADS READY")


if __name__ == "__main__":
    run()
