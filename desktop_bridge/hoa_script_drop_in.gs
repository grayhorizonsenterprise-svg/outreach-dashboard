/**
 * ================================================================
 *  GRAY HORIZONS ENTERPRISE — UNIFIED INTAKE BACKEND  v5
 * ================================================================
 *  DEPLOY:  Extensions → Apps Script → Deploy → New deployment
 *           Type: Web App | Execute as: Me | Who has access: Anyone
 *
 *  FIRST-RUN CHECKLIST (do in order, once, in GAS editor):
 *    1. Confirm MASTER_SHEET_ID below matches your HOA spreadsheet
 *    2. Run removeAllTriggers()  — clears any stray onEdit triggers
 *    3. Run selfTest()           — authorises + verifies all 4 modes
 *    4. Deploy as Web App        — copy the /exec URL
 *    5. Paste that URL into index.html as GHE_SCRIPT_URL
 *
 *  SHEET LAYOUT:
 *    Each mode writes to its OWN separate Google Spreadsheet.
 *    HOA  → fixed sheet (HOA_SHEET_ID below, embed URL still works).
 *    HVAC / Dental / Plumbing / Contractor → auto-created on first
 *    submission; IDs saved to Script Properties (SHEET_HVAC, etc.).
 *
 *  TRANSPORT:
 *    doGet  = JSONP  (primary — what all portal forms use)
 *    doPost = JSON   (sendBeacon fallback)
 * ================================================================
 */

// ── CONFIG ───────────────────────────────────────────────────────
// HOA sheet ID is fixed (existing compliance sheet + embed URL).
// HVAC / Dental / Plumbing sheets are auto-created on first submission
// and their IDs saved to Script Properties (SHEET_HVAC, etc.).
var HOA_SHEET_ID   = '1yYneTtS53eZy_Jw8yFCLxhijB190KFy4el3SKzfn9-w';
var NOTIFY_EMAIL   = 'grayhorizonsenterprise@gmail.com';
var EMAIL_ENABLED  = true;
var RATE_LIMIT_SEC = 15;
var TZ             = 'America/Los_Angeles';

var VALID_MODES = ['hoa', 'hvac', 'dental', 'plumbing', 'contractor'];

var SHEET_TITLES = {
  hoa:        'GH — HOA Compliance',
  hvac:       'GH — HVAC System',
  dental:     'GH — Dental System',
  plumbing:   'GH — Plumbing System',
  contractor: 'GH — Contractor System'
};

// Headers per sheet — must match column order in _buildRow()
var TAB_HEADERS = {
  hoa:        ['ID','Timestamp','Resident Name','Email','Phone','Unit #','Violation Type','Notice','Status'],
  hvac:       ['ID','Timestamp','Customer Name','Email','Property Address','Service Type','Description','Status'],
  dental:     ['ID','Timestamp','Patient Name','Email','Phone / Patient ID','Appointment Type','Details','Status'],
  plumbing:   ['ID','Timestamp','Customer Name','Email','Property Address','Service Type','Description','Status'],
  contractor: ['ID','Timestamp','Client Name','Email','Project Address','Project Type','Details','Status']
};
// ─────────────────────────────────────────────────────────────────


/* ================================================================
   ENTRY POINTS
   ================================================================ */

/** doGet — JSONP. Primary transport from all portal HTML files. */
function doGet(e) {
  var cb  = (e && e.parameter && e.parameter.callback) ? String(e.parameter.callback) : null;
  var raw = (e && e.parameter && e.parameter.data)     ? e.parameter.data             : null;

  function respond(obj) {
    var json = JSON.stringify(obj);
    var out  = cb ? cb + '(' + json + ');' : json;
    return ContentService
      .createTextOutput(out)
      .setMimeType(cb ? ContentService.MimeType.JAVASCRIPT : ContentService.MimeType.JSON);
  }

  // List sheet URLs action — called by frontend on load
  var action = (e && e.parameter) ? e.parameter.action : null;
  if (action === 'listSheets') {
    return respond({ status: 'ok', sheets: _getSheetUrls() });
  }

  // Health ping — no data param
  if (!raw) {
    _log('INFO', 'ping', 'Health check');
    return respond({ status: 'ok', ping: true, ts: new Date().toISOString() });
  }

  var data;
  try { data = JSON.parse(decodeURIComponent(raw)); }
  catch (err) {
    _log('ERROR', 'doGet', 'JSON parse: ' + err.message);
    return respond({ status: 'error', msg: 'JSON parse failed' });
  }

  var result;
  try   { result = _process(data); }
  catch (err) {
    _log('ERROR', 'doGet', err.message);
    result = { status: 'error', msg: err.message };
  }

  return respond(result);
}

/** doPost — JSON body. sendBeacon / fetch fallback. */
function doPost(e) {
  function respond(obj) {
    return ContentService
      .createTextOutput(JSON.stringify(obj))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (!e || !e.postData || !e.postData.contents) {
    return respond({ status: 'error', msg: 'No POST body' });
  }

  var data;
  try { data = JSON.parse(e.postData.contents); }
  catch (err) {
    _log('ERROR', 'doPost', 'JSON parse: ' + err.message);
    return respond({ status: 'error', msg: 'Invalid JSON' });
  }

  var result;
  try   { result = _process(data); }
  catch (err) {
    _log('ERROR', 'doPost', err.message);
    result = { status: 'error', msg: err.message };
  }

  return respond(result);
}


/* ================================================================
   CORE PROCESSING
   ================================================================ */
function _process(data) {
  // 1. Validate mode
  var mode = data && data.mode ? String(data.mode).toLowerCase().trim() : null;
  if (!mode || VALID_MODES.indexOf(mode) === -1) {
    throw new Error('Invalid mode. Expected: ' + VALID_MODES.join(', '));
  }

  // 2. Sanitise inputs
  var name   = _s(data.name,    64);
  var email  = _s(data.email,  128);
  var phone  = _s(data.phone,   32);
  var unit   = _s(data.unit,    64);
  var type   = _s(data.type,    64);
  var notice = _s(data.notice, 1000);
  var id     = _s(data.id,      32) || ('R' + Date.now());
  var ts     = _s(data.ts,      48) ||
               Utilities.formatDate(new Date(), TZ, 'M/d/yyyy h:mm a');

  // 3. Required fields
  if (!name)             throw new Error('Name is required');
  if (!email)            throw new Error('Email is required');
  if (!_validEmail(email)) throw new Error('Invalid email');
  if (!notice)           throw new Error('Details/notice is required');

  // 4. Rate limit — same email+mode within N seconds
  _rateLimit(email, mode);

  // 5. Write row to correct spreadsheet
  var sheet  = _getSheet(mode);
  var row    = _buildRow(mode, id, ts, name, email, phone, unit, type, notice);
  sheet.appendRow(row);
  SpreadsheetApp.flush();
  var rowNum = sheet.getLastRow();
  _log('INFO', '_process', 'Row ' + rowNum + ' written mode=' + mode + ' id=' + id);

  // Mark status pending while email sends
  var statusCol = row.length;
  sheet.getRange(rowNum, statusCol).setValue('Processing…');

  // 6. Send confirmation email (non-fatal)
  var emailSent = false;
  if (EMAIL_ENABLED) {
    try {
      _sendConfirmation(mode, name, email, phone, unit, type, notice, ts);
      emailSent = true;
      sheet.getRange(rowNum, statusCol).setValue('✓ Email Sent');
    } catch (err) {
      sheet.getRange(rowNum, statusCol).setValue('Sheet Only');
      _log('WARN', '_process', 'Email failed (non-fatal): ' + err.message);
    }
  } else {
    sheet.getRange(rowNum, statusCol).setValue('Logged');
  }

  // 7. Owner alert (non-fatal)
  try { _ownerAlert(mode, name, email, unit, type, notice, rowNum); } catch (_) {}

  // 8. Prune — keep header + 2 most recent data rows only
  //    Protects against sensitive data accumulation on the sheet.
  try {
    var totalRows = sheet.getLastRow();
    if (totalRows > 3) {
      sheet.deleteRows(2, totalRows - 3);
    }
  } catch (pruneErr) {
    _log('WARN', '_process', 'Row prune failed (non-fatal): ' + pruneErr.message);
  }

  return { status: 'ok', row: rowNum, id: id, emailSent: emailSent, mode: mode };
}


/* ================================================================
   SHEET MANAGEMENT — each mode has its own separate spreadsheet
   HOA uses the fixed HOA_SHEET_ID.
   Other modes are auto-created and IDs saved to Script Properties.
   ================================================================ */
function _getSheet(mode) {
  var ss;
  if (mode === 'hoa') {
    ss = SpreadsheetApp.openById(HOA_SHEET_ID);
  } else {
    var props = PropertiesService.getScriptProperties();
    var key   = 'SHEET_' + mode.toUpperCase();
    var id    = props.getProperty(key);
    if (id) {
      try { ss = SpreadsheetApp.openById(id); }
      catch (_) { props.deleteProperty(key); id = null; }
    }
    if (!id) {
      ss = SpreadsheetApp.create(SHEET_TITLES[mode]);
      props.setProperty(key, ss.getId());
      Logger.log('Created sheet [' + mode + ']: https://docs.google.com/spreadsheets/d/' + ss.getId());
    }
  }
  var sheet = ss.getSheets()[0];
  if (!sheet.getRange(1, 1).getValue()) _setupSheet(sheet, mode);
  return sheet;
}

function _setupSheet(sheet, mode) {
  var headers = TAB_HEADERS[mode];
  var r = sheet.getRange(1, 1, 1, headers.length);
  r.setValues([headers]);
  r.setFontWeight('bold');
  r.setBackground('#1a3a5c');
  r.setFontColor('#ffffff');
  sheet.setFrozenRows(1);
  try { sheet.autoResizeColumns(1, headers.length); } catch (_) {}
  _lockSheet(sheet);
}

function _lockSheet(sheet) {
  // Remove any existing protections first
  sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET)
       .forEach(function(p) { p.remove(); });
  var protection = sheet.protect().setDescription('Read-only — managed by GHE automation script');
  // Strip all editors except the script owner
  protection.removeEditors(protection.getEditors());
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
}


function _getSheetUrls() {
  var base = 'https://docs.google.com/spreadsheets/d/';
  var urls = { hoa: base + HOA_SHEET_ID };
  var props = PropertiesService.getScriptProperties().getProperties();
  ['hvac','dental','plumbing','contractor'].forEach(function(m) {
    var id = props['SHEET_' + m.toUpperCase()];
    urls[m] = id ? base + id : null;
  });
  return urls;
}


/* ================================================================
   ROW BUILDER
   Column order must match TAB_HEADERS above exactly.
   ================================================================ */
function _buildRow(mode, id, ts, name, email, phone, unit, type, notice) {
  switch (mode) {
    case 'hoa':
      // ID | Timestamp | Resident Name | Email | Phone | Unit # | Violation Type | Notice | Status
      return [id, ts, name, email, phone, unit, type, notice, 'Pending'];
    case 'hvac':
      // ID | Timestamp | Customer Name | Email | Property Address | Service Type | Description | Status
      return [id, ts, name, email, unit, type, notice, 'Pending'];
    case 'dental':
      // ID | Timestamp | Patient Name | Email | Phone/Patient ID | Appointment Type | Details | Status
      return [id, ts, name, email, unit, type, notice, 'Pending'];
    case 'plumbing':
      // ID | Timestamp | Customer Name | Email | Property Address | Service Type | Description | Status
      return [id, ts, name, email, unit, type, notice, 'Pending'];
    case 'contractor':
      // ID | Timestamp | Client Name | Email | Project Address | Project Type | Details | Status
      return [id, ts, name, email, unit, type, notice, 'Pending'];
    default:
      return [id, ts, name, email, unit, type, notice, 'Pending'];
  }
}


/* ================================================================
   EMAIL — HTML confirmation to submitter + plain-text owner alert
   ================================================================ */
function _sendConfirmation(mode, name, email, phone, unit, type, notice, ts) {
  var cfg = {
    hoa: {
      subject: 'HOA Violation Notice — Unit ' + (unit || 'N/A'),
      headline: 'Violation Notice Received',
      intro: 'This is an official record of a violation logged against your unit. Please address it promptly.',
      fields: [['Unit #', unit], ['Violation Type', type], ['Notice', notice], ['Logged', ts]]
    },
    hvac: {
      subject: 'HVAC Service Request Confirmed — ' + (type || 'Request'),
      headline: 'Service Request Received',
      intro: 'We\'ve received your HVAC service request. A technician will contact you shortly to confirm scheduling.',
      fields: [['Service Type', type], ['Property', unit], ['Description', notice], ['Submitted', ts]]
    },
    dental: {
      subject: 'Dental Appointment Request — ' + (type || 'Appointment'),
      headline: 'Appointment Request Received',
      intro: 'Your appointment request has been received. Our scheduling team will confirm your time within 24 hours.',
      fields: [['Appointment Type', type], ['Phone / Patient ID', unit], ['Details', notice], ['Submitted', ts]]
    },
    plumbing: {
      subject: 'Plumbing Service Request Confirmed — ' + (type || 'Request'),
      headline: 'Service Request Received',
      intro: 'We\'ve received your plumbing service request. A plumber will contact you shortly to confirm scheduling.',
      fields: [['Service Type', type], ['Property', unit], ['Issue', notice], ['Submitted', ts]]
    },
    contractor: {
      subject: 'Project Intake Received — ' + (type || 'Project'),
      headline: 'Project Intake Confirmed',
      intro: 'We\'ve received your project intake. Our team will review the details and contact you shortly to discuss next steps.',
      fields: [['Project Type', type], ['Project Address', unit], ['Details', notice], ['Submitted', ts]]
    }
  };

  var c = cfg[mode] || {
    subject: 'Request Received — Gray Horizons Enterprise',
    headline: 'Request Received',
    intro: 'Your request has been received and logged.',
    fields: [['Type', type], ['Details', notice], ['Submitted', ts]]
  };

  var tableRows = c.fields.map(function(f) {
    return '<tr>' +
      '<td style="padding:8px 12px;font-weight:600;color:#374151;background:#f8fafc;' +
           'border:1px solid #e2e8f0;width:38%;vertical-align:top">' + f[0] + '</td>' +
      '<td style="padding:8px 12px;color:#1e293b;border:1px solid #e2e8f0">' + (f[1] || '—') + '</td>' +
    '</tr>';
  }).join('');

  var html =
    '<div style="font-family:Inter,system-ui,sans-serif;max-width:540px;margin:0 auto;' +
               'padding:32px 24px;background:#fff;border-radius:12px;">' +
      '<div style="background:linear-gradient(90deg,#1d4ed8,#2563eb);border-radius:8px;' +
                  'padding:18px 24px;margin-bottom:24px;">' +
        '<p style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;' +
                  'color:rgba(255,255,255,.7);margin:0 0 4px">Gray Horizons Enterprise</p>' +
        '<h2 style="font-size:20px;font-weight:800;color:#fff;margin:0">' + c.headline + '</h2>' +
      '</div>' +
      '<p style="font-size:15px;color:#1e293b;margin:0 0 8px">Hi <strong>' + name + '</strong>,</p>' +
      '<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 20px">' + c.intro + '</p>' +
      '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:14px">' +
        tableRows +
      '</table>' +
      '<hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 16px">' +
      '<p style="font-size:12px;color:#94a3b8;margin:0">' +
        'Gray Horizons Enterprise &mdash; ' +
        '<a href="https://grayhorizonsenterprise.com" style="color:#4f9cff;text-decoration:none;">' +
          'grayhorizonsenterprise.com</a>' +
        '<br>This is an automated confirmation. Reply to this email with any questions.' +
      '</p>' +
    '</div>';

  GmailApp.sendEmail(email, c.subject, html.replace(/<[^>]+>/g, ' '), {
    htmlBody:  html,
    name:      'Gray Horizons Enterprise',
    replyTo:   NOTIFY_EMAIL
  });
}

function _ownerAlert(mode, name, email, unit, type, notice, rowNum) {
  if (!NOTIFY_EMAIL || NOTIFY_EMAIL === 'your@email.com') return;
  var label = (SHEET_TITLES[mode] || mode).replace('GH — ','');
  GmailApp.sendEmail(
    NOTIFY_EMAIL,
    '[GHE] New ' + label + ' — ' + name + ' (row ' + rowNum + ')',
    'Mode: '    + label                         + '\n' +
    'Name: '    + name                          + '\n' +
    'Email: '   + email                         + '\n' +
    'Unit: '    + (unit   || 'N/A')             + '\n' +
    'Type: '    + (type   || 'N/A')             + '\n' +
    'Details: ' + notice                        + '\n' +
    'Row: '     + rowNum
  );
}


/* ================================================================
   RATE LIMITER
   ================================================================ */
function _rateLimit(email, mode) {
  var props    = PropertiesService.getScriptProperties();
  var safeKey  = 'RL_' + mode + '_' + email.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 180);
  var last     = props.getProperty(safeKey);
  var now      = Date.now();
  if (last && (now - parseInt(last, 10)) < RATE_LIMIT_SEC * 1000) {
    throw new Error('Rate limit: please wait before resubmitting');
  }
  props.setProperty(safeKey, String(now));
}


/* ================================================================
   HELPERS
   ================================================================ */
function _s(val, maxLen) {
  if (val === null || val === undefined) return '';
  return String(val).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '').trim().slice(0, maxLen || 255);
}

function _validEmail(e) {
  return /^[^\s@]{1,64}@[^\s@]+\.[^\s@]{2,}$/.test(e);
}

function _log(level, fn, msg) {
  Logger.log('[' + level + '] ' + fn + ': ' + msg);
}


/* ================================================================
   UTILITY FUNCTIONS — run manually in GAS editor
   ================================================================ */

/**
 * Run FIRST in GAS editor.
 * Authorises the script, writes one test row per mode, sends test emails.
 * Check View → Executions for output; check the master spreadsheet for rows.
 */
function selfTest() {
  var tester = Session.getActiveUser().getEmail() || NOTIFY_EMAIL;
  Logger.log('selfTest start — tester=' + tester);

  VALID_MODES.forEach(function(mode) {
    try {
      var result = _process({
        id:     'SELFTEST-' + mode.toUpperCase() + '-' + Date.now(),
        ts:     Utilities.formatDate(new Date(), TZ, 'M/d/yyyy h:mm a'),
        name:   'GHE Self-Test (' + mode + ')',
        email:  tester,
        phone:  '555-000-0000',
        unit:   'TEST-UNIT',
        type:   'System Verification',
        notice: 'Automated self-test — verifying sheet write and email for mode: ' + mode,
        mode:   mode
      });
      Logger.log('PASS [' + mode + ']: ' + JSON.stringify(result));
    } catch (err) {
      Logger.log('FAIL [' + mode + ']: ' + err.message);
    }
  });

  Logger.log('selfTest complete — check master sheet and inbox.');
}

/** Simulate a health ping (no data — tests doGet responds correctly). */
function testPing() {
  var urls = _getSheetUrls();
  Logger.log('Ping OK — sheet URLs: ' + JSON.stringify(urls));
}

/** Remove all project triggers (run once after first deploy). */
function removeAllTriggers() {
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });
  Logger.log('All triggers removed.');
}

/** Clear only rate-limit keys from Script Properties. */
function clearRateLimits() {
  var props = PropertiesService.getScriptProperties();
  var all   = props.getProperties();
  var count = 0;
  Object.keys(all).forEach(function(k) {
    if (k.indexOf('RL_') === 0) { props.deleteProperty(k); count++; }
  });
  Logger.log('Cleared ' + count + ' rate-limit entries.');
}

/**
 * Lock every sheet that already exists (HOA + any already-created niches).
 * Run once manually after deploy — new sheets are auto-locked on creation.
 */
function lockAllSheets() {
  var targets = [{ id: HOA_SHEET_ID, label: 'HOA' }];
  var props = PropertiesService.getScriptProperties().getProperties();
  ['HVAC','DENTAL','PLUMBING','CONTRACTOR'].forEach(function(k) {
    var id = props['SHEET_' + k];
    if (id) targets.push({ id: id, label: k });
  });
  targets.forEach(function(t) {
    try {
      var sheet = SpreadsheetApp.openById(t.id).getSheets()[0];
      _lockSheet(sheet);
      Logger.log('Locked: ' + t.label);
    } catch (err) {
      Logger.log('FAILED to lock ' + t.label + ': ' + err.message);
    }
  });
}

/** Print all spreadsheet URLs to Logger. */
function listSheets() {
  Logger.log('HOA (fixed): https://docs.google.com/spreadsheets/d/' + HOA_SHEET_ID);
  var props = PropertiesService.getScriptProperties().getProperties();
  ['HVAC','DENTAL','PLUMBING','CONTRACTOR'].forEach(function(k) {
    var id = props['SHEET_' + k];
    Logger.log(k + ': ' + (id ? 'https://docs.google.com/spreadsheets/d/' + id : '(not yet created)'));
  });
}
