"""
test_carrier_sms.py — blast a text via carrier email gateways
Usage: python test_carrier_sms.py 9096448087
"""
import smtplib, sys, os
from email.mime.text import MIMEText
from pathlib import Path

# Load .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SG_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
SENDER = os.getenv("SENDER_EMAIL", "").strip().lower()

CARRIERS = [
    "txt.att.net",           # AT&T
    "vtext.com",             # Verizon
    "tmomail.net",           # T-Mobile
    "messaging.sprintpcs.com",  # Sprint
    "sms.myboostmobile.com", # Boost
    "sms.cricketwireless.net",  # Cricket
    "mymetropcs.com",        # Metro PCS
    "email.uscc.net",        # US Cellular
    "msg.fi.google.com",     # Google Fi
]

def send_carrier_sms(phone_raw: str, message: str, subject: str = "") -> dict:
    digits = "".join(c for c in phone_raw if c.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return {"error": f"Invalid phone: {phone_raw}"}

    results = {}
    try:
        server = smtplib.SMTP("smtp.sendgrid.net", 587, timeout=10)
        server.starttls()
        server.login("apikey", SG_KEY)
        for carrier in CARRIERS:
            to = f"{digits}@{carrier}"
            msg = MIMEText(message)
            msg["From"] = SENDER
            msg["To"] = to
            msg["Subject"] = subject
            try:
                server.sendmail(SENDER, [to], msg.as_string())
                results[carrier] = "sent"
                print(f"  [OK]   {to}")
            except Exception as e:
                results[carrier] = f"fail: {e}"
                print(f"  [FAIL] {to} — {e}")
        server.quit()
    except Exception as e:
        return {"error": str(e)}
    return results

if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "9096448087"
    msg = (
        "Hey, this is Jordan with Gray Horizons Enterprise. "
        "Here's your link to book a free 15-min demo: "
        "calendly.com/grayhorizonsenterprise/30min"
    )
    print(f"\nBlasting to {phone} across {len(CARRIERS)} carriers...\n")
    results = send_carrier_sms(phone, msg)
    hits = sum(1 for v in results.values() if v == "sent")
    print(f"\nDone — {hits}/{len(CARRIERS)} gateways accepted.")
