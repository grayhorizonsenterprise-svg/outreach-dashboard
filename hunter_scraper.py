"""
hunter_scraper.py — Gray Horizons Enterprise
Hunter.io — finds NAMED personal decision-maker emails only.
Filters out all role addresses (info@, service@, contact@, etc.).
Only emails with confidence >= 70 AND a real person name enter the queue.

Mode 1: Enrichment — takes prospects_raw.csv rows with website, finds the right email
Mode 2: Direct search — searches niche seed domains for named owners/CEOs

Free tier: 25 domain searches/month, 50 verifications
Paid ($49/month): 500 searches — worth it, these are verified named contacts.

Get API key: app.hunter.io → Settings → API → copy key
Add HUNTER_API_KEY to Railway → ghe-dashboard → Variables
"""

import requests
import pandas as pd
import urllib.parse
import time
import os
import sys
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")
BASE_URL   = "https://api.hunter.io/v2"

MIN_CONFIDENCE = 70

OWNER_TITLES = [
    "owner", "co-owner", "ceo", "chief executive", "founder", "co-founder",
    "president", "partner", "principal", "managing director", "general manager",
    "practice owner", "clinic director", "practice manager", "proprietor",
]

# Seed domains for each niche — Hunter finds the named decision-maker at each
NICHE_SEEDS = {
    "hvac": [
        "highdesertmechanical.com", "aircomfortexperts.com", "precisionairhvac.com",
        "greenwayheating.com", "serviceexpressair.com", "clockworkair.com",
        "comfortmastersinc.com", "allseasonsheating.com", "procomfortair.com",
    ],
    "dental": [
        "smiledentistry.com", "familydentistrycare.com", "moderndentalgroup.com",
        "brightersmiledental.com", "completedentistry.com", "advanceddentalcare.com",
    ],
    "roofing": [
        "integrityroofingco.com", "eliteroofinggroup.com", "vertexroofing.com",
        "signaturerestorations.com", "protectedroofing.com", "peakperformanceroofing.com",
    ],
    "plumbing": [
        "servicemasterplumbing.com", "royalplumbingservice.com", "eliteplumbers.com",
        "accurateplumbing.com", "priorityplumbing.com",
    ],
    "landscaping": [
        "greenmasterslawn.com", "elitelawnpros.com", "nativelandscaping.com",
        "groundsguys.com", "forevergreenlandscaping.com", "promiselawncare.com",
    ],
    "contractor": [
        "buildrighthomes.com", "premiercontractingco.com", "elitehomebuilders.com",
        "mastercraftconstruction.com", "integritybuilders.com",
    ],
    "chiropractic": [
        "alignchiropractic.com", "motionchiropracticcare.com", "spineandwellness.com",
        "familychiropractic.com", "naturalspinecenter.com",
    ],
    "gym": [
        "evolutionfitnessgym.com", "peakperformancegym.com", "ironwillgym.com",
        "proelitegym.com", "crossfitperformance.com", "corefitnesscenter.com",
    ],
    "insurance": [
        "independentinsurancegroup.com", "keystoneinsurance.com",
        "localinsuranceagency.com", "trustedinsurancepartners.com",
    ],
    "realestate": [
        "keystonerealty.com", "elitehomesrealty.com", "prorealtors.com",
        "signaturepropertiesgroup.com", "advancedrealestate.com",
    ],
}


def _get(url: str, params: dict) -> dict | None:
    try:
        r = requests.get(url, params={**params, "api_key": HUNTER_KEY}, timeout=15)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print("[HUNTER] Rate limit — sleeping 60s")
            time.sleep(60)
        elif r.status_code == 401:
            print("[HUNTER] Invalid API key — check HUNTER_API_KEY in Railway vars")
        elif r.status_code == 422:
            pass  # domain not found in Hunter db — expected
        else:
            print(f"[HUNTER] {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[HUNTER] Request error: {e}")
    return None


def domain_search(domain: str) -> list:
    """Return personal emails at a domain with confidence >= MIN_CONFIDENCE."""
    data = _get(f"{BASE_URL}/domain-search", {"domain": domain, "type": "personal", "limit": 10})
    if not data:
        return []
    emails = data.get("data", {}).get("emails", [])
    return [
        e for e in emails
        if e.get("type") == "personal"
        and e.get("confidence", 0) >= MIN_CONFIDENCE
        and e.get("first_name")
        and e.get("last_name")
    ]


def _is_decision_maker(email_data: dict) -> bool:
    pos = (email_data.get("position") or "").lower()
    if not pos:
        return True  # no title info — include it (named personal email already)
    return any(t in pos for t in OWNER_TITLES)


def _parse(email_data: dict, domain: str, niche: str) -> dict | None:
    email = (email_data.get("value") or "").strip().lower()
    if not email or "@" not in email:
        return None
    first = (email_data.get("first_name") or "").strip()
    last  = (email_data.get("last_name") or "").strip()
    if not first or not last:
        return None
    position = (email_data.get("position") or "").strip()
    company  = domain.replace("www.", "").split(".")[0].replace("-", " ").title()
    return {
        "email":      email,
        "name":       f"{first} {last}",
        "company":    company,
        "title":      position,
        "website":    f"https://{domain}",
        "city":       "",
        "state":      "",
        "phone":      "",
        "niche":      niche,
        "source":     f"hunter:{domain}",
        "status":     "pending",
        "confidence": str(email_data.get("confidence", 0)),
    }


def enrich_existing(per_run_cap: int = 20):
    """
    Mode 1: Take rows in prospects_raw.csv that have a website but no email,
    find the named decision-maker email via Hunter domain search.
    """
    if not os.path.exists(OUT_FILE):
        return 0
    df = pd.read_csv(OUT_FILE, dtype=str).fillna("")

    needs = df[
        (df["email"].str.strip() == "") &
        (df.get("website", pd.Series([""] * len(df))).str.strip() != "")
    ]
    print(f"[HUNTER ENRICH] {len(needs)} leads need email enrichment")
    enriched = 0
    for i, row in list(needs.iterrows())[:per_run_cap]:
        site = str(row.get("website", "")).strip().rstrip("/")
        try:
            domain = urllib.parse.urlparse(site if site.startswith("http") else "https://" + site).netloc.lower().replace("www.", "")
        except Exception:
            continue
        if not domain or "." not in domain:
            continue
        emails = domain_search(domain)
        if not emails:
            time.sleep(1.5)
            continue
        # Prefer decision-makers
        best = next((e for e in emails if _is_decision_maker(e)), emails[0])
        email_val = best.get("value", "").lower().strip()
        if email_val:
            df.at[i, "email"]  = email_val
            df.at[i, "name"]   = f"{best.get('first_name','')} {best.get('last_name','')}".strip()
            df.at[i, "title"]  = best.get("position", "")
            df.at[i, "status"] = "pending"
            print(f"  [ENRICH +] {str(row.get('company',''))[:30]} → {email_val} [{best.get('confidence')}%]")
            enriched += 1
        time.sleep(random.uniform(1.5, 3))
    df.to_csv(OUT_FILE, index=False)
    print(f"[HUNTER ENRICH] {enriched} emails added")
    return enriched


def search_niche_domains(max_leads: int = 80):
    """
    Mode 2: Search seed domains per niche, pull named decision-maker emails,
    add them directly to prospects_raw.csv as new leads.
    """
    existing_emails: set = set()
    existing_rows:   list = []
    if os.path.exists(OUT_FILE):
        try:
            df_e = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            existing_emails = set(df_e["email"].str.lower().str.strip())
            existing_rows   = df_e.to_dict("records")
        except Exception:
            pass

    new_rows  = []
    new_count = 0
    niches = list(NICHE_SEEDS.keys())
    random.shuffle(niches)

    for niche in niches:
        if new_count >= max_leads:
            break
        domains = NICHE_SEEDS[niche][:]
        random.shuffle(domains)
        for domain in domains:
            if new_count >= max_leads:
                break
            print(f"  [HUNTER] {niche.upper()} | {domain}")
            emails = domain_search(domain)
            for e in emails:
                if new_count >= max_leads:
                    break
                if not _is_decision_maker(e):
                    continue
                rec = _parse(e, domain, niche)
                if not rec or rec["email"] in existing_emails:
                    continue
                existing_emails.add(rec["email"])
                new_rows.append(rec)
                new_count += 1
                print(f"    [+] {rec['name']} ({rec['title']}) — {rec['email']} [{rec['confidence']}%]")
            time.sleep(random.uniform(2, 4))

    if new_rows:
        all_rows = existing_rows + new_rows
        pd.DataFrame(all_rows).to_csv(OUT_FILE, index=False)
        print(f"[HUNTER] +{new_count} named decision-maker emails added (total: {len(all_rows)})")
    else:
        print("[HUNTER] No new leads this run")
    return new_count


def run():
    if not HUNTER_KEY:
        print("[HUNTER] HUNTER_API_KEY not set.")
        print("  Get it: app.hunter.io → Account → API → copy key")
        print("  Add HUNTER_API_KEY to Railway → ghe-dashboard → Variables")
        return

    print("[HUNTER] Mode: Enrich existing leads + search niche seed domains")
    enrich_existing(per_run_cap=15)
    search_niche_domains(max_leads=50)
    print("[HUNTER] Done. All emails are named personal contacts — expect <3% bounce rate.")


if __name__ == "__main__":
    run()
