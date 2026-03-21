import smtplib
from email.mime.text import MIMEText
import os

def send_email(to_email, subject, body):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_APP_PASSWORD")

    if not sender or not password:
        raise Exception("Missing email credentials (SENDER_EMAIL or SENDER_APP_PASSWORD)")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Email failed: {e}")
        raise