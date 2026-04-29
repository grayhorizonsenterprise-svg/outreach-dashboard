/**
 * deliveryAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates onboarding confirmations and delivery milestone messages.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const DELIVERY_TEMPLATES = {
  hoa: (company) => ({
    welcome: {
      subject: `Welcome to Gray Horizons, ${company} — you're live`,
      body: `Hi,

Your HOA Compliance System is active.

Here's what's ready right now:
✓ Violation intake form — live and accepting submissions
✓ Board notification emails — configured
✓ Status dashboard — accessible at your admin link
✓ Audit trail — logging every action from this moment forward

Your onboarding call is scheduled. Before then, add your top 3 communities to the dashboard so we can review them together.

Questions before the call? Reply here — I check this daily.

Alex
Gray Horizons Enterprise`,
    },
    milestone30: {
      subject: `${company} — 30-day check-in`,
      body: `Hi,

30 days in. Here's where things stand:

Violations logged this month: [auto-filled]
Average resolution time: [auto-filled]
Board notifications sent: [auto-filled]

Most teams see a 40% drop in resolution time by month two. To get there, make sure your staff is routing all reports through the intake form — not email.

Anything we should adjust? Reply and I'll make it happen today.

Alex`,
    },
  }),
  hvac: (company) => ({
    welcome: {
      subject: `${company} — your AI receptionist is live`,
      body: `Hi,

Your HVAC AI Receptionist is active and answering calls.

What's running now:
✓ 24/7 call handling — live
✓ Emergency escalation — configured to your on-call tech
✓ Scheduling integration — connected
✓ After-hours capture — active

Test it right now: call your business number after hours and listen to how it responds. If anything sounds off, reply and I'll adjust the script today.

Alex
Gray Horizons Enterprise`,
    },
    milestone30: {
      subject: `${company} — first month results`,
      body: `Hi,

Month one is done. Here's the summary:

Calls captured after hours: [auto-filled]
Emergency dispatches handled: [auto-filled]
Estimated revenue recovered: [auto-filled]

The biggest gains in month two come from enabling the follow-up sequence for non-emergency calls. Want me to turn that on?

Alex`,
    },
  }),
  dental: (company) => ({
    welcome: {
      subject: `${company} — patient system is live`,
      body: `Hi,

Your patient retention system is active.

Running now:
✓ Appointment reminders — SMS + email, 48h and 2h before
✓ Cancellation re-booking — automated prompt sent within 1 hour
✓ Reactivation campaign — queued for patients 6+ months overdue
✓ No-show tracking — dashboard live

Your front desk doesn't need to change anything. The system runs alongside whatever you're already doing.

First report lands in 2 weeks. Watch your no-show rate.

Alex
Gray Horizons Enterprise`,
    },
    milestone30: {
      subject: `${company} — 30-day patient retention report`,
      body: `Hi,

Here's month one:

Reminders sent: [auto-filled]
No-shows prevented: [auto-filled]
Re-bookings recovered: [auto-filled]

At this rate, you're recovering approximately [auto-filled] in monthly revenue that was previously walking out the door.

Ready to activate the 6-month reactivation list?

Alex`,
    },
  }),
  plumbing: (company) => ({
    welcome: {
      subject: `${company} — your follow-up engine is live`,
      body: `Hi,

Your Plumbing Follow-Up Engine is active.

What's running:
✓ Estimate follow-up sequence — 5-touch, automated
✓ After-hours call capture — live
✓ Review request automation — sends 24h after job close
✓ Pipeline dashboard — tracking all open estimates

First estimates should start flowing through the system today. You'll see them in your dashboard.

Any estimates already outstanding? Forward them to me and I'll manually trigger the sequence.

Alex
Gray Horizons Enterprise`,
    },
    milestone30: {
      subject: `${company} — 30-day close rate update`,
      body: `Hi,

Month one numbers:

Estimates followed up automatically: [auto-filled]
Estimates closed from follow-up: [auto-filled]
Reviews collected: [auto-filled]

Most companies see close rate improvement in month two when we tune the messaging. Want to run an A/B test on the follow-up copy?

Alex`,
    },
  }),
  contractor: (company) => ({
    welcome: {
      subject: `${company} — project intake system is live`,
      body: `Hi,

Your Contractor Intake + CRM is active.

Live now:
✓ Project intake form — accepting submissions
✓ Auto-qualification flow — scoring leads on submission
✓ Follow-up sequences — triggered automatically
✓ Pipeline board — every lead tracked from inquiry to close

Share your intake link with your team and add it to your website — that's the only step required from you.

First leads should appear in the dashboard within 24 hours of your first submission.

Alex
Gray Horizons Enterprise`,
    },
    milestone30: {
      subject: `${company} — first month project pipeline report`,
      body: `Hi,

Month one wrap-up:

Leads captured through intake: [auto-filled]
Leads auto-qualified: [auto-filled]
Proposals sent: [auto-filled]
Projects closed: [auto-filled]

The next lever: activating the subcontractor coordination board. Want me to set that up this week?

Alex`,
    },
  }),
};

async function generateDelivery({ company = 'Client', niche = 'hoa', type = 'welcome' } = {}) {
  try {
    const key = API_KEY();
    if (key) {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method:  'POST',
        headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({
          model:      MODEL,
          max_tokens: 500,
          messages: [{
            role:    'user',
            content: `Write a ${type === 'welcome' ? 'client onboarding welcome email' : '30-day milestone check-in email'} for "${company}", a ${niche} business that just signed with Gray Horizons Enterprise for AI workflow automation. Be specific, confident, and action-oriented. Sign off exactly as:\n\nAlex\nGray Horizons Enterprise\n\nNever use "--" before the signature. Return JSON: { "subject": "...", "body": "..." }`,
          }],
        }),
        signal: AbortSignal.timeout(12000),
      });
      if (res.ok) {
        const data  = await res.json();
        const txt   = data.content?.[0]?.text?.trim() || '';
        const match = txt.match(/\{[\s\S]*\}/);
        if (match) {
          const parsed = JSON.parse(match[0]);
          if (parsed.subject && parsed.body) {
            parsed.body = parsed.body.replace(/\n--\s*\n/g, '\n\n').replace(/\n--\s*$/g, '');
            return { ...parsed, source: 'claude', niche, company, type };
          }
        }
      }
    }

    const tmpl = (DELIVERY_TEMPLATES[niche] || DELIVERY_TEMPLATES.hoa)(company);
    const msg  = type === 'milestone30' ? tmpl.milestone30 : tmpl.welcome;
    return { ...msg, source: 'template', niche, company, type };
  } catch (err) {
    console.error('[deliveryAgent] Error:', err.message);
    return {
      subject: `${company} — you're all set`,
      body:    `Hi,\n\nYour system is live. Dashboard access has been sent separately.\n\nAlex\nGray Horizons Enterprise`,
      source:  'fallback', niche, company, type,
    };
  }
}

module.exports = { generateDelivery };
