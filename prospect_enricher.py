import pandas as pd
import requests
import re
from bs4 import BeautifulSoup

INPUT_FILE = "outreach_queue.csv"

# =========================
# FIND WEBSITE (FROM GOOGLE SEARCH)
# =========================
def find_website(company):
    try:
        url = "https://duckduckgo.com/html/"
        res = requests.post(url, data={"q": company})
        soup = BeautifulSoup(res.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "http" in href and "duckduckgo" not in href:
                return href
    except:
        pass
    return ""

# =========================
# EXTRACT EMAIL FROM PAGE
# =========================
def extract_email(url):
    try:
        res = requests.get(url, timeout=5)
        emails = re.findall(r"[\w\.-]+@[\w\.-]+", res.text)

        for email in emails:
            if not any(x in email for x in ["example", "test", "png", "jpg"]):
                return email
    except:
        pass
    return ""

# =========================
# MAIN ENRICH
# =========================
def run():
    df = pd.read_csv(INPUT_FILE)

    if "email" not in df.columns:
        df["email"] = ""

    for i, row in df.iterrows():
        if not row["email"] and row.get("company"):

            print(f"Searching: {row['company']}")

            site = find_website(row["company"])

            if site:
                email = extract_email(site)

                if email:
                    print(f"FOUND: {email}")
                    df.at[i, "email"] = email
                else:
                    print("No email on site")
            else:
                print("No website found")

    df.to_csv(INPUT_FILE, index=False)
    print("DONE")

if __name__ == "__main__":
    run()