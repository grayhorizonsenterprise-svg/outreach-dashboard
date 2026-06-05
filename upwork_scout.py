"""
upwork_scout.py — Gray Horizons Enterprise
Scans Upwork RSS feeds for matching jobs, scores them, drafts proposals.
Saves results to upwork_opportunities.json for dashboard review.

Run automatically every 2 hours. User reviews dashboard, picks connects, applies.
No Upwork API needed — uses public RSS feeds.
"""

import json
import time
import re
import os
import random
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT     = DATA_DIR / "upwork_opportunities.json"
SEEN_FILE  = DATA_DIR / "upwork_seen.json"

CALENDLY   = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")

RSS_SEARCHES = [
    "GoHighLevel",
    "GHL+automation",
    "AI+voice+agent",
    "CRM+automation",
    "Vapi+AI",
    "GoHighLevel+CRM",
    "AI+automation+local+business",
    "GHL+workflow",
]

SKIP_KEYWORDS = [
    "n8n", "shopify", "wordpress", "woocommerce", "php", "java",
    "ruby", "swift", "android", "ios", "blockchain", "solidity",
    "data entry", "virtual assistant", "content writing", "seo writing",
]

REQUIRE_KEYWORDS = [
    "gohighlevel", "highlevel", "ghl", "vapi", "voice agent",
    "crm automation", "ai automation", "workflow automation",
    "lead automation", "sms automation", "follow up automation",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GHE-Scout/1.0)"}


def load_seen() -> set:
    try:
        return set(json.loads(SEEN_FILE.read_text()).get("ids", []))
    except Exception:
        return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps({"ids": list(seen)}, indent=2))


def fetch_rss(query: str) -> list[dict]:
    url = f"https://www.upwork.com/ab/feed/jobs/rss?q={query}&sort=recency&paging=0%3B10"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        items = []
        for item in root.findall(".//item"):
            title       = (item.findtext("title") or "").strip()
            link        = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date    = (item.findtext("pubDate") or "").strip()
            items.append({"title": title, "link": link, "description": description, "pub_date": pub_date})
        return items
    except Exception as e:
        print(f"[UPWORK SCOUT] RSS error for '{query}': {e}")
        return []


def score_job(title: str, description: str) -> int:
    text = (title + " " + description).lower()

    # Hard disqualifiers
    for kw in SKIP_KEYWORDS:
        if kw in text:
            return 0

    # Must have at least one relevant keyword
    if not any(kw in text for kw in REQUIRE_KEYWORDS):
        return 0

    score = 50

    # Positive signals
    if any(k in text for k in ["payment verified", "verified"]):       score += 10
    if any(k in text for k in ["gohighlevel", "ghl"]):                 score += 15
    if any(k in text for k in ["vapi", "voice agent", "ai voice"]):    score += 15
    if any(k in text for k in ["long term", "ongoing", "retainer"]):   score += 10
    if any(k in text for k in ["pipeline", "workflow", "automation"]): score += 10
    if any(k in text for k in ["hvac", "dental", "contractor", "real estate", "medical"]): score += 10
    if any(k in text for k in ["$30", "$35", "$40", "$45", "$50"]):    score += 10
    if "fewer than 5" in text or "5 to 10" in text:                    score += 15
    if "10 to 15" in text:                                              score += 8

    # Negative signals
    if any(k in text for k in ["$5", "$8", "$10", "$12"]):             score -= 20
    if "50+" in text or "50 to 100" in text:                           score -= 25
    if "$0 spent" in text or "no reviews" in text:                     score -= 10

    return min(score, 100)


PROPOSAL_TEMPLATES = [
    """GHL automation is my core service. I build pipelines, workflows, and lead systems full-time for local service businesses.

{match_line}

I have built sub-account setups, A2P SMS registration, Meta Ads integration, automated follow-up sequences, appointment booking workflows, and full pipeline QA. Clean builds that hold up after handoff.

Available immediately. {question}

Rate: $35/hr or fixed project pricing available.""",

    """GHL and AI automation is what I do daily — pipelines, voice agents, CRM builds, and workflow QA for service businesses.

{match_line}

Recent builds include: instant SMS follow-up on lead submission, 7-touch nurture sequences, missed call text-back, AI inbound voice agent for appointment booking, and full GHL sub-account setup with documentation.

{question}

Rate: $35/hr. Available to start this week.""",
]


def draft_proposal(title: str, description: str) -> str:
    text = (title + " " + description).lower()

    if "voice" in text or "vapi" in text:
        match_line = "Your voice agent requirement is something I build regularly — inbound qualification, calendar booking, and CRM push all connected."
        question   = "What platform are you currently using for the voice layer?"
    elif "pipeline" in text or "kpi" in text:
        match_line = "Pipeline setup and reporting is a core part of what I deliver — stage tracking, custom fields, and dashboard visibility all included."
        question   = "Are you starting from a fresh GHL account or cleaning up an existing setup?"
    elif "lead" in text or "follow" in text:
        match_line = "Lead follow-up automation is where I see the most immediate ROI for clients — response in under 60 seconds, 7-touch sequence, no manual work."
        question   = "What does your current lead response process look like right now?"
    else:
        match_line = "The build you are describing maps directly to work I do regularly for similar businesses."
        question   = "What part of the system is most broken right now?"

    return random.choice(PROPOSAL_TEMPLATES).format(
        match_line=match_line,
        question=question,
    )


def run():
    seen = load_seen()
    opportunities = []

    for query in RSS_SEARCHES:
        jobs = fetch_rss(query)
        for job in jobs:
            job_id = job["link"].split("?")[0].strip("/").split("/")[-1]
            if job_id in seen:
                continue

            score = score_job(job["title"], job["description"])
            if score < 55:
                continue

            proposal = draft_proposal(job["title"], job["description"])
            opportunities.append({
                "id":          job_id,
                "title":       job["title"],
                "link":        job["link"],
                "score":       score,
                "pub_date":    job["pub_date"],
                "description": job["description"][:500],
                "proposal":    proposal,
                "found_at":    datetime.now(timezone.utc).isoformat(),
                "status":      "new",
            })
            seen.add(job_id)
        time.sleep(2)

    opportunities.sort(key=lambda x: x["score"], reverse=True)

    existing = []
    try:
        existing = json.loads(OUTPUT.read_text())
    except Exception:
        pass

    merged = {o["id"]: o for o in existing}
    for o in opportunities:
        merged[o["id"]] = o

    final = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:50]
    OUTPUT.write_text(json.dumps(final, indent=2))
    save_seen(seen)

    print(f"[UPWORK SCOUT] {len(opportunities)} new opportunities found. Total: {len(final)}")
    return opportunities


if __name__ == "__main__":
    run()
