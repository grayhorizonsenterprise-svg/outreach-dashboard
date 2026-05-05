/**
 * grantSearch.js — Gray Horizons Enterprise Revenue Engine
 * Standalone grant discovery engine. No external dependencies beyond Node 18+.
 */

'use strict';

const { PROFILE, WEIGHTS, SIGNALS } = require('./grantProfile');

const GRANTS_GOV_URL = 'https://api.grants.gov/v1/api/search2';

const SEARCH_KEYWORDS = [
  'minority business', 'black owned business', 'small business technology',
  'AI innovation', 'automation startup', 'SaaS small business',
  'economic development', 'SBIR', 'minority entrepreneur',
  'underrepresented technology', 'disadvantaged business', 'innovation grant',
];

const FALLBACK_GRANTS = [
  { title: 'SBIR Phase I — Small Business Innovation Research', amount: '$50,000 – $275,000', deadline: 'Rolling', source: 'SBA / Federal', url: 'https://www.sbir.gov', tags: ['sbir','small business','ai','technology','innovation'] },
  { title: 'MBDA Business Center Grant Program', amount: '$50,000 – $500,000', deadline: 'Annual', source: 'Minority Business Development Agency', url: 'https://www.mbda.gov', tags: ['minority','black','mbda','business development'] },
  { title: 'SBA 8(a) Business Development Program', amount: 'Up to $250,000', deadline: 'Open enrollment', source: 'Small Business Administration', url: 'https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program', tags: ['8a','minority','black','small business','disadvantaged'] },
  { title: 'California CEDAP — Capital & Tech Access Grant', amount: '$5,000 – $75,000', deadline: 'Rolling', source: 'CA Office of the Small Business Advocate', url: 'https://calosba.ca.gov', tags: ['california','small business','technology','minority'] },
  { title: 'Google for Startups — Black Founders Fund', amount: '$50,000 – $100,000', deadline: 'Annual', source: 'Google', url: 'https://startup.google.com/programs/black-founders-fund/', tags: ['black','technology','startup','ai','saas'] },
  { title: 'Hello Alice — Black Business Owners Grant', amount: '$500 – $10,000', deadline: 'Rolling', source: 'Hello Alice', url: 'https://helloalice.com/grants', tags: ['black','minority','small business','entrepreneur'] },
  { title: 'NSF America\'s Seed Fund (SBIR/STTR)', amount: '$256,000 Phase I', deadline: 'Rolling cycles', source: 'National Science Foundation', url: 'https://seedfund.nsf.gov', tags: ['sbir','sttr','technology','ai','innovation','federal'] },
  { title: 'NMSDC Innovation in Business Award Grant', amount: '$5,000 – $25,000', deadline: 'Annual Q3', source: 'National Minority Supplier Development Council', url: 'https://nmsdc.org', tags: ['minority','black','innovation','technology'] },
  { title: 'FedEx Small Business Grant Contest', amount: '$2,500 – $50,000', deadline: 'Annual Q1', source: 'FedEx', url: 'https://www.fedex.com/en-us/small-business/grant.html', tags: ['small business','startup','entrepreneur','technology'] },
  { title: 'Comcast RISE Investment Fund', amount: '$10,000', deadline: 'Rolling', source: 'Comcast', url: 'https://www.comcastrise.com', tags: ['minority','black','small business','technology'] },
  { title: 'DOC Minority Business Development Grant', amount: '$50,000 – $300,000', deadline: 'Annual', source: 'Department of Commerce', url: 'https://www.commerce.gov/news/grants', tags: ['minority','black','economic development','federal'] },
  { title: 'Verizon Small Business Digital Ready Grant', amount: '$10,000', deadline: 'Rolling', source: 'Verizon', url: 'https://digitalreadysmallbusiness.verizon.com', tags: ['small business','technology','digital','automation'] },
];

function scoreGrant(grant) {
  const text = [grant.title||'', grant.synopsis||'', grant.agency||'', (grant.tags||[]).join(' '), grant.source||''].join(' ').toLowerCase();
  let score = 0;
  if (SIGNALS.minority.some(s => text.includes(s)))    score += WEIGHTS.minority;
  if (SIGNALS.tech.some(s => text.includes(s)))         score += WEIGHTS.tech;
  if (SIGNALS.smallBiz.some(s => text.includes(s)))     score += WEIGHTS.smallBiz;
  if (SIGNALS.community.some(s => text.includes(s)))    score += WEIGHTS.community;
  if (SIGNALS.california.some(s => text.includes(s)))   score += WEIGHTS.california;
  const amt = parseInt(String(grant.amount || grant.awardCeiling || '0').replace(/[^0-9]/g,''), 10) || 0;
  if (amt >= PROFILE.funding.minAmount && amt <= PROFILE.funding.maxAmount) score += WEIGHTS.fundRange;
  else if (amt === 0) score += Math.floor(WEIGHTS.fundRange / 2);
  return Math.min(score, 100);
}

function normalizeGovGrant(hit) {
  return {
    title:    hit.title || hit.oppTitle || 'Untitled Grant',
    amount:   hit.awardCeiling ? `Up to $${Number(hit.awardCeiling).toLocaleString()}` : 'See listing',
    deadline: hit.closeDate || 'See listing',
    source:   hit.agencyName || 'Grants.gov',
    synopsis: hit.synopsis || '',
    agency:   hit.agencyName || '',
    url:      `https://www.grants.gov/search-results-detail/${hit.id || ''}`,
    tags:     [],
  };
}

async function fetchKeyword(keyword) {
  try {
    const res = await fetch(GRANTS_GOV_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, oppStatuses: ['posted'], rows: 8, startRecordNum: 0 }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data?.data?.oppHits || data?.oppHits || []).map(normalizeGovGrant);
  } catch {
    return [];
  }
}

function dedup(grants) {
  const seen = new Set();
  return grants.filter(g => {
    const key = (g.title || '').toLowerCase().trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function enhanceWithClaude(grants, apiKey) {
  if (!apiKey || !grants.length) return grants;
  try {
    const sample = grants.slice(0, 5);
    const prompt = sample.map((g, i) => `${i+1}. ${g.title} | ${g.amount} | ${g.source}`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-3-haiku-20240307', max_tokens: 200,
        messages: [{ role: 'user', content: `Rank these grants best-to-worst for a Black-owned AI/SaaS small business in California. Return JSON array of 1-based indexes only.\n\n${prompt}` }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return grants;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\d,\s]+\]/);
    if (!match) return grants;
    const order = JSON.parse(match[0]);
    const reordered = order.filter(n => n >= 1 && n <= sample.length).map(n => sample[n - 1]);
    return [...reordered, ...grants.slice(5)];
  } catch {
    return grants;
  }
}

async function searchGrants({ claudeKey = null, limit = 20 } = {}) {
  try {
    const BATCH = 4;
    let liveGrants = [];
    for (let i = 0; i < SEARCH_KEYWORDS.length; i += BATCH) {
      const results = await Promise.all(SEARCH_KEYWORDS.slice(i, i + BATCH).map(fetchKeyword));
      results.forEach(r => liveGrants.push(...r));
    }
    const combined  = dedup([...liveGrants, ...FALLBACK_GRANTS]);
    const scored    = combined.map(g => ({ ...g, score: scoreGrant(g) })).sort((a, b) => b.score - a.score);
    const enhanced  = await enhanceWithClaude(scored, claudeKey);
    return enhanced.slice(0, Math.max(limit, FALLBACK_GRANTS.length));
  } catch (err) {
    console.error('[grantSearch] Error:', err.message);
    return FALLBACK_GRANTS.map(g => ({ ...g, score: scoreGrant(g) }));
  }
}

module.exports = { searchGrants };
