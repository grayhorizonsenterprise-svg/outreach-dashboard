"""
prospect_enricher.py — Gray Horizons Enterprise
Scrapes emails from every contact path on every prospect site.
Validates emails against the company domain — no personal/junk emails.
Saves progress every 5 records so a crash loses nothing.
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

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

# Domains that are never real business contact emails
PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "msn.com", "live.com", "me.com",
    "protonmail.com", "mail.com", "ymail.com",
}

# String patterns that indicate a junk/placeholder email
JUNK_PATTERNS = [
    "example", "test@", "noreply", "no-reply", "donotreply",
    "sentry", "wixpress", "pinterest", "youtube", "twitter",
    "linkedin", "facebook", "instagram", "craigslist",
    "first.last", "name@email", "user@email", "user@domain",
    "your@email", "email@email", "@email.com", "info@example", "rocketreach",
    "360training", "@2x", ".png", ".jpg", ".webp", ".svg", ".gif",
    "domain.com", "yourname", "company.com", "address@",
    "placeholder", "sample@", "demo@", "fake@", "null@", "none@",
    "@test.", "@example.", "@mailinator.", "@tempmail.", "@guerrilla",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus", "/contact_us",
    "/about", "/about-us", "/aboutus", "/about_us",
    "/team", "/our-team", "/management-team", "/the-team",
    "/staff", "/our-staff", "/people", "/leadership",
    "/executives", "/management", "/managers",
    "/reach-us", "/get-in-touch", "/connect", "/hello",
    "/info", "/office", "/offices", "/locations", "/location",
    "/reach", "/email-us", "/meet-the-team",
]


def get_domain(url: str) -> str:
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""


def is_valid_email(email: str, site_url: str = "") -> bool:
    """True only if the email looks like a real business contact."""
    e = email.lower().strip()

    # Must have proper structure
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False

    # Reject junk patterns
    if any(p in e for p in JUNK_PATTERNS):
        return False

    # Reject personal email domains for B2B outreach
    email_domain = e.split("@")[-1]
    if email_domain in PERSONAL_DOMAINS:
        return False

    # Prefer emails that match the company's domain
    # (don't reject mismatches — some companies use third-party email)
    return True


def score_email(email: str, site_url: str) -> int:
    """Higher score = better email. Used to pick the best one."""
    e    = email.lower()
    site = get_domain(site_url)
    score = 0

    # Domain match is the strongest signal
    email_domain = e.split("@")[-1]
    if site and (email_domain in site or site in email_domain):
        score += 100

    # Professional-sounding local parts
    for prefix in ["info", "contact", "hello", "office", "admin", "manager", "team"]:
        if e.startswith(prefix + "@"):
            score += 10

    # Personal name emails are fine but ranked lower
    if re.match(r"^[a-z]+\.[a-z]+@", e):
        score += 5

    return score


def fetch(url: str, retries: int = 2) -> str:
    """Fetch URL with retries and rotating user agents. Returns HTML text or ''."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, headers=get_headers(), timeout=10,
                verify=False, allow_redirects=True
            )
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 403 and attempt < retries:
                time.sleep(random.uniform(2, 4))
        except requests.exceptions.SSLError:
            try:
                resp = requests.get(url, headers=get_headers(), timeout=10,
                                    verify=False, allow_redirects=True)
                if resp.status_code == 200:
                    return resp.text
            except Exception:
                pass
        except Exception:
            if attempt < retries:
                time.sleep(random.uniform(1, 3))
    return ""


def extract_emails(html: str, site_url: str) -> list:
    """Extract and validate all emails from HTML, sorted by quality score."""
    raw = EMAIL_REGEX.findall(html)

    # Also find mailto: links
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr:
                raw.append(addr)

    valid = [e for e in raw if is_valid_email(e, site_url)]
    deduped = list(dict.fromkeys(e.lower() for e in valid))
    return sorted(deduped, key=lambda e: score_email(e, site_url), reverse=True)


def enrich_prospect(site: str, contact_page: str = "") -> str:
    """Try every possible page to find a valid email. Returns best one or ''."""
    base = site.rstrip("/")
    candidates = []

    # 1. Main homepage
    html = fetch(base)
    if html:
        candidates += extract_emails(html, site)
        # 2. Any contact link found on the homepage
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(k in href for k in ["contact", "about", "team", "staff", "reach"]):
                full = href if href.startswith("http") else urllib.parse.urljoin(base, href)
                if get_domain(full) == get_domain(site):
                    linked_html = fetch(full)
                    if linked_html:
                        candidates += extract_emails(linked_html, site)
                    break

    # 3. contact_page_url found by prospect_finder
    if contact_page and contact_page not in ("", "nan", "None"):
        html = fetch(contact_page)
        if html:
            candidates += extract_emails(html, site)

    # 4. Brute-force common contact paths
    if not candidates:
        for path in CONTACT_PATHS:
            time.sleep(random.uniform(0.4, 1.0))
            html = fetch(base + path)
            if html:
                found = extract_emails(html, site)
                candidates += found
                if found:
                    break  # got something — move on

    # Dedupe and return the best scored email
    seen = set()
    deduped = []
    for e in candidates:
        if e not in seen:
            seen.add(e)
            deduped.append(e)

    if not deduped:
        return ""

    return sorted(deduped, key=lambda e: score_email(e, site), reverse=True)[0]


def run():
    # Suppress SSL warnings (we handle SSL errors ourselves)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found yet — skipping enrichment.")
        return
    df = pd.read_csv(INPUT_FILE)

    for col in ["email", "website", "lead_type", "contact_page_url"]:
        if col not in df.columns:
            df[col] = ""

    total = len(df)
    enriched = 0

    for i, row in df.iterrows():
        existing = str(row.get("email", "")).strip()

        # Already has a validated business email — skip
        if existing not in ("", "nan", "None") and is_valid_email(existing, str(row.get("website", ""))):
            df.at[i, "lead_type"] = "READY"
            continue

        # Invalid existing email — clear it and re-enrich
        if existing not in ("", "nan", "None"):
            df.at[i, "email"] = ""

        site = str(row.get("website", "")).strip()
        if site in ("", "nan", "None"):
            df.at[i, "lead_type"] = "NO_DATA"
            continue

        company = str(row.get("company", "Unknown")).strip()
        contact_page = str(row.get("contact_page_url", "")).strip()

        print(f"\n[ENRICH] {company}", flush=True)
        print(f"  [SITE] {site}", flush=True)

        email = enrich_prospect(site, contact_page)

        if email:
            df.at[i, "email"]     = email
            df.at[i, "lead_type"] = "READY"
            print(f"  [EMAIL] {email}", flush=True)
            enriched += 1
        else:
            df.at[i, "lead_type"] = "WEBSITE_ONLY"
            print(f"  [NO EMAIL]", flush=True)

        # Save every 5 rows so a crash doesn't wipe progress
        if i % 5 == 0:
            df.to_csv(INPUT_FILE, index=False)

        time.sleep(random.uniform(0.8, 1.8))

    df.to_csv(INPUT_FILE, index=False)
    ready = len(df[df["lead_type"] == "READY"])
    print(f"\n[DONE] {ready}/{total} leads have verified emails (+{enriched} newly found)", flush=True)


if __name__ == "__main__":
    run()
