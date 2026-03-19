import csv
import subprocess

QUEUE_FILE = "outreach_queue.csv"

def run_queue():

    rows = []

    with open(QUEUE_FILE, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    updated_rows = []

    print("\n===== OUTREACH APPROVAL QUEUE =====\n")

    for row in rows:

        if row["approved_to_send"].strip().upper() != "NO":
            updated_rows.append(row)
            continue

        print("\n------------------------------------")
        print("Company:", row["company_name"])
        print("Website:", row["website"])
        print("Email:", row["email"])
        print("\nMessage Preview:\n")
        print(row["message"][:300] + "...\n")

        choice = input("Send outreach? (y/n): ").strip().lower()

        if choice == "y":
            row["approved_to_send"] = "YES"
            print("✔ Approved\n")
        else:
            row["approved_to_send"] = "SKIP"
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