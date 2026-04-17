"""
FastAPI Routes

Endpoints:
  GET  /grants                    - List grants (filtered, ranked)
  GET  /grants/{id}               - Single grant detail
  POST /search                    - On-demand search (keyword)
  POST /scan                      - Trigger manual scan
  POST /grants/{id}/apply         - Generate application (Claude only)
  POST /grants/{id}/dual-apply    - Generate application (Claude + GPT-4o + synthesis)
  POST /grants/{id}/checklist     - Get step-by-step application guide
  POST /grants/{id}/submit        - Attempt auto-submission

  GET  /applications              - List all applications with grant info
  GET  /applications/{id}         - Single application detail
  PATCH /applications/{id}/status - Update application status

  GET  /profile                   - View business profile
  PUT  /profile                   - Update business profile
  GET  /stats                     - Dashboard stats (grants + applications)
"""
import json
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from database.db import (
    get_grants, get_grant_by_id, upsert_grant,
    update_scores, save_application, log_scan,
    get_application, get_applications, update_application_status,
    get_application_stats,
)
from discovery.grants_gov import search as ggov_search, bulk_scan as ggov_bulk
from discovery.rss_feeds import fetch_all as rss_fetch
from scoring.scorer import score_grant, score_batch
from generation.generator import generate_application, generate_dual_application, generate_checklist

router = APIRouter()

PROFILE_PATH = Path(__file__).parent.parent / "user_profile.json"


def _load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text())
    return {}


# ─── Models ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    keyword: str = ""
    min_score: int = 0
    limit: int = 25


class ProfileUpdate(BaseModel):
    data: dict


class StatusUpdate(BaseModel):
    status: str
    notes: str = ""


# ─── Grants ───────────────────────────────────────────────────────────────────

@router.get("/grants")
def list_grants(
    min_score: int = Query(0, ge=0, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    track: Optional[str] = None,   # apply_now | avoid | review
    limit: int = Query(50, le=200),
):
    """Return ranked grant list from DB, optionally filtered by track."""
    from scoring.scorer import classify_track
    grants = get_grants(min_score=min_score, status=status, limit=limit, search=search)

    # Attach track to any grant missing it, then filter
    for g in grants:
        if not g.get("track"):
            g["track"] = classify_track(g)

    if track:
        grants = [g for g in grants if g.get("track") == track]

    # Summary counts for UI
    counts = {"apply_now": 0, "avoid": 0, "review": 0}
    for g in grants:
        t = g.get("track", "review")
        counts[t] = counts.get(t, 0) + 1

    return {"grants": grants, "count": len(grants), "track_counts": counts}


@router.get("/grants/{grant_id}")
def get_grant(grant_id: int):
    """Get single grant by ID."""
    grant = get_grant_by_id(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    return grant


@router.post("/search")
def on_demand_search(body: SearchRequest):
    """
    Live search — hits Grants.gov API in real time, scores results, returns immediately.
    Does NOT save to DB (use /scan to persist).
    """
    profile = _load_profile()
    raw_grants = ggov_search(keyword=body.keyword, rows=body.limit)

    if not raw_grants:
        return {"grants": [], "count": 0, "source": "grants.gov"}

    scored = score_batch(raw_grants, profile)
    filtered = [g for g in scored if g["match_score"] >= body.min_score]

    return {
        "grants": filtered,
        "count": len(filtered),
        "source": "grants.gov",
        "keyword": body.keyword,
    }


@router.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks, deep: bool = False):
    """Trigger a manual scan in the background."""
    from scheduler.jobs import run_daily_scan, run_deep_scan

    if deep:
        background_tasks.add_task(run_deep_scan)
        return {"status": "deep scan started", "message": "Playwright scan running in background"}
    else:
        background_tasks.add_task(run_daily_scan)
        return {"status": "scan started", "message": "Daily scan running in background"}


# ─── Application generation ───────────────────────────────────────────────────

@router.post("/grants/{grant_id}/apply")
def generate_apply(grant_id: int):
    """
    Generate a complete grant application using Claude only.
    Returns all sections + saves to DB with status=draft.
    """
    grant = get_grant_by_id(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")

    profile = _load_profile()
    application = generate_application(grant, profile)
    app_id = save_application(grant_id, application)

    return {
        "application_id": app_id,
        "grant_id": grant_id,
        "grant_name": grant.get("name"),
        "ai_mode": "claude",
        **application,
    }


@router.post("/grants/{grant_id}/dual-apply")
def generate_dual_apply(grant_id: int):
    """
    Generate a grant application using both Claude AND GPT-4o, then synthesize.

    Returns:
      - Synthesized best-of-both sections (main application)
      - claude_text, openai_text, synthesized_text (full narratives)
      - claude_sections, openai_sections (per-model section breakdown)
      - application_id saved to DB
    """
    grant = get_grant_by_id(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")

    profile = _load_profile()
    application = generate_dual_application(grant, profile)
    app_id = save_application(grant_id, application)

    return {
        "application_id": app_id,
        "grant_id": grant_id,
        "grant_name": grant.get("name"),
        "status": "draft",
        **application,
    }


@router.post("/grants/{grant_id}/checklist")
def get_checklist(grant_id: int):
    """Generate a step-by-step application checklist."""
    grant = get_grant_by_id(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")

    checklist = generate_checklist(grant)
    return {"grant_id": grant_id, "grant_name": grant.get("name"), "checklist": checklist}


@router.post("/grants/{grant_id}/submit")
def attempt_submit(grant_id: int):
    """Attempt to auto-fill the grant application form."""
    grant = get_grant_by_id(grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")

    from automation.submitter import prepare_submission

    profile = _load_profile()
    application = generate_application(grant, profile)
    result = prepare_submission(grant, application, profile)

    return {"grant_id": grant_id, "grant_name": grant.get("name"), **result}


# ─── Applications (tracker) ───────────────────────────────────────────────────

@router.get("/applications")
def list_applications(
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
):
    """List all generated applications with grant info, newest first."""
    apps = get_applications(status=status, limit=limit)
    return {"applications": apps, "count": len(apps)}


@router.get("/applications/{app_id}")
def get_single_application(app_id: int):
    """Get a single application with full detail."""
    app = get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/applications/{app_id}/status")
def update_status(app_id: int, body: StatusUpdate):
    """
    Update application status.
    Valid statuses: draft | submitted | under_review | awarded | rejected
    """
    VALID = {"draft", "submitted", "under_review", "awarded", "rejected"}
    if body.status not in VALID:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID)}")

    ok = update_application_status(app_id, body.status, body.notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")

    return {"application_id": app_id, "status": body.status, "notes": body.notes}


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.get("/profile")
def get_profile():
    """Return current user profile."""
    return _load_profile()


@router.put("/profile")
def update_profile(body: ProfileUpdate):
    """Update user profile."""
    current = _load_profile()
    current.update(body.data)
    PROFILE_PATH.write_text(json.dumps(current, indent=2))
    return {"status": "updated", "profile": current}


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats():
    """Dashboard stats — grants + application pipeline."""
    import sqlite3
    from database.db import DB_PATH

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    total        = conn.execute("SELECT COUNT(*) as c FROM grants").fetchone()["c"]
    high_match   = conn.execute("SELECT COUNT(*) as c FROM grants WHERE match_score >= 70").fetchone()["c"]
    apps_total   = conn.execute("SELECT COUNT(*) as c FROM applications").fetchone()["c"]
    awarded      = conn.execute("SELECT COUNT(*) as c FROM applications WHERE status='awarded'").fetchone()["c"]
    submitted    = conn.execute("SELECT COUNT(*) as c FROM applications WHERE status IN ('submitted','under_review')").fetchone()["c"]

    # Total potential value in pipeline (submitted + under review)
    pipeline_val = conn.execute("""
        SELECT COALESCE(SUM(g.amount_max),0) as v
        FROM applications a
        LEFT JOIN grants g ON g.id=a.grant_id
        WHERE a.status IN ('submitted','under_review')
    """).fetchone()["v"]

    awarded_val = conn.execute("""
        SELECT COALESCE(SUM(g.amount_max),0) as v
        FROM applications a
        LEFT JOIN grants g ON g.id=a.grant_id
        WHERE a.status='awarded'
    """).fetchone()["v"]

    recent_scans = conn.execute(
        "SELECT * FROM scan_log ORDER BY scanned_at DESC LIMIT 5"
    ).fetchall()

    top_grants = conn.execute(
        "SELECT id, name, match_score, win_probability, amount_max, deadline FROM grants ORDER BY match_score DESC LIMIT 5"
    ).fetchall()

    # Per-status application counts
    status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
    ).fetchall()
    app_by_status = {r["status"]: r["cnt"] for r in status_rows}

    conn.close()

    return {
        "total_grants":        total,
        "high_match_grants":   high_match,
        "applications_generated": apps_total,
        "awarded_count":       awarded,
        "in_pipeline":         submitted,
        "pipeline_value":      pipeline_val,
        "awarded_value":       awarded_val,
        "app_by_status":       app_by_status,
        "recent_scans":        [dict(r) for r in recent_scans],
        "top_grants":          [dict(r) for r in top_grants],
    }
