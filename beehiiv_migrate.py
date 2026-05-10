"""
beehiiv_migrate.py — Gray Horizons Enterprise
Exports signals subscribers to Beehiiv-ready CSV.
Beehiiv has built-in paid tiers + Boosts ($1-$3/new subscriber).
2,000 subscribers = $2,000-$6,000/month from Boosts alone.

Step 1: Run this script to export subscriber list
Step 2: Go to beehiiv.com → Audience → Import → upload beehiiv_subscribers.csv
Step 3: Set up paid tier at $49/month in Beehiiv monetization
Step 4: Enable Boosts in Beehiiv dashboard (instant passive income)

Usage:
  python beehiiv_migrate.py
"""

import pandas as pd
import os
import sys
import requests
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE   = os.path.join(DATA_DIR, "outreach_queue.csv")
BLAST_LOG    = os.path.join(DATA_DIR, "signals_blast_log.csv")
EXPORT_FILE  = os.path.join(DATA_DIR, "beehiiv_subscribers.csv")

BEEHIIV_KEY  = os.getenv("BEEHIIV_API_KEY", "")
BEEHIIV_PUB  = os.getenv("BEEHIIV_PUBLICATION_ID", "")


def export_subscribers():
    """Export all leads who received signals blast as potential Beehiiv subscribers."""
    sources = []

    # Signals blast log — people who already got the signals email
    if os.path.exists(BLAST_LOG):
        df_blast = pd.read_csv(BLAST_LOG).fillna("")
        df_blast = df_blast[df_blast["sent"] == True][["email", "name"]].copy()
        df_blast["source"] = "signals_blast"
        sources.append(df_blast)
        print(f"[BEEHIIV] Signals blast subscribers: {len(df_blast)}")

    # Full queue — sent leads
    if os.path.exists(QUEUE_FILE):
        df_queue = pd.read_csv(QUEUE_FILE).fillna("")
        df_sent  = df_queue[df_queue["status"] == "sent"][["email", "company"]].copy()
        df_sent  = df_sent.rename(columns={"company": "name"})
        df_sent["source"] = "outreach_sent"
        sources.append(df_sent)
        print(f"[BEEHIIV] Outreach sent leads: {len(df_sent)}")

    if not sources:
        print("[BEEHIIV] No subscriber data found")
        return

    df = pd.concat(sources, ignore_index=True)
    df = df.drop_duplicates(subset=["email"])
    df["email"] = df["email"].str.lower().str.strip()
    df = df[df["email"].str.contains("@")]

    # Beehiiv import format
    df_export = pd.DataFrame({
        "email":      df["email"],
        "name":       df.get("name", ""),
        "utm_source": df.get("source", "gray_horizons"),
        "utm_medium": "email",
        "utm_campaign": "ghe_signals",
        "double_opt_in": "false",
        "send_welcome_email": "false",
    })

    df_export.to_csv(EXPORT_FILE, index=False)
    print(f"\n[BEEHIIV] Exported {len(df_export)} subscribers to {EXPORT_FILE}")
    return df_export


def add_via_api(df: pd.DataFrame):
    """Optionally add subscribers via Beehiiv API if keys are set."""
    if not BEEHIIV_KEY or not BEEHIIV_PUB:
        print("[BEEHIIV] No API keys — use manual CSV import instead")
        print(f"[BEEHIIV] Upload {EXPORT_FILE} at: app.beehiiv.com → Audience → Import")
        return

    headers = {
        "Authorization": f"Bearer {BEEHIIV_KEY}",
        "Content-Type": "application/json",
    }

    added = 0
    for _, row in df.iterrows():
        try:
            r = requests.post(
                f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB}/subscriptions",
                headers=headers,
                json={
                    "email": row["email"],
                    "utm_source": "gray_horizons",
                    "utm_medium": "email",
                    "double_opt_override": "off",
                    "send_welcome_email": False,
                },
                timeout=10,
            )
            if r.status_code in (200, 201):
                added += 1
        except Exception:
            pass

    print(f"[BEEHIIV] Added {added} subscribers via API")


def print_setup_guide():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           BEEHIIV SETUP GUIDE — Gray Horizons                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  1. Go to beehiiv.com → Create free account                  ║
║  2. Publication name: "Edge Engine by Gray Horizons"         ║
║  3. Audience → Import → upload beehiiv_subscribers.csv       ║
║  4. Monetize → Paid Subscriptions → Enable at $49/month      ║
║  5. Monetize → Boosts → Enable (earn $1-$3/new subscriber)   ║
║  6. Add BEEHIIV_API_KEY + BEEHIIV_PUBLICATION_ID to Railway  ║
║                                                              ║
║  Revenue projection at 2,000 subscribers:                    ║
║  • Boosts: $2,000-$6,000/month passive                       ║
║  • Paid tiers: $49 × paid subs                               ║
║  • Sponsorships: $500-$2,000/newsletter at scale             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def run():
    print("[BEEHIIV] Preparing subscriber migration to Beehiiv...")
    df = export_subscribers()

    if df is not None and len(df) > 0:
        add_via_api(df)

    print_setup_guide()


if __name__ == "__main__":
    run()
