/**
 * outreachEngine.js — Gray Horizons Enterprise
 * Production-ready SendGrid outreach engine.
 * Throttled · Retrying · Follow-up aware · Fully logged
 */

'use strict';

const sgMail = require('@sendgrid/mail');

sgMail.setApiKey(process.env.SENDGRID_API_KEY);

// ── Config ────────────────────────────────────────────────────────────────────

const CONFIG = {
  DAILY_LIMIT:              150,
  DELAY_BETWEEN_EMAILS_MS:  20000,   // 20 s between sends — safe for inbox delivery
  MAX_RETRIES:              2,
  FOLLOW_UP_DELAY_HOURS:    48,
  FROM:                     'grayhorizonsenterprise@gmail.com',  // HARD SET — DO NOT CHANGE
};

// ── State (in-memory, resets on redeploy) ─────────────────────────────────────

let dailySentCount  = 0;
let dailyResetDate  = _todayStr();
const sendLog       = [];   // full history this session

function _todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function _checkDailyReset() {
  const today = _todayStr();
  if (today !== dailyResetDate) {
    console.log(`[Outreach] New day (${today}) — resetting daily counter`);
    dailySentCount = 0;
    dailyResetDate = today;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function _log(entry) {
  const record = { ...entry, ts: new Date().toISOString() };
  sendLog.push(record);
  // Keep last 500 records in memory
  if (sendLog.length > 500) sendLog.shift();
  return record;
}

// ── Core send (with retry) ────────────────────────────────────────────────────

async function sendEmailSafe({ to, subject, text }, attempt = 0) {
  const msg = {
    to,
    from:    CONFIG.FROM,
    subject,
    text,
  };

  console.log(`[Outreach] Sending -> ${to} (attempt ${attempt + 1})`);
  console.log(`[Outreach] FROM: ${msg.from}`);

  try {
    await sgMail.send(msg);
    console.log(`[Outreach] SENT -> ${to}`);
    _log({ to, subject, success: true, attempt });
    return { success: true };

  } catch (err) {
    const detail = err.response
      ? JSON.stringify(err.response.body)
      : err.message;
    console.error(`[Outreach] FAILED -> ${to} | ${detail}`);

    if (attempt < CONFIG.MAX_RETRIES) {
      const backoff = 5000 * (attempt + 1);  // 5 s, 10 s
      console.log(`[Outreach] Retrying ${to} in ${backoff / 1000}s...`);
      await delay(backoff);
      return sendEmailSafe({ to, subject, text }, attempt + 1);
    }

    _log({ to, subject, success: false, attempt, error: detail });
    return { success: false, error: detail };
  }
}

// ── Batch send (throttled, daily-limited) ─────────────────────────────────────

async function sendBatchSafe(leads) {
  _checkDailyReset();

  const results   = [];
  const remaining = CONFIG.DAILY_LIMIT - dailySentCount;

  if (remaining <= 0) {
    console.log('[Outreach] Daily limit already reached — no emails sent');
    return { sent: 0, failed: 0, skipped: leads.length, results };
  }

  const batch = leads.slice(0, remaining);
  console.log(`[Outreach] Starting batch: ${batch.length} emails (${leads.length - batch.length} deferred to tomorrow)`);

  for (let i = 0; i < batch.length; i++) {
    // If lead has no text, generate a human-sounding email automatically
    const lead   = (batch[i].text || batch[i].subject)
      ? batch[i]
      : { ...generateHumanEmail(batch[i]), ...batch[i] };
    const result = await sendEmailSafe(lead);
    results.push({ ...lead, ...result });

    if (result.success) dailySentCount++;

    if (i < batch.length - 1) {
      console.log(`[Outreach] Waiting ${CONFIG.DELAY_BETWEEN_EMAILS_MS / 1000}s before next send...`);
      await delay(CONFIG.DELAY_BETWEEN_EMAILS_MS);
    }
  }

  const sent   = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  console.log(`[Outreach] Batch complete — ${sent} sent, ${failed} failed | Daily total: ${dailySentCount}/${CONFIG.DAILY_LIMIT}`);

  return { sent, failed, skipped: leads.length - batch.length, results };
}

// ── Human email generator ─────────────────────────────────────────────────────
// Sounds like a real person typing fast — no templates, no corp-speak.

const OPENERS = [
  'Hey — quick question',
  'Quick one for you',
  'Not sure if this is relevant, but figured I\'d ask',
  'Wanted to run something by you real quick',
  'Random question — feel free to ignore if not relevant',
];

const PROBLEMS = [
  'when a homeowner submits a complaint or violation, how are you tracking it from start to finish?',
  'are you still managing violations through email threads or do you have something more structured?',
  'curious how your team keeps everything organized once a violation gets reported — is there a system, or is it still pretty manual?',
  'when something gets reported by a resident, what does the follow-through process look like on your end?',
  'how are you handling the gap between when something gets flagged and when it actually gets resolved?',
];

const CLOSERS = [
  'Happy to share what we\'ve been seeing if it helps.',
  'Can show you what we put together if you\'re curious.',
  'No pitch — just comparing notes.',
  'Let me know if that\'s even something you\'re dealing with.',
  'Worth a quick chat if any of this sounds familiar.',
];

function _pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function generateHumanEmail(lead) {
  const opener  = _pick(OPENERS);
  const problem = _pick(PROBLEMS);
  const closer  = _pick(CLOSERS);

  return {
    to:      lead.to || lead.email,
    subject: 'Quick question',
    text:
`${opener},

${problem}

We've been working with a few HOA teams and noticed things tend to fall apart between the report and resolution.

${closer}

— Alex`,
  };
}

// ── Follow-up generator ───────────────────────────────────────────────────────

const FOLLOWUP_OPENERS = [
  'Hey — just wanted to bump this up in case it got buried.',
  'Circling back on this real quick.',
  'Didn\'t hear back — totally fine if timing\'s off.',
  'Following up — no pressure at all.',
];

const FOLLOWUP_CLOSERS = [
  'Still happy to share what we\'ve been seeing.',
  'Let me know either way.',
  'Even a quick no works — just want to make sure this landed.',
  'Happy to keep it short if you want to connect.',
];

function generateFollowUp(original) {
  return {
    to:      original.to,
    subject: 'Quick follow-up',
    text:
`${_pick(FOLLOWUP_OPENERS)}

${_pick(FOLLOWUP_CLOSERS)}

— Alex`,
  };
}

// ── Follow-up runner (fires after FOLLOW_UP_DELAY_HOURS) ─────────────────────
// NOTE: schedules in-process — survives as long as the server stays up.
// For persistent follow-ups across redeploys, use a queue or cron job.

function scheduleFollowUps(sentLeads) {
  const delayMs = CONFIG.FOLLOW_UP_DELAY_HOURS * 60 * 60 * 1000;
  console.log(`[Outreach] Scheduling ${sentLeads.length} follow-ups in ${CONFIG.FOLLOW_UP_DELAY_HOURS}h`);

  setTimeout(async () => {
    console.log(`[Outreach] Running ${sentLeads.length} follow-ups...`);
    const followUps = sentLeads.map(generateFollowUp);
    await sendBatchSafe(followUps);
  }, delayMs);
}

// ── Status ────────────────────────────────────────────────────────────────────

function getStatus() {
  _checkDailyReset();
  return {
    dailySent:   dailySentCount,
    dailyLimit:  CONFIG.DAILY_LIMIT,
    remaining:   CONFIG.DAILY_LIMIT - dailySentCount,
    resetDate:   dailyResetDate,
    logEntries:  sendLog.length,
    recentLog:   sendLog.slice(-10),
  };
}

module.exports = { sendEmailSafe, sendBatchSafe, scheduleFollowUps, generateHumanEmail, getStatus, CONFIG };
