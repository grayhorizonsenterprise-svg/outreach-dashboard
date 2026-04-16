"""
Normalizes raw grant data from any source into a standard schema.
"""
from __future__ import annotations

import re
import hashlib
from datetime import datetime


AMOUNT_PATTERNS = [
    r'\$[\d,]+(?:\.\d{2})?',
    r'(?:up to|maximum|max\.?)\s+\$[\d,]+',
    r'\$[\d,]+\s*[-–]\s*\$[\d,]+',
]


def parse_amount(text: str) -> tuple[int, int]:
    """Extract min/max dollar amounts from a string."""
    if not text:
        return 0, 0

    text = str(text)
    numbers = re.findall(r'[\d,]+', text.replace('$', ''))
    nums = []
    for n in numbers:
        try:
            nums.append(int(n.replace(',', '')))
        except ValueError:
            pass

    if not nums:
        return 0, 0
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)


def normalize_date(date_str: str) -> str | None:
    """Try to parse various date formats into YYYY-MM-DD."""
    if not date_str:
        return None

    date_str = str(date_str).strip()
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:20], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str  # Return raw if unparseable


def make_external_id(source: str, url: str, name: str) -> str:
    """Generate a stable dedup ID from source + url."""
    raw = f"{source}:{url or name}"
    return hashlib.md5(raw.encode()).hexdigest()


def normalize(raw: dict, source: str) -> dict:
    """
    Convert any raw grant dict to the standard schema.

    Standard schema:
        source, external_id, name, amount_min, amount_max,
        deadline, eligibility, description, url, category,
        tags, posted_date
    """
    name = (raw.get("title") or raw.get("name") or raw.get("opportunityTitle") or "").strip()
    url = raw.get("url") or raw.get("link") or raw.get("opportunityUrl") or ""
    agency = (raw.get("agencyName") or raw.get("agency") or raw.get("agencyCode") or "").strip()

    # Amount parsing
    amount_str = (
        raw.get("awardCeiling") or
        raw.get("amount") or
        raw.get("award_amount") or
        raw.get("totalFundingAmount") or
        ""
    )
    amount_floor_str = raw.get("awardFloor") or raw.get("amount_min") or ""

    amount_max = raw.get("awardCeiling") or raw.get("amount_max") or 0
    amount_min = raw.get("awardFloor") or raw.get("amount_min") or 0

    try:
        amount_max = int(str(amount_max).replace(",", "").replace("$", "")) if amount_max else 0
    except (ValueError, TypeError):
        _, amount_max = parse_amount(str(amount_str))

    try:
        amount_min = int(str(amount_min).replace(",", "").replace("$", "")) if amount_min else 0
    except (ValueError, TypeError):
        amount_min, _ = parse_amount(str(amount_str))

    # Deadline
    deadline_raw = (
        raw.get("closeDate") or
        raw.get("deadline") or
        raw.get("applicationDeadline") or
        raw.get("due_date") or
        ""
    )
    deadline = normalize_date(deadline_raw)

    # Posted date
    posted_raw = (
        raw.get("postDate") or
        raw.get("openDate") or
        raw.get("posted_date") or
        raw.get("published") or
        ""
    )
    posted_date = normalize_date(posted_raw)

    # Description / Eligibility
    description = (
        raw.get("description") or
        raw.get("synopsis") or
        raw.get("summary") or
        raw.get("opportunityDescription") or
        ""
    ).strip()

    eligibility = (
        raw.get("eligibility") or
        raw.get("eligibleApplicants") or
        raw.get("applicantEligibility") or
        ""
    ).strip()

    category = (
        raw.get("category") or
        raw.get("opportunityCategory") or
        raw.get("fundingActivity") or
        ""
    ).strip()

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    external_id = (
        raw.get("opportunityId") or
        raw.get("id") or
        raw.get("external_id") or
        make_external_id(source, url, name)
    )

    return {
        "source": source,
        "external_id": str(external_id),
        "name": name,
        "agency": agency,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "deadline": deadline,
        "eligibility": eligibility,
        "description": description[:2000] if description else "",
        "url": url,
        "category": category,
        "tags": tags,
        "posted_date": posted_date,
    }
