/**
 * opportunityAgent.js — Gray Horizons Enterprise Revenue Engine
 * Identifies immediate revenue opportunities based on market signals and GHE assets.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const OPPORTUNITIES = [
  {
    id:          'op-001',
    title:       'Close the 25 pending HOA leads in outreach_queue.csv',
    type:        'Pipeline',
    revenueImpact: '$9,925/mo (25 × $397)',
    probability:  72,
    effort:       'Low',
    timeToRevenue: '7-14 days',
    action:       'Send the outreach emails sitting in the dashboard. They are written. Press send.',
    blockers:     ['SENDER_APP_PASSWORD must be set on Railway', 'Review each message before sending'],
  },
  {
    id:          'op-002',
    title:       'Apply to 3 grant programs this week',
    type:        'Grants',
    revenueImpact: '$50,000 – $500,000 (non-dilutive)',
    probability:  55,
    effort:       'Medium',
    timeToRevenue: '60-120 days',
    action:       'Submit MBDA Business Center + Hello Alice + SBIR Phase I applications. Deadlines Q2 2026.',
    blockers:     ['Requires 2-3 hours of application work per program'],
  },
  {
    id:          'op-003',
    title:       'Pitch AI receptionist to 5 HVAC companies this week',
    type:        'Sales',
    revenueImpact: '$1,485–$1,985/mo if 2 close',
    probability:  60,
    effort:       'Low',
    timeToRevenue: '3-7 days',
    action:       'Use leadAgent /leads?niche=hvac to generate targets. Send outreach via dashboard.',
    blockers:     [],
  },
  {
    id:          'op-004',
    title:       'Package and sell the outreach system itself as a service',
    type:        'Productization',
    revenueImpact: '$500–$1,500/mo per client',
    probability:  65,
    effort:       'Medium',
    timeToRevenue: '14-21 days',
    action:       'The outreach pipeline you built is a sellable product. Offer managed outreach service to other service businesses.',
    blockers:     ['Need a service agreement template', 'Need pricing page'],
  },
  {
    id:          'op-005',
    title:       'Activate dental vertical — zero penetration, high fit',
    type:        'Market Expansion',
    revenueImpact: '$347 × 5 clients = $1,735/mo in 30 days',
    probability:  68,
    effort:       'Low',
    timeToRevenue: '14-30 days',
    action:       'Use /leads?niche=dental. Send cold outreach. Demo script ready in /outreach (stage=demo).',
    blockers:     [],
  },
  {
    id:          'op-006',
    title:       'Partner with a local HVAC or plumbing association',
    type:        'Channel',
    revenueImpact: 'Potential 10-50 warm referrals',
    probability:  45,
    effort:       'Medium',
    timeToRevenue: '30-60 days',
    action:       'Find Inland Empire HVAC/Plumbing trade associations. Offer revenue share or referral fee for member introductions.',
    blockers:     ['Requires outreach to association directors'],
  },
];

async function enhanceWithClaude(opps) {
  const key = API_KEY();
  if (!key) return opps;
  try {
    const prompt = opps.slice(0, 3).map((o, i) => `${i+1}. ${o.title} | Impact: ${o.revenueImpact} | Probability: ${o.probability}%`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 250,
        messages: [{ role: 'user', content: `You are an advisor for Gray Horizons Enterprise, Black-owned AI firm, Rialto CA. For each opportunity, add a "smartMove" — one contrarian or non-obvious tactic to increase the probability of success.\n\n${prompt}\n\nReturn JSON array: [{"id":"op-001","smartMove":"..."}]` }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return opps;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\s\S]*\]/);
    if (!match) return opps;
    const moves = JSON.parse(match[0]);
    const map   = Object.fromEntries(moves.map(m => [m.id, m.smartMove]));
    return opps.map(o => map[o.id] ? { ...o, smartMove: map[o.id] } : o);
  } catch {
    return opps;
  }
}

async function findOpportunities() {
  try {
    const opps     = OPPORTUNITIES.map(o => ({ ...o, generatedAt: new Date().toISOString() }));
    const enhanced = await enhanceWithClaude(opps);
    return enhanced.sort((a, b) => b.probability - a.probability);
  } catch (err) {
    console.error('[opportunityAgent] Error:', err.message);
    return OPPORTUNITIES;
  }
}

module.exports = { findOpportunities };
