from flask import Flask, redirect
import pandas as pd
import os
import requests
import threading
import time

app = Flask(__name__)

# =========================
# KEEP-ALIVE (prevents Render free tier from sleeping)
# Pings /health every 10 minutes
# =========================
def keep_alive():
    time.sleep(30)  # wait for server to start
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    local_url  = f"http://127.0.0.1:{os.getenv('PORT', 8080)}"
    target = render_url or local_url
    while True:
        try:
            requests.get(f"{target}/health", timeout=10)
        except Exception:
            pass
        time.sleep(600)  # every 10 minutes

threading.Thread(target=keep_alive, daemon=True).start()

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
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
def send_email(to_email, name, company, message):
    api_key = os.getenv("SENDGRID_API_KEY")
    sender = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")

    if not api_key or not sender or not to_email:
        print("Missing email config or recipient")
        return

    html = f"""
    <div style="font-family:Arial;line-height:1.6;">
        <p>Hi {name or 'there'},</p>
        <p>{format_message(message)}</p>
        <p>— {sender_name}<br>Gray Horizons Enterprise</p>
    </div>
    """

    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender, "name": sender_name},
        "subject": f"{company} — quick question",
        "content": [{"type": "text/html", "value": html}]
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        requests.post("https://api.sendgrid.com/v3/mail/send", json=data, headers=headers)
    except Exception as e:
        print("Send error:", e)

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

    html += f"""
    <div class="stats">
        <span>Pending: <span class="stat-val">{pending_count}</span></span>
        <span>Sent: <span class="stat-val">{sent_count}</span></span>
        <span>Skipped: <span class="stat-val">{skipped_count}</span></span>
        <span>Total: <span class="stat-val">{len(df)}</span></span>
    </div>
    <div class="refresh-note">Auto-refreshes every 5 minutes</div>
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
# HEALTH CHECK
# =========================
@app.route('/health')
def health():
    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)