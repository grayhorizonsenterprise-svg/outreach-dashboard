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
    f"""Most local service businesses pay for leads they never follow up on fast enough.

The window to convert an inbound lead is under 5 minutes. After that, the conversion rate drops by over 80%.

A properly built GoHighLevel automation fires an SMS within 60 seconds of a form submission. No staff required.

If your CRM is sitting idle while leads go cold, that is a fixable problem.

See how it works: {FIVERR_GHL}""",

    f"""The 5 GHL automations every HVAC, dental, and contractor business needs:

1. Instant SMS on new lead
2. Missed call text-back
3. 7-day follow-up sequence
4. Appointment reminder 24 hours out
5. Review request after job completion

Most businesses have zero of these. The ones that do close 30 to 40 percent more leads from the same ad spend.

Built and running in 5 days: {FIVERR_GHL}""",

    f"""A client was running Google Ads, getting 40 to 50 leads per month, and closing maybe 8 of them.

The problem was not the ads. The problem was a 4-hour average response time and no follow-up after day 1.

We built a GHL pipeline with instant SMS, a 5-touch follow-up sequence, and a missed call bot.

Next month: 21 closes from the same 47 leads.

Same ad budget. Better system: {FIVERR_GHL}""",

    f"""GoHighLevel is one of the most powerful CRM platforms available for local service businesses.

Most people use 10% of it.

Pipelines, automations, SMS sequences, appointment booking, reputation management, voice AI, and reporting are all built in.

If you are paying for GHL and still manually following up with leads, something is wrong with the setup.

Let us fix it: {FIVERR_GHL}""",

    f"""What a fully automated lead pipeline looks like in practice:

Lead fills out form at 11:47 PM.
60 seconds later: Automated SMS fires. "Saw your inquiry. What is a good time to connect tomorrow?"
Lead replies: "10 AM works."
Calendar invite sent automatically. Owner gets a notification.

No one touched this manually.

That is what we build: {FIVERR_GHL}""",

    f"""The biggest mistake I see in GHL setups: workflows that trigger but do not close the loop.

A lead comes in. SMS fires. No reply. Nothing else happens.

A proper sequence has 7 touches over 14 days across SMS, email, and voicemail drop. Most leads convert on touch 4 or 5, not touch 1.

If your automation stops after the first message, you are leaving money on the table.

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""Most businesses that invest in AI tools end up with 10 different subscriptions and no system connecting them.

The value of AI is not in the tools. It is in the workflow that ties them together.

A voice AI that answers calls and books appointments. A CRM that scores leads automatically. A follow-up engine that knows when to push and when to wait.

That is what we build at Gray Horizons Enterprise.

{FIVERR_VOICE}""",

    f"""AI voice agents are no longer a novelty. They are a competitive advantage.

A dental office running an AI inbound agent:
- Answers every call, even at 2 AM
- Qualifies the caller in 90 seconds
- Books directly into the calendar
- Sends a confirmation SMS automatically

First month: 14 new patient bookings that would have gone to voicemail.

This is real and it is available now: {FIVERR_VOICE}""",

    f"""The businesses winning right now are not the ones spending the most on ads.

They are the ones with the tightest follow-up systems.

Speed to lead. Consistent nurture. Automated booking.

If you want to see what that looks like built for your business: {FIVERR_LEAD}""",

    f"""Three questions I ask every business owner before building their automation system:

1. What happens when someone fills out your contact form right now?
2. How many times does your team follow up before giving up?
3. What does your average lead-to-close timeline look like?

Most of the time the answers reveal the same thing: the system stops too early.

We fix that: {FIVERR_LEAD}""",

    f"""There is a version of your business where leads never fall through the cracks.

Where every inquiry gets a response in under 60 seconds.
Where follow-ups happen automatically for 30 days.
Where your calendar fills without your team touching a single thing manually.

That version exists. We build it.

Gray Horizons Enterprise. AI automation for local service businesses.

{FIVERR_GHL}""",
]

EDGE_ENGINE_POSTS = [
    f"""Most retail traders lose not because they pick bad stocks, but because they size positions emotionally.

The Kelly Criterion removes the emotion. It tells you exactly what percentage of your capital to risk on each trade based on your actual win rate and average win/loss ratio.

We built this into the Edge Engine scoring system.

{GUMROAD_LINK}""",

    f"""Congressional members are required to disclose stock trades within 45 days under the STOCK Act.

The pattern shows up before the disclosure in volume and options flow. Not always. But often enough to track.

We scan every new disclosure and run it through our momentum scoring model.

Edge Engine: {GUMROAD_LINK}""",

    f"""A trading edge is not a hot tip. It is a repeatable process.

RSI divergence. Volume anomaly relative to 30-day average. EMA cross confirmation.

When all three line up, the score is above 70. That is when we look closer.

When none align, we wait. That is the discipline most people cannot maintain.

Edge Engine scoring system: {GUMROAD_LINK}""",

    f"""The most honest thing I can tell you about trading signals:

No system wins 100% of the time. The goal is a positive expected value over many trades.

Win rate of 55%. Average win 2x the average loss. That math compounds into real results over time.

We track every signal, every outcome. Transparency is the product.

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
    t = threading.Thread(target=server.handle_request)
    t.start()

    params = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": "http://localhost:8000/callback",
        "scope": "r_liteprofile w_member_social openid profile",
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
