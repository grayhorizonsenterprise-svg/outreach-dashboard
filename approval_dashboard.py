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
    time.sleep(600)  # wait 10 min — let gunicorn fully stabilize before pipeline starts
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

    for col in ["company","name","email","message","status","niche"]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")
    df.loc[df["status"] == "", "status"] = "pending"
    # Tag all untagged rows as hoa (existing data pre-dates niche column)
    df.loc[df["niche"] == "", "niche"] = "hoa"

    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# FORMAT MESSAGE (FIX PARAGRAPHS)
# =========================
def format_message(msg):
    if not msg:
        return ""
    # Preserve paragraph breaks (double newline) and single line breaks
    # Do NOT break on every ". " — that makes emails look choppy
    paragraphs = msg.split("\n\n")
    parts = []
    for p in paragraphs:
        parts.append(p.replace("\n", "<br>"))
    return "</p><p style='margin:0 0 12px 0;'>".join(
        f"<p style='margin:0 0 12px 0;'>{p}</p>" for p in parts
    )

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

def _build_html_body(name, sender_name, message):
    return f"""
    <div style="font-family:Arial;line-height:1.6;">
        <p>Hi {name or 'there'},</p>
        <p>{format_message(message)}</p>
        <p>{sender_name}<br>Gray Horizons Enterprise</p>
    </div>
    """

def _send_via_sendgrid(api_key, sender_addr, sender_name, to_email, subject, html_body, name, company):
    # Force lowercase — SendGrid sender verification is case-sensitive
    verified_from = "grayhorizonsenterprise@gmail.com"
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": verified_from, "name": sender_name},
        "reply_to": {"email": verified_from, "name": sender_name},
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
            print(f"[SEND:SendGrid] OK -> {to_email} ({company})")
            log_sent(to_email, name, company, subject, True, "sendgrid")
            return True
        else:
            err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            print(f"[SEND:SendGrid] FAILED -> {to_email} | {err}")
            log_sent(to_email, name, company, subject, False, f"sendgrid: {err}")
            return False
    except Exception as e:
        print(f"[SEND:SendGrid] EXCEPTION -> {to_email} | {e}")
        log_sent(to_email, name, company, subject, False, f"sendgrid exception: {e}")
        return False

def _send_via_smtp(sender_addr, smtp_password, to_email, subject, html_body, name, company):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText as MIMETextPart
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender_addr
        msg["To"]      = to_email
        msg.attach(MIMETextPart(html_body, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(sender_addr, smtp_password)
        server.sendmail(sender_addr, to_email, msg.as_string())
        server.quit()
        print(f"[SEND:SMTP] OK -> {to_email} ({company})")
        log_sent(to_email, name, company, subject, True, "smtp")
        return True
    except Exception as e:
        print(f"[SEND:SMTP] EXCEPTION -> {to_email} | {e}")
        log_sent(to_email, name, company, subject, False, f"smtp: {e}")
        return False

def send_email(to_email, name, company, message):
    sender_addr = os.getenv("SENDER_EMAIL", "").strip()
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")
    subject     = f"{company} — quick question"

    if not sender_addr:
        print("[SEND] ERROR: SENDER_EMAIL not set")
        log_sent(to_email, name, company, subject, False, "SENDER_EMAIL not set")
        return False

    if not to_email or not str(to_email).strip():
        print("[SEND] ERROR: No recipient email")
        log_sent(to_email, name, company, subject, False, "no recipient")
        return False

    html_body = _build_html_body(name, sender_name, message)

    # ── Primary: SendGrid (if key is set) ─────────────────────────────────────
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    if api_key:
        return _send_via_sendgrid(api_key, sender_addr, sender_name,
                                  to_email, subject, html_body, name, company)

    # ── Fallback: Gmail SMTP (uses SENDER_APP_PASSWORD) ───────────────────────
    smtp_password = os.getenv("SENDER_APP_PASSWORD", "").strip()
    if smtp_password:
        print(f"[SEND] No SendGrid key — using Gmail SMTP for {to_email}")
        return _send_via_smtp(sender_addr, smtp_password,
                              to_email, subject, html_body, name, company)

    # ── Neither available ─────────────────────────────────────────────────────
    print("[SEND] ERROR: No sending method — set SENDGRID_API_KEY or SENDER_APP_PASSWORD")
    log_sent(to_email, name, company, subject, False,
             "no sending method: set SENDGRID_API_KEY or SENDER_APP_PASSWORD")
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
  html,body{{height:100%;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;overflow-x:hidden;}}
  .header{{background:#020617;padding:12px 16px;text-align:center;font-size:18px;font-weight:bold;border-bottom:1px solid #1e293b;}}
  /* Nav — scrollable on mobile */
  .nav{{display:flex;background:#020617;border-bottom:2px solid #1e293b;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;scrollbar-width:none;}}
  .nav::-webkit-scrollbar{{display:none;}}
  .nav a{{padding:10px 16px;color:#64748b;font-size:13px;text-decoration:none;cursor:pointer;border-bottom:3px solid transparent;display:inline-block;flex-shrink:0;}}
  .nav a.active{{color:#38bdf8;border-bottom:3px solid #38bdf8;font-weight:bold;}}
  .nav a.grants-tab{{color:#a78bfa;}}
  .nav a.grants-tab.active{{color:#a78bfa;border-bottom:3px solid #a78bfa;}}
  .topbar{{display:flex;justify-content:space-between;align-items:center;padding:8px 16px;background:#020617;border-bottom:1px solid #1e293b;flex-wrap:wrap;gap:6px;}}
  .stats{{display:flex;gap:12px;font-size:12px;color:#94a3b8;flex-wrap:wrap;}}
  .stat-val{{color:#38bdf8;font-weight:bold;}}
  .btn-link{{background:#3b82f6;color:white;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;}}
  .btn-link:hover{{background:#2563eb;}}
  .tab-content{{display:none;}}
  .tab-content.active{{display:block;}}

  /* Outreach cards */
  .card{{background:#1e293b;padding:16px;margin:12px auto;width:94%;max-width:720px;border-radius:10px;}}
  .card-title{{font-size:16px;color:#38bdf8;font-weight:bold;}}
  .card-sub{{color:#94a3b8;font-size:12px;margin:4px 0 8px;}}
  .card-msg{{line-height:1.6;font-size:13px;word-break:break-word;}}
  .btn-send{{background:#22c55e;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;}}
  .btn-skip{{background:#ef4444;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;margin-left:8px;}}
  .btn-disabled{{background:#475569;color:#94a3b8;border:none;padding:9px 16px;border-radius:6px;font-size:13px;margin-top:10px;}}
  .note{{text-align:center;font-size:11px;color:#475569;padding:6px;}}
  .niche-filters{{display:flex;gap:8px;flex-wrap:wrap;padding:10px 16px;background:#020617;border-bottom:1px solid #1e293b;}}
  .nf-btn{{background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:6px 14px;border-radius:20px;cursor:pointer;font-size:12px;font-weight:600;}}
  .nf-btn:hover{{background:#334155;color:#e2e8f0;}}
  .nf-btn.active{{background:#38bdf8;color:#000;border-color:#38bdf8;}}
  .niche-badge{{font-size:10px;font-weight:bold;padding:2px 8px;border-radius:10px;text-transform:uppercase;}}
  .niche-hoa{{background:#1e3a5f;color:#60a5fa;}}
  .niche-hvac{{background:#1a2e1a;color:#4ade80;}}
  .niche-dental{{background:#2d1a3a;color:#c084fc;}}
  .niche-plumbing{{background:#2a1f0a;color:#fbbf24;}}
  .niche-contractor{{background:#2a1515;color:#f87171;}}

  /* Grant iframe wrapper */
  .grants-iframe-wrap{{position:relative;width:100%;height:calc(100vh - 90px);overflow:auto;-webkit-overflow-scrolling:touch;}}
  .grants-iframe-wrap iframe{{width:100%;height:100%;border:none;display:block;}}
  /* Mobile fallback — shown only on small screens */
  .grants-mobile-fallback{{display:none;padding:32px 20px;text-align:center;}}
  .grants-mobile-fallback a{{display:inline-block;background:#7c3aed;color:white;padding:14px 28px;border-radius:8px;font-size:15px;font-weight:bold;text-decoration:none;margin-top:12px;}}
  @media(max-width:640px){{
    .grants-iframe-wrap{{display:none;}}
    .grants-mobile-fallback{{display:block;}}
    .header{{font-size:15px;padding:10px;}}
    .nav a{{padding:8px 12px;font-size:12px;}}
    .card{{padding:14px;}}
    .topbar{{padding:8px 12px;}}
    .stats{{gap:8px;font-size:11px;}}
  }}

  /* Grants table (legacy, kept for reference) */
  .grants-wrap{{padding:16px 20px;}}
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
  <a onclick="showTab('outreach')" id="tab-outreach" class="{'active' if active_tab=='outreach' else ''}">Outreach ({pending_count} pending)</a>
  <a onclick="showTab('grants')"   id="tab-grants"   class="grants-tab {'active' if active_tab=='grants' else ''}">💰 Grant Agent</a>
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
      <a href="/resend-failed" class="btn-link" style="background:#f59e0b;color:#000;">Resend Failed</a>
      <a href="/refresh" class="btn-link">{'Scraping...' if pipeline_running else 'Refresh Leads'}</a>
    </div>
  </div>
  <div class="note">{len(df)} total leads · auto-refreshes every 5 min</div>
  <div class="niche-filters">
    <button class="nf-btn active" onclick="filterNiche('all',this)">All Niches</button>
    <button class="nf-btn" onclick="filterNiche('hoa',this)">HOA</button>
    <button class="nf-btn" onclick="filterNiche('hvac',this)">HVAC</button>
    <button class="nf-btn" onclick="filterNiche('dental',this)">Dental</button>
    <button class="nf-btn" onclick="filterNiche('plumbing',this)">Plumbing</button>
    <button class="nf-btn" onclick="filterNiche('contractor',this)">Contractor</button>
  </div>
"""

    # Empty state when nothing is pending
    pending_rows = df[df["status"] == "pending"]
    if len(pending_rows) == 0:
        scraping_msg = "Pipeline is scraping new leads now — check back in a few minutes." if pipeline_running else "No pending leads. Click Refresh Leads to scrape new ones."
        html += f"""
  <div style="text-align:center;padding:60px 20px;color:#64748b;">
    <div style="font-size:2rem;margin-bottom:12px;">{'⏳' if pipeline_running else '🔄'}</div>
    <div style="font-size:16px;color:#94a3b8;margin-bottom:8px;">{scraping_msg}</div>
    <div style="font-size:13px;">Sent: {sent_count} · Skipped: {skipped_count}</div>
  </div>"""

    # Outreach lead cards
    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue
        name    = row.get("name", "") or "Contact"
        company = row.get("company", "") or "Unknown Company"
        email   = row.get("email", "")
        niche   = str(row.get("niche", "hoa") or "hoa").strip().lower()
        html += f"""
  <div class="card" data-niche="{niche}">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div class="card-title">{company}</div>
      <span class="niche-badge niche-{niche}">{niche.upper()}</span>
    </div>
    <div class="card-sub">{email if email else '❌ No Email'}</div>
    <div class="card-msg">{format_message(row["message"])}</div>
    <div>"""
        if email:
            html += f'<a href="/send/{i}" class="btn-send">Send</a>'
        else:
            html += '<button class="btn-disabled">No Email</button>'
        html += f'<a href="/skip/{i}" class="btn-skip">Skip</a></div></div>'

    html += "</div><!-- end outreach tab -->\n"

    # GRANTS TAB — full grant agent embedded as iframe (desktop) + link (mobile)
    html += f"""
<!-- GRANTS TAB -->
<div id="content-grants" class="tab-content {'active' if active_tab=='grants' else ''}">
  <!-- Desktop: full embedded grant agent -->
  <div class="grants-iframe-wrap">
    <iframe
      id="grants-iframe"
      src="{URL_GRANTS}"
      title="Grant Agent System"
      loading="lazy"
      allowfullscreen
    ></iframe>
  </div>
  <!-- Mobile: tap to open in full browser -->
  <div class="grants-mobile-fallback">
    <div style="font-size:32px;margin-bottom:12px;">💰</div>
    <div style="font-size:18px;font-weight:bold;color:#a78bfa;margin-bottom:8px;">Grant Agent System</div>
    <div style="color:#94a3b8;font-size:14px;margin-bottom:20px;">12 curated grants · SBIR · MBDA · SBA 8(a) · Google Black Founders Fund</div>
    <a href="{URL_GRANTS}" target="_blank">Open Grant Agent ↗</a>
    <div style="color:#475569;font-size:12px;margin-top:16px;">Opens full dashboard with scan, apply, and AI application tools</div>
  </div>
</div><!-- end grants tab -->

<script>
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(function(el){{ el.classList.remove('active'); }});
  document.querySelectorAll('.nav a[id^="tab-"]').forEach(function(el){{ el.classList.remove('active'); }});
  document.getElementById('content-' + name).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

function filterNiche(niche, btn) {{
  document.querySelectorAll('.nf-btn').forEach(function(b){{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(function(card) {{
    if (niche === 'all' || card.dataset.niche === niche) {{
      card.style.display = '';
    }} else {{
      card.style.display = 'none';
    }}
  }});
}}
</script>
</body>
</html>"""

    return html

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

    # Compute stats for the banner
    total_entries = len(rows)
    sent_count_log = sum(
        1 for r in rows
        if str(r.get("success", r.get("status", ""))).strip().lower()
        in ("true", "1", "smtp", "sendgrid", "gmail-smtp-accepted")
    )
    failed_count_log = sum(
        1 for r in rows
        if str(r.get("success", r.get("status", ""))).strip().lower()
        in ("false", "0", "")
        and str(r.get("error", r.get("note", ""))).strip().lower() not in ("skipped", "no email address found")
    )

    html = f"""
    <style>
        body {{ background:#0f172a; color:white; font-family:Arial; margin:0; }}
        .header {{ text-align:center; padding:20px; font-size:22px; font-weight:bold; background:#020617; }}
        .stats-bar {{ display:flex; gap:16px; justify-content:center; flex-wrap:wrap; padding:16px; background:#020617; border-bottom:1px solid #1e293b; }}
        .stat-box {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:12px 24px; text-align:center; }}
        .stat-num {{ font-size:28px; font-weight:bold; }}
        .stat-lbl {{ font-size:11px; color:#64748b; margin-top:4px; }}
        .notice {{ background:#1e293b; border-left:4px solid #f59e0b; margin:16px auto; width:92%; max-width:860px; padding:12px 16px; border-radius:6px; font-size:13px; color:#cbd5e1; line-height:1.6; }}
        .verify-btn {{ display:block; text-align:center; margin:12px auto; }}
        .verify-btn a {{ background:#22c55e; color:#000; font-weight:bold; padding:10px 28px; border-radius:8px; text-decoration:none; font-size:14px; }}
        .wrap {{ overflow-x:auto; width:96%; margin:20px auto; }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; min-width:900px; }}
        th {{ background:#1e293b; padding:10px; text-align:left; color:#38bdf8; white-space:nowrap; }}
        td {{ padding:9px 10px; border-bottom:1px solid #1e293b; vertical-align:top; }}
        td.err {{ color:#f87171; font-size:12px; max-width:340px; word-break:break-word; white-space:pre-wrap; }}
        .ok   {{ color:#22c55e; font-weight:bold; }}
        .fail {{ color:#ef4444; font-weight:bold; }}
        a.back {{ display:inline-block; margin:8px 12px; color:#38bdf8; }}
    </style>
    <div class="header">Outreach Sent Log</div>
    <div class="stats-bar">
        <div class="stat-box">
            <div class="stat-num" style="color:#22c55e;">{sent_count_log}</div>
            <div class="stat-lbl">Accepted by Gmail SMTP</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#ef4444;">{failed_count_log}</div>
            <div class="stat-lbl">Failed to Send</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#94a3b8;">{total_entries}</div>
            <div class="stat-lbl">Total Log Entries</div>
        </div>
    </div>
    <div class="notice">
        <strong style="color:#f59e0b;">What "SENT" means:</strong>
        Gmail's SMTP server accepted the message — the email left this system successfully.
        Inbox delivery depends on the recipient's spam filters. To get open/click/bounce tracking,
        connect <a href="https://sendgrid.com" target="_blank" style="color:#38bdf8;">SendGrid</a>
        (free tier: 100/day) by adding <code>SENDGRID_API_KEY</code> to your .env file.
        &nbsp;&nbsp;<strong>→</strong>&nbsp;
        <a href="/test-email" style="color:#22c55e;font-weight:bold;">Send live test email to your inbox now</a>
    </div>
    <div style="text-align:center;margin:8px 0;">
        <a class="back" href="/">&#8592; Dashboard</a>
        <a class="back" href="/resend-failed" style="color:#f59e0b;">Resend Failed</a>
        <a class="back" href="/test-email" style="color:#22c55e;">&#10003; Send Test Email</a>
    </div>
    """

    if not rows:
        html += '<p style="text-align:center;color:#64748b;">No emails sent yet.</p>'
    else:
        # also check old-format column names (status/note vs success/error)
        html += "<div class='wrap'><table><tr><th>Time</th><th>Company</th><th>Email</th><th>Subject</th><th>Status</th><th>Error / Detail</th></tr>"
        for r in reversed(rows):
            success_raw = str(r.get("success", r.get("status", ""))).strip().lower()
            error_msg   = str(r.get("error",   r.get("note",   ""))).strip()
            if success_raw in ("true", "1", "yes", "smtp", "sendgrid"):
                status_cell = '<span class="ok">SENT</span>'
            elif success_raw in ("skipped",):
                status_cell = '<span style="color:#94a3b8;font-weight:bold;">SKIPPED</span>'
            else:
                status_cell = '<span class="fail">FAILED</span>'
            company = str(r.get("company", r.get("company_name", ""))).strip()
            email   = str(r.get("email", "")).strip()
            subject = str(r.get("subject", "")).strip()
            ts      = str(r.get("timestamp", "")).strip()
            html += (
                "<tr>"
                "<td style='white-space:nowrap;color:#94a3b8;font-size:11px;'>" + ts + "</td>"
                "<td>" + company + "</td>"
                "<td style='color:#7dd3fc;'>" + email + "</td>"
                "<td style='color:#cbd5e1;font-size:12px;'>" + subject + "</td>"
                "<td>" + status_cell + "</td>"
                "<td class='err'>" + error_msg + "</td>"
                "</tr>"
            )
        html += "</table></div>"

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
# RESEND FAILED EMAILS
# GET  /resend-failed        — preview page showing what will be resent
# POST /resend-failed        — fire the actual resend batch
# =========================

def _get_failed_emails_from_log():
    """Return set of email addresses that have a failed delivery in sent_log.csv."""
    failed = set()
    if not os.path.exists(SENT_LOG):
        return failed
    try:
        import csv as _csv
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                # Handle both old format (status/note) and new format (success/error)
                success_raw = (
                    row.get("success", "") or
                    row.get("status",  "")
                ).strip().lower()
                email = (row.get("email", "") or "").strip().lower()
                if email and success_raw in ("false", "0", ""):
                    failed.add(email)
    except Exception as e:
        print(f"[resend] Could not parse sent_log: {e}")
    return failed


def _do_resend_batch(dry_run=False):
    """
    Find every queue row whose email appears in the failed-log set, then resend.
    Returns list of result dicts.
    """
    failed_emails = _get_failed_emails_from_log()
    df            = load_data()
    results       = []

    for i, row in df.iterrows():
        email = str(row.get("email", "") or "").strip().lower()
        if not email:
            continue
        # Resend if: email is in the failed set, OR status is "sent" with no prior success
        in_failed_log = email in failed_emails
        was_marked_sent = str(row.get("status", "")).strip().lower() == "sent"
        if not (in_failed_log or was_marked_sent):
            continue

        company = row.get("company", "Unknown")
        name    = row.get("name",    "")
        message = row.get("message", "")

        if dry_run:
            results.append({"email": email, "company": company, "status": "preview — not sent"})
            continue

        ok = send_email(email, name, company, message)
        results.append({
            "email":   email,
            "company": company,
            "status":  "SENT" if ok else "FAILED",
        })
        # Keep queue row as "sent" regardless — delivery status is in sent_log
        df.at[i, "status"] = "sent"

    if not dry_run and results:
        save_data(df)

    return results


@app.route('/resend-failed', methods=["GET"])
def resend_failed_preview():
    """Show a confirmation page listing what will be resent."""
    preview = _do_resend_batch(dry_run=True)
    count   = len(preview)

    rows_html = "".join(
        "<tr><td style='padding:8px;border-bottom:1px solid #1e293b;'>" + r['company'] + "</td>"
        "<td style='padding:8px;border-bottom:1px solid #1e293b;'>" + r['email'] + "</td></tr>"
        for r in preview
    )

    if count == 0:
        body_html = '<p style="color:#22c55e;font-size:15px;">Nothing to resend — no failed emails found.</p>'
    else:
        body_html = (
            '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;">'
            '<tr>'
            '<th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Company</th>'
            '<th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Email</th>'
            '</tr>'
            + rows_html +
            '</table>'
            '<form method="POST" action="/resend-failed">'
            '<button type="submit" style="background:#22c55e;color:white;border:none;'
            'padding:14px 28px;border-radius:8px;font-size:15px;font-weight:bold;'
            'cursor:pointer;width:100%;">Send All ' + str(count) + ' Email(s) Now</button>'
            '</form>'
        )

    return (
        '<div style="background:#0f172a;color:#e2e8f0;font-family:Arial;min-height:100vh;padding:40px 20px;">'
        '<div style="max-width:700px;margin:0 auto;">'
        '<h2 style="color:#f59e0b;margin-bottom:8px;">Resend Failed Emails</h2>'
        '<p style="color:#94a3b8;margin-bottom:24px;">Found <strong style="color:#f59e0b;">'
        + str(count) +
        '</strong> email(s) queued for resend. These previously failed delivery. '
        'Click the button below to send them now via Gmail SMTP.</p>'
        + body_html +
        '<br><br><a href="/" style="color:#38bdf8;">Back to Dashboard</a>'
        '&nbsp;|&nbsp;<a href="/sent" style="color:#38bdf8;">View Sent Log</a>'
        '</div></div>'
    )


@app.route('/resend-failed', methods=["POST"])
def resend_failed_execute():
    """Fire the actual resend batch and show results."""
    results = _do_resend_batch(dry_run=False)
    sent_ok  = [r for r in results if r["status"] == "SENT"]
    failed   = [r for r in results if r["status"] == "FAILED"]

    rows_html = "".join(
        f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">{r['company']}</td>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">{r['email']}</td>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">
            <span style="color:{'#22c55e' if r['status']=='SENT' else '#ef4444'};font-weight:bold;">
              {r['status']}
            </span>
          </td>
        </tr>"""
        for r in results
    )

    summary_color = "#22c55e" if not failed else "#f59e0b"
    summary_text  = (
        f"All {len(sent_ok)} emails sent successfully." if not failed
        else f"{len(sent_ok)} sent · {len(failed)} still failing — check env vars below."
    )

    return f"""
    <div style="background:#0f172a;color:#e2e8f0;font-family:Arial;min-height:100vh;padding:40px 20px;">
      <div style="max-width:700px;margin:0 auto;">
        <h2 style="color:{summary_color};margin-bottom:8px;">Resend Complete</h2>
        <p style="margin-bottom:24px;">{summary_text}</p>

        {'<div style="background:#1e293b;padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:13px;color:#f59e0b;">Still failing? Go to <a href="/debug" style="color:#38bdf8;">/debug</a> and confirm SENDER_EMAIL and SENDER_APP_PASSWORD are set.</div>' if failed else ''}

        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px;">
          <tr>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Company</th>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Email</th>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Result</th>
          </tr>
          {rows_html}
        </table>

        <a href="/" style="color:#38bdf8;">← Back to Dashboard</a>
        &nbsp;|&nbsp;
        <a href="/sent" style="color:#38bdf8;">View Sent Log</a>
        &nbsp;|&nbsp;
        <a href="/resend-failed" style="color:#f59e0b;">Resend Again</a>
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
    sg_key      = os.getenv("SENDGRID_API_KEY",    "").strip()
    sender      = os.getenv("SENDER_EMAIL",         "").strip()
    smtp_pass   = os.getenv("SENDER_APP_PASSWORD",  "").strip()
    sender_name = os.getenv("SENDER_NAME",          "").strip()

    def row(label, value, ok):
        color = "#22c55e" if ok else "#ef4444"
        icon  = "&#10003;" if ok else "&#10007; MISSING"
        return (
            "<tr>"
            "<td style='padding:10px 16px;color:#94a3b8;'>" + label + "</td>"
            "<td style='padding:10px 16px;'><strong style='color:" + color + ";'>" +
            (value if ok else icon) + "</strong></td>"
            "</tr>"
        )

    sg_ok    = bool(sg_key)
    smtp_ok  = bool(smtp_pass)
    send_ok  = bool(sender)

    method = "SendGrid" if sg_ok else ("Gmail SMTP" if smtp_ok else "NONE — emails will fail")
    method_color = "#22c55e" if (sg_ok or smtp_ok) else "#ef4444"

    rows = (
        row("SENDER_EMAIL",        sender    if send_ok  else "",  send_ok)  +
        row("SENDER_APP_PASSWORD", "SET (" + str(len(smtp_pass)) + " chars)" if smtp_ok else "", smtp_ok) +
        row("SENDGRID_API_KEY",    "SET"     if sg_ok    else "not set (optional)", sg_ok) +
        row("SENDER_NAME",         sender_name if sender_name else "Gray Horizons (default)", True)
    )

    return (
        "<div style='background:#0f172a;color:white;font-family:Arial;padding:40px;'>"
        "<h2 style='color:#38bdf8;margin-bottom:4px;'>Config Check</h2>"
        "<p style='color:#94a3b8;margin-bottom:24px;'>Active send method: "
        "<strong style='color:" + method_color + ";'>" + method + "</strong></p>"
        "<table style='border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;margin-bottom:24px;'>"
        + rows +
        "</table>"
        "<p style='color:#64748b;font-size:13px;'>DATA_DIR: " + DATA_DIR + "</p>"
        "<p style='color:#64748b;font-size:13px;'>Pipeline running: " + str(pipeline_running) + "</p>"
        "<br>"
        "<a href='/test-email' style='color:#38bdf8;margin-right:16px;'>Run Test Email</a>"
        "<a href='/sent'       style='color:#38bdf8;margin-right:16px;'>View Sent Log</a>"
        "<a href='/resend-failed' style='color:#f59e0b;margin-right:16px;'>Resend Failed</a>"
        "<a href='/'           style='color:#38bdf8;'>Dashboard</a>"
        "</div>"
    )

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