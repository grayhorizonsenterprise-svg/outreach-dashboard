import pandas as pd
import random
import re
import os

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE    = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE   = os.path.join(DATA_DIR, "outreach_queue.csv")
CALENDLY_URL  = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")

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

        """\
Hey,

Quick question - when a violation gets reported, what does your process look like from that initial report to final resolution? Is there a system tracking each step or is it mostly email threads?

That gap is where most HOA teams run into problems.

Alex
Gray Horizons Enterprise""",

        """\
Hey,

When a board member asks for a status update on an open violation, how long does it take your team to pull that together?

We've been working on cutting that time down. Happy to show you what we built if it's relevant.

Alex
Gray Horizons Enterprise""",
    ],

    "hvac": [
        """\
Hey,

HVAC companies with a full schedule typically miss 15-20 calls a week during peak season. At an average job value of $450, that's $6,750-$9,000 walking out the door every week.

We set up an automated follow-up system for HVAC shops that catches every missed inquiry and follows up immediately - so the customer hears from you before they book someone else.

Three shops we've set this up for recovered 6-10 jobs in the first month they'd have otherwise lost.

Worth a 20-minute call to see if it fits? {calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Quick question - when your line is busy or it's after hours and a customer calls about a broken AC or furnace, what happens to that call?

If it goes to voicemail, research shows 80% of those customers book the next company that answers before you call back.

We built a follow-up system that responds to those inquiries automatically and keeps them engaged until your team can get them on the schedule. Happy to show you how it works in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Most HVAC owners I talk to say the same thing - the jobs they lose aren't from bad work, they're from slow follow-up. Estimate sent, no response, job goes to whoever follows up first.

We built an automated system that follows up on every open estimate and every missed inquiry without anyone on your team having to do it manually.

If that sounds like something worth looking at, grab a time here: {calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hi,

The average HVAC company loses $45,000-$120,000 per year to missed and unreturned calls. Most owners don't realize it because there's no system tracking what's being lost.

We fix that. I can show you exactly what it looks like for a shop your size in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise""",
    ],

    "dental": [
        """\
Hey,

The average dental practice loses 8-12 new patients every month to slow follow-up. A patient submits a form or calls after hours, nobody responds until the next morning, and by then they've booked somewhere else.

At $1,200 average lifetime value per new patient, that's $9,600-$14,400 a month slipping through.

We built a follow-up system that responds to every new patient inquiry immediately - even at 11pm - and keeps them engaged until they're booked. Happy to show you how it works in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Quick question for you - when a new patient submits a form on your website at 8pm on a Tuesday, what happens to that inquiry?

If it sits until the next morning, research shows 78% of those patients have already booked somewhere else by the time you call back.

We fix that with an automated follow-up system. Three practices we've set this up for saw immediate increases in new patient bookings in the first 30 days.

Worth 20 minutes to see the setup? {calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hey,

Most practices have 200-400 patients who called or filled out a form, never booked, and were never followed up with again. That's $240,000-$480,000 in lost lifetime value sitting in a spreadsheet or voicemail box.

We built a reactivation system that reaches back out to those patients automatically and gets them back on the schedule.

I can show you what this looks like for your practice in 20 minutes: {calendly}

Alex
Gray Horizons Enterprise""",

        """\
Hi,

Patient no-shows cost the average dental practice $50,000-$150,000 per year in lost chair time. Most practices send one reminder. We send an automated sequence that cuts no-show rates by 40-60%.

Happy to walk you through exactly how it works: {calendly}

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

        """\
Hey,

Direct question - when an emergency call comes in at night and your main line is busy, how does your team handle it? Does it route somewhere or go to voicemail?

That's usually the biggest gap I hear about from plumbing companies.

Alex
Gray Horizons Enterprise""",

        """\
Hi,

When you finish a job, what does the follow-up process look like? Is there anything automated that checks in with the customer, or does it depend on the tech remembering to do it?

We've built that whole post-job flow into a system. Happy to show you how it works.

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

        """\
Hey,

When you send out an estimate and don't hear back, what does your follow-up process look like? Is there a system tracking each open bid or does it depend on whoever sent it remembering to follow up?

That's usually where jobs go cold.

Alex
Gray Horizons Enterprise""",

        """\
Hi,

After-hours leads from homeowners - when they come in through your website or Google listing at night, what happens to them? Does something catch it automatically or does it sit until morning?

Just asking because that's usually where the fastest-responding contractor wins the job.

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

NICHE_MESSAGES["auto"] = [
    """\
Hey,

When someone calls about a repair and you're backed up, what happens to that call? Does it get logged or does it depend on whoever picks up remembering to follow through?

That's usually where shops lose the most appointments without realizing it.

Alex
Gray Horizons Enterprise""",

    """\
Hi,

After a repair is done, does your shop have anything that automatically follows up with the customer — check-in, review request, next service reminder?

Most shops we've worked with said that whole process was completely manual.

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Direct question — when a customer calls for a quote and you don't hear back, how does your team track that? Is there a system following up or does it fall off?

Happy to show you what we've built for this if it's relevant.

Alex
Gray Horizons Enterprise""",

    """\
Hi,

Missed calls during your busiest hours are probably your biggest revenue leak. The customer calls once, nobody picks up, and they book somewhere else before you call back.

We built a system that catches those and routes them automatically. I can show you how it works.

Alex
Gray Horizons Enterprise""",
]

NICHE_MESSAGES["chiropractic"] = [
    """\
Hey,

New patient calls that come in after hours or while the front desk is with someone — what happens to those? Is there something catching them automatically or do they go to voicemail?

That gap is where most practices lose new patients without realizing it.

Alex
Gray Horizons Enterprise""",

    """\
Hi,

When a new patient inquiry comes in through your website or a referral calls after hours, how fast does your team typically follow up?

The practices we've worked with said that window was their biggest drop-off point for new patients.

Alex
Gray Horizons Enterprise""",

    """\
Hey,

Patient reactivation — reaching back out to patients who haven't been in for 3-6 months — is one of the highest-return things a practice can do. Most don't do it because it's manual.

We automated that entire process for a few practices. Happy to show you what it looks like.

Alex
Gray Horizons Enterprise""",
]

NICHE_MESSAGES["realestate"] = [
    """\
Hey,

When a new buyer or seller inquiry comes in through your website at night or on the weekend, how fast does your team get back to them?

In real estate that response window is usually where the lead goes to whoever calls back first.

Alex
Gray Horizons Enterprise""",

    """\
Hi,

Leads that go cold between first inquiry and first showing — how does your team track and follow up on those? Is there a system or does it depend on the agent remembering?

That follow-up gap is where most agencies lose deals they should have closed.

Alex
Gray Horizons Enterprise""",

    """\
Hey,

After a showing, what does your follow-up process look like? Is there anything automated that checks in with the buyer, or is it all manual from the agent?

We built that entire post-showing flow into a system for a few agencies. Happy to walk you through it.

Alex
Gray Horizons Enterprise""",
]

NICHE_MESSAGES["salon"] = [
    """\
Hey,

When a client tries to book online and your calendar is full, what happens to that request? Does it get captured somewhere or does that client just go book somewhere else?

That overflow moment is usually where salons lose their best new clients.

Alex
Gray Horizons Enterprise""",

    """\
Hi,

Clients who haven't been in for 60-90 days — is there anything that automatically reaches back out to them, or does that depend on someone on your staff remembering?

We built a reactivation system for a few salons that runs completely on its own.

Alex
Gray Horizons Enterprise""",

    """\
Hey,

After-hours booking requests — when someone fills out your contact form at 10pm, what happens to it? Does something respond automatically or does it sit until morning?

By morning they've usually booked somewhere else.

Alex
Gray Horizons Enterprise""",
]

NICHE_SUBJECTS = {
    "hoa":          ["Quick question", "How do you handle this?", "Something we built for HOA teams", "Process question"],
    "hvac":         ["Quick question", "Something we built", "How do you handle this?", "Question for you"],
    "dental":       ["Quick question", "Something we built for practices", "How do you handle this?", "Question for you"],
    "plumbing":     ["Quick question", "Something we built", "How do you handle missed calls?", "Question for you"],
    "contractor":   ["Quick question", "Something we built for contractors", "How do you handle this?", "Question for you"],
    "landscaping":  ["Quick question", "Something we built", "How do you handle overflow leads?"],
    "roofing":      ["Quick question", "Something we built for roofers", "How do you handle this?", "Question for you"],
    "auto":         ["Quick question", "Something we built for shops", "How do you handle this?", "Question for you"],
    "chiropractic": ["Quick question", "Something we built for practices", "How do you handle this?", "Question for you"],
    "realestate":   ["Quick question", "Something we built for agents", "How do you handle this?", "Question for you"],
    "salon":        ["Quick question", "Something we built for salons", "How do you handle this?", "Question for you"],
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

def _add_periods(msg):
    skip = {"hey", "hi", "alex", "gray horizons enterprise", "https://grayhorizonsenterprise.com"}
    lines = msg.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped.lower() not in skip and not stripped.startswith("http"):
            if stripped[-1] not in ".!?,;:":
                line = line.rstrip() + "."
        out.append(line)
    return "\n".join(out)

def generate_message(company, niche):
    templates = NICHE_MESSAGES.get(niche, NICHE_MESSAGES["hoa"])
    template  = random.choice(templates)
    display   = company if is_clean_name(company) else "your team"
    msg = template.replace("{company}", display)
    msg = msg.replace("{calendly}", CALENDLY_URL)
    msg = _add_periods(msg)
    if "grayhorizonsenterprise.com" not in msg and CALENDLY_URL not in msg:
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

    # Never email these — large corporations, insurance, hospitals, government
    corporate_email_blocks = [
        "bcbs", "bluecross", "blueshield", "aetna", "cigna", "humana",
        "anthem", "molina", "kaiser", "unitedhealthcare", "centene",
        ".gov", ".edu", ".mil",
    ]
    corporate_name_blocks = [
        "blue cross", "blue shield", "bcbs", "aetna", "cigna", "humana",
        "anthem", "molina", "kaiser", "united health", "centene",
        "hospital", "health system", "medical center", "health network",
        "insurance company", "insurance group", "insurance co",
        "university", "college", "school district", "public school",
        "city of ", "county of ", "state of ", "department of ",
        "township", "municipality", "government",
        "nationwide", "national chain", "franchise",
        "chamber of commerce", "nonprofit", "non-profit", "foundation",
        # Software platforms and large management companies (have ticket systems)
        "software", "platform", "saas", "tech solutions", "technologies",
        "opencare", "rowcal", "appfolio", "buildium", "propertyware",
        "management company", "management group", "management corp",
        "national association", "association of ", " association",
    ]

    # Also block support@ emails — companies with support@ have ticket systems, not owners
    corporate_email_blocks.extend(["support@", "ticket@", "helpdesk@", "info@opencare", "info@rowcal"])

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
        # Block corporate/insurance/government emails
        if any(p in e for p in corporate_email_blocks):
            skipped += 1
            continue

        seen_emails.add(email.lower())

        company = str(row.get("company", "")).strip()
        company_lower = company.lower()

        # Block corporate/institutional company names
        if any(p in company_lower for p in corporate_name_blocks):
            seen_emails.discard(email.lower())
            skipped += 1
            continue

        niche   = str(row.get("niche",   "hoa")).strip().lower()
        if niche not in NICHE_MESSAGES:
            # best-effort mapping for alternate spellings
            if niche in ("landscape", "lawn", "lawn care"):
                niche = "landscaping"
            elif niche in ("roof", "roofer"):
                niche = "roofing"
            elif niche in ("electric", "electrician"):
                niche = "contractor"
            elif niche in ("auto repair", "mechanic", "auto shop"):
                niche = "auto"
            elif niche in ("chiropractor", "chiro"):
                niche = "chiropractic"
            elif niche in ("real estate", "realtor", "realty"):
                niche = "realestate"
            elif niche in ("hair salon", "spa", "beauty", "nail salon"):
                niche = "salon"
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
