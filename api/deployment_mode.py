"""Deployment mode — controls write access and surface area.

Four operating modes. Same code, different access envelope.

  open        Full functionality. Default for development and public instances.
  restricted  Writes require a physical token file at CONCORDANCE_TOKEN_PATH.
              Reads remain open. The token file represents the physical key —
              microSD token, USB dongle, or any mounted file the operator
              controls. Remove the file (eject the drive) to lock writes.
  lockdown    Read-only. All POST/PUT/PATCH/DELETE return 423.
              For mesh nodes with limited resources or hostile environments.
  quantum     Reserved. Currently equivalent to restricted.

Environment variables:
  CONCORDANCE_MODE        open | restricted | lockdown | quantum  (default: open)
  CONCORDANCE_TOKEN_PATH  Path to the physical token file
                          (default: ~/.concordance/physical_token.key)

The mode check runs as FastAPI middleware so every write endpoint is
covered without per-endpoint decoration. Read endpoints are never blocked.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

VALID_MODES = frozenset({"open", "restricted", "lockdown", "quantum"})

_MODE_ENV_KEY  = "CONCORDANCE_MODE"
_TOKEN_ENV_KEY = "CONCORDANCE_TOKEN_PATH"
_DEFAULT_TOKEN = Path("~/.concordance/physical_token.key").expanduser()

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Endpoints exempt from mode gate even in lockdown:
# none — in lockdown every write is blocked.


def get_mode() -> str:
    """Return the current deployment mode (always a valid member of VALID_MODES)."""
    raw = os.environ.get(_MODE_ENV_KEY, "open").strip().lower()
    return raw if raw in VALID_MODES else "open"


def _token_path() -> Path:
    raw = os.environ.get(_TOKEN_ENV_KEY, "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_TOKEN


def token_present() -> bool:
    """Physical token check — token file must exist and be non-empty."""
    try:
        p = _token_path()
        return p.exists() and p.stat().st_size > 0
    except OSError:
        return False


def writes_allowed() -> bool:
    """True when write operations are permitted under the current mode."""
    mode = get_mode()
    if mode == "open":
        return True
    if mode == "lockdown":
        return False
    # restricted / quantum: token must be present
    return token_present()


def mode_info() -> Dict[str, Any]:
    """Return a dict describing the current mode — surfaced at GET /mode."""
    mode = get_mode()
    token_path = _token_path()
    present = token_present() if mode in {"restricted", "quantum"} else None
    return {
        "mode": mode,
        "writes_enabled": writes_allowed(),
        "token_path": str(token_path),
        "token_present": present,
        "description": {
            "open":       "Full functionality — all endpoints available",
            "restricted": "Writes require physical token at token_path",
            "lockdown":   "Read-only — all write endpoints return 423 Locked",
            "quantum":    "Reserved — currently equivalent to restricted",
        }.get(mode, "unknown"),
    }


async def mode_gate_middleware(request, call_next):
    """ASGI middleware: enforce deployment mode on all write requests.

    Checks run before any auth or handler logic — if the mode says no,
    nothing further executes for that request.
    """
    if request.method in _WRITE_METHODS:
        mode = get_mode()
        if mode == "lockdown":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=423,
                content={
                    "detail": "Instance is in lockdown mode — write operations are disabled. "
                              "Read-only endpoints remain available.",
                    "mode": "lockdown",
                },
            )
        if mode in {"restricted", "quantum"}:
            if not token_present():
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=423,
                    content={
                        "detail": (
                            f"Instance is in {mode} mode — physical token required. "
                            f"Place a non-empty key file at {_token_path()} to enable writes."
                        ),
                        "mode": mode,
                        "token_path": str(_token_path()),
                    },
                )
    return await call_next(request)
