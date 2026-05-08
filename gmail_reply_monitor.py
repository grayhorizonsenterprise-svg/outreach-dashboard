"""
gmail_reply_monitor.py — Gray Horizons Enterprise
Monitors Gmail for replies to outreach emails.
- Detects positive/interested replies
- Auto-responds with Calendly link
- Sends morning digest of hot leads
- Runs as a background thread in the Flask app

Env vars required:
  GMAIL_CLIENT_ID
  GMAIL_CLIENT_SECRET
  GMAIL_REFRESH_TOKEN
  CALENDLY_URL
  GHE_EMAIL = grayhorizonsenterprise@gmail.com
  ANTHROPIC_API_KEY (optional — falls back to keyword detection)
"""

import os
import sys
import json
import base64
import time
import datetime
import re
import threading
from email.mime.text import MIMEText

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR       = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
CALENDLY_URL   = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
GHE_EMAIL      = os.getenv("GHE_EMAIL", "grayhorizonsenterprise@gmail.com")
DIGEST_HOUR    = int(os.getenv("DIGEST_HOUR", "7"))   # 7am daily digest

INTEREST_KEYWORDS = [
    "interested", "tell me more", "how does", "sounds good", "love to",
    "would like", "more info", "set up a call", "book a call", "schedule",
    "yes", "definitely", "absolutely", "sure", "let's talk", "let me know",
    "sounds interesting", "how much", "pricing", "cost", "what's included",
    "sign up", "get started", "when can", "available", "reach out",
]

IGNORE_KEYWORDS = [
    "unsubscribe", "remove me", "stop emailing", "not interested",
    "do not contact", "opt out", "auto-reply", "out of office",
    "vacation", "automatic reply", "delivery failure", "mailer-daemon",
    "noreply", "no-reply", "donotreply",
]

HOT_LEADS_FILE = os.path.join(DATA_DIR, "hot_leads.json")
PROCESSED_FILE = os.path.join(DATA_DIR, "gmail_processed.json")


def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=os.getenv("GMAIL_REFRESH_TOKEN"),
            client_id=os.getenv("GMAIL_CLIENT_ID"),
            client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        print(f"[GMAIL] Auth error: {e}")
        return None


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_processed(ids):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(ids), f)


def load_hot_leads():
    if os.path.exists(HOT_LEADS_FILE):
        try:
            with open(HOT_LEADS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_hot_lead(lead):
    leads = load_hot_leads()
    leads.append(lead)
    with open(HOT_LEADS_FILE, "w") as f:
        json.dump(leads, f, indent=2)


def is_interested(subject, body):
    text = (subject + " " + body).lower()
    if any(k in text for k in IGNORE_KEYWORDS):
        return False
    # Must be a reply (Re:)
    if not subject.lower().startswith("re:"):
        return False
    return any(k in text for k in INTEREST_KEYWORDS)


def build_reply(sender_name, niche="hvac"):
    niche_line = {
        "hvac":        "the missed call recovery and lead follow-up system for HVAC companies",
        "dental":      "the automated new patient follow-up system for dental practices",
        "hoa":         "the violation tracking and follow-up automation for HOA teams",
        "plumbing":    "the emergency call capture and dispatch system for plumbing companies",
        "contractor":  "the estimate follow-up and lead recovery system for contractors",
        "landscaping": "the overflow lead capture system for landscaping companies",
        "roofing":     "the storm call management and estimate follow-up system for roofers",
    }.get(niche, "the automated lead follow-up system")

    name = sender_name.split()[0] if sender_name else "there"

    return f"""\
Hey {name},

Thanks for getting back to me — glad it resonated.

I'd love to walk you through {niche_line} and show you exactly what it looks like for a business your size. It's a 20-minute call and I'll have specific numbers ready for your market.

Grab a time that works for you here:
{CALENDLY_URL}

Looking forward to it.

Alex
Gray Horizons Enterprise
https://grayhorizonsenterprise.com"""


def send_reply(service, message_id, thread_id, to_email, sender_name, niche):
    try:
        reply_body = build_reply(sender_name, niche)
        msg = MIMEText(reply_body)
        msg["To"] = to_email
        msg["From"] = GHE_EMAIL
        msg["Subject"] = "Re: Let's set up a time"
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id}
        ).execute()
        print(f"[GMAIL] Replied to {to_email}")
        return True
    except Exception as e:
        print(f"[GMAIL] Reply failed to {to_email}: {e}")
        return False


def get_message_details(service, msg_id):
    try:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "")
        sender  = headers.get("From", "")
        thread  = msg.get("threadId", "")

        # Extract email address and name from From header
        email_match = re.search(r"<([^>]+)>", sender)
        sender_email = email_match.group(1) if email_match else sender
        sender_name  = sender.split("<")[0].strip().strip('"') if "<" in sender else sender

        # Extract body
        body = ""
        payload = msg.get("payload", {})
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
        elif payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return {
            "id": msg_id,
            "thread_id": thread,
            "subject": subject,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "body": body[:2000],
        }
    except Exception as e:
        print(f"[GMAIL] Error reading message {msg_id}: {e}")
        return None


def guess_niche_from_context(subject, body):
    text = (subject + " " + body).lower()
    if any(k in text for k in ["hvac", "heating", "cooling", "ac ", "furnace", "air condition"]):
        return "hvac"
    if any(k in text for k in ["dental", "dentist", "patient", "teeth", "orthodon"]):
        return "dental"
    if any(k in text for k in ["hoa", "homeowner", "violation", "community", "association"]):
        return "hoa"
    if any(k in text for k in ["plumb", "pipe", "drain", "sewer"]):
        return "plumbing"
    if any(k in text for k in ["roof", "shingle", "storm damage"]):
        return "roofing"
    if any(k in text for k in ["landscape", "lawn", "mowing", "irrigation"]):
        return "landscaping"
    if any(k in text for k in ["contractor", "construction", "remodel", "build"]):
        return "contractor"
    return "hvac"


def check_inbox(service, processed_ids):
    new_hot = []
    try:
        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=50,
            q="is:unread"
        ).execute()

        messages = results.get("messages", [])
        for m in messages:
            mid = m["id"]
            if mid in processed_ids:
                continue

            details = get_message_details(service, mid)
            if not details:
                continue

            processed_ids.add(mid)

            # Skip own emails
            if GHE_EMAIL.lower() in details["sender_email"].lower():
                continue

            if is_interested(details["subject"], details["body"]):
                niche = guess_niche_from_context(details["subject"], details["body"])
                sent  = send_reply(
                    service, details["id"], details["thread_id"],
                    details["sender_email"], details["sender_name"], niche
                )
                lead = {
                    "email":       details["sender_email"],
                    "name":        details["sender_name"],
                    "subject":     details["subject"],
                    "snippet":     details["body"][:300],
                    "niche":       niche,
                    "replied":     sent,
                    "timestamp":   datetime.datetime.utcnow().isoformat(),
                }
                save_hot_lead(lead)
                new_hot.append(lead)
                print(f"[GMAIL] HOT LEAD: {details['sender_name']} <{details['sender_email']}>")

    except Exception as e:
        print(f"[GMAIL] Inbox check error: {e}")

    return new_hot


def send_morning_digest(service, leads):
    if not leads:
        return
    try:
        lines = [f"Gray Horizons — {len(leads)} Hot Lead(s) Today\n"]
        for i, l in enumerate(leads, 1):
            lines.append(f"{i}. {l['name']} <{l['email']}> ({l['niche'].upper()})")
            lines.append(f"   Said: {l['snippet'][:150]}")
            lines.append(f"   Reply sent: {'YES' if l['replied'] else 'NO — reply manually'}")
            lines.append(f"   Time: {l['timestamp']}\n")
        lines.append(f"\nBook link: {CALENDLY_URL}")

        msg = MIMEText("\n".join(lines))
        msg["To"]      = GHE_EMAIL
        msg["From"]    = GHE_EMAIL
        msg["Subject"] = f"[GHE] {len(leads)} Hot Lead(s) — {datetime.date.today().strftime('%b %d')}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[GMAIL] Morning digest sent — {len(leads)} leads")
    except Exception as e:
        print(f"[GMAIL] Digest error: {e}")


def run_monitor():
    if not all([
        os.getenv("GMAIL_CLIENT_ID"),
        os.getenv("GMAIL_CLIENT_SECRET"),
        os.getenv("GMAIL_REFRESH_TOKEN"),
    ]):
        print("[GMAIL] Missing credentials — set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")
        return

    print("[GMAIL] Reply monitor starting...")
    service       = get_gmail_service()
    if not service:
        return

    processed_ids = load_processed()
    digest_sent   = False
    daily_leads   = []

    while True:
        now = datetime.datetime.utcnow()

        # Morning digest at configured hour (UTC)
        if now.hour == DIGEST_HOUR and not digest_sent and daily_leads:
            send_morning_digest(service, daily_leads)
            daily_leads  = []
            digest_sent  = True
        elif now.hour != DIGEST_HOUR:
            digest_sent = False

        new = check_inbox(service, processed_ids)
        daily_leads.extend(new)
        save_processed(processed_ids)

        time.sleep(300)  # check every 5 minutes


def start_background():
    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()


if __name__ == "__main__":
    run_monitor()
