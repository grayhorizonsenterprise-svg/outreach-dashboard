import pandas as pd
import os

INPUT_FILE = "prospects_enriched.csv"
OUTPUT_FILE = "outreach_queue.csv"


def clean(val):
    if pd.isna(val):
        return ""
    return str(val).strip()


def clean_company(name):
    if not name:
        return ""

    name = str(name)

    for sep in ["|", " - "]:
        if sep in name:
            name = name.split(sep)[0]

    return name.strip()


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

    if not os.path.exists(INPUT_FILE):
        print(f"{INPUT_FILE} not found. Run previous steps first.")
        return

    df = pd.read_csv(INPUT_FILE)

    if df.empty:
        print("No enriched prospects found.")
        return

    rows = []

    for _, r in df.iterrows():

        company = clean_company(r.get("company_name"))
        email = clean(r.get("contact_email"))

        if not company:
            continue

        message = generate_message(company)

        rows.append({
            "company_name": company,
            "email": email,
            "message": message,
            "approved_to_send": "NO",
            "status": "pending"
        })

    if not rows:
        print("0 valid prospects after cleaning.")
        return

    pd.DataFrame(rows).to_csv(OUTPUT_FILE, index=False)

    print(f"Generated {len(rows)} outreach messages → {OUTPUT_FILE}")


if __name__ == "__main__":
    run()