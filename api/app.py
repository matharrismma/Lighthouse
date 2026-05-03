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
    from concordance_engine.engine import (
        validate_packet, validate_and_seal, EngineConfig,
    )
    from concordance_engine.validate import compute_packet_hash
    from concordance_engine.witness_record import (
        Anchor, ClosestCase, WitnessRecord,
    )
    from concordance_engine.walkthrough import (
        render_walkthrough, render_walkthrough_html,
        render_walkthrough_compact,
    )
    from concordance_engine.nl_to_packet import parse as nl_parse
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


class SealRenderRequest(BaseModel):
    """Body for `POST /seal/render` — the human-form pipeline.

    Accepts a natural-language claim, routes it through nl_to_packet
    to build a real packet, runs validate_and_seal, and returns both
    the WitnessRecord JSON and a pre-rendered Socratic walkthrough
    (markdown or HTML, caller's choice). The front-end can drop the
    walkthrough into a div without re-implementing the renderer.
    """
    text: str
    format: str = "html"  # "html" | "markdown" | "compact"
    expand_traces: bool = False


class SealRequest(BaseModel):
    """Body for `POST /seal` — the canonical sealed-record endpoint.

    Identical to ValidateRequest but carries the optional rendering-
    layer concerns (anchors, closest_case, packet_id) that turn a bare
    EngineResult into a full WitnessRecord. Anchors are dicts of shape
    {ref, layer, text?}; closest_case is a dict of shape {precedent_id,
    shared_dimensions?, shared_anchors?, distance?, reasoning_overlay?}.
    Both default to absent/empty rather than fabricated.
    """
    packet: Dict[str, Any]
    now_epoch: Optional[int] = None
    run_verifiers: bool = True
    anchors: Optional[List[Dict[str, Any]]] = None
    closest_case: Optional[Dict[str, Any]] = None
    packet_id: Optional[str] = None


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


@app.get("/version")
def version():
    """Return the deployed engine version, schema version, and git SHA
    if available. Lets external callers (and us at 3am) verify what's
    actually running without grepping logs.

    git_sha resolves at request time from .git/HEAD if a git tree is
    visible; falls back to the env var CONCORDANCE_GIT_SHA (set by
    deploy scripts) or "unknown" if neither is available.
    """
    git_sha = os.environ.get("CONCORDANCE_GIT_SHA", "")
    if not git_sha:
        # Best-effort: read .git/HEAD from the repo on disk.
        try:
            repo_root = Path(__file__).parent.parent
            head = (repo_root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
            if head.startswith("ref: "):
                ref_path = repo_root / ".git" / head[5:]
                if ref_path.exists():
                    git_sha = ref_path.read_text(encoding="utf-8").strip()
            else:
                git_sha = head  # detached HEAD = direct SHA
        except (OSError, ValueError):
            git_sha = "unknown"

    out = {
        "git_sha": git_sha or "unknown",
        "engine_available": _ENGINE_AVAILABLE,
        "schema_version": "1.0",
    }
    if _ENGINE_AVAILABLE:
        try:
            import concordance_engine
            out["engine_package_version"] = getattr(
                concordance_engine, "__version__", "1.0.6",
            )
        except Exception:
            out["engine_package_version"] = "unknown"
    return out


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


# ── Sealed-record endpoint ─────────────────────────────────────────────
# /seal returns the full WitnessRecord shape — gate verdicts, every
# verifier result with its data (formula / rule / anchor), axis
# coordinates on the dimensional scaffold, citations with their
# source-hierarchy layer, and an optional closest-case overlay.
# /validate keeps the legacy EngineResult shape for backward compat.

@app.post("/seal")
def seal(req: SealRequest):
    """Run a packet through the four gates and return the sealed
    WitnessRecord.

    The canonical agent-facing surface for tonight's engine work.
    Where /validate returns a stripped EngineResult (overall + gate
    verdicts), /seal returns the WitnessRecord shape that walkthroughs
    are rendered from: each verifier_result carries its full `data`
    payload (rule, formula, doctrinal anchor for the rules that have
    one); axis_coords places the packet on the 36-axis scaffold;
    anchors carry their source-hierarchy layer; closest_case is
    explicit-absent (precedent_id=None) when no precedent applies.

    The endpoint also writes to the audit ledger like /submit does, so
    every sealed record is part of the permanent chain. ledger_seq and
    ledger_entry_hash come back alongside the WitnessRecord JSON.

    Doctrinal commitment: the response carries no `final_answer` /
    `answer` / `engine_answer` field, ever. The witness verifier's
    no_fabricated_answer check enforces that against any record sealed.
    """
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

    # Coerce optional anchor / closest_case payloads into the schema
    # types so any future structural changes propagate through one
    # boundary, not many.
    try:
        anchors = tuple(
            Anchor.from_dict(a) for a in (req.anchors or [])
        )
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"malformed anchors: {exc}",
        )
    closest_case = None
    if req.closest_case is not None:
        try:
            closest_case = ClosestCase.from_dict(req.closest_case)
        except (KeyError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"malformed closest_case: {exc}",
            )

    try:
        record = validate_and_seal(
            req.packet,
            now_epoch=req.now_epoch,
            config=config,
            anchors=anchors,
            closest_case=closest_case,
            packet_id=req.packet_id or req.packet.get("id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Write to the audit ledger using the gate_results from the record
    # so the persisted entry matches the returned record.
    ledger = get_ledger()
    try:
        entry = ledger.append(
            req.packet, record.overall, list(record.gate_results),
        )
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    out = record.to_dict()
    if ledger_seq is not None:
        out["ledger_seq"] = ledger_seq
        out["ledger_entry_hash"] = ledger_hash
    out["elapsed_ms"] = round(elapsed_ms, 2)
    return out


@app.post("/seal/render", include_in_schema=False)
def seal_render(req: SealRenderRequest):
    """Human-form pipeline: natural-language → packet → seal → rendered walkthrough.

    Routes the user's text through nl_to_packet (deterministic
    template parser) to build a real packet, runs validate_and_seal,
    and returns both the WitnessRecord JSON and a pre-rendered
    walkthrough so the front-end just innerHTML's the response.

    When the parser doesn't recognize the input shape, returns a
    structured 422 listing the templates that *are* supported, so
    the user gets a useful "try something like..." instead of a
    confusing error. Templates currently understood:
      * chemistry equation: "is C + O2 -> CO2 balanced?"
      * one-sample t-test: "p=0.05 from a t-test, n=30, mean=5, sd=1, mu0=4"
      * physics dimensional: "F = m*a where F in newtons, m in kg, a in m/s^2"
      * math equality / derivative: "d/dx(x^2) = 2x"
      * CS complexity: "merge sort runs in O(n log n)"
      * governance proposal: "should we admit Alice with 3 witnesses?"
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")

    parsed = nl_parse(text)
    if parsed is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_template_matched",
                "message": (
                    "The deterministic parser doesn't recognize this "
                    "input shape yet. Try one of the supported forms."
                ),
                "supported_templates": [
                    "chemistry: 'is C + O2 -> CO2 balanced?'",
                    "statistics: 'p=0.05 from a t-test, n=30, mean=5, sd=1, mu0=4'",
                    "physics: 'F = m*a where F in newtons, m in kg, a in m/s^2'",
                    "mathematics: 'd/dx(x^2) = 2x'",
                    "computer science: 'merge sort runs in O(n log n)'",
                    "governance: 'should we admit Alice with 3 witnesses?'",
                ],
                "input_text": text,
            },
        )

    t0 = time.perf_counter()
    config = _make_config()

    # Force `wait_window_seconds=0` on the packet so the GOD wait
    # window doesn't block one-shot human submissions. Mirrors the
    # /submit handler's behavior.
    packet_for_engine = {**parsed.packet, "wait_window_seconds": 0}

    try:
        record = validate_and_seal(
            packet_for_engine,
            config=config,
            packet_id=packet_for_engine.get("id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Write to the audit ledger.
    ledger = get_ledger()
    try:
        entry = ledger.append(
            parsed.packet, record.overall, list(record.gate_results),
        )
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    # Render the walkthrough in the requested format. HTML is embedded
    # (inner-content only) so the front-end can drop it into a div
    # without dragging the renderer's full document wrapper / styles
    # into the host page.
    fmt = (req.format or "html").lower()
    if fmt == "markdown":
        walkthrough = render_walkthrough(record, expand_traces=req.expand_traces)
    elif fmt == "compact":
        walkthrough = render_walkthrough_compact(record)
    else:
        walkthrough = render_walkthrough_html(
            record, expand_traces=req.expand_traces, embedded=True,
        )

    return {
        "record": record.to_dict(),
        "walkthrough": walkthrough,
        "format": fmt,
        "parse_template": parsed.template,
        "parse_confidence": parsed.confidence,
        "parse_notes": parsed.notes,
        "ledger_seq": ledger_seq,
        "ledger_entry_hash": ledger_hash,
        "elapsed_ms": round(elapsed_ms, 2),
    }


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


# ── /audit-chain — canonical-naming aliases ────────────────────────────
# Same handlers as /ledger but at the canonically-correct URL. Per the
# doctrinal-distinction note: "ledger" the doctrinal term refers to
# judgment-keeping (gospel ends the ledger); the engine's mechanism is
# an audit chain, not a judgment ledger. The /ledger URLs stay live for
# backward compat; new clients should prefer /audit-chain.

@app.get("/audit-chain", include_in_schema=True)
def audit_chain_recent(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Most recent audit-chain entries (alias for /ledger)."""
    return ledger_recent(limit=limit, offset=offset)


@app.get("/audit-chain/verify", include_in_schema=True)
def audit_chain_verify():
    """Walk the chain and confirm prev_hash → entry_hash links hold
    (alias for /ledger/verify)."""
    return ledger_verify()


@app.get("/audit-chain/{packet_id}", include_in_schema=True)
def audit_chain_by_id(packet_id: str):
    """All audit-chain entries for a specific packet_id (alias for
    /ledger/{packet_id})."""
    return ledger_by_id(packet_id)
