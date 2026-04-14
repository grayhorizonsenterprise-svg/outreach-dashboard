/**
 * Gray Horizons Enterprise — AI Voice Receptionist Server
 * Multi-niche: HOA | HVAC | Dental | Plumbing | Contractor
 * Node 18+ | Native fetch | CommonJS
 */
const express = require('express');
const cors    = require('cors');

const app = express();

// Allow requests from any origin (grayhorizonsenterprise.com, Railway, local dev)
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '')
  .split(',').map(s => s.trim()).filter(Boolean);

app.use(cors({
  origin: function(origin, cb) {
    // Allow no-origin (curl, Postman, same-origin) + configured domains
    if (!origin) return cb(null, true);
    if (ALLOWED_ORIGINS.length === 0) return cb(null, true); // dev: open
    if (ALLOWED_ORIGINS.some(o => origin.startsWith(o))) return cb(null, true);
    cb(new Error('CORS: origin not allowed — ' + origin));
  },
  methods: ['GET','POST','OPTIONS'],
  allowedHeaders: ['Content-Type'],
}));

app.use(express.json({ limit: '16kb' }));

const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL   = 'claude-haiku-4-5-20251001';
const PORT    = process.env.PORT || 3000;

// ── Niche system prompts ──────────────────────────────────────────────────────

const PROMPTS = {
  hoa: `You are a live HOA receptionist for Gray Horizons Enterprise in Rialto, CA.
Handle: violation notices, disputes, parking complaints, board inquiries, maintenance requests.
Collect: resident name, unit number, issue description.
Rules: 1–2 sentences max. Ask ONE question at a time. Stay calm and professional. Never escalate emotionally.
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

function getPrompt(niche) {
  return PROMPTS[niche] || PROMPTS.hoa;
}

// ── Session store ─────────────────────────────────────────────────────────────
// Key: sessionId  Value: { messages: [], lastActive: timestamp }

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

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', model: MODEL, port: PORT, niches: Object.keys(PROMPTS) });
});

// ── POST /voice ───────────────────────────────────────────────────────────────
app.post('/voice', async (req, res) => {
  const { message, sessionId = 'default', niche = 'hoa' } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required' });
  }
  if (!API_KEY) {
    return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set on server' });
  }

  const session = getSession(sessionId);
  session.messages.push({ role: 'user', content: message.trim().slice(0, 1000) });

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key':         API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type':      'application/json',
      },
      body: JSON.stringify({
        model:      MODEL,
        max_tokens: 200,
        system:     getPrompt(niche),
        messages:   session.messages,
      }),
      signal: AbortSignal.timeout(15000),
    });

    if (!response.ok) {
      const txt = await response.text();
      console.error('[Voice] Anthropic error:', response.status, txt);
      return res.status(502).json({ error: 'AI API error', status: response.status });
    }

    const data  = await response.json();
    const reply = data.content?.[0]?.text?.trim() || "Sorry, could you repeat that?";

    session.messages.push({ role: 'assistant', content: reply });

    // Cap at 40 turns
    if (session.messages.length > 80) sessions.delete(sessionId);

    res.json({ reply, turns: Math.floor(session.messages.length / 2), niche });

  } catch (err) {
    console.error('[Voice] Error:', err.message);
    res.status(500).json({ error: 'Server error — try again' });
  }
});

// ── POST /reset ───────────────────────────────────────────────────────────────
app.post('/reset', (req, res) => {
  const { sessionId = 'default' } = req.body;
  sessions.delete(sessionId);
  res.json({ status: 'reset', sessionId });
});

// ── Static files (serves index.html, etc.) ────────────────────────────────────
app.use(express.static(__dirname));

// ── Root ──────────────────────────────────────────────────────────────────────
app.get("/", (_req, res) => {
  res.send("AI Voice Server is running 🚀");
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n[Voice Server] http://localhost:${PORT}`);
  console.log(`[Voice Server] API key: ${API_KEY ? 'SET ✓' : 'NOT SET ✗'}`);
  console.log(`[Voice Server] Niches: ${Object.keys(PROMPTS).join(', ')}\n`);
});
