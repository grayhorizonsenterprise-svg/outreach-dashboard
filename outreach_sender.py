from outreach_sender import send_email

@app.route('/test-email')
def test_email():
    try:
        send_email(
            "grayhorizonsenterprise@gmail.com",
            "Test Email",
            "Your HOA outreach system is working."
        )
        return "✅ Email sent successfully!"
    except Exception as e:
        return f"❌ Error sending email: {str(e)}"