"""
Auto-Application / Assist Layer

Tries to detect submission type (API vs form) and either:
  a) Submits via API if available
  b) Auto-fills form fields via Playwright
  c) Returns a guided checklist if full automation isn't possible

IMPORTANT: Always review auto-filled forms before final submission.
"""
import asyncio
import json
import re
from pathlib import Path

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from generation.generator import generate_checklist


# ─── Form field patterns ──────────────────────────────────────────────────────
FIELD_MAP = {
    # Applicant info
    "business_name": ["business name", "organization name", "company name", "applicant name"],
    "business_type": ["business type", "entity type", "organization type"],
    "ein": ["ein", "tax id", "employer identification"],
    "address": ["address", "street", "mailing address"],
    "city": ["city"],
    "state": ["state"],
    "zip": ["zip", "postal"],
    "phone": ["phone", "telephone"],
    "email": ["email"],
    "website": ["website", "url"],
    # Project info
    "mission_statement": ["mission", "mission statement"],
    "business_description": ["description", "business description", "organization description", "about"],
    "use_of_funds": ["use of funds", "how will funds be used", "budget narrative", "project budget"],
    "impact_statement": ["impact", "expected outcomes", "project goals", "what impact"],
    "amount_requested": ["amount requested", "funding requested", "grant amount"],
    # Other
    "employees": ["number of employees", "full-time employees", "staff count"],
    "annual_revenue": ["annual revenue", "gross revenue", "annual sales"],
    "founded_year": ["year founded", "date established", "year established"],
}


def _load_profile() -> dict:
    profile_path = Path(__file__).parent.parent / "user_profile.json"
    if profile_path.exists():
        with open(profile_path) as f:
            return json.load(f)
    return {}


def _build_fill_data(profile: dict, application: dict, amount_requested: int = 0) -> dict:
    """Build a flat dict of all fill values from profile + application."""
    loc = profile.get("location", {})
    return {
        "business_name": profile.get("business_name", ""),
        "business_type": profile.get("business_type", ""),
        "ein": profile.get("ein", ""),
        "address": loc.get("address", ""),
        "city": loc.get("city", ""),
        "state": loc.get("state", ""),
        "zip": loc.get("zip", ""),
        "phone": profile.get("phone", ""),
        "email": profile.get("email", ""),
        "website": profile.get("website", ""),
        "mission_statement": application.get("mission_statement", ""),
        "business_description": application.get("business_description", ""),
        "use_of_funds": application.get("use_of_funds", ""),
        "impact_statement": application.get("impact_statement", ""),
        "amount_requested": str(amount_requested or profile.get("min_grant_amount", 0)),
        "employees": str(profile.get("employees", "")),
        "annual_revenue": str(profile.get("annual_revenue", "")),
        "founded_year": str(profile.get("founded_year", "")),
    }


def detect_submission_type(url: str) -> str:
    """
    Attempt to detect submission type from URL patterns.
    Returns: 'api', 'form', or 'external'
    """
    url_lower = url.lower()

    # Known API submission grants
    api_patterns = ["grants.gov", "api.grants.gov", "apply.grants.gov"]
    if any(p in url_lower for p in api_patterns):
        return "api"

    # External portals (Submittable, JotForm, Typeform, etc.)
    form_platforms = ["submittable", "jotform", "typeform", "formstack", "cognito", "wufoo", "airtable.com/shr"]
    if any(p in url_lower for p in form_platforms):
        return "form"

    # PDF / Word doc applications
    if any(ext in url_lower for ext in [".pdf", ".doc", ".docx"]):
        return "document"

    return "form"  # Default assumption


async def _autofill_form(url: str, fill_data: dict) -> dict:
    """
    Use Playwright to open the form URL and attempt to autofill fields.
    Returns result with filled_count and screenshot path.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright not installed", "filled_count": 0}

    filled_count = 0
    screenshot_path = "form_prefilled.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible so user can review
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Get all input, textarea, select elements
            inputs = await page.query_selector_all("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select")

            for inp in inputs:
                # Get identifying attributes
                label_text = ""
                placeholder = await inp.get_attribute("placeholder") or ""
                name_attr = await inp.get_attribute("name") or ""
                id_attr = await inp.get_attribute("id") or ""
                aria_label = await inp.get_attribute("aria-label") or ""

                # Try to find associated label
                if id_attr:
                    label_el = await page.query_selector(f"label[for='{id_attr}']")
                    if label_el:
                        label_text = await label_el.inner_text()

                search_text = " ".join([label_text, placeholder, name_attr, id_attr, aria_label]).lower()

                # Match against our field map
                matched_key = None
                for field_key, patterns in FIELD_MAP.items():
                    if any(pat in search_text for pat in patterns):
                        matched_key = field_key
                        break

                if matched_key and fill_data.get(matched_key):
                    inp_type = await inp.get_attribute("type") or "text"
                    tag_name = await inp.evaluate("el => el.tagName.toLowerCase()")

                    try:
                        if tag_name == "select":
                            await inp.select_option(label=fill_data[matched_key])
                        elif inp_type in ["text", "email", "tel", "url", "number"] or tag_name == "textarea":
                            await inp.fill(fill_data[matched_key])
                            filled_count += 1
                    except Exception:
                        pass

            # Take screenshot for review
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[Submitter] Filled {filled_count} fields. Screenshot saved: {screenshot_path}")
            print("[Submitter] Browser left open for manual review. Close it when done.")

            # Wait for user to review (30 seconds)
            await page.wait_for_timeout(30000)

        except Exception as e:
            await browser.close()
            return {"success": False, "error": str(e), "filled_count": 0}

        await browser.close()

    return {
        "success": True,
        "filled_count": filled_count,
        "screenshot": screenshot_path,
        "note": "Review form before submitting. Auto-fill is a starting point only."
    }


def autofill_form(url: str, application: dict, profile: dict = None) -> dict:
    """Synchronous wrapper."""
    if profile is None:
        profile = _load_profile()

    fill_data = _build_fill_data(profile, application)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _autofill_form(url, fill_data))
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(_autofill_form(url, fill_data))
    except Exception as e:
        return {"success": False, "error": str(e), "filled_count": 0}


def prepare_submission(grant: dict, application: dict, profile: dict = None) -> dict:
    """
    High-level function: detect type → autofill or generate guide.

    Returns:
        {
            "submission_type": "form" | "api" | "document",
            "auto_filled": bool,
            "checklist": [...],
            "result": {...}
        }
    """
    if profile is None:
        profile = _load_profile()

    url = grant.get("url", "")
    sub_type = detect_submission_type(url)
    checklist = generate_checklist(grant)

    print(f"[Submitter] Grant: {grant.get('name')} | Type: {sub_type}")

    if sub_type == "form" and url:
        result = autofill_form(url, application, profile)
        return {
            "submission_type": "form",
            "auto_filled": result.get("success", False),
            "filled_fields": result.get("filled_count", 0),
            "checklist": checklist,
            "result": result,
        }

    # For API or document types — return guided checklist only
    return {
        "submission_type": sub_type,
        "auto_filled": False,
        "checklist": checklist,
        "result": {"note": f"Manual submission required. Follow checklist. URL: {url}"},
    }
