"""
Grant Agent System — Main Entry Point

FastAPI application with:
  - REST API routes
  - Background scheduler (daily scans)
  - SQLite database initialization
  - Static dashboard serving
"""
import sys
import os
import threading
import time
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

# On Render, use /data for persistent storage; locally use project dir
if os.environ.get("RENDER"):
    os.environ.setdefault("DB_PATH", "/data/grant_agent.db")
    _profile_src = Path(__file__).parent / "user_profile.json"
    _profile_dst = Path("/data/user_profile.json")
    if _profile_src.exists() and not _profile_dst.exists():
        import shutil
        shutil.copy(_profile_src, _profile_dst)

# Only import what's needed for the server to BIND and serve routes.
# Heavy imports (scheduler, scraper, playwright deps) are deferred to
# the background thread so a broken import can't prevent /health from
# responding within Railway's 30-second healthcheck window.
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from api.routes import router
from config import settings

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Grant Agent System",
    description="Automated grant discovery, scoring, and application generation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /health registered before anything else — always returns 200
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

# API routes
app.include_router(router, prefix="/api")

# Static dashboard
dashboard_dir = Path(__file__).parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(str(dashboard_dir / "index.html"))


# ─── Background init (all heavy I/O, deferred imports) ────────────────────────

def _background_init():
    """
    Runs in a daemon thread after uvicorn starts accepting connections.
    Imports scheduler here so any broken dep (playwright, etc.) only fails
    here — not at module load time, which would prevent /health from binding.
    """
    import json as _json

    # 1. DB init
    try:
        init_db()
        print("[Init] DB ready", flush=True)
    except Exception as e:
        print(f"[Init] init_db error: {e}", flush=True)

    # 2. Seed curated grants
    try:
        from discovery.grants_gov import CURATED_GRANTS
        from database.db import upsert_grant, update_scores
        from scoring.scorer import score_grant
        _pfile = Path(__file__).parent / "user_profile.json"
        profile = _json.loads(_pfile.read_text()) if _pfile.exists() else {}
        seeded = 0
        for grant in CURATED_GRANTS:
            gid, is_new = upsert_grant(grant)
            update_scores(gid, score_grant(grant, profile))
            if is_new:
                seeded += 1
        print(f"[Init] Seeded {seeded} new curated grants ({len(CURATED_GRANTS)} total)", flush=True)
    except Exception as e:
        print(f"[Init] Seed error (non-fatal): {e}", flush=True)

    # 3. Start scheduler (imports scraper/jobs here, not at module load)
    try:
        from scheduler.jobs import start_scheduler
        start_scheduler()
        print("[Init] Scheduler started", flush=True)
    except Exception as e:
        print(f"[Init] Scheduler error (non-fatal): {e}", flush=True)

    # 4. Initial live scan
    try:
        from scheduler.jobs import run_daily_scan
        print("[Init] Running initial live grant scan...", flush=True)
        run_daily_scan()
    except Exception as e:
        print(f"[Init] Initial scan error (non-fatal): {e}", flush=True)

    print("[Init] Background init complete", flush=True)


def _keep_alive():
    """Ping /health every 10 min to prevent Railway from idling the service."""
    time.sleep(120)
    import requests as _req
    port = os.environ.get("PORT", str(settings.port))
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if railway_domain:
        target = f"https://{railway_domain.rstrip('/')}"
    elif render_url:
        target = render_url.rstrip("/")
    else:
        target = f"http://127.0.0.1:{port}"
    print(f"[KeepAlive] Pinging {target}/health every 10 min", flush=True)
    while True:
        try:
            _req.get(f"{target}/health", timeout=10)
        except Exception:
            pass
        time.sleep(600)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    # Returns in <1ms — uvicorn starts accepting /health immediately
    threading.Thread(target=_background_init, daemon=True).start()
    threading.Thread(target=_keep_alive, daemon=True).start()
    print("[Startup] Server ready — background init running", flush=True)


@app.on_event("shutdown")
async def on_shutdown():
    print("[App] Shutting down...")


# ─── Local dev ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
    )
