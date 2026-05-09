"""
apollo_scraper.py — Gray Horizons Enterprise
Apollo.io free tier — 50 verified B2B contacts/day with direct emails + phone numbers.
Far higher quality than directory scraping. Decision-makers, not info@ addresses.

Get free account at apollo.io — no credit card needed for free tier.
Add APOLLO_API_KEY to Railway env vars.

Docs: https://apolloio.github.io/apollo-api-docs/
"""

import requests
import pandas as pd
import time
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")
APOLLO_KEY  = os.getenv("APOLLO_API_KEY", "")
APOLLO_URL  = "https://api.apollo.io/v1/mixed_people/search"

# Target titles — owners and decision-makers only
TARGET_TITLES = [
    "owner", "founder", "president", "ceo", "principal",
    "managing partner", "director", "general manager", "operator",
]

# Niche → Apollo industry/keyword mapping
NICHE_SEARCHES = [
    ("hvac",         {"q_organization_industry_tag_ids": [], "q_keywords": "hvac heating cooling air conditioning", "person_titles": TARGET_TITLES}),
    ("dental",       {"q_keywords": "dental practice dentist", "person_titles": TARGET_TITLES}),
    ("plumbing",     {"q_keywords": "plumbing contractor", "person_titles": TARGET_TITLES}),
    ("roofing",      {"q_keywords": "roofing contractor", "person_titles": TARGET_TITLES}),
    ("contractor",   {"q_keywords": "general contractor remodeling", "person_titles": TARGET_TITLES}),
    ("landscaping",  {"q_keywords": "landscaping lawn care", "person_titles": TARGET_TITLES}),
    ("chiropractic", {"q_keywords": "chiropractic clinic", "person_titles": TARGET_TITLES}),
    ("auto",         {"q_keywords": "auto repair mechanic shop", "person_titles": TARGET_TITLES}),
    ("pest_control", {"q_keywords": "pest control exterminator", "person_titles": TARGET_TITLES}),
    ("electrician",  {"q_keywords": "electrical contractor electrician", "person_titles": TARGET_TITLES}),
]

EMPLOYEE_RANGE = [["1", "10"], ["11", "25"], ["26", "50"]]  # Small businesses only


def search_apollo(niche: str, params: dict, page: int = 1) -> list:
    if not APOLLO_KEY:
        return []

    payload = {
        "api_key":               APOLLO_KEY,
        "page":                  page,
        "per_page":              25,
        "person_titles":         params.get("person_titles", TARGET_TITLES),
        "q_keywords":            params.get("q_keywords", ""),
        "organization_num_employees_ranges": EMPLOYEE_RANGE,
        "contact_email_status":  ["verified", "likely to engage"],
    }

    try:
        r = requests.post(APOLLO_URL, json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            people = data.get("people", [])
            return people
        elif r.status_code == 429:
            print("[APOLLO] Rate limit — sleeping 60s")
            time.sleep(60)
        else:
            print(f"[APOLLO] {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[APOLLO] Error: {e}")
    return []


def parse_person(person: dict, niche: str) -> dict | None:
    email = person.get("email", "") or ""
    if not email or email == "email_not_unlocked@domain.com":
        return None

    org     = person.get("organization", {}) or {}
    name    = f"{person.get('first_name','')} {person.get('last_name','')}".strip()
    company = org.get("name", "") or ""
    website = org.get("website_url", "") or ""
    phone   = person.get("phone_numbers", [{}])[0].get("raw_number", "") if person.get("phone_numbers") else ""
    city    = person.get("city", "") or ""
    state   = person.get("state", "") or ""
    location = f"{city}, {state}".strip(", ")

    if not company:
        return None

    return {
        "company":          company,
        "website":          website,
        "email":            email.lower(),
        "contact_name":     name,
        "contact_page_url": "",
        "location":         location,
        "niche":            niche,
        "lead_type":        "READY",
        "phone":            re.sub(r"[^\d]", "", phone) if phone else "",
    }


def run():
    import re
    if not APOLLO_KEY:
        print("[APOLLO] No APOLLO_API_KEY set — get free key at apollo.io")
        return

    existing   = pd.read_csv(OUTPUT_FILE).fillna("") if os.path.exists(OUTPUT_FILE) else pd.DataFrame()
    done_emails = set(existing["email"].str.lower().tolist()) if len(existing) and "email" in existing.columns else set()

    new_rows = []

    for niche, params in NICHE_SEARCHES:
        for page in [1, 2]:
            people = search_apollo(niche, params, page)
            for person in people:
                row = parse_person(person, niche)
                if not row:
                    continue
                if row["email"] in done_emails:
                    continue
                done_emails.add(row["email"])
                new_rows.append(row)
            time.sleep(1.5)
            if len(new_rows) >= 100:
                break
        if len(new_rows) >= 100:
            break

    if not new_rows:
        print("[APOLLO] No new verified leads found")
        return

    new_df = pd.DataFrame(new_rows)
    for col in ["phone", "contact_name"]:
        if col not in existing.columns and len(existing):
            existing[col] = ""
    out = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"[APOLLO] Done — {len(new_rows)} verified decision-maker contacts added")
    for niche in new_df["niche"].unique():
        count = len(new_df[new_df["niche"] == niche])
        print(f"  {niche.upper():14s}: {count}")


if __name__ == "__main__":
    run()
