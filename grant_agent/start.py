"""
Entrypoint for Railway / production deployment.
Reads PORT directly from environment — no shell variable expansion needed.
"""
import os
import sys
from pathlib import Path

# Print early so Deploy Logs immediately confirm the process started
port = int(os.environ.get("PORT", 8000))
print(f"=== start.py: launching uvicorn on port {port} ===", flush=True)
print(f"Python {sys.version}", flush=True)
print(f"Working dir: {Path.cwd()}", flush=True)

import uvicorn

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    access_log=False,
)
