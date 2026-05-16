"""
camicb_scraper.py - Gray Horizons Enterprise
Scrapes CAMICB's public Find-a-CMCA directory for credentialed HOA /
community association managers (CMCA designation). These are the actual
decision-makers who sign contracts for HOA management services.

Output: camicb_queue.csv (name, company, city, state, email, source)
Next: run email_verifier.py then feed into outreach pipeline.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import sys
import time
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.path.dirname(os.path.abspath(__file__))
OUT_FILE   = os.path.join(DATA_DIR, "camicb_queue.csv")
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.camicb.org/find-a-cmca",
}


def get_form_token(session: requests.Session) -> dict:
    """Fetch the search page and extract any hidden form fields."""
    tokens = {}
    try:
        r = session.get("https://www.camicb.org/find-a-cmca", headers=HEADERS, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for inp in soup.find_all("input", {"type": "hidden"}):
                name = inp.get("name", "")
                val  = inp.get("value", "")
                if name:
                    tokens[name] = val
    except Exception as e:
        print(f"  [CAMICB] Could not load form: {e}")
    return tokens


def search_by_state(state: str, session: requests.Session, tokens: dict) -> list:
    """POST to CAMICB search form for a given state, return list of manager dicts."""
    results = []
    try:
        form_data = {**tokens, "state": state, "last_name": "", "city": "", "company": ""}
        r = session.post(
            "https://www.camicb.org/find-a-cmca",
            data=form_data,
            headers=HEADERS,
            timeout=20,
        )
        if r.status_code != 200:
            # Try GET with query params as fallback
            r = session.get(
                "https://www.camicb.org/find-a-cmca",
                params={"state": state},
                headers=HEADERS,
                timeout=20,
            )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")

            # Try table rows first (most common directory layout)
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]  # skip header row
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) >= 2 and cells[0]:
                        results.append({
                            "name":    cells[0],
                            "company": cells[1] if len(cells) > 1 else "",
                            "city":    cells[2] if len(cells) > 2 else "",
                            "state":   state,
                            "email":   "",
                            "source":  "camicb",
                            "status":  "pending",
                        })

            # Fallback: div-based results
            if not results:
                for div in soup.select(".search-result, .directory-result, .member-result, .result-row"):
                    name_el    = div.select_one(".name, h3, h4, strong")
                    company_el = div.select_one(".company, .organization, .employer")
                    city_el    = div.select_one(".city, .location")
                    if name_el:
                        results.append({
                            "name":    name_el.get_text(strip=True),
                            "company": company_el.get_text(strip=True) if company_el else "",
                            "city":    city_el.get_text(strip=True) if city_el else "",
                            "state":   state,
                            "email":   "",
                            "source":  "camicb",
                            "status":  "pending",
                        })

            if not results:
                # Check if page returned a "no results" or a login wall
                page_text = soup.get_text(separator=" ", strip=True).lower()
                if "no results" in page_text or "no records" in page_text:
                    pass  # genuine empty state
                elif "login" in page_text or "sign in" in page_text:
                    print(f"  [CAMICB] Login wall detected for {state} - directory may require account")
        else:
            print(f"  [CAMICB] HTTP {r.status_code} for state {state}")

    except Exception as e:
        print(f"  [CAMICB] Error for {state}: {e}")
    return results


def find_email_hunter(first: str, last: str, company: str) -> str:
    """Use Hunter.io email finder to enrich a contact."""
    if not HUNTER_KEY or not company or not first or not last:
        return ""
    try:
        r = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "company":    company,
                "first_name": first,
                "last_name":  last,
                "api_key":    HUNTER_KEY,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("email", "")
    except Exception:
        pass
    return ""


def parse_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return full_name, ""


def run():
    print("[CAMICB] Scraping CAMICB Find-a-CMCA directory for HOA managers...")

    existing: set = set()
    rows: list    = []
    if os.path.exists(OUT_FILE):
        df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
        existing = set((df_exist["name"] + "|" + df_exist["state"]).str.lower())
        rows     = df_exist.to_dict("records")
        print(f"  Existing: {len(rows)} contacts in camicb_queue.csv")

    session    = requests.Session()
    tokens     = get_form_token(session)
    new_count  = 0
    with_email = 0

    for state in STATES:
        print(f"  [CAMICB] State: {state}", end=" ", flush=True)
        contacts = search_by_state(state, session, tokens)
        added = 0
        for c in contacts:
            key = f"{c['name']}|{c['state']}".lower()
            if key in existing:
                continue
            # Hunter enrichment if key available
            if HUNTER_KEY and c["company"]:
                first, last = parse_name(c["name"])
                c["email"] = find_email_hunter(first, last, c["company"])
                time.sleep(0.6)
                if c["email"]:
                    with_email += 1
            rows.append(c)
            existing.add(key)
            new_count += 1
            added += 1
        print(f"-> {added} found")
        time.sleep(random.uniform(2.0, 4.0))

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["name", "company", "city", "state", "email", "source", "status"])
    df.to_csv(OUT_FILE, index=False)
    print(f"\n[CAMICB] Done. +{new_count} managers added. Total: {len(rows)}")
    print(f"  With email: {with_email} | Without: {new_count - with_email}")
    if new_count == 0:
        print("  NOTE: CAMICB directory may require a member login.")
        print("  If that's the case, the CAI directory (caionline.org) is an alternative.")
        print("  Or enrich company names via Hunter: add HUNTER_API_KEY to Railway env vars.")
    elif not HUNTER_KEY:
        print("  Tip: Add HUNTER_API_KEY to Railway to auto-find emails for each manager.")


if __name__ == "__main__":
    run()
