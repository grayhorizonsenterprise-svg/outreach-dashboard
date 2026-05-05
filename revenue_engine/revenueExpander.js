/**
 * revenueExpander.js — Gray Horizons Enterprise Revenue Engine
 * Generates revenue expansion plays: upsells, cross-sells, new streams.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const EXPANSION_PLAYS = [
  {
    id:           'exp-001',
    type:         'Upsell',
    title:        'HOA Enterprise Tier Upgrade',
    trigger:      'Client has been live 30+ days and manages 5+ communities',
    currentMRR:   397,
    targetMRR:    1197,
    uplift:       800,
    pitch:        'You\'ve got the system working across 5 communities. The Enterprise tier unlocks unlimited communities, role-based staff access, and the board portal. At your growth rate, it pays for itself when you add two more communities.',
    probability:  55,
  },
  {
    id:           'exp-002',
    type:         'Cross-sell',
    title:        'Add AI Receptionist to HOA Clients',
    trigger:      'HOA client has a main office phone number',
    currentMRR:   397,
    targetMRR:    694,
    uplift:       297,
    pitch:        'Your compliance system is running great. One thing we hear from management firms is that incoming resident calls are still a bottleneck. We can add AI call handling — it routes to the right team member automatically. $297/month on top of what you\'re already paying.',
    probability:  45,
  },
  {
    id:           'exp-003',
    type:         'New Stream',
    title:        'Managed Outreach Service',
    trigger:      'GHE outreach system proven internally',
    currentMRR:   0,
    targetMRR:    1500,
    uplift:       1500,
    pitch:        'The outreach system Gray Horizons runs internally — AI-generated cold emails, lead scoring, pipeline tracking — is sellable as a done-for-you service to other service businesses. $1,000-$2,000/mo per client.',
    probability:  60,
  },
  {
    id:           'exp-004',
    type:         'New Stream',
    title:        'Grant Application Service',
    trigger:      'GHE successfully receives first grant',
    currentMRR:   0,
    targetMRR:    2500,
    uplift:       2500,
    pitch:        'Once GHE has a funded grant under its belt, the process and templates are sellable. Charge other minority-owned businesses $500-$1,500 to prepare and submit grant applications. High-margin, minimal ongoing overhead.',
    probability:  50,
  },
  {
    id:           'exp-005',
    type:         'Upsell',
    title:        'Analytics + Reporting Add-On',
    trigger:      'Any client active 60+ days',
    currentMRR:   397,
    targetMRR:    547,
    uplift:       150,
    pitch:        'We can add monthly executive reports — PDF format, board-ready — showing compliance rates, resolution times, and trend lines. Some boards require it. $150/month.',
    probability:  65,
  },
  {
    id:           'exp-006',
    type:         'Channel',
    title:        'Referral Program Launch',
    trigger:      'First satisfied client',
    currentMRR:   0,
    targetMRR:    1200,
    uplift:       1200,
    pitch:        'Give every satisfied client a referral link. They get one month free for every referral that converts. You get a new $400/mo client for $400 cost — 1:1 CAC-to-MRR ratio, and it scales without hiring.',
    probability:  70,
  },
];

async function enrichExpansion(plays) {
  const key = API_KEY();
  if (!key) return plays;
  try {
    const topPlays = plays.slice(0, 3);
    const prompt   = topPlays.map((p, i) => `${i+1}. ${p.title} | Uplift: $${p.uplift}/mo | Probability: ${p.probability}%`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 250,
        messages: [{ role: 'user', content: `You are a growth advisor for Gray Horizons Enterprise, Black-owned AI firm, Rialto CA. For each expansion play below, add the single biggest risk that would kill this opportunity.\n\n${prompt}\n\nReturn JSON array: [{"id":"exp-001","risk":"..."}]` }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return plays;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\s\S]*\]/);
    if (!match) return plays;
    const risks = JSON.parse(match[0]);
    const map   = Object.fromEntries(risks.map(r => [r.id, r.risk]));
    return plays.map(p => map[p.id] ? { ...p, topRisk: map[p.id] } : p);
  } catch {
    return plays;
  }
}

async function expandRevenue() {
  try {
    const plays    = EXPANSION_PLAYS.map(p => ({ ...p, generatedAt: new Date().toISOString() }));
    const enriched = await enrichExpansion(plays);
    const totalUpliftPotential = enriched.reduce((sum, p) => sum + p.uplift, 0);
    return {
      totalUpliftPotential: `$${totalUpliftPotential.toLocaleString()}/mo`,
      plays: enriched.sort((a, b) => (b.uplift * b.probability / 100) - (a.uplift * a.probability / 100)),
    };
  } catch (err) {
    console.error('[revenueExpander] Error:', err.message);
    return { totalUpliftPotential: '$0/mo', plays: EXPANSION_PLAYS };
  }
}

module.exports = { expandRevenue };
