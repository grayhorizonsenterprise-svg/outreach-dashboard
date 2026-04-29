/**
 * outreachAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates personalized cold outreach messages per niche and stage.
 * Claude-enhanced if API key set; rich curated fallbacks always available.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

// ── Fallback message templates by niche ──────────────────────────────────────

const TEMPLATES = {
  hoa: {
    cold: (company, contact) => ({
      subject: `${company} — quick question about violation tracking`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Came across ${company} and had a genuine question.

When a homeowner submits a violation or compliance issue — where does it live? Still email threads and spreadsheets, or do you have something built out?

We work with HOA management firms across Southern California and that handoff — report to resolution — is where things fall through for most of them. We built something that keeps it all in one place, and I wanted to see if it's a problem you're running into.

No pitch. Happy to hear what you're working with.

Alex
Gray Horizons Enterprise`,
    }),
    warm: (company, contact) => ({
      subject: `Following up — ${company}`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Reaching back out because I want to make sure this landed.

You mentioned managing multiple HOAs — that's exactly where our system tends to make the biggest difference. One dashboard, full audit trail, board notifications automated.

Worth 10 minutes to show you? I can work around your schedule.

Alex
Gray Horizons Enterprise`,
    }),
  },
  hvac: {
    cold: (company, contact) => ({
      subject: `${company} — question about your dispatch process`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Found ${company} while researching HVAC firms in the area and had a quick question.

When an emergency call comes in after hours — how is that handled? Still a live answering service, or do you have something automated?

We've been helping HVAC companies capture more after-hours calls and auto-dispatch without adding headcount. Wanted to see if that's a gap you're dealing with.

Happy to show you a quick demo if it's relevant.

Alex
Gray Horizons Enterprise`,
    }),
    warm: (company, contact) => ({
      subject: `Re: ${company} — quick follow-up`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Just following up — I know timing is everything.

The firms we've worked with are typically capturing 20-30% more after-hours calls within the first month. Wanted to make sure you had the full picture before you decided.

15 minutes? I'll show you the exact setup.

Alex
Gray Horizons Enterprise`,
    }),
  },
  dental: {
    cold: (company, contact) => ({
      subject: `${company} — question about patient scheduling`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Reached out to ${company} because I had a specific question.

What does your no-show rate look like right now? And when a patient misses — is there an automated re-booking flow, or does your team handle that manually?

We help dental practices cut no-shows significantly with AI-driven scheduling and reminders. Not selling anything today — genuinely wanted to know if it's on your radar.

Alex
Gray Horizons Enterprise`,
    }),
    warm: (company, contact) => ({
      subject: `Following up — ${company} scheduling system`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Coming back around — wanted to make sure you saw my last note.

The system we built specifically addresses no-shows and manual reactivation. Most practices are recapturing 15-20 lost appointments per month within 60 days.

Worth a quick look? No commitment.

Alex
Gray Horizons Enterprise`,
    }),
  },
  plumbing: {
    cold: (company, contact) => ({
      subject: `${company} — question about your lead follow-up`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Found ${company} while looking into plumbing firms in the region.

Quick question — when someone requests an estimate and you don't hear back from them, what does your follow-up process look like? Automated, or mostly manual?

We help plumbing companies close more of those open estimates without adding to the workload. Curious if that's a gap you feel.

Alex
Gray Horizons Enterprise`,
    }),
    warm: (company, contact) => ({
      subject: `${company} — one more thing`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Tried reaching out once before — wanted to give this one more shot.

The firms we work with typically see their estimate close rate jump 20-35% once follow-ups are automated. It runs itself — no extra staff needed.

Can I show you the system in 15 minutes?

Alex
Gray Horizons Enterprise`,
    }),
  },
  contractor: {
    cold: (company, contact) => ({
      subject: `${company} — quick question about project intake`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Came across ${company} and wanted to reach out directly.

When a potential client reaches out about a project — what does intake look like? Is there a system that captures it and keeps everything organized, or is it still mostly calls and emails?

We work with general contractors to streamline that front end — intake, estimate, follow-up. Wanted to see if it's something you're actively trying to solve.

Alex
Gray Horizons Enterprise`,
    }),
    warm: (company, contact) => ({
      subject: `Following up — ${company}`,
      body: `Hi${contact ? ' ' + contact.split(' ')[0] : ''},

Wanted to follow up on my last message.

The intake and follow-up system we've built is running for a few contractors in Southern California. The biggest shift they've seen: no more losing leads because someone forgot to follow up.

15 minutes to show you how it works?

Alex
Gray Horizons Enterprise`,
    }),
  },
};

// ── Claude message generation ─────────────────────────────────────────────────

async function generateWithClaude({ company, contact, niche, stage, context }) {
  const key = API_KEY();
  if (!key) return null;

  try {
    const SIG_RULE = ' Always sign off exactly as:\n\nAlex\nGray Horizons Enterprise\n\nNever use "--" or any separator before the signature.';
    const systemPrompts = {
      hoa:        'You write cold outreach emails for a Black-owned AI automation firm targeting HOA property management companies. Pain: violation tracking, compliance documentation, board communication.' + SIG_RULE,
      hvac:       'You write cold outreach emails for a Black-owned AI automation firm targeting HVAC companies. Pain: after-hours dispatch, customer follow-up, emergency call capture.' + SIG_RULE,
      dental:     'You write cold outreach emails for a Black-owned AI automation firm targeting dental practices. Pain: no-shows, scheduling, patient reactivation.' + SIG_RULE,
      plumbing:   'You write cold outreach emails for a Black-owned AI automation firm targeting plumbing companies. Pain: estimate follow-up, dispatch, customer retention.' + SIG_RULE,
      contractor: 'You write cold outreach emails for a Black-owned AI automation firm targeting general contractors. Pain: project intake, lead follow-up, subcontractor coordination.' + SIG_RULE,
    };

    const stageGuide = stage === 'warm'
      ? 'This is a warm follow-up — they have seen a previous message. Reference the previous outreach briefly. More direct ask for a call.'
      : 'This is a cold first-touch email. Lead with curiosity. Ask ONE question. No hard pitch.';

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method:  'POST',
      headers: {
        'x-api-key':         key,
        'anthropic-version': '2023-06-01',
        'content-type':      'application/json',
      },
      body: JSON.stringify({
        model:      MODEL,
        max_tokens: 400,
        system:     systemPrompts[niche] || systemPrompts.hoa,
        messages: [{
          role:    'user',
          content: `Write a short outreach email for:\nCompany: ${company}\nContact: ${contact || 'unknown'}\nStage: ${stage}\n${context ? 'Context: ' + context : ''}\n\n${stageGuide}\n\nReturn JSON: {"subject": "...", "body": "..."}`,
        }],
      }),
      signal: AbortSignal.timeout(12000),
    });

    if (!res.ok) return null;
    const data = await res.json();
    const txt  = data.content?.[0]?.text?.trim() || '';
    const match = txt.match(/\{[\s\S]*\}/);
    if (!match) return null;
    const parsed = JSON.parse(match[0]);
    if (parsed.body) parsed.body = sanitizeSignature(parsed.body);
    return parsed;
  } catch {
    return null;
  }
}

// Strip any "--" separator lines that appear before the sign-off
function sanitizeSignature(body) {
  return body.replace(/\n--\s*\n/g, '\n\n').replace(/\n--\s*$/g, '');
}

// ── generateOutreach ──────────────────────────────────────────────────────────

async function generateOutreach({ company = 'Prospect', contact = '', niche = 'hoa', stage = 'cold', context = '' } = {}) {
  try {
    // Try Claude first
    const claude = await generateWithClaude({ company, contact, niche, stage, context });
    if (claude?.subject && claude?.body) {
      return { ...claude, source: 'claude', stage, niche };
    }

    // Fallback to templates
    const nicheTemplates = TEMPLATES[niche] || TEMPLATES.hoa;
    const stageFn        = nicheTemplates[stage] || nicheTemplates.cold;
    const result         = stageFn(company, contact);
    return { ...result, source: 'template', stage, niche };
  } catch (err) {
    console.error('[outreachAgent] Error:', err.message);
    return {
      subject: `${company} — quick question`,
      body:    `Hi,\n\nReached out because I had a quick question about how your team handles [process].\n\nWould love to connect.\n\nAlex\nGray Horizons Enterprise`,
      source:  'fallback',
      stage,
      niche,
    };
  }
}

module.exports = { generateOutreach };
