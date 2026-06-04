"""
bland_caller.py — Gray Horizons Enterprise
AI voice caller via Bland.ai. No Twilio registration required.
Triggered automatically when a lead replies with interest OR books Calendly.
Handles the full sales conversation, books to Calendly or closes to Stripe.

Railway env vars needed:
  BLAND_API_KEY          — get free at app.bland.ai
  CALENDLY_URL           — already set
  STRIPE_PAYMENT_LINK    — already set
"""

import os
import requests
import json

BLAND_API_KEY  = os.getenv("BLAND_API_KEY", "")
CALENDLY_URL   = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
STRIPE_LINK    = os.getenv("STRIPE_PAYMENT_LINK", "")
FROM_EMAIL     = os.getenv("FROM_EMAIL", os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com"))

BLAND_API_URL  = "https://api.bland.ai/v1/calls"

NICHE_PAIN = {
    "hvac":        "missing calls during peak season — every unanswered call is a $400-800 job going to a competitor",
    "dental":      "new patient inquiries going cold after hours — the average practice loses 8-12 new patients a month this way",
    "hoa":         "violation tracking falling apart between report and resolution — boards getting hit with liability they didn't see coming",
    "plumbing":    "missing emergency calls — a plumber who answers first gets the job, period",
    "roofing":     "storm-season call volume overwhelming the team — 30-50% of storm leads go unanswered",
    "landscaping": "overflow leads getting lost when the schedule fills up",
    "contractor":  "estimates sent but never followed up on — 40-60% of open bids go cold",
    "chiropractic":"after-hours new patient inquiries sitting until morning — 8-12 new patients lost per month",
    "salon":       "full-calendar overflow and client reactivation — inactive clients never coming back",
    "auto":        "missed calls during busy repair windows — 5-10 appointments lost per busy week",
    "realestate":  "buyer and seller leads going cold before first contact",
    "pest_control":"missed calls during peak season — customers call the next company if you don't answer",
    "electrician": "after-hours emergency calls going to competitors",
    "veterinary":  "appointment requests sitting unanswered overnight",
    "optometry":   "new patient inquiries going cold after hours",
}

CALL_SCRIPT = """
You are a sales consultant from Gray Horizons Enterprise. You are friendly, confident, and direct.
You are calling {name} at {company}.

Your opening (say this exactly):
"Hi, is this {name}? This is Gray Horizons Enterprise calling — I sent you an email recently about automating your lead follow-up. Got a quick minute?"

If they say yes, continue:
"The reason I'm calling is we keep seeing {niche_business} businesses lose revenue because of {pain}. We built a system that fixes that automatically. I wanted to see if that's actually a problem for you right now."

Ask these questions and LISTEN — do not rush:
1. "When a lead comes in after hours or during a busy stretch, what happens to it right now?"
2. "Roughly how many leads a week do you think slip through?"
3. "What's your average job or client value?"

Based on their answers, present the offer:
"Here's what we set up: the system responds to every new inquiry instantly — email, contact form, wherever they come from — 24 hours a day. We've had {niche_business} owners recover 6-10 jobs in the first month. It's $997 to set up, $297 a month after that, and there's a 30-day guarantee — if you don't capture at least 5 leads you would have missed, we refund the setup."

Close:
"Does that sound like something worth trying? I can send you a secure payment link right now and have you live within 5 business days."

If they want to think about it:
"Totally fair. I'll send the full details to your email — takes 30 seconds to review. What's the best email for that?"

If they ask about what the system actually does:
"It's an AI follow-up system — when someone contacts you, it responds immediately with the right message, qualifies them, and gets them booked. You just see confirmed appointments in your calendar. We handle everything in between."

If they're not interested: "No problem at all, I appreciate your time. Have a great day."

Keep responses short. Never be pushy. Be conversational — this is a real conversation, not a pitch.
"""

def make_call(name: str, phone: str, company: str, niche: str, email: str = "") -> dict:
    if not BLAND_API_KEY:
        print(f"[BLAND] No API key set — skipping call to {name} ({phone})")
        return {"status": "skipped", "reason": "no_api_key"}

    phone = "".join(c for c in phone if c.isdigit() or c == "+")
    if len(phone.lstrip("+")) < 10:
        print(f"[BLAND] Invalid phone for {name}: {phone!r}")
        return {"status": "skipped", "reason": "invalid_phone"}

    niche_key = niche.lower().replace(" ", "_")
    pain = NICHE_PAIN.get(niche_key, "leads slipping through because of slow follow-up")
    niche_business = niche.replace("_", " ").title()
    script = CALL_SCRIPT.format(
        name=name or "there",
        company=company or "your business",
        pain=pain,
        niche_business=niche_business,
    )

    payload = {
        "phone_number": phone if phone.startswith("+") else f"+1{phone}",
        "task": script,
        "voice": "maya",
        "language": "en",
        "max_duration": 15,
        "record": True,
        "reduce_latency": True,
        "request_data": {
            "name": name,
            "company": company,
            "niche": niche,
            "email": email,
            "stripe_link": STRIPE_LINK,
            "calendly_url": CALENDLY_URL,
        },
    }

    try:
        r = requests.post(
            BLAND_API_URL,
            headers={"authorization": BLAND_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            call_id = data.get("call_id", "")
            print(f"[BLAND] Call initiated → {name} at {phone} ({niche}) call_id={call_id}")
            return {"status": "initiated", "call_id": call_id, "to": phone, "name": name}
        else:
            print(f"[BLAND] API error {r.status_code}: {r.text[:300]}")
            return {"status": "error", "code": r.status_code, "detail": r.text[:200]}
    except Exception as e:
        print(f"[BLAND] Exception: {e}")
        return {"status": "error", "detail": str(e)}


def call_from_calendly(webhook_payload: dict) -> dict:
    """Auto-call when someone books Calendly — pre-qualifies before the actual meeting."""
    try:
        data    = webhook_payload.get("payload", {})
        invitee = data.get("invitee", {})
        name    = invitee.get("name", "")
        email   = invitee.get("email", "")
        phone   = ""
        company = ""
        niche_notes = ""

        for qa in invitee.get("questions_and_answers", []):
            q = qa.get("question", "").lower()
            a = qa.get("answer", "")
            if any(k in q for k in ["phone", "number", "mobile", "cell"]):
                phone = a
            if any(k in q for k in ["company", "business", "organization"]):
                company = a
            niche_notes += f" {a}"

        if not company:
            company = name

        from auto_proposal import detect_niche
        niche = detect_niche(niche_notes + " " + email)

        if not phone:
            print(f"[BLAND] Calendly booking from {name} — no phone number provided, skipping call")
            return {"status": "skipped", "reason": "no_phone_in_booking"}

        return make_call(name, phone, company, niche, email)
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def call_hot_lead(lead: dict) -> dict:
    """Call a hot lead from the Gmail reply monitor."""
    return make_call(
        name    = lead.get("name", lead.get("company", "there")),
        phone   = lead.get("phone", ""),
        company = lead.get("company", ""),
        niche   = lead.get("niche", "hvac"),
        email   = lead.get("email", ""),
    )


def get_call_status(call_id: str) -> dict:
    if not BLAND_API_KEY:
        return {}
    try:
        r = requests.get(
            f"https://api.bland.ai/v1/calls/{call_id}",
            headers={"authorization": BLAND_API_KEY},
            timeout=10,
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        result = make_call(
            name    = sys.argv[1],
            phone   = sys.argv[2],
            company = sys.argv[3],
            niche   = sys.argv[4] if len(sys.argv) > 4 else "hvac",
        )
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python bland_caller.py 'John Smith' '5551234567' 'Smith HVAC' hvac")
