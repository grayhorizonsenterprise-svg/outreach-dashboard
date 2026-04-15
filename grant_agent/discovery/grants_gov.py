"""
Grants.gov API v2 — real-time and bulk grant discovery.
No API key required.

Docs: https://api.grants.gov/v2/api-docs
"""
import requests
from .normalizer import normalize

GRANTS_GOV_SEARCH = "https://api.grants.gov/v1/api/search2"

DEFAULT_PARAMS = {
    "keyword": "",
    "oppStatuses": ["posted"],
    "rows": 25,
    "startRecordNum": 0,
}

# Funding activity keywords relevant to small/minority businesses
RELEVANT_KEYWORDS = [
    "small business",
    "minority business",
    "economic development",
    "workforce development",
    "community development",
    "technology",
    "entrepreneurship",
    "construction",
    "infrastructure",
]


def search(keyword: str = "", rows: int = 25, offset: int = 0) -> list[dict]:
    """Search Grants.gov and return normalized grant list."""
    params = {
        **DEFAULT_PARAMS,
        "keyword": keyword,
        "rows": rows,
        "startRecordNum": offset,
    }

    try:
        resp = requests.post(
            GRANTS_GOV_SEARCH,
            json=params,
            timeout=20,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[Grants.gov] Raw keys: {list(data.keys())}")
    except Exception as e:
        print(f"[Grants.gov] Error: {e}")
        return []

    # API returns either data.oppHits or data.data.oppHits depending on version
    opportunities = (
        data.get("oppHits") or
        data.get("data", {}).get("oppHits") or
        []
    )
    results = []
    for opp in opportunities:
        grant = normalize(opp, source="grants.gov")
        results.append(grant)

    print(f"[Grants.gov] '{keyword}' → {len(results)} grants")
    return results


def bulk_scan(keywords: list[str] = None) -> list[dict]:
    """Run search for multiple relevant keywords, dedup by external_id."""
    if keywords is None:
        keywords = RELEVANT_KEYWORDS

    seen = set()
    all_grants = []

    for kw in keywords:
        grants = search(keyword=kw, rows=20)
        for g in grants:
            eid = g["external_id"]
            if eid not in seen:
                seen.add(eid)
                all_grants.append(g)

    print(f"[Grants.gov] Bulk scan complete: {len(all_grants)} unique grants")
    return all_grants
