"""
linkedin_scraper.py — Gray Horizons Enterprise
LinkedIn people search using Playwright browser session + li_at cookie auth.
Targets business owners and decision-makers by job title.
Zero API cost — uses your own LinkedIn session.

Requires Railway env var: LINKEDIN_LI_AT=<your li_at cookie value>
"""

import pandas as pd
import re
import time
import random
import os
import sys
import urllib.parse
from bs4 import BeautifulSoup
import requests
from ddgs import DDGS

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

LI_AT = os.getenv("LINKEDIN_LI_AT", "").strip()

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "msn.com", "live.com",
}
JUNK_EMAIL_PATTERNS = [
    "noreply", "no-reply", "donotreply", "sentry", "wixpress",
    "example", "test@", "domain.com", "placeholder",
]

# Decision-maker title searches per niche
TITLE_SEARCHES = [
    ("hoa",          "HOA property manager"),
    ("hoa",          "community association manager"),
    ("hoa",          "HOA management company owner"),
    ("hvac",         "HVAC company owner"),
    ("hvac",         "HVAC business owner"),
    ("dental",       "dental practice owner"),
    ("dental",       "dentist owner"),
    ("plumbing",     "plumbing company owner"),
    ("contractor",   "general contractor owner"),
    ("contractor",   "construction company owner"),
    ("landscaping",  "landscaping business owner"),
    ("roofing",      "roofing company owner"),
    ("auto",         "auto repair shop owner"),
    ("chiropractic", "chiropractor owner"),
    ("realestate",   "real estate broker owner"),
    ("salon",        "salon owner"),
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def extract_domain(url):
    if not url:
        return ""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "").split(":")[0]
    except Exception:
        return ""


def is_valid_email(email, site_url=""):
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if any(p in e for p in JUNK_EMAIL_PATTERNS):
        return False
    if e.split("@")[-1] in PERSONAL_DOMAINS:
        return False
    return True


def find_company_email(company_name, location):
    """Search DuckDuckGo for the company website then scrape for email."""
    if not company_name or len(company_name) < 3:
        return "", ""

    query   = f'"{company_name}" {location} contact email'
    website = ""
    email   = ""

    skip = {"linkedin.com", "facebook.com", "yelp.com", "yellowpages.com", "indeed.com"}

    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=6):
                url    = r.get("href", "")
                domain = extract_domain(url)
                if domain and domain not in skip:
                    website = url
                    break
    except Exception:
        pass

    if not website:
        return "", ""

    try:
        resp = requests.get(
            website,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=7,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    addr = a["href"][7:].split("?")[0].strip()
                    if is_valid_email(addr, website):
                        return website, addr
            for e in EMAIL_REGEX.findall(resp.text):
                if is_valid_email(e, website):
                    return website, e
    except Exception:
        pass

    domain = extract_domain(website)
    if domain and "." in domain:
        guessed = f"info@{domain}"
        if is_valid_email(guessed):
            return website, guessed

    return website, ""


def scrape_with_playwright(searches_per_run, max_per_search):
    """Use Playwright browser to scrape LinkedIn search results."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[LI] Playwright not installed — skipping LinkedIn scrape.")
        return []

    results = []

    combos = random.sample(TITLE_SEARCHES, min(searches_per_run, len(TITLE_SEARCHES)))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--single-process",
                "--no-zygote",
                "--disable-extensions",
                "--disable-background-networking",
            ],
        )

        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )

        # Inject li_at session cookie — this is the auth
        context.add_cookies([{
            "name":     "li_at",
            "value":    LI_AT,
            "domain":   ".linkedin.com",
            "path":     "/",
            "secure":   True,
            "httpOnly": True,
            "sameSite": "None",
        }])

        page = context.new_page()

        # Verify session is active
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            if "authwall" in page.url or "login" in page.url:
                print("[LI] Cookie expired or invalid — session redirected to login.")
                browser.close()
                return []
            print("[LI] Session active — logged in successfully.")
        except Exception as e:
            print(f"[LI] Feed load error: {e}")
            browser.close()
            return []

        for niche, keywords in combos:
            print(f"  [LI:{niche.upper()}] Searching '{keywords}'")
            search_url = (
                "https://www.linkedin.com/search/results/people/?"
                + urllib.parse.urlencode({
                    "keywords": keywords,
                    "origin":   "GLOBAL_SEARCH_HEADER",
                })
            )

            try:
                page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(random.uniform(3, 5))

                # Check for auth wall
                if "authwall" in page.url or "login" in page.url:
                    print("[LI] Auth wall hit — cookie may have expired.")
                    break

                # Extract result cards from rendered HTML
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # LinkedIn result cards
                cards = (
                    soup.find_all("li", class_=re.compile(r"reusable-search__result-container", re.I))
                    or soup.find_all("div", class_=re.compile(r"entity-result", re.I))
                    or soup.find_all("li", class_=re.compile(r"search-result", re.I))
                )

                found = 0
                for card in cards[:max_per_search]:
                    name    = ""
                    title   = ""
                    company = ""
                    location = ""

                    # Name
                    name_tag = (
                        card.find(class_=re.compile(r"entity-result__title-text|actor-name|search-result__title", re.I))
                        or card.find("span", attrs={"aria-hidden": "true"})
                    )
                    if name_tag:
                        name = name_tag.get_text(strip=True)

                    # Title / headline
                    sub = card.find(class_=re.compile(r"entity-result__primary-subtitle|subline-level-1", re.I))
                    if sub:
                        title = sub.get_text(strip=True)

                    # Company (from secondary subtitle or parsed from title)
                    sec = card.find(class_=re.compile(r"entity-result__secondary-subtitle|subline-level-2", re.I))
                    if sec:
                        company = sec.get_text(strip=True)
                    if not company and " at " in title:
                        company = title.split(" at ", 1)[-1].strip()

                    # Location
                    loc_tag = card.find(class_=re.compile(r"entity-result__location|location", re.I))
                    if loc_tag:
                        location = loc_tag.get_text(strip=True)

                    if not name or not company or len(company) < 3:
                        continue

                    results.append({
                        "name":     name,
                        "headline": title,
                        "company":  company,
                        "location": location,
                        "niche":    niche,
                    })
                    found += 1

                print(f"    {found} profiles extracted")

            except PWTimeout:
                print(f"  [LI] Timeout on '{keywords}' — continuing")
            except Exception as exc:
                print(f"  [LI] Error on '{keywords}': {exc}")

            # Human-like delay between searches
            time.sleep(random.uniform(5, 9))

        browser.close()

    return results


def run():
    if not LI_AT:
        print("[LI] LINKEDIN_LI_AT env var not set — skipping LinkedIn scrape.")
        print("[LI] Add LINKEDIN_LI_AT=<li_at cookie value> to Railway env vars.")
        return

    seen_domains = set()
    seen_emails  = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            df_ex = pd.read_csv(OUTPUT_FILE).fillna("")
            for url in df_ex.get("website", pd.Series(dtype=str)).tolist():
                d = extract_domain(str(url))
                if d:
                    seen_domains.add(d)
            for e in df_ex.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
        except Exception:
            pass

    if os.path.exists(OUTREACH_FILE):
        try:
            oq = pd.read_csv(OUTREACH_FILE).fillna("")
            for e in oq.get("email", pd.Series(dtype=str)).tolist():
                e = str(e).strip().lower()
                if e and e not in ("", "nan", "none"):
                    seen_emails.add(e)
        except Exception:
            pass

    searches_per_run = int(os.getenv("LI_SEARCHES_PER_RUN",  "6"))
    max_per_search   = int(os.getenv("LI_RESULTS_PER_SEARCH", "8"))

    print(f"[LI] Starting Playwright session — {searches_per_run} searches, {max_per_search} results each")
    profiles = scrape_with_playwright(searches_per_run, max_per_search)
    print(f"[LI] {len(profiles)} profiles collected — finding company emails...")

    all_new      = []
    niche_counts: dict[str, int] = {}

    for profile in profiles:
        company  = profile["company"]
        location = profile["location"]
        niche    = profile["niche"]

        # Rate limit email-finding lookups
        time.sleep(random.uniform(2.0, 4.0))

        website, email = find_company_email(company, location)
        if not email:
            continue

        email_lower = email.lower()
        if email_lower in seen_emails:
            continue
        domain = extract_domain(website)
        if domain and domain in seen_domains:
            continue

        seen_emails.add(email_lower)
        if domain:
            seen_domains.add(domain)

        all_new.append({
            "company":          company,
            "website":          website,
            "email":            email,
            "contact_page_url": "",
            "location":         location,
            "niche":            niche,
            "phone":            "",
            "name":             profile["name"],
        })
        niche_counts[niche] = niche_counts.get(niche, 0) + 1
        print(f"  + {profile['name']} @ {company} — {email}")

    if not all_new:
        print("[LI] No new emailable contacts found this run.")
        return

    df_new = pd.DataFrame(all_new)
    df_new.drop_duplicates(subset=["email"], inplace=True)

    if os.path.exists(OUTPUT_FILE):
        try:
            df_existing = pd.read_csv(OUTPUT_FILE).fillna("")
            for col in ["phone", "name"]:
                if col not in df_existing.columns:
                    df_existing[col] = ""
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=["email"], inplace=True)
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    df_combined.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[LI DONE] {len(df_new)} owner contacts added | {len(df_combined)} total")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {c}")


if __name__ == "__main__":
    run()
