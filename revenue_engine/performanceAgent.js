/**
 * performanceAgent.js — Gray Horizons Enterprise Revenue Engine
 * Tracks and reports KPIs across all revenue streams.
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// Paths to source data files (relative to repo root, not this module)
const DATA_ROOT = path.resolve(__dirname, '..');

function safeReadCSV(filePath) {
  try {
    if (!fs.existsSync(filePath)) return [];
    const lines = fs.readFileSync(filePath, 'utf8').trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
    return lines.slice(1).map(line => {
      const vals = line.match(/(".*?"|[^,]+)(?=,|$)/g) || [];
      const obj  = {};
      headers.forEach((h, i) => { obj[h] = (vals[i] || '').replace(/"/g, '').trim(); });
      return obj;
    });
  } catch {
    return [];
  }
}

function getOutreachMetrics() {
  try {
    const queue   = safeReadCSV(path.join(DATA_ROOT, 'outreach_queue.csv'));
    const sentLog = safeReadCSV(path.join(DATA_ROOT, 'sent_log.csv'));

    const totalInQueue = queue.length;
    const pending      = queue.filter(r => r.status === 'pending').length;
    const sent         = queue.filter(r => r.status === 'sent').length;
    const skipped      = queue.filter(r => r.status === 'skipped').length;

    const deliveredOk  = sentLog.filter(r => {
      const v = String(r.success || '').toLowerCase();
      return v === 'true' || v === '1' || v === 'smtp' || v === 'sendgrid';
    }).length;
    const failed = sentLog.filter(r => {
      const v = String(r.success || '').toLowerCase();
      return v === 'false' || v === '0';
    }).length;

    return {
      totalInQueue,
      pending,
      sent,
      skipped,
      deliveredOk,
      failed,
      deliveryRate: sentLog.length > 0 ? Math.round((deliveredOk / sentLog.length) * 100) : 0,
    };
  } catch {
    return { totalInQueue: 0, pending: 0, sent: 0, skipped: 0, deliveredOk: 0, failed: 0, deliveryRate: 0 };
  }
}

async function getMetrics() {
  try {
    const outreach = getOutreachMetrics();

    return {
      generatedAt: new Date().toISOString(),
      outreach,
      pipeline: {
        estimatedMRR:       outreach.sent * 397,
        estimatedARR:       outreach.sent * 397 * 12,
        conversionTarget:   '10% of sent → demo booked',
        demoTarget:         '40% of demos → close',
        projectedMonthlyCloses: Math.max(1, Math.floor(outreach.sent * 0.1 * 0.4)),
      },
      health: {
        outreachDeliveryRate: `${outreach.deliveryRate}%`,
        status: outreach.failed > 0 ? 'WARNING: failed sends detected — check /debug on dashboard' : 'OK',
        alerts: outreach.failed > 0
          ? [`${outreach.failed} email(s) failed to deliver. Verify SENDGRID_API_KEY or SENDER_APP_PASSWORD on Railway.`]
          : [],
      },
    };
  } catch (err) {
    console.error('[performanceAgent] Error:', err.message);
    return {
      generatedAt: new Date().toISOString(),
      outreach:    { totalInQueue: 0, pending: 0, sent: 0, skipped: 0, deliveredOk: 0, failed: 0, deliveryRate: 0 },
      pipeline:    { estimatedMRR: 0, estimatedARR: 0 },
      health:      { status: 'UNKNOWN', alerts: ['Could not read data files'] },
    };
  }
}

module.exports = { getMetrics };
