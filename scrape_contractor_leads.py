"""
scrape_contractor_leads.py — Gray Horizons Enterprise
Scrapes CA contractor business websites for email addresses.

Sources: DuckDuckGo text search -> business websites -> email regex extraction.
No external API keys required. Uses existing duckduckgo_search package.

Outputs to: contractor_prospects.csv (niche column feeds send_contractor_outreach.py)

Schedule: run daily via run_all_engines.py Phase 1 to refill the lead queue.

Usage:
  python scrape_contractor_leads.py --dry-run   (search only, no CSV write)
  python scrape_contractor_leads.py             (full run, appends new leads)
"""

import os
import sys
import re
import csv
import time
import random
import argparse
import requests
from pathlib import Path
from datetime import datetime
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = DATA_DIR / "contractor_prospects.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "live.com", "msn.com", "me.com", "mac.com",
    "sampleemail.com", "example.com", "test.com", "domain.com", "email.com", "mysite.com",
    "sendgrid.com", "mailchimp.com", "constantcontact.com",
    "wixsite.com", "squarespace.com", "godaddy.com", "weebly.com",
    "wordpress.com", "yelp.com", "bbb.org", "angi.com",
    "homeadvisor.com", "thumbtack.com", "houzz.com", "angieslist.com",
    "kayak.com", "expedia.com", "booking.com", "tripadvisor.com",
    "justwatch.com", "netflix.com", "amazon.com", "google.com",
    "sentry.io", "bugsnag.com", "datadog.com", "newrelic.com",
    "todayshomeowner.com", "thisoldhouse.com", "hgtv.com",
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "monster.com",
    "air.org", "aircareers.org", "hvacinstitution.com",
    "notification.com", "mailer.com", "bounce.com",
    "2x.png", "1x.png", "notification",
}

JUNK_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "postmaster",
    "mailer", "bounce", "unsubscribe", "webmaster", "support", "help",
    "news", "newsletter", "marketing", "careers", "jobs", "hr",
    "recruitment", "hiring", "feedback", "privacy", "legal",
    "abuse", "report", "admin", "info", "hello", "contact",
    "team", "office",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Niche -> list of DDG search queries targeting real CA business websites
SEARCHES = {
    "hvac": [
        "heating ventilation cooling contractor \"Los Angeles\" California contact email -jobs -careers",
        "HVAC repair company \"San Diego\" California email contact -jobs",
        "HVAC contractor \"Sacramento\" California contact email -careers",
        "HVAC installation service \"Orange County\" CA email -jobs",
        "heating cooling repair company \"Riverside\" California email",
        "HVAC contractor \"Fresno\" California contact email",
        "HVAC service company \"San Jose\" California email",
        "heating cooling company \"Anaheim\" California email contact",
        "HVAC repair service \"Long Beach\" California email",
        "heating cooling contractor \"Bakersfield\" California email contact",
    ],
    "roofing": [
        "roofing contractor \"Los Angeles\" California email contact -jobs",
        "roofing company \"San Diego\" California email -careers",
        "roof repair contractor \"Sacramento\" California email contact",
        "roofing service \"Orange County\" CA email contact",
        "roofing contractor \"Riverside\" California email",
        "roofing company \"Fresno\" California email contact",
        "roofing contractor \"San Jose\" California email",
        "roof replacement company \"Bakersfield\" California email",
        "roofing contractor \"Stockton\" California email contact",
        "roofing company \"Anaheim\" California email",
    ],
    "solar": [
        "solar panel installation company \"Los Angeles\" California email",
        "solar contractor \"San Diego\" California email contact",
        "solar panel installer \"Sacramento\" California email",
        "solar company \"Orange County\" California email contact",
        "solar installation \"Riverside\" California email",
        "solar energy company \"Fresno\" California email",
        "solar installer \"San Jose\" California email contact",
        "solar panels company \"Bakersfield\" California email",
    ],
    "plumbing": [
        "plumbing contractor \"Los Angeles\" California email contact -jobs",
        "plumber \"San Diego\" California email contact",
        "plumbing company \"Sacramento\" California email",
        "plumbing service \"Orange County\" California email contact",
        "plumber \"Riverside\" California email",
        "plumbing company \"Fresno\" California email contact",
        "plumbing contractor \"San Jose\" California email",
    ],
    "dental": [
        "dental office \"Los Angeles\" California email contact -jobs",
        "dentist practice \"San Diego\" California email contact",
        "dental clinic \"Sacramento\" California email contact",
        "dental office \"Orange County\" California email -careers",
        "dentist \"Riverside\" California email contact",
        "dental practice \"Fresno\" California email",
        "dentist office \"San Jose\" California email contact",
        "dental clinic \"Bakersfield\" California email",
        "dental office \"Long Beach\" California email contact",
        "dentist \"Anaheim\" California email contact",
    ],
}

TARGET_PER_NICHE = 25

SKIP_DOMAINS_IN_URL = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "yelp.com", "yellowpages.com", "bbb.org", "angi.com", "homeadvisor.com",
    "thumbtack.com", "houzz.com", "nextdoor.com", "google.com", "youtube.com",
    "indeed.com", "glassdoor.com", "reddit.com", "pinterest.com",
    "kayak.com", "expedia.com", "booking.com", "tripadvisor.com",
    "justwatch.com", "netflix.com", "amazon.com", "imdb.com",
    "sentry.io", "bugsnag.com", "datadog.com", "newrelic.com",
    "todayshomeowner.com", "thisoldhouse.com", "hgtv.com", "familyhandyman.com",
    "air.org", "aircareers.org", "ziprecruiter.com", "monster.com",
    "bing.com", "yahoo.com", "duckduckgo.com", "ask.com",
    "clutch.co", "bark.com", "porch.com", "fixr.com",
    "energystar.gov", "energy.gov", "epa.gov", ".gov/",
}


def _is_valid_email(email: str) -> bool:
    email = email.lower().strip()
    if "@" not in email:
        return False
    # Reject URL-encoded entities (u003c = <, u002f = /, etc.)
    if "u003" in email or "u002" in email or "u00" in email:
        return False
    # Reject emails that look like image filenames or paths
    if any(ext in email for ext in (".png", ".jpg", ".gif", ".svg", ".css", ".js", ".webp", ".ico", ".ttf", ".woff")):
        return False
    # Reject very short local parts (e.g. a@b.com)
    if len(email.split("@")[0]) < 2:
        return False
    domain = email.split("@")[-1]
    prefix = email.split("@")[0]
    if domain in JUNK_DOMAINS:
        return False
    # Reject any domain that is in the junk domain list by substring
    for junk_d in JUNK_DOMAINS:
        if email.endswith("@" + junk_d) or ("." + junk_d) in domain:
            return False
    for junk in JUNK_PREFIXES:
        if prefix == junk or prefix.startswith(junk + ".") or prefix.startswith(junk + "+"):
            return False
    if len(email) < 8 or len(email) > 80:
        return False
    if ".." in email or email.startswith(".") or email.endswith("."):
        return False
    # Must have a real TLD (2+ chars)
    parts = domain.split(".")
    if len(parts) < 2 or len(parts[-1]) < 2:
        return False
    # Reject numeric-only local parts (sentry IDs, tracking hashes)
    if re.match(r"^[0-9a-f]{16,}$", prefix):
        return False
    return True


def _scrape_emails_from_url(url: str) -> list:
    emails = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            if "text" in ct or "html" in ct:
                found = EMAIL_RE.findall(r.text)
                for e in found:
                    e = e.lower().strip().rstrip(".,;:\"'")
                    if _is_valid_email(e) and e not in emails:
                        emails.append(e)
    except Exception:
        pass
    return emails


def _load_existing_emails() -> set:
    if not CSV_PATH.exists():
        return set()
    existing = set()
    try:
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                e = row.get("email", "").strip().lower()
                if e:
                    existing.add(e)
    except Exception:
        pass
    return existing


def _append_to_csv(rows: list):
    fieldnames = ["email", "niche", "status", "source", "scraped_at"]
    file_exists = CSV_PATH.exists() and CSV_PATH.stat().st_size > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def run(dry_run: bool = False) -> int:
    existing = _load_existing_emails()
    print(f"[SCRAPER] Starting — {len(existing)} emails already in queue")

    total_new = 0
    new_rows = []

    for niche, queries in SEARCHES.items():
        print(f"\n[{niche.upper()}] Scanning {len(queries)} queries (target: {TARGET_PER_NICHE})")
        niche_emails = set()

        for query in queries:
            if len(niche_emails) >= TARGET_PER_NICHE:
                break

            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=8))

                for result in results:
                    url = result.get("href", "")
                    if not url:
                        continue
                    # Skip directories and social media
                    if any(d in url for d in SKIP_DOMAINS_IN_URL):
                        continue

                    emails = _scrape_emails_from_url(url)

                    for email in emails:
                        if email not in existing and email not in niche_emails:
                            niche_emails.add(email)
                            print(f"  + {email}")
                            if not dry_run:
                                new_rows.append({
                                    "email": email,
                                    "niche": niche,
                                    "status": "pending",
                                    "source": url[:100],
                                    "scraped_at": datetime.now().strftime("%Y-%m-%d"),
                                })

                    time.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                print(f"  [WARN] {e}")
                time.sleep(6)

        print(f"[{niche.upper()}] Found {len(niche_emails)} new emails")
        total_new += len(niche_emails)
        existing.update(niche_emails)

    if not dry_run and new_rows:
        _append_to_csv(new_rows)
        print(f"\n[SCRAPER] Done — {len(new_rows)} new leads added to {CSV_PATH.name}")
    elif dry_run:
        print(f"\n[DRY RUN] Would add {total_new} leads. Remove --dry-run to save.")
    else:
        print(f"\n[SCRAPER] Done — no new leads found this run.")

    return total_new


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("\n=== GHE Contractor Lead Scraper ===")
    print("Target: CA HVAC / Roofing / Solar / Plumbing\n")
    run(dry_run=args.dry_run)
