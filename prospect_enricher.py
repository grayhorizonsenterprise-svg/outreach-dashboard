import pandas as pd

INPUT_FILE = "prospects_raw.csv"
OUTPUT_FILE = "prospects_enriched.csv"


def clean(val):
    if pd.isna(val):
        return ""
    return str(val).strip()


def run():

    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"ERROR loading {INPUT_FILE}: {e}")
        return

    if df.empty:
        print("No raw prospects found.")
        return

    rows = []

    for _, r in df.iterrows():

        company = clean(r.get("company_name"))
        website = clean(r.get("website"))

        if not company:
            continue

        rows.append({
            "company_name": company,
            "website": website,
            "contact_email": "",
            "contact_page_url": website,
            "location": clean(r.get("location")),
            "keyword_hits": clean(r.get("keyword_hits")),
            "hoa_size_estimate": ""
        })

    if not rows:
        print("No valid rows after cleaning.")
        return

    pd.DataFrame(rows).to_csv(OUTPUT_FILE, index=False)

    print(f"[DONE] Enriched {len(rows)} prospects → {OUTPUT_FILE}")


if __name__ == "__main__":
    run()