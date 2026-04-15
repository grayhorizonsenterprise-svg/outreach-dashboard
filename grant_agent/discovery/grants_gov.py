"""
Grants.gov API v2 — real-time and bulk grant discovery.
No API key required.

Docs: https://api.grants.gov/v2/api-docs
"""
import requests
from .normalizer import normalize, make_external_id

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
    "black owned business",
    "economic development",
    "workforce development",
    "community development",
    "technology",
    "entrepreneurship",
    "construction",
    "infrastructure",
    "AI innovation",
    "automation startup",
    "SBIR",
    "STTR",
    "minority technology",
    "underrepresented entrepreneur",
    "disadvantaged business",
    "innovation grant",
    "SaaS small business",
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


# ── Curated fallback grants — always returned even when API fails ─────────────
# These are real, active programs. Update URLs/amounts if they change.

CURATED_GRANTS = [
    {
        "source": "curated",
        "external_id": "curated-sbir-phase1",
        "name": "SBIR Phase I — Small Business Innovation Research",
        "agency": "SBA / Federal",
        "amount_min": 50000,
        "amount_max": 275000,
        "deadline": None,
        "eligibility": "Small businesses with fewer than 500 employees focused on R&D",
        "description": "Federal program funding early-stage R&D for small tech businesses. AI, automation, SaaS, and deep-tech startups are strong fits.",
        "url": "https://www.sbir.gov",
        "category": "technology",
        "tags": ["sbir", "small business", "ai", "technology", "innovation", "r&d"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-mbda-business-center",
        "name": "MBDA Business Center Grant Program",
        "agency": "Minority Business Development Agency",
        "amount_min": 50000,
        "amount_max": 500000,
        "deadline": None,
        "eligibility": "Minority-owned businesses including Black-owned firms",
        "description": "MBDA provides capital access, contracts, and market expansion support for minority-owned businesses in technology and construction.",
        "url": "https://www.mbda.gov",
        "category": "minority business",
        "tags": ["minority", "black", "mbda", "business development", "entrepreneurship"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-sba-8a",
        "name": "SBA 8(a) Business Development Program",
        "agency": "Small Business Administration",
        "amount_min": 0,
        "amount_max": 250000,
        "deadline": None,
        "eligibility": "Socially and economically disadvantaged small businesses (Black-owned qualifies)",
        "description": "Federal contracting set-aside program giving minority-owned small businesses access to sole-source contracts up to $4.5M.",
        "url": "https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program",
        "category": "minority business",
        "tags": ["8a", "minority", "black", "small business", "disadvantaged", "contracting"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-ca-cedap",
        "name": "California CEDAP — Capital & Tech Access Grant",
        "agency": "CA Office of the Small Business Advocate",
        "amount_min": 5000,
        "amount_max": 75000,
        "deadline": None,
        "eligibility": "California small businesses, priority for underserved communities",
        "description": "California's grant for small businesses in technology, construction, and community development sectors. Based in Rialto/Inland Empire qualifies.",
        "url": "https://calosba.ca.gov",
        "category": "small business",
        "tags": ["california", "small business", "technology", "minority", "community", "inland empire"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-hello-alice-black",
        "name": "Hello Alice — Black Business Owners Grant",
        "agency": "Hello Alice",
        "amount_min": 500,
        "amount_max": 10000,
        "deadline": None,
        "eligibility": "Black-owned businesses in the United States",
        "description": "Rolling grant program for Black business owners. Focus on technology, innovation, and community impact.",
        "url": "https://helloalice.com/grants",
        "category": "minority business",
        "tags": ["black", "minority", "small business", "entrepreneur", "equity"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-google-black-founders",
        "name": "Google for Startups — Black Founders Fund",
        "agency": "Google",
        "amount_min": 50000,
        "amount_max": 100000,
        "deadline": None,
        "eligibility": "Black-founded tech startups in the United States",
        "description": "Non-dilutive cash awards plus Google Cloud credits for Black-founded technology and SaaS startups.",
        "url": "https://startup.google.com/programs/black-founders-fund/",
        "category": "technology",
        "tags": ["black", "technology", "startup", "ai", "saas", "software"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-nsf-sbir",
        "name": "NSF America's Seed Fund (SBIR/STTR)",
        "agency": "National Science Foundation",
        "amount_min": 50000,
        "amount_max": 256000,
        "deadline": None,
        "eligibility": "US-based small businesses with deep tech or research focus",
        "description": "NSF SBIR funds AI, machine learning, automation, and software companies at Phase I ($256K) and Phase II ($1M+).",
        "url": "https://seedfund.nsf.gov",
        "category": "technology",
        "tags": ["sbir", "sttr", "technology", "ai", "innovation", "research", "federal"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-comcast-rise",
        "name": "Comcast RISE Investment Fund",
        "agency": "Comcast",
        "amount_min": 10000,
        "amount_max": 10000,
        "deadline": None,
        "eligibility": "Small businesses owned by people of color with 3+ years in operation",
        "description": "Monetary grants plus marketing, technology, and media resources for minority-owned small businesses.",
        "url": "https://www.comcastrise.com",
        "category": "minority business",
        "tags": ["minority", "black", "small business", "technology", "community"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-fedex-grant",
        "name": "FedEx Small Business Grant Contest",
        "agency": "FedEx",
        "amount_min": 2500,
        "amount_max": 50000,
        "deadline": None,
        "eligibility": "US-based small businesses with under $10M revenue",
        "description": "Annual grant contest awarding up to $50,000 to innovative small businesses.",
        "url": "https://www.fedex.com/en-us/small-business/grant.html",
        "category": "small business",
        "tags": ["small business", "startup", "entrepreneur", "technology"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-verizon-digital-ready",
        "name": "Verizon Small Business Digital Ready Grant",
        "agency": "Verizon",
        "amount_min": 10000,
        "amount_max": 10000,
        "deadline": None,
        "eligibility": "Small businesses with under 25 employees focused on digital adoption",
        "description": "Grants for small businesses embracing digital technology, automation, and smart business tools.",
        "url": "https://digitalreadysmallbusiness.verizon.com",
        "category": "technology",
        "tags": ["small business", "technology", "digital", "automation", "community"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-doc-mbda",
        "name": "DOC Minority Business Development Grant",
        "agency": "Department of Commerce",
        "amount_min": 50000,
        "amount_max": 300000,
        "deadline": None,
        "eligibility": "Minority-owned businesses and MBDAs",
        "description": "Federal Department of Commerce grants for minority business development, technology adoption, and economic growth.",
        "url": "https://www.mbda.gov/page/grant-opportunities",
        "category": "minority business",
        "tags": ["minority", "black", "economic development", "business", "federal"],
        "posted_date": None,
    },
    {
        "source": "curated",
        "external_id": "curated-nmsdc-innovation",
        "name": "NMSDC Innovation in Business Award Grant",
        "agency": "National Minority Supplier Development Council",
        "amount_min": 5000,
        "amount_max": 25000,
        "deadline": None,
        "eligibility": "NMSDC-certified minority-owned businesses",
        "description": "Annual award for minority-owned businesses demonstrating innovation in technology, operations, or market expansion.",
        "url": "https://nmsdc.org",
        "category": "minority business",
        "tags": ["minority", "black", "innovation", "technology", "supplier"],
        "posted_date": None,
    },
]


def bulk_scan(keywords: list[str] = None) -> list[dict]:
    """Run search for multiple relevant keywords, always include curated fallbacks."""
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

    # Always include curated grants (API fallback + guaranteed quality leads)
    for g in CURATED_GRANTS:
        eid = g["external_id"]
        if eid not in seen:
            seen.add(eid)
            all_grants.append(g)

    print(f"[Grants.gov] Bulk scan complete: {len(all_grants)} unique grants ({len(CURATED_GRANTS)} curated)")
    return all_grants
