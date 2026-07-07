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
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
ACCESS_TOKEN  = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
PERSON_ID     = os.getenv("LINKEDIN_PERSON_ID", "")

DATA_DIR      = Path(os.path.dirname(os.path.abspath(__file__)))
POSTED_LOG    = DATA_DIR / "linkedin_posted.json"
TOKEN_FILE    = DATA_DIR / "linkedin_token.json"
COOLDOWN_FILE = DATA_DIR / "linkedin_last_post.json"
MIN_HOURS_BETWEEN_POSTS = 20

BOOK_CALL      = "https://calendly.com/grayhorizonsenterprise/30min"
DEMO_LINE      = "+1 (903) 627-8040"
FIVERR_GHL     = BOOK_CALL
FIVERR_VOICE   = BOOK_CALL
FIVERR_LEAD    = BOOK_CALL
# Primary CTA: demo line first, Calendly second — the AI sells itself
CTA = f"Call {DEMO_LINE} right now. It answers like a real receptionist. Takes 90 seconds.\n\nTo get yours built for your business: {BOOK_CALL}"
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
    f"""The average HVAC company takes 47 hours to respond to a new lead.

After 5 minutes, the chance of closing that lead drops by 80%.

If someone's AC goes out on Saturday afternoon and they call you, they have already booked your competitor by Sunday morning.

One missed call in HVAC is worth $1,200 to $4,000.

The fix is not more staff. It is a system that responds in under 15 seconds, 24 hours a day.

{CTA}""",

    f"""Someone in your service area is having an HVAC emergency right now.

They are calling 3 companies at 9:47pm.

What happens when they call yours?

If nobody answers, they move on. If they hit voicemail, they move on.

The first voice they hear is the one that books the job.

Setup: $997. Monthly: $297. First recovered job covers the cost.

{CTA}""",

    f"""Simple math for a roofing contractor.

Average storm job: $8,000 to $12,000.
Missed calls per week after hours: 3 to 6.
If 30% would have booked: 1 to 2 jobs lost per week.

The Autonomous Front Desk answers every call in under 15 seconds. It costs $997 to set up.

One recovered job pays for the setup 8 to 12 times over.

{CTA}""",

    f"""A solar installer was spending $3,200 a month on Facebook ads and closing 4 out of every 50 leads.

The problem was not the ads. Every lead went to a voicemail or a callback 2 days later.

We put an AI front desk on his inbound line. It answered every inquiry in under 15 seconds, qualified by bill size, and sent a booking text automatically.

He closed 11 jobs the next month. Same ad budget. Nothing else changed.

{CTA}""",

    f"""Before you read any more about this, call this number: {DEMO_LINE}

It will answer. It will ask what you need. It will collect your information and tell you a technician will follow up within the hour.

That is exactly what every caller to your business would hear, 24 hours a day, even at 2am on a Sunday.

That is the Autonomous Front Desk. $997 to set up. $297 a month to run.

To get yours configured for your company name and services: {BOOK_CALL}""",

    f"""This HVAC owner was spending $4,000 a month on Google Ads and closing 9 out of 48 leads every month.

Same leads for three years. He thought it was a traffic problem.

It was not. It was a follow-up problem.

We built instant SMS on every form submission, missed call text-back, and 7 follow-up touches over 2 weeks.

Next month: same 48 leads, same budget. 23 closes.

Nothing changed except what happened after the lead came in.

{CTA}""",

    f"""A roofing lead called at 7pm. Nobody answered. No callback until the next morning.

By then they had already booked with someone else.

That lead was worth $4,800. Gone because of one missed call and a 14-hour response gap.

We set up a missed call text-back that fires in under 10 seconds.

That one client recovered 6 leads in the first month that would have walked.

{CTA}""",

    f"""11:47pm. A lead filled out an HVAC form.

11:47:52. Automated SMS fires.

11:51pm. They reply: "Tomorrow morning works."

Calendar invite sent. Owner notified. Done.

Nobody touched this. Nobody was awake. The system handled it start to finish.

What happens to leads that come into your business after hours right now?

{CTA}""",

    f"""This contractor had 60 inbound leads last month. He only followed up on 38 of them.

The other 22 went to voicemail and were never contacted again. He had no idea.

We built a sequence that follows up automatically for 14 days without anyone touching it.

4 of those 22 converted in week two. Revenue recovered from leads he had already written off.

{CTA}""",

    f"""Two HVAC companies. Same neighborhood. Same ad budget. One closing 9 leads a month, the other closing 19.

Same product. Same price. Same market.

The difference: one responds to new leads in under 60 seconds. The other averaged 4 hours.

We fixed the response speed for the slower one. Closes went from 9 to 21 the next month. Nothing else changed.

{CTA}""",
]

AI_SERVICES_POSTS = [
    f"""I am not selling you a tool.

What I build is called the Autonomous Front Desk. It answers every call to your service business in under 15 seconds, 24 hours a day, collects the lead's name and phone number, and routes it automatically.

No staff. No voicemail. No missed jobs.

$997 to set up. $297 a month to run. One recovered job in month one covers the cost.

{CTA}""",

    f"""A contractor called me last month after his GHL subscription had been renewing for 8 months.

He had never set up a single automation.

$2,376 spent. Zero workflows running. Leads going to voicemail. Calendar managed in a Notes app on his phone.

We built the full system in 5 days. Instant SMS on every form. Missed call text-back in under 10 seconds. 7-touch follow-up over 14 days.

First month: 14 jobs closed from leads he had no system to track before.

{CTA}""",

    f"""An HVAC company was missing 14 calls a week and nobody had done the math on what that cost them.

Average job value: $1,200. If 30% of those calls would have booked, that is $5,040 a week going to voicemail.

We put an AI front desk on their inbound line. It answers every call, qualifies in 90 seconds, and texts a booking link automatically.

Week one: 11 jobs booked from calls that would have gone to voicemail.

{CTA}""",

    f"""This roofing contractor had never booked a single job after 6pm in 6 years of being open.

Every after-hours call went to voicemail. Nobody called back until morning. By then the job was gone.

We set up an AI voice agent that answers every call, qualifies the job, and texts a booking link automatically.

First storm season after launch: 11 emergency jobs booked overnight. Owner woke up to a full calendar.

{CTA}""",

    f"""A landscaping company had 41 form submissions last month. 14 of them never got a reply within 24 hours.

Those 14 people booked with someone else.

We built an instant SMS follow-up that fires in under 60 seconds of every new form submission.

9 jobs recovered in the first week. Zero new ad spend.

{CTA}""",

    f"""A plumbing company running 3 trucks was managing their entire pipeline in a Notes app.

Leads called in. Someone wrote it down. Half the follow-ups never happened.

We built a setup that captures every inbound call, fires a text confirmation, and runs a 5-touch follow-up automatically.

They closed 14 jobs in the first 30 days from leads they would have previously lost.

{CTA}""",

    f"""A garage door company was calling back inbound leads 2 days after they came in.

By then the customer had already booked whoever picked up first.

We set up an AI front desk that answers every call, captures the job details, and fires a booking text in under 60 seconds.

First month: 8 warm leads recovered. No extra headcount. No bigger budget.

{CTA}""",

    f"""The four things I check in every service business before I build anything:

What happens the second someone fills out your form?
How many times does your team follow up before they stop?
When did you last call a new lead back in under 5 minutes?
Do you have any automations running that you have not manually checked in 30 days?

Nine times out of ten, it is not the leads. It is what happens after the lead comes in.

{CTA}""",
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

TEACHING_POSTS = [
    f"""A dental office in Orange County was missing 22 calls a week.

Nobody tracked it until I asked them to pull the voicemail log.

New patient average: $1,400. If 30 percent would have booked, that is $9,240 walking out the door every week.

They had no idea because nobody ever added up the cost of not answering.

We put an AI front desk on their inbound line. It answers every call, asks the patient what they need, and books them straight to the calendar.

Week one: 14 calls handled after hours that would have gone to voicemail.

What does your phone do at 9pm when a new patient calls?

Call {DEMO_LINE} to hear exactly what it would sound like for your practice.""",

    f"""I called 11 HVAC companies in Southern California last Tuesday at 8:47pm.

7 went to voicemail. 3 had a recording. 1 answered.

That company closed me as a lead before I finished the call.

The other 10 will follow up in the morning. By then I have already booked.

This is happening to your business every single day. The leads do not wait.

Call {DEMO_LINE} and hear what the company that answered sounds like.""",

    f"""A solar company in San Diego was spending $4,800 a month on Google Ads.

Closing 5 percent of leads. Owner thought the leads were low quality.

We looked at the response data. The average time from form submission to first contact: 31 hours.

By that point the homeowner had already had a site visit with someone else.

Same budget. Same leads. We added an AI front desk that contacted every inbound inquiry in under 15 seconds.

Conversion rate went to 14 percent the next month.

The leads were fine. The response was broken.

What is your average lead response time right now?""",

    f"""A roofing contractor in Riverside missed 6 calls last weekend.

Saturday afternoon storm. Homeowners calling 3 companies each.

He was on a job site and his phone was in his truck.

Those 6 calls were worth an estimated $48,000 to $72,000 in potential jobs.

He found out Monday when he checked voicemail.

I built a system that answers every call in under 15 seconds no matter where you are. Qualifies the job. Texts you a summary. Books the inspection automatically.

He has not missed a lead since.

Call {DEMO_LINE} and hear what his callers hear now.""",

    f"""Plumber gets a call at 11:43pm. Burst pipe. Customer panicking.

Old setup: straight to voicemail. Customer calls the next company. Job gone.

New setup: AI front desk answers in 3 seconds. Gets the address and situation. Texts the plumber immediately. Sends the customer a confirmation that someone is coming.

Plumber closes the job at midnight. $1,800 emergency call.

That job would not have existed under the old system.

How many emergency calls are hitting your voicemail right now?

Call {DEMO_LINE} to hear the system in action.""",

    f"""A dental practice was sending a new patient intake form after the appointment was booked.

Most people never filled it out. Half the ones who did still had to repeat everything at the front desk.

We automated the intake to fire the moment the appointment was confirmed. Reminder 48 hours before. Second reminder 2 hours before. Cancellation catch with an immediate rebooking link.

No-show rate dropped from 18 percent to 6 percent.

Nobody changed anything about how they ran the office. Just what happened automatically between booking and arrival.

What percentage of your appointments no-show right now?""",

    f"""An HVAC owner told me he gets about 3 calls a night after hours.

He said he figured most of them were not real leads.

We turned on the AI front desk and tracked the first 30 days.

61 after-hours calls. 34 qualified leads. 9 booked appointments. 7 closed jobs.

Average job: $1,400.

He had been writing off $9,800 a month in potential revenue as "not real leads."

They were real. They were just going to voicemail.

Call {DEMO_LINE} right now. It is running live.""",

    f"""The contractor who is winning in your market is not outspending you on ads.

He is just faster.

Studies on lead response time show that calling within 5 minutes is 21 times more effective than calling within 30 minutes.

Most contractors call back the next morning.

The first voice a customer hears is usually the one that gets the job.

That is the entire game. Response speed.

Call {DEMO_LINE} and hear what 15-second response sounds like.""",

    f"""I took on 3 service businesses last quarter for what I call a Quick Win build.

One automation. The one that makes the biggest difference in the first 30 days.

Every single time it was the same thing: missed call text-back.

When someone calls and you do not answer, they get an automatic text in under 10 seconds. It says you are with a client, you will call back shortly, and here is a link to book online if they want.

Average recovery rate across all three: 31 percent of missed calls converted to booked jobs.

One of those businesses recovered 14 jobs in 30 days they would have never seen.

What would 14 extra jobs a month do for your revenue?""",

    f"""I asked a roofing contractor in Fresno how many leads he lost last year because nobody answered.

He said he did not know.

I asked how many calls went to voicemail after 5pm.

He said probably 4 or 5 a week.

Average roofing job in Fresno: $8,500.

4 calls a week. 30 percent booking rate. 52 weeks.

That is 62 jobs. $527,000 in potential revenue going to voicemail every year.

He sat with that number for a minute.

Then he asked how fast we could get it set up.

Call {DEMO_LINE} to hear exactly what his callers hear now.""",
]

DEMO_POSTS = [
    f"""I set up an AI receptionist for a Riverside roofer.

Before he signed anything, I told him to call one number.

{DEMO_LINE}

He called at 8:43pm on a Wednesday.

It answered in 2 seconds. Greeted him as a potential customer. Asked what the job was. Offered to book an appointment.

He texted me after: "That's wild. How fast can we get this on my line?"

90 seconds is all it takes to hear what your business should sound like after hours.

Call it yourself. No login. No sales call. Just the demo.

Full system walkthrough at grayhorizonsenterprise.com""",

    f"""Most contractors have never heard what happens when someone calls their business at 11pm.

I built a system that answers that call in under 3 seconds, 24 hours a day.

Call {DEMO_LINE} right now and hear it yourself.

It answers like a real receptionist. Takes a job request. Offers to book.

The whole thing runs without a single staff member.

If you want to see how it works for your business: grayhorizonsenterprise.com""",

    f"""I called 11 HVAC companies last Tuesday at 8:47pm.

1 answered.

That company booked a $2,200 job that night.

The other 10 lost it to voicemail.

Call {DEMO_LINE} to hear what that one company sounds like now.

Then go to grayhorizonsenterprise.com to see the full system.""",
]

AUDIT_POSTS = [
    f"""Want to know exactly how many calls your business missed last week?

I will do a free 5-minute missed call audit for the first 3 businesses that comment below.

HVAC, roofing, solar, plumbing, or dental — does not matter the niche.

I will tell you:
- Estimated missed calls per week based on your industry average
- What that costs you in lost revenue annually
- Whether an AI front desk would pay for itself in month 1

No pitch. Just the numbers.

Comment your niche below and I will send you the breakdown.""",

    f"""I did a free missed call audit for a San Diego plumber last month.

He had no idea how many calls he was losing after hours.

The math:
Industry average after-hours call rate for plumbing: 34% of total calls
His monthly call volume (based on Google listing): ~280 calls
After-hours estimate: 95 calls per month
Industry answer rate after hours: 31%
Missed: 66 calls per month
Average emergency plumbing job: $680
At 30% conversion: $13,453 in missed revenue every single month.

He booked a setup call the same day I sent him the breakdown.

If you want me to do this for your business, comment your city and niche below.

No cost. No obligation. Just the real number.""",

    f"""Most service business owners have no idea what their missed calls are costing them.

Not because they do not care.

Because nobody has ever shown them the math.

I will do it for free.

If you run an HVAC, roofing, solar, plumbing, or dental business in California — comment below with your niche and I will send you a missed call cost breakdown specific to your market.

Takes me 5 minutes to run. Costs you nothing.

The number is almost always shocking.

Call {DEMO_LINE} to hear what the solution sounds like while you wait.""",
]

# LINKEDIN ONLY: GHL automation + AI services posts
# NEVER add EDGE_ENGINE_POSTS or PRODUCT_POSTS here — trading content stays on Twitter/X only
ALL_POSTS = GHL_POSTS + AI_SERVICES_POSTS + TEACHING_POSTS + DEMO_POSTS + AUDIT_POSTS

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

def check_cooldown():
    """Returns (ok_to_post, hours_since_last). Enforces MIN_HOURS_BETWEEN_POSTS."""
    if not COOLDOWN_FILE.exists():
        return True, None
    try:
        data = json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(data["last_post"])
        elapsed = (datetime.now() - last).total_seconds() / 3600
        if elapsed < MIN_HOURS_BETWEEN_POSTS:
            return False, elapsed
        return True, elapsed
    except Exception:
        return True, None

def record_post_time():
    COOLDOWN_FILE.write_text(
        json.dumps({"last_post": datetime.now().isoformat()}), encoding="utf-8"
    )

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

    ok, elapsed = check_cooldown()
    if not ok:
        print(f"[SKIP] Posted {elapsed:.1f}h ago — cooldown active ({MIN_HOURS_BETWEEN_POSTS}h minimum). No post sent.")
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
        record_post_time()
        preview = post_text[:80].replace("\n", " ")
        print(f"[POSTED] {preview}...")
    else:
        print(f"[ERROR] Status {status}: {response}")

if __name__ == "__main__":
    if "--auth" in sys.argv:
        run_auth()
    else:
        main()
