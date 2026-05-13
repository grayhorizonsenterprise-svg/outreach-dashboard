"""
snov_scraper.py — Gray Horizons Enterprise
Snov.io free tier — 50 verified B2B contacts/month. No business email required.
Finds decision-maker emails for local service businesses.

Setup (2 minutes, any email works):
  1. Go to snov.io → Sign up free (Gmail works fine)
  2. Go to Settings → API → copy Client ID and Client Secret
  3. Add to Railway env vars:
       SNOV_CLIENT_ID
       SNOV_CLIENT_SECRET

Appends verified contacts to prospects_raw.csv.
"""

import requests
import pandas as pd
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR        = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE        = os.path.join(DATA_DIR, "prospects_raw.csv")
SNOV_CLIENT_ID  = os.getenv("SNOV_CLIENT_ID", "")
SNOV_SECRET     = os.getenv("SNOV_CLIENT_SECRET", "")
TOKEN_URL       = "https://api.snov.io/v1/oauth/access_token"
SEARCH_URL      = "https://api.snov.io/v1/get-domain-emails-with-info"
PROSPECT_URL    = "https://api.snov.io/v1/get-prospects-by-company"

NICHES = [
    ("hvac",         ["HVAC", "Air Conditioning", "Heating Cooling"]),
    ("plumbing",     ["Plumbing", "Plumber"]),
    ("roofing",      ["Roofing", "Roofer"]),
    ("landscaping",  ["Landscaping", "Lawn Care"]),
    ("contractor",   ["General Contractor", "Remodeling"]),
    ("dental",       ["Dental Practice", "Dentist"]),
    ("chiropractic", ["Chiropractor", "Chiropractic"]),
    ("auto",         ["Auto Repair", "Mechanic"]),
    ("pest_control", ["Pest Control"]),
    ("cleaning",     ["Cleaning Service", "Maid Service"]),
    ("electrician",  ["Electrician", "Electrical Contractor"]),
    ("salon",        ["Hair Salon", "Beauty Salon"]),
]

TARGET_DOMAINS = [
    # High-value local business domains — publicly listed companies
    "angieslist.com", "homeadvisor.com", "thumbtack.com",
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
    except Exception as e:
        print(f"[SNOV] Token error: {e}")
    return ""


def search_emails_by_domain(domain: str, token: str) -> list:
    try:
        r = requests.post(SEARCH_URL,
            data={"domain": domain, "type": "personal", "limit": 10, "lastId": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("emails", [])
    except Exception as e:
        print(f"[SNOV] Domain search error for {domain}: {e}")
    return []


def search_prospects_by_company(company: str, token: str) -> list:
    try:
        r = requests.post(PROSPECT_URL,
            data={"companyName": company, "limit": 5},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("prospects", [])
    except Exception as e:
        print(f"[SNOV] Prospect search error for {company}: {e}")
    return []


def run(max_contacts: int = 100):
    if not SNOV_CLIENT_ID or not SNOV_SECRET:
        print("[SNOV] Missing credentials.")
        print("  Sign up free (Gmail OK): snov.io")
        print("  Settings → API → copy Client ID + Client Secret")
        print("  Add to Railway: SNOV_CLIENT_ID, SNOV_CLIENT_SECRET")
        return

    token = get_token()
    if not token:
        print("[SNOV] Could not get access token — check credentials")
        return

    print(f"[SNOV] Authenticated. Searching for verified B2B contacts...")

    existing_emails = set()
    rows = []
    if os.path.exists(OUT_FILE):
        df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
        existing_emails = set(df_exist["email"].str.lower().str.strip())
        rows = df_exist.to_dict("records")
        print(f"  Existing: {len(rows)} prospects")

    new_count = 0

    for niche, keywords in NICHES:
        if new_count >= max_contacts:
            break
        for keyword in keywords:
            if new_count >= max_contacts:
                break

            prospects = search_prospects_by_company(keyword, token)
            for p in prospects:
                if new_count >= max_contacts:
                    break

                email = (p.get("email") or "").strip().lower()
                if not email or email in existing_emails:
                    continue
                if p.get("emailStatus") not in ("verified", "valid", None):
                    continue

                name    = f"{p.get('firstName','')} {p.get('lastName','')}".strip()
                company = p.get("companyName", "")
                title   = p.get("position", "")

                rows.append({
                    "email":   email,
                    "name":    name,
                    "company": company,
                    "title":   title,
                    "niche":   niche,
                    "source":  "snov",
                    "status":  "pending",
                })
                existing_emails.add(email)
                new_count += 1

            time.sleep(2)  # respect free tier rate limit

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FILE, index=False)
    print(f"[SNOV] Done. +{new_count} verified contacts. Total: {len(rows)}")


if __name__ == "__main__":
    run()
