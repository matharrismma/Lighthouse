#!/usr/bin/env python3
"""engine_watchdog.py — keeps the Concordance engine alive.

Polls http://localhost:8000/health every POLL_INTERVAL seconds.
After FAILURE_THRESHOLD consecutive failures, runs the restart script.
Honors RESTART_COOLDOWN so a flapping engine doesn't get restart-stormed.

Designed to run as a Windows Scheduled Task at startup, elevated
(the engine needs elevation; this watchdog must be able to launch
an elevated process).

Configuration (environment variables, with defaults):
    NH_HEALTH_URL          default: http://localhost:8000/health
    NH_POLL_INTERVAL       default: 30           (seconds between checks)
    NH_FAILURE_THRESHOLD   default: 3            (consecutive failures before restart)
    NH_RESTART_COOLDOWN    default: 300          (seconds between restart attempts)
    NH_RESTART_SCRIPT      default: ~/OneDrive/Desktop/Restart_Concordance_Server.ps1
    NH_LOG_DIR             default: <repo>/logs

Logs to <NH_LOG_DIR>/watchdog.log with rotation at 5 MB.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────
HEALTH_URL = os.environ.get("NH_HEALTH_URL", "http://localhost:8000/health")
POLL_INTERVAL = int(os.environ.get("NH_POLL_INTERVAL", "30"))
FAILURE_THRESHOLD = int(os.environ.get("NH_FAILURE_THRESHOLD", "3"))
RESTART_COOLDOWN = int(os.environ.get("NH_RESTART_COOLDOWN", "300"))
RESTART_SCRIPT = os.environ.get(
    "NH_RESTART_SCRIPT",
    str(Path.home() / "OneDrive" / "Desktop" / "Restart_Concordance_Server.ps1"),
)
LOG_DIR = Path(
    os.environ.get("NH_LOG_DIR", str(Path(__file__).resolve().parent.parent / "logs"))
)
LOG_FILE = LOG_DIR / "watchdog.log"
HEALTH_TIMEOUT = 10  # seconds per probe


# ── Logging setup ──────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.watchdog")
    logger.setLevel(logging.INFO)
    # Rotate at 5 MB, keep 5 files
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)
    # Also stream to stdout (Scheduled Task captures it)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(sh)
    return logger


log = _setup_logging()


# ── Probes + actions ──────────────────────────────────────────────
def check_health() -> bool:
    """Return True if /health responds 200 within HEALTH_TIMEOUT seconds."""
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "nh-watchdog/1"})
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as r:
            return r.status == 200
    except Exception as e:
        log.debug("health check failed: %s", e)
        return False


def restart_engine() -> bool:
    """Invoke the PowerShell restart script. Return True on clean exit."""
    if not Path(RESTART_SCRIPT).exists():
        log.error("restart script missing at %s; cannot recover", RESTART_SCRIPT)
        return False
    log.warning("triggering restart via %s", RESTART_SCRIPT)
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                RESTART_SCRIPT,
            ],
            timeout=180,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log.info("restart script completed cleanly")
            return True
        log.error(
            "restart script returned %s; stderr: %s",
            result.returncode,
            (result.stderr or "").strip()[:500],
        )
        return False
    except subprocess.TimeoutExpired:
        log.error("restart script timed out after 180s")
        return False
    except Exception as e:
        log.exception("restart script raised: %s", e)
        return False


# ── Main loop ──────────────────────────────────────────────────────
def main() -> int:
    log.info(
        "watchdog started · polling=%s every=%ds threshold=%d cooldown=%ds script=%s",
        HEALTH_URL,
        POLL_INTERVAL,
        FAILURE_THRESHOLD,
        RESTART_COOLDOWN,
        RESTART_SCRIPT,
    )
    consecutive_failures = 0
    last_restart_ts = 0.0
    last_state_alive: bool | None = None  # None = unknown, True/False = previous state

    while True:
        ok = check_health()

        # State-change logging (don't spam logs every 30s when healthy)
        if last_state_alive is None or ok != last_state_alive:
            if ok:
                if last_state_alive is False:
                    log.info("engine recovered (was down %d cycles)", consecutive_failures)
                else:
                    log.info("engine alive")
            else:
                log.info("engine unresponsive")
            last_state_alive = ok

        if ok:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            log.info("health fail #%d/%d", consecutive_failures, FAILURE_THRESHOLD)

            if consecutive_failures >= FAILURE_THRESHOLD:
                now = time.time()
                since_last = now - last_restart_ts
                if since_last < RESTART_COOLDOWN:
                    log.warning(
                        "restart cooldown active (%ds remain); continuing to poll",
                        int(RESTART_COOLDOWN - since_last),
                    )
                else:
                    ok_restart = restart_engine()
                    last_restart_ts = time.time()
                    # Either way, reset counter and give the engine breathing room
                    consecutive_failures = 0
                    last_state_alive = None  # force a fresh state log next cycle
                    log.info(
                        "post-restart wait 60s before next probe (restart %s)",
                        "succeeded" if ok_restart else "FAILED",
                    )
                    time.sleep(60)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("watchdog stopped by user")
        sys.exit(0)
