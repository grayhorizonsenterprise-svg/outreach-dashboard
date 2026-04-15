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
    # Copy user_profile.json to /data on first run so it persists
    _profile_src = Path(__file__).parent / "user_profile.json"
    _profile_dst = Path("/data/user_profile.json")
    if _profile_src.exists() and not _profile_dst.exists():
        import shutil
        shutil.copy(_profile_src, _profile_dst)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from api.routes import router
from scheduler.jobs import start_scheduler
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

# Mount API routes
app.include_router(router, prefix="/api")

# Serve dashboard
dashboard_dir = Path(__file__).parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(str(dashboard_dir / "index.html"))


# ─── Startup ──────────────────────────────────────────────────────────────────

def _keep_alive():
    """Ping /health every 10 min so the service never idles."""
    time.sleep(90)  # wait for server to fully start
    import requests as _req
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    port = os.environ.get("PORT", str(settings.port))
    if render_url:
        target = render_url.rstrip("/")
    elif railway_domain:
        target = f"https://{railway_domain.rstrip('/')}"
    else:
        target = f"http://127.0.0.1:{port}"
    print(f"[KeepAlive] Pinging {target}/health every 10 min", flush=True)
    while True:
        try:
            _req.get(f"{target}/health", timeout=10)
        except Exception:
            pass
        time.sleep(600)

threading.Thread(target=_keep_alive, daemon=True).start()


@app.on_event("startup")
async def on_startup():
    import json as _json
    from pathlib import Path as _Path

    # Step 1: DB init — synchronous so /health is ready immediately after
    init_db()

    # Step 2: Seed curated grants so DB is never empty on first deploy
    try:
        from discovery.grants_gov import CURATED_GRANTS
        from database.db import upsert_grant, update_scores
        from scoring.scorer import score_grant
        _pfile = _Path(__file__).parent / "user_profile.json"
        profile = _json.loads(_pfile.read_text()) if _pfile.exists() else {}
        seeded = 0
        for grant in CURATED_GRANTS:
            gid, is_new = upsert_grant(grant)
            scores = score_grant(grant, profile)
            update_scores(gid, scores)
            if is_new:
                seeded += 1
        print(f"[Startup] Seeded {seeded} new curated grants ({len(CURATED_GRANTS)} total in library)")
    except Exception as e:
        print(f"[Startup] Curated grant seeding error (non-fatal): {e}")

    # Step 3: Start cron scheduler — synchronous
    start_scheduler()

    # Step 4: Live scan in background (non-blocking — /health already answering)
    def _initial_scan():
        import time
        time.sleep(3)
        from scheduler.jobs import run_daily_scan
        run_daily_scan()

    threading.Thread(target=_initial_scan, daemon=True).start()
    print("[Startup] Server ready — live scan running in background")

    print(f"\n  API:       http://localhost:{settings.port}/api")
    print(f"  Dashboard: http://localhost:{settings.port}/")
    print(f"  Docs:      http://localhost:{settings.port}/docs")
    print("=" * 50 + "\n")


@app.on_event("shutdown")
async def on_shutdown():
    print("[App] Shutting down...")


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
    )
