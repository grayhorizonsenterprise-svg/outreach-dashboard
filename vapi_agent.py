"""
vapi_agent.py — Gray Horizons Enterprise
Handles inbound and outbound calling via Vapi.ai.

Outbound: Calls leads 3 days after email is sent (multi-touch sequence).
Inbound:  Answers calls to the GHE Vapi phone number, qualifies, books Calendly.

Railway env vars:
  VAPI_API_KEY          — from dashboard.vapi.ai
  VAPI_PHONE_NUMBER_ID  — from Vapi dashboard after buying a number
  VAPI_ASSISTANT_ID     — optional, created automatically on first run
  CALENDLY_URL          — already set
  STRIPE_PAYMENT_LINK   — already set
"""

import os
import csv
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

VAPI_KEY              = os.getenv("VAPI_API_KEY", "")
PHONE_NUMBER_ID       = os.getenv("VAPI_PHONE_NUMBER_ID", "")
OUTBOUND_ASSISTANT_ID = os.getenv("VAPI_OUTBOUND_ASSISTANT_ID", "a614121f-e9df-4396-b18e-02d0bd682372")
INBOUND_ASSISTANT_ID  = os.getenv("VAPI_INBOUND_ASSISTANT_ID", "31251738-3c30-4ccb-9d91-c9d4a944dff3")
CALENDLY_URL          = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
STRIPE_LINK           = os.getenv("STRIPE_PAYMENT_LINK", "")

BASE_URL  = "https://api.vapi.ai"
QUEUE_CSV = Path(os.path.dirname(os.path.abspath(__file__))) / "outreach_queue.csv"

HEADERS = {
    "Authorization": f"Bearer {VAPI_KEY}",
    "Content-Type": "application/json",
}

NICHE_PAIN = {
    "hvac":        "missing calls during peak season — every unanswered call is a $400-800 job going to a competitor",
    "dental":      "new patient inquiries going cold after hours — practices lose 8-12 new patients a month this way",
    "hoa":         "violation tracking falling apart between report and resolution — boards facing liability they didn't see coming",
    "plumbing":    "missing emergency calls — whoever answers first gets the job",
    "roofing":     "storm-season call volume overwhelming the team — 30-50% of leads go unanswered",
    "contractor":  "estimates sent but never followed up — 40-60% of open bids go cold",
    "chiropractic":"after-hours new patient inquiries sitting until morning",
    "salon":       "full-calendar overflow and client reactivation — inactive clients never return",
    "auto":        "missed calls during busy repair windows",
    "realestate":  "buyer and seller leads going cold before first contact",
    "pest_control":"missed calls during peak season",
    "electrician": "after-hours emergency calls going to competitors",
    "veterinary":  "appointment requests sitting unanswered overnight",
}

OUTBOUND_SYSTEM_PROMPT = """You are a professional sales representative for Gray Horizons Enterprise, an AI automation company. You are friendly, confident, and direct. Keep responses short and conversational.

Your goal: Qualify the lead and book a 15-minute call or close a $997 setup fee on the spot.

Opening: "Hi, is this {name}? This is Gray Horizons Enterprise calling. I sent you an email recently about automating your lead follow-up. Got a quick minute?"

If yes: "We work with {niche} businesses that are losing revenue because of {pain}. We built a system that fixes that automatically. Is that actually a problem for you right now?"

Discovery questions (ask one at a time):
1. "When a lead comes in after hours, what happens to it right now?"
2. "How many leads a week do you think slip through?"
3. "What's your average job or client value?"

Offer: "We set up a system that responds to every new inquiry instantly, 24 hours a day. It's $997 setup, $297 a month after that, with a 30-day guarantee. If you don't capture at least 5 leads you would have missed, we refund the setup fee."

Close: "Does that sound worth trying? I can send a secure payment link right now and have you live in 5 business days."

If hesitant: "Totally fair. I'll send full details to your email. Takes 30 seconds to review."

If not interested: "No problem at all. Have a great day." Then end the call.

Never be pushy. Never repeat yourself. End the call naturally when done."""

INBOUND_SYSTEM_PROMPT = """You are the AI receptionist for Gray Horizons Enterprise, an AI automation company based in California. You are professional, warm, and efficient.

When someone calls:
1. Greet them: "Thank you for calling Gray Horizons Enterprise. How can I help you today?"
2. Find out: what they need, what type of business they run, and their name and email.
3. If they want to learn about services: briefly explain that GHE builds AI automation systems — automated lead follow-up, AI voice agents, CRM pipelines, and email outreach.
4. Always try to book a 15-minute discovery call: "I can get you on the calendar with our team. The call is 15 minutes and completely free. What does your schedule look like this week?"
5. Collect: their name, email, best callback number, and business type.
6. Confirm the booking and tell them to expect a confirmation email.

Booking link: """ + CALENDLY_URL + """

If they are an existing client: take their name and message, confirm someone will follow up within 24 hours.

Keep responses under 3 sentences. Be human, not robotic."""


def get_or_create_assistant(outbound: bool = True) -> str:
    if ASSISTANT_ID:
        return ASSISTANT_ID

    prompt = OUTBOUND_SYSTEM_PROMPT if outbound else INBOUND_SYSTEM_PROMPT
    name   = "GHE Outbound Agent" if outbound else "GHE Inbound Agent"

    payload = {
        "name": name,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "systemPrompt": prompt,
            "temperature": 0.7,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
        },
        "firstMessage": "Hi, this is Gray Horizons Enterprise calling. Do you have a quick minute?",
        "endCallMessage": "Thank you for your time. Have a great day.",
        "recordingEnabled": True,
        "maxDurationSeconds": 600,
    }

    r = requests.post(f"{BASE_URL}/assistant", headers=HEADERS, json=payload, timeout=15)
    if r.status_code in (200, 201):
        assistant_id = r.json().get("id", "")
        print(f"[VAPI] Assistant created: {assistant_id}")
        print(f"Add to Railway: VAPI_ASSISTANT_ID={assistant_id}")
        return assistant_id
    else:
        print(f"[VAPI] Failed to create assistant: {r.status_code} {r.text[:200]}")
        return ""


def make_outbound_call(name: str, phone: str, company: str, niche: str = "hvac") -> dict:
    if not VAPI_KEY:
        return {"status": "skipped", "reason": "no_api_key"}
    if not PHONE_NUMBER_ID:
        return {"status": "skipped", "reason": "no_phone_number_id - buy a number at dashboard.vapi.ai"}

    phone = "".join(c for c in phone if c.isdigit() or c == "+")
    if len(phone.lstrip("+")) < 10:
        return {"status": "skipped", "reason": "invalid_phone"}

    if not phone.startswith("+"):
        phone = f"+1{phone}"

    pain      = NICHE_PAIN.get(niche.lower().replace(" ", "_"), "leads slipping through slow follow-up")
    prompt    = OUTBOUND_SYSTEM_PROMPT.replace("{name}", name or "there").replace("{niche}", niche).replace("{pain}", pain)
    payload = {
        "assistantId": OUTBOUND_ASSISTANT_ID,
        "assistantOverrides": {
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "systemPrompt": prompt,
            },
            "firstMessage": f"Hi, is this {name or 'there'}? This is Gray Horizons Enterprise calling.",
        },
        "phoneNumberId": PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name": company or name,
        },
    }

    try:
        r = requests.post(f"{BASE_URL}/call/phone", headers=HEADERS, json=payload, timeout=15)
        if r.status_code in (200, 201):
            call_id = r.json().get("id", "")
            print(f"[VAPI] Outbound call initiated: {name} at {phone} | call_id={call_id}")
            return {"status": "initiated", "call_id": call_id}
        else:
            print(f"[VAPI] Error {r.status_code}: {r.text[:200]}")
            return {"status": "error", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def run_followup_calls(days_after: int = 3, max_calls: int = 20) -> None:
    """Call leads whose emails were sent N days ago and haven't responded."""
    if not VAPI_KEY or not PHONE_NUMBER_ID:
        print("[VAPI] Missing VAPI_API_KEY or VAPI_PHONE_NUMBER_ID. Skipping calls.")
        return

    try:
        rows = []
        with open(QUEUE_CSV, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        print("[VAPI] outreach_queue.csv not found.")
        return

    cutoff = datetime.now() - timedelta(days=days_after)
    called = 0

    updated = []
    for row in rows:
        if called >= max_calls:
            updated.append(row)
            continue

        status     = row.get("status", "").strip().lower()
        sent_date  = row.get("sent_date", "").strip()
        phone      = row.get("phone", "").strip()
        call_status = row.get("call_status", "").strip().lower()

        if status != "sent" or call_status in ("called", "no_phone") or not phone:
            updated.append(row)
            continue

        if sent_date:
            try:
                sent_dt = datetime.fromisoformat(sent_date)
                if sent_dt > cutoff:
                    updated.append(row)
                    continue
            except ValueError:
                pass

        niche   = row.get("niche", "hvac") or "hvac"
        result  = make_outbound_call(
            name    = row.get("name", ""),
            phone   = phone,
            company = row.get("company", ""),
            niche   = niche,
        )

        row["call_status"] = "called" if result.get("status") == "initiated" else "error"
        row["call_id"]     = result.get("call_id", "")
        called += 1
        updated.append(row)

    all_fields = list(fieldnames)
    for f in ["phone", "sent_date", "call_status", "call_id"]:
        if f not in all_fields:
            all_fields.append(f)

    with open(QUEUE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        writer.writerows(updated)

    print(f"[VAPI] Follow-up calls complete. Called: {called}")


def get_call_status(call_id: str) -> dict:
    if not VAPI_KEY or not call_id:
        return {}
    try:
        r = requests.get(f"{BASE_URL}/call/{call_id}", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "call":
        result = make_outbound_call(
            name    = sys.argv[2] if len(sys.argv) > 2 else "",
            phone   = sys.argv[3] if len(sys.argv) > 3 else "",
            company = sys.argv[4] if len(sys.argv) > 4 else "",
            niche   = sys.argv[5] if len(sys.argv) > 5 else "hvac",
        )
        print(json.dumps(result, indent=2))
    elif len(sys.argv) >= 2 and sys.argv[1] == "followup":
        run_followup_calls(days_after=3, max_calls=20)
    else:
        print("Usage:")
        print("  python vapi_agent.py call 'John Smith' '5551234567' 'Smith HVAC' hvac")
        print("  python vapi_agent.py followup")
