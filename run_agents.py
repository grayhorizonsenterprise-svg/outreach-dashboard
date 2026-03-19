import os
import time

print("Starting HOA Outreach Pipeline...\n")

steps = [
    "python prospect_finder.py",
    "python prospect_enricher.py",
    "python prospect_qualifier.py",
    "python outreach_generator.py",
    "python outreach_review.py"
]

for step in steps:
    print(f"\nRunning: {step}")
    os.system(step)
    time.sleep(3)

print("\nPipeline Complete.")