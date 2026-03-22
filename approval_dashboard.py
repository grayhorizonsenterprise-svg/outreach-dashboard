from flask import Flask, redirect
import pandas as pd
import os
import requests
import re

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"

# =========================
# EMAIL FINDER
# =========================
def find_email(company):
    try:
        res = requests.post("https://duckduckgo.com/html/", data={"q": f"{company} email"})
        emails = re.findall(r"[\\w\\.-]+@[\\w\\.-]+", res.text)
        return emails[0] if emails else ""
    except:
        return ""

# =========================
# FIX MESSAGE FORMATTING
# =========================
def format_message(msg):
    if not msg:
        return ""

    # Replace periods with line breaks for readability
    msg = msg.replace(". ", ".\n\n")

    # Preserve line breaks in HTML
    return msg.replace("\n", "<br>")

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

    # AUTO EMAIL FIND
    for i, row in df.iterrows():
        if not row["email"] and row["company"]:
            df.at[i, "email"] = find_email(row["company"])

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

    if not to_email:
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

    requests.post("https://api.sendgrid.com/v3/mail/send", json=data, headers=headers)

# =========================
# DASHBOARD
# =========================
@app.route('/')
def dashboard():
    df = load_data()
    save_data(df)

    html = """
    <style>
        body { background:#0f172a; color:white; font-family:Arial; }
        .card { background:#1e293b; padding:20px; margin:20px; border-radius:10px; }
        .title { font-size:20px; color:#38bdf8; }
        .company { color:#e2e8f0; }
        .email { color:#94a3b8; margin-bottom:10px; }
        .message { margin-top:10px; line-height:1.6; }
        .btn { padding:10px; border:none; border-radius:6px; cursor:pointer; }
        .send { background:#22c55e; }
        .skip { background:#ef4444; margin-left:10px; }
    </style>

    <h1 style="text-align:center;">Outreach Dashboard</h1>
    """

    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue

        html += f"""
        <div class="card">
            <div class="title">{row['name'] or "Contact"}</div>
            <div class="company">{row['company']}</div>
            <div class="email">{row['email'] or "No email found"}</div>

            <div class="message">{format_message(row['message'])}</div>

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
        row["email"],
        row["name"],
        row["company"],
        row["message"]
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)