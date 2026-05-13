"""
nonprofitscraper_propublica.py — Gray Horizons Enterprise
Pulls nonprofit data directly from ProPublica Nonprofit Explorer API.
Source: IRS 990 filings — 100% legitimate, verified organizations.
No scraping. No ToS violations. Free API, no key needed.
Writes to grant_queue.csv (name, email, city, state, revenue, mission).
"""

import requests
import pandas as pd
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "grant_queue.csv")
BASE_URL   = "https://projects.propublica.org/nonprofits/api/v2"

# Search terms that match orgs with grant-eligible budgets ($50k–$5M range)
SEARCH_TERMS = [
    "community development",
    "youth programs",
    "food bank",
    "housing assistance",
    "workforce development",
    "mental health services",
    "arts education",
    "environmental conservation",
    "veterans services",
    "literacy program",
    "job training",
    "domestic violence",
    "senior services",
    "disability services",
    "immigrant services",
    "affordable housing",
    "rural development",
    "STEM education",
    "women empowerment",
    "small business development",
]

# States to target (broad coverage)
STATES = ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI",
          "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI"]


def search_nonprofits(term: str, state: str = "", page: int = 0) -> list:
    params = {"q": term, "page": page}
    if state:
        params["state[id]"] = state
    try:
        r = requests.get(f"{BASE_URL}/search.json", params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("organizations", [])
    except Exception as e:
        print(f"  [PROPUBLICA] Error: {e}")
    return []


def get_org_detail(ein: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/organizations/{ein}.json", timeout=15)
        if r.status_code == 200:
            return r.json().get("organization", {})
    except Exception:
        pass
    return {}


def build_email_guess(org: dict) -> str:
    """Best-effort email from org name + common patterns if no direct email."""
    name = org.get("name", "").lower()
    city = org.get("city", "").lower().replace(" ", "")
    # ProPublica doesn't expose emails directly (990s rarely have them)
    # Return empty — we rely on domain lookup or Hunter enrichment
    return ""


def run(max_orgs: int = 500):
    print("[PROPUBLICA] Starting nonprofit scrape from IRS 990 data...")

    existing = set()
    rows = []
    if os.path.exists(OUT_FILE):
        df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
        existing = set(df_exist["ein"].str.strip()) if "ein" in df_exist.columns else set()
        rows = df_exist.to_dict("records")
        print(f"  Existing: {len(rows)} orgs in grant_queue.csv")

    new_count = 0

    for term in SEARCH_TERMS:
        if new_count >= max_orgs:
            break
        for state in STATES[:8]:  # top 8 states per term
            if new_count >= max_orgs:
                break
            orgs = search_nonprofits(term, state)
            for org in orgs:
                if new_count >= max_orgs:
                    break
                ein = str(org.get("ein", "")).strip()
                if not ein or ein in existing:
                    continue

                name    = org.get("name", "").strip()
                city    = org.get("city", "").strip()
                st      = org.get("state", "").strip()
                revenue = org.get("income_amount", 0) or 0
                ntee    = org.get("ntee_code", "")

                # Filter: revenue $25k–$10M (small enough to need help, real enough to pay)
                if revenue < 25_000 or revenue > 10_000_000:
                    continue

                rows.append({
                    "ein":       ein,
                    "company":   name,
                    "email":     "",
                    "city":      city,
                    "state":     st,
                    "revenue":   revenue,
                    "ntee":      ntee,
                    "search_term": term,
                    "status":    "pending",
                    "message":   "",
                    "subject":   "",
                })
                existing.add(ein)
                new_count += 1

            time.sleep(0.4)
        time.sleep(0.5)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FILE, index=False)
    print(f"[PROPUBLICA] Done. +{new_count} new orgs. Total: {len(rows)} in grant_queue.csv")
    print(f"  Next: run hunter_enricher.py to find emails for each org domain")


if __name__ == "__main__":
    run()
