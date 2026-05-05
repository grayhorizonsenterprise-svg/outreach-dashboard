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
Hey, this is Alex with Gray Horizons

Most HOA teams we've worked with were losing track of violations between the initial report and final resolution

We fixed that with a simple system that handles tracking and follow-ups automatically

If this is even slightly an issue on your side, I can show you exactly how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex

The biggest issue we keep seeing with HOA teams is violations getting lost between report, board review, and resolution

We built a system that locks that entire process down so nothing slips through

If you want, I can walk you through it and get something similar set up for you quickly

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex with Gray Horizons

HOA teams we've worked with had the same problem - violations documented at the start, then lost somewhere between board review and resolution

We built a system that tracks the full lifecycle automatically so nothing slips

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex

Violation follow-up is where most HOA teams lose time - the documentation exists but pulling it together for a board review or audit takes way longer than it should

We fixed that for a handful of firms and now it runs on its own

I can walk you through the setup this week and show you what it looks like in practice

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex with Gray Horizons

The gap between a homeowner filing a report and that violation being fully resolved is where HOA teams take on the most risk

We built a system that locks that gap down - every step tracked, documented, and followed up automatically

I can get you set up in about a week. Let me know and I'll show you exactly how it works

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex

Straight to it - we help HOA management teams stop losing violations in the handoff between report, tracking, and resolution

Most teams we work with had it happening constantly and didn't realize how much time it was costing

I can show you exactly how we fixed it this week if you want to see it

Alex
Gray Horizons Enterprise""",
    ],

    "hvac": [
        """\
Hey,

Most HVAC companies we work with had the same problem - emergency calls coming in with no centralized way to track from first call to job close-out

We built a system that handles dispatch, updates, and follow-up automatically so nothing falls through

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The gap between a service call being logged and the tech actually getting dispatched is where most HVAC companies lose time and customers

We fixed that for several companies and now it runs without anyone manually tracking it

I can walk you through the setup this week if you want to see it in action

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Missed calls during peak season cost HVAC companies more revenue than almost anything else - the customer calls once, nobody answers, and they book someone else

We built a system that captures those calls and routes them automatically so you stop losing jobs to competitors

I can show you exactly how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

When a customer calls back asking for a job update and nobody on your team knows where it stands - that is the moment you lose the review and the referral

We built a system that keeps every job status updated and visible without anyone having to chase it down

I can get you set up in about a week. Let me know and I will show you how it works

Alex
Gray Horizons Enterprise""",

        """\
Hey,

After a tech finishes a job the follow-up almost never happens automatically - no check-in, no review request, no next appointment

We built that entire post-job flow into a system that runs on its own

I can show you what it looks like and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

HVAC companies lose more revenue to missed and unreturned calls than almost any other gap in the business

We built a system that captures every missed call and routes it back into your pipeline automatically

I can show you exactly how it works this week

Alex
Gray Horizons Enterprise""",
    ],

    "dental": [
        """\
Hey,

Most dental practices we work with were losing new patients between the first inquiry and the actual booking - the follow-up just was not happening consistently

We built a system that handles that entire process automatically so no inquiry goes cold

I can show you exactly how it works and get it running for your practice this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

After-hours voicemails and contact form submissions are where most practices lose new patients - nobody follows up until the next day and by then the patient has booked somewhere else

We built a system that responds and follows up automatically regardless of when they reach out

I can walk you through it this week and show you what it looks like in practice

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Patients who call, get put on a waitlist, and never hear back again are lost revenue that most practices do not even track

We built a system that keeps every patient inquiry active and followed up until they are booked or confirmed out

I can show you how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The gap between a new patient reaching out and actually sitting in your chair is where practices lose the most revenue

We closed that gap for several practices with a system that manages intake, follow-up, and booking automatically

I can get you set up in about a week. Let me know and I will show you exactly how it works

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Patient reactivation is one of the highest-return activities a practice can do - reaching back out to patients who have not been in over a year

We built a system that handles outreach, scheduling, and follow-up automatically so your team does not have to manage it manually

I can show you how it works this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Most practices have hundreds of patients who inquired, never booked, and were never followed up with again

We built a system that recovers those patients automatically - no manual work from your front desk

I can show you exactly how it works and what it would look like for your practice this week

Alex
Gray Horizons Enterprise""",
    ],

    "plumbing": [
        """\
Hey,

The biggest revenue leak for most plumbing companies is missed calls - the customer calls once, nobody answers, and they book someone else before you call back

We built a system that captures every missed call and gets it back into your pipeline automatically

I can show you exactly how it works this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Emergency calls are where plumbing companies win or lose customers - the ones who respond fastest get the job

We built a dispatch system that routes emergency calls to the right tech instantly and keeps the customer updated automatically

I can walk you through it this week and show you what it looks like running

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Most plumbing companies we work with had no system for job tracking across crews - status updates required calling the tech directly every time

We fixed that with a system that keeps every job visible from dispatch to close-out without anyone having to chase it down

I can get you set up in about a week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

After-hours and weekend calls are where most plumbing companies lose the most jobs - by the time someone calls back the customer has already moved on

We built a system that captures and responds to those inquiries automatically so you stop losing jobs to whoever answers first

I can show you exactly how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Post-job follow-up almost never happens in plumbing - no check-in call, no review request, no next service reminder

We built that entire process into a system that runs automatically after every job closes

I can show you what it looks like and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The gap between a job finishing and the customer leaving a review is where most plumbing companies lose their referral pipeline

We built a system that handles post-job follow-up and review collection automatically

I can show you how it works this week

Alex
Gray Horizons Enterprise""",
    ],

    "contractor": [
        """\
Hey,

Most contractors we work with were losing jobs not because of the work but because estimate follow-up was not happening consistently

We built a system that tracks every open bid and follows up automatically until you get a response

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The window between sending an estimate and hearing back is where most contracting jobs go cold - the customer gets another quote and signs with whoever follows up first

We built a system that handles automatic follow-up so you stop losing jobs to faster competitors

I can walk you through it this week

Alex
Gray Horizons Enterprise""",

        """\
Hey,

After-hours inquiries from homeowners are some of the highest-intent leads a contractor gets - and most of them go unanswered until the next day

We built a system that captures and responds to those leads automatically so you are always first to respond

I can show you how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The gap between a lead reaching out and your team getting them a quote is usually where the job goes to a competitor

We built a system that cuts that response time down and automates the follow-up so no lead goes cold

I can get you set up in about a week. Let me know and I will show you exactly how it works

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Contractors lose more jobs to slow follow-up than to price - the client moves on before the estimate even gets a response

We fixed that for several firms with a system that tracks every estimate and follows up automatically

I can show you what that looks like this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

When a homeowner submits a project request through your website or Google listing after hours it almost always sits until the next day

By then they have already called two more contractors

We built a system that responds immediately and keeps them engaged until your team is available

I can show you how it works this week

Alex
Gray Horizons Enterprise""",
    ],

    "landscaping": [
        """\
Hey,

The first company to respond to an estimate request in landscaping almost always wins the job - most homeowners book whoever gets back to them first

We built a system that captures new inquiries and responds automatically so you are always first

I can show you exactly how it works this week

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Seasonal clients who go quiet between services are lost revenue that most landscaping companies never recover

We built a system that keeps every recurring client on schedule with automatic reminders and follow-up

I can walk you through it this week and show you what it looks like running

Alex
Gray Horizons Enterprise""",

        """\
Hey,

When your schedule is full and a new lead comes in it almost always gets lost - there is no system to capture it for later

We built a system that holds every overflow lead and follows up automatically when your schedule opens

I can show you how we set it up this week

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Not trying to waste your time - just wanted to ask: when you have a full schedule and someone new reaches out, how does your team capture that lead without it getting lost?

That overflow moment is usually where companies either grow or miss out.

Alex
Gray Horizons Enterprise""",
    ],

    "roofing": [
        """\
Hey,

Quick one: after a storm comes through your area, how does your team handle the wave of calls that come in? Is there a system to track each one or does it get a little chaotic?

We've been helping roofing companies manage exactly that.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

How are you following up on estimates that went out but never got a response? In roofing those can be pretty high-value jobs to let slip.

Just curious what your current process looks like.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Direct question: when a homeowner calls about a leak or damage and you can't get to them for three days, how do you keep them from calling someone else in the meantime?

That's usually the biggest gap I hear about. Happy to share what we've built if it's useful.

Alex
Gray Horizons Enterprise""",
    ],
}

NICHE_SUBJECTS = {
    "hoa":         ["Violation tracking question", "HOA follow-up process", "Compliance documentation gap", "HOA violation workflow"],
    "hvac":        ["HVAC dispatch question", "Service call follow-up", "Job tracking question", "Missed calls this season"],
    "dental":      ["New patient follow-up", "Appointment booking gap", "Patient intake question", "After-hours inquiry process"],
    "plumbing":    ["Emergency call routing", "Dispatch follow-up question", "Job tracking question", "Missed call recovery"],
    "contractor":  ["Estimate follow-up process", "Bid tracking question", "Lead response time", "Job closing question"],
    "landscaping": ["New lead response time", "Client scheduling question", "Seasonal client follow-up"],
    "roofing":     ["Storm call management", "Estimate follow-up question", "Job pipeline question", "Post-storm inquiry process"],
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
    msg = template.replace("{company}", display)
    if "grayhorizonsenterprise.com" not in msg:
        msg += "\nhttps://grayhorizonsenterprise.com"
    return msg

def run():
    if not os.path.exists(INPUT_FILE):
        print(f"[SKIP] {INPUT_FILE} not found yet - skipping outreach generation.")
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
            # best-effort mapping for alternate spellings
            if niche in ("landscape", "lawn"):
                niche = "landscaping"
            elif niche in ("roof", "roofer"):
                niche = "roofing"
            elif niche in ("electric", "electrician"):
                niche = "contractor"
            else:
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
