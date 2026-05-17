"""
snov_scraper.py - Gray Horizons Enterprise
Snov.io Pro — automated prospect search across all niches.
Searches by job title + industry + location. No manual work needed.
Runs automatically every 6 hours as part of the main pipeline.

Setup (one time, 2 minutes):
  1. Log into snov.io → Settings → API
  2. Copy Client ID and Client Secret
  3. Add to Railway env vars:
       SNOV_CLIENT_ID
       SNOV_CLIENT_SECRET

Credits used: ~1 per email found. 5,000 credits/month = ~5,000 fresh leads.
"""

import requests
import pandas as pd
import os
import sys
import time
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR       = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE       = os.path.join(DATA_DIR, "prospects_raw.csv")
SNOV_CLIENT_ID = os.getenv("SNOV_CLIENT_ID", "")
SNOV_SECRET    = os.getenv("SNOV_CLIENT_SECRET", "")

TOKEN_URL      = "https://api.snov.io/v1/oauth/access_token"
SEARCH_URL     = "https://api.snov.io/v2/prospect-search"
DOMAIN_URL     = "https://api.snov.io/v1/get-domain-emails-with-info"
FINDER_URL     = "https://api.snov.io/v1/get-emails-from-url"

# Decision-maker titles across all niches
OWNER_TITLES = [
    "Owner", "Co-Owner", "CEO", "Founder", "President",
    "Partner", "Principal", "Managing Director", "General Manager",
    "Practice Owner", "Office Manager",
]

# Niche configs — each runs as a separate search pass
NICHE_CONFIGS = [
    {
        "niche":    "hvac",
        "keywords": ["HVAC", "Air Conditioning", "Heating and Cooling", "Mechanical Contractor"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "roofing",
        "keywords": ["Roofing", "Roofing Contractor", "Roofer"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "plumbing",
        "keywords": ["Plumbing", "Plumbing Contractor"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "landscaping",
        "keywords": ["Landscaping", "Lawn Care", "Landscape Services"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "contractor",
        "keywords": ["General Contractor", "Home Improvement", "Remodeling"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "dental",
        "keywords": ["Dental Practice", "Dentistry", "Dental Office"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "auto",
        "keywords": ["Auto Repair", "Automotive Repair", "Auto Service"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "hoa",
        "keywords": ["HOA Management", "Community Association", "Property Management"],
        "sizes":    ["1-50", "11-200"],
    },
    {
        "niche":    "pest_control",
        "keywords": ["Pest Control", "Exterminator"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "electrician",
        "keywords": ["Electrical Contractor", "Electrician"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "financial",
        "keywords": ["Independent Financial Advisor", "Registered Investment Advisor", "Wealth Management"],
        "sizes":    ["1-10", "11-50"],
    },
    {
        "niche":    "trading",
        "keywords": ["Trading", "Stock Trader", "Investment Fund", "Algorithmic Trading"],
        "sizes":    ["1-10", "11-50"],
    },
]

# States to rotate through — high-density markets first
TARGET_STATES = [
    "Texas", "Florida", "California", "Georgia", "North Carolina",
    "Arizona", "Colorado", "Tennessee", "Nevada", "Ohio",
    "Illinois", "Washington", "Virginia", "Michigan", "Pennsylvania",
]


def get_token() -> str:
    if not SNOV_CLIENT_ID or not SNOV_SECRET:
        return ""
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     SNOV_CLIENT_ID,
            "client_secret": SNOV_SECRET,
        }, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token", "")
        print(f"[SNOV] Token error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[SNOV] Token error: {e}")
    return ""


def prospect_search(token: str, keyword: str, title: str, state: str,
                    size: str, page: int = 1) -> list:
    """Search Snov.io for prospects matching niche + title + location."""
    try:
        payload = {
            "position":    title,
            "companyType": keyword,
            "location":    f"{state}, United States",
            "companySize": size,
            "page":        page,
            "perPage":     50,
        }
        r = requests.post(
            SEARCH_URL,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("prospects", [])
        elif r.status_code == 402:
            print("[SNOV] Credit limit reached for this period")
            return None  # signal to stop
        elif r.status_code == 401:
            print("[SNOV] Token expired — will refresh next run")
            return None
        else:
            print(f"[SNOV] Search {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"[SNOV] Search error: {e}")
    return []


def domain_search(token: str, domain: str) -> list:
    """Fallback: find emails at a specific company domain."""
    try:
        r = requests.post(
            DOMAIN_URL,
            data={"domain": domain, "type": "personal", "limit": 10, "lastId": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("emails", [])
    except Exception:
        pass
    return []


def parse_prospect(p: dict, niche: str) -> dict | None:
    """Extract clean record from Snov.io prospect object."""
    email = (p.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return None

    # Drop role/generic addresses
    prefix = email.split("@")[0]
    role   = {"info", "contact", "admin", "support", "hello", "office",
               "sales", "help", "team", "marketing", "noreply", "no-reply"}
    if prefix in role:
        return None

    # Drop if email status is invalid
    status = (p.get("emailStatus") or p.get("email_status") or "").lower()
    if status in ("invalid", "bounced", "unverifiable"):
        return None

    name    = f"{p.get('firstName', '') or p.get('first_name', '')} {p.get('lastName', '') or p.get('last_name', '')}".strip()
    company = (p.get("companyName") or p.get("company_name") or p.get("company") or "").strip()
    title   = (p.get("position") or p.get("title") or "").strip()
    linkedin = (p.get("linkedinUrl") or p.get("linkedin_url") or "").strip()

    return {
        "email":    email,
        "name":     name,
        "company":  company,
        "title":    title,
        "niche":    niche,
        "linkedin": linkedin,
        "source":   "snov_pro",
        "status":   "pending",
    }


def run(max_contacts: int = 300):
    if not SNOV_CLIENT_ID or not SNOV_SECRET:
        print("[SNOV] Credentials not set.")
        print("  snov.io → Settings → API → copy Client ID + Client Secret")
        print("  Add to Railway: SNOV_CLIENT_ID, SNOV_CLIENT_SECRET")
        return

    token = get_token()
    if not token:
        print("[SNOV] Authentication failed — check credentials in Railway")
        return

    print(f"[SNOV] Authenticated. Searching {len(NICHE_CONFIGS)} niches...")

    # Load existing to dedup by email AND domain
    existing_emails:  set = set()
    existing_domains: set = set()
    rows: list = []
    if os.path.exists(OUT_FILE):
        try:
            df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            existing_emails  = set(df_exist["email"].str.lower().str.strip())
            existing_domains = set(df_exist["email"].str.lower().str.strip()
                                   .apply(lambda e: e.split("@")[-1] if "@" in e else ""))
            rows = df_exist.to_dict("records")
            print(f"  Existing: {len(rows)} prospects, {len(existing_domains)} domains blocked")
        except Exception:
            pass

    new_count = 0
    credits_exhausted = False

    # Shuffle niches so each run covers different territory
    niches  = random.sample(NICHE_CONFIGS, len(NICHE_CONFIGS))
    states  = random.sample(TARGET_STATES, min(6, len(TARGET_STATES)))
    titles  = random.sample(OWNER_TITLES, min(4, len(OWNER_TITLES)))

    for cfg in niches:
        if credits_exhausted or new_count >= max_contacts:
            break
        niche    = cfg["niche"]
        keywords = cfg["keywords"]
        sizes    = cfg["sizes"]

        for keyword in keywords:
            if credits_exhausted or new_count >= max_contacts:
                break
            for state in states:
                if credits_exhausted or new_count >= max_contacts:
                    break
                title = random.choice(titles)
                size  = random.choice(sizes)

                print(f"  [SNOV] {niche.upper()} | {keyword} | {title} | {state}")
                prospects = prospect_search(token, keyword, title, state, size)

                if prospects is None:  # credit limit or auth error
                    credits_exhausted = True
                    break

                for p in prospects:
                    if new_count >= max_contacts:
                        break
                    rec = parse_prospect(p, niche)
                    if not rec:
                        continue
                    email  = rec["email"]
                    domain = email.split("@")[-1]
                    if email in existing_emails or domain in existing_domains:
                        continue
                    existing_emails.add(email)
                    existing_domains.add(domain)
                    rows.append(rec)
                    new_count += 1
                    print(f"    [+] {rec['name']} | {rec['title']} | {rec['company']} | {email}")

                time.sleep(random.uniform(1.5, 3.0))

    if not rows:
        print("[SNOV] No contacts found — check credentials or try different search terms")
        return

    pd.DataFrame(rows).to_csv(OUT_FILE, index=False)
    print(f"\n[SNOV] Done. +{new_count} new verified contacts. Total pipeline: {len(rows)}")
    if credits_exhausted:
        print("  Credits exhausted for this period — will resume next billing cycle")


if __name__ == "__main__":
    run()
