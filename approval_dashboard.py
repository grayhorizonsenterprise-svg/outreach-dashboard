from flask import Flask, redirect
import pandas as pd
import os
import requests

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"

# =========================
# LOAD DATA (SMART FIX)
# =========================
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["company","name","email","message","status"])

    df = pd.read_csv(CSV_FILE)

    # 🔥 AUTO-FIX COMMON COLUMN ISSUES
    column_map = {
        "Company": "company",
        "company_name": "company",
        "Name": "name",
        "Email": "email",
        "Message": "message"
    }

    df = df.rename(columns=column_map)

    # Ensure required columns exist
    for col in ["company","name","email","message","status"]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")

    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# SEND EMAIL
# =========================
def send_email(to_email, name, company, message):
    api_key = os.getenv("SENDGRID_API_KEY")
    sender = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons")

    subject = f"{company} — quick question"

    html = f"""
    <div style="font-family:Arial;line-height:1.6;">
        <p>Hi {name or "there"},</p>

        <p>{message}</p>

        <p>
        — {sender_name}<br>
        Gray Horizons Enterprise
        </p>
    </div>
    """

    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender, "name": sender_name},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}]
    }

    headers = {
        "Authorization": f"Bearer {api_key},
        "Content-Type": "application/json"
    }

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=data,
        headers=headers
    )

# =========================
# DASHBOARD (MODERN UI)
# =========================
@app.route('/')
def dashboard():
    df = load_data()

    html = """
    <style>
        body { font-family: Arial; background:#f5f7fa; }
        .card {
            background:white;
            padding:20px;
            margin:20px auto;
            border-radius:10px;
            width:80%;
            box-shadow:0 2px 8px rgba(0,0,0,0.1);
        }
        .title { font-size:22px; font-weight:bold; }
        .email { color:#555; margin-bottom:10px; }
        .btn {
            padding:10px 16px;
            border:none;
            border-radius:6px;
            cursor:pointer;
            font-size:14px;
        }
        .send { background:#28a745; color:white; }
        .skip { background:#dc3545; color:white; margin-left:10px; }
    </style>

    <h1 style="text-align:center;">Gray Horizons Outreach Dashboard</h1>
    """

    for i, row in df.iterrows():
        if str(row["status"]).lower() != "pending":
            continue

        html += f"""
        <div class="card">
            <div class="title">{row.get("company","No Company")}</div>
            <div class="email">{row.get("email","No Email")}</div>

            <p>{row.get("message","")}</p>

            <a href="/send/{i}">
                <button class="btn send">Send</button>
            </a>

            <a href="/skip/{i}">
                <button class="btn skip">Skip</button>
            </a>
        </div>
        """

    return html

# =========================
# SEND
# =========================
@app.route('/send/<int:index>')
def send(index):
    df = load_data()

    row = df.loc[index]

    send_email(
        row.get("email",""),
        row.get("name",""),
        row.get("company",""),
        row.get("message","")
    )

    df.at[index, "status"] = "sent"
    save_data(df)

    return redirect('/')

# =========================
# SKIP
# =========================
@app.route('/skip/<int:index>')
def skip(index):
    df = load_data()
    df.at[index, "status"] = "skipped"
    save_data(df)
    return redirect('/')

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)