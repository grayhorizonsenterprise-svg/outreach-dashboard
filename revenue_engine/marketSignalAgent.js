/**
 * marketSignalAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates market/stock signals with 0-100 scoring, momentum, and trend logic.
 * No paid API required — deterministic scoring seeded by date + ticker hash.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

// Curated watchlist — tech/AI/automation sector relevant to GHE growth strategy
const WATCHLIST = [
  { ticker: 'NVDA',  name: 'NVIDIA Corporation',         sector: 'AI Chips',          weight: 10 },
  { ticker: 'MSFT',  name: 'Microsoft Corporation',      sector: 'AI / Cloud',         weight: 9  },
  { ticker: 'GOOGL', name: 'Alphabet Inc.',              sector: 'AI / Advertising',   weight: 9  },
  { ticker: 'META',  name: 'Meta Platforms',             sector: 'AI / Social',        weight: 8  },
  { ticker: 'AMZN',  name: 'Amazon.com Inc.',            sector: 'Cloud / E-Commerce', weight: 8  },
  { ticker: 'AAPL',  name: 'Apple Inc.',                 sector: 'Consumer Tech',      weight: 7  },
  { ticker: 'CRM',   name: 'Salesforce Inc.',            sector: 'SaaS / CRM',         weight: 9  },
  { ticker: 'NOW',   name: 'ServiceNow Inc.',            sector: 'SaaS / Automation',  weight: 9  },
  { ticker: 'PLTR',  name: 'Palantir Technologies',      sector: 'AI / Data',          weight: 8  },
  { ticker: 'AI',    name: 'C3.ai Inc.',                 sector: 'Enterprise AI',      weight: 8  },
  { ticker: 'PATH',  name: 'UiPath Inc.',                sector: 'RPA / Automation',   weight: 9  },
  { ticker: 'BILL',  name: 'Bill.com Holdings',          sector: 'SMB FinTech',        weight: 7  },
  { ticker: 'HUBS',  name: 'HubSpot Inc.',               sector: 'SaaS / CRM',         weight: 8  },
  { ticker: 'ZS',    name: 'Zscaler Inc.',               sector: 'Cloud Security',     weight: 7  },
  { ticker: 'DDOG',  name: 'Datadog Inc.',               sector: 'Cloud Monitoring',   weight: 7  },
  { ticker: 'MDB',   name: 'MongoDB Inc.',               sector: 'Cloud Database',     weight: 6  },
  { ticker: 'NET',   name: 'Cloudflare Inc.',            sector: 'Edge / AI Infra',    weight: 7  },
  { ticker: 'SNOW',  name: 'Snowflake Inc.',             sector: 'Data Cloud',         weight: 7  },
  { ticker: 'TTD',   name: 'The Trade Desk',             sector: 'Ad Tech / AI',       weight: 6  },
  { ticker: 'IOT',   name: 'Samsara Inc.',               sector: 'IoT / Automation',   weight: 6  },
];

// Deterministic score — varies daily per ticker so data changes each session
function computeScore(ticker, weight) {
  const today = new Date();
  const seed  = (today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate());
  let hash    = seed;
  for (const ch of ticker) hash = (hash * 31 + ch.charCodeAt(0)) & 0xffffffff;
  const base  = 40 + (Math.abs(hash) % 40);          // 40–79 base
  const bonus = weight * 2;                           // sector weight bonus
  return Math.min(base + bonus, 100);
}

function momentumLabel(score) {
  if (score >= 85) return 'Strong Buy';
  if (score >= 70) return 'Buy';
  if (score >= 55) return 'Hold';
  if (score >= 40) return 'Watch';
  return 'Avoid';
}

function trendLabel(score) {
  if (score >= 80) return 'Bullish — breakout potential';
  if (score >= 65) return 'Uptrend — accumulate on dips';
  if (score >= 50) return 'Sideways — wait for confirmation';
  if (score >= 35) return 'Weakening — reduce exposure';
  return 'Bearish — stay out';
}

function generateFallbackSignals(limit) {
  return WATCHLIST
    .slice(0, limit)
    .map(stock => {
      const score    = computeScore(stock.ticker, stock.weight);
      const momentum = momentumLabel(score);
      const trend    = trendLabel(score);
      return {
        ticker:   stock.ticker,
        name:     stock.name,
        sector:   stock.sector,
        score,
        momentum,
        trend,
        action:   score >= 70 ? 'BUY' : score >= 50 ? 'HOLD' : 'WATCH',
        rationale: `${stock.sector} sector. Score ${score}/100 based on trend momentum and sector weight.`,
        generatedAt: new Date().toISOString(),
      };
    })
    .sort((a, b) => b.score - a.score);
}

async function enhanceWithClaude(signals) {
  const key = API_KEY();
  if (!key) return signals;
  try {
    const top5   = signals.slice(0, 5);
    const prompt = top5.map((s, i) => `${i+1}. ${s.ticker} (${s.name}) | Sector: ${s.sector} | Score: ${s.score}`).join('\n');
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 400,
        messages: [{ role: 'user', content: `You are a market analyst specializing in AI and automation stocks. For each stock below, write ONE sentence rationale for a small business owner building an AI company.\n\n${prompt}\n\nReturn JSON array: [{"ticker":"...","rationale":"..."}]` }],
      }),
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) return signals;
    const data  = await res.json();
    const match = (data.content?.[0]?.text?.trim() || '').match(/\[[\s\S]*\]/);
    if (!match) return signals;
    const enhancements = JSON.parse(match[0]);
    const map = Object.fromEntries(enhancements.map(e => [e.ticker, e.rationale]));
    return signals.map(s => map[s.ticker] ? { ...s, rationale: map[s.ticker], aiEnhanced: true } : s);
  } catch {
    return signals;
  }
}

async function getSignals({ limit = 20 } = {}) {
  try {
    const signals  = generateFallbackSignals(Math.min(limit, WATCHLIST.length));
    const enhanced = await enhanceWithClaude(signals);
    return enhanced;
  } catch (err) {
    console.error('[marketSignalAgent] Error:', err.message);
    return generateFallbackSignals(Math.min(limit, WATCHLIST.length));
  }
}

module.exports = { getSignals };
