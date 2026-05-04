import os
import sys
import subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("\n=== Starting Full Outreach Pipeline ===\n", flush=True)

steps = [
    "maps_scraper.py",       # Google Maps: 100 cities x 7 niches = thousands of businesses
    "prospect_finder.py",    # DuckDuckGo: supplemental email-direct leads
    "prospect_enricher.py",  # scrape company websites for contact emails
    "prospect_qualifier.py", # score and rank leads
    "outreach_generator.py", # generate personalized messages
]

for step in steps:
    print(f"Running: {step}", flush=True)
    subprocess.run([sys.executable, step])

print("\n[DONE] Pipeline complete.\n")
print("Now run: python approval_dashboard.py\n")