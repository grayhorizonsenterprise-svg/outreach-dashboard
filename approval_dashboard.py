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
    # Direct directory scrapers — no DDG, hit YP/SP pages directly
    "yellowpages_scraper.py",
    "superpages_scraper.py",
    # API-based (only run if keys are set in Railway env vars)
    "yelp_scraper.py",
    "snov_scraper.py",
    "hunter_scraper.py",
    "apollo_scraper.py",
    # Enrichment + quality + generation
    "prospect_enricher.py",
    "prospect_qualifier.py",
    "email_verifier.py",
    "outreach_generator.py",
    # outreach_sender.py intentionally excluded — sending is manual-only via dashboard buttons
]

DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", "150"))  # throttled: 26.7% bounce rate detected — rebuild reputation before scaling
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
        conn = _get_db()
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
        conn = _get_db()
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


def _twitter_scheduler():
    """Posts to Twitter 5x/day at 8am, 10am, 1pm, 5pm, 8pm UTC.
    Also fires one post immediately on startup so deploys never go dark."""
    import datetime as _dt
    POST_HOURS = {13, 15, 18, 21, 1}
    fired = set()
    time.sleep(120)  # let app stabilize
    # Fire immediately on startup regardless of hour
    _run_engine("Twitter Post (startup)", "twitter_poster.py", extra_args=["--force"])
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
    """Auto-sends main outreach queue 3x/day: 10am, 2pm, 6pm UTC.
    Sends up to DAILY_EMAIL_LIMIT total, split across the 3 windows.
    Only fires if there are pending leads — never double-sends."""
    import datetime as _dt
    BLAST_HOURS = {10, 14, 18}
    fired_today: set = set()
    time.sleep(300)  # let pipeline stabilize first
    while True:
        now = _dt.datetime.utcnow()
        key = (now.date(), now.hour)
        if now.hour in BLAST_HOURS and key not in fired_today and now.minute < 15:
            pending = get_pending_count()
            sent_today = count_sent_today()
            remaining = max(0, DAILY_EMAIL_LIMIT - sent_today)
            if pending > 0 and remaining > 0:
                cap = min(pending, remaining, 700)  # max 700 per window
                print(f"[AUTO-BLAST] {pending} pending, {remaining} daily remaining — sending {cap}", flush=True)
                threading.Thread(target=run_batch_send, kwargs={"limit": cap}, daemon=True).start()
            else:
                print(f"[AUTO-BLAST] Skipping — pending={pending}, remaining={remaining}", flush=True)
            fired_today.add(key)
            if len(fired_today) > 10:
                fired_today = set(list(fired_today)[-5:])
        time.sleep(60)


# Start all revenue engine threads
for _fn in [
    _signals_engine_daily,
    _grant_pipeline_daily,
    _twitter_scheduler,
    _gmail_monitor_thread,
    _reddit_monitor_thread,
    _shadow_clans_nightly,
    _realestate_engine_daily,
    _medspa_engine_daily,
    _insurance_engine_daily,
    _ecommerce_engine_daily,
    _restaurant_engine_daily,
    _gym_engine_daily,
    _mortgage_engine_daily,
    _followup_engine_daily,
    _auto_blast_scheduler,
]:
    threading.Thread(target=_fn, daemon=True).start()

print("[ENGINES] All 14 revenue engine schedulers started", flush=True)

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

def _get_db():
    if not _DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(_DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        print(f"[DB] Connect failed: {e}", flush=True)
        return None

def _init_db():
    conn = _get_db()
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
                    "Alex\nGray Horizons Enterprise"
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
    conn = _get_db()
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
    conn = _get_db()
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
    from datetime import datetime
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
        "<p style='margin:0;'>Alex<br>"
        "Gray Horizons Enterprise<br>"
        "<a href='https://grayhorizonsenterprise.com' style='color:#1a73e8;'>"
        "grayhorizonsenterprise.com</a></p>"
        "</div>"
    )

def _send_via_sendgrid(api_key, sender_addr, sender_name, to_email, subject, html_body, name, company):
    # Force lowercase — SendGrid sender verification is case-sensitive
    verified_from = "grayhorizonsenterprise@gmail.com"
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": verified_from, "name": sender_name},
        "reply_to": {"email": verified_from, "name": sender_name},
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

VERIFIED_SENDER = "grayhorizonsenterprise@gmail.com"

def send_email(to_email, name, company, message, subject=""):
    sender_addr = VERIFIED_SENDER  # verified in SendGrid, always use this
    sender_name = os.getenv("SENDER_NAME", "Alex")
    subject     = subject.strip() if subject.strip() else "Quick question for your team"

    if not to_email or not str(to_email).strip():
        log_sent(to_email, name, company, subject, False, "no recipient")
        return False

    html_body = _build_html_body(name, sender_name, message)

    smtp_password = os.getenv("SENDER_APP_PASSWORD", "").strip()

    # ── Primary: SendGrid (if key is set) ─────────────────────────────────────
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    if api_key:
        ok = _send_via_sendgrid(api_key, sender_addr, sender_name,
                                to_email, subject, html_body, name, company)
        if ok:
            return True
        # SendGrid failed — fall through to SMTP
        print(f"[SEND] SendGrid failed for {to_email} — trying Gmail SMTP")

    # ── Fallback: Gmail SMTP ───────────────────────────────────────────────────
    if smtp_password:
        return _send_via_smtp(sender_addr, smtp_password,
                              to_email, subject, html_body, name, company)

    # ── Neither available ─────────────────────────────────────────────────────
    print("[SEND] ERROR: No sending method — set SENDGRID_API_KEY or SENDER_APP_PASSWORD")
    log_sent(to_email, name, company, subject, False,
             "no sending method: set SENDGRID_API_KEY or SENDER_APP_PASSWORD")
    return False

# =========================
# BATCH SENDER — runs in background thread
# =========================
_batch_started_at = 0.0

def run_batch_send(limit=None):
    global batch_running, batch_sent_count, _batch_started_at
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

    # Build global "already sent" wall — email + domain level, CSV + DB
    opt_outs      = load_opt_outs()
    ever_sent     = set()
    ever_domains  = set()

    # 1. Load from PostgreSQL (persistent across redeploys — authoritative source)
    try:
        _conn = _get_db()
        if _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT email FROM leads WHERE status IN ('sent','opted_out','skipped')")
                for (_e,) in _cur.fetchall():
                    if _e:
                        _em = str(_e).strip().lower()
                        ever_sent.add(_em)
                        if "@" in _em:
                            ever_domains.add(_em.split("@")[-1])
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
        email_key  = str(row["email"]).strip().lower()
        domain_key = email_key.split("@")[-1] if "@" in email_key else ""
        if email_key in opt_outs or email_key in ever_sent or domain_key in ever_domains:
            df.at[i, "status"] = "sent"   # already contacted — sync status
        elif email_key not in seen_emails:
            seen_emails.add(email_key)
            if domain_key:
                ever_domains.add(domain_key)  # block rest of run from same company
            rows.append((i, row))
        else:
            df.at[i, "status"] = "skipped"
    save_data(df)
    df = load_data()
    rows = rows[:cap]

    sent_indexes = []

    def _send_one(item):
        i, row = item
        ok = send_email(
            row["email"], row.get("name", ""), row.get("company", ""),
            row["message"], row.get("subject", "")
        )
        return i, ok

    with ThreadPoolExecutor(max_workers=10) as executor:
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
      Alex<br>Gray Horizons Enterprise<br>
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
        name="Alex",
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
            "from": {"email": sender, "name": "Alex"},
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
        conn = _get_db()
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
        conn = _get_db()
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
    These are the #1 cause of the 26.7% bounce rate.
    """
    from email_verifier import is_role_address, is_valid_syntax
    removed_db  = 0
    removed_csv = 0

    # -- Purge from PostgreSQL DB --
    conn = _get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email FROM leads WHERE status IN ('pending','failed')")
                rows = cur.fetchall()
                bad_ids = []
                for row_id, email in rows:
                    email = (email or "").strip().lower()
                    if not email or not is_valid_syntax(email) or is_role_address(email):
                        bad_ids.append(row_id)
                if bad_ids:
                    cur.execute(
                        "DELETE FROM leads WHERE id = ANY(%s)",
                        (bad_ids,)
                    )
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
    """Live Snov.io API test — shows token, one search result, credit status."""
    import os as _os
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
        # Test domain email lookup — try both auth methods
        for auth_method, payload in [
            ("body token", {"access_token": token, "domain": "associa.com", "type": "personal", "limit": 5, "lastId": 0}),
            ("header token", {"domain": "associa.com", "type": "personal", "limit": 5, "lastId": 0}),
        ]:
            hdrs = {"Authorization": f"Bearer {token}"} if auth_method == "header token" else {}
            r2 = _req.post("https://api.snov.io/v1/get-domain-emails-with-info", data=payload, headers=hdrs, timeout=20)
            lines.append(f"<b>Domain search ({auth_method}):</b> HTTP {r2.status_code}")
            if r2.status_code == 200:
                emails = r2.json().get("emails", [])
                lines.append(f"<b>Emails found:</b> {len(emails)}")
                for e in emails[:3]:
                    lines.append(f"  &nbsp;&nbsp;{e.get('firstName','')} {e.get('lastName','')} | {e.get('value','no email')}")
                break
            else:
                lines.append(f"<span style=color:orange>{r2.text[:200]}</span>")

        # Also test Hunter.io as backup
        hunter_key = _os.getenv("HUNTER_API_KEY", "")
        lines.append(f"<br><b>Hunter.io key:</b> {'SET' if hunter_key else '<span style=color:red>NOT SET</span>'}")
        if hunter_key:
            rh = _req.get("https://api.hunter.io/v2/domain-search",
                params={"domain": "associa.com", "api_key": hunter_key, "limit": 3}, timeout=15)
            lines.append(f"<b>Hunter domain search:</b> HTTP {rh.status_code}")
            if rh.status_code == 200:
                data = rh.json().get("data", {})
                emails = data.get("emails", [])
                lines.append(f"<b>Hunter emails found:</b> {len(emails)}")
                for e in emails[:3]:
                    lines.append(f"  &nbsp;&nbsp;{e.get('first_name','')} {e.get('last_name','')} | {e.get('position','')} | {e.get('value','')}")
            else:
                lines.append(f"<span style=color:red>Hunter failed: {rh.text[:200]}</span>")
    except Exception as ex:
        lines.append(f"<span style=color:red>Exception: {ex}</span>")
    style = "background:#0f172a;color:#e2e8f0;font-family:monospace;padding:40px;line-height:2"
    return f'<html><body style="{style}"><h2 style="color:#22c55e">Snov.io API Test</h2>' + "<br>".join(lines) + '<br><br><a href="/" style="color:#06b6d4">Back</a></body></html>'


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
    from_email = os.getenv("FROM_EMAIL", "grayhorizonsenterprise@gmail.com")
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

Alex
Gray Horizons Enterprise
https://grayhorizonsenterprise.com"""

    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": from_email, "name": "Alex | Gray Horizons"},
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


@app.route('/performance')
def performance():
    try:
        from performance_tracker import get_summary
        return f"<pre style='font-family:monospace;padding:24px;background:#0f172a;color:#e2e8f0;'>{get_summary()}</pre>"
    except Exception as e:
        return f"No performance data yet: {e}"

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