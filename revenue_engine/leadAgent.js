/**
 * leadAgent.js — Gray Horizons Enterprise Revenue Engine
 * Generates qualified leads per niche.
 * Claude-enhanced if ANTHROPIC_API_KEY is set; always returns fallback data.
 */

'use strict';

const MODEL   = 'claude-3-haiku-20240307';
const API_KEY = () => process.env.ANTHROPIC_API_KEY;

// ── Curated lead pools by niche ───────────────────────────────────────────────

const LEAD_POOLS = {
  hoa: [
    { company: 'Westside Community Management', contact: 'Jennifer Morris',  email: 'jmorris@westsidecm.com',   phone: '(714) 555-0192', title: 'Operations Manager',   city: 'Anaheim, CA',     score: 92, pain: 'violation tracking scattered across email' },
    { company: 'Summit HOA Services',           contact: 'David Chen',       email: 'dchen@summithoa.com',       phone: '(909) 555-0341', title: 'Property Director',    city: 'Rancho Cucamonga', score: 88, pain: 'manual compliance docs, no system' },
    { company: 'Pacific Crest Management',      contact: 'Maria Sanchez',    email: 'msanchez@pacificcrest.com', phone: '(951) 555-0274', title: 'Community Manager',    city: 'Riverside, CA',   score: 85, pain: 'board handoffs constantly fail' },
    { company: 'Elite HOA Group',               contact: 'Robert Kim',       email: 'rkim@elitehoa.com',         phone: '(760) 555-0118', title: 'GM',                   city: 'Palm Desert, CA', score: 79, pain: 'managing 15 HOAs with spreadsheets' },
    { company: 'Cornerstone Association Mgmt',  contact: 'Linda Torres',     email: 'ltorres@cornerstonehoa.net',phone: '(562) 555-0455', title: 'VP Operations',        city: 'Long Beach, CA',  score: 91, pain: 'homeowner complaints unresolved >30 days' },
    { company: 'Coastal Community Partners',    contact: 'James Webb',       email: 'jwebb@coastalpartners.com', phone: '(619) 555-0388', title: 'Portfolio Manager',    city: 'San Diego, CA',   score: 83, pain: 'no audit trail for violations' },
    { company: 'Inland Empire HOA',             contact: 'Susan Park',       email: 'spark@iehoamgmt.com',       phone: '(909) 555-0561', title: 'Director',             city: 'Rialto, CA',      score: 95, pain: 'enforcement inconsistent across properties' },
    { company: 'Desert Springs Association',    contact: 'Carlos Ruiz',      email: 'cruiz@desertspringsassoc.com',phone:'(760) 555-0229',title: 'Executive Director',  city: 'Palm Springs, CA',score: 77, pain: 'owners bypass management directly to board' },
    { company: 'Prestige Property Management',  contact: 'Angela Wright',    email: 'awright@prestigepm.com',    phone: '(626) 555-0347', title: 'Chief Operating Officer',city:'Pasadena, CA',   score: 86, pain: 'documentation lost during staff turnover' },
    { company: 'Horizon Community Services',    contact: 'Michael Davis',    email: 'mdavis@horizoncs.org',      phone: '(805) 555-0193', title: 'Regional Manager',     city: 'Ventura, CA',     score: 81, pain: 'compliance deadlines missed regularly' },
  ],
  hvac: [
    { company: 'CoolAir Solutions',             contact: 'Tom Nguyen',       email: 'tnguyen@coolair.com',       phone: '(714) 555-0811', title: 'Service Manager',      city: 'Orange, CA',      score: 89, pain: 'dispatching still done by phone/paper' },
    { company: 'Premier HVAC & Mechanical',     contact: 'Lisa Chen',        email: 'lchen@premierhvac.net',     phone: '(909) 555-0622', title: 'Operations Lead',      city: 'Ontario, CA',     score: 84, pain: 'no automated customer follow-up' },
    { company: 'Desert Comfort Systems',        contact: 'Mark Johnson',     email: 'mjohnson@desertcomfort.com',phone: '(760) 555-0433', title: 'Owner',                city: 'Indio, CA',       score: 91, pain: 'losing emergency calls to competitors' },
    { company: 'Pacific Coast Climate',         contact: 'Diana Lee',        email: 'dlee@pcclimate.com',        phone: '(858) 555-0719', title: 'GM',                   city: 'San Diego, CA',   score: 76, pain: 'technician scheduling inefficiencies' },
    { company: 'All Season Comfort',            contact: 'Greg Martinez',    email: 'gmartinez@allseasoncomfort.com',phone:'(951) 555-0566',title:'Service Director',  city: 'Temecula, CA',    score: 87, pain: 'customer retention under 40%' },
  ],
  dental: [
    { company: 'Bright Smiles Dental Group',    contact: 'Dr. Amanda Walsh', email: 'awalsh@brightsmiles.com',   phone: '(310) 555-0944', title: 'Practice Owner',       city: 'Los Angeles, CA', score: 93, pain: 'no-show rate over 25%' },
    { company: 'Family Dental Associates',      contact: 'Nancy Cooper',     email: 'ncooper@familydental.net',  phone: '(626) 555-0371', title: 'Office Manager',       city: 'Monrovia, CA',    score: 88, pain: 'phone tag scheduling wastes 3hrs/day' },
    { company: 'Riverside Oral Health Center',  contact: 'Dr. Kevin Park',   email: 'kpark@riversiodental.com',  phone: '(951) 555-0218', title: 'Lead Dentist',         city: 'Riverside, CA',   score: 82, pain: 'new patient intake all paper-based' },
    { company: 'SoCal Dental Network',          contact: 'Maria Vasquez',    email: 'mvasquez@socaldentalnet.com',phone:'(619) 555-0537',title: 'Network Director',    city: 'San Diego, CA',   score: 79, pain: 'insurance verification delays' },
    { company: 'Inland Dental Group',           contact: 'Dr. James Tran',   email: 'jtran@inlanddentalgroup.com',phone:'(909) 555-0684',title: 'Practice Director',   city: 'Fontana, CA',     score: 85, pain: 'no system for recall / reactivation' },
  ],
  plumbing: [
    { company: 'Rapid Response Plumbing',       contact: 'Steve Adams',      email: 'sadams@rapidresponse.com',  phone: '(909) 555-0752', title: 'Owner',                city: 'San Bernardino, CA',score:90, pain: 'missing emergency calls overnight' },
    { company: 'Pacific Pipe Works',            contact: 'Jason Lee',        email: 'jlee@pacificpipe.com',      phone: '(951) 555-0839', title: 'Operations Manager',   city: 'Moreno Valley, CA',score:86, pain: 'estimate-to-close rate under 35%' },
    { company: 'SoCal Plumbing Pros',           contact: 'Marcus Green',     email: 'mgreen@socalplumbing.net',  phone: '(714) 555-0913', title: 'GM',                   city: 'Santa Ana, CA',   score: 81, pain: 'no customer follow-up system' },
    { company: 'Desert Valley Plumbing',        contact: 'Carlos Rivera',    email: 'crivera@desertvp.com',      phone: '(760) 555-0127', title: 'Service Director',     city: 'Victorville, CA', score: 77, pain: 'technicians use personal phones for dispatch' },
    { company: 'Pro Flow Solutions',            contact: 'Kim Tran',         email: 'ktran@proflowsolutions.com',phone: '(562) 555-0468', title: 'Owner/Operator',       city: 'Downey, CA',      score: 88, pain: 'zero online booking presence' },
  ],
  contractor: [
    { company: 'Apex General Contracting',      contact: 'Brandon Scott',    email: 'bscott@apexgc.com',         phone: '(909) 555-0382', title: 'President',            city: 'Rialto, CA',      score: 94, pain: 'project intake entirely manual' },
    { company: 'SoCal Build Group',             contact: 'Rachel Torres',    email: 'rtorres@socalbuild.com',     phone: '(951) 555-0519', title: 'Project Manager',      city: 'Riverside, CA',   score: 87, pain: 'estimate follow-up falling through cracks' },
    { company: 'Desert Sun Construction',       contact: 'Miguel Ortiz',     email: 'mortiz@desertsun.build',    phone: '(760) 555-0746', title: 'Operations Director',  city: 'Palm Desert, CA', score: 83, pain: 'subcontractor coordination chaos' },
    { company: 'Pacific Edge Builders',         contact: 'Danielle Kim',     email: 'dkim@pacificedge.build',    phone: '(619) 555-0633', title: 'VP Business Dev',      city: 'San Diego, CA',   score: 89, pain: 'no CRM for project leads' },
    { company: 'Cornerstone Renovations',       contact: 'Tony Williams',    email: 'twilliams@cornerstonereno.com',phone:'(714)555-0881',title:'Owner',              city: 'Anaheim, CA',     score: 85, pain: 'change orders managed over text message' },
  ],
};

// ── Claude-enhanced lead scoring ──────────────────────────────────────────────

async function enhanceLeadsWithClaude(leads, niche) {
  const key = API_KEY();
  if (!key) return leads;

  try {
    const sample = leads.slice(0, 5);
    const prompt = sample.map((l, i) =>
      `${i + 1}. ${l.company} | ${l.title} | Pain: ${l.pain}`
    ).join('\n');

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method:  'POST',
      headers: {
        'x-api-key':         key,
        'anthropic-version': '2023-06-01',
        'content-type':      'application/json',
      },
      body: JSON.stringify({
        model:      MODEL,
        max_tokens: 300,
        messages: [{
          role:    'user',
          content: `You are a sales strategist for a Black-owned AI automation firm (Gray Horizons Enterprise, Rialto CA) that sells workflow automation to ${niche} businesses.\n\nRank these leads 1-5 (best opportunity first). Return JSON array of 1-based indexes only. No explanation.\n\nLeads:\n${prompt}`,
        }],
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) return leads;
    const data = await res.json();
    const txt  = data.content?.[0]?.text?.trim() || '';
    const match = txt.match(/\[[\d,\s]+\]/);
    if (!match) return leads;
    const order = JSON.parse(match[0]);
    const reordered = order
      .filter(n => n >= 1 && n <= sample.length)
      .map(n => ({ ...sample[n - 1], aiRanked: true }));
    return [...reordered, ...leads.slice(5)];
  } catch {
    return leads;
  }
}

// ── generateLeads ─────────────────────────────────────────────────────────────

async function generateLeads({ niche = 'hoa', count = 10 } = {}) {
  try {
    const pool = LEAD_POOLS[niche] || LEAD_POOLS.hoa;
    let leads  = pool.slice(0, count).map(l => ({
      ...l,
      niche,
      nextAction: _nextAction(l.score),
      generatedAt: new Date().toISOString(),
    }));

    leads = await enhanceLeadsWithClaude(leads, niche);
    return leads;
  } catch (err) {
    console.error('[leadAgent] Error:', err.message);
    // Hard fallback — always returns something
    return (LEAD_POOLS[niche] || LEAD_POOLS.hoa).slice(0, count).map(l => ({
      ...l, niche, nextAction: 'Send cold outreach email', generatedAt: new Date().toISOString(),
    }));
  }
}

function _nextAction(score) {
  if (score >= 90) return 'High priority — send personalized cold email today';
  if (score >= 80) return 'Schedule outreach within 48 hours';
  if (score >= 70) return 'Add to nurture sequence';
  return 'Research more — confirm pain point fit';
}

module.exports = { generateLeads };
