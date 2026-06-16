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

# Canonical-substrate write paths. In restricted/quantum mode THESE require the
# physical token (the operator's key); everything else -- public verify,
# generation, the agent (/robot/*) endpoints, user activity -- stays OPEN so the
# engine keeps serving people and agents (a public engine must accept verify
# POSTs). This is "own our writes" for a public instance: the canonical truth
# substrate can only be mutated with the key in hand; the public service is not.
#
# FAIL-OPEN for unlisted paths: forgetting to list a write here leaves it at
# today's ungated behaviour -- it never breaks a public flow. Tighten over time.
# (Lockdown still blocks ALL writes -- that mode is for read-only mesh nodes.)
_GUARDED_PREFIXES = ("/seal",)   # /seal, /seal/polymathic, /seal/render -- minting seals
_GUARDED_EXACT = frozenset({
    "/cas",               # content-addressable store write
    "/chain/receive",     # federation ingest into the append-only ledger
    "/receipts/promote",  # promotion to canonical receipts
    "/packets/import",    # bulk import into the substrate
    "/grid/axis/add",     # mutating the coordinate map
    "/grid/axis/remove",
})


def is_guarded_path(path: str) -> bool:
    """True if `path` mutates the canonical substrate (so it needs the physical
    key in restricted/quantum mode). Public verify/read/agent paths are NOT
    guarded and pass freely."""
    p = (path or "").rstrip("/") or "/"
    if p in _GUARDED_EXACT:
        return True
    return any(p == pre or p.startswith(pre + "/") for pre in _GUARDED_PREFIXES)


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
    guarded = mode in {"restricted", "quantum"}
    present = token_present() if guarded else None
    return {
        "mode": mode,
        "writes_enabled": writes_allowed(),
        "substrate_writes_enabled": (token_present() if guarded
                                     else (mode == "open")),
        "token_path": str(token_path),
        "token_present": present,
        "guarded_paths": (sorted(_GUARDED_EXACT) + [p + "/*" for p in _GUARDED_PREFIXES]
                          if guarded else None),
        "description": {
            "open":       "Full functionality — all endpoints available",
            "restricted": "Canonical-substrate writes require the physical token; "
                          "public verify / read / agent endpoints stay open",
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
            # Only canonical-substrate writes need the key; public/agent writes pass.
            if is_guarded_path(request.url.path) and not token_present():
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=423,
                    content={
                        "detail": (
                            f"Instance is in {mode} mode — this writes to the canonical "
                            f"substrate, which requires the physical token. Mount the key "
                            f"file at {_token_path()} to enable. Public verify / read / agent "
                            f"endpoints remain open."
                        ),
                        "mode": mode,
                        "guarded_path": request.url.path,
                        "token_path": str(_token_path()),
                    },
                )
    return await call_next(request)
