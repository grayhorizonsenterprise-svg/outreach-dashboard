import subprocess
import time

print("\n================================")
print("GRAY HORIZONS OUTREACH ENGINE")
print("================================\n")

steps = [

    "maps_scraper.py",
    "niche_splitter.py",
    "prospect_enricher.py",
    "prospect_qualifier.py",
    "email_finder.py",
    "outreach_generator.py",
    "outreach_sender.py",
    "agent_alert.py"

]

def run_step(step):

    print(f"\nRunning: {step}")

    try:
        subprocess.run(["python", step], check=True)
    except Exception as e:
        print("Error running", step)
        print(e)

    time.sleep(2)

for step in steps:
    run_step(step)

print("\nOUTREACH WAVE COMPLETE\n")