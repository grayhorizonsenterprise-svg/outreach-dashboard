from flask import Flask, redirect, request as flask_request, Response
import pandas as pd
import os
import requests
import threading
import time
import subprocess
import sys
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    PACIFIC = ZoneInfo("America/Los_Angeles")
    def now_pacific():
        return datetime.now(PACIFIC)
    def fmt_pacific(ts):
        return datetime.fromtimestamp(ts, PACIFIC).strftime("%I:%M %p PT")
except Exception:
    _PT = timezone(timedelta(hours=-7))
    def now_pacific():
        return datetime.now(_PT)
    def fmt_pacific(ts):
        return datetime.fromtimestamp(ts, _PT).strftime("%I:%M %p PT")

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)

URL_HOA        = os.getenv("HOA_URL", "#")
URL_DENTAL     = os.getenv("DENTAL_URL", "#")
URL_HVAC       = os.getenv("HVAC_URL", "#")
URL_HUB        = os.getenv("HUB_URL", "#")
URL_PLUMBING   = os.getenv("PLUMBING_URL", "#")
EDGE_ENGINE_URL = os.getenv("EDGE_ENGINE_URL", "https://outreach-dashboard-production-6894.up.railway.app")
URL_GRANTS       = "https://ghe-grant-agent-production.up.railway.app"
URL_VOICE_SERVER = os.getenv("VOICE_SERVER_URL", "https://ghe-voice-production.up.railway.app")
PIPELINE_SCRIPTS = [
    # DDG-based (may be rate-limited on cloud IPs — kept as fallback)
    "hotfrog_scraper.py",
    "chamberofcommerce_scraper.py",
    "bark_scraper.py",
    # Google Maps scraper — no API key, finds real local business websites
    "gmaps_scraper.py",
    # Scrape emails directly from company websites (free, no API)
    "website_email_scraper.py",
    # Direct directory scrapers — no DDG, hit YP/SP pages directly
    "yellowpages_scraper.py",
    "superpages_scraper.py",
    # API-based (only run if keys are set in Railway env vars)
    "yelp_scraper.py",
    # "snov_scraper.py",  # DISABLED — refund pending, credits burning
    "hunter_scraper.py",
    "apollo_scraper.py",
    # Enrichment + quality + generation
    "prospect_enricher.py",
    "prospect_qualifier.py",
    "email_verifier.py",
    "outreach_generator.py",
    # outreach_sender.py intentionally excluded — sending is manual-only via dashboard buttons
]

DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", "50"))  # conservative: rebuilding SendGrid reputation after 26.7% bounce
batch_running     = False
batch_sent_count  = 0

# =========================
# BACKGROUND PIPELINE ENGINE
# Runs the full pipeline every 6 hours inside the same process
# so one Render web service handles everything
# =========================
pipeline_running = False
last_run_time = None

SYNC_AFTER = {"outreach_generator.py", "yelp_scraper.py", "apollo_scraper.py"}

def _write_skip_list():
    """Dump all sent/opted-out email domains to sent_domains.csv so scrapers skip them."""
    try:
        conn = __get_db()
        rows = []
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT email, website FROM leads WHERE status IN ('sent','opted_out')")
                rows = cur.fetchall()
            conn.close()
        domains = set()
        for email, website in rows:
            if email and '@' in email:
                domains.add(email.split('@')[-1].lower().strip())
            if website:
                try:
                    from urllib.parse import urlparse as _up
                    d = _up(str(website)).netloc.lower().replace('www.', '').split(':')[0]
                    if d and '.' in d:
                        domains.add(d)
                except Exception:
                    pass
        import csv as _csv
        skip_path = os.path.join(DATA_DIR, 'sent_domains.csv')
        with open(skip_path, 'w', newline='') as f:
            w = _csv.writer(f)
            w.writerow(['domain'])
            for d in domains:
                w.writerow([d])
        print(f"[SKIP] {len(domains)} already-sent domains written — scrapers will skip these", flush=True)
    except Exception as e:
        print(f"[SKIP] Error writing skip list: {e}", flush=True)

def run_pipeline_once():
    global pipeline_running, last_run_time
    if pipeline_running:
        return
    pipeline_running = True
    script_dir = os.path.dirname(os.path.abspath(__file__))
    _write_skip_list()  # tell scrapers which domains we've already emailed
    print("[ENGINE] Starting pipeline cycle...", flush=True)
    for script in PIPELINE_SCRIPTS:
        try:
            print(f"[ENGINE] Running {script}", flush=True)
            subprocess.run(
                [sys.executable, "-u", os.path.join(script_dir, script)],
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                timeout=1800
            )
        except Exception as e:
            print(f"[ENGINE] Error in {script}: {e}", flush=True)
        # Sync to DB immediately after each lead-producing script — don't wait for end
        if script in SYNC_AFTER:
            try:
                _sync_csv_to_db()
                print(f"[ENGINE] Mid-pipeline DB sync after {script}", flush=True)
            except Exception as e:
                print(f"[ENGINE] Mid-sync error: {e}", flush=True)
    # Final sync to catch anything missed
    try:
        _sync_csv_to_db()
    except Exception as e:
        print(f"[ENGINE] Sync error: {e}", flush=True)
    last_run_time = time.time()
    _record_engine_run("Pipeline (Lead Gen)")
    pipeline_running = False
    print("[ENGINE] Cycle done.", flush=True)

def get_pending_count():
    """Quick check of pending lead count from DB or CSV."""
    try:
        conn = __get_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM leads WHERE status='pending'")
                count = cur.fetchone()[0]
            conn.close()
            return count
    except Exception:
        pass
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE, dtype=str).fillna("")
            return len(df[df["status"] == "pending"])
    except Exception:
        pass
    return 0

def run_pipeline_loop():
    time.sleep(600)  # wait 10 min — let gunicorn fully stabilize before pipeline starts
    while True:
        run_pipeline_once()
        # Auto-refill: if pending drops below 1000, run again in 1 hour instead of 4
        pending = get_pending_count()
        if pending < 1000:
            print(f"[ENGINE] Low queue ({pending} pending) — refilling in 60 min.", flush=True)
            time.sleep(3600)
        else:
            print(f"[ENGINE] Queue healthy ({pending} pending) — next cycle in 4 hours.", flush=True)
            time.sleep(14400)

threading.Thread(target=run_pipeline_loop, daemon=True).start()

# =========================
# KEEP-ALIVE (prevents Render free tier from sleeping)
# =========================
def keep_alive():
    time.sleep(60)
    # Support Render (RENDER_EXTERNAL_URL) and Railway (RAILWAY_PUBLIC_DOMAIN)
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    port = os.getenv("PORT", "8080")
    if render_url:
        target = render_url.rstrip("/")
    elif railway_domain:
        target = f"https://{railway_domain.rstrip('/')}"
    else:
        target = f"http://127.0.0.1:{port}"
    print(f"[KeepAlive] Pinging {target}/health every 10 min", flush=True)
    while True:
        try:
            requests.get(f"{target}/health", timeout=10)
        except Exception:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# =========================
# REVENUE ENGINE SCHEDULER
# Runs all money-making engines 24/7 on Railway — no computer needed
# =========================

def _run_engine(label: str, script: str, extra_args: list = None):
    """Run a script from the project root. Non-fatal if missing."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    if not os.path.exists(path):
        print(f"[ENGINE] {label}: script not found ({script})", flush=True)
        return
    print(f"[ENGINE] Starting: {label}", flush=True)
    cmd = [sys.executable, "-u", path] + (extra_args or [])
    try:
        subprocess.run(
            cmd,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            timeout=3600,
        )
        _record_engine_run(label)
        print(f"[ENGINE] Done: {label}", flush=True)
    except Exception as e:
        print(f"[ENGINE] Error in {label}: {e}", flush=True)


def _signals_engine_daily():
    """Runs once per day: FINRA → signals blast → Stocktwits → LinkedIn outreach."""
    import datetime as _dt
    _last_ran = [None]
    time.sleep(120)
    # Fire LinkedIn immediately on startup so restarts don't miss the day
    _run_engine("LinkedIn Outreach (startup)", "linkedin_outreach.py")
    _last_ran[0] = _dt.datetime.utcnow().date()
    while True:
        now = _dt.datetime.utcnow()
        today = now.date()
        if today != _last_ran[0] and now.hour >= 7:
            _run_engine("FINRA Financial Advisor Leads", "finra_leads.py")
            _run_engine("Signals Email Blast", "signals_engine.py")
            _run_engine("Stocktwits Post", "stocktwits_poster.py")
            _run_engine("LinkedIn Post", "linkedin_poster.py")
            _run_engine("LinkedIn Outreach", "linkedin_outreach.py")
            _last_ran[0] = today
            time.sleep(600)
        time.sleep(60)


def _grant_pipeline_daily():
    """Scrapes nonprofits → verifies → generates messages → blasts. Runs at 9am UTC."""
    import datetime as _dt
    time.sleep(180)
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 9 and now.minute < 10:
            _run_engine("Nonprofit Scraper (ProPublica)", "nonprofitscraper_propublica.py")
            _run_engine("Email Verifier", "email_verifier.py")
            _run_engine("Grant Outreach Generator", "grant_outreach_generator.py")
            _run_engine("Grant Email Blast", "grant_blast.py")
            time.sleep(600)
        time.sleep(60)


def _twitter_engage_scheduler():
    """DISABLED — burns API credits. Re-enable only after revenue covers Twitter API cost."""
    print("[TWITTER ENGAGE] Disabled — no budget.", flush=True)
    return


def _twitter_scheduler():
    """Posts to Twitter 5x/day at 8am, 10am, 1pm, 5pm, 8pm UTC.
    Also fires one post immediately on startup so deploys never go dark."""
    import datetime as _dt
    POST_HOURS = {13, 15, 18, 21, 1}
    fired = set()
    time.sleep(120)  # let app stabilize
    # Fire startup post only if we haven't posted in the last 4 hours (prevents redeploy spam)
    import datetime as _dt2
    _startup_log = os.path.join(DATA_DIR, "twitter_startup.txt")
    _do_startup = True
    try:
        if os.path.exists(_startup_log):
            _last = float(open(_startup_log).read().strip())
            if (time.time() - _last) < 14400:  # 4 hours
                _do_startup = False
                print("[TWITTER] Skipping startup post — posted within last 4 hours", flush=True)
    except Exception:
        pass
    if _do_startup:
        _run_engine("Twitter Post (startup)", "twitter_poster.py", extra_args=["--force"])
        try:
            open(_startup_log, "w").write(str(time.time()))
        except Exception:
            pass
    fired.add((_dt.datetime.utcnow().date(), _dt.datetime.utcnow().hour))
    while True:
        now = _dt.datetime.utcnow()
        key = (now.date(), now.hour)
        if now.hour in POST_HOURS and key not in fired and now.minute < 10:
            _run_engine("Twitter Post", "twitter_poster.py")
            fired.add(key)
            if len(fired) > 20:
                fired = set(list(fired)[-10:])
        time.sleep(60)


def _gmail_monitor_thread():
    """Monitors Gmail for hot leads every 5 minutes."""
    time.sleep(300)
    while True:
        _run_engine("Gmail Reply Monitor", "gmail_reply_monitor.py")
        time.sleep(300)


def _reddit_monitor_thread():
    """Checks Reddit for comments needing replies every hour."""
    time.sleep(600)
    while True:
        _run_engine("Reddit Monitor", "reddit_monitor.py")
        time.sleep(3600)


def _shadow_clans_nightly():
    """Generates one Shadow Clans episode per night at 11pm UTC."""
    import datetime as _dt
    time.sleep(360)
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 23 and now.minute < 10:
            _run_engine("Shadow Clans Episode Generator", "shadow_clans_engine.py")
            time.sleep(600)
        time.sleep(60)


def _realestate_engine_daily():
    """Fires immediately on startup then daily at 7am UTC."""
    import datetime as _dt
    time.sleep(120)
    _run_engine("Real Estate Engine", "realestate_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 7 and now.minute < 10:
            _run_engine("Real Estate Engine", "realestate_engine.py")
            time.sleep(600)
        time.sleep(60)


def _medspa_engine_daily():
    """Fires immediately on startup then daily at 10am UTC."""
    import datetime as _dt
    time.sleep(300)
    _run_engine("Med Spa Engine", "medspa_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 10 and now.minute < 10:
            _run_engine("Med Spa Engine", "medspa_engine.py")
            time.sleep(600)
        time.sleep(60)


def _insurance_engine_daily():
    """Fires immediately on startup then daily at 11am UTC."""
    import datetime as _dt
    time.sleep(480)
    _run_engine("Insurance Engine", "insurance_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 11 and now.minute < 10:
            _run_engine("Insurance Engine", "insurance_engine.py")
            time.sleep(600)
        time.sleep(60)


def _ecommerce_engine_daily():
    """Fires immediately on startup then daily at 12pm UTC."""
    import datetime as _dt
    time.sleep(660)
    _run_engine("E-Commerce Engine", "ecommerce_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 12 and now.minute < 10:
            _run_engine("E-Commerce Engine", "ecommerce_engine.py")
            time.sleep(600)
        time.sleep(60)


def _restaurant_engine_daily():
    """Fires immediately on startup then daily at 2pm UTC."""
    import datetime as _dt
    time.sleep(840)
    _run_engine("Restaurant Engine", "restaurant_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 14 and now.minute < 10:
            _run_engine("Restaurant Engine", "restaurant_engine.py")
            time.sleep(600)
        time.sleep(60)


def _gym_engine_daily():
    """Fires immediately on startup then daily at 3pm UTC."""
    import datetime as _dt
    time.sleep(1020)
    _run_engine("Gym Engine", "gym_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 15 and now.minute < 10:
            _run_engine("Gym Engine", "gym_engine.py")
            time.sleep(600)
        time.sleep(60)


def _mortgage_engine_daily():
    """Fires immediately on startup then daily at 4pm UTC."""
    import datetime as _dt
    time.sleep(1200)
    _run_engine("Mortgage Engine", "mortgage_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 16 and now.minute < 10:
            _run_engine("Mortgage Engine", "mortgage_engine.py")
            time.sleep(600)
        time.sleep(60)


def _followup_engine_daily():
    """Fires immediately on startup then daily at 6pm UTC."""
    import datetime as _dt
    time.sleep(1380)
    _run_engine("Follow-Up Engine", "followup_engine.py")
    while True:
        now = _dt.datetime.utcnow()
        if now.hour == 18 and now.minute < 10:
            _run_engine("Follow-Up Engine", "followup_engine.py")
            time.sleep(600)
        time.sleep(60)


def _auto_blast_scheduler():
    """Sends cold outreach daily at 6 AM UTC via SendGrid.
    50 emails/day. Role addresses and SendGrid suppressions filtered before every send."""
    import datetime as _dt
    fired_today: set = set()
    print("[AUTO-BLAST] Scheduler active — fires daily at 06:00 UTC", flush=True)
    while True:
        try:
            now = _dt.datetime.utcnow()
            key = now.date()
            if now.hour == 6 and now.minute < 10 and key not in fired_today:
                fired_today.add(key)
                if len(fired_today) > 3:
                    fired_today = set(list(fired_today)[-2:])
                print(f"[AUTO-BLAST] Firing daily batch — {now.strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
                run_batch_send()
        except Exception as _e:
            print(f"[AUTO-BLAST] Error: {_e}", flush=True)
        time.sleep(60)


def _upwork_scout_scheduler():
    """Scans Upwork RSS every 2 hours for matching jobs, drafts proposals."""
    time.sleep(240)
    while True:
        try:
            from upwork_scout import run as scout_run
            scout_run()
        except Exception as e:
            print(f"[UPWORK SCOUT] Error: {e}", flush=True)
        time.sleep(7200)


def _vapi_followup_scheduler():
    """Calls leads 3 days after email was sent. Runs daily at 10 AM."""
    import random
    while True:
        now = datetime.now()
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        time.sleep((target - now).total_seconds())
        try:
            from vapi_agent import run_followup_calls
            run_followup_calls(days_after=3, max_calls=20)
        except Exception as e:
            print(f"[VAPI FOLLOWUP] Error: {e}", flush=True)


# Start only essential schedulers — others disabled until fixed
for _fn in [
    _twitter_scheduler,
    _shadow_clans_nightly,
]:
    threading.Thread(target=_fn, daemon=True).start()

print("[ENGINES] Essential schedulers started (Twitter, Shadow Clans)", flush=True)

CSV_FILE      = os.path.join(DATA_DIR, "outreach_queue.csv")
SOCIAL_FILE   = os.path.join(DATA_DIR, "social_pipeline.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")

def load_opt_outs() -> set:
    """Return lowercase set of all opted-out emails."""
    try:
        if os.path.exists(OPT_OUT_FILE):
            df = pd.read_csv(OPT_OUT_FILE, dtype=str).fillna("")
            return set(df["email"].str.lower().str.strip())
    except Exception:
        pass
    return set()

def add_opt_out(email: str, reason: str = "requested removal"):
    """Append an email to the opt-out list (idempotent)."""
    email = email.lower().strip()
    existing = load_opt_outs()
    if email in existing:
        return
    row = pd.DataFrame([{"email": email, "reason": reason}])
    if os.path.exists(OPT_OUT_FILE):
        row.to_csv(OPT_OUT_FILE, mode="a", header=False, index=False)
    else:
        row.to_csv(OPT_OUT_FILE, index=False)
    print(f"[OPT-OUT] Added {email}", flush=True)

# =========================
# POSTGRESQL — persistent queue storage
# =========================
import psycopg2
import psycopg2.extras

_DATABASE_URL = os.getenv("DATABASE_URL", "")

def __get_db():
    if not _DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(_DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        print(f"[DB] Connect failed: {e}", flush=True)
        return None

_get_db = __get_db  # alias used by vapi_collect, confirm_email, calls routes

def _init_db():
    conn = __get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    company TEXT DEFAULT '',
                    name TEXT DEFAULT '',
                    email TEXT UNIQUE NOT NULL,
                    message TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    niche TEXT DEFAULT 'hoa',
                    subject TEXT DEFAULT '',
                    website TEXT DEFAULT ''
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vapi_leads (
                    id SERIAL PRIMARY KEY,
                    name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    business_type TEXT DEFAULT '',
                    raw_email TEXT DEFAULT '',
                    email_sent BOOLEAN DEFAULT FALSE,
                    sms_sent BOOLEAN DEFAULT FALSE,
                    confirm_token TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE vapi_leads ADD COLUMN IF NOT EXISTS confirm_token TEXT DEFAULT ''")
        conn.commit()
        print("[DB] Table ready", flush=True)
    except Exception as e:
        print(f"[DB] Init error: {e}", flush=True)
    finally:
        conn.close()

threading.Thread(target=_init_db, daemon=True).start()

SOCIAL_STAGES = ["commented", "replied", "demo_sent", "closed", "dead"]

def load_social():
    import csv as _csv
    if not os.path.exists(SOCIAL_FILE):
        return []
    with open(SOCIAL_FILE, newline="", encoding="utf-8") as f:
        return list(_csv.DictReader(f))

def save_social(rows):
    import csv as _csv
    if not rows:
        return
    with open(SOCIAL_FILE, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def add_social_prospect(handle, platform, notes, email=""):
    import csv as _csv
    rows  = load_social()
    new_id = str(len(rows) + 1)
    row = {
        "id":       new_id,
        "handle":   handle.strip(),
        "platform": platform.strip(),
        "email":    email.strip(),
        "stage":    "commented",
        "notes":    notes.strip(),
        "added":    datetime.now().strftime("%m/%d %I:%M %p"),
    }
    rows.append(row)
    save_social(rows)

    # Auto-queue in email outreach if email provided and not already in queue
    if email.strip():
        df = load_data()
        existing_emails = df["email"].fillna("").str.lower().tolist()
        if email.strip().lower() not in existing_emails:
            new_email_row = {
                "company": handle.strip(),
                "name":    "",
                "email":   email.strip(),
                "website": "",
                "niche":   "social",
                "subject": "Quick question about your content",
                "message": (
                    "Hey,\n\n"
                    "Saw your content and had a quick question: are you getting customers "
                    "from your posts or mostly just views?\n\n"
                    "We help businesses turn content into actual leads. "
                    "Happy to show you what that looks like.\n\n"
                    "Gray Horizons Enterprise"
                ),
                "status": "pending",
            }
            df = pd.concat([df, pd.DataFrame([new_email_row])], ignore_index=True)
            save_data(df)
            print(f"[SOCIAL→EMAIL] Auto-queued {email} from social pipeline", flush=True)

def build_social_table():
    rows = load_social()
    if not rows:
        return '<div style="text-align:center;padding:40px;color:#475569;font-size:13px;">No prospects yet. Drop a comment and add them above.</div>'

    STAGE_COLORS = {
        "commented":  ("#1e3a5f", "#60a5fa", "Commented"),
        "replied":    ("#1a3a1a", "#4ade80", "Replied"),
        "demo_sent":  ("#2d1a00", "#fbbf24", "Demo Sent"),
        "closed":     ("#14532d", "#86efac", "CLOSED"),
        "dead":       ("#1f1f1f", "#6b7280", "Dead"),
    }

    html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:13px;">'
    html += '<tr style="background:#0f172a;"><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Handle</th><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;">Platform</th><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;">Email</th><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;">Stage</th><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;">Notes</th><th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;">Move</th></tr>'

    for row in reversed(rows):
        sid   = row.get("id", "")
        stage = row.get("stage", "commented")
        bg, fg, label = STAGE_COLORS.get(stage, ("#1e293b", "#e2e8f0", stage))
        email = row.get("email", "")
        email_cell = f'<span style="color:#38bdf8;font-size:11px;">{email}</span>' if email else '<span style="color:#475569;font-size:11px;">none</span>'

        idx        = SOCIAL_STAGES.index(stage) if stage in SOCIAL_STAGES else 0
        next_stage = SOCIAL_STAGES[idx + 1] if idx + 1 < len(SOCIAL_STAGES) else None
        next_btn   = f'<a href="/social/advance/{sid}" style="background:#f97316;color:#000;border:none;padding:4px 10px;border-radius:5px;font-size:11px;font-weight:bold;text-decoration:none;">Next</a>' if next_stage else '<span style="color:#475569;font-size:11px;">Done</span>'
        kill_btn   = f'<a href="/social/kill/{sid}" style="background:#ef4444;color:#fff;border:none;padding:4px 8px;border-radius:5px;font-size:11px;font-weight:bold;text-decoration:none;margin-left:4px;">✕</a>'

        html += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:9px 10px;color:#e2e8f0;font-weight:bold;">{row.get("handle","")}</td>'
            f'<td style="padding:9px 10px;color:#94a3b8;">{row.get("platform","")}</td>'
            f'<td style="padding:9px 10px;">{email_cell}</td>'
            f'<td style="padding:9px 10px;"><span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;">{label}</span></td>'
            f'<td style="padding:9px 10px;color:#64748b;font-size:12px;">{row.get("notes","")}</td>'
            f'<td style="padding:9px 10px;">{next_btn}{kill_btn}</td>'
            f'</tr>'
        )

    html += '</table></div>'
    return html

# =========================
# LOAD DATA
# =========================
def _clean_df(df):
    df = df.rename(columns={"Company": "company", "Email": "email", "Message": "message", "Name": "name"})
    for col in ["company","name","email","message","status","niche","subject","website"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    df["message"] = (
        df["message"]
        .str.replace("—", ",", regex=False)
        .str.replace("--", ",", regex=False)
        .str.replace("  ", " ", regex=False)
    )
    df.loc[df["status"] == "", "status"] = "pending"
    df.loc[df["niche"] == "", "niche"] = "hoa"
    return df

def load_data():
    conn = __get_db()
    if conn:
        try:
            df = pd.read_sql(
                "SELECT company,name,email,message,status,niche,subject,website FROM leads ORDER BY id",
                conn
            )
            conn.close()
            return _clean_df(df)
        except Exception as e:
            print(f"[DB] Load error: {e}", flush=True)
            try:
                conn.close()
            except Exception:
                pass
    # Fallback to CSV
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["company","name","email","message","status","niche","subject","website"])
    return _clean_df(pd.read_csv(CSV_FILE))

def save_data(df):
    conn = __get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                for _, row in df.iterrows():
                    email = str(row.get("email","")).strip().lower()
                    if not email:
                        continue
                    cur.execute("""
                        INSERT INTO leads (company,name,email,message,status,niche,subject,website)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (email) DO UPDATE SET
                            company=EXCLUDED.company, name=EXCLUDED.name,
                            message=EXCLUDED.message,
                            status=CASE WHEN leads.status IN ('sent','opted_out','skipped')
                                        THEN leads.status
                                        ELSE EXCLUDED.status END,
                            niche=EXCLUDED.niche, subject=EXCLUDED.subject,
                            website=EXCLUDED.website
                    """, (
                        str(row.get("company","")), str(row.get("name","")),
                        email, str(row.get("message","")),
                        str(row.get("status","pending")), str(row.get("niche","hoa")),
                        str(row.get("subject","")), str(row.get("website",""))
                    ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Save error: {e}", flush=True)
            try:
                conn.close()
            except Exception:
                pass
    # Always write CSV backup too
    df.to_csv(CSV_FILE, index=False)

def count_sent_today() -> int:
    if not os.path.exists(SENT_LOG):
        return 0
    try:
        import csv as _csv
        today = now_pacific().strftime("%Y-%m-%d")
        n = 0
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                ts = row.get("timestamp", "")
                ok = str(row.get("success", row.get("status", ""))).strip().lower() in (
                    "true", "1", "smtp", "sendgrid", "gmail-smtp-accepted"
                )
                if ok and ts.startswith(today):
                    n += 1
        return n
    except Exception:
        return 0

# =========================
# FORMAT MESSAGE (FIX PARAGRAPHS)
# =========================
def format_message(msg):
    if not msg:
        return ""
    clean = msg.replace("\r\n", "\n").replace("\r", "\n")
    # Strip signature block so it doesn't show in the card preview
    for marker in ["Alex\nGray Horizons Enterprise", "Gray\nGray Horizons Enterprise"]:
        if marker in clean:
            clean = clean[:clean.rfind(marker)].rstrip()
            break
    for url in ["https://grayhorizonsenterprise.com", "grayhorizonsenterprise.com"]:
        if clean.rstrip().endswith(url):
            clean = clean[:clean.rstrip().rfind(url)].rstrip()
    paragraphs = clean.split("\n\n")
    return "</p><p style='margin:0 0 12px 0;'>".join(
        f"<p style='margin:0 0 12px 0;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs
    )

# =========================
# SEND EMAIL (SENDGRID)
# =========================
SENT_LOG = os.path.join(DATA_DIR, "sent_log.csv")

def log_sent(to_email, name, company, subject, success, error=""):
    import csv
    row = {
        "timestamp": now_pacific().strftime("%Y-%m-%d %I:%M %p PT"),
        "company": company,
        "name": name,
        "email": to_email,
        "subject": subject,
        "success": success,
        "error": error,
    }
    file_exists = os.path.exists(SENT_LOG)
    with open(SENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    # Immediately persist to DB so redeploys don't lose sent records
    if success and to_email:
        try:
            _c = __get_db()
            if _c:
                with _c.cursor() as _cur:
                    _cur.execute(
                        """INSERT INTO leads (company,name,email,message,status,niche,subject,website)
                           VALUES (%s,%s,%s,%s,'sent',%s,%s,%s)
                           ON CONFLICT (email) DO UPDATE SET status='sent'""",
                        (company or "", name or "", str(to_email).strip().lower(),
                         "", "", subject or "", "")
                    )
                _c.commit()
                _c.close()
        except Exception:
            pass

def _build_html_body(name, sender_name, message):
    # Normalize line endings before any processing
    clean_msg = message.replace("\r\n", "\n").replace("\r", "\n")
    # Strip any existing signature block and URL
    for sig_marker in [
        "Alex\nGray Horizons Enterprise",
        "Gray\nGray Horizons Enterprise",
        "alex\nGray Horizons Enterprise",
    ]:
        if sig_marker in clean_msg:
            clean_msg = clean_msg[:clean_msg.rfind(sig_marker)].rstrip()
            break
    # Also strip any trailing URL line
    for url_trail in ["https://grayhorizonsenterprise.com", "grayhorizonsenterprise.com",
                      "GrayHorizonsEnterprise.com"]:
        if clean_msg.rstrip().endswith(url_trail):
            clean_msg = clean_msg[:clean_msg.rstrip().rfind(url_trail)].rstrip()
    return (
        "<div style='font-family:Arial,sans-serif;line-height:1.7;color:#222;max-width:600px;'>"
        "<p>" + clean_msg.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
        "<br>"
        "<p style='margin:0;'>"
        "<a href='https://calendly.com/grayhorizonsenterprise/30min' "
        "style='display:inline-block;background:#1a73e8;color:#ffffff;padding:10px 22px;"
        "border-radius:5px;text-decoration:none;font-weight:bold;font-size:14px;'>"
        "Book a Free 15-Minute Call</a>"
        "</p>"
        "<br>"
        "<p style='margin:0;'>Gray Horizons Enterprise<br>"
        "<a href='https://grayhorizonsenterprise.com' style='color:#1a73e8;'>"
        "grayhorizonsenterprise.com</a></p>"
        "</div>"
    )

def _send_via_sendgrid(api_key, sender_addr, sender_name, to_email, subject, html_body, name, company):
    # Force lowercase — SendGrid sender verification is case-sensitive
    verified_from = sender_addr
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": verified_from, "name": sender_name},
        "reply_to": {"email": REPLY_TO_EMAIL, "name": "Gray Horizons Enterprise"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}]
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload, headers=headers, timeout=15
        )
        if resp.status_code == 202:
            print(f"[SEND:SendGrid] OK -> {to_email} ({company})")
            log_sent(to_email, name, company, subject, True, "sendgrid")
            return True
        else:
            err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            print(f"[SEND:SendGrid] FAILED -> {to_email} | {err}")
            log_sent(to_email, name, company, subject, False, f"sendgrid: {err}")
            return False
    except Exception as e:
        print(f"[SEND:SendGrid] EXCEPTION -> {to_email} | {e}")
        log_sent(to_email, name, company, subject, False, f"sendgrid exception: {e}")
        return False

def _send_via_smtp(sender_addr, smtp_password, to_email, subject, html_body, name, company):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText as MIMETextPart
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender_addr
        msg["To"]      = to_email
        msg.attach(MIMETextPart(html_body, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(sender_addr, smtp_password)
        server.sendmail(sender_addr, to_email, msg.as_string())
        server.quit()
        print(f"[SEND:SMTP] OK -> {to_email} ({company})")
        log_sent(to_email, name, company, subject, True, "smtp")
        return True
    except Exception as e:
        print(f"[SEND:SMTP] EXCEPTION -> {to_email} | {e}")
        log_sent(to_email, name, company, subject, False, f"smtp: {e}")
        return False

VERIFIED_SENDER = "jordan@grayhorizonsenterprise.com"
REPLY_TO_EMAIL  = "grayhorizonsenterprise@gmail.com"
DASHBOARD_URL   = os.getenv("DASHBOARD_URL", "https://ghe-dashboard-production.up.railway.app")

def _send_via_brevo(to_email, subject, html_body, name, company, sender_addr, sender_name):
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    if not brevo_key:
        return False
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender": {"email": sender_addr, "name": sender_name},
                "to": [{"email": to_email, "name": name}],
                "subject": subject,
                "htmlContent": html_body,
            },
            timeout=15,
        )
        ok = resp.status_code in (200, 201, 202)
        log_sent(to_email, name, company, subject, ok, f"brevo:{resp.status_code}")
        if ok:
            print(f"[SEND] Brevo OK -> {to_email}")
        else:
            print(f"[SEND] Brevo {resp.status_code}: {resp.text[:120]}")
        return ok
    except Exception as e:
        print(f"[SEND] Brevo exception: {e}")
        return False


def send_email(to_email, name, company, message, subject=""):
    sender_addr = VERIFIED_SENDER
    sender_name = os.getenv("SENDER_NAME", "Gray Horizons Enterprise")
    subject     = subject.strip() if subject.strip() else "Quick question for your team"

    if not to_email or not str(to_email).strip():
        log_sent(to_email, name, company, subject, False, "no recipient")
        return False

    html_body = _build_html_body(name, sender_name, message)

    # ── Primary: SendGrid ─────────────────────────────────────────────────────
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    if api_key:
        ok = _send_via_sendgrid(api_key, sender_addr, sender_name,
                                to_email, subject, html_body, name, company)
        if ok:
            return True
        print(f"[SEND] SendGrid failed for {to_email} — trying Gmail SMTP")

    # ── Fallback: Gmail SMTP ───────────────────────────────────────────────────
    smtp_password = os.getenv("SENDER_APP_PASSWORD", "").strip()
    if smtp_password:
        return _send_via_smtp(sender_addr, smtp_password,
                              to_email, subject, html_body, name, company)

    print("[SEND] ERROR: No sending method — set BREVO_API_KEY, SENDGRID_API_KEY, or SENDER_APP_PASSWORD")
    log_sent(to_email, name, company, subject, False, "no sending method")
    return False

# =========================
# BOUNCE SUPPRESSION — checks SendGrid suppression lists before every send
# =========================
_suppression_cache: dict = {}   # email -> True (suppressed) cached for the session

_ROLE_PREFIXES = {
    "info", "contact", "support", "admin", "noreply", "no-reply",
    "hello", "team", "sales", "help", "service", "billing",
    "office", "mail", "email", "reception", "enquiries", "enquiry",
    "general", "business", "company", "webmaster", "postmaster",
    "accounts", "accounting", "customerservice", "customer",
}

def _is_role_address(email: str) -> bool:
    local = email.lower().split("@")[0]
    return local in _ROLE_PREFIXES

def _is_sendgrid_suppressed(email: str) -> bool:
    """Returns True if SendGrid has this email on any suppression list (bounce/spam/unsubscribe).
    Caches per-session so we only hit the API once per address."""
    email = email.strip().lower()
    if email in _suppression_cache:
        return _suppression_cache[email]
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    if not api_key:
        return False
    headers = {"Authorization": f"Bearer {api_key}"}
    for endpoint in [
        f"https://api.sendgrid.com/v3/suppression/bounces/{email}",
        f"https://api.sendgrid.com/v3/suppression/spam_reports/{email}",
        f"https://api.sendgrid.com/v3/suppression/unsubscribes/{email}",
    ]:
        try:
            r = requests.get(endpoint, headers=headers, timeout=8)
            if r.status_code == 200 and r.json():
                _suppression_cache[email] = True
                return True
        except Exception:
            pass
    _suppression_cache[email] = False
    return False


# =========================
# BATCH SENDER — runs in background thread
# =========================
_batch_started_at = 0.0

def run_batch_send(limit=None):
    global batch_running, batch_sent_count, _batch_started_at
    if not os.getenv("BREVO_API_KEY", "").strip() and not os.getenv("SENDGRID_API_KEY", "").strip():
        print("[BATCH] PAUSED — No sender configured. Add BREVO_API_KEY or SENDGRID_API_KEY to Railway.", flush=True)
        return
    if batch_running:
        # Safety: if stuck for > 45 min, auto-reset
        if time.time() - _batch_started_at > 2700:
            print("[BATCH] Watchdog: resetting stuck batch_running flag", flush=True)
            batch_running = False
        else:
            return
    batch_running    = True
    _batch_started_at = time.time()
    batch_sent_count = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    lock = threading.Lock()

    cap = limit if limit else DAILY_EMAIL_LIMIT
    print(f"[BATCH] Sending up to {cap} emails...", flush=True)

    df      = load_data()
    mask    = (df["status"] == "pending") & (df["email"].fillna("").str.strip() != "")
    pending = df[mask]

    # Build global "already sent" wall — email + domain + company name level, CSV + DB
    opt_outs      = load_opt_outs()
    ever_sent     = set()
    ever_domains  = set()
    ever_companies = set()  # company name dedup — catches same company with different emails

    def _norm_company(c):
        """Normalize company name for dedup — lowercase, strip punctuation/suffixes."""
        import re
        c = str(c).strip().lower()
        c = re.sub(r'\b(inc|llc|ltd|corp|co|management|services|solutions|group|associates|properties|property)\b', '', c)
        c = re.sub(r'[^a-z0-9 ]', '', c)
        return re.sub(r'\s+', ' ', c).strip()

    # 1. Load from PostgreSQL (persistent across redeploys — authoritative source)
    try:
        _conn = __get_db()
        if _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT email, website, company FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (_e, _w, _c) in _cur.fetchall():
                    if _e:
                        _em = str(_e).strip().lower()
                        ever_sent.add(_em)
                        if "@" in _em:
                            ever_domains.add(_em.split("@")[-1])
                    # Block by website domain so same company ≠ re-emailed via different address
                    if _w:
                        _wd = str(_w).strip().lower().replace("https://","").replace("http://","").replace("www.","").split("/")[0]
                        if _wd and "." in _wd:
                            ever_domains.add(_wd)
                    # Block by normalized company name — catches same company, different email/domain
                    if _c:
                        _nc = _norm_company(_c)
                        if _nc:
                            ever_companies.add(_nc)
            _conn.close()
    except Exception as _ex:
        print(f"[BATCH] DB dedup load error (non-fatal): {_ex}", flush=True)

    # 2. Also load sent_log.csv as backup
    try:
        if os.path.exists(SENT_LOG):
            sl = pd.read_csv(SENT_LOG, dtype=str).fillna("")
            if "email" in sl.columns:
                for _e in sl.loc[sl.get("success", sl.get("status","")) == "True", "email"].str.lower().str.strip():
                    ever_sent.add(_e)
                    if "@" in _e:
                        ever_domains.add(_e.split("@")[-1])
    except Exception:
        pass

    # 3. Opt-outs add to domain block too
    for _e in opt_outs:
        if "@" in _e:
            ever_domains.add(_e.split("@")[-1])

    print(f"[BATCH] Dedup wall: {len(ever_sent)} emails, {len(ever_domains)} domains blocked", flush=True)

    seen_emails = set()
    rows = []
    for i, row in pending.iterrows():
        email_key   = str(row["email"]).strip().lower()
        domain_key  = email_key.split("@")[-1] if "@" in email_key else ""
        company_key = _norm_company(row.get("company", "") or "")

        # Skip role addresses — #1 cause of bounces
        if _is_role_address(email_key):
            df.at[i, "status"] = "skipped"
            continue

        already_contacted = (
            email_key in opt_outs
            or email_key in ever_sent
            or domain_key in ever_domains
            or (company_key and company_key in ever_companies)
        )
        if already_contacted:
            df.at[i, "status"] = "sent"
        elif email_key not in seen_emails:
            seen_emails.add(email_key)
            if domain_key:
                ever_domains.add(domain_key)
            if company_key:
                ever_companies.add(company_key)
            rows.append((i, row))
        else:
            df.at[i, "status"] = "skipped"
    save_data(df)
    df = load_data()
    rows = rows[:cap]

    sent_indexes = []

    def _send_one(item):
        i, row = item
        email = str(row["email"]).strip().lower()
        # Check SendGrid suppression lists before attempting send
        if _is_sendgrid_suppressed(email):
            print(f"[BATCH] Suppressed (bounce/spam/unsub): {email}", flush=True)
            return i, False
        time.sleep(1.5)  # ~33 emails/min max — avoids burst-spam flags
        ok = send_email(
            row["email"], row.get("name", ""), row.get("company", ""),
            row["message"], row.get("subject", "")
        )
        return i, ok

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_send_one, r): r for r in rows}
        for future in as_completed(futures):
            try:
                i, ok = future.result()
                if ok:
                    with lock:
                        sent_indexes.append(i)
                        batch_sent_count += 1
            except Exception as e:
                print(f"[BATCH] thread error: {e}", flush=True)

    df2 = load_data()
    for i in sent_indexes:
        if i < len(df2):
            df2.at[i, "status"] = "sent"
    save_data(df2)

    print(f"[BATCH] Done — {batch_sent_count} sent", flush=True)
    batch_running = False
    _batch_started_at = 0.0


# =========================
# FETCH GRANTS FROM GRANT AGENT API
# =========================
def fetch_grants(limit=20):
    # Try grant agent (Python FastAPI) first — has scored DB grants
    try:
        resp = requests.get(f"{URL_GRANTS}/api/grants?min_score=0&limit={limit}", timeout=8)
        if resp.status_code == 200:
            grants = resp.json().get("grants", [])
            if grants:
                return grants
    except Exception as e:
        print(f"[Grants] Grant agent fetch failed: {e}")

    # Fallback: voice server always returns curated grants even if DB is empty
    try:
        resp = requests.get(f"{URL_VOICE_SERVER}/api/grants?limit={limit}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("grants", [])
    except Exception as e:
        print(f"[Grants] Voice server fallback failed: {e}")

    return []


# =========================
# DASHBOARD UI — UNIFIED
# =========================
@app.route('/')
def dashboard():
    from flask import request as flask_request
    active_tab = flask_request.args.get('tab', 'outreach')

    df = load_data()

    pending_count     = len(df[df["status"] == "pending"])
    sent_count        = len(df[df["status"] == "sent"])
    skipped_count     = len(df[df["status"] == "skipped"])
    sent_today        = count_sent_today()
    daily_remaining   = max(0, DAILY_EMAIL_LIMIT - sent_today)
    social_table_html = build_social_table()

    # Load Upwork scouted opportunities
    _upwork_opps = []
    _upwork_opp_file = os.path.join(DATA_DIR, "upwork_opportunities.json")
    try:
        import json as _json
        if os.path.exists(_upwork_opp_file):
            _upwork_opps = _json.loads(open(_upwork_opp_file).read())
    except Exception:
        pass

    def _build_upwork_jobs_html(opps):
        if not opps:
            return "<p style='color:#64748b;padding:20px 0;'>Scout running — jobs appear here every 2 hours. Use the Paste Job tool below to score and draft instantly.</p>"
        rows = ""
        for o in opps[:15]:
            clr = "#22c55e" if o.get("score", 0) >= 75 else "#f59e0b" if o.get("score", 0) >= 55 else "#ef4444"
            safe_proposal = o.get("proposal", "").replace("`", "'").replace("\\", "\\\\").replace("\n", "\\n")
            rows += f"""
            <div style='background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;margin-bottom:12px;'>
              <div style='display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:8px;'>
                <a href='{o.get("link","#")}' target='_blank' style='color:#38bdf8;font-weight:600;font-size:14px;text-decoration:none;flex:1;'>{o.get("title","Untitled")[:90]}</a>
                <span style='background:{clr};color:#000;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;white-space:nowrap;'>Score: {o.get("score",0)}/100</span>
              </div>
              <p style='color:#94a3b8;font-size:12px;margin:0 0 10px 0;'>{o.get("description","")[:220]}...</p>
              <div style='display:flex;gap:8px;flex-wrap:wrap;'>
                <button onclick='copyProposal(this, `{safe_proposal}`)' style='background:#0ea5e9;color:#fff;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer;'>Copy Proposal</button>
                <a href='{o.get("link","#")}' target='_blank' style='background:#22c55e;color:#000;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:700;text-decoration:none;'>Apply on Upwork</a>
                <span style='color:#64748b;font-size:11px;align-self:center;'>Boost: 15-20 connects for top visibility</span>
              </div>
              <details style='margin-top:10px;'>
                <summary style='color:#64748b;cursor:pointer;font-size:12px;'>View full proposal</summary>
                <pre style='background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;font-size:12px;white-space:pre-wrap;margin-top:8px;border:1px solid #334155;'>{o.get("proposal","")}</pre>
              </details>
            </div>"""
        return rows

    _upwork_jobs_html = _build_upwork_jobs_html(_upwork_opps)

    status_text = '<span style="color:#22c55e">Scraping leads now...</span>' if pipeline_running else (
        f"Last run: {fmt_pacific(last_run_time)}" if last_run_time else "Starting soon..."
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300;url=/?tab={active_tab}">
<title>Gray Horizons — Command Center</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  html,body{{height:100%;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;overflow-x:hidden;}}
  .header{{background:#020617;padding:12px 16px;text-align:center;font-size:18px;font-weight:bold;border-bottom:1px solid #1e293b;}}
  /* Nav — scrollable on mobile */
  .nav{{display:flex;background:#020617;border-bottom:2px solid #1e293b;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;scrollbar-width:none;}}
  .nav::-webkit-scrollbar{{display:none;}}
  .nav a{{padding:10px 16px;color:#64748b;font-size:13px;text-decoration:none;cursor:pointer;border-bottom:3px solid transparent;display:inline-block;flex-shrink:0;}}
  .nav a.active{{color:#38bdf8;border-bottom:3px solid #38bdf8;font-weight:bold;}}
  .nav a.grants-tab{{color:#a78bfa;}}
  .nav a.grants-tab.active{{color:#a78bfa;border-bottom:3px solid #a78bfa;}}
  .topbar{{display:flex;justify-content:space-between;align-items:center;padding:8px 16px;background:#020617;border-bottom:1px solid #1e293b;flex-wrap:wrap;gap:6px;}}
  .stats{{display:flex;gap:12px;font-size:12px;color:#94a3b8;flex-wrap:wrap;}}
  .stat-val{{color:#38bdf8;font-weight:bold;}}
  .btn-link{{background:#3b82f6;color:white;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;}}
  .btn-link:hover{{background:#2563eb;}}
  .tab-content{{display:none;}}
  .tab-content.active{{display:block;}}

  /* Outreach cards */
  .card{{background:#1e293b;padding:16px;margin:12px auto;width:94%;max-width:720px;border-radius:10px;}}
  .card-title{{font-size:16px;color:#38bdf8;font-weight:bold;}}
  .card-sub{{color:#94a3b8;font-size:12px;margin:4px 0 8px;}}
  .card-msg{{line-height:1.6;font-size:13px;word-break:break-word;}}
  .btn-send{{background:#22c55e;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;}}
  .btn-skip{{background:#ef4444;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;display:inline-block;margin-top:10px;margin-left:8px;}}
  .btn-disabled{{background:#475569;color:#94a3b8;border:none;padding:9px 16px;border-radius:6px;font-size:13px;margin-top:10px;}}
  .note{{text-align:center;font-size:11px;color:#475569;padding:6px;}}
  .niche-filters{{display:flex;gap:8px;flex-wrap:wrap;padding:10px 16px;background:#020617;border-bottom:1px solid #1e293b;}}
  .nf-btn{{background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:6px 14px;border-radius:20px;cursor:pointer;font-size:12px;font-weight:600;}}
  .nf-btn:hover{{background:#334155;color:#e2e8f0;}}
  .nf-btn.active{{background:#38bdf8;color:#000;border-color:#38bdf8;}}
  .niche-badge{{font-size:10px;font-weight:bold;padding:2px 8px;border-radius:10px;text-transform:uppercase;}}
  .niche-hoa{{background:#1e3a5f;color:#60a5fa;}}
  .niche-hvac{{background:#1a2e1a;color:#4ade80;}}
  .niche-dental{{background:#2d1a3a;color:#c084fc;}}
  .niche-plumbing{{background:#2a1f0a;color:#fbbf24;}}
  .niche-contractor{{background:#2a1515;color:#f87171;}}
  .niche-roofing{{background:#1a1a2e;color:#818cf8;}}
  .niche-landscaping{{background:#0f2a1a;color:#34d399;}}

  /* Grant iframe wrapper */
  .grants-iframe-wrap{{position:relative;width:100%;height:calc(100vh - 90px);overflow:auto;-webkit-overflow-scrolling:touch;}}
  .grants-iframe-wrap iframe{{width:100%;height:100%;border:none;display:block;}}
  /* Mobile fallback — shown only on small screens */
  .grants-mobile-fallback{{display:none;padding:32px 20px;text-align:center;}}
  .grants-mobile-fallback a{{display:inline-block;background:#7c3aed;color:white;padding:14px 28px;border-radius:8px;font-size:15px;font-weight:bold;text-decoration:none;margin-top:12px;}}
  @media(max-width:640px){{
    .grants-iframe-wrap{{display:none;}}
    .grants-mobile-fallback{{display:block;}}
    .header{{font-size:15px;padding:10px;}}
    .nav a{{padding:8px 12px;font-size:12px;}}
    .card{{padding:14px;}}
    .topbar{{padding:8px 12px;}}
    .stats{{gap:8px;font-size:11px;}}
  }}

  /* Grants table (legacy, kept for reference) */
  .grants-wrap{{padding:16px 20px;}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold;}}
  .badge-high{{background:#14532d;color:#4ade80;}}
  .badge-med{{background:#1e3a5f;color:#60a5fa;}}
  .badge-low{{background:#2d1b69;color:#a78bfa;}}
  .grant-name{{color:#e2e8f0;font-weight:bold;max-width:260px;}}
  .grant-agency{{color:#64748b;font-size:11px;}}
  .no-grants{{text-align:center;color:#475569;padding:40px;font-size:14px;}}
  .scan-btn{{background:#7c3aed;color:white;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;}}
  .scan-btn:hover{{background:#6d28d9;}}
</style>
</head>
<body>
<div class="header">Gray Horizons Enterprise | Command Center</div>

{'<div style="background:#060a12;border-bottom:1px solid #1f2937;padding:6px 24px;display:flex;align-items:center;gap:6px;"><span style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-right:8px;">Dashboard</span><a href="' + EDGE_ENGINE_URL + '" style="padding:4px 12px;border-radius:5px;font-size:10px;font-weight:700;text-decoration:none;background:transparent;color:#6b7280;border:1px solid #1f2937;" target="_blank">Edge Engine</a><span style="padding:4px 12px;border-radius:5px;font-size:10px;font-weight:700;background:#06b6d4;color:#000;border:1px solid #06b6d4;">Outreach</span></div>' if EDGE_ENGINE_URL else ''}

<div class="nav">
  <a onclick="showTab('outreach')" id="tab-outreach" class="{'active' if active_tab=='outreach' else ''}">Outreach ({pending_count} pending)</a>
  <a onclick="showTab('social')"   id="tab-social"   class="{'active' if active_tab=='social' else ''}" style="color:#f97316;">Social Pipeline</a>
  <a onclick="showTab('grants')"   id="tab-grants"   class="grants-tab {'active' if active_tab=='grants' else ''}">💰 Grant Agent</a>
  <a onclick="showTab('twitter')"  id="tab-twitter"  class="{'active' if active_tab=='twitter' else ''}" style="color:#1d9bf0;font-weight:bold;">🐦 Twitter</a>
  <a onclick="showTab('upwork')"  id="tab-upwork"  class="{'active' if active_tab=='upwork' else ''}" style="color:#14a800;font-weight:bold;">💼 Upwork ({len(_upwork_opps)} jobs)</a>
  <a href="/status" style="color:#22c55e;font-weight:bold;">⚡ System Status</a>
  <a href="/trigger-pipeline" style="color:#f97316;font-weight:bold;" onclick="return confirm('Run pipeline now to fetch fresh leads?')">▶ Run Pipeline Now</a>
  <a href="/purge-bounced" style="color:#ef4444;font-weight:bold;" onclick="return confirm('Purge all role/generic emails (info@, service@, hello@) from queue? This fixes your 26.7% bounce rate.')">🧹 Purge Bounced</a>
  <a href="/dedup-queue" style="color:#f59e0b;font-weight:bold;" onclick="return confirm('Remove all duplicate emails from the queue CSV?')">🔁 Dedup Queue</a>
  <a href="/activate-leads" style="color:#22c55e;font-weight:bold;" onclick="return confirm('Activate all blank-status leads in outreach_queue.csv? This will unlock ~28,000 pending leads.')">⚡ Activate Leads</a>
  <a href="/blast-signals-now" style="color:#a78bfa;font-weight:bold;" onclick="return confirm('Send signals blast to all unsent leads in signals_queue.csv now?')">📡 Blast Signals</a>
  <a href="/test-linkedin" style="color:#0ea5e9;font-weight:bold;">🔗 Test LinkedIn</a>
</div>

<!-- OUTREACH TAB -->
<div id="content-outreach" class="tab-content {'active' if active_tab=='outreach' else ''}">
  <div class="topbar">
    <div style="font-size:12px;color:#64748b;">{status_text}</div>
    <div class="stats">
      <span>Pending: <span class="stat-val">{pending_count}</span></span>
      <span>Sent: <span class="stat-val">{sent_count}</span></span>
      <span>Skipped: <span class="stat-val">{skipped_count}</span></span>
      <span>Today: <span class="stat-val" style="color:#f97316;">{sent_today}/{DAILY_EMAIL_LIMIT}</span></span>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a href="/send-batch" class="btn-link" style="background:{'#475569' if batch_running else '#f97316'};color:{'#94a3b8' if batch_running else '#000'};font-weight:bold;">{'Sending...' if batch_running else f'Send {daily_remaining} Now'}</a>
      <a href="/send-batch-1k" class="btn-link" style="background:{'#475569' if batch_running else '#16a34a'};color:#fff;font-weight:bold;">{'Sending...' if batch_running else 'Blast 1,000'}</a>
      <a href="/send-batch-5k" class="btn-link" style="background:{'#475569' if batch_running else '#dc2626'};color:#fff;font-weight:bold;">{'Sending...' if batch_running else 'Blast 5,000'}</a>
      <a href="/upload-queue" class="btn-link" style="background:#22c55e;color:#000;font-weight:bold;">Upload Leads</a>
      <a href="/sent" class="btn-link" style="background:#7c3aed;">View Sent</a>
      <a href="/resend-failed" class="btn-link" style="background:#f59e0b;color:#000;">Resend Failed</a>
      <a href="/rebuild-queue" class="btn-link" style="background:#06b6d4;color:#000;font-weight:bold;">Rebuild Queue</a>
      <a href="/opt-out" class="btn-link" style="background:#7f1d1d;color:#fca5a5;font-weight:bold;">+ Opt-Out</a>
      <a href="/run-all-engines" class="btn-link" style="background:#7c3aed;color:#fff;font-weight:bold;">Run All Engines</a>
      <a href="/refresh" class="btn-link">{'Scraping...' if pipeline_running else 'Refresh Leads'}</a>
    </div>
  </div>
  <div class="note">{len(df)} total leads · auto-refreshes every 5 min</div>
  <div class="niche-filters">
    <button class="nf-btn active" onclick="filterNiche('all',this)">All Niches</button>
    <button class="nf-btn" onclick="filterNiche('hoa',this)">HOA</button>
    <button class="nf-btn" onclick="filterNiche('hvac',this)">HVAC</button>
    <button class="nf-btn" onclick="filterNiche('dental',this)">Dental</button>
    <button class="nf-btn" onclick="filterNiche('plumbing',this)">Plumbing</button>
    <button class="nf-btn" onclick="filterNiche('contractor',this)">Contractor</button>
    <button class="nf-btn" onclick="filterNiche('roofing',this)">Roofing</button>
    <button class="nf-btn" onclick="filterNiche('landscaping',this)">Landscaping</button>
  </div>
"""

    # Empty state when nothing is pending
    pending_rows = df[df["status"] == "pending"]
    if len(pending_rows) == 0:
        scraping_msg = "Pipeline is scraping new leads now — check back in a few minutes." if pipeline_running else "No pending leads. Click Refresh Leads to scrape new ones."
        html += f"""
  <div style="text-align:center;padding:60px 20px;color:#64748b;">
    <div style="font-size:2rem;margin-bottom:12px;">{'⏳' if pipeline_running else '🔄'}</div>
    <div style="font-size:16px;color:#94a3b8;margin-bottom:8px;">{scraping_msg}</div>
    <div style="font-size:13px;">Sent: {sent_count} · Skipped: {skipped_count}</div>
  </div>"""

    # Outreach lead cards
    for i, row in df.iterrows():
        if row["status"] != "pending":
            continue
        name    = row.get("name", "") or "Contact"
        company = row.get("company", "") or "Unknown Company"
        email   = row.get("email", "")
        niche   = str(row.get("niche", "hoa") or "hoa").strip().lower()
        html += f"""
  <div class="card" data-niche="{niche}">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div class="card-title">{company}</div>
      <span class="niche-badge niche-{niche}">{niche.upper()}</span>
    </div>
    <div class="card-sub">{email if email else '❌ No Email'}</div>
    <div class="card-msg">{format_message(row["message"])}</div>
    <div style="border-top:1px solid #334155;margin:10px 0 8px;padding-top:8px;font-size:12px;color:#64748b;line-height:1.7;">
      Gray Horizons Enterprise<br>
      <a href="https://grayhorizonsenterprise.com" style="color:#38bdf8;text-decoration:none;">grayhorizonsenterprise.com</a>
    </div>
    <div>"""
        if email:
            html += f'<a href="/send/{i}" class="btn-send">Send</a>'
        else:
            html += '<button class="btn-disabled">No Email</button>'
        html += f'<a href="/skip/{i}" class="btn-skip">Skip</a>'
        html += '</div></div>'

    html += "</div><!-- end outreach tab -->\n"

    # GRANTS TAB — full grant agent embedded as iframe (desktop) + link (mobile)
    html += f"""
<!-- GRANTS TAB -->
<div id="content-grants" class="tab-content {'active' if active_tab=='grants' else ''}">
  <!-- Desktop: full embedded grant agent -->
  <div class="grants-iframe-wrap">
    <iframe
      id="grants-iframe"
      src="{URL_GRANTS}"
      title="Grant Agent System"
      loading="lazy"
      allowfullscreen
    ></iframe>
  </div>
  <!-- Mobile: tap to open in full browser -->
  <div class="grants-mobile-fallback">
    <div style="font-size:32px;margin-bottom:12px;">💰</div>
    <div style="font-size:18px;font-weight:bold;color:#a78bfa;margin-bottom:8px;">Grant Agent System</div>
    <div style="color:#94a3b8;font-size:14px;margin-bottom:20px;">12 curated grants · SBIR · MBDA · SBA 8(a) · Google Black Founders Fund</div>
    <a href="{URL_GRANTS}" target="_blank">Open Grant Agent ↗</a>
    <div style="color:#475569;font-size:12px;margin-top:16px;">Opens full dashboard with scan, apply, and AI application tools</div>
  </div>
</div><!-- end grants tab -->

<!-- SOCIAL PIPELINE TAB -->
<div id="content-social" class="tab-content {'active' if active_tab=='social' else ''}">
  <div style="max-width:780px;margin:0 auto;padding:20px 16px;">

    <!-- MESSAGE TEMPLATES -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px;font-weight:bold;color:#f97316;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;">Message Templates — Click to Copy</div>

      <div style="background:#1e293b;border-radius:10px;padding:16px;margin-bottom:12px;border-left:3px solid #38bdf8;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <span style="font-size:11px;font-weight:bold;color:#38bdf8;text-transform:uppercase;">Message 1 — Cold Comment / DM</span>
          <button onclick="copyMsg('msg1')" style="background:#38bdf8;color:#000;border:none;padding:4px 12px;border-radius:5px;font-size:11px;font-weight:bold;cursor:pointer;">Copy</button>
        </div>
        <div id="msg1" style="font-size:13px;line-height:1.7;color:#e2e8f0;white-space:pre-wrap;">Saw your post — quick question

Are you trying to get customers from your content or just views?

I focus specifically on content that brings in customers.

Want a quick example?</div>
      </div>

      <div style="background:#1e293b;border-radius:10px;padding:16px;margin-bottom:12px;border-left:3px solid #22c55e;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <span style="font-size:11px;font-weight:bold;color:#22c55e;text-transform:uppercase;">Message 2 — After They Reply (attach clip)</span>
          <button onclick="copyMsg('msg2')" style="background:#22c55e;color:#000;border:none;padding:4px 12px;border-radius:5px;font-size:11px;font-weight:bold;cursor:pointer;">Copy</button>
        </div>
        <div id="msg2" style="font-size:13px;line-height:1.7;color:#e2e8f0;white-space:pre-wrap;">Here's a quick example 👇

This is the type of content we use to drive attention + customers.

We can set this up for you within a few days.

👇 [attach clip from READY_TO_UPLOAD folder]</div>
      </div>

      <div style="background:#1e293b;border-radius:10px;padding:16px;margin-bottom:12px;border-left:3px solid #f97316;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <span style="font-size:11px;font-weight:bold;color:#f97316;text-transform:uppercase;">Message 3 — Close</span>
          <button onclick="copyMsg('msg3')" style="background:#f97316;color:#000;border:none;padding:4px 12px;border-radius:5px;font-size:11px;font-weight:bold;cursor:pointer;">Copy</button>
        </div>
        <div id="msg3" style="font-size:13px;line-height:1.7;color:#e2e8f0;white-space:pre-wrap;">We usually start at $1,000–$2,000 depending on volume.

If you're ready, we can get started today.</div>
      </div>
    </div>

    <!-- ADD PROSPECT -->
    <div style="background:#1e293b;border-radius:10px;padding:16px;margin-bottom:20px;">
      <div style="font-size:13px;font-weight:bold;color:#f97316;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">Track a Prospect</div>
      <form method="POST" action="/social/add" style="display:flex;gap:8px;flex-wrap:wrap;">
        <input name="handle"   placeholder="@handle or name"  required style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:8px 10px;font-size:13px;flex:1;min-width:130px;">
        <input name="platform" placeholder="TikTok / YouTube" required style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:8px 10px;font-size:13px;width:120px;">
        <input name="email"    placeholder="email (auto-queues outreach)" style="background:#0f172a;color:#e2e8f0;border:1px solid #f97316;border-radius:6px;padding:8px 10px;font-size:13px;flex:2;min-width:180px;">
        <input name="notes"    placeholder="notes"             style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:8px 10px;font-size:13px;flex:1;min-width:100px;">
        <button type="submit" style="background:#f97316;color:#000;border:none;padding:8px 18px;border-radius:6px;font-size:13px;font-weight:bold;cursor:pointer;">Add</button>
      </form>
      <div style="font-size:11px;color:#475569;margin-top:6px;">Tip: add their email and it auto-queues in the Email Outreach system too.</div>
    </div>

    <!-- PIPELINE TABLE -->
    <div style="font-size:13px;font-weight:bold;color:#f97316;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Pipeline</div>
    {social_table_html}

    <!-- DAILY TARGETS -->
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;margin-top:20px;font-size:12px;color:#64748b;line-height:1.8;">
      <span style="color:#f97316;font-weight:bold;">Daily targets:</span>
      50-100 comments posted &nbsp;·&nbsp;
      10-20 replies expected &nbsp;·&nbsp;
      3-5 email leads &nbsp;·&nbsp;
      2-4 closes/week &nbsp;·&nbsp;
      <span style="color:#22c55e;">$2k–$6k/month</span>
    </div>
  </div>
</div><!-- end social tab -->

<script>
function copyMsg(id) {{
  var el = document.getElementById(id);
  var text = el.innerText;
  navigator.clipboard.writeText(text).then(function() {{
    var btn = el.previousElementSibling.querySelector('button');
    var orig = btn.innerText;
    btn.innerText = 'Copied!';
    setTimeout(function(){{ btn.innerText = orig; }}, 1500);
  }});
}}
</script>

<script>
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(function(el){{ el.classList.remove('active'); }});
  document.querySelectorAll('.nav a[id^="tab-"]').forEach(function(el){{ el.classList.remove('active'); }});
  document.getElementById('content-' + name).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'twitter') {{ loadTwitterSuggestions(); }}
}}

function loadTwitterSuggestions() {{
  fetch('/twitter-suggestions-json')
    .then(r => r.json())
    .then(data => {{ renderTwitterCards(data); }})
    .catch(e => console.log('Twitter load error', e));
}}

function renderTwitterCards(suggestions) {{
  var container = document.getElementById('twitter-cards');
  if (!suggestions || suggestions.length === 0) {{
    container.innerHTML = '<div style="color:#475569;padding:20px;text-align:center;">No suggestions yet. Click Fetch Tweets to load opportunities.</div>';
    return;
  }}
  var html = '';
  suggestions.forEach(function(s) {{
    var choices = s.reply_choices || [];
    var choiceHtml = '';
    choices.forEach(function(c, i) {{
      var colors = ['#1d4ed8','#7c3aed','#0f766e','#b45309'];
      var labels = ['Value Add','Ask Question','Authority','Product Hook'];
      choiceHtml += '<button onclick="postReply(\\'' + s.tweet_id + '\\',\\'' + encodeURIComponent(c) + '\\')" style="background:' + colors[i] + ';color:#fff;border:none;padding:7px 12px;border-radius:6px;cursor:pointer;font-size:12px;margin:4px 4px 4px 0;">' + labels[i] + '</button>';
    }});
    html += '<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:14px 16px;margin:10px 0;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
      '<span style="color:#1d9bf0;font-weight:bold;font-size:13px;">@' + (s.author||'') + '</span>' +
      '<span style="color:#475569;font-size:12px;">❤ ' + (s.likes||0) + ' &nbsp; 🔁 ' + (s.retweets||0) + '</span>' +
      '</div>' +
      '<div style="color:#94a3b8;font-size:13px;line-height:1.5;margin-bottom:10px;">' + (s.tweet_text||'').substring(0,180) + '...</div>' +
      '<div style="margin-bottom:10px;">' + choiceHtml + '</div>' +
      '<div id="reply-status-' + s.tweet_id + '" style="font-size:12px;color:#22c55e;display:none;">Posted!</div>' +
      '<a href="' + (s.tweet_url||'#') + '" target="_blank" style="font-size:12px;color:#475569;text-decoration:none;">View tweet ↗</a>' +
      '</div>';
  }});
  container.innerHTML = html;
}}

function postReply(tweetId, encodedComment) {{
  var comment = decodeURIComponent(encodedComment);
  var statusEl = document.getElementById('reply-status-' + tweetId);
  fetch('/post-twitter-reply', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{tweet_id: tweetId, comment: comment}})
  }}).then(r => r.json()).then(data => {{
    if (statusEl) {{
      statusEl.style.display = 'block';
      statusEl.textContent = data.ok ? 'Reply posted!' : 'Failed: ' + (data.error||'unknown');
      statusEl.style.color = data.ok ? '#22c55e' : '#ef4444';
    }}
  }}).catch(e => {{
    if (statusEl) {{ statusEl.style.display='block'; statusEl.textContent='Error: '+e; statusEl.style.color='#ef4444'; }}
  }});
}}

function triggerFollow() {{
  var max = document.getElementById('follow-max').value || 20;
  var terms = document.getElementById('follow-terms').value || '';
  fetch('/twitter-auto-follow?max=' + max + '&terms=' + encodeURIComponent(terms))
    .then(r => r.json())
    .then(data => {{
      document.getElementById('follow-status').textContent = 'Followed ' + (data.new_follows||0) + ' new accounts.';
    }});
}}

function fetchTweets() {{
  document.getElementById('twitter-cards').innerHTML = '<div style="color:#94a3b8;padding:20px;text-align:center;">Fetching tweet opportunities...</div>';
  fetch('/twitter-fetch-suggestions')
    .then(r => r.json())
    .then(data => {{ renderTwitterCards(data); }})
    .catch(e => {{ document.getElementById('twitter-cards').innerHTML = '<div style="color:#ef4444;padding:20px;">Error fetching tweets.</div>'; }});
}}

function filterNiche(niche, btn) {{
  document.querySelectorAll('.nf-btn').forEach(function(b){{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(function(card) {{
    if (niche === 'all' || card.dataset.niche === niche) {{
      card.style.display = '';
    }} else {{
      card.style.display = 'none';
    }}
  }});
}}
</script>

<!-- TWITTER TAB -->
<div id="content-twitter" class="tab-content {'active' if active_tab=='twitter' else ''}">
  <div style="max-width:760px;margin:0 auto;padding:20px 16px;">

    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <div>
        <div style="font-size:18px;font-weight:bold;color:#1d9bf0;">Twitter Growth Center</div>
        <div style="font-size:12px;color:#475569;margin-top:2px;">Reply to trending posts, grow followers, post content</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button onclick="fetchTweets()" style="background:#1d9bf0;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold;">Fetch Tweet Opportunities</button>
        <a href="/twitter-post-now" style="background:#22c55e;color:#000;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:bold;text-decoration:none;">Post Now</a>
      </div>
    </div>

    <!-- Auto-Follow Controls -->
    <div style="background:#1e293b;border-radius:10px;padding:16px;margin-bottom:16px;">
      <div style="font-size:14px;font-weight:bold;color:#94a3b8;margin-bottom:12px;">Auto-Follow Settings</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;">
        <div>
          <div style="font-size:11px;color:#475569;margin-bottom:4px;">Max follows per run</div>
          <input id="follow-max" type="number" value="20" min="1" max="50"
            style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px 10px;width:80px;font-size:13px;">
        </div>
        <div style="flex:1;min-width:200px;">
          <div style="font-size:11px;color:#475569;margin-bottom:4px;">Search terms (comma separated, leave blank for defaults)</div>
          <input id="follow-terms" type="text" placeholder="e.g. trading signals, RSI stocks, position sizing"
            style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px 10px;width:100%;font-size:13px;">
        </div>
        <button onclick="triggerFollow()" style="background:#7c3aed;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold;">Run Auto-Follow</button>
      </div>
      <div id="follow-status" style="font-size:12px;color:#22c55e;margin-top:8px;"></div>
      <div style="margin-top:10px;font-size:11px;color:#475569;">
        Default target accounts: TradingView, MarketWatch, unusual_whales, OptionsFlow, CryptoDaily, tastytrade +20 more<br>
        Safe limit: 20 follows/day on free API tier
      </div>
    </div>

    <!-- Reply Choice Explanation -->
    <div style="background:#1e293b;border-radius:10px;padding:12px 16px;margin-bottom:16px;display:flex;gap:10px;flex-wrap:wrap;">
      <div style="font-size:12px;color:#94a3b8;">Reply styles:</div>
      <span style="background:#1d4ed8;color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;">Value Add — share insight</span>
      <span style="background:#7c3aed;color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;">Ask Question — drive engagement</span>
      <span style="background:#0f766e;color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;">Authority — position as expert</span>
      <span style="background:#b45309;color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;">Product Hook — subtle mention</span>
    </div>

    <!-- Tweet Cards -->
    <div id="twitter-cards">
      <div style="color:#475569;padding:40px;text-align:center;">Click "Fetch Tweet Opportunities" to load trending posts to reply to.</div>
    </div>

  </div>
</div><!-- end twitter tab -->

<!-- UPWORK TAB -->
<div id="content-upwork" class="tab-content {'active' if active_tab=='upwork' else ''}">
  <div style="max-width:860px;margin:0 auto;padding:20px 16px;">

    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
      <div>
        <div style="font-size:18px;font-weight:bold;color:#14a800;">Upwork Job Board</div>
        <div style="font-size:12px;color:#64748b;margin-top:2px;">Auto-scouted every 2 hours. Copy proposal, boost 15-20 connects, click Apply.</div>
      </div>
      <div style="display:flex;gap:8px;">
        <a href="https://www.upwork.com/nx/find-work/" target="_blank" style="background:#14a800;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:700;text-decoration:none;">Browse Upwork</a>
        <a href="https://www.upwork.com/nx/plans/connects/purchase/" target="_blank" style="background:#1e293b;color:#14a800;border:1px solid #14a800;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:700;text-decoration:none;">Buy Connects</a>
      </div>
    </div>

    <!-- Connects guide -->
    <div style="background:#1e293b;border-left:4px solid #14a800;border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:20px;font-size:13px;color:#94a3b8;">
      <strong style="color:#14a800;">Connect Boost Strategy:</strong> Standard apply = 6 connects. Boost to top = 15-20 connects. Only boost on jobs posted under 2 hours old with under 15 proposals. Score 75+ = apply immediately.
    </div>

    <!-- Scouted Jobs -->
    <div style="font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:12px;">Auto-Scouted Jobs ({len(_upwork_opps)} found)</div>
    {_upwork_jobs_html}

    <hr style="border-color:#1e293b;margin:28px 0;">

    <!-- Paste Job Drafter -->
    <div style="font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:8px;">Paste Any Job Description</div>
    <p style="color:#64748b;font-size:12px;margin-bottom:12px;">Paste a job from Upwork. System scores it and writes your proposal instantly.</p>
    <form method="POST" action="/upwork-draft" target="_blank">
      <textarea name="job_text" rows="8" placeholder="Paste full job description here..."
        style="width:100%;background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:12px;font-size:14px;resize:vertical;"></textarea>
      <div style="margin-top:10px;">
        <button type="submit" style="background:#14a800;color:#fff;border:none;padding:10px 28px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;">Score + Draft Proposal</button>
      </div>
    </form>

  </div>
</div><!-- end upwork tab -->

<script>
function copyProposal(btn, text) {{
  var decoded = text.replace(/\\n/g, '\n');
  navigator.clipboard.writeText(decoded).then(function() {{
    btn.textContent = 'Copied!';
    btn.style.background = '#22c55e';
    btn.style.color = '#000';
    setTimeout(function() {{ btn.textContent = 'Copy Proposal'; btn.style.background = '#0ea5e9'; btn.style.color = '#fff'; }}, 2000);
  }});
}}
</script>

</script>
</body>
</html>"""

    return html

# =========================
# SEND ACTION
# =========================
@app.route('/send/<int:index>')
def send(index):
    df = load_data()

    if index >= len(df):
        return redirect('/')

    row = df.loc[index]

    send_email(
        row["email"],
        row["name"],
        row["company"],
        row["message"],
        row.get("subject", ""),
    )

    df.at[index, "status"] = "sent"
    save_data(df)

    return redirect('/')

# =========================
# SKIP ACTION
# =========================
@app.route('/skip/<int:index>')
def skip(index):
    df = load_data()

    if index < len(df):
        df.at[index, "status"] = "skipped"
        save_data(df)

    return redirect('/')

# =========================
# SENT LOG VIEW
# =========================
@app.route('/sent')
def sent_log_view():
    rows = []
    if os.path.exists(SENT_LOG):
        try:
            log_df = pd.read_csv(SENT_LOG).fillna("")
            rows = log_df.to_dict("records")
        except Exception:
            pass

    # Compute stats for the banner
    total_entries = len(rows)
    sent_count_log = sum(
        1 for r in rows
        if str(r.get("success", r.get("status", ""))).strip().lower()
        in ("true", "1", "smtp", "sendgrid", "gmail-smtp-accepted")
    )
    failed_count_log = sum(
        1 for r in rows
        if str(r.get("success", r.get("status", ""))).strip().lower()
        in ("false", "0", "")
        and str(r.get("error", r.get("note", ""))).strip().lower() not in ("skipped", "no email address found")
    )

    html = f"""
    <style>
        body {{ background:#0f172a; color:white; font-family:Arial; margin:0; }}
        .header {{ text-align:center; padding:20px; font-size:22px; font-weight:bold; background:#020617; }}
        .stats-bar {{ display:flex; gap:16px; justify-content:center; flex-wrap:wrap; padding:16px; background:#020617; border-bottom:1px solid #1e293b; }}
        .stat-box {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:12px 24px; text-align:center; }}
        .stat-num {{ font-size:28px; font-weight:bold; }}
        .stat-lbl {{ font-size:11px; color:#64748b; margin-top:4px; }}
        .notice {{ background:#1e293b; border-left:4px solid #f59e0b; margin:16px auto; width:92%; max-width:860px; padding:12px 16px; border-radius:6px; font-size:13px; color:#cbd5e1; line-height:1.6; }}
        .verify-btn {{ display:block; text-align:center; margin:12px auto; }}
        .verify-btn a {{ background:#22c55e; color:#000; font-weight:bold; padding:10px 28px; border-radius:8px; text-decoration:none; font-size:14px; }}
        .wrap {{ overflow-x:auto; width:96%; margin:20px auto; }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; min-width:900px; }}
        th {{ background:#1e293b; padding:10px; text-align:left; color:#38bdf8; white-space:nowrap; }}
        td {{ padding:9px 10px; border-bottom:1px solid #1e293b; vertical-align:top; }}
        td.err {{ color:#f87171; font-size:12px; max-width:340px; word-break:break-word; white-space:pre-wrap; }}
        .ok   {{ color:#22c55e; font-weight:bold; }}
        .fail {{ color:#ef4444; font-weight:bold; }}
        a.back {{ display:inline-block; margin:8px 12px; color:#38bdf8; }}
    </style>
    <div class="header">Outreach Sent Log</div>
    <div class="stats-bar">
        <div class="stat-box">
            <div class="stat-num" style="color:#22c55e;">{sent_count_log}</div>
            <div class="stat-lbl">Accepted by Gmail SMTP</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#ef4444;">{failed_count_log}</div>
            <div class="stat-lbl">Failed to Send</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#94a3b8;">{total_entries}</div>
            <div class="stat-lbl">Total Log Entries</div>
        </div>
    </div>
    <div class="notice">
        <strong style="color:#f59e0b;">What "SENT" means:</strong>
        Gmail's SMTP server accepted the message — the email left this system successfully.
        Inbox delivery depends on the recipient's spam filters. To get open/click/bounce tracking,
        connect <a href="https://sendgrid.com" target="_blank" style="color:#38bdf8;">SendGrid</a>
        (free tier: 100/day) by adding <code>SENDGRID_API_KEY</code> to your .env file.
        &nbsp;&nbsp;<strong>→</strong>&nbsp;
        <a href="/test-email" style="color:#22c55e;font-weight:bold;">Send live test email to your inbox now</a>
    </div>
    <div style="text-align:center;margin:8px 0;">
        <a class="back" href="/">&#8592; Dashboard</a>
        <a class="back" href="/resend-failed" style="color:#f59e0b;">Resend Failed</a>
        <form method="POST" action="/recycle-failed" style="display:inline;">
            <button type="submit" style="background:#ef4444;color:#fff;border:none;padding:6px 18px;border-radius:6px;font-weight:bold;font-size:13px;cursor:pointer;margin:0 8px;"
                onclick="return confirm('Reset all {failed_count_log} failed emails back to pending queue with fresh messages?')">
                &#9851; Recycle Failed &#8594; Pending
            </button>
        </form>
        <a class="back" href="/test-email" style="color:#22c55e;">&#10003; Send Test Email</a>
    </div>
    """

    if not rows:
        html += '<p style="text-align:center;color:#64748b;">No emails sent yet.</p>'
    else:
        # also check old-format column names (status/note vs success/error)
        html += "<div class='wrap'><table><tr><th>Time</th><th>Company</th><th>Email</th><th>Subject</th><th>Status</th><th>Error / Detail</th><th>Follow Up</th></tr>"
        for r in reversed(rows):
            success_raw = str(r.get("success", r.get("status", ""))).strip().lower()
            error_msg   = str(r.get("error",   r.get("note",   ""))).strip()
            was_sent    = success_raw in ("true", "1", "yes", "smtp", "sendgrid", "gmail-smtp-accepted")
            if was_sent:
                status_cell = '<span class="ok">SENT</span>'
            elif success_raw in ("skipped",):
                status_cell = '<span style="color:#94a3b8;font-weight:bold;">SKIPPED</span>'
            else:
                status_cell = '<span class="fail">FAILED</span>'
            company = str(r.get("company", r.get("company_name", ""))).strip()
            email   = str(r.get("email", "")).strip()
            subject = str(r.get("subject", "")).strip()
            ts      = str(r.get("timestamp", "")).strip()
            import urllib.parse
            social_btn = (
                f'<a href="/social/from-sent?company={urllib.parse.quote(company)}&email={urllib.parse.quote(email)}" '
                f'style="background:#f97316;color:#000;padding:3px 10px;border-radius:5px;font-size:11px;font-weight:bold;text-decoration:none;white-space:nowrap;">Social</a>'
            ) if was_sent else ""
            html += (
                "<tr>"
                "<td style='white-space:nowrap;color:#94a3b8;font-size:11px;'>" + ts + "</td>"
                "<td>" + company + "</td>"
                "<td style='color:#7dd3fc;'>" + email + "</td>"
                "<td style='color:#cbd5e1;font-size:12px;'>" + subject + "</td>"
                "<td>" + status_cell + "</td>"
                "<td class='err'>" + error_msg + "</td>"
                "<td style='padding:8px;'>" + social_btn + "</td>"
                "</tr>"
            )
        html += "</table></div>"

    return html

# =========================
# TEST EMAIL
# =========================
@app.route('/test-email')
def test_email():
    result = send_email(
        to_email="grayhorizonsenterprise@gmail.com",
        name="Gray Horizons Enterprise",
        company="Gray Horizons Enterprise",
        message="This is a test message confirming the outreach system is live and sending correctly."
    )
    status = "SUCCESS" if result else "FAILED — check /sent for error details"
    color  = "#22c55e" if result else "#ef4444"
    return f"""
    <div style="background:#0f172a;color:white;font-family:Arial;min-height:100vh;display:flex;align-items:center;justify-content:center;">
        <div style="text-align:center;">
            <div style="font-size:22px;font-weight:bold;color:{color};margin-bottom:16px;">{status}</div>
            <a href="/" style="color:#38bdf8;">&#8592; Back</a> &nbsp;|&nbsp;
            <a href="/sent" style="color:#38bdf8;">View Sent Log</a>
        </div>
    </div>"""

@app.route('/test-sendgrid')
def test_sendgrid():
    """Diagnose SendGrid: check key validity, sender verification, account status."""
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    sender  = VERIFIED_SENDER
    lines   = []

    if not api_key:
        return "<p style='font-family:Arial;color:red;padding:40px;'>SENDGRID_API_KEY not set in Railway Variables.</p>"

    lines.append(f"API key found: ...{api_key[-6:]}")
    lines.append(f"Sender address: {sender}")

    # 1. Check account / API key validity
    try:
        r = requests.get("https://api.sendgrid.com/v3/user/account",
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        lines.append(f"Account check: HTTP {r.status_code}")
        if r.status_code == 200:
            info = r.json()
            lines.append(f"  Plan: {info.get('type','?')} | Company: {info.get('company','?')}")
        else:
            lines.append(f"  Response: {r.text[:300]}")
    except Exception as e:
        lines.append(f"Account check ERROR: {e}")

    # 2. Check sender verification
    try:
        r2 = requests.get("https://api.sendgrid.com/v3/verified_senders",
                          headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        lines.append(f"Sender verification: HTTP {r2.status_code}")
        if r2.status_code == 200:
            senders = r2.json().get("results", [])
            if senders:
                for s in senders:
                    lines.append(f"  {s.get('from_email')} — verified={s.get('verified')} locked={s.get('locked')}")
            else:
                lines.append("  NO verified senders found — this blocks all sending")
        else:
            lines.append(f"  Response: {r2.text[:300]}")
    except Exception as e:
        lines.append(f"Sender check ERROR: {e}")

    # 3. Send a live test
    try:
        payload = {
            "personalizations": [{"to": [{"email": sender}]}],
            "from": {"email": sender, "name": "Gray Horizons Enterprise"},
            "subject": "SendGrid live test",
            "content": [{"type": "text/plain", "value": "SendGrid test from Gray Horizons dashboard."}]
        }
        r3 = requests.post("https://api.sendgrid.com/v3/mail/send",
                           json=payload,
                           headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                           timeout=15)
        lines.append(f"Live send test: HTTP {r3.status_code}")
        if r3.status_code == 202:
            lines.append("  SUCCESS — check your inbox")
        else:
            lines.append(f"  FAILED: {r3.text[:400]}")
    except Exception as e:
        lines.append(f"Live send ERROR: {e}")

    body = "<br>".join(lines)
    return f"""<div style='background:#0f172a;color:#e2e8f0;font-family:monospace;padding:40px;min-height:100vh;line-height:2;'>
    <h2 style='color:#38bdf8;'>SendGrid Diagnostics</h2>
    {body}<br><br>
    <a href='/' style='color:#38bdf8;'>&#8592; Dashboard</a>
    </div>"""

# =========================
# RESEND FAILED EMAILS
# GET  /resend-failed        — preview page showing what will be resent
# POST /resend-failed        — fire the actual resend batch
# =========================

def _get_failed_emails_from_log():
    """Return set of email addresses that have a failed delivery in sent_log.csv."""
    failed = set()
    if not os.path.exists(SENT_LOG):
        return failed
    try:
        import csv as _csv
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                # Handle both old format (status/note) and new format (success/error)
                success_raw = (
                    row.get("success", "") or
                    row.get("status",  "")
                ).strip().lower()
                email = (row.get("email", "") or "").strip().lower()
                if email and success_raw in ("false", "0", ""):
                    failed.add(email)
    except Exception as e:
        print(f"[resend] Could not parse sent_log: {e}")
    return failed


def _do_resend_batch(dry_run=False):
    """
    Find every queue row whose email appears in the failed-log set, then resend.
    Returns list of result dicts.
    """
    failed_emails = _get_failed_emails_from_log()
    df            = load_data()
    results       = []

    for i, row in df.iterrows():
        email = str(row.get("email", "") or "").strip().lower()
        if not email:
            continue
        # Resend if: email is in the failed set, OR status is "sent" with no prior success
        in_failed_log = email in failed_emails
        was_marked_sent = str(row.get("status", "")).strip().lower() == "sent"
        if not (in_failed_log or was_marked_sent):
            continue

        company = row.get("company", "Unknown")
        name    = row.get("name",    "")
        message = row.get("message", "")

        if dry_run:
            results.append({"email": email, "company": company, "status": "preview — not sent"})
            continue

        ok = send_email(email, name, company, message)
        results.append({
            "email":   email,
            "company": company,
            "status":  "SENT" if ok else "FAILED",
        })
        # Keep queue row as "sent" regardless — delivery status is in sent_log
        df.at[i, "status"] = "sent"

    if not dry_run and results:
        save_data(df)

    return results


@app.route('/resend-failed', methods=["GET"])
def resend_failed_preview():
    """Show a confirmation page listing what will be resent."""
    preview = _do_resend_batch(dry_run=True)
    count   = len(preview)

    rows_html = "".join(
        "<tr><td style='padding:8px;border-bottom:1px solid #1e293b;'>" + r['company'] + "</td>"
        "<td style='padding:8px;border-bottom:1px solid #1e293b;'>" + r['email'] + "</td></tr>"
        for r in preview
    )

    if count == 0:
        body_html = '<p style="color:#22c55e;font-size:15px;">Nothing to resend — no failed emails found.</p>'
    else:
        body_html = (
            '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;">'
            '<tr>'
            '<th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Company</th>'
            '<th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Email</th>'
            '</tr>'
            + rows_html +
            '</table>'
            '<form method="POST" action="/resend-failed">'
            '<button type="submit" style="background:#22c55e;color:white;border:none;'
            'padding:14px 28px;border-radius:8px;font-size:15px;font-weight:bold;'
            'cursor:pointer;width:100%;">Send All ' + str(count) + ' Email(s) Now</button>'
            '</form>'
        )

    return (
        '<div style="background:#0f172a;color:#e2e8f0;font-family:Arial;min-height:100vh;padding:40px 20px;">'
        '<div style="max-width:700px;margin:0 auto;">'
        '<h2 style="color:#f59e0b;margin-bottom:8px;">Resend Failed Emails</h2>'
        '<p style="color:#94a3b8;margin-bottom:24px;">Found <strong style="color:#f59e0b;">'
        + str(count) +
        '</strong> email(s) queued for resend. These previously failed delivery. '
        'Click the button below to send them now via Gmail SMTP.</p>'
        + body_html +
        '<br><br><a href="/" style="color:#38bdf8;">Back to Dashboard</a>'
        '&nbsp;|&nbsp;<a href="/sent" style="color:#38bdf8;">View Sent Log</a>'
        '</div></div>'
    )


@app.route('/resend-failed', methods=["POST"])
def resend_failed_execute():
    """Fire the actual resend batch and show results."""
    results = _do_resend_batch(dry_run=False)
    sent_ok  = [r for r in results if r["status"] == "SENT"]
    failed   = [r for r in results if r["status"] == "FAILED"]

    rows_html = "".join(
        f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">{r['company']}</td>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">{r['email']}</td>
          <td style="padding:8px;border-bottom:1px solid #1e293b;">
            <span style="color:{'#22c55e' if r['status']=='SENT' else '#ef4444'};font-weight:bold;">
              {r['status']}
            </span>
          </td>
        </tr>"""
        for r in results
    )

    summary_color = "#22c55e" if not failed else "#f59e0b"
    summary_text  = (
        f"All {len(sent_ok)} emails sent successfully." if not failed
        else f"{len(sent_ok)} sent · {len(failed)} still failing — check env vars below."
    )

    return f"""
    <div style="background:#0f172a;color:#e2e8f0;font-family:Arial;min-height:100vh;padding:40px 20px;">
      <div style="max-width:700px;margin:0 auto;">
        <h2 style="color:{summary_color};margin-bottom:8px;">Resend Complete</h2>
        <p style="margin-bottom:24px;">{summary_text}</p>

        {'<div style="background:#1e293b;padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:13px;color:#f59e0b;">Still failing? Go to <a href="/debug" style="color:#38bdf8;">/debug</a> and confirm SENDER_EMAIL and SENDER_APP_PASSWORD are set.</div>' if failed else ''}

        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px;">
          <tr>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Company</th>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Email</th>
            <th style="text-align:left;padding:8px;background:#1e293b;color:#38bdf8;">Result</th>
          </tr>
          {rows_html}
        </table>

        <a href="/" style="color:#38bdf8;">← Back to Dashboard</a>
        &nbsp;|&nbsp;
        <a href="/sent" style="color:#38bdf8;">View Sent Log</a>
        &nbsp;|&nbsp;
        <a href="/resend-failed" style="color:#f59e0b;">Resend Again</a>
      </div>
    </div>
    """


# =========================
# RECYCLE FAILED → PENDING
# =========================
@app.route('/recycle-failed', methods=["POST"])
def recycle_failed():
    """Reset all failed sent_log entries back to pending in the queue with fresh messages."""
    import csv as _csv
    from outreach_generator import generate_subject, generate_message

    # 1. Collect failed emails from sent_log
    failed_emails = set()
    clean_rows = []
    if os.path.exists(SENT_LOG):
        try:
            with open(SENT_LOG, newline="", encoding="utf-8") as f:
                for row in _csv.DictReader(f):
                    success_raw = str(row.get("success", row.get("status", ""))).strip().lower()
                    error_msg   = str(row.get("error",   row.get("note",   ""))).strip().lower()
                    was_failed  = success_raw in ("false", "0", "") and error_msg not in ("skipped",)
                    email = str(row.get("email", "")).strip().lower()
                    if was_failed and email:
                        failed_emails.add(email)
                    else:
                        clean_rows.append(row)
        except Exception as e:
            return f"<p style='color:red;font-family:Arial;padding:40px;'>Error reading sent log: {e}</p>", 500

    if not failed_emails:
        return "<p style='font-family:Arial;padding:40px;color:#e2e8f0;background:#0f172a;min-height:100vh;'>No failed emails found to recycle.</p>"

    # 2. Reset those emails in the queue — ONE row per email only, mark rest skipped
    df = load_data()
    recycled = 0
    already_reset = set()
    for idx, row in df.iterrows():
        email_key = str(row.get("email", "")).strip().lower()
        if email_key in failed_emails:
            if email_key not in already_reset:
                niche   = str(row.get("niche", "hoa")).strip().lower()
                company = str(row.get("company", "")).strip()
                df.at[idx, "status"]  = "pending"
                df.at[idx, "subject"] = generate_subject(company, niche)
                df.at[idx, "message"] = generate_message(company, niche)
                already_reset.add(email_key)
                recycled += 1
            else:
                df.at[idx, "status"] = "skipped"  # duplicate — skip it

    df.to_csv(CSV_FILE, index=False)

    # 3. Rewrite sent_log without the failed rows
    if clean_rows:
        with open(SENT_LOG, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=clean_rows[0].keys())
            writer.writeheader()
            writer.writerows(clean_rows)
    else:
        open(SENT_LOG, "w").close()

    return f"""
    <div style="background:#0f172a;color:#e2e8f0;font-family:Arial;min-height:100vh;display:flex;align-items:center;justify-content:center;">
      <div style="background:#1e293b;border-radius:12px;padding:40px;max-width:480px;width:100%;text-align:center;">
        <div style="font-size:48px;margin-bottom:16px;">&#9851;</div>
        <h2 style="color:#22c55e;margin-bottom:12px;">Recycled {recycled} Emails</h2>
        <p style="color:#94a3b8;margin-bottom:24px;">{recycled} failed emails reset to pending with fresh messages. {len(clean_rows)} successful entries preserved in sent log.</p>
        <a href="/" style="display:inline-block;background:#22c55e;color:#000;padding:12px 32px;border-radius:8px;font-weight:bold;font-size:15px;text-decoration:none;">Go to Dashboard &#8594;</a>
      </div>
    </div>
    """

# =========================
# MANUAL REFRESH TRIGGER
# =========================
@app.route('/refresh')
def refresh():
    if not pipeline_running:
        threading.Thread(target=run_pipeline_once, daemon=True).start()
    return redirect('/')

@app.route('/rebuild-queue')
def rebuild_queue():
    def _run():
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print("[REBUILD] Running outreach_generator.py...", flush=True)
        try:
            subprocess.run(
                [sys.executable, "-u", os.path.join(script_dir, "outreach_generator.py")],
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                timeout=300
            )
            print("[REBUILD] Done — syncing CSV to DB...", flush=True)
            # Generator writes to CSV only — sync pending rows into PostgreSQL
            _sync_csv_to_db()
        except Exception as e:
            print(f"[REBUILD] Error: {e}", flush=True)
    threading.Thread(target=_run, daemon=True).start()
    return redirect('/')


def _sync_csv_to_db():
    """Push any pending rows from outreach_queue.csv into PostgreSQL.
    Called after outreach_generator.py runs so new leads actually appear."""
    if not os.path.exists(CSV_FILE):
        return
    try:
        df = pd.read_csv(CSV_FILE, dtype=str).fillna("")
        # Convert blank status to pending (same as _clean_df)
        blank_mask = df["status"].str.strip() == ""
        if blank_mask.any():
            df.loc[blank_mask, "status"] = "pending"
            df.to_csv(CSV_FILE, index=False)
            print(f"[SYNC] Activated {blank_mask.sum()} blank-status rows → pending", flush=True)
        pending = df[df["status"] == "pending"]
        if pending.empty:
            print("[SYNC] No pending rows to sync.", flush=True)
            return
        # Only insert/update rows that aren't already sent in DB
        conn = __get_db()
        if not conn:
            print("[SYNC] No DB — CSV is the queue.", flush=True)
            return
        synced = 0
        with conn.cursor() as cur:
            for _, row in pending.iterrows():
                email = str(row.get("email", "")).strip().lower()
                if not email:
                    continue
                cur.execute("""
                    INSERT INTO leads (company,name,email,message,status,niche,subject,website)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (email) DO UPDATE SET
                        company=EXCLUDED.company, name=EXCLUDED.name,
                        message=EXCLUDED.message,
                        status=CASE WHEN leads.status IN ('sent','opted_out','skipped')
                                    THEN leads.status
                                    ELSE 'pending' END,
                        niche=EXCLUDED.niche, subject=EXCLUDED.subject,
                        website=EXCLUDED.website
                """, (
                    str(row.get("company","")), str(row.get("name","")),
                    email, str(row.get("message","")), "pending",
                    str(row.get("niche","hoa")), str(row.get("subject","")),
                    str(row.get("website",""))
                ))
                synced += 1
        conn.commit()
        conn.close()
        print(f"[SYNC] {synced} pending leads pushed to DB.", flush=True)
    except Exception as e:
        print(f"[SYNC] Error: {e}", flush=True)

# =========================
# DEDUP + CLEAN QUEUE
# =========================
@app.route('/dedup-queue')
def dedup_queue():
    """Remove duplicate emails from outreach_queue.csv and sync clean list to DB."""
    def _run():
        try:
            if not os.path.exists(CSV_FILE):
                print("[DEDUP] No CSV found", flush=True)
                return
            df = pd.read_csv(CSV_FILE, dtype=str).fillna("")
            before = len(df)
            df["_email_lower"] = df["email"].str.strip().str.lower()
            df = df[df["_email_lower"].str.contains("@")]  # drop blank/invalid
            df = df.drop_duplicates(subset=["_email_lower"], keep="first")
            df = df.drop(columns=["_email_lower"])
            dupes = before - len(df)
            df.to_csv(CSV_FILE, index=False)
            print(f"[DEDUP] Removed {dupes} duplicates. {len(df)} clean leads remain.", flush=True)
            _sync_csv_to_db()
        except Exception as e:
            print(f"[DEDUP] Error: {e}", flush=True)
    threading.Thread(target=_run, daemon=True).start()
    return '<html><body style="background:#0f172a;color:#22c55e;font-family:Arial;padding:40px;"><h2>Deduplicating queue...</h2><p>Removing duplicate emails from outreach_queue.csv and syncing to DB. Check Railway logs for count. <a href="/" style="color:#06b6d4;">Back</a></p></body></html>'

# =========================
# ACTIVATE BLANK-STATUS LEADS
# =========================
@app.route('/activate-leads')
def activate_leads():
    """Convert all blank-status rows in outreach_queue.csv to pending and sync to DB."""
    def _run():
        try:
            if not os.path.exists(CSV_FILE):
                return
            df = pd.read_csv(CSV_FILE, dtype=str).fillna("")
            blank = df["status"].str.strip() == ""
            count = int(blank.sum())
            df.loc[blank, "status"] = "pending"
            df.to_csv(CSV_FILE, index=False)
            print(f"[ACTIVATE] {count} blank leads activated → pending", flush=True)
            _sync_csv_to_db()
        except Exception as e:
            print(f"[ACTIVATE] Error: {e}", flush=True)
    threading.Thread(target=_run, daemon=True).start()
    return '<html><body style="background:#0f172a;color:#22c55e;font-family:Arial;padding:40px;"><h2>✅ Activating all blank-status leads!</h2><p>Converting blank status → pending and syncing to DB. Your pending count will update in ~30 seconds.</p><p><a href="/" style="color:#06b6d4;">Back to dashboard</a></p></body></html>'

# =========================
# BLAST SIGNALS NOW (manual)
# =========================
@app.route('/blast-signals-now')
def blast_signals_now():
    """Immediately run signals_engine.py to send to all unsent signals leads."""
    threading.Thread(target=lambda: _run_engine("Signals Email Blast", "signals_engine.py"), daemon=True).start()
    return '<html><body style="background:#0f172a;color:#a78bfa;font-family:Arial;padding:40px;"><h2>📡 Signals Blast Firing!</h2><p>Sending signals pitch to all unsent leads in signals_queue.csv now.</p><p>Check <a href="/status" style="color:#06b6d4;">System Status</a> for progress.</p><p><a href="/" style="color:#06b6d4;">Back to dashboard</a></p></body></html>'

# =========================
# TEST LINKEDIN OUTREACH
# =========================
@app.route('/test-linkedin')
def test_linkedin():
    """Check LinkedIn credentials and attempt a dry-run search."""
    import subprocess, sys
    li_at = os.getenv("LINKEDIN_LI_AT", "")
    csrf  = os.getenv("LINKEDIN_CSRF_TOKEN", "")
    lines = []
    lines.append(f"LINKEDIN_LI_AT set: {'YES (' + str(len(li_at)) + ' chars)' if li_at else 'NO - add to Railway vars'}")
    lines.append(f"LINKEDIN_CSRF_TOKEN set: {'YES (' + str(len(csrf)) + ' chars)' if csrf else 'NO - add to Railway vars'}")

    if li_at and csrf:
        try:
            import requests as _req
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/vnd.linkedin.normalized+json+2.1",
                "Cookie": f"li_at={li_at}; JSESSIONID=\"{csrf}\"",
                "Csrf-Token": csrf,
                "X-Li-Lang": "en_US",
                "X-RestLi-Protocol-Version": "2.0.0",
                "Referer": "https://www.linkedin.com/",
            }
            r = _req.get(
                "https://www.linkedin.com/voyager/api/graphql",
                params={
                    "variables": "(start:0,origin:GLOBAL_SEARCH_HEADER,query:(keywords:HOA property manager,flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:resultType,value:List(PEOPLE))),includeFiltersInResponse:false))",
                    "queryId": "voyagerSearchDashClusters.02af3bc5ca7e4fdd4d70b3f792d51313",
                },
                headers=headers, timeout=12,
            )
            lines.append(f"LinkedIn API search status: HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                clusters = data.get("data", {}).get("searchDashClustersByAll", {}).get("elements", [])
                count = sum(len(c.get("items", {}).get("elements", [])) for c in clusters)
                lines.append(f"Search returned {count} profiles - credentials are VALID")
            elif r.status_code == 401:
                lines.append("401 Unauthorized — li_at cookie is expired. Refresh it from Chrome DevTools.")
            elif r.status_code == 403:
                lines.append("403 Forbidden — CSRF token mismatch. Re-copy JSESSIONID from Chrome.")
            else:
                lines.append(f"Response: {r.text[:200]}")
        except Exception as e:
            lines.append(f"Error: {e}")
    else:
        lines.append("Cannot test — missing credentials above.")

    body = "<br>".join(f"<p>{l}</p>" for l in lines)
    return f'<html><body style="background:#0f172a;color:#e2e8f0;font-family:Arial;padding:40px;max-width:700px;"><h2 style="color:#0ea5e9;">LinkedIn Outreach Check</h2>{body}<br><p><a href="/" style="color:#06b6d4;">Back to dashboard</a></p></body></html>'

# =========================
# TRIGGER PIPELINE MANUALLY
# =========================
@app.route('/trigger-pipeline')
def trigger_pipeline():
    if pipeline_running:
        return '<html><body style="background:#0f172a;color:#f97316;font-family:Arial;padding:40px;"><h2>Pipeline already running...</h2><p>Check back in a few minutes. <a href="/" style="color:#06b6d4;">Back to dashboard</a></p></body></html>'
    threading.Thread(target=run_pipeline_once, daemon=True).start()
    return '<html><body style="background:#0f172a;color:#22c55e;font-family:Arial;padding:40px;"><h2>Pipeline triggered!</h2><p>Scraping Yelp and enriching leads now. Leads will appear in your queue in 5-15 minutes.</p><p><a href="/status" style="color:#06b6d4;">Check status</a> &nbsp;|&nbsp; <a href="/" style="color:#06b6d4;">Back to dashboard</a></p></body></html>'

# Track engine last-run times
_engine_last_ran: dict = {}

def _record_engine_run(label: str):
    _engine_last_ran[label] = time.time()

def _twitter_suggestions_panel() -> str:
    """Render comment suggestion cards from twitter_poster's saved JSON."""
    import json as _json
    suggestions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitter_comment_suggestions.json")
    try:
        if os.path.exists(suggestions_path):
            with open(suggestions_path) as f:
                suggestions = _json.load(f)
        else:
            suggestions = []
    except Exception:
        suggestions = []

    if not suggestions:
        return """<div style="background:#1e293b;border-radius:8px;padding:16px;max-width:720px;margin:16px 0;color:#475569;font-size:13px;">
  <strong style="color:#94a3b8;">Twitter Comment Opportunities</strong><br>
  No suggestions yet — fires after next Twitter post cycle (every 2 hrs).
</div>"""

    cards = ""
    for s in suggestions[:5]:
        tweet_url = s.get("tweet_url", "#")
        author    = s.get("author", "")
        text      = s.get("tweet_text", "")[:140]
        likes     = s.get("likes", 0)
        comment   = s.get("suggested_comment", "")
        tweet_id  = s.get("tweet_id", "")
        cards += f"""
<div style="background:#0f172a;border:1px solid #334155;border-radius:6px;padding:12px 16px;margin:8px 0;">
  <div style="font-size:12px;color:#64748b;">@{author} &nbsp;·&nbsp; ❤ {likes}</div>
  <div style="font-size:13px;color:#94a3b8;margin:6px 0 8px;">{text}…</div>
  <div style="font-size:12px;color:#38bdf8;font-style:italic;margin-bottom:8px;">Suggested reply: {comment[:120]}…</div>
  <a href="{tweet_url}" target="_blank"
     style="font-size:12px;color:#22c55e;text-decoration:none;margin-right:12px;">View tweet ↗</a>
  <a href="/post-twitter-comment?tweet_id={tweet_id}&comment={comment[:200].replace(' ', '+')}"
     style="font-size:12px;background:#1d4ed8;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;">Post Reply</a>
</div>"""

    return f"""
<div style="background:#1e293b;border-radius:8px;padding:16px;max-width:720px;margin:16px 0;">
  <div style="font-size:14px;font-weight:700;color:#38bdf8;margin-bottom:8px;">
    Twitter Comment Opportunities — grow your audience by engaging trending posts
  </div>
  {cards}
</div>"""

# =========================
# SYSTEM STATUS PAGE — live data
# =========================
@app.route('/status')
def status():
    import datetime as _dt

    # ── Lead queue counts from DB ──
    pending = 0; total_sent = 0; total_opted = 0; total_all = 0
    try:
        conn = __get_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
                for st, cnt in cur.fetchall():
                    total_all += cnt
                    if st == 'pending':   pending    = cnt
                    elif st == 'sent':    total_sent = cnt
                    elif st == 'opted_out': total_opted = cnt
            conn.close()
    except Exception:
        pending = get_pending_count()

    # ── SendGrid stats (today) ──
    sg_delivered = sg_bounced = sg_opens = sg_clicks = sg_requests = 0
    sg_error = ""
    sg_key = os.getenv("SENDGRID_API_KEY", "")
    if sg_key:
        try:
            today = _dt.date.today().isoformat()
            r = requests.get(
                "https://api.sendgrid.com/v3/stats",
                headers={"Authorization": f"Bearer {sg_key}"},
                params={"start_date": today, "aggregated_by": "day"},
                timeout=10
            )
            if r.status_code == 200 and r.json():
                m = r.json()[0].get("stats", [{}])[0].get("metrics", {})
                sg_requests  = m.get("requests", 0)
                sg_delivered = m.get("delivered", 0)
                sg_bounced   = m.get("bounces", 0)
                sg_opens     = m.get("unique_opens", 0)
                sg_clicks    = m.get("unique_clicks", 0)
            else:
                sg_error = f"HTTP {r.status_code}"
        except Exception as e:
            sg_error = str(e)[:60]

    # ── Helpers ──
    def _check(key, label=""):
        val = os.getenv(key, "").strip()
        ok = bool(val)
        color = "#22c55e" if ok else "#ef4444"
        text  = "SET" if ok else "MISSING"
        return f'<tr><td style="padding:8px 16px;color:#cbd5e1;">{label or key}</td><td style="padding:8px 16px;"><span style="color:{color};font-weight:bold;">{text}</span></td></tr>'

    def _eng(label):
        ts = _engine_last_ran.get(label)
        if ts:
            ago = int((time.time() - ts) / 60)
            note = f"{ago}m ago" if ago < 60 else f"{ago//60}h ago"
            color = "#22c55e"
        else:
            note = "not yet this session"
            color = "#f97316"
        return f'<tr><td style="padding:8px 16px;color:#cbd5e1;">{label}</td><td style="padding:8px 16px;color:{color};font-weight:bold;">{note}</td></tr>'

    queue_color = "#22c55e" if pending >= 1000 else ("#f97316" if pending >= 100 else "#ef4444")
    queue_label = "HEALTHY" if pending >= 1000 else ("LOW — REFILLING" if pending >= 100 else "CRITICAL — PIPELINE RUNNING")
    last_run_str = _dt.datetime.fromtimestamp(last_run_time).strftime('%I:%M %p') if last_run_time else 'Not yet'
    open_rate = f"{round(sg_opens/sg_delivered*100,1)}%" if sg_delivered else "—"
    bounce_rate = f"{round(sg_bounced/sg_requests*100,1)}%" if sg_requests else "—"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>GHE Live Status</title>
<meta http-equiv="refresh" content="30">
<style>
body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;margin:0;padding:20px;}}
h1{{color:#22c55e;margin:0 0 4px;}}
.sub{{color:#64748b;font-size:12px;margin-bottom:20px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;max-width:720px;margin-bottom:20px;}}
.stat{{background:#1e293b;border-radius:8px;padding:14px;}}
.stat-val{{font-size:1.7rem;font-weight:bold;color:#22c55e;}}
.stat-lbl{{font-size:11px;color:#64748b;text-transform:uppercase;margin-top:2px;}}
table{{width:100%;max-width:720px;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden;margin-bottom:20px;}}
th{{background:#0f172a;color:#64748b;text-align:left;padding:8px 14px;font-size:11px;text-transform:uppercase;}}
a{{color:#06b6d4;text-decoration:none;}}
.warn{{color:#f97316;font-weight:bold;}}
</style></head>
<body>
<h1>GHE Live Status</h1>
<div class="sub">Refreshes every 30s &nbsp;|&nbsp; <a href="/">Dashboard</a> &nbsp;|&nbsp; <a href="/trigger-pipeline" onclick="return confirm('Run pipeline now?')">▶ Run Pipeline Now</a></div>

<div class="grid">
  <div class="stat"><div class="stat-val" style="color:{queue_color};">{pending}</div><div class="stat-lbl">Pending Leads</div></div>
  <div class="stat"><div class="stat-val">{total_sent}</div><div class="stat-lbl">Total Sent (DB)</div></div>
  <div class="stat"><div class="stat-val" style="color:#22c55e;">{sg_delivered}</div><div class="stat-lbl">Delivered Today</div></div>
  <div class="stat"><div class="stat-val" style="color:#f97316;">{sg_bounced}</div><div class="stat-lbl">Bounced Today</div></div>
  <div class="stat"><div class="stat-val" style="color:#06b6d4;">{sg_opens}</div><div class="stat-lbl">Opens Today</div></div>
  <div class="stat"><div class="stat-val" style="color:#a855f7;">{sg_clicks}</div><div class="stat-lbl">Clicks Today</div></div>
  <div class="stat"><div class="stat-val">{open_rate}</div><div class="stat-lbl">Open Rate</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#ef4444' if sg_bounced>10 else '#22c55e'};">{bounce_rate}</div><div class="stat-lbl">Bounce Rate</div></div>
</div>

<div style="background:#1e293b;border-radius:8px;padding:12px 16px;max-width:720px;margin-bottom:20px;font-size:13px;color:#94a3b8;">
  Pipeline: <strong style="color:{'#f97316' if pipeline_running else '#22c55e'};">{'RUNNING NOW' if pipeline_running else 'IDLE'}</strong>
  &nbsp;|&nbsp; Last run: <strong>{last_run_str}</strong>
  &nbsp;|&nbsp; Queue: <strong style="color:{queue_color};">{queue_label}</strong>
  {f'&nbsp;|&nbsp; <span class="warn">SendGrid error: {sg_error}</span>' if sg_error else ''}
</div>

<table>
<tr><th>API / Integration</th><th>Status</th></tr>
{_check("SENDGRID_API_KEY", "SendGrid (Email Sending)")}
{_check("DATABASE_URL", "PostgreSQL (Lead Storage)")}
{_check("YELP_API_KEY", "Yelp API (Leads)")}
{_check("HUNTER_API_KEY", "Hunter.io (Email Finder)")}
{_check("TWITTER_API_KEY", "Twitter Auto-Poster")}
{_check("TWITTER_ACCESS_TOKEN", "Twitter Access Token")}
{_check("GMAIL_CLIENT_ID", "Gmail Reply Monitor")}
{_check("ANTHROPIC_API_KEY", "Claude AI (Auto-Reply)")}
{_check("CALENDLY_URL", "Calendly Link")}
{_check("STRIPE_PAYMENT_LINK", "Stripe Payment Link")}
{_check("STOCKTWITS_ACCESS_TOKEN", "Stocktwits (Trader Audience)")}
</table>

<table>
<tr><th>Engine</th><th>Last Fired This Session</th></tr>
{_eng("Pipeline (Lead Gen)")}
{_eng("FINRA Financial Advisor Leads")}
{_eng("Signals Email Blast")}
{_eng("Stocktwits Post")}
{_eng("Grant Pipeline")}
{_eng("Twitter Post")}
{_eng("Gmail Monitor")}
{_eng("Follow-Up Engine")}
{_eng("Niche: Real Estate")}
{_eng("Niche: Gym")}
{_eng("Niche: Mortgage")}
{_eng("Niche: E-Commerce")}
{_eng("Niche: Restaurant")}
{_eng("Niche: Med Spa")}
{_eng("Niche: Insurance")}
</table>

{_twitter_suggestions_panel()}

<div style="background:#1e293b;border-radius:8px;padding:14px;max-width:720px;font-size:12px;color:#475569;">
  DB totals — Pending: {pending} &nbsp;|&nbsp; Sent: {total_sent} &nbsp;|&nbsp; Opted out: {total_opted} &nbsp;|&nbsp; Total: {total_all}<br>
  All engines run 24/7 on Railway. "Not yet this session" resets on each Railway deploy.
</div>
</body></html>"""

# =========================
# PURGE BOUNCED — remove all role/generic/bounced addresses from DB + CSV
# =========================
@app.route('/purge-bounced')
def purge_bounced():
    """
    Scrubs the leads DB and CSV of:
    - Role addresses: info@, service@, hello@, office@, contact@, admin@...
    - Any address marked 'bounced' or 'failed' in DB
    - All addresses in SendGrid's bounce/block/spam suppression lists
    """
    from email_verifier import is_role_address, is_valid_syntax
    removed_db  = 0
    removed_csv = 0

    # -- Pull SendGrid suppression lists (bounces, blocks, spam reports, invalids) --
    sg_bad_emails = set()
    sg_key = os.getenv("SENDGRID_API_KEY", "")
    if sg_key:
        try:
            for endpoint in ["suppression/bounces", "suppression/blocks",
                             "suppression/spam_reports", "suppression/invalid_emails"]:
                r = requests.get(
                    f"https://api.sendgrid.com/v3/{endpoint}?limit=500",
                    headers={"Authorization": f"Bearer {sg_key}"}, timeout=15
                )
                if r.status_code == 200:
                    for item in r.json():
                        e = (item.get("email") or "").strip().lower()
                        if e:
                            sg_bad_emails.add(e)
            print(f"[PURGE] SendGrid suppressions: {len(sg_bad_emails)} emails to block", flush=True)
        except Exception as ex:
            print(f"[PURGE] SendGrid fetch error: {ex}", flush=True)

    # -- Purge from PostgreSQL DB --
    conn = __get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email FROM leads WHERE status IN ('pending','failed')")
                rows = cur.fetchall()
                bad_ids = []
                for row_id, email in rows:
                    email = (email or "").strip().lower()
                    if not email or not is_valid_syntax(email) or is_role_address(email) or email in sg_bad_emails:
                        bad_ids.append(row_id)
                if bad_ids:
                    cur.execute("DELETE FROM leads WHERE id = ANY(%s)", (bad_ids,))
                    removed_db = len(bad_ids)
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PURGE] DB error: {e}")

    # -- Purge from CSV --
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE, dtype=str).fillna("")
            before = len(df)
            df = df[df["email"].apply(lambda e: is_valid_syntax(str(e)) and not is_role_address(str(e)))]
            df = df[df["status"].isin(["pending"])]
            removed_csv = before - len(df)
            df.to_csv(CSV_FILE, index=False)
        except Exception as e:
            print(f"[PURGE] CSV error: {e}")

    msg = f"Purged {removed_db} role/invalid addresses from DB + {removed_csv} from CSV. Daily limit is now 150/day while deliverability recovers."
    print(f"[PURGE] {msg}", flush=True)
    return f"""<div style='font-family:Arial;background:#0f172a;color:#e2e8f0;padding:40px;'>
<h2 style='color:#22c55e;'>Purge Complete</h2>
<p>{msg}</p>
<p style='color:#94a3b8;font-size:13px;'>
Addresses dropped: info@, service@, hello@, office@, contact@, admin@, support@, billing@, etc.<br>
These were your bounces. Only named personal addresses (john@company.com) will remain.
</p>
<a href='/' style='color:#38bdf8;'>← Dashboard</a> &nbsp;
<a href='/status' style='color:#38bdf8;'>Status →</a>
</div>"""


# =========================
# DEBUG CONFIG (no secrets shown)
# =========================
@app.route('/debug')
def debug():
    sg_key      = os.getenv("SENDGRID_API_KEY",    "").strip()
    sender      = os.getenv("SENDER_EMAIL",         "").strip()
    smtp_pass   = os.getenv("SENDER_APP_PASSWORD",  "").strip()
    sender_name = os.getenv("SENDER_NAME",          "").strip()

    def row(label, value, ok):
        color = "#22c55e" if ok else "#ef4444"
        icon  = "&#10003;" if ok else "&#10007; MISSING"
        return (
            "<tr>"
            "<td style='padding:10px 16px;color:#94a3b8;'>" + label + "</td>"
            "<td style='padding:10px 16px;'><strong style='color:" + color + ";'>" +
            (value if ok else icon) + "</strong></td>"
            "</tr>"
        )

    sg_ok    = bool(sg_key)
    smtp_ok  = bool(smtp_pass)
    send_ok  = bool(sender)

    method = "SendGrid" if sg_ok else ("Gmail SMTP" if smtp_ok else "NONE — emails will fail")
    method_color = "#22c55e" if (sg_ok or smtp_ok) else "#ef4444"

    rows = (
        row("SENDER_EMAIL",        sender    if send_ok  else "",  send_ok)  +
        row("SENDER_APP_PASSWORD", "SET (" + str(len(smtp_pass)) + " chars)" if smtp_ok else "", smtp_ok) +
        row("SENDGRID_API_KEY",    "SET"     if sg_ok    else "not set (optional)", sg_ok) +
        row("SENDER_NAME",         sender_name if sender_name else "Gray Horizons (default)", True)
    )

    return (
        "<div style='background:#0f172a;color:white;font-family:Arial;padding:40px;'>"
        "<h2 style='color:#38bdf8;margin-bottom:4px;'>Config Check</h2>"
        "<p style='color:#94a3b8;margin-bottom:24px;'>Active send method: "
        "<strong style='color:" + method_color + ";'>" + method + "</strong></p>"
        "<table style='border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;margin-bottom:24px;'>"
        + rows +
        "</table>"
        "<p style='color:#64748b;font-size:13px;'>DATA_DIR: " + DATA_DIR + "</p>"
        "<p style='color:#64748b;font-size:13px;'>Pipeline running: " + str(pipeline_running) + "</p>"
        "<br>"
        "<a href='/test-email' style='color:#38bdf8;margin-right:16px;'>Run Test Email</a>"
        "<a href='/sent'       style='color:#38bdf8;margin-right:16px;'>View Sent Log</a>"
        "<a href='/resend-failed' style='color:#f59e0b;margin-right:16px;'>Resend Failed</a>"
        "<a href='/'           style='color:#38bdf8;'>Dashboard</a>"
        "</div>"
    )

# =========================
# SOCIAL PIPELINE ROUTES
# =========================
@app.route('/send-batch')
def send_batch():
    if not batch_running:
        threading.Thread(target=run_batch_send, daemon=True).start()
    return redirect('/')

@app.route('/send-batch-1k')
def send_batch_1k():
    if not batch_running:
        threading.Thread(target=run_batch_send, kwargs={"limit": 1000}, daemon=True).start()
    return redirect('/')

@app.route('/send-batch-5k')
def send_batch_5k():
    if not batch_running:
        threading.Thread(target=run_batch_send, kwargs={"limit": 5000}, daemon=True).start()
    return redirect('/')

@app.route('/test-snov')
def test_snov():
    """Live Snov.io v2 async API test — credit balance + 3 test domains."""
    import os as _os, time as _time
    client_id  = _os.getenv("SNOV_CLIENT_ID", "")
    client_sec = _os.getenv("SNOV_CLIENT_SECRET", "")
    lines = [f"<b>SNOV_CLIENT_ID:</b> {'SET (' + client_id[:8] + '...)' if client_id else '<span style=color:red>NOT SET</span>'}",
             f"<b>SNOV_CLIENT_SECRET:</b> {'SET (' + client_sec[:8] + '...)' if client_sec else '<span style=color:red>NOT SET</span>'}"]
    if not client_id or not client_sec:
        return "<br>".join(lines)
    try:
        import requests as _req
        r = _req.post("https://api.snov.io/v1/oauth/access_token", data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_sec,
        }, timeout=15)
        lines.append(f"<b>Token request:</b> HTTP {r.status_code}")
        if r.status_code != 200:
            lines.append(f"<span style=color:red>Auth failed: {r.text[:300]}</span>")
            return "<br>".join(lines)
        token = r.json().get("access_token", "")
        lines.append(f"<b>Token:</b> {token[:20]}...")
        hdrs = {"Authorization": f"Bearer {token}"}

        # Credit balance check
        rb = _req.get("https://api.snov.io/v1/user-balance", headers=hdrs, timeout=10)
        lines.append(f"<br><b>Credit balance check:</b> HTTP {rb.status_code}")
        if rb.status_code == 200:
            bd = rb.json()
            lines.append(f"<b>Credits remaining:</b> {bd.get('credits_left', bd)}")

        # Try 3 different company domains — mix of large and small
        test_domains = ["airriteairconditioning.com", "coolrayhvac.com", "aceplumbing.com"]
        lines.append("<br><b>Testing 3 domains for email coverage:</b>")
        for test_domain in test_domains:
            r2 = _req.post(f"https://api.snov.io/v2/domain-search/domain-emails/start?domain={test_domain}",
                           headers=hdrs, timeout=15)
            lines.append(f"<br>&nbsp;&nbsp;<b>{test_domain}</b> — start HTTP {r2.status_code}")
            if r2.status_code == 402:
                lines.append("&nbsp;&nbsp;<span style=color:red>Credits exhausted</span>")
                break
            if r2.status_code not in (200, 202):
                lines.append(f"&nbsp;&nbsp;<span style=color:orange>{r2.text[:150]}</span>")
                continue
            d0 = r2.json()
            task_hash = (d0.get("task_hash") or d0.get("taskHash")
                         or (d0.get("meta") or {}).get("task_hash", ""))
            if not task_hash:
                lines.append(f"&nbsp;&nbsp;<span style=color:orange>No task_hash: {str(d0)[:150]}</span>")
                continue
            lines.append(f"&nbsp;&nbsp;task_hash: {task_hash[:20]}...")
            emails = []
            for attempt in range(6):
                _time.sleep(3)
                r3 = _req.get(f"https://api.snov.io/v2/domain-search/domain-emails/result/{task_hash}",
                              headers=hdrs, timeout=15)
                st = r3.json().get("status", "?") if r3.status_code == 200 else "err"
                lines.append(f"&nbsp;&nbsp;Poll #{attempt+1}: HTTP {r3.status_code} status={st}")
                if r3.status_code != 200:
                    break
                if st in ("done", "complete", "completed", "finished"):
                    raw = r3.json()
                    emails = raw.get("data") or raw.get("emails") or []
                    break
            lines.append(f"&nbsp;&nbsp;<b style=color:#22c55e>Emails found: {len(emails)}</b>")
            for e in emails[:5]:
                addr = e.get("email") or e.get("value", "")
                lines.append(f"&nbsp;&nbsp;&nbsp;&nbsp;{addr}")

        # Hunter.io status
        hunter_key = _os.getenv("HUNTER_API_KEY", "")
        lines.append(f"<br><b>Hunter.io key:</b> {'SET (resets May 22)' if hunter_key else '<span style=color:red>NOT SET</span>'}")
    except Exception as ex:
        lines.append(f"<span style=color:red>Exception: {ex}</span>")
    style = "background:#0f172a;color:#e2e8f0;font-family:monospace;padding:40px;line-height:2"
    return f'<html><body style="{style}"><h2 style="color:#22c55e">Snov.io v2 API Test</h2>' + "<br>".join(lines) + '<br><br><a href="/" style="color:#06b6d4">Back</a></body></html>'


@app.route('/test-twitter')
def test_twitter():
    """Diagnose Twitter posting — shows exact error at each step."""
    import os as _os
    lines = []
    api_key    = _os.getenv("TWITTER_API_KEY", "")
    api_secret = _os.getenv("TWITTER_API_SECRET", "")
    acc_token  = _os.getenv("TWITTER_ACCESS_TOKEN", "")
    acc_secret = _os.getenv("TWITTER_ACCESS_SECRET", "")
    lines.append(f"TWITTER_API_KEY: {'SET ('+api_key[:6]+'...)' if api_key else 'MISSING'}")
    lines.append(f"TWITTER_API_SECRET: {'SET' if api_secret else 'MISSING'}")
    lines.append(f"TWITTER_ACCESS_TOKEN: {'SET ('+acc_token[:18]+'...)' if acc_token else 'MISSING'}")
    lines.append(f"TWITTER_ACCESS_SECRET: {'SET ('+acc_secret[:6]+'...)' if acc_secret else 'MISSING'}")
    if not all([api_key, api_secret, acc_token, acc_secret]):
        lines.append("ERROR: Missing credentials — cannot continue")
    else:
        try:
            import tweepy, requests as _req
            from requests_oauthlib import OAuth1 as _OAuth1
            lines.append("libs: OK")
            # Test with raw requests + OAuth1 (bypasses tweepy entirely)
            oauth = _OAuth1(api_key, api_secret, acc_token, acc_secret)
            r2 = _req.post(
                "https://api.twitter.com/2/tweets",
                json={"text": "GHE Edge Engine — congressional trade signals, momentum scores, volume anomalies. $49/month: horizons56.gumroad.com"},
                auth=oauth, timeout=15,
            )
            lines.append(f"Direct API call: HTTP {r2.status_code}")
            lines.append(f"Response: {r2.text[:300]}")
            if r2.status_code in (200, 201):
                tid = r2.json().get("data", {}).get("id", "?")
                lines.append(f"SUCCESS: twitter.com/i/web/status/{tid}")
        except Exception as e:
            lines.append(f"ERROR: {type(e).__name__}: {e}")
    body = "<br>".join(lines)
    return f'<html><body style="background:#0f172a;color:#e2e8f0;font-family:monospace;padding:40px;font-size:14px;"><h2>Twitter Test</h2>{body}<br><br><a href="/" style="color:#06b6d4;">Back</a></body></html>'


@app.route('/post-twitter-comment')
def post_twitter_comment_route():
    tweet_id = flask_request.args.get("tweet_id", "").strip()
    comment  = flask_request.args.get("comment", "").strip()
    if not tweet_id or not comment:
        return "Missing tweet_id or comment", 400
    try:
        from twitter_poster import post_comment
        ok = post_comment(tweet_id, comment)
        msg = "Comment posted!" if ok else "Failed — check Twitter credentials"
    except Exception as e:
        msg = f"Error: {e}"
    return f"<p style='font-family:Arial;padding:20px;color:{'#22c55e' if ok else '#ef4444'};'>{msg}</p><a href='/status'>← Back to Status</a>"


@app.route('/twitter-suggestions-json')
def twitter_suggestions_json():
    """Return saved comment suggestions as JSON for the Twitter tab."""
    from flask import jsonify
    import json as _json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitter_comment_suggestions.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = _json.load(f)
            # Attach 4 reply choices to each suggestion
            for s in data:
                topic = s.get("tweet_text","")[:40].replace('"','')
                author = s.get("author","someone")
                s["reply_choices"] = [
                    # Value Add
                    f"Good point. The pattern we track is volume anomaly plus RSI momentum on the same bar — when both align above threshold the setup quality is completely different. Most miss it without the right filter.",
                    # Ask Question
                    f"Curious — do you use any scoring system to filter setups or do you evaluate each one manually? Finding that a 0-100 score cuts the noise significantly.",
                    # Authority
                    f"We built a congressional disclosure tracker that flags volume patterns before the disclosure goes public. Retail sees the move 2-3 weeks after the pattern is already visible. The edge is in the timing.",
                    # Product Hook
                    f"This is exactly why we built the Edge Scanner — momentum scoring plus congressional tracking before the open. If you want to see how it works: horizons56.gumroad.com",
                ]
        else:
            data = []
    except Exception:
        data = []
    return jsonify(data)


@app.route('/twitter-fetch-suggestions')
def twitter_fetch_suggestions_route():
    """Trigger a live fetch of comment suggestions and return results."""
    from flask import jsonify
    try:
        from twitter_poster import fetch_comment_suggestions
        results = fetch_comment_suggestions()
        # Attach reply choices
        for s in results:
            s["reply_choices"] = [
                "Good point. The pattern we track is volume anomaly plus RSI momentum on the same bar — when both align above threshold the setup quality is completely different. Most miss it without the right filter.",
                "Curious — do you use any scoring system to filter setups or evaluate each one manually? Finding that a 0-100 score cuts the noise significantly.",
                "We built a congressional disclosure tracker that flags volume patterns before the disclosure goes public. Retail sees the move 2-3 weeks after the pattern is already visible. The edge is in the timing.",
                "This is exactly why we built the Edge Scanner — momentum scoring plus congressional tracking before the open. If you want to see how it works: horizons56.gumroad.com",
            ]
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/post-twitter-reply', methods=['POST'])
def post_twitter_reply_route():
    """Post a reply from the Twitter tab choice buttons."""
    from flask import jsonify, request as _req
    import json as _json
    data = _req.get_json(force=True, silent=True) or {}
    tweet_id = str(data.get("tweet_id","")).strip()
    comment  = str(data.get("comment","")).strip()
    if not tweet_id or not comment:
        return jsonify({"ok": False, "error": "Missing tweet_id or comment"}), 400
    try:
        from twitter_poster import post_comment
        ok = post_comment(tweet_id, comment)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/twitter-auto-follow')
def twitter_auto_follow_route():
    """Trigger auto-follow with optional custom search terms."""
    from flask import jsonify, request as _req
    max_follows = int(_req.args.get("max", 20))
    terms_raw   = _req.args.get("terms", "").strip()
    try:
        from twitter_poster import auto_follow_accounts, TRENDING_SEARCH_TERMS
        import twitter_poster as _tp
        if terms_raw:
            custom = [t.strip() for t in terms_raw.split(",") if t.strip()]
            _tp.TRENDING_SEARCH_TERMS = custom + TRENDING_SEARCH_TERMS
        new_follows = auto_follow_accounts(max_follows=max_follows)
        return jsonify({"ok": True, "new_follows": new_follows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "new_follows": 0}), 500


@app.route('/twitter-post-now')
def twitter_post_now_route():
    """Force post one tweet immediately."""
    def _bg():
        _run_engine("Twitter Force Post", "twitter_poster.py", extra_args=["--force"])
    threading.Thread(target=_bg, daemon=True).start()
    return ("<html><body style='background:#0f172a;color:#e2e8f0;font-family:Arial;padding:2rem;'>"
            "<h2 style='color:#1d9bf0;'>Tweet queued</h2>"
            "<p>Post will go out in ~10 seconds. Check Twitter to confirm.</p>"
            "<br><a href='/?tab=twitter' style='color:#38bdf8;'>Back to Twitter Tab</a>"
            "</body></html>")


@app.route('/run-all-engines')
def run_all_engines_route():
    """Manually trigger every outreach engine right now."""
    engines = [
        ("Real Estate Engine",  "realestate_engine.py"),
        ("Med Spa Engine",      "medspa_engine.py"),
        ("Insurance Engine",    "insurance_engine.py"),
        ("E-Commerce Engine",   "ecommerce_engine.py"),
        ("Restaurant Engine",   "restaurant_engine.py"),
        ("Gym Engine",          "gym_engine.py"),
        ("Mortgage Engine",     "mortgage_engine.py"),
        ("Signals Blast",       "signals_engine.py"),
        ("Follow-Up Engine",    "followup_engine.py"),
    ]
    stagger = 0
    for label, script in engines:
        def _fire(l=label, s=script, delay=stagger):
            time.sleep(delay)
            _run_engine(l, s)
        threading.Thread(target=_fire, daemon=True).start()
        stagger += 90  # 90-second stagger between engines
    return (
        "<html><body style='background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem;'>"
        f"<h2 style='color:#4ade80;'>All {len(engines)} engines queued</h2>"
        "<p>Engines will fire 90 seconds apart to avoid overload.<br>"
        "First engine starts in ~5 seconds. Check Railway logs for progress.</p>"
        "<br><a href='/' style='color:#38bdf8;'>Back to Dashboard</a>"
        "</body></html>"
    )


@app.route('/trigger-calls', methods=['GET', 'POST'])
def trigger_calls_route():
    """Fire outbound calls to all prospects with phone numbers. Business hours enforced inside script."""
    def _run():
        _run_engine("Outbound Calls", "outbound_caller.py", ["--max", "5"])
    threading.Thread(target=_run, daemon=True).start()
    return (
        "<html><body style='background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem;'>"
        "<h2 style='color:#4ade80;'>Outbound calls queued</h2>"
        "<p>Jordan is calling up to 5 prospects. Business hours enforced (9am-5pm ET Mon-Fri).<br>"
        "Check Railway logs for call results.</p>"
        "<br><a href='/' style='color:#38bdf8;'>Back to Dashboard</a>"
        "</body></html>"
    )


def _daily_call_scheduler():
    """Background thread: fires outbound calls once per day at 9am ET."""
    from zoneinfo import ZoneInfo
    import time as _time
    ET = ZoneInfo("America/New_York")
    while True:
        now = datetime.now(ET)
        # Run Mon-Fri at 9am ET
        if now.weekday() < 5 and now.hour == 9 and now.minute < 5:
            print("[SCHEDULER] 9am ET — firing outbound calls", flush=True)
            _run_engine("Daily Outbound Calls", "outbound_caller.py", ["--max", "5"])
            _time.sleep(360)  # sleep 6 min so it doesn't double-fire within same 9am window
        else:
            _time.sleep(60)


# Start the daily call scheduler in background when app boots
threading.Thread(target=_daily_call_scheduler, daemon=True).start()


@app.route('/opt-out', methods=['GET', 'POST'])
def opt_out_route():
    if flask_request.method == 'POST':
        email  = flask_request.form.get("email", "").strip().lower()
        reason = flask_request.form.get("reason", "manual entry").strip()
        if email:
            add_opt_out(email, reason)
            # Update DB in background so page responds immediately
            def _bg_update(e=email):
                try:
                    df = load_data()
                    mask = df["email"].str.lower().str.strip() == e
                    df.loc[mask & (df["status"] == "pending"), "status"] = "opted_out"
                    save_data(df)
                except Exception:
                    pass
            threading.Thread(target=_bg_update, daemon=True).start()
        return redirect('/')
    return (
        "<html><body style='background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem;'>"
        "<h2>Add Opt-Out</h2>"
        "<form method='POST'>"
        "<label>Email: <input name='email' style='width:300px;padding:6px;margin:8px;'></label><br>"
        "<label>Reason: <input name='reason' value='requested removal' style='width:300px;padding:6px;margin:8px;'></label><br>"
        "<button type='submit' style='padding:8px 20px;background:#dc2626;color:#fff;border:none;cursor:pointer;'>Add to Opt-Out List</button>"
        "</form>"
        "<br><a href='/' style='color:#38bdf8;'>Back to Dashboard</a>"
        "</body></html>"
    )

@app.route('/social/from-sent')
def social_from_sent():
    company  = flask_request.args.get("company", "").strip()
    email    = flask_request.args.get("email",   "").strip()
    if company or email:
        rows = load_social()
        existing_emails = [r.get("email","").lower() for r in rows]
        if email.lower() not in existing_emails:
            add_social_prospect(company or email, "Email", "no reply — follow up socially", email)
    return redirect('/?tab=social')

@app.route('/social/from-email/<int:index>')
def social_from_email(index):
    df = load_data()
    if index < len(df):
        row      = df.loc[index]
        handle   = str(row.get("company", "")).strip() or f"Lead #{index}"
        email    = str(row.get("email",   "")).strip()
        platform = "Email"
        notes    = str(row.get("niche",   "")).strip()
        rows = load_social()
        existing_emails = [r.get("email","").lower() for r in rows]
        if email.lower() not in existing_emails:
            add_social_prospect(handle, platform, notes, email)
    return redirect('/?tab=social')

@app.route('/social/add', methods=["POST"])
def social_add():
    from flask import request as freq
    handle   = freq.form.get("handle",   "").strip()
    platform = freq.form.get("platform", "").strip()
    notes    = freq.form.get("notes",    "").strip()
    email    = freq.form.get("email",    "").strip()
    if handle:
        add_social_prospect(handle, platform, notes, email)
    return redirect('/?tab=social')

@app.route('/social/advance/<sid>')
def social_advance(sid):
    rows = load_social()
    for row in rows:
        if row.get("id") == sid:
            stage = row.get("stage", "commented")
            idx   = SOCIAL_STAGES.index(stage) if stage in SOCIAL_STAGES else 0
            if idx + 1 < len(SOCIAL_STAGES):
                row["stage"] = SOCIAL_STAGES[idx + 1]
            break
    save_social(rows)
    return redirect('/?tab=social')

@app.route('/social/kill/<sid>')
def social_kill(sid):
    rows = load_social()
    for row in rows:
        if row.get("id") == sid:
            row["stage"] = "dead"
            break
    save_social(rows)
    return redirect('/?tab=social')

# =========================
# UPLOAD QUEUE — drag & drop outreach_queue.csv into Railway
# GET  /upload-queue  — upload form
# POST /upload-queue  — receives CSV, merges with existing queue
# =========================
@app.route('/upload-queue', methods=["GET"])
def upload_queue_form():
    df      = load_data()
    pending = len(df[df["status"] == "pending"]) if len(df) else 0
    total   = len(df)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Upload Leads — Gray Horizons</title>
    <style>
      *{{box-sizing:border-box;margin:0;padding:0;}}
      body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}}
      .box{{background:#1e293b;border-radius:12px;padding:36px 32px;max-width:560px;width:100%;}}
      h2{{color:#22c55e;font-size:20px;margin-bottom:6px;}}
      .sub{{color:#64748b;font-size:13px;margin-bottom:24px;}}
      .stats{{background:#0f172a;border-radius:8px;padding:12px 16px;font-size:13px;color:#94a3b8;margin-bottom:24px;line-height:1.8;}}
      .stat-hi{{color:#38bdf8;font-weight:bold;}}
      label{{display:block;font-size:13px;color:#94a3b8;margin-bottom:8px;}}
      .drop-zone{{border:2px dashed #334155;border-radius:8px;padding:40px 20px;text-align:center;cursor:pointer;transition:border-color .2s;margin-bottom:20px;}}
      .drop-zone:hover,.drop-zone.over{{border-color:#22c55e;background:#0f2a1a;}}
      .drop-zone input{{display:none;}}
      .drop-icon{{font-size:36px;margin-bottom:8px;}}
      .drop-text{{color:#64748b;font-size:13px;}}
      .file-name{{color:#22c55e;font-size:13px;margin-top:8px;font-weight:bold;}}
      .btn{{background:#22c55e;color:#000;border:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:bold;cursor:pointer;width:100%;}}
      .btn:hover{{background:#16a34a;}}
      .note{{font-size:11px;color:#475569;margin-top:16px;line-height:1.6;}}
      a.back{{display:inline-block;margin-top:20px;color:#38bdf8;font-size:13px;}}
    </style>
    </head>
    <body>
    <div class="box">
      <h2>Upload Lead Queue</h2>
      <div class="sub">Loads your outreach_queue.csv directly into the dashboard.</div>

      <div class="stats">
        Current queue on Railway:<br>
        <span class="stat-hi">{total}</span> total leads &nbsp;·&nbsp;
        <span class="stat-hi">{pending}</span> pending
      </div>

      <form method="POST" action="/upload-queue" enctype="multipart/form-data" id="uploadForm">
        <div class="drop-zone" id="dropZone" onclick="document.getElementById('csvFile').click()">
          <input type="file" name="csv_file" id="csvFile" accept=".csv" onchange="showFile(this)">
          <div class="drop-icon">📂</div>
          <div class="drop-text">Click to select <strong>outreach_queue.csv</strong><br>or drag and drop it here</div>
          <div class="file-name" id="fileName"></div>
        </div>

        <div style="margin-bottom:16px;">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
            <input type="checkbox" name="merge" value="1" checked style="width:16px;height:16px;">
            <span style="font-size:13px;color:#94a3b8;">Merge with existing (preserve sent/skipped — only add new pending)</span>
          </label>
        </div>

        <button type="submit" class="btn">Upload & Load into Dashboard</button>
      </form>

      <div class="note">
        After upload, all leads appear in the Outreach tab with Send / Skip buttons.<br>
        Existing sent and skipped records are preserved when merge is checked.
      </div>

      <a class="back" href="/">← Back to Dashboard</a>
    </div>

    <script>
    function showFile(input) {{
      document.getElementById('fileName').textContent = input.files[0] ? input.files[0].name : '';
    }}
    var dz = document.getElementById('dropZone');
    dz.addEventListener('dragover', function(e){{ e.preventDefault(); dz.classList.add('over'); }});
    dz.addEventListener('dragleave', function(){{ dz.classList.remove('over'); }});
    dz.addEventListener('drop', function(e){{
      e.preventDefault(); dz.classList.remove('over');
      var f = e.dataTransfer.files[0];
      if (f) {{
        var dt = new DataTransfer(); dt.items.add(f);
        document.getElementById('csvFile').files = dt.files;
        showFile(document.getElementById('csvFile'));
      }}
    }});
    </script>
    </body>
    </html>
    """

@app.route('/upload-queue', methods=["POST"])
def upload_queue_post():
    file  = flask_request.files.get("csv_file")
    merge = flask_request.form.get("merge") == "1"

    if not file or not file.filename.endswith(".csv"):
        return "<p style='color:red;font-family:Arial;padding:40px;'>No valid CSV file received. <a href='/upload-queue' style='color:#38bdf8;'>Try again</a></p>", 400

    try:
        import io
        content  = file.read().decode("utf-8", errors="replace")
        uploaded = pd.read_csv(io.StringIO(content)).fillna("")

        for col in ["company","name","email","message","status","niche","subject","website"]:
            if col not in uploaded.columns:
                uploaded[col] = ""

        # Always force uploaded leads to pending — DB tracks what's actually sent
        uploaded["status"] = "pending"

        if merge:
            existing = load_data()
            # Keep sent/skipped from DB (source of truth); add only new emails
            done_emails = set(
                existing.loc[existing["status"].isin(["sent","skipped"]), "email"]
                .str.strip().str.lower().tolist()
            )
            existing_done = existing[existing["status"].isin(["sent","skipped"])]
            new_pending   = uploaded[
                ~uploaded["email"].str.strip().str.lower().isin(done_emails)
            ].copy()
            new_pending["status"] = "pending"
            merged = pd.concat([existing_done, new_pending], ignore_index=True)
        else:
            merged = uploaded

        save_data(merged)

        added   = len(merged[merged["status"] == "pending"])
        kept    = len(merged[merged["status"].isin(["sent","skipped"])])
        total   = len(merged)

        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Upload Complete</title>
        <style>body{{background:#0f172a;color:#e2e8f0;font-family:Arial;display:flex;align-items:center;justify-content:center;min-height:100vh;}}
        .box{{background:#1e293b;border-radius:12px;padding:40px;max-width:480px;width:100%;text-align:center;}}</style>
        </head>
        <body><div class="box">
          <div style="font-size:48px;margin-bottom:16px;">✅</div>
          <h2 style="color:#22c55e;margin-bottom:16px;">Upload Complete</h2>
          <div style="background:#0f172a;border-radius:8px;padding:16px;font-size:14px;line-height:2;margin-bottom:24px;">
            <div><span style="color:#94a3b8;">Total loaded:</span> <strong style="color:#38bdf8;">{total}</strong></div>
            <div><span style="color:#94a3b8;">Pending (ready to send):</span> <strong style="color:#22c55e;">{added}</strong></div>
            <div><span style="color:#94a3b8;">Preserved (sent/skipped):</span> <strong style="color:#64748b;">{kept}</strong></div>
          </div>
          <a href="/" style="display:inline-block;background:#22c55e;color:#000;padding:12px 32px;border-radius:8px;font-weight:bold;font-size:15px;text-decoration:none;">Go to Dashboard →</a>
        </div></body></html>
        """

    except Exception as e:
        return f"<p style='color:red;font-family:Arial;padding:40px;'>Upload failed: {e}<br><a href='/upload-queue' style='color:#38bdf8;'>Try again</a></p>", 500


# =========================
# WEBHOOKS — CALENDLY + STRIPE
# =========================
@app.route('/webhook/calendly', methods=['POST'])
def calendly_webhook():
    try:
        payload = flask_request.get_json(force=True) or {}
        from auto_proposal import handle_calendly_webhook
        result = handle_calendly_webhook(payload)
        # Also trigger Bland.ai call if booking has a phone number
        threading.Thread(
            target=_bland_call_calendly,
            args=(payload,),
            daemon=True,
        ).start()
        return result, 200
    except Exception as e:
        return {"error": str(e)}, 500


def _bland_call_calendly(payload: dict):
    try:
        from bland_caller import call_from_calendly
        call_from_calendly(payload)
    except Exception as e:
        print(f"[BLAND] Calendly trigger error: {e}")


@app.route('/call-lead', methods=['POST'])
def call_lead():
    """Manually trigger a Bland.ai call for a specific lead from the dashboard."""
    try:
        data  = flask_request.get_json(force=True) or {}
        from bland_caller import make_call
        result = make_call(
            name    = data.get("name", ""),
            phone   = data.get("phone", ""),
            company = data.get("company", ""),
            niche   = data.get("niche", "hvac"),
            email   = data.get("email", ""),
        )
        return result, 200
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/signals')
def signals_page():
    """Landing page for Edge Engine paid signals subscription."""
    stripe_link = os.getenv("STRIPE_SIGNALS_LINK", "#")
    try:
        from signals_mailer import get_active_subscribers
        sub_count = len(get_active_subscribers())
    except Exception:
        sub_count = 0
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Edge Engine Signals</title>
<style>
  body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:0;}}
  .wrap{{max-width:580px;margin:60px auto;padding:0 20px;}}
  h1{{color:#38bdf8;font-size:28px;}}
  .price{{font-size:48px;color:#22c55e;font-weight:bold;margin:24px 0 4px;}}
  .mo{{color:#94a3b8;font-size:16px;}}
  .btn{{display:block;background:#22c55e;color:#000;padding:18px;text-align:center;border-radius:8px;font-weight:bold;font-size:18px;text-decoration:none;margin:32px 0;}}
  ul{{color:#94a3b8;line-height:2;padding-left:20px;}}
  .badge{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;margin:20px 0;font-size:14px;color:#64748b;}}
</style>
</head>
<body>
<div class="wrap">
  <h1>Gray Horizons Edge Engine</h1>
  <p style="color:#94a3b8;">Daily AI-powered signals for stocks, crypto, and sports.</p>
  <div class="price">$49<span class="mo">/month</span></div>
  <ul>
    <li>Daily stock signals with entry points + confidence scores</li>
    <li>Crypto signals with trend analysis</li>
    <li>Sports edge picks with Kelly criterion bet sizing</li>
    <li>Congressional trading alerts</li>
    <li>Delivered to your inbox every morning</li>
    <li>Cancel anytime</li>
  </ul>
  <a href="{stripe_link}" class="btn">Subscribe — $49/month</a>
  <div class="badge">{sub_count} active subscribers · Powered by Gray Horizons AI</div>
  <p style="color:#475569;font-size:12px;">Not financial advice. Signals are algorithmic and for informational purposes only.</p>
</div>
</body>
</html>"""


@app.route('/webhook/stripe-signals', methods=['POST'])
def stripe_signals_webhook():
    """Stripe webhook for signals subscription payment — adds subscriber."""
    try:
        payload    = flask_request.get_json(force=True) or {}
        event_type = payload.get("type", "")
        if event_type == "checkout.session.completed":
            data   = payload.get("data", {}).get("object", {})
            email  = data.get("customer_details", {}).get("email", "")
            name   = data.get("customer_details", {}).get("name", "")
            cust   = data.get("customer", "")
            if email:
                from signals_mailer import add_subscriber, send_welcome_email
                add_subscriber(email, name, cust)
                send_welcome_email(email, name)
        elif event_type in ("customer.subscription.deleted", "invoice.payment_failed"):
            data  = payload.get("data", {}).get("object", {})
            email = data.get("customer_email", "")
            if email:
                from signals_mailer import remove_subscriber
                remove_subscriber(email)
        return {"received": True}, 200
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """On successful payment, send onboarding email automatically."""
    try:
        import json as _json
        payload = flask_request.get_json(force=True) or {}
        event_type = payload.get("type", "")
        if event_type == "checkout.session.completed":
            data     = payload.get("data", {}).get("object", {})
            email    = data.get("customer_details", {}).get("email", "")
            name     = data.get("customer_details", {}).get("name", "")
            amount   = data.get("amount_total", 0) / 100
            niche    = data.get("metadata", {}).get("niche", "hvac")
            _send_onboarding(name, email, amount)
            try:
                from performance_tracker import record_payment
                record_payment(niche, amount)
            except Exception:
                pass
        return {"received": True}, 200
    except Exception as e:
        return {"error": str(e)}, 500


def _send_onboarding(name: str, email: str, amount: float):
    import requests as _req
    key  = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("FROM_EMAIL", "jordan@grayhorizonsenterprise.com")
    cal  = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
    if not key or not email:
        return
    first = name.split()[0] if name else "there"
    body  = f"""Hey {first},

Payment confirmed — thank you! You're officially on.

Here's what happens next:

1. Your AI Lead Follow-Up System will be live within 5 business days
2. You'll receive your custom email sequences and dashboard access via this email
3. Book your kickoff call here so we can walk through the setup together: {cal}

If you have any questions before then, just reply to this email.

Gray Horizons Enterprise
https://grayhorizonsenterprise.com"""

    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": from_email, "name": "Gray Horizons Enterprise"},
        "subject": "You're in — here's what happens next",
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        _req.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=10,
        )
        print(f"[ONBOARD] Sent to {email} (${amount})")
    except Exception as e:
        print(f"[ONBOARD] Error: {e}")


# =========================
# HOT LEADS API
# =========================
@app.route('/api/hot-leads')
def api_hot_leads():
    try:
        import json as _json
        hot_file = os.path.join(DATA_DIR, "hot_leads.json")
        if os.path.exists(hot_file):
            with open(hot_file) as f:
                return _json.load(f), 200
        return [], 200
    except Exception:
        return [], 200


# =========================
# HEALTH CHECK
# =========================
@app.route('/health')
def health():
    status = "running" if pipeline_running else "idle"
    leads = 0
    try:
        leads = len(pd.read_csv(CSV_FILE))
    except Exception:
        pass
    return f"OK | pipeline={status} | leads={leads}"


@app.route('/linkedin-dms', methods=['GET', 'POST'])
def linkedin_dms():
    import json
    from pathlib import Path
    dm_file = Path(__file__).parent / "linkedin_dm_queue.json"
    action  = request.form.get("action", "")
    dm_id   = request.form.get("dm_id", "")

    queue = json.loads(dm_file.read_text(encoding="utf-8")) if dm_file.exists() else []

    if action == "mark_sent" and dm_id:
        for e in queue:
            if str(e["id"]) == dm_id:
                e["status"]  = "sent"
                e["sent_at"] = datetime.now().isoformat()
        dm_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

    if action == "scan":
        try:
            from linkedin_dm_drafter import run_dm_scan
            run_dm_scan()
            queue = json.loads(dm_file.read_text(encoding="utf-8")) if dm_file.exists() else []
        except Exception as e:
            pass

    pending = [e for e in queue if e.get("status") == "pending"]
    sent    = [e for e in queue if e.get("status") == "sent"]

    rows = ""
    for e in pending[:30]:
        rows += f"""
        <div style='background:#1e293b;border-radius:10px;padding:16px;margin-bottom:14px;border-left:4px solid #38bdf8;'>
          <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>
            <div>
              <span style='color:#38bdf8;font-weight:700;font-size:14px;'>{e['name']}</span>
              <span style='color:#64748b;font-size:12px;margin-left:10px;'>{e['niche']}</span>
            </div>
            <a href='{e['profile_url']}' target='_blank' style='color:#0ea5e9;font-size:12px;'>View Profile</a>
          </div>
          <div style='background:#0f172a;border-radius:6px;padding:12px;color:#e2e8f0;font-size:13px;line-height:1.6;margin-bottom:10px;white-space:pre-wrap;'>{e['dm_text']}</div>
          <form method='POST' style='display:inline;'>
            <input type='hidden' name='action' value='mark_sent'>
            <input type='hidden' name='dm_id' value='{e['id']}'>
            <button type='submit' style='background:#22c55e;color:#000;border:none;padding:6px 16px;border-radius:5px;font-weight:700;cursor:pointer;font-size:12px;'>Mark Sent</button>
          </form>
        </div>"""

    html = f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>
    <title>LinkedIn DM Queue</title>
    <style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0f172a;font-family:Arial,sans-serif;padding:24px;color:#e2e8f0;}}</style>
    </head><body>
    <div style='max-width:900px;margin:0 auto;'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;'>
        <h1 style='color:#38bdf8;font-size:22px;'>LinkedIn DM Queue</h1>
        <div>
          <span style='color:#22c55e;font-size:13px;margin-right:16px;'>{len(pending)} pending / {len(sent)} sent</span>
          <form method='POST' style='display:inline;'>
            <input type='hidden' name='action' value='scan'>
            <button type='submit' style='background:#38bdf8;color:#000;border:none;padding:8px 18px;border-radius:6px;font-weight:700;cursor:pointer;'>Scan for New Profiles</button>
          </form>
        </div>
      </div>
      <p style='color:#64748b;font-size:12px;margin-bottom:20px;'>Copy each DM, paste into LinkedIn, click "Mark Sent" to track.</p>
      {rows if rows else "<p style='color:#64748b;'>No pending DMs. Click Scan to find new profiles.</p>"}
    </div></body></html>"""
    return html


@app.route('/upwork-draft', methods=['GET', 'POST'])
def upwork_draft_inline():
    """Handles the Paste Job form from the Upwork dashboard tab."""
    proposal = ""
    score = 0
    title = ""
    error = ""
    job_text = ""
    if flask_request.method == 'POST':
        job_text = flask_request.form.get('job_text', '').strip()
        if job_text:
            try:
                from upwork_scout import score_job, draft_proposal
                lines = job_text.split('\n')
                title = lines[0][:100] if lines else "Job"
                score = score_job(title, job_text)
                proposal = draft_proposal(title, job_text)
            except Exception as e:
                error = str(e)
    score_color = "#22c55e" if score >= 75 else "#f59e0b" if score >= 55 else "#ef4444"
    return f"""<!DOCTYPE html>
<html><head><title>Upwork Draft</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;max-width:800px;margin:0 auto;padding:24px;}}
textarea{{width:100%;background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:12px;font-size:14px;}}
button{{background:#14a800;color:#fff;border:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;}}
pre{{background:#1e293b;padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;border:1px solid #22c55e;}}
h1{{color:#14a800;}}h2{{color:#94a3b8;font-size:16px;}}
a{{color:#38bdf8;}}
</style></head><body>
<h1>Upwork Proposal Drafter</h1>
<a href='javascript:window.close()' style='font-size:13px;'>Close window</a>
<form method='POST' style='margin-top:16px;'>
  <textarea name='job_text' rows='10' placeholder='Paste full job description here...'>{job_text}</textarea>
  <br><br><button type='submit'>Score + Draft Proposal</button>
</form>
{f'''<div style="margin-top:24px;padding:16px;background:#1e293b;border-radius:8px;border-left:4px solid {score_color};">
  <h2>Score: <span style="color:{score_color};">{score}/100</span> — {title}</h2>
  {f'<p style="color:#ef4444;">{error}</p>' if error else ''}
  <div style="margin-top:8px;"><button onclick="navigator.clipboard.writeText(document.getElementById('prop').innerText).then(()=>this.textContent='Copied!')" style="background:#0ea5e9;padding:8px 20px;font-size:13px;">Copy Proposal</button></div>
  <pre id="prop" style="margin-top:12px;">{proposal}</pre>
  <p style="color:#64748b;font-size:12px;margin-top:12px;">Boost: use 15-20 connects for top placement. Apply to jobs under 2 hours old.</p>
</div>''' if flask_request.method=='POST' else ''}
</body></html>"""


@app.route('/upwork', methods=['GET', 'POST'])
def upwork_drafter():
    proposal = ""
    score = 0
    title = ""
    error = ""
    opportunities_html = ""

    # Load scouted opportunities
    opp_file = os.path.join(DATA_DIR, "upwork_opportunities.json")
    try:
        import json
        opps = json.loads(open(opp_file).read()) if os.path.exists(opp_file) else []
        for o in opps[:10]:
            clr = "#22c55e" if o['score'] >= 75 else "#f59e0b" if o['score'] >= 55 else "#ef4444"
            opportunities_html += f"""
            <div style='background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:12px;'>
              <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>
                <a href='{o["link"]}' target='_blank' style='color:#38bdf8;font-weight:600;font-size:15px;text-decoration:none;'>{o["title"][:80]}</a>
                <span style='background:{clr};color:#000;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;'>Score: {o["score"]}</span>
              </div>
              <p style='color:#94a3b8;font-size:12px;margin:0 0 8px 0;'>{o["description"][:200]}...</p>
              <details style='margin-top:8px;'>
                <summary style='color:#38bdf8;cursor:pointer;font-size:13px;'>View drafted proposal</summary>
                <pre style='background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;font-size:12px;white-space:pre-wrap;margin-top:8px;'>{o["proposal"]}</pre>
              </details>
            </div>"""
    except Exception as e:
        opportunities_html = f"<p style='color:#ef4444;'>No scouted jobs yet: {e}</p>"

    if flask_request.method == 'POST':
        job_text = flask_request.form.get('job_text', '').strip()
        if job_text:
            try:
                from upwork_scout import score_job, draft_proposal
                lines = job_text.split('\n')
                title = lines[0][:100] if lines else "Job"
                score = score_job(title, job_text)
                proposal = draft_proposal(title, job_text)
            except Exception as e:
                error = str(e)

    score_color = "#22c55e" if score >= 75 else "#f59e0b" if score >= 55 else "#ef4444"
    return f"""<!DOCTYPE html>
<html><head><title>Upwork 2nd Brain</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;}}
textarea{{width:100%;background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:12px;font-size:14px;}}
button{{background:#0ea5e9;color:#fff;border:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;}}
pre{{background:#1e293b;padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;border:1px solid #22c55e;}}
h1{{color:#38bdf8;}}h2{{color:#94a3b8;font-size:16px;}}
</style></head><body>
<h1>Upwork 2nd Brain</h1>
<p style='color:#94a3b8;'>Paste any job description below. System scores it and drafts your proposal instantly.</p>
<form method='POST'>
  <textarea name='job_text' rows='10' placeholder='Paste full job description here...'>{flask_request.form.get('job_text','') if flask_request.method=='POST' else ''}</textarea>
  <br><br><button type='submit'>Score + Draft Proposal</button>
</form>
{f'''<div style="margin-top:24px;padding:16px;background:#1e293b;border-radius:8px;border-left:4px solid {score_color};">
  <h2>Score: <span style="color:{score_color};">{score}/100</span> — {title}</h2>
  {f'<p style="color:#ef4444;">{error}</p>' if error else ''}
  <h2 style="margin-top:16px;">Drafted Proposal — copy and paste into Upwork:</h2>
  <pre>{proposal}</pre>
</div>''' if flask_request.method=='POST' else ''}
<hr style='border-color:#334155;margin:32px 0;'>
<h2 style='color:#38bdf8;font-size:18px;'>Auto-Scouted Jobs (updated every 2 hrs)</h2>
{opportunities_html if opportunities_html else '<p style="color:#94a3b8;">Scout running — check back in 2 hours or run upwork_scout.py locally.</p>'}
</body></html>"""


def _send_sms_textbelt(to_phone: str, message: str) -> bool:
    """Send SMS via carrier email gateways — free, no account needed.
    Blasts all major US carriers simultaneously; the matching one delivers."""
    import smtplib as _smtp
    from email.mime.text import MIMEText as _MIMEText

    sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
    sender  = VERIFIED_SENDER
    if not sg_key:
        print("[SMS] SENDGRID_API_KEY not set")
        return False

    digits = "".join(c for c in str(to_phone) if c.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        print(f"[SMS] Invalid phone: {to_phone}")
        return False

    carriers = [
        "txt.att.net",
        "vtext.com",
        "tmomail.net",
        "messaging.sprintpcs.com",
        "sms.myboostmobile.com",
        "sms.cricketwireless.net",
        "mymetropcs.com",
        "email.uscc.net",
        "msg.fi.google.com",
    ]

    sent = 0
    try:
        server = _smtp.SMTP("smtp.sendgrid.net", 587, timeout=10)
        server.starttls()
        server.login("apikey", sg_key)
        for carrier in carriers:
            to_addr = f"{digits}@{carrier}"
            msg = _MIMEText(message)
            msg["From"] = sender
            msg["To"]   = to_addr
            msg["Subject"] = ""
            try:
                server.sendmail(gmail_user, [to_addr], msg.as_string())
                sent += 1
            except Exception:
                pass
        server.quit()
    except Exception as e:
        print(f"[SMS] Gateway exception: {e}")
        return False

    print(f"[SMS] Carrier blast -> {to_phone} | {sent}/{len(carriers)} gateways accepted")
    return sent > 0


@app.route('/confirm-email', methods=['GET', 'POST'])
def confirm_email():
    """Caller taps link from SMS, types their email, booking link fires instantly."""
    import secrets as _secrets
    import re as _re

    if flask_request.method == 'POST':
        token    = flask_request.form.get('token', '').strip()
        email    = flask_request.form.get('email', '').strip().lower()
        if not _re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return confirm_email_page(token, error="Please enter a valid email address.")

        # Look up lead by token
        lead = None
        try:
            conn = _get_db()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name, phone, business_type FROM vapi_leads WHERE confirm_token=%s", (token,))
                    lead = cur.fetchone()
                    if lead:
                        cur.execute("UPDATE vapi_leads SET email=%s, email_sent=FALSE WHERE confirm_token=%s", (email, token))
                conn.commit()
                conn.close()
        except Exception as _e:
            print(f"[CONFIRM EMAIL] DB error: {_e}")

        if not lead:
            return "<html><body style='background:#0f172a;color:#ef4444;font-family:Arial;padding:40px;text-align:center;'><h2>Link expired or invalid.</h2><p>Please call us again at (909) 927-6310.</p></body></html>"

        lead_id, name, phone, business_type = lead
        calendly    = os.getenv("CALENDLY_URL", "https://calendly.com/grayhorizonsenterprise/30min")
        upload_url  = f"{DASHBOARD_URL}/job-upload"
        sender_name = "Gray Horizons Enterprise"

        caller_html = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
  <p>Hey {name},</p>
  <p>Thanks for calling Gray Horizons Enterprise. Here is your booking link:</p>
  <p style="text-align:center;margin:28px 0;">
    <a href="{calendly}" style="background:#1a73e8;color:#fff;padding:12px 28px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:15px;">
      Book Your Free 15-Minute Call
    </a>
  </p>
  <p>We will show you exactly what the system looks like for {business_type or 'your business'}. No pitch, just the demo.</p>
  <p style="margin-top:24px;padding:16px;background:#f0f9ff;border-radius:8px;border-left:4px solid #0ea5e9;">
    <b>Your client portal is ready.</b> Submit project details before the call so our team is already prepared.<br><br>
    <a href="{upload_url}" style="background:#0ea5e9;color:#fff;padding:10px 22px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:8px;">
      Open Your Client Portal
    </a>
  </p>
  <p>Talk soon,<br>Gray Horizons Enterprise</p>
</div>"""

        sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
        sent = False
        if sg_key:
            sent = _send_via_sendgrid(sg_key, VERIFIED_SENDER, sender_name, email,
                                      "Your booking link — Gray Horizons Enterprise",
                                      caller_html, name, "")
        if sent:
            try:
                conn = _get_db()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE vapi_leads SET email=%s, email_sent=TRUE WHERE confirm_token=%s", (email, token))
                    conn.commit()
                    conn.close()
            except Exception:
                pass
            print(f"[CONFIRM EMAIL] Booking link sent to {email} for {name}")

        return f"""<!DOCTYPE html>
<html><head><title>You're all set</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.card{{background:#1e293b;border-radius:12px;padding:40px 32px;max-width:420px;text-align:center;}}
h2{{color:#22c55e;margin-top:0;}} a{{color:#38bdf8;}}</style>
</head><body><div class='card'>
<h2>You're all set, {name}.</h2>
<p>Your booking link is on its way to <b>{email}</b>.</p>
<p>Check your inbox — it arrives within 30 seconds.</p>
<p style='margin-top:28px;font-size:13px;color:#475569;'>Gray Horizons Enterprise &nbsp;·&nbsp; grayhorizonsenterprise.com</p>
</div></body></html>"""

    # GET — show the form
    token = flask_request.args.get('t', '')
    return confirm_email_page(token)


def confirm_email_page(token, error=None):
    name = "there"
    try:
        conn = _get_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM vapi_leads WHERE confirm_token=%s", (token,))
                row = cur.fetchone()
                if row:
                    name = row[0].split()[0] if row[0] else "there"
            conn.close()
    except Exception:
        pass

    error_html = f"<p style='color:#ef4444;margin-bottom:16px;'>{error}</p>" if error else ""
    return f"""<!DOCTYPE html>
<html><head><title>Confirm Your Email — Gray Horizons Enterprise</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>
body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.card{{background:#1e293b;border-radius:12px;padding:40px 32px;max-width:420px;width:90%;}}
h2{{color:#38bdf8;margin-top:0;font-size:22px;}}
p{{color:#94a3b8;line-height:1.6;}}
input{{width:100%;padding:12px 14px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:16px;box-sizing:border-box;margin-top:8px;}}
input:focus{{outline:none;border-color:#38bdf8;}}
button{{width:100%;padding:13px;background:#1a73e8;color:#fff;border:none;border-radius:6px;font-size:16px;font-weight:bold;cursor:pointer;margin-top:16px;}}
button:hover{{background:#1557b0;}}
.brand{{margin-top:28px;font-size:12px;color:#475569;text-align:center;}}
</style>
</head><body><div class='card'>
<h2>One quick step, {name}.</h2>
<p>Enter your email below and we'll send your booking link instantly.</p>
{error_html}
<form method='POST' action='/confirm-email'>
  <input type='hidden' name='token' value='{token}'>
  <label style='font-size:13px;color:#64748b;'>Your email address</label>
  <input type='email' name='email' placeholder='you@example.com' required autofocus>
  <button type='submit'>Send My Booking Link</button>
</form>
<div class='brand'>Gray Horizons Enterprise &nbsp;·&nbsp; grayhorizonsenterprise.com</div>
</div></body></html>"""


@app.route('/calls')
def calls_dashboard():
    """Live inbound call leads captured by Jordan."""
    rows = []
    try:
        conn = _get_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, email, phone, business_type, raw_email, email_sent, created_at, confirm_token
                    FROM vapi_leads ORDER BY created_at DESC LIMIT 100
                """)
                rows = cur.fetchall()
            conn.close()
    except Exception as e:
        print(f"[CALLS] DB error: {e}")

    rows_html = ""
    for r in rows:
        name, email, phone, biz, raw_email, email_sent, created_at, confirm_token = r
        ts = created_at.strftime("%b %d %I:%M %p") if created_at else ""
        email_badge = (
            "<span style='color:#22c55e;font-weight:bold;'>Sent</span>" if email_sent
            else "<span style='color:#ef4444;'>Not sent</span>"
        )
        email_display = email or f"<span style='color:#f97316;'>{raw_email or 'Not given'}</span>"
        confirm_link = (
            f"<a href='/confirm-email?t={confirm_token}' target='_blank' "
            f"style='background:#1a73e8;color:#fff;padding:4px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold;'>Send Email</a>"
            if confirm_token else "—"
        )
        rows_html += f"""
        <tr style='border-bottom:1px solid #1e293b;'>
          <td style='padding:12px 16px;color:#e2e8f0;'>{ts}</td>
          <td style='padding:12px 16px;color:#f1f5f9;font-weight:bold;'>{name}</td>
          <td style='padding:12px 16px;color:#94a3b8;'>{email_display}</td>
          <td style='padding:12px 16px;color:#94a3b8;'>{phone or '—'}</td>
          <td style='padding:12px 16px;color:#94a3b8;'>{biz or '—'}</td>
          <td style='padding:12px 16px;'>{email_badge}</td>
          <td style='padding:12px 16px;'>{confirm_link}</td>
        </tr>"""

    empty = "<tr><td colspan='7' style='padding:40px;text-align:center;color:#475569;'>No calls captured yet. Make a test call to Jordan at (909) 927-6310.</td></tr>" if not rows else ""

    return f"""<!DOCTYPE html>
<html><head><title>Inbound Calls — GHE</title>
<meta http-equiv='refresh' content='15'>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;margin:0;padding:32px;}}
h1{{color:#38bdf8;margin-bottom:4px;}}
.sub{{color:#475569;font-size:13px;margin-bottom:28px;}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;}}
th{{background:#0f172a;padding:12px 16px;text-align:left;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:.05em;}}
tr:hover{{background:#263348;}}
.back{{color:#38bdf8;text-decoration:none;font-size:13px;}}</style>
</head><body>
<a href='/' class='back'>← Dashboard</a>
<h1 style='margin-top:16px;'>Inbound Call Leads</h1>
<div class='sub'>Jordan captures these mid-call. Auto-refreshes every 15 seconds. {len(rows)} total.</div>
<table>
  <thead><tr>
    <th>Time</th><th>Name</th><th>Email</th><th>Phone</th><th>Business</th><th>Status</th><th>Action</th>
  </tr></thead>
  <tbody>{rows_html}{empty}</tbody>
</table>
</body></html>"""


@app.route('/vapi-webhook', methods=['POST'])
def vapi_webhook():
    """Receives Vapi end-of-call events. Fires owner alert + caller email + SMS immediately."""
    import re as _re
    try:
        data  = flask_request.get_json(silent=True) or {}
        event = data.get("message", {}).get("type", "")
        if event != "end-of-call-report":
            return "ok", 200

        msg        = data.get("message", {})
        artifact   = msg.get("artifact", {})
        transcript = artifact.get("transcript", "")
        call_obj   = msg.get("call", {})
        duration_s = int(msg.get("durationSeconds", 0))
        caller_num = call_obj.get("customer", {}).get("number", "unknown")

        # Pull email from transcript
        emails = _re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", transcript)
        to_email = emails[0].lower() if emails else ""

        # Pull caller name
        name = "the caller"
        name_match = _re.search(r"(?:my name is|this is)\s+([A-Z][a-z]+)", transcript)
        if name_match:
            name = name_match.group(1)

        # Detect inspection/photo keywords
        photo_keywords = ["photo", "picture", "inspect", "estimate", "quote", "job site",
                          "look at", "come out", "come by", "measure", "assess", "bathroom",
                          "roof", "hvac", "remodel", "repair", "install"]
        wants_photos = any(kw in transcript.lower() for kw in photo_keywords)
        upload_url   = f"{DASHBOARD_URL}/job-upload"

        sender_name = "Gray Horizons Enterprise"
        minutes     = duration_s // 60
        seconds     = duration_s % 60
        duration_str = f"{minutes}m {seconds}s"

        # ── 1. Owner alert — fires on EVERY call, regardless of email collected ──
        owner_email = "grayhorizonsenterprise@gmail.com"
        owner_subject = f"New call: {name} ({caller_num}) — {duration_str}"
        owner_html = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;padding:24px;">
  <h2 style="color:#1a73e8;margin-top:0;">New Inbound Call — Jordan</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
    <tr><td style="padding:6px 12px;background:#f8fafc;font-weight:bold;width:140px;">Caller</td><td style="padding:6px 12px;">{name}</td></tr>
    <tr><td style="padding:6px 12px;background:#f1f5f9;font-weight:bold;">Phone</td><td style="padding:6px 12px;">{caller_num}</td></tr>
    <tr><td style="padding:6px 12px;background:#f8fafc;font-weight:bold;">Email given</td><td style="padding:6px 12px;">{to_email if to_email else 'Not collected'}</td></tr>
    <tr><td style="padding:6px 12px;background:#f1f5f9;font-weight:bold;">Duration</td><td style="padding:6px 12px;">{duration_str}</td></tr>
    <tr><td style="padding:6px 12px;background:#f8fafc;font-weight:bold;">Wants photos</td><td style="padding:6px 12px;">{'Yes' if wants_photos else 'No'}</td></tr>
  </table>
  <h3 style="color:#475569;">Transcript</h3>
  <pre style="background:#f8fafc;padding:16px;border-radius:6px;font-size:13px;white-space:pre-wrap;">{transcript[:2000]}</pre>
  {'<p><a href="' + upload_url + '" style="color:#1a73e8;">View client portal</a></p>' if wants_photos else ''}
</div>"""
        sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
        if sg_key:
            _send_via_sendgrid(sg_key, VERIFIED_SENDER, sender_name, owner_email, owner_subject, owner_html, "Curtis", "GHE")
        print(f"[VAPI WEBHOOK] Owner alert sent — caller: {name} {caller_num} | email: {to_email or 'none'}")

        # ── 2. Caller follow-up email (only if email was collected) ──────────────
        if to_email:
            upload_section = ""
            if wants_photos:
                upload_section = f"""
  <p style="margin-top:24px;padding:16px;background:#f0f9ff;border-radius:8px;border-left:4px solid #0ea5e9;">
    <b>Your personalized client portal is ready.</b> Submit your project details and photos using your secure access link below. Our team reviews everything before your call.<br><br>
    <a href="{upload_url}" style="background:#0ea5e9;color:#fff;padding:10px 22px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:8px;">
      Open Your Client Portal
    </a>
  </p>"""

            caller_subject = "Your booking link from Gray Horizons Enterprise"
            caller_html = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
  <p>Hey {name},</p>
  <p>Thanks for calling Gray Horizons Enterprise. As promised, here is your link to book a free 15-minute call with our team:</p>
  <p style="text-align:center;margin:28px 0;">
    <a href="https://calendly.com/grayhorizonsenterprise/30min"
       style="background:#1a73e8;color:#fff;padding:12px 28px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:15px;">
      Book Your Free 15-Minute Call
    </a>
  </p>
  <p>We will show you exactly what the system looks like for your type of business. No pitch, just the demo.</p>{upload_section}
  <p>You can also browse our services at <a href="https://grayhorizonsenterprise.com">grayhorizonsenterprise.com</a>.</p>
  <p>Talk soon,<br>Gray Horizons Enterprise</p>
</div>"""
            sent = False
            sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
            if sg_key:
                sent = _send_via_sendgrid(sg_key, VERIFIED_SENDER, sender_name, to_email, caller_subject, caller_html, name, "")
            print(f"[VAPI WEBHOOK] Caller email {'sent' if sent else 'FAILED'} -> {to_email}")

        # SMS sent by /vapi-collect when tool fires mid-call — do not duplicate here

    except Exception as e:
        print(f"[VAPI WEBHOOK] Error: {e}")
    return "ok", 200


def _parse_spoken_email(transcript: str) -> str:
    """Parse email spoken aloud: 'grayhorizons at gmail dot com' -> grayhorizons@gmail.com"""
    import re as _re
    # Standard format first
    m = _re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", transcript)
    if m:
        return m[0].lower()
    # Spoken format: "word at word dot com/net/org/io"
    spoken = _re.search(
        r"([\w]+(?:\s+[\w]+)*)\s+at\s+([\w]+(?:\s+[\w]+)*)\s+dot\s+(com|net|org|io|co|us|biz)",
        transcript, _re.IGNORECASE
    )
    if spoken:
        local  = spoken.group(1).strip().replace(" ", "").lower()
        domain = spoken.group(2).strip().replace(" ", "").lower()
        tld    = spoken.group(3).lower()
        return f"{local}@{domain}.{tld}"
    return ""


_sms_sent_ids: set = set()  # dedup: one SMS per tool_call_id

@app.route('/vapi-collect', methods=['POST'])
def vapi_collect():
    """Mid-call tool endpoint. Jordan calls this the moment name+email+phone are collected.
    Fires email and SMS immediately — caller receives it before the call even ends."""
    import re as _re
    try:
        data = flask_request.get_json(silent=True) or {}
        # Vapi wraps tool call params under message.toolCallList[0].function.arguments
        tool_calls = data.get("message", {}).get("toolCallList", [])
        args = {}
        tool_call_id = ""
        if tool_calls:
            raw_args = tool_calls[0].get("function", {}).get("arguments", {})
            if isinstance(raw_args, str):
                import json as _json
                try:
                    args = _json.loads(raw_args)
                except Exception:
                    args = {}
            else:
                args = raw_args
            tool_call_id = tool_calls[0].get("id", "")
        if not args:
            args = data  # fallback if called directly

        name          = str(args.get("name", "there")).strip()
        raw_email     = str(args.get("email", "")).strip()
        phone         = str(args.get("phone", "")).strip()
        business_type = str(args.get("business_type", "your business")).strip()

        # Parse spoken email if needed
        to_email = _parse_spoken_email(raw_email) if raw_email else ""

        upload_url  = f"{DASHBOARD_URL}/job-upload"
        sender_name = "Gray Horizons Enterprise"
        calendly    = "https://calendly.com/grayhorizonsenterprise/30min"

        print(f"[VAPI COLLECT] name={name} email={to_email} phone={phone} biz={business_type}")

        # ── Save to DB immediately — before any email/SMS attempt ────────────────
        import secrets as _sec
        confirm_token = _sec.token_urlsafe(20)
        try:
            conn = _get_db()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO vapi_leads (name, email, phone, business_type, raw_email, confirm_token)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (name, to_email or raw_email, phone, business_type, raw_email, confirm_token))
                conn.commit()
                conn.close()
        except Exception as _e:
            print(f"[VAPI COLLECT] DB save error: {_e}")

        # ── Owner alert ──────────────────────────────────────────────────────────
        owner_html = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;padding:24px;">
  <h2 style="color:#22c55e;margin-top:0;">Lead Captured — Mid-Call</h2>
  <table style="width:100%;border-collapse:collapse;">
    <tr><td style="padding:6px 12px;background:#f8fafc;font-weight:bold;width:140px;">Name</td><td style="padding:6px 12px;">{name}</td></tr>
    <tr><td style="padding:6px 12px;background:#f1f5f9;font-weight:bold;">Email</td><td style="padding:6px 12px;">{to_email or raw_email}</td></tr>
    <tr><td style="padding:6px 12px;background:#f8fafc;font-weight:bold;">Phone</td><td style="padding:6px 12px;">{phone or 'Not given'}</td></tr>
    <tr><td style="padding:6px 12px;background:#f1f5f9;font-weight:bold;">Business</td><td style="padding:6px 12px;">{business_type}</td></tr>
  </table>
</div>"""
        sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
        if sg_key:
            _send_via_sendgrid(sg_key, VERIFIED_SENDER, sender_name,
                               "grayhorizonsenterprise@gmail.com",
                               f"Lead captured: {name} — {business_type}",
                               owner_html, "Curtis", "GHE")

        # ── Caller email ─────────────────────────────────────────────────────────
        if to_email:
            caller_html = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
  <p>Hey {name},</p>
  <p>Thanks for calling Gray Horizons Enterprise. Here is your booking link as promised:</p>
  <p style="text-align:center;margin:28px 0;">
    <a href="{calendly}"
       style="background:#1a73e8;color:#fff;padding:12px 28px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:15px;">
      Book Your Free 15-Minute Call
    </a>
  </p>
  <p>We specialize in AI automation for {business_type}. The 15-minute call is a live demo built around your exact situation.</p>
  <p style="margin-top:24px;padding:16px;background:#f0f9ff;border-radius:8px;border-left:4px solid #0ea5e9;">
    <b>Your personalized client portal is ready.</b> Submit your project details through your secure onboarding link before the call so our team is already prepared.<br><br>
    <a href="{upload_url}" style="background:#0ea5e9;color:#fff;padding:10px 22px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:8px;">
      Open Your Client Portal
    </a>
  </p>
  <p>Talk soon,<br>Gray Horizons Enterprise</p>
</div>"""
            sent = False
            sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
            if sg_key:
                sent = _send_via_sendgrid(sg_key, VERIFIED_SENDER, sender_name,
                                          to_email, f"Your booking link — Gray Horizons Enterprise",
                                          caller_html, name, "")
            print(f"[VAPI COLLECT] Caller email {'sent' if sent else 'FAILED'} -> {to_email}")
            if sent:
                try:
                    conn = _get_db()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE vapi_leads SET email_sent=TRUE WHERE email=%s", (to_email,))
                        conn.commit()
                        conn.close()
                except Exception:
                    pass

        # ── SMS to caller — one per tool_call_id to prevent Vapi retry duplicate sends ─
        if phone and tool_call_id not in _sms_sent_ids:
            _sms_sent_ids.add(tool_call_id)
            sms = (f"Hi {name}, this is Gray Horizons Enterprise. Book your free 15-min demo here: "
                   f"calendly.com/grayhorizonsenterprise/30min")
            sms_ok = _send_sms_textbelt(phone, sms)
            print(f"[VAPI COLLECT] SMS {'sent' if sms_ok else 'FAILED'} -> {phone}")
        elif phone:
            print(f"[VAPI COLLECT] SMS skipped — duplicate tool_call_id {tool_call_id}")

    except Exception as e:
        print(f"[VAPI COLLECT] Error: {e}")

    # Vapi requires a result response to continue the call
    return {
        "results": [{
            "toolCallId": tool_call_id if 'tool_call_id' in dir() else "",
            "result": "Contact info received. Follow-up sent."
        }]
    }, 200


@app.route('/performance')
def performance():
    try:
        from performance_tracker import get_summary
        return f"<pre style='font-family:monospace;padding:24px;background:#0f172a;color:#e2e8f0;'>{get_summary()}</pre>"
    except Exception as e:
        return f"No performance data yet: {e}"


# ── Job Photo Upload ──────────────────────────────────────────────────────────
import uuid as _uuid

PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_photos")
os.makedirs(PHOTO_DIR, exist_ok=True)

@app.route('/job-upload', methods=["GET"])
def job_upload_form():
    token = flask_request.args.get("t", "")
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Upload Job Photos</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;}}
    .card{{max-width:520px;margin:40px auto;background:#1e293b;border-radius:12px;padding:32px;}}
    h2{{color:#38bdf8;margin-top:0;font-size:1.4rem;}}
    label{{display:block;margin:16px 0 6px;font-size:.9rem;color:#94a3b8;}}
    input,textarea{{width:100%;padding:10px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;font-size:.95rem;box-sizing:border-box;}}
    .upload-area{{border:2px dashed #38bdf8;border-radius:8px;padding:24px;text-align:center;margin-top:8px;cursor:pointer;}}
    .upload-area:hover{{background:#0ea5e920;}}
    button{{width:100%;margin-top:24px;padding:14px;background:#38bdf8;color:#000;font-weight:bold;font-size:1rem;border:none;border-radius:8px;cursor:pointer;}}
    button:hover{{background:#0ea5e9;}}
    p.sub{{color:#64748b;font-size:.85rem;margin-top:8px;}}
  </style>
</head>
<body>
  <div class="card">
    <h2>Upload Job Site Photos</h2>
    <p class="sub">Gray Horizons Enterprise uses your photos to speed up the inspection and estimate process. All uploads are secure.</p>
    <form method="POST" action="/job-upload" enctype="multipart/form-data">
      <input type="hidden" name="token" value="{token}">
      <label>Your Name</label>
      <input type="text" name="name" placeholder="First Last" required>
      <label>Email</label>
      <input type="email" name="email" placeholder="you@example.com" required>
      <label>Phone</label>
      <input type="tel" name="phone" placeholder="(555) 555-5555">
      <label>Brief Job Description</label>
      <textarea name="description" rows="3" placeholder="e.g. bathroom remodel, roof inspection, HVAC replacement..."></textarea>
      <label>Upload Photos (up to 10, JPG/PNG/HEIC)</label>
      <div class="upload-area">
        <input type="file" name="photos" accept="image/*" multiple style="width:100%;cursor:pointer;">
        <p class="sub">Tap to select or drag photos here</p>
      </div>
      <button type="submit">Send Photos to GHE</button>
    </form>
  </div>
</body>
</html>"""


@app.route('/job-upload', methods=["POST"])
def job_upload_post():
    try:
        name        = flask_request.form.get("name", "").strip()
        email       = flask_request.form.get("email", "").strip()
        phone       = flask_request.form.get("phone", "").strip()
        description = flask_request.form.get("description", "").strip()
        files       = flask_request.files.getlist("photos")

        job_id  = _uuid.uuid4().hex[:8].upper()
        job_dir = os.path.join(PHOTO_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        saved = []
        for f in files:
            if f and f.filename:
                safe_name = f.filename.replace("/", "_").replace("\\", "_")
                path = os.path.join(job_dir, safe_name)
                f.save(path)
                saved.append(safe_name)

        # Log the submission
        log_path = os.path.join(PHOTO_DIR, "submissions.json")
        try:
            submissions = json.load(open(log_path)) if os.path.exists(log_path) else []
        except Exception:
            submissions = []
        submissions.append({
            "job_id": job_id, "name": name, "email": email, "phone": phone,
            "description": description, "photos": saved,
            "submitted_at": datetime.utcnow().isoformat()
        })
        with open(log_path, "w") as lf:
            json.dump(submissions, lf, indent=2)

        # Notify GHE via email
        sg_key = os.getenv("SENDGRID_API_KEY", "").strip()
        if sg_key and saved:
            notify_html = f"""
<div style="font-family:Arial;font-size:15px;color:#222;max-width:560px;">
  <h3 style="color:#1a73e8;">New Job Photo Submission #{job_id}</h3>
  <p><b>Name:</b> {name}<br>
  <b>Email:</b> {email}<br>
  <b>Phone:</b> {phone}</p>
  <p><b>Description:</b><br>{description or 'Not provided'}</p>
  <p><b>Photos uploaded:</b> {len(saved)}<br>
  {'<br>'.join(saved)}</p>
  <p style="color:#64748b;font-size:13px;">Saved to job_photos/{job_id}/</p>
</div>"""
            payload = {
                "personalizations": [{"to": [{"email": VERIFIED_SENDER}]}],
                "from": {"email": VERIFIED_SENDER, "name": "GHE Job Uploads"},
                "subject": f"Job Photos Received #{job_id} — {name}",
                "content": [{"type": "text/html", "value": notify_html}],
            }
            try:
                requests.post("https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
                    json=payload, timeout=10)
            except Exception:
                pass

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Photos Received</title>
<style>body{{font-family:Arial;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;}}
.card{{max-width:480px;margin:60px auto;background:#1e293b;border-radius:12px;padding:40px;text-align:center;}}
h2{{color:#22c55e;}} p{{color:#94a3b8;}}</style></head>
<body><div class="card">
<h2>Photos Received</h2>
<p>Thank you {name}. We received {len(saved)} photo{'s' if len(saved)!=1 else ''}.<br>
Reference: <b>#{job_id}</b></p>
<p>Our team will review them and reach out within 1 business day.</p>
</div></body></html>"""
    except Exception as e:
        return f"<p style='color:red;padding:40px;font-family:Arial;'>Upload error: {e}</p>", 500

# =========================
# GMAIL REPLY MONITOR
# =========================
try:
    from gmail_reply_monitor import start_background as start_gmail_monitor
    start_gmail_monitor()
    print("[STARTUP] Gmail reply monitor started")
except Exception as _gmail_err:
    print(f"[STARTUP] Gmail monitor skipped: {_gmail_err}")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)