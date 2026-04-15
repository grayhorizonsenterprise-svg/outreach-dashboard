"""
Grant Scoring Engine

Assigns each grant:
  - match_score (0–100): how well this grant fits the user profile
  - win_probability (0–100): estimated chance of winning
  - effort_level: low / medium / high
  - days_to_apply: estimated prep time in days

All scoring is rule-based for speed (no LLM calls).
"""
import json
import re
from datetime import datetime, date
from pathlib import Path


def _load_profile() -> dict:
    profile_path = Path(__file__).parent.parent / "user_profile.json"
    if profile_path.exists():
        with open(profile_path) as f:
            return json.load(f)
    return {}


# ─── Keyword maps ─────────────────────────────────────────────────────────────

MINORITY_KEYWORDS = [
    "minority", "black-owned", "black owned", "african american",
    "disadvantaged", "mbe", "8(a)", "8a", "wbe", "sbe",
    "diverse", "underserved", "underrepresented", "bipoc",
    "minority-owned", "historically underutilized",
]

INDUSTRY_KEYWORDS = {
    "technology": [
        "tech", "technology", "digital", "software", "innovation", "stem", "it ", "information technology",
        "ai", "artificial intelligence", "automation", "saas", "machine learning", "data science",
        "cloud", "sbir", "sttr", "r&d", "research and development", "emerging technology",
    ],
    "ai": [
        "ai", "artificial intelligence", "machine learning", "automation", "saas", "deep learning",
        "neural", "nlp", "data science", "algorithm", "predictive",
    ],
    "automation": [
        "automation", "automate", "automated", "robotic", "rpa", "workflow automation",
        "smart home", "iot", "internet of things",
    ],
    "saas": ["saas", "software as a service", "cloud software", "subscription software", "platform"],
    "innovation": ["innovation", "innovative", "emerging", "cutting-edge", "breakthrough", "novel"],
    "entrepreneurship": ["entrepreneur", "entrepreneurship", "startup", "founder", "new venture", "business owner"],
    "construction": ["construction", "contractor", "infrastructure", "renovation", "building", "facilities"],
    "community development": ["community", "neighborhood", "revitalization", "nonprofit", "social impact"],
    "workforce development": ["workforce", "training", "employment", "jobs", "apprenticeship", "career"],
    "economic development": ["economic", "business development", "entrepreneurship", "startup", "small business"],
}

LOW_EFFORT_SIGNALS = [
    "simple application", "one-page", "letter of intent", "loi", "short form",
    "online form", "quick apply", "2-page", "two-page",
]

HIGH_EFFORT_SIGNALS = [
    "rfp", "proposal", "audit", "financial statements", "501c3",
    "tax returns", "business plan required", "site visit", "interview required",
]


def score_grant(grant: dict, profile: dict = None) -> dict:
    """
    Score a single grant against the user profile.
    Returns dict with match_score, win_probability, effort_level, days_to_apply.
    """
    if profile is None:
        profile = _load_profile()

    text = " ".join([
        grant.get("name", ""),
        grant.get("description", ""),
        grant.get("eligibility", ""),
        grant.get("category", ""),
        " ".join(grant.get("tags", []) if isinstance(grant.get("tags"), list) else []),
    ]).lower()

    score = 0
    reasons = []

    # ── 1. Minority/demographic alignment (up to 25 pts) ─────────────────────
    owner_demos = [d.lower() for d in profile.get("owner_demographics", [])]
    is_minority = any("minority" in d or "black" in d for d in owner_demos)

    minority_match = any(kw in text for kw in MINORITY_KEYWORDS)
    general_business = any(kw in text for kw in ["small business", "entrepreneur", "startup", "business owner"])

    if minority_match and is_minority:
        score += 25
        reasons.append("minority-specific grant matches owner profile")
    elif general_business:
        score += 15
        reasons.append("general small business grant")
    elif not minority_match:
        score += 10  # Open to everyone
        reasons.append("open eligibility")

    # ── 2. Industry alignment (up to 25 pts) ─────────────────────────────────
    user_industries = [i.lower() for i in profile.get("target_grant_types", [])]
    best_industry_score = 0
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            if any(industry in ui for ui in user_industries):
                best_industry_score = max(best_industry_score, 25)
                reasons.append(f"strong industry match: {industry}")
            else:
                best_industry_score = max(best_industry_score, 10)
    score += best_industry_score

    # ── 3. Amount fit (up to 20 pts) ─────────────────────────────────────────
    amount_max = grant.get("amount_max", 0) or 0
    min_desired = profile.get("min_grant_amount", 5000)

    if amount_max >= 100000:
        score += 20
        reasons.append(f"large grant: ${amount_max:,}")
    elif amount_max >= min_desired:
        score += 15
        reasons.append(f"meets minimum: ${amount_max:,}")
    elif amount_max == 0:
        score += 10  # Unknown amount, don't penalize
    else:
        score += 5
        reasons.append(f"small grant: ${amount_max:,}")

    # ── 4. Deadline urgency / recency (up to 15 pts) ─────────────────────────
    deadline_str = grant.get("deadline")
    if deadline_str:
        try:
            dl = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            days_left = (dl - date.today()).days
            if 7 <= days_left <= 60:
                score += 15
                reasons.append(f"deadline in {days_left} days (sweet spot)")
            elif days_left > 60:
                score += 10
                reasons.append(f"deadline in {days_left} days")
            elif 0 < days_left < 7:
                score += 5
                reasons.append(f"urgent: {days_left} days left")
            else:
                score -= 10  # Expired
                reasons.append("deadline may have passed")
        except ValueError:
            score += 5
    else:
        score += 8  # Rolling deadline likely

    # ── 5. Location fit (up to 15 pts) ───────────────────────────────────────
    user_state = profile.get("location", {}).get("state", "").lower()
    if user_state:
        if user_state in text or "nationwide" in text or "national" in text or "all states" in text:
            score += 15
            reasons.append("location eligible")
        elif "federal" in text or "u.s." in text or "united states" in text:
            score += 12
        else:
            score += 8  # Unknown — don't penalize heavily

    # ── Cap at 100 ────────────────────────────────────────────────────────────
    match_score = min(100, max(0, score))

    # ── Win probability ───────────────────────────────────────────────────────
    # Based on match score + competition signals
    competition_penalty = 0
    federal_grant = grant.get("source", "").startswith("grants.gov")
    if federal_grant:
        competition_penalty = 15  # Federal grants = more competition

    win_prob = max(5, min(90, int(match_score * 0.8) - competition_penalty))

    # ── Effort level ──────────────────────────────────────────────────────────
    effort = "medium"
    days = 5

    if any(sig in text for sig in LOW_EFFORT_SIGNALS):
        effort = "low"
        days = 2
    elif any(sig in text for sig in HIGH_EFFORT_SIGNALS):
        effort = "high"
        days = 14

    # Large federal grants = more effort
    if amount_max > 500000:
        effort = "high"
        days = max(days, 14)
    elif amount_max < 25000:
        effort = min(effort, "medium") if effort != "low" else "low"
        days = min(days, 5)

    max_effort = profile.get("max_effort_days", 7)
    if days > max_effort * 1.5:
        match_score = int(match_score * 0.85)  # Slight penalty for over-effort

    return {
        "match_score": match_score,
        "win_probability": win_prob,
        "effort_level": effort,
        "days_to_apply": days,
        "score_reasons": reasons,
    }


def score_batch(grants: list[dict], profile: dict = None) -> list[dict]:
    """Score a list of grants and return them with scores, sorted by match_score."""
    if profile is None:
        profile = _load_profile()

    scored = []
    for g in grants:
        scores = score_grant(g, profile)
        g.update(scores)
        scored.append(g)

    return sorted(scored, key=lambda x: x["match_score"], reverse=True)
