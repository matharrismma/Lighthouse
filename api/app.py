"""
Concordance Wisdom Engine — FastAPI server.

Endpoints:
  POST /validate          Submit a packet for validation. Result is written to ledger.
  GET  /ledger            Recent ledger entries (newest first).
  GET  /ledger/{id}       All ledger entries for a specific packet_id.
  GET  /ledger/verify     Verify the full hash chain (tamper detection).
  GET  /health            Liveness check.
  GET  /                  API info.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# -- Engine import -------------------------------------------------------
# The concordance-engine package is installed from pyproject.toml at repo root.
# CONCORDANCE_ENGINE_PATH env var can also point to a local src/ tree as fallback.
_engine_path = os.environ.get("CONCORDANCE_ENGINE_PATH")
if _engine_path:
    sys.path.insert(0, str(Path(_engine_path) / "src"))

try:
    from concordance_engine.engine import validate_packet, EngineConfig
    from concordance_engine.validate import compute_packet_hash
    _ENGINE_AVAILABLE = True
    _ENGINE_ERROR = None
except ImportError as _e:
    _ENGINE_AVAILABLE = False
    _ENGINE_ERROR = str(_e)

# -- Ledger import -------------------------------------------------------
from api.ledger import get_ledger

# -- App setup -----------------------------------------------------------
app = FastAPI(
    title="Concordance",
    description="""
A deterministic verification and decision-recording engine for AI agents.

## When to use this API

Call before:
- Stating a chemical equation, physics relationship, or mathematical result as verified fact
- Committing funds, resources, or authority on behalf of an organization
- Recording any decision that cannot be reversed without significant cost

Do NOT call for conversation, analysis, or any reversible action.

## Four Gates

Every packet passes through these gates in order. First failure stops the chain:

- **RED** — Rejects coercion, unilateral authority, rights violations
- **FLOOR** — Rejects structurally incomplete or internally inconsistent packets
- **BROTHERS** — Quarantines if fewer than 2 witnesses or review window not elapsed
- **GOD** — Records permanently if all prior gates pass

## Agent entry points

- `POST /submit` — unauthenticated submission (use this for agents)
- `POST /validate` — authenticated submission (requires X-Api-Key header)
- `GET /ledger` — permanent verification record (newest first)
- `GET /ledger/verify` — SHA-256 chain integrity check
- `GET /llms.txt` — full tool inventory, packet schema, and examples

## Minimum viable packet

```json
{
  "domain": "governance",
  "witness_count": 2,
  "created_epoch": 1700000000,
  "DECISION_PACKET": {
    "title": "Short label",
    "decision": "The exact action being taken",
    "rationale": "Why this decision is being made",
    "scope": "adapter",
    "red_items": ["No coercion applied", "Acting within authorized role"],
    "floor_items": ["All required parties informed"],
    "way_path": "standard",
    "execution_steps": ["Step 1"],
    "witnesses": ["Alice Johnson", "Bob Smith"],
    "witness_count": 2
  }
}
```

scope: adapter (individual) | local (team) | mesh (cross-team) | canon (org-wide) | kernel (core policy)

On REJECT: read gate_results[i].reasons for the first failed gate and fix those fields.
On QUARANTINE: add witnesses or allow more time, then resubmit.

Source: https://github.com/matharrismma/Lighthouse — Apache 2.0
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# -- Optional API key auth -----------------------------------------------
_API_KEY = os.environ.get("API_KEY", "")

def _check_api_key(x_api_key: str = Header(default="")) -> None:
    """Reject requests that don't carry the correct API key.
    If API_KEY env var is not set, auth is disabled (dev mode).
    """
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# -- Schema discovery ----------------------------------------------------
_SCHEMA_PATH_ENV = os.environ.get("CONCORDANCE_SCHEMA_PATH")
_SCHEMA_PATH: Optional[Path] = None
if _SCHEMA_PATH_ENV:
    _SCHEMA_PATH = Path(_SCHEMA_PATH_ENV)
else:
    # Default: schema/ at repo root (works in Docker)
    candidate = Path(__file__).parent.parent / "schema" / "packet.schema.json"
    if candidate.exists():
        _SCHEMA_PATH = candidate


def _make_config() -> "EngineConfig":
    schema = str(_SCHEMA_PATH) if _SCHEMA_PATH and _SCHEMA_PATH.exists() else ""
    return EngineConfig(schema_path=schema, run_verifiers=True)


# -- Request / Response models -------------------------------------------
class ValidateRequest(BaseModel):
    packet: Dict[str, Any]
    now_epoch: Optional[int] = None
    run_verifiers: bool = True


class GateResultOut(BaseModel):
    gate: str
    status: str
    reasons: List[str]
    details: Optional[Dict[str, Any]] = None


class ValidateResponse(BaseModel):
    overall: str
    gate_results: List[GateResultOut]
    ledger_seq: Optional[int] = None
    ledger_entry_hash: Optional[str] = None
    packet_hash: str
    elapsed_ms: float


class LedgerEntryOut(BaseModel):
    seq: int
    timestamp_iso: str
    timestamp_epoch: int
    packet_id: str
    domain: str
    overall: str
    gate_summary: Dict[str, str]
    top_reasons: List[str]
    packet_hash: str
    prev_hash: str
    entry_hash: str


class LedgerListResponse(BaseModel):
    entries: List[LedgerEntryOut]
    count: int


class ChainVerifyResponse(BaseModel):
    valid: bool
    entries_checked: int
    first_broken_seq: Optional[int]
    message: str


# -- Routes --------------------------------------------------------------

@app.get("/llms.txt", include_in_schema=False)
def llms_txt():
    """AI-readable service description for agent discovery (llms.txt standard)."""
    f = Path(__file__).parent.parent / "site" / "llms.txt"
    if f.exists():
        return FileResponse(str(f), media_type="text/plain")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("llms.txt not found", status_code=404)


@app.get("/", include_in_schema=False)
def root():
    index = Path(__file__).parent.parent / "site" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "name": "Concordance Engine API",
        "version": "1.0.0",
        "engine_available": _ENGINE_AVAILABLE,
        "docs": "/docs",
        "endpoints": {
            "validate": "POST /validate",
            "submit": "POST /submit",
            "ledger": "GET /ledger",
            "ledger_by_id": "GET /ledger/{packet_id}",
            "chain_verify": "GET /ledger/verify",
            "health": "GET /health",
        },
    }


@app.get("/health")
def health():
    ledger = get_ledger()
    recent = ledger.recent(n=1)
    return {
        "status": "ok",
        "engine_available": _ENGINE_AVAILABLE,
        "ledger_entries": recent[0].get("seq") if recent else 0,
        "timestamp": int(time.time()),
    }


@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest, _: None = Depends(_check_api_key)):
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = _make_config()
    if not req.run_verifiers:
        config = EngineConfig(
            schema_path=config.schema_path,
            run_verifiers=False,
        )

    try:
        result = validate_packet(
            req.packet,
            now_epoch=req.now_epoch,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    ledger = get_ledger()
    try:
        entry = ledger.append(req.packet, result.overall, result.gate_results)
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    p_hash = compute_packet_hash(req.packet)

    return ValidateResponse(
        overall=result.overall,
        gate_results=[
            GateResultOut(
                gate=gr.gate,
                status=gr.status,
                reasons=gr.reasons,
                details=gr.details,
            )
            for gr in result.gate_results
        ],
        ledger_seq=ledger_seq,
        ledger_entry_hash=ledger_hash,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )




@app.post("/submit", include_in_schema=False)
def submit_public(req: ValidateRequest):
    """Public unauthenticated endpoint for the human-facing form.

    Behaves like /validate but bypasses the GOD-gate wait window — the
    public form is for one-shot evaluations, not bound community
    decisions. The wait-window override is applied on the packet
    itself (the engine reads `wait_window_seconds` per-packet); the
    EngineConfig dataclass doesn't carry that field.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = EngineConfig(
        schema_path=str(_SCHEMA_PATH) if _SCHEMA_PATH and _SCHEMA_PATH.exists() else "",
        run_verifiers=True,
    )

    # Bypass the GOD wait window for the public form by overriding the
    # packet's own wait_window_seconds (engine-level mechanism).
    packet_for_engine = {**req.packet, "wait_window_seconds": 0}

    try:
        result = validate_packet(
            packet_for_engine,
            now_epoch=req.now_epoch,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    ledger = get_ledger()
    try:
        entry = ledger.append(req.packet, result.overall, result.gate_results)
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    p_hash = compute_packet_hash(req.packet)

    return ValidateResponse(
        overall=result.overall,
        gate_results=[
            GateResultOut(
                gate=gr.gate,
                status=gr.status,
                reasons=gr.reasons,
                details=gr.details,
            )
            for gr in result.gate_results
        ],
        ledger_seq=ledger_seq,
        ledger_entry_hash=ledger_hash,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )


# ── Ledger read endpoints ──────────────────────────────────────────────
# Advertised by the home page (/) and /llms.txt; previously unimplemented.
# The underlying Ledger class already provides recent / get_by_id /
# verify_chain — these handlers are thin wrappers that surface them
# over HTTP so external auditors and AI agents can read the permanent
# record without touching the validator authentication path.

@app.get("/ledger")
def ledger_recent(
    limit: int = Query(50, ge=1, le=500,
                       description="How many entries to return (newest first)"),
    offset: int = Query(0, ge=0,
                        description="Skip the most recent N entries"),
):
    """Return the most recent ledger entries, newest first.

    Read-only and unauthenticated — the ledger is a public verification
    record. Each entry includes packet_hash, entry_hash, prev_hash, and
    overall verdict, so external auditors can replay and verify the
    chain without engine access.
    """
    ledger = get_ledger()
    entries = ledger.recent(n=limit, offset=offset)
    return {
        "count": len(entries),
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }


@app.get("/ledger/verify")
def ledger_verify():
    """Walk the ledger chain and confirm every prev_hash → entry_hash
    link is intact. Returns valid=True if the chain is whole, plus the
    seq number of the first break if not. The hash chain is the
    tampering check — any edit to any entry breaks it.
    """
    ledger = get_ledger()
    return ledger.verify_chain()


@app.get("/ledger/{packet_id}")
def ledger_by_id(packet_id: str):
    """Return all ledger entries for a specific packet_id, oldest first.

    Same packet may appear multiple times if it was resubmitted; the
    list is the full audit trail for that id. Empty list if the id
    isn't in the ledger.
    """
    ledger = get_ledger()
    entries = ledger.get_by_id(packet_id)
    return {
        "packet_id": packet_id,
        "count": len(entries),
        "entries": entries,
    }
