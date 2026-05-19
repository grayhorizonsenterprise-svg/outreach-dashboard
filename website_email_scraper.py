"""
website_email_scraper.py - Gray Horizons Enterprise
Scrapes email addresses directly from company websites.
No API key needed — finds mailto: links and plain email patterns
on contact/about pages. Works on any domain already in prospects_raw.csv
that has a website but no email yet.
"""

import requests
import pandas as pd
import os
import sys
import re
import time
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

EMAIL_RE = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

ROLE_PREFIXES = {
    "info", "contact", "admin", "support", "hello", "office",
    "sales", "help", "team", "marketing", "noreply", "no-reply",
    "billing", "accounts", "service", "care", "enquiries", "enquiry",
    "webmaster", "postmaster", "privacy", "legal", "press", "media",
}

SKIP_DOMAINS = {
    "example.com", "sentry.io", "gmail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "wixpress.com", "squarespace.com", "godaddy.com",
    "wordpress.com", "google.com", "facebook.com", "instagram.com",
    "twitter.com", "linkedin.com", "yelp.com", "bbb.org",
}

CONTACT_PATHS = ["", "/contact", "/contact-us", "/about", "/about-us", "/reach-us"]


def extract_emails(html: str, site_domain: str) -> list:
    """Pull all non-role emails that belong to the site's own domain."""
    found = set()
    # mailto: links first (most reliable)
    for m in re.finditer(r'mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', html):
        found.add(m.group(1).lower())
    # plain text email pattern
    for m in EMAIL_RE.finditer(html):
        found.add(m.group(0).lower())

    results = []
    for email in found:
        prefix = email.split("@")[0]
        domain = email.split("@")[-1]
        if prefix in ROLE_PREFIXES:
            continue
        if domain in SKIP_DOMAINS:
            continue
        # Prefer emails that match the site domain exactly
        if domain == site_domain or site_domain.endswith("." + domain) or domain.endswith("." + site_domain):
            results.insert(0, email)  # site-domain emails first
        else:
            results.append(email)
    return results[:3]


def scrape_website(website: str) -> str:
    """Try homepage + contact page, return first usable email found."""
    base = website.rstrip("/").lower()
    if not base.startswith("http"):
        base = "https://" + base
    site_domain = base.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    for path in CONTACT_PATHS:
        url = base + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if r.status_code != 200:
                continue
            emails = extract_emails(r.text, site_domain)
            if emails:
                return emails[0]
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 1.2))
    return ""


def run(max_enrich: int = 300):
    print("[WEBSITE] Scraping emails from company websites...")

    if not os.path.exists(OUT_FILE):
        print("[WEBSITE] No prospects_raw.csv — skipping")
        return

    try:
        df = pd.read_csv(OUT_FILE, dtype=str).fillna("")
    except Exception as e:
        print(f"[WEBSITE] CSV load error: {e}")
        return

    # Only rows that have a website but no email
    mask = (df.get("website", pd.Series(dtype=str)).str.strip() != "") & \
           (df.get("email",   pd.Series(dtype=str)).str.strip() == "")
    targets = df[mask].copy()
    print(f"  {len(targets)} rows have website but no email")

    if targets.empty:
        print("[WEBSITE] Nothing to enrich")
        return

    # Load already-contacted emails from DB to skip
    existing_emails: set = set()
    existing_domains: set = set()
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, sslmode="require")
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (e,) in cur.fetchall():
                    if e:
                        em = str(e).strip().lower()
                        existing_emails.add(em)
                        if "@" in em:
                            existing_domains.add(em.split("@")[-1])
            conn.close()
        except Exception as ex:
            print(f"  DB load skipped: {ex}")

    enriched = 0
    indices = list(targets.index)
    random.shuffle(indices)

    for idx in indices:
        if enriched >= max_enrich:
            break
        row = df.loc[idx]
        website = str(row.get("website", "")).strip()
        if not website:
            continue

        site_domain = website.lower().replace("https://","").replace("http://","").replace("www.","").split("/")[0]
        if site_domain in existing_domains:
            continue

        print(f"  [SCRAPE] {website}")
        email = scrape_website(website)
        if not email:
            print(f"    no email found")
            continue

        email_domain = email.split("@")[-1]
        if email in existing_emails or email_domain in existing_domains:
            print(f"    [SKIP] {email} already contacted")
            continue

        df.at[idx, "email"] = email
        existing_emails.add(email)
        existing_domains.add(email_domain)
        enriched += 1
        print(f"    [+] {email}")
        time.sleep(random.uniform(1.0, 2.5))

    df.to_csv(OUT_FILE, index=False)
    print(f"\n[WEBSITE] Done. Enriched {enriched} companies with emails from their own websites.")


if __name__ == "__main__":
    run()
