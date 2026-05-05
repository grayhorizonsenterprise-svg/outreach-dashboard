/**
 * grantProfile.js — Gray Horizons Enterprise Revenue Engine
 * Business owner profile + scoring weights for grant matching.
 */

'use strict';

const PROFILE = {
  owner: {
    minority:  true,
    black:     true,
    male:      true,
    ageRange:  '35-45',
    married:   true,
    hasFamily: true,
  },
  business: {
    name:      'Gray Horizons Enterprise',
    industry:  ['AI', 'automation', 'SaaS', 'technology', 'software'],
    stage:     'active',
    location:  'Rialto, CA',
    state:     'CA',
    employees: 5,
    forProfit: true,
  },
  funding: {
    minAmount: 500,
    maxAmount: 500000,
  },
};

const WEIGHTS = {
  minority:    25,
  tech:        25,
  smallBiz:    20,
  fundRange:   15,
  community:   10,
  california:   5,
};

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
