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
Hey,

I saw you're looking to automate [SPECIFIC PAIN FROM LISTING].

That's exactly what we do at Gray Horizons Enterprise. We've built automation systems for local service businesses — HVAC, HOA management, contractors, dental — that handle lead capture, follow-up, and appointment booking without manual effort.

Here's what I'd set up for you:

- Missed call / after-hours lead capture with instant SMS response
- Automated follow-up sequences (day 2, day 5, day 8 after inquiry)
- Calendar booking integrated directly into your workflow
- CRM pipeline tracking so nothing falls through

Setup takes 5-7 days. You get a 7-day free trial before committing.

Happy to jump on a 20-minute call to walk through exactly what this looks like for your business.

Alex
Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "crm": """\
Hey,

Saw your post about setting up a CRM / lead pipeline.

I specialize in this for local service businesses. Most of the clients I work with had the same situation: leads coming in but no consistent system to track, follow up, or close them.

Here's how I typically set it up in 5-7 days:

- Full pipeline build in Go High Level (or your preferred CRM)
- Automated follow-up sequences tied to each stage
- Lead source tracking so you know what's working
- SMS and email touchpoints so no lead goes cold

I offer a 7-day free trial so you can see it running before you pay anything.

Would a 20-minute call work to go over the details?

Alex
Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "hoa": """\
Hey,

Your post caught my eye — we've built automation systems specifically for HOA management companies.

The two things I see constantly:

1. Violation tracking going into spreadsheets and getting lost between report, board review, and resolution
2. Homeowner communication done manually when it should be automated

We fix both. Automated violation lifecycle tracking, homeowner notifications, and follow-up sequences — all set up in about a week.

Free 7-day trial. No upfront commitment.

Happy to show you exactly what it looks like.

Alex
Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",

    "general": """\
Hey,

Saw your post and wanted to reach out — this is exactly the kind of work we do.

We build automation systems for local service businesses that handle lead capture, follow-up, and workflow management so the team can focus on delivering the work, not chasing it.

Setup time is typically 5-7 days. I offer a free 7-day trial so you can see it working before committing to anything.

Can we jump on a quick call to go over your specific situation?

Alex
Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min""",
}

def _pick_template(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ["hoa", "homeowner", "community association", "property manag"]):
        return PROPOSAL_TEMPLATES["hoa"]
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
