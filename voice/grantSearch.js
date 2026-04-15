/**
 * grantSearch.js — Gray Horizons Enterprise
 * Multi-source grant discovery engine.
 *
 * Sources (in order of priority):
 *   1. Grants.gov API — live federal grants
 *   2. Curated fallback list — always populated, profile-matched
 *
 * Scoring: profile-aware, 0–100
 * Claude: optional enhancement only — never required to function
 */

'use strict';

const { PROFILE, WEIGHTS, SIGNALS } = require('./grantProfile');

const GRANTS_GOV_URL = 'https://api.grants.gov/v1/api/search2';

// ── Keywords sent to Grants.gov (broad + profile-specific) ───────────────────

const SEARCH_KEYWORDS = [
  'minority business',
  'black owned business',
  'small business technology',
  'AI innovation',
  'automation startup',
  'SaaS small business',
  'economic development',
  'entrepreneurship',
  'SBIR',
  'STTR',
  'minority entrepreneur',
  'underrepresented technology',
  'community development business',
  'disadvantaged business',
  'innovation grant',
];

// ── Curated fallback grants (real programs, always returned if API fails) ─────

const FALLBACK_GRANTS = [
  {
    title:    'SBIR Phase I — Small Business Innovation Research',
    amount:   '$50,000 – $275,000',
    deadline: 'Rolling',
    source:   'SBA / Federal',
    url:      'https://www.sbir.gov',
    tags:     ['sbir', 'small business', 'ai', 'technology', 'innovation', 'r&d'],
  },
  {
    title:    'MBDA Business Center Grant Program',
    amount:   '$50,000 – $500,000',
    deadline: 'Annual — check site',
    source:   'Minority Business Development Agency',
    url:      'https://www.mbda.gov',
    tags:     ['minority', 'black', 'mbda', 'business development', 'entrepreneurship'],
  },
  {
    title:    'SBA 8(a) Business Development Program',
    amount:   'Up to $250,000',
    deadline: 'Open enrollment',
    source:   'Small Business Administration',
    url:      'https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program',
    tags:     ['8a', 'minority', 'black', 'small business', 'disadvantaged'],
  },
  {
    title:    'California CEDAP — Capital & Tech Access Grant',
    amount:   '$5,000 – $75,000',
    deadline: 'Rolling',
    source:   'CA Office of the Small Business Advocate',
    url:      'https://calosba.ca.gov',
    tags:     ['california', 'small business', 'technology', 'minority', 'community'],
  },
  {
    title:    'FedEx Small Business Grant Contest',
    amount:   '$2,500 – $50,000',
    deadline: 'Annual — Q1',
    source:   'FedEx',
    url:      'https://www.fedex.com/en-us/small-business/grant.html',
    tags:     ['small business', 'startup', 'entrepreneur', 'technology'],
  },
  {
    title:    'Hello Alice — Black Business Owners Grant',
    amount:   '$500 – $10,000',
    deadline: 'Rolling',
    source:   'Hello Alice',
    url:      'https://helloalice.com/grants',
    tags:     ['black', 'minority', 'small business', 'entrepreneur', 'equity'],
  },
  {
    title:    'NMSDC Innovation in Business Award Grant',
    amount:   '$5,000 – $25,000',
    deadline: 'Annual — Q3',
    source:   'National Minority Supplier Development Council',
    url:      'https://nmsdc.org',
    tags:     ['minority', 'black', 'innovation', 'technology', 'supplier'],
  },
  {
    title:    'Google for Startups — Black Founders Fund',
    amount:   '$50,000 – $100,000',
    deadline: 'Annual — rolling',
    source:   'Google',
    url:      'https://startup.google.com/programs/black-founders-fund/',
    tags:     ['black', 'technology', 'startup', 'ai', 'saas', 'software'],
  },
  {
    title:    'Comcast RISE Investment Fund',
    amount:   '$10,000',
    deadline: 'Rolling',
    source:   'Comcast',
    url:      'https://www.comcastrise.com',
    tags:     ['minority', 'black', 'small business', 'technology', 'community'],
  },
  {
    title:    'DOC Minority Business Development Grant',
    amount:   '$50,000 – $300,000',
    deadline: 'Annual — check site',
    source:   'Department of Commerce',
    url:      'https://www.commerce.gov/news/grants',
    tags:     ['minority', 'black', 'economic development', 'business', 'federal'],
  },
  {
    title:    'NSF — America's Seed Fund (SBIR/STTR)',
    amount:   '$256,000 Phase I',
    deadline: 'Rolling cycles',
    source:   'National Science Foundation',
    url:      'https://seedfund.nsf.gov',
    tags:     ['sbir', 'sttr', 'technology', 'ai', 'innovation', 'research', 'federal'],
  },
  {
    title:    'Verizon Small Business Digital Ready Grant',
    amount:   '$10,000',
    deadline: 'Rolling',
    source:   'Verizon',
    url:      'https://digitalreadysmallbusiness.verizon.com',
    tags:     ['small business', 'technology', 'digital', 'automation', 'community'],
  },
];

// ── Score a single grant against the owner profile ────────────────────────────

function scoreGrant(grant) {
  const text = [
    grant.title    || '',
    grant.synopsis || '',
    grant.agency   || '',
    (grant.tags || []).join(' '),
    grant.source   || '',
  ].join(' ').toLowerCase();

  let score = 0;

  // Minority / Black-owned signals
  const minorityHit = SIGNALS.minority.some(s => text.includes(s));
  if (minorityHit) score += WEIGHTS.minority;

  // Tech / AI / automation signals
  const techHit = SIGNALS.tech.some(s => text.includes(s));
  if (techHit) score += WEIGHTS.tech;

  // Small business signals
  const sbHit = SIGNALS.smallBiz.some(s => text.includes(s));
  if (sbHit) score += WEIGHTS.smallBiz;

  // Community / family signals
  const commHit = SIGNALS.community.some(s => text.includes(s));
  if (commHit) score += WEIGHTS.community;

  // California preference
  const caHit = SIGNALS.california.some(s => text.includes(s));
  if (caHit) score += WEIGHTS.california;

  // Funding range check
  const amtStr = String(grant.amount || grant.awardCeiling || '0').replace(/[^0-9]/g, '');
  const amt    = parseInt(amtStr, 10) || 0;
  if (amt >= PROFILE.funding.minAmount && amt <= PROFILE.funding.maxAmount) {
    score += WEIGHTS.fundRange;
  } else if (amt === 0) {
    // Unknown amount — give partial credit (don't penalize missing data)
    score += Math.floor(WEIGHTS.fundRange / 2);
  }

  return Math.min(score, 100);
}

// ── Normalize a raw Grants.gov oppHit into standard shape ────────────────────

function normalizeGovGrant(hit) {
  return {
    title:    hit.title         || hit.oppTitle || 'Untitled Grant',
    amount:   hit.awardCeiling  ? `Up to $${Number(hit.awardCeiling).toLocaleString()}` : 'See listing',
    deadline: hit.closeDate     || hit.expectedNumberOfAwards || 'See listing',
    source:   hit.agencyName    || hit.agencyCode || 'Grants.gov',
    synopsis: hit.synopsis      || '',
    agency:   hit.agencyName    || '',
    url:      hit.oppNumber
              ? `https://www.grants.gov/search-results-detail/${hit.id || ''}`
              : 'https://www.grants.gov',
    tags:     [],
    raw:      true,
  };
}

// ── Fetch one keyword from Grants.gov — safe, never throws ───────────────────

async function fetchKeyword(keyword) {
  try {
    const res = await fetch(GRANTS_GOV_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        keyword:         keyword,
        oppStatuses:     ['posted'],
        rows:            10,
        startRecordNum:  0,
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) {
      console.warn(`[GrantSearch] Grants.gov ${res.status} for "${keyword}"`);
      return [];
    }

    const data = await res.json();
    const hits = data?.data?.oppHits || data?.oppHits || [];
    console.log(`[GrantSearch] "${keyword}" → ${hits.length} results`);
    return hits.map(normalizeGovGrant);

  } catch (err) {
    console.error(`[GrantSearch] Fetch error for "${keyword}":`, err.message);
    return [];
  }
}

// ── Deduplicate by title ──────────────────────────────────────────────────────

function dedup(grants) {
  const seen = new Set();
  return grants.filter(g => {
    const key = (g.title || '').toLowerCase().trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ── Optional: safe Claude enhancement (5 items max, never required) ───────────

async function enhanceWithClaude(grants, apiKey) {
  if (!apiKey || !grants.length) return grants;

  const sample = grants.slice(0, 5); // hard cap — never send large payload
  const prompt = sample.map((g, i) =>
    `${i + 1}. ${g.title} | ${g.amount} | ${g.source}`
  ).join('\n');

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method:  'POST',
      headers: {
        'x-api-key':         apiKey,
        'anthropic-version': '2023-06-01',
        'content-type':      'application/json',
      },
      body: JSON.stringify({
        model:      'claude-3-haiku-20240307',
        max_tokens: 400,
        messages:   [{
          role:    'user',
          content: `You are a grant advisor for a Black-owned AI/tech small business in California.\n\nRank these grants best to worst for this owner. Return a JSON array of numbers (1-based index order, best first). No explanation.\n\nGrants:\n${prompt}`,
        }],
      }),
      signal: AbortSignal.timeout(12000),
    });

    if (!res.ok) {
      console.warn('[GrantSearch] Claude enhancement skipped:', res.status);
      return grants;
    }

    const data = await res.json();
    const txt  = data.content?.[0]?.text?.trim() || '';
    // Try to parse reorder array — if it fails just return original order
    const match = txt.match(/\[[\d,\s]+\]/);
    if (!match) return grants;

    const order = JSON.parse(match[0]);
    const reordered = order
      .filter(n => n >= 1 && n <= sample.length)
      .map(n => sample[n - 1]);

    // Append any grants Claude didn't touch
    const rest = grants.slice(5);
    console.log('[GrantSearch] Claude reordered top 5');
    return [...reordered, ...rest];

  } catch (err) {
    console.warn('[GrantSearch] Claude enhancement failed (non-fatal):', err.message);
    return grants; // always return something
  }
}

// ── Main export: searchGrants() ───────────────────────────────────────────────

async function searchGrants(options = {}) {
  const { claudeKey = null, limit = 20 } = options;

  console.log('[GrantSearch] Starting multi-source search...');

  // 1. Hit Grants.gov for profile-relevant keywords (parallel)
  const BATCH = 5; // max concurrent requests
  const keyBatches = [];
  for (let i = 0; i < SEARCH_KEYWORDS.length; i += BATCH) {
    keyBatches.push(SEARCH_KEYWORDS.slice(i, i + BATCH));
  }

  let liveGrants = [];
  for (const batch of keyBatches) {
    const results = await Promise.all(batch.map(fetchKeyword));
    results.forEach(r => liveGrants.push(...r));
  }

  console.log(`[GrantSearch] Grants.gov total raw: ${liveGrants.length}`);

  // 2. Combine live + fallback (fallback always included)
  const combined = dedup([...liveGrants, ...FALLBACK_GRANTS]);
  console.log(`[GrantSearch] Combined + deduped: ${combined.length}`);

  // 3. Score every grant
  const scored = combined.map(g => ({ ...g, score: scoreGrant(g) }));

  // 4. Sort descending by score
  scored.sort((a, b) => b.score - a.score);

  // 5. Optional Claude reorder of top 5 only
  const enhanced = await enhanceWithClaude(scored, claudeKey);

  // 6. Return top N, always at least fallback count
  const results = enhanced.slice(0, Math.max(limit, FALLBACK_GRANTS.length));

  console.log(`[GrantSearch] Returning ${results.length} grants (top score: ${results[0]?.score ?? 0})`);
  return results;
}

module.exports = { searchGrants };
