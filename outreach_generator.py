import pandas as pd

INPUT_FILE = "prospects_enriched.csv"
OUTPUT_FILE = "outreach_queue.csv"

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

    for _, row in df.iterrows():
        company = row.get("company") or row.get("name") or ""

        rows.append({
            "company": company,
            "name": "",
            "email": row.get("email", ""),
            "message": generate_message(company),
            "status": "pending"
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False)

    print("✅ Outreach queue built")

if __name__ == "__main__":
    run()