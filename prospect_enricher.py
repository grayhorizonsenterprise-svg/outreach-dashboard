import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import time

INPUT_FILE = "outreach_queue.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# FIND WEBSITE
# =========================
def find_website(company):
    try:
        res = requests.post(
            "https://duckduckgo.com/html/",
            data={"q": company},
            headers=HEADERS,
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
# GET ALL LINKS FROM PAGE
# =========================
def get_internal_links(url):
    links = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]

            if href.startswith("/"):
                links.append(url.rstrip("/") + href)
            elif url in href:
                links.append(href)

    except:
        pass

    return list(set(links))


# =========================
# EXTRACT EMAILS
# =========================
def extract_emails(url):
    emails = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=5)

        found = re.findall(r"[\\w\\.-]+@[\\w\\.-]+", res.text)

        for e in found:
            if not any(x in e for x in ["png", "jpg", "example", "test"]):
                emails.append(e)

    except:
        pass

    return emails


# =========================
# MAIN ENRICH
# =========================
def run():
    df = pd.read_csv(INPUT_FILE)

    for i, row in df.iterrows():

        if row["email"]:
            continue

        company = row["company"]

        print(f"\n🔍 Searching: {company}")

        site = find_website(company)

        if not site:
            print("❌ No website")
            continue

        print("🌐", site)

        emails = []

        # homepage
        emails += extract_emails(site)

        # common pages
        for path in ["/contact", "/about", "/team"]:
            emails += extract_emails(site.rstrip("/") + path)

        # deeper scan
        links = get_internal_links(site)

        for link in links[:5]:  # limit to avoid overload
            emails += extract_emails(link)

        if emails:
            email = list(set(emails))[0]
            print("✅ FOUND:", email)
            df.at[i, "email"] = email
        else:
            print("❌ No email found")

        time.sleep(1)

    df.to_csv(INPUT_FILE, index=False)
    print("\n🚀 DONE")


if __name__ == "__main__":
    run()