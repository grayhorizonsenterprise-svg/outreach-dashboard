# DROP-IN CONTEXT PROMPT — Gray Horizons Enterprise
## Paste this entire block at the start of the next Claude Code session

---

You are continuing an active build for Gray Horizons Enterprise. Here is the full system state as of 2026-05-04.

---

## WHO I AM
- Owner: Curtis, grayhorizonsenterprise@gmail.com
- Brand: Gray Horizons Enterprise — AI-powered outreach and automation for local service businesses
- Sender name in all emails: **Alex** (never "Gray", never anything else)
- Website: https://grayhorizonsenterprise.com
- GitHub: grayhorizonsenterprise-svg/outreach-dashboard
- Project dir: `C:\Users\curti\Downloads\First Agentic Workflows`

---

## WHAT IS BUILT

### 1. Email Outreach System (PRIMARY REVENUE)
- Flask dashboard deployed on Railway (`approval_dashboard.py`)
- **6,918 total leads** loaded in Railway dashboard as of last session
- **6,338 pending**, sending 400/day via "Send 400 Now" button
- Leads stored in `outreach_queue.csv` (gitignored — uploaded manually via /upload-queue)
- Raw prospects in `prospects_raw.csv` (18,174 rows, 7,235 with emails)
- Source: `maps_scraper.py` — Google Maps Places API, 100 cities × 7 niches

### 2. Social Pipeline System
- Tracked in dashboard Social Pipeline tab
- Stages: `commented → replied → demo_sent → closed → dead`
- Social prospects with email auto-queue into email outreach
- Sent log has "Social" button to route non-responders into social pipeline

### 3. Video Pipeline
- `run_pipeline.bat` → `viral_system.py` → `metadata_engine.py` → `auto_render.bat`
- Clips: `clips/raw/` → `clips/output/` → `clips/posted/`
- ffmpeg overlay: "GET MORE CUSTOMERS" (top) / "Most businesses get ignored online" (middle) / "We fix that" (bottom, yellow)
- `comment_generator.py` → 100 outreach comments → `comments_today.txt`
- `response_scripts.txt` → 4-stage DM conversion flow

---

## KEY FILES

| File | Purpose |
|------|---------|
| `approval_dashboard.py` | Main Flask app — Railway deployed |
| `outreach_generator.py` | Builds outreach_queue.csv from prospects_raw.csv |
| `prospect_qualifier.py` | Filters new Maps leads (protects rows with emails from deletion) |
| `maps_scraper.py` | Google Maps scraper — national lead generation |
| `viral_system.py` | Pexels clip downloader + MoviePy renderer |
| `auto_render.bat` | ffmpeg batch renderer, 3-text overlay, 1080x1920 |
| `run_pipeline.bat` | Single entry point for full video pipeline |
| `comment_generator.py` | 100 TikTok/YouTube outreach comments |
| `response_scripts.txt` | Comment → DM → demo → close scripts |
| `metadata_engine.py` | Clip title/description/tags generator |
| `CONTEXT.md` | Full technical reference (this project dir) |

---

## EMAIL RULES (CRITICAL — never break these)
- Sender name: **Alex** only
- Signature must be exactly:
  ```
  Alex
  Gray Horizons Enterprise
  https://grayhorizonsenterprise.com
  ```
- **No em dashes, no double hyphens, no dashes in subject lines**
- Subject pulled from outreach_queue.csv subject column
- Daily limit: 400 emails/day (`DAILY_EMAIL_LIMIT=400`)
- Sending: Gmail SMTP primary, SendGrid fallback

---

## NICHES + MESSAGE STYLE

Supported: `hoa`, `hvac`, `dental`, `plumbing`, `contractor`, `landscaping`, `roofing`

**HOA template style (ALL templates must follow this):**
- Assume the problem exists — don't ask if they have it
- State what we fixed / built
- End with a direct call to action: "I can show you exactly how we set it up this week"
- No "curious", no "happy to", no open-ended questions
- No sign-off URL in the body (dashboard appends it automatically)

---

## DASHBOARD ROUTES

| Route | What it does |
|-------|-------------|
| `/` | Pending queue — green = approve, red = skip |
| `/sent` | Sent log — Social button routes non-responders |
| `/social` | Social Pipeline stage tracker |
| `/send-batch` | POST — fires background batch send (400/day) |
| `/upload-queue` | Drag-drop CSV upload to load leads into Railway |
| `/run/<script>` | POST — run pipeline scripts |

---

## RAILWAY DEPLOYMENT
- Service: `ghe-dashboard`
- Start: `python approval_dashboard.py`
- Env vars: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `SENDGRID_API_KEY`, `GOOGLE_PLACES_API_KEY`, `PEXELS_API_KEY`, `SENDER_NAME=Alex`, `DAILY_EMAIL_LIMIT=400`
- **CSVs are gitignored** — always upload outreach_queue.csv manually via /upload-queue after regenerating locally

---

## GIT STATE (as of 2026-05-04)
- Branch: `main`
- Last commit: `ed9be76` — Update HOA outreach templates to closing-oriented messaging
- .gitignore: `*.csv`, `*.mp4`, `output/`, `clips/`, `__pycache__/`

---

## CURRENT STATUS (from dashboard screenshot 2026-05-04)
- 6,918 total leads in Railway
- 6,338 pending, scraper actively running
- Niche filters live: All Niches / HOA / HVAC / Dental / Plumbing / Contractor / Roofing
- Buttons live: Send 400 Now / Upload Leads / View Sent / Resend Failed / Scraping

---

## WHAT TO PICK UP NEXT
1. Monitor daily sends — confirm 400 going out daily
2. Track replies — Social Pipeline for warm leads
3. Scale video pipeline — render clips, post daily, drive inbound
4. Update remaining niche templates (HVAC, Dental, etc.) to closing-oriented style matching HOA
5. Add Landscaping niche filter button to dashboard (missing from niche bar)

---

**Read `CONTEXT.md` and `approval_dashboard.py` for full technical detail before making any changes.**
