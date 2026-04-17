"""
resend_now.py — Gray Horizons Enterprise
Sends all pending/failed outreach emails directly via Gmail SMTP.
Run: python resend_now.py
"""

import csv
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
SENDER_EMAIL = "GRAYHORIZONSENTERPRISE@GMAIL.COM"
SENDER_APP_PASSWORD = "jgtygciaympwjini"

# ── Load .env manually ────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

load_env()

SENDER_EMAIL    = os.getenv("SENDER_EMAIL", "").strip()
SENDER_PASSWORD = os.getenv("SENDER_APP_PASSWORD", "").strip()
QUEUE_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach_queue.csv")
LOG_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_log.csv")

# ── Validate credentials ──────────────────────────────────────────────────────
print("\n" + "="*50)
print("GRAY HORIZONS — OUTREACH RESEND")
print("="*50)

if not SENDER_EMAIL:
    print("ERROR: SENDER_EMAIL not set in .env")
    exit(1)
if not SENDER_PASSWORD:
    print("ERROR: SENDER_APP_PASSWORD not set in .env")
    exit(1)

print(f"Sender: {SENDER_EMAIL}")
print(f"Queue:  {QUEUE_FILE}")
print()

# ── Load queue ────────────────────────────────────────────────────────────────
if not os.path.exists(QUEUE_FILE):
    print("ERROR: outreach_queue.csv not found")
    exit(1)

with open(QUEUE_FILE, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Target: pending AND previously-marked-sent (all failed before fix)
to_send = [
    r for r in rows
    if r.get("status", "").strip().lower() in ("pending", "sent")
    and r.get("email", "").strip()
]

print(f"Found {len(to_send)} emails to send ({len(rows)} total in queue)\n")

if not to_send:
    print("Nothing to send. All emails already delivered or no email addresses found.")
    exit(0)

# Preview
print("Preview (first 5):")
for r in to_send[:5]:
    print(f"  {r.get('company','?'):35s}  {r.get('email','')}")
if len(to_send) > 5:
    print(f"  ... and {len(to_send)-5} more")

print()
confirm = input(f"Send all {len(to_send)} emails now? (yes/no): ").strip().lower()
if confirm not in ("yes", "y"):
    print("Cancelled.")
    exit(0)

# ── SMTP connection ───────────────────────────────────────────────────────────
print("\nConnecting to Gmail SMTP...")
try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    print("Connected.\n")
except Exception as e:
    print(f"SMTP CONNECTION FAILED: {e}")
    print()
    print("Most likely causes:")
    print("  1. App password wrong — generate a new one at myaccount.google.com/security")
    print("  2. 2-Step Verification not enabled on your Google account")
    print("  3. Gmail blocking sign-in — check grayhorizonsenterprise@gmail.com for a security alert")
    exit(1)

# ── Send loop ─────────────────────────────────────────────────────────────────
sent_ok  = []
failed   = []

# Prepare log file
log_exists = os.path.exists(LOG_FILE)
log_fields = ["timestamp", "company", "name", "email", "subject", "success", "error"]

with open(LOG_FILE, "a", newline="", encoding="utf-8") as log_f:
    writer = csv.DictWriter(log_f, fieldnames=log_fields)
    if not log_exists:
        writer.writeheader()

    for i, row in enumerate(to_send, 1):
        email   = row.get("email",   "").strip()
        company = row.get("company", "Unknown").strip()
        name    = row.get("name",    "").strip()
        message = row.get("message", "").strip()
        subject = f"{company} — quick question"

        print(f"[{i}/{len(to_send)}] Sending to {email} ({company})...", end=" ", flush=True)

        html_body = (
            "<div style='font-family:Arial;line-height:1.6;'>"
            "<p>Hi " + (name or "there") + ",</p>"
            "<p>" + message.replace("\n", "<br>") + "</p>"
            "<p>— Alex<br>Gray Horizons Enterprise<br>grayhorizonsenterprise.com</p>"
            "</div>"
        )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = SENDER_EMAIL
            msg["To"]      = email
            msg.attach(MIMEText(html_body, "html"))
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            print("SENT")
            sent_ok.append(email)
            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "company": company, "name": name, "email": email,
                "subject": subject, "success": True, "error": "smtp-local"
            })
            # Mark sent in memory
            row["status"] = "sent"
        except Exception as e:
            print(f"FAILED — {e}")
            failed.append((email, str(e)))
            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "company": company, "name": name, "email": email,
                "subject": subject, "success": False, "error": str(e)
            })

        # Small delay to avoid Gmail rate limiting
        time.sleep(1.5)

try:
    server.quit()
except Exception:
    pass

# ── Update queue statuses ─────────────────────────────────────────────────────
sent_emails = set(sent_ok)
for row in rows:
    if row.get("email", "").strip() in sent_emails:
        row["status"] = "sent"

with open(QUEUE_FILE, "w", newline="", encoding="utf-8") as f:
    if rows:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("="*50)
print(f"DONE — {len(sent_ok)} sent · {len(failed)} failed")
print("="*50)

if failed:
    print("\nFailed emails:")
    for email, err in failed:
        print(f"  {email}: {err}")

print(f"\nFull log saved to: {LOG_FILE}")
print()
