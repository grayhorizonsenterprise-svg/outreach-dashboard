"""
yt_content_generator.py — Gray Horizons Enterprise
Generates ready-to-record YouTube scripts for 3 channels and 4 content types.
Run daily to get a fresh batch of video ideas with full scripts.

Channels:
  1. GHE Automation — AI automation tutorials for local service businesses
  2. Edge Engine — Trading signals, market analysis, position sizing education
  3. ShadowClans — Narrative / storytelling / brand content

Output: yt_scripts/ folder — one .txt file per script, ready to read on camera
"""

import os
import json
import random
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "yt_scripts"
OUTPUT_DIR.mkdir(exist_ok=True)

LOG_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "yt_generator_log.json"

# ── GHE AUTOMATION CHANNEL ────────────────────────────────────────────────────

GHE_TUTORIALS = [
    {
        "title": "How I Built an AI Voice Agent That Books HVAC Appointments Automatically",
        "hook": "HVAC companies lose 40 percent of their calls to voicemail every peak season. I built a system that answers every single one without a human touching it. Here is exactly how.",
        "sections": [
            ("The Problem", "Peak season. Techs are on jobs. Calls come in. Nobody answers. Customer calls the next company on Google."),
            ("What We Built", "A Vapi AI voice agent connected to the business phone number. It answers, asks for name, address, issue type, and urgency. Emergency jobs get flagged instantly."),
            ("The Tech Stack", "Vapi for the voice layer. GoHighLevel for the CRM and pipeline. Webhook to connect them. The whole build took about 4 hours."),
            ("Live Demo", "Walk through the actual dashboard. Show a real call transcript. Show the booking confirmation that fired automatically."),
            ("Results", "Zero missed calls. Every job logged. Customer gets a confirmation text before they hang up. Tech gets the job details on their phone."),
        ],
        "cta": "If you want this built for your business, the link is in the description. We demo it for free before you pay anything.",
        "tags": "HVAC automation, AI voice agent, Vapi, GoHighLevel, small business AI, missed call automation",
        "thumbnail": "AI ANSWERS EVERY CALL | Zero missed jobs | Show Vapi dashboard screenshot",
    },
    {
        "title": "I Built a Lead Follow-Up System That Never Forgets a Prospect",
        "hook": "Most contractors lose a job not because they gave a bad estimate but because they forgot to follow up. I automated the entire thing. Here is how it works.",
        "sections": [
            ("The Real Problem", "Estimates get sent. Client says they will think about it. Contractor moves on. 5 days later the client hired someone else who called twice."),
            ("The Automated Follow-Up", "Every estimate sent triggers a sequence. Day 3: text message. Day 5: email. Day 8: final check-in. Runs automatically until they respond or opt out."),
            ("Building It in GHL", "Show the workflow inside GoHighLevel. Trigger. Wait step. SMS action. Branch logic for if they reply."),
            ("What Changed", "Close rate example. Before: 22 percent. After automated follow-up: 39 percent in 60 days. Same leads. Same prices. Just better follow-up."),
            ("You Can Copy This", "Walk through how to set this up yourself or hire someone to do it."),
        ],
        "cta": "I build these systems for contractors and service businesses. Book a free demo at the link below.",
        "tags": "contractor automation, lead follow-up, GoHighLevel workflow, CRM automation, sales automation",
        "thumbnail": "NEVER LOSE A LEAD AGAIN | Automated follow-up system | Show GHL pipeline",
    },
    {
        "title": "How Dental Offices Can Stop Losing Patients to Voicemail",
        "hook": "40 percent of new patient calls come in after your front desk goes home. Most of those calls never get returned. I built a system that captures every one of them.",
        "sections": [
            ("The After-Hours Problem", "New patient calls at 7pm. Hits voicemail. Does not leave a message. Calls the next dentist on the list who has a chat widget that responds instantly."),
            ("What the System Does", "AI answers the call after hours. Collects name, callback number, reason for calling, preferred appointment window."),
            ("The Morning Briefing", "Every morning the front desk gets a sorted list: name, number, reason, best time to call back. No missed patients. No manual logging."),
            ("Reminder and Recall Sequences", "Appointment reminders fire automatically 48 hours and 2 hours before. Overdue patients get a recall text sequence that runs until they respond."),
            ("What This Is Worth", "One recovered new patient is worth $500 to $2,000 in lifetime value. The system costs less than one patient."),
        ],
        "cta": "We will show you a live demo built for a dental practice before you pay anything. Link in description.",
        "tags": "dental office automation, patient intake, after-hours calls, appointment reminders, healthcare AI",
        "thumbnail": "STOP LOSING PATIENTS TO VOICEMAIL | AI after-hours system | Show Vapi transcript",
    },
    {
        "title": "What I Built for HOA Managers to Stop Drowning in Email",
        "hook": "HOA managers spend 20 hours a week on emails that a system could handle automatically. Here is the exact setup I built that eliminated most of that manual work.",
        "sections": [
            ("The Problem", "Maintenance requests. Violation notices. Vendor follow-up. Board meeting reminders. All done manually. Things fall through the cracks constantly."),
            ("Request Intake and Auto-Ack", "Every resident request gets an instant acknowledgment. The system logs it, assigns it, and starts tracking it without the manager touching it."),
            ("Violation Notice Automation", "Violation reported. System drafts the notice. Manager reviews in 30 seconds and sends. Follow-up fires automatically if no response in 7 days."),
            ("Weekly Digest Report", "Every Monday morning: one report. Every open item, every resolved item, everything pending. No digging through email threads."),
            ("The Result", "20 hours a week back. Every item tracked. Nothing falls through."),
        ],
        "cta": "If you manage HOA communities and want this built, the demo is free. Link below.",
        "tags": "HOA management automation, property management AI, workflow automation, violation tracking",
        "thumbnail": "20 HOURS SAVED PER WEEK | HOA automation system | Show GHL dashboard",
    },
]

GHE_CASE_STUDIES = [
    {
        "title": "This Contractor Went from 22 to 39 Percent Close Rate in 60 Days",
        "hook": "Same leads. Same prices. Same service quality. The only thing that changed was the follow-up system. Here is what happened.",
        "sections": [
            ("Before", "Estimates sent. Average follow-up time: 12 days. Most homeowners make a decision in 5 days. He was following up after the decision was already made."),
            ("The Build", "Automated follow-up sequence. Text at day 3. Email at day 5. Final check-in at day 8. Personalized with the job type and estimate amount."),
            ("60 Days Later", "Close rate moved from 22 to 39 percent. That is roughly 8 additional closed jobs per month at his average ticket. Real numbers."),
            ("What You Can Take From This", "Follow-up timing matters more than follow-up volume. Being first is not enough. Being consistent wins."),
        ],
        "cta": "I build these systems. Book a free demo at the link in the description.",
        "tags": "contractor case study, sales automation, close rate improvement, lead follow-up",
        "thumbnail": "22% TO 39% CLOSE RATE | Real contractor results | 60 days",
    },
]

GHE_QUICK_TIPS = [
    {
        "title": "The One GHL Workflow Every Service Business Needs",
        "hook": "Most businesses set up a CRM and never build the workflow that makes it actually useful. Here is the one that changes everything in 30 minutes.",
        "sections": [
            ("What It Does", "New lead comes in from any source. Gets tagged. Gets an instant SMS. Gets added to the right pipeline stage. Gets a follow-up sequence started. All automatic."),
            ("How to Build It", "Trigger: contact created. Action 1: send SMS. Action 2: add to opportunity. Action 3: start workflow. Walk through each step live in GHL."),
            ("Why It Matters", "The first business to respond wins 78 percent of the time. This gets you there in under 90 seconds automatically."),
        ],
        "cta": "Subscribe for more builds like this. Full system builds at the link below.",
        "tags": "GoHighLevel tutorial, GHL workflow, CRM automation, lead response, quick tutorial",
        "thumbnail": "THE ONE WORKFLOW YOU NEED | GHL setup in 30 min | Screen recording",
    },
]

GHE_TOOL_REVIEWS = [
    {
        "title": "Vapi vs Retell AI: Which Voice Agent Platform Is Actually Better in 2026",
        "hook": "I have built with both. Here is the honest comparison nobody else is giving you because most reviewers have not actually shipped a real project with either one.",
        "sections": [
            ("Setup Complexity", "Vapi: more configuration upfront but more control. Retell: faster initial setup but less flexibility. Winner depends on use case."),
            ("Voice Quality", "Both use leading LLMs. Vapi gives you more control over voice selection and latency settings. Retell has better out-of-the-box defaults for simple use cases."),
            ("CRM Integration", "Vapi webhooks are more flexible for custom GHL integrations. Retell has native integrations that are faster to deploy."),
            ("Pricing", "Break down the per-minute costs. At scale, the math matters. Walk through real numbers."),
            ("My Recommendation", "For complex custom builds with specific CRM requirements: Vapi. For fast deployment on standard use cases: Retell. Either way you need someone who knows both."),
        ],
        "cta": "I build custom voice agents for service businesses. Link in description.",
        "tags": "Vapi vs Retell, AI voice agent comparison, voice AI 2026, Vapi review, Retell AI review",
        "thumbnail": "VAPI vs RETELL | Honest comparison | 2026 | Real projects only",
    },
]

# ── EDGE ENGINE CHANNEL ────────────────────────────────────────────────────────

EDGE_EDUCATION = [
    {
        "title": "Why 97 Percent of Traders Blow Up (It Has Nothing to Do With Their Entries)",
        "hook": "The number one reason trading accounts blow up is not bad picks. It is position sizing. Most traders never learn this until they lose everything. Here is what you need to know.",
        "sections": [
            ("The Myth", "Everyone obsesses over entry points. The perfect indicator. The perfect setup. Entry accounts for maybe 20 percent of your long-term outcome."),
            ("The Real Problem", "You can be right 60 percent of the time and still blow your account if you overleverage the 40 percent you lose. That is not a theory. That is math."),
            ("Kelly Criterion", "The formula: (Win rate times avg win minus loss rate times avg loss) divided by avg win. That number is the maximum fraction of your account to risk per trade."),
            ("Real Example", "Win rate 58 percent. Avg win 1.8R. Avg loss 1.0R. Kelly fraction: 14.4 percent. On a 10K account that is 1,440 dollars max risk. Not a guess. Math."),
            ("What Changes When You Size Right", "Same strategy. Same entries. Proper position sizing. The account survives the drawdowns and compounds the wins. That is the entire game."),
        ],
        "cta": "The Edge Engine includes a Kelly Criterion calculator built in. Link in description.",
        "tags": "position sizing, Kelly Criterion, trading psychology, risk management, trading education",
        "thumbnail": "WHY TRADERS BLOW UP | It is not your entries | Kelly Criterion explained",
    },
    {
        "title": "How Congressional Trade Tracking Actually Works (And Why Retail Ignores It)",
        "hook": "Congress members have up to 45 days to report their trades. Volume patterns appear in week one. By the time it is public, retail already missed most of the move. Here is how to track it.",
        "sections": [
            ("The Disclosure Window", "STOCK Act requires members to report trades within 45 days. Most file late. The average disclosure comes 30 days after the trade."),
            ("What the Volume Tells You", "Unusual volume on a ticker before a congressional disclosure is not random. It is a pattern. Tracking it is legal. It is public information."),
            ("How We Track It", "Every STOCK Act filing gets parsed. Tickers get flagged. Volume anomaly scanner runs against those tickers. Momentum score gets updated."),
            ("Real Examples", "Walk through 3 real historical examples where the volume pattern preceded the public disclosure and the price move."),
            ("How to Use This", "You are not front-running anyone. You are reading publicly available data faster than most retail traders. That is the edge."),
        ],
        "cta": "The Edge Engine tracks every disclosure as it drops. Link to join in description.",
        "tags": "congressional trading, STOCK Act, unusual volume, trading edge, market intelligence",
        "thumbnail": "CONGRESS TRADES BEFORE YOU | How to track it legally | Real data",
    },
]

EDGE_SIGNAL_RECAPS = [
    {
        "title": "This Week's Signal Sheet: 3 Setups That Scored 70 Plus",
        "hook": "Every week the Edge Engine scores every setup from 0 to 100. This week 3 scored above 70. Here is what they were and what happened.",
        "sections": [
            ("Setup 1", "Ticker, score, why it qualified, what happened after the flag. Specific numbers only."),
            ("Setup 2", "Same format. Honest about results whether they worked or not."),
            ("Setup 3", "Same format. Walk through the exit and final return."),
            ("The Week Overall", "How many setups were scored. How many qualified. Average result of the qualified ones."),
            ("What This Proves", "High conviction only. If it does not score 70 or above, we skip it. That filter is why the batting average holds."),
        ],
        "cta": "Get the signal sheet every morning before the open. Link in description.",
        "tags": "trading signals, weekly recap, stock picks, momentum trading, Edge Engine",
        "thumbnail": "THIS WEEK'S SIGNALS | 3 setups scored 70 plus | Real results",
    },
]

EDGE_MINDSET = [
    {
        "title": "The Boring Trading Strategy That Actually Compounds",
        "hook": "The best trading strategy I have ever used is also the most boring. One setup per week. Full Kelly sizing. Hold. Log it. Repeat. Here is why boring wins.",
        "sections": [
            ("Why Exciting Trades Lose", "High activity equals high fees, high emotional involvement, and high error rate. Traders who trade every day underperform traders who wait for high conviction."),
            ("The Boring Process", "Monday: check the signal sheet. One setup above 70. Size it correctly. Place the order. Go to work. Check it Friday."),
            ("The Math Over 52 Weeks", "If you average one trade per week at 8.2 percent return on properly sized positions, walk through what that does to a 10K account over a year."),
            ("What Gets in the Way", "Boredom. FOMO. The urge to trade something even when nothing qualifies. The discipline to skip is the entire skill."),
        ],
        "cta": "The Edge Engine makes boring easier by only surfacing setups that qualify. Link below.",
        "tags": "trading mindset, boring trading strategy, long term trading, discipline, compound returns",
        "thumbnail": "THE BORING STRATEGY THAT WINS | One trade per week | Real compounding",
    },
]

EDGE_TOOLS = [
    {
        "title": "How I Built a Momentum Scorer That Filters 90 Percent of Noise",
        "hook": "I used to spend two hours every morning scanning charts. Now I spend ten minutes reviewing what the scorer already filtered. Here is exactly how I built it.",
        "sections": [
            ("The Problem With Manual Scanning", "30 tickers. 5 indicators each. Two hours minimum. And you still miss things because human attention is inconsistent."),
            ("The Scoring Formula", "RSI reading plus volume anomaly multiplier plus EMA cross confirmation equals raw score. Normalized to 0 to 100. Only look at 70 and above."),
            ("Building It in Pine Script", "Walk through the actual indicator code. Show each component. Show how the score gets calculated and displayed on the chart."),
            ("Adding Congressional Data", "How to pull STOCK Act data and cross-reference against the momentum score. When both align, the conviction goes up."),
            ("What It Changed", "Scanning time cut from 2 hours to 10 minutes. Setup quality went up because only the highest conviction ideas make it through."),
        ],
        "cta": "The full indicator suite is on Gumroad. Link in description.",
        "tags": "Pine Script tutorial, TradingView indicator, momentum scanner, trading tools, build your own scanner",
        "thumbnail": "I BUILT A MOMENTUM SCORER | Filters 90% of noise | Pine Script walkthrough",
    },
]

# ── SHADOWCLANS CHANNEL ────────────────────────────────────────────────────────

SHADOW_STORYTELLING = [
    {
        "title": "Building a Business From Zero With Nothing But a Laptop and Stubbornness",
        "hook": "Five months ago I decided to stop trading time for a paycheck and start building something that runs without me. Here is what actually happened.",
        "sections": [
            ("Month 1", "Learning tools. No clients. No income. Just building demos nobody had asked for yet."),
            ("Month 2", "First real project. First real feedback. First real understanding of what businesses actually need versus what I thought they needed."),
            ("Month 3", "Systems start working. Outreach starts going out. Zero responses. Start to question everything."),
            ("Month 4", "First signal. First reply. First real conversation with a potential client. Understand what the profile problem was."),
            ("Month 5", "Fix the profile. Fix the outreach. Fix the positioning. Everything starts to move differently."),
            ("What This Actually Takes", "Not intelligence. Not capital. Willingness to stay in it past the point where most people quit."),
        ],
        "cta": "Subscribe to follow the build. New episode every week.",
        "tags": "entrepreneur journey, building from zero, AI business, freelancer story, real talk",
        "thumbnail": "BUILDING FROM ZERO | Month by month | Real story no highlights",
    },
]

SHADOW_BEHIND_SCENES = [
    {
        "title": "What a Real AI Automation Business Looks Like Day to Day",
        "hook": "Everyone shows you the revenue screenshots. Nobody shows you what happens the 4 months before that. Here is what my actual day looks like right now.",
        "sections": [
            ("Morning", "Check overnight Upwork activity. Check Twitter engagement. Check lead scanner output. Check email for any replies."),
            ("Core Work Hours", "Applying to jobs. Building demos. Writing proposals. The unglamorous productive work."),
            ("Evenings", "Content creation. System improvements. Learning new tools. Recording videos."),
            ("The Reality", "Most days nothing dramatic happens. The business gets built in 2-hour blocks of focused work over months. That is the actual story."),
        ],
        "cta": "Follow the build. Subscribe.",
        "tags": "day in the life, AI business owner, freelancer reality, entrepreneur daily routine",
        "thumbnail": "REAL DAY IN THE LIFE | AI automation business | No highlights reel",
    },
]

# ── GENERATOR ─────────────────────────────────────────────────────────────────

ALL_CONTENT = {
    "GHE Automation": {
        "Tutorial": GHE_TUTORIALS,
        "Case Study": GHE_CASE_STUDIES,
        "Quick Tip": GHE_QUICK_TIPS,
        "Tool Review": GHE_TOOL_REVIEWS,
    },
    "Edge Engine": {
        "Education": EDGE_EDUCATION,
        "Signal Recap": EDGE_SIGNAL_RECAPS,
        "Mindset": EDGE_MINDSET,
        "Tool Build": EDGE_TOOLS,
    },
    "ShadowClans": {
        "Storytelling": SHADOW_STORYTELLING,
        "Behind the Scenes": SHADOW_BEHIND_SCENES,
    },
}


def generate_script(channel, content_type, video):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"CHANNEL: {channel}")
    lines.append(f"TYPE: {content_type}")
    lines.append(f"DATE: {date_str}")
    lines.append("=" * 60)
    lines.append(f"TITLE: {video['title']}")
    lines.append(f"\nTHUMBNAIL CONCEPT: {video['thumbnail']}")
    lines.append(f"\nTAGS: {video['tags']}")
    lines.append("\n" + "=" * 60)
    lines.append("SCRIPT")
    lines.append("=" * 60)
    lines.append(f"\n[HOOK — say this in the first 15 seconds]")
    lines.append(video["hook"])
    for section_title, section_body in video["sections"]:
        lines.append(f"\n[{section_title.upper()}]")
        lines.append(section_body)
    lines.append(f"\n[CALL TO ACTION]")
    lines.append(video["cta"])
    lines.append("\n" + "=" * 60)
    lines.append("RECORDING NOTES")
    lines.append("=" * 60)
    lines.append("- Record in one take if possible. Imperfect is fine. Authentic beats polished.")
    lines.append("- Show your screen whenever referencing a tool or dashboard.")
    lines.append("- Target length: 8-12 minutes for tutorials. 3-5 minutes for tips and recaps.")
    lines.append("- Upload to YouTube. Add the link from description to the matching landing page.")
    return "\n".join(lines)


def run():
    print("=" * 60)
    print("  YT CONTENT GENERATOR — Gray Horizons Enterprise")
    print("=" * 60)

    generated = []
    today = datetime.now().strftime("%Y-%m-%d")

    for channel, types in ALL_CONTENT.items():
        channel_dir = OUTPUT_DIR / channel.replace(" ", "_")
        channel_dir.mkdir(exist_ok=True)

        for content_type, videos in types.items():
            if not videos:
                continue
            video = random.choice(videos)
            script = generate_script(channel, content_type, video)

            safe_title = video["title"][:50].replace(" ", "_").replace("/", "-")
            filename = f"{today}_{content_type.replace(' ', '_')}_{safe_title}.txt"
            filepath = channel_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(script)

            print(f"\n[{channel}] {content_type}")
            print(f"  Title: {video['title']}")
            print(f"  Saved: {filepath.name}")
            generated.append({"channel": channel, "type": content_type, "title": video["title"], "file": str(filepath)})

    log = {"date": today, "generated": generated}
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  {len(generated)} scripts generated in yt_scripts/")
    print(f"  Open any .txt file and record directly from the script.")
    print("=" * 60)


if __name__ == "__main__":
    run()
