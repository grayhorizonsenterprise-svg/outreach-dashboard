"""
prospect_finder.py — Gray Horizons Enterprise
Searches the web for HOA management companies across the entire West Coast.
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
# WEST COAST SEARCH QUERIES
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

SEARCH_QUERIES = []

# State-level queries
for state in WEST_COAST_STATES:
    SEARCH_QUERIES.append(f"HOA property management company {state}")
    SEARCH_QUERIES.append(f"community association management {state}")

# City-level queries for major metros
for city in WEST_COAST_CITIES:
    SEARCH_QUERIES.append(f"HOA management company {city}")

# Generic industry queries
SEARCH_QUERIES += [
    "homeowners association management firm west coast",
    "HOA management company California contact email",
    "community association management Oregon Washington",
    "property management HOA Nevada Arizona contact",
    "HOA management services Colorado Utah Idaho",
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


def scrape_prospect(url: str, title: str, snippet: str) -> dict:
    prospect = {
        "company": title,
        "website": url,
        "email": "",
        "contact_page_url": "",
        "location": "",
    }
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

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

    for query in SEARCH_QUERIES:
        print(f"\n[SEARCH] {query}")
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

            print(f"  [SCRAPE] {url}")
            prospect = scrape_prospect(url, result["title"], result["snippet"])
            all_prospects.append(prospect)
            time.sleep(random.uniform(1.0, 2.5))

    if not all_prospects:
        print("\n[INFO] No prospects collected. Check network connectivity.")
        return

    df = pd.DataFrame(all_prospects, columns=[
        "company", "website", "email", "contact_page_url", "location"
    ])
    df.drop_duplicates(subset=["website"], inplace=True)

    output_path = os.path.join(DATA_DIR, "prospects_raw.csv")
    df.to_csv(output_path, index=False)
    print(f"\n[DONE] Saved {len(df)} prospects to prospects_raw.csv")


if __name__ == "__main__":
    run()
