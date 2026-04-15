from flask import Flask, redirect
import pandas as pd
import os
import requests
import threading
import time
import subprocess
import sys
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    PACIFIC = ZoneInfo("America/Los_Angeles")
    def now_pacific():
        return datetime.now(PACIFIC)
    def fmt_pacific(ts):
        return datetime.fromtimestamp(ts, PACIFIC).strftime("%I:%M %p PT")
except Exception:
    _PT = timezone(timedelta(hours=-7))
    def now_pacific():
        return datetime.now(_PT)
    def fmt_pacific(ts):
        return datetime.fromtimestamp(ts, _PT).strftime("%I:%M %p PT")

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)

URL_HOA       = os.getenv("HOA_URL", "#")
URL_DENTAL    = os.getenv("DENTAL_URL", "#")
URL_HVAC      = os.getenv("HVAC_URL", "#")
URL_HUB       = os.getenv("HUB_URL", "#")
URL_PLUMBING  = os.getenv("PLUMBING_URL", "#")
URL_GRANTS       = "https://ghe-grant-agent-production.up.railway.app"
URL_VOICE_SERVER = os.getenv("VOICE_SERVER_URL", "https://ghe-voice-production.up.railway.app")
PIPELINE_SCRIPTS = ["prospect_finder.py", "prospect_enricher.py",
                    "prospect_qualifier.py", "outreach_generator.py"]

# =========================
# BACKGROUND PIPELINE ENGINE
# Runs the full pipeline every 6 hours inside the same process
# so one Render web service handles everything
# =========================
pipeline_running = False
last_run_time = None

def run_pipeline_once():
    global pipeline_running, last_run_time
    if pipeline_running:
        return
    pipeline_running = True
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print("[ENGINE] Starting pipeline cycle...", flush=True)
    for script in PIPELINE_SCRIPTS:
        try:
            print(f"[ENGINE] Running {script}", flush=True)
            subprocess.run(
                [sys.executable, "-u", os.path.join(script_dir, script)],
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                timeout=1800
            )
        except Exception as e:
            print(f"[ENGINE] Error in {script}: {e}", flush=True)
    last_run_time = time.time()
    pipeline_running = False
    print("[ENGINE] Cycle done.", flush=True)

def run_pipeline_loop():
    time.sleep(5)  # let server start first
    while True:
        run_pipeline_once()
        print("[ENGINE] Sleeping 4 hours until next cycle.", flush=True)
        time.sleep(14400)

threading.Thread(target=run_pipeline_loop, daemon=True).start()

# =========================
# KEEP-ALIVE (prevents Render free tier from sleeping)
# =========================
def keep_alive():
    time.sleep(60)
    # Support Render (RENDER_EXTERNAL_URL) and Railway (RAILWAY_PUBLIC_DOMAIN)
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    port = os.getenv("PORT", "8080")
    if render_url:
        target = render_url.rstrip("/")
    elif railway_domain:
        target = f"https://{railway_domain.rstrip('/')}"
    else:
        target = f"http://127.0.0.1:{port}"
    print(f"[KeepAlive] Pinging {target}/health every 10 min", flush=True)
    while True:
        try:
            requests.get(f"{target}/health", timeout=10)
        except Exception:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

CSV_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

# =========================
# LOAD DATA
# =========================
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["company","name","email","message","status"])

    df = pd.read_csv(CSV_FILE)

    df = df.rename(columns={
        "Company": "company",
        "Email": "email",
        "Message": "message",
        "Name": "name"
    })

    for col in ["company","name","email","message","status"]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")
    df.loc[df["status"] == "", "status"] = "pending"

    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# FORMAT MESSAGE (FIX PARAGRAPHS)
# =========================
def format_message(msg):
    if not msg:
        return ""
    return msg.replace("\n", "<br>").replace(". ", ".<br><br>")

# =========================
# SEND EMAIL (SENDGRID)
# =========================
SENT_LOG = os.path.join(DATA_DIR, "sent_log.csv")

def log_sent(to_email, name, company, subject, success, error=""):
    import csv
    from datetime import datetime
    row = {
        "timestamp": now_pacific().strftime("%Y-%m-%d %I:%M %p PT"),
        "company": company,
        "name": name,
        "email": to_email,
        "subject": subject,
        "success": success,
        "error": error,
    }
    file_exists = os.path.exists(SENT_LOG)
    with open(SENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def send_email(to_email, name, company, message):
    api_key     = os.getenv("SENDGRID_API_KEY")
    sender_addr = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")
    subject     = f"{company} — quick question"

    if not api_key or not sender_addr:
        print("[SEND] ERROR: Missing SENDGRID_API_KEY or SENDER_EMAIL env vars")
        log_sent(to_email, name, company, subject, False, "missing env vars")
        return False

    if not to_email:
        print("[SEND] ERROR: No recipient email")
        log_sent(to_email, name, company, subject, False, "no recipient")
        return False

    html_body = f"""
    <div style="font-family:Arial;line-height:1.6;">
        <p>Hi {name or 'there'},</p>
        <p>{format_message(message)}</p>
        <p>— {sender_name}<br>Gray Horizons Enterprise</p>
    </div>
    """

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender_addr, "name": sender_name},
        "reply_to": {"email": sender_addr, "name": sender_name},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}]
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload, headers=headers, timeout=15
        )
        if resp.status_code == 202:
            print(f"[SEND] OK -> {to_email} ({company})")
            log_sent(to_email, name, company, subject, True)
            return True
        else:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:300]}"
            print(f"[SEND] FAILED -> {to_email} | {error_msg}")
            log_sent(to_email, name, company, subject, False, error_msg)
            return False
    except Exception as e:
        print(f"[SEND] EXCEPTION -> {to_email} | {e}")
        log_sent(to_email, name, company, subject, False, str(e))
        return False

# =========================
# FETCH GRANTS FROM GRANT AGENT API
# =========================
def fetch_grants(limit=20):
    # Try grant agent (Python FastAPI) first — has scored DB grants
    try:
        resp = requests.get(f"{URL_GRANTS}/api/grants?min_score=0&limit={limit}", timeout=8)
        if resp.status_code == 200:
            grants = resp.json().get("grants", [])
            if grants:
                return grants
    except Exception as e:
        print(f"[Grants] Grant agent fetch failed: {e}")

    # Fallback: voice server always returns curated grants even if DB is empty
    try:
        resp = requests.get(f"{URL_VOICE_SERVER}/api/grants?limit={limit}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("grants", [])
    except Exception as e:
        print(f"[Grants] Voice server fallback failed: {e}")

    return []


# =========================
# DASHBOARD UI — UNIFIED
# =========================
@app.route('/')
def dashboard():
    from flask import request as flask_request
    active_tab = flask_request.args.get('tab', 'outreach')

    df = load_data()
    grants = fetch_grants(limit=25)

    pending_count = len(df[df["status"] == "pending"])
    sent_count    = len(df[df["status"] == "sent"])
    skipped_count = len(df[df["status"] == "skipped"])

    status_text = '<span style="color:#22c55e">Scraping leads now...</span>' if pipeline_running else (
        f"Last run: {fmt_pacific(last_run_time)}" if last_run_time else "Starting soon..."
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300;url=/?tab={active_tab}">
<title>Gray Horizons — Command Center</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;}}
  .header{{background:#020617;padding:16px;text-align:center;font-size:22px;font-weight:bold;border-bottom:1px solid #1e293b;}}
  .nav{{display:flex;background:#020617;border-bottom:2px solid #1e293b;flex-wrap:wrap;}}
  .nav a{{padding:10px 22px;color:#64748b;font-size:13px;text-decoration:none;cursor:pointer;border-bottom:3px solid transparent;}}
  .nav a.active{{color:#38bdf8;border-bottom:3px solid #38bdf8;font-weight:bold;}}
  .nav a.grants-tab{{color:#a78bfa;}}
  .nav a.grants-tab.active{{color:#a78bfa;border-bottom:3px solid #a78bfa;}}
  .topbar{{display:flex;justify-content:space-between;align-items:center;padding:10px 24px;background:#020617;border-bottom:1px solid #1e293b;flex-wrap:wrap;gap:8px;}}
  .stats{{display:flex;gap:20px;font-size:13px;color:#94a3b8;}}
  .stat-val{{color:#38bdf8;font-weight:bold;}}
  .btn-link{{background:#3b82f6;color:white;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;}}
  .btn-link:hover{{background:#2563eb;}}
  .tab-content{{display:none;}}
  .tab-content.active{{display:block;}}

  /* Outreach cards */
  .card{{background:#1e293b;padding:18px;margin:16px auto;width:92%;max-width:720px;border-radius:10px;}}
  .card-title{{font-size:18px;color:#38bdf8;font-weight:bold;}}
  .card-sub{{color:#94a3b8;font-size:13px;margin:4px 0 10px;}}
  .card-msg{{line-height:1.6;font-size:14px;}}
  .btn-send{{background:#22c55e;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;}}
  .btn-skip{{background:#ef4444;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;margin-left:8px;}}
  .btn-disabled{{background:#475569;color:#94a3b8;border:none;padding:9px 16px;border-radius:6px;font-size:13px;margin-top:10px;}}
  .note{{text-align:center;font-size:11px;color:#475569;padding:6px;}}

  /* Grants table */
  .grants-wrap{{padding:16px 20px;}}
  .grants-topbar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;}}
  .grants-topbar h2{{font-size:16px;color:#a78bfa;}}
  table{{width:100%;border-collapse:collapse;font-size:13px;}}
  th{{background:#1e293b;padding:10px 12px;text-align:left;color:#94a3b8;font-weight:normal;border-bottom:1px solid #334155;}}
  td{{padding:10px 12px;border-bottom:1px solid #1e293b;vertical-align:top;}}
  tr:hover td{{background:#1e293b55;}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold;}}
  .badge-high{{background:#14532d;color:#4ade80;}}
  .badge-med{{background:#1e3a5f;color:#60a5fa;}}
  .badge-low{{background:#2d1b69;color:#a78bfa;}}
  .grant-name{{color:#e2e8f0;font-weight:bold;max-width:260px;}}
  .grant-agency{{color:#64748b;font-size:11px;}}
  .no-grants{{text-align:center;color:#475569;padding:40px;font-size:14px;}}
  .scan-btn{{background:#7c3aed;color:white;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;}}
  .scan-btn:hover{{background:#6d28d9;}}
</style>
</head>
<body>
<div class="header">Gray Horizons Enterprise — Command Center</div>

<div class="nav">
  <a href="{URL_HOA}" target="_blank">HOA</a>
  <a href="{URL_DENTAL}" target="_blank">Dental</a>
  <a href="{URL_HVAC}" target="_blank">HVAC</a>
  <a href="{URL_PLUMBING}" target="_blank">Plumbing</a>
  <a href="{URL_HUB}" target="_blank">All Niches</a>
  <a onclick="showTab('outreach')" id="tab-outreach" class="{'active' if active_tab=='outreach' else ''}">Outreach ({pending_count} pending)</a>
  <a onclick="showTab('grants')" id="tab-grants" class="grants-tab {'active' if active_tab=='grants' else ''}">💰 Grants ({len(grants)} found)</a>
</div>

<!-- OUTREACH TAB -->
<div id="content-outreach" class="tab-content {'active' if active_tab=='outreach' else ''}">
  <div class="topbar">
    <div style="font-size:12px;color:#64748b;">{status_text}</div>
    <div class="stats">
      <span>Pending: <span class="stat-val">{pending_count}</span></span>
      <span>Sent: <span class="stat-val">{sent_count}</span></span>
      <span>Skipped: <span class="stat-val">{skipped_count}</span></span>
    </div>
    <div style="display:flex;gap:8px;">
      <a href="/sent" class="btn-link" style="background:#7c3aed;">View Sent</a>
      <a href="/refresh" class="btn-link">{'Scraping...' if pipeline_running else 'Refresh Leads'}</a>
    </div>
  </div>
  <div class="note">{len(df)} total leads · auto-refreshes every 5 min</div>
"""

    # Outreach lead cards
    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue
        name    = row["name"] or "Contact"
        company = row["company"] or "Unknown Company"
        email   = row["email"]
        html += f"""
  <div class="card">
    <div class="card-title">{name}</div>
    <div class="card-sub">{company} &nbsp;·&nbsp; {email if email else '❌ No Email'}</div>
    <div class="card-msg">{format_message(row["message"])}</div>
    <div>"""
        if email:
            html += f'<a href="/send/{i}" class="btn-send">Send</a>'
        else:
            html += '<button class="btn-disabled">No Email</button>'
        html += f'<a href="/skip/{i}" class="btn-skip">Skip</a></div></div>'

    html += "</div><!-- end outreach tab -->\n"

    # GRANTS TAB
    html += f"""
<!-- GRANTS TAB -->
<div id="content-grants" class="tab-content {'active' if active_tab=='grants' else ''}">
  <div class="grants-wrap">
    <div class="grants-topbar">
      <h2>💰 Live Grant Opportunities</h2>
      <div style="display:flex;gap:8px;align-items:center;">
        <span style="font-size:12px;color:#64748b;">{len(grants)} grants loaded</span>
        <form method="POST" action="/scan-grants" style="display:inline"><button type="submit" class="scan-btn">Scan Now</button></form>
        <a href="{URL_GRANTS}" target="_blank" class="btn-link" style="background:#374151;">Open Full Dashboard ↗</a>
      </div>
    </div>"""

    if not grants:
        html += '<div class="no-grants">No grants loaded yet. Click <strong>Scan Now</strong> to pull from Grants.gov.</div>'
    else:
        html += """
    <table>
      <thead>
        <tr>
          <th>Grant Name</th>
          <th>Agency</th>
          <th>Amount</th>
          <th>Deadline</th>
          <th>Match</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>"""
        for g in grants:
            score = g.get("match_score", 0) or 0
            if score >= 70:
                badge = f'<span class="badge badge-high">{score}%</span>'
            elif score >= 40:
                badge = f'<span class="badge badge-med">{score}%</span>'
            else:
                badge = f'<span class="badge badge-low">{score}%</span>'

            amt_min = g.get("amount_min") or 0
            amt_max = g.get("amount_max") or 0
            if amt_max:
                amt = f"${amt_max:,.0f}"
            elif amt_min:
                amt = f"${amt_min:,.0f}"
            else:
                amt = "—"

            deadline = g.get("deadline") or "—"
            if deadline and deadline != "—":
                deadline = deadline[:10]

            name    = (g.get("name") or "Unnamed Grant")[:60]
            agency  = (g.get("agency") or "")[:40]
            gid     = g.get("id", "")
            apply_url = f"{URL_GRANTS}/api/grants/{gid}/apply" if gid else "#"

            html += f"""
        <tr>
          <td><div class="grant-name">{name}</div><div class="grant-agency">{agency}</div></td>
          <td style="color:#64748b;font-size:12px;">{agency}</td>
          <td style="color:#4ade80;">{amt}</td>
          <td style="color:#94a3b8;">{deadline}</td>
          <td>{badge}</td>
          <td><a href="{URL_GRANTS}" target="_blank" class="scan-btn" style="font-size:11px;">Apply ↗</a></td>
        </tr>"""
        html += "</tbody></table>"

    html += """
  </div>
</div><!-- end grants tab -->

<script>
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(function(el){ el.classList.remove('active'); });
  document.querySelectorAll('.nav a[id^="tab-"]').forEach(function(el){ el.classList.remove('active'); });
  document.getElementById('content-' + name).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}
</script>
</body>
</html>"""

    return html

# =========================
# SCAN GRANTS ACTION
# =========================
@app.route('/scan-grants', methods=['POST'])
def scan_grants():
    try:
        resp = requests.post(f"{URL_GRANTS}/api/scan", timeout=10)
        print(f"[ScanGrants] Triggered: {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[ScanGrants] Error: {e}", flush=True)
    return redirect('/?tab=grants')

# =========================
# SEND ACTION
# =========================
@app.route('/send/<int:index>')
def send(index):
    df = load_data()

    if index >= len(df):
        return redirect('/')

    row = df.loc[index]

    send_email(
        row["email"],
        row["name"],
        row["company"],
        row["message"]
    )

    df.at[index, "status"] = "sent"
    save_data(df)

    return redirect('/')

# =========================
# SKIP ACTION
# =========================
@app.route('/skip/<int:index>')
def skip(index):
    df = load_data()

    if index < len(df):
        df.at[index, "status"] = "skipped"
        save_data(df)

    return redirect('/')

# =========================
# SENT LOG VIEW
# =========================
@app.route('/sent')
def sent_log_view():
    rows = []
    if os.path.exists(SENT_LOG):
        try:
            log_df = pd.read_csv(SENT_LOG).fillna("")
            rows = log_df.to_dict("records")
        except Exception:
            pass

    html = """
    <style>
        body { background:#0f172a; color:white; font-family:Arial; margin:0; }
        .header { text-align:center; padding:20px; font-size:22px; font-weight:bold; background:#020617; }
        table { width:90%; margin:20px auto; border-collapse:collapse; font-size:13px; }
        th { background:#1e293b; padding:10px; text-align:left; color:#38bdf8; }
        td { padding:9px 10px; border-bottom:1px solid #1e293b; }
        .ok { color:#22c55e; font-weight:bold; }
        .fail { color:#ef4444; font-weight:bold; }
        a.back { display:block; text-align:center; margin:16px; color:#38bdf8; }
    </style>
    <div class="header">Sent Log</div>
    <a class="back" href="/">← Back to Dashboard</a>
    """

    if not rows:
        html += '<p style="text-align:center;color:#64748b;">No emails sent yet.</p>'
    else:
        html += "<table><tr><th>Time</th><th>Company</th><th>Name</th><th>Email</th><th>Subject</th><th>Status</th><th>Error</th></tr>"
        for r in reversed(rows):
            success_val = str(r.get("success", "")).strip().lower()
            status_cell = '<span class="ok">SENT</span>' if success_val in ("true", "1", "yes") else '<span class="fail">FAILED</span>'
            html += f"<tr><td>{r.get('timestamp','')}</td><td>{r.get('company','')}</td><td>{r.get('name','')}</td><td>{r.get('email','')}</td><td>{r.get('subject','')}</td><td>{status_cell}</td><td>{r.get('error','')}</td></tr>"
        html += "</table>"

    return html

# =========================
# TEST EMAIL
# =========================
@app.route('/test-email')
def test_email():
    result = send_email(
        to_email="grayhorizonsenterprise@gmail.com",
        name="Alex",
        company="Gray Horizons Enterprise",
        message="This is a test message confirming the outreach system is live and sending correctly through SendGrid. If you received this, everything is working."
    )
    status = "SUCCESS — email delivered to grayhorizonsenterprise@gmail.com" if result else "FAILED — check /sent for the error details"
    color  = "#22c55e" if result else "#ef4444"
    return f"""
    <div style="background:#0f172a;color:white;font-family:Arial;min-height:100vh;display:flex;align-items:center;justify-content:center;">
        <div style="text-align:center;">
            <div style="font-size:22px;font-weight:bold;color:{color};margin-bottom:16px;">{status}</div>
            <a href="/" style="color:#38bdf8;">← Back to Dashboard</a>
            &nbsp;|&nbsp;
            <a href="/sent" style="color:#38bdf8;">View Sent Log</a>
        </div>
    </div>
    """

# =========================
# MANUAL REFRESH TRIGGER
# =========================
@app.route('/refresh')
def refresh():
    if not pipeline_running:
        threading.Thread(target=run_pipeline_once, daemon=True).start()
    return redirect('/')

# =========================
# DEBUG CONFIG (no secrets shown)
# =========================
@app.route('/debug')
def debug():
    sg_key    = os.getenv("SENDGRID_API_KEY", "")
    sender    = os.getenv("SENDER_EMAIL", "")
    sg_set    = "SET" if sg_key else "MISSING"
    sender_set = sender if sender else "MISSING"
    color_key  = "#22c55e" if sg_key else "#ef4444"
    color_sndr = "#22c55e" if sender else "#ef4444"
    return f"""
    <div style="background:#0f172a;color:white;font-family:Arial;padding:40px;">
        <h2 style="color:#38bdf8;">Config Check</h2>
        <p>SENDGRID_API_KEY: <strong style="color:{color_key};">{sg_set}</strong></p>
        <p>SENDER_EMAIL: <strong style="color:{color_sndr};">{sender_set}</strong></p>
        <p>DATA_DIR: {DATA_DIR}</p>
        <p>Pipeline running: {pipeline_running}</p>
        <br>
        <a href="/test-email" style="color:#38bdf8;">Run Test Email</a>
        &nbsp;|&nbsp;
        <a href="/sent" style="color:#38bdf8;">View Sent Log</a>
        &nbsp;|&nbsp;
        <a href="/" style="color:#38bdf8;">Dashboard</a>
    </div>
    """

# =========================
# HEALTH CHECK
# =========================
@app.route('/health')
def health():
    status = "running" if pipeline_running else "idle"
    leads = 0
    try:
        leads = len(pd.read_csv(CSV_FILE))
    except Exception:
        pass
    return f"OK | pipeline={status} | leads={leads}"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)