import pandas as pd
import re
import os
import urllib.parse

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "prospects_raw.csv")

BUSINESS_WORDS = [
    # HOA
    "management", "association", "properties", "property",
    "hoa", "community", "realty", "mgmt", "residential", "condo", "homeowner",
    # HVAC
    "hvac", "heating", "cooling", "air conditioning", "furnace", "heat pump",
    "refrigeration", "mechanical", "climate", "ventilation",
    # Dental
    "dental", "dentist", "orthodontic", "oral", "smile", "teeth", "tooth",
    "periodontal", "endodontic", "implant",
    # Plumbing
    "plumbing", "plumber", "drain", "sewer", "pipe", "rooter",
    "waterworks", "water heater",
    # Contractor
    "contractor", "construction", "remodel", "renovation", "builder",
    "roofing", "flooring", "framing", "general contractor",
    # Generic business
    "services", "group", "company", "inc", "llc", "corp",
]

# These patterns in the RAW title mean skip the row entirely
RAW_JUNK_PATTERNS = [
    r"top\s*\d+", r"best\s+\d+", r"list\s+of", r"directory",
    r"\bblog\b", r"\barticle\b", r"\bguide\b", r"\byelp\b",
    r"\breview\b", r"\breddit\b", r"\bcraigslist\b", r"\bfiverr\b",
    r"\bavvo\b", r"yellow\s*pages", r"find.us.here", r"ipaddress",
    r"yonfi", r"leadclub", r"rocketreach", r"biggerpockets",
    r"hoaleader", r"expertise\.com", r"\bwikipedia\b",
]

# Title suffixes to strip to get the real company name
STRIP_SUFFIXES = [
    r"hoa\s*&?\s*coa\s*&?\s*condo\s*(management|services?)?",
    r"hoa\s*&?\s*property\s*management\s*(company|services?|firm)?",
    r"community\s*association\s*management\s*(company|services?|firm)?",
    r"homeowners?\s*association\s*management\s*(company|services?|firm)?",
    r"property\s*&?\s*(condo\s*&?\s*)?hoa\s*management\s*(company|services?|firm)?",
    r"property\s*management\s*(company|services?|firm)?",
    r"association\s*management\s*(company|services?|firm)?",
    r"hoa\s*management\s*(company|services?|firm)?",
    r"community\s*management\s*(company|services?)?",
    r"condo\s*(association\s*)?management\s*(company|services?)?",
    r"hoa\s*services?",
    r"welcome\s*to",
    r"about\s*us",
    r"\babout$",
    r"\bhome$",
]


def extract_from_domain(website: str) -> str:
    if not website:
        return ""
    parsed = urllib.parse.urlparse(website)
    netloc = parsed.netloc.lower().replace("www.", "")
    slug = netloc.split(".")[0]
    slug = re.sub(r"([a-z])([A-Z])", r"\1 \2", slug)
    slug = slug.replace("-", " ").replace("_", " ")
    slug = re.sub(r"\bhoa\b", "HOA", slug, flags=re.IGNORECASE)
    slug = re.sub(r"\bmgmt\b", "Management", slug, flags=re.IGNORECASE)
    slug = re.sub(r"\bmgrs?\b", "Management", slug, flags=re.IGNORECASE)
    slug = re.sub(r"\bnw\b", "NW", slug, flags=re.IGNORECASE)
    slug = re.sub(r"\bppm\b", "PPM", slug, flags=re.IGNORECASE)
    slug = re.sub(r"\bcm\b", "CM", slug, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", slug).title().strip()


def clean_company_name(raw: str, website: str = "") -> str:
    if pd.isna(raw) or not str(raw).strip():
        return extract_from_domain(website)

    name = str(raw).strip()

    # Split on common title separators — take the shortest meaningful part
    for sep in ["|", " – ", " — ", "—", "–", "·", ": ", " - "]:
        if sep in name:
            parts = [p.strip() for p in name.split(sep) if len(p.strip()) > 3]
            if parts:
                name = min(parts, key=len)
            break

    # Strip leading filler adjectives
    name = re.sub(
        r"^(trusted|professional|premier|leading|expert|top|best|local|full|all|new|small)\s+",
        "", name, flags=re.IGNORECASE
    ).strip()

    # Strip known title suffixes
    for pattern in STRIP_SUFFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip(" -–—|·,&")

    # Strip location tails: "in Los Angeles, CA" / "for Denver" / "of Boise"
    name = re.sub(
        r"\s+(in|for|of|near|serving|across)\s+[A-Z][^,]{2,}(?:,\s*[A-Z]{2})?$",
        "", name, flags=re.IGNORECASE
    ).strip()

    # Strip trailing ellipsis and dangling words
    name = re.sub(r"[.]{2,}$|…$", "", name).strip()
    name = re.sub(r"[\s&,|]+$", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip(" -–—|·,")

    return name


KNOWN_NICHES = {"hoa", "hvac", "dental", "plumbing", "contractor"}

# Niche keywords used to loosen word-count and name validation
NICHE_KEYWORDS = {
    "hvac", "heating", "cooling", "air conditioning", "plumbing", "plumber",
    "dental", "dentist", "contractor", "construction", "remodel",
}


def is_valid_raw(name: str, niche: str = "") -> bool:
    """Filter on the original scraped title before any cleaning.
    If the row came from a known niche query, skip the BUSINESS_WORDS
    requirement — the search query already confirmed it's a niche company.
    """
    if pd.isna(name):
        return False
    n = name.lower()
    for pattern in RAW_JUNK_PATTERNS:
        if re.search(pattern, n):
            return False
    # If it came from a known niche query, trust it
    if str(niche).strip().lower() in KNOWN_NICHES:
        return True
    # Otherwise require at least one business indicator word
    if not any(word in n for word in BUSINESS_WORDS):
        return False
    return True


def is_valid_clean(name: str, niche: str = "") -> bool:
    """Validate the cleaned company name is actually usable."""
    if not name or len(name) < 3:
        return False
    n = name.lower().strip()

    # Hard junk — always reject regardless of niche
    if re.search(r"\b20\d{2}\b", name):
        return False
    if re.search(r"\bhow\s+to\b|\btips?\s+(to|for)\b|\btrends?\s+to\b|\b#\d+\b", name, re.IGNORECASE):
        return False
    if name.endswith("!"):
        return False
    if re.match(r"^\d", name):
        return False

    # If it came from a known niche query, only apply the hard-junk checks above
    if str(niche).strip().lower() in KNOWN_NICHES:
        # Still reject bare location names and obvious content titles
        if re.match(r"^[a-zA-Z ]+,\s*[a-z]{2}$", n):
            return False
        if re.match(r"^(what|how|why|when|where|which|choosing|tips|guide|"
                    r"topics|contact|about|staff|planning)\b", n, re.IGNORECASE):
            return False
        return True

    # Strict path for anything without a niche tag
    if re.match(r"^(in|at|for|of|the|what|how|why|when|where|which|and|or|"
                r"these|those|contact|choosing|serving|about|requests?|"
                r"topics?|staff|city|planning|small|best|communities|"
                r"enriching|homeowner\s+vendor|county)\b", n, re.IGNORECASE):
        return False

    JUNK_SINGLES = {
        "best", "communities", "small", "staff", "city", "planning",
        "requests", "nevada", "arizona", "colorado", "idaho", "utah",
        "montana", "oregon", "washington", "california", "local",
        "allstate", "overleaf", "expertise.com", "county", "topics",
        "people", "edge", "home", "contact", "info", "page", "team",
        "management", "association", "services", "hoas", "what we do",
        "mtnonprofit", "sacaramento",
    }
    if n in JUNK_SINGLES:
        return False

    if re.match(r"^[a-zA-Z ]+,\s*[a-z]{2}$", n):
        return False

    LOCATIONS = {
        "arizona", "california", "colorado", "idaho", "montana", "nevada",
        "new mexico", "oregon", "utah", "washington", "spokane", "boise",
        "denver", "phoenix", "seattle", "portland", "reno", "tacoma",
        "frisco", "tahoe", "alaska", "hawaii", "albuquerque", "raleigh nc",
    }
    if n in LOCATIONS:
        return False

    niche_hit = any(k in n for k in NICHE_KEYWORDS)
    if len(name.split()) > (8 if niche_hit else 6):
        return False

    return True


def clean():
    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found yet — skipping qualification.")
        return
    df = pd.read_csv(INPUT_FILE)
    original_count = len(df)

    if "niche" not in df.columns:
        df["niche"] = ""

    # Step 1: filter raw titles — pass niche so known-niche rows bypass word check
    mask = df.apply(lambda r: is_valid_raw(r["company"], r.get("niche", "")), axis=1)
    df = df[mask].copy()

    # Step 2: clean names
    df["company"] = df.apply(
        lambda r: clean_company_name(r["company"], r.get("website", "")), axis=1
    )

    # Step 3: validate cleaned names — pass niche for looser rules on confirmed niches
    mask2 = df.apply(lambda r: is_valid_clean(r["company"], r.get("niche", "")), axis=1)
    df = df[mask2].copy()

    cleaned_count = len(df)
    df.to_csv(OUTPUT_FILE, index=False)

    # Report per-niche survival counts
    for niche in sorted(df["niche"].dropna().unique()):
        cnt = len(df[df["niche"] == niche])
        print(f"  {niche.upper():12s}: {cnt} leads")

    print(f"\nRemoved {original_count - cleaned_count} non-company leads")
    print(f"{cleaned_count} valid prospects remaining")


if __name__ == "__main__":
    clean()
