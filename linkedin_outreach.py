"""
linkedin_outreach.py — Gray Horizons Enterprise
Automated LinkedIn outreach: finds decision-makers, sends connection requests
with personalized messages. Runs daily, 15 requests max (safe limit).
You only need to respond to replies — everything else is automated.

Setup (one time, 2 minutes):
  1. Log into LinkedIn in Chrome
  2. Open DevTools (F12) → Application → Cookies → linkedin.com
  3. Find cookie named "li_at" → copy its value
  4. Add to Railway: LINKEDIN_LI_AT=<value>
  5. Also add: LINKEDIN_CSRF_TOKEN=<value of "JSESSIONID" cookie, without quotes>

Safe limits: 15 connection requests/day — stays under LinkedIn radar.
"""

import requests
import json
import random
import time
import os
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR       = Path(os.path.dirname(os.path.abspath(__file__)))
CONTACTED_FILE = DATA_DIR / "linkedin_contacted.json"
LI_AT          = os.getenv("LINKEDIN_LI_AT", "").strip()
CSRF_TOKEN     = os.getenv("LINKEDIN_CSRF_TOKEN", "").strip().strip('"')

CALENDLY_LINK  = os.getenv("CALENDLY_LINK", "https://calendly.com/grayhorizonsenterprise")

DAILY_LIMIT = 15

# Search queries targeting decision-makers by niche
SEARCH_QUERIES = [
    "HOA property manager",
    "community association manager",
    "HVAC company owner",
    "roofing company owner",
    "landscaping business owner",
    "plumbing company owner",
    "general contractor owner",
    "dental practice owner",
    "auto repair shop owner",
    "real estate broker owner",
    "small business owner operations",
    "independent financial advisor",
    "trading signals analyst",
]

# Personalized messages by detected niche keyword
MESSAGES = {
    "hoa": "Hi {name}, I work with HOA management teams to automate violation tracking and board reporting — cuts admin time significantly. Happy to show you what we built if it's relevant to your team.",
    "hvac": "Hi {name}, I help HVAC owners capture leads that go to voicemail automatically. Most owners recover 2-3 jobs/week they were losing. Worth a quick look?",
    "roofing": "Hi {name}, I build systems for roofing companies that follow up with storm leads automatically. Happy to show you how it works if timing is right.",
    "landscaping": "Hi {name}, I help landscaping businesses automate their estimate follow-ups so no lead slips through. Quick question — how are you currently handling missed calls?",
    "dental": "Hi {name}, I work with dental practices to automate new patient follow-ups and reduce no-shows. Happy to show you what we put together for similar practices.",
    "financial": "Hi {name}, I build AI tools for independent advisors — signals, momentum scoring, congressional trade tracking. Might be relevant to your workflow.",
    "trading": "Hi {name}, I run Edge Engine — daily trading signals with RSI momentum scoring and congressional disclosure tracking. Happy to connect with serious traders.",
    "default": "Hi {name}, I build AI automation systems for small businesses — saves owners 5-10 hours/week on follow-ups and lead tracking. Happy to connect and share what we've built.",
}


def load_contacted() -> set:
    if CONTACTED_FILE.exists():
        try:
            return set(json.loads(CONTACTED_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_contacted(contacted: set):
    CONTACTED_FILE.write_text(json.dumps(list(contacted)))


def get_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/vnd.linkedin.normalized+json+2.1",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": f"li_at={LI_AT}; JSESSIONID=\"{CSRF_TOKEN}\"",
        "Csrf-Token": CSRF_TOKEN,
        "X-Li-Lang": "en_US",
        "X-RestLi-Protocol-Version": "2.0.0",
        "Referer": "https://www.linkedin.com/",
    }


def search_people(query: str, start: int = 0) -> list:
    """Search LinkedIn for people matching query."""
    # Try GraphQL-based endpoint first (current as of 2025)
    endpoints = [
        {
            "url": "https://www.linkedin.com/voyager/api/graphql",
            "params": {
                "variables": f"(start:{start},origin:GLOBAL_SEARCH_HEADER,query:(keywords:{query},flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:resultType,value:List(PEOPLE))),includeFiltersInResponse:false))",
                "queryId": "voyagerSearchDashClusters.02af3bc5ca7e4fdd4d70b3f792d51313",
            },
        },
        {
            "url": "https://www.linkedin.com/voyager/api/search/blended",
            "params": {
                "keywords": query, "q": "blended", "origin": "GLOBAL_SEARCH_HEADER",
                "start": start, "count": 10,
                "filters": "List((key:resultType,value:List(PEOPLE)))",
            },
        },
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep["url"], params=ep["params"], headers=get_headers(), timeout=15)
            if r.status_code == 200:
                data = r.json()
                people = []
                # GraphQL response structure
                clusters = (data.get("data", {})
                               .get("searchDashClustersByAll", {})
                               .get("elements", []))
                for cluster in clusters:
                    for item in cluster.get("items", {}).get("elements", []):
                        entity = item.get("item", {}).get("entityResult", {})
                        if not entity:
                            continue
                        urn = entity.get("entityUrn", "")
                        title = entity.get("title", {}).get("text", "")
                        subtitle = entity.get("primarySubtitle", {}).get("text", "")
                        nav = entity.get("navigationUrl", "")
                        pub_id = nav.split("/in/")[-1].strip("/") if "/in/" in nav else ""
                        parts = title.split(" ", 1)
                        people.append({
                            "id":         urn.replace("urn:li:fsd_profile:", "").replace("urn:li:fs_miniProfile:", ""),
                            "first_name": parts[0] if parts else title,
                            "last_name":  parts[1] if len(parts) > 1 else "",
                            "headline":   subtitle,
                            "public_id":  pub_id,
                        })
                # Legacy blended response structure
                if not people:
                    for el in data.get("elements", []):
                        for item in el.get("elements", []):
                            entity = item.get("hitInfo", {}).get("com.linkedin.voyager.search.SearchProfile", {})
                            if not entity:
                                continue
                            member = entity.get("miniProfile", {})
                            if not member:
                                continue
                            people.append({
                                "id":         member.get("entityUrn", "").replace("urn:li:fs_miniProfile:", ""),
                                "first_name": member.get("firstName", ""),
                                "last_name":  member.get("lastName", ""),
                                "headline":   member.get("occupation", ""),
                                "public_id":  member.get("publicIdentifier", ""),
                            })
                if people:
                    return people
            else:
                print(f"[LI SEARCH] {ep['url'].split('/')[-1]} → {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print(f"[LI SEARCH] Error on {ep['url'].split('/')[-1]}: {e}")
    return []


def send_connection(person: dict, message: str) -> bool:
    """Send a connection request with a personalized note."""
    profile_id = person.get("id", "")
    if not profile_id:
        return False
    try:
        payload = {
            "trackingId": "unused",
            "invitations": [],
            "excludeInvitations": [],
            "invitation": {
                "com.linkedin.voyager.growth.invitation.InviteToConnect": {
                    "message": message[:300],
                    "profileId": profile_id,
                }
            },
        }
        r = requests.post(
            "https://www.linkedin.com/voyager/api/growth/normInvitations",
            headers={**get_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            return True
        elif r.status_code == 429:
            print("[LI CONNECT] Rate limit hit — stopping for today")
            return None  # signal to stop
        else:
            print(f"[LI CONNECT] {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        print(f"[LI CONNECT] Error: {e}")
        return False


def pick_message(person: dict, query: str) -> str:
    """Pick message template based on niche."""
    name     = person.get("first_name", "there")
    headline = (person.get("headline", "") + " " + query).lower()

    if any(k in headline for k in ["hoa", "community association", "property manager"]):
        template = MESSAGES["hoa"]
    elif any(k in headline for k in ["hvac", "heating", "cooling", "air conditioning"]):
        template = MESSAGES["hvac"]
    elif any(k in headline for k in ["roofing", "roof"]):
        template = MESSAGES["roofing"]
    elif any(k in headline for k in ["landscaping", "lawn"]):
        template = MESSAGES["landscaping"]
    elif any(k in headline for k in ["dental", "dentist"]):
        template = MESSAGES["dental"]
    elif any(k in headline for k in ["financial", "advisor", "wealth", "investment"]):
        template = MESSAGES["financial"]
    elif any(k in headline for k in ["trading", "trader", "signals", "stocks"]):
        template = MESSAGES["trading"]
    else:
        template = MESSAGES["default"]

    return template.format(name=name, calendly=CALENDLY_LINK)


def run():
    if not LI_AT:
        print("[LI OUTREACH] LINKEDIN_LI_AT not set.")
        print("  1. Log into LinkedIn in Chrome")
        print("  2. F12 → Application → Cookies → linkedin.com")
        print("  3. Copy value of 'li_at' cookie")
        print("  4. Add LINKEDIN_LI_AT to Railway variables")
        print("  Also add LINKEDIN_CSRF_TOKEN (value of JSESSIONID cookie)")
        return

    contacted = load_contacted()
    sent      = 0
    today     = datetime.utcnow().strftime("%Y-%m-%d")

    # Count how many sent today
    today_sent = sum(1 for c in contacted if c.startswith(today))
    if today_sent >= DAILY_LIMIT:
        print(f"[LI OUTREACH] Daily limit reached ({DAILY_LIMIT}) — try again tomorrow")
        return

    queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))

    for query in queries:
        if sent + today_sent >= DAILY_LIMIT:
            break
        print(f"  [LI] Searching: {query}")
        people = search_people(query, start=random.randint(0, 50))

        for person in people:
            if sent + today_sent >= DAILY_LIMIT:
                break

            uid = person.get("id", "")
            if not uid or uid in contacted:
                continue

            message = pick_message(person, query)
            name    = f"{person.get('first_name','')} {person.get('last_name','')}".strip()

            result = send_connection(person, message)
            if result is None:  # rate limit
                break
            if result:
                contacted.add(uid)
                contacted.add(f"{today}:{uid}")
                sent += 1
                print(f"    [+] Connected: {name} ({person.get('headline','')[:50]})")
                time.sleep(random.uniform(8, 15))  # human-like delay
            else:
                time.sleep(2)

        time.sleep(random.uniform(5, 10))

    save_contacted(contacted)
    print(f"[LI OUTREACH] Done — {sent} connection requests sent today")


if __name__ == "__main__":
    run()
