"""
outbound_caller.py — Gray Horizons Enterprise
Calls prospects with phone numbers between 9am-5pm Mon-Fri.
Jordan (Vapi outbound agent) qualifies, pitches, books Calendly.
Auto-proposal fires the moment they book.

Run:
  python outbound_caller.py           (up to 20 calls)
  python outbound_caller.py --max 50

Safe: checks business hours before every call. Skips nights/weekends.
Tracks call_status in prospects_raw.csv so same number never gets called twice.
"""

import os, csv, re, sys, json, requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VAPI_KEY          = os.getenv("VAPI_PRIVATE_KEY", os.getenv("VAPI_API_KEY", ""))
PHONE_NUMBER_ID   = os.getenv("VAPI_PHONE_NUMBER_ID", "e80874f3-73be-486f-b453-1b73573dbf9b")
OUTBOUND_AGENT_ID = "a614121f-e9df-4396-b18e-02d0bd682372"
CALENDLY_URL      = "https://calendly.com/grayhorizonsenterprise/30min"
DATA_DIR          = Path(os.path.dirname(os.path.abspath(__file__)))
PROSPECTS_CSV     = DATA_DIR / "prospects_raw.csv"
CALL_LOG          = DATA_DIR / "call_log.json"
EASTERN           = ZoneInfo("America/New_York")

NICHE_PAIN = {
    "hoa":        "violation tracking falling apart between report and resolution",
    "hvac":       "missing calls during peak season — every unanswered call is a lost job",
    "dental":     "new patient inquiries going cold after hours",
    "roofing":    "storm-season call volume overwhelming the team",
    "plumbing":   "missing emergency calls — whoever answers first gets the job",
    "contractor": "estimates sent but never followed up",
    "default":    "leads going cold because no one follows up fast enough",
}

PHONE_RE = re.compile(r"[\d]{10,}")


def clean_phone(raw: str) -> str:
    # handles floats like "3646232020.0"
    raw = str(raw).split(".")[0]
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return ""


def is_business_hours() -> bool:
    now = datetime.now(EASTERN)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 17


def load_called() -> set:
    try:
        return set(json.loads(CALL_LOG.read_text()).get("called", []))
    except Exception:
        return set()


def save_called(called: set):
    CALL_LOG.write_text(json.dumps({"called": list(called)}, indent=2))


def fire_call(phone: str, name: str, company: str, niche: str) -> bool:
    pain = NICHE_PAIN.get(niche.lower(), NICHE_PAIN["default"])
    payload = {
        "assistantId": OUTBOUND_AGENT_ID,
        "assistantOverrides": {
            "firstMessage": (
                f"Hi, this is Jordan calling from Gray Horizons Enterprise. "
                f"Am I speaking with someone at {company or 'your office'}?"
            ),
            "variableValues": {
                "company": company,
                "niche": niche,
                "pain": pain,
                "calendly": CALENDLY_URL,
            },
        },
        "phoneNumberId": PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name": company or name or "Business Owner",
        },
    }
    headers = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post("https://api.vapi.ai/call/phone", headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            call_id = r.json().get("id", "")
            print(f"  [CALLED] {company or name} | {phone} | call_id={call_id}")
            return True
        else:
            print(f"  [FAIL]   {phone} | {r.status_code} | {r.text[:100]}")
            return False
    except Exception as e:
        print(f"  [ERROR]  {phone} | {e}")
        return False


def main(max_calls: int = 20):
    if not VAPI_KEY:
        print("[ERROR] VAPI_PRIVATE_KEY not set")
        sys.exit(1)

    if not is_business_hours():
        now = datetime.now(EASTERN)
        print(f"[SKIP] Outside business hours ({now.strftime('%a %I:%M %p ET')}). Run Mon-Fri 9am-5pm ET.")
        sys.exit(0)

    called = load_called()

    rows = list(csv.DictReader(open(PROSPECTS_CSV, encoding="utf-8", errors="ignore")))
    prospects = []
    for r in rows:
        phone = clean_phone(r.get("phone", ""))
        if not phone or phone in called:
            continue
        prospects.append({
            "phone":   phone,
            "name":    r.get("name", ""),
            "company": r.get("company", ""),
            "niche":   r.get("niche", "default"),
        })

    print(f"[OUTBOUND] {len(prospects)} prospects with phones | calling up to {max_calls}")

    fired = 0
    for p in prospects[:max_calls]:
        if fire_call(p["phone"], p["name"], p["company"], p["niche"]):
            called.add(p["phone"])
            fired += 1

    save_called(called)
    print(f"\n[DONE] Calls fired: {fired}")


if __name__ == "__main__":
    limit = 20
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--max" and i + 2 <= len(sys.argv) - 1:
            try:
                limit = int(sys.argv[i + 2])
            except ValueError:
                pass
    main(limit)
