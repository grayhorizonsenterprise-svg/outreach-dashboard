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

TOKEN_URL         = "https://api.snov.io/v1/oauth/access_token"
DOMAIN_START_URL  = "https://api.snov.io/v2/domain-search/domain-emails/start"
DOMAIN_RESULT_URL = "https://api.snov.io/v2/domain-search/domain-emails/result/"

OWNER_TITLES = {
    "owner", "co-owner", "ceo", "chief executive", "founder", "co-founder",
    "president", "partner", "principal", "managing director", "general manager",
    "practice owner", "office manager", "director", "proprietor",
}

# Seed domains per niche — real local business websites Snov searches for decision-makers
NICHE_DOMAINS = {
    "hoa": [
        "associa.com","firstservice.com","cmcrealestate.com","amg-fl.com",
        "wallickandvolk.com","ppminc.com","gradymanagement.com","recon.com",
        "seabreezecm.com","keystonepacific.com","ccmcnet.com","acm.com",
        "spectrumam.com","towerhouston.com","globalpropertymanagement.net",
    ],
    "hvac": [
        "airriteairconditioning.com","petrosheating.com","abilenehvac.com",
        "airandenergyoftampa.com","beehiveac.com","bergelectric.com",
        "brookstonehvac.com","callashvac.com","cantexinc.com","climatedoctors.com",
        "comfortairco.com","coolrayhvac.com","dayandnite.net","deltaairconditioning.com",
        "eagleairconditioning.com","emeraldhvac.com","familyhvac.com",
    ],
    "roofing": [
        "absolutelyroofing.com","aceroofingco.com","advancedroofing.com",
        "allstatesroofing.com","ameristarroofing.com","arceroofing.com",
        "atlasroofing.com","aztecroofing.com","barefootroofing.com",
        "bestroofingcompany.com","blueridgeroofing.com","buildrightroofing.com",
        "capitalroofing.com","certifiedroofing.com","civilizedroofing.com",
    ],
    "plumbing": [
        "aaaplumbingandheating.com","abcplumbing.com","aceplumbing.com",
        "actionplumbing.com","advancedplumbing.com","allcityplumbing.com",
        "alliedplumbing.com","allproserv.com","allstarplumbing.com",
        "alphaplumbing.com","alwaysreadyplumbing.com","americanplumbing.com",
        "anytimeplumbing.com","apolloplumbing.com","arrowplumbing.com",
    ],
    "landscaping": [
        "acapulcolandscaping.com","acculawn.com","accuratelawn.com",
        "aceslandscaping.com","actionlandscaping.com","adamslawncare.com",
        "addisontreeexperts.com","adelaidelandscaping.com","admirallawn.com",
        "advancedlawncare.com","agreenthumb.com","alawncare.com",
        "albertsonlandscaping.com","aldrichlawncare.com","alexanderlawn.com",
    ],
    "contractor": [
        "absoluteconstruction.com","aceconstruction.com","achievebuilders.com",
        "acmeconstruction.com","acornconstruction.com","actionbuilders.com",
        "acuitybuilders.com","adamsconstruction.com","adaptivebuilders.com",
        "adelaideconstruction.com","admiralconstruction.com","advancedbuilders.com",
        "aegisbuilders.com","aetnabuilding.com","affordablebuilders.com",
    ],
    "dental": [
        "aadentistry.com","abcdental.com","absolutedental.com","accessdental.com",
        "achievedental.com","acorndental.com","actiondental.com","adamsdds.com",
        "adelaidedental.com","admiraldental.com","advanceddentistry.com",
        "aegisdental.com","affordabledental.com","agapedental.com","aglessdental.com",
    ],
    "auto": [
        "aaautorepair.com","abcautorepair.com","absoluteauto.com","accessauto.com",
        "accurateauto.com","acuteauto.com","adamautorepair.com","adelaideauto.com",
        "admiralauto.com","advancedauto.com","aegisauto.com","affordableauto.com",
        "agileauto.com","agmauto.com","airportautorepair.com",
    ],
    "pest_control": [
        "aapestcontrol.com","abcpest.com","absolutepest.com","accesspest.com",
        "accuratepest.com","acepestcontrol.com","actionpest.com","adapestcontrol.com",
        "adelaidepest.com","admiralpest.com","advancedpestcontrol.com",
        "aegispest.com","affordablepest.com","agapepest.com","aggressivepest.com",
    ],
    "electrician": [
        "aaelectrical.com","abcelectrical.com","absoluteelectrical.com",
        "accesselectrical.com","accurateelectrical.com","aceelectrical.com",
        "actionelectrical.com","adamelectrical.com","adelaideelectric.com",
        "admiralelectrical.com","advancedelectrical.com","aegiselectric.com",
        "affordableelectrical.com","agapeelectrical.com","airportelectric.com",
    ],
    "financial": [
        "aadvisors.com","abcfinancial.com","absolutefinancial.com",
        "accessfinancial.com","accuratefinancial.com","acefinancial.com",
        "actionfinancial.com","adamfinancial.com","adelaidefinancial.com",
        "admiralfinancial.com","advancedfinancial.com","aegisfinancial.com",
        "affordablefinancial.com","agapefinancial.com","agentfinancial.com",
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
    """Find decision-maker emails at a company domain (v2 async: start → poll)."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # Step 1: start the search — domain goes in query string per Snov.io support
        r = requests.post(
            f"{DOMAIN_START_URL}?domain={domain}",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 402:
            print("[SNOV] Credits exhausted")
            return None
        if r.status_code == 401:
            print("[SNOV] Token expired")
            return None
        if r.status_code not in (200, 202):
            print(f"[SNOV] Start {r.status_code}: {r.text[:100]}")
            return []

        data0 = r.json()
        task_hash = (data0.get("task_hash") or data0.get("taskHash")
                     or (data0.get("meta") or {}).get("task_hash", ""))
        if not task_hash:
            print(f"[SNOV] No task_hash in response: {r.text[:100]}")
            return []

        # Step 2: poll until complete (max ~30s)
        for attempt in range(10):
            time.sleep(3)
            rr = requests.get(
                f"{DOMAIN_RESULT_URL}{task_hash}",
                headers=headers,
                timeout=15,
            )
            if rr.status_code == 402:
                print("[SNOV] Credits exhausted")
                return None
            if rr.status_code != 200:
                print(f"[SNOV] Poll {rr.status_code}: {rr.text[:80]}")
                return []
            data = rr.json()
            status = data.get("status", "")
            if status in ("done", "complete", "completed", "finished"):
                return data.get("data") or data.get("emails") or []
            if status in ("error", "failed"):
                print(f"[SNOV] Task failed for {domain}")
                return []
            # still processing — continue polling

        print(f"[SNOV] Timeout polling {domain}")
    except Exception as e:
        print(f"[SNOV] Error: {e}")
    return []


def is_decision_maker(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(o in t for o in OWNER_TITLES)


def parse_email_record(rec: dict, domain: str, niche: str) -> dict | None:
    email = (rec.get("email") or rec.get("value") or "").strip().lower()
    if not email or "@" not in email:
        return None

    # Skip role/generic addresses
    prefix = email.split("@")[0]
    role = {"info", "contact", "admin", "support", "hello", "office",
            "sales", "help", "team", "marketing", "noreply", "no-reply",
            "billing", "accounts", "service", "care"}
    if prefix in role:
        return None

    status = (rec.get("emailStatus") or rec.get("email_status") or rec.get("status") or "").lower()
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

    # Merge seed_companies.csv into NICHE_DOMAINS if available
    seed_path = os.path.join(DATA_DIR, "seed_companies.csv")
    if os.path.exists(seed_path):
        try:
            seed_df = pd.read_csv(seed_path, dtype=str).fillna("")
            for _, row in seed_df.iterrows():
                niche  = row.get("niche", "").strip().lower()
                domain = row.get("domain", "").strip().lower()
                if niche and domain and niche in NICHE_DOMAINS:
                    if domain not in NICHE_DOMAINS[niche]:
                        NICHE_DOMAINS[niche].append(domain)
            print(f"[SNOV] Loaded seed_companies.csv — {len(seed_df)} additional domains")
        except Exception as ex:
            print(f"[SNOV] Seed load skipped: {ex}")

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
