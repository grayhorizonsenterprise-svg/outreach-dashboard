import os
import sys
import subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("\n=== Starting Full Outreach Pipeline ===\n", flush=True)

steps = [
    "prospect_finder.py",
    "prospect_enricher.py",
    "prospect_qualifier.py",
    "outreach_generator.py"
]

for step in steps:
    print(f"Running: {step}", flush=True)
    subprocess.run([sys.executable, step])

print("\n[DONE] Pipeline complete.\n")
print("Now run: python approval_dashboard.py\n")