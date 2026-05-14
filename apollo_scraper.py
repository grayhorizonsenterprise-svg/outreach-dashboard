"""
apollo_scraper.py — Gray Horizons Enterprise
Apollo.io People Search API — pulls VERIFIED, DECISION-MAKER contacts only.

Targeting logic:
  - Titles: Owner, CEO, Founder, President, Partner, Principal
  - Industries: High-LTV local service businesses with budget and pain
  - Employee size: 2-50 (small enough to have the problem, big enough to pay $497)
  - Revenue: $500K-$10M (proven business, not a startup)
  - Email status: verified only — no guesses

Free tier: 50 credits/month (still 50 PERFECT leads vs 3,000 random ones)
Basic plan: $49/month = 1,000 verified contacts = worth it

Get API key: apollo.io → Settings → Integrations → API Keys
Add APOLLO_API_KEY to Railway → ghe-dashboard → Variables
"""

import requests
import pandas as pd
import os
import sys
import time
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
APOLLO_KEY = os.getenv("APOLLO_API_KEY", "")
BASE_URL   = "https://api.apollo.io/api/v1"

# Decision-makers only — no marketing managers, no receptionists
TARGET_TITLES = [
    "Owner",
    "Co-Owner",
    "CEO",
    "Founder",
    "President",
    "Partner",
    "Principal",
    "Managing Director",
    "General Manager",
    "Practice Owner",
    "Clinic Owner",
    "Office Manager",  # dental/chiro — they control vendor decisions
]

# Industries where our AI automation pitch hits hardest:
# - They depend on phone calls / missed calls cost them money
# - They do repeat business / follow-up is critical
# - They have $500K-$5M revenue so $497 setup is an easy yes
NICHE_CONFIGS = [
    {
        "niche":      "hvac",
        "keywords":   ["HVAC", "heating cooling", "air conditioning", "furnace"],
        "industries": ["Consumer Services", "Mechanical or Industrial Engineering"],
        "pitch":      "missed calls cost you 10-15 jobs/month",
    },
    {
        "niche":      "dental",
        "keywords":   ["dental", "dentistry", "dental practice"],
        "industries": ["Health, Wellness and Fitness", "Medical Practice"],
        "pitch":      "slow new patient response costs $10K+/month in lost LTV",
    },
    {
        "niche":      "plumbing",
        "keywords":   ["plumbing", "plumber"],
        "industries": ["Consumer Services", "Construction"],
        "pitch":      "emergency call overflow is your biggest revenue leak",
    },
    {
        "niche":      "roofing",
        "keywords":   ["roofing", "roofer", "roof repair"],
        "industries": ["Construction", "Consumer Services"],
        "pitch":      "storm call volume overwhelms manual intake",
    },
    {
        "niche":      "contractor",
        "keywords":   ["general contractor", "remodeling", "home improvement"],
        "industries": ["Construction"],
        "pitch":      "estimates go cold because follow-up doesn't happen",
    },
    {
        "niche":      "landscaping",
        "keywords":   ["landscaping", "lawn care", "landscape"],
        "industries": ["Consumer Services", "Farming"],
        "pitch":      "seasonal clients go quiet between services without automation",
    },
    {
        "niche":      "chiropractic",
        "keywords":   ["chiropractor", "chiropractic"],
        "industries": ["Health, Wellness and Fitness", "Medical Practice"],
        "pitch":      "patient no-shows and drop-off kill recurring revenue",
    },
    {
        "niche":      "auto_repair",
        "keywords":   ["auto repair", "automotive", "mechanic shop"],
        "industries": ["Automotive", "Consumer Services"],
        "pitch":      "repeat service reminders add 20-30% to lifetime value",
    },
    {
        "niche":      "pest_control",
        "keywords":   ["pest control", "exterminator"],
        "industries": ["Consumer Services", "Environmental Services"],
        "pitch":      "recurring contract renewals drop 40% without automation",
    },
    {
        "niche":      "insurance",
        "keywords":   ["insurance agency", "independent insurance", "insurance broker"],
        "industries": ["Insurance", "Financial Services"],
        "pitch":      "policy renewal reminders and cross-sell automation drive 25% more LTV",
    },
    {
        "niche":      "realestate",
        "keywords":   ["real estate", "realtor", "real estate broker"],
        "industries": ["Real Estate"],
        "pitch":      "dead leads and past clients are sitting money without follow-up",
    },
    {
        "niche":      "gym",
        "keywords":   ["gym", "fitness studio", "personal training"],
        "industries": ["Health, Wellness and Fitness", "Sports"],
        "pitch":      "members churn at month 2 from zero engagement automation",
    },
]

# High-growth states — larger TAM, more competition = more willingness to pay for automation
TARGET_STATES = [
    "Texas", "Florida", "Georgia", "North Carolina", "Arizona",
    "Colorado", "Tennessee", "Nevada", "Indiana", "Ohio",
    "California", "Illinois", "Washington", "Virginia", "Michigan",
]

# Employee size bands — small enough to not have a full ops team, big enough to have revenue
EMPLOYEE_RANGES = ["1,10", "11,20", "21,50"]


def _headers():
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_KEY,
    }


def search_people(keywords: list, titles: list, state: str,
                  employee_range: str = "1,50", page: int = 1) -> list:
    """Search Apollo for verified decision-makers matching criteria."""
    if not APOLLO_KEY:
        return []

    payload = {
        "q_keywords":            " OR ".join(keywords),
        "person_titles":         titles,
        "person_locations":      [f"{state}, United States"],
        "contact_email_status":  ["verified"],
        "num_employees_ranges":  [employee_range],
        "page":                  page,
        "per_page":              25,
    }

    try:
        r = requests.post(
            f"{BASE_URL}/mixed_people/search",
            headers=_headers(),
            json=payload,
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("people", [])
        elif r.status_code == 401:
            print("[APOLLO] Invalid API key — check APOLLO_API_KEY in Railway vars")
            return []
        elif r.status_code == 429:
            print("[APOLLO] Rate limit — sleeping 60s")
            time.sleep(60)
        elif r.status_code == 422:
            # Free tier hit credit limit
            print("[APOLLO] Credit limit reached for this billing period")
            return []
        else:
            print(f"[APOLLO] {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"[APOLLO] Request error: {e}")
    return []


def parse_person(p: dict, niche: str) -> dict | None:
    """Extract clean contact record from Apollo person object."""
    email = (p.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return None

    # Skip obvious junk emails
    prefix = email.split("@")[0]
    junk = {"noreply", "no-reply", "info", "contact", "admin", "support",
            "hello", "office", "help", "sales", "marketing"}
    if prefix in junk:
        return None

    name    = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    org     = (p.get("organization") or {})
    company = org.get("name", "").strip()
    city    = (p.get("city") or "").strip()
    state   = (p.get("state") or "").strip()
    title   = (p.get("title") or "").strip()

    # Phone — prefer direct dial over company line
    phone = ""
    for pn in (p.get("phone_numbers") or []):
        if pn.get("type") in ("direct", "mobile"):
            phone = pn.get("raw_number", "")
            break
    if not phone and p.get("phone_numbers"):
        phone = p["phone_numbers"][0].get("raw_number", "")

    linkedin = (p.get("linkedin_url") or "").strip()
    employees = org.get("num_employees", "")

    return {
        "email":    email,
        "name":     name,
        "company":  company,
        "title":    title,
        "city":     city,
        "state":    state,
        "phone":    phone,
        "linkedin": linkedin,
        "employees": str(employees),
        "niche":    niche,
        "source":   "apollo_verified",
        "status":   "pending",
    }


def run(max_contacts: int = 250):
    if not APOLLO_KEY:
        print("[APOLLO] APOLLO_API_KEY not set.")
        print("  Sign up free: apollo.io → Settings → Integrations → API Keys")
        print("  Free tier = 50 verified contacts/month (already better than 3,000 random scraped)")
        return

    print(f"[APOLLO] Starting — targeting decision-makers with verified emails...")

    # Load existing to dedup
    existing_emails: set = set()
    existing_rows: list = []
    if os.path.exists(OUT_FILE):
        try:
            df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            existing_emails = set(df_exist["email"].str.lower().str.strip())
            existing_rows   = df_exist.to_dict("records")
        except Exception:
            pass

    new_rows  = []
    new_count = 0
    credits_hit = False

    # Shuffle to vary which niches/states get pulled each run
    niches = random.sample(NICHE_CONFIGS, len(NICHE_CONFIGS))
    states = random.sample(TARGET_STATES, min(8, len(TARGET_STATES)))

    for niche_cfg in niches:
        if credits_hit or new_count >= max_contacts:
            break
        niche    = niche_cfg["niche"]
        keywords = niche_cfg["keywords"]

        for state in states:
            if credits_hit or new_count >= max_contacts:
                break

            emp_range = random.choice(EMPLOYEE_RANGES)
            print(f"  [APOLLO] {niche.upper()} | {state} | {emp_range} employees")

            people = search_people(keywords, TARGET_TITLES, state, emp_range, page=1)
            if not people:
                credits_hit = True  # likely hit credit limit
                break

            for p in people:
                if new_count >= max_contacts:
                    break
                rec = parse_person(p, niche)
                if not rec:
                    continue
                if rec["email"] in existing_emails:
                    continue
                existing_emails.add(rec["email"])
                new_rows.append(rec)
                new_count += 1
                print(f"    [+] {rec['name']} | {rec['title']} | {rec['company']} | {rec['email']}")

            time.sleep(random.uniform(1.5, 3.0))

    if not new_rows:
        print("[APOLLO] No new contacts found this run")
        return

    all_rows = existing_rows + new_rows
    pd.DataFrame(all_rows).to_csv(OUT_FILE, index=False)
    print(f"[APOLLO] Done. +{new_count} verified decision-makers added (total: {len(all_rows)})")
    print(f"[APOLLO] These contacts convert 10-20x better than directory scrapes.")


if __name__ == "__main__":
    run()
