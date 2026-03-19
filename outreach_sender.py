import csv
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL=os.getenv("SENDER_EMAIL")
PASS=os.getenv("SENDER_APP_PASSWORD")

QUEUE="outreach_queue.csv"

def send():

    with open(QUEUE,newline="",encoding="utf-8") as f:

        reader=csv.DictReader(f)

        for row in reader:

            if row["APPROVED_TO_SEND"]!="YES":
                continue

            msg=EmailMessage()

            msg["Subject"]=row["subject"]
            msg["From"]=EMAIL
            msg["To"]=row["email"]

            msg.set_content(row["message"])

            with smtplib.SMTP("smtp.gmail.com",587) as s:

                s.starttls()
                s.login(EMAIL,PASS)
                s.send_message(msg)

            print("Sent to",row["email"])

send()