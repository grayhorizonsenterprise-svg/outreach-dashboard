"""
start.py — Gray Horizons Dashboard
Reads PORT from environment directly — bypasses Railway shell expansion issues.
"""
import os
import subprocess
import sys

port = os.environ.get("PORT", "8080")

print(f"[start.py] Starting gunicorn on port {port}", flush=True)

subprocess.run([
    sys.executable, "-m", "gunicorn",
    "approval_dashboard:app",
    "--bind", f"0.0.0.0:{port}",
    "--workers", "1",
    "--threads", "2",
    "--timeout", "120",
    "--keep-alive", "10",
    "--log-level", "info",
])
