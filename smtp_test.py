import smtplib

# --- HARD SET VALUES (NO ENV, NO CONFUSION) ---
SENDER_EMAIL = "GRAYHORIZONSENTERPRISE@GMAIL.COM"
SENDER_APP_PASSWORD = "aalyouzwpmzoovbt"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

try:
    print("Connecting to Gmail SMTP...")

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.ehlo()
    server.starttls()

    print("EMAIL:", SENDER_EMAIL)
    print("PASS:", SENDER_APP_PASSWORD)

    server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)

    print("CONNECTED SUCCESSFULLY")

    message = """Subject: Test Email

This is a test email from your system.
"""

    server.sendmail(SENDER_EMAIL, SENDER_EMAIL, message)

    print("TEST EMAIL SENT")

    server.quit()

except Exception as e:
    print("SMTP CONNECTION FAILED")
    print(e)
