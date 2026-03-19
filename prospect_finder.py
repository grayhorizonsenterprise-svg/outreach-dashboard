"""
prospect_finder.py — Gray Horizons Enterprise
Searches the web for HOA management companies and collects prospect data.
Stores results in prospects_raw.csv.

SAFETY RULES:
- Only collects publicly visible information
- Avoids scraping the same domain repeatedly
- Never sends emails automatically
"""

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import pandas as pd
import re
import time
import urllib.parse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

SEARCH_QUERIES = [
    "hoa property management company",
    "community association management",
    "homeowners association board contact",
    "hoa management company",
    "community association management firm",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CONTACT_PATH_PATTERNS = re.compile(
    r"contact|about|reach|connect|team", re.IGNORECASE
)


def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    Uses the duckduckgo-search package to fetch organic search results.
    Returns a list of dicts with keys: title, url, snippet.
    No API key required.
    """
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
    return parsed.netloc.lower().lstrip("www.")


def find_contact_page(soup: BeautifulSoup, base_url: str) -> str:
    """Looks for a contact/about link on the page."""
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
    """
    Tries to extract a US state from meta description or snippet.
    Very lightweight — avoids scraping personal/private data.
    """
    us_states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
        "New Hampshire", "New Jersey", "New Mexico", "New York",
        "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
        "West Virginia", "Wisconsin", "Wyoming",
    ]
    combined = snippet + " "
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        combined += meta_desc.get("content", "")
    for state in us_states:
        if state.lower() in combined.lower():
            return state
    return ""


def scrape_prospect(url: str, title: str, snippet: str) -> dict:
    """
    Visits a single page and extracts prospect details.
    Returns a dict with prospect fields.
    """
    prospect = {
        "company_name": title,
        "website": url,
        "contact_email": "",
        "contact_page_url": "",
        "location": "",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract emails visible in page text
        page_text = soup.get_text(" ", strip=True)
        emails = EMAIL_REGEX.findall(page_text)
        filtered = [
            e for e in emails
            if not any(x in e.lower() for x in ["example", "domain", "email", "user@"])
        ]
        if filtered:
            prospect["contact_email"] = filtered[0]

        # Find contact page
        prospect["contact_page_url"] = find_contact_page(soup, url)

        # Extract location
        prospect["location"] = extract_location(soup, snippet)

    except Exception as exc:
        print(f"  [WARN] Could not scrape {url}: {exc}")

    return prospect


def run():
    seen_domains: set[str] = set()
    all_prospects: list[dict] = []

    for query in SEARCH_QUERIES:
        print(f"\n[SEARCH] {query}")
        results = search_web(query, max_results=10)
        print(f"  Found {len(results)} results")
        time.sleep(2)  # polite delay between searches

        for result in results:
            url = result["url"]
            if not url:
                continue
            domain = extract_domain(url)
            if not domain:
                continue

            # Safety rule: skip domains already scraped
            if domain in seen_domains:
                print(f"  [SKIP] Already scraped: {domain}")
                continue
            seen_domains.add(domain)

            print(f"  [SCRAPE] {url}")
            prospect = scrape_prospect(url, result["title"], result["snippet"])
            all_prospects.append(prospect)
            time.sleep(1.5)  # polite delay between page requests

    if not all_prospects:
        print("\n[INFO] No prospects collected. Check network connectivity.")
        return

    df = pd.DataFrame(all_prospects, columns=[
        "company_name", "website", "contact_email", "contact_page_url", "location"
    ])
    df.drop_duplicates(subset=["website"], inplace=True)
    df.to_csv("prospects_raw.csv", index=False)
    print(f"\n[DONE] Saved {len(df)} prospects to prospects_raw.csv")


if __name__ == "__main__":
    run()
