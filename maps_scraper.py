"""
maps_scraper.py — Gray Horizons Enterprise
National Google Maps lead scraper.
Covers all 50 states, 7 niches, small-to-mid-size markets.
Outputs to prospects_raw.csv with niche + website columns.
"""

import requests
import pandas as pd
import time
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBcyVrmGiYFMQv7LrT4uqoP5P-q7Kkr1q4")
OUTPUT_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prospects_raw.csv")
CHECKPOINT     = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".maps_checkpoint.json")

# ── 100 US cities — small/mid-size focus, all 50 states covered ──────────────
CITIES = [
    # West Coast
    "Sacramento CA", "Fresno CA", "Bakersfield CA", "Stockton CA", "Modesto CA",
    "Spokane WA", "Tacoma WA", "Bellevue WA", "Bellingham WA",
    "Eugene OR", "Salem OR", "Medford OR", "Bend OR",
    "Boise ID", "Nampa ID", "Meridian ID",
    "Reno NV", "Henderson NV", "North Las Vegas NV",
    # Southwest
    "Tucson AZ", "Mesa AZ", "Chandler AZ", "Gilbert AZ", "Scottsdale AZ",
    "Albuquerque NM", "Santa Fe NM", "Las Cruces NM",
    "El Paso TX", "Lubbock TX", "Amarillo TX", "Waco TX", "Laredo TX",
    # Mountain
    "Bozeman MT", "Billings MT", "Missoula MT", "Great Falls MT",
    "Cheyenne WY", "Casper WY",
    "Grand Junction CO", "Pueblo CO", "Fort Collins CO", "Colorado Springs CO",
    "Sioux Falls SD", "Rapid City SD",
    "Fargo ND", "Bismarck ND",
    # Midwest
    "Omaha NE", "Lincoln NE",
    "Wichita KS", "Overland Park KS", "Kansas City KS",
    "Des Moines IA", "Cedar Rapids IA", "Davenport IA",
    "Minneapolis MN", "Saint Paul MN", "Rochester MN",
    "Madison WI", "Green Bay WI", "Kenosha WI",
    "Peoria IL", "Rockford IL", "Springfield IL",
    "Fort Wayne IN", "South Bend IN", "Evansville IN",
    "Grand Rapids MI", "Lansing MI", "Flint MI", "Ann Arbor MI",
    "Toledo OH", "Akron OH", "Dayton OH", "Columbus OH",
    # South Central
    "Tulsa OK", "Norman OK", "Broken Arrow OK",
    "Little Rock AR", "Fort Smith AR",
    "Shreveport LA", "Baton Rouge LA", "Lafayette LA",
    "Jackson MS", "Gulfport MS",
    "Memphis TN", "Knoxville TN", "Chattanooga TN", "Clarksville TN",
    "Huntsville AL", "Montgomery AL", "Mobile AL",
    "Louisville KY", "Lexington KY",
    # Southeast
    "Raleigh NC", "Greensboro NC", "Winston-Salem NC", "Durham NC",
    "Columbia SC", "Charleston SC", "Greenville SC",
    "Augusta GA", "Savannah GA", "Macon GA",
    "Tallahassee FL", "Gainesville FL", "Pensacola FL", "Fort Myers FL",
    "Chesapeake VA", "Norfolk VA", "Richmond VA", "Arlington VA",
    "Charleston WV", "Huntington WV",
    # Mid-Atlantic / Northeast
    "Pittsburgh PA", "Allentown PA", "Lancaster PA", "York PA",
    "Baltimore MD", "Frederick MD", "Annapolis MD",
    "Wilmington DE",
    "Providence RI",
    "Hartford CT", "New Haven CT", "Bridgeport CT",
    "Worcester MA", "Springfield MA", "Lowell MA",
    "Manchester NH", "Nashua NH",
    "Burlington VT",
    "Portland ME",
    "Buffalo NY", "Rochester NY", "Syracuse NY", "Albany NY", "Yonkers NY",
    "Newark NJ", "Jersey City NJ", "Trenton NJ",
    # Non-continental
    "Anchorage AK",
    "Honolulu HI",
]

# ── Niche search terms ────────────────────────────────────────────────────────
NICHES = {
    "hoa":         "HOA property management company",
    "hvac":        "HVAC heating and cooling company",
    "dental":      "dental office dentist",
    "plumbing":    "plumbing company plumber",
    "contractor":  "general contractor construction company",
    "landscaping": "landscaping lawn care company",
    "roofing":     "roofing company roofer",
}

PLACES_URL  = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def text_search(query: str) -> list[dict]:
    """Run a Places text search and return up to 3 pages of results."""
    results = []
    params = {"query": query, "key": GOOGLE_API_KEY}

    for page_num in range(3):
        try:
            resp = requests.get(PLACES_URL, params=params, timeout=10).json()
        except Exception as e:
            print(f"  [WARN] text_search error: {e}")
            break

        status = resp.get("status", "")
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"  [WARN] API status: {status}")
            break

        for place in resp.get("results", []):
            results.append({
                "place_id": place.get("place_id", ""),
                "name":     place.get("name", ""),
                "address":  place.get("formatted_address", ""),
                "rating":   place.get("rating", ""),
            })

        next_token = resp.get("next_page_token")
        if not next_token or page_num == 2:
            break
        time.sleep(2)
        params = {"pagetoken": next_token, "key": GOOGLE_API_KEY}

    return results


def get_website(place_id: str) -> str:
    """Fetch the website URL from Place Details."""
    try:
        resp = requests.get(
            DETAILS_URL,
            params={"place_id": place_id, "fields": "website,formatted_phone_number", "key": GOOGLE_API_KEY},
            timeout=8,
        ).json()
        result = resp.get("result", {})
        return result.get("website", "")
    except Exception:
        return ""


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"done_keys": [], "records": []}


def save_checkpoint(done_keys: list, records: list):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump({"done_keys": done_keys, "records": records}, f)


def run():
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "PASTE_YOUR_KEY_HERE":
        print("ERROR: Set GOOGLE_API_KEY in .env or directly in this file.")
        return

    print("\n========================================")
    print(" GRAY HORIZONS — National Maps Scraper")
    print(f" Cities: {len(CITIES)} | Niches: {len(NICHES)}")
    print(f" Max queries: {len(CITIES) * len(NICHES)}")
    print("========================================\n")

    state = load_checkpoint()
    done_keys: set = set(state["done_keys"])
    records: list  = state["records"]

    seen_place_ids: set = {r["place_id"] for r in records}

    total_queries = len(CITIES) * len(NICHES)
    completed     = len(done_keys)

    for city in CITIES:
        for niche, term in NICHES.items():
            key = f"{city}|{niche}"
            if key in done_keys:
                continue

            query = f"{term} {city}"
            print(f"[{completed+1}/{total_queries}] {query}")

            places = text_search(query)
            new_count = 0

            for place in places:
                pid = place["place_id"]
                if pid in seen_place_ids:
                    continue
                seen_place_ids.add(pid)

                # Fetch website via Details API
                website = get_website(pid)
                time.sleep(0.15)

                records.append({
                    "company":          place["name"],
                    "address":          place["address"],
                    "rating":           place["rating"],
                    "place_id":         pid,
                    "website":          website,
                    "email":            "",
                    "contact_page_url": "",
                    "location":         city,
                    "niche":            niche,
                    "lead_type":        "",
                })
                new_count += 1

            print(f"  +{new_count} new ({len(records)} total so far)")
            done_keys.add(key)
            completed += 1

            # Save progress every 10 queries
            if completed % 10 == 0:
                save_checkpoint(list(done_keys), records)

            time.sleep(0.3)

    # Save final output
    if records:
        df = pd.DataFrame(records)
        df.drop_duplicates(subset=["place_id"], inplace=True)

        # Merge with existing prospects_raw.csv to preserve enriched data
        if os.path.exists(OUTPUT_FILE):
            try:
                existing = pd.read_csv(OUTPUT_FILE).fillna("")
                # Only add records not already in the existing file
                existing_ids = set(existing.get("place_id", pd.Series()).astype(str))
                df = df[~df["place_id"].isin(existing_ids)]
                df = pd.concat([existing, df], ignore_index=True)
            except Exception as e:
                print(f"[WARN] Could not merge with existing CSV: {e}")

        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n[DONE] {len(df)} total prospects saved to prospects_raw.csv")

        # Count by niche
        if "niche" in df.columns:
            print("\nLeads by niche:")
            for n, c in df.groupby("niche").size().sort_index().items():
                print(f"  {n.upper():14s}: {c}")
    else:
        print("[INFO] No records collected.")

    # Clear checkpoint on successful completion
    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)


if __name__ == "__main__":
    run()
