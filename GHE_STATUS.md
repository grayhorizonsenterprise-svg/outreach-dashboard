# Gray Horizons Enterprise — System Status & Handoff

## What This Is
Fully automated lead generation + outreach + content system targeting $50K/month.
Runs on Railway (cloud) + Windows Task Scheduler (local 6am daily sync).

---

## Live Revenue Engines (15 total)

| # | Engine | Price | Script |
|---|--------|-------|--------|
| 1 | AI System (lead gen + outreach) | $997 one-time | `sync_to_railway.py` |
| 2 | Signals newsletter | $49/month | `signals_engine.py` |
| 3 | Grant Writing | $1,500/client | `grant_outreach_generator.py` |
| 4 | GHL CRM | $297/month | `ghl_outreach.py` |
| 5 | TradingView Indicators | $19-39/month | `tradingview_engine.py` |
| 6 | Video Pipeline (YouTube/TikTok) | Ad revenue | `video_pipeline.py` |
| 7 | Missed Call Text-Back | $97/month | `missed_call_textback.py` |
| 8 | Review Generation | $147/month | `review_generation.py` |
| 9 | GBP Optimization | $197/month | `gbp_optimizer.py` |
| 10 | AI Chatbot | $97/month | `ai_chatbot_outreach.py` |
| 11 | AI Voice Receptionist | $197/month | `ai_voice_receptionist.py` |
| 12 | Lead Reactivation | $497 one-time | `lead_reactivation.py` |
| 13 | Social Media Mgmt | $297/month | `social_media_mgmt.py` |
| 14 | Website Audit | $297+$97/month | `website_audit.py` |
| 15 | SMS Marketing | $147/month | `sms_marketing.py` |

Plus: `lead_scanner.py` (continuous DDG scanner feeding all queues), `twitter_poster.py` (3 posts/day).

---

## Shadow Clans Content Engine
- File: `shadow_clans_engine.py`
- Original dark fantasy IP: Wolf Clan (RAIZEN), Raven Order (KURO), Gorilla Titans (VARN), The Hollow Gate
- Generates: Full episodes + YouTube Shorts → saves to `shadow_clans_output/ready_to_upload/`
- **No auto-upload** — user reviews and uploads manually
- Needs: `ANTHROPIC_API_KEY` (required), `STABILITY_API_KEY` (optional, for AI frames)
- Visual style: 70% cinematic realism / 20% dark fantasy / 10% retro anime flicker
- **Sample generator**: `generate_sample.py` — creates Episode 1 to Desktop using ffmpeg only (no API keys needed). Run this first to approve the style before enabling full automation.

---

## Railway Deployment
- Dashboard URL: `https://ghe-dashboard-production.up.railway.app`
- GitHub repo: `grayhorizonsenterprise-svg/outreach-dashboard`
- Auto-deploys on git push to main

### Railway Variables (all set as of 2026-05-12)
```
DATABASE_URL          ✓ (PostgreSQL)
HUNTER_API_KEY        ✓
LINKEDIN_LI_AT        ✓
PYTHONUNBUFFERED      ✓
SENDER_APP_PASSWORD   ✓
SENDER_EMAIL          ✓
SENDER_NAME           ✓
SENDGRID_API_KEY      ✓
STRIPE_PAYMENT_LINK   ✓
STRIPE_SIGNALS_LINK   ✓
TWITTER_API_KEY       ✓ (just added)
TWITTER_API_SECRET    ✓ (just added)
TWITTER_ACCESS_TOKEN  ✓ (just added)
TWITTER_ACCESS_SECRET ✓ (just added)
```
### Still needs to be added to Railway
- `CALENDLY_URL` — for booking links in outreach emails
- `STABILITY_API_KEY` — optional, for AI-generated video frames
- `ANTHROPIC_API_KEY` — ✓ already set in Railway

---

## Scrapers (Lead Sources)
All 6 scrapers now use DuckDuckGo (DDGS) — no more 403 blocks on Railway cloud IPs:
- `yellowpages_scraper.py`
- `superpages_scraper.py`
- `manta_scraper.py` ← fixed this session
- `hotfrog_scraper.py` ← fixed this session
- `chamberofcommerce_scraper.py` ← fixed this session
- `bark_scraper.py` ← fixed this session

Current lead count: **3,699 total** in `prospects_raw.csv`

---

## Known Issues / Blockers

### 1. Git Push Blocked (CRITICAL)
Push to GitHub/Railway is blocked by large files in git history:
- `Antigravity.exe` (208MB) — added in commit `ad927fc`, not yet removed from history
- `viral_clips/raw_clips/36383997_score2.mp4` (108MB) — in a prior commit

**Fix needed**: Run `git filter-branch` to strip these from the 9 unpushed commits, then push.
Command:
```bash
git filter-branch --index-filter \
  'git rm --cached --ignore-unmatch "Antigravity.exe" && git rm -r --cached --ignore-unmatch "viral_clips/"' \
  --prune-empty -- origin/main..HEAD
git push origin main
```
Until this is fixed, new code changes are NOT reaching Railway.

### 2. prospect_enricher.py NaN error (FIXED locally, not pushed)
Fixed: `pd.read_csv(INPUT_FILE, dtype=str).fillna("")` — prevents float64 cast error on empty columns.
File: `prospect_enricher.py` line 248. Committed locally as `4dd2c36` but not pushed yet (blocked by #1).

### 3. Shadow Clans — No content generated yet
The `shadow_clans_output/` directory doesn't exist. Run `generate_sample.py` first to review style.
`ANTHROPIC_API_KEY` is already in Railway — once git push is fixed, full automation is ready.

### 4. Video pipeline clips not processed
`viral_clips/top_clips/` has 6 score-5 clips ready. `viral_clips/raw_clips/` has 46 clips.
`viral_clips/READY_TO_UPLOAD/` is empty — `viral_engine.py` needs to be run to add captions and trim.

### 5. Google Cloud billing suspended
$860.74 Maps API bill. $643.41 credited. ~$217 still outstanding.
Do NOT pay — request full credit from Google support. Maps scraper was already removed.

---

## Pending Actions (in priority order)

1. **Fix git push** — strip large files from history, push 9 stacked commits to Railway
2. **Run `generate_sample.py`** — generate Desktop sample video for Shadow Clans review
3. **Add CALENDLY_URL to Railway** — needed for outreach booking links
5. **Run `viral_engine.py`** — processes raw clips → adds captions → READY_TO_UPLOAD
6. **Task Scheduler** — add `lead_scanner.py` as separate 4-hour job alongside 6am full pipeline
7. **Beehiiv** — send email blast offering free AI audit + Calendly link (fast revenue path)
8. **TradingView** — upgrade to Essential ($15/mo), publish 3 indicators
9. **Google Cloud** — follow up on remaining $217 credit request
10. **Twitter** — keys are in Railway; first auto-post fires next pipeline run

---

## Local Setup
- Working directory: `C:\Users\curti\Downloads\First Agentic Workflows`
- Python runs locally via Windows Task Scheduler (6am daily)
- Main orchestrator: `sync_to_railway.py`
- `.env` file has: `SENDER_EMAIL`, `SENDER_APP_PASSWORD`, `SENDGRID_API_KEY`
- ffmpeg is installed (v8.1)
- tweepy added to `requirements.txt` (v4.14.0+)
