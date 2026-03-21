import smtplib
from email.mime.text import MIMEText
import os

def send_email(to_email, subject, body):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_APP_PASSWORD")

    if not sender or not password:
        raise Exception("Missing email credentials")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email

    try:
        # USE TLS (587) — NOT 465
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()

        return "sent"

    except Exception as e:
        return str(e)