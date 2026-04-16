"""
Playwright-based scraper for dynamic grant sites.
Targets sites that don't have RSS or public APIs.

Usage:
    from discovery.scraper import scrape_all
    grants = scrape_all()

Run `playwright install chromium` once before using.
"""
import asyncio
import re
from datetime import datetime

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False
    print("[Scraper] Playwright unavailable (not installed or missing libs). Skipping dynamic scrape.")

from .normalizer import normalize, make_external_id

# ─── Scraper Targets ──────────────────────────────────────────────────────────
# Each entry defines how to scrape a specific site.
# Add new targets here to expand coverage.

SCRAPE_TARGETS = [
    {
        "name": "MBDA Business Center Grants",
        "source_key": "mbda.gov",
        "url": "https://www.mbda.gov/page/grant-opportunities",
        "grant_selector": "article, .view-row, .grant-item, h3 a, h2 a",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "desc_selector": "p, .field-content",
    },
    {
        "name": "Hello Alice Grants",
        "source_key": "helloalice.com",
        "url": "https://helloalice.com/grants/",
        "grant_selector": ".grant-card, .opportunity-card, article",
        "title_selector": "h2, h3, .card-title",
        "link_selector": "a",
        "desc_selector": "p, .card-description",
    },
    {
        "name": "Instrumentl Grants (public)",
        "source_key": "instrumentl.com",
        "url": "https://www.instrumentl.com/resources/small-business-grants",
        "grant_selector": "article, .grant-item, .resource-item",
        "title_selector": "h2, h3",
        "link_selector": "a",
        "desc_selector": "p",
    },
]


async def _scrape_target(page, target: dict) -> list[dict]:
    """Scrape a single target page."""
    grants = []

    try:
        await page.goto(target["url"], wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)  # Allow JS to settle

        # Try to find grant cards/items
        items = await page.query_selector_all(target["grant_selector"])

        if not items:
            # Fallback: grab all links that look like grants
            links = await page.query_selector_all("a")
            for link in links:
                text = await link.inner_text()
                href = await link.get_attribute("href") or ""
                combined = (text + " " + href).lower()
                if any(kw in combined for kw in ["grant", "funding", "award", "opportunity"]):
                    raw = {
                        "title": text.strip(),
                        "url": href if href.startswith("http") else target["url"],
                        "description": "",
                        "id": href,
                    }
                    grants.append(normalize(raw, source=target["source_key"]))
            return grants

        for item in items[:30]:  # Cap at 30 per site
            # Extract title
            title_el = await item.query_selector(target.get("title_selector", "h2, h3"))
            title = (await title_el.inner_text()).strip() if title_el else ""

            # Extract link
            link_el = await item.query_selector(target.get("link_selector", "a"))
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    base = re.match(r"https?://[^/]+", target["url"])
                    href = (base.group(0) if base else "") + href

            # Extract description
            desc_el = await item.query_selector(target.get("desc_selector", "p"))
            desc = (await desc_el.inner_text()).strip() if desc_el else ""

            if not title:
                continue

            raw = {
                "title": title,
                "url": href or target["url"],
                "description": desc,
                "id": href or title,
            }
            grants.append(normalize(raw, source=target["source_key"]))

    except Exception as e:
        print(f"[Scraper] Error on {target['name']}: {e}")

    print(f"[Scraper] {target['name']}: {len(grants)} grants")
    return grants


async def _scrape_all_async() -> list[dict]:
    if not PLAYWRIGHT_AVAILABLE:
        return []

    all_grants = []
    seen = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set realistic headers
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        for target in SCRAPE_TARGETS:
            grants = await _scrape_target(page, target)
            for g in grants:
                eid = g["external_id"]
                if eid not in seen:
                    seen.add(eid)
                    all_grants.append(g)

        await browser.close()

    return all_grants


def scrape_all() -> list[dict]:
    """Synchronous wrapper for async scraper."""
    if not PLAYWRIGHT_AVAILABLE:
        print("[Scraper] Playwright unavailable, skipping dynamic scrape.")
        return []

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _scrape_all_async())
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(_scrape_all_async())
    except Exception as e:
        print(f"[Scraper] Fatal error: {e}")
        return []
