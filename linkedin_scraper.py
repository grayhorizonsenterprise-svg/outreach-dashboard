"""
linkedin_scraper.py — Gray Horizons Enterprise
LinkedIn people search targeting business owners and decision-makers.
Uses li_at session cookie — no API key, no cost.
Rate-limited to stay safe (3-6s between calls, max 40 profiles per run).

Requires env var: LINKEDIN_COOKIE=<your li_at cookie value>
"""

import requests
import pandas as pd
import re
import time
import random
import os
import sys
import json
import urllib.parse
from bs4 import BeautifulSoup
from ddgs import DDGS

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE   = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

LI_AT = os.getenv("LINKEDIN_COOKIE", "").strip()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# Job title keyword searches — goes after owners and decision-makers, not staff
TITLE_SEARCHES = [
    ("hoa",          "HOA property manager"),
    ("hoa",          "community association manager owner"),
    ("hoa",          "HOA management company owner"),
    ("hvac",         "HVAC company owner"),
    ("hvac",         "HVAC business owner"),
    ("dental",       "dental practice owner"),
    ("dental",       "dentist owner"),
    ("plumbing",     "plumbing company owner"),
    ("plumbing",     "master plumber owner"),
    ("contractor",   "general contractor owner"),
    ("contractor",   "construction company owner"),
    ("landscaping",  "landscaping business owner"),
    ("landscaping",  "lawn care company owner"),
    ("roofing",      "roofing company owner"),
    ("roofing",      "roofing contractor owner"),
    ("auto",         "auto repair shop owner"),
    ("auto",         "automotive shop owner"),
    ("chiropractic", "chiropractor owner"),
    ("chiropractic", "chiropractic practice owner"),
    ("realestate",   "real estate broker owner"),
    ("realestate",   "independent realty owner"),
    ("salon",        "salon owner"),
    ("salon",        "spa owner"),
]

EMAIL_REGEX     = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "msn.com", "live.com",
}
JUNK_EMAIL_PATTERNS = [
    "noreply", "no-reply", "donotreply", "sentry", "wixpress",
    "example", "test@", "domain.com", "placeholder",
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
    domain = e.split("@")[-1]
    if domain in PERSONAL_DOMAINS:
        return False
    return True


def get_li_session():
    """
    Open a session with li_at cookie and capture JSESSIONID for CSRF.
    Returns (session, csrf_token) or (None, None) on failure.
    """
    if not LI_AT:
        print("[LI] LINKEDIN_COOKIE not set — skipping LinkedIn scrape.")
        print("[LI] Set it in Railway env vars: LINKEDIN_COOKIE=<li_at value>")
        return None, None

    session   = requests.Session()
    ua        = random.choice(USER_AGENTS)
    session.headers.update({
        "User-Agent":      ua,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    session.cookies.set("li_at", LI_AT, domain=".linkedin.com")

    try:
        resp = session.get("https://www.linkedin.com/feed/", timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            print(f"[LI] Login check failed — HTTP {resp.status_code}. Cookie may be expired.")
            return None, None

        # JSESSIONID (without quotes) doubles as CSRF token
        jsessionid = session.cookies.get("JSESSIONID", "")
        csrf_token = jsessionid.strip('"')

        if not csrf_token:
            # Try to pull CSRF from page meta
            soup = BeautifulSoup(resp.text, "html.parser")
            meta = soup.find("meta", attrs={"name": "pageKey"})
            csrf_token = resp.cookies.get("JSESSIONID", "").strip('"') or "ajax:0"

        print(f"[LI] Session active. CSRF: {csrf_token[:12]}...")
        return session, csrf_token

    except Exception as exc:
        print(f"[LI] Session setup error: {exc}")
        return None, None


def search_people(session, csrf_token, keywords, start=0, count=25):
    """
    Call LinkedIn Voyager people-search API.
    Returns list of raw profile dicts.
    """
    params = {
        "decorationId": "com.linkedin.voyager.deco.jserp.WebSearchPeopleResultWithDistance-4",
        "q":            "people",
        "query":        f"(keywords:{urllib.parse.quote(keywords)},flagshipSearchIntent:SEARCH_SRP)",
        "start":        start,
        "count":        count,
    }
    url = "https://www.linkedin.com/voyager/api/search/blended?" + urllib.parse.urlencode(params)

    headers = {
        "accept":                    "application/vnd.linkedin.normalized+json+2.1",
        "csrf-token":                csrf_token,
        "x-li-lang":                 "en_US",
        "x-li-track":                '{"clientVersion":"1.13.1665","osName":"web"}',
        "x-restli-protocol-version": "2.0.0",
        "referer":                   f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(keywords)}",
    }

    try:
        resp = session.get(url, headers=headers, timeout=12)
        if resp.status_code == 401:
            print("[LI] 401 Unauthorized — cookie expired or invalid.")
            return []
        if resp.status_code != 200:
            print(f"[LI] Search HTTP {resp.status_code} for '{keywords}'")
            return []
        return resp.json().get("elements", [])
    except Exception as exc:
        print(f"[LI] Search error for '{keywords}': {exc}")
        return []


def parse_profiles(elements):
    """
    Extract clean profile dicts from Voyager search results.
    """
    profiles = []
    for el in elements:
        # Results are nested — dig into SEARCH_HITS
        if isinstance(el, dict):
            inner = el.get("elements", [el])
            for item in inner:
                if not isinstance(item, dict):
                    continue
                mp = item.get("*miniProfile") or item.get("miniProfile") or item
                first  = mp.get("firstName", "")
                last   = mp.get("lastName",  "")
                name   = f"{first} {last}".strip()
                if not name or len(name) < 3:
                    continue
                headline  = mp.get("headline", "")
                pub_id    = mp.get("publicIdentifier", "")
                location  = mp.get("geoLocationName", "")
                company   = ""
                # Parse company from headline ("Title at Company")
                if " at " in headline:
                    company = headline.split(" at ", 1)[-1].strip()
                profiles.append({
                    "name":     name,
                    "headline": headline,
                    "company":  company,
                    "location": location,
                    "li_url":   f"https://www.linkedin.com/in/{pub_id}" if pub_id else "",
                })
    return profiles


def find_company_email(company_name, location):
    """
    Search DuckDuckGo for the company website then scrape for email.
    Returns (website, email) or ("", "").
    """
    if not company_name or len(company_name) < 3:
        return "", ""

    query = f'"{company_name}" {location} contact email site'
    website = ""
    email   = ""

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        for r in results:
            url = r.get("href", "")
            domain = extract_domain(url)
            if not domain or domain in {"linkedin.com", "facebook.com", "yelp.com", "yellowpages.com"}:
                continue
            website = url
            break
    except Exception:
        pass

    if not website:
        return "", ""

    # Scrape the website for email
    try:
        resp = requests.get(
            website,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=7,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Check mailto links first (most reliable)
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    addr = a["href"][7:].split("?")[0].strip()
                    if is_valid_email(addr, website):
                        email = addr
                        break
            # Fall back to regex scan
            if not email:
                found = EMAIL_REGEX.findall(resp.text)
                for e in found:
                    if is_valid_email(e, website):
                        email = e
                        break
    except Exception:
        pass

    # Last resort: guess info@ from domain
    if not email:
        domain = extract_domain(website)
        if domain and "." in domain:
            guessed = f"info@{domain}"
            if is_valid_email(guessed):
                email = guessed

    return website, email


def run():
    if not LI_AT:
        print("[LI] LINKEDIN_COOKIE env var not set — skipping.")
        print("[LI] To enable: copy your li_at cookie from LinkedIn DevTools")
        print("[LI] and add LINKEDIN_COOKIE=<value> to Railway env vars.")
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

    session, csrf_token = get_li_session()
    if not session:
        return

    # How many title searches to run per cycle — keep low to protect account
    searches_per_run = int(os.getenv("LI_SEARCHES_PER_RUN", "8"))
    combos           = random.sample(TITLE_SEARCHES, min(searches_per_run, len(TITLE_SEARCHES)))
    max_per_search   = int(os.getenv("LI_RESULTS_PER_SEARCH", "10"))

    print(f"[LI] Running {len(combos)} LinkedIn searches, {max_per_search} results each...")

    all_new      = []
    niche_counts: dict[str, int] = {}

    for niche, keywords in combos:
        print(f"  [LI:{niche.upper()}] '{keywords}'")
        elements = search_people(session, csrf_token, keywords, count=max_per_search)
        profiles = parse_profiles(elements)
        print(f"    {len(profiles)} profiles found")

        for profile in profiles:
            company  = profile["company"]
            location = profile["location"]

            if not company or len(company) < 3:
                continue

            # Rate limit — critical to avoid LinkedIn flag
            time.sleep(random.uniform(3.0, 6.0))

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
                "contact_page_url": profile.get("li_url", ""),
                "location":         location,
                "niche":            niche,
                "phone":            "",
                "name":             profile["name"],
            })
            niche_counts[niche] = niche_counts.get(niche, 0) + 1
            print(f"    + {profile['name']} @ {company} — {email}")

        # Pause between searches — looks more human
        time.sleep(random.uniform(4.0, 8.0))

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
    print(f"\n[LI DONE] {len(df_new)} owner-level contacts added | {len(df_combined)} total")
    for n, c in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {c}")


if __name__ == "__main__":
    run()
