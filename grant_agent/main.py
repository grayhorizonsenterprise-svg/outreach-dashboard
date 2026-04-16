"""
Grant Agent System — Main Entry Point
"""
from __future__ import annotations

import sys
import os
import threading
import time
from pathlib import Path

# Log Python version immediately so it appears in Railway Deploy Logs
print(f"=== GRANT AGENT STARTING === Python {sys.version}", flush=True)

sys.path.insert(0, str(Path(__file__).parent))

if os.environ.get("RENDER"):
    os.environ.setdefault("DB_PATH", "/data/grant_agent.db")
    _profile_src = Path(__file__).parent / "user_profile.json"
    _profile_dst = Path("/data/user_profile.json")
    if _profile_src.exists() and not _profile_dst.exists():
        import shutil
        shutil.copy(_profile_src, _profile_dst)

# ─── Core app (no optional imports yet) ──────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

print("[Boot] FastAPI imported OK", flush=True)

try:
    from config import settings
    _PORT = settings.port
    print("[Boot] Config loaded OK", flush=True)
except Exception as _e:
    print(f"[Boot] Config error: {_e} — using defaults", flush=True)
    _PORT = int(os.environ.get("PORT", 8000))

    class _Settings:
        port = _PORT
        env = "production"
        scan_hour = 6
        scan_minute = 0
    settings = _Settings()

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

# /health is registered FIRST and depends on NOTHING else
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

print("[Boot] /health endpoint registered", flush=True)

# ─── Optional: API routes (non-fatal if broken) ───────────────────────────────

try:
    from api.routes import router
    app.include_router(router, prefix="/api")
    print("[Boot] API routes loaded OK", flush=True)
except Exception as _e:
    import traceback
    print(f"[Boot] ERROR loading API routes: {_e}", flush=True)
    traceback.print_exc()

# ─── Optional: Static dashboard ───────────────────────────────────────────────

try:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    dashboard_dir = Path(__file__).parent / "dashboard"
    if dashboard_dir.exists():
        app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

        @app.get("/")
        def serve_dashboard():
            return FileResponse(str(dashboard_dir / "index.html"))

        print("[Boot] Dashboard mounted OK", flush=True)
except Exception as _e:
    print(f"[Boot] Dashboard mount error (non-fatal): {_e}", flush=True)

print("[Boot] App object ready — waiting for uvicorn startup event", flush=True)


# ─── Background init ──────────────────────────────────────────────────────────

def _background_init():
    """All heavy I/O + deferred imports run here after uvicorn starts."""
    import json as _json

    print("[Init] Background thread started", flush=True)

    try:
        from database.db import init_db
        init_db()
        print("[Init] DB ready", flush=True)
    except Exception as e:
        print(f"[Init] init_db error: {e}", flush=True)

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

    try:
        from scheduler.jobs import start_scheduler
        start_scheduler()
        print("[Init] Scheduler started", flush=True)
    except Exception as e:
        print(f"[Init] Scheduler error (non-fatal): {e}", flush=True)

    try:
        from scheduler.jobs import run_daily_scan
        print("[Init] Running initial grant scan...", flush=True)
        run_daily_scan()
    except Exception as e:
        print(f"[Init] Initial scan error (non-fatal): {e}", flush=True)

    print("[Init] Background init complete", flush=True)


def _keep_alive():
    time.sleep(120)
    import requests as _req
    port = os.environ.get("PORT", str(_PORT))
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
    print("[Startup] on_startup called — launching background threads", flush=True)
    threading.Thread(target=_background_init, daemon=True).start()
    threading.Thread(target=_keep_alive, daemon=True).start()
    print("[Startup] Background threads started — server ready", flush=True)


@app.on_event("shutdown")
async def on_shutdown():
    print("[App] Shutting down...")


# ─── Local dev ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=_PORT,
                reload=settings.env == "development")
