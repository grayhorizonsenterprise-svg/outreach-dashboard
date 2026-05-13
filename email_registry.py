"""
email_registry.py — Gray Horizons Enterprise
Global cross-engine email deduplication registry.
Every engine imports this before scraping or sending.
One email address = one engine, one time, forever.
"""
import os
import csv
import threading
import pandas as pd
from datetime import datetime

_lock = threading.Lock()

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(DATA_DIR, "global_sent.csv")

# Every queue and log file across all engines
_ALL_FILES = [
    # Sent logs
    "sent_log.csv",
    "signals_sent_log.csv",
    "followup_log.csv",
    "global_sent.csv",
    # Opt-out
    "unsubscribe_list.csv",
    # All engine queues — blocks cross-engine duplicates at scrape AND send time
    "outreach_queue.csv",
    "signals_queue.csv",
    "realestate_queue.csv",
    "medspa_queue.csv",
    "insurance_queue.csv",
    "ecommerce_queue.csv",
    "restaurant_queue.csv",
    "gym_queue.csv",
    "mortgage_queue.csv",
    "grant_queue.csv",
]


def load_global_registry(exclude_queue: str = None) -> set:
    """
    Returns every email ever scraped, queued, or sent across all engines.
    Pass exclude_queue="realestate_queue.csv" so the engine can still work
    its own pending rows — but every OTHER engine's addresses are blocked.
    """
    registry = set()
    for fname in _ALL_FILES:
        if exclude_queue and fname == exclude_queue:
            continue
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            if "email" in df.columns:
                registry.update(
                    e for e in df["email"].str.lower().str.strip() if e
                )
        except Exception:
            pass
    return registry


def register_sent(email: str, engine: str) -> None:
    """
    Write a successfully sent email to the global registry.
    Thread-safe. All engines call this after every successful send.
    """
    email = email.lower().strip()
    if not email:
        return
    with _lock:
        row = {
            "email": email,
            "engine": engine,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        file_exists = os.path.exists(REGISTRY_FILE)
        with open(REGISTRY_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                w.writeheader()
            w.writerow(row)
