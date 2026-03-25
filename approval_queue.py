import csv
import subprocess
import os

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

def run_queue():

    rows = []

    with open(QUEUE_FILE, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    updated_rows = []

    print("\n===== OUTREACH APPROVAL QUEUE =====\n")

    for row in rows:

        if row.get("status", "pending").strip().lower() != "pending":
            updated_rows.append(row)
            continue

        print("\n------------------------------------")
        print("Company:", row.get("company", ""))
        print("Email:", row.get("email", ""))
        print("\nMessage Preview:\n")
        print(row.get("message", "")[:300] + "...\n")

        choice = input("Send outreach? (y/n): ").strip().lower()

        if choice == "y":
            row["status"] = "approved"
            print("✔ Approved\n")
        else:
            row["status"] = "skipped"
            print("✖ Skipped\n")

        updated_rows.append(row)

    with open(QUEUE_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=updated_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated_rows)

    print("\nQueue updated.")

    run_send = input("\nSend approved emails now? (y/n): ").strip().lower()

    if run_send == "y":
        subprocess.run(["python", "outreach_sender.py"])


if __name__ == "__main__":
    run_queue()