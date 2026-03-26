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
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_user = os.getenv("GMAIL_ADDRESS")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")
    subject = f"{company} — quick question"

    if not gmail_user or not gmail_pass:
        print("[SEND] ERROR: Missing GMAIL_ADDRESS or GMAIL_APP_PASSWORD env vars")
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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{gmail_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())
        print(f"[SEND] OK -> {to_email} ({company})")
        log_sent(to_email, name, company, subject, True)
        return True
    except Exception as e:
        print(f"[SEND] FAILED -> {to_email} | {e}")
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
            status_cell = '<span class="ok">SENT</span>' if str(r.get("success","")).lower() in ("true","1") else '<span class="fail">FAILED</span>'
            html += f"<tr><td>{r.get('timestamp','')}</td><td>{r.get('company','')}</td><td>{r.get('name','')}</td><td>{r.get('email','')}</td><td>{r.get('subject','')}</td><td>{status_cell}</td><td>{r.get('error','')}</td></tr>"
        html += "</table>"

    return html

# =========================
# MANUAL REFRESH TRIGGER
# =========================
@app.route('/refresh')
def refresh():
    if not pipeline_running:
        threading.Thread(target=run_pipeline_once, daemon=True).start()
    return redirect('/')

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