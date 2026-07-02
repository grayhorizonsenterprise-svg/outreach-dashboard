"""
grant_portal_app.py — GHE Grant Application Portal
A SaaS tool for small business owners: AI writes their grant applications.
Trial: 3 applications OR 14 days. After limit: status-only + upgrade CTA.

Deploy to Railway as its own service.
Admin generates unique URLs → users fill profile → AI writes narratives → copy & submit.
"""

import sqlite3, uuid, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
ADMIN_KEY     = os.getenv("PORTAL_ADMIN_KEY", "ghe-admin-2026")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CALENDLY      = "https://calendly.com/grayhorizonsenterprise/30min"
DB_PATH       = Path(os.getenv("DATA_DIR", ".")) / "grant_portal.db"
TRIAL_APPS    = int(os.getenv("TRIAL_APPS", "3"))
TRIAL_DAYS    = int(os.getenv("TRIAL_DAYS", "14"))
PORT          = int(os.getenv("PORT", 8080))

app    = FastAPI(title="GHE Grant Portal", docs_url=None, redoc_url=None)
client = Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ─── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS portals (
        token           TEXT PRIMARY KEY,
        created_at      TEXT NOT NULL,
        business_name   TEXT DEFAULT '',
        owner_name      TEXT DEFAULT '',
        business_type   TEXT DEFAULT '',
        ethnicity       TEXT DEFAULT '',
        gender          TEXT DEFAULT '',
        state           TEXT DEFAULT '',
        has_ein         INTEGER DEFAULT 0,
        has_dba         INTEGER DEFAULT 0,
        revenue_range   TEXT DEFAULT 'pre-revenue',
        employees       TEXT DEFAULT '1-5',
        description     TEXT DEFAULT '',
        apps_used       INTEGER DEFAULT 0,
        profile_done    INTEGER DEFAULT 0,
        label           TEXT DEFAULT ''
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS applications (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        token        TEXT NOT NULL,
        grant_id     TEXT NOT NULL,
        grant_name   TEXT NOT NULL,
        grant_amount TEXT NOT NULL,
        narrative    TEXT DEFAULT '',
        status       TEXT DEFAULT 'Not Started',
        created_at   TEXT NOT NULL,
        apply_url    TEXT DEFAULT '',
        notes        TEXT DEFAULT ''
    )""")
    db.commit()
    db.close()

init_db()

# ─── Grant Database ───────────────────────────────────────────────────────────
GRANTS = {
    # ── Micro ($500-$5K fastest wins) ─────────────────────────────────────────
    "hello-alice-micro": {
        "name": "Hello Alice Monthly Micro-Grant",
        "amount": "$500",
        "min_amount": 500,
        "timeline": "2-4 weeks",
        "speed": "FASTEST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://helloalice.com/grants",
        "req_minority": False, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Monthly $500 rolling grant. Any small business owner. Low competition. Fastest decision available.",
        "questions": [
            "Describe your business in 2-3 sentences.",
            "How will you use this $500 grant?",
            "What is the biggest challenge your business is facing right now?",
        ],
    },
    "naacp-keep-local": {
        "name": "NAACP Keep It Local — Nextdoor Kind Foundation",
        "amount": "$5,000",
        "min_amount": 5000,
        "timeline": "3-6 weeks",
        "speed": "FAST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://naacp.org/find-resources/grants/keep-it-local-business-fund",
        "req_minority": True, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Entrepreneurs of color. 20 winners per round. Includes Nextdoor ad credit + business coaching.",
        "questions": [
            "Tell us about your business and its role in the local community.",
            "How will this $5,000 grant help your business grow?",
            "What is one specific way your business strengthens your neighborhood or local economy?",
            "Tell us about yourself as a founder and why you started this business.",
        ],
    },
    "sogal-black-founder": {
        "name": "SoGal Black Founder Startup Grant",
        "amount": "$5,000-$10,000",
        "min_amount": 5000,
        "timeline": "4-8 weeks",
        "speed": "FAST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://sogalventures.com/grants/",
        "req_minority": True, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Early-stage Black founders. Rolling applications — no deadline pressure. Cash plus mentorship network.",
        "questions": [
            "What is your company and what problem does it solve?",
            "Why do you need this funding right now?",
            "What is your unfair advantage as a founder?",
            "What traction or proof do you have that this business works?",
        ],
    },
    "amber-grant": {
        "name": "WomensNet Amber Grant",
        "amount": "$10,000",
        "min_amount": 10000,
        "timeline": "2-4 weeks",
        "speed": "FASTEST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://ambergrant.com",
        "req_minority": False, "req_woman": True, "req_california": False, "req_sam": False,
        "desc": "Women entrepreneurs only. Monthly awards. One of the highest-volume small business grants available.",
        "questions": [
            "Tell us about your business — what you do, who you serve, and why you started it.",
            "What will you do with the Amber Grant money?",
            "What does success look like for your business in the next 12 months?",
        ],
    },
    # ── Standard ($10K-$30K) ───────────────────────────────────────────────────
    "hello-alice-10k": {
        "name": "Hello Alice Black Business Owners Grant",
        "amount": "$10,000",
        "min_amount": 10000,
        "timeline": "4-8 weeks",
        "speed": "FAST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://helloalice.com/grants",
        "req_minority": True, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Black-owned small businesses. Unrestricted cash. Rolling rounds — one of the most accessible $10K grants.",
        "questions": [
            "Describe your business — what it does, who it serves, and what problem it solves.",
            "How will you use the $10,000 grant funds?",
            "How does your business impact your community?",
            "Tell us your founder story — why did you start this business?",
        ],
    },
    "verizon-digital": {
        "name": "Verizon Small Business Digital Ready Grant",
        "amount": "$10,000",
        "min_amount": 10000,
        "timeline": "4-8 weeks",
        "speed": "FAST",
        "difficulty": "EASY",
        "color": "green",
        "url": "https://digitalreadysmallbusiness.verizon.com",
        "req_minority": False, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Any small business. Complete 2-3 free courses first to unlock eligibility. 10 winners per month.",
        "questions": [
            "Describe your business — what do you do and who do you serve?",
            "How have digital tools impacted your business?",
            "How will you use the $10,000 grant funds?",
            "What digital skills or tools do you plan to learn or improve?",
        ],
    },
    "comcast-rise": {
        "name": "Comcast RISE Investment Fund",
        "amount": "$10,000",
        "min_amount": 10000,
        "timeline": "6-10 weeks",
        "speed": "MEDIUM",
        "difficulty": "MEDIUM",
        "color": "green",
        "url": "https://www.comcastrise.com",
        "req_minority": True, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Minority, women, or veteran-owned businesses. Quarterly awards. Also includes marketing + tech resources.",
        "questions": [
            "Tell us about your business — what you do, who you serve, and how long you've been operating.",
            "How has your business been affected by economic challenges?",
            "How would the Comcast RISE grant and resources help your business grow?",
            "Describe your connection to your local community.",
        ],
    },
    "hello-alice-25k": {
        "name": "Hello Alice Small Business Growth Fund",
        "amount": "$25,000",
        "min_amount": 25000,
        "timeline": "6-10 weeks",
        "speed": "MEDIUM",
        "difficulty": "MEDIUM",
        "color": "amber",
        "url": "https://helloalice.com/grants",
        "req_minority": False, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Growth-stage small businesses. Apply simultaneously with other Hello Alice grants in one login session.",
        "questions": [
            "Describe your business and its current stage of growth.",
            "What are the biggest barriers to growth you're facing right now?",
            "How will you use the $25,000 to scale your business?",
            "What does your business look like in 12 months if you receive this funding?",
        ],
    },
    "fedex-grant": {
        "name": "FedEx Small Business Grant Contest",
        "amount": "$30,000",
        "min_amount": 30000,
        "timeline": "8-12 weeks",
        "speed": "MEDIUM",
        "difficulty": "MEDIUM",
        "color": "amber",
        "url": "https://smallbusiness.fedex.com",
        "req_minority": False, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Annual contest. Up to $30K. Story-driven — strong narrative about business impact wins.",
        "questions": [
            "Tell us your business story — how did you get started and what drives you?",
            "What makes your business unique in your market?",
            "How will the FedEx grant help your business achieve its next milestone?",
            "What impact does your business have on your employees, customers, and community?",
        ],
    },
    # ── Large ($50K+) ──────────────────────────────────────────────────────────
    "cedap": {
        "name": "California CEDAP — Capital and Tech Access Program",
        "amount": "Up to $75,000",
        "min_amount": 75000,
        "timeline": "6-12 weeks",
        "speed": "MEDIUM",
        "difficulty": "MEDIUM",
        "color": "amber",
        "url": "https://calosba.ca.gov",
        "req_minority": False, "req_woman": False, "req_california": True, "req_sam": False,
        "desc": "California businesses only. Founder labor costs are eligible expenses. Request an advisor call first.",
        "questions": [
            "Describe your project and what you plan to accomplish with CEDAP funding.",
            "How will this project benefit underserved communities in California?",
            "Provide a detailed budget breakdown for the requested funds.",
            "What are the measurable outcomes of your project?",
        ],
    },
    "google-bff": {
        "name": "Google for Startups Black Founders Fund",
        "amount": "$50,000-$100,000",
        "min_amount": 50000,
        "timeline": "8-16 weeks",
        "speed": "SLOWER",
        "difficulty": "HARD",
        "color": "purple",
        "url": "https://startup.google.com/programs/black-founders-fund/",
        "req_minority": True, "req_woman": False, "req_california": False, "req_sam": False,
        "desc": "Black founders. Cohort-based — monitor for open dates. Cash plus Google Cloud credits.",
        "questions": [
            "What does your company do and what problem does it solve?",
            "Why do you need this funding and what will you use it for?",
            "What is your company's unfair advantage?",
            "What traction has your company achieved so far?",
            "Why are you the right person to build this company?",
        ],
    },
    "nsf-sbir": {
        "name": "NSF SBIR Phase I — America's Seed Fund",
        "amount": "$275,000",
        "min_amount": 275000,
        "timeline": "9-12 months",
        "speed": "LONG",
        "difficulty": "HARD",
        "color": "purple",
        "url": "https://seedfund.nsf.gov",
        "req_minority": False, "req_woman": False, "req_california": False, "req_sam": True,
        "desc": "Any US small business with R&D innovation. Requires SAM.gov registration. PI salary ~$85K/yr built in.",
        "questions": [
            "What is the core innovation or technical advancement your project proposes?",
            "What is the broader commercial and societal impact of this technology?",
            "What research and development work needs to be done in Phase I?",
            "Why is your team uniquely positioned to execute this research?",
            "Provide a budget justification for the requested Phase I funding.",
        ],
    },
}

SPEED_ORDER = {"FASTEST": 0, "FAST": 1, "MEDIUM": 2, "SLOWER": 3, "LONG": 4}
STATUS_COLORS = {
    "Not Started": "gray", "Applied": "blue",
    "Under Review": "amber", "Awarded": "green", "Rejected": "red"
}

# ─── Narrative generation ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a professional grant writer with 15 years of experience winning grants for minority-owned small businesses. You write narratives that sound real, personal, and human — never corporate or AI-generated.

Rules you never break:
- Write in first person as the business owner
- Short sentences. Direct. Grounded in specific numbers.
- No buzzwords: leverage, synergize, paradigm, disruptive, empower, ecosystem, holistic
- Maximum 3 short paragraphs per section
- Sound like a person wrote this at their kitchen table, not a consultant in a boardroom
- Always answer: What does this business do? Why do they need money RIGHT NOW? What happens if they get it? Who benefits?
- Use real specificity: dollar amounts, time frames, client types, service names"""

def generate_narrative(portal: dict, grant: dict) -> str:
    """Generate Q&A pairs as JSON string, or a narrative blob if no questions defined."""
    if not client:
        return json.dumps({"mode": "error", "text": "ANTHROPIC_API_KEY not set — contact GHE to activate."})

    eth = portal.get("ethnicity", "")
    minority_status = f"Minority-owned ({eth})" if eth and eth.lower() not in ["white/caucasian", ""] else ""
    questions = grant.get("questions", [])

    if questions:
        q_list = "\n".join(f'{i+1}. "{q}"' for i, q in enumerate(questions))
        prompt = f"""Answer each grant application question below for this business. Write in first person as the owner.

BUSINESS:
- Name: {portal['business_name']}
- Owner: {portal['owner_name']}
- Type: {portal['business_type']}
- State: {portal['state']}
- Revenue: {portal['revenue_range']}
- Employees: {portal.get('employees','1')}
- {minority_status}
- EIN: {"Yes" if portal.get('has_ein') else "No"}
- Formation: {"DBA/LLC" if portal.get('has_dba') else "Sole proprietor"}
- Description: {portal['description']}

GRANT: {grant['name']} — {grant['amount']}

QUESTIONS:
{q_list}

Write 2-3 paragraphs per answer. Sound like a real person — specific, direct, no buzzwords.
Respond ONLY with valid JSON in this exact format:
{{"mode":"qa","answers":[{{"q":"exact question text","a":"your answer"}}]}}"""
    else:
        prompt = f"""Write a complete grant application for {portal['business_name']} applying to {grant['name']} ({grant['amount']}).
Owner: {portal['owner_name']} | Type: {portal['business_type']} | State: {portal['state']}
Revenue: {portal['revenue_range']} | {minority_status}
Description: {portal['description']}

Include: business description, why they need funding, how funds will be used, community impact, why they will win.
Be specific, human, first person. No buzzwords.
Respond as JSON: {{"mode":"narrative","text":"full narrative here"}}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        # Validate it's parseable JSON
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        # Wrap plain text response as narrative mode
        return json.dumps({"mode": "narrative", "text": msg.content[0].text if 'msg' in dir() else "[Generation failed]"})
    except Exception as e:
        return json.dumps({"mode": "error", "text": f"Generation error: {str(e)[:100]}"})

# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_portal(token: str):
    db = get_db()
    r = db.execute("SELECT * FROM portals WHERE token=?", (token,)).fetchone()
    db.close()
    return dict(r) if r else None

def get_apps(token: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM applications WHERE token=? ORDER BY created_at DESC", (token,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_all_portals():
    db = get_db()
    rows = db.execute("SELECT * FROM portals ORDER BY created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

def is_locked(portal: dict) -> tuple[bool, str]:
    created = datetime.fromisoformat(portal["created_at"])
    days = (datetime.now(timezone.utc) - created).days
    if days >= TRIAL_DAYS:
        return True, f"Your {TRIAL_DAYS}-day trial has ended."
    if portal["apps_used"] >= TRIAL_APPS:
        return True, f"You've used all {TRIAL_APPS} free applications."
    return False, ""

def match_grants(portal: dict) -> list:
    is_minority = portal.get("ethnicity", "").lower() not in ["white/caucasian", ""]
    is_woman    = portal.get("gender", "").lower() in ["female", "woman"]
    is_ca       = portal.get("state", "").upper() in ["CA", "CALIFORNIA"]
    results = []
    for gid, g in GRANTS.items():
        if g["req_minority"] and not is_minority:
            continue
        if g["req_woman"] and not is_woman:
            continue
        if g["req_california"] and not is_ca:
            continue
        entry = g.copy()
        entry["id"] = gid
        results.append(entry)
    return sorted(results, key=lambda x: SPEED_ORDER.get(x["speed"], 99))

# ─── Shared CSS ───────────────────────────────────────────────────────────────
CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;position:sticky;top:0;z-index:100}
.logo{font-size:18px;font-weight:bold;color:#38bdf8;letter-spacing:.02em}
.sub{color:#64748b;font-size:13px}
.container{max-width:820px;margin:0 auto;padding:24px 16px}
.card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:22px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:14px}
label{font-size:13px;color:#94a3b8;display:block;margin-bottom:4px}
input,select,textarea{width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:10px 12px;border-radius:6px;font-size:14px;margin-bottom:14px;outline:none}
input:focus,select:focus,textarea:focus{border-color:#38bdf8}
textarea{min-height:90px;resize:vertical}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.btn{background:#38bdf8;color:#0f172a;border:none;padding:11px 22px;border-radius:6px;font-size:14px;font-weight:bold;cursor:pointer;text-decoration:none;display:inline-block;transition:background .15s}
.btn:hover{background:#7dd3fc}
.btn-outline{background:transparent;border:1px solid #475569;color:#94a3b8}
.btn-outline:hover{border-color:#38bdf8;color:#38bdf8}
.btn-green{background:#16a34a}.btn-green:hover{background:#22c55e}
.btn-sm{padding:7px 14px;font-size:12px}
.grant-row{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:14px 16px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.grant-info{flex:1;min-width:0}
.grant-name{font-size:14px;font-weight:bold;color:#e2e8f0;margin-bottom:3px}
.grant-meta{font-size:12px;color:#64748b;margin-bottom:3px}
.grant-desc{font-size:12px;color:#94a3b8;line-height:1.5}
.badge{padding:2px 9px;border-radius:10px;font-size:11px;font-weight:bold;white-space:nowrap;display:inline-block}
.bg-green{background:#16a34a;color:#fff}
.bg-amber{background:#d97706;color:#fff}
.bg-purple{background:#7c3aed;color:#fff}
.bg-blue{background:#1d4ed8;color:#fff}
.bg-red{background:#dc2626;color:#fff}
.bg-gray{background:#334155;color:#94a3b8}
.narrative-box{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:16px;font-size:13px;color:#cbd5e1;line-height:1.8;white-space:pre-wrap;position:relative;margin:12px 0}
.copy-btn{position:absolute;top:8px;right:8px;background:#334155;border:none;color:#94a3b8;padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer}
.copy-btn:hover{background:#38bdf8;color:#0f172a}
.status-sel{width:auto;margin:0;padding:4px 8px;font-size:12px;border-radius:4px}
.trial-bar{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 18px;display:flex;gap:28px;align-items:center;margin-bottom:18px;flex-wrap:wrap}
.trial-stat{text-align:center}
.trial-num{font-size:24px;font-weight:bold;color:#38bdf8}
.trial-lbl{font-size:11px;color:#64748b}
.lock-box{background:#1e3a5f;border:2px solid #2563eb;border-radius:10px;padding:28px;text-align:center;margin-bottom:22px}
.lock-box h2{color:#93c5fd;font-size:20px;margin-bottom:10px}
.lock-box p{color:#bfdbfe;font-size:14px;margin-bottom:18px;line-height:1.6}
.alert{background:#1e3a5f;border-left:4px solid #3b82f6;padding:11px 16px;border-radius:4px;font-size:13px;color:#93c5fd;margin-bottom:16px}
.alert-warn{background:#451a03;border-color:#f59e0b;color:#fcd34d}
.section-label{font-size:11px;font-weight:bold;color:#38bdf8;text-transform:uppercase;letter-spacing:.06em;margin:16px 0 6px}
.speed-tag{font-size:10px;padding:2px 7px;border-radius:8px;font-weight:bold;margin-left:6px}
.speed-FASTEST{background:#064e3b;color:#34d399}
.speed-FAST{background:#14532d;color:#86efac}
.speed-MEDIUM{background:#451a03;color:#fcd34d}
.speed-SLOWER{background:#1e1b4b;color:#a5b4fc}
.speed-LONG{background:#1e293b;color:#64748b}
@media(max-width:600px){.g2{grid-template-columns:1fr}.grant-row{flex-direction:column;align-items:flex-start}.trial-bar{gap:16px}}
</style>"""

# ─── Page builders ────────────────────────────────────────────────────────────
def page(title: str, body: str, subtitle: str = "GHE Grant Application Portal") -> str:
    return f"""<!DOCTYPE html><html lang=en><head>
<meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title>{CSS}</head><body>
<header>
  <div class=logo>GHE Grant Portal</div>
  <div class=sub>{subtitle}</div>
</header>
<div class=container>{body}</div>
<script>
function copyText(id,btn){{
  const el=document.getElementById(id);
  const t=el.innerText.replace(/^Copy$/m,'').trim();
  navigator.clipboard.writeText(t).then(()=>{{
    btn.textContent='Copied!';btn.style.background='#22c55e';btn.style.color='#fff';
    setTimeout(()=>{{btn.textContent='Copy';btn.style.background='';btn.style.color='';}},1600);
  }});
}}
</script>
</body></html>"""

def profile_html(token: str, error: str = "") -> str:
    err = f'<div class="alert alert-warn">{error}</div>' if error else ""
    return page("Setup — GHE Grant Portal", f"""
{err}
<div class=card>
<h2>Tell us about your business</h2>
<p style="font-size:13px;color:#64748b;margin-bottom:18px">We match you with grants and write your narratives. Takes 2 minutes.</p>
<form method=POST action="/u/{token}/profile">
<div class=g2>
<div><label>Business Name *</label><input name=business_name required placeholder="Your business name"></div>
<div><label>Your Full Name *</label><input name=owner_name required placeholder="First and last name"></div>
</div>
<label>Business Type / Industry *</label>
<input name=business_type required placeholder="e.g. AI automation company, HVAC contractor, roofing, landscaping">
<div class=g2>
<div><label>State</label>
<select name=state>
<option value=CA>California</option><option value=TX>Texas</option><option value=FL>Florida</option>
<option value=NY>New York</option><option value=GA>Georgia</option><option value=NC>North Carolina</option>
<option value=IL>Illinois</option><option value=OH>Ohio</option><option value=AZ>Arizona</option>
<option value=Other>Other State</option>
</select></div>
<div><label>Annual Revenue</label>
<select name=revenue_range>
<option value=pre-revenue>Pre-revenue</option>
<option value=under-50k>Under $50K</option>
<option value=50k-250k>$50K to $250K</option>
<option value=250k-1m>$250K to $1M</option>
<option value=over-1m>Over $1M</option>
</select></div>
</div>
<div class=g2>
<div><label>Owner Ethnicity / Race</label>
<select name=ethnicity>
<option value="Black/African American">Black / African American</option>
<option value="Hispanic/Latino">Hispanic / Latino</option>
<option value="Asian/Pacific Islander">Asian / Pacific Islander</option>
<option value="Native American">Native American</option>
<option value="Multiracial">Multiracial</option>
<option value="White/Caucasian">White / Caucasian</option>
<option value="Other">Other / Prefer not to say</option>
</select></div>
<div><label>Owner Gender</label>
<select name=gender>
<option value=Male>Male</option>
<option value=Female>Female</option>
<option value=Non-binary>Non-binary</option>
<option value="Prefer not to say">Prefer not to say</option>
</select></div>
</div>
<div class=g2>
<div><label>Number of Employees</label>
<select name=employees>
<option value="1 (solo)">1 (solo founder)</option>
<option value="2-5">2 to 5</option>
<option value="6-10">6 to 10</option>
<option value="11-25">11 to 25</option>
</select></div>
<div><label>Do you have an EIN?</label>
<select name=has_ein>
<option value=1>Yes</option>
<option value=0>No (get free at irs.gov)</option>
</select></div>
</div>
<div class=g2>
<div><label>Business Formation</label>
<select name=has_dba>
<option value=0>Sole proprietor (no DBA or LLC)</option>
<option value=1>DBA filed</option>
<option value=2>LLC or corporation</option>
</select></div>
</div>
<label>What does your business do? Who do you serve? What problem do you solve? *</label>
<textarea name=description required placeholder="Write 2-4 sentences. Be specific about what you do, who your customers are, and what problem you solve for them."></textarea>
<button class=btn type=submit>Find My Grants →</button>
</form>
</div>""")

def dashboard_html(token: str, portal: dict, grants: list, apps: list, locked: bool, reason: str) -> str:
    created = datetime.fromisoformat(portal["created_at"])
    days_left = max(0, TRIAL_DAYS - (datetime.now(timezone.utc) - created).days)
    apps_left = max(0, TRIAL_APPS - portal["apps_used"])
    applied_ids = {a["grant_id"] for a in apps}

    # Trial bar
    trial_bar = ""
    if not locked:
        al_color = "#22c55e" if apps_left > 0 else "#ef4444"
        dl_color = "#22c55e" if days_left > 3 else "#ef4444"
        trial_bar = f"""
<div class=trial-bar>
  <div class=trial-stat><div class=trial-num style="color:{al_color}">{apps_left}</div><div class=trial-lbl>Applications Left</div></div>
  <div class=trial-stat><div class=trial-num style="color:{dl_color}">{days_left}</div><div class=trial-lbl>Days Remaining</div></div>
  <div class=trial-stat><div class=trial-num>{len(apps)}</div><div class=trial-lbl>Generated</div></div>
  <div style="margin-left:auto"><a href="/u/{token}/upgrade" class="btn btn-outline btn-sm">Upgrade — Unlimited</a></div>
</div>"""

    # Lock banner
    lock_html = ""
    if locked:
        lock_html = f"""
<div class=lock-box>
  <h2>Trial Limit Reached</h2>
  <p>{reason}<br>You can still view and update your existing application statuses below.</p>
  <a href="/u/{token}/upgrade" class=btn>Upgrade to Full Access →</a>
</div>"""

    # Existing applications
    apps_html = ""
    if apps:
        status_options = list(STATUS_COLORS.keys())
        items = ""
        for a in apps:
            sc = STATUS_COLORS.get(a["status"], "gray")
            opts = "".join(
                f'<option value="{s}"{"selected" if s==a["status"] else ""}>{s}</option>'
                for s in status_options
            )
            gdata = GRANTS.get(a["grant_id"], {})
            narrative_html = render_narrative_blocks(a["narrative"], a["id"])
            items += f"""
<div class=card style="padding:16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:10px">
    <div>
      <div style="font-weight:bold;color:#e2e8f0;font-size:14px">{a['grant_name']}</div>
      <div style="font-size:12px;color:#64748b">{a['grant_amount']} &middot; Generated {a['created_at'][:10]}</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <form method=POST action="/u/{token}/status/{a['id']}">
        <select name=status class=status-sel onchange="this.form.submit()">{opts}</select>
      </form>
      <a href="/u/{token}/apply/{a['grant_id']}" class="btn btn-green btn-sm">Open Apply View ↗</a>
    </div>
  </div>
  {narrative_html}
</div>"""
        apps_html = f'<div class=card><h2>Your Applications</h2>{items}</div>'

    # Grant list
    grants_html = ""
    for g in grants:
        already = g["id"] in applied_ids
        color = f"bg-{g['color']}"
        speed = g["speed"]
        if already:
            action = '<span class="badge bg-blue">Applied</span>'
        elif locked:
            action = f'<a href="/u/{token}/upgrade" class="btn btn-outline btn-sm">Upgrade</a>'
        else:
            action = f'''<form method=POST action="/u/{token}/generate/{g['id']}">
<button class="btn btn-green btn-sm" type=submit>Generate Application</button></form>'''

        grants_html += f"""
<div class=grant-row>
  <div class=grant-info>
    <div class=grant-name>{g['name']} <span class="speed-tag speed-{speed}">{speed}</span></div>
    <div class=grant-meta><span class="badge {color}">{g['amount']}</span> &nbsp; {g['timeline']} &nbsp;&middot;&nbsp; {g['difficulty']}</div>
    <div class=grant-desc>{g['desc']}</div>
  </div>
  <div style="flex-shrink:0">{action}</div>
</div>"""

    total_available = sum(g["min_amount"] for g in grants)
    return page(
        f"Grant Portal — {portal['business_name']}",
        f"""
{trial_bar}
{lock_html}
{apps_html}
<div class=card>
<h2>Matched Grants — {len(grants)} available &nbsp;<span style="font-size:12px;color:#64748b;font-weight:normal">Up to ${total_available:,} total potential</span></h2>
<p style="font-size:13px;color:#64748b;margin-bottom:14px">Sorted fastest to slowest. Click Generate to get your AI-written narrative ready to paste into the application form.</p>
{grants_html}
</div>""",
        subtitle=portal["business_name"]
    )

def render_narrative_blocks(narrative_json: str, app_id: int) -> str:
    """Render narrative JSON as copyable blocks."""
    try:
        data = json.loads(narrative_json)
    except Exception:
        return f'<div class=narrative-box id="n{app_id}"><button class=copy-btn onclick="copyText(\'n{app_id}\',this)">Copy</button>{narrative_json}</div>'

    mode = data.get("mode", "narrative")
    if mode == "qa":
        blocks = ""
        for i, pair in enumerate(data.get("answers", [])):
            bid = f"n{app_id}q{i}"
            blocks += f"""
<div style="margin-bottom:16px">
  <div style="font-size:12px;font-weight:bold;color:#38bdf8;margin-bottom:6px">{pair['q']}</div>
  <div class=narrative-box id="{bid}" style="margin:0"><button class=copy-btn onclick="copyText('{bid}',this)">Copy</button>{pair['a']}</div>
</div>"""
        return blocks
    elif mode == "error":
        return f'<div class=alert alert-warn>{data.get("text","Error")}</div>'
    else:
        bid = f"n{app_id}"
        return f'<div class=narrative-box id="{bid}"><button class=copy-btn onclick="copyText(\'{bid}\',this)">Copy</button>{data.get("text","")}</div>'

def split_view_html(token: str, portal: dict, grant: dict, app_record: dict) -> str:
    answers_html = render_narrative_blocks(app_record["narrative"], app_record["id"])
    grant_url = grant["url"]
    iframe_js = f"""
<script>
var fr = document.getElementById('grant-frame');
fr.onerror = function(){{ showFallback(); }};
setTimeout(function(){{
  try {{
    var d = fr.contentDocument || fr.contentWindow.document;
    if(!d || d.location.href==='about:blank') showFallback();
  }} catch(e) {{ showFallback(); }}
}}, 3000);
function showFallback(){{
  document.getElementById('frame-wrap').style.display='none';
  document.getElementById('frame-fallback').style.display='block';
}}
</script>"""
    return f"""<!DOCTYPE html><html lang=en><head>
<meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Apply — {grant['name']}</title>{CSS}
<style>
.split{{display:grid;grid-template-columns:1fr 1fr;gap:0;height:calc(100vh - 56px)}}
.split-left{{overflow-y:auto;padding:20px;border-right:1px solid #334155;background:#0f172a}}
.split-right{{overflow:hidden;position:relative}}
iframe{{width:100%;height:100%;border:none}}
.fallback-box{{padding:32px;text-align:center}}
@media(max-width:700px){{.split{{grid-template-columns:1fr;height:auto}}.split-right{{height:500px}}}}
</style>
</head><body>
<header style="padding:10px 16px">
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <a href="/u/{token}" style="color:#64748b;font-size:13px;text-decoration:none">← Back</a>
    <div class=logo style="font-size:15px">{grant['name']}</div>
    <span class="badge bg-{grant['color']}" style="margin-left:4px">{grant['amount']}</span>
    <a href="{grant_url}" target=_blank class="btn btn-sm" style="margin-left:auto">Open Official Form in New Tab ↗</a>
  </div>
</header>
<div class=split>
  <div class=split-left>
    <div style="font-size:13px;font-weight:bold;color:#38bdf8;margin-bottom:4px">YOUR AI-WRITTEN ANSWERS</div>
    <p style="font-size:12px;color:#64748b;margin-bottom:16px">Copy each answer and paste it into the form on the right. If the form won't load, use the "Open in New Tab" button above.</p>
    {answers_html}
  </div>
  <div class=split-right>
    <div id=frame-wrap style="height:100%">
      <iframe id=grant-frame src="{grant_url}" sandbox="allow-forms allow-scripts allow-same-origin allow-popups"></iframe>
    </div>
    <div id=frame-fallback style="display:none" class=fallback-box>
      <div style="font-size:40px;margin-bottom:12px">&#128279;</div>
      <h3 style="color:#e2e8f0;margin-bottom:8px">This site blocks embedding</h3>
      <p style="color:#94a3b8;font-size:13px;margin-bottom:20px">Copy your answers from the left panel, then open the official form in a new tab to paste them in.</p>
      <a href="{grant_url}" target=_blank class=btn>Open {grant['name']} Form ↗</a>
    </div>
  </div>
</div>
{iframe_js}
<script>
function copyText(id,btn){{
  const el=document.getElementById(id);
  const t=el.innerText.replace(/^Copy$/m,'').trim();
  navigator.clipboard.writeText(t).then(()=>{{
    btn.textContent='Copied!';btn.style.background='#22c55e';btn.style.color='#fff';
    setTimeout(()=>{{btn.textContent='Copy';btn.style.background='';btn.style.color='';}},1600);
  }});
}}
</script>
</body></html>"""

def upgrade_html(token: str) -> str:
    return page("Upgrade — GHE Grant Portal", f"""
<div class=card style="text-align:center;padding:48px 24px">
  <div style="font-size:52px;margin-bottom:14px">&#128274;</div>
  <h2 style="font-size:22px;margin-bottom:10px">Your Free Trial Is Over</h2>
  <p style="color:#94a3b8;font-size:14px;max-width:480px;margin:0 auto 28px;line-height:1.7">
    Upgrade to get unlimited grant applications, new grants added monthly, status tracking,
    and direct support from Gray Horizons Enterprise.
  </p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:460px;margin:0 auto 28px;text-align:left">
    <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:18px">
      <div style="font-size:11px;color:#64748b;margin-bottom:6px;font-weight:bold">STARTER</div>
      <div style="font-size:26px;font-weight:bold;color:#38bdf8;margin-bottom:6px">$47<span style="font-size:13px;color:#64748b">/mo</span></div>
      <div style="font-size:12px;color:#94a3b8;line-height:1.8">10 applications/month<br>All grant categories<br>Status tracking</div>
    </div>
    <div style="background:#0f172a;border:2px solid #38bdf8;border-radius:8px;padding:18px">
      <div style="font-size:11px;color:#38bdf8;margin-bottom:6px;font-weight:bold">PRO — BEST VALUE</div>
      <div style="font-size:26px;font-weight:bold;color:#38bdf8;margin-bottom:6px">$97<span style="font-size:13px;color:#64748b">/mo</span></div>
      <div style="font-size:12px;color:#94a3b8;line-height:1.8">Unlimited applications<br>New grants every month<br>1-on-1 support calls</div>
    </div>
  </div>
  <a href="{CALENDLY}" target=_blank class=btn style="font-size:15px;padding:14px 36px">Book a Call to Upgrade →</a>
  <div style="margin-top:14px"><a href="/u/{token}" style="color:#64748b;font-size:13px;text-decoration:none">← Back to my applications</a></div>
</div>""")

def admin_html(portals: list, base_url: str) -> str:
    rows = ""
    for p in portals:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(p["created_at"])).days
        locked = days >= TRIAL_DAYS or p["apps_used"] >= TRIAL_APPS
        status = "LOCKED" if locked else f"{TRIAL_APPS - p['apps_used']} apps left"
        label = p.get("label") or p.get("business_name") or "New Portal"
        rows += f"""<tr style="border-bottom:1px solid #334155">
<td style="padding:10px 12px;color:#e2e8f0">{label}</td>
<td style="padding:10px 12px;color:#64748b;font-size:12px">{p['created_at'][:10]}</td>
<td style="padding:10px 12px;color:#{"ef4444" if locked else "22c55e"};font-size:12px">{status}</td>
<td style="padding:10px 12px;font-size:12px"><a href="/u/{p['token']}" style="color:#38bdf8;text-decoration:none" target=_blank>/u/{p['token'][:12]}...</a></td>
</tr>"""

    return page("Admin — GHE Grant Portal", f"""
<div class=card>
  <h2>Generate New Portal Link</h2>
  <p style="font-size:13px;color:#64748b;margin-bottom:16px">Each link gives a user {TRIAL_APPS} free applications over {TRIAL_DAYS} days.</p>
  <form method=POST action="/admin/generate" style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end">
  <div style="flex:1;min-width:200px">
  <label>Label (optional — client name or note)</label>
  <input name=label placeholder="e.g. John HVAC, Facebook Lead #4" style="margin-bottom:0">
  </div>
  <input type=hidden name=admin_key id=akey>
  <button class=btn type=submit onclick="document.getElementById('akey').value=prompt('Admin key:')">Generate Link</button>
  </form>
</div>
{"<div class=card><h2>Active Portals</h2><table style='width:100%;border-collapse:collapse'><thead><tr style='border-bottom:1px solid #334155'><th style='padding:8px 12px;text-align:left;color:#64748b;font-size:12px'>Client</th><th style='padding:8px 12px;text-align:left;color:#64748b;font-size:12px'>Created</th><th style='padding:8px 12px;text-align:left;color:#64748b;font-size:12px'>Status</th><th style='padding:8px 12px;text-align:left;color:#64748b;font-size:12px'>Link</th></tr></thead><tbody>"+rows+"</tbody></table></div>" if portals else ""}
""", subtitle="Admin Dashboard")

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    key = request.query_params.get("key", "")
    if key != ADMIN_KEY:
        return HTMLResponse(page("Admin Login", """
<div class=card style="max-width:400px">
<h2>Admin Access</h2>
<form method=GET action="/admin" style="margin-top:14px">
<label>Admin Key</label>
<input name=key type=password placeholder="Enter admin key">
<button class=btn type=submit>Login</button>
</form></div>"""))
    portals = get_all_portals()
    base = str(request.base_url).rstrip("/")
    return HTMLResponse(admin_html(portals, base))

@app.post("/admin/generate", response_class=HTMLResponse)
async def admin_generate(request: Request):
    form = await request.form()
    key = form.get("admin_key", "")
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    token = uuid.uuid4().hex[:16]
    label = form.get("label", "").strip()
    db = get_db()
    db.execute("INSERT INTO portals (token, created_at, label) VALUES (?,?,?)",
               (token, datetime.now(timezone.utc).isoformat(), label))
    db.commit()
    db.close()
    base = str(request.base_url).rstrip("/")
    url = f"{base}/u/{token}"
    return HTMLResponse(page("Link Generated", f"""
<div class=card style="text-align:center;padding:36px">
  <div style="font-size:13px;color:#64748b;margin-bottom:8px">New portal link generated</div>
  <div style="font-size:15px;font-weight:bold;color:#38bdf8;background:#0f172a;border:1px solid #334155;padding:14px;border-radius:6px;word-break:break-all;margin-bottom:18px">{url}</div>
  <button class=btn onclick="navigator.clipboard.writeText('{url}');this.textContent='Copied!'">Copy Link</button>
  &nbsp;
  <a href="/admin?key={ADMIN_KEY}" class="btn btn-outline">Back to Admin</a>
</div>"""))

@app.get("/u/{token}", response_class=HTMLResponse)
async def portal_get(token: str):
    portal = get_portal(token)
    if not portal:
        raise HTTPException(status_code=404, detail="This portal link is invalid or expired.")
    if not portal["profile_done"]:
        return HTMLResponse(profile_html(token))
    locked, reason = is_locked(portal)
    grants = match_grants(portal)
    apps = get_apps(token)
    return HTMLResponse(dashboard_html(token, portal, grants, apps, locked, reason))

@app.post("/u/{token}/profile", response_class=HTMLResponse)
async def save_profile(token: str, request: Request):
    portal = get_portal(token)
    if not portal:
        raise HTTPException(status_code=404)
    form = await request.form()
    biz  = form.get("business_name", "").strip()
    own  = form.get("owner_name", "").strip()
    desc = form.get("description", "").strip()
    if not biz or not own or not desc:
        return HTMLResponse(profile_html(token, "Please fill in all required fields."))
    db = get_db()
    db.execute("""UPDATE portals SET
        business_name=?,owner_name=?,business_type=?,ethnicity=?,gender=?,
        state=?,has_ein=?,has_dba=?,revenue_range=?,employees=?,description=?,profile_done=1
        WHERE token=?""",
        (biz, own, form.get("business_type",""), form.get("ethnicity",""),
         form.get("gender",""), form.get("state","CA"),
         int(form.get("has_ein","0")), int(form.get("has_dba","0")),
         form.get("revenue_range","pre-revenue"), form.get("employees","1 (solo)"),
         desc, token))
    db.commit()
    db.close()
    return RedirectResponse(f"/u/{token}", status_code=302)

@app.post("/u/{token}/generate/{grant_id}", response_class=HTMLResponse)
async def generate_app(token: str, grant_id: str):
    portal = get_portal(token)
    if not portal:
        raise HTTPException(status_code=404)
    locked, _ = is_locked(portal)
    if locked:
        return RedirectResponse(f"/u/{token}/upgrade", status_code=302)
    grant = GRANTS.get(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    db = get_db()
    already = db.execute(
        "SELECT id FROM applications WHERE token=? AND grant_id=?", (token, grant_id)
    ).fetchone()
    if already:
        db.close()
        return RedirectResponse(f"/u/{token}", status_code=302)
    narrative = generate_narrative(portal, grant)
    db.execute("""INSERT INTO applications (token,grant_id,grant_name,grant_amount,narrative,created_at,apply_url)
        VALUES (?,?,?,?,?,?,?)""",
        (token, grant_id, grant["name"], grant["amount"], narrative,
         datetime.now(timezone.utc).isoformat(), grant["url"]))
    db.execute("UPDATE portals SET apps_used=apps_used+1 WHERE token=?", (token,))
    db.commit()
    db.close()
    return RedirectResponse(f"/u/{token}", status_code=302)

@app.post("/u/{token}/status/{app_id}")
async def update_status(token: str, app_id: int, request: Request):
    form = await request.form()
    status = form.get("status", "Not Started")
    db = get_db()
    db.execute("UPDATE applications SET status=? WHERE id=? AND token=?", (status, app_id, token))
    db.commit()
    db.close()
    return RedirectResponse(f"/u/{token}", status_code=302)

@app.get("/u/{token}/apply/{grant_id}", response_class=HTMLResponse)
async def apply_split_view(token: str, grant_id: str):
    portal = get_portal(token)
    if not portal:
        raise HTTPException(status_code=404)
    grant = GRANTS.get(grant_id)
    if not grant:
        raise HTTPException(status_code=404)
    db = get_db()
    app_record = db.execute(
        "SELECT * FROM applications WHERE token=? AND grant_id=?", (token, grant_id)
    ).fetchone()
    db.close()
    if not app_record:
        return RedirectResponse(f"/u/{token}", status_code=302)
    return HTMLResponse(split_view_html(token, portal, grant, dict(app_record)))

@app.get("/u/{token}/upgrade", response_class=HTMLResponse)
async def upgrade_view(token: str):
    portal = get_portal(token)
    if not portal:
        raise HTTPException(status_code=404)
    return HTMLResponse(upgrade_html(token))

@app.get("/health")
async def health():
    return {"status": "ok", "grants": len(GRANTS)}

@app.get("/")
async def root():
    return RedirectResponse("/admin")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
