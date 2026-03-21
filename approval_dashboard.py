from flask import Flask
import urllib.parse

app = Flask(__name__)

@app.route('/')
def home():
    email = "yourtarget@email.com"  # change per lead
    subject = urllib.parse.quote("Quick question")
    body = urllib.parse.quote("Hi, I wanted to reach out about HOA compliance automation.")

    mailto_link = f"mailto:{email}?subject={subject}&body={body}"

    return f"""
    <h1>HOA Outreach Dashboard</h1>

    <a href="{mailto_link}">
        <button style="padding:20px;font-size:22px;">
            📧 Send Email
        </button>
    </a>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)