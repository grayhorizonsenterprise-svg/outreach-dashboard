# Gray Horizons Enterprise — System Context
**Date:** 2026-05-04 | **Project dir:** `C:\Users\curti\Downloads\First Agentic Workflows`  
**Railway app:** `ghe-dashboard` | **GitHub:** `grayhorizonsenterprise-svg/outreach-dashboard`  
**Owner email:** grayhorizonsenterprise@gmail.com

---

## SYSTEM OVERVIEW

Two revenue systems wired together:
1. **Email Outreach** — 6,462 leads queued, send 400/day via Flask dashboard on Railway
2. **Social Pipeline** — comment → reply → demo → close, tracked in dashboard Social tab

Both managed from `approval_dashboard.py` (Railway-deployed Flask app).

---

## KEY FILES

| File | Purpose |
|------|---------|
| `approval_dashboard.py` | Main Flask app — Railway deployed, all routes/logic |
| `outreach_generator.py` | Builds outreach_queue.csv from prospects_raw.csv |
| `prospect_qualifier.py` | Filters new Maps leads (protects rows with emails) |
| `maps_scraper.py` | Google Maps Places API — 100 cities × 7 niches = 18k prospects |
| `outreach_queue.csv` | 6,462 pending emails (NOT in git — upload via /upload-queue) |
| `prospects_raw.csv` | 18,174 raw prospects, 7,235 with emails (NOT in git) |
| `sent_log.csv` | Log of all sent emails with timestamps (NOT in git) |
| `social_pipeline.csv` | Social prospects + stages (NOT in git) |
| `viral_system.py` | Consolidated clip downloader + renderer (MoviePy) |
| `auto_render.bat` | ffmpeg batch renderer — 3-text overlay, 1080x1920 |
| `run_pipeline.bat` | Entry point: viral_system.py → metadata_engine.py → auto_render.bat |
| `comment_generator.py` | 100 TikTok/YouTube outreach comments → comments_today.txt |
| `response_scripts.txt` | 4-stage DM conversion: comment→demo→close |
| `metadata_engine.py` | Generates title/description/tags for clips |

**CSVs are gitignored** (`*.csv` in .gitignore) — Railway never gets them via git. Upload manually.

---

## DASHBOARD ROUTES (approval_dashboard.py)

| Route | Function |
|-------|----------|
| `/` | Pending queue — approve/skip emails |
| `/sent` | Sent log — Social button here to route non-responders |
| `/social` | Social Pipeline tab — prospect stage tracker |
| `/send-batch` | POST — starts background thread, sends up to 400 emails/day |
| `/upload-queue` | GET/POST — drag-drop CSV upload, merges into queue |
| `/social/add` | POST — add prospect to social pipeline |
| `/social/advance/<sid>` | POST — advance stage |
| `/social/kill/<sid>` | POST — mark dead |
| `/social/from-email/<idx>` | POST — route pending email prospect to social |
| `/social/from-sent` | POST — route sent email to social (used by Sent log) |
| `/run/<script>` | POST — run pipeline scripts |

---

## EMAIL SYSTEM

- **Limit:** `DAILY_EMAIL_LIMIT = 400` (env var or hardcoded default)
- **Sender:** Alex / Gray Horizons Enterprise
- **Signature format:**
  ```
  Alex
  Gray Horizons Enterprise
  https://grayhorizonsenterprise.com  (clickable link)
  ```
- **No em dashes, no hyphens in subjects**
- Subject pulled from `outreach_queue.csv` subject column
- SMTP: Gmail (grayhorizonsenterprise@gmail.com) or SendGrid fallback
- `_build_html_body()` strips old sigs before appending correct footer
- `count_sent_today()` reads sent_log.csv to enforce daily limit
- `run_batch_send()` background thread — 1.5s delay between sends

---

## LEAD DATA

- **prospects_raw.csv:** 18,174 rows, 7,235 with emails
- **outreach_queue.csv:** 6,462 pending + 51 previously sent/skipped preserved
- **Breakdown:** HOA 1,254 | Contractor 1,249 | Dental 970 | Roofing 875 | HVAC 903 | Plumbing 661 | Landscaping 550
- **Source:** maps_scraper.py — Google Maps Places API, 100 cities × 7 niches

---

## NICHES SUPPORTED

`hoa`, `hvac`, `dental`, `plumbing`, `contractor`, `landscaping`, `roofing`

Alternate spellings mapped in outreach_generator.py:
- landscape/lawn → landscaping
- roof/roofer → roofing  
- electric/electrician → contractor

---

## HOA TEMPLATES (closing-oriented, no questions, assumes problem)

All 6 HOA templates follow this formula:
- Open with "Hey, this is Alex with Gray Horizons" or "Hey, this is Alex"
- State the specific problem HOA teams face (violations lost between report and resolution)
- State "We fixed that / We built a system that..."
- Close with direct path to action: "I can show you exactly how we set it up this week"
- No "curious", no "happy to", no open-ended questions

---

## VIDEO PIPELINE

**Clip path:** `clips/raw/` → `clips/output/` → `clips/posted/`

**run_pipeline.bat flow:**
1. `python viral_system.py` — download + score clips from Pexels
2. `python metadata_engine.py` — generate titles/descriptions
3. `call auto_render.bat` — ffmpeg render with 3-text overlay

**auto_render.bat overlay:**
- TOP (y=200): "GET MORE CUSTOMERS" — white, size 72
- MIDDLE (y=900): "Most businesses get ignored online" — white, size 58
- BOTTOM (y=1500): "We fix that" — yellow, size 64

---

## SOCIAL PIPELINE STAGES

`commented` → `replied` → `demo_sent` → `closed` → `dead`

**Wiring to email:**
- Adding social prospect with email → auto-queues in outreach_queue.csv
- Sent log has "Social" button → routes email non-responders to social pipeline

---

## RAILWAY DEPLOYMENT

- **Service:** ghe-dashboard
- **Start command:** `python approval_dashboard.py`
- **Root dir:** `/` (repo root)
- **Env vars needed:** `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `SENDGRID_API_KEY`, `GOOGLE_PLACES_API_KEY`, `PEXELS_API_KEY`, `SENDER_NAME=Alex`, `DAILY_EMAIL_LIMIT=400`
- **CSVs NOT synced via git** — use /upload-queue to push local outreach_queue.csv to Railway

---

## KNOWN ISSUES / PENDING

1. **Upload leads to Railway:** Local has 6,462 leads. Railway still has 632 (old). Go to Railway URL → /upload-queue → drag outreach_queue.csv
2. **prospect_qualifier.py** runs daily — fixed to protect rows with emails from being filtered out
3. **outreach_queue.csv** regenerated with new HOA templates — needs upload to Railway
4. **CSVs gitignored** — any time leads are regenerated locally, must re-upload to Railway

---

## GIT STATE

```
Branch: main
Remote: https://github.com/grayhorizonsenterprise-svg/outreach-dashboard.git
Last commit: ed9be76 — Update HOA outreach templates to closing-oriented messaging
```

**.gitignore includes:** `*.csv`, `*.mp4`, `output/`, `clips/`, `__pycache__/`

---

## HOW TO START NEXT SESSION

Drop this file as context. Key questions to ask:
- Did you upload outreach_queue.csv to Railway via /upload-queue?
- Are emails sending at 400/day from the Railway dashboard?
- Do you need more niche message templates updated?
- Video pipeline status — any clips rendered and ready to post?
