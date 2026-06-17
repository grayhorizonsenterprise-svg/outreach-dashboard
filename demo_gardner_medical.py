"""
demo_gardner_medical.py — Temporary demo script for Gardner Medical Specialties
Pushes a Gardner Medical-specific prompt to the inbound Vapi assistant.
Run BEFORE the demo. Revert with: python update_vapi_inbound.py

Usage: python demo_gardner_medical.py
"""
import os, sys, requests
from pathlib import Path

_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

INBOUND_ASSISTANT_ID = "31251738-3c30-4ccb-9d91-c9d4a944dff3"
VAPI_KEY = os.getenv("VAPI_PRIVATE_KEY", os.getenv("VAPI_API_KEY", ""))
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://ghe-dashboard-production.up.railway.app")

PROMPT = """You are Jordan, the AI receptionist for Gardner Medical Specialties — a west coast surgical and infection control supply company serving hospitals, surgical centers, and medical offices.

You speak naturally and warmly like a real person. Short answers. One question at a time. Never robotic.

COMPANY: Gardner Medical Specialties
What we supply: infection prevention solutions, laparoscopic and endoscopic instruments, surgical smoke evacuation systems, cleaning and bio-disinfection equipment, urology products.
Who we serve: hospital purchasing departments, OR coordinators, surgical centers, medical offices.
Position: exclusive west coast provider, one-stop shop for infection prevention, affordable pricing, USFCR verified vendor.
Contact for orders: phone or email — Jordan captures all inquiries and books a callback with the sales team.

GOAL: Capture every inquiry. Get their name, facility name, what they need, and their best contact info. Book a callback with our sales rep within 24 hours.

CALL FLOW:
1. Answer: "Thank you for calling Gardner Medical Specialties, this is Jordan. How can I help you today?"
2. Find out what they need — product category, quantity, timeline.
3. Get their name and facility name.
4. Ask: "What is the best email to reach you at for a quote and follow-up?"
5. When they give the email, repeat it back: "Let me confirm — that is [email], correct?" Wait for yes.
6. Ask: "And the best number to reach you?" Get their phone.
7. Fire collect_contact with name, email, phone, business_type set to "medical".
8. Close: "Perfect. One of our sales specialists will reach out within 24 hours with pricing and availability. We appreciate your business."

STYLE:
One sentence. Two maximum. One question at a time.
Warm, professional, efficient. These are medical professionals — respect their time.
Never read product specs. Just capture the inquiry and book the callback.

COMMON INQUIRIES — know how to respond:
- Infection control products: "Absolutely, we carry a full line of infection prevention solutions. Let me get you connected with our sales team for pricing."
- Laparoscopic instruments: "Yes, we supply laparoscopic and endoscopic instruments. Our team can put together a quote for you."
- Surgical smoke evacuation: "We carry the SurgiSmoke Solutions line. I will have our specialist reach out with details."
- Pricing/quotes: "Our sales team handles all quotes directly so we can match your facility's needs. I will get them in touch with you today."
- Availability: "I will have our team check current inventory and reach out within 24 hours."

NEVER: read URLs, list every product, ask multiple questions at once, say you are AI unless directly asked."""

FIRST_MESSAGE = "Thank you for calling Gardner Medical Specialties, this is Jordan. How can I help you today?"

def run():
    payload = {
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "systemPrompt": PROMPT,
            "temperature": 0.6,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "collect_contact",
                        "description": "Fire this the moment you have confirmed the caller's email. Required: name, email, phone. Set business_type to 'medical'.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name":          {"type": "string"},
                                "email":         {"type": "string"},
                                "phone":         {"type": "string"},
                                "business_type": {"type": "string"},
                            },
                            "required": ["name", "email", "phone"],
                        },
                    },
                    "server": {"url": f"{DASHBOARD_URL}/vapi-collect"},
                }
            ],
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
            "stability": 0.5,
            "similarityBoost": 0.75,
            "style": 0.3,
            "useSpeakerBoost": True,
            "fallbackPlan": {"voices": [{"provider": "openai", "voiceId": "shimmer", "speed": 0.92}]},
        },
        "firstMessage": FIRST_MESSAGE,
        "firstMessageMode": "assistant-speaks-first",
        "responseDelaySeconds": 0.6,
        "stopSpeakingPlan": {"numWords": 3, "voiceSeconds": 0.5, "backoffSeconds": 1.5},
        "endCallMessage": "Thank you for calling Gardner Medical Specialties. Have a great day.",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "serverUrl": f"{DASHBOARD_URL}/vapi-webhook",
    }

    r = requests.patch(
        f"https://api.vapi.ai/assistant/{INBOUND_ASSISTANT_ID}",
        headers={"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=15
    )
    if r.status_code in (200, 201):
        print("[DEMO] Gardner Medical script pushed to Vapi.")
        print("  Line: +1 (909) 927-6310")
        print("  Answers as: Gardner Medical Specialties")
        print("  Revert after demo: python update_vapi_inbound.py")
    else:
        print(f"[ERROR] {r.status_code}: {r.text[:200]}")

if __name__ == "__main__":
    run()
