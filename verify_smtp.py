"""
verify_smtp.py — Gray Horizons Enterprise
Proves the outreach system is working end-to-end.
Run: python verify_smtp.py

Checks:
  1. SMTP credentials connect to Gmail
  2. Sends a test email to your own inbox
  3. Prints a summary of sent_log.csv stats
"""

import csv
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Load .env ─────────────────────────────────────────────────────────────────
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
LOG_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_log.csv")

print("\n" + "="*55)
print("  GRAY HORIZONS — OUTREACH SYSTEM VERIFICATION")
print("="*55 + "\n")

# ── 1. Check credentials ──────────────────────────────────────────────────────
print(f"Sender:   {SENDER_EMAIL or 'NOT SET'}")
print(f"Password: {'SET [ok]' if SENDER_PASSWORD else 'NOT SET [missing]'}\n")

if not SENDER_EMAIL or not SENDER_PASSWORD:
    print("ERROR: Missing credentials in .env — set SENDER_EMAIL and SENDER_APP_PASSWORD")
    exit(1)

# ── 2. SMTP connection test ───────────────────────────────────────────────────
print("[1/3] Testing SMTP connection to smtp.gmail.com:587...")
try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    print("      CONNECTED [ok] — credentials are valid\n")
except Exception as e:
    print(f"      FAILED ✗ — {e}")
    print()
    print("  Fix options:")
    print("  1. Generate a NEW app password at:")
    print("     https://myaccount.google.com/apppasswords")
    print("  2. Make sure 2-Step Verification is ON for the Gmail account")
    print("  3. Update SENDER_APP_PASSWORD in .env with the new 16-char password")
    exit(1)

# ── 3. Send test email to your own inbox ─────────────────────────────────────
print(f"[2/3] Sending test email to {SENDER_EMAIL}...")
try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[OK] Outreach System Verification - {datetime.now().strftime('%b %d %I:%M %p')}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = SENDER_EMAIL
    html_body = f"""
    <div style="font-family:Arial;line-height:1.7;padding:20px;background:#f8fafc;">
      <h2 style="color:#1e40af;">Gray Horizons - System Verification</h2>
      <p>This email confirms your outreach system is <strong>live and operational</strong>.</p>
      <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:6px 12px;color:#64748b;">Sent at:</td>
            <td style="padding:6px 12px;font-weight:bold;">{datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}</td></tr>
        <tr><td style="padding:6px 12px;color:#64748b;">From:</td>
            <td style="padding:6px 12px;">{SENDER_EMAIL}</td></tr>
        <tr><td style="padding:6px 12px;color:#64748b;">Method:</td>
            <td style="padding:6px 12px;">Gmail SMTP (smtp.gmail.com:587)</td></tr>
      </table>
      <p style="color:#475569;">
        <strong>What "SENT" means in your log:</strong><br>
        Gmail's SMTP server accepted the message. The email left your system successfully.
        Inbox delivery depends on the recipient's spam filters — this is normal for all cold outreach.
      </p>
      <p style="margin-top:20px;color:#64748b;font-size:13px;">
        -Alex<br>Gray Horizons Enterprise
      </p>
    </div>
    """
    msg.attach(MIMEText(html_body, "html"))
    server.sendmail(SENDER_EMAIL, SENDER_EMAIL, msg.as_string())
    print(f"      SENT [ok] — check {SENDER_EMAIL} inbox now\n")
except Exception as e:
    print(f"      FAILED ✗ — {e}\n")
finally:
    try:
        server.quit()
    except Exception:
        pass

# ── 4. Sent log stats ─────────────────────────────────────────────────────────
print("[3/3] Reading sent_log.csv...")
if not os.path.exists(LOG_FILE):
    print("      sent_log.csv not found\n")
else:
    total = sent = failed = skipped = 0
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            success_raw = str(row.get("success", row.get("status", ""))).strip().lower()
            note = str(row.get("error", row.get("note", ""))).strip().lower()
            if note == "skipped" or "no email" in note:
                skipped += 1
            elif success_raw in ("true", "1", "smtp", "sendgrid", "gmail-smtp-accepted"):
                sent += 1
            else:
                failed += 1

    print(f"      Total log entries : {total}")
    print(f"      Accepted by SMTP  : {sent}  <-- emails that left your system")
    print(f"      Failed to send    : {failed}")
    print(f"      Skipped (no email): {skipped}")
    print()
    print("  NOTE: 'Accepted by SMTP' means Gmail processed the message.")
    print("  For inbox delivery confirmation, check your Gmail Sent folder")
    print("  or use SendGrid (free tier) for open/click/bounce tracking.")

print()
print("="*55)
print("  VERIFICATION COMPLETE")
print("="*55 + "\n")
