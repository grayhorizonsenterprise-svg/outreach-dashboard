/**
 * Minimal fail-safe Claude test server
 * Run: node test-server.js
 * Test: GET /health  |  GET /test-claude
 */
const express = require('express');
const app = express();

app.use(express.json());

const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL   = 'claude-3-haiku-20240307';
const PORT    = process.env.PORT || 4000;

// ── /health — always works ────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  console.log('[Health] OK');
  res.send('OK');
});

// ── /test-claude — safe Claude call ──────────────────────────────────────────
app.get('/test-claude', async (_req, res) => {
  console.log('[Test] Calling Claude...');

  if (!API_KEY) {
    console.error('[Test] No API key set');
    return res.json({ success: false, error: 'ANTHROPIC_API_KEY not set' });
  }

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method:  'POST',
      headers: {
        'x-api-key':         API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type':      'application/json',
      },
      body: JSON.stringify({
        model:      MODEL,
        max_tokens: 50,
        messages:   [{ role: 'user', content: 'Say hello in one short sentence.' }],
      }),
      signal: AbortSignal.timeout(12000),
    });

    if (!response.ok) {
      const txt = await response.text();
      console.error('[Test] Claude HTTP error:', response.status, txt);
      return res.json({ success: false, error: `HTTP ${response.status}: ${txt}` });
    }

    const data  = await response.json();
    const reply = data.content?.[0]?.text?.trim() || '(empty response)';
    console.log('[Test] Claude replied:', reply);
    res.json({ success: true, reply, model: MODEL });

  } catch (err) {
    // Never crash — always return JSON
    console.error('[Test] Claude failed:', err.message);
    res.json({ success: false, error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`\n[Test Server] http://localhost:${PORT}`);
  console.log(`[Test Server] API key: ${API_KEY ? 'SET ✓' : 'NOT SET ✗'}`);
  console.log(`[Test Server] Routes: GET /health | GET /test-claude\n`);
});
