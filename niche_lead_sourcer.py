"""
niche_lead_sourcer.py — Gray Horizons Enterprise
Replaces DDG-based scraping in all niche engines.
Scrapes YellowPages directly — no DDG, works on Railway cloud IPs.
Returns ready-to-use leads with emails extracted from business websites.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import urllib.parse
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SKIP_DOMAINS = {
    "yelp.com", "yellowpages.com", "superpages.com", "facebook.com",
    "twitter.com", "instagram.com", "linkedin.com", "youtube.com",
    "google.com", "bbb.org", "angi.com", "thumbtack.com", "homeadvisor.com",
    "nextdoor.com", "reddit.com", "wikipedia.org", "mapquest.com",
    "angieslist.com", "houzz.com", "porch.com", "bark.com",
}

JUNK_PREFIXES = {
    "abuse", "spam", "report", "complaints", "privacy", "legal", "billing",
    "webmaster", "postmaster", "mailer", "careers", "jobs", "news",
    "newsletter", "press", "media", "helpdesk", "ticket", "noreply",
    "no-reply", "donotreply", "do-not-reply", "notifications", "updates",
    "alerts",
}

CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/team", "/reach-us"]
GUESS_PREFIXES = ["info", "contact", "hello", "office", "admin"]

NICHE_YP_TERMS = {
    "realestate":   ["real estate agency", "realty company", "real estate broker", "real estate office"],
    "medspa":       ["medical spa", "med spa", "aesthetic clinic", "laser clinic", "skin care clinic"],
    "insurance":    ["insurance agency", "insurance broker", "independent insurance agent", "insurance office"],
    "restaurant":   ["restaurant", "dining", "bistro", "eatery", "cafe", "diner"],
    "gym":          ["gym", "fitness center", "personal training studio", "crossfit gym", "health club"],
    "mortgage":     ["mortgage broker", "mortgage company", "home loan", "mortgage lender"],
    "ecommerce":    ["digital marketing agency", "ecommerce consultant", "marketing company", "web design"],
    "hvac":         ["hvac", "air conditioning repair", "heating cooling", "furnace repair"],
    "dental":       ["dentist", "dental office", "dental practice", "dental clinic"],
    "plumbing":     ["plumber", "plumbing company", "drain cleaning", "plumbing service"],
    "contractor":   ["general contractor", "home remodeling", "construction company", "home improvement"],
    "roofing":      ["roofing company", "roofer", "roof repair", "roofing contractor"],
    "landscaping":  ["landscaping", "lawn care", "landscape design", "lawn service"],
    "hoa":          ["HOA management", "property management", "community association", "homeowner association"],
    "chiropractic": ["chiropractor", "chiropractic office", "chiropractic clinic", "spine center"],
    "salon":        ["hair salon", "day spa", "nail salon", "beauty salon"],
    "auto":         ["auto repair shop", "mechanic", "automotive service", "auto mechanic"],
    "pest_control": ["pest control", "exterminator", "termite control", "pest management"],
    "electrician":  ["electrician", "electrical contractor", "electrical service", "electric company"],
    "veterinary":   ["veterinarian", "animal hospital", "pet clinic", "veterinary clinic"],
    "optometry":    ["optometrist", "eye doctor", "vision center", "eye care"],
    "cleaning":     ["cleaning service", "house cleaning", "janitorial service", "maid service"],
    "painting":     ["painting contractor", "house painter", "painting company", "interior painting"],
    "flooring":     ["flooring company", "hardwood floors", "carpet installation", "floor installation"],
    "moving":       ["moving company", "movers", "relocation service", "moving service"],
    "storage":      ["self storage", "storage facility", "storage unit", "moving and storage"],
    "tutoring":     ["tutoring service", "learning center", "academic tutoring", "tutoring center"],
    "photography":  ["photographer", "photography studio", "wedding photographer", "portrait studio"],
}

US_CITIES = [
    "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX", "Phoenix, AZ",
    "Philadelphia, PA", "San Antonio, TX", "San Diego, CA", "Dallas, TX", "San Jose, CA",
    "Austin, TX", "Jacksonville, FL", "Fort Worth, TX", "Columbus, OH", "Charlotte, NC",
    "Indianapolis, IN", "San Francisco, CA", "Seattle, WA", "Denver, CO", "Nashville, TN",
    "Oklahoma City, OK", "El Paso, TX", "Las Vegas, NV", "Louisville, KY", "Memphis, TN",
    "Portland, OR", "Baltimore, MD", "Milwaukee, WI", "Albuquerque, NM", "Tucson, AZ",
    "Fresno, CA", "Sacramento, CA", "Mesa, AZ", "Atlanta, GA", "Kansas City, MO",
    "Omaha, NE", "Colorado Springs, CO", "Raleigh, NC", "Miami, FL", "Tampa, FL",
    "Cleveland, OH", "Minneapolis, MN", "Wichita, KS", "Aurora, CO", "Anaheim, CA",
    "Corpus Christi, TX", "Riverside, CA", "St. Louis, MO", "Lexington, KY", "Pittsburgh, PA",
    "Stockton, CA", "Cincinnati, OH", "Greensboro, NC", "Plano, TX", "Henderson, NV",
    "Lincoln, NE", "Buffalo, NY", "Fort Wayne, IN", "Orlando, FL", "St. Petersburg, FL",
    "Norfolk, VA", "Chandler, AZ", "Laredo, TX", "Madison, WI", "Durham, NC",
    "Lubbock, TX", "Winston-Salem, NC", "Garland, TX", "Glendale, AZ", "Hialeah, FL",
    "Reno, NV", "Baton Rouge, LA", "Irvine, CA", "Scottsdale, AZ", "Fremont, CA",
    "Gilbert, AZ", "San Bernardino, CA", "Birmingham, AL", "Boise, ID", "Rochester, NY",
    "Richmond, VA", "Spokane, WA", "Des Moines, IA", "Montgomery, AL", "Huntsville, AL",
    "Akron, OH", "Glendale, CA", "Little Rock, AR", "Augusta, GA", "Grand Rapids, MI",
    "Shreveport, LA", "Tallahassee, FL", "Huntington Beach, CA", "Worcester, MA", "Knoxville, TN",
    "Providence, RI", "Brownsville, TX", "Tempe, AZ", "Santa Clarita, CA", "Garden Grove, CA",
    "Oceanside, CA", "Chattanooga, TN", "Fort Lauderdale, FL", "Mobile, AL", "Rancho Cucamonga, CA",
    "Santa Rosa, CA", "Port Arthur, TX", "Moreno Valley, CA", "Fayetteville, NC", "Glendale, CA",
    "Tacoma, WA", "Oxnard, CA", "Eugene, OR", "Peoria, IL", "Salem, OR",
    "Cary, NC", "Fort Collins, CO", "Springfield, MO", "Jackson, MS", "Alexandria, VA",
    "Hayward, CA", "Lancaster, CA", "Salinas, CA", "Sunnyvale, CA", "Pomona, CA",
]


def _get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def _is_clean(email: str, site_domain: str = "") -> bool:
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e):
        return False
    if e.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
        return False
    prefix = e.split("@")[0]
    if prefix in JUNK_PREFIXES:
        return False
    domain = e.split("@")[-1]
    if domain in SKIP_DOMAINS:
        return False
    return True


def _fetch(url: str, timeout: int = 8) -> str:
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers=_get_headers(), timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""


def _extract_emails(html: str, site_domain: str = "") -> list:
    raw = list(EMAIL_RE.findall(html))
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
    seen = set()
    out = []
    for e in raw:
        e = e.lower().strip()
        if e not in seen and _is_clean(e, site_domain):
            seen.add(e)
            out.append(e)
    return out


def _enrich(website: str) -> str:
    """Extract email from a business website. Falls back to guessing info@domain."""
    if not website or website in ("", "nan", "None"):
        return ""
    try:
        domain = urllib.parse.urlparse(website).netloc.lower().replace("www.", "")
    except Exception:
        domain = ""

    base = website.rstrip("/")
    html = _fetch(base)
    emails = _extract_emails(html, domain) if html else []

    if not emails and html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(k in href for k in ["contact", "about", "team", "reach"]):
                    full = href if href.startswith("http") else urllib.parse.urljoin(base, href)
                    if domain and domain not in urllib.parse.urlparse(full).netloc.lower():
                        continue
                    linked = _fetch(full)
                    if linked:
                        emails = _extract_emails(linked, domain)
                    if emails:
                        break
        except Exception:
            pass

    if not emails:
        for path in CONTACT_PATHS:
            linked = _fetch(base + path)
            if linked:
                emails = _extract_emails(linked, domain)
                if emails:
                    break

    if not emails and domain and "." in domain:
        for prefix in GUESS_PREFIXES:
            emails = [f"{prefix}@{domain}"]
            break

    return emails[0] if emails else ""


def _scrape_yp(search_term: str, location: str) -> list:
    """Scrape one YP results page. Returns list of {company, website, phone}."""
    url = "https://www.yellowpages.com/search?" + urllib.parse.urlencode({
        "search_terms": search_term,
        "geo_location_terms": location,
        "page": 1,
    })
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        listings = (
            soup.find_all("div", class_="result") or
            soup.find_all("div", class_=re.compile(r"\bv-card\b")) or
            soup.find_all("article", class_=re.compile(r"listing|result", re.I))
        )
        results = []
        for listing in listings:
            name = ""
            for sel in [
                lambda el: el.find("a", class_="business-name"),
                lambda el: el.find("h2"),
                lambda el: el.find("h3"),
            ]:
                tag = sel(listing)
                if tag and tag.get_text(strip=True):
                    name = tag.get_text(strip=True)
                    break
            if not name or len(name) < 3:
                continue
            website = ""
            ws = listing.find("a", class_=re.compile(r"track-visit-website|website", re.I))
            if ws:
                href = ws.get("href", "")
                if href.startswith("http") and "yellowpages.com" not in href:
                    website = href
                elif "yellowpages.com" in href and "url=" in href:
                    try:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        website = qs.get("url", [href])[0]
                    except Exception:
                        pass
            phone = ""
            ph = listing.find(class_=re.compile(r"\bphones?\b|\bphone\b", re.I))
            if ph:
                phone = re.sub(r"[^\d\-\(\) ]", "", ph.get_text(strip=True)).strip()
            results.append({"company": name, "website": website, "phone": phone})
        return results
    except Exception:
        return []


def get_leads(niche: str, limit: int = 300, seen: set = None, global_seen: set = None) -> list:
    """
    Main entry for niche engines — replaces DDG scrape() function.
    Returns list of dicts compatible with all niche engine queue formats:
      {email, name, website, source, status, niche, phone}
    """
    if seen is None:
        seen = set()
    if global_seen is None:
        global_seen = set()

    terms = NICHE_YP_TERMS.get(niche, ["local business service"])
    cities = random.sample(US_CITIES, min(40, len(US_CITIES)))

    leads = []
    seen_domains = set()

    for city in cities:
        if len(leads) >= limit:
            break
        term = random.choice(terms)
        print(f"  [SRC:{niche.upper()}] '{term}' in {city}")

        listings = _scrape_yp(term, city)
        for listing in listings:
            if len(leads) >= limit:
                break

            website = listing.get("website", "").strip()
            company = listing.get("company", "").strip()
            phone   = listing.get("phone", "").strip()

            domain = ""
            if website:
                try:
                    domain = urllib.parse.urlparse(website).netloc.lower().replace("www.", "")
                except Exception:
                    pass

            if domain and (domain in seen_domains or domain in SKIP_DOMAINS):
                continue

            email = _enrich(website) if website else ""
            if not email:
                continue

            if email.lower() in seen or email.lower() in global_seen:
                continue

            if domain:
                seen_domains.add(domain)
            seen.add(email.lower())

            leads.append({
                "email":   email,
                "name":    company,
                "website": website,
                "source":  f"yp:{term}:{city}",
                "status":  "pending",
                "niche":   niche,
                "phone":   phone,
            })
            print(f"    [+] {email} ({company[:40]})")

        time.sleep(random.uniform(2.0, 4.0))

    print(f"  [SRC] {len(leads)} new {niche} leads found via YP")
    return leads
