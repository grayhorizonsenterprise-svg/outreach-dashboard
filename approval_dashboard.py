from flask import Flask
from outreach_sender import send_email

app = Flask(__name__)

# ===== HOME ROUTE =====
@app.route('/')
def home():
    return """
    <h1>HOA Outreach Dashboard</h1>
    <p>System is running.</p>

    <a href="/test-email">
        <button style="padding:10px;font-size:18px;">Send Test Email</button>
    </a>
    """

# ===== EMAIL TEST ROUTE =====
@app.route('/test-email')
def test_email():
    try:
        send_email(
            "yournamegrayhorizonsenterprise@gmail.com",  # 🔴 CHANGE THIS TO YOUR EMAIL
            "Test Email",
            "Your HOA outreach system is working."
        )
        return "✅ Email sent successfully!"
    except Exception as e:
        return f"❌ Error sending email: {str(e)}"


# ===== RUN APP =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)