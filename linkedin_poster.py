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

FIVERR_GHL   = "https://grayhorizonsenterprise.com"
FIVERR_VOICE = "https://grayhorizonsenterprise.com"
FIVERR_LEAD  = "https://calendly.com/grayhorizonsenterprise/30min"
GUMROAD_LINK = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")

# ── Content Pools ──────────────────────────────────────────────────────────────

GHL_POSTS = [
    f"""talked to an HVAC owner last week who was spending $4k/month on google ads.

48 leads a month. closing 9.

not a lead problem. a follow up problem.

built out his GHL, got instant SMS firing on every form submission, missed call text-back, 7 touches over 2 weeks.

next month same 48 leads. 23 closes.

same budget. just fixed what happens after the lead comes in.

{FIVERR_GHL}""",

    f"""real scenario from a roofing client.

lead calls at 7pm. goes to voicemail. no callback until next morning.

by then the lead already booked with someone else.

the missed call text-back went live that week. fires in under 10 seconds. "hey sorry i missed you, what can i help with?"

recovered 6 leads in the first month that would have been gone.

what does a missed call cost you? genuinely asking.

{FIVERR_GHL}""",

    f"""11:47pm. someone fills out an HVAC form.

11:47:52 automated SMS goes out.

11:51 they reply "tomorrow morning works."

calendar invite sent. owner gets notified. done.

nobody touched this. nobody was awake. nobody had to do anything.

that's what we set up. {FIVERR_GHL}""",

    f"""paying $297/month for GHL with zero automations running is like buying a truck and leaving it in the garage.

i see this constantly.

no workflows. no follow up sequences. leads coming in and getting responded to 6 hours later by a human who forgot.

a properly set up GHL replaces a receptionist, a follow up VA, and a booking coordinator.

if you're on GHL and still doing it manually, something's wrong with the build.

{FIVERR_GHL}""",

    f"""honest question for any service business owner reading this:

what actually happens when someone fills out your contact form at 10pm?

if the answer is "we get to it in the morning" you are losing a percentage of every lead you pay for.

the window is 5 minutes. after that the conversion rate tanks.

not trying to sell you anything right now. just a real question worth sitting with.

{FIVERR_GHL}""",

    f"""most owners i talk to think they have a lead problem.

they don't. they have a speed problem.

same leads, competitor responds in 45 seconds vs your team responding in 4 hours. competitor wins.

the fix isn't hiring. it's automating the first 3 to 5 touches so no human has to be involved until the lead is actually warm.

drop your average response time in the comments. curious where people are at.

{FIVERR_GHL}""",
]

AI_SERVICES_POSTS = [
    f"""dental office. 22 missed calls a week.

they knew the number because they checked. they didn't know the revenue number because they never did the math.

new patient avg value: $1,400. 30% of those calls would have converted. that's $9,240 a week going to voicemail.

put an AI voice agent on their inbound line. answers every call, qualifies in 90 seconds, books straight to the calendar.

week one: 14 bookings that would have been missed.

the math isn't complicated. {FIVERR_VOICE}""",

    f"""the HVAC company answering calls at 2am with an AI agent is booking jobs while the competitor sleeps.

the contractor with 14-day automated follow up is closing leads on day 9 that the other guy gave up on day 2.

this isn't a prediction. it's already happening. in every market.

the businesses that move on this in the next 6 months are going to look very different from the ones that wait.

{FIVERR_LEAD}""",

    f"""3 things i ask every business owner before we build anything:

what happens the second someone fills out your form?
how many times does your team follow up before they stop?
when did you last call a lead back in under 5 minutes?

the answers tell me exactly where the revenue is leaking.

9 times out of 10 it's not the leads. it's what happens after.

what does your follow up look like right now? be real in the comments.

{FIVERR_LEAD}""",

    f"""there's a version of your business where leads never sit cold.

where every inquiry gets a response before a minute passes.
where follow up runs for 30 days without your team lifting a finger.
where your calendar fills itself.

none of that requires more staff. just a different setup.

we build that in 5 days. {FIVERR_GHL}""",

    f"""the businesses that scale over the next few years won't necessarily be the biggest.

they'll be the ones running lean with the right systems underneath.

one person with a properly built CRM and automation stack outperforms a 5 person team on spreadsheets.

we build those systems. HVAC. roofing. dental. contractors. HOA.

if you want to see what it looks like for your operation: {FIVERR_LEAD}""",
]

EDGE_ENGINE_POSTS = [
    f"""most traders don't lose because they pick bad setups.

they lose because they size based on how confident they feel.

that's not an edge. that's gambling with extra steps.

win rate 55%. average win 2x the average loss. size at Kelly. that compounds into something real over time.

built that math directly into the Edge Engine. every signal comes with a score and a size.

{GUMROAD_LINK}""",

    f"""congress members disclosed $213M in trades last quarter.

45 days to report under the STOCK Act. but the footprint shows up in options flow before the disclosure.

not every trade is actionable. but when it lines up with the volume and momentum signals, it's worth watching.

we track all of it and run it through the scoring model automatically.

{GUMROAD_LINK}""",

    f"""an edge isn't a hot tip from a discord server.

it's a process that has positive expected value over hundreds of trades.

RSI divergence. volume 40% above the 30-day avg. EMA cross with a confirmation candle.

when all three line up the score clears 75. that's when we look closer.

when none of them align we sit on our hands. that part is harder than it sounds.

{GUMROAD_LINK}""",

    f"""nobody talks about this but i will:

no signal system wins every time. anyone selling you that is lying.

what a real system does: positive expected value over time. more wins than losses. small losses, bigger wins.

we log every signal and every result. open book. if it stops working we say so.

{GUMROAD_LINK}""",
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
