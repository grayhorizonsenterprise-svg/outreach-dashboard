/**
 * strategyAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates actionable strategic recommendations based on current state.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const BASE_STRATEGY = {
  focus:       'Close first 5 paying clients across HOA + HVAC niches within 30 days',
  stage:       'Pre-revenue → First $2,000 MRR',
  priorities: [
    {
      rank:   1,
      action: 'Fix email delivery and send all pending outreach',
      why:    '25+ messages are written and sitting unsent. This is the highest-leverage action available right now — zero additional work required.',
      metric: 'Target: 25 emails sent this week',
    },
    {
      rank:   2,
      action: 'Book 3 demos from outreach responses',
      why:    'Pipeline converts at roughly 10% cold to demo. 25 emails should produce 2-3 interested responses.',
      metric: 'Target: 3 demo calls scheduled within 14 days',
    },
    {
      rank:   3,
      action: 'Apply to 2 grant programs this week',
      why:    'Non-dilutive capital between $10K-$500K is available. MBDA and Hello Alice have open windows. This is free money that requires only time.',
      metric: 'Target: 2 applications submitted within 7 days',
    },
    {
      rank:   4,
      action: 'Close first paying client at $397/mo',
      why:    'First client validates the offer, creates a case study, and builds momentum. HOA vertical is most likely — 91/100 opportunity score.',
      metric: 'Target: 1 signed client within 21 days',
    },
    {
      rank:   5,
      action: 'Scale outreach to HVAC + dental niches in parallel',
      why:    'HOA pipeline is running. Adding HVAC and dental doubles the surface area without duplicating any infrastructure.',
      metric: 'Target: 15 more leads researched and messaged within 30 days',
    },
  ],
  avoid: [
    'Building new features before getting first paying client',
    'Spending money on ads before validating the offer manually',
    'Chasing too many niches simultaneously — HOA + HVAC first',
    'Over-engineering the system before product-market fit',
  ],
  nextWeekPlan: [
    'Monday: Fix Railway env vars → send 10 pending emails',
    'Tuesday: Send remaining 15 emails + begin MBDA grant application',
    'Wednesday: Follow up on Monday sends + book first demo',
    'Thursday: Submit MBDA application + generate 10 new HVAC leads',
    'Friday: Run demo if scheduled + send Hello Alice grant application',
  ],
};

async function enrichStrategyWithClaude(strategy) {
  const key = API_KEY();
  if (!key) return strategy;
  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 400,
        messages: [{
          role:    'user',
          content: `You are a strategic advisor to Gray Horizons Enterprise — a Black-owned AI automation company in Rialto, CA. Current stage: pre-revenue, targeting HOA management and HVAC companies with workflow automation. 25 outreach emails are sitting unsent due to a technical bug that was just fixed.\n\nGiven this context, what is the single most important non-obvious move the owner should make in the next 72 hours that is NOT "send the emails"? Give a concrete answer in 2-3 sentences. Then give 3 second-order effects of getting the first client signed. Return JSON: { "keyMove72h": "...", "secondOrderEffects": ["...","...","..."] }`,
        }],
      }),
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) return strategy;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\{[\s\S]*\}/);
    if (!match) return strategy;
    const intel = JSON.parse(match[0]);
    return { ...strategy, aiIntel: intel };
  } catch {
    return strategy;
  }
}

async function getStrategy() {
  try {
    return await enrichStrategyWithClaude({ ...BASE_STRATEGY, generatedAt: new Date().toISOString() });
  } catch (err) {
    console.error('[strategyAgent] Error:', err.message);
    return { ...BASE_STRATEGY, generatedAt: new Date().toISOString() };
  }
}

module.exports = { getStrategy };
