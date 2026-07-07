"""
send_sms_outreach.py — Gray Horizons Enterprise
Sends SMS outreach to contractor phone numbers via TextBelt.

Usage:
  python send_sms_outreach.py --dry-run   (preview messages, no sends)
  python send_sms_outreach.py             (send to all pending rows with phone numbers)

Input: hot_leads.csv (from scrape_yelp_hot_leads.py) or any CSV with:
  phone, niche, business_name, status columns

TextBelt free tier: 1 SMS/day free. Paid: ~$0.01/text with key from textbelt.com
"""

import os
import sys
import csv
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEXTBELT_KEY = os.getenv("TEXTBELT_API_KEY", "textbelt")
FROM_NAME    = "Curtis Gardner"
DEMO_LINE    = "+19036278040"
CALENDLY     = "https://calendly.com/grayhorizonsenterprise/30min"

CSV_PATH = Path(os.path.dirname(__file__)) / "hot_leads.csv"

# Keep SMS to 160 chars or under to avoid multi-part billing
MESSAGES = {
    "hvac": (
        "Hey — HVAC businesses in CA miss 40%+ of after-hours calls. "
        "Hear what a fix sounds like: {demo_line} (90 sec, AI answers live). "
        "Curtis @ Gray Horizons"
    ),
    "plumbing": (
        "Hey — emergency plumbing calls go to whoever answers first. "
        "Hear the fix: {demo_line} (90 sec AI demo). "
        "Curtis @ Gray Horizons"
    ),
    "roofing": (
        "Hey — roofing companies miss storm leads when they do not answer fast. "
        "Hear the fix: {demo_line} (90 sec AI demo). "
        "Curtis @ Gray Horizons"
    ),
    "solar": (
        "Hey — solar leads book with the first company that responds. "
        "Hear what 15-second response sounds like: {demo_line}. "
        "Curtis @ Gray Horizons"
    ),
    "dental": (
        "Hey — dental offices miss 22+ calls/week on average. "
        "Hear a fix in 90 sec: {demo_line}. "
        "Curtis @ Gray Horizons"
    ),
    "other": (
        "Hey — service businesses miss 30-40% of inbound calls. "
        "Hear a 90-sec AI demo: {demo_line}. "
        "Curtis @ Gray Horizons"
    ),
}


def _clean_phone(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return ""


def _send_sms(phone: str, message: str) -> bool:
    try:
        r = requests.post(
            "https://textbelt.com/text",
            data={"phone": phone, "message": message, "key": TEXTBELT_KEY},
            timeout=15,
        )
        data = r.json()
        if data.get("success"):
            remaining = data.get("quotaRemaining", "?")
            print(f"  [SMS SENT] {phone} | quota remaining: {remaining}")
            return True
        else:
            print(f"  [SMS FAIL] {phone} — {data.get('error', 'unknown error')}")
            return False
    except Exception as e:
        print(f"  [SMS ERROR] {phone} — {e}")
        return False


def run(dry_run: bool = False):
    if not CSV_PATH.exists():
        print(f"[ERROR] {CSV_PATH} not found. Run scrape_yelp_hot_leads.py first.")
        return

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    if "status" not in fieldnames:
        fieldnames.append("status")
        for row in rows:
            if "status" not in row:
                row["status"] = "pending"

    pending = [
        r for r in rows
        if r.get("status", "pending").strip().lower() == "pending"
        and r.get("phone", "").strip()
    ]
    print(f"[SMS] {len(pending)} pending with phone numbers of {len(rows)} total")

    if dry_run:
        print("\n[DRY RUN] Messages that would be sent:\n")
        for row in pending[:5]:
            phone = _clean_phone(row.get("phone", ""))
            niche = row.get("niche", "other")
            template = MESSAGES.get(niche, MESSAGES["other"])
            msg = template.format(demo_line=DEMO_LINE)
            print(f"  TO: {phone} | NICHE: {niche}")
            print(f"  MSG ({len(msg)} chars): {msg}")
            print()
        print("[DRY RUN] Remove --dry-run to send.")
        return

    sent = 0
    errors = 0

    for row in rows:
        if row.get("status", "pending").strip().lower() != "pending":
            continue
        phone_raw = row.get("phone", "").strip()
        if not phone_raw:
            continue

        phone = _clean_phone(phone_raw)
        if not phone:
            print(f"  [SKIP] Bad phone: {phone_raw}")
            row["status"] = "skipped_phone"
            continue

        niche = row.get("niche", "other")
        template = MESSAGES.get(niche, MESSAGES["other"])
        msg = template.format(demo_line=DEMO_LINE)

        ok = _send_sms(phone, msg)
        if ok:
            row["status"] = "sms_sent"
            sent += 1
        else:
            row["status"] = "sms_error"
            errors += 1

        time.sleep(2.0)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[SMS] Done — Sent: {sent} | Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
