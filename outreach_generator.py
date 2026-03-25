import pandas as pd
import random
import os

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

SUBJECTS = [
    "Quick HOA question",
    "Question about violation notices",
    "Quick question about compliance",
    "HOA compliance question",
]

def generate_subject():
    return random.choice(SUBJECTS)

def generate_message(company):
    return f"""Hi there,

I came across {company} while reviewing HOA management firms in your area.

One thing we consistently see is that many teams are still handling violation notices across email threads and spreadsheets, which makes tracking and compliance harder than it should be.

We built a workflow that centralizes notices, documentation, and tracking so nothing slips through and your team is not stuck managing it manually.

Out of curiosity, how are you currently handling that process?

If it makes sense, I can walk you through how it works.

Alex
Lead Operations Specialist
Gray Horizons Enterprise
https://grayhorizonsenterprise.com
"""

def run():
    df = pd.read_csv(INPUT_FILE)

    rows = []
    skipped = 0

    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip()

        # Only include leads where we have a confirmed email
        if email in ("", "nan", "None"):
            skipped += 1
            continue

        company = str(row.get("company", "")).strip()

        rows.append({
            "company": company,
            "name": "",
            "email": email,
            "website": row.get("website", ""),
            "subject": generate_subject(),
            "message": generate_message(company),
            "status": "pending"
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False, quoting=1)

    print(f"[DONE] outreach_queue.csv: {len(rows)} ready leads ({skipped} skipped — no email)")

if __name__ == "__main__":
    run()
