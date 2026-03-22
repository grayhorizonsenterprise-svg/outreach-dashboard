from flask import Flask, redirect
import pandas as pd
import os
import requests

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"

# =========================
# REAL EMAIL FINDER (HUNTER)
# =========================
def find_email(company):
    api_key = os.getenv("066f1a238c1325bf0c7aad6f5015149f50c58037")

    if not api_key or not company:
        return ""

    try:
        url = f"https://api.hunter.io/v2/domain-search?domain={company.replace(' ', '').lower()}.com&api_key={api_key}"
        r = requests.get(url).json()

        emails = r.get("data", {}).get("emails", [])
        if emails:
            return emails[0]["value"]

    except:
        pass

    return ""

# =========================
# LOAD DATA
# =========================
def load_data():
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

    # 🔥 REAL EMAIL ENRICHMENT
    for i, row in df.iterrows():
        if not row["email"] and row["company"]:
            email = find_email(row["company"])
            if email:
                df.at[i, "email"] = email

    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# SEND EMAIL
# =========================
def send_email(to_email, message):
    api_key = os.getenv("SENDGRID_API_KEY")
    sender = os.getenv("SENDER_EMAIL")

    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender},
        "subject": "Quick question",
        "content": [{"type": "text/plain", "value": message}]
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

    html = "<h1>Outreach Dashboard</h1>"

    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue

        html += f"""
        <div style="border:1px solid #ccc;padding:20px;margin:20px;">
            <h3>{row['company']}</h3>
            <p>{row['email'] or "Still searching..."}</p>
            <p>{row['message']}</p>

            <a href="/send/{i}">
                <button>Send</button>
            </a>

            <a href="/skip/{i}">
                <button>Skip</button>
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

    if row["email"]:
        send_email(row["email"], row["message"])
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