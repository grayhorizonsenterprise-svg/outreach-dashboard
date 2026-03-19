from flask import Flask, request, redirect
import pandas as pd
import os

app = Flask(__name__)

FILE = "outreach_queue.csv"


def load_data():
    if not os.path.exists(FILE):
        return pd.DataFrame()

    df = pd.read_csv(FILE)

    if "approved_to_send" not in df.columns:
        df["approved_to_send"] = "NO"

    df = df.fillna("")
    return df


def save_data(df):
    df.to_csv(FILE, index=False)


@app.route("/")
def dashboard():

    df = load_data()

    if df.empty:
        return "<h2 style='color:white;'>No outreach messages. Run pipeline first.</h2>"

    html = """
    <html>
    <head>
    <title>Gray Horizons Outreach Console</title>
    <style>
        body {
            background: linear-gradient(135deg, #0b1f2a, #0f2f3f);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
            color: white;
            padding: 30px;
        }

        .header {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 30px;
        }

        .sub {
            color: #9ca3af;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(18,52,71,0.85);
            backdrop-filter: blur(10px);
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 14px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            transition: transform 0.2s ease;
        }

        .card:hover {
            transform: translateY(-2px);
        }

        .company {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .meta {
            font-size: 13px;
            color: #9ca3af;
            margin-bottom: 15px;
        }

        .message {
            white-space: pre-wrap;
            line-height: 1.6;
            font-size: 15px;
        }

        .buttons {
            margin-top: 20px;
            display: flex;
            gap: 10px;
        }

        button {
            padding: 12px 18px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 500;
        }

        .send {
            background: #22c55e;
            color: white;
        }

        .skip {
            background: #ef4444;
            color: white;
        }

        .send:hover {
            background: #16a34a;
        }

        .skip:hover {
            background: #dc2626;
        }

        .footer {
            margin-top: 40px;
            font-size: 12px;
            color: #6b7280;
            text-align: center;
        }
    </style>
    </head>
    <body>

    <div class="header">Gray Horizons Outreach Console</div>
    <div class="sub">AI-assisted outbound review • Human approval required</div>
    """

    for i, row in df.iterrows():

        if row["approved_to_send"] == "YES":
            continue

        html += f"""
        <div class="card">
            <div class="company">{row['company_name']}</div>
            <div class="meta">{row['email']}</div>

            <div class="message">{row['message']}</div>

            <div class="buttons">
                <form method="POST" action="/approve">
                    <input type="hidden" name="index" value="{i}">
                    <button class="send">Approve & Send</button>
                </form>

                <form method="POST" action="/skip">
                    <input type="hidden" name="index" value="{i}">
                    <button class="skip">Skip</button>
                </form>
            </div>
        </div>
        """

    html += """
    <div class="footer">
    Gray Horizons Enterprise • Internal Outreach System
    </div>

    </body>
    </html>
    """

    return html


@app.route("/approve", methods=["POST"])
def approve():
    df = load_data()
    i = int(request.form["index"])
    df.at[i, "approved_to_send"] = "YES"
    save_data(df)
    return redirect("/")


@app.route("/skip", methods=["POST"])
def skip():
    df = load_data()
    i = int(request.form["index"])
    df.at[i, "approved_to_send"] = "SKIPPED"
    save_data(df)
    return redirect("/")


if __name__ == "__main__":
    print("Starting premium dashboard...")
    app.run(host="0.0.0.0", port=5000, debug=False)