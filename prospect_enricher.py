import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import time

INPUT_FILE = "outreach_queue.csv"

# =========================
# FIND WEBSITE
# =========================
def find_website(company):
    try:
        res = requests.post(
            "https://duckduckgo.com/html/",
            data={"q": company},
            timeout=5
        )

        soup = BeautifulSoup(res.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "http" in href and "duckduckgo" not in href:
                return href
    except:
        pass

    return ""

# =========================
# EXTRACT EMAILS FROM PAGE
# =========================
def extract_emails_from_url(url):
    emails = []

    try:
        res = requests.get(url, timeout=5)
        found = re.findall(r"[\\w\\.-]+@[\\w\\.-]+", res.text)

        for e in found:
            if not any(x in e for x in ["example", "png", "jpg", "test"]):
                emails.append(e)
    except:
        pass

    return emails

# =========================
# MAIN ENRICHMENT
# =========================
def run():
    df = pd.read_csv(INPUT_FILE)

    if "email" not in df.columns:
        df["email"] = ""

    if "company" not in df.columns:
        df["company"] = ""

    for i, row in df.iterrows():

        if row["email"] or not row["company"]:
            continue

        company = row["company"]

        print(f"\n🔍 Searching: {company}")

        website = find_website(company)

        if not website:
            print("❌ No website")
            continue

        print("🌐 Website:", website)

        emails = []

        # homepage
        emails += extract_emails_from_url(website)

        # contact page
        emails += extract_emails_from_url(website.rstrip("/") + "/contact")

        if emails:
            email = emails[0]
            print("✅ FOUND:", email)
            df.at[i, "email"] = email
        else:
            print("❌ No email found")

        time.sleep(1)

    df.to_csv(INPUT_FILE, index=False)
    print("\n🚀 ENRICHMENT COMPLETE")


if __name__ == "__main__":
    run()