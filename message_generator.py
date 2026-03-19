import random

# ----- Greeting options -----

greetings = [
    "Hi",
    "Hi there",
    "Good morning",
    "Good afternoon"
]

# ----- Opening hooks -----

openers = [
    "Quick question for your team.",
    "I wanted to reach out with a quick question.",
    "Not sure who handles this on your side, but I had a quick question.",
    "Hope you don't mind the quick outreach."
]

# ----- Context lines -----

context = [
    "I was looking through HOA and community management companies in your area and came across your organization.",
    "I was reviewing HOA management groups in your region and your company came up.",
    "I was researching community association management firms and noticed your team.",
    "I came across your company while looking into HOA management groups."
]

# ----- Problem recognition -----

problems = [
    "One thing we hear constantly from HOA managers is how messy violation tracking becomes across email threads, spreadsheets, and board requests.",
    "A lot of HOA teams we speak with say violation tracking becomes difficult once boards start asking for documentation or follow-ups.",
    "Many management teams still end up juggling violation notices across multiple tools, which makes record keeping painful.",
    "We kept hearing from managers that violation notices start simple but turn into chaos when boards request documentation later."
]

# ----- Insight / credibility -----

insights = [
    "We ended up building a compliance system that automates violation notices and keeps a clean record for the board automatically.",
    "So we built a compliance workflow that logs violations, generates notices, and keeps everything documented automatically.",
    "That led us to build a simple system that handles violation notices and keeps the compliance history organized.",
    "We developed a workflow that automates notices and creates a complete record in case boards ever need it."
]

# ----- Soft curiosity hook -----

hooks = [
    "Just curious — is your team still handling violation notices manually right now?",
    "Out of curiosity, is violation tracking something your team is still doing manually?",
    "Are you currently handling violation notices manually or through software?",
    "Is that something your team already has a system for?"
]

# ----- Closing lines -----

closings = [
    "If it's helpful I can show you how it works.",
    "Happy to share a quick demo if you're curious.",
    "Glad to walk you through it if it would help.",
    "I can send over a quick demo if you're interested."
]

# ----- Signature -----

signature = """

– Gray
Gray Horizons Enterprise
https://grayhorizonsenterprise.com
"""

# ----- Generator -----

def generate_message(company):

    greeting = random.choice(greetings)
    opener = random.choice(openers)
    context_line = random.choice(context)
    problem = random.choice(problems)
    insight = random.choice(insights)
    hook = random.choice(hooks)
    closing = random.choice(closings)

    message = f"""{greeting},

{opener}

{context_line}

{problem}

{insight}

{hook}

{closing}

{signature}
"""

    return message


# ----- Example test -----

if __name__ == "__main__":

    company = "HOA Management Company in Phoenix"

    print(generate_message(company))