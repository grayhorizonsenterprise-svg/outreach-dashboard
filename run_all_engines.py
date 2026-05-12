"""
run_all_engines.py — Gray Horizons Enterprise
Master runner for ALL revenue engines. Fully standalone — zero dashboard dependency.
Each engine scrapes its own leads, sends its own emails, tracks its own queue.

Schedule via Windows Task Scheduler: run every 6 hours
Or Railway: add to Procfile as a worker

Revenue engines included:
  Signals        $49/month   — traders, bettors, investors (individuals)
  AI System      $997        — local businesses (HVAC, dental, HOA, etc.)
  Grant Writing  $1,500      — nonprofits
  GHL CRM        $297/month  — agencies and local businesses
  Missed Call    $97/month   — local service businesses
  Review Gen     $147/month  — local businesses with Google presence
  GBP Optimizer  $197/month  — local businesses on Google Maps
  AI Chatbot     $97/month   — businesses with websites
  Voice AI       $197/month  — service businesses taking calls
  Lead Reactiv.  $497        — businesses with old lead lists
  Social Media   $297/month  — businesses needing content
  Website Audit  $297+$97    — businesses with outdated sites
  SMS Marketing  $147/month  — local businesses with customer lists
"""

import subprocess
import sys
import os
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = os.path.dirname(os.path.abspath(__file__))

def run(label, script, timeout=1200):
    path = os.path.join(DIR, script)
    if not os.path.exists(path):
        print(f"  [SKIP] {script} not found")
        return
    print(f"\n[{label}]")
    try:
        subprocess.run([sys.executable, "-u", path], timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {label} took too long — continuing")
    except Exception as e:
        print(f"  [ERROR] {e}")


# ── PHASE 1: SCRAPE LEADS ─────────────────────────────────────────────────────
# Each scraper feeds its own queue independently

print("=" * 60)
print("  PHASE 1 — SCRAPING LEADS")
print("=" * 60)

run("Signals: mass scrape traders/bettors/investors", "signals_mass_scraper.py", 900)
run("Local biz: YellowPages",                        "yellowpages_scraper.py",   600)
run("Local biz: Superpages",                         "superpages_scraper.py",    600)
run("Local biz: Manta",                              "manta_scraper.py",         600)
run("Local biz: Hotfrog",                            "hotfrog_scraper.py",       600)
run("Local biz: Chamber of Commerce",                "chamberofcommerce_scraper.py", 600)
run("Local biz: Bark",                               "bark_scraper.py",          600)
run("Local biz: Yelp",                               "yelp_scraper.py",          600)
run("Nonprofits: grant writing leads",               "nonprofit_scraper.py",     600)
run("Continuous multi-source scan",                  "lead_scanner.py",          600)

# ── PHASE 2: ENRICH + QUALIFY ─────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PHASE 2 — ENRICH + QUALIFY")
print("=" * 60)

run("Enrich emails + phones",  "prospect_enricher.py",  1200)
run("Qualify leads",           "prospect_qualifier.py",  600)
run("Hunter.io enrichment",    "hunter_scraper.py",      600)

# ── PHASE 3: GENERATE OUTREACH ────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PHASE 3 — GENERATE OUTREACH")
print("=" * 60)

run("Generate local biz outreach",   "outreach_generator.py",       300)
run("Generate grant outreach",        "grant_outreach_generator.py", 300)

# ── PHASE 4: SEND ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PHASE 4 — SEND OUTREACH")
print("=" * 60)

run("Send: Signals (traders/bettors)",  "signals_sender.py",          600)
run("Send: Local biz outreach",         "outreach_sender.py",         600)
run("Send: Grant writing outreach",     "grant_blast.py",             600)
run("Send: GHL agency outreach",        "ghl_outreach.py",            600)
run("Send: Missed call pitch",          "missed_call_textback.py",    600)
run("Send: Review generation pitch",   "review_generation.py",       600)
run("Send: GBP optimization pitch",    "gbp_optimizer.py",           600)
run("Send: AI chatbot pitch",          "ai_chatbot_outreach.py",     600)
run("Send: Voice AI pitch",            "ai_voice_receptionist.py",   600)
run("Send: Lead reactivation pitch",   "lead_reactivation.py",       600)
run("Send: Social media mgmt pitch",   "social_media_mgmt.py",       600)
run("Send: Website audit pitch",       "website_audit.py",           600)
run("Send: SMS marketing pitch",       "sms_marketing.py",           600)

# ── PHASE 5: FOLLOW-UPS ───────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PHASE 5 — FOLLOW-UPS")
print("=" * 60)

run("Follow-up: local biz",      "followup_sender.py",   600)
run("Follow-up: signals",        "signals_engine.py",    600)
run("Follow-up: grant writing",  "signals_engine.py",    600)

# ── PHASE 6: CONTENT ──────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PHASE 6 — CONTENT + SOCIAL")
print("=" * 60)

run("Twitter auto-posts (3/day)",    "twitter_poster.py",      300)
run("Shadow Clans episode gen",      "shadow_clans_engine.py", 1200)
run("Video pipeline",                "video_pipeline.py",      900)

print("\n" + "=" * 60)
print("  ALL ENGINES COMPLETE")
print("=" * 60)
