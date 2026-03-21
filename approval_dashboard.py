from flask import Flask, request, redirect
import pandas as pd

app = Flask(__name__)

CSV_FILE = "outreach_queue.csv"

def load_data():
    return pd.read_csv(CSV_FILE)

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

@app.route('/')
def dashboard():
    df = load_data()

    rows = ""
    for i, row in df.iterrows():
        if row.get("status", "") != "pending":
            continue

        rows += f"""
        <div style="border:1px solid #ccc;padding:15px;margin:10px;">
            <h3>{row.get('name','')}</h3>
            <p><b>Email:</b> {row.get('email','')}</p>
            <p>{row.get('message','')}</p>

            <a href="/send/{i}">
                <button style="background:green;color:white;padding:10px;">
                    ✅ Send
                </button>
            </a>

            <a href="/skip/{i}">
                <button style="background:red;color:white;padding:10px;">
                    ❌ Skip
                </button>
            </a>
        </div>
        """

    return f"<h1>Outreach Approval Dashboard</h1>{rows}"

@app.route('/send/<int:index>')
def send(index):
    df = load_data()

    # TEMP: mark as sent (email sending comes next step)
    df.at[index, "status"] = "sent"
    save_data(df)

    return redirect('/')

@app.route('/skip/<int:index>')
def skip(index):
    df = load_data()

    df.at[index, "status"] = "skipped"
    save_data(df)

    return redirect('/')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)