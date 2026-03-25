import pandas as pd
import re
import os

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

BAD_PATTERNS = [
    r"top\s*\d+",
    r"best\s+\d+",
    r"list\s+of",
    r"directory",
    r"blog",
    r"article",
    r"guide",
    r"yelp",
    r"review",
]


def is_valid_company(name):

    if pd.isna(name):
        return False

    name = name.lower()

    for pattern in BAD_PATTERNS:
        if re.search(pattern, name):
            return False

    # must contain at least one business word
    BUSINESS_WORDS = [
        "management",
        "association",
        "properties",
        "property",
        "hoa",
        "community",
        "realty",
        "services",
        "group",
        "company"
    ]

    if not any(word in name for word in BUSINESS_WORDS):
        return False

    return True


def clean():

    df = pd.read_csv(INPUT_FILE)

    original_count = len(df)

    df = df[df["company"].apply(is_valid_company)]

    cleaned_count = len(df)

    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Removed {original_count - cleaned_count} non-company leads")
    print(f"{cleaned_count} valid prospects remaining")


if __name__ == "__main__":
    clean()