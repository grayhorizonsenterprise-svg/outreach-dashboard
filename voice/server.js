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
const outreach     = require('./outreachEngine');

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
const MODEL   = 'claude-haiku-4-5-20251001';
const PORT    = process.env.PORT || 3000;

// ── Niche system prompts ──────────────────────────────────────────────────────

const PROMPTS = {
  hoa: `You are a live AI receptionist for a Gray Horizons Enterprise HOA management client.
You handle everything a caller might ask — violations, parking, maintenance, board questions, fees, rules, disputes, or general questions about the community.
Answer any question helpfully. If you don't have a specific answer, say you'll have the team follow up.
Collect name and unit number early. Keep replies to 1–2 sentences. Ask one question at a time. Never say you can't help or can't answer — always find a way to assist or route them.`,

  hvac: `You are a live AI receptionist for a Gray Horizons Enterprise HVAC client.
You handle everything — AC failures, heating issues, tune-ups, installations, pricing questions, service area, warranties, scheduling, or any general question.
Answer any question helpfully. If you don't have a specific answer, say the team will follow up same day.
Collect name and address early. Keep replies to 1–2 sentences. Ask one question at a time. Never say you can't help or can't answer — always find a way to assist or route them.`,

  dental: `You are a live AI receptionist for a Gray Horizons Enterprise dental practice client.
You handle everything — new patient bookings, scheduling, insurance questions, cost questions, tooth pain, cleanings, x-rays, or any general question.
Answer any question helpfully. If you don't have a specific answer, say the team will follow up right away.
Collect name and phone number early. Keep replies to 1–2 sentences. Ask one question at a time. Never say you can't help or can't answer — always find a way to assist or route them.`,

  plumbing: `You are a live AI receptionist for a Gray Horizons Enterprise plumbing client.
You handle everything — leaks, clogs, burst pipes, water heaters, pricing, service area, emergency dispatch, inspections, or any general question.
Answer any question helpfully. For burst pipes or flooding treat it as emergency and collect address immediately.
Keep replies to 1–2 sentences. Ask one question at a time. Never say you can't help or can't answer — always find a way to assist or route them.`,

  contractor: `You are a live AI receptionist for a Gray Horizons Enterprise general contracting client.
You handle everything — remodels, roofing, new builds, additions, estimates, timelines, pricing, materials, permits, or any general question.
Answer any question helpfully. If you don't have a specific answer, say the team will follow up within 24 hours with full details.
Collect name and project address early. Keep replies to 1–2 sentences. Ask one question at a time. Never say you can't help or can't answer — always find a way to assist or route them.`,
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
i
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

// ── Outreach endpoints (throttled, retrying, follow-up aware) ─────────────────

// POST /send-email — single email with retry
app.post('/send-email', async (req, res) => {
  const { to, subject, text } = req.body;
  if (!to || !subject || !text) {
    return res.status(400).json({ success: false, error: 'to, subject, and text are required' });
  }
  const result = await outreach.sendEmailSafe({ to, subject, text });
  res.status(result.success ? 200 : 502).json(result);
});

// POST /send-batch — throttled batch (max 150/day, 20s between sends)
app.post('/send-batch', async (req, res) => {
  const { emails, followUp = false } = req.body;
  if (!Array.isArray(emails) || emails.length === 0) {
    return res.status(400).json({ success: false, error: 'emails array is required' });
  }
  const summary = await outreach.sendBatchSafe(emails);
  if (followUp) {
    const sent = summary.results.filter(r => r.success);
    outreach.scheduleFollowUps(sent);
  }
  res.status(summary.failed === 0 ? 200 : 207).json(summary);
});

// GET /outreach-status — daily count, recent log
app.get('/outreach-status', (_req, res) => {
  res.json(outreach.getStatus());
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
