"""
inject_raw_leads.py — Gray Horizons Enterprise
Pulls real contractor business emails from prospects_raw.csv,
generates niche-specific outreach, injects into outreach_queue.csv.

Run:
  python inject_raw_leads.py
  python inject_raw_leads.py --dry-run   (preview without writing)
"""

import csv, re, sys, random
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(__file__).parent
RAW_CSV  = BASE / "prospects_raw.csv"
QUEUE_CSV = BASE / "outreach_queue.csv"

TARGET_NICHES = {"hvac", "roofing", "plumbing", "solar", "contractor"}

# ── Junk domain blacklist ──────────────────────────────────────────────────────
JUNK_DOMAINS = {
    # Media / news
    "weather.com", "accuweather.com", "nbc.com", "nbcuni.com", "nbcnews.com",
    "cbs.com", "cbsnews.com", "abc.com", "foxnews.com", "heavy.com",
    "usatoday.com", "reuters.com", "apnews.com", "bloomberg.com",
    "wsj.com", "nytimes.com", "washingtonpost.com", "latimes.com",
    # Directories / aggregators
    "buildzoom.com", "angi.com", "angieslist.com", "homeadvisor.com",
    "thumbtack.com", "houzz.com", "yelp.com", "bbb.org",
    "todayshomeowner.com", "thisoldhouse.com", "bobvila.com",
    "improvenet.com", "networx.com", "porch.com", "bark.com", "example.com", "test.com",
    # Corporates / wrong targets
    "fedex.com", "ups.com", "amazon.com", "google.com", "microsoft.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    # State boards / government (supplement the .gov TLD check)
    "cslb.ca.gov", "dpor.virginia.gov", "tdlr.texas.gov",
    "lacounty.gov", "cityof.com", "state.ca.us",
}

JUNK_TLDS    = {".gov", ".mil", ".edu", ".org"}
JUNK_PREFIXES = re.compile(
    r'^(info|contact|noreply|no-reply|donotreply|support|admin|webmaster|'
    r'postmaster|sales|hello|mail|office|team|help|service|enquiries|enquiry|'
    r'billing|privacy|legal|press|media|hr|careers|jobs|feedback|customercare|'
    r'customersupport|customer|care|general|info1|info2|findapro|findaretailer|'
    r'utilities|localservice|localplumbers|digitalcare|clientcare|webadmin|'
    r'countyof|department|magruder|customerservice)@',
    re.I
)

JUNK_COMPANY_WORDS = re.compile(
    r'\b(directory|association|national|supply store|supply co|county|district|'
    r'municipality|dollar general|ferguson|department of|bureau of|chamber of|'
    r'institute|federation|coalition|society|foundation|onmicrosoft)\b',
    re.I
)

# Company must contain a real contractor signal
NICHE_SIGNALS = {
    "hvac":       re.compile(r'hvac|heating|cooling|air cond|furnace|ductwork|refriger', re.I),
    "roofing":    re.compile(r'roof|shingle|gutter|exterior', re.I),
    "plumbing":   re.compile(r'plumb|pipe|drain|sewer|water heater', re.I),
    "solar":      re.compile(r'solar|photovolt|panel|renewable|energy', re.I),
    "contractor": re.compile(r'contractor|construction|remodel|build|handyman|general', re.I),
}

# ── Email templates ────────────────────────────────────────────────────────────
SUBJECTS = [
    "Quick question",
    "Question for you",
    "Had a quick question",
    "Wanted to reach out",
]

BODIES = {
    "hvac": [
        """\
Hey,

HVAC companies with a full schedule typically miss 15-20 calls a week during peak season. At an average job value of $450, that's $6,750-$9,000 walking out the door every week.

We set up an automated follow-up system for HVAC shops that catches every missed inquiry and follows up immediately so the customer hears from you before they call someone else.

I can show you exactly what it looks like for a shop your size in 20 minutes.

https://calendly.com/grayhorizonsenterprise/30min

We offer a 7-day free trial. No cost, no contract. You see it working before committing to anything.

Gray Horizons Enterprise
grayhorizonsenterprise.com""",

        """\
Hey,

When your techs are on jobs and a new call comes in, what happens to it? Voicemail? A callback that never gets made?

We build AI front desks for HVAC shops that answer every call, qualify the lead, and book the estimate automatically. No staff needed.

Three HVAC shops we've set this up for recovered an average of $8,400/month in calls they were previously missing.

Worth a 20-minute look?

https://calendly.com/grayhorizonsenterprise/30min

Gray Horizons Enterprise
grayhorizonsenterprise.com""",
    ],
    "roofing": [
        """\
Hey,

Storm season is when roofing companies win or lose the year. The shops that answer every inquiry fast are the ones that book out.

We set up an automated system that catches every missed call or web inquiry and follows up within 60 seconds, books the inspection, and keeps track of follow-ups so nothing falls through.

I can walk you through it in 20 minutes.

https://calendly.com/grayhorizonsenterprise/30min

Gray Horizons Enterprise
grayhorizonsenterprise.com""",
    ],
    "plumbing": [
        """\
Hey,

Emergency plumbing calls are won by whoever picks up first. If your team is on a job and can't answer, that customer has already called the next number on Google.

We build AI phone systems for plumbing companies that answer 24/7, qualify the emergency, and dispatch or book automatically.

Worth a 20-minute look?

https://calendly.com/grayhorizonsenterprise/30min

Gray Horizons Enterprise
grayhorizonsenterprise.com""",
    ],
    "solar": [
        """\
Hey,

Inbound solar leads go cold fast. The company that follows up within 5 minutes wins the sale 78% of the time.

We set up automated follow-up systems for solar companies that respond to every inquiry instantly, qualify the lead, and book the consult automatically.

I can show you exactly how it works in 20 minutes.

https://calendly.com/grayhorizonsenterprise/30min

Gray Horizons Enterprise
grayhorizonsenterprise.com""",
    ],
    "contractor": [
        """\
Hey,

General contractors lose more estimates to slow follow-up than to price. The client submits a request, gets one call, and then hears from your competitor three times.

We build automated follow-up systems that stay on every estimate until it converts. No extra staff.

I can walk you through it in 20 minutes.

https://calendly.com/grayhorizonsenterprise/30min

Gray Horizons Enterprise
grayhorizonsenterprise.com""",
    ],
}


def is_junk(email: str, company: str, niche: str) -> bool:
    em   = email.strip().lower()
    comp = company.strip().lower()
    if not em or "@" not in em:
        return True
    domain = em.split("@")[-1]
    if domain in JUNK_DOMAINS:
        return True
    if any(domain.endswith(tld) for tld in JUNK_TLDS):
        return True
    if JUNK_PREFIXES.search(em):
        return True
    # onmicrosoft.com = corporate/govt tenant — never a small contractor
    if "onmicrosoft.com" in domain:
        return True
    if JUNK_COMPANY_WORDS.search(comp):
        return True
    # Must have a real niche signal in the company name
    sig = NICHE_SIGNALS.get(niche)
    if sig and not sig.search(comp):
        return True
    return False


def build_email(niche: str, company: str) -> tuple[str, str]:
    subject = random.choice(SUBJECTS)
    pool    = BODIES.get(niche, BODIES["contractor"])
    body    = random.choice(pool)
    return subject, body


def main(dry_run: bool = False):
    raw   = list(csv.DictReader(open(RAW_CSV, encoding="utf-8", errors="ignore")))
    queue = list(csv.DictReader(open(QUEUE_CSV, encoding="utf-8", errors="ignore")))

    queue_emails = {r.get("email", "").strip().lower() for r in queue}
    fieldnames   = list(queue[0].keys()) if queue else [
        "company", "name", "email", "website", "subject", "message", "status", "niche", "phone"
    ]

    injected = []
    skipped  = 0

    for r in raw:
        niche  = r.get("niche", "").strip().lower()
        if niche not in TARGET_NICHES:
            continue
        email   = r.get("email", "").strip()
        company = r.get("company", "").strip()
        phone   = r.get("phone", "").strip()

        if email.lower() in queue_emails:
            continue
        if is_junk(email, company, niche):
            skipped += 1
            continue

        subject, body = build_email(niche, company)
        row = {
            "company": company,
            "name":    "",
            "email":   email,
            "website": r.get("website", ""),
            "subject": subject,
            "message": body,
            "status":  "pending",
            "niche":   niche,
            "phone":   phone,
        }
        injected.append(row)
        queue_emails.add(email.lower())

    print(f"[INJECT] Raw contractor rows scanned: {sum(1 for r in raw if r.get('niche','').strip().lower() in TARGET_NICHES)}")
    print(f"[INJECT] Already in queue:   {sum(1 for r in raw if r.get('niche','').strip().lower() in TARGET_NICHES and r.get('email','').strip().lower() in {rr.get('email','').strip().lower() for rr in queue})}")
    print(f"[INJECT] Junk/filtered out:  {skipped}")
    print(f"[INJECT] Ready to inject:    {len(injected)}")
    print()

    for row in injected:
        flag = "[DRY]" if dry_run else "[ADD]"
        print(f"  {flag} {row['niche']} | {row['company']} | {row['email']}")

    if dry_run:
        print("\n[DRY RUN] Nothing written. Remove --dry-run to inject.")
        return

    if not injected:
        print("[INJECT] Nothing new to inject.")
        return

    all_rows = queue + injected
    with open(QUEUE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    print(f"\n[INJECT] Done. {len(injected)} leads added to outreach_queue.csv with status=pending")
    print("         Run outreach_sender.py to send them.")


if __name__ == "__main__":
    import sys
    main(dry_run="--dry-run" in sys.argv)
