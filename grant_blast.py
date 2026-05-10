"""
grant_blast.py — Gray Horizons Enterprise
Sends grant writing outreach emails to nonprofits and small businesses.
Run daily or on demand. Logs to grant_blast_log.csv.

Usage:
  python grant_blast.py
"""

import pandas as pd
import requests
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL   = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
CALENDLY     = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE   = os.path.join(DATA_DIR, "grant_queue.csv")
LOG_FILE     = os.path.join(DATA_DIR, "grant_blast_log.csv")
UNSUB_FILE   = os.path.join(DATA_DIR, "unsubscribe_list.csv")

DAILY_LIMIT  = 200


def build_html(company: str, message: str) -> str:
    paragraphs = message.strip().split("\n\n")
    body_html = "".join(
        f"<p style='margin:0 0 14px 0;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
{body_html}
<p>
  <a href="{CALENDLY}" style="display:inline-block;background:#0f172a;color:#38bdf8;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">Schedule a quick call</a>
</p>
<p style="color:#64748b;font-size:12px;">
  To unsubscribe, reply with "remove" in the subject line.
</p>
</body>
</html>"""


def send(email: str, name: str, subject: str, html: str) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def run():
    if not SENDGRID_KEY:
        print("[GRANT] No SENDGRID_API_KEY set")
        return

    if not os.path.exists(QUEUE_FILE):
        print("[GRANT] No grant_queue.csv — run nonprofit_scraper.py first")
        return

    df = pd.read_csv(QUEUE_FILE).fillna("")

    # Load already-sent and unsubscribed
    sent_emails = set()
    if os.path.exists(LOG_FILE):
        sent_emails = set(pd.read_csv(LOG_FILE)["email"].str.lower().tolist())
    if os.path.exists(UNSUB_FILE):
        unsubs = set(pd.read_csv(UNSUB_FILE)["email"].str.lower().tolist())
        sent_emails |= unsubs

    targets = df[
        (df["email"].str.strip() != "") &
        (df["message"].str.strip() != "") &
        (~df["email"].str.lower().isin(sent_emails))
    ].head(DAILY_LIMIT)

    print(f"[GRANT] Sending to {len(targets)} grant prospects...")

    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email   = str(row["email"]).strip().lower()
        name    = str(row.get("company", "")).strip()
        subject = str(row.get("subject", "Grant funding opportunity"))
        message = str(row.get("message", ""))

        html    = build_html(name, message)
        success = send(email, name, subject, html)

        log.append({"email": email, "company": name, "sent": success})

        if success:
            sent += 1
        else:
            fail += 1

        if (sent + fail) % 25 == 0:
            print(f"  [{sent + fail}/{len(targets)}] sent={sent} fail={fail}")

        time.sleep(0.15)

    if log:
        log_df = pd.DataFrame(log)
        if os.path.exists(LOG_FILE):
            log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)

    print(f"\n[GRANT] Done — {sent} sent, {fail} failed")
    print(f"Expected responses at 2%: ~{int(sent * 0.02)} leads")
    print(f"Expected revenue at $750/close: ~${int(sent * 0.02 * 0.3) * 750}/month")


if __name__ == "__main__":
    run()
