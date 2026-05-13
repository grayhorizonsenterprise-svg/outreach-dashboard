"""
hunter_scraper.py — Gray Horizons Enterprise
Hunter.io API — finds verified decision-maker emails by company domain.
Free tier: 50 searches/month. Paid: $49/month for 1,000.
Gets direct emails, not info@ guesses.

Get free key at hunter.io → Settings → API
Add HUNTER_API_KEY to Railway env vars.
"""

import requests
import pandas as pd
import time
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
HUNTER_KEY  = os.getenv("HUNTER_API_KEY", "")
DOMAIN_URL  = "https://api.hunter.io/v2/domain-search"
FIND_URL    = "https://api.hunter.io/v2/email-finder"


def search_domain(domain: str) -> list:
    """Get all emails found for a domain."""
    if not HUNTER_KEY or not domain:
        return []
    try:
        r = requests.get(
            DOMAIN_URL,
            params={"domain": domain, "api_key": HUNTER_KEY, "limit": 5},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            return data.get("emails", [])
        elif r.status_code == 429:
            print("[HUNTER] Rate limit — sleeping 60s")
            time.sleep(60)
    except Exception as e:
        print(f"[HUNTER] Error for {domain}: {e}")
    return []


def get_best_email(emails: list) -> tuple:
    """Pick the highest confidence email, prefer owners/managers."""
    if not emails:
        return "", ""

    priority_titles = ["owner", "founder", "ceo", "president", "director", "manager", "principal"]

    for email_data in emails:
        position = (email_data.get("position") or "").lower()
        if any(t in position for t in priority_titles):
            return email_data.get("value", ""), email_data.get("first_name", "") + " " + email_data.get("last_name", "")

    # Fall back to highest confidence
    best = max(emails, key=lambda e: e.get("confidence", 0))
    return best.get("value", ""), best.get("first_name", "") + " " + best.get("last_name", "")


def run():
    if not HUNTER_KEY:
        print("[HUNTER] No HUNTER_API_KEY set — get free key at hunter.io")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"[HUNTER] {INPUT_FILE} not found")
        return

    df = pd.read_csv(INPUT_FILE).fillna("")

    # Normalise: merge "domain" column into "website" if website is missing
    if "domain" in df.columns:
        mask = (df.get("website", pd.Series([""] * len(df))).str.strip() == "") & (df["domain"].str.strip() != "")
        df.loc[mask, "website"] = df.loc[mask, "domain"]

    # Only enrich leads that have websites but no email
    needs_email = df[
        (df["email"].str.strip() == "") &
        (df["website"].str.strip() != "")
    ].copy()

    print(f"[HUNTER] {len(needs_email)} leads need email enrichment")

    if len(needs_email) == 0:
        print("[HUNTER] Nothing to enrich")
        return

    import urllib.parse
    enriched = 0

    # Free tier = 25/month. Cap at 20/run so we never accidentally blow the limit.
    monthly_limit = int(os.getenv("HUNTER_MONTHLY_LIMIT", "25"))
    per_run_cap   = max(1, monthly_limit // 2)
    for i, row in needs_email.head(per_run_cap).iterrows():
        site = str(row["website"]).strip().rstrip("/")
        try:
            domain = urllib.parse.urlparse(site).netloc.replace("www.", "")
        except Exception:
            continue

        if not domain or "." not in domain:
            continue

        emails = search_domain(domain)
        email, name = get_best_email(emails)

        if email:
            df.at[i, "email"] = email.lower()
            if name.strip() and "contact_name" in df.columns:
                df.at[i, "contact_name"] = name.strip()
            df.at[i, "lead_type"] = "READY"
            print(f"  [OK] {str(row['company'])[:30]:30s} → {email}")
            enriched += 1
        else:
            print(f"  [--] {str(row['company'])[:30]:30s} → no email found")

        time.sleep(1.2)

    df.to_csv(INPUT_FILE, index=False)
    print(f"\n[HUNTER] Done — {enriched} emails enriched")


if __name__ == "__main__":
    run()
