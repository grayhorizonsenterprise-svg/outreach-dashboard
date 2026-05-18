"""
snov_scraper.py - Gray Horizons Enterprise
Snov.io Pro — domain email finder across all niches.
Reads companies with websites from prospects_raw.csv (no email yet),
finds decision-maker emails via Snov.io domain search, appends results.
Runs automatically every 6 hours as part of the main pipeline.

Setup (one time):
  1. snov.io → Settings → API → copy API User ID + API Secret
  2. Add to Railway: SNOV_CLIENT_ID, SNOV_CLIENT_SECRET

Credits: ~1 per email found. 5,000/month = ~5,000 verified leads.
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

TOKEN_URL  = "https://api.snov.io/v1/oauth/access_token"
DOMAIN_URL = "https://api.snov.io/v1/get-domain-emails-with-info"

OWNER_TITLES = {
    "owner", "co-owner", "ceo", "chief executive", "founder", "co-founder",
    "president", "partner", "principal", "managing director", "general manager",
    "practice owner", "office manager", "director", "proprietor",
}

# Seed domains per niche — real local business websites Snov searches for decision-makers
NICHE_DOMAINS = {
    "hvac": [
        "highdesertmechanical.com","aircomfortexperts.com","precisionairhvac.com",
        "greenwayheating.com","clockworkair.com","comfortmastersinc.com",
        "allseasonsheating.com","procomfortair.com","texasairsystems.com",
        "floridaaccutemp.com","arizonaairconditioningrepair.com","hvacpros.com",
        "columbusheatingair.com","nashvilleac.com","phoenixhvacpros.com",
    ],
    "roofing": [
        "integrityroofingco.com","eliteroofinggroup.com","vertexroofing.com",
        "signaturerestorations.com","protectedroofing.com","peakroofing.com",
        "texasroofingpros.com","floridaeliteroofing.com","atlroofinggroup.com",
        "carolinaroofexperts.com","coloradopeakroofing.com","nevadaproroofing.com",
    ],
    "plumbing": [
        "royalplumbingservice.com","eliteplumbers.com","accurateplumbing.com",
        "priorityplumbing.com","texasplumbingpros.com","floridaplumbers.com",
        "georgiaeliteplumbing.com","phoenixplumbingpros.com","ncplumbingexperts.com",
    ],
    "landscaping": [
        "greenmasterslawn.com","elitelawnpros.com","nativelandscaping.com",
        "texaslawncare.com","floridaelitelandscaping.com","georgiaprolawn.com",
        "arizonadesertlandscaping.com","coloradolandscapedesign.com",
    ],
    "contractor": [
        "integritybuildersinc.com","precisionhomeremodeling.com","elitecontractors.com",
        "texasremodeling.com","floridacontractors.com","georgiahomebuilders.com",
        "arizonacontractorpros.com","coloradobuilders.com","nashvilleremodeling.com",
    ],
    "dental": [
        "smiledentistry.com","familydentistrycare.com","moderndentalgroup.com",
        "brightersmiledental.com","completedentistry.com","advanceddentalcare.com",
        "texasfamilydental.com","floridadentalgroup.com","georgiadentistry.com",
    ],
    "auto": [
        "precisionautorepair.com","eliteautoservice.com","masterautotech.com",
        "texasautorepair.com","floridacarcare.com","georgiaautoshop.com",
        "arizonaautorepair.com","coloradoautoservice.com","nashvilleautorepair.com",
    ],
    "hoa": [
        "associatedmanagement.com","communityassociationmgmt.com","elitehoa.com",
        "propertymgmtgroup.com","texashoa.com","floridahoamanagement.com",
        "georgiahoa.com","arizonahoa.com","coloradohoa.com","carolinahoa.com",
    ],
    "pest_control": [
        "elitepestcontrol.com","proexterminating.com","guardianpestservices.com",
        "texaspestcontrol.com","floridapestpros.com","georgiapestcontrol.com",
        "arizonapestexperts.com","coloradopestpros.com",
    ],
    "electrician": [
        "precisionelectrical.com","eliteelectricgroup.com","masterelectricians.com",
        "texaselectricpros.com","floridaelectricians.com","georgiaelectric.com",
        "arizonaelectricalcontractors.com","coloradoelectricpros.com",
    ],
    "financial": [
        "independentfinancialadvisors.com","wealthmanagementpros.com","riagroup.com",
        "texasfinancialadvisors.com","floridafinancialplanning.com","georgiawealth.com",
    ],
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


def domain_search(token: str, domain: str) -> list:
    """Find decision-maker emails at a company domain."""
    try:
        r = requests.post(
            DOMAIN_URL,
            data={"domain": domain, "type": "personal", "limit": 10, "lastId": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("emails", [])
        elif r.status_code == 402:
            print("[SNOV] Credits exhausted")
            return None
        elif r.status_code == 401:
            print("[SNOV] Token expired")
            return None
        else:
            print(f"[SNOV] Domain search {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"[SNOV] Error: {e}")
    return []


def is_decision_maker(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(o in t for o in OWNER_TITLES)


def parse_email_record(rec: dict, domain: str, niche: str) -> dict | None:
    email = (rec.get("value") or "").strip().lower()
    if not email or "@" not in email:
        return None

    # Skip role/generic addresses
    prefix = email.split("@")[0]
    role = {"info", "contact", "admin", "support", "hello", "office",
            "sales", "help", "team", "marketing", "noreply", "no-reply",
            "billing", "accounts", "service", "care"}
    if prefix in role:
        return None

    status = (rec.get("emailStatus") or rec.get("email_status") or "").lower()
    if status in ("invalid", "bounced", "unverifiable"):
        return None

    first = (rec.get("firstName") or rec.get("first_name") or "").strip()
    last  = (rec.get("lastName")  or rec.get("last_name")  or "").strip()
    name  = f"{first} {last}".strip()
    title = (rec.get("position") or rec.get("title") or "").strip()

    return {
        "email":   email,
        "name":    name,
        "company": domain,
        "title":   title,
        "niche":   niche,
        "website": f"https://{domain}",
        "source":  "snov_domain",
        "status":  "pending",
    }


def run(max_contacts: int = 400):
    if not SNOV_CLIENT_ID or not SNOV_SECRET:
        print("[SNOV] Credentials not set — add SNOV_CLIENT_ID + SNOV_CLIENT_SECRET to Railway")
        return

    token = get_token()
    if not token:
        print("[SNOV] Auth failed")
        return

    print(f"[SNOV] Authenticated. Searching {len(NICHE_DOMAINS)} niches via domain lookup...")

    # Load already-contacted emails + domains from DB
    existing_emails:  set = set()
    existing_domains: set = set()
    if DB_URL:
        try:
            conn = psycopg2.connect(DB_URL, sslmode="require")
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (e,) in cur.fetchall():
                    if e:
                        em = str(e).strip().lower()
                        existing_emails.add(em)
                        if "@" in em:
                            existing_domains.add(em.split("@")[-1])
            conn.close()
            print(f"  Blocking {len(existing_emails)} already-contacted emails / {len(existing_domains)} domains")
        except Exception as ex:
            print(f"  DB load skipped: {ex}")

    # Also load from existing prospects_raw.csv
    rows: list = []
    if os.path.exists(OUT_FILE):
        try:
            df_exist = pd.read_csv(OUT_FILE, dtype=str).fillna("")
            for e in df_exist.get("email", pd.Series(dtype=str)).str.lower().str.strip():
                if e:
                    existing_emails.add(e)
                    if "@" in e:
                        existing_domains.add(e.split("@")[-1])
            rows = df_exist.to_dict("records")
        except Exception:
            pass

    new_count = 0
    credits_exhausted = False

    # Shuffle niches + domains each run for variety
    niches = list(NICHE_DOMAINS.items())
    random.shuffle(niches)

    for niche, domains in niches:
        if credits_exhausted or new_count >= max_contacts:
            break
        random.shuffle(domains)
        for domain in domains:
            if credits_exhausted or new_count >= max_contacts:
                break
            if domain in existing_domains:
                print(f"  [SKIP] {domain} already contacted")
                continue

            print(f"  [SNOV] {niche.upper()} | {domain}")
            emails = domain_search(token, domain)

            if emails is None:
                credits_exhausted = True
                break

            for rec in emails:
                if new_count >= max_contacts:
                    break
                result = parse_email_record(rec, domain, niche)
                if not result:
                    continue
                email  = result["email"]
                dom    = email.split("@")[-1]
                if email in existing_emails or dom in existing_domains:
                    continue
                existing_emails.add(email)
                existing_domains.add(dom)
                rows.append(result)
                new_count += 1
                print(f"    [+] {result['name'] or 'Unknown'} | {result['title'] or 'No title'} | {email}")

            time.sleep(random.uniform(1.0, 2.5))

    if not rows:
        print("[SNOV] No new contacts found")
        return

    pd.DataFrame(rows).to_csv(OUT_FILE, index=False)
    print(f"\n[SNOV] Done. +{new_count} new contacts. Total pipeline: {len(rows)}")
    if credits_exhausted:
        print("  Credits exhausted — will resume next billing cycle")


if __name__ == "__main__":
    run()
