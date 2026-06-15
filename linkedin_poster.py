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

    f"""Paying $297/month for GHL with zero automations running is like buying a truck and leaving it in the garage.

I see this constantly.

No workflows. No follow-up sequences. Leads coming in and sitting for 6 hours until someone remembers to call back.

A properly built GHL can replace a receptionist, a follow-up VA, and a booking coordinator.

If you're on GHL and still doing it manually, something is off with the setup.

{FIVERR_GHL}""",

    f"""Honest question for any service business owner reading this:

What actually happens when someone fills out your contact form at 10pm?

If the answer is "we get to it in the morning," you're losing a percentage of every lead you're paying for.

The window is 5 minutes. After that, conversion drops fast.

Not trying to sell you anything right now. Just a real question worth sitting with.

{FIVERR_GHL}""",

    f"""Most owners I talk to think they have a lead problem.

They don't. They have a speed problem.

Same leads. Competitor responds in 45 seconds. Your team responds in 4 hours. Competitor wins.

The fix isn't hiring more people. It's automating the first 3 to 5 touches so no one has to be involved until the lead is actually warm.

Drop your average response time in the comments. Curious where people are at.

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""Dental office. 22 missed calls a week.

They tracked the number. They never did the math on the revenue.

New patient average value: $1,400. If 30% of those calls would have converted, that's $9,240 a week going to voicemail.

We put an AI voice agent on their inbound line. Answers every call, qualifies in 90 seconds, books straight to the calendar.

Week one: 14 bookings that would have been missed.

The math isn't complicated. {FIVERR_VOICE}""",

    f"""The HVAC company answering calls at 2am with an AI agent is booking jobs while the competition sleeps.

The contractor with a 14-day automated follow-up is closing leads on day 9 that the other guy gave up on day 2.

This isn't a prediction. It's already happening in every market right now.

The businesses that move on this in the next 6 months are going to look very different from the ones that wait.

{FIVERR_LEAD}""",

    f"""Three things I ask every business owner before we build anything:

What happens the second someone fills out your form?
How many times does your team follow up before they stop?
When did you last call a lead back in under 5 minutes?

The answers tell me exactly where the revenue is leaking.

Nine times out of 10, it's not the leads. It's what happens after.

What does your follow-up look like right now? Be honest in the comments.

{FIVERR_LEAD}""",

    f"""There's a version of your business where leads never sit cold.

Where every inquiry gets a response in under a minute.
Where follow-up runs for 30 days without your team lifting a finger.
Where your calendar fills itself.

None of that requires more staff. Just a different setup.

We build that in 5 days. {FIVERR_GHL}""",

    f"""The businesses that scale over the next few years won't necessarily be the biggest.

They'll be the ones running lean with the right systems underneath.

One person with a properly built CRM and automation stack can outperform a 5-person team running on spreadsheets.

We build those systems for HVAC, roofing, dental, contractors, and HOA companies.

If you want to see what it looks like for your operation: {FIVERR_LEAD}""",
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
    f"""If you run a contracting business and you're still following up manually, you're losing jobs to whoever responds first.

We put together a full playbook on how to automate your lead follow-up, booking, and client intake.

No fluff. Just the system.

{GUMROAD_CONTRACTOR}""",

    f"""AI automation for small business doesn't have to be complicated.

I put together a guide covering exactly what to automate first, what tools to use, and how to set it up without a tech background.

If you're still doing things manually that a $12 tool could handle, this is worth your time.

{GUMROAD_AI_BIZ}""",

    f"""HOA managers are drowning in violation tracking, notices, and follow-up.

Most are still doing it on spreadsheets or email chains.

We put together a guide on how to automate the whole process — from violation report to resident notice to compliance log.

{GUMROAD_HOA}""",

    f"""The sports betting edge most people miss isn't picking winners.

It's Kelly sizing and expected value. Bet too big on a good edge and variance wipes you out. Size correctly and it compounds.

We built a full breakdown of the math and the model.

{GUMROAD_BETS}""",

    f"""Stock trading for people who have a job and a life.

Not day trading. Not screen-watching. Institutional flow signals, RSI, congressional trades — filtered and scored daily.

You get the signal. You decide. Takes 10 minutes a day.

{GUMROAD_TRADING}""",
]

ALL_POSTS = GHL_POSTS + AI_SERVICES_POSTS + EDGE_ENGINE_POSTS + PRODUCT_POSTS

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
