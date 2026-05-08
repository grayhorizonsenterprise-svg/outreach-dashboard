"""
performance_tracker.py — Gray Horizons Enterprise
Tracks which email templates, niches, and subject lines generate
replies and payments. Auto-weights the outreach generator toward
what's working. Zero human input required.

Data written to performance.json in DATA_DIR.
Called by gmail_reply_monitor when a hot lead is detected,
and by the Stripe webhook when a payment lands.
"""

import os
import json
import datetime

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
PERF_FILE = os.path.join(DATA_DIR, "performance.json")


def _load() -> dict:
    if os.path.exists(PERF_FILE):
        try:
            with open(PERF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "niches":   {},   # niche -> {sent, replies, payments, revenue}
        "subjects": {},   # subject -> {sent, replies}
        "last_updated": None,
    }


def _save(data: dict):
    data["last_updated"] = datetime.datetime.utcnow().isoformat()
    with open(PERF_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_sent(niche: str, subject: str):
    d = _load()
    d["niches"].setdefault(niche, {"sent": 0, "replies": 0, "payments": 0, "revenue": 0.0})
    d["niches"][niche]["sent"] += 1
    d["subjects"].setdefault(subject, {"sent": 0, "replies": 0})
    d["subjects"][subject]["sent"] += 1
    _save(d)


def record_reply(niche: str, subject: str = ""):
    d = _load()
    d["niches"].setdefault(niche, {"sent": 0, "replies": 0, "payments": 0, "revenue": 0.0})
    d["niches"][niche]["replies"] += 1
    if subject:
        d["subjects"].setdefault(subject, {"sent": 0, "replies": 0})
        d["subjects"][subject]["replies"] += 1
    _save(d)


def record_payment(niche: str, amount: float):
    d = _load()
    d["niches"].setdefault(niche, {"sent": 0, "replies": 0, "payments": 0, "revenue": 0.0})
    d["niches"][niche]["payments"] += 1
    d["niches"][niche]["revenue"] += amount
    _save(d)


def get_niche_weights() -> dict:
    """
    Returns a weight per niche based on reply rate + payment rate.
    Used by outreach_generator to allocate more emails to winning niches.
    Default weight 1.0 for niches with no data.
    """
    d = _load()
    weights = {}
    for niche, stats in d["niches"].items():
        sent = max(stats.get("sent", 1), 1)
        reply_rate   = stats.get("replies", 0) / sent
        payment_rate = stats.get("payments", 0) / sent
        # weight = reply rate * 2 + payment rate * 10 (payments matter more)
        weights[niche] = round(1.0 + (reply_rate * 2) + (payment_rate * 10), 3)
    return weights


def get_best_subjects(niche: str = None, top_n: int = 3) -> list:
    """Returns top N subject lines by reply rate."""
    d = _load()
    scored = []
    for subj, stats in d["subjects"].items():
        sent = max(stats.get("sent", 1), 1)
        rate = stats.get("replies", 0) / sent
        scored.append((rate, subj))
    scored.sort(reverse=True)
    return [s for _, s in scored[:top_n]] if scored else []


def get_summary() -> str:
    d = _load()
    lines = ["=== PERFORMANCE SUMMARY ==="]
    total_sent = total_replies = total_payments = total_rev = 0

    for niche, s in sorted(d["niches"].items()):
        sent  = s.get("sent", 0)
        rep   = s.get("replies", 0)
        pay   = s.get("payments", 0)
        rev   = s.get("revenue", 0)
        rrate = f"{rep/sent*100:.1f}%" if sent else "n/a"
        lines.append(f"  {niche.upper():12s} | sent={sent:4d} | replies={rep:3d} ({rrate}) | paid={pay} | ${rev:,.0f}")
        total_sent += sent; total_replies += rep
        total_payments += pay; total_rev += rev

    lines.append(f"\n  TOTAL: {total_sent} sent | {total_replies} replies | {total_payments} payments | ${total_rev:,.0f} revenue")

    best = get_best_subjects(top_n=3)
    if best:
        lines.append("\n  TOP SUBJECTS:")
        for s in best:
            st = d["subjects"].get(s, {})
            lines.append(f"    '{s}' — {st.get('replies',0)}/{st.get('sent',1)} replies")

    return "\n".join(lines)


if __name__ == "__main__":
    print(get_summary())
    print("\nNiche weights:", get_niche_weights())
