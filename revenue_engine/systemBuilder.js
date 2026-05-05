/**
 * systemBuilder.js — Gray Horizons Enterprise Revenue Engine
 * Generates system architecture and automation blueprints per niche.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

const SYSTEM_BLUEPRINTS = {
  hoa: {
    systemName:  'HOA Compliance & Communication Platform',
    components: [
      { name: 'Violation Intake Form',         type: 'Frontend',    status: 'live',    description: 'Homeowner-facing submission portal. Captures: type, unit, photos, description.' },
      { name: 'Board Notification Engine',     type: 'Automation',  status: 'live',    description: 'Auto-sends email to board members on new violation. Configurable per HOA.' },
      { name: 'Status Dashboard',              type: 'Frontend',    status: 'live',    description: 'Single-view across all communities. Status, age, owner, deadline.' },
      { name: 'Audit Trail Logger',            type: 'Backend',     status: 'live',    description: 'Every action timestamped and logged. Exportable for legal/board review.' },
      { name: 'Outreach + Follow-Up Engine',   type: 'Automation',  status: 'live',    description: 'Automated follow-up to unresolved violations at 7, 14, 30 days.' },
      { name: 'Resident Communication Portal', type: 'Frontend',    status: 'planned', description: 'Self-service portal for residents to track their own violations.' },
    ],
    integrations: ['Email (Gmail/SendGrid)', 'CSV export', 'Google Sheets sync (planned)'],
    deliveryTime: '3 business days to fully live',
    techStack:    'Python + Flask dashboard, CSV/SQLite data store, SendGrid/SMTP delivery',
  },
  hvac: {
    systemName:  'HVAC AI Receptionist & Dispatch System',
    components: [
      { name: 'AI Voice Receptionist',         type: 'AI',          status: 'live',    description: '24/7 call handling. Collects: caller name, address, issue, urgency. Uses Claude.' },
      { name: 'Emergency Dispatch Router',     type: 'Automation',  status: 'live',    description: 'Detects emergency keywords → fires SMS to on-call tech immediately.' },
      { name: 'Appointment Scheduler',         type: 'Backend',     status: 'live',    description: 'Confirms scheduling based on availability rules. Sends confirmation to caller.' },
      { name: 'Follow-Up Sequence',            type: 'Automation',  status: 'planned', description: 'Post-service follow-up at 24h, 7 days, 30 days for reviews and re-booking.' },
      { name: 'Call Capture Report',           type: 'Reporting',   status: 'planned', description: 'Monthly summary: calls handled, dispatched, missed, revenue estimate.' },
    ],
    integrations: ['Twilio (SMS dispatch)', 'Calendar API', 'Email notifications'],
    deliveryTime: 'Same-day activation',
    techStack:    'Node.js + Express, Claude API (Haiku), Twilio for SMS, Railway deployment',
  },
  dental: {
    systemName:  'Dental Patient Retention & Scheduling System',
    components: [
      { name: 'Appointment Reminder Engine',   type: 'Automation',  status: 'live',    description: 'Sends SMS + email reminders at 48h and 2h before appointment.' },
      { name: 'Smart Re-Booking Flow',         type: 'Automation',  status: 'live',    description: 'Cancellation detected → immediate re-booking prompt with available slots.' },
      { name: 'Reactivation Campaigns',        type: 'Automation',  status: 'live',    description: 'Identifies patients inactive 6+ months. Sends sequence of 3 re-engagement messages.' },
      { name: 'No-Show Analytics Dashboard',  type: 'Frontend',    status: 'live',    description: 'Tracks no-show rate, recovered appointments, revenue impact by month.' },
      { name: 'Insurance Alert System',        type: 'Automation',  status: 'planned', description: 'Flags patients with expiring insurance benefits — drives end-of-year appointment surge.' },
    ],
    integrations: ['Practice management software (read export)', 'SMS/Email', 'Google Calendar'],
    deliveryTime: '2 business days',
    techStack:    'Python automation, Twilio SMS, SendGrid email, SQLite patient store',
  },
  plumbing: {
    systemName:  'Plumbing Estimate Follow-Up & Lead Engine',
    components: [
      { name: 'Estimate Follow-Up Sequencer',  type: 'Automation',  status: 'live',    description: '5-touch email sequence: 24h, 3 days, 7 days, 14 days, 21 days post-estimate.' },
      { name: 'After-Hours Call Capture',      type: 'AI',          status: 'live',    description: 'AI answers calls after hours, captures job details, fires morning summary to team.' },
      { name: 'Review Request Automation',     type: 'Automation',  status: 'live',    description: '24h after job marked complete → Google Review request sent to customer.' },
      { name: 'Pipeline Dashboard',            type: 'Frontend',    status: 'live',    description: 'Open estimates by age, close rate tracking, revenue forecast.' },
    ],
    integrations: ['Gmail/SendGrid', 'SMS via Twilio', 'Google Reviews link'],
    deliveryTime: '1 business day',
    techStack:    'Python + Node.js, Claude API, Railway deployment',
  },
  contractor: {
    systemName:  'Contractor Project Intake & Pipeline CRM',
    components: [
      { name: 'Smart Intake Form',             type: 'Frontend',    status: 'live',    description: 'Captures: client name, address, project type, scope, timeline, budget range.' },
      { name: 'Lead Qualification Scorer',     type: 'Backend',     status: 'live',    description: 'Auto-scores leads 0-100 on project fit, budget, timeline urgency.' },
      { name: 'Follow-Up Sequence Engine',     type: 'Automation',  status: 'live',    description: '5-touch sequence post-inquiry. Stops on reply. Escalates high-score leads to owner.' },
      { name: 'Project Pipeline Board',        type: 'Frontend',    status: 'live',    description: 'Kanban-style: Inquiry → Qualified → Proposal Sent → Negotiation → Closed.' },
      { name: 'Subcontractor Coordination',    type: 'Backend',     status: 'planned', description: 'Assign subs to projects, track availability, send scope documents.' },
      { name: 'Change Order Tracker',          type: 'Backend',     status: 'planned', description: 'Document and approve change orders digitally. Eliminates text-message agreements.' },
    ],
    integrations: ['Email', 'PDF proposal generator', 'Google Drive sync'],
    deliveryTime: '3 business days',
    techStack:    'Node.js + Express, React frontend (planned), SQLite/Postgres data store',
  },
};

async function buildSystemBlueprint({ niche = 'hoa' } = {}) {
  try {
    const blueprint = SYSTEM_BLUEPRINTS[niche] || SYSTEM_BLUEPRINTS.hoa;
    const key = API_KEY();

    if (key) {
      const liveComponents    = blueprint.components.filter(c => c.status === 'live').map(c => c.name).join(', ');
      const plannedComponents = blueprint.components.filter(c => c.status === 'planned').map(c => c.name).join(', ');

      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({
          model: MODEL, max_tokens: 250,
          messages: [{
            role:    'user',
            content: `For a ${niche} business automation system with these live components: ${liveComponents}. Planned: ${plannedComponents}.\n\nWhat is the single most valuable "quick win" component to build next that would materially increase the monthly contract value? Answer in 2 sentences. Return JSON: { "nextBuild": "component name", "rationale": "...", "revenueImpact": "$X/mo" }`,
          }],
        }),
        signal: AbortSignal.timeout(10000),
      });

      if (res.ok) {
        const data  = await res.json();
        const match = (data.content?.[0]?.text?.trim() || '').match(/\{[\s\S]*\}/);
        if (match) {
          const parsed = JSON.parse(match[0]);
          return { ...blueprint, niche, aiRecommendation: parsed, generatedAt: new Date().toISOString() };
        }
      }
    }

    return { ...blueprint, niche, generatedAt: new Date().toISOString() };
  } catch (err) {
    console.error('[systemBuilder] Error:', err.message);
    return { ...(SYSTEM_BLUEPRINTS[niche] || SYSTEM_BLUEPRINTS.hoa), niche, generatedAt: new Date().toISOString() };
  }
}

module.exports = { buildSystemBlueprint };
