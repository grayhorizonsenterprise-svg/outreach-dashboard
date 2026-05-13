"""
email_verifier.py — Gray Horizons Enterprise
Verifies emails before sending to protect domain reputation.
Uses Hunter.io verify endpoint (free: 50/month) + basic syntax/MX checks.
Run before any blast to remove invalid addresses.
Reads prospects_raw.csv or grant_queue.csv, adds verified=True/False column.
"""

import re
import socket
import pandas as pd
import requests
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR   = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwam.com",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "spam4.me", "trashmail.com", "dispostable.com", "mailnull.com",
}

ROLE_PREFIXES = {
    "info", "contact", "support", "admin", "noreply", "no-reply",
    "hello", "team", "sales", "help", "service", "billing",
}


def is_valid_syntax(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def is_disposable(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in DISPOSABLE_DOMAINS


def is_role_address(email: str) -> bool:
    local = email.split("@")[0].lower()
    return local in ROLE_PREFIXES


def has_mx_record(email: str) -> bool:
    domain = email.split("@")[-1]
    try:
        socket.getaddrinfo(domain, None)
        return True
    except Exception:
        return False


def hunter_verify(email: str) -> str:
    """Returns: valid | invalid | unknown (if no key or limit reached)"""
    if not HUNTER_KEY:
        return "unknown"
    try:
        r = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": HUNTER_KEY},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("result", "unknown")
        elif r.status_code == 429:
            print("[VERIFY] Hunter rate limit")
            return "unknown"
    except Exception:
        pass
    return "unknown"


def verify_email(email: str, use_hunter: bool = False) -> tuple[bool, str]:
    """Returns (keep: bool, reason: str)"""
    email = email.strip().lower()
    if not email:
        return False, "empty"
    if not is_valid_syntax(email):
        return False, "invalid_syntax"
    if is_disposable(email):
        return False, "disposable"
    if not has_mx_record(email):
        return False, "no_mx"

    # Role addresses are lower priority but not invalid
    if is_role_address(email):
        return True, "role_address"

    if use_hunter:
        result = hunter_verify(email)
        if result == "invalid":
            return False, "hunter_invalid"
        if result == "valid":
            return True, "hunter_verified"

    return True, "basic_pass"


def run(input_file: str = None, use_hunter: bool = False):
    files_to_check = []
    if input_file:
        files_to_check = [input_file]
    else:
        for fname in ["prospects_raw.csv", "grant_queue.csv", "signals_queue.csv"]:
            path = os.path.join(DATA_DIR, fname)
            if os.path.exists(path):
                files_to_check.append(path)

    for path in files_to_check:
        print(f"\n[VERIFY] Checking {os.path.basename(path)}...")
        df = pd.read_csv(path, dtype=str).fillna("")

        if "email" not in df.columns:
            print("  No email column — skipping")
            continue

        before = len(df)
        results = []
        removed = 0

        for i, row in df.iterrows():
            email = str(row["email"]).strip().lower()
            keep, reason = verify_email(email, use_hunter=use_hunter)
            results.append({"keep": keep, "verify_reason": reason})
            if not keep:
                removed += 1
            if use_hunter:
                time.sleep(0.5)

        df["_keep"]          = [r["keep"] for r in results]
        df["verify_reason"]  = [r["verify_reason"] for r in results]

        df_clean = df[df["_keep"]].drop(columns=["_keep"])
        df_clean.to_csv(path, index=False)

        print(f"  Before: {before} | Removed: {removed} | Clean: {len(df_clean)}")
        if removed > 0:
            reasons = {}
            for r in results:
                if not r["keep"]:
                    reasons[r["verify_reason"]] = reasons.get(r["verify_reason"], 0) + 1
            for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"    {reason}: {count}")

    print("\n[VERIFY] Done. Lists cleaned.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=None, help="Specific CSV to verify")
    parser.add_argument("--hunter", action="store_true", help="Use Hunter.io API verification")
    args = parser.parse_args()
    run(input_file=args.file, use_hunter=args.hunter)
