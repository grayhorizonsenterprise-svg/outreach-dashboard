import smtplib
from email.mime.text import MIMEText
import os

def send_email(to_email, subject, body):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_APP_PASSWORD")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email

    # TRY TLS FIRST
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return "sent"

    except Exception as e:
        raise Exception(f"SMTP FAILED: {str(e)}")