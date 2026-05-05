/**
 * offerGenerator.js — Gray Horizons Enterprise Revenue Engine
 * Generates priced service offers per niche with ROI framing.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const BASE_OFFERS = [
  {
    id:          'offer-hoa-starter',
    niche:       'hoa',
    name:        'HOA Compliance Starter',
    price:       '$397/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['Violation intake portal','Automated board notifications','Status dashboard (up to 5 communities)','Full audit trail','Resident communication log'],
    roiFrame:    'Saves 8-10 staff hours/week on manual tracking. At $25/hr, ROI positive in week one.',
    bestFor:     'Management companies with 3-10 HOA communities',
    closeScript: 'If this eliminates 8 hours of manual work per week, what\'s that worth to you? We\'re asking $397/month.',
  },
  {
    id:          'offer-hoa-enterprise',
    niche:       'hoa',
    name:        'HOA Compliance Enterprise',
    price:       '$1,197/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['Everything in Starter','Unlimited communities','Multi-staff access + roles','Board member portal','Monthly compliance reports','Priority support'],
    roiFrame:    'Replaces a part-time compliance coordinator at $2,500+/mo. Pays for itself 3x over.',
    bestFor:     'Portfolio managers with 15+ HOA communities',
    closeScript: 'You\'re managing 20 communities. If this system prevents even one lawsuit from a missed violation, it paid for a year.',
  },
  {
    id:          'offer-hvac-receptionist',
    niche:       'hvac',
    name:        'HVAC AI Receptionist',
    price:       '$297/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['24/7 AI call answering','Emergency dispatch automation','Appointment scheduling','Tech notification system','Monthly call capture report'],
    roiFrame:    'Captures 3-5 missed emergency calls/month. At $300 avg ticket, ROI is 3-5x monthly cost.',
    bestFor:     'HVAC companies doing $500K+ annual revenue',
    closeScript: 'How many emergency calls do you miss per week? Multiply that by your average ticket. That\'s what this system costs you to NOT have.',
  },
  {
    id:          'offer-dental-retention',
    niche:       'dental',
    name:        'Dental Patient Retention System',
    price:       '$347/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['Automated appointment reminders (SMS + email)','Smart cancellation re-booking','6-month reactivation campaigns','No-show analytics dashboard','Insurance verification alerts'],
    roiFrame:    'Recovers 8-12 appointments/month. At $200 avg value, that\'s $1,600-$2,400/mo recovered.',
    bestFor:     'Dental practices with 5+ chairs and 20%+ no-show rate',
    closeScript: 'Two recovered appointments covers this system for the month. Everything after that is pure upside.',
  },
  {
    id:          'offer-plumbing-followup',
    niche:       'plumbing',
    name:        'Plumbing Follow-Up Engine',
    price:       '$247/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['5-touch automated estimate follow-up','After-hours call capture','Review request automation','Open estimate pipeline dashboard','Monthly close rate report'],
    roiFrame:    'Closes 2-3 extra jobs/month. At $450 avg job, that\'s $900-$1,350/mo in recovered revenue.',
    bestFor:     'Plumbing companies sending 15+ estimates/month',
    closeScript: 'One extra job a month from this system covers it completely. We\'re looking at 2-3 extra on average.',
  },
  {
    id:          'offer-contractor-intake',
    niche:       'contractor',
    name:        'Contractor Project Intake CRM',
    price:       '$397/month',
    setupFee:    '$0',
    trialDays:   30,
    features:    ['Smart project intake form','Lead auto-qualification scoring','5-touch follow-up sequences','Project pipeline dashboard','Subcontractor coordination board','Estimate tracking'],
    roiFrame:    'Captures 1-2 extra projects/month. At $5K avg project, ROI is 12-25x monthly cost.',
    bestFor:     'General contractors doing $500K+ annual revenue',
    closeScript: 'One extra project this month from captured leads pays for 12 months of this system.',
  },
];

async function enhanceWithClaude(offers) {
  const key = API_KEY();
  if (!key) return offers;
  try {
    const prompt = offers.slice(0, 3).map((o, i) => `${i+1}. ${o.name} | ${o.price} | ROI: ${o.roiFrame.slice(0, 60)}`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 300,
        messages: [{ role: 'user', content: `You are a pricing strategist for Gray Horizons Enterprise. For each offer below, add a "upsell" — one natural add-on or upgrade path worth $100-$300/mo more.\n\n${prompt}\n\nReturn JSON array: [{"id":"offer-hoa-starter","upsell":"..."}]` }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return offers;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\s\S]*\]/);
    if (!match) return offers;
    const upsells = JSON.parse(match[0]);
    const map     = Object.fromEntries(upsells.map(u => [u.id, u.upsell]));
    return offers.map(o => map[o.id] ? { ...o, upsell: map[o.id] } : o);
  } catch {
    return offers;
  }
}

async function generateOffers({ niche = null } = {}) {
  try {
    let offers = BASE_OFFERS;
    if (niche) offers = offers.filter(o => o.niche === niche || o.niche === 'all');
    const enhanced = await enhanceWithClaude(offers);
    return enhanced;
  } catch (err) {
    console.error('[offerGenerator] Error:', err.message);
    return BASE_OFFERS;
  }
}

module.exports = { generateOffers };
