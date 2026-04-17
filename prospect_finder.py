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
# GEOGRAPHY
# =========================
WEST_COAST_STATES = [
    "California", "Oregon", "Washington", "Nevada", "Arizona",
    "Utah", "Colorado", "Idaho", "Montana", "New Mexico"
]

WEST_COAST_CITIES = [
    "Los Angeles", "San Francisco", "San Diego", "Sacramento",
    "Portland", "Seattle", "Tacoma", "Spokane",
    "Las Vegas", "Henderson", "Reno",
    "Phoenix", "Tucson", "Scottsdale",
    "Salt Lake City", "Denver", "Boise",
]

# =========================
# NICHE SEARCH QUERIES
# Each entry: (niche_tag, query_string)
# =========================
NICHE_QUERIES: list[tuple[str, str]] = []

# ── HOA Management ────────────────────────────────────────────────────────────
for state in WEST_COAST_STATES:
    NICHE_QUERIES.append(("hoa", f"HOA property management company {state}"))
    NICHE_QUERIES.append(("hoa", f"community association management {state}"))

for city in WEST_COAST_CITIES:
    NICHE_QUERIES.append(("hoa", f"HOA management company {city}"))

NICHE_QUERIES += [
    ("hoa", "homeowners association management firm west coast"),
    ("hoa", "HOA management company California contact email"),
    ("hoa", "community association management Oregon Washington"),
    ("hoa", "property management HOA Nevada Arizona contact"),
    ("hoa", "HOA management services Colorado Utah Idaho"),
]

# ── HVAC ──────────────────────────────────────────────────────────────────────
for state in WEST_COAST_STATES:
    NICHE_QUERIES.append(("hvac", f"HVAC company {state} contact email"))
    NICHE_QUERIES.append(("hvac", f"air conditioning heating service {state}"))

for city in WEST_COAST_CITIES:
    NICHE_QUERIES.append(("hvac", f"HVAC contractor {city}"))

NICHE_QUERIES += [
    ("hvac", "HVAC company California contact email"),
    ("hvac", "heating cooling service company Arizona Nevada"),
    ("hvac", "air conditioning repair company Colorado Utah"),
]

# ── Dental ────────────────────────────────────────────────────────────────────
for state in WEST_COAST_STATES:
    NICHE_QUERIES.append(("dental", f"dental office {state} contact email"))
    NICHE_QUERIES.append(("dental", f"dentist practice {state}"))

for city in WEST_COAST_CITIES:
    NICHE_QUERIES.append(("dental", f"dental clinic {city} contact"))

NICHE_QUERIES += [
    ("dental", "dental office California contact email"),
    ("dental", "family dentist practice Arizona Nevada contact"),
    ("dental", "dental group Colorado Utah Oregon"),
]

# ── Plumbing ──────────────────────────────────────────────────────────────────
for state in WEST_COAST_STATES:
    NICHE_QUERIES.append(("plumbing", f"plumbing company {state} contact email"))
    NICHE_QUERIES.append(("plumbing", f"plumber service {state}"))

for city in WEST_COAST_CITIES:
    NICHE_QUERIES.append(("plumbing", f"plumbing contractor {city}"))

NICHE_QUERIES += [
    ("plumbing", "plumbing company California contact email"),
    ("plumbing", "plumber service Arizona Nevada Utah"),
    ("plumbing", "plumbing repair company Oregon Washington Colorado"),
]

# ── General Contractor ────────────────────────────────────────────────────────
for state in WEST_COAST_STATES:
    NICHE_QUERIES.append(("contractor", f"general contractor {state} contact email"))
    NICHE_QUERIES.append(("contractor", f"construction company {state}"))

for city in WEST_COAST_CITIES:
    NICHE_QUERIES.append(("contractor", f"general contractor {city}"))

NICHE_QUERIES += [
    ("contractor", "general contractor California contact email"),
    ("contractor", "construction remodeling company Arizona Nevada"),
    ("contractor", "home remodel contractor Colorado Utah Oregon"),
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

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
        resp = requests.get(url, headers=get_headers(), timeout=10)
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
        results = search_web(query, max_results=10)
        print(f"  Found {len(results)} results")
        time.sleep(random.uniform(1.5, 3.0))

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
            time.sleep(random.uniform(1.0, 2.5))

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
