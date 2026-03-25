"""
watchdog.py — Gray Horizons Enterprise
Monitors the dashboard 24/7. If it crashes, restarts it automatically.
Logs every event. Never stops — even if the watchdog itself hits an error.

Run once: python watchdog.py
It registers itself in Windows Startup and then loops forever.
"""

import subprocess
import time
import os
import sys
import logging
import socket

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
WORK_DIR       = os.path.dirname(os.path.abspath(__file__))
PYTHON         = sys.executable
DASHBOARD      = os.path.join(WORK_DIR, "approval_dashboard.py")
HEALTH_URL     = "http://127.0.0.1:8080/health"
CHECK_INTERVAL = 60       # seconds between health checks
FAIL_THRESHOLD = 3        # consecutive failures before restart
RESTART_WAIT   = 8        # seconds to wait after kill before restarting
LOG_FILE       = os.path.join(WORK_DIR, "watchdog.log")

# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("watchdog")


# ─────────────────────────────────────────
# SELF-REGISTER IN WINDOWS STARTUP
# So the watchdog itself starts on every login
# ─────────────────────────────────────────
def register_startup():
    try:
        startup = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        vbs_path = os.path.join(startup, "GHEWatchdog.vbs")
        vbs = (
            'Set WshShell = CreateObject("WScript.Shell")\r\n'
            f'WshShell.Run "{PYTHON} ""{DASHBOARD}""", 0, False\r\n'
            'WScript.Sleep 8000\r\n'
            f'WshShell.Run "{PYTHON} ""{os.path.abspath(__file__)}""", 0, False\r\n'
        )
        with open(vbs_path, "w") as f:
            f.write(vbs)
        log.info(f"Startup entry written to {vbs_path}")
    except Exception as e:
        log.warning(f"Could not write startup entry: {e}")


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
def is_alive() -> bool:
    """Returns True if the dashboard is responding."""
    try:
        # Use socket directly — no third-party dependency needed here
        sock = socket.create_connection(("127.0.0.1", 8080), timeout=5)
        sock.send(b"GET /health HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
        response = sock.recv(256).decode("utf-8", errors="ignore")
        sock.close()
        return "200" in response
    except Exception:
        return False


# ─────────────────────────────────────────
# PROCESS CONTROL
# ─────────────────────────────────────────
def kill_dashboard():
    """Kill all Python processes (dashboard + pipeline threads)."""
    try:
        subprocess.run(
            ["powershell.exe", "-Command",
             "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"],
            capture_output=True, timeout=15
        )
        log.info("Killed existing Python processes")
    except Exception as e:
        log.warning(f"Kill failed (non-critical): {e}")


def start_dashboard():
    """Launch the dashboard as a detached background process."""
    try:
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [PYTHON, DASHBOARD],
            cwd=WORK_DIR,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Dashboard started")
    except Exception as e:
        log.error(f"Failed to start dashboard: {e}")


def wait_for_startup(timeout: int = 30) -> bool:
    """Wait until the dashboard responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_alive():
            return True
        time.sleep(2)
    return False


# ─────────────────────────────────────────
# MAIN WATCHDOG LOOP
# ─────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("GHE Watchdog started")
    log.info(f"Monitoring: {HEALTH_URL}")
    log.info(f"Check interval: {CHECK_INTERVAL}s  |  Fail threshold: {FAIL_THRESHOLD}")
    log.info("=" * 50)

    register_startup()

    # Make sure the dashboard is running right now
    if not is_alive():
        log.info("Dashboard not running on startup — launching now")
        start_dashboard()
        if wait_for_startup(30):
            log.info("Dashboard is up")
        else:
            log.warning("Dashboard did not respond within 30s — will retry on next check")

    consecutive_failures = 0
    restart_count = 0

    while True:
        try:
            time.sleep(CHECK_INTERVAL)

            if is_alive():
                consecutive_failures = 0
                # Log a heartbeat every 10 successful checks (~10 min)
            else:
                consecutive_failures += 1
                log.warning(f"Health check failed ({consecutive_failures}/{FAIL_THRESHOLD})")

                if consecutive_failures >= FAIL_THRESHOLD:
                    restart_count += 1
                    log.error(f"Dashboard is down — restarting (restart #{restart_count})")

                    kill_dashboard()
                    time.sleep(RESTART_WAIT)
                    start_dashboard()

                    if wait_for_startup(30):
                        log.info(f"Dashboard recovered after restart #{restart_count}")
                        consecutive_failures = 0
                    else:
                        log.error("Dashboard still not responding after restart — will try again")

        except KeyboardInterrupt:
            log.info("Watchdog stopped by user")
            break
        except Exception as e:
            # Never let the watchdog crash — log and keep going
            log.error(f"Watchdog loop error (non-fatal): {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
