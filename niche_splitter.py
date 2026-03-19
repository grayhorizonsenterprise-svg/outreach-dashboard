import csv

INPUT="prospects_raw.csv"

files={
"hoa":"hoa_leads.csv",
"plumbing":"plumber_leads.csv",
"hvac":"hvac_leads.csv",
"roofing":"roofing_leads.csv",
"electric":"electrician_leads.csv"
}

def detect(name):

    n=name.lower()

    if "hoa" in n:
        return "hoa"

    if "plumb" in n:
        return "plumbing"

    if "hvac" in n:
        return "hvac"

    if "roof" in n:
        return "roofing"

    if "electric" in n:
        return "electric"

    return None


def split():

    buckets={k:[] for k in files}

    with open(INPUT,newline="",encoding="utf-8") as f:

        reader=csv.DictReader(f)

        for row in reader:

            niche=detect(row["company_name"])

            if niche:
                buckets[niche].append(row)

    for niche,data in buckets.items():

        if not data:
            continue

        with open(files[niche],"w",newline="",encoding="utf-8") as f:

            writer=csv.DictWriter(
                f,
                fieldnames=["company_name","website","email"]
            )

            writer.writeheader()
            writer.writerows(data)

split()