import schedule
import subprocess
import time

def run_prospect_finder():
    print("Running prospect finder...")
    subprocess.run(["python", "prospect_finder.py"])

def run_email_enricher():
    print("Running email enricher...")
    subprocess.run(["python", "prospect_enricher.py"])

def run_outreach_generator():
    print("Generating outreach drafts...")
    subprocess.run(["python", "outreach_generator.py"])

def run_email_sender():
    print("Sending approved outreach...")
    subprocess.run(["python", "outreach_sender.py"])

# MORNING LEAD GENERATION
schedule.every().day.at("08:00").do(run_prospect_finder)

# EMAIL ENRICHMENT
schedule.every().day.at("08:05").do(run_email_enricher)

# OUTREACH CREATION
schedule.every().day.at("08:10").do(run_outreach_generator)

# SEND APPROVED EMAILS
schedule.every().day.at("08:20").do(run_email_sender)

print("Scheduler running...")

while True:
    schedule.run_pending()
    time.sleep(30)