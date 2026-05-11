"""
sync_to_railway.py — Gray Horizons Enterprise
ONE script to run locally. Does everything:
  1. Runs all scrapers to collect fresh leads
  2. Enriches with emails + phone numbers
  3. Qualifies and scores leads
  4. Generates outreach messages
  5. Pushes queue to Railway automatically

Schedule this with Windows Task Scheduler to run every morning at 6am.
Then you never touch it again.

Usage:
  python sync_to_railway.py              # full run
  python sync_to_railway.py --push-only  # skip scraping, just push current queue
"""

import subprocess
import sys
import os
import requests
import argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAILWAY_URL  = os.getenv("RAILWAY_URL", "https://ghe-dashboard-production.up.railway.app")
UPLOAD_URL   = f"{RAILWAY_URL}/upload-queue"
QUEUE_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach_queue.csv")

PIPELINE = [
    # ── ENGINE 1: AI System $997 ──────────────────────────────
    ("Scraping YellowPages",        "yellowpages_scraper.py"),
    ("Scraping Superpages",         "superpages_scraper.py"),
    ("Scraping Manta",              "manta_scraper.py"),
    ("Scraping Hotfrog",            "hotfrog_scraper.py"),
    ("Scraping Chamber of Commerce","chamberofcommerce_scraper.py"),
    ("Scraping Bark",               "bark_scraper.py"),
    ("Scraping Yelp",               "yelp_scraper.py"),
    ("Hunter.io email enrichment",  "hunter_scraper.py"),
    ("Finding leads via search",    "prospect_finder.py"),
    ("Enriching emails + phones",   "prospect_enricher.py"),
    ("Qualifying leads",            "prospect_qualifier.py"),
    ("Generating outreach",         "outreach_generator.py"),
    ("Sending follow-ups",          "followup_sender.py"),

    # ── ENGINE 2: Signals $49/month ───────────────────────────
    ("Scraping trader audience",    "signals_scraper.py"),
    ("Sending signals outreach",    "signals_engine.py"),

    # ── ENGINE 3: Grant Writing $1,500/client ─────────────────
    ("Scraping nonprofits",         "nonprofit_scraper.py"),
    ("Generating grant outreach",   "grant_outreach_generator.py"),
    ("Sending grant outreach",      "grant_blast.py"),

    # ── ENGINE 4: GHL CRM $297/month ──────────────────────────
    ("GHL agency outreach",         "ghl_outreach.py"),

    # ── ENGINE 5: TradingView Indicators $19-39/month ─────────
    ("TradingView trader outreach", "tradingview_engine.py"),

    # ── ENGINE 6: Video Pipeline (YouTube/TikTok) ─────────────
    ("Fetching + processing video clips", "video_pipeline.py"),
    ("Shadow Clans episode generation",   "shadow_clans_engine.py"),

    # ── ENGINE 7: Missed Call Text-Back $97/month ─────────────
    ("Scraping + pitching missed call",   "missed_call_textback.py"),

    # ── ENGINE 8: Review Generation $147/month ────────────────
    ("Scraping + pitching review gen",    "review_generation.py"),

    # ── ENGINE 9: GBP Optimization $197/month ─────────────────
    ("Scraping + pitching GBP mgmt",      "gbp_optimizer.py"),

    # ── ENGINE 10: AI Chatbot $97/month ───────────────────────
    ("Scraping + pitching AI chatbot",    "ai_chatbot_outreach.py"),

    # ── ENGINE 11: AI Voice Receptionist $197/month ────────────
    ("Scraping + pitching voice AI",      "ai_voice_receptionist.py"),

    # ── ENGINE 12: Lead Reactivation $497 one-time ─────────────
    ("Scraping + pitching reactivation",  "lead_reactivation.py"),

    # ── ENGINE 13: Social Media Mgmt $297/month ────────────────
    ("Scraping + pitching social media",  "social_media_mgmt.py"),

    # ── ENGINE 14: Website Audit $297 + $97/month ──────────────
    ("Scraping + pitching website audit", "website_audit.py"),

    # ── ENGINE 15: SMS Marketing $147/month ────────────────────
    ("Scraping + pitching SMS marketing", "sms_marketing.py"),

    # ── CONTINUOUS LEAD SCANNER (feeds all queues) ─────────────
    ("Multi-source lead scan",            "lead_scanner.py"),
]


def run_step(label: str, script: str) -> bool:
    print(f"\n[{label}]", flush=True)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    if not os.path.exists(script_path):
        print(f"  Skipping — {script} not found")
        return True
    try:
        result = subprocess.run(
            [sys.executable, "-u", script_path],
            timeout=1800,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  Timed out after 30 minutes — continuing")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def push_to_railway() -> bool:
    if not os.path.exists(QUEUE_FILE):
        print("[PUSH] No outreach_queue.csv found — run pipeline first")
        return False

    file_size = os.path.getsize(QUEUE_FILE)
    print(f"\n[PUSH] Uploading {QUEUE_FILE} ({file_size:,} bytes) to Railway...")

    try:
        with open(QUEUE_FILE, "rb") as f:
            response = requests.post(
                UPLOAD_URL,
                files={"csv_file": ("outreach_queue.csv", f, "text/csv")},
                data={"merge": "1"},
                timeout=60,
            )

        if response.status_code == 200:
            text = response.text
            # Extract counts from response HTML
            import re
            added_match = re.search(r"(\d+)\s+pending", text)
            added = added_match.group(1) if added_match else "?"
            print(f"[PUSH] Success — {added} leads now pending in Railway")
            return True
        else:
            print(f"[PUSH] Railway returned {response.status_code}")
            print(f"       Try manual upload at: {UPLOAD_URL}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[PUSH] Could not reach Railway — check your internet connection")
        print(f"       Manual upload URL: {UPLOAD_URL}")
        return False
    except Exception as e:
        print(f"[PUSH] Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push-only", action="store_true", help="Skip scraping, just push current queue")
    args = parser.parse_args()

    print("=" * 55)
    print("  GRAY HORIZONS — SYNC TO RAILWAY")
    print("=" * 55)

    if args.push_only:
        print("Push-only mode — skipping pipeline\n")
    else:
        print("Running full pipeline...\n")
        for label, script in PIPELINE:
            run_step(label, script)

    success = push_to_railway()

    print()
    print("=" * 55)
    if success:
        print("  DONE — Railway is loaded and sending")
    else:
        print("  DONE — Queue built locally")
        print(f"  Manual upload: {UPLOAD_URL}")
    print("=" * 55)


if __name__ == "__main__":
    main()
