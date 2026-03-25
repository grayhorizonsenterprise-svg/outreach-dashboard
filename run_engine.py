import subprocess
import time

def run(script):
    print(f"\nRunning {script}...\n")
    subprocess.run(["python", script])

while True:

    print("\n===== GHE OUTREACH ENGINE =====\n")

    run("prospect_finder.py")
    run("prospect_enricher.py")
    run("prospect_qualifier.py")
    run("outreach_generator.py")

    print("\nCycle complete. Sleeping 6 hours...\n")

    time.sleep(21600)