"""
Scheduled Jobs — APScheduler

Jobs:
  - daily_scan: runs every day at configured hour, pulls all sources, scores, saves to DB
  - weekly_deep_scan: full Playwright scrape once a week
  - After each scan: sends email digest if SMTP configured
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from config import settings
from database.db import upsert_grant, update_scores, log_scan, get_grants
from discovery.grants_gov import bulk_scan as grants_gov_scan
from discovery.rss_feeds import fetch_all as rss_scan
from discovery.scraper import scrape_all as playwright_scan
from scoring.scorer import score_grant

import json


def _load_profile():
    from pathlib import Path
    p = Path(__file__).parent.parent / "user_profile.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _send_digest_if_configured(new_count: int, total_new: int):
    """Send email digest after a scan if SMTP is configured."""
    try:
        from notifications.email_notify import send_digest
        import sqlite3
        from database.db import DB_PATH

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) as c FROM grants").fetchone()["c"]
        high_match = conn.execute("SELECT COUNT(*) as c FROM grants WHERE match_score >= 70").fetchone()["c"]
        conn.close()

        top_grants = get_grants(min_score=60, limit=20)
        scan_stats = {
            "total": total,
            "high_match": high_match,
            "new_today": total_new,
        }
        send_digest(top_grants, scan_stats)
    except Exception as e:
        print(f"[Scheduler] Email digest error: {e}")


def run_daily_scan():
    """Pull from Grants.gov + RSS feeds, score, save to DB, then email digest."""
    print(f"\n[Scheduler] Daily scan started at {datetime.now()}")
    profile = _load_profile()

    sources = {
        "grants.gov": grants_gov_scan,
        "rss": rss_scan,
    }

    total_new = 0

    for source_name, fetch_fn in sources.items():
        try:
            grants = fetch_fn()
            found = len(grants)
            new_count = 0

            for grant in grants:
                grant_id, is_new = upsert_grant(grant)
                if is_new:
                    new_count += 1
                    total_new += 1
                    scores = score_grant(grant, profile)
                    update_scores(grant_id, scores)

            log_scan(source_name, found, new_count)
            print(f"[Scheduler] {source_name}: {found} found, {new_count} new")

        except Exception as e:
            log_scan(source_name, 0, 0, str(e))
            print(f"[Scheduler] Error in {source_name}: {e}")

    print(f"[Scheduler] Daily scan complete at {datetime.now()}")
    _send_digest_if_configured(total_new, total_new)
    print()


def run_deep_scan():
    """Full scan including Playwright for dynamic sites."""
    print(f"\n[Scheduler] Deep scan (Playwright) started at {datetime.now()}")
    profile = _load_profile()
    total_new = 0

    try:
        grants = playwright_scan()
        found = len(grants)
        new_count = 0

        for grant in grants:
            grant_id, is_new = upsert_grant(grant)
            if is_new:
                new_count += 1
                total_new += 1
                scores = score_grant(grant, profile)
                update_scores(grant_id, scores)

        log_scan("playwright", found, new_count)
        print(f"[Scheduler] Deep scan: {found} found, {new_count} new")
    except Exception as e:
        log_scan("playwright", 0, 0, str(e))
        print(f"[Scheduler] Deep scan error: {e}")

    _send_digest_if_configured(total_new, total_new)


def start_scheduler() -> BackgroundScheduler:
    """Initialize and start the background scheduler."""
    scheduler = BackgroundScheduler()

    # Daily scan at configured time
    scheduler.add_job(
        run_daily_scan,
        trigger=CronTrigger(hour=settings.scan_hour, minute=settings.scan_minute),
        id="daily_scan",
        name="Daily Grant Scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Weekly deep scan — Sundays at 3 AM
    scheduler.add_job(
        run_deep_scan,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_deep_scan",
        name="Weekly Deep Scan (Playwright)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    print(f"[Scheduler] Started. Daily scan at {settings.scan_hour:02d}:{settings.scan_minute:02d}")
    return scheduler
