# DROP-IN CONTEXT PROMPT — Gray Horizons Enterprise
## Paste this entire block at the start of the next Claude Code session

---

You are continuing an active build for Gray Horizons Enterprise. Here is the full system state as of 2026-06-13.

---

## WHO I AM
- Owner: Curtis, grayhorizonsenterprise@gmail.com
- Brand: Gray Horizons Enterprise — AI-powered outreach and automation for local service businesses
- Sender name in all emails: **Alex** (never "Gray", never anything else)
- Website: https://grayhorizonsenterprise.com
- GitHub: grayhorizonsenterprise
- Project dir: `C:\Users\curti\Downloads\First Agentic Workflows`

---

## WHAT IS BUILT

### 1. Email Outreach System (PRIMARY REVENUE)
- Flask dashboard deployed on Railway (`approval_dashboard.py`)
- Leads stored in `outreach_queue.csv` (gitignored — upload manually via /upload-queue)
- Raw prospects in `prospects_raw.csv`
- Daily email limit currently set to **50/day** (conservative — rebuilding SendGrid reputation after 26.7% bounce rate)
- Sending: SendGrid primary, Brevo fallback, Gmail SMTP tertiary
- **Only 16 verified contacts in the real pipeline** — never cite inflated CSV numbers

### 2. Outbound Calling System (Vapi)
- Vapi AI calls leads automatically — capped at **5 calls/day**
- `CALLS_PAUSED` env var halts all outbound calls when set (currently paused until Telnyx SMS is ready)
- Call dedup via `call_log.json`
- Webhook: `/vapi-webhook` and `/vapi-collect` routes
- Owner email fires on every call completion
- Route: `/trigger-calls`, `/calls` dashboard tab

### 3. SMS System (Telnyx)
- **Switched from Twilio to Telnyx** — Twilio A2P 10DLC stuck in review
- Env vars needed: `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER`
- SMS fires as part of lead follow-up flow

### 4. Social / Twitter System
- Twitter auto-posts 3x/day via `_twitter_scheduler`
- Posts tracked in `twitter_posted.json` (5 logged so far)
- LinkedIn auto-posts 1x/day
- Posts tracked in `linkedin_posted.json`
- Routes: `/test-twitter`, `/twitter-post-now`, `/post-twitter-comment`
- **Grammar rule: capitalize I, fix grammar on every post before publishing**

### 5. Shadow Clans Video Pipeline
- Nightly episode generation via `_shadow_clans_nightly`
- Output: `shadow_clans_output/frames/EP001–EP013/` and `image_prompts/`
- Episode log: `shadow_clans_output/episode_log.json`
- Currently at EP013

### 6. Background Engine Schedulers
- **Only 2 engines run on boot:** `_twitter_scheduler` and `_shadow_clans_nightly`
- 14 other engines exist in code but are **disabled at startup** — they were crashing the app (no creds, dead feeds, high CPU)
- Disabled: signals, grant pipeline, Gmail monitor, Reddit monitor, real estate, medspa, insurance, ecommerce, restaurant, gym, mortgage, followup, auto blast, Vapi followup, Twitter engage, Upwork scout

### 7. Social Pipeline
- Tracked in dashboard Social Pipeline tab
- Stages: `commented → replied → demo_sent → closed → dead`
- Route: `/social`, `/social/from-sent`, `/social/add`

### 8. Upwork Scout
- `upwork_scout.py` — scrapes Upwork job postings
- Route: `/upwork`, `/upwork-draft`

---

## KEY FILES

| File | Purpose |
|------|---------|
| `approval_dashboard.py` | Main Flask app — Railway deployed (4300+ lines) |
| `outreach_queue.csv` | Lead queue — gitignored, upload manually |
| `prospects_raw.csv` | Raw scraped leads |
| `upwork_scout.py` | Upwork job scraper |
| `update_vapi_inbound.py` | Vapi inbound call config updater |
| `run_log.txt` | Engine run history |
| `twitter_posted.json` | Twitter post dedup log |
| `linkedin_posted.json` | LinkedIn post dedup log |
| `call_log.json` | Vapi call dedup log |
| `shadow_clans_output/` | Shadow Clans episode frames + prompts |
| `DROP_IN_PROMPT.md` | This file — update at end of every session |
| `performance.json` | Performance tracking |

---

## EMAIL RULES (CRITICAL — never break these)
- Sender name: **Alex** only
- Signature must be exactly:
  ```
  Alex
  Gray Horizons Enterprise
  grayhorizonsenterprise.com
  ```
- **No em dashes, no double hyphens, no dashes in subject lines**
- **No colons in subject lines**
- Subject pulled from outreach_queue.csv subject column
- Daily limit: 50 emails/day (rebuilding reputation — do NOT raise without checking bounce rate)

---

## POST / SOCIAL GRAMMAR RULES (CRITICAL)
- Always capitalize **I**
- Fix all grammar before posting to LinkedIn, X, Whop, Beehiiv, or Gumroad
- No em dashes anywhere in posts

---

## DASHBOARD ROUTES (key ones)

| Route | What it does |
|-------|-------------|
| `/` | Pending queue — approve/skip leads |
| `/sent` | Sent log |
| `/social` | Social Pipeline stage tracker |
| `/send-batch` | Fire background batch send |
| `/upload-queue` | Drag-drop CSV upload |
| `/calls` | Outbound call dashboard |
| `/trigger-calls` | POST — fire Vapi calls (capped 5/day) |
| `/vapi-webhook` | Vapi call result webhook |
| `/upwork` | Upwork job board |
| `/signals` | Signals dashboard |
| `/status` | System health check |
| `/performance` | Performance tracking |

---

## RAILWAY DEPLOYMENT
- Service: `ghe-dashboard`
- Start: `python approval_dashboard.py`
- Key env vars:
  - `GMAIL_USER`, `SENDER_APP_PASSWORD`
  - `SENDGRID_API_KEY`
  - `BREVO_API_KEY`
  - `SENDER_NAME=Alex`
  - `SENDER_EMAIL`
  - `DAILY_EMAIL_LIMIT=50`
  - `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER`
  - `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`
  - `LINKEDIN_LI_AT`, `LINKEDIN_CSRF_TOKEN`
  - `CALLS_PAUSED=true` (set to disable all outbound calls)
  - `DASHBOARD_URL=https://ghe-dashboard-production.up.railway.app`
  - `DATABASE_URL` (Postgres on Railway)
- **CSVs are gitignored** — always upload outreach_queue.csv manually via /upload-queue

---

## GIT STATE (as of 2026-06-13)
- Branch: `main`
- Last commit: `3920fc9` — Switch SMS provider from Twilio to Telnyx
- Recent commits:
  - `3920fc9` Switch SMS provider from Twilio to Telnyx
  - `debe1e5` Rewrite X posts for algorithm reach + fix 280-char truncation bug
  - `61a3408` Add CALLS_PAUSED env var to halt outbound calls until Telnyx SMS is ready
  - `1e9b534` Wire Vapi webhook URL into outbound caller — owner email fires on every call
  - `27fc185` Strip 16 broken background engines from startup — keep only Twitter + Shadow Clans

---

## CURRENT STATUS (2026-06-13)
- Outbound calling: **PAUSED** (CALLS_PAUSED=true) — waiting for Telnyx SMS to be live
- SMS: Telnyx configured in code, needs `TELNYX_API_KEY` + `TELNYX_PHONE_NUMBER` in Railway
- Twitter: posting 3x/day, 5 posts logged
- Shadow Clans: generating through EP013
- Email: 50/day limit, SendGrid reputation rebuild in progress
- 14 background engines disabled at startup — do not re-enable without fixing root cause first

---

## WHAT TO PICK UP NEXT
1. Set `TELNYX_API_KEY` and `TELNYX_PHONE_NUMBER` in Railway to activate SMS
2. Once SMS is live, remove `CALLS_PAUSED` to re-enable Vapi outbound calls
3. Monitor Twitter/LinkedIn daily posts — confirm automation is firing
4. Check SendGrid bounce rate before raising email limit above 50/day
5. Update this file (DROP_IN_PROMPT.md) at the end of every session

---

**Read `approval_dashboard.py` for full technical detail before making any changes.**
