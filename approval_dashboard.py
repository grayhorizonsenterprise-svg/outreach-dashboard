from flask import Flask, redirect
import pandas as pd
import os
import requests
import threading
import time
import subprocess
import sys

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
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
        print("[ENGINE] Sleeping 6 hours until next cycle.", flush=True)
        time.sleep(21600)

threading.Thread(target=run_pipeline_loop, daemon=True).start()

# =========================
# KEEP-ALIVE (prevents Render free tier from sleeping)
# =========================
def keep_alive():
    time.sleep(60)
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    port = os.getenv("PORT", "8080")
    target = render_url if render_url else f"http://127.0.0.1:{port}"
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
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
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
# DASHBOARD UI (FINAL CLEAN VERSION)
# =========================
@app.route('/')
def dashboard():
    df = load_data()

    pending_count = len(df[df["status"] == "pending"])
    sent_count    = len(df[df["status"] == "sent"])
    skipped_count = len(df[df["status"] == "skipped"])

    html = """
    <meta http-equiv="refresh" content="300">
    <style>
        body {
            background:#0f172a;
            color:white;
            font-family:Arial;
            margin:0;
        }

        .header {
            text-align:center;
            padding:20px;
            font-size:24px;
            font-weight:bold;
            background:#020617;
        }

        .stats {
            display:flex;
            justify-content:center;
            gap:30px;
            padding:12px;
            background:#0f172a;
            font-size:14px;
            color:#94a3b8;
        }

        .stat-val {
            font-weight:bold;
            color:#38bdf8;
        }

        .refresh-note {
            text-align:center;
            font-size:11px;
            color:#475569;
            padding-bottom:8px;
        }

        .top-bar {
            display:flex;
            justify-content:space-between;
            align-items:center;
            padding:10px 30px;
            background:#020617;
            border-bottom:1px solid #1e293b;
        }

        .refresh-btn {
            background:#3b82f6;
            color:white;
            border:none;
            padding:8px 18px;
            border-radius:6px;
            cursor:pointer;
            font-size:13px;
            text-decoration:none;
            display:inline-block;
        }

        .refresh-btn:hover { background:#2563eb; }

        .pipeline-status {
            font-size:12px;
            color:#64748b;
        }

        .pipeline-active { color:#22c55e; }

        .card {
            background:#1e293b;
            padding:20px;
            margin:20px auto;
            width:90%;
            max-width:700px;
            border-radius:10px;
        }

        .title {
            font-size:20px;
            color:#38bdf8;
            font-weight:bold;
        }

        .company {
            color:#e2e8f0;
        }

        .email {
            color:#94a3b8;
            margin-bottom:10px;
        }

        .message {
            margin-top:10px;
            line-height:1.6;
        }

        .btn {
            padding:10px 14px;
            border:none;
            border-radius:6px;
            cursor:pointer;
        }

        .send {
            background:#22c55e;
            color:white;
        }

        .skip {
            background:#ef4444;
            color:white;
            margin-left:10px;
        }

        .disabled {
            background:#555;
        }
    </style>

    <div class="header">Gray Horizons Outreach Dashboard</div>
    """

    status_text = '<span class="pipeline-active">Scraping new leads now...</span>' if pipeline_running else (
        f"Last run: {time.strftime('%I:%M %p', time.localtime(last_run_time))}" if last_run_time else "Starting soon..."
    )

    html += f"""
    <div class="top-bar">
        <div class="pipeline-status">{status_text}</div>
        <div class="stats" style="margin:0;padding:0;">
            <span>Pending: <span class="stat-val">{pending_count}</span></span>
            <span>Sent: <span class="stat-val">{sent_count}</span></span>
            <span>Skipped: <span class="stat-val">{skipped_count}</span></span>
        </div>
        <div style="display:flex;gap:10px;">
            <a href="/sent" class="refresh-btn" style="background:#7c3aed;">View Sent</a>
            <a href="/refresh" class="refresh-btn">{'Scraping...' if pipeline_running else 'Refresh Leads'}</a>
        </div>
    </div>
    <div class="refresh-note">Page auto-refreshes every 5 min &nbsp;|&nbsp; {len(df)} total leads</div>
    """

    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue

        name = row["name"] or "Contact"
        company = row["company"] or "Unknown Company"
        email = row["email"]

        html += f"""
        <div class="card">

            <div class="title">{name}</div>
            <div class="company">{company}</div>
            <div class="email">{email if email else "❌ No Email"}</div>

            <div class="message">{format_message(row["message"])}</div>
        """

        if email:
            html += f"""
            <a href="/send/{i}">
                <button class="btn send">Send</button>
            </a>
            """
        else:
            html += """
            <button class="btn disabled">No Email</button>
            """

        html += f"""
            <a href="/skip/{i}">
                <button class="btn skip">Skip</button>
            </a>

        </div>
        """

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