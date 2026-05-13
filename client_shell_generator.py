"""
client_shell_generator.py — Gray Horizons Enterprise
Generates a fully-configured outreach engine for any client/niche instantly.

Usage:
    python client_shell_generator.py

    OR import and call generate():
        from client_shell_generator import generate
        generate(
            niche="plumbing",
            client_name="Blue River Plumbing",
            city="Dallas",
            state="TX",
            region="Texas",          # optional — defaults to nationwide
            daily_limit=300,
            calendly="https://calendly.com/yourlink/30min",
            output_file="blueriver_engine.py"  # optional
        )

The generated engine:
  - Searches the entire country (all 50 states, 300+ cities)
  - Finds business emails via DDG + page-fetch
  - Sends personalized cold emails pitching GHE automation services
  - Logs to its own queue CSV and integrates with email_registry for dedup
  - Runs standalone or can be wired into approval_dashboard.py scheduler
"""

import os
import sys
import re

# ─── All 50-state city pool (shared by all generated engines) ─────────────────

ALL_CITIES = [
    "Birmingham AL","Montgomery AL","Huntsville AL","Mobile AL",
    "Anchorage AK","Fairbanks AK",
    "Phoenix AZ","Tucson AZ","Mesa AZ","Scottsdale AZ","Chandler AZ","Gilbert AZ","Tempe AZ","Peoria AZ","Surprise AZ",
    "Little Rock AR","Fort Smith AR","Fayetteville AR","Springdale AR",
    "Los Angeles CA","San Diego CA","San Jose CA","San Francisco CA","Fresno CA","Sacramento CA",
    "Long Beach CA","Oakland CA","Bakersfield CA","Anaheim CA","Riverside CA","Stockton CA",
    "Irvine CA","Fremont CA","San Bernardino CA","Modesto CA","Fontana CA","Visalia CA",
    "Elk Grove CA","Roseville CA","Torrance CA","Escondido CA","Temecula CA","Chula Vista CA",
    "Denver CO","Colorado Springs CO","Aurora CO","Fort Collins CO","Lakewood CO","Pueblo CO",
    "Bridgeport CT","New Haven CT","Hartford CT","Stamford CT","Waterbury CT",
    "Wilmington DE","Dover DE",
    "Jacksonville FL","Miami FL","Tampa FL","Orlando FL","St Petersburg FL","Hialeah FL",
    "Tallahassee FL","Fort Lauderdale FL","Cape Coral FL","Pembroke Pines FL","Hollywood FL",
    "Gainesville FL","Clearwater FL","West Palm Beach FL","Lakeland FL","Sarasota FL",
    "Atlanta GA","Columbus GA","Augusta GA","Macon GA","Savannah GA","Athens GA",
    "Marietta GA","Sandy Springs GA","Roswell GA","Albany GA",
    "Honolulu HI","Pearl City HI",
    "Boise ID","Nampa ID","Meridian ID","Idaho Falls ID",
    "Chicago IL","Aurora IL","Joliet IL","Naperville IL","Rockford IL","Springfield IL",
    "Elgin IL","Peoria IL","Champaign IL","Waukegan IL",
    "Indianapolis IN","Fort Wayne IN","Evansville IN","South Bend IN","Carmel IN",
    "Fishers IN","Bloomington IN","Hammond IN",
    "Des Moines IA","Cedar Rapids IA","Davenport IA","Sioux City IA","Iowa City IA",
    "Wichita KS","Overland Park KS","Kansas City KS","Topeka KS","Olathe KS",
    "Louisville KY","Lexington KY","Bowling Green KY","Owensboro KY",
    "New Orleans LA","Baton Rouge LA","Shreveport LA","Lafayette LA","Lake Charles LA",
    "Portland ME","Lewiston ME",
    "Baltimore MD","Frederick MD","Rockville MD","Gaithersburg MD",
    "Boston MA","Worcester MA","Springfield MA","Cambridge MA","Lowell MA",
    "Detroit MI","Grand Rapids MI","Warren MI","Sterling Heights MI","Ann Arbor MI",
    "Lansing MI","Flint MI","Dearborn MI","Livonia MI","Troy MI","Kalamazoo MI",
    "Minneapolis MN","Saint Paul MN","Rochester MN","Duluth MN","Bloomington MN",
    "Jackson MS","Gulfport MS","Biloxi MS",
    "Kansas City MO","St Louis MO","Springfield MO","Columbia MO","Independence MO",
    "Billings MT","Missoula MT","Great Falls MT","Bozeman MT",
    "Omaha NE","Lincoln NE","Bellevue NE",
    "Las Vegas NV","Henderson NV","Reno NV","North Las Vegas NV","Sparks NV",
    "Manchester NH","Nashua NH","Concord NH",
    "Newark NJ","Jersey City NJ","Paterson NJ","Elizabeth NJ","Trenton NJ","Edison NJ",
    "Albuquerque NM","Las Cruces NM","Rio Rancho NM","Santa Fe NM",
    "New York NY","Buffalo NY","Rochester NY","Yonkers NY","Syracuse NY","Albany NY",
    "Charlotte NC","Raleigh NC","Greensboro NC","Durham NC","Winston-Salem NC",
    "Fayetteville NC","Cary NC","Wilmington NC","Concord NC",
    "Fargo ND","Bismarck ND","Grand Forks ND",
    "Columbus OH","Cleveland OH","Cincinnati OH","Toledo OH","Akron OH","Dayton OH",
    "Parma OH","Canton OH","Youngstown OH",
    "Oklahoma City OK","Tulsa OK","Norman OK","Broken Arrow OK","Edmond OK",
    "Portland OR","Salem OR","Eugene OR","Gresham OR","Hillsboro OR","Bend OR",
    "Philadelphia PA","Pittsburgh PA","Allentown PA","Erie PA","Reading PA","Lancaster PA",
    "Providence RI","Cranston RI","Warwick RI",
    "Columbia SC","Charleston SC","North Charleston SC","Greenville SC","Spartanburg SC",
    "Sioux Falls SD","Rapid City SD",
    "Nashville TN","Memphis TN","Knoxville TN","Chattanooga TN","Clarksville TN",
    "Murfreesboro TN","Franklin TN",
    "Houston TX","San Antonio TX","Dallas TX","Austin TX","Fort Worth TX","El Paso TX",
    "Arlington TX","Corpus Christi TX","Plano TX","Lubbock TX","Garland TX","Irving TX",
    "Amarillo TX","Frisco TX","McKinney TX","Denton TX","Midland TX","Waco TX",
    "Round Rock TX","McAllen TX","Tyler TX","Beaumont TX",
    "Salt Lake City UT","West Valley City UT","Provo UT","Ogden UT","Sandy UT",
    "Burlington VT",
    "Virginia Beach VA","Norfolk VA","Chesapeake VA","Richmond VA","Newport News VA",
    "Alexandria VA","Hampton VA","Roanoke VA",
    "Seattle WA","Spokane WA","Tacoma WA","Vancouver WA","Bellevue WA","Everett WA",
    "Renton WA","Kennewick WA","Yakima WA","Bellingham WA",
    "Charleston WV","Huntington WV","Morgantown WV",
    "Milwaukee WI","Madison WI","Green Bay WI","Kenosha WI","Racine WI","Appleton WI",
    "Cheyenne WY","Casper WY",
]

# ─── Niche query templates ─────────────────────────────────────────────────────

NICHE_QUERIES = {
    "hvac": [
        "hvac contractor","air conditioning repair","heating repair","furnace repair",
        "hvac company","AC installation","duct cleaning","heat pump repair",
        "HVAC technician","air conditioning installation",
    ],
    "dental": [
        "dentist office","dental clinic","family dentist","dental practice",
        "cosmetic dentist","orthodontist","dental implants","emergency dentist",
    ],
    "plumbing": [
        "plumber","plumbing services","drain cleaning","plumbing company",
        "water heater repair","emergency plumber","sewer line repair",
    ],
    "contractor": [
        "general contractor","home remodeling","home renovation","kitchen remodel",
        "bathroom remodel","deck builder","home builder","addition contractor",
    ],
    "landscaping": [
        "landscaping company","lawn care service","lawn mowing","landscaper",
        "irrigation company","tree service","lawn maintenance","hardscape contractor",
    ],
    "roofing": [
        "roofing contractor","roof repair","roofer","roof replacement",
        "gutter company","storm damage roof","metal roofing","flat roof repair",
    ],
    "hoa": [
        "property management","HOA management","community management",
        "condominium management","homeowners association management",
    ],
    "chiropractic": [
        "chiropractor","chiropractic clinic","sports chiropractor",
        "back pain chiropractor","wellness chiropractic",
    ],
    "auto": [
        "auto repair shop","auto mechanic","auto body shop","car repair",
        "transmission repair","brake repair","oil change service",
    ],
    "electrician": [
        "electrician","electrical contractor","electrical company",
        "residential electrician","commercial electrician","generator installation",
    ],
    "pest_control": [
        "pest control","exterminator","pest removal","termite control",
        "rodent control","mosquito control",
    ],
    "salon": [
        "hair salon","beauty salon","nail salon","day spa","barbershop",
        "hair stylist","lash studio",
    ],
    "gym": [
        "gym owner","personal trainer","fitness studio","CrossFit gym",
        "yoga studio","personal training studio","wellness center",
    ],
    "restaurant": [
        "restaurant owner","catering company","food truck","cafe owner","bistro owner",
    ],
    "medspa": [
        "med spa","aesthetic clinic","botox clinic","laser clinic","skin care clinic",
    ],
    "mortgage": [
        "mortgage broker","loan officer","mortgage lender","home loan specialist",
        "refinance specialist","hard money lender",
    ],
    "insurance": [
        "insurance agent","insurance broker","life insurance agent",
        "auto insurance agent","independent insurance agent",
    ],
    "realestate": [
        "real estate agent","realtor","real estate broker","listing agent",
        "buyer agent","property manager",
    ],
    "cleaning": [
        "house cleaning","commercial cleaning","maid service","janitorial service",
        "carpet cleaning","pressure washing",
    ],
    "painting": [
        "painting contractor","house painter","interior painter",
        "exterior painting","commercial painting","deck staining",
    ],
    "moving": [
        "moving company","local moving company","residential mover","commercial mover",
    ],
    "flooring": [
        "flooring company","hardwood floor installation","carpet installer",
        "tile installer","flooring contractor",
    ],
    "ecommerce": [
        "Shopify store owner","ecommerce brand founder","online store owner",
        "DTC brand founder","dropshipping store owner",
    ],
}

# ─── Email template library per niche ─────────────────────────────────────────

NICHE_TEMPLATES = {
    "hvac": {
        "subjects": [
            "Most HVAC shops lose 15+ calls/week during peak season",
            "Quick question about your after-hours calls",
            "The follow-up system top HVAC companies run automatically",
            "How are you handling missed calls right now?",
        ],
        "messages": [
            """\
Hey,

HVAC companies with a full schedule typically miss 15-20 calls a week during peak season. At an average job value of $450, that's $6,750-$9,000 walking out the door every week.

We set up automated follow-up systems for HVAC shops that catch every missed inquiry and follow up immediately so the customer hears from you before they book someone else.

Shops we've set this up for recovered 6-10 jobs in the first month they'd have otherwise lost.

Worth a 20-minute call to see if it fits? {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
            """\
Hey,

Quick question - when your line is busy or it's after hours and a customer calls about a broken AC or furnace, what happens to that call?

If it goes to voicemail, 80% of those customers book the next company that answers before you call back.

We built a system that responds to those inquiries automatically and keeps them engaged until your team can get them on the schedule.

{calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "dental": {
        "subjects": [
            "Most practices lose 8-12 new patients every month to slow follow-up",
            "Quick question about your new patient process",
            "When a patient submits a form at 8pm - what happens?",
            "The retention system top dental practices run automatically",
        ],
        "messages": [
            """\
Hey,

The average dental practice loses 8-12 new patients every month to slow follow-up. A patient submits a form or calls after hours, nobody responds until the next morning, and by then they've booked somewhere else.

At $1,200 average lifetime value per new patient, that's $9,600-$14,400 a month slipping through.

We built a follow-up system that responds to every new patient inquiry immediately and keeps them engaged until they're booked.

Happy to show you how it works in 20 minutes: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "plumbing": {
        "subjects": [
            "The biggest revenue leak for most plumbing companies",
            "Quick question about your missed calls",
            "How are you handling after-hours emergency calls?",
        ],
        "messages": [
            """\
Hey,

The biggest revenue leak for most plumbing companies is missed calls - the customer calls once, nobody answers, and they book someone else before you call back.

We built a system that captures every missed call and gets it back into your pipeline automatically.

I can show you exactly how it works this week: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "contractor": {
        "subjects": [
            "Contractors lose more jobs to slow follow-up than to price",
            "Quick question about your estimate follow-up",
            "How are you tracking your open bids right now?",
        ],
        "messages": [
            """\
Hey,

Most contractors we work with were losing jobs not because of the work but because estimate follow-up was not happening consistently.

We built a system that tracks every open bid and follows up automatically until you get a response.

I can show you exactly how it works and get it running for your team this week: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "landscaping": {
        "subjects": [
            "The first company to respond wins the job in landscaping",
            "Quick question about your overflow leads",
            "Seasonal clients going quiet between services?",
        ],
        "messages": [
            """\
Hey,

The first company to respond to an estimate request in landscaping almost always wins the job - most homeowners book whoever gets back to them first.

We built a system that captures new inquiries and responds automatically so you are always first.

I can show you exactly how it works this week: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "roofing": {
        "subjects": [
            "Quick question about your storm lead process",
            "How do you handle estimate follow-up right now?",
            "After a storm - how does your team handle the wave of calls?",
        ],
        "messages": [
            """\
Hey,

Quick one: after a storm comes through your area, how does your team handle the wave of calls that come in? Is there a system to track each one or does it get chaotic?

We've been helping roofing companies manage exactly that - automated intake, follow-up, and estimate tracking.

{calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "gym": {
        "subjects": [
            "Most gyms lose 40% of new members in month 2",
            "Quick question about your member retention process",
            "The retention system top gyms run automatically",
        ],
        "messages": [
            """\
Hey,

Quick question - when someone signs up for a free trial at your gym, what does the follow-up look like for the next 30 days?

For most gyms, the answer is "not much." And that's why month-2 churn is the industry's biggest problem.

We build automated onboarding and retention sequences that check in with new members, celebrate milestones, fill empty class spots, and flag members who are showing cancellation signals.

Happy to show you what it looks like for your specific setup: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "restaurant": {
        "subjects": [
            "Most restaurants lose repeat customers to zero follow-up",
            "Quick question about your customer retention",
            "How are you getting customers back through the door?",
        ],
        "messages": [
            """\
Hey,

Quick question - after a customer dines with you, what does your follow-up look like?

For most restaurants, the answer is nothing. No thank you, no birthday offer, no "we miss you" after 60 days.

We build automated guest retention systems - post-visit thank you, loyalty incentives, birthday outreach, and win-back campaigns for guests who haven't returned.

Worth 15 minutes to see what it looks like: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "medspa": {
        "subjects": [
            "Most med spas lose 60% of first-time clients to zero follow-up",
            "Quick question about your client retention",
            "The rebooking system top med spas run automatically",
        ],
        "messages": [
            """\
Hey,

After a client's first treatment, what does your follow-up look like?

Most med spas send nothing. And that's why 60%+ of first-time clients never come back.

We build automated retention systems for aesthetic practices: post-treatment follow-up, rebooking reminders, VIP birthday offers, and win-back campaigns for clients who've gone quiet.

Happy to show you what it looks like: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "mortgage": {
        "subjects": [
            "How are you capturing rate-shopping leads before they disappear?",
            "Most LOs miss 60% of their leads after hours",
            "Quick question about your past client refi pipeline",
        ],
        "messages": [
            """\
Hey,

When a borrower fills out a rate inquiry on your site at 8pm on a Friday, what happens?

If the answer is "we call them Monday," you've already lost them. Rate shoppers contact 3-5 lenders simultaneously and go with whoever responds first.

We build instant response systems for mortgage brokers and LOs - automated rate inquiry acknowledgment, pre-qual questionnaire, and calendar booking.

Happy to walk you through it: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "insurance": {
        "subjects": [
            "Most insurance agents lose leads to slow follow-up",
            "Quick question about your quote follow-up process",
            "The automation system top agents use to close more policies",
        ],
        "messages": [
            """\
Hey,

After you send a quote, what does your follow-up process look like?

Most agents follow up once or twice and move on. But research shows it takes 7 touchpoints before most prospects make a decision.

We build automated nurture sequences for insurance agents - educational content, rate change alerts, and timely follow-up that keeps you top of mind without you having to manually track everyone.

Worth a quick call: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "realestate": {
        "subjects": [
            "Leads go cold between first inquiry and first showing",
            "Quick question about your lead follow-up",
            "When a buyer inquires at night - what happens?",
        ],
        "messages": [
            """\
Hey,

When a new buyer or seller inquiry comes in through your website at night or on the weekend, how fast does your team get back to them?

In real estate that response window is usually where the lead goes to whoever calls back first.

We build automated response and nurture systems for agents - instant acknowledgment, pre-qualification questions, and follow-up sequences that keep leads warm until they're ready to move.

{calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "cleaning": {
        "subjects": [
            "Quick question about your new client follow-up",
            "Most cleaning companies lose 40% of leads to slow response",
            "The booking system top cleaning companies run automatically",
        ],
        "messages": [
            """\
Hey,

When a homeowner fills out a quote request on your site after hours, what happens to that inquiry?

Most cleaning companies get back to them the next day. By then, they've already booked someone else.

We build automated response and booking systems for cleaning companies - instant quote acknowledgment, availability check, and follow-up until they're booked.

Worth 15 minutes to see: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
    "ecommerce": {
        "subjects": [
            "Your cart abandonment rate is probably 70%+",
            "One email sequence that typically adds 15% revenue",
            "How are you handling customers who don't come back?",
        ],
        "messages": [
            """\
Hey,

If you're running an online store and not doing automated abandoned cart recovery, you're leaving roughly 70% of your revenue on the table.

We build the full email and SMS sequence - cart abandonment, post-purchase upsell, browse abandonment, win-back - configured for your specific product catalog.

Most stores see 10-20% revenue lift in the first 30 days.

If you want to see what it looks like for your store: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        ]
    },
}

# Add generic fallback for any niche not in the template library
GENERIC_TEMPLATE = {
    "subjects": [
        "Quick question about your follow-up process",
        "How are you capturing leads after hours?",
        "The system top businesses in your industry use",
        "One thing most business owners miss that costs them clients",
    ],
    "messages": [
        """\
Hey,

Quick question - when a potential customer reaches out after hours or on the weekend, what happens to that inquiry?

Most businesses let it sit. By morning, the customer has already called two competitors.

We build automated response and follow-up systems that make sure you're always first to respond - even when your team is off the clock.

Happy to show you what it looks like for your specific business: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
        """\
Hey,

The businesses winning in your market right now aren't necessarily working more leads - they're working a better system.

We help business owners set up the backend most never build: lead response automation, nurture sequences, past client reactivation, and referral systems.

Takes about a week to build. After that it runs and compounds.

If you're looking to add consistent revenue without adding headcount: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
    ]
}


def generate(
    niche: str,
    client_name: str = "Gray Horizons Enterprise",
    city: str = "",
    state: str = "",
    region: str = "nationwide",
    daily_limit: int = 300,
    calendly: str = "https://calendly.com/grayhorizonsenterprise/30min",
    sendgrid_env: str = "SENDGRID_API_KEY",
    output_file: str = None,
) -> str:
    """Generate a complete outreach engine script for the given niche."""

    niche_key  = niche.lower().replace(" ", "_").replace("-", "_")
    safe_name  = re.sub(r"[^a-z0-9_]", "_", client_name.lower().replace(" ", "_"))
    safe_niche = re.sub(r"[^a-z0-9_]", "_", niche_key)

    queries  = NICHE_QUERIES.get(niche_key, [f"{niche} owner", f"{niche} company", f"{niche} business"])
    tmpls    = NICHE_TEMPLATES.get(niche_key, GENERIC_TEMPLATE)
    subjects = tmpls["subjects"]
    messages = tmpls["messages"]

    # Limit city pool if a specific region was given
    if city and state:
        city_filter = f"{city} {state}"
        city_pool = [c for c in ALL_CITIES if state.upper() in c] or ALL_CITIES
    elif state:
        city_pool = [c for c in ALL_CITIES if state.upper() in c] or ALL_CITIES
    elif region.lower() not in ("nationwide", "national", "all", ""):
        # Try to match region as state name or abbreviation
        city_pool = [c for c in ALL_CITIES if region.upper() in c.upper()] or ALL_CITIES
    else:
        city_pool = ALL_CITIES

    queue_file  = f"{safe_niche}_{safe_name}_queue.csv"
    engine_name = f"{safe_niche}_{safe_name}_engine"
    label       = f"{niche.title()} Engine ({client_name})"

    queries_repr  = repr(queries)
    cities_repr   = repr(city_pool)
    subjects_repr = repr(subjects)
    messages_repr = repr(messages)
    calendly_repr = repr(calendly)

    script = f'''"""
{engine_name}.py — Gray Horizons Enterprise
Auto-generated outreach engine for: {client_name}
Niche: {niche.title()} | Region: {region}
Daily limit: {daily_limit} emails
Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}

Deploy: copy to Railway project root, add to approval_dashboard.py scheduler
"""
import os, sys, re, time, random, pandas as pd, requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
try:
    from email_registry import load_global_registry, register_sent
except ImportError:
    def load_global_registry(**_): return set()
    def register_sent(*_): pass

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE    = os.path.join(DATA_DIR, {repr(queue_file)})
SENDGRID_KEY  = os.getenv({repr(sendgrid_env)}, "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Alex")
CALENDLY      = {calendly_repr}
DAILY_LIMIT   = int(os.getenv({repr(engine_name.upper() + "_DAILY_LIMIT")}, {repr(daily_limit)}))
REFILL_BELOW  = 200

SEARCH_QUERIES = {queries_repr}

LOCATIONS = {cities_repr}

SUBJECTS = {subjects_repr}

MESSAGES = {messages_repr}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{{2,}}")
BAD_PREFIXES = {{
    "abuse","spam","report","complaints","privacy","legal","billing",
    "webmaster","postmaster","mailer","sales","marketing","hr",
    "careers","jobs","news","newsletter","press","media","helpdesk",
    "support","ticket","noreply","no-reply","donotreply",
}}
SKIP_DOMAINS = {{
    "reddit.com","twitter.com","facebook.com","instagram.com","linkedin.com",
    "youtube.com","google.com","yelp.com","wikipedia.org","yellowpages.com",
    "angi.com","thumbtack.com","homeadvisor.com","bbb.org","nextdoor.com",
    "superpages.com","healthgrades.com","zocdoc.com","houzz.com",
}}

def is_clean(email):
    e = email.lower().strip()
    if not re.match(r"^[a-z0-9._%+\\-]+@[a-z0-9.\\-]+\\.[a-z]{{2,}}$", e): return False
    if e.endswith((".png",".jpg",".gif",".webp",".svg")): return False
    prefix = e.split("@")[0]
    return not any(prefix == b or prefix.startswith(b) for b in BAD_PREFIXES)

def fetch_emails(url):
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(url, headers={{"User-Agent": random.choice(USER_AGENTS)}}, timeout=8, verify=False)
        if r.status_code != 200: return []
        text = r.text
        for a in BeautifulSoup(text, "html.parser").find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                text += f" {{a['href'][7:].split('?')[0]}}"
        return list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text) if is_clean(e.lower())))
    except Exception:
        return []

def scrape(seen, global_seen):
    import urllib.parse
    combos = [(q, loc) for q in SEARCH_QUERIES for loc in LOCATIONS]
    random.shuffle(combos)
    combos = combos[:80]
    new, ddgs = [], DDGS()
    for i, (q, loc) in enumerate(combos):
        query = f"{{q}} {{loc}} email contact"
        print(f"  [{engine_name.upper()} {{i+1}}/{{len(combos)}}] {{q}} in {{loc}}")
        try:
            for r in list(ddgs.text(query, max_results=6)):
                url = r.get("href", "")
                domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                if domain in SKIP_DOMAINS or not url: continue
                for email in fetch_emails(url):
                    if email in seen or email in global_seen: continue
                    seen.add(email)
                    new.append({{"email": email, "name": r.get("title","")[:80],
                                 "website": url, "source": q[:60],
                                 "status": "pending", "niche": {repr(niche_key)}}})
                    print(f"    [+] {{email}}")
                time.sleep(random.uniform(0.3, 0.6))
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"    [ERR] {{e}}"); time.sleep(2)
    return new

def send_one(email, subject, body):
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={{"Authorization": f"Bearer {{SENDGRID_KEY}}", "Content-Type": "application/json"}},
            json={{"personalizations": [{{"to": [{{"email": email}}]}}],
                  "from": {{"email": FROM_EMAIL, "name": SENDER_NAME}},
                  "subject": subject, "content": [{{"type": "text/plain", "value": body}}]}},
            timeout=15)
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {{e}}"); return False

def run():
    if not SENDGRID_KEY:
        print("[{label}] SENDGRID_API_KEY not set"); return

    seen, df_existing = set(), pd.DataFrame()
    if os.path.exists(QUEUE_FILE):
        try:
            df_existing = pd.read_csv(QUEUE_FILE, dtype=str).fillna("")
            seen = set(df_existing["email"].str.lower().str.strip())
        except Exception:
            pass

    pending_count = int((df_existing.get("status", pd.Series()) == "pending").sum()) if not df_existing.empty else 0
    global_seen = load_global_registry(exclude_queue={repr(queue_file)})

    if pending_count < REFILL_BELOW:
        new = scrape(seen, global_seen)
        if new:
            df_new = pd.DataFrame(new)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["email"]) if not df_existing.empty else df_new
            df_combined.to_csv(QUEUE_FILE, index=False)
        else:
            df_combined = df_existing
    else:
        df_combined = df_existing

    if df_combined.empty: return

    indices = list(df_combined[df_combined["status"] == "pending"].index)
    random.shuffle(indices)
    sent = 0
    for idx in indices[:DAILY_LIMIT]:
        email = str(df_combined.loc[idx].get("email", "")).strip()
        if not email or email.lower() in global_seen:
            df_combined.at[idx, "status"] = "opted_out"; continue
        body = random.choice(MESSAGES).replace("{{calendly}}", CALENDLY)
        ok = send_one(email, random.choice(SUBJECTS), body)
        df_combined.at[idx, "status"] = "sent" if ok else "failed"
        if ok:
            sent += 1
            global_seen.add(email.lower())
            register_sent(email, {repr(niche_key)})
            print(f"  [OK] {{email}}")
        if sent % 50 == 0 and sent > 0:
            df_combined.to_csv(QUEUE_FILE, index=False)
        time.sleep(random.uniform(0.3, 0.7))

    df_combined.to_csv(QUEUE_FILE, index=False)
    print(f"[{label} DONE] {{sent}} sent today")

if __name__ == "__main__":
    run()
'''

    if output_file is None:
        output_file = f"{engine_name}.py"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"[SHELL] Generated: {output_file}")
    print(f"  Niche:       {niche.title()}")
    print(f"  Client:      {client_name}")
    print(f"  Region:      {region} ({len(city_pool)} cities)")
    print(f"  Queries:     {len(queries)}")
    print(f"  Daily limit: {daily_limit}")
    print(f"  Queue file:  {queue_file}")
    print(f"\n  To deploy:")
    print(f"    1. Copy {output_file} to your Railway project root")
    print(f"    2. Add to approval_dashboard.py scheduler:")
    print(f"       threading.Thread(target=lambda: _run_engine('{label}', '{output_file}'), daemon=True).start()")
    print(f"    3. git add {output_file} && git commit -m 'Add {label}' && git push")

    return output_file


def interactive():
    """Interactive CLI for generating engines."""
    print("=" * 60)
    print("GHE Client Shell Generator")
    print("=" * 60)
    print("\nAvailable niches:")
    for k in sorted(NICHE_QUERIES.keys()):
        print(f"  {k}")
    print()

    niche       = input("Niche (e.g. hvac, dental, gym): ").strip()
    client_name = input("Client/business name (or press Enter for GHE): ").strip() or "Gray Horizons Enterprise"
    city        = input("Target city (or press Enter for nationwide): ").strip()
    state       = input("Target state abbreviation (e.g. TX, or press Enter for nationwide): ").strip()
    limit_str   = input("Daily email limit (default 300): ").strip()
    daily_limit = int(limit_str) if limit_str.isdigit() else 300
    calendly    = input("Calendly link (press Enter for GHE default): ").strip() or "https://calendly.com/grayhorizonsenterprise/30min"
    out         = input("Output filename (press Enter for auto): ").strip() or None

    region = "nationwide"
    if state:
        region = state
    elif city:
        region = city

    generate(
        niche=niche,
        client_name=client_name,
        city=city,
        state=state,
        region=region,
        daily_limit=daily_limit,
        calendly=calendly,
        output_file=out,
    )


if __name__ == "__main__":
    # Quick demo — generate 3 example engines
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        generate("hvac",       "Demo HVAC Client",    state="TX", daily_limit=300)
        generate("dental",     "Demo Dental Client",  state="FL", daily_limit=300)
        generate("gym",        "Demo Gym Client",     region="nationwide", daily_limit=300)
    else:
        interactive()
