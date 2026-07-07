"""
scrape_yelp_hot_leads.py — Gray Horizons Enterprise
Finds CA service businesses with Yelp reviews complaining about missed calls,
no answer, or voicemail — these are the highest-converting prospects for the
Autonomous Front Desk because the problem is already publicly documented.

Output: hot_leads.csv with email (if found), business name, Yelp URL, pain quote.

Usage:
  python scrape_yelp_hot_leads.py
"""

import os
import sys
import re
import csv
import time
import random
import requests
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT   = DATA_DIR / "hot_leads.csv"
FIELDNAMES = ["business_name", "email", "phone", "yelp_url", "niche", "pain_quote", "found_at"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")

# Pain keywords in reviews that signal the missed-call problem
PAIN_KEYWORDS = [
    "never answers", "no answer", "went to voicemail", "called multiple times",
    "doesn't answer", "hard to reach", "couldn't get through", "left a message",
    "no one called back", "missed my call", "couldn't reach", "voice mail",
    "phone goes to voicemail", "never called back", "hard to contact",
    "unreachable", "no callback", "won't answer", "didn't call back",
]

# DDG search queries targeting Yelp reviews with the pain keywords
SEARCHES = [
    'site:yelp.com/biz "hvac" "California" "voicemail" OR "no answer" OR "never calls back"',
    'site:yelp.com/biz "air conditioning" "Los Angeles" "voicemail" OR "no answer"',
    'site:yelp.com/biz "plumber" "California" "voicemail" OR "no answer" OR "never called back"',
    'site:yelp.com/biz "roofing" "California" "voicemail" OR "no answer" OR "never called back"',
    'site:yelp.com/biz "solar" "California" "voicemail" OR "no answer"',
    'site:yelp.com/biz "dentist" "California" "voicemail" OR "no answer" OR "hard to reach"',
    'site:yelp.com/biz "dental" "Los Angeles" "voicemail" OR "couldn\'t get through"',
    'site:yelp.com/biz "hvac" "San Diego" "voicemail" OR "no answer"',
    'site:yelp.com/biz "plumbing" "Los Angeles" "voicemail" OR "no answer"',
    'site:yelp.com/biz "contractor" "California" "voicemail" OR "never answers"',
]

NICHE_MAP = {
    "hvac": "hvac", "air conditioning": "hvac", "heating": "hvac", "cooling": "hvac",
    "plumb": "plumbing", "plumber": "plumbing",
    "roof": "roofing",
    "solar": "solar",
    "dental": "dental", "dentist": "dental",
    "contractor": "contractor",
}


def _detect_niche(text: str) -> str:
    text = text.lower()
    for kw, niche in NICHE_MAP.items():
        if kw in text:
            return niche
    return "other"


def _extract_pain_quote(text: str) -> str:
    text_lower = text.lower()
    for pain in PAIN_KEYWORDS:
        idx = text_lower.find(pain)
        if idx != -1:
            start = max(0, idx - 40)
            end   = min(len(text), idx + len(pain) + 60)
            return "..." + text[start:end].strip() + "..."
    return ""


def _scrape_yelp_page(url: str) -> dict:
    """Visit a Yelp business page and extract contact info + pain quotes."""
    result = {"email": "", "phone": "", "pain_quote": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=14, allow_redirects=True)
        if r.status_code != 200:
            return result
        text = r.text

        # Extract pain quotes from review snippets in the HTML
        pain_quote = _extract_pain_quote(text)
        result["pain_quote"] = pain_quote[:200] if pain_quote else ""

        # Extract phone
        phones = PHONE_RE.findall(text)
        if phones:
            result["phone"] = phones[0]

        # Extract email (rare on Yelp, but sometimes in schema/meta)
        emails = EMAIL_RE.findall(text)
        business_email = ""
        JUNK = {"yelp.com", "example.com", "sentry.io", "google.com", "apple.com"}
        for e in emails:
            domain = e.split("@")[-1].lower()
            if domain not in JUNK and len(e) < 80:
                business_email = e
                break
        result["email"] = business_email

    except Exception:
        pass
    return result


def _extract_business_name(url: str, html: str) -> str:
    # Try to get from og:title or h1
    m = re.search(r'<title[^>]*>([^<|]+)', html)
    if m:
        name = m.group(1).strip()
        name = re.sub(r'\s*[-|]\s*Yelp.*', '', name).strip()
        return name
    # Fallback: parse from URL slug
    slug = url.split("/biz/")[-1].split("?")[0]
    return slug.replace("-", " ").title()


def run():
    existing_urls = set()
    if OUTPUT.exists():
        with open(OUTPUT, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                existing_urls.add(row.get("yelp_url", ""))

    print("[HOT LEADS] Scanning Yelp for missed-call complaints in CA service businesses")

    new_rows = []

    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            print("[ERROR] ddgs / duckduckgo_search not installed")
            return

    for query in SEARCHES:
        print(f"\n  Query: {query[:80]}...")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=6))

            for result in results:
                url = result.get("href", "")
                if "yelp.com/biz" not in url:
                    continue
                if url in existing_urls:
                    continue

                title = result.get("title", "")
                snippet = result.get("body", "")
                niche = _detect_niche(title + " " + snippet)

                # Check the snippet for pain keywords before visiting the page
                pain_quote = _extract_pain_quote(snippet)

                page_data = _scrape_yelp_page(url)
                if not page_data["pain_quote"] and not pain_quote:
                    continue  # skip if no pain signal found

                pain_final = page_data["pain_quote"] or pain_quote

                row = {
                    "business_name": _extract_business_name(url, title),
                    "email": page_data["email"],
                    "phone": page_data["phone"],
                    "yelp_url": url,
                    "niche": niche,
                    "pain_quote": pain_final[:200],
                    "found_at": datetime.now().strftime("%Y-%m-%d"),
                }
                new_rows.append(row)
                existing_urls.add(url)
                print(f"  + {row['business_name']} ({niche}) — {pain_final[:60]}...")

            time.sleep(random.uniform(3.0, 6.0))

        except Exception as e:
            print(f"  [WARN] {e}")
            time.sleep(8)

    if new_rows:
        file_exists = OUTPUT.exists() and OUTPUT.stat().st_size > 0
        with open(OUTPUT, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)
        print(f"\n[HOT LEADS] Done — {len(new_rows)} hot leads saved to {OUTPUT.name}")
    else:
        print(f"\n[HOT LEADS] No new hot leads found this run.")


if __name__ == "__main__":
    run()
