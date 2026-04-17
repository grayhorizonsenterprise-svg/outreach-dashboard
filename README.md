# Gray Horizons Enterprise — Agentic Workflows

Full-stack outreach, grant hunting, and voice sales system for a 5-niche B2B agency.
Deployed on Railway (Python/Flask dashboard + Node.js voice server).

---

## System Overview

| System | Purpose | Stack |
|---|---|---|
| Outreach Dashboard | Approve/send emails to prospects | Python / Flask / SendGrid |
| Prospect Pipeline | Find, enrich, qualify, generate emails | Python pipeline scripts |
| Grant Agent | Find, score, and draft federal/local grants | Python / FastAPI / SQLite |
| Voice Server | AI voice sales rep per niche | Node.js / Express |
| Revenue Engine | 16 agentic revenue modules | Node.js |

---

## Target Niches

1. HOA Management
2. HVAC
3. Dental
4. Plumbing
5. General Contractor

---

## Outreach Pipeline

### Scripts (run in order)

```
prospect_finder.py       → prospects_raw.csv
prospect_enricher.py     → prospects_enriched.csv
prospect_qualifier.py    → prospects_ranked.csv
outreach_generator.py    → outreach_queue.csv
approval_dashboard.py    → Flask UI (approve → send via SendGrid)
```

### prospect_finder.py
- Uses DuckDuckGo Search (ddgs) to find company websites
- 60 queries total: 12 per niche × 5 niches
- Regional coverage: West Coast, Southwest, Midwest, Southeast, Texas
- Scrapes each URL for email, contact page, and company name
- Skips junk domains (Yelp, LinkedIn, Angi, BBB, etc.)
- Output: `prospects_raw.csv` with columns: company, website, email, contact_page_url, location, niche
- Runtime: ~15 min, ~600 prospects per run

### outreach_generator.py
- Reads `prospects_ranked.csv`
- 3 subject lines + 3 message templates per niche (15 total variations)
- Randomizes subject and body per prospect
- Tags each row with niche field
- Output: `outreach_queue.csv`

### approval_dashboard.py (Flask app — Railway)
- Shows pending leads as cards, filterable by niche
- Niche filter buttons: All / HOA / HVAC / Dental / Plumbing / Contractor
- Approve single lead or Approve All
- Sends via SendGrid API (Gmail SMTP is blocked by Railway)
- Resend Failed button for any failed sends
- Empty state: shows scraping status message when queue is empty
- `/debug` route shows SMTP/SendGrid env status

### Email Sending
- **Platform**: SendGrid API (`@sendgrid/mail` in Node, `sendgrid` in Python)
- **Verified sender**: `grayhorizonsenterprise@gmail.com` (hardcoded — case-sensitive)
- **Why not Gmail SMTP**: Railway blocks outbound SMTP (Errno 101 Network unreachable)
- **Daily limit**: 150 emails, 20s between sends, 2 retries with exponential backoff

### resend_now.py
- Standalone script to retry failed emails from `sent_log.csv`
- Reads `.env` manually, strips whitespace from app password
- Uses Gmail SMTP (local use only — not Railway)

---

## Approval Dashboard — Key Details

- **Start command**: `python start.py` (Railway) or `python approval_dashboard.py` (local)
- **Port**: 5001 (local) / assigned by Railway
- **Data dir**: `DATA_DIR` env var (defaults to script directory)
- **SendGrid env vars needed**:
  - `SENDGRID_API_KEY`
  - `SENDER_EMAIL=grayhorizonsenterprise@gmail.com` (must be lowercase)

---

## Grant Agent

Location: `grant_agent/`

### Architecture

```
main.py              FastAPI entrypoint
api/routes.py        All REST endpoints
database/db.py       SQLite operations
discovery/           grants_gov.py + rss_feeds.py
scoring/scorer.py    Match score + track classification
generation/generator.py   Claude/GPT-4o application writer
scheduler/jobs.py    Daily scan cron
automation/          Auto-submit (Playwright)
dashboard/index.html Single-page UI
```

### Endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | /grants | List all grants, filterable by track/score/status |
| POST | /scan | Trigger background grant scan |
| POST | /search | Live keyword search (not saved) |
| POST | /grants/{id}/apply | Generate application via Claude |
| POST | /grants/{id}/dual-apply | Claude + GPT-4o + synthesis |
| POST | /grants/{id}/checklist | Step-by-step application guide |
| GET | /applications | All generated applications |
| PATCH | /applications/{id}/status | Update status (draft/submitted/awarded/etc.) |
| GET | /stats | Dashboard stats |

### Grant Track Classification (scorer.py)

Three tracks assigned to every grant:

- **apply_now** — minority-owned, local/city grants, pilot programs, emerging entrepreneur signals
- **avoid** — proven track record required, infrastructure focus, highly competitive federal
- **review** — everything else

Dashboard renders grants in three sections: Apply Now → Review → Avoid (avoid rows dimmed).

### Genius Mode (generator.py)
Every AI-generated section follows a 5-part structure:
1. Current State — what the business does now
2. Demand Signal — market need or growth indicator
3. Constraint — what's holding them back
4. Action — what the grant funds
5. Outcome — measurable result

Applied via system prompt to both Claude and GPT-4o calls.
Falls back to `generate_fallback_application()` (deterministic, no AI) if API unavailable.

### Grant Agent Deploy (Railway)
- **Start**: `python start.py` inside `grant_agent/`
- **Nixpacks config**: `grant_agent/nixpacks.toml`
- **Railway config**: `grant_agent/railway.toml`

---

## Voice Server

Location: `voice/`

### Stack
- Node.js / Express
- `@sendgrid/mail` for email
- Web Speech API (browser-side STT)
- Per-niche AI voice persona

### Tabs (voice/index.html)
Five independent tabs, each with:
- Niche icon, title, description
- Independent chat window
- Start Talking + Reset buttons
- Text input fallback
- Tabs filter in-place — no page navigation

### outreachEngine.js
Production outreach engine used by voice server:

```
CONFIG:
  DAILY_LIMIT: 150
  DELAY_BETWEEN_EMAILS_MS: 20000   (20s throttle)
  MAX_RETRIES: 2
  FOLLOW_UP_DELAY_HOURS: 48
  FROM: grayhorizonsenterprise@gmail.com

Functions:
  sendEmailSafe()       retry with 5s/10s backoff
  sendBatchSafe()       daily limit + throttle + auto-generate copy if missing
  generateHumanEmail()  5 openers × 5 problems × 5 closers = 125 combinations
  generateFollowUp()    randomized follow-up copy
  scheduleFollowUps()   fires 48h after send via setTimeout
  getStatus()           daily count, remaining, recent log
```

### Voice Server Routes
| Route | Purpose |
|---|---|
| POST /voice | Chat with AI persona |
| POST /send-email | Send single email via SendGrid |
| POST /send-batch | Send batch (respects daily limit) |
| GET /outreach-status | Daily count, remaining, log |
| GET /health | Service health + SendGrid key status |

### Voice Server Deploy (Railway)
- **Start**: `node server.js` inside `voice/`
- **Env vars needed**: `SENDGRID_API_KEY`, `ANTHROPIC_API_KEY`

---

## Revenue Engine

Location: `revenue_engine/`

16 agentic modules (all Node.js):

| Module | Purpose |
|---|---|
| leadAgent.js | Lead sourcing |
| outreachAgent.js | Email/contact automation |
| closeAgent.js | Deal closing logic |
| deliveryAgent.js | Service delivery tracking |
| demoAgent.js | Demo scheduling |
| grantProfile.js | Grant profile builder |
| grantSearch.js | Grant opportunity finder |
| marketSignalAgent.js | Market trend signals |
| offerGenerator.js | Proposal/offer generation |
| opportunityAgent.js | Opportunity scoring |
| performanceAgent.js | KPI tracking |
| revenueExpander.js | Upsell/expansion logic |
| strategyAgent.js | Strategic recommendations |
| systemBuilder.js | Workflow orchestration |
| trendScanner.js | Industry trend scanner |
| server.js | Express API entrypoint |

---

## Environment Variables

### Root (approval_dashboard / outreach)
```
SENDGRID_API_KEY=
SENDER_EMAIL=grayhorizonsenterprise@gmail.com
SENDER_APP_PASSWORD=           # Gmail app password — local SMTP only
DATA_DIR=                      # Optional: override CSV data directory
```

### grant_agent
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

### voice
```
SENDGRID_API_KEY=
ANTHROPIC_API_KEY=
```

---

## Known Issues / Pitfalls

| Issue | Fix |
|---|---|
| Railway blocks SMTP (Errno 101) | Use SendGrid API, not Gmail SMTP |
| SendGrid 403 "from does not match verified sender" | `verified_from` must be lowercase, exact match |
| Gmail App Password invalidated | Changing Google account password kills all app passwords — regenerate |
| Spaces in App Password | Google shows it with spaces — strip before use |
| Niche tabs opening new pages | Use JS filter (`filterNiche()`), not `<a href>` nav links |
| Pipeline slow (1+ hour) | Replace state/city loop with 60 targeted regional queries |

---

## Deployment (Railway)

Two services deployed:

1. **ghe-dashboard** — Python Flask outreach approval UI
   - Root: `/`
   - Start: `python start.py`

2. **ghe-grant-agent** — Python FastAPI grant hunter
   - Root: `grant_agent/`
   - Start: `python start.py`

3. **ghe-voice** — Node.js voice/outreach server
   - Root: `voice/`
   - Start: `node server.js`

No healthcheck in `railway.toml` — Flask/FastAPI need time to boot before Railway probes.

---

## Local Dev

```bash
# Outreach dashboard
python approval_dashboard.py

# Run full prospect pipeline
python run_pipeline.py

# Grant agent
cd grant_agent && python main.py

# Voice server
cd voice && node server.js
```
