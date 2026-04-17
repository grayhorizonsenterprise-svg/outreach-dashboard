"""
prospect_finder.py — Gray Horizons Enterprise
Searches the web for prospects across all 5 niches:
  HOA Management · HVAC · Dental · Plumbing · General Contractor
Rotates browser user agents to avoid blocks.
Stores results in prospects_raw.csv.
"""

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import pandas as pd
import re
import time
import random
import urllib.parse
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))

# =========================
# ROTATING USER AGENTS (Chrome, Firefox, Safari, Edge)
# =========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

# =========================
# NICHE SEARCH QUERIES — regional coverage, fast execution
# West Coast · Southwest · Midwest
# 12 queries per niche × 5 niches = 60 total (~15 min runtime)
# Each query yields ~10 results = ~600 prospects per run
# =========================
NICHE_QUERIES: list[tuple[str, str]] = [
    # ── HOA ───────────────────────────────────────────────────────────────────
    # Signals: "LLC" "Inc" "free quote" "serving" force actual company pages not directories
    ("hoa", 'HOA management company California LLC -yelp -angi -thumbtack -directory'),
    ("hoa", 'HOA management company Arizona Nevada Utah LLC -yelp -directory'),
    ("hoa", 'HOA management company Oregon Washington "free quote" -yelp -thumbtack'),
    ("hoa", 'HOA management Colorado Texas "contact us" -yelp -angi -directory'),
    ("hoa", 'community association management company Chicago Dallas "serving" -yelp'),
    ("hoa", 'HOA management company Los Angeles Phoenix Denver LLC -yelp -directory'),
    ("hoa", 'HOA management company Florida Georgia LLC -yelp -angi -thumbtack'),
    ("hoa", 'homeowners association management company Illinois Ohio -yelp -directory'),
    ("hoa", 'community association management Midwest "contact us" LLC -yelp'),
    ("hoa", 'property management HOA company Texas "free proposal" -yelp -angi'),
    ("hoa", 'HOA management company "serving" California Nevada -yelp -thumbtack'),
    ("hoa", 'condo association management company Southeast LLC -yelp -directory'),

    # ── HVAC ──────────────────────────────────────────────────────────────────
    ("hvac", 'HVAC company California "free estimate" LLC -yelp -angi -thumbtack'),
    ("hvac", 'HVAC company Arizona Texas "licensed" -yelp -angi -thumbtack -directory'),
    ("hvac", 'HVAC contractor Oregon Washington "serving" LLC -yelp -directory'),
    ("hvac", 'heating cooling company Illinois Ohio Michigan LLC -yelp -angi'),
    ("hvac", 'HVAC company Chicago Dallas Houston "free estimate" -yelp -thumbtack'),
    ("hvac", 'air conditioning company Los Angeles Phoenix "licensed" -yelp -angi'),
    ("hvac", 'HVAC company Florida Georgia LLC "contact us" -yelp -directory'),
    ("hvac", 'heating air conditioning company Denver Colorado LLC -yelp -thumbtack'),
    ("hvac", 'commercial HVAC company California Texas "licensed contractor" -yelp'),
    ("hvac", 'HVAC contractor Salt Lake City Nevada "free quote" -yelp -angi'),
    ("hvac", 'residential HVAC company "serving" Midwest LLC -yelp -directory'),
    ("hvac", 'HVAC service company Southwest "free estimate" -yelp -thumbtack'),

    # ── Dental ────────────────────────────────────────────────────────────────
    ("dental", 'dental office California "accepting new patients" -yelp -healthgrades -zocdoc'),
    ("dental", 'dental clinic Arizona Nevada Texas "new patients welcome" -yelp -healthgrades'),
    ("dental", 'dentist practice Oregon Washington "accepting new patients" -yelp -directory'),
    ("dental", 'dental office Illinois Ohio Michigan LLC "contact us" -yelp -healthgrades'),
    ("dental", 'dental practice Chicago Dallas Houston "new patients" -yelp -zocdoc'),
    ("dental", 'family dentist Los Angeles Phoenix "accepting patients" -yelp -healthgrades'),
    ("dental", 'dental clinic Florida Georgia "same day appointments" -yelp -directory'),
    ("dental", 'dental group practice Midwest LLC "contact" -yelp -healthgrades'),
    ("dental", 'dentist office Colorado Utah "accepting new patients" -yelp -zocdoc'),
    ("dental", 'multi-location dental office "contact us" -yelp -healthgrades -directory'),
    ("dental", 'dental management group "locations" LLC -yelp -healthgrades'),
    ("dental", 'dental practice Southwest "free consultation" -yelp -angi -directory'),

    # ── Plumbing ──────────────────────────────────────────────────────────────
    ("plumbing", 'plumbing company California "licensed" LLC -yelp -angi -thumbtack'),
    ("plumbing", 'plumber Arizona Nevada Texas "free estimate" -yelp -angi -thumbtack'),
    ("plumbing", 'plumbing contractor Oregon Washington LLC "serving" -yelp -directory'),
    ("plumbing", 'plumbing company Illinois Ohio Michigan "licensed" -yelp -angi'),
    ("plumbing", 'plumber Chicago Dallas Houston "free estimate" LLC -yelp -thumbtack'),
    ("plumbing", 'plumbing service Los Angeles Phoenix "licensed contractor" -yelp'),
    ("plumbing", 'plumbing company Florida Georgia LLC "contact us" -yelp -angi'),
    ("plumbing", 'plumbing contractor Denver Colorado "free estimate" -yelp -directory'),
    ("plumbing", 'commercial plumbing company California Texas "licensed" -yelp -angi'),
    ("plumbing", 'plumbing repair service Utah Nevada LLC -yelp -thumbtack'),
    ("plumbing", 'residential plumbing contractor Midwest "free quote" -yelp -directory'),
    ("plumbing", 'plumbing company Southwest LLC "serving" -yelp -angi -thumbtack'),

    # ── General Contractor ────────────────────────────────────────────────────
    ("contractor", 'general contractor California LLC "free estimate" -yelp -angi -thumbtack'),
    ("contractor", 'general contractor Arizona Texas "licensed" LLC -yelp -angi -directory'),
    ("contractor", 'construction company Oregon Washington "free estimate" -yelp -directory'),
    ("contractor", 'general contractor Illinois Ohio Michigan LLC -yelp -angi -thumbtack'),
    ("contractor", 'construction company Chicago Dallas Houston "free estimate" -yelp'),
    ("contractor", 'home remodel contractor Los Angeles Phoenix "licensed" -yelp -angi'),
    ("contractor", 'general contractor Florida Georgia LLC "contact us" -yelp -directory'),
    ("contractor", 'construction remodeling company Midwest LLC -yelp -thumbtack'),
    ("contractor", 'general contractor Colorado Utah "free estimate" -yelp -angi'),
    ("contractor", 'residential contractor company "serving" -yelp -angi -thumbtack'),
    ("contractor", 'commercial construction company LLC "contact us" -yelp -directory'),
    ("contractor", 'home builder contractor Southwest "free quote" LLC -yelp -angi'),
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

WEST_COAST_STATES = [
    "California", "Oregon", "Washington", "Nevada", "Arizona", "Utah", "Idaho",
    "Colorado", "New Mexico", "Montana", "Wyoming",
    "Texas", "Illinois", "Ohio", "Michigan", "Indiana", "Wisconsin",
    "Florida", "Georgia", "North Carolina", "Tennessee",
    "Los Angeles", "Phoenix", "Denver", "Seattle", "Portland", "Las Vegas",
    "Chicago", "Dallas", "Houston", "Atlanta", "Miami",
]

JUNK_EMAIL_PATTERNS = [
    "example", "domain", "user@", "noreply", "no-reply",
    "sentry", "wixpress", "pinterest", "youtube", "twitter",
    "linkedin", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js",
]

CONTACT_PATH_PATTERNS = re.compile(
    r"contact|about|reach|connect|team|staff|people", re.IGNORECASE
)


def search_web(query: str, max_results: int = 10) -> list[dict]:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception as exc:
        print(f"  [WARN] Search failed for '{query}': {exc}")
    return results


def extract_domain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def find_contact_page(soup: BeautifulSoup, base_url: str) -> str:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if CONTACT_PATH_PATTERNS.search(href) or CONTACT_PATH_PATTERNS.search(text):
            if href.startswith("http"):
                return href
            else:
                return urllib.parse.urljoin(base_url, href)
    return ""


def extract_location(soup: BeautifulSoup, snippet: str) -> str:
    combined = snippet + " "
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        combined += meta_desc.get("content", "")
    for state in WEST_COAST_STATES:
        if state.lower() in combined.lower():
            return state
    return ""


def is_junk_email(email: str) -> bool:
    e = email.lower()
    return any(p in e for p in JUNK_EMAIL_PATTERNS)


def extract_company_name(soup: BeautifulSoup, url: str, fallback_title: str) -> str:
    """Try to get the real company name from the page, not the SEO title."""

    # 1. og:site_name is almost always the clean company name
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content", "").strip():
        return og_site["content"].strip()

    # 2. Twitter site name
    tw_site = soup.find("meta", attrs={"name": "twitter:site"})
    if tw_site and tw_site.get("content", "").strip():
        name = tw_site["content"].strip().lstrip("@")
        if len(name) > 2:
            return name

    # 3. First <h1> on the page — usually the company or page heading
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(" ", strip=True)
        # Only use if short and looks like a name, not a headline
        if 2 < len(h1_text.split()) <= 6 and not re.search(r"\d{4}|how\s+to|\?", h1_text, re.IGNORECASE):
            return h1_text

    # 4. <title> tag — split on | or - and take the shortest part
    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        for sep in [" | ", " – ", " — ", " - ", ": "]:
            if sep in raw:
                parts = [p.strip() for p in raw.split(sep) if len(p.strip()) > 2]
                if parts:
                    return min(parts, key=len)
        return raw

    return fallback_title


def scrape_prospect(url: str, title: str, snippet: str, niche: str = "hoa") -> dict:
    prospect = {
        "company": title,
        "website": url,
        "email": "",
        "contact_page_url": "",
        "location": "",
        "niche": niche,
    }
    try:
        resp = requests.get(url, headers=get_headers(), timeout=6)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Get real company name from the page itself
        prospect["company"] = extract_company_name(soup, url, title)

        page_text = soup.get_text(" ", strip=True)
        emails = EMAIL_REGEX.findall(page_text)
        clean = [e for e in emails if not is_junk_email(e)]
        if clean:
            prospect["email"] = clean[0]

        prospect["contact_page_url"] = find_contact_page(soup, url)
        prospect["location"] = extract_location(soup, snippet)

    except Exception as exc:
        print(f"  [WARN] Could not scrape {url}: {exc}")

    return prospect


def run():
    seen_domains: set[str] = set()
    all_prospects: list[dict] = []

    # Skip noisy domains that never have usable leads
    SKIP_DOMAINS = {
        "yelp.com", "youtube.com", "pinterest.com", "twitter.com",
        "linkedin.com", "facebook.com", "instagram.com", "reddit.com",
        "nolo.com", "wikipedia.org", "zillow.com", "trulia.com",
        "angi.com", "thumbtack.com", "nextdoor.com", "bbb.org",
        "myfloridalicense.com", "newswire.com", "businesswire.com",
    }

    niche_counts: dict[str, int] = {}

    for niche, query in NICHE_QUERIES:
        print(f"\n[SEARCH:{niche.upper()}] {query}")
        results = search_web(query, max_results=15)
        print(f"  Found {len(results)} results")
        time.sleep(random.uniform(0.8, 1.5))

        for result in results:
            url = result["url"]
            if not url:
                continue
            domain = extract_domain(url)
            if not domain:
                continue
            if domain in seen_domains or domain in SKIP_DOMAINS:
                print(f"  [SKIP] {domain}")
                continue
            seen_domains.add(domain)

            print(f"  [SCRAPE:{niche}] {url}")
            prospect = scrape_prospect(url, result["title"], result["snippet"], niche)
            all_prospects.append(prospect)
            niche_counts[niche] = niche_counts.get(niche, 0) + 1
            time.sleep(random.uniform(0.5, 1.2))

    if not all_prospects:
        print("\n[INFO] No prospects collected. Check network connectivity.")
        return

    df = pd.DataFrame(all_prospects, columns=[
        "company", "website", "email", "contact_page_url", "location", "niche"
    ])
    df.drop_duplicates(subset=["website"], inplace=True)

    output_path = os.path.join(DATA_DIR, "prospects_raw.csv")
    df.to_csv(output_path, index=False)
    print(f"\n[DONE] Saved {len(df)} prospects to prospects_raw.csv")
    for n, count in sorted(niche_counts.items()):
        print(f"  {n.upper():12s}: {count}")


if __name__ == "__main__":
    run()
