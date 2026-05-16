"""
contractor_license_scraper.py - Gray Horizons Enterprise
Scrapes public state contractor license boards for HVAC, roofing, plumbing,
landscaping, and general contractor companies. All government public records -
no ToS issues. License holders = verified active businesses with real owners.

Strategy:
  1. California CSLB (largest: 300k+ licenses, filterable by trade)
  2. Texas TDLR (HVAC, plumbing, electrical)
  3. Generic state board fallback (publicrecords.com)

Trade codes (California CSLB):
  B  = General Building Contractor
  C-20 = HVAC
  C-27 = Landscaping
  C-36 = Plumbing
  C-39 = Roofing

Output: contractor_queue.csv
Next: run email_verifier.py then feed into outreach pipeline.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import sys
import time
import random
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.path.dirname(os.path.abspath(__file__))
OUT_FILE   = os.path.join(DATA_DIR, "contractor_queue.csv")
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# California trade license codes mapped to our niches
CSLB_TRADES = {
    "hvac":        "C-20",
    "roofing":     "C-39",
    "plumbing":    "C-36",
    "landscaping": "C-27",
    "general":     "B",
}

# Major California zip codes covering the highest-density metro areas
CA_METRO_ZIPS = [
    # Los Angeles
    "90001", "90010", "90025", "90040", "90057", "90210", "90230", "90272",
    "90401", "90502", "90620", "90630", "90701", "90731", "90802",
    # San Francisco Bay Area
    "94102", "94110", "94501", "94601", "94702", "94901", "95002", "95008",
    "95054", "95101", "95120", "95128", "95209", "95340", "95401",
    # San Diego
    "92101", "92108", "92121", "92130", "92154", "92173",
    # Sacramento
    "95814", "95821", "95826", "95838",
    # Inland Empire
    "92501", "92376", "91710", "91761",
    # Fresno / Central Valley
    "93701", "93720", "93728",
]

# Texas zip codes for TDLR searches
TX_METRO_ZIPS = [
    # Houston
    "77001", "77019", "77025", "77040", "77057", "77079", "77098",
    # Dallas / Fort Worth
    "75201", "75217", "75229", "75240", "76101", "76116", "76132",
    # San Antonio
    "78201", "78216", "78229", "78232",
    # Austin
    "78701", "78723", "78741", "78757",
]

# Florida zip codes
FL_METRO_ZIPS = [
    "33101", "33130", "33150", "33179", "33301", "33401", "33602",
    "33755", "34201", "32801", "32901",
]


def cslb_search_zip(session: requests.Session, zip_code: str, trade_code: str) -> list:
    """
    Search California CSLB contractor database by zip code and trade.
    Uses the public ZipCodeSearch endpoint.
    """
    results = []
    try:
        # Step 1: GET the page to capture ViewState and form tokens
        home_url = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/ZipCodeSearch.aspx"
        r = session.get(home_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Extract ASP.NET form tokens
        form_data = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name", "")
            val  = inp.get("value", "")
            if name:
                form_data[name] = val

        # Build form submission
        form_data.update({
            "ctl00$ContentPlaceHolder1$txtZipCode":       zip_code,
            "ctl00$ContentPlaceHolder1$ddlClassification": trade_code,
            "ctl00$ContentPlaceHolder1$btnSearch":         "Search",
        })

        # Step 2: POST the search form
        r2 = session.post(home_url, data=form_data, headers={
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": home_url,
        }, timeout=25)

        if r2.status_code != 200:
            return []

        soup2 = BeautifulSoup(r2.text, "html.parser")

        # Parse results table
        table = soup2.find("table", {"id": re.compile(r"gvResult|GridView|Results", re.I)})
        if not table:
            table = soup2.find("table", class_=re.compile(r"result|grid|license", re.I))
        if not table:
            # Try any table with 4+ columns (name, license#, city, classification)
            for t in soup2.find_all("table"):
                header_cells = t.find("tr")
                if header_cells and len(header_cells.find_all(["th", "td"])) >= 3:
                    table = t
                    break

        if table:
            rows = table.find_all("tr")[1:]  # skip header
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cells) >= 3 and cells[0]:
                    # Typical CSLB columns: License #, Business Name, City, Classification, Status
                    # Column order varies - find the business name (usually the longest text cell)
                    license_no = ""
                    company    = ""
                    city       = ""

                    for i, cell in enumerate(cells):
                        if re.match(r"^\d{5,9}$", cell):
                            license_no = cell
                        elif len(cell) > 5 and not re.match(r"^[A-Z]-\d+$", cell) and city == "":
                            if company == "":
                                company = cell
                            else:
                                city = cell

                    if company:
                        results.append({
                            "license_no": license_no,
                            "company":    company,
                            "city":       city,
                            "state":      "CA",
                            "zip":        zip_code,
                            "trade":      trade_code,
                            "name":       "",
                            "email":      "",
                            "source":     "cslb_ca",
                            "status":     "pending",
                        })

    except Exception as e:
        print(f"  [CSLB] Error zip {zip_code} trade {trade_code}: {e}")
    return results


def tdlr_search_zip(session: requests.Session, zip_code: str, trade: str) -> list:
    """
    Texas TDLR (Dept of Licensing and Regulation) - HVAC, plumbing, electrical.
    Public search at: https://www.tdlr.texas.gov/LicenseSearch/
    """
    results = []
    try:
        url = "https://www.tdlr.texas.gov/LicenseSearch/licfile.asp"
        # TDLR uses query params for their search
        params = {
            "lictype":   "HVAC" if trade == "hvac" else "PLUMB",
            "liczip":    zip_code,
            "B1":        "Search",
        }
        r = session.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if table:
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 2 and cells[0]:
                    results.append({
                        "license_no": cells[0] if cells else "",
                        "company":    cells[1] if len(cells) > 1 else "",
                        "city":       cells[2] if len(cells) > 2 else "",
                        "state":      "TX",
                        "zip":        zip_code,
                        "trade":      trade,
                        "name":       "",
                        "email":      "",
                        "source":     "tdlr_tx",
                        "status":     "pending",
                    })
    except Exception as e:
        print(f"  [TDLR] Error zip {zip_code}: {e}")
    return results


def florida_dbpr_search(session: requests.Session, zip_code: str, trade: str) -> list:
    """
    Florida DBPR contractor license search.
    Public records: https://www.myfloridalicense.com/
    """
    results = []
    # FL DBPR license types: CCC=roofing, CAC=HVAC, CFC=plumbing, CGC=general
    license_type_map = {
        "roofing":  "CCC",
        "hvac":     "CAC",
        "plumbing": "CFC",
        "general":  "CGC",
    }
    lic_type = license_type_map.get(trade, "CGC")
    try:
        url = "https://www.myfloridalicense.com/wl11.asp"
        params = {
            "mode":     "1",
            "SID":      "",
            "brd":      "0004",
            "typ":      lic_type,
            "zp":       zip_code,
            "S1":       "Search",
        }
        r = session.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", summary=re.compile(r"result|license", re.I))
        if not table:
            for t in soup.find_all("table"):
                if len(t.find_all("tr")) > 2:
                    table = t
                    break
        if table:
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 2 and cells[0]:
                    results.append({
                        "license_no": cells[0],
                        "company":    cells[1] if len(cells) > 1 else "",
                        "city":       cells[3] if len(cells) > 3 else "",
                        "state":      "FL",
                        "zip":        zip_code,
                        "trade":      trade,
                        "name":       "",
                        "email":      "",
                        "source":     "dbpr_fl",
                        "status":     "pending",
                    })
    except Exception as e:
        print(f"  [DBPR FL] Error zip {zip_code}: {e}")
    return results


def enrich_email_hunter(company: str) -> str:
    """Use Hunter.io domain search to find emails for a company."""
    if not HUNTER_KEY or not company:
        return ""
    try:
        # First try domain search by company name
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"company": company, "api_key": HUNTER_KEY, "limit": 1},
            timeout=10,
        )
        if r.status_code == 200:
            data  = r.json().get("data", {})
            emails = data.get("emails", [])
            if emails:
                # Prefer non-generic emails
                for e in emails:
                    prefix = e.get("value", "").split("@")[0].lower()
                    if e.get("type") == "personal" or prefix not in {
                        "info", "contact", "admin", "support", "hello", "sales", "office"
                    }:
                        return e.get("value", "")
                return emails[0].get("value", "")
    except Exception:
        pass
    return ""


def run(max_per_state: int = 100):
    print("[CONTRACTOR] Scraping state contractor license boards...")
    print(f"  Targets: CA CSLB, TX TDLR, FL DBPR")
    print(f"  Trades: {', '.join(CSLB_TRADES.keys())}")

    existing: set = set()
    rows: list    = []
    if os.path.exists(OUT_FILE):
        df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
        existing = set(df_exist["company"].str.lower().str.strip())
        rows     = df_exist.to_dict("records")
        print(f"  Existing: {len(rows)} contacts in contractor_queue.csv")

    session    = requests.Session()
    new_count  = 0
    with_email = 0

    # -- California CSLB --
    print("\n[CSLB CA] Searching by trade + zip...")
    ca_zips = random.sample(CA_METRO_ZIPS, min(20, len(CA_METRO_ZIPS)))
    for trade, code in CSLB_TRADES.items():
        if new_count >= max_per_state * 3:
            break
        print(f"  Trade: {trade} ({code})")
        for zip_code in ca_zips:
            contacts = cslb_search_zip(session, zip_code, code)
            for c in contacts:
                key = c["company"].lower().strip()
                if not key or key in existing:
                    continue
                if HUNTER_KEY:
                    c["email"] = enrich_email_hunter(c["company"])
                    if c["email"]:
                        with_email += 1
                    time.sleep(0.5)
                rows.append(c)
                existing.add(key)
                new_count += 1
                if c.get("email"):
                    print(f"    [+] {c['company']} | {c['city']} | {c['email']}")
                else:
                    print(f"    [ ] {c['company']} | {c['city']} CA")
            time.sleep(random.uniform(1.5, 3.0))

    # -- Texas TDLR --
    print("\n[TDLR TX] Searching HVAC + plumbing...")
    tx_zips = random.sample(TX_METRO_ZIPS, min(10, len(TX_METRO_ZIPS)))
    for trade in ["hvac", "plumbing"]:
        for zip_code in tx_zips:
            contacts = tdlr_search_zip(session, zip_code, trade)
            for c in contacts:
                key = c["company"].lower().strip()
                if not key or key in existing:
                    continue
                if HUNTER_KEY:
                    c["email"] = enrich_email_hunter(c["company"])
                    if c["email"]:
                        with_email += 1
                    time.sleep(0.5)
                rows.append(c)
                existing.add(key)
                new_count += 1
            time.sleep(random.uniform(1.5, 3.0))

    # -- Florida DBPR --
    print("\n[DBPR FL] Searching HVAC + roofing + general...")
    fl_zips = random.sample(FL_METRO_ZIPS, min(8, len(FL_METRO_ZIPS)))
    for trade in ["hvac", "roofing", "general"]:
        for zip_code in fl_zips:
            contacts = florida_dbpr_search(session, zip_code, trade)
            for c in contacts:
                key = c["company"].lower().strip()
                if not key or key in existing:
                    continue
                if HUNTER_KEY:
                    c["email"] = enrich_email_hunter(c["company"])
                    if c["email"]:
                        with_email += 1
                    time.sleep(0.5)
                rows.append(c)
                existing.add(key)
                new_count += 1
            time.sleep(random.uniform(1.5, 3.0))

    # Save results
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "license_no", "company", "city", "state", "zip", "trade",
        "name", "email", "source", "status",
    ])
    df.to_csv(OUT_FILE, index=False)

    print(f"\n[CONTRACTOR] Done. +{new_count} companies. Total: {len(rows)}")
    print(f"  With email: {with_email} | Without: {new_count - with_email}")
    if new_count == 0:
        print("  NOTE: State board sites use ASP.NET - they may block automated requests.")
        print("  If getting 0 results, try running with a VPN or smaller zip batch.")
        print("  Alternative: leadz.biz and coldlytics.com sell pre-built contractor lists.")
    elif not HUNTER_KEY:
        print("  Tip: Add HUNTER_API_KEY to Railway to auto-find emails for each company.")
        print("  Hunter.io domain search finds owner emails from company name alone.")


if __name__ == "__main__":
    run()
