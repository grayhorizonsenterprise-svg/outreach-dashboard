"""
signals_blast.py — Gray Horizons Enterprise
One-time email blast to all existing leads about Edge Engine signals subscription.
Different pitch from the AI system — targets anyone interested in market edge.

Run once:
  python signals_blast.py
"""

import pandas as pd
import requests
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SENDGRID_KEY       = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL         = os.getenv("SENDER_EMAIL", "grayhorizonsenterprise@gmail.com")
SIGNALS_LINK       = os.getenv("STRIPE_SIGNALS_LINK", "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01")
DRAFTKINGS_URL     = os.getenv("DRAFTKINGS_AFFILIATE_URL", "")
FANDUEL_URL        = os.getenv("FANDUEL_AFFILIATE_URL", "")
DATA_DIR           = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE         = os.path.join(DATA_DIR, "outreach_queue.csv")
BLAST_LOG          = os.path.join(DATA_DIR, "signals_blast_log.csv")

SUBJECT = "Something separate — daily market signals"

def _build_html():
    affiliate_block = ""
    if DRAFTKINGS_URL or FANDUEL_URL:
        links = ""
        if DRAFTKINGS_URL:
            links += f'<a href="{DRAFTKINGS_URL}" style="display:inline-block;background:#53d22c;color:#000;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:bold;margin-right:8px;">DraftKings — Get Bonus</a>'
        if FANDUEL_URL:
            links += f'<a href="{FANDUEL_URL}" style="display:inline-block;background:#1493ff;color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:bold;">FanDuel — Get Bonus</a>'
        affiliate_block = f"""
<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
<p><strong>Want to put the sports picks to use?</strong></p>
<p>If you're not already on DraftKings or FanDuel, both are offering sign-up bonuses right now. We use both platforms when we run our picks.</p>
<p>{links}</p>
<p style="color:#94a3b8;font-size:12px;">Bonus offers vary by state. Must be 21+. Please gamble responsibly.</p>
"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:32px auto;color:#1e293b;line-height:1.7;">
<p>Hey,</p>

<p>Separate from everything else we do — we run an AI signal engine that scans stocks, crypto, and sports lines every morning and surfaces the highest-edge opportunities before the market opens.</p>

<p>We've been running it internally. Starting to open it up.</p>

<p><strong>What you get daily:</strong></p>
<ul>
  <li>Stock signals with entry points and confidence scores</li>
  <li>Crypto trend alerts</li>
  <li>Sports edge picks with Kelly criterion bet sizing</li>
  <li>Congressional trading alerts (Pelosi et al)</li>
</ul>

<p>Delivered to your inbox every morning before 8am. $49/month, cancel anytime.</p>

<p><a href="{SIGNALS_LINK}" style="display:inline-block;background:#0f172a;color:#38bdf8;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">See the details — $49/month</a></p>

{affiliate_block}

<p style="color:#64748b;font-size:13px;">Not financial advice. Signals are algorithmic and for informational purposes only.</p>

<p>— Alex<br>Gray Horizons Enterprise</p>
</body>
</html>"""

HTML = _build_html()


def send(email: str, name: str = "") -> bool:
    payload = {
        "personalizations": [{"to": [{"email": email, "name": name}]}],
        "from": {"email": FROM_EMAIL, "name": "Alex | Gray Horizons"},
        "subject": SUBJECT,
        "content": [{"type": "text/html", "value": HTML}],
    }
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def run():
    if not SENDGRID_KEY:
        print("[BLAST] No SENDGRID_API_KEY set")
        return

    df = pd.read_csv(QUEUE_FILE).fillna("")

    # Only blast to leads that were already sent the main outreach (warm) or pending
    targets = df[
        (df["email"].str.strip() != "") &
        (df["status"].isin(["sent", "pending"]))
    ].drop_duplicates(subset=["email"])

    # Filter out wrong targets
    bad_email_prefixes = [
        "noreply@", "no-reply@", "support@", "help@", "helpdesk@",
        "ticket@", "billing@", "admin@", "clientcare@", "customercare@",
        "care@", "service@", "accounts@", "team@", "press@", "media@",
    ]
    bad_company_keywords = [
        "insurance", "bank", "attorney", "law firm", "malpractice",
        "hospital", "health system", "medical center", "webmd", "communicare",
        "university", "college", "school", "government", "nonprofit",
        "chamber of commerce", "association", "magazine", "publisher",
        "software", "platform", "saas", "highrises", "appfolio", "buildium",
        "academy of general dentistry", "agd", "membership services",
    ]
    targets = targets[~targets["email"].str.lower().apply(
        lambda e: any(e.startswith(p) for p in bad_email_prefixes)
    )]
    targets = targets[~targets.get("company", pd.Series([""] * len(targets))).str.lower().apply(
        lambda c: any(p in c for p in bad_company_keywords)
    )]

    # Skip unsubscribed
    unsub_file = os.path.join(DATA_DIR, "unsubscribe_list.csv")
    if os.path.exists(unsub_file):
        unsubs = set(pd.read_csv(unsub_file)["email"].str.lower().tolist())
        targets = targets[~targets["email"].str.lower().isin(unsubs)]

    # Skip anyone already blasted
    if os.path.exists(BLAST_LOG):
        done = set(pd.read_csv(BLAST_LOG)["email"].str.lower().tolist())
        targets = targets[~targets["email"].str.lower().isin(done)]

    print(f"[BLAST] Sending signals pitch to {len(targets)} leads...")

    log = []
    sent = fail = 0

    for _, row in targets.iterrows():
        email = str(row["email"]).strip().lower()
        name  = str(row.get("name", row.get("company", ""))).strip()

        success = send(email, name)
        log.append({"email": email, "name": name, "sent": success})

        if success:
            sent += 1
        else:
            fail += 1

        if (sent + fail) % 50 == 0:
            print(f"  [{sent + fail}/{len(targets)}] sent={sent} fail={fail}")

        time.sleep(0.1)

    pd.DataFrame(log).to_csv(BLAST_LOG, index=False)
    print(f"\n[BLAST] Done — {sent} sent, {fail} failed")
    print(f"Expected subscribers at 0.5% conversion: ~{int(sent * 0.005)}")
    print(f"Expected revenue at $49/mo: ~${int(sent * 0.005) * 49}/month")


if __name__ == "__main__":
    run()
