"""
grant_outreach_generator.py — Gray Horizons Enterprise
Generates personalized grant writing outreach emails for nonprofits
and small businesses. Reads from grant_queue.csv, writes messages.
"""

import pandas as pd
import os
import sys
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(DATA_DIR, "grant_queue.csv")
CALENDLY   = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
STRIPE_GRANT = os.getenv("STRIPE_GRANT_LINK", "")

SUBJECT_LINES = [
    "Grant funding for {company}",
    "Found 3 grants {company} may qualify for",
    "Quick question about funding for {company}",
    "Grant opportunities — {company}",
    "{company} may be leaving money on the table",
]

MESSAGES = [
    """\
Hey,

I run a grant research service and we came across {company} while looking at organizations in your space.

There are currently 3-5 active federal and private grants your organization likely qualifies for — ranging from $5,000 to $250,000. Most go unclaimed simply because organizations don't have the bandwidth to find and apply.

We handle the full application — research, writing, submission. Flat fee, no retainer.

If you want, I can pull the specific grants we found for you and send them over this week.

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Quick one — we specialize in grant writing for organizations like {company}.

Right now there are several active grants in your sector that are open for applications. The average award we've helped clients secure is $47,000.

We write the full application for a flat fee. If it doesn't get funded, we apply again at no extra charge.

Worth a 15-minute call to see if there's a fit?

Alex
Gray Horizons Enterprise""",

    """\
Hey,

We work with nonprofits and small businesses to identify and apply for grants they qualify for but aren't currently pursuing.

For organizations like {company}, there are usually 4-7 active opportunities at any given time. Most require a strong written application — that's what we do.

Flat fee per application. No upfront retainer. We've helped clients secure between $10,000 and $300,000.

Happy to send over the specific grants we identified for your organization if you're interested.

Alex
Gray Horizons Enterprise""",
]


def generate_subject(company: str) -> str:
    template = random.choice(SUBJECT_LINES)
    return template.format(company=company[:30] if company else "your organization")


def generate_message(company: str) -> str:
    template = random.choice(MESSAGES)
    return template.format(company=company if company else "your organization")


def run():
    if not os.path.exists(QUEUE_FILE):
        print("[GRANT] No grant_queue.csv found — run nonprofit_scraper.py first")
        return

    df = pd.read_csv(QUEUE_FILE).fillna("")

    needs_message = df[
        (df["email"].str.strip() != "") &
        (df.get("message", pd.Series([""] * len(df))).str.strip() == "") &
        (df["status"] == "pending")
    ].copy()

    print(f"[GRANT] Generating outreach for {len(needs_message)} grant prospects...")

    for i, row in needs_message.iterrows():
        company = str(row.get("company", "")).strip()
        df.at[i, "subject"] = generate_subject(company)
        df.at[i, "message"] = generate_message(company)

    df.to_csv(QUEUE_FILE, index=False)
    print(f"[GRANT] Done — messages generated")


if __name__ == "__main__":
    run()
