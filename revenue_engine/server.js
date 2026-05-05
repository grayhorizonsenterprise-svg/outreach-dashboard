/**
 * Gray Horizons Enterprise — Revenue Engine
 * Sales · Grants · Market Signals · Trends · Opportunities
 *
 * Node 18+ | CommonJS | Express 4
 * NEVER crashes — every route is guarded, every module has fallbacks.
 *
 * Routes:
 *   GET  /health
 *   GET  /leads
 *   POST /outreach
 *   GET  /signals
 *   GET  /api/grants
 *   GET  /trends
 */

'use strict';

const express = require('express');

const leadAgent        = require('./leadAgent');
const outreachAgent    = require('./outreachAgent');
const marketSignalAgent= require('./marketSignalAgent');
const grantSearch      = require('./grantSearch');
const trendScanner     = require('./trendScanner');
const opportunityAgent = require('./opportunityAgent');
const offerGenerator   = require('./offerGenerator');
const performanceAgent = require('./performanceAgent');
const strategyAgent    = require('./strategyAgent');
const revenueExpander  = require('./revenueExpander');

const app   = express();
const PORT  = process.env.PORT || 4000;

app.use(express.json({ limit: '32kb' }));

// ── CORS (open — restrict in production via ALLOWED_ORIGINS) ─────────────────
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin',  '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// ── Utility: safe async route wrapper ────────────────────────────────────────
function safe(fn) {
  return async (req, res) => {
    try {
      await fn(req, res);
    } catch (err) {
      console.error('[Server] Unhandled route error:', err.message);
      res.status(500).json({ success: false, error: 'Internal server error', data: [] });
    }
  };
}

// ── GET /health ───────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({
    status:  'ok',
    service: 'revenue-engine',
    port:    PORT,
    apiKey:  process.env.ANTHROPIC_API_KEY ? 'SET ✓' : 'NOT SET (fallback mode)',
    modules: [
      'leadAgent','outreachAgent','marketSignalAgent','grantSearch',
      'trendScanner','opportunityAgent','offerGenerator',
      'performanceAgent','strategyAgent','revenueExpander',
    ],
    routes:  ['GET /health','GET /leads','POST /outreach',
              'GET /signals','GET /api/grants','GET /trends'],
  });
});

// ── GET /leads ────────────────────────────────────────────────────────────────
app.get('/leads', safe(async (req, res) => {
  const niche = (req.query.niche || 'hoa').toLowerCase();
  const count = Math.min(parseInt(req.query.count) || 10, 50);
  const leads = await leadAgent.generateLeads({ niche, count });
  res.json({ success: true, count: leads.length, niche, leads });
}));

// ── POST /outreach ────────────────────────────────────────────────────────────
app.post('/outreach', safe(async (req, res) => {
  const {
    company   = 'Prospect Company',
    contact   = '',
    niche     = 'hoa',
    stage     = 'cold',          // cold | warm | demo | close
    context   = '',
  } = req.body;

  const [message, script, offer] = await Promise.all([
    outreachAgent.generateOutreach({ company, contact, niche, stage, context }),
    stage === 'demo'  ? require('./demoAgent').generateDemoScript({ company, niche })  : Promise.resolve(null),
    stage === 'close' ? require('./closeAgent').generateClose({ company, niche })       : Promise.resolve(null),
  ]);

  res.json({
    success: true,
    stage,
    niche,
    company,
    message,
    demoScript:   script  || undefined,
    closeMessage: offer   || undefined,
  });
}));

// ── GET /signals ──────────────────────────────────────────────────────────────
app.get('/signals', safe(async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 20, 50);
  const signals = await marketSignalAgent.getSignals({ limit });
  res.json({ success: true, count: signals.length, generatedAt: new Date().toISOString(), signals });
}));

// ── GET /api/grants ───────────────────────────────────────────────────────────
app.get('/api/grants', safe(async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 20, 50);
  const grants = await grantSearch.searchGrants({
    claudeKey: process.env.ANTHROPIC_API_KEY,
    limit,
  });
  res.json({ success: true, count: grants.length, grants });
}));

// ── GET /trends ───────────────────────────────────────────────────────────────
app.get('/trends', safe(async (req, res) => {
  const [trends, opportunities, offers, expansion] = await Promise.all([
    trendScanner.scanTrends(),
    opportunityAgent.findOpportunities(),
    offerGenerator.generateOffers(),
    revenueExpander.expandRevenue(),
  ]);

  res.json({
    success: true,
    generatedAt: new Date().toISOString(),
    trends,
    opportunities,
    offers,
    expansion,
  });
}));

// ── GET /performance ──────────────────────────────────────────────────────────
app.get('/performance', safe(async (req, res) => {
  const [perf, strategy] = await Promise.all([
    performanceAgent.getMetrics(),
    strategyAgent.getStrategy(),
  ]);
  res.json({ success: true, performance: perf, strategy });
}));

// ── Global error handler ──────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error('[Server] Uncaught middleware error:', err.message);
  res.status(500).json({ success: false, error: 'Server error' });
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n[Revenue Engine] http://localhost:${PORT}`);
  console.log(`[Revenue Engine] Claude: ${process.env.ANTHROPIC_API_KEY ? 'ACTIVE' : 'FALLBACK MODE'}`);
  console.log(`[Revenue Engine] Routes: /health /leads /outreach /signals /api/grants /trends /performance\n`);
});
