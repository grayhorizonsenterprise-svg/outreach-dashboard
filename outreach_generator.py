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

HOA teams we've worked with had the same problem — violations documented at the start, then lost somewhere between board review and resolution

We built a system that tracks the full lifecycle automatically so nothing slips

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex

Violation follow-up is where most HOA teams lose time — the documentation exists but pulling it together for a board review or audit takes way longer than it should

We fixed that for a handful of firms and now it runs on its own

I can walk you through the setup this week and show you what it looks like in practice

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex with Gray Horizons

The gap between a homeowner filing a report and that violation being fully resolved is where HOA teams take on the most risk

We built a system that locks that gap down — every step tracked, documented, and followed up automatically

I can get you set up in about a week. Let me know and I'll show you exactly how it works

Alex
Gray Horizons Enterprise""",

        """\
Hey, this is Alex

Straight to it — we help HOA management teams stop losing violations in the handoff between report, tracking, and resolution

Most teams we work with had it happening constantly and didn't realize how much time it was costing

I can show you exactly how we fixed it this week if you want to see it

Alex
Gray Horizons Enterprise""",
    ],

    "hvac": [
        """\
Hey,

Quick one: when a customer calls in for an emergency repair, how are you dispatching and tracking that job from the first call to close-out? Still phone and spreadsheet, or do you have a system?

We've been working with HVAC companies to tighten up that gap. Curious how you're handling it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is relevant, but how are you managing your service calls and maintenance schedules right now? Specifically keeping techs, customers, and follow-ups all in sync without things falling through.

Happy to share what we've seen work well if it's useful.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Wanted to ask something real quick: during peak season when calls are stacking up, how does your team keep track of which jobs are pending, in progress, and completed? Is it centralized anywhere or still kind of scattered?

Alex
Gray Horizons Enterprise""",

        """\
Hi,

How do you handle it when a customer calls back three days later asking for an update on their service request and no one on the team knows where that job stands? That one comes up a lot with HVAC companies I talk to.

Genuinely curious how you manage it.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

One quick question: after a tech finishes a job, how does that get communicated back to the office and to the customer? Is there a system for that or is it still mostly a phone call?

Happy to share what we've put together if you're open to it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not a pitch — just wanted to ask how you're handling missed calls during busy periods. Specifically when someone calls for a repair and doesn't reach anyone, what happens to that lead?

That gap is usually where a lot of revenue walks out the door.

Alex
Gray Horizons Enterprise""",
    ],

    "dental": [
        """\
Hey,

Quick question: how are you handling new patient intake and appointment follow-ups right now? Specifically making sure patients who inquire actually get booked and don't fall off.

We've been working with a few dental practices on exactly that. Curious how you're running it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is an issue on your end, but how does your front desk handle it when someone calls for an emergency appointment and the schedule is already full? Is there a system for that or is it mostly judgment call?

Happy to share what we've seen work.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Random question: how are you tracking patients who called, got put on a waitlist, and never followed up? That gap between first inquiry and actual booking is where a lot of practices lose people.

Curious if that's something you're actively managing.

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Not a pitch — just wanted to ask: when a potential new patient fills out a contact form or leaves a voicemail after hours, what's the follow-up process? Do they hear back the same day or does it depend on who picks it up?

That's usually where practices lose the most new patients.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Quick one: how many new patient inquiries would you say your office gets in a week where someone reaches out but never actually books? Even a rough number.

We've been helping practices recover those. Happy to share how if it's useful.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

How are you handling patient reactivation right now — people who haven't been in for over a year? Is that something your team actively reaches out on or does it tend to fall through the cracks?

Just curious what your process looks like.

Alex
Gray Horizons Enterprise""",
    ],

    "plumbing": [
        """\
Hey,

Quick one: when an emergency call comes in, how are you routing it to a tech and making sure the customer gets an update without someone manually tracking it the whole time?

We work with plumbing companies to clean up that dispatch-to-completion flow. Curious how you're handling it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this is relevant, but how are you managing job tracking across your crews right now? Specifically knowing where each job stands without having to call the tech directly.

Happy to compare notes if that's something you deal with.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Direct question: when a customer calls about a burst pipe or active leak, what does the first 10 minutes look like on your end? Is dispatch centralized or is it still kind of ad hoc?

Alex
Gray Horizons Enterprise""",

        """\
Hi,

One thing I hear a lot from plumbing companies: by the time they call back a missed lead, someone else already got there. How are you handling after-hours calls and weekend inquiries right now?

Curious what your process looks like.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Not trying to take up much of your time — just wanted to ask: when a job gets finished, how does your team handle following up with the customer to check in or ask for a review? Is that something you have a process for?

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

How many calls does your office miss on an average day — calls that don't get a callback or get lost in the shuffle? We've been helping plumbing companies capture those and turn them into booked jobs.

Happy to share how if it's useful.

Alex
Gray Horizons Enterprise""",
    ],

    "contractor": [
        """\
Hey,

Quick question: how are you managing the gap between a client's first estimate request and when the actual project kicks off? That handoff tends to be where leads go cold.

We've been working with contracting firms on tightening up that process. Curious how you're running it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not sure if this applies, but how are you tracking open bids and follow-ups right now? Specifically making sure estimates you sent out actually get a response before they go stale.

Happy to share what we've put together if it's useful.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Random question: when a potential client reaches out about a remodel or addition, how quickly does your team get them a quote and follow up? That response window is usually the difference between winning the job and losing it.

Curious how you're handling the volume.

Alex
Gray Horizons Enterprise""",

        """\
Hi,

One thing I keep hearing from contractors: they're great at the work but the leads that don't convert are usually the ones where follow-up fell through. Is that something you track, or does it kind of get lost once the estimate goes out?

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Quick one: when you send an estimate and don't hear back for a week, does your team follow up automatically or does it depend on someone remembering to do it?

We've been helping contractors close more jobs by automating that part. Happy to share what that looks like.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

Not a pitch — just wanted to ask: how do you handle it when a homeowner reaches out through your website or Google listing after hours? Is there a system that captures and responds to that, or does it sit until someone gets to it the next day?

That after-hours window is usually where a lot of jobs go to a competitor.

Alex
Gray Horizons Enterprise""",
    ],

    "landscaping": [
        """\
Hey,

Quick question: when a homeowner calls for an estimate, how quickly does your team get back to them? In landscaping that first response window is usually what wins or loses the job.

Curious how you're handling it.

Alex
Gray Horizons Enterprise""",

        """\
Hi there,

How are you managing recurring client schedules and reminders right now? Specifically making sure seasonal clients don't fall off or go quiet between services.

Happy to compare notes if that's something you deal with.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Not trying to waste your time — just wanted to ask: when you have a full schedule and someone new reaches out, how does your team capture that lead without it getting lost?

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
    "hoa":          ["Quick question", "How do you handle violation tracking?", "Quick one for you", "HOA compliance question"],
    "hvac":         ["Quick question", "How are you dispatching right now?",    "Quick one for you", "HVAC service tracking"],
    "dental":       ["Quick question", "How are you handling new patients?",    "Quick one for you", "New patient follow-up"],
    "plumbing":     ["Quick question", "How do you handle emergency calls?",    "Quick one for you", "Dispatch question"],
    "contractor":   ["Quick question", "How are you managing bids?",            "Quick one for you", "Estimate follow-up"],
    "landscaping":  ["Quick question", "How are you handling new leads?",       "Quick one for you"],
    "roofing":      ["Quick question", "How are you managing storm calls?",     "Quick one for you", "Storm season question"],
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
