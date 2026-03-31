import pandas as pd
import random
import re
import os

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE  = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "outreach_queue.csv")

SUBJECTS = [
    "how do you handle violation tracking?",
    "quick question about your workflow",
    "how does your team handle this?",
    "had a question about {company}",
    "saw your firm — quick question",
]

def generate_subject(company):
    subject = random.choice(SUBJECTS)
    return subject.replace("{company}", company)

MESSAGES = [
    """\
Hey,

Came across {company} and wanted to reach out directly.

I'm curious — when a homeowner submits a violation or complaint, how does your team keep track of it from that first report all the way to resolution? Still email threads, or do you have something built out?

Reason I'm asking is we work with a few HOA firms and that handoff tends to be where things fall through. We put together something pretty simple that keeps it all in one place, and I wanted to see if it's even a problem you're running into.

Either way, happy to chat if it's relevant.

Alex
Gray Horizons Enterprise
grayhorizonsenterprise.com\
""",
    """\
Hi there,

I noticed {company} while doing some research on HOA management firms and wanted to shoot you a quick note.

How are you guys currently handling violation notices and compliance documentation across your communities? I ask because it's one of those things that sounds simple but gets messy fast once you're managing more than a handful of associations.

We've been helping firms like yours get that process a lot tighter — nothing complicated, just a cleaner way to track things end to end.

Worth a 15-minute call if that's something you're actively dealing with. No pressure either way.

Alex
Gray Horizons Enterprise
grayhorizonsenterprise.com\
""",
    """\
Hey,

Found {company} while looking into firms managing communities on the West Coast — reached out because I had a genuine question.

How does your team currently deal with violation management across multiple HOAs? Specifically the documentation side — keeping records, following up, making sure nothing gets dropped.

We built something that a few management firms have been using to clean that up. Some were doing it in spreadsheets, some in email, some in a mix of both. Not here to pitch hard — just wanted to see if it's a headache you're familiar with.

Let me know if it's worth talking.

Alex
Gray Horizons Enterprise
grayhorizonsenterprise.com\
""",
    """\
Hi,

Quick one — how does {company} handle it when a community board flags a violation? Is there a system in place or is it mostly managed through email and manual follow-up?

I work with HOA management firms to tighten up that process, specifically around tracking and documentation so things don't fall through the cracks between the board and the management team.

If that's something you're still piecing together, I'd love to show you what we've built. Takes about 10 minutes to see if it's even relevant to how you operate.

Alex
Gray Horizons Enterprise
grayhorizonsenterprise.com\
""",
    """\
Hey,

Reached out because I came across {company} and it looked like you guys are running a real operation — wanted to ask a direct question.

When your team gets a violation report or a compliance issue from one of your HOAs, where does it live? Email inbox, shared doc, some software? Or is it still kind of scattered depending on who's handling it?

We work with management firms that were dealing with exactly that and helped them get it centralized. Not trying to sell you anything today — just genuinely wanted to know if it's on your radar.

Happy to show you what it looks like if you're curious.

Alex
Gray Horizons Enterprise
grayhorizonsenterprise.com\
""",
]

def is_clean_name(name: str) -> bool:
    """Returns True if the name is human-readable enough to use in an email."""
    if not name or len(name) < 3:
        return False
    # Domain slugs: all lowercase with no spaces
    if name == name.lower() and " " not in name:
        return False
    # CamelCase stuck together
    if re.search(r"[a-z][A-Z]", name):
        return False
    # Contains URL-like patterns
    if re.search(r"https?://|\.[a-z]{2,4}(/|$)", name, re.IGNORECASE):
        return False
    # Has a year or looks like a sentence
    if re.search(r"\b20\d{2}\b|^\d", name):
        return False
    # Too long — still a page title fragment
    if len(name.split()) > 5:
        return False
    return True


def generate_subject(company):
    subject = random.choice(SUBJECTS)
    display = company if is_clean_name(company) else "your firm"
    return subject.replace("{company}", display)


def generate_message(company):
    template = random.choice(MESSAGES)
    if is_clean_name(company):
        return template.replace("{company}", company)
    else:
        # Use generic but still natural phrasing
        return (template
                .replace("{company}", "your firm")
                .replace("Hi {company}", "Hi there")
                .replace("Hi your firm team,", "Hi there,")
                .replace("Hi your firm,", "Hi there,"))

def run():
    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found yet — skipping outreach generation.")
        return
    df = pd.read_csv(INPUT_FILE)

    # Load existing queue to preserve sent/skipped status
    done_emails = set()
    existing_rows = []
    if os.path.exists(OUTPUT_FILE):
        try:
            existing = pd.read_csv(OUTPUT_FILE).fillna("")
            for _, r in existing.iterrows():
                status = str(r.get("status", "")).strip()
                email  = str(r.get("email", "")).strip().lower()
                if status in ("sent", "skipped") and email:
                    done_emails.add(email)
                    existing_rows.append(r.to_dict())
        except Exception:
            pass

    rows = []
    skipped = 0
    seen_emails = set(done_emails)

    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip()

        # Only include leads where we have a confirmed email
        if email in ("", "nan", "None"):
            skipped += 1
            continue

        # Skip duplicates and already-processed emails
        if email.lower() in seen_emails:
            skipped += 1
            continue
        seen_emails.add(email.lower())

        company = str(row.get("company", "")).strip()

        rows.append({
            "company": company,
            "name": "",
            "email": email,
            "website": row.get("website", ""),
            "subject": generate_subject(company),
            "message": generate_message(company),
            "status": "pending"
        })

    out = pd.DataFrame(existing_rows + rows)
    out.to_csv(OUTPUT_FILE, index=False, quoting=1)

    print(f"[DONE] outreach_queue.csv: {len(rows)} new leads added, {len(done_emails)} preserved, {skipped} skipped")

if __name__ == "__main__":
    run()
