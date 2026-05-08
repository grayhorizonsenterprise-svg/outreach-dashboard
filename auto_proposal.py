"""
auto_proposal.py — Gray Horizons Enterprise
Triggered by Calendly webhook after a call ends.
Auto-generates and sends a proposal + Stripe payment link.
No human action required after the close call.

Railway env vars:
  STRIPE_PAYMENT_LINK   — your Stripe payment link URL
  SENDGRID_API_KEY      — existing SendGrid key
  FROM_EMAIL            — grayhorizonsenterprise@gmail.com
  CALENDLY_URL          — your Calendly link
"""

import os
import sys
import json
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL         = os.getenv("FROM_EMAIL", "grayhorizonsenterprise@gmail.com")
STRIPE_LINK        = os.getenv("STRIPE_PAYMENT_LINK", "")
CALENDLY_URL       = os.getenv("CALENDLY_URL", "https://grayhorizonsenterprise.com")
GHE_SITE           = "https://grayhorizonsenterprise.com"


def detect_niche(notes: str) -> str:
    notes = notes.lower()
    if any(k in notes for k in ["hvac", "heating", "cooling", "ac", "furnace"]):
        return "hvac"
    if any(k in notes for k in ["dental", "dentist", "patient", "teeth"]):
        return "dental"
    if any(k in notes for k in ["hoa", "homeowner", "violation", "association"]):
        return "hoa"
    if any(k in notes for k in ["plumb", "pipe", "drain"]):
        return "plumbing"
    if any(k in notes for k in ["roof", "shingle"]):
        return "roofing"
    if any(k in notes for k in ["landscape", "lawn", "mow"]):
        return "landscaping"
    if any(k in notes for k in ["contractor", "construction", "remodel"]):
        return "contractor"
    if any(k in notes for k in ["chiro", "spine", "adjustment"]):
        return "chiropractic"
    if any(k in notes for k in ["salon", "hair", "spa", "beauty"]):
        return "salon"
    if any(k in notes for k in ["auto", "mechanic", "repair shop", "oil change"]):
        return "auto"
    return "hvac"


NICHE_PAIN = {
    "hvac":        ("missed calls and slow follow-up during peak season", "$45,000–$120,000/year in lost jobs"),
    "dental":      ("new patient inquiries going cold after hours", "$9,600–$14,400/month in lost new patient revenue"),
    "hoa":         ("violations slipping between report and resolution", "board liability and homeowner trust"),
    "plumbing":    ("missed emergency calls going to competitors", "$150,000+/year in lost emergency jobs"),
    "roofing":     ("storm-season call volume overwhelming the team", "30–50% of storm leads going unanswered"),
    "landscaping": ("overflow leads lost when schedule is full", "20–30% of new client opportunities missed"),
    "contractor":  ("estimates sent but never followed up on", "40–60% of open bids going cold"),
    "chiropractic":("after-hours new patient inquiries sitting until morning", "8–12 new patients lost per month"),
    "salon":       ("full-calendar overflow and client reactivation", "60–90 day inactive clients never recovering"),
    "auto":        ("missed calls during busy repair windows", "5–10 appointments lost per busy week"),
}


def build_proposal(name: str, company: str, email: str, niche: str) -> str:
    pain, cost = NICHE_PAIN.get(niche, NICHE_PAIN["hvac"])
    first = name.split()[0] if name else "there"
    today = datetime.date.today().strftime("%B %d, %Y")

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 0; }}
  .wrap {{ max-width: 600px; margin: 40px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
  .header {{ background: #0f172a; color: #fff; padding: 32px 40px; }}
  .header h1 {{ margin: 0; font-size: 22px; color: #38bdf8; }}
  .header p {{ margin: 8px 0 0; color: #94a3b8; font-size: 14px; }}
  .body {{ padding: 36px 40px; }}
  .section {{ margin-bottom: 28px; }}
  h2 {{ color: #0f172a; font-size: 16px; margin: 0 0 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
  .highlight {{ background: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px 20px; border-radius: 0 8px 8px 0; margin: 16px 0; }}
  .price {{ font-size: 28px; color: #22c55e; font-weight: bold; }}
  .line {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
  .cta {{ text-align: center; margin: 32px 0; }}
  .btn {{ display: inline-block; background: #22c55e; color: #000; padding: 16px 48px; border-radius: 8px; font-weight: bold; font-size: 16px; text-decoration: none; }}
  .footer {{ background: #f8fafc; padding: 20px 40px; text-align: center; color: #94a3b8; font-size: 12px; }}
  .check {{ color: #22c55e; font-weight: bold; margin-right: 8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>Gray Horizons Enterprise</h1>
    <p>AI Lead Follow-Up System — Proposal for {company}</p>
    <p style="color:#64748b;font-size:12px;">Prepared {today}</p>
  </div>
  <div class="body">
    <div class="section">
      <p>Hey {first},</p>
      <p>Thanks for taking the time to connect. Based on our conversation, the core issue is <strong>{pain}</strong> — which is costing businesses like yours roughly <strong>{cost}</strong>.</p>
      <p>Here's exactly what we'll set up for you:</p>
    </div>

    <div class="section">
      <h2>What's Included</h2>
      <p><span class="check">✓</span><strong>Automated Lead Follow-Up</strong> — every inquiry gets an immediate response, even at 2am</p>
      <p><span class="check">✓</span><strong>3-Touch Email Sequence</strong> — custom-written for your business, runs automatically</p>
      <p><span class="check">✓</span><strong>Lead Tracking Dashboard</strong> — see every inquiry, response, and status in one place</p>
      <p><span class="check">✓</span><strong>Monthly Performance Report</strong> — how many leads captured, responded to, and converted</p>
      <p><span class="check">✓</span><strong>30-Day Guarantee</strong> — you capture 5+ leads you would have missed, or we refund the setup fee</p>
    </div>

    <div class="section">
      <h2>Investment</h2>
      <div class="highlight">
        <div class="line"><span>One-time setup fee</span><span class="price">$2,500</span></div>
        <div class="line"><span>Monthly management</span><span><strong>$297/mo</strong></span></div>
        <div class="line"><span>Setup timeline</span><span>Live within 5 business days</span></div>
        <div class="line" style="border:none"><span>Contract</span><span>Month-to-month, cancel anytime</span></div>
      </div>
    </div>

    <div class="section">
      <h2>30-Day Guarantee</h2>
      <p>If you don't capture at least 5 leads in the first 30 days that you would have otherwise missed, we refund your setup fee in full. No questions.</p>
    </div>

    <div class="cta">
      <p style="font-size:15px;margin-bottom:20px;">Ready to get started? Click below to complete payment and we'll begin setup within 24 hours.</p>
      <a href="{STRIPE_LINK}" class="btn">Secure Your Spot — Pay Now</a>
      <p style="font-size:12px;color:#94a3b8;margin-top:16px;">Questions? Reply to this email or book a follow-up: <a href="{CALENDLY_URL}">{CALENDLY_URL}</a></p>
    </div>
  </div>
  <div class="footer">
    Gray Horizons Enterprise · <a href="{GHE_SITE}" style="color:#38bdf8;">{GHE_SITE}</a><br>
    This proposal is valid for 7 days from {today}.
  </div>
</div>
</body>
</html>
""".strip()


def send_proposal(name: str, company: str, email: str, niche: str) -> bool:
    if not SENDGRID_API_KEY:
        print(f"[PROPOSAL] No SendGrid key — skipping send to {email}")
        return False
    if not STRIPE_LINK:
        print(f"[PROPOSAL] No STRIPE_PAYMENT_LINK set — skipping send to {email}")
        return False

    html = build_proposal(name, company, email, niche)
    first = name.split()[0] if name else "there"

    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
        "subject": f"Your proposal — AI Lead Follow-Up System for {company}",
        "content": [{"type": "text/html", "value": html}],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 202):
            print(f"[PROPOSAL] Sent to {name} <{email}> ({niche})")
            return True
        else:
            print(f"[PROPOSAL] SendGrid error {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"[PROPOSAL] Error: {e}")
        return False


def handle_calendly_webhook(payload: dict) -> dict:
    """Parse Calendly webhook and trigger proposal send."""
    try:
        event = payload.get("event", "")
        if event != "invitee.created":
            return {"status": "ignored", "reason": f"event={event}"}

        data     = payload.get("payload", {})
        invitee  = data.get("invitee", {})
        name     = invitee.get("name", "")
        email    = invitee.get("email", "")
        answers  = invitee.get("questions_and_answers", [])
        company  = ""
        notes    = ""

        for qa in answers:
            q = qa.get("question", "").lower()
            a = qa.get("answer", "")
            if "company" in q or "business" in q:
                company = a
            notes += f" {a}"

        if not company:
            company = name

        niche = detect_niche(notes + " " + email)
        sent  = send_proposal(name, company, email, niche)

        return {
            "status": "sent" if sent else "failed",
            "to": email,
            "niche": niche,
        }
    except Exception as e:
        print(f"[PROPOSAL] Webhook parse error: {e}")
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    # Test: python auto_proposal.py name email company
    import sys
    if len(sys.argv) >= 4:
        n, e, c = sys.argv[1], sys.argv[2], sys.argv[3]
        send_proposal(n, c, e, "hvac")
    else:
        print("Usage: python auto_proposal.py 'John Smith' john@hvac.com 'Smith HVAC'")
