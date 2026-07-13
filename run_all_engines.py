"""
run_all_engines.py — Gray Horizons Enterprise
Master runner — VERIFIED scripts only. No ghost scripts, no fake data.

Revenue focus:
  PRIMARY:  Autonomous Front Desk — $997 setup + $297/mo (HVAC, roofing, solar, dental, plumbing)
  SECONDARY: Gumroad products — trading indicators, guides ($12-$67)

Schedule: Windows Task Scheduler or Railway cron, every 6 hours.

CONTENT RULES (enforced here):
  - No fake client stories passed as real
  - No AI-generated "signals" with random data (sendgrid_blaster.py is BLOCKED)
  - Only real stats, real Vapi screenshots, real demo line calls as proof
  - LinkedIn: contractor/AI services content ONLY
  - Twitter/X: Edge Engine trading signals ONLY
"""

import subprocess
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = Path(os.path.dirname(os.path.abspath(__file__)))

NEVER_RUN = {
    "sendgrid_blaster.py",       # fake random investment signals — BLOCKED
    "signals_blast.py",          # one-time blast — would re-fire entire queue
    "send_hoa_outreach.py",      # HOA outreach — wrong target market
    "send_hoa_followup.py",      # HOA follow-up — wrong target market
    "demo_gardner_medical.py",   # reconfigures Vapi as Gardner Medical — NEVER RUN
    "send_gardner_quote.py",     # sends Gardner Medical emails — NEVER RUN
    "send_demo_and_gardner.py",  # Gardner Medical demo sender — NEVER RUN
    "setup_gardner_agent.py",    # rebuilds Gardner Medical Vapi agent — NEVER RUN
    "bland_caller.py",           # separate calling system — conflicts with outbound_caller.py
}

def run(label, script, timeout=600, args=None):
    if script in NEVER_RUN:
        print(f"  [BLOCKED] {script} is on the never-run list.")
        return
    path = DIR / script
    if not path.exists():
        print(f"  [SKIP] {script} not found")
        return
    cmd = [sys.executable, "-u", str(path)] + (args or [])
    print(f"  >> {label}")
    try:
        subprocess.run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {label}")
    except Exception as e:
        print(f"  [ERROR] {e}")


def _days_since_file(path: Path) -> float | None:
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds() / 86400


def _is_monday() -> bool:
    return datetime.now().weekday() == 0


now = datetime.now()
print("=" * 62)
print(f"  GHE ENGINES  —  {now.strftime('%Y-%m-%d %H:%M')}")
print("=" * 62)


# ── PHASE 1: LEAD SCRAPING ────────────────────────────────────────────────────
# Goal: fill hot_leads.csv and contractor_prospects.csv with real CA businesses.
# Only run scrapers once per 24 hours to avoid rate limits.

print("\n[PHASE 1] LEAD SCRAPING + INTELLIGENCE")

days_since_leads = _days_since_file(DIR / "contractor_queue.csv")
if days_since_leads is None or days_since_leads > 1.0:
    run("CSLB CA gov license board scraper (public records)", "contractor_license_scraper.py", 900)
else:
    print(f"  [SKIP] contractor_queue.csv updated {days_since_leads:.1f}d ago — skipping CSLB scrape")

# Prospect intelligence: multi-source scoring (BBB, Angi, Google)
# Runs once every 3 days to build hot_prospects_scored.csv
days_since_hot = _days_since_file(DIR / "hot_prospects_scored.csv")
if days_since_hot is None or days_since_hot > 3.0:
    run("Multi-source prospect intelligence + scoring", "prospect_intelligence.py", 1800)
else:
    print(f"  [SKIP] hot_prospects_scored.csv updated {days_since_hot:.1f}d ago — skipping intel scrape")

# Enrich existing contractor_prospects.csv with phone numbers from their websites
days_since_enrich = _days_since_file(DIR / "contractor_prospects.csv")
if days_since_enrich is None or days_since_enrich > 1.0:
    run("Extract phones from contractor websites", "scrape_phones_from_websites.py", 600)
else:
    print(f"  [SKIP] contractor_prospects.csv enriched {days_since_enrich:.1f}d ago")


# ── PHASE 2: OUTREACH — PRIMARY REVENUE DRIVER ───────────────────────────────
# send_contractor_outreach.py: only sends to status=pending rows — safe to run every cycle
# send_followup_outreach.py:   checks date column, only fires when 7+ days since last email

print("\n[PHASE 2] OUTREACH")

run("Contractor cold outreach (pending only)",        "send_contractor_outreach.py",  300)
run("Outreach queue batch sender (contractor leads)",  "outreach_sender.py",           300)
run("Contractor 7-day follow-up (auto-date)",        "send_followup_outreach.py",    300)
run("Poll Vapi call outcomes + log voicemails",      "check_call_outcomes.py",       120)
run("Voicemail follow-up emails (from outcome log)", "vmail_followup.py",            120)
run("SMS outreach to hot leads",                     "send_sms_outreach.py",         300)


# ── PHASE 3: NEWSLETTER ──────────────────────────────────────────────────────
# Beehiiv API requires Enterprise plan — publishing is manual via dashboard.
# This phase prepares the next issue content so it's ready to copy-paste.
# Issues 1-4 are written in beehiiv_newsletter.py.
# TO SEND: Beehiiv > New Post > paste content from beehiiv_sent.json next issue.

print("\n[PHASE 3] NEWSLETTER")

if _is_monday():
    # Sends preview to Curtis's email — he replies approval then runs --send
    run("Newsletter preview to owner (Monday prep)", "send_newsletter_sendgrid.py", 120, args=["--prepare"])
    print("  [ACTION NEEDED] Check grayhorizonsenterprise@gmail.com for preview.")
    print("  When approved: python send_newsletter_sendgrid.py --send")
else:
    print(f"  Newsletter prep fires on Mondays. Today: {now.strftime('%A')}")


# ── PHASE 4: SOCIAL CONTENT ──────────────────────────────────────────────────
# LinkedIn: contractor/AI services content — stats-based, demo line CTA, no fake stories
# Twitter:  Edge Engine trading/signals content ONLY
# Cooldown enforcement is inside each script (20h minimum between posts)

print("\n[PHASE 4] SOCIAL CONTENT")

run("LinkedIn auto-post (1/day, 20h cooldown)",  "linkedin_poster.py",  120)
run("LinkedIn engage — reply comments, like niche posts", "linkedin_engage.py", 120)
run("Twitter/X auto-post (signals/trading only)", "twitter_poster.py",   120)
run("Twitter/X engage — reply mentions, like trending",   "twitter_engage.py",  120)


# ── PHASE 5: PERFORMANCE LOG ─────────────────────────────────────────────────

print("\n[PHASE 5] PERFORMANCE")

run("Performance tracker", "performance_tracker.py", 120)


print("\n" + "=" * 62)
print(f"  CYCLE COMPLETE  —  {datetime.now().strftime('%H:%M:%S')}")
print("=" * 62)
print("""
  MANUAL ACTIONS STILL NEEDED:
  - Send Carl Grant-Acquah LinkedIn DM (text already written)
  - Raise X API spend cap to $15 (billing resets July 10)
  - Beehiiv newsletter: copy issue from beehiiv_newsletter.py, paste into dashboard, publish
  - Twilio: submit EIN support ticket to unblock SMS via Twilio
  - Gumroad covers: upload 5 PNG files from gumroad_covers/ folder
""")
