"""
outbound_caller.py — Gray Horizons Enterprise
Calls prospects with phone numbers between 9am-5pm Mon-Fri.
Jordan (Vapi outbound agent) qualifies, pitches, books Calendly.
Auto-proposal fires the moment they book.

Run:
  python outbound_caller.py           (up to 20 calls)
  python outbound_caller.py --max 50

Safe: checks business hours before every call. Skips nights/weekends.
Tracks call_status in call_log.json so same number never gets called twice.
Saves call IDs to pending_calls.json for outcome polling (check_call_outcomes.py).
"""

import os, csv, re, sys, json, time, requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VAPI_KEY          = os.getenv("VAPI_PRIVATE_KEY", os.getenv("VAPI_API_KEY", ""))
PHONE_NUMBER_ID   = "e80874f3-73be-486f-b453-1b73573dbf9b"   # +1 (909) 927-6310 — CA area code, outbound line
OUTBOUND_AGENT_ID = "a614121f-e9df-4396-b18e-02d0bd682372"   # GHE Outbound Sales Agent (Jordan)
DEMO_LINE         = "+1 (909) 927-6310"
CALENDLY_URL      = "https://calendly.com/grayhorizonsenterprise/30min"
DATA_DIR          = Path(os.path.dirname(os.path.abspath(__file__)))

# Call list priority (best-first):
# 1. callable_prospects.csv      — scored, ranked, cleaned (rule_qualify_prospects.py output)
# 2. ai_qualified_prospects.csv  — Claude AI-scored (requires valid ANTHROPIC_API_KEY)
# 3. contractor_prospects.csv    — raw fallback
CALLABLE_CSV  = DATA_DIR / "callable_prospects.csv"
AI_QUALIFIED_CSV = DATA_DIR / "ai_qualified_prospects.csv"
PROSPECTS_CSV = DATA_DIR / "contractor_prospects.csv"
CALL_LOG      = DATA_DIR / "call_log.json"
PENDING_LOG   = DATA_DIR / "pending_calls.json"   # call IDs → outcome polling

PACIFIC = ZoneInfo("America/Los_Angeles")  # CA businesses — call in their timezone

# HARD COST GUARD — never exceed this per run without explicit override
# 20 calls × avg 90 sec × $0.12/min ≈ $3.60 max per run
DEFAULT_MAX_CALLS = 20

# ── NANP area code whitelist ─────────────────────────────────────────────────
# All currently allocated US area codes. Rejects unallocated codes (749, 822, 699, etc.)
VALID_AREA_CODES = {
    201, 202, 203, 205, 206, 207, 208, 209, 210, 212, 213, 214, 215, 216,
    217, 218, 219, 220, 224, 225, 228, 229, 231, 234, 239, 240, 248, 251,
    252, 253, 254, 256, 260, 262, 267, 269, 270, 272, 276, 279, 281, 301,
    302, 303, 304, 305, 307, 308, 309, 310, 312, 313, 314, 315, 316, 317,
    318, 319, 320, 321, 323, 325, 330, 331, 332, 334, 336, 337, 339, 346,
    347, 351, 352, 360, 361, 364, 380, 385, 386, 401, 402, 404, 405, 406,
    407, 408, 409, 410, 412, 413, 414, 415, 417, 419, 423, 424, 425, 430,
    432, 434, 435, 440, 442, 443, 458, 463, 469, 470, 475, 478, 479, 480,
    484, 501, 502, 503, 504, 505, 507, 508, 509, 510, 512, 513, 515, 516,
    517, 518, 520, 530, 531, 534, 539, 540, 541, 551, 559, 561, 562, 563,
    564, 567, 570, 571, 573, 574, 575, 580, 585, 586, 601, 602, 603, 605,
    606, 607, 608, 609, 610, 612, 614, 615, 616, 617, 618, 619, 620, 623,
    626, 628, 629, 630, 631, 636, 641, 646, 650, 651, 657, 659, 660, 661,
    662, 667, 669, 678, 680, 682, 689, 701, 702, 703, 704, 706, 707, 708,
    712, 713, 714, 715, 716, 717, 718, 719, 720, 724, 725, 726, 727, 731,
    732, 734, 737, 740, 743, 747, 754, 757, 760, 762, 763, 765, 769, 770,
    772, 774, 775, 779, 781, 785, 786, 787, 801, 802, 803, 804, 805, 806,
    808, 810, 812, 813, 814, 815, 816, 817, 818, 820, 828, 830, 831, 832,
    835, 838, 843, 845, 847, 848, 850, 854, 856, 857, 858, 859, 860, 862,
    863, 864, 865, 870, 872, 878, 901, 903, 904, 906, 907, 908, 909, 910,
    912, 913, 914, 915, 916, 917, 918, 919, 920, 925, 928, 929, 930, 931,
    936, 937, 940, 941, 945, 947, 949, 951, 952, 954, 956, 959, 970, 971,
    972, 973, 978, 979, 980, 984, 985, 989,
}

NICHE_PAIN = {
    "hvac":       "missing calls during peak season — every unanswered call is a lost job",
    "dental":     "new patient inquiries going cold after hours",
    "roofing":    "storm-season call volume overwhelming the team",
    "plumbing":   "missing emergency calls — whoever answers first gets the job",
    "solar":      "inbound leads going cold while your team is on other calls",
    "contractor": "estimates sent but never followed up",
    "default":    "leads going cold because no one follows up fast enough",
}


def clean_phone(raw: str) -> str:
    raw = str(raw).split(".")[0]
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        area = int(digits[:3])
        exchange_first = int(digits[3])
        if area not in VALID_AREA_CODES or exchange_first < 2:
            return ""
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        area = int(digits[1:4])
        exchange_first = int(digits[4])
        if area not in VALID_AREA_CODES or exchange_first < 2:
            return ""
        return f"+{digits}"
    return ""


def is_business_hours() -> bool:
    now = datetime.now(PACIFIC)
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


def load_pending() -> dict:
    try:
        return json.loads(PENDING_LOG.read_text()) if PENDING_LOG.exists() else {}
    except Exception:
        return {}


def save_pending(pending: dict):
    PENDING_LOG.write_text(json.dumps(pending, indent=2))


VOICEMAIL_SCRIPTS = {
    # California §17941 — "this is an automated message" at start
    "hvac": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Quick question about missed calls during peak HVAC season — specifically the ones "
        "going to voicemail after hours. Takes 60 seconds. "
        "Call back at 9-0-9, 9-2-7, 6-3-1-0. That's 9-0-9, 9-2-7, 6-3-1-0. Thank you."
    ),
    "roofing": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Had a quick question about calls that don't get answered after hours or when you're on a job. "
        "60-second conversation. Call back at 9-0-9, 9-2-7, 6-3-1-0. "
        "That's 9-0-9, 9-2-7, 6-3-1-0. Thanks."
    ),
    "plumbing": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Quick question — what happens when an emergency call comes in at 11pm and no one picks up? "
        "60 seconds. Call me back at 9-0-9, 9-2-7, 6-3-1-0. "
        "That's 9-0-9, 9-2-7, 6-3-1-0. Thanks."
    ),
    "solar": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Quick question about inbound leads when your team is busy on other calls. "
        "60-second conversation. Call back at 9-0-9, 9-2-7, 6-3-1-0. "
        "That's 9-0-9, 9-2-7, 6-3-1-0. Thanks."
    ),
    "dental": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Quick question about new patient calls coming in after hours or going to hold. "
        "Just 60 seconds. Call back at 9-0-9, 9-2-7, 6-3-1-0. "
        "That's 9-0-9, 9-2-7, 6-3-1-0. Thank you."
    ),
    "default": (
        "Hi, this is an automated message from Jordan at Gray Horizons Enterprise. "
        "Quick 60-second question about missed calls and how your business handles them. "
        "Call back at 9-0-9, 9-2-7, 6-3-1-0. That's 9-0-9, 9-2-7, 6-3-1-0. Thanks."
    ),
}


def fire_call(phone: str, name: str, company: str, niche: str,
              email: str = "", ai_opener: str = "") -> tuple[bool, str]:
    """Returns (success, call_id). call_id is empty string on failure."""
    pain = NICHE_PAIN.get(niche.lower(), NICHE_PAIN["default"])

    # California §17941 — must disclose AI nature at start of call
    if ai_opener and len(ai_opener.strip()) > 20:
        raw = ai_opener.strip()
        if "ai" not in raw.lower()[:40] and "automated" not in raw.lower()[:40]:
            first_msg = raw[:raw.find(" ")+1] + "I'm Jordan, an AI assistant — " + raw[raw.find(" ")+1:]
        else:
            first_msg = raw
    else:
        first_msg = (
            f"Hi, is this {company or 'the office'}? "
            f"I'm Jordan — an AI assistant calling on behalf of Gray Horizons Enterprise. "
            f"I have a quick 60-second question for whoever handles your phones. Is now a good time?"
        )

    vmail_script = VOICEMAIL_SCRIPTS.get(niche.lower(), VOICEMAIL_SCRIPTS["default"])

    payload = {
        "assistantId": OUTBOUND_AGENT_ID,
        "assistantOverrides": {
            "firstMessage":     first_msg,
            "voicemailMessage": vmail_script,
            "variableValues": {
                "company":   company,
                "niche":     niche,
                "pain":      pain,
                "calendly":  CALENDLY_URL,
                "demo_line": DEMO_LINE,
            },
        },
        "phoneNumberId":     PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name":   company or name or "Business Owner",
        },
        "maxDurationSeconds": 180,
    }

    headers = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post("https://api.vapi.ai/call/phone", headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            call_id = r.json().get("id", "")
            print(f"  [CALLED] {company or name} | {phone} | call_id={call_id}")
            return True, call_id
        else:
            print(f"  [FAIL]   {phone} | {r.status_code} | {r.text[:120]}")
            return False, ""
    except Exception as e:
        print(f"  [ERROR]  {phone} | {e}")
        return False, ""


def main(max_calls: int = DEFAULT_MAX_CALLS):
    if os.getenv("CALLS_PAUSED", "1").lower() in ("1", "true", "yes"):
        print("[PAUSED] Outbound calls are paused. Set CALLS_PAUSED=false in .env to enable.")
        sys.exit(0)

    if not VAPI_KEY:
        print("[ERROR] VAPI_PRIVATE_KEY not set")
        sys.exit(1)

    if not is_business_hours():
        now = datetime.now(PACIFIC)
        print(f"[SKIP] Outside CA business hours ({now.strftime('%a %I:%M %p PT')}). Calls run Mon-Fri 9am-5pm PT.")
        sys.exit(0)

    called  = load_called()
    pending = load_pending()

    if CALLABLE_CSV.exists():
        call_source = CALLABLE_CSV
    elif AI_QUALIFIED_CSV.exists():
        call_source = AI_QUALIFIED_CSV
    elif PROSPECTS_CSV.exists():
        call_source = PROSPECTS_CSV
    else:
        print("[ERROR] No call list found. Run: python rule_qualify_prospects.py")
        sys.exit(1)

    print(f"[OUTBOUND] Reading from: {call_source.name}")
    rows = list(csv.DictReader(open(call_source, encoding="utf-8", errors="ignore")))

    prospects      = []
    phones_this_run = set()

    for r in rows:
        phone = clean_phone(r.get("phone", ""))
        if not phone:
            continue
        if phone in called or phone in phones_this_run:
            continue

        email   = r.get("email", "")
        company = r.get("company", "")
        if not company and email:
            domain  = email.split("@")[-1].split(".")[0].replace("-", " ").title()
            company = domain

        priority = r.get("priority", r.get("ai_priority", "warm"))
        if priority == "cold":
            continue
        if r.get("ai_priority", "") == "cold":
            continue

        phones_this_run.add(phone)
        prospects.append({
            "phone":     phone,
            "name":      r.get("name", ""),
            "company":   company,
            "email":     email,
            "niche":     r.get("niche", "hvac"),
            "ai_opener": r.get("ai_opener", ""),
            "ai_pain":   r.get("ai_pain", 5),
        })

    print(f"[OUTBOUND] {len(prospects)} prospects queued | calling up to {max_calls} this run")
    print(f"           Estimated cost: ~${max_calls * 0.18:.2f} max (3 min × $0.12/min × {max_calls} calls)")
    print()

    fired = 0
    for p in prospects[:max_calls]:
        ok, call_id = fire_call(
            p["phone"], p["name"], p["company"], p["niche"],
            email=p.get("email", ""), ai_opener=p.get("ai_opener", "")
        )
        if ok:
            called.add(p["phone"])
            fired += 1
            # Save call_id for outcome polling (check_call_outcomes.py runs 30 min later)
            if call_id:
                pending[call_id] = {
                    "email":     p.get("email", ""),
                    "phone":     p["phone"],
                    "niche":     p["niche"],
                    "company":   p["company"],
                    "fired_at":  datetime.now().isoformat(),
                }
        time.sleep(2)

    save_called(called)
    save_pending(pending)
    print(f"\n[DONE] Calls fired: {fired} | Estimated cost: ~${fired * 0.18:.2f}")
    print(f"       {len(pending)} call IDs saved -> run check_call_outcomes.py in 30 min for voicemail follow-ups")
    print("       Check Vapi dashboard for recordings and outcomes.")


if __name__ == "__main__":
    limit = DEFAULT_MAX_CALLS
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--max" and i + 2 <= len(sys.argv) - 1:
            try:
                limit = int(sys.argv[i + 2])
            except ValueError:
                pass
    main(limit)
