import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("\n=== Starting Full Outreach Pipeline ===\n")

steps = [
    "python prospect_finder.py",
    "python prospect_enricher.py",
    "python prospect_qualifier.py",
    "python outreach_generator.py"
]

for step in steps:
    print(f"Running: {step}")
    os.system(step)

print("\n[DONE] Pipeline complete.\n")
print("Now run: python approval_dashboard.py\n")