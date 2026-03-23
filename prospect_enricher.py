import pandas as pd
import requests
import os

HUNTER_API_KEY = os.getenv("066f1a238c1325bf0c7aad6f5015149f50c58037")

INPUT_FILE = "outreach_queue.csv"

# =========================
# CLEAN DOMAIN (BETTER GUESS)
# =========================
def get_domain(company):
    if not company:
        return ""

    clean = company.lower()
    clean = clean.replace(",", "")
    clean = clean.replace(".", "")
    clean = clean.replace(" ", "")

    return f"{clean}.com"

# =========================
# FIND EMAIL (HUNTER API)
# =========================
def find_email(company):
    if not HUNTER_API_KEY:
        print("❌ Missing HUNTER_API_KEY")
        return ""

    domain = get_domain(company)

    try:
        url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
        res = requests.get(url).json()

        emails = res.get("data", {}).get("emails", [])

        if emails:
            return emails[0]["value"]

    except Exception as e:
        print("ERROR:", e)

    return ""

# =========================
# MAIN LOOP (THIS IS WHAT YOU ASKED)
# =========================
def run():
    df = pd.read_csv(INPUT_FILE)

    if "email" not in df.columns:
        df["email"] = ""

    for i, row in df.iterrows():

        # 🔥 THIS IS THE LOOP YOU ASKED ABOUT
        if not row.get("email") and row.get("company"):

            email = find_email(row["company"])

            if email:
                print(f"FOUND: {email}")
                df.at[i, "email"] = email
            else:
                print(f"NO EMAIL: {row['company']}")

    df.to_csv(INPUT_FILE, index=False)
    print("✅ EMAIL ENRICHMENT COMPLETE")


if __name__ == "__main__":
    run()