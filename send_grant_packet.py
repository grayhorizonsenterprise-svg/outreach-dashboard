"""
send_grant_packet.py — Gray Horizons Enterprise
Sends the full grant application packet to grayhorizonsenterprise@gmail.com
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
<body style="font-family:Arial,sans-serif;max-width:680px;margin:32px auto;color:#1e293b;line-height:1.75;font-size:15px;">

<h1 style="color:#0f172a;border-bottom:3px solid #38bdf8;padding-bottom:12px;">
  GHE Grant Application Packet
</h1>
<p style="color:#64748b;">Apply to ALL FIVE simultaneously. Do not wait on one before starting the next.</p>

<!-- MASTER ACTION — TODAY -->
<div style="background:#fef9c3;border-left:5px solid #eab308;padding:16px 20px;margin:24px 0;border-radius:6px;">
  <h2 style="margin:0 0 10px;color:#92400e;">DO THESE THREE THINGS TODAY</h2>
  <ol style="margin:0;padding-left:20px;">
    <li style="margin-bottom:8px;"><strong>Verizon Digital Ready</strong> — complete 2-3 free courses first, then apply for $10K grant<br>
      <a href="https://digitalreadysmallbusiness.verizon.com" style="color:#0369a1;">digitalreadysmallbusiness.verizon.com</a></li>
    <li style="margin-bottom:8px;"><strong>Hello Alice</strong> — create account, paste the narrative below, submit<br>
      <a href="https://helloalice.com/grants" style="color:#0369a1;">helloalice.com/grants</a></li>
    <li style="margin-bottom:8px;"><strong>SAM.gov</strong> — register GHE now (takes 2-4 weeks to process, required for NSF $275K)<br>
      <a href="https://sam.gov" style="color:#0369a1;">sam.gov</a></li>
  </ol>
</div>

<!-- GRANT 1 -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <h2 style="margin:0;color:#0f172a;">1. Hello Alice — Black Business Owners Grant</h2>
    <span style="background:#22c55e;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$10,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://helloalice.com/grants" style="color:#0369a1;">helloalice.com/grants</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 4-8 weeks &nbsp;|&nbsp; <strong>Difficulty:</strong> LOW &nbsp;|&nbsp; <strong>Owner pay:</strong> YES — unrestricted</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

  <h3 style="color:#0369a1;margin:0 0 8px;">BUSINESS DESCRIPTION — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is a California-based AI automation company founded to solve one of the most expensive and invisible problems facing local service businesses: the gap between a lead coming in and a business actually responding.

The average contractor, HVAC company, or roofing firm loses 30 to 40 percent of their inbound leads to slow follow-up, missed calls, and manual processes that break down after hours. Most of these businesses know something is wrong. Almost none have the technical resources to fix it.

Gray Horizons Enterprise builds and manages the full AI infrastructure that closes that gap: automated CRM workflows inside GoHighLevel, AI voice agents that answer and book inbound calls 24 hours a day, and intake systems that follow up with every lead for 14 days without any human intervention.

We also operate the Edge Engine, a proprietary AI-powered market intelligence platform that generates trading signals and portfolio indicators for individual investors, scoring market setups on a 0-100 scale using RSI divergence, volume anomaly detection, and congressional disclosure tracking.

Both product lines are built on the same principle: intelligent automation creates leverage. One person, properly equipped, can outperform a much larger team. Gray Horizons Enterprise exists to build that leverage for underserved business owners who have been priced out of enterprise-grade AI tools.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">HOW FUNDS WILL BE USED — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">The $10,000 grant will be allocated as follows:

- $3,500 — Platform infrastructure (GoHighLevel, Railway hosting, AI API costs)
- $2,500 — Sales and marketing to close first three paying retainer clients at $750/month
- $2,000 — Founder living wage during the 60-day pre-revenue runway
- $1,500 — Legal and business formation (contracts, LLC, EIN)
- $500 — Professional development

This funding covers the 60-day runway needed to close the first client contract, at which point the business becomes self-sustaining on recurring revenue.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">IMPACT — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise serves a market that is chronically underserved by technology companies — local service business owners, the majority of whom are in working-class communities, running businesses started from scratch without investment capital or access to enterprise tools.

When a Black-owned plumbing company can afford an AI voice agent that captures every after-hours call, they stop losing jobs to competitors who had the money to hire a full-time receptionist. When a minority-owned roofing contractor gets a CRM that follows up on leads automatically, they compete on equal footing for the first time.

Every client Gray Horizons Enterprise serves creates a visible ripple: more jobs booked, more revenue generated, more stability for the owner and their family. The grant funds one founder building systems that will serve dozens of those businesses in the next 12 months.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">FOUNDER STORY — paste if asked</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">I started Gray Horizons Enterprise because I watched the technology divide play out in real time. Businesses that could afford enterprise tools scaled. The ones that could not, did not. The tools existed. The access did not.

I spent years learning GoHighLevel, AI voice agents, market intelligence systems, and automation engineering — not to work for a tech company but to bring those same capabilities to business owners who could not walk into a bank and get a loan to hire an AI team.

This is a business built on the belief that intelligence and access to the right tools should not be reserved for people who already have capital. The grant funding is not a shortcut. It is the bridge between a working system and the clients who need it.</div>
</div>

<!-- GRANT 2 -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <h2 style="margin:0;color:#0f172a;">2. Verizon Small Business Digital Ready Grant</h2>
    <span style="background:#22c55e;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$10,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://digitalreadysmallbusiness.verizon.com" style="color:#0369a1;">digitalreadysmallbusiness.verizon.com</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 4-8 weeks &nbsp;|&nbsp; <strong>Difficulty:</strong> LOW &nbsp;|&nbsp; <strong>Owner pay:</strong> YES — unrestricted</p>
  <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:12px 16px;margin:12px 0;border-radius:4px;">
    <strong>IMPORTANT:</strong> Must complete free courses FIRST before the grant application unlocks. Go to the site now and start the Digital Marketing or AI for Small Business course. Takes 2-4 hours.
  </div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

  <h3 style="color:#0369a1;margin:0 0 8px;">BUSINESS DESCRIPTION — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is a California-based AI automation company serving local service businesses and individual investors. We build and manage AI voice agents, CRM automation workflows, and market intelligence systems for contractors, HVAC companies, roofers, and plumbers who need enterprise-grade technology at small business prices.

Our flagship service is a fully managed automation stack built inside GoHighLevel CRM: instant SMS response to every inbound lead, AI voice agents that answer and book calls 24/7, and 14-day follow-up sequences that run without any human involvement.

The business is founder-operated, Black-owned, and based in California. We serve businesses that have been priced out of AI adoption — and prove that with the right system, a one-person operation can outperform a team.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">HOW DIGITAL TOOLS HAVE IMPACTED YOUR BUSINESS — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Digital tools are not a supplement to Gray Horizons Enterprise. They are the entire product. Every system we deliver to a client runs on cloud infrastructure: GoHighLevel for CRM, Railway for hosting, Vapi for voice AI, Anthropic for language model inference, and Twilio for SMS. These tools replaced what would have required a 5-person team to operate manually.

The challenge is affordability of the infrastructure while building toward the first paying client. Monthly platform costs exceed $500 before counting development time. The Verizon Digital Ready grant directly covers 12 months of core infrastructure, freeing the founder to focus entirely on client acquisition.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">HOW THE $10,000 WILL BE USED — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">- $3,564 — GoHighLevel CRM platform (12 months at $297/month)
- $2,400 — AI API costs (Anthropic, Vapi voice agent, Twilio SMS)
- $1,200 — Railway hosting and deployment infrastructure
- $1,500 — Content and marketing for client acquisition
- $836 — Legal (contracts, service agreements)
- $500 — Contingency</div>
</div>

<!-- GRANT 3 -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <h2 style="margin:0;color:#0f172a;">3. California CEDAP — Capital and Tech Access Grant</h2>
    <span style="background:#f59e0b;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">Up to $75,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://calosba.ca.gov" style="color:#0369a1;">calosba.ca.gov</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 6-12 weeks &nbsp;|&nbsp; <strong>Difficulty:</strong> MEDIUM &nbsp;|&nbsp; <strong>Owner pay:</strong> YES — as "project labor"</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

  <h3 style="color:#0369a1;margin:0 0 8px;">PROJECT DESCRIPTION — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is requesting CEDAP funding to accelerate the deployment of AI automation systems for underserved local service businesses in California's Inland Empire region and surrounding communities.

The project has two components. The first is client acquisition and service delivery infrastructure. Gray Horizons Enterprise has built a complete AI automation stack including GoHighLevel CRM workflows, AI voice agents for inbound call handling, and automated lead nurture sequences. The CEDAP grant funds the critical 90-day window required to close the first three paying retainer clients, document the outcomes, and establish the case studies needed to scale.

The second component is community impact: the businesses we serve are disproportionately minority-owned, working-class operations in trades industries — HVAC, roofing, plumbing, contracting, landscaping. These are the businesses that keep Inland Empire communities running and the ones being left behind by a technology shift that assumes enterprise-level resources.

Gray Horizons Enterprise brings the same AI capabilities that enterprise companies deploy at $150,000 per year in salary costs and delivers them for $750 per month. The CEDAP grant accelerates the point at which we prove this model works — and replicate it across the Inland Empire's small business ecosystem.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">BUDGET NARRATIVE — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Founder/operator labor:    $30,000 (90 days full-time at $333/day — building and managing AI systems)
Platform subscriptions:    $8,000  (GoHighLevel, Railway, Anthropic, Vapi, SendGrid)
Sales and marketing:       $12,000 (lead generation, demo production, outreach campaigns)
Legal and compliance:      $5,000  (contracts, LLC, business licensing)
Equipment and software:    $5,000  (demo recording setup, design tools)
Contingency:               $5,000
TOTAL REQUESTED:           $65,000</div>
</div>

<!-- GRANT 4 -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <h2 style="margin:0;color:#0f172a;">4. Google for Startups — Black Founders Fund</h2>
    <span style="background:#f59e0b;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">$50K-$100K</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://startup.google.com/programs/black-founders-fund/" style="color:#0369a1;">startup.google.com/programs/black-founders-fund</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 8-16 weeks &nbsp;|&nbsp; <strong>Difficulty:</strong> MEDIUM-HIGH &nbsp;|&nbsp; <strong>Owner pay:</strong> YES — unrestricted cash</p>
  <div style="background:#f0f9ff;border-left:4px solid #0369a1;padding:12px 16px;margin:12px 0;border-radius:4px;">
    Monitor the site for cohort open dates — applications open 1-2 times per year. Set a browser bookmark and check weekly.
  </div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

  <h3 style="color:#0369a1;margin:0 0 8px;">WHAT DOES YOUR COMPANY DO — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise builds AI automation infrastructure for two underserved markets simultaneously.

The first is local service businesses — contractors, HVAC companies, roofers, plumbers, and landscapers — who are hemorrhaging revenue to slow response times, missed calls, and broken follow-up processes. We build the complete automation stack: GoHighLevel CRM workflows, AI voice agents that answer and book inbound calls 24/7, and 14-day lead nurture sequences that run without any human intervention. These are enterprise-grade systems delivered to businesses that could never afford an enterprise contract.

The second is individual investors who want access to the same signal intelligence that institutions use. The Edge Engine is our proprietary market intelligence platform that scores stock and crypto setups 0-100 using RSI divergence, volume anomaly detection, EMA crossover confirmation, and congressional disclosure tracking. Subscribers get pre-scored setups with Kelly Criterion position sizing built in.

The market opportunity is real: 88% of businesses have adopted AI tools. Only 6% are using them effectively. That gap is where Gray Horizons Enterprise operates.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">WHY DO YOU NEED FUNDING — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise does not have a product problem. The systems are built, tested, and ready to deploy. The constraint is runway.

Every dollar currently spent on platform subscriptions, hosting, and API costs comes directly from the founder. There is no investor. There is no safety net. The business is one bad month away from having to shut down the infrastructure while actively trying to close the first paying client.

The funding solves this three ways: it eliminates financial pressure that compresses the sales cycle; it funds the production of assets that close deals (demo videos, case studies, content); and it allows the founder to pay himself a living wage during the 90 days required to reach the first milestone of 8 retainer clients at $750/month — $6,000 MRR and self-sustaining.

This is a bridge, not a crutch. The business model works. The technology works. The market is real. The funding is the 90-day window between where we are and where this becomes a company that funds itself.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">UNFAIR ADVANTAGE — paste this</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">The unfair advantage is integration. Most AI automation companies pick a lane: CRM, voice AI, trading tools, or content generation. Gray Horizons Enterprise built across all four because one founder, unencumbered by committee decisions or departmental budgets, could iterate at the speed of the technology itself.

The second unfair advantage is positioning. Most AI companies sell to venture-backed startups or enterprise buyers. Gray Horizons Enterprise targets the 30 million US small businesses that have been told AI is not for them. The beachhead is local service businesses — a market with massive, recurring, cash-generating contracts that no major AI company is focused on closing.

We are building where the competition is not.</div>
</div>

<!-- GRANT 5 -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <h2 style="margin:0;color:#0f172a;">5. NSF SBIR Phase I — America's Seed Fund</h2>
    <span style="background:#7c3aed;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;">Up to $275,000</span>
  </div>
  <p style="margin:8px 0 4px;"><strong>Apply:</strong> <a href="https://seedfund.nsf.gov" style="color:#0369a1;">seedfund.nsf.gov</a></p>
  <p style="margin:0 0 4px;"><strong>Timeline:</strong> 6 months &nbsp;|&nbsp; <strong>Difficulty:</strong> HIGH &nbsp;|&nbsp; <strong>Owner pay:</strong> YES — PI salary is a required budget line (~$85K/year)</p>
  <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:12px 16px;margin:12px 0;border-radius:4px;">
    <strong>START TODAY:</strong> Register at <a href="https://sam.gov" style="color:#ef4444;">sam.gov</a> — takes 2-4 weeks to process. Cannot submit federal grants without it. This is the most important clock to start.
  </div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

  <h3 style="color:#0369a1;margin:0 0 8px;">PROJECT PITCH (submit first — NSF reviews before inviting full proposal)</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Gray Horizons Enterprise is developing an AI-powered operational intelligence platform that closes the gap between AI adoption and AI effectiveness for small and medium-sized service businesses.

The core problem: 88% of US businesses have adopted AI tools. Only 6% are using them effectively. The gap is not capability — it is implementation. Small businesses lack the technical infrastructure to translate AI potential into operational outcomes.

The innovation: a proprietary scoring and automation architecture combining conversational AI voice agents, CRM workflow automation, and real-time signal intelligence into a single managed system deployable for any service-sector business in under 7 days. The system includes a novel application of Kelly Criterion position-sizing logic to business lead scoring — ranking inbound leads by conversion probability and automating response priority accordingly.

The market: 33 million US small businesses. Agentic AI market projected at $202 billion by 2026. No current platform delivers a full-stack managed AI OS to businesses under $5M annual revenue at accessible price points.

The ask: NSF SBIR Phase I funding of $275,000 to validate core technical claims, formalize the lead-scoring algorithm, and deploy to a cohort of 25 service businesses with documented outcomes.</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">EMAIL TO NSF PROGRAM OFFICER — send before submitting</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">Subject: Project Pitch Inquiry — AI Operational Intelligence for Service-Sector SMBs

I am preparing a Phase I SBIR submission for a project developing an AI-powered operational intelligence platform for small and medium-sized service businesses.

The core innovation is a unified system combining probabilistic lead scoring (adapted from Kelly Criterion logic), autonomous AI voice intake, and real-time signal intelligence. The research question: does this system produce statistically measurable improvements in lead conversion rate, response time, and revenue per inbound contact versus manual operations?

Gray Horizons Enterprise is a Black-owned California company with hands-on technical deployment of each component of the proposed system.

I would welcome 20 minutes to discuss fit with current NSF SBIR topic areas before submitting a formal Project Pitch.

Curtis Gray
Gray Horizons Enterprise
grayhorizonsenterprise@gmail.com
grayhorizonsenterprise.com</div>

  <h3 style="color:#0369a1;margin:16px 0 8px;">BUDGET SUMMARY (Phase I — $275,000)</h3>
  <div style="background:#f8fafc;padding:16px;border-radius:6px;font-size:14px;white-space:pre-wrap;">PI Salary — Curtis Gray (12 months, 100% effort):  $85,000
Fringe benefits (15%):                             $12,750
Subcontractors — ML engineer, data analyst:        $40,000
Platform infrastructure (GHL, Railway, APIs):      $24,000
Pilot business stipends (25 x $1,000):             $25,000
Data collection and analysis:                      $15,000
Travel (NSF meetings):                              $8,000
Indirect costs (20%):                              $42,500
Contingency:                                       $22,750
TOTAL:                                            $275,000</div>
</div>

<!-- KEY STATS -->
<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:20px;margin:24px 0;">
  <h2 style="margin:0 0 12px;color:#166534;">Key Stats — Use in Every Application</h2>
  <ul style="margin:0;padding-left:20px;">
    <li>88% of businesses use AI — only 6% do it effectively (IBM research)</li>
    <li>76% of CEOs now have a Chief AI Officer equivalent — up from 26% two years ago</li>
    <li>Average contractor loses $45,000-$120,000/year to missed and unreturned calls</li>
    <li>Agentic AI market: $202 billion projected by 2026</li>
    <li>AI consulting market: $64 billion by 2028</li>
    <li>GHE retainer: $750/month — 10 clients = $7,500 MRR and self-sustaining</li>
    <li>Platform is live, tested, deployable in under 7 days per client</li>
  </ul>
</div>

<!-- DOCUMENTS NEEDED -->
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:24px 0;">
  <h2 style="margin:0 0 12px;color:#0f172a;">Documents to Prepare (needed for most applications)</h2>
  <ul style="margin:0;padding-left:20px;">
    <li>Government-issued ID (proof of Black ownership)</li>
    <li>EIN — get free at irs.gov if not already done</li>
    <li>California business license or registration</li>
    <li>Business bank account statements (2-3 months)</li>
    <li>Proof of California address</li>
    <li>Website: grayhorizonsenterprise.com</li>
    <li>Email: grayhorizonsenterprise@gmail.com</li>
  </ul>
</div>

<p style="color:#64748b;font-size:13px;margin-top:32px;border-top:1px solid #e2e8f0;padding-top:16px;">
  Gray Horizons Enterprise &mdash; grayhorizonsenterprise.com
</p>
</body>
</html>"""

payload = {
    "personalizations": [{"to": [{"email": TO_EMAIL, "name": "Curtis Gray"}]}],
    "from": {"email": FROM_EMAIL, "name": "Gray Horizons Enterprise"},
    "subject": "GHE Grant Packet — All 5 Applications Ready to Submit",
    "content": [{"type": "text/html", "value": HTML}],
}

r = requests.post(
    "https://api.sendgrid.com/v3/mail/send",
    headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
    json=payload,
    timeout=20,
)
print(f"Status: {r.status_code} — {'SENT' if r.status_code in (200,202) else 'FAILED'}")
if r.status_code not in (200, 202):
    print(r.text)
