"""
start_edge.py — Edge Engine dashboard (outreach-dashboard Railway service)
"""
import os
import subprocess
import sys

port = os.environ.get("PORT", "5050")
print(f"[start_edge.py] Starting Edge Engine on port {port}", flush=True)

subprocess.run([
    sys.executable, "-m", "gunicorn",
    "dashboard:app",
    "--bind", f"0.0.0.0:{port}",
    "--workers", "1",
    "--threads", "4",
    "--timeout", "120",
    "--keep-alive", "5",
    "--log-level", "info",
], cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_engine"))
