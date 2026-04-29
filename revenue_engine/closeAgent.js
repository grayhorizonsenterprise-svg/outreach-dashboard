/**
 * closeAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates closing messages and proposals per niche.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const CLOSE_TEMPLATES = {
  hoa: (company) => ({
    subject: `${company} — next step to get started`,
    body: `Hi,

Based on our conversation, here's what I'd propose:

**Gray Horizons HOA Compliance System**
- Violation intake + automated board notifications
- Full audit trail per property
- Status dashboard across all your communities
- Resident-facing portal

Setup: 3 business days
Investment: $397/month | First month free to test

To move forward, I just need your top 3 communities to start — we'll have you live this week.

Ready to begin?

Alex
Gray Horizons Enterprise`,
    urgencyTrigger: 'First month free expires end of month.',
    nextStep:       'Reply YES and I\'ll send the onboarding form today.',
  }),
  hvac: (company) => ({
    subject: `${company} — ready to start capturing more calls`,
    body: `Hi,

Here's the proposal we discussed:

**Gray Horizons HVAC AI Receptionist**
- 24/7 call answering + auto-dispatch
- Emergency escalation + tech notification
- Customer follow-up sequences
- Monthly call capture report

Setup: Same-day
Investment: $297/month | 30-day trial, cancel anytime

Based on your call volume, we're projecting 8-12 recovered calls in the first month.

Want to start the trial?

Alex
Gray Horizons Enterprise`,
    urgencyTrigger: 'Every week without this, you\'re losing emergency call revenue to competitors.',
    nextStep:       'Reply and I\'ll send the activation link today.',
  }),
  dental: (company) => ({
    subject: `${company} — proposal to reduce no-shows`,
    body: `Hi,

Here's what we'd build for your practice:

**Gray Horizons Dental Patient Retention System**
- Automated appointment reminders (SMS + email)
- Smart re-booking for cancellations
- 6-month reactivation campaigns
- No-show analytics dashboard

Setup: 2 business days
Investment: $347/month | 30-day free pilot

At your no-show rate, this pays for itself on the first 2 recovered appointments per month.

Ready to pilot?

Alex
Gray Horizons Enterprise`,
    urgencyTrigger: 'Every month without this, you\'re leaving $2,000-4,000 on the table.',
    nextStep:       'Reply YES and I\'ll send your practice onboarding link.',
  }),
  plumbing: (company) => ({
    subject: `${company} — let's close more estimates`,
    body: `Hi,

Here's the proposal:

**Gray Horizons Plumbing Follow-Up Engine**
- Automated estimate follow-up (5-touch sequence)
- Emergency call capture after hours
- Customer review request automation
- Closed/open pipeline dashboard

Setup: 1 business day
Investment: $247/month | First month free

Most plumbing companies see 2-4 extra closed jobs in the first month.

Want to activate?

Alex
Gray Horizons Enterprise`,
    urgencyTrigger: 'Estimates sitting in your inbox aren\'t closing themselves.',
    nextStep:       'Reply to confirm and I\'ll get you set up today.',
  }),
  contractor: (company) => ({
    subject: `${company} — project intake proposal`,
    body: `Hi,

Here's the system I'd build for your company:

**Gray Horizons Contractor Intake + CRM**
- Smart project intake form (captures scope, timeline, budget)
- Auto-qualification + follow-up sequences
- Subcontractor coordination board
- Estimate pipeline dashboard

Setup: 3 business days
Investment: $397/month | First month free

This is built to capture the projects that currently slip through.

Ready to get started?

Alex
Gray Horizons Enterprise`,
    urgencyTrigger: 'Busy season is coming — every missed lead is a missed contract.',
    nextStep:       'Reply YES and I\'ll send the intake setup form.',
  }),
};

async function generateClose({ company = 'Prospect', niche = 'hoa' } = {}) {
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
            content: `Write a closing proposal email for "${company}" in the ${niche} industry. Product: Gray Horizons Enterprise AI workflow automation. Include: subject, proposal body with pricing ($247-$497/month), urgency trigger, and next step. Sign off exactly as:\n\nAlex\nGray Horizons Enterprise\n\nNever use "--" before the signature. Return JSON: { "subject":"...", "body":"...", "urgencyTrigger":"...", "nextStep":"..." }`,
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
            return { ...parsed, source: 'claude', niche, company };
          }
        }
      }
    }

    const fn = CLOSE_TEMPLATES[niche] || CLOSE_TEMPLATES.hoa;
    return { ...fn(company), source: 'template', niche, company };
  } catch (err) {
    console.error('[closeAgent] Error:', err.message);
    return {
      subject:        `${company} — proposal`,
      body:           `Hi,\n\nHere's our proposal for ${company}. Investment: $347/month, first month free.\n\nReady to start?\n\nAlex\nGray Horizons Enterprise`,
      urgencyTrigger: 'Limited onboarding slots available this month.',
      nextStep:       'Reply YES to proceed.',
      source:         'fallback',
      niche,
      company,
    };
  }
}

module.exports = { generateClose };
