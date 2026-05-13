import pandas as pd
import random
import re
import os

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE    = os.path.join(DATA_DIR, "prospects_raw.csv")
OUTPUT_FILE   = os.path.join(DATA_DIR, "outreach_queue.csv")
CALENDLY_URL  = "https://calendly.com/grayhorizonsenterprise/30min"
STRIPE_LINK   = os.getenv("STRIPE_PAYMENT_LINK", "https://grayhorizonsenterprise.com")
GUMROAD_STORE = "horizons56.gumroad.com"

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
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey, this is Alex

The biggest issue we keep seeing with HOA teams is violations getting lost between report, board review, and resolution

We built a system that locks that entire process down so nothing slips through

If you want, I can walk you through it and get something similar set up for you quickly

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey, this is Alex with Gray Horizons

HOA teams we've worked with had the same problem - violations documented at the start, then lost somewhere between board review and resolution

We built a system that tracks the full lifecycle automatically so nothing slips

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey, this is Alex

Violation follow-up is where most HOA teams lose time - the documentation exists but pulling it together for a board review or audit takes way longer than it should

We fixed that for a handful of firms and now it runs on its own

I can walk you through the setup this week and show you what it looks like in practice

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey, this is Alex with Gray Horizons

The gap between a homeowner filing a report and that violation being fully resolved is where HOA teams take on the most risk

We built a system that locks that gap down - every step tracked, documented, and followed up automatically

I can get you set up in about a week. Let me know and I'll show you exactly how it works

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey, this is Alex

Straight to it - we help HOA management teams stop losing violations in the handoff between report, tracking, and resolution

Most teams we work with had it happening constantly and didn't realize how much time it was costing

I can show you exactly how we fixed it this week if you want to see it

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Quick question - when a violation gets reported, what does your process look like from that initial report to final resolution? Is there a system tracking each step or is it mostly email threads?

That gap is where most HOA teams run into problems.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

When a board member asks for a status update on an open violation, how long does it take your team to pull that together?

We've been working on cutting that time down. Happy to show you what we built if it's relevant.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "hvac": [
        """\
Hey,

HVAC companies with a full schedule typically miss 15-20 calls a week during peak season. At an average job value of $450, that's $6,750-$9,000 walking out the door every week.

We set up an automated follow-up system for HVAC shops that catches every missed inquiry and follows up immediately - so the customer hears from you before they book someone else.

Three shops we've set this up for recovered 6-10 jobs in the first month they'd have otherwise lost.

Worth a 20-minute call to see if it fits? {calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

Quick question - when your line is busy or it's after hours and a customer calls about a broken AC or furnace, what happens to that call?

If it goes to voicemail, research shows 80% of those customers book the next company that answers before you call back.

We built a follow-up system that responds to those inquiries automatically and keeps them engaged until your team can get them on the schedule. Happy to show you how it works in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Most HVAC owners I talk to say the same thing - the jobs they lose aren't from bad work, they're from slow follow-up. Estimate sent, no response, job goes to whoever follows up first.

We built an automated system that follows up on every open estimate and every missed inquiry without anyone on your team having to do it manually.

If that sounds like something worth looking at, grab a time here: {calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

The average HVAC company loses $45,000-$120,000 per year to missed and unreturned calls. Most owners don't realize it because there's no system tracking what's being lost.

We fix that. I can show you exactly what it looks like for a shop your size in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "dental": [
        """\
Hey,

The average dental practice loses 8-12 new patients every month to slow follow-up. A patient submits a form or calls after hours, nobody responds until the next morning, and by then they've booked somewhere else.

At $1,200 average lifetime value per new patient, that's $9,600-$14,400 a month slipping through.

We built a follow-up system that responds to every new patient inquiry immediately - even at 11pm - and keeps them engaged until they're booked. Happy to show you how it works in 20 minutes.

{calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

Quick question for you - when a new patient submits a form on your website at 8pm on a Tuesday, what happens to that inquiry?

If it sits until the next morning, research shows 78% of those patients have already booked somewhere else by the time you call back.

We fix that with an automated follow-up system. Three practices we've set this up for saw immediate increases in new patient bookings in the first 30 days.

Worth 20 minutes to see the setup? {calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Most practices have 200-400 patients who called or filled out a form, never booked, and were never followed up with again. That's $240,000-$480,000 in lost lifetime value sitting in a spreadsheet or voicemail box.

We built a reactivation system that reaches back out to those patients automatically and gets them back on the schedule.

I can show you what this looks like for your practice in 20 minutes: {calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

Patient no-shows cost the average dental practice $50,000-$150,000 per year in lost chair time. Most practices send one reminder. We send an automated sequence that cuts no-show rates by 40-60%.

Happy to walk you through exactly how it works: {calendly}

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "plumbing": [
        """\
Hey,

The biggest revenue leak for most plumbing companies is missed calls - the customer calls once, nobody answers, and they book someone else before you call back

We built a system that captures every missed call and gets it back into your pipeline automatically

I can show you exactly how it works this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

Emergency calls are where plumbing companies win or lose customers - the ones who respond fastest get the job

We built a dispatch system that routes emergency calls to the right tech instantly and keeps the customer updated automatically

I can walk you through it this week and show you what it looks like running

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Most plumbing companies we work with had no system for job tracking across crews - status updates required calling the tech directly every time

We fixed that with a system that keeps every job visible from dispatch to close-out without anyone having to chase it down

I can get you set up in about a week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

After-hours and weekend calls are where most plumbing companies lose the most jobs - by the time someone calls back the customer has already moved on

We built a system that captures and responds to those inquiries automatically so you stop losing jobs to whoever answers first

I can show you exactly how we set it up this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Post-job follow-up almost never happens in plumbing - no check-in call, no review request, no next service reminder

We built that entire process into a system that runs automatically after every job closes

I can show you what it looks like and get it running for your team this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

The gap between a job finishing and the customer leaving a review is where most plumbing companies lose their referral pipeline

We built a system that handles post-job follow-up and review collection automatically

I can show you how it works this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Direct question - when an emergency call comes in at night and your main line is busy, how does your team handle it? Does it route somewhere or go to voicemail?

That's usually the biggest gap I hear about from plumbing companies.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

When you finish a job, what does the follow-up process look like? Is there anything automated that checks in with the customer, or does it depend on the tech remembering to do it?

We've built that whole post-job flow into a system. Happy to show you how it works.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "contractor": [
        """\
Hey,

Most contractors we work with were losing jobs not because of the work but because estimate follow-up was not happening consistently

We built a system that tracks every open bid and follows up automatically until you get a response

I can show you exactly how it works and get it running for your team this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

The window between sending an estimate and hearing back is where most contracting jobs go cold - the customer gets another quote and signs with whoever follows up first

We built a system that handles automatic follow-up so you stop losing jobs to faster competitors

I can walk you through it this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

After-hours inquiries from homeowners are some of the highest-intent leads a contractor gets - and most of them go unanswered until the next day

We built a system that captures and responds to those leads automatically so you are always first to respond

I can show you how we set it up this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

The gap between a lead reaching out and your team getting them a quote is usually where the job goes to a competitor

We built a system that cuts that response time down and automates the follow-up so no lead goes cold

I can get you set up in about a week. Let me know and I will show you exactly how it works

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Contractors lose more jobs to slow follow-up than to price - the client moves on before the estimate even gets a response

We fixed that for several firms with a system that tracks every estimate and follows up automatically

I can show you what that looks like this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

When a homeowner submits a project request through your website or Google listing after hours it almost always sits until the next day

By then they have already called two more contractors

We built a system that responds immediately and keeps them engaged until your team is available

I can show you how it works this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

When you send out an estimate and don't hear back, what does your follow-up process look like? Is there a system tracking each open bid or does it depend on whoever sent it remembering to follow up?

That's usually where jobs go cold.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

After-hours leads from homeowners - when they come in through your website or Google listing at night, what happens to them? Does something catch it automatically or does it sit until morning?

Just asking because that's usually where the fastest-responding contractor wins the job.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "landscaping": [
        """\
Hey,

The first company to respond to an estimate request in landscaping almost always wins the job - most homeowners book whoever gets back to them first

We built a system that captures new inquiries and responds automatically so you are always first

I can show you exactly how it works this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi,

Seasonal clients who go quiet between services are lost revenue that most landscaping companies never recover

We built a system that keeps every recurring client on schedule with automatic reminders and follow-up

I can walk you through it this week and show you what it looks like running

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

When your schedule is full and a new lead comes in it almost always gets lost - there is no system to capture it for later

We built a system that holds every overflow lead and follows up automatically when your schedule opens

I can show you how we set it up this week

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Not trying to waste your time - just wanted to ask: when you have a full schedule and someone new reaches out, how does your team capture that lead without it getting lost?

That overflow moment is usually where companies either grow or miss out.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],

    "roofing": [
        """\
Hey,

Quick one: after a storm comes through your area, how does your team handle the wave of calls that come in? Is there a system to track each one or does it get a little chaotic?

We've been helping roofing companies manage exactly that.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hi there,

How are you following up on estimates that went out but never got a response? In roofing those can be pretty high-value jobs to let slip.

Just curious what your current process looks like.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

        """\
Hey,

Direct question: when a homeowner calls about a leak or damage and you can't get to them for three days, how do you keep them from calling someone else in the meantime?

That's usually the biggest gap I hear about. Happy to share what we've built if it's useful.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
    ],
}

NICHE_MESSAGES["auto"] = [
    """\
Hey,

When someone calls about a repair and you're backed up, what happens to that call? Does it get logged or does it depend on whoever picks up remembering to follow through?

That's usually where shops lose the most appointments without realizing it.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hi,

After a repair is done, does your shop have anything that automatically follows up with the customer, check-in, review request, next service reminder?

Most shops we've worked with said that whole process was completely manual.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hey,

Direct question, when a customer calls for a quote and you don't hear back, how does your team track that? Is there a system following up or does it fall off?

Happy to show you what we've built for this if it's relevant.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hi,

Missed calls during your busiest hours are probably your biggest revenue leak. The customer calls once, nobody picks up, and they book somewhere else before you call back.

We built a system that catches those and routes them automatically. I can show you how it works.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
]

NICHE_MESSAGES["chiropractic"] = [
    """\
Hey,

New patient calls that come in after hours or while the front desk is with someone, what happens to those? Is there something catching them automatically or do they go to voicemail?

That gap is where most practices lose new patients without realizing it.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hi,

When a new patient inquiry comes in through your website or a referral calls after hours, how fast does your team typically follow up?

The practices we've worked with said that window was their biggest drop-off point for new patients.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hey,

Patient reactivation, reaching back out to patients who haven't been in for 3-6 months, is one of the highest-return things a practice can do. Most don't do it because it's manual.

We automated that entire process for a few practices. Happy to show you what it looks like.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
]

NICHE_MESSAGES["realestate"] = [
    """\
Hey,

When a new buyer or seller inquiry comes in through your website at night or on the weekend, how fast does your team get back to them?

In real estate that response window is usually where the lead goes to whoever calls back first.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hi,

Leads that go cold between first inquiry and first showing, how does your team track and follow up on those? Is there a system or does it depend on the agent remembering?

That follow-up gap is where most agencies lose deals they should have closed.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hey,

After a showing, what does your follow-up process look like? Is there anything automated that checks in with the buyer, or is it all manual from the agent?

We built that entire post-showing flow into a system for a few agencies. Happy to walk you through it.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
]

NICHE_MESSAGES["salon"] = [
    """\
Hey,

When a client tries to book online and your calendar is full, what happens to that request? Does it get captured somewhere or does that client just go book somewhere else?

That overflow moment is usually where salons lose their best new clients.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hi,

Clients who haven't been in for 60-90 days, is there anything that automatically reaches back out to them, or does that depend on someone on your staff remembering?

We built a reactivation system for a few salons that runs completely on its own.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",

    """\
Hey,

After-hours booking requests, when someone fills out your contact form at 10pm, what happens to it? Does something respond automatically or does it sit until morning?

By morning they've usually booked somewhere else.

Alex
Gray Horizons Enterprise

To opt out of future emails, reply with REMOVE.""",
]

# ── 16 additional niche templates ─────────────────────────────────────────────

NICHE_MESSAGES["electrician"] = [
    """\
Hey,

When a homeowner calls for an electrical emergency and your line is busy, what happens?

Most electricians lose those calls. The customer books the first company that picks up.

We built a system that captures every missed call and follows up automatically so you stop losing jobs to whoever answers first.

Happy to show you how it works this week.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Estimate follow-up is where most electrical contractors lose jobs. Quote goes out, no response, the homeowner went with someone else.

We built a system that follows up on every open estimate automatically until you get an answer.

I can get you set up in about a week.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["pest_control"] = [
    """\
Hey,

When a homeowner calls about an infestation and gets your voicemail, 80% of them call the next company before you call back.

We built a system that captures every missed inquiry and responds automatically so you're always the first pest control company they hear back from.

Worth a quick look?

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Recurring service customers who miss a scheduled treatment and don't reschedule are revenue that most pest control companies never recover.

We built an automated re-engagement system that follows up with lapsed customers and gets them back on the schedule.

Happy to walk you through it.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["veterinary"] = [
    """\
Hey,

When a pet owner calls your clinic after hours about an emergency, what happens to that call?

If it goes to voicemail, they're already searching for an emergency vet. We built a system that captures those calls and directs them appropriately so you never lose an emergency case to a missed call.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Clients who haven't brought their pet in for 6-12 months are your highest-value lapsed customers.

We built a reactivation system that reaches out to those clients automatically with wellness reminders timed to their pet's care history.

I can show you what it looks like this week.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["optometry"] = [
    """\
Hey,

Patients who are due for an annual exam but haven't scheduled yet — is there anything reaching out to them automatically, or does it depend on them calling in?

That gap is usually worth $800-$1,200 per patient per year in missed exams and lens sales.

We built an automated recall system that handles exactly that. Happy to show you how it works.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

When a new patient calls to book an exam and you can't answer, do they get a callback automatically or does it depend on someone at the front desk remembering?

Most practices lose 20-30% of new patient calls that way.

We built a system that captures every missed inquiry and books them automatically.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["cleaning"] = [
    """\
Hey,

When someone fills out a quote request on your website at 9pm, what happens to it?

If it sits until morning, they've already booked another cleaning company.

We built a system that responds instantly and captures the booking automatically — after hours, weekends, whenever.

Happy to show you how it works.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Clients who used your service once and never rebooked — do you have anything reaching back out to them automatically?

Most cleaning companies have 50-100 of these lapsed clients sitting in their records. We built a reactivation system that converts a percentage of them back every month.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["painting"] = [
    """\
Hey,

After you send a quote, what does your follow-up process look like? Is there a system tracking open bids or does it depend on someone remembering to follow up?

Most painting contractors lose 30-40% of their estimates to slow follow-up.

We built a system that tracks every open quote and follows up automatically until you get a yes or a no.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

After-hours and weekend calls for painting projects — when they come in and nobody picks up, do those get captured somewhere or do they usually go cold?

We built a system that responds to every inquiry automatically so you're always first to reply.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["flooring"] = [
    """\
Hey,

When a homeowner submits a flooring quote request and you don't hear back from them, what does your follow-up look like?

That gap between the estimate and the decision is where most flooring companies lose jobs.

We built a system that follows up on every open quote automatically so you stop losing installs to competitors who follow up faster.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Referrals from past flooring customers are your best leads. Most companies never ask for them systematically.

We built a post-install follow-up system that collects reviews and asks for referrals automatically after every completed job.

Worth a quick look?

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["moving"] = [
    """\
Hey,

Moving leads are time-sensitive — the customer gets 3-5 quotes and goes with the first company that responds.

When someone requests a moving quote on your site after hours, how fast does your team follow up?

We built a system that responds instantly and locks in the booking before your competitors call back.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Most moving companies have no system to follow up with leads who got a quote but didn't book.

We built an automated sequence that follows up with those leads at the right intervals — and converts a percentage of them without anyone on your team having to track it manually.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["medspa"] = [
    """\
Hey,

After a client's first treatment, what does your follow-up look like?

Most med spas send nothing. That's why 60% of first-time clients don't come back.

We build automated retention systems: post-treatment follow-up, rebooking reminders, VIP birthday offers, and win-back campaigns for clients who've gone quiet.

Happy to show you what it looks like.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Clients who came in for a consultation but never booked a treatment — is there anything following up with them automatically or does that fall off?

We built a system that nurtures those consult leads with timely messages until they're ready to commit.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["insurance"] = [
    """\
Hey,

After you send a quote, what does your follow-up sequence look like?

Research shows it takes 7 touchpoints before most prospects make an insurance decision. Most agents follow up once or twice and move on.

We built automated nurture sequences that keep you in front of every prospect until they're ready — without you having to track each one manually.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Policy renewal season — how are you proactively reaching out to clients before their renewal dates?

We built an automated renewal pipeline that reaches out at the right intervals, flags at-risk clients, and prompts cross-sell conversations automatically.

Happy to show you how it works this week.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["mortgage"] = [
    """\
Hey,

When a borrower fills out a rate inquiry on your site at 8pm on a Friday, what happens?

Rate shoppers contact 3-5 lenders simultaneously and go with whoever responds first.

We build instant response systems for mortgage brokers — automated inquiry acknowledgment, pre-qual questions, and calendar booking — so you're always first in the door.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Past clients are your best source of refis and referrals. Most LOs communicate with them once a year at best.

We build automated past-client pipelines: rate drop alerts, annual review outreach, referral asks timed to the right moment.

Top producers we work with generate 2-4 deals per month purely from past client automation.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["gym"] = [
    """\
Hey,

When someone signs up for a free trial at your gym, what does the follow-up look like for the next 30 days?

For most gyms, the answer is not much. And that's why month-2 churn is the industry's biggest problem.

We build automated onboarding and retention sequences that check in with new members, fill empty class spots, and flag members showing cancellation signals before they leave.

Happy to show you what it looks like.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Slow Tuesday afternoons and empty Thursday morning classes are pure revenue left on the table.

We set up automated class-fill campaigns that go out to members based on their attendance patterns — nudging the right people to book the right classes at the right time.

Worth 15 minutes to see what's possible?

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["restaurant"] = [
    """\
Hey,

After a customer dines with you, what does your follow-up look like?

For most restaurants, the answer is nothing. No thank you, no birthday offer, no "we miss you" after 60 days.

We build automated guest retention systems — post-visit follow-up, loyalty incentives, and win-back campaigns for guests who haven't returned.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    """\
Hey,

Slow nights and empty reservation slots — is there anything going out automatically to your regulars when you have openings, or is it all manual?

We built an automated fill system that messages your best customers at the right time to drive reservations when you need them most.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["storage"] = [
    """\
Hey,

When someone calls about a storage unit and gets your voicemail, what happens to that inquiry?

Most storage facilities lose 30-40% of phone leads this way.

We built a system that captures every missed inquiry and follows up automatically with availability and pricing — before they book a competitor.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["tutoring"] = [
    """\
Hey,

When a parent inquires about tutoring services and doesn't hear back within an hour, they usually move on to the next option.

We built a system that responds to every inquiry instantly and captures the enrollment without anyone on your team having to manually follow up.

Happy to show you how it works.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]

NICHE_MESSAGES["photography"] = [
    """\
Hey,

After a consultation or inquiry, what does your follow-up look like?

Most photographers send one email and hope for the best. We built a system that follows up on every open inquiry automatically — so you book more sessions without chasing leads manually.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
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
    "electrician":  ["Quick question", "How do you handle missed calls?", "Something we built for electricians"],
    "pest_control": ["Quick question", "How do you handle missed calls?", "Something we built for pest control"],
    "veterinary":   ["Quick question", "Something we built for vet clinics", "How do you handle this?"],
    "optometry":    ["Quick question", "Something we built for eye care", "How do you handle this?"],
    "cleaning":     ["Quick question", "Something we built for cleaning companies", "How do you handle this?"],
    "painting":     ["Quick question", "Something we built for painters", "How do you handle your estimates?"],
    "flooring":     ["Quick question", "How do you handle your quotes?", "Something we built for flooring companies"],
    "moving":       ["Quick question", "Something we built for movers", "How do you handle new leads?"],
    "medspa":       ["Quick question", "Something we built for med spas", "How do you handle client retention?"],
    "insurance":    ["Quick question", "Something we built for agents", "How do you handle quote follow-up?"],
    "mortgage":     ["Quick question", "Something we built for LOs", "How do you handle after-hours leads?"],
    "gym":          ["Quick question", "Something we built for gyms", "How do you handle member retention?"],
    "restaurant":   ["Quick question", "Something we built for restaurants", "How do you get customers back?"],
    "storage":      ["Quick question", "Something we built for storage facilities", "How do you handle missed calls?"],
    "tutoring":     ["Quick question", "Something we built for tutors", "How do you handle new inquiries?"],
    "photography":  ["Quick question", "Something we built for photographers", "How do you handle booking?"],
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
    skip = {"hey", "hi", "alex", "gray horizons enterprise", "https://calendly.com/grayhorizonsenterprise/30min"}
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
    msg = msg.replace("{calendly}", "https://calendly.com/grayhorizonsenterprise/30min")
    msg = msg.replace("{stripe}", STRIPE_LINK)
    msg = _add_periods(msg)
    if "grayhorizonsenterprise.com" not in msg and "https://calendly.com/grayhorizonsenterprise/30min" not in msg:
        msg += "\nhttps://calendly.com/grayhorizonsenterprise/30min"
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
            existing = pd.read_csv(OUTPUT_FILE, dtype=str).fillna("")
            for _, r in existing.iterrows():
                status = str(r.get("status", "")).strip()
                email  = str(r.get("email",  "")).strip().lower()
                if status in ("sent", "skipped", "opted_out") and email:
                    done_emails.add(email)
                    existing_rows.append(r.to_dict())
        except Exception:
            pass

    # Also load sent_log.csv as authoritative "never email again" source
    _sent_log = os.path.join(os.path.dirname(os.path.abspath(OUTPUT_FILE)), "sent_log.csv")
    if os.path.exists(_sent_log):
        try:
            sl = pd.read_csv(_sent_log, dtype=str).fillna("")
            if "email" in sl.columns:
                for e in sl["email"].str.lower().str.strip():
                    if e:
                        done_emails.add(e)
        except Exception:
            pass

    # Load unsubscribe list
    _unsub = os.path.join(os.path.dirname(os.path.abspath(OUTPUT_FILE)), "unsubscribe_list.csv")
    if os.path.exists(_unsub):
        try:
            ub = pd.read_csv(_unsub, dtype=str).fillna("")
            if "email" in ub.columns:
                for e in ub["email"].str.lower().str.strip():
                    if e:
                        done_emails.add(e)
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

    # Block ticket/system email prefixes, these are never real decision makers
    corporate_email_blocks = [
        # Generic system emails
        "noreply@", "no-reply@", "donotreply@", "do-not-reply@",
        "support@", "ticket@", "helpdesk@", "help@",
        "clientcare@", "customercare@", "customerservice@",
        "care@", "service@", "billing@", "accounts@", "admin@",
        "hello@", "team@", "press@", "media@",
        # Known bad domains/patterns
        "info@opencare", "info@rowcal",
        "finda", "attorneys.org", "jobleads",
        # Insurance/financial in email domain
        "insurance", "insure", "underwrite",
        "bcbs", "bluecross", "blueshield", "aetna", "cigna", "humana",
        "anthem", "molina", "kaiser", "unitedhealthcare",
        # Government
        ".gov", ".edu", ".mil",
    ]

    # Block these company name patterns, wrong targets entirely
    corporate_name_blocks = [
        # Insurance (all forms)
        "insurance", "insurer", "underwriter", "surety", "indemnity",
        "blue cross", "blue shield", "bcbs", "aetna", "cigna", "humana",
        "anthem", "molina", "kaiser", "united health", "centene",
        # Medical/Healthcare institutions and major websites
        "hospital", "health system", "medical center", "health network",
        "clinic group", "medical group", "patient portal", "communicare",
        "webmd", "healthline", "mayo clinic", "cleveland clinic",
        "academy of general dentistry", "agd", "membership services",
        # Education/Government
        "university", "college", "school district", "public school",
        "city of ", "county of ", "state of ", "department of ",
        "township", "municipality", "government", "public works",
        # Financial
        "bank", "national bank", "credit union", "financial services",
        "lending", "mortgage", "investment trust",
        "real estate investment", "reit", "property investor",
        "city national", "chase", "wells fargo", "bank of america",
        # Legal
        "law firm", "law office", "attorney", "attorneys", "legal services",
        "malpractice", "litigation", "lawyers",
        # Tech/SaaS/Directories
        "software", "platform", "saas", "tech solutions", "technologies",
        "smugmug", "squarespace", "wix", "shopify", "hubspot", "salesforce",
        "photography studio", "media group", "digital agency",
        "hosting", "cloud services", "it services", "managed services",
        "findamedical", "findadoctor", "findadentist", "findalawyer",
        "jobleads", "directory", "listings",
        # Property management platforms and software
        "opencare", "rowcal", "appfolio", "buildium", "propertyware", "highrises",
        "management company", "management group", "management corp",
        # Non-profits/Associations
        "national association", "association of ", " association",
        "chamber of commerce", "nonprofit", "non-profit", "foundation",
        "nationwide", "national chain", "franchise",
        # Media
        "magazine", "publisher", "broadcasting", "newspaper",
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

        subject = generate_subject(company, niche)
        rows.append({
            "company": company,
            "name":    "",
            "email":   email,
            "website": row.get("website", ""),
            "niche":   niche,
            "subject": subject,
            "message": generate_message(company, niche),
            "status":  "pending",
        })
        niche_count[niche] = niche_count.get(niche, 0) + 1

        # Track sent for performance weighting
        try:
            from performance_tracker import record_sent
            record_sent(niche, subject)
        except Exception:
            pass

    out = pd.DataFrame(existing_rows + rows)
    out.to_csv(OUTPUT_FILE, index=False, quoting=1)

    # Log performance weights so operator can see what's working
    try:
        from performance_tracker import get_niche_weights, get_summary
        weights = get_niche_weights()
        if any(w != 1.0 for w in weights.values()):
            print("\n[PERF] Niche weights (auto-adjusted):")
            for n, w in sorted(weights.items(), key=lambda x: -x[1]):
                print(f"  {n.upper():12s}: {w}x")
    except Exception:
        pass

    print(f"[DONE] outreach_queue.csv: {len(rows)} new leads added, {len(done_emails)} preserved, {skipped} skipped")
    for n, c in sorted(niche_count.items()):
        print(f"  {n.upper():12s}: {c} leads")

if __name__ == "__main__":
    run()
