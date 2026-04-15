/**
 * grantProfile.js — Gray Horizons Enterprise
 * Business owner profile + scoring weights for grant matching.
 * Edit this file to update profile → scores adjust automatically.
 */

const PROFILE = {
  // Owner demographics
  owner: {
    minority:   true,
    black:      true,
    male:       true,
    ageRange:   '35-45',
    married:    true,
    hasFamily:  true,
  },

  // Business details
  business: {
    name:       'Gray Horizons Enterprise',
    industry:   ['AI', 'automation', 'SaaS', 'technology', 'software'],
    stage:      'active',        // seed | active | growth
    location:   'Rialto, CA',
    state:      'CA',
    employees:  5,               // update as you grow
    forProfit:  true,
  },

  // Funding target
  funding: {
    minAmount:  500,
    maxAmount:  500000,
  },
};

// ── Scoring weights (must total ~100 when all match) ─────────────────────────

const WEIGHTS = {
  minority:    25,   // minority / Black-owned mention
  tech:        25,   // AI / automation / SaaS / tech
  smallBiz:    20,   // small business
  fundRange:   15,   // amount falls in $500–$500k
  community:   10,   // family / community / economic development
  california:   5,   // CA or West Coast preference
};

// ── Keyword signal lists (used by scorer) ────────────────────────────────────

const SIGNALS = {
  minority: [
    'minority', 'black', 'african american', 'bipoc', 'underrepresented',
    'disadvantaged', 'equity', 'diverse', 'mbe', 'minority-owned',
    'black-owned', 'mbda', '8(a)', '8a', 'historically underutilized',
    'hub zone', 'hubzone',
  ],
  tech: [
    'technology', 'tech', 'ai', 'artificial intelligence', 'automation',
    'saas', 'software', 'innovation', 'digital', 'startup', 'r&d',
    'research and development', 'sbir', 'sttr', 'advanced technology',
    'emerging technology', 'machine learning', 'data', 'cloud',
  ],
  smallBiz: [
    'small business', 'small businesses', 'entrepreneur', 'entrepreneurship',
    'startup', 'new business', 'emerging business', 'microbusiness',
    'microenterprise', 'sba', 'self-employed', 'sole proprietor',
  ],
  community: [
    'community', 'economic development', 'workforce', 'family',
    'local business', 'neighborhood', 'rural', 'urban', 'community development',
    'low-income', 'underserved', 'capacity building',
  ],
  california: [
    'california', 'ca ', ' ca,', 'west coast', 'southern california',
    'inland empire', 'san bernardino', 'los angeles', 'riverside',
  ],
};

module.exports = { PROFILE, WEIGHTS, SIGNALS };
