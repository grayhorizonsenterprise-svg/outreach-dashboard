"""
followup_engine.py — Gray Horizons Enterprise
Sends follow-up emails to leads contacted 3-7 days ago with no reply.
Reads sent_log.csv, checks followup_log.csv to avoid double follow-ups.
Runs standalone daily — no dashboard required.
"""
import os, sys, time, random, re
from datetime import datetime, timedelta
import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR      = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
SENT_LOG      = os.path.join(DATA_DIR, "sent_log.csv")
FOLLOWUP_LOG  = os.path.join(DATA_DIR, "followup_log.csv")
OPT_OUT_FILE  = os.path.join(DATA_DIR, "unsubscribe_list.csv")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SENDER_NAME   = os.getenv("SENDER_NAME", "Alex")
CALENDLY      = "https://calendly.com/grayhorizonsenterprise/30min"
DAILY_LIMIT   = int(os.getenv("FOLLOWUP_DAILY_LIMIT", "200"))
FOLLOWUP_AFTER_DAYS = 3
FOLLOWUP_CUTOFF_DAYS = 7  # don't follow up if sent more than 7 days ago

SUBJECTS_F1 = [
    "Just following up",
    "Did you get a chance to see this?",
    "Circling back",
    "One more thought on this",
    "Still relevant?",
]

MESSAGES_F1 = [
    """\
Hey,

Wanted to follow up on my message from a few days ago.

I know inboxes get busy. Just wanted to make sure this didn't get buried.

If any part of what I mentioned resonated, I'm happy to do a quick 15-minute call to see if it actually makes sense for your situation.

No pitch. Just a conversation: {calendly}

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Following up in case my last message got lost.

We help business owners set up AI-powered systems that generate leads, follow up automatically, and close more without adding headcount.

If you're open to a quick call to see if it applies to what you're working on: {calendly}

If now's not the right time, no worries at all - just reply and I'll get out of your inbox.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Last follow-up from me on this.

I sent you a note a few days ago about how we help businesses automate their outreach and follow-up. If it caught your attention at all, I'd love to show you exactly what it looks like for your specific situation.

15 minutes: {calendly}

If it's not a fit, just say the word and I won't reach out again.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",

    """\
Hey,

Didn't want to let this go without one more try.

We've helped businesses in your space add significant revenue just by fixing the gaps in their follow-up and outreach processes. Some clients see results in the first 30 days.

If you're curious whether that's possible for you: {calendly}

Either way, hope business is going well.

Alex
Gray Horizons Enterprise

To opt out reply REMOVE.""",
]


def load_opt_outs() -> set:
    out = set()
    if os.path.exists(OPT_OUT_FILE):
        try:
            df = pd.read_csv(OPT_OUT_FILE, dtype=str).fillna("")
            if "email" in df.columns:
                out.update(df["email"].str.lower().str.strip())
        except Exception:
            pass
    return out


def load_already_followed_up() -> set:
    if not os.path.exists(FOLLOWUP_LOG):
        return set()
    try:
        df = pd.read_csv(FOLLOWUP_LOG, dtype=str).fillna("")
        if "email" in df.columns:
            return set(df["email"].str.lower().str.strip())
    except Exception:
        return set()
    return set()


def log_followup(email: str, subject: str, success: bool):
    import csv
    row = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "email": email.lower().strip(),
        "subject": subject,
        "success": success,
    }
    file_exists = os.path.exists(FOLLOWUP_LOG)
    with open(FOLLOWUP_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            w.writeheader()
        w.writerow(row)


def send_one(email, subject, body) -> bool:
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": email}]}],
                "from": {"email": FROM_EMAIL, "name": SENDER_NAME},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            }, timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"    [ERR] {e}")
        return False


def run():
    if not SENDGRID_KEY:
        print("[FOLLOWUP] SENDGRID_API_KEY not set"); return
    if not os.path.exists(SENT_LOG):
        print("[FOLLOWUP] sent_log.csv not found"); return

    try:
        df = pd.read_csv(SENT_LOG, dtype=str).fillna("")
    except Exception as e:
        print(f"[FOLLOWUP] Cannot read sent_log: {e}"); return

    if "email" not in df.columns:
        print("[FOLLOWUP] sent_log has no email column"); return

    now = datetime.utcnow()
    cutoff_min = now - timedelta(days=FOLLOWUP_CUTOFF_DAYS)
    cutoff_max = now - timedelta(days=FOLLOWUP_AFTER_DAYS)

    opt_outs      = load_opt_outs()
    already_done  = load_already_followed_up()

    # Find successfully-sent rows within the follow-up window
    candidates = []
    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip().lower()
        if not email or email in opt_outs or email in already_done:
            continue
        # Check success column (log_sent writes bool True)
        success_val = str(row.get("success", "")).strip()
        if success_val not in ("True", "true", "1", "sent"):
            continue
        # Parse timestamp
        ts_raw = str(row.get("timestamp", "")).strip()
        ts = None
        for fmt in ("%Y-%m-%d %I:%M %p PT", "%Y-%m-%d %H:%M UTC", "%Y-%m-%d %H:%M:%S"):
            try:
                ts = datetime.strptime(ts_raw[:19], fmt[:len(ts_raw[:19])])
                break
            except Exception:
                pass
        if ts is None:
            continue
        if cutoff_min <= ts <= cutoff_max:
            candidates.append(email)

    # Deduplicate
    candidates = list(dict.fromkeys(candidates))
    random.shuffle(candidates)
    candidates = candidates[:DAILY_LIMIT]

    print(f"[FOLLOWUP] {len(candidates)} leads eligible for follow-up today")

    sent = 0
    for email in candidates:
        subject = random.choice(SUBJECTS_F1)
        body    = random.choice(MESSAGES_F1).format(calendly=CALENDLY)
        ok = send_one(email, subject, body)
        log_followup(email, subject, ok)
        if ok:
            sent += 1
            print(f"  [OK] {email}")
        time.sleep(random.uniform(0.4, 0.9))

    print(f"[FOLLOWUP DONE] {sent} follow-ups sent today")


if __name__ == "__main__":
    run()
