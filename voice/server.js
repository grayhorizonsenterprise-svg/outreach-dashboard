/**
 * Gray Horizons Enterprise — AI Voice Receptionist Server
 * Multi-niche: HOA | HVAC | Dental | Plumbing | Contractor
 * Node 18+ | Native fetch | CommonJS
 *
 * SAFE BUILD — Claude failures never crash the server.
 * Flow: retryClaude (2 attempts) → callClaudeSafe → fallback reply
 */
const express      = require('express');
const cors         = require('cors');
const sgMail       = require('@sendgrid/mail');
const { searchGrants } = require('./grantSearch');

// ── SendGrid setup ────────────────────────────────────────────────────────────
const SENDGRID_KEY = process.env.SENDGRID_API_KEY || '';
sgMail.setApiKey(process.env.SENDGRID_API_KEY);

const app = express();

const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '')
  .split(',').map(s => s.trim()).filter(Boolean);

app.use(cors({
  origin: function(origin, cb) {
    if (!origin) return cb(null, true);
    if (ALLOWED_ORIGINS.length === 0) return cb(null, true);
    if (ALLOWED_ORIGINS.some(o => origin.startsWith(o))) return cb(null, true);
    cb(new Error('CORS: origin not allowed — ' + origin));
  },
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type'],
}));

app.use(express.json({ limit: '16kb' }));

const API_KEY = process.env.ANTHROPIC_API_KEY;
// ✅ FIXED: use stable model — haiku-4-5 was causing 500s
const MODEL   = 'claude-3-haiku-20240307';
const PORT    = process.env.PORT || 3000;

// ── Niche system prompts ──────────────────────────────────────────────────────

const PROMPTS = {
  hoa: `You are a live HOA receptionist for Gray Horizons Enterprise in Rialto, CA.
Handle: violation notices, disputes, parking complaints, board inquiries, maintenance requests.
Collect: resident name, unit number, issue description.
Rules: 1–2 sentences max. Ask ONE question at a time. Stay calm and professional.
If they need to file a violation, say you'll log it immediately and they'll get a confirmation.`,

  hvac: `You are a live HVAC receptionist for Gray Horizons Enterprise.
Handle: AC/heat failures, emergency repairs, tune-ups, installations, maintenance.
Collect: customer name, property address, issue description, urgency (emergency vs scheduled).
Rules: 1–2 sentences max. Ask ONE question at a time. Be efficient and direct.
For emergencies say a tech can be dispatched within the hour — confirm address first.`,

  dental: `You are a live dental receptionist for Gray Horizons Enterprise.
Handle: new patient bookings, appointment scheduling, insurance questions, emergency tooth pain.
Collect: patient name, phone number, preferred appointment time, reason for visit.
Rules: 1–2 sentences max. Ask ONE question at a time. Be warm and reassuring.
For pain emergencies, say you'll find the earliest available slot today or tomorrow.`,

  plumbing: `You are a live plumbing receptionist for Gray Horizons Enterprise.
Handle: leaks, burst pipes, drain clogs, water heater issues, emergency repairs, inspections.
Collect: customer name, property address, issue description, urgency level.
Rules: 1–2 sentences max. Ask ONE question at a time. Be calm and action-oriented.
For burst pipes or flooding, treat as emergency — confirm address and dispatch immediately.`,

  contractor: `You are a live project intake receptionist for Gray Horizons Enterprise, a Black-owned general contracting firm in Rialto, CA.
Handle: kitchen/bathroom remodels, roofing, new builds, additions, emergency repairs, project estimates.
Collect: client name, project address, project type, scope of work, timeline.
Rules: 1–2 sentences max. Ask ONE question at a time. Be professional and enthusiastic.
For estimates say the team will follow up within 24 hours with a full quote.`,
};

// Scripted fallbacks — used when Claude is unavailable so callers always get a response
const FALLBACKS = {
  hoa:        "Thanks for reaching out to Gray Horizons HOA. Please share your name, unit number, and issue and we'll follow up right away.",
  hvac:       "Thanks for calling Gray Horizons HVAC. Can you give me your name and address so I can get a tech scheduled for you?",
  dental:     "Thanks for calling Gray Horizons Dental. Can I get your name and the reason for your visit so we can get you booked?",
  plumbing:   "Thanks for calling Gray Horizons Plumbing. Please give me your name and address and we'll get someone out ASAP.",
  contractor: "Thanks for reaching out to Gray Horizons General Contracting. Can you tell me your name and what type of project you need?",
};

function getPrompt(niche)    { return PROMPTS[niche]   || PROMPTS.hoa;   }
function getFallback(niche)  { return FALLBACKS[niche] || FALLBACKS.hoa; }

// ── Session store ─────────────────────────────────────────────────────────────

const sessions = new Map();

function getSession(id) {
  if (!sessions.has(id)) sessions.set(id, { messages: [], lastActive: Date.now() });
  const s = sessions.get(id);
  s.lastActive = Date.now();
  return s;
}

// Auto-purge sessions idle > 30 min
setInterval(() => {
  const cutoff = Date.now() - 30 * 60 * 1000;
  sessions.forEach((s, id) => { if (s.lastActive < cutoff) sessions.delete(id); });
}, 5 * 60 * 1000);

// ── STEP 1: retryClaude — 2 attempts before giving up ────────────────────────

async function retryClaude(body, retries = 2) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key':         API_KEY,
          'anthropic-version': '2023-06-01',
          'content-type':      'application/json',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      });

      if (!response.ok) {
        const txt = await response.text();
        console.error(`[Claude] Attempt ${i + 1} HTTP ${response.status}:`, txt);
        // Don't retry on auth errors — they won't self-heal
        if (response.status === 401 || response.status === 403) return null;
        continue;
      }

      const data = await response.json();
      console.log(`[Claude] OK on attempt ${i + 1}`);
      return data;

    } catch (err) {
      console.error(`[Claude] Attempt ${i + 1} error:`, err.message);
      if (i < retries - 1) {
        console.log('[Claude] Retrying...');
        await new Promise(r => setTimeout(r, 800)); // brief pause before retry
      }
    }
  }
  return null; // all attempts failed
}

// ── STEP 2: callClaudeSafe — wraps retry, never throws ───────────────────────

async function callClaudeSafe(body) {
  try {
    const result = await retryClaude(body);
    if (!result) {
      console.log('[Claude] All retries failed — returning null for fallback');
      return null;
    }
    return result;
  } catch (err) {
    console.error('[Claude] callClaudeSafe crash (should not happen):', err.message);
    return null;
  }
}

// ── Email via SendGrid ────────────────────────────────────────────────────────

async function sendEmail(email, subject, body) {
  try {
    const msg = {
      to: email,
      from: 'grayhorizonsenterprise@gmail.com', // HARD SET - DO NOT CHANGE
      subject: subject,
      text: body,
    };

    console.log('SENDING FROM:', msg.from);

    await sgMail.send(msg);

    console.log(`SENT -> ${email}`);
    return true;

  } catch (err) {
    console.error(`FAILED -> ${email}`);
    console.error(err.response?.body || err.message);
    return false;
  }
}

async function sendBatch(emails) {
  const results = [];
  for (const e of emails) {
    const ok = await sendEmail(e.to, e.subject, e.text || e.body || '');
    results.push({ to: e.to, success: ok });
  }
  const sent   = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  console.log(`Batch done — ${sent} sent, ${failed} failed`);
  return results;
}

// POST /send-email  — single email
app.post('/send-email', async (req, res) => {
  const { to, subject, text, body } = req.body;
  if (!to || !subject || (!text && !body)) {
    return res.status(400).json({ success: false, error: 'to, subject, and text are required' });
  }
  const ok = await sendEmail(to, subject, text || body);
  res.status(ok ? 200 : 502).json({ success: ok });
});

// POST /send-batch  — array of { to, subject, text }
app.post('/send-batch', async (req, res) => {
  const { emails } = req.body;
  if (!Array.isArray(emails) || emails.length === 0) {
    return res.status(400).json({ success: false, error: 'emails array is required' });
  }
  const results = await sendBatch(emails);
  const allOk   = results.every(r => r.success);
  res.status(allOk ? 200 : 207).json({ results });
});

// ── Health — ALWAYS works regardless of Claude state ─────────────────────────

app.get('/health', (_req, res) => {
  res.json({
    status:      'ok',
    model:       MODEL,
    port:        PORT,
    claudeKey:   API_KEY      ? 'SET ✓' : 'NOT SET ✗',
    sendgridKey: SENDGRID_KEY ? 'SET ✓' : 'NOT SET ✗',
    niches:      Object.keys(PROMPTS),
  });
});

// ── GET /test-claude — quick smoke test ──────────────────────────────────────

app.get('/test-claude', async (_req, res) => {
  if (!API_KEY) {
    return res.json({ success: false, error: 'ANTHROPIC_API_KEY not set' });
  }

  const data = await callClaudeSafe({
    model:      MODEL,
    max_tokens: 50,
    messages:   [{ role: 'user', content: 'Say hello in one sentence.' }],
  });

  if (!data) {
    return res.json({ success: false, error: 'Claude did not respond after retries' });
  }

  res.json({
    success: true,
    reply:   data.content?.[0]?.text?.trim() || '(empty)',
    model:   MODEL,
  });
});

// ── POST /voice ───────────────────────────────────────────────────────────────

app.post('/voice', async (req, res) => {
  const { message, sessionId = 'default', niche = 'hoa' } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required' });
  }

  const session = getSession(sessionId);
  session.messages.push({ role: 'user', content: message.trim().slice(0, 1000) });

  // ── STEP 3: updated flow — Claude optional, fallback guaranteed ──
  let reply;

  if (!API_KEY) {
    console.log('[Voice] No API key — using scripted fallback');
    reply = getFallback(niche);
  } else {
    const data = await callClaudeSafe({
      model:      MODEL,
      max_tokens: 200,
      system:     getPrompt(niche),
      messages:   session.messages,
    });

    if (!data) {
      // Claude unavailable — use scripted fallback, server still responds 200
      console.log('[Voice] Claude unavailable — using scripted fallback');
      reply = getFallback(niche);
    } else {
      reply = data.content?.[0]?.text?.trim() || getFallback(niche);
    }
  }

  session.messages.push({ role: 'assistant', content: reply });

  // Cap at 40 turns (80 message objects)
  if (session.messages.length > 80) sessions.delete(sessionId);

  res.json({ reply, turns: Math.floor(session.messages.length / 2), niche });
});

// ── GET /api/grants ───────────────────────────────────────────────────────────

app.get('/api/grants', async (_req, res) => {
  try {
    const grants = await searchGrants({ claudeKey: API_KEY, limit: 20 });
    res.json({ success: true, count: grants.length, grants });
  } catch (err) {
    console.error('[/api/grants] Error:', err.message);
    res.status(500).json({ success: false, error: 'Grant fetch failed', grants: [] });
  }
});

// ── POST /reset ───────────────────────────────────────────────────────────────

app.post('/reset', (req, res) => {
  const { sessionId = 'default' } = req.body;
  sessions.delete(sessionId);
  res.json({ status: 'reset', sessionId });
});

// ── Static + root ─────────────────────────────────────────────────────────────

app.use(express.static(__dirname));

app.get('/', (_req, res) => {
  res.send('Gray Horizons AI Voice Server — running ✓');
});

// ── Global error guard — catches any unhandled synchronous throws ─────────────

app.use((err, _req, res, _next) => {
  console.error('[Server] Unhandled error:', err.message);
  res.status(500).json({ error: 'Server error — please try again' });
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`\n[Voice Server] http://localhost:${PORT}`);
  console.log(`[Voice Server] Model:      ${MODEL}`);
  console.log(`[Voice Server] Claude key: ${API_KEY    ? 'SET ✓' : 'NOT SET ✗ (fallback mode active)'}`);
  console.log(`SENDGRID KEY:              ${SENDGRID_KEY ? 'Loaded ✓' : 'Missing ✗'}`);
  console.log(`[Voice Server] Niches:     ${Object.keys(PROMPTS).join(', ')}`);
  console.log(`[Voice Server] Test:       http://localhost:${PORT}/test-claude\n`);
});
