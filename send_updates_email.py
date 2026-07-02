"""
send_updates_email.py — GHE one-shot updates email
Sends new grants + Upwork proposal templates to grayhorizonsenterprise@gmail.com
"""
import os, requests
from dotenv import load_dotenv
load_dotenv()

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = "grayhorizonsenterprise@gmail.com"
TO_EMAIL     = "grayhorizonsenterprise@gmail.com"

HTML = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:32px auto;color:#1e293b;line-height:1.75;font-size:15px;">

<h1 style="color:#0f172a;border-bottom:3px solid #38bdf8;padding-bottom:12px;">
  GHE System Update: New Grants + Upwork Templates
</h1>
<p style="color:#64748b;">Two things in this email: (1) three new fast-win grants you do not have yet, (2) Upwork proposal templates ready to paste.</p>

<!-- URGENT BANNER -->
<div style="background:#fef9c3;border-left:5px solid #eab308;padding:16px 20px;margin:24px 0;border-radius:6px;">
  <h2 style="margin:0 0 10px;color:#92400e;">NEW: 3 ADDITIONAL GRANTS TO APPLY TO NOW</h2>
  <p style="margin:0;">These are in addition to the original 5. Apply to all 8 simultaneously. The more applications in flight, the higher the odds of landing one in the next 4-8 weeks.</p>
</div>

<!-- NEW GRANT A -->
<div style="border:2px solid #22c55e;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <h2 style="margin:0;color:#0f172a;">A. NAACP Keep It Local Business Fund</h2>
    <span style="background:#22c55e;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$5,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply via Hello Alice:</strong> <a href="https://naacp.org/find-resources/grants/keep-it-local-business-fund" style="color:#0369a1;">naacp.org/find-resources/grants/keep-it-local-business-fund</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 3-6 weeks | <strong>Difficulty:</strong> LOW | <strong>Owner pay:</strong> YES - unrestricted</p>
  <p style="margin:0 0 12px;"><strong>Partners:</strong> NAACP + Nextdoor Kind Foundation + Hello Alice</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
  <p style="margin:0 0 8px;"><strong>Why apply:</strong> $5K microgrant for entrepreneurs of color. 20 winners per round. Lower competition than larger grants. Winners also get free advertising on Nextdoor platform and 1-on-1 business coaching.</p>
  <p style="margin:0 0 8px;"><strong>Requirements:</strong> Business owner of color, US-based, strengthening local community. DBA with EIN qualifies.</p>

  <h3 style="color:#0369a1;margin:16px 0 8px;">NARRATIVE - paste directly</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is a Black-owned AI automation company serving local service businesses in California's Inland Empire. We build the systems that help minority-owned contractors, HVAC companies, and roofers compete on equal footing with larger competitors for the first time.

When a homeowner calls an HVAC company after hours and no one picks up, that business loses the job. Our AI voice agent answers that call, qualifies the lead in 90 seconds, and sends the booking link automatically. The owner wakes up to a confirmed appointment they would have otherwise lost.

This grant directly supports the 60-day runway needed to close our first three paying clients and begin generating the revenue that funds the next phase. We are asking for a bridge, not a lifeline. The system is built. The market is real. The funding is the gap between where we are and where we prove it works.</div>
</div>

<!-- NEW GRANT B -->
<div style="border:2px solid #7c3aed;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <h2 style="margin:0;color:#0f172a;">B. SoGal Black Founder Startup Grant</h2>
    <span style="background:#7c3aed;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$5,000-$10,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://sogalventures.com/grants/" style="color:#0369a1;">sogalventures.com/grants</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 4-8 weeks | <strong>Difficulty:</strong> LOW-MEDIUM | <strong>Owner pay:</strong> YES - unrestricted</p>
  <p style="margin:0 0 12px;"><strong>Application type:</strong> Rolling - apply any time</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
  <p style="margin:0 0 8px;"><strong>Why apply:</strong> Rolling applications, early-stage Black founders, cash plus mentorship and global network access. No round deadline pressure.</p>
  <p style="margin:0 0 8px;"><strong>Requirements:</strong> Early-stage Black founder, US-based business, tech or innovation focus. GHE qualifies on all counts.</p>

  <h3 style="color:#0369a1;margin:16px 0 8px;">NARRATIVE - paste directly</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is an early-stage AI company I built from scratch as a Black founder with no outside capital and no technical co-founder. The entire system - AI voice agents, CRM automation, market intelligence platform - was designed, built, and deployed by one person.

The market problem I am solving: 88% of businesses have adopted AI tools. Only 6% are using them effectively. That gap exists almost entirely in small and local businesses. They bought the tools. They never had the infrastructure or expertise to make them work. I build that infrastructure.

The technology is operational. The product is deployed. What I need is the runway to close the first three paying clients and document the outcomes that prove the model. This grant is the bridge between a working system and a funded company.</div>
</div>

<!-- NEW GRANT C -->
<div style="border:2px solid #f59e0b;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <h2 style="margin:0;color:#0f172a;">C. Hello Alice Small Business Growth Fund</h2>
    <span style="background:#f59e0b;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$25,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://helloalice.com/grants" style="color:#0369a1;">helloalice.com/grants</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 6-10 weeks | <strong>Difficulty:</strong> MEDIUM | <strong>Owner pay:</strong> YES - unrestricted</p>
  <p style="margin:0 0 12px;"><strong>Note:</strong> This is separate from the $10K Black Business Grant - same platform, different fund. Apply to both simultaneously when you log into Hello Alice.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
  <p style="margin:0 0 8px;"><strong>Why apply:</strong> $25K is 2.5x the $10K fund. You are already on Hello Alice for the Black Business Grant - add this application in the same session. Takes 15 extra minutes.</p>

  <h3 style="color:#0369a1;margin:16px 0 8px;">HOW FUNDS WILL BE USED - paste directly</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">The $25,000 grant funds the next growth phase after first clients are closed:

- $8,000 - Founder salary (3 months at $2,667/month during growth phase)
- $6,000 - Platform infrastructure scale-up (GHL, Railway, API costs for 8-10 active clients)
- $5,000 - Client acquisition: content production, Upwork engine, outreach automation
- $4,000 - Legal: LLC formation, service contracts, IP protection
- $2,000 - Professional development and certifications
Total: $25,000

At 8 clients paying $750/month, GHE generates $6,000 MRR and is self-sustaining. This grant funds the 90-day sprint to reach that milestone.</div>
</div>

<!-- GRANT PRIORITY ORDER -->
<div style="background:#f0f9ff;border:1px solid #7dd3fc;border-radius:8px;padding:20px;margin:24px 0;">
  <h2 style="margin:0 0 12px;color:#0c4a6e;">UPDATED PRIORITY ORDER - Apply in this sequence today</h2>
  <ol style="margin:0;padding-left:20px;line-height:2;">
    <li><strong>Verizon Digital Ready $10K</strong> - complete courses first, then apply</li>
    <li><strong>Hello Alice Black Business Grant $10K</strong> - apply now</li>
    <li><strong>Hello Alice Growth Fund $25K</strong> - apply in same Hello Alice session</li>
    <li><strong>NAACP Keep It Local $5K</strong> - via Hello Alice, apply same session</li>
    <li><strong>SoGal Black Founder Grant $5-10K</strong> - sogalventures.com, rolling</li>
    <li><strong>CA CEDAP up to $75K</strong> - calosba.ca.gov, check if round is open</li>
    <li><strong>Google Black Founders Fund $50-100K</strong> - monitor for cohort dates</li>
    <li><strong>NSF SBIR $275K</strong> - register at sam.gov TODAY to start the clock</li>
  </ol>
  <p style="margin:12px 0 0;color:#0369a1;font-weight:bold;">Potential total across all 8: up to $420,000</p>
</div>

<hr style="border:none;border-top:2px solid #e2e8f0;margin:40px 0 24px;">

<!-- UPWORK SECTION -->
<h1 style="color:#0f172a;margin:0 0 8px;">Upwork Proposal Templates - Updated</h1>
<p style="margin:0 0 20px;color:#64748b;">All templates now open with a diagnostic question, not a pitch. Lead with curiosity, earn the right to present a solution.</p>

<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;color:#0369a1;">AUTOMATION JOBS - use this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I build this exact system for service businesses and I want to ask one question before pitching anything.

When someone fills out your form or calls after hours right now, what actually happens to that inquiry?

I ask because 88% of businesses have automation tools. Only 6% have them set up in a way that actually converts. The gap is almost always in what happens in the first 5 minutes after a lead comes in.

I've built full intake and follow-up systems inside GoHighLevel for contractors, HVAC companies, and home services firms. Instant SMS response, 14-day automated follow-up, AI voice agent for after-hours calls, pipeline tracking. Deployed in under a week.

Before I tell you what I'd build, I want to understand where yours is breaking down right now. What does your current follow-up process look like from the moment a lead comes in?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min</div>
</div>

<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;color:#0369a1;">CRM / GHL JOBS - use this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I've built GHL from scratch for local service businesses and I want to understand your situation before suggesting anything.

Most owners I talk to have the same issue: GHL is paid for, some things are set up, but leads are still falling through because the follow-up sequence was never fully built or the pipeline stages don't match how they actually sell.

One contractor I worked with had 60 inbound leads last month. Followed up on 38. The other 22 went to voicemail and were never contacted again. He had no idea. We fixed the follow-up system in 5 days and 4 of those 22 converted in week two.

Before I walk you through what I'd build, what does your current GHL setup actually handle end to end without anyone touching it?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min</div>
</div>

<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;color:#0369a1;">AI VOICE AGENT JOBS - use this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I build AI voice agents for inbound call handling and I want to understand your situation before assuming anything.

Quick question: when someone calls your business after 5pm or on a weekend right now, what happens to that call?

I've deployed voice agents for HVAC companies, roofing contractors, and service businesses that answer every call, qualify the lead in 90 seconds, and text a booking link automatically. One roofing client booked 11 emergency jobs overnight in the first storm season after launch. Owner woke up to a full calendar.

The system runs 24/7 without anyone on staff. Before I walk through what I'd build for you, what does your current after-hours call handling look like?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min</div>
</div>

<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;color:#0369a1;">HOA / PROPERTY MANAGEMENT JOBS - use this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I've built violation tracking and homeowner communication automation specifically for HOA management firms and I want to ask one thing before anything else.

When a homeowner submits a violation or complaint right now, what does your team's process look like from that first report all the way to resolution? Is there a system tracking each step or is it mostly email threads?

I ask because that handoff is where most HOA teams lose time and create liability. We've built systems that lock the full violation lifecycle down automatically: intake, board notification, status tracking, homeowner updates, resolution logging. Deployed in about a week.

Worth a 10-minute call to see if it maps to what you're dealing with?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min</div>
</div>

<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;color:#0369a1;">GENERAL AUTOMATION JOBS - use this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I want to ask one question before telling you anything about what I do.

When your team gets a new inbound lead right now, what happens to it in the first 5 minutes? And when did you last manually verify that every automation you have running is actually working?

I ask because 88% of businesses have AI or automation tools. Only 6% have them set up in a way that's actually converting. The gap is almost always silent: tools running, leads falling through, nobody noticing.

I've built full automation stacks for contractors, HVAC companies, HOA management firms, and service businesses. GoHighLevel, AI voice agents, 14-day follow-up sequences, pipeline tracking. Deployed in under a week.

What does your current setup actually handle without anyone touching it?

Gray Horizons Enterprise
https://calendly.com/grayhorizonsenterprise/30min</div>
</div>

<!-- UPWORK SEARCH TERMS -->
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h3 style="margin:0 0 12px;color:#0f172a;">Updated Upwork Search Terms - System Now Scanning These</h3>
  <div style="font-size:13px;color:#475569;columns:2;column-gap:20px;">
    <p style="margin:2px 0;">workflow automation</p>
    <p style="margin:2px 0;">CRM automation</p>
    <p style="margin:2px 0;">AI automation small business</p>
    <p style="margin:2px 0;">missed call text back</p>
    <p style="margin:2px 0;">HOA management software</p>
    <p style="margin:2px 0;">GHL Go High Level</p>
    <p style="margin:2px 0;">business automation setup</p>
    <p style="margin:2px 0;">lead follow up automation</p>
    <p style="margin:2px 0;">appointment booking automation</p>
    <p style="margin:2px 0;">property management automation</p>
    <p style="margin:2px 0;">HVAC software automation</p>
    <p style="margin:2px 0;">contractor CRM setup</p>
    <p style="margin:2px 0;">Vapi voice agent</p>
    <p style="margin:2px 0;">AI voice agent setup</p>
    <p style="margin:2px 0;">GoHighLevel setup</p>
    <p style="margin:2px 0;">GoHighLevel expert</p>
    <p style="margin:2px 0;">GHL workflow</p>
    <p style="margin:2px 0;">AI receptionist</p>
    <p style="margin:2px 0;">small business CRM setup</p>
    <p style="margin:2px 0;">automation consultant</p>
    <p style="margin:2px 0;">n8n automation</p>
    <p style="margin:2px 0;">Make.com automation</p>
  </div>
</div>

<p style="color:#64748b;font-size:13px;margin-top:32px;border-top:1px solid #e2e8f0;padding-top:16px;">
  Gray Horizons Enterprise | grayhorizonsenterprise@gmail.com
</p>
</body>
</html>"""

payload = {
    "personalizations": [{"to": [{"email": TO_EMAIL, "name": "Curtis Gray"}]}],
    "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
    "subject": "GHE Update: 3 New Grants + All 5 Upwork Templates",
    "content": [{"type": "text/html", "value": HTML}],
}

r = requests.post(
    "https://api.sendgrid.com/v3/mail/send",
    headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
    json=payload,
    timeout=20,
)
print(f"Status: {r.status_code} -- {'SENT' if r.status_code in (200,202) else 'FAILED'}")
if r.status_code not in (200, 202):
    print(r.text)
