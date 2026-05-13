"""
apollo_scraper.py — Gray Horizons Enterprise
Apollo.io free tier — 50 verified B2B contacts/day.
Pulls decision-maker emails (owner, CEO, director) for local service businesses.
Free account: apollo.io → sign up → API key in Settings → Integrations.
Add APOLLO_API_KEY to Railway env vars.
Appends to prospects_raw.csv.
"""

import requests
import pandas as pd
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
APOLLO_KEY = os.getenv("APOLLO_API_KEY", "")
BASE_URL   = "https://api.apollo.io/v1"

TITLES = [
    "Owner", "CEO", "President", "Founder",
    "General Manager", "Director", "Principal",
]

# Local service niches — these are the buyers for the AI automation system
INDUSTRIES = [
    "HVAC",
    "Plumbing",
    "Roofing",
    "Landscaping",
    "General Contracting",
    "Dental Practice",
    "Chiropractic",
    "Auto Repair",
    "Pest Control",
    "Cleaning Services",
    "Real Estate",
    "Insurance",
    "Accounting",
    "Law Firm",
    "Physical Therapy",
]

US_STATES = ["California", "Texas", "Florida", "New York", "Georgia",
             "North Carolina", "Illinois", "Arizona", "Washington", "Colorado"]


def search_people(title: str, industry: str, state: str, page: int = 1) -> list:
    if not APOLLO_KEY:
        return []
    try:
        payload = {
            "api_key": APOLLO_KEY,
            "person_titles": [title],
            "organization_industry_tag_ids": [],
            "person_locations": [f"{state}, United States"],
            "q_keywords": industry,
            "page": page,
            "per_page": 10,
            "contact_email_status": ["verified"],
        }
        r = requests.post(
            f"{BASE_URL}/mixed_people/search",
            json=payload,
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("people", [])
        elif r.status_code == 429:
            print("[APOLLO] Rate limit — sleeping 30s")
            time.sleep(30)
        else:
            print(f"[APOLLO] {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[APOLLO] Error: {e}")
    return []


def run(max_contacts: int = 200):
    if not APOLLO_KEY:
        print("[APOLLO] No APOLLO_API_KEY set.")
        print("  Get free key: apollo.io → sign up → Settings → Integrations → API")
        return

    print("[APOLLO] Searching for verified B2B decision-makers...")

    existing_emails = set()
    rows = []
    if os.path.exists(OUT_FILE):
        df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
        existing_emails = set(df_exist["email"].str.lower().str.strip())
        rows = df_exist.to_dict("records")

    new_count = 0

    for industry in INDUSTRIES:
        if new_count >= max_contacts:
            break
        for state in US_STATES[:4]:
            if new_count >= max_contacts:
                break
            for title in TITLES[:3]:
                if new_count >= max_contacts:
                    break

                people = search_people(title, industry, state)
                for p in people:
                    email = (p.get("email") or "").strip().lower()
                    if not email or email in existing_emails:
                        continue

                    name    = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                    company = (p.get("organization", {}) or {}).get("name", "")
                    city    = p.get("city", "")
                    st      = p.get("state", "")
                    phone   = p.get("phone_numbers", [{}])[0].get("raw_number", "") if p.get("phone_numbers") else ""

                    rows.append({
                        "email":   email,
                        "name":    name,
                        "company": company,
                        "city":    city,
                        "state":   st,
                        "phone":   phone,
                        "niche":   industry.lower().replace(" ", "_"),
                        "source":  "apollo",
                        "status":  "pending",
                    })
                    existing_emails.add(email)
                    new_count += 1

                time.sleep(1.5)  # stay within free tier rate limit

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FILE, index=False)
    print(f"[APOLLO] Done. +{new_count} verified contacts added. Total: {len(rows)}")


if __name__ == "__main__":
    run()
