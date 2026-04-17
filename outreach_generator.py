import pandas as pd
import random
import re
import os

DATA_DIR    = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

# =========================
# NICHE MESSAGE TEMPLATES
# =========================

NICHE_MESSAGES = {

    "hoa": [
        """\
Hey,

Quick question — when a homeowner submits a violation or complaint, how does your team track it from that first report all the way to resolution? Still email threads, or do you have something more structured?

We work with a few HOA firms and that handoff tends to be where things fall through. Happy to share what we put together if it's relevant.

— Alex
Gray Horizons Enterprise""",

        """\
Hi there,

How are you handling violation notices and compliance documentation across your communities? It sounds simple but gets messy fast once you're managing more than a handful of associations.

Not a pitch — just genuinely curious how you're running it right now.

— Alex
Gray Horizons Enterprise""",

        """\
Hey,

Direct question — how does your team deal with violation management across multiple HOAs? Specifically the documentation side — keeping records, following up, making sure nothing gets dropped.

Happy to compare notes if that's a pain point.

— Alex
Gray Horizons Enterprise""",
    ],

    "hvac": [
        """\
Hey,

Quick one — when a customer calls in for an emergency repair, how are you dispatching and tracking that job from the first call to close-out? Still phone and spreadsheet, or do you have a system?

We've been working with HVAC companies to tighten up that gap. Curious how you're handling it.

— Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is relevant, but — how are you managing your service calls and maintenance schedules right now? Specifically keeping techs, customers, and follow-ups all in sync without things falling through.

Happy to share what we've seen work well if it's useful.

— Alex
Gray Horizons Enterprise""",

        """\
Hey,

Wanted to ask something real quick — during peak season when calls are stacking up, how does your team keep track of which jobs are pending, in progress, and completed? Is it centralized anywhere or still kind of scattered?

— Alex
Gray Horizons Enterprise""",
    ],

    "dental": [
        """\
Hey,

Quick question — how are you handling new patient intake and appointment follow-ups right now? Specifically making sure patients who inquire actually get booked and don't fall off.

We've been working with a few dental practices on exactly that. Curious how you're running it.

— Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is an issue on your end, but — how does your front desk handle it when someone calls for an emergency appointment and the schedule is already full? Is there a system for that or is it mostly judgment call?

Happy to share what we've seen work.

— Alex
Gray Horizons Enterprise""",

        """\
Hey,

Random question — how are you tracking patients who called, got put on a waitlist, and never followed up? That gap between first inquiry and actual booking is where a lot of practices lose people.

Curious if that's something you're actively managing.

— Alex
Gray Horizons Enterprise""",
    ],

    "plumbing": [
        """\
Hey,

Quick one — when an emergency call comes in, how are you routing it to a tech and making sure the customer gets an update without someone manually tracking it the whole time?

We work with plumbing companies to clean up that dispatch-to-completion flow. Curious how you're handling it.

— Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is relevant, but — how are you managing job tracking across your crews right now? Specifically knowing where each job stands without having to call the tech directly.

Happy to compare notes if that's something you deal with.

— Alex
Gray Horizons Enterprise""",

        """\
Hey,

Direct question — when a customer calls about a burst pipe or active leak, what does the first 10 minutes look like on your end? Is dispatch centralized or is it still kind of ad hoc?

— Alex
Gray Horizons Enterprise""",
    ],

    "contractor": [
        """\
Hey,

Quick question — how are you managing the gap between a client's first estimate request and when the actual project kicks off? That handoff tends to be where leads go cold.

We've been working with contracting firms on tightening up that process. Curious how you're running it.

— Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this applies, but — how are you tracking open bids and follow-ups right now? Specifically making sure estimates you sent out actually get a response before they go stale.

Happy to share what we've put together if it's useful.

— Alex
Gray Horizons Enterprise""",

        """\
Hey,

Random question — when a potential client reaches out about a remodel or addition, how quickly does your team get them a quote and follow up? That response window is usually the difference between winning the job and losing it.

Curious how you're handling the volume.

— Alex
Gray Horizons Enterprise""",
    ],
}

NICHE_SUBJECTS = {
    "hoa":        ["Quick question", "How do you handle violation tracking?", "Quick one for you"],
    "hvac":       ["Quick question", "How are you dispatching right now?",    "Quick one for you"],
    "dental":     ["Quick question", "How are you handling new patients?",    "Quick one for you"],
    "plumbing":   ["Quick question", "How do you handle emergency calls?",    "Quick one for you"],
    "contractor": ["Quick question", "How are you managing bids?",            "Quick one for you"],
}

def is_clean_name(name: str) -> bool:
    if not name or len(name) < 3:
        return False
    if name == name.lower() and " " not in name:
        return False
    if re.search(r"[a-z][A-Z]", name):
        return False
    if re.search(r"https?://|\.[a-z]{2,4}(/|$)", name, re.IGNORECASE):
        return False
    if re.search(r"\b20\d{2}\b|^\d", name):
        return False
    if len(name.split()) > 5:
        return False
    return True

def generate_subject(company, niche):
    subjects = NICHE_SUBJECTS.get(niche, NICHE_SUBJECTS["hoa"])
    subject  = random.choice(subjects)
    display  = company if is_clean_name(company) else "your firm"
    return subject.replace("{company}", display)

def generate_message(company, niche):
    templates = NICHE_MESSAGES.get(niche, NICHE_MESSAGES["hoa"])
    template  = random.choice(templates)
    display   = company if is_clean_name(company) else "your team"
    return template.replace("{company}", display)

def run():
    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found yet — skipping outreach generation.")
        return

    df = pd.read_csv(INPUT_FILE).fillna("")

    # Load existing queue to preserve sent/skipped status
    done_emails  = set()
    existing_rows = []
    if os.path.exists(OUTPUT_FILE):
        try:
            existing = pd.read_csv(OUTPUT_FILE).fillna("")
            for _, r in existing.iterrows():
                status = str(r.get("status", "")).strip()
                email  = str(r.get("email",  "")).strip().lower()
                if status in ("sent", "skipped") and email:
                    done_emails.add(email)
                    existing_rows.append(r.to_dict())
        except Exception:
            pass

    rows        = []
    skipped     = 0
    seen_emails = set(done_emails)
    niche_count: dict[str, int] = {}

    junk_patterns = [
        "email@email", "@email.com", "example", "test@", "noreply",
        "placeholder", "demo@", "fake@", "domain.com", "company.com",
        "yourname", "sample@", "null@", "none@", "@mailinator", "@tempmail"
    ]

    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip()
        if email in ("", "nan", "None"):
            skipped += 1
            continue
        if email.lower() in seen_emails:
            skipped += 1
            continue
        e = email.lower()
        if any(p in e for p in junk_patterns):
            skipped += 1
            continue

        seen_emails.add(email.lower())

        company = str(row.get("company", "")).strip()
        niche   = str(row.get("niche",   "hoa")).strip().lower()
        if niche not in NICHE_MESSAGES:
            niche = "hoa"

        rows.append({
            "company": company,
            "name":    "",
            "email":   email,
            "website": row.get("website", ""),
            "niche":   niche,
            "subject": generate_subject(company, niche),
            "message": generate_message(company, niche),
            "status":  "pending",
        })
        niche_count[niche] = niche_count.get(niche, 0) + 1

    out = pd.DataFrame(existing_rows + rows)
    out.to_csv(OUTPUT_FILE, index=False, quoting=1)

    print(f"[DONE] outreach_queue.csv: {len(rows)} new leads added, {len(done_emails)} preserved, {skipped} skipped")
    for n, c in sorted(niche_count.items()):
        print(f"  {n.upper():12s}: {c} leads")

if __name__ == "__main__":
    run()
