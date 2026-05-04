import csv

INPUT = "prospects_raw.csv"

files = {
    "hoa":          "hoa_leads.csv",
    "plumbing":     "plumber_leads.csv",
    "hvac":         "hvac_leads.csv",
    "roofing":      "roofing_leads.csv",
    "electric":     "electrician_leads.csv",
    "dental":       "dental_leads.csv",
    "contractor":   "contractor_leads.csv",
    "landscaping":  "landscaping_leads.csv",
}


def detect(name):
    n = name.lower()
    if any(k in n for k in ("hoa", "homeowners association", "community association")):
        return "hoa"
    if any(k in n for k in ("plumb",)):
        return "plumbing"
    if any(k in n for k in ("hvac", "heating", "cooling", "air conditioning")):
        return "hvac"
    if any(k in n for k in ("roof", "roofer")):
        return "roofing"
    if any(k in n for k in ("electric",)):
        return "electric"
    if any(k in n for k in ("dental", "dentist", "orthodont")):
        return "dental"
    if any(k in n for k in ("contractor", "construction", "remodel", "builder", "renovati")):
        return "contractor"
    if any(k in n for k in ("landscap", "lawn", "landscape")):
        return "landscaping"
    return None


def split():
    buckets = {k: [] for k in files}

    with open(INPUT, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use the "niche" column if present (set by prospect_finder.py)
            niche = row.get("niche", "").strip().lower()
            if niche not in files:
                niche = detect(row.get("company", ""))
            if niche:
                buckets[niche].append(row)

    for niche, data in buckets.items():
        if not data:
            continue
        with open(files[niche], "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["company", "website", "email"]
            )
            writer.writeheader()
            writer.writerows(data)
        print(f"  {niche.upper():14s}: {len(data)} leads → {files[niche]}")


split()
