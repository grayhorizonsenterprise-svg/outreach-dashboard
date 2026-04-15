"""
RSS feed ingestion for grant opportunities.
Pulls from Grants.gov RSS and other public grant feeds.
"""
import feedparser
import requests
from datetime import datetime
from .normalizer import normalize, make_external_id

RSS_SOURCES = [
    {
        "name": "Grants.gov New Opportunities",
        "url": "https://www.grants.gov/rss/GG_NewOpps.xml",
        "source_key": "grants.gov.rss",
    },
    {
        "name": "SBA Grants & Funding",
        "url": "https://www.sba.gov/rss.xml",
        "source_key": "sba.gov",
    },
    {
        "name": "USDA Rural Development",
        "url": "https://www.rd.usda.gov/rss.xml",
        "source_key": "usda.rd",
    },
]

# Additional curated feeds can be added here
EXTRA_FEEDS: list[dict] = []


def fetch_feed(feed_config: dict) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    url = feed_config["url"]
    source_key = feed_config["source_key"]

    try:
        # feedparser handles most RSS/Atom formats
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"[RSS] Failed to parse {url}: {feed.bozo_exception}")
            return []
    except Exception as e:
        print(f"[RSS] Error fetching {url}: {e}")
        return []

    grants = []
    for entry in feed.entries:
        raw = {
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "description": entry.get("summary", entry.get("description", "")),
            "published": entry.get("published", ""),
            "id": entry.get("id", entry.get("link", "")),
        }

        # Skip entries without a title
        if not raw["title"]:
            continue

        # Only include entries that look like grants
        combined = (raw["title"] + " " + raw["description"]).lower()
        grant_keywords = ["grant", "funding", "award", "opportunity", "assistance", "sbir", "sttr"]
        if not any(kw in combined for kw in grant_keywords):
            continue

        grant = normalize(raw, source=source_key)
        grants.append(grant)

    print(f"[RSS] {feed_config['name']}: {len(grants)} grant entries")
    return grants


def fetch_all() -> list[dict]:
    """Fetch all configured RSS feeds."""
    all_sources = RSS_SOURCES + EXTRA_FEEDS
    seen = set()
    results = []

    for feed_config in all_sources:
        grants = fetch_feed(feed_config)
        for g in grants:
            eid = g["external_id"]
            if eid not in seen:
                seen.add(eid)
                results.append(g)

    print(f"[RSS] Total unique grants from feeds: {len(results)}")
    return results
