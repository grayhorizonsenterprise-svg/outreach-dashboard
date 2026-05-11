import random

subjects = [
"Quick HOA question",
"Question about violation notices",
"Quick HOA compliance question",
"Quick question for your team"
]

openers = [
"I came across your organization while researching HOA management groups.",
"I found your company while looking into community association management firms.",
"I was reviewing HOA management groups in your area and saw your organization.",
"I noticed your company while researching HOA management firms."
]

questions = [
"How are violation notices currently handled?",
"Do your boards track compliance manually or through software?",
"How does your team manage violation notices right now?",
"Are compliance notices handled internally or through a system?"
]

closers = [
"Happy to show how a few communities automated this if helpful.",
"I can share how some boards simplified this if you're curious.",
"If useful I can show how other HOAs are handling this.",
"Happy to show a quick example if helpful."
]

signoffs = [
"— Gray",
"— GHE",
"— Gray Horizons"
]

companies = [
"Sunset HOA Management",
"Keystone Property Services",
"Blue Ridge Community Association",
"Metro HOA Management"
]

def generate():

    company = random.choice(companies)

    msg = f"""
Subject: {random.choice(subjects)}

Hi {company} team,

{random.choice(openers)}

Quick question — {random.choice(questions)}

{random.choice(closers)}

{random.choice(signoffs)}
"""

    return msg


for i in range(10):

    print("\n------ MESSAGE ------\n")
    print(generate())