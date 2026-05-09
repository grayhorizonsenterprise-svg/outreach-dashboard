import subprocess
import time

print("\n================================")
print("GRAY HORIZONS OUTREACH ENGINE")
print("================================\n")

steps = [

    "prospect_finder.py",    # DuckDuckGo web search: supplemental email-direct leads
    "niche_splitter.py",     # split into per-niche CSV files
    "prospect_enricher.py",  # scrape contact emails from company websites
    "prospect_qualifier.py", # score and rank leads
    "email_finder.py",       # additional email lookup fallback
    "outreach_generator.py", # generate personalized email per lead
    "agent_alert.py"         # notify on completion — run resend_now.py to send

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