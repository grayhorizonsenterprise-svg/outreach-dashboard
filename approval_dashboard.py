from flask import Flask, redirect
import pandas as pd
import os
import requests
from datetime import datetime

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"
LOG_FILE = "sent_log.csv"

# =========================
# LOAD DATA (SAFE)
# =========================
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["company","name","email","message","status"])

    df = pd.read_csv(CSV_FILE)

    # Fix column names automatically
    df = df.rename(columns={
        "Company": "company",
        "Email": "email",
        "Message": "message",
        "Name": "name"
    })

    # Ensure all required columns exist
    for col in ["company","name","email","message","status"]:
        if col not in df.columns:
            df[col] = ""

    return df.fillna("")


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# LOG SENT EMAILS
# =========================
def log_sent(row):
    log_entry = pd.DataFrame([{
        "company": row.get("company",""),
        "email": row.get("email",""),
        "time": datetime.now().isoformat()
    }])

    if os.path.exists(LOG_FILE):
        existing = pd.read_csv(LOG_FILE)
        log_entry = pd.concat([existing, log_entry])

    log_entry.to_csv(LOG_FILE, index=False)

# =========================
# SEND EMAIL (SENDGRID)
# =========================
def send_email(to_email, name, company, message):
    api_key = os.getenv("SENDGRID_API_KEY")
    sender = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")

    subject = f"{company} — quick question"

    html = f"""
    <div style="font-family:Arial;">
        <p>Hi {name or "there"},</p>
        <p>{message}</p>
        <p>— {sender_name}<br>Gray Horizons Enterprise</p>
    </div>
    """

    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender, "name": sender_name},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}]
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=data,
        headers=headers
    )

    if response.status_code != 202:
        print("EMAIL ERROR:", response.text)

# =========================
# DASHBOARD UI
# =========================
@app.route('/')
def dashboard():
    df = load_data()

    html = """
    <style>
        body { font-family:Arial; background:#f4f6f8; margin:0; }
        .header {
            background:#111;
            color:white;
            padding:15px;
            text-align:center;
            font-size:20px;
        }
        .card {
            background:white;
            padding:20px;
            margin:20px auto;
            width:90%;
            max-width:700px;
            border-radius:10px;
            box-shadow:0 2px 8px rgba(0,0,0,0.1);
        }
        .company { font-size:20px; font-weight:bold; }
        .email { color:#555; margin-bottom:10px; }
        .btn {
            padding:12px;
            border:none;
            border-radius:6px;
            font-size:14px;
            cursor:pointer;
        }
        .send { background:#28a745; color:white; }
        .skip { background:#dc3545; color:white; margin-left:10px; }
    </style>

    <div class="header">Gray Horizons Outreach Dashboard</div>
    """

    for i, row in df.iterrows():
        if str(row["status"]).lower() != "pending":
            continue

        html += f"""
        <div class="card">
            <div class="company">{row.get("company","No Company")}</div>
            <div class="email">{row.get("email","No Email")}</div>

            <p>{row.get("message","")}</p>

            <a href="/send/{i}">
                <button class="btn send">Approve & Send</button>
            </a>

            <a href="/skip/{i}">
                <button class="btn skip">Reject</button>
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
        row.get("email",""),
        row.get("name",""),
        row.get("company",""),
        row.get("message","")
    )

    df.at[index, "status"] = "sent"
    save_data(df)
    log_sent(row)

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
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)