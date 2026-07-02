"""
upwork_alert.py — Gray Horizons Enterprise
Monitors Upwork RSS feeds for automation/AI/CRM jobs that match GHE's services.
Runs daily, emails a digest of fresh listings with pre-written proposals.

No API keys needed — uses Upwork's public RSS feeds.
Scheduled via sync_to_railway.py or run standalone.
"""

import os
import re
import json
import time
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR     = Path(os.path.dirname(os.path.abspath(__file__)))
SEEN_FILE    = DATA_DIR / "upwork_seen.json"
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")

# ─── Job Search Feeds ─────────────────────────────────────────────────────────
# Upwork RSS: https://www.upwork.com/ab/feed/jobs/rss?q=TERM&sort=recency

SEARCH_TERMS = [
    "workflow automation",
    "CRM automation",
    "AI automation small business",
    "missed call text back",
    "HOA management software",
    "GHL Go High Level",
    "business automation setup",
    "lead follow up automation",
    "appointment booking automation",
    "property management automation",
    "HVAC software automation",
    "contractor CRM setup",
    "Vapi voice agent",
    "AI voice agent setup",
    "GoHighLevel setup",
    "GoHighLevel expert",
    "GHL workflow",
    "AI receptionist",
    "small business CRM setup",
    "automation consultant",
    "n8n automation",
    "Make.com automation",
]

RSS_BASE = "https://www.upwork.com/ab/feed/jobs/rss"

# ─── Keyword filters (must match at least one to qualify) ─────────────────────
MUST_MATCH = [
    "automat", "crm", "workflow", "go high level", "ghl", "hoa",
    "follow.?up", "lead", "sms", "missed call", "appointment",
    "property manag", "ai agent", "chatbot", "zapier", "make.com",
    "n8n", "airtable", "pipeline", "hvac", "contractor",
]

# Block these — wrong category
BLOCK_TERMS = [
    "logo", "design", "photoshop", "video edit", "translation",
    "seo content", "blog post", "copywriting", "data entry",
    "amazon fba", "dropshipping", "shopify store",
]

# ─── Proposal Templates ───────────────────────────────────────────────────────

PROPOSAL_TEMPLATES = {
    "automation": """\
I build this exact system for service businesses and I want to ask one question before pitching anything.

When someone fills out your form or calls after hours right now, what actually happens to that inquiry?

I ask because 88% of businesses have automation tools. Only 6% have them set up in a way that actually converts. The gap is almost always in what happens in the first 5 minutes after a lead comes in.

I've built full intake and follow-up systems inside GoHighLevel for contractors, HVAC companies, and home services firms. Instant SMS response, 14-day automated follow-up, AI voice agent for after-hours calls, pipeline tracking. Deployed in under a week.

Before I tell you what I'd build, I want to understand where yours is breaking down right now. What does your current follow-up process look like from the moment a lead comes in?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "crm": """\
I've built GHL from scratch for local service businesses and I want to understand your situation before suggesting anything.

Most owners I talk to have the same issue: GHL is paid for, some things are set up, but leads are still falling through because the follow-up sequence was never fully built or the pipeline stages don't match how they actually sell.

One contractor I worked with had 60 inbound leads last month. Followed up on 38. The other 22 went to voicemail and were never contacted again. He had no idea. We fixed the follow-up system in 5 days and 4 of those 22 converted in week two.

Before I walk you through what I'd build, what does your current GHL setup actually handle end to end without anyone touching it?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "hoa": """\
I've built violation tracking and homeowner communication automation specifically for HOA management firms and I want to ask one thing before anything else.

When a homeowner submits a violation or complaint right now, what does your team's process look like from that first report all the way to resolution? Is there a system tracking each step or is it mostly email threads?

I ask because that handoff is where most HOA teams lose time and create liability. We've built systems that lock the full violation lifecycle down automatically: intake, board notification, status tracking, homeowner updates, resolution logging. Deployed in about a week.

Worth a 10-minute call to see if it maps to what you're dealing with?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "voice": """\
I build AI voice agents for inbound call handling and I want to understand your situation before assuming anything.

Quick question: when someone calls your business after 5pm or on a weekend right now, what happens to that call?

I've deployed voice agents for HVAC companies, roofing contractors, and service businesses that answer every call, qualify the lead in 90 seconds, and text a booking link automatically. One roofing client booked 11 emergency jobs overnight in the first storm season after launch. Owner woke up to a full calendar.

The system runs 24/7 without anyone on staff. Before I walk through what I'd build for you, what does your current after-hours call handling look like?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "general": """\
I want to ask one question before telling you anything about what I do.

When your team gets a new inbound lead right now, what happens to it in the first 5 minutes? And when did you last manually verify that every automation you have running is actually working?

I ask because 88% of businesses have AI or automation tools. Only 6% have them set up in a way that's actually converting. The gap is almost always silent: tools running, leads falling through, nobody noticing.

I've built full automation stacks for contractors, HVAC companies, HOA management firms, and service businesses. GoHighLevel, AI voice agents, 14-day follow-up sequences, pipeline tracking. Deployed in under a week.

What does your current setup actually handle without anyone touching it?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",
}

def _pick_template(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ["hoa", "homeowner", "community association", "property manag"]):
        return PROPOSAL_TEMPLATES["hoa"]
    if any(k in text for k in ["voice agent", "vapi", "ai receptionist", "answering", "inbound call", "phone"]):
        return PROPOSAL_TEMPLATES["voice"]
    if any(k in text for k in ["crm", "pipeline", "go high level", "ghl", "contact manag"]):
        return PROPOSAL_TEMPLATES["crm"]
    if any(k in text for k in ["automat", "workflow", "zapier", "make.com", "n8n", "follow.?up"]):
        return PROPOSAL_TEMPLATES["automation"]
    return PROPOSAL_TEMPLATES["general"]


# ─── Feed fetching ────────────────────────────────────────────────────────────

def _job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()).get("ids", []))
        except Exception:
            pass
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps({"ids": list(seen)}, indent=2))


def fetch_jobs(term: str) -> list[dict]:
    try:
        r = requests.get(
            RSS_BASE,
            params={"q": term, "sort": "recency"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            return []
        jobs = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
            pub   = (item.findtext("pubDate") or "").strip()
            if title and link:
                jobs.append({"title": title, "link": link, "desc": desc, "pub": pub})
        return jobs
    except Exception as e:
        print(f"  [UPWORK] Feed error for '{term}': {e}")
        return []


def is_relevant(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    if any(b in text for b in BLOCK_TERMS):
        return False
    return any(re.search(k, text) for k in MUST_MATCH)


def scan_all() -> list[dict]:
    seen    = load_seen()
    new_ids = set()
    results = []

    for term in SEARCH_TERMS:
        jobs = fetch_jobs(term)
        for j in jobs:
            jid = _job_id(j["link"])
            if jid in seen or jid in new_ids:
                continue
            if not is_relevant(j["title"], j["desc"]):
                continue
            new_ids.add(jid)
            j["id"]       = jid
            j["template"] = _pick_template(j["title"], j["desc"])
            results.append(j)
        time.sleep(1.5)

    seen.update(new_ids)
    save_seen(seen)
    print(f"[UPWORK] {len(results)} new matching jobs found")
    return results


# ─── Email digest ─────────────────────────────────────────────────────────────

def _build_email_body(jobs: list[dict]) -> str:
    lines = [
        f"Upwork Job Alert — {datetime.now().strftime('%b %d, %Y')}",
        f"{len(jobs)} new matching job(s) found\n",
        "=" * 60,
        "",
    ]
    for i, j in enumerate(jobs, 1):
        lines += [
            f"{i}. {j['title']}",
            f"   Posted: {j['pub']}",
            f"   Link: {j['link']}",
            "",
            "   --- PROPOSAL TO COPY ---",
            j["template"],
            "",
            "=" * 60,
            "",
        ]
    lines += [
        "To apply: log into Upwork, open the link, and paste the proposal.",
        "Edit [SPECIFIC PAIN FROM LISTING] to match what they actually wrote.",
        "",
        "- GHE Automation",
    ]
    return "\n".join(lines)


def send_digest(jobs: list[dict]):
    if not SENDGRID_KEY:
        print("[UPWORK] No SendGrid key — printing digest only")
        print(_build_email_body(jobs))
        return

    body = _build_email_body(jobs)
    payload = {
        "personalizations": [{"to": [{"email": SENDER_EMAIL}]}],
        "from": {"email": SENDER_EMAIL, "name": "GHE Upwork Alerts"},
        "subject": f"Upwork Alert: {len(jobs)} new automation jobs",
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 202):
            print(f"[UPWORK] Digest emailed to {SENDER_EMAIL}")
        else:
            print(f"[UPWORK] Email failed {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[UPWORK] Email error: {e}")


def run():
    print(f"[UPWORK] Scanning {len(SEARCH_TERMS)} search terms...")
    jobs = scan_all()
    if not jobs:
        print("[UPWORK] No new jobs — done")
        return
    send_digest(jobs)


if __name__ == "__main__":
    run()
