import csv
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL=os.getenv("SENDER_EMAIL")
PASS=os.getenv("SENDER_APP_PASSWORD")

QUEUE_FILE="outreach_queue.csv"

def build_table():

    rows=[]

    with open(QUEUE_FILE,newline="",encoding="utf-8") as f:

        reader=csv.DictReader(f)

        for row in reader:

            rows.append(
                f"{row['company_name']} | {row['email']} | APPROVED_TO_SEND = NO"
            )

    return "\n".join(rows[:20])  # show first 20 leads


def alert():

    msg=EmailMessage()

    msg["Subject"]="Outreach Approval Queue"
    msg["From"]=EMAIL
    msg["To"]=EMAIL

    body=f"""
New outreach leads ready.

To approve emails:

Open outreach_queue.csv
Change APPROVED_TO_SEND from NO → YES

Then run:

python outreach_sender.py

Leads waiting:

{build_table()}
"""

    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com",587) as s:

        s.starttls()
        s.login(EMAIL,PASS)
        s.send_message(msg)

alert()