"""
linkedin_dm_drafter.py — Gray Horizons Enterprise
Finds LinkedIn business owner profiles and generates ready-to-send DM templates.
Outputs a queue of personalized DMs for manual or semi-automated sending.

Usage:
  python linkedin_dm_drafter.py          # generates DM queue
  Access /linkedin-dms on dashboard to review and copy DMs
"""

import os
import json
import random
import time
from datetime import datetime
from pathlib import Path
from duckduckgo_search import DDGS

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DM_QUEUE  = DATA_DIR / "linkedin_dm_queue.json"

CALENDLY  = "https://calendly.com/grayhorizonsenterprise/30min"

# ── Target profiles to find ───────────────────────────────────────────────────

SEARCH_TARGETS = [
    ("site:linkedin.com/in owner HVAC company",           "HVAC",        "hvac"),
    ("site:linkedin.com/in owner roofing company",         "Roofing",     "roofing"),
    ("site:linkedin.com/in owner plumbing company",        "Plumbing",    "plumbing"),
    ("site:linkedin.com/in owner dental practice",         "Dental",      "dental"),
    ("site:linkedin.com/in owner contractor construction", "Contractor",  "contractor"),
    ("site:linkedin.com/in owner landscaping company",     "Landscaping", "landscaping"),
    ("site:linkedin.com/in HOA property manager",          "HOA",         "hoa"),
    ("site:linkedin.com/in owner med spa aesthetic",       "Med Spa",     "medspa"),
    ("site:linkedin.com/in owner auto repair shop",        "Auto Repair", "auto"),
    ("site:linkedin.com/in owner pest control company",    "Pest Control","pest"),
    ("site:linkedin.com/in owner electrical contractor",   "Electrical",  "electrical"),
    ("site:linkedin.com/in owner insurance agency",        "Insurance",   "insurance"),
    ("site:linkedin.com/in owner law firm attorney",       "Legal",       "legal"),
    ("site:linkedin.com/in owner gym fitness studio",      "Fitness",     "fitness"),
    ("site:linkedin.com/in owner staffing agency",         "Staffing",    "staffing"),
]

# ── DM Templates by niche ─────────────────────────────────────────────────────

DM_TEMPLATES = {
    "hvac": [
        "Hey {name}, I work with HVAC owners to set up automated lead follow-up systems that respond to new inquiries in under 60 seconds. Most owners I talk to are losing 30 to 40 percent of inbound leads to slow response time. Would a quick 15-minute call be worth it to show you what that looks like for your market?",
        "Hey {name}, saw your profile and wanted to reach out. We build automated CRM systems for HVAC companies that handle new leads, missed calls, and appointment booking without any manual work. Free call if you want to see the numbers: {calendly}",
    ],
    "roofing": [
        "Hey {name}, quick question for a roofing owner: what happens when someone fills out your contact form at 10 PM? We build systems that respond in under 60 seconds and follow up for 14 days automatically. Worth a 15-minute call to see the ROI?",
        "Hey {name}, we help roofing contractors close more from the same lead volume using automated follow-up and booking. No extra ad spend. Happy to show you a live example: {calendly}",
    ],
    "dental": [
        "Hey {name}, we set up AI voice agents for dental practices that answer calls after hours, qualify patients, and book directly into the calendar. First month typically recovers 10 to 15 missed appointment opportunities. Worth a quick call?",
        "Hey {name}, noticed you run a dental practice. We build patient communication automation that handles after-hours calls, appointment reminders, and review requests automatically. Free 15-minute walkthrough: {calendly}",
    ],
    "contractor": [
        "Hey {name}, we build lead automation systems for contractors that respond to new inquiries in under 60 seconds and follow up for 2 weeks without any manual effort. Typically closes 40 to 60 percent more leads from the same ad budget. Quick call to show you?",
        "Hey {name}, quick one: how fast does your team respond to new online leads? We automate that entire process for contractors. Happy to show you a live demo: {calendly}",
    ],
    "hoa": [
        "Hey {name}, we built an HOA violation tracking system that automates notices, follow-ups, and escalations. Board members stop chasing paper and residents get notified instantly. Would a quick demo be useful?",
        "Hey {name}, we work with HOA managers to automate violation tracking, resident communication, and compliance logging. Everything runs without manual input. Free call if you want to see it live: {calendly}",
    ],
    "default": [
        "Hey {name}, we build AI automation systems for local service businesses that handle lead follow-up, appointment booking, and customer communication automatically. Quick 15-minute call to show you what that looks like for your business?",
        "Hey {name}, saw your profile and wanted to connect. We help business owners like you automate the stuff that eats time: follow-up, booking, reminders, reviews. Free demo call here if you are curious: {calendly}",
    ],
}

# ── Core functions ────────────────────────────────────────────────────────────

def load_queue():
    if DM_QUEUE.exists():
        return json.loads(DM_QUEUE.read_text(encoding="utf-8"))
    return []

def save_queue(queue):
    DM_QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

def extract_name(title: str) -> str:
    parts = title.split("|")[0].split("-")[0].strip().split()
    return parts[0] if parts else "there"

def get_template(niche: str, name: str) -> str:
    templates = DM_TEMPLATES.get(niche, DM_TEMPLATES["default"])
    return random.choice(templates).format(name=name, calendly=CALENDLY)

def run_dm_scan(max_per_niche: int = 3):
    existing = load_queue()
    existing_urls = {e["profile_url"] for e in existing}
    new_entries = []

    ddgs = DDGS()
    print(f"[DM SCANNER] Starting LinkedIn profile scan...")

    for query, niche_label, niche_key in SEARCH_TARGETS:
        try:
            results = list(ddgs.text(query, max_results=5))
            count = 0
            for r in results:
                url = r.get("href", "")
                if "linkedin.com/in/" not in url:
                    continue
                if url in existing_urls:
                    continue
                name = extract_name(r.get("title", "there"))
                dm   = get_template(niche_key, name)
                entry = {
                    "id":          len(existing) + len(new_entries) + 1,
                    "name":        name,
                    "niche":       niche_label,
                    "profile_url": url,
                    "title":       r.get("title", "")[:120],
                    "dm_text":     dm,
                    "status":      "pending",
                    "found_at":    datetime.now().isoformat(),
                    "sent_at":     None,
                }
                new_entries.append(entry)
                existing_urls.add(url)
                count += 1
                if count >= max_per_niche:
                    break
            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            print(f"[DM SCANNER] Error on {niche_label}: {e}")

    all_entries = existing + new_entries
    save_queue(all_entries)
    print(f"[DM SCANNER] Done. +{len(new_entries)} new profiles. Total: {len(all_entries)}")
    return new_entries

if __name__ == "__main__":
    run_dm_scan()
