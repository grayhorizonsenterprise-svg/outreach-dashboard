"""
prospect_enricher.py — Gray Horizons Enterprise
Parallel email enrichment — 8 workers, 6s timeout, smart path selection.
Skips any prospect that already has a valid email from prospect_finder.
Saves progress every 10 records.
"""

import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import time
import random
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

WORKERS = 8   # parallel scrapers
TIMEOUT = 6   # seconds per request

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "msn.com", "live.com", "me.com",
    "protonmail.com", "mail.com", "ymail.com",
}

JUNK_PATTERNS = [
    "example", "test@", "noreply", "no-reply", "donotreply",
    "sentry", "wixpress", "pinterest", "youtube", "twitter",
    "linkedin", "facebook", "instagram",
    "first.last", "name@email", "user@email", "user@domain",
    "your@email", "email@email", "@email.com", "info@example",
    ".png", ".jpg", ".webp", ".svg", ".gif",
    "domain.com", "yourname", "company.com",
    "placeholder", "sample@", "demo@", "fake@", "null@",
    "@test.", "@example.", "@mailinator.",
]

# Only the 5 most common paths — don't brute-force 20+
CONTACT_PATHS = [
    "/contact", "/contact-us", "/about", "/about-us", "/team",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def get_domain(url: str) -> str:
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""


def is_valid_email(email: str, site_url: str = "") -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if any(p in e for p in JUNK_PATTERNS):
        return False
    email_domain = e.split("@")[-1]
    if email_domain in PERSONAL_DOMAINS:
        return False
    return True


def score_email(email: str, site_url: str) -> int:
    e    = email.lower()
    site = get_domain(site_url)
    score = 0
    email_domain = e.split("@")[-1]
    if site and (email_domain in site or site in email_domain):
        score += 100
    for prefix in ["info", "contact", "hello", "office", "admin", "manager", "team"]:
        if e.startswith(prefix + "@"):
            score += 10
    if re.match(r"^[a-z]+\.[a-z]+@", e):
        score += 5
    return score


def fetch(url: str) -> str:
    """Single fetch, no retries — caller handles fallback."""
    try:
        resp = requests.get(
            url, headers=get_headers(), timeout=TIMEOUT,
            verify=False, allow_redirects=True
        )
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def extract_emails(html: str, site_url: str) -> list:
    raw = EMAIL_REGEX.findall(html)
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr:
                    raw.append(addr)
    except Exception:
        pass
    valid = [e for e in raw if is_valid_email(e, site_url)]
    deduped = list(dict.fromkeys(e.lower() for e in valid))
    return sorted(deduped, key=lambda e: score_email(e, site_url), reverse=True)


def enrich_prospect(site: str, contact_page: str = "") -> str:
    """Fast enrichment: homepage → contact link on page → known contact_page → 5 common paths."""
    base = site.rstrip("/")
    candidates = []

    # 1. Homepage
    html = fetch(base)
    if html:
        candidates += extract_emails(html, site)
        if not candidates:
            # Follow first contact-like link found on homepage
            try:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].lower()
                    if any(k in href for k in ["contact", "about", "team", "reach"]):
                        full = href if href.startswith("http") else urllib.parse.urljoin(base, href)
                        if get_domain(full) == get_domain(site):
                            linked = fetch(full)
                            if linked:
                                candidates += extract_emails(linked, site)
                            break
            except Exception:
                pass

    # 2. contact_page from prospect_finder if we still have nothing
    if not candidates and contact_page and contact_page not in ("", "nan", "None"):
        html = fetch(contact_page)
        if html:
            candidates += extract_emails(html, site)

    # 3. Brute-force the 5 common paths as last resort
    if not candidates:
        for path in CONTACT_PATHS:
            html = fetch(base + path)
            if html:
                found = extract_emails(html, site)
                if found:
                    candidates += found
                    break

    if not candidates:
        return ""

    seen = set()
    deduped = []
    for e in candidates:
        if e not in seen:
            seen.add(e)
            deduped.append(e)

    return sorted(deduped, key=lambda e: score_email(e, site), reverse=True)[0]


def process_row(args):
    """Worker function — enriches a single row. Returns (index, email, lead_type)."""
    i, row = args
    existing = str(row.get("email", "")).strip()
    site     = str(row.get("website", "")).strip()

    # Already has a valid email — nothing to do
    if existing not in ("", "nan", "None") and is_valid_email(existing, site):
        return (i, existing, "READY")

    if site in ("", "nan", "None"):
        return (i, "", "NO_DATA")

    contact_page = str(row.get("contact_page_url", "")).strip()
    email = enrich_prospect(site, contact_page)

    if email:
        return (i, email, "READY")
    return (i, "", "WEBSITE_ONLY")


def run():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found — skipping enrichment.")
        return

    df = pd.read_csv(INPUT_FILE)

    for col in ["email", "website", "lead_type", "contact_page_url"]:
        if col not in df.columns:
            df[col] = ""

    total = len(df)

    # Split into already-done and needs-work
    needs_work = [(i, row) for i, row in df.iterrows()
                  if str(row.get("email", "")).strip() in ("", "nan", "None")
                  or not is_valid_email(str(row.get("email", "")), str(row.get("website", "")))]

    already_ready = total - len(needs_work)
    print(f"[ENRICH] {total} prospects — {already_ready} already have emails, {len(needs_work)} need scraping")
    print(f"[ENRICH] Running {WORKERS} parallel workers...\n")

    enriched = 0
    save_counter = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(process_row, args): args[0] for args in needs_work}

        for future in as_completed(futures):
            idx = futures[future]
            try:
                i, email, lead_type = future.result()
                df.at[i, "email"]     = email
                df.at[i, "lead_type"] = lead_type
                company = str(df.at[i, "company"])[:30]
                if lead_type == "READY":
                    print(f"  [OK] {company} → {email}")
                    enriched += 1
                else:
                    print(f"  [--] {company} → no email")

                save_counter += 1
                if save_counter % 10 == 0:
                    df.to_csv(INPUT_FILE, index=False)

            except Exception as exc:
                print(f"  [ERR] row {idx}: {exc}")

    df.to_csv(INPUT_FILE, index=False)
    ready = len(df[df["lead_type"] == "READY"])
    print(f"\n[DONE] {ready}/{total} leads have verified emails (+{enriched} newly found)")


if __name__ == "__main__":
    run()
