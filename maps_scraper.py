import requests
import pandas as pd
import time

# =========================
# 🔑 PASTE YOUR GOOGLE API KEY HERE
# =========================
GOOGLE_API_KEY = "AIzaSyBcyVrmGiYFMQv7LrT4uqoP5P-q7Kkr1q4"

# =========================
# CONFIG
# =========================
QUERY = "HOA property management companies California"
OUTPUT_FILE = "prospects_raw.csv"

# =========================
# FETCH PLACES
# =========================
def fetch_places():
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    params = {
        "query": QUERY,
        "key": GOOGLE_API_KEY
    }

    all_results = []

    while True:
        res = requests.get(url, params=params).json()
        results = res.get("results", [])

        for place in results:
            all_results.append({
                "company": place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "rating": place.get("rating", ""),
                "place_id": place.get("place_id", "")
            })

        next_token = res.get("next_page_token")

        if not next_token:
            break

        # Google requires delay before using next_page_token
        time.sleep(2)

        params = {
            "pagetoken": next_token,
            "key": GOOGLE_API_KEY
        }

    return all_results

# =========================
# MAIN RUN
# =========================
def run():
    if GOOGLE_API_KEY == "PASTE_YOUR_KEY_HERE":
        print("❌ ERROR: You did NOT paste your API key")
        return

    print("🔍 Fetching leads from Google Maps...")

    leads = fetch_places()

    if not leads:
        print("❌ No results returned — check API key / API enabled")
        return

    df = pd.DataFrame(leads)

    df.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved {len(df)} leads to {OUTPUT_FILE}")

if __name__ == "__main__":
    run()