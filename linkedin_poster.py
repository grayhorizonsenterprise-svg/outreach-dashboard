"""
linkedin_poster.py — Gray Horizons Enterprise
Auto-posts to LinkedIn once per day. Three content streams:
  1. GHL automation tips (drives Fiverr/Upwork leads)
  2. AI services / local business hooks (drives service inquiries)
  3. Edge Engine / trading signals (drives Gumroad sales)

Setup (one-time, 10 minutes):
  1. Go to developer.linkedin.com and create an app
  2. Add products: "Share on LinkedIn" and "Sign In with LinkedIn"
  3. Under Auth, add redirect URL: http://localhost:8000/callback
  4. Copy Client ID and Client Secret to env vars below
  5. Run: python linkedin_poster.py --auth
     Opens browser, you approve, token saved automatically
  6. Token lasts 60 days. Re-run --auth before it expires.

Railway env vars to add:
  LINKEDIN_CLIENT_ID
  LINKEDIN_CLIENT_SECRET
  LINKEDIN_ACCESS_TOKEN
  LINKEDIN_PERSON_ID  (auto-filled after --auth)
"""

import os
import sys
import json
import random
import webbrowser
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
ACCESS_TOKEN  = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
PERSON_ID     = os.getenv("LINKEDIN_PERSON_ID", "")

DATA_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
POSTED_LOG = DATA_DIR / "linkedin_posted.json"
TOKEN_FILE = DATA_DIR / "linkedin_token.json"

FIVERR_GHL   = "https://www.fiverr.com/s/5rYYAZQ"
FIVERR_VOICE = "https://www.fiverr.com/s/Eg88Kld"
FIVERR_LEAD  = "https://www.fiverr.com/s/m588eez"
GUMROAD_LINK = "https://horizons56.gumroad.com"

# ── Content Pools ──────────────────────────────────────────────────────────────

GHL_POSTS = [
    f"""Everyone says you need more leads.

Wrong. You need to close the ones you already have.

A roofing company was spending $4,200/month on Google Ads. 48 leads per month. 9 closes.

We built their GHL pipeline: instant SMS on form submit, missed call text-back, 7-touch follow-up over 14 days.

Next month: same 48 leads. 23 closes. Zero extra ad spend.

The leads were always there. The system was not.

Built and live in 5 days: {FIVERR_GHL}""",

    f"""A lead that calls your business and gets voicemail has already started Googling your competitor.

This is not an opinion. This is what the data shows.

50% of buyers go with the vendor that responds first. Not the best one. The fastest one.

A missed call text-back automation fires in under 10 seconds. "Hey, sorry I missed you. What can I help with?"

That one message recovers 30 to 40% of missed call leads.

What is a missed call worth to your business?

{FIVERR_GHL}""",

    f"""What a fully automated lead pipeline looks like at 11:47 PM:

Lead fills out HVAC form.
11:47:52 PM: SMS fires automatically.
11:51 PM: Lead replies "tomorrow morning works."
11:51 PM: Booking confirmed. Owner notified. Calendar updated.

Zero humans involved. Zero leads lost to slow response.

That is not the future. That is what we build today: {FIVERR_GHL}""",

    f"""The 5 GHL automations that separate businesses closing 40% of leads from ones closing 15%:

1. Sub-60-second SMS on every new inquiry
2. Missed call text-back with open-ended question
3. 7-touch nurture sequence over 14 days
4. Appointment reminder 24 hours and 2 hours before
5. Review request triggered on job completion

Most businesses have none of these.
The ones that do close more from the same lead volume.

Drop a comment if you want to know which one drives the most revenue.

{FIVERR_GHL}""",

    f"""I see GHL accounts every week that cost $297/month and do nothing.

No workflows active. No pipelines configured. No automations firing.

It is not the platform. The platform is exceptional. It is the setup.

A properly configured GHL account replaces a receptionist, a follow-up VA, and a booking coordinator.

If you are paying for GHL and still manually following up with leads, the setup is wrong.

We fix it in 5 days: {FIVERR_GHL}""",

    f"""Controversial opinion: most local businesses do not have a lead problem. They have a speed problem.

48-hour response time is not a CRM issue. It is a lost revenue issue.

The fix is not hiring faster people. The fix is automating the first 5 touchpoints so no human has to be involved until the lead is warm.

What does your current average response time look like? Drop it in the comments.

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""A dental office was losing 22 calls per week to voicemail.

They knew the number because they checked missed calls. They did not know the revenue because they never calculated it.

Average new patient value: $1,400.
22 missed calls per week at a 30% conversion rate: $9,240 per week walking out the door.

We deployed an AI inbound voice agent. It answers every call, qualifies in 90 seconds, books directly into the calendar.

Week one: 14 recovered bookings.

The math is not complicated: {FIVERR_VOICE}""",

    f"""AI is not replacing your business. It is replacing the businesses that do not use it.

The HVAC company with an AI voice agent answering calls at 2 AM is booking jobs while their competitor sleeps.

The contractor with automated follow-up closing leads on day 5 is winning deals the manual operation gave up on day 2.

This is not theoretical. This is happening right now in every market.

Gray Horizons Enterprise builds these systems for local service businesses: {FIVERR_LEAD}""",

    f"""3 questions I ask every business owner before we start:

1. What happens the second someone fills out your contact form?
2. How many follow-up touches happen before your team gives up?
3. When was the last time you called a lead back within 5 minutes?

The answers reveal everything about where revenue is leaking.

Most of the time the leak is not the leads. It is what happens after.

What does your current follow-up process look like? Be honest in the comments.

{FIVERR_LEAD}""",

    f"""There is a version of your business where:

Every lead gets a response in under 60 seconds.
Every missed call gets a text back in under 10 seconds.
Every appointment gets confirmed and reminded automatically.
Every closed job triggers a review request.

None of this requires hiring anyone.

That version of your business exists. We build it in 5 days.

Gray Horizons Enterprise: {FIVERR_GHL}""",

    f"""The businesses that win the next 3 years will not be the ones with the most staff.

They will be the ones with the best systems behind a lean team.

1 person running an AI-backed CRM outperforms a 5-person team running spreadsheets.

We build those systems for local service businesses. HVAC. Roofing. Dental. Contractors. HOA management.

If you are curious what that looks like for your specific business: {FIVERR_LEAD}""",
]

EDGE_ENGINE_POSTS = [
    f"""Most retail traders do not lose because they pick bad setups.

They lose because they size positions based on how confident they feel instead of what the math says.

Confidence is not an edge. Expected value is.

Win rate 55%. Average win 2x average loss. Position sized at 2% Kelly. That compounds into something real.

We built the math into the Edge Engine. Every signal comes with a score and a sizing recommendation.

{GUMROAD_LINK}""",

    f"""Congressional members disclosed $213M in stock trades last quarter.

The STOCK Act requires disclosure within 45 days. The pattern shows up in options flow before that.

We track every disclosure and cross-reference it against volume anomalies and institutional flow data.

Not every disclosure is actionable. But the ones that line up with the other signals are worth watching.

Edge Engine scans this automatically: {GUMROAD_LINK}""",

    f"""An edge is not a tip. It is a repeatable process with a positive expected value over 100 trades.

RSI divergence. Volume 40% above 30-day average. EMA cross with confirmation candle.

When all three align the score is above 75. That is when we look harder.

When none align we wait. Most people cannot do that part.

Edge Engine: {GUMROAD_LINK}""",

    f"""The honest truth about trading signals that nobody says:

No system wins every time. Anyone claiming otherwise is selling something.

What a good system does: win more than it loses, keep losses small, let winners run.

We track every signal and every outcome publicly. Win rate, average return, max drawdown.

Transparency is the product. Everything else is noise.

{GUMROAD_LINK}""",
]

ALL_POSTS = GHL_POSTS + AI_SERVICES_POSTS + EDGE_ENGINE_POSTS

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_posted():
    if POSTED_LOG.exists():
        return json.loads(POSTED_LOG.read_text(encoding="utf-8"))
    return []

def save_posted(posted):
    POSTED_LOG.write_text(json.dumps(posted, indent=2), encoding="utf-8")

def load_token():
    if TOKEN_FILE.exists():
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("access_token", ""), data.get("person_id", "")
    return ACCESS_TOKEN, PERSON_ID

def get_person_id(token):
    r = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r.status_code == 200:
        return r.json().get("sub", "")
    r2 = requests.get(
        "https://api.linkedin.com/v2/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r2.status_code == 200:
        return r2.json().get("id", "")
    return ""

def post_to_linkedin(token, person_id, text):
    payload = {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    r = requests.post("https://api.linkedin.com/v2/ugcPosts", json=payload, headers=headers)
    return r.status_code, r.text

# ── OAuth Flow ─────────────────────────────────────────────────────────────────

def run_auth():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET first.")
        return

    import http.server
    import threading

    auth_code = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                auth_code["code"] = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorized. You can close this tab.")
        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", 8000), Handler)

    def serve_until_code():
        while "code" not in auth_code:
            server.handle_request()

    t = threading.Thread(target=serve_until_code)
    t.daemon = True
    t.start()

    params = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": "http://localhost:8000/callback",
        "scope": "openid profile w_member_social",
        "state": "ghe_auth"
    })
    webbrowser.open(f"https://www.linkedin.com/oauth/v2/authorization?{params}")
    print("Browser opened. Approve the LinkedIn permission request...")
    t.join(timeout=120)

    if "code" not in auth_code:
        print("ERROR: No auth code received. Try again.")
        return

    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code",
        "code": auth_code["code"],
        "redirect_uri": "http://localhost:8000/callback",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })

    if r.status_code != 200:
        print(f"ERROR getting token: {r.text}")
        return

    token = r.json()["access_token"]
    person_id = get_person_id(token)

    TOKEN_FILE.write_text(json.dumps({
        "access_token": token,
        "person_id": person_id,
        "saved_at": datetime.now().isoformat()
    }, indent=2), encoding="utf-8")

    print(f"Token saved to {TOKEN_FILE}")
    print(f"Person ID: {person_id}")
    print("\nAdd these to Railway env vars:")
    print(f"  LINKEDIN_ACCESS_TOKEN={token}")
    print(f"  LINKEDIN_PERSON_ID={person_id}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    token, person_id = load_token()

    if not token:
        print("[SKIP] No LinkedIn token. Run: python linkedin_poster.py --auth")
        return

    if not person_id:
        person_id = get_person_id(token)
        if not person_id:
            print("[SKIP] Could not get LinkedIn person ID. Re-run --auth.")
            return

    posted = load_posted()
    available = [p for p in ALL_POSTS if p not in posted]

    if not available:
        print("[RESET] All posts cycled. Starting over.")
        posted = []
        available = ALL_POSTS[:]

    post_text = random.choice(available)
    status, response = post_to_linkedin(token, person_id, post_text)

    if status in (200, 201):
        posted.append(post_text)
        save_posted(posted)
        preview = post_text[:80].replace("\n", " ")
        print(f"[POSTED] {preview}...")
    else:
        print(f"[ERROR] Status {status}: {response}")

if __name__ == "__main__":
    if "--auth" in sys.argv:
        run_auth()
    else:
        main()
