from flask import Flask, redirect
import pandas as pd
import os

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"

# =========================
# SAFE DATA LOADER
# =========================
def load_data():
    try:
        if not os.path.exists(CSV_FILE):
            return pd.DataFrame(columns=["name", "email", "message", "status"])

        df = pd.read_csv(CSV_FILE)

        # Ensure required columns exist
        required_cols = ["name", "email", "message", "status"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Remove NaN safely
        df = df.fillna("")

        return df

    except Exception as e:
        print("LOAD ERROR:", e)
        return pd.DataFrame(columns=["name", "email", "message", "status"])


# =========================
# SAFE SAVE
# =========================
def save_data(df):
    try:
        df.to_csv(CSV_FILE, index=False)
    except Exception as e:
        print("SAVE ERROR:", e)


# =========================
# MAIN DASHBOARD
# =========================
@app.route('/')
def dashboard():
    df = load_data()

    html = """
    <h1 style="font-family:sans-serif;">HOA Outreach Dashboard</h1>
    """

    pending_found = False

    for i, row in df.iterrows():
        try:
            status = str(row.get("status", "")).lower()

            if status != "pending":
                continue

            pending_found = True

            name = row.get("name", "") or "No Name"
            email = row.get("email", "") or "No Email"
            message = row.get("message", "") or "No Message"

            html += f"""
            <div style="border:1px solid #ccc;padding:20px;margin:15px;border-radius:10px;font-family:sans-serif;">
                <h2>{name}</h2>
                <p><b>Email:</b> {email}</p>
                <p style="white-space:pre-wrap;">{message}</p>

                <a href="/send/{i}">
                    <button style="background:green;color:white;padding:12px 20px;font-size:16px;border:none;border-radius:5px;">
                        ✅ Send
                    </button>
                </a>

                <a href="/skip/{i}">
                    <button style="background:red;color:white;padding:12px 20px;font-size:16px;border:none;border-radius:5px;margin-left:10px;">
                        ❌ Skip
                    </button>
                </a>
            </div>
            """

        except Exception as e:
            print("ROW ERROR:", e)
            continue

    if not pending_found:
        html += "<p style='font-family:sans-serif;'>No pending outreach.</p>"

    return html


# =========================
# SEND (SAFE MODE — NO CRASH)
# =========================
@app.route('/send/<int:index>')
def send(index):
    try:
        df = load_data()

        if index >= len(df):
            return "Invalid index"

        # Mark as sent (no email yet = no crash risk)
        df.at[index, "status"] = "sent"
        save_data(df)

        return redirect('/')

    except Exception as e:
        return f"ERROR: {str(e)}"


# =========================
# SKIP
# =========================
@app.route('/skip/<int:index>')
def skip(index):
    try:
        df = load_data()

        if index >= len(df):
            return "Invalid index"

        df.at[index, "status"] = "skipped"
        save_data(df)

        return redirect('/')

    except Exception as e:
        return f"ERROR: {str(e)}"


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)