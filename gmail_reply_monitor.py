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
    "interested", "tell me more", "how does this work", "sounds good", "love to",
    "would like", "more info", "set up a call", "book a call", "schedule a call",
    "let's talk", "let me know more", "sounds interesting", "how much",
    "what's included", "get started", "when can we",
    "can you send", "can you show", "i'd like to", "we'd like to",
    "can we chat", "can we talk", "what does it cost", "how does it work",
    "send me more", "walk me through", "what do you charge", "open to learning",
    "would love to see", "can you explain", "this looks interesting",
]

# Any of these = definitive opt-out, noise, or counter-solicitation — never a hot lead
IGNORE_KEYWORDS = [
    # Negative replies
    "no thanks", "no thank you", "not interested", "not for us",
    "not a good fit", "not the right time", "pass on this", "no need",
    "don't need", "don't contact", "please don't", "not looking",
    "remove me", "unsubscribe", "stop emailing", "do not contact",
    "opt out", "take me off", "please remove", "stop sending",
    "remove from", "remove me from",
    # Auto-replies / system mail
    "auto-reply", "automatic reply", "out of office", "vacation reply",
    "i am out", "i'm out of office", "i will be out", "away from",
    "currently unavailable", "on leave", "on vacation",
    "delivery failure", "mailer-daemon", "mail delivery", "undeliverable",
    "returned mail", "bounce", "failed to deliver",
    # Marketing / advertisements
    "you have been selected", "congratulations", "special offer",
    "click here to", "this email was sent to", "advertisement",
    "promotional", "newsletter", "mailing list",
    # System senders
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "notifications@", "updates@", "alerts@",
    # Counter-solicitations — they're selling TO us, not buying
    "guest post", "sponsored post", "link insertion", "link placement",
    "we are offering", "we offer", "we provide", "our service",
    "our pricing", "our rates", "per month", "per link", "per post",
    "payment via paypal", "payment via", "we can help you",
    "digital marketing services", "seo package", "seo service",
    "backlink", "we noticed your website", "i noticed your website",
    "we specialize in", "our team can", "looking to promote",
    "buy our", "purchase our", "subscribe to our", "sign up for our",
    "we'd love to work with", "collaboration opportunity",
    "partnership opportunity", "business opportunity",
    "affiliate program", "referral program",
    # Recruiter / job spam
    "job opportunity", "career opportunity", "we're hiring", "open position",
    "hiring for", "talent acquisition", "recruitment",
    # Generic "thanks we got it" with no buying intent
    "thank you for your email", "thanks for your inquiry",
    "this is an automated", "auto response",
]

# Sender is flagged as opt-out — add to unsubscribe list automatically
OPT_OUT_TRIGGERS = [
    "no thanks", "no thank you", "not interested", "remove me",
    "unsubscribe", "stop emailing", "do not contact", "opt out",
    "take me off", "please remove",
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


def load_sent_emails() -> set:
    """Load every email we've ever sent to — only flag replies from these people."""
    sent = set()
    sent_log = os.path.join(DATA_DIR, "sent_log.csv")
    if os.path.exists(sent_log):
        try:
            import csv
            with open(sent_log, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    e = row.get("email", "").strip().lower()
                    if e:
                        sent.add(e)
        except Exception:
            pass
    return sent


def is_opt_out(subject, body) -> bool:
    text = (subject + " " + body).lower()
    return any(k in text for k in OPT_OUT_TRIGGERS)


def add_to_unsubscribe(email: str):
    """Append email to unsubscribe_list.csv."""
    unsub = os.path.join(DATA_DIR, "unsubscribe_list.csv")
    import csv
    exists = os.path.exists(unsub)
    try:
        with open(unsub, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["email", "reason"])
            if not exists:
                w.writeheader()
            w.writerow({"email": email.lower().strip(), "reason": "replied opt-out"})
        print(f"[GMAIL] Auto-opted-out: {email}")
    except Exception as e:
        print(f"[GMAIL] Opt-out write error: {e}")


def is_interested(subject, body):
    text = (subject + " " + body).lower()
    # Must be a reply thread
    if not subject.lower().startswith("re:"):
        return False
    # Any ignore signal = not a lead
    if any(k in text for k in IGNORE_KEYWORDS):
        return False
    # Block replies where body is longer than 800 chars with no question mark
    # (counter-solicitations tend to be long pitches with no questions)
    body_lower = body.lower()
    if len(body) > 600 and "?" not in body and any(
        k in body_lower for k in ["we offer", "we provide", "our service", "we are offering", "our team"]
    ):
        return False
    # Must contain a genuine interest signal
    return any(k in text for k in INTEREST_KEYWORDS)


STRIPE_SETUP_LINK = os.getenv("STRIPE_SETUP_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
SIGNALS_LINK      = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")


def build_reply(sender_name, niche="hvac"):
    niche_value = {
        "hvac":        ("missed calls and slow follow-up are costing you 10-15 jobs a month",
                        "missed call recovery + automated follow-up for HVAC"),
        "dental":      ("slow new patient response is costing your practice $10k+/month in lost lifetime value",
                        "automated new patient follow-up for dental practices"),
        "hoa":         ("violations getting lost in the handoff between report and resolution",
                        "violation tracking + automated follow-up for HOA teams"),
        "plumbing":    ("missed calls during peak hours are your biggest revenue leak",
                        "emergency call capture + automated dispatch for plumbing"),
        "contractor":  ("estimates going cold because follow-up doesn't happen consistently",
                        "estimate follow-up + lead recovery for contractors"),
        "landscaping": ("overflow leads and seasonal clients going quiet between services",
                        "overflow lead capture + client retention for landscaping"),
        "roofing":     ("storm call volume spikes overwhelming your intake process",
                        "storm call management + estimate follow-up for roofers"),
        "gym":         ("new members churning in month 2 from zero follow-up",
                        "automated member retention + rebooking for gyms"),
        "restaurant":  ("customers not coming back because there's no follow-up system",
                        "guest retention + loyalty automation for restaurants"),
        "mortgage":    ("rate-shopping leads going cold before your team calls back",
                        "instant lead response + nurture for mortgage brokers"),
    }.get(niche, ("leads going cold from slow follow-up",
                  "automated lead follow-up system"))

    pain, system_name = niche_value
    name = sender_name.split()[0] if sender_name else "there"

    return f"""\
Hey {name},

Thanks for getting back to me.

Here's the short version: {pain}. We fix that with {system_name} — fully automated, set up in about a week.

Two ways to move forward:

1. Get started now — flat $497 setup, no call needed:
{STRIPE_SETUP_LINK}

2. See it first — 20-minute walkthrough, I'll show you exactly what it looks like for your business:
{CALENDLY_URL}

Either way works. Most people who want to move fast just go straight to option 1.

Gray Horizons Enterprise"""


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
    sent_emails = load_sent_emails()  # only flag replies from people we emailed

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
            sender_email = details["sender_email"].lower().strip()

            # Skip own emails
            if GHE_EMAIL.lower() in sender_email:
                continue

            # Only process replies from people we actually emailed
            if sent_emails and sender_email not in sent_emails:
                continue

            subject = details["subject"]
            body    = details["body"]

            # Auto opt-out anyone who replied negatively
            if is_opt_out(subject, body):
                add_to_unsubscribe(sender_email)
                print(f"[GMAIL] Opt-out reply from {sender_email} — added to unsubscribe list")
                continue

            if is_interested(subject, body):
                niche = guess_niche_from_context(subject, body)
                sent  = send_reply(
                    service, details["id"], details["thread_id"],
                    sender_email, details["sender_name"], niche
                )
                lead = {
                    "email":     sender_email,
                    "name":      details["sender_name"],
                    "subject":   subject,
                    "snippet":   body[:300],
                    "niche":     niche,
                    "replied":   sent,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
                save_hot_lead(lead)
                new_hot.append(lead)
                print(f"[GMAIL] HOT LEAD: {details['sender_name']} <{sender_email}>")

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
