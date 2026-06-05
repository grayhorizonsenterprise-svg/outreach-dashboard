"""
phone_finder.py — Gray Horizons Enterprise
Scrapes phone numbers from business websites in outreach_queue.csv.
Run once to populate the phone column so vapi_agent.py can make follow-up calls.

Usage: python phone_finder.py
"""

import csv
import re
import time
import requests
from pathlib import Path

QUEUE_CSV = Path(__file__).parent / "outreach_queue.csv"
PHONE_RE  = re.compile(r'(\+?1?\s*[-.]?\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})')
HEADERS   = {"User-Agent": "Mozilla/5.0 (compatible; GHE-PhoneFinder/1.0)"}


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def fetch_phone(url: str) -> str:
    if not url or not url.startswith("http"):
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        matches = PHONE_RE.findall(r.text)
        for m in matches:
            p = clean_phone(m)
            if p:
                return p
    except Exception:
        pass
    return ""


def run():
    rows = []
    fieldnames = []

    with open(QUEUE_CSV, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "phone" not in fieldnames:
        fieldnames.append("phone")

    updated = 0
    for i, row in enumerate(rows):
        if row.get("phone", "").strip():
            continue

        website = row.get("website", "").strip()
        if not website:
            continue

        phone = fetch_phone(website)
        if phone:
            row["phone"] = phone
            updated += 1
            print(f"[{i+1}/{len(rows)}] {row.get('company','?')} → {phone}")
        else:
            print(f"[{i+1}/{len(rows)}] {row.get('company','?')} → no phone found")

        time.sleep(0.5)

    with open(QUEUE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows := rows)

    print(f"\nDone. Phones found: {updated} / {len(rows)}")


if __name__ == "__main__":
    run()
