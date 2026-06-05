"""
vapi_setup.py — Run once to create GHE inbound and outbound assistants in Vapi.
Prints the assistant IDs to add to Railway env vars.

Usage: python vapi_setup.py YOUR_VAPI_PRIVATE_KEY
"""

import sys
import json
import requests

CALENDLY_URL = "https://grayhorizonsenterprise.com"

def create_assistant(key: str, name: str, system_prompt: str, first_message: str) -> str:
    payload = {
        "name": name,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "systemPrompt": system_prompt,
            "temperature": 0.7,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
        },
        "firstMessage": first_message,
        "endCallMessage": "Thank you for your time. Have a great day.",
        "recordingEnabled": True,
        "maxDurationSeconds": 600,
        "silenceTimeoutSeconds": 30,
        "responseDelaySeconds": 0.5,
    }
    r = requests.post(
        "https://api.vapi.ai/assistant",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    if r.status_code in (200, 201):
        return r.json().get("id", "")
    else:
        print(f"Error creating {name}: {r.status_code} {r.text[:300]}")
        return ""


OUTBOUND_PROMPT = """You are a professional sales representative for Gray Horizons Enterprise, an AI automation company. Be friendly, confident, and brief. One question at a time.

Goal: Qualify the lead and book a 15-minute call or close $997 setup on the spot.

After opening, ask:
1. When a lead comes in after hours, what happens to it right now?
2. How many leads a week slip through?
3. What is your average job or client value?

Then present: We set up a system that responds to every inquiry instantly, 24 hours a day. $997 setup, $297 a month, 30-day guarantee. If you do not capture at least 5 leads you would have missed, we refund the setup fee.

Close: Does that sound worth trying? I can send a secure payment link right now.

If hesitant: I will send full details to your email. Takes 30 seconds to review.
If not interested: No problem at all. Have a great day. Then end the call.

Never be pushy. Keep every response under 3 sentences."""

INBOUND_PROMPT = f"""You are the AI receptionist for Gray Horizons Enterprise, an AI automation company in California. Professional, warm, and efficient.

When someone calls:
1. Greet: Thank you for calling Gray Horizons Enterprise. How can I help you today?
2. Find out what they need, what type of business they run, their name and email.
3. If asking about services: GHE builds AI automation systems including automated lead follow-up, AI voice agents, CRM pipelines, and email outreach for local service businesses.
4. Always try to book a 15-minute discovery call: I can get you on the calendar. The call is free and takes 15 minutes. What does your schedule look like this week?
5. Collect name, email, callback number, and business type.
6. Confirm the booking.

Booking link: {CALENDLY_URL}

If existing client: take their name and message, confirm follow-up within 24 hours.

Keep every response under 3 sentences. Be human."""


def main():
    if len(sys.argv) < 2:
        print("Usage: python vapi_setup.py YOUR_VAPI_PRIVATE_KEY")
        sys.exit(1)

    key = sys.argv[1].strip()

    print("Testing API key...")
    r = requests.get("https://api.vapi.ai/assistant", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    if r.status_code not in (200, 201):
        print(f"Invalid key or API error: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print("API key valid.\n")

    print("Creating outbound assistant...")
    outbound_id = create_assistant(
        key,
        name="GHE Outbound Sales Agent",
        system_prompt=OUTBOUND_PROMPT,
        first_message="Hi, is this {name}? This is Gray Horizons Enterprise calling. I sent you an email recently about automating your lead follow-up. Got a quick minute?",
    )

    print("Creating inbound assistant...")
    inbound_id = create_assistant(
        key,
        name="GHE Inbound Receptionist",
        system_prompt=INBOUND_PROMPT,
        first_message="Thank you for calling Gray Horizons Enterprise. How can I help you today?",
    )

    print("\n--- ADD THESE TO RAILWAY ENV VARS ---")
    print(f"VAPI_OUTBOUND_ASSISTANT_ID={outbound_id}")
    print(f"VAPI_INBOUND_ASSISTANT_ID={inbound_id}")
    print("-------------------------------------")
    print("\nNext: Buy a phone number in Vapi dashboard, assign the inbound assistant to it, then add VAPI_PHONE_NUMBER_ID to Railway.")


if __name__ == "__main__":
    main()
