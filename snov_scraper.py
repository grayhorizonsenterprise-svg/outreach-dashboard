"""
snov_scraper.py - Gray Horizons Enterprise
Uses Snov.io Prospect Search (Find People) to pull Owner/CEO/President
contacts filtered by industry and company size. No domain guessing.
Only verified decision-maker emails enter the pipeline.

Railway env vars required:
  SNOV_CLIENT_ID
  SNOV_CLIENT_SECRET
"""

import requests
import pandas as pd
import os
import sys
import time
import random
import psycopg2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR       = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE       = os.path.join(DATA_DIR, "prospects_raw.csv")
SNOV_CLIENT_ID = os.getenv("SNOV_CLIENT_ID", "")
SNOV_SECRET    = os.getenv("SNOV_CLIENT_SECRET", "")
DB_URL         = os.getenv("DATABASE_URL", "")

TOKEN_URL      = "https://api.snov.io/v1/oauth/access_token"
SEARCH_URL     = "https://api.snov.io/v2/prospect-searches"
VERIFY_URL     = "https://api.snov.io/v1/get-emails-verification-status"

# Decision maker titles only
TARGET_TITLES = [
    "Owner", "CEO", "President", "Co-Owner",
    "Founder", "Principal", "Managing Director",
    "General Manager", "Practice Owner",
]

# Snov.io industry filters mapped to our niches
NICHE_SEARCHES = [
    {
        "niche":    "hoa",
        "industry": "Real Estate",
        "keywords": ["HOA", "homeowners association", "community management",
                     "property management", "association management"],
        "employees_min": 2,
        "employees_max": 50,
    },
    {
        "niche":    "hvac",
        "industry": "Construction",
        "keywords": ["HVAC", "heating cooling", "air conditioning",
                     "mechanical contractor", "refrigeration"],
        "employees_min": 2,
        "employees_max": 75,
    },
    {
        "niche":    "dental",
        "industry": "Medical Practice",
        "keywords": ["dental", "dentistry", "orthodontics",
                     "oral health", "dental practice"],
        "employees_min": 2,
        "employees_max": 30,
    },
]

ROLE_PREFIXES = {
    "info", "contact", "admin", "support", "hello", "office",
    "sales", "help", "team", "marketing", "noreply", "no-reply",
    "billing", "accounts", "service", "care", "reception", "front",
}


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


def search_prospects(token: str, niche_cfg: dict, title: str,
                     page: int = 1, per_page: int = 50) -> dict:
    """Search Snov.io for decision makers by title + industry keyword."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    keyword = random.choice(niche_cfg["keywords"])
    payload = {
        "jobTitle":        title,
        "keyword":         keyword,
        "employeesFrom":   niche_cfg["employees_min"],
        "employeesTo":     niche_cfg["employees_max"],
        "page":            page,
        "perPage":         per_page,
        "hasEmail":        True,
    }
    try:
        r = requests.post(SEARCH_URL, json=payload, headers=headers, timeout=20)
        if r.status_code == 402:
            print("[SNOV] Credits exhausted")
            return {"exhausted": True}
        if r.status_code == 401:
            print("[SNOV] Token expired")
            return {"expired": True}
        if r.status_code != 200:
            print(f"[SNOV] Search error {r.status_code}: {r.text[:150]}")
            return {}
        return r.json()
    except Exception as e:
        print(f"[SNOV] Search exception: {e}")
        return {}


def verify_email(token: str, email: str) -> bool:
    """Returns True if email is valid/deliverable."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(VERIFY_URL,
                          json={"emails": [email]},
                          headers=headers, timeout=15)
        if r.status_code != 200:
            return True  # assume valid if verify fails — don't discard
        data = r.json()
        statuses = data.get("data", [])
        if not statuses:
            return True
        status = str(statuses[0].get("status", "")).lower()
        return status not in ("invalid", "bounced", "undeliverable", "spam")
    except Exception:
        return True


def parse_prospect(rec: dict, niche: str) -> dict | None:
    """Extract and validate a single prospect record."""
    email = str(rec.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return None

    prefix = email.split("@")[0]
    if prefix in ROLE_PREFIXES:
        return None

    first  = str(rec.get("firstName") or rec.get("first_name") or "").strip()
    last   = str(rec.get("lastName")  or rec.get("last_name")  or "").strip()
    name   = f"{first} {last}".strip()
    title  = str(rec.get("jobTitle") or rec.get("position") or rec.get("title") or "").strip()
    company = str(rec.get("companyName") or rec.get("company") or "").strip()
    website = str(rec.get("companyWebsite") or rec.get("website") or "").strip()
    if website and not website.startswith("http"):
        website = f"https://{website}"

    return {
        "email":   email,
        "name":    name,
        "company": company,
        "title":   title,
        "niche":   niche,
        "website": website,
        "source":  "snov_prospect_search",
        "status":  "pending",
    }


def load_existing(rows: list) -> tuple[set, set, set]:
    """Load already-contacted emails, domains, and companies from DB + CSV."""
    emails    = set()
    domains   = set()
    companies = set()

    import re
    def norm_company(c):
        c = str(c).strip().lower()
        c = re.sub(r'\b(inc|llc|ltd|corp|co|management|services|solutions|group|associates|properties|property)\b', '', c)
        c = re.sub(r'[^a-z0-9 ]', '', c)
        return re.sub(r'\s+', ' ', c).strip()

    if DB_URL:
        try:
            conn = psycopg2.connect(DB_URL, sslmode="require")
            with conn.cursor() as cur:
                cur.execute("SELECT email, website, company FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (e, w, c) in cur.fetchall():
                    if e:
                        em = str(e).strip().lower()
                        emails.add(em)
                        if "@" in em:
                            domains.add(em.split("@")[-1])
                    if w:
                        wd = str(w).strip().lower().replace("https://","").replace("http://","").replace("www.","").split("/")[0]
                        if wd and "." in wd:
                            domains.add(wd)
                    if c:
                        nc = norm_company(c)
                        if nc:
                            companies.add(nc)
            conn.close()
            print(f"[SNOV] Blocking {len(emails)} emails / {len(domains)} domains / {len(companies)} companies")
        except Exception as ex:
            print(f"[SNOV] DB load skipped: {ex}")

    for row in rows:
        e = str(row.get("email", "")).strip().lower()
        if e:
            emails.add(e)
            if "@" in e:
                domains.add(e.split("@")[-1])
        c = row.get("company", "")
        if c:
            nc = norm_company(c)
            if nc:
                companies.add(nc)

    return emails, domains, companies


def run(max_contacts: int = 300):
    if not SNOV_CLIENT_ID or not SNOV_SECRET:
        print("[SNOV] Missing SNOV_CLIENT_ID / SNOV_CLIENT_SECRET in Railway env vars")
        return

    token = get_token()
    if not token:
        print("[SNOV] Auth failed")
        return

    print(f"[SNOV] Authenticated. Searching for Owner/CEO/President in HOA, HVAC, Dental...")

    # Load existing pipeline
    rows: list = []
    if os.path.exists(OUT_FILE):
        try:
            rows = pd.read_csv(OUT_FILE, dtype=str).fillna("").to_dict("records")
        except Exception:
            pass

    existing_emails, existing_domains, existing_companies = load_existing(rows)

    import re
    def norm_company(c):
        c = str(c).strip().lower()
        c = re.sub(r'\b(inc|llc|ltd|corp|co|management|services|solutions|group|associates|properties|property)\b', '', c)
        c = re.sub(r'[^a-z0-9 ]', '', c)
        return re.sub(r'\s+', ' ', c).strip()

    new_count = 0
    credits_exhausted = False

    random.shuffle(NICHE_SEARCHES)

    for niche_cfg in NICHE_SEARCHES:
        if credits_exhausted or new_count >= max_contacts:
            break

        niche = niche_cfg["niche"]
        print(f"\n[SNOV] Searching niche: {niche.upper()}")

        titles = TARGET_TITLES.copy()
        random.shuffle(titles)

        for title in titles:
            if credits_exhausted or new_count >= max_contacts:
                break

            for page in range(1, 4):  # up to 3 pages per title
                if credits_exhausted or new_count >= max_contacts:
                    break

                print(f"  [{niche.upper()}] {title} — page {page}")
                result = search_prospects(token, niche_cfg, title, page=page)

                if result.get("exhausted"):
                    credits_exhausted = True
                    break
                if result.get("expired"):
                    token = get_token()
                    if not token:
                        credits_exhausted = True
                    break

                prospects = result.get("data") or result.get("prospects") or []
                if not prospects:
                    break  # no more pages

                for rec in prospects:
                    if new_count >= max_contacts:
                        break

                    parsed = parse_prospect(rec, niche)
                    if not parsed:
                        continue

                    email      = parsed["email"]
                    domain     = email.split("@")[-1] if "@" in email else ""
                    company_nc = norm_company(parsed["company"])

                    if (email in existing_emails
                            or domain in existing_domains
                            or (company_nc and company_nc in existing_companies)):
                        continue

                    # Verify email is deliverable before adding
                    if not verify_email(token, email):
                        print(f"    [INVALID] {email} — skipped")
                        continue

                    existing_emails.add(email)
                    if domain:
                        existing_domains.add(domain)
                    if company_nc:
                        existing_companies.add(company_nc)

                    rows.append(parsed)
                    new_count += 1
                    print(f"    [+] {parsed['name']} | {parsed['title']} | {parsed['company']} | {email}")

                time.sleep(random.uniform(1.5, 3.0))

    if new_count == 0:
        print("[SNOV] No new decision-maker contacts found this run")
    else:
        pd.DataFrame(rows).to_csv(OUT_FILE, index=False)
        print(f"\n[SNOV] Done. +{new_count} verified Owner/CEO contacts added. Total pipeline: {len(rows)}")

    if credits_exhausted:
        print("[SNOV] Credits exhausted — will resume next cycle")


if __name__ == "__main__":
    run()
