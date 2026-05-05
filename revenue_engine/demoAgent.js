/**
 * demoAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates structured demo scripts per niche for sales calls.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const DEMO_SCRIPTS = {
  hoa: (company) => ({
    duration: '15 minutes',
    sections: [
      {
        title:    'Opening (2 min)',
        script:   `"Thanks for making time, ${company}. Before I show you anything — what's the biggest headache right now when it comes to violation tracking or compliance? I want to make sure I show you the right thing."`,
        goal:     'Confirm the pain. Let them talk first.',
      },
      {
        title:    'Problem Confirmation (3 min)',
        script:   '"Most managers I talk to are either doing this in email, a spreadsheet, or some combination of both — and the issue isn\'t tracking one violation, it\'s tracking 50 across 6 communities and knowing where each one stands. Does that sound familiar?"',
        goal:     'Build resonance. If they say yes, you move. If no — adjust.',
      },
      {
        title:    'Solution Walkthrough (7 min)',
        script:   '"Let me show you what we built. Here\'s the violation intake — homeowner submits it here, the system automatically logs it, assigns it, and the board gets notified instantly. No email thread. Here\'s the status dashboard — right now I can see every open violation, who owns it, what stage it\'s in, and when it\'s due. One click to send a follow-up. Everything has an audit trail automatically."',
        goal:     'Show. Don\'t just tell. Walk through real screens.',
      },
      {
        title:    'Close Attempt (3 min)',
        script:   '"Based on what you\'ve seen — does this solve the problem you described at the start? If it does, I\'d like to talk about getting you set up. What does your timeline look like?"',
        goal:     'Direct close. Silence after the question.',
      },
    ],
    objections: {
      'We already have software': '"What does it handle well — and what do you still manage outside of it? In my experience there\'s always a gap."',
      'Not the right time':       '"Understood. What would need to change for this to be the right time? Is it budget, bandwidth, or something else?"',
      'Need to check with board': '"Absolutely. What information does the board need to move forward? I can put together a one-pager for them."',
      'Too expensive':            '"What\'s the cost right now of NOT having this — staff hours, missed deadlines, homeowner complaints? Let\'s put a number on it."',
    },
  }),
  hvac: (company) => ({
    duration: '15 minutes',
    sections: [
      { title: 'Opening (2 min)',           script: `"Thanks for the time, ${company}. Quick question before we start — on average, how many calls are you missing or losing after hours each week? Even a rough number."`, goal: 'Anchor the cost of the problem immediately.' },
      { title: 'Problem Confirmation (3 min)', script: '"Most HVAC companies I\'ve spoken with say they lose 30-40% of emergency calls after 6 PM — not because they\'re not good at the work, but because the phone rings and no one picks up. That revenue just goes to a competitor."', goal: 'Make the pain financial.' },
      { title: 'Solution Walkthrough (7 min)', script: '"Here\'s what we built. AI receptionist answers every call — 24/7. It collects the issue, the address, urgency level, and confirms them on the schedule automatically. Your tech gets a notification. No missed calls. No manual dispatch at midnight."', goal: 'Demo the live flow.' },
      { title: 'Close Attempt (3 min)',     script: '"If this captures even 3 extra emergency calls a month at your average ticket price — what does that number look like? Is that worth a 30-day trial?"', goal: 'ROI close.' },
    ],
    objections: {
      'We have an answering service': '"Does it auto-schedule, or does someone still have to call back? That\'s the gap we close."',
      'Not sure about AI':            '"Fair. Let me show you a real call — you tell me if you can tell the difference."',
    },
  }),
  dental: (company) => ({
    duration: '15 minutes',
    sections: [
      { title: 'Opening (2 min)',           script: `"Thanks for the time. ${company} — can you tell me your current no-show rate? And what does one no-show cost the practice on average?"`, goal: 'Quantify the problem in dollars.' },
      { title: 'Problem Confirmation (3 min)', script: '"At a 20% no-show rate and $200 average appointment value — a 10-chair practice is losing $4,000 a week. Most of that is recoverable with the right system."', goal: 'Make the math undeniable.' },
      { title: 'Solution Walkthrough (7 min)', script: '"Here\'s our patient communication system. Automated reminders by text and email, smart re-booking if they cancel, and a reactivation campaign for patients who haven\'t been in 6 months. Your staff does nothing — it runs itself."', goal: 'Show the automation flow live.' },
      { title: 'Close Attempt (3 min)',     script: '"If we recover 10 no-show appointments per month — that\'s $2,000 back per month. Our system costs a fraction of that. Want to start a 30-day pilot?"', goal: 'ROI-driven close.' },
    ],
    objections: {
      'Our patients prefer calling': '"Absolutely — calls still work. This layer handles everyone who doesn\'t call back. You\'re not replacing calls, you\'re capturing what falls through."',
      'Our staff handles reminders':  '"How many hours per week does that take? Let\'s free them up for higher-value work."',
    },
  }),
  plumbing: (company) => ({
    duration: '15 minutes',
    sections: [
      { title: 'Opening (2 min)',           script: `"Quick question for ${company} — when you send out an estimate and don\'t hear back, what\'s your follow-up process right now?"`, goal: 'Surface the specific gap.' },
      { title: 'Problem Confirmation (3 min)', script: '"Most plumbing companies send the estimate and maybe follow up once. The reality is it takes 5 touches on average to close — and almost nobody does 5."', goal: 'Normalize the problem.' },
      { title: 'Solution Walkthrough (7 min)', script: '"Here\'s our automated follow-up system. Estimate goes out, system automatically follows up at 24h, 3 days, 7 days with different messages. If they respond, your team takes it from there. If not — they get a final offer. Close rate goes up without your team doing anything extra."', goal: 'Show the automation sequence.' },
      { title: 'Close Attempt (3 min)',     script: '"If this closes 2 extra jobs a month at your average ticket — what does that add up to in a year? Worth a test?"', goal: 'ROI close.' },
    ],
    objections: {
      'We already follow up': '"How consistently? The system does it even when your team is busy. That\'s the difference."',
    },
  }),
  contractor: (company) => ({
    duration: '15 minutes',
    sections: [
      { title: 'Opening (2 min)',           script: `"${company} — what does your current intake process look like when a potential client reaches out about a project?"`, goal: 'Map the current state.' },
      { title: 'Problem Confirmation (3 min)', script: '"The pattern I see most often: lead comes in by phone or email, someone means to follow up, things get busy — and a week later the project went to someone else."', goal: 'Mirror their experience.' },
      { title: 'Solution Walkthrough (7 min)', script: '"Here\'s the intake system we built for contractors. Lead submits info — project type, address, scope. System qualifies it, sends a confirmation, schedules a callback, and logs everything in a pipeline. Nothing falls through."', goal: 'Walk through the intake flow.' },
      { title: 'Close Attempt (3 min)',     script: '"How many projects do you think slip through in a month right now? If this captures even one more — what\'s that worth? Let\'s get you set up."', goal: 'Value-based close.' },
    ],
    objections: {
      'We handle intake fine': '"How many leads converted last month versus how many came in? I\'d love to help you measure that."',
    },
  }),
};

async function generateDemoScript({ company = 'Prospect', niche = 'hoa' } = {}) {
  try {
    const key = API_KEY();
    if (key) {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method:  'POST',
        headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({
          model:      MODEL,
          max_tokens: 600,
          messages: [{
            role:    'user',
            content: `Create a 15-minute demo script for selling AI workflow automation to "${company}", a ${niche} business. Return JSON: { "duration": "15 minutes", "sections": [{"title":"...","script":"...","goal":"..."}], "objections": {"objection":"response"} }. Include 4 sections and 3 objection handlers.`,
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
          if (parsed.sections) return { ...parsed, source: 'claude', niche, company };
        }
      }
    }

    const scriptFn = DEMO_SCRIPTS[niche] || DEMO_SCRIPTS.hoa;
    return { ...scriptFn(company), source: 'template', niche, company };
  } catch (err) {
    console.error('[demoAgent] Error:', err.message);
    return {
      duration: '15 minutes',
      sections: [
        { title: 'Opening',  script: 'Start by asking about their biggest operational pain.', goal: 'Confirm fit' },
        { title: 'Demo',     script: 'Show the dashboard and automation flow.',              goal: 'Build desire' },
        { title: 'Close',    script: 'Ask what it would take to move forward.',              goal: 'Get commitment' },
      ],
      objections: { 'Price concern': 'Anchor to the cost of NOT solving the problem.' },
      source: 'fallback',
      niche,
      company,
    };
  }
}

module.exports = { generateDemoScript };
