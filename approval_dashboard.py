from flask import Flask, redirect
import pandas as pd
import os
import requests
from datetime import datetime

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"
LOG_FILE = "sent_log.csv"

# =========================
# LOAD + AUTO FIX DATA
# =========================
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["company","name","email","message","status"])

    try:
        df = pd.read_csv(CSV_FILE)
    except:
        return pd.DataFrame(columns=["company","name","email","message","status"])

    # normalize column names
    mapping = {}
    for col in df.columns:
        c = col.lower()
        if "company" in c:
            mapping[col] = "company"
        elif "name" in c:
            mapping[col] = "name"
        elif "email" in c:
            mapping[col] = "email"
        elif "message" in c or "body" in c:
            mapping[col] = "message"
        elif "status" in c:
            mapping[col] = "status"

    df = df.rename(columns=mapping)

    for col in ["company","name","email","message","status"]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")

    df.loc[df["status"] == "", "status"] = "pending"
    df["name"] = df["name"].replace("", "Outreach Contact")

    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# LOG SENT EMAILS
# =========================
def log_sent(row):
    entry = pd.DataFrame([{
        "company": row.get("company",""),
        "email": row.get("email",""),
        "time": datetime.now().isoformat()
    }])

    if os.path.exists(LOG_FILE):
        existing = pd.read_csv(LOG_FILE)
        entry = pd.concat([existing, entry])

    entry.to_csv(LOG_FILE, index=False)

# =========================
# SEND EMAIL (SENDGRID)
# =========================
def send_email(to_email, name, company, message):
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender = os.getenv("SENDER_EMAIL")
        sender_name = os.getenv("SENDER_NAME", "Gray Horizons")

        if not api_key or not sender:
            print("Missing SendGrid config")
            return

        if not to_email:
            print("Missing recipient email")
            return

        subject = f"{company or 'Quick question'}"

        html = f"""
        <div style="font-family:Arial;">
            <p>Hi {name},</p>
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

        print("SEND STATUS:", response.status_code)

    except Exception as e:
        print("SEND ERROR:", str(e))

# =========================
# DASHBOARD UI
# =========================
@app.route('/')
def dashboard():
    df = load_data()

    html = """
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #0f172a;
            color: white;
            margin: 0;
        }

        .header {
            background: #020617;
            padding: 20px;
            text-align: center;
            font-size: 22px;
            font-weight: bold;
            border-bottom: 1px solid #1e293b;
        }

        .card {
            background: #1e293b;
            padding: 20px;
            margin: 20px auto;
            width: 90%;
            max-width: 700px;
            border-radius: 10px;
        }

        .title {
            font-size: 22px;
            font-weight: bold;
            color: #38bdf8;
        }

        .company {
            font-size: 16px;
            color: #e2e8f0;
        }

        .email {
            font-size: 14px;
            color: #94a3b8;
            margin-bottom: 15px;
        }

        .message {
            margin-bottom: 15px;
        }

        .btn {
            padding: 12px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
        }

        .send {
            background: #22c55e;
            color: white;
        }

        .skip {
            background: #ef4444;
            color: white;
            margin-left: 10px;
        }
    </style>

    <div class="header">Gray Horizons Outreach Dashboard</div>
    """

    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue

        title = row["name"]
        company = row["company"] or "Unknown Company"
        email = row["email"] or "⚠ Missing Email"
        message = row["message"]

        html += f"""
        <div class="card">

            <div class="title">{title}</div>
            <div class="company">{company}</div>
            <div class="email">{email}</div>

            <div class="message">{message}</div>

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
        row["email"],
        row["name"],
        row["company"],
        row["message"]
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
# HEALTH CHECK
# =========================
@app.route('/health')
def health():
    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)