import os
import csv
import requests
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

SEARCH_TERMS = [
    "hoa management",
    "property management",
    "community association management",
    "condo management",
]

CITIES = [
    "San Bernardino CA",
    "Los Angeles CA",
    "Phoenix AZ",
    "Las Vegas NV"
]

OUTPUT_FILE = "prospects_raw.csv"

BASE_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def search_places(query):
    params = {
        "query": query,
        "key": API_KEY
    }
    return requests.get(BASE_URL, params=params).json().get("results", [])


def get_details(place_id):
    params = {
        "place_id": place_id,
        "fields": "name,website",
        "key": API_KEY
    }
    return requests.get(DETAILS_URL, params=params).json().get("result", {})


def run():

    seen = {}
    rows = []

    for city in CITIES:
        for term in SEARCH_TERMS:

            query = f"{term} in {city}"
            print(f"Searching: {query}")

            results = search_places(query)

            for place in results:

                pid = place.get("place_id")

                if pid in seen:
                    continue

                details = get_details(pid)

                name = details.get("name") or ""
                website = details.get("website") or ""

                seen[pid] = True

                rows.append({
                    "company_name": name.strip(),
                    "website": website.strip(),
                    "contact_email": "",
                    "contact_page_url": website.strip(),
                    "location": city,
                    "keyword_hits": term,
                    "hoa_size_estimate": ""
                })

                time.sleep(0.2)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} prospects → {OUTPUT_FILE}")


if __name__ == "__main__":
    run()