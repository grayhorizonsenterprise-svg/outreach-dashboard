import os

print("\n🚀 Starting Full Outreach Pipeline...\n")

steps = [
    "python maps_scraper.py",
    "python prospect_enricher.py",
    "python outreach_generator.py"
]

for step in steps:
    print(f"Running: {step}")
    os.system(step)

print("\n✅ Pipeline complete.\n")
print("Now run: python approval_dashboard.py\n")