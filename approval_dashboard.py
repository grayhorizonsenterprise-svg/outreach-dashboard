from flask import Flask, redirect
import pandas as pd
import os
import requests

app = Flask(__name__)

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

    html = """
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