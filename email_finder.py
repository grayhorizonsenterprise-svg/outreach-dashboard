import random

subjects = [
"Quick HOA question",
"Question about violation notices",
"Quick question about compliance",
"HOA compliance question"
]

openers = [
"I came across your organization while looking through HOA management groups.",
"I found your company while researching HOA boards in your area.",
"I was reviewing HOA management groups and your organization came up."
]

questions = [
"How are violation notices currently handled?",
"Are compliance notices handled manually or through software?",
"How does your team track violation notices right now?"
]

closers = [
"Happy to show how a few communities automated this if helpful.",
"I can share how a few boards simplified this if you're curious.",
"If useful, I can show how other HOAs are handling this."
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

    print("\n----- MESSAGE -----\n")
    print(generate())