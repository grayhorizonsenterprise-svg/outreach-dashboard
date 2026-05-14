"""
finra_leads.py — Gray Horizons Enterprise
FINRA BrokerCheck public API → Hunter.io → verified financial advisor emails.

Why this works:
  - FINRA has 600,000+ registered brokers/advisors in the US
  - These are ACTIVE traders who manage money daily
  - They want signals, indicators, and edge
  - Their firm emails are professional and indexed in Hunter
  - 100% free to access (public regulatory database)
  - Conversion to signals subscription is highest of any audience

Flow: FINRA search → firm name → Hunter domain lookup (free) →
      Hunter email-count check (free) → Hunter domain search (1 credit) → named email

No credits wasted on domains with 0 results.
Writes to signals_queue.csv — goes straight to signals blast.
"""

import requests
import pandas as pd
import os
import sys
import time
import random
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "signals_queue.csv")
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")
BASE_HUNTER = "https://api.hunter.io/v2"

FINRA_SEARCH = "https://efts.finra.org/LATEST/search-index"
FINRA_API    = "https://api.brokercheck.finra.org/search/individual"

MIN_CONFIDENCE = 65

# States with highest concentration of independent financial advisors
TARGET_STATES = [
    "FL", "TX", "CA", "NY", "GA", "NC", "AZ", "CO", "TN", "NV",
    "OH", "IL", "VA", "WA", "MN", "MO", "IN", "MD", "WI", "OR",
]

FINRA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://brokercheck.finra.org/",
}


def search_finra(state: str, start: int = 0) -> list:
    """Search FINRA for registered individual advisors in a state."""
    try:
        params = {
            "query":            "*",
            "hl":               "true",
            "includePrevious":  "true",
            "wt":               "json",
            "sort":             "score+desc",
            "start":            start,
            "rows":             25,
            "fq":               f"stateOfEmployment:{state} AND iacrd:\"RA\" AND NOT disclosureCount:[1 TO *]",
        }
        r = requests.get(FINRA_API, headers=FINRA_HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            hits = r.json().get("hits", {}).get("hits", [])
            return hits
        else:
            print(f"  [FINRA] {r.status_code} for {state}")
    except Exception as e:
        print(f"  [FINRA] Error: {e}")
    return []


def parse_advisor(hit: dict) -> dict | None:
    """Extract advisor info from FINRA hit."""
    try:
        source = hit.get("_source", {})
        ind    = source.get("ind_bc_scope", {}) if isinstance(source.get("ind_bc_scope"), dict) else {}

        first = (source.get("ind_firstname") or source.get("firstname") or "").strip()
        last  = (source.get("ind_lastname") or source.get("lastname") or "").strip()
        if not first or not last:
            return None

        firm = (
            source.get("ind_bc_scope", {}).get("currentEmployments", [{}])[0].get("firmName", "")
            if isinstance(source.get("ind_bc_scope"), dict)
            else ""
        )
        if not firm:
            firms = source.get("currentFirms", [])
            firm = firms[0].get("firmName", "") if firms else ""

        state = source.get("stateOfEmployment", "")
        city  = source.get("ind_bc_scope", {}).get("currentEmployments", [{}])[0].get("city", "") \
                if isinstance(source.get("ind_bc_scope"), dict) else ""

        return {
            "first": first,
            "last":  last,
            "firm":  firm.strip(),
            "city":  city.strip(),
            "state": state.strip(),
        }
    except Exception:
        return None


def hunter_find_domain(company: str) -> str:
    """Find a company's email domain by name — FREE, no credit used."""
    if not HUNTER_KEY or not company:
        return ""
    try:
        r = requests.get(
            f"{BASE_HUNTER}/domain-search",
            params={"company": company, "api_key": HUNTER_KEY, "limit": 1},
            timeout=10,
        )
        if r.status_code == 200:
            domain = r.json().get("data", {}).get("domain", "")
            return domain or ""
        elif r.status_code == 404:
            return ""
    except Exception:
        pass
    return ""


def hunter_email_count(domain: str) -> int:
    """Check how many personal emails Hunter has for a domain — FREE."""
    if not HUNTER_KEY or not domain:
        return 0
    try:
        r = requests.get(
            f"{BASE_HUNTER}/email-count",
            params={"domain": domain, "api_key": HUNTER_KEY},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("personal_emails", 0)
    except Exception:
        pass
    return 0


def hunter_domain_search(domain: str) -> list:
    """Get personal emails at domain — costs 1 credit. Only call after count check."""
    if not HUNTER_KEY or not domain:
        return []
    try:
        r = requests.get(
            f"{BASE_HUNTER}/domain-search",
            params={
                "domain":  domain,
                "type":    "personal",
                "limit":   5,
                "api_key": HUNTER_KEY,
            },
            timeout=12,
        )
        if r.status_code == 200:
            emails = r.json().get("data", {}).get("emails", [])
            return [
                e for e in emails
                if e.get("confidence", 0) >= MIN_CONFIDENCE
                and e.get("first_name")
                and e.get("last_name")
            ]
    except Exception:
        pass
    return []


def hunter_email_finder(first: str, last: str, domain: str) -> str:
    """Find specific person's email — costs 1 credit. Most precise method."""
    if not HUNTER_KEY or not domain:
        return ""
    try:
        r = requests.get(
            f"{BASE_HUNTER}/email-finder",
            params={
                "first_name": first,
                "last_name":  last,
                "domain":     domain,
                "api_key":    HUNTER_KEY,
            },
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data.get("score", 0) >= MIN_CONFIDENCE:
                return data.get("email", "")
    except Exception:
        pass
    return ""


def run(max_leads: int = 40, credits_budget: int = 35):
    """
    Pull financial advisors from FINRA, find their firm emails via Hunter.
    max_leads: stop after this many new leads
    credits_budget: never spend more than this many Hunter credits in one run
    """
    if not HUNTER_KEY:
        print("[FINRA] HUNTER_API_KEY not set — cannot find emails")
        return

    print(f"[FINRA] Searching for financial advisor leads (budget: {credits_budget} Hunter credits)...")

    # Load existing to dedup
    existing_emails: set = set()
    existing_rows:   list = []
    if os.path.exists(OUT_FILE):
        try:
            df_e = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            existing_emails = set(df_e["email"].str.lower().str.strip())
            existing_rows   = df_e.to_dict("records")
        except Exception:
            pass

    new_rows     = []
    new_count    = 0
    credits_used = 0
    states       = random.sample(TARGET_STATES, min(8, len(TARGET_STATES)))

    for state in states:
        if new_count >= max_leads or credits_used >= credits_budget:
            break

        print(f"  [FINRA] Searching {state}...")
        start = random.randint(0, 200)  # vary starting position to get different advisors each run
        hits  = search_finra(state, start)

        if not hits:
            time.sleep(2)
            continue

        random.shuffle(hits)
        for hit in hits:
            if new_count >= max_leads or credits_used >= credits_budget:
                break

            advisor = parse_advisor(hit)
            if not advisor or not advisor["firm"]:
                continue

            firm  = advisor["firm"]
            first = advisor["first"]
            last  = advisor["last"]

            # Step 1: Find firm domain by company name (FREE)
            domain = hunter_find_domain(firm)
            if not domain:
                # Try simplified firm name
                firm_simple = firm.split(",")[0].split(" LLC")[0].split(" Inc")[0].strip()
                domain = hunter_find_domain(firm_simple)
            if not domain:
                continue

            # Skip big wire-houses — want independent advisors who make own decisions
            skip_firms = ["morgan stanley", "merrill lynch", "wells fargo", "edward jones",
                          "ameriprise", "raymond james", "fidelity", "vanguard", "schwab",
                          "jpmorgan", "goldman sachs", "citigroup", "ubs", "stifel"]
            if any(s in domain.lower() or s in firm.lower() for s in skip_firms):
                continue

            # Step 2: Check if Hunter has personal emails (FREE)
            personal_count = hunter_email_count(domain)
            if personal_count == 0:
                continue

            # Step 3: Find this specific person's email (1 credit)
            email = hunter_email_finder(first, last, domain)
            credits_used += 1

            if not email:
                # Fallback: domain search to get any advisor email there (1 credit)
                emails = hunter_domain_search(domain)
                credits_used += 1
                email = emails[0]["value"] if emails else ""

            if not email or email.lower() in existing_emails:
                continue

            existing_emails.add(email.lower())
            new_rows.append({
                "email":   email.lower(),
                "name":    f"{first} {last}",
                "company": firm,
                "city":    advisor["city"],
                "state":   advisor["state"],
                "phone":   "",
                "niche":   "financial_advisor",
                "source":  f"finra:{state}",
                "status":  "pending",
            })
            new_count += 1
            print(f"    [+] {first} {last} | {firm} | {email} [{credits_used} credits used]")

        time.sleep(random.uniform(2, 4))

    if new_rows:
        all_rows = existing_rows + new_rows
        pd.DataFrame(all_rows).to_csv(OUT_FILE, index=False)
        print(f"[FINRA] Done. +{new_count} financial advisor leads added ({credits_used} Hunter credits used)")
        print(f"[FINRA] These go to signals_queue.csv → signals blast tomorrow morning")
    else:
        print(f"[FINRA] No new leads this run ({credits_used} credits used)")
        print(f"[FINRA] Try again after Hunter resets May 22 or upgrade to Starter ($49/mo = 500 credits)")


if __name__ == "__main__":
    run()
