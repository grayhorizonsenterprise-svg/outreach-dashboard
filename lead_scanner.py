"""
lead_scanner.py — Gray Horizons Enterprise
Continuous multi-source lead scanner. Runs independently — feeds ALL engine queues.
Sources: DuckDuckGo, LinkedIn (via DDG), Twitter/X mentions, Reddit business owners.
Runs in a loop with rate-limit-safe pausing. Add to Task Scheduler separately.

Schedule: run every 4 hours via Task Scheduler for continuous fresh leads.
Usage: python lead_scanner.py
"""

import os
import sys
import time
import random
import re
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = DATA_DIR / "lead_scanner_log.txt"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_EMAILS = {
    "example", "test@", "noreply", "no-reply", "info@info", "admin@admin",
    "support@support", "contact@contact", "help@help",
}

# ─── Queue map — each lead type feeds the right script's queue ────────────────
QUEUE_MAP = {
    "main":          DATA_DIR / "prospects_raw.csv",
    "signals":       DATA_DIR / "signals_queue.csv",
    "missed_call":   DATA_DIR / "missed_call_queue.csv",
    "review":        DATA_DIR / "review_queue.csv",
    "gbp":           DATA_DIR / "gbp_queue.csv",
    "chatbot":       DATA_DIR / "chatbot_queue.csv",
    "voice":         DATA_DIR / "voice_queue.csv",
    "reactivation":  DATA_DIR / "reactivation_queue.csv",
    "social":        DATA_DIR / "social_queue.csv",
    "website":       DATA_DIR / "website_queue.csv",
    "sms":           DATA_DIR / "sms_queue.csv",
    "grant":         DATA_DIR / "grant_queue.csv",
    "ghl":           DATA_DIR / "ghl_blast_queue.csv",
    "tradingview":   DATA_DIR / "tradingview_queue.csv",
}

# ─── Search targets per channel ───────────────────────────────────────────────

LINKEDIN_TARGETS = [
    "site:linkedin.com/in owner dentist",
    "site:linkedin.com/in owner HVAC company",
    "site:linkedin.com/in CEO small business",
    "site:linkedin.com/in owner roofing company",
    "site:linkedin.com/in owner law firm",
    "site:linkedin.com/in owner restaurant",
    "site:linkedin.com/in owner real estate agency",
    "site:linkedin.com/in owner marketing agency",
    "site:linkedin.com/in owner gym fitness",
    "site:linkedin.com/in owner plumbing company",
    "site:linkedin.com/in founder SaaS company",
    "site:linkedin.com/in owner insurance agency",
    "site:linkedin.com/in owner accounting firm",
    "site:linkedin.com/in director nonprofit organization",
    "site:linkedin.com/in owner solar company",
]

TWITTER_TARGETS = [
    "site:twitter.com small business owner email",
    "site:x.com entrepreneur contact email",
    "site:twitter.com agency owner contact",
    "site:x.com startup founder email reach",
]

REDDIT_TARGETS = [
    "site:reddit.com \"small business owner\" email contact",
    "site:reddit.com \"my business\" email looking for",
    "site:reddit.com r/entrepreneur email contact",
    "site:reddit.com r/smallbusiness email reach out",
]

DIRECT_TARGETS = [
    # Service businesses
    ("plumber owner email contact", "missed_call", "main"),
    ("electrician owner email", "missed_call", "main"),
    ("HVAC company email contact", "missed_call", "main"),
    ("roofer owner email", "missed_call", "main"),
    ("landscaping company email contact", "review", "main"),
    ("pest control owner email", "review", "main"),
    # Healthcare
    ("dentist office email contact", "review", "chatbot", "voice"),
    ("chiropractor email contact", "review", "chatbot"),
    ("med spa owner email", "review", "social", "chatbot"),
    ("optometrist email contact", "review", "voice"),
    # Professional services
    ("attorney email contact site", "website", "chatbot"),
    ("accountant email CPA firm", "website", "chatbot"),
    ("real estate agent email contact", "social", "chatbot"),
    ("insurance agent email contact", "missed_call", "chatbot"),
    # Retail / hospitality
    ("restaurant owner email contact", "social", "sms", "review"),
    ("salon owner email contact", "social", "sms", "review"),
    ("gym owner email contact", "social", "sms", "gbp"),
    ("barbershop email contact owner", "sms", "review"),
    # High-value
    ("nonprofit executive director email", "grant"),
    ("agency owner email digital marketing", "ghl"),
    ("trader investor email newsletter", "tradingview", "signals"),
    ("solar company email contact", "website", "missed_call"),
]


def clean_email(email: str) -> str | None:
    email = email.strip().lower()
    if len(email) < 6 or "@" not in email:
        return None
    if any(j in email for j in JUNK_EMAILS):
        return None
    if email.endswith((".png", ".jpg", ".gif", ".pdf", ".css")):
        return None
    domain = email.split("@")[-1]
    if len(domain) < 4 or "." not in domain:
        return None
    return email


def load_existing_emails(queue_file: Path) -> set:
    if not queue_file.exists():
        return set()
    try:
        df = pd.read_csv(queue_file)
        if "email" in df.columns:
            return set(df["email"].str.lower().dropna())
    except Exception:
        pass
    return set()


def append_to_queue(queue_file: Path, leads: list[dict]):
    if not leads:
        return
    new_df = pd.DataFrame(leads).drop_duplicates(subset=["email"])
    if queue_file.exists():
        try:
            existing = pd.read_csv(queue_file)
            combined = pd.concat([existing, new_df]).drop_duplicates(subset=["email"]).reset_index(drop=True)
            combined.to_csv(queue_file, index=False)
            return
        except Exception:
            pass
    new_df.to_csv(queue_file, index=False)


def log(msg: str):
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ─── LinkedIn (via DuckDuckGo) ────────────────────────────────────────────────

def scan_linkedin(ddgs: DDGS) -> dict[str, list[dict]]:
    results_by_queue: dict[str, list[dict]] = {}
    queries = random.sample(LINKEDIN_TARGETS, min(5, len(LINKEDIN_TARGETS)))
    for query in queries:
        try:
            results = list(ddgs.text(query, max_results=8))
            for r in results:
                body = r.get("body", "") + " " + r.get("title", "")
                emails = [clean_email(e) for e in EMAIL_RE.findall(body)]
                emails = [e for e in emails if e]
                for email in emails:
                    lead = {
                        "email":   email,
                        "company": r.get("title", "")[:60],
                        "source":  "linkedin_ddg",
                        "url":     r.get("href", ""),
                        "niche":   "professional",
                        "city":    "",
                    }
                    # Route to main + ghl
                    for q in ["main", "ghl"]:
                        results_by_queue.setdefault(q, []).append(lead)
            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            log(f"  LinkedIn DDG error: {e}")
    return results_by_queue


# ─── Twitter/X (via DuckDuckGo) ───────────────────────────────────────────────

def scan_twitter(ddgs: DDGS) -> dict[str, list[dict]]:
    results_by_queue: dict[str, list[dict]] = {}
    queries = random.sample(TWITTER_TARGETS, min(2, len(TWITTER_TARGETS)))
    for query in queries:
        try:
            results = list(ddgs.text(query, max_results=6))
            for r in results:
                body = r.get("body", "")
                emails = [clean_email(e) for e in EMAIL_RE.findall(body)]
                emails = [e for e in emails if e]
                for email in emails:
                    lead = {
                        "email":   email,
                        "company": r.get("title", "")[:60],
                        "source":  "twitter_ddg",
                        "url":     r.get("href", ""),
                        "niche":   "entrepreneur",
                        "city":    "",
                    }
                    for q in ["main", "signals"]:
                        results_by_queue.setdefault(q, []).append(lead)
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            log(f"  Twitter DDG error: {e}")
    return results_by_queue


# ─── Reddit (via DuckDuckGo) ──────────────────────────────────────────────────

def scan_reddit(ddgs: DDGS) -> dict[str, list[dict]]:
    results_by_queue: dict[str, list[dict]] = {}
    queries = random.sample(REDDIT_TARGETS, min(2, len(REDDIT_TARGETS)))
    for query in queries:
        try:
            results = list(ddgs.text(query, max_results=6))
            for r in results:
                body = r.get("body", "")
                emails = [clean_email(e) for e in EMAIL_RE.findall(body)]
                emails = [e for e in emails if e]
                for email in emails:
                    lead = {
                        "email":   email,
                        "company": r.get("title", "")[:60],
                        "source":  "reddit_ddg",
                        "url":     r.get("href", ""),
                        "niche":   "small_business",
                        "city":    "",
                    }
                    for q in ["main", "reactivation"]:
                        results_by_queue.setdefault(q, []).append(lead)
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            log(f"  Reddit DDG error: {e}")
    return results_by_queue


# ─── Direct niche scan ────────────────────────────────────────────────────────

def scan_direct(ddgs: DDGS) -> dict[str, list[dict]]:
    results_by_queue: dict[str, list[dict]] = {}
    targets = random.sample(DIRECT_TARGETS, min(10, len(DIRECT_TARGETS)))
    cities  = ["Atlanta GA", "Dallas TX", "Phoenix AZ", "Charlotte NC", "Nashville TN",
               "Tampa FL", "Austin TX", "Denver CO", "Las Vegas NV", "Raleigh NC"]

    for target in targets:
        query       = target[0]
        queue_names = list(target[1:])
        city        = random.choice(cities)
        full_query  = f"{query} {city}"
        try:
            results = list(ddgs.text(full_query, max_results=6))
            for r in results:
                body = r.get("body", "")
                emails = [clean_email(e) for e in EMAIL_RE.findall(body)]
                emails = [e for e in emails if e]
                for email in emails:
                    lead = {
                        "email":   email,
                        "company": r.get("title", "")[:60],
                        "source":  "direct_ddg",
                        "url":     r.get("href", ""),
                        "niche":   query.split()[0],
                        "city":    city,
                    }
                    for q in queue_names:
                        results_by_queue.setdefault(q, []).append(lead)
            time.sleep(random.uniform(0.8, 2.0))
        except Exception as e:
            log(f"  Direct scan error ({query[:30]}): {e}")
    return results_by_queue


# ─── Merge and deduplicate ────────────────────────────────────────────────────

def merge_results(*dicts) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = {}
    for d in dicts:
        for queue, leads in d.items():
            merged.setdefault(queue, []).extend(leads)
    # Deduplicate within each queue
    for queue in merged:
        seen  = set()
        dedup = []
        for lead in merged[queue]:
            if lead["email"] not in seen:
                seen.add(lead["email"])
                dedup.append(lead)
        merged[queue] = dedup
    return merged


# ─── Main run ─────────────────────────────────────────────────────────────────

def run_scan():
    log("=" * 50)
    log("LEAD SCANNER — starting scan cycle")

    ddgs = DDGS()
    total_new = 0

    log("  [1/4] Scanning LinkedIn via DuckDuckGo...")
    li_results = scan_linkedin(ddgs)

    log("  [2/4] Scanning Twitter/X via DuckDuckGo...")
    tw_results = scan_twitter(ddgs)

    log("  [3/4] Scanning Reddit via DuckDuckGo...")
    rd_results = scan_reddit(ddgs)

    log("  [4/4] Direct niche scanning...")
    dr_results = scan_direct(ddgs)

    all_results = merge_results(li_results, tw_results, rd_results, dr_results)

    log(f"  Scan complete. Writing to {len(all_results)} queues...")

    for queue_name, leads in all_results.items():
        queue_file = QUEUE_MAP.get(queue_name)
        if not queue_file:
            continue
        existing = load_existing_emails(queue_file)
        new_leads = [l for l in leads if l["email"] not in existing]
        if new_leads:
            append_to_queue(queue_file, new_leads)
            log(f"    {queue_name}: +{len(new_leads)} new leads")
            total_new += len(new_leads)

    log(f"SCAN DONE — {total_new} total new leads added across all queues")
    log("=" * 50)
    return total_new


def run():
    """Single scan cycle. Task Scheduler runs this every 4 hours."""
    try:
        run_scan()
    except KeyboardInterrupt:
        log("Scanner stopped by user")
    except Exception as e:
        log(f"Scanner error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run()
