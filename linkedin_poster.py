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
    f"""This HVAC owner was spending $4,000 a month on Google Ads and closing 9 out of 48 leads every month.

Same leads for three years. He thought it was a traffic problem.

It was not. It was a follow-up problem.

We built out his GHL with instant SMS on every form submission, missed call text-back, and 7 touches over 2 weeks.

Next month: same 48 leads, same budget. 23 closes.

Nothing changed except what happened after the lead came in.

What is your lead-to-close rate right now?

{FIVERR_GHL}""",

    f"""A roofing lead called at 7pm. Nobody answered. No callback until the next morning.

By then they had already booked with someone else.

That lead was worth $4,800. Gone because of one missed call and a 14-hour response gap.

We set up a missed call text-back that fires in under 10 seconds: "Hey, sorry I missed you. What can I help with?"

That one client recovered 6 leads in the first month that would have walked.

How many calls does your business miss after 5pm each week?

{FIVERR_GHL}""",

    f"""11:47pm. A lead filled out an HVAC form.

11:47:52. Automated SMS fires.

11:51pm. They reply: "Tomorrow morning works."

Calendar invite sent. Owner notified. Done.

Nobody touched this. Nobody was awake. The system handled it start to finish.

What happens to leads that come into your business after hours right now?

{FIVERR_GHL}""",

    f"""A roofing company was paying $297 a month for GHL with zero automations running.

Leads were sitting for 6 hours before anyone called back. Calendar managed on paper.

We built the full workflow in 48 hours: instant form response, missed call text-back, 7-touch follow-up sequence.

First 30 days: 11 more closes than the month before. Same ad budget. Nothing else changed.

Is your CRM actually doing anything for you right now?

{FIVERR_GHL}""",

    f"""This contractor had 60 inbound leads last month. He only followed up on 38 of them.

The other 22 went to voicemail and were never contacted again. He had no idea.

We built a GHL sequence that follows up automatically for 14 days without anyone touching it.

4 of those 22 converted in week two. Revenue recovered from leads he had already written off.

How many leads did your team write off last month without realizing it?

{FIVERR_GHL}""",

    f"""Two HVAC companies. Same neighborhood. Same ad budget. One closing 9 leads a month, the other closing 19.

Same product. Same price. Same market.

The difference: one responds to new leads in under 60 seconds. The other averaged 4 hours.

We fixed the response speed for the slower one. Nothing else changed. Closes went from 9 to 21 the next month.

How long does it take your team to respond to a new lead that just came in?

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""A dental office was missing 22 calls a week and nobody had done the math on what that actually cost them.

New patient average value: $1,400. If 30% of those calls would have booked, that is $9,240 a week going to voicemail.

We put an AI voice agent on their inbound line. It answers every call, qualifies in 90 seconds, and books straight to the calendar.

Week one: 14 appointments booked that would have been missed calls.

Do you know how many calls your business misses in a week?

{FIVERR_VOICE}""",

    f"""This roofing contractor had never booked a single job after 6pm in 6 years of being open.

Every after-hours call went to voicemail. Nobody called back until morning. By then the job was gone.

We set up an AI voice agent that answers every call, qualifies the job, and texts a booking link automatically.

First storm season after launch: 11 emergency jobs booked overnight. Owner woke up to a full calendar.

What happens when someone calls your business after hours tonight?

{FIVERR_LEAD}""",

    f"""34 people filled out a form on this med spa's website last month. 11 of them never heard back within 24 hours.

Those 11 people were gone. They booked somewhere else.

We built an instant SMS follow-up and AI qualifier that fires in under 60 seconds of form submission.

9 appointments booked from the backlog in the first week. Zero new ad spend.

How fast does your team follow up on a new form submission right now?

{FIVERR_LEAD}""",

    f"""A law firm with 3 receptionists was still losing 18% of their inbound calls every single day.

Potential clients were hanging up during lunch hour and calling the next firm on Google.

We built an AI intake agent to handle overflow calls and qualify prospects automatically.

Consultation bookings up 40% in 30 days. No new hires. No bigger team. Same staff.

What does your business do when all your lines are busy?

{FIVERR_GHL}""",

    f"""200 people started a free trial at this gym last quarter. 80 of them disappeared after day 7 with no follow-up at all.

No check-in. No message. No reason to come back.

We built an automated sequence that fires at day 3, day 6, and day 10 with a personal check-in message.

31 converted to paid memberships in 60 days. Same leads, no extra cost.

What does your follow-up look like after someone goes quiet?

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
