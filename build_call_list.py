"""
build_call_list.py — Gray Horizons Enterprise
Fast phone enrichment on existing leads.
Visits each company website, extracts phone number.
Outputs call_list.csv — ready to import into Bland.ai or call manually.

Run locally:
  python build_call_list.py

Takes ~10-20 minutes. Generates 100-300 leads with phone numbers.
"""

import pandas as pd
import requests
import re
import os
import sys
import time
import random
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE    = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE   = os.path.join(DATA_DIR, "call_list.csv")

WORKERS = 12
TIMEOUT = 7

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

PHONE_REGEX = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")

NICHE_PRIORITY = ["hvac", "plumbing", "roofing", "dental", "contractor", "landscaping", "hoa", "chiropractic", "auto", "salon"]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def clean_phone(raw: str) -> str:
    digits = re.sub(r"[^\d]", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) == 10 and digits[0] not in ("0", "1"):
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return ""


def extract_phone_from_html(html: str) -> str:
    # Try tel: links first — most reliable
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("tel:"):
            digits = re.sub(r"[^\d]", "", href[4:])
            p = clean_phone(digits)
            if p:
                return p

    # Fall back to regex on full HTML
    for m in PHONE_REGEX.findall(html):
        p = clean_phone(m)
        if p:
            return p
    return ""


def fetch_phone(args):
    i, row = args
    site = str(row.get("website", "")).strip()
    if not site or site in ("nan", "None", ""):
        return (i, "")
    try:
        r = requests.get(site.rstrip("/"), headers=get_headers(), timeout=TIMEOUT, verify=False, allow_redirects=True)
        if r.status_code == 200:
            return (i, extract_phone_from_html(r.text))
    except Exception:
        pass
    return (i, "")


def run():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] {INPUT_FILE} not found")
        return

    df = pd.read_csv(INPUT_FILE).fillna("")

    # Prioritize by niche and email availability
    df["niche_rank"] = df["niche"].apply(lambda n: NICHE_PRIORITY.index(n) if n in NICHE_PRIORITY else 99)
    df["has_email"]  = (df["email"].str.strip() != "").astype(int)
    df = df.sort_values(["has_email", "niche_rank"], ascending=[False, True])

    # Take top 500 leads to enrich — balanced across niches
    samples = []
    for niche in NICHE_PRIORITY:
        niche_leads = df[df["niche"] == niche].head(60)
        samples.append(niche_leads)
    sample = pd.concat(samples, ignore_index=True).drop_duplicates(subset=["website"])
    sample = sample[sample["website"].str.strip() != ""].head(500)

    print(f"[CALL LIST] Enriching {len(sample)} leads for phone numbers ({WORKERS} workers)...")
    print("[CALL LIST] This takes 10-15 minutes. Go get a coffee.\n")

    phones = {}
    done   = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_phone, (i, row)): i for i, row in sample.iterrows()}
        for future in as_completed(futures):
            i, phone = future.result()
            phones[i] = phone
            done += 1
            if done % 25 == 0:
                found = sum(1 for p in phones.values() if p)
                print(f"  [{done}/{len(sample)}] phones found so far: {found}")

    sample["phone"] = sample.index.map(lambda i: phones.get(i, ""))

    # Only keep leads with phones
    call_list = sample[sample["phone"] != ""].copy()
    call_list  = call_list[["company", "phone", "email", "niche", "location", "website"]]
    call_list  = call_list.sort_values("niche")

    call_list.to_csv(OUTPUT_FILE, index=False)

    print(f"\n[DONE] {len(call_list)} leads with phone numbers saved to call_list.csv")
    print()
    print("Breakdown by niche:")
    for niche, count in call_list["niche"].value_counts().items():
        has_email = (call_list[call_list["niche"] == niche]["email"] != "").sum()
        print(f"  {niche.upper():14s}: {count:3d} leads  ({has_email} with email + phone)")

    print()
    print("Top 10 leads ready to call:")
    top = call_list[call_list["email"] != ""].head(10)
    for _, row in top.iterrows():
        print(f"  {row['company'][:35]:35s} | {row['phone']} | {row['niche']} | {row['email']}")


if __name__ == "__main__":
    run()
