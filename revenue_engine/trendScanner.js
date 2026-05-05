/**
 * trendScanner.js — Gray Horizons Enterprise Revenue Engine
 * Identifies market trends and monetization angles for GHE niches.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const CURATED_TRENDS = [
  {
    name:             'AI Voice Receptionist Adoption',
    category:         'Technology',
    opportunityScore: 94,
    momentum:         'Accelerating',
    description:      'SMBs in service industries (HVAC, plumbing, dental) are replacing answering services with AI receptionists. Adoption rate growing 40% YoY. Decision cycle: 2-4 weeks.',
    monetization:     '$247–$397/mo SaaS. Upsell: multi-location, CRM integration, analytics dashboard.',
    targetNiches:     ['hvac', 'plumbing', 'dental', 'contractor'],
    urgency:          'High — early-mover advantage window is 12-18 months',
  },
  {
    name:             'HOA Compliance Automation',
    category:         'PropTech',
    opportunityScore: 91,
    momentum:         'Growing',
    description:      'HOA management companies managing 10+ communities still use email/spreadsheets for violations. Digital transformation budgets up 35% post-COVID. Decision makers: Operations VPs and GMs.',
    monetization:     '$397/mo per management company. Enterprise: $1,200+/mo for portfolios of 50+ HOAs.',
    targetNiches:     ['hoa'],
    urgency:          'High — HOA management is consolidating, sign large firms before they get acquired',
  },
  {
    name:             'Black-Owned Business Grant Wave',
    category:         'Funding',
    opportunityScore: 88,
    momentum:         'Peak',
    description:      'Federal and corporate grant programs for minority-owned tech businesses are at record funding levels. MBDA, SBIR, and Google Black Founders Fund all active. Application windows open Q2 2026.',
    monetization:     'Direct grants $5K–$500K. Non-dilutive. 60-day application cycles.',
    targetNiches:     ['all'],
    urgency:          'Urgent — Q2 2026 deadlines approaching. Apply within 30 days.',
  },
  {
    name:             'Contractor Intake Digitization',
    category:         'ConstructionTech',
    opportunityScore: 85,
    momentum:         'Growing',
    description:      'General contractors losing 20-30% of inbound project leads due to manual intake. $15B+ in residential renovation spend in SoCal annually. No dominant SMB intake tool exists.',
    monetization:     '$397/mo. Upsell: subcontractor coordination, change order management, client portal.',
    targetNiches:     ['contractor'],
    urgency:          'Medium — summer build season starting, contractors actively looking for systems',
  },
  {
    name:             'Dental No-Show Recovery Automation',
    category:         'HealthTech',
    opportunityScore: 89,
    momentum:         'Steady',
    description:      'Average dental practice loses $80K/year to no-shows. AI reminder + rebooking systems proven to cut no-show rates by 30-50%. Market fragmented — no clear winner below $500/mo.',
    monetization:     '$347/mo. ROI positive on day one for most practices. High retention once installed.',
    targetNiches:     ['dental'],
    urgency:          'Medium — steady demand, year-round opportunity',
  },
  {
    name:             'Outbound AI Sales Automation',
    category:         'SalesTech',
    opportunityScore: 82,
    momentum:         'Accelerating',
    description:      'AI-generated personalized outreach at scale is replacing manual cold email. Response rates 2-3x higher than templates. GHE outreach system is ahead of the curve.',
    monetization:     'Internal multiplier — scale outreach 10x without hiring. Also sellable as a service.',
    targetNiches:     ['all'],
    urgency:          'High — use now to fill own pipeline before competitors catch up',
  },
];

async function enhanceWithClaude(trends) {
  const key = API_KEY();
  if (!key) return trends;
  try {
    const prompt = trends.slice(0, 3).map((t, i) => `${i+1}. ${t.name} | Score: ${t.opportunityScore} | ${t.description.slice(0, 80)}`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 300,
        messages: [{ role: 'user', content: `You are a business strategist for Gray Horizons Enterprise, a Black-owned AI automation firm in Rialto CA. Add a 1-sentence "immediateAction" for each trend — what should the owner do THIS WEEK?\n\n${prompt}\n\nReturn JSON array: [{"name":"...","immediateAction":"..."}]` }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return trends;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\s\S]*\]/);
    if (!match) return trends;
    const actions = JSON.parse(match[0]);
    const map     = Object.fromEntries(actions.map(a => [a.name, a.immediateAction]));
    return trends.map(t => map[t.name] ? { ...t, immediateAction: map[t.name] } : t);
  } catch {
    return trends;
  }
}

async function scanTrends() {
  try {
    const trends   = CURATED_TRENDS.map(t => ({ ...t, scannedAt: new Date().toISOString() }));
    const enhanced = await enhanceWithClaude(trends);
    return enhanced.sort((a, b) => b.opportunityScore - a.opportunityScore);
  } catch (err) {
    console.error('[trendScanner] Error:', err.message);
    return CURATED_TRENDS;
  }
}

module.exports = { scanTrends };
