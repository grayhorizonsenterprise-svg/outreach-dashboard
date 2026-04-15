"""
Grant Agent Watchdog

Keeps the FastAPI server alive at all times.
If it crashes or stops, this restarts it automatically.

Run this script instead of main.py directly for production-style always-on behavior.

Usage:
    python watchdog.py
"""
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime

RESTART_DELAY = 5       # seconds before restart
MAX_RESTARTS = 50       # safety limit per session
LOG_FILE = Path(__file__).parent / "watchdog.log"
SERVER_CMD = [sys.executable, "main.py"]


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run():
    # Change to grant_agent directory
    os.chdir(Path(__file__).parent)

    restarts = 0
    log("=== Grant Agent Watchdog Started ===")

    while restarts < MAX_RESTARTS:
        log(f"Starting Grant Agent (attempt {restarts + 1})...")

        proc = subprocess.Popen(
            SERVER_CMD,
            cwd=str(Path(__file__).parent),
            stdout=None,  # inherit — shows in terminal
            stderr=None,
        )

        log(f"Server running (PID {proc.pid})")

        exit_code = proc.wait()  # blocks until process exits

        if exit_code == 0:
            log("Server exited cleanly. Watchdog stopping.")
            break

        restarts += 1
        log(f"Server crashed (exit {exit_code}). Restarting in {RESTART_DELAY}s... [{restarts}/{MAX_RESTARTS}]")
        time.sleep(RESTART_DELAY)

    if restarts >= MAX_RESTARTS:
        log(f"Max restarts ({MAX_RESTARTS}) reached. Watchdog stopping.")


if __name__ == "__main__":
    run()
