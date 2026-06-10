# Gray Horizons Enterprise — Master System README
**Goal:** $240K NET by November 30, 2026
**Owner:** Curtis Gardner | grayhorizonsenterprise@gmail.com
**Dashboard:** https://ghe-dashboard-production.up.railway.app (Railway)
**Website:** https://grayhorizonsenterprise.com
**Calendly:** https://calendly.com/grayhorizonsenterprise/30min
**Voice Agent:** +1 (909) 927-6310 (Vapi — Jordan)

---

## CURRENT STATE (as of 2026-06-09)

| System | Status | Notes |
|---|---|---|
| Email outreach | BROKEN — no scheduler | 42 sent, 933 pending, needs cron |
| LinkedIn poster | RUNNING | Token valid ~Aug 6 2026 |
| Twitter poster | RUNNING | 3 posts/day |
| Upwork scout | RUNNING | Scans every 2 hours, saves to upwork_opportunities.json |
| Vapi voice agent | LIVE | Jordan at (909)927-6310 |
| Auto-proposal | LIVE | Fires on Calendly webhook, sends Stripe link |
| SendGrid | LIVE | 496K credits/month, domain authenticated |
| Railway deploy | LIVE | Auto-deploys from main branch push |

---

## REVENUE STREAMS + PRICING

| Offer | Price | Stripe Link Env Var |
|---|---|---|
| AI System Build (HVAC/dental/etc) | $997 one-time | STRIPE_PAYMENT_LINK |
| Edge Engine Trading Signals | $49/month | STRIPE_SIGNALS_LINK |
| Grant Writing | $1,500 | STRIPE_GRANT_LINK |
| Retainer (managed service) | $2,500 setup + $750/mo | (no link yet) |

---

## EVERY SYSTEM — WHAT IT DOES

### OUTREACH PIPELINE

**`outreach_generator.py`**
Reads `prospects_raw.csv`, generates personalized cold emails per niche (HOA, HVAC, dental, roofing, etc.), writes to `outreach_queue.csv`.

**`outreach_sender.py`**
Reads `outreach_queue.csv`, sends pending rows via SendGrid (primary) > Gmail SMTP (fallback). Marks rows `sent`. Sends 50/day by default.

**`outreach_queue.csv`**
Current: 42 sent, 6 skipped, 933 pending. 2,322 total prospects in `prospects_raw.csv`.

**`run_all_engines.py`**
Master runner. Runs all scrapers > enrichment > outreach generation > email send > social posts. Run this to trigger a full cycle. NOT on a scheduler currently.

**`followup_engine.py` / `followup_sender.py`**
Sends follow-up emails to prospects who opened but did not reply. Depends on SendGrid open tracking.

**`grant_outreach_generator.py` / `grant_blast.py`**
Same pipeline but for nonprofits. Offer: $1,500 grant writing.

### LEAD SCRAPERS (feed `prospects_raw.csv`)

**`yellowpages_scraper.py`** — YellowPages local business scraper
**`superpages_scraper.py`** — Superpages scraper
**`manta_scraper.py`** — Manta business directory
**`hotfrog_scraper.py`** — Hotfrog directory
**`chamberofcommerce_scraper.py`** — Chamber of Commerce directory
**`bark_scraper.py`** — Bark.com service providers
**`yelp_scraper.py`** — Yelp local business scraper
**`gmaps_scraper.py`** — Google Maps scraper
**`nonprofit_scraper.py`** / **`nonprofitscraper_propublica.py`** — Nonprofit leads for grant writing
**`lead_scanner.py`** — Multi-source continuous scanner
**`niche_lead_sourcer.py`** — Targets specific niches (HVAC, dental, roofing, HOA)
**`signals_mass_scraper.py`** — Scrapes trader/investor emails for Edge Engine product

### ENRICHMENT

**`prospect_enricher.py`** — Adds emails + phones to prospects via Hunter.io
**`prospect_qualifier.py`** — Scores and filters leads by quality
**`email_verifier.py`** — Validates email addresses before send
**`phone_finder.py`** — Finds phone numbers for prospects
**`hunter_scraper.py`** — Hunter.io email finder integration

### SOCIAL / CONTENT

**`twitter_poster.py`**
Posts 3 tweets/day automatically. Uses Twitter OAuth 1.0a. Content: GHL tips, AI services, Edge Engine signals. Uses `STRIPE_SIGNALS_LINK` env var. Tracks posted in `twitter_posted.json`.

**`linkedin_poster.py`**
Posts 1 LinkedIn post/day. Uses `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_PERSON_ID`. Token expires ~Aug 6 2026. Content pools: GHL, AI services, Edge Engine. Uses `STRIPE_SIGNALS_LINK`. Tracks posted in `linkedin_posted.json`.

**`beehiiv_broadcaster.py`** — Newsletter broadcast via Beehiiv API
**`comment_generator.py`** — Generates engagement comments for social
**`stocktwits_poster.py`** — Posts to StockTwits for signals product

### VAPI VOICE AGENT

**`update_vapi_inbound.py`**
Updates Vapi inbound agent config. Jordan answers at (909)927-6310. Qualifies callers, books to Calendly.

**`vapi_agent.py`** / **`vapi_setup.py`**
Vapi configuration and webhook handling. Webhook fires after call — triggers SMS + logs call data.

**`missed_call_textback.py`**
When Jordan misses a call or call ends, fires SMS via Twilio with Calendly link.

### AUTO-PROPOSAL

**`auto_proposal.py`**
Listens on `/calendly-webhook`. When someone books a call, instantly sends a proposal email with the Stripe payment link. Uses `STRIPE_PAYMENT_LINK`. This is the money button — books = proposal sent automatically.

### DASHBOARD

**`approval_dashboard.py`**
Main Flask dashboard at Railway. Tabs:
- Outreach — email queue, send controls
- Social — LinkedIn/Twitter post history
- Grants — grant outreach pipeline
- Twitter — tweet history
- Upwork — scouted jobs, copy proposals, apply links

Routes:
- `/` — main dashboard
- `/approve` — approve/reject outreach emails
- `/calendly-webhook` — auto-proposal trigger
- `/vapi-webhook` — Vapi call data receiver
- `/calls` — call log view
- `/upwork-draft` — paste-job proposal drafter

### EDGE ENGINE (Trading Signals Product — $49/mo)

**`edge_engine/scan.py`** — Main signal scanner (RSI, volume, EMA)
**`edge_engine/signals.py`** — Signal generation logic
**`edge_engine/patterns.py`** — Chart pattern detection
**`edge_engine/scout.py`** — Market scouting
**`edge_engine/intelligence.py`** — Congress trades + dark pool tracking
**`edge_engine/notify.py`** — Alert delivery
**`signals_mailer.py`** / **`signals_sender.py`** / **`signals_blast.py`** — Email delivery for signals subscribers
**`signals_mass_scraper.py`** — Scrapes trader/investor emails for cold outreach

### GRANT AGENT

**`grant_agent/`** directory — Full grant discovery + proposal generation system
- `discovery/` — Finds grants via Grants.gov and RSS
- `scoring/scorer.py` — Scores grant fit
- `generation/generator.py` — Drafts grant proposals using Claude
- `automation/submitter.py` — Submission automation
- `api/routes.py` — Grant agent Flask API
- `watchdog.py` — Keeps grant agent alive

### NICHE OUTREACH ENGINES (specialty scripts)

**`ai_chatbot_outreach.py`** — Targets businesses needing AI chatbots ($97/mo)
**`ai_voice_receptionist.py`** — Targets businesses needing voice AI ($197/mo)
**`gbp_optimizer.py`** — Google Business Profile optimization outreach ($197/mo)
**`ghl_outreach.py`** — GoHighLevel CRM setup outreach ($297/mo)
**`lead_reactivation.py`** — Reactivate old lead lists for businesses ($497)
**`review_generation.py`** — Google review generation outreach ($147/mo)
**`sms_marketing.py`** — SMS marketing setup outreach ($147/mo)
**`social_media_mgmt.py`** — Social media management outreach ($297/mo)
**`website_audit.py`** — Website audit outreach ($297 + $97/mo)
**`missed_call_textback.py`** — Missed call text-back outreach ($97/mo)
**`medspa_engine.py`** — MedSpa niche outreach
**`insurance_engine.py`** — Insurance niche outreach
**`mortgage_engine.py`** — Mortgage niche outreach
**`realestate_engine.py`** — Real estate niche outreach
**`restaurant_engine.py`** — Restaurant niche outreach
**`gym_engine.py`** — Gym/fitness niche outreach

### UPWORK

**`upwork_scout.py`**
Scans Upwork RSS feed every 2 hours. Saves matched jobs to `upwork_opportunities.json`. Dashboard shows jobs with Copy Proposal buttons and Apply links.

**`upwork_alert.py`**
Sends alert when high-scoring Upwork job is found.

### CONTENT / MEDIA

**`shadow_clans_engine.py`** — Generates Shadow Clans episode content (video series)
**`video_pipeline.py`** — Video processing pipeline
**`viral_clip_fetcher.py`** — Finds viral clip sources
**`viral_engine.py`** — Viral content strategy engine
**`yt_analyzer.py`** — YouTube video analysis
**`yt_content_generator.py`** — YouTube content generation
**`video_intel.py`** — Video intelligence from transcripts
**`kdp_ebook_generator.py`** — KDP ebook generation (passive income)
**`generate_ep001.py`** / **`generate_sample.py`** — Episode generation scripts

### UTILITY

**`email_registry.py`** — Tracks all emails sent across all systems, prevents duplicates
**`performance_tracker.py`** — Tracks revenue metrics, open rates, replies
**`reddit_monitor.py`** — Monitors Reddit for business owners asking for help
**`linkedin_dm_drafter.py`** — Drafts LinkedIn DMs to connected prospects
**`linkedin_outreach.py`** — LinkedIn connection + DM outreach
**`gmail_reply_monitor.py`** — Monitors Gmail for replies from prospects
**`sync_to_railway.py`** — Syncs local files to Railway deployment

---

## ENV VARS — ALL REQUIRED

| Var | Purpose | Status |
|---|---|---|
| SENDGRID_API_KEY | Email sending | SET |
| LINKEDIN_ACCESS_TOKEN | LinkedIn posting | SET (expires ~Aug 6 2026) |
| LINKEDIN_PERSON_ID | LinkedIn posting | SET |
| TWITTER_API_KEY | Twitter OAuth | SET |
| TWITTER_API_SECRET | Twitter OAuth | SET |
| TWITTER_ACCESS_TOKEN | Twitter OAuth | SET |
| TWITTER_ACCESS_SECRET | Twitter OAuth | SET |
| VAPI_PRIVATE_KEY | Vapi voice agent | SET |
| TWILIO_ACCOUNT_SID | SMS sending | SET |
| TWILIO_AUTH_TOKEN | SMS sending | SET |
| TWILIO_FROM_NUMBER | SMS from number | SET |
| ANTHROPIC_API_KEY | Claude AI (proposals, grant gen) | SET |
| STRIPE_PAYMENT_LINK | AI System offer payment | SET |
| STRIPE_SIGNALS_LINK | Edge Engine signals payment | SET |
| STRIPE_GRANT_LINK | Grant writing payment | SET |
| SENDER_EMAIL | From email address | SET |
| SENDER_APP_PASSWORD | Gmail SMTP fallback | SET |

---

## CRITICAL BROKEN ITEMS (fix first)

1. **No email scheduler** — emails stopped at 42 sent. Need Windows Task Scheduler or Railway cron running daily.
2. **Upwork proposals manual** — Scout finds jobs but proposals must be submitted manually on Upwork. $2.14/proposal. Submit 10/day to jobs under 2 hours old.
3. **LinkedIn token expiry** — Token expires ~Aug 6 2026. Run `python linkedin_poster.py --auth` before that date.
4. **Reddit monitor not running** — `reddit_monitor.py` finds business owners asking for help in real time. Not scheduled.

---

## KEY DATA FILES

| File | Purpose |
|---|---|
| `outreach_queue.csv` | 981 rows: 42 sent, 6 skipped, 933 pending |
| `prospects_raw.csv` | 2,322 scraped local business leads |
| `upwork_opportunities.json` | Scouted Upwork jobs (refreshes every 2 hrs) |
| `twitter_posted.json` | Twitter post history (dedup) |
| `linkedin_posted.json` | LinkedIn post history (dedup) |
| `performance.json` | Revenue + outreach performance metrics |
| `video_analyses/` | 22 stored YouTube video transcripts + strategy extracts |

---

## HOW TO RESTART EVERYTHING

```bash
# Send today's email batch (50 emails)
python outreach_sender.py

# Run full cycle (scrape + generate + send + post)
python run_all_engines.py

# Re-authenticate LinkedIn (before Aug 6 2026)
python linkedin_poster.py --auth

# Check dashboard locally
python approval_dashboard.py
# then open http://localhost:5000
```

---

## RAILWAY DEPLOYMENT

- Repo auto-deploys on every `git push origin main`
- Dashboard live at: https://ghe-dashboard-production.up.railway.app
- Procfile controls what runs: `web: python approval_dashboard.py`
- All env vars above must be set in Railway dashboard Settings > Variables

---

*Last updated: 2026-06-09*
