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

BOOK_CALL      = "https://calendly.com/grayhorizonsenterprise/30min"
FIVERR_GHL     = BOOK_CALL
FIVERR_VOICE   = BOOK_CALL
FIVERR_LEAD    = BOOK_CALL
GUMROAD_SIGNALS   = "https://horizons56.gumroad.com/l/hwghqu"
GUMROAD_FLOW      = "https://horizons56.gumroad.com/l/ibbxcp"
GUMROAD_INDICATORS= "https://horizons56.gumroad.com/l/ghe-indicators"
GUMROAD_AI_BIZ    = "https://horizons56.gumroad.com/l/ai-small-business-guide"
GUMROAD_CONTRACTOR= "https://horizons56.gumroad.com/l/contractors-playbook"
GUMROAD_HOA       = "https://horizons56.gumroad.com/l/hoa-management-guide"
GUMROAD_TRADING   = "https://horizons56.gumroad.com/l/stock-trading-guide"
GUMROAD_BETS      = "https://horizons56.gumroad.com/l/sports-bettors-edge"
GUMROAD_LINK      = GUMROAD_SIGNALS

# ── Content Pools ──────────────────────────────────────────────────────────────

GHL_POSTS = [
    f"""Talked to an HVAC owner last week spending $4k/month on Google Ads.

48 leads a month. Closing 9.

Not a lead problem. A follow-up problem.

We built out his GHL: instant SMS on every form submission, missed call text-back, 7 touches over 2 weeks.

Next month, same 48 leads. 23 closes. Same budget.

Just fixed what happens after the lead comes in.

{FIVERR_GHL}""",

    f"""Real scenario from a roofing client I worked with last quarter.

Lead called at 7pm. Went to voicemail. No callback until the next morning.

By then they had already booked with someone else.

We set up a missed call text-back that fires in under 10 seconds. "Hey, sorry I missed you. What can I help with?"

Recovered 6 leads in the first month that would have walked.

What does a missed call actually cost you? I'm genuinely curious.

{FIVERR_GHL}""",

    f"""11:47pm. Someone fills out an HVAC form.

11:47:52. Automated SMS goes out.

11:51. They reply: "Tomorrow morning works."

Calendar invite sent. Owner gets notified. Done.

Nobody touched this. Nobody was awake. The system handled it start to finish.

That's what we build. {FIVERR_GHL}""",

    f"""Roofing company. $297/month in GHL. Zero automations running.

Leads sitting for 6 hours before anyone called back. Calendar still managed on paper.

We built the full workflow in 48 hours: instant form response, missed call text-back, 7-touch follow-up sequence.

First 30 days: 11 more closes than the month before. Same ad budget.

{FIVERR_GHL}""",

    f"""Contractor. 60 inbound leads last month. Called back 38.

The other 22 went to voicemail and never got a follow-up.

We built a GHL sequence that follows up automatically for 14 days without anyone touching it.

4 of those 22 converted in week two. Revenue recovered from leads they had already written off.

{FIVERR_GHL}""",

    f"""HVAC company. Same 48 leads per month for 3 years. Closing 9.

Competitor down the street closing 19 from fewer leads.

Difference: competitor responds in under 60 seconds. This client averaged 4 hours.

We fixed the follow-up speed. Nothing else changed. Closes went to 21 the next month.

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""Dental office. 22 missed calls a week.

They tracked the number. They never did the math on the revenue.

New patient average value: $1,400. If 30% of those calls would have converted, that's $9,240 a week going to voicemail.

We put an AI voice agent on their inbound line. Answers every call, qualifies in 90 seconds, books straight to the calendar.

Week one: 14 bookings that would have been missed.

The math isn't complicated. {FIVERR_VOICE}""",

    f"""Roofing contractor. 6 years of $0 in after-hours revenue.

Calls after 6pm went to voicemail. Nobody called back until morning. Jobs went to whoever answered.

We set up an AI voice agent that answers every call, qualifies the job, and texts a booking link automatically.

First storm season: 11 emergency jobs booked overnight. Owner woke up to a full calendar.

{FIVERR_LEAD}""",

    f"""Med spa. Running Facebook ads. Getting clicks. 34 form fills last month.

11 of them never got a follow-up within 24 hours. Gone.

We built an instant SMS follow-up and AI qualifier that fires in under 60 seconds.

9 appointments booked from the backlog in the first week. No new ad spend.

{FIVERR_LEAD}""",

    f"""Law firm. 3 receptionists. Still losing 18% of inbound calls to voicemail during lunch.

Potential clients hanging up and calling the next firm on Google.

We built an AI intake agent to handle overflow calls and qualify prospects automatically.

Consultation bookings up 40% in 30 days. No new hires. No bigger team.

{FIVERR_GHL}""",

    f"""Gym owner. 200 trial members last quarter. 40% never came back after day 7.

No follow-up sequence. No re-engagement. Just lost revenue sitting in the CRM.

We built an automated sequence that fires at day 3, day 6, and day 10 with a personal check-in.

31 converted to paid memberships in 60 days. Same leads, no extra cost.

{FIVERR_LEAD}""",
]

EDGE_ENGINE_POSTS = [
    f"""Most traders don't lose because they pick bad setups.

They lose because they size based on how confident they feel.

That's not an edge. That's gambling with extra steps.

Win rate 55%. Average win 2x the average loss. Size at Kelly. That compounds into something real over time.

Built that math directly into the Edge Engine. Every signal comes with a score and a size.

{GUMROAD_SIGNALS}""",

    f"""Congress members disclosed $213M in trades last quarter.

45 days to report under the STOCK Act. But the footprint shows up in options flow before the disclosure.

Not every trade is actionable. But when it lines up with the volume and momentum signals, it's worth watching.

We track all of it and run it through the scoring model automatically.

Daily signals: {GUMROAD_SIGNALS}""",

    f"""An edge isn't a hot tip from a Discord server.

It's a process that has positive expected value over hundreds of trades.

RSI divergence. Volume 40% above the 30-day avg. EMA cross with a confirmation candle.

When all three line up the score clears 75. That's when we look closer.

When none of them align we sit on our hands. That part is harder than it sounds.

{GUMROAD_INDICATORS}""",

    f"""Nobody talks about this but I will:

No signal system wins every time. Anyone selling you that is lying.

What a real system does: positive expected value over time. More wins than losses. Small losses, bigger wins.

We log every signal and every result. Open book. If it stops working we say so.

{GUMROAD_SIGNALS}""",
]

PRODUCT_POSTS = [
    f"""Electrical contractor. Following up on leads by hand. Losing jobs on day 3 when they stopped calling.

We wrote the exact playbook we use to automate contractor follow-up, booking, and client intake in GHL.

Step by step. No tech background required.

{GUMROAD_CONTRACTOR}""",

    f"""Small business owner. 3 tools already paid for. Using none of them to their potential.

We put together a guide on exactly what to automate first, what free or cheap tools handle it, and how to set it up in a weekend.

If any part of your operation still runs on manual follow-up, this covers the fix.

{GUMROAD_AI_BIZ}""",

    f"""HOA manager. 400 units. Violation tracking in spreadsheets. Notices sent by hand. Follow-up forgotten half the time.

We wrote the full process for automating violations, resident notices, and compliance logs from one system.

{GUMROAD_HOA}""",

    f"""Sports bettor. Winning 54% of games. Still losing money.

The problem is never the pick rate. It is sizing a 54% edge like it is a 90% lock.

We built the full breakdown of Kelly Criterion, expected value, and how to size every bet based on actual edge.

{GUMROAD_BETS}""",

    f"""Full-time job. Watching the market in 10-minute windows.

Institutional flow signals, RSI confirmation, congressional disclosure tracking — all scored and filtered before 8am.

You get the signal with the position size already calculated. You decide in under a minute.

{GUMROAD_TRADING}""",
]

ALL_POSTS = GHL_POSTS + AI_SERVICES_POSTS

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
