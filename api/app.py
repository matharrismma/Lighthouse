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

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
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

# -- Front-end session auth (passphrase + invite codes) ------------------
# Scope: governs who sees the dashboard. Does NOT apply to existing
# API/agent endpoints (/validate, /seal, /path, verifiers, etc.) —
# those keep their own X-Api-Key auth. BROTHERS gate applies only at
# the record boundary (POST /seal, /confess) and between parties
# (federation), not to internal sandbox operations.

_PASSPHRASE = os.environ.get("CONCORDANCE_PASSPHRASE", "")
_SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
_PASSPHRASE_HASH = (
    hashlib.sha256(_PASSPHRASE.encode()).hexdigest() if _PASSPHRASE else ""
)

_AUTH_DIR = (
    Path(os.environ.get("CONCORDANCE_DATA_DIR", "~/.concordance")).expanduser()
    / "auth"
)


def _make_token(user_id: str) -> str:
    expiry = int(time.time()) + 86400
    payload = f"{user_id}|{expiry}"
    sig = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _verify_token(token: str) -> bool:
    if not token or not _PASSPHRASE:
        return True  # dev mode — no passphrase configured
    try:
        *payload_parts, sig = token.split("|")
        payload = "|".join(payload_parts)
        expected = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        user_id, expiry_str = payload_parts[0], payload_parts[1]  # noqa: F841
        return int(expiry_str) >= int(time.time())
    except Exception:
        return False


def _load_invites() -> dict:
    try:
        if _AUTH_DIR.joinpath("invites.json").exists():
            return json.loads(_AUTH_DIR.joinpath("invites.json").read_text())
    except Exception:
        pass
    return {}


def _save_invites(invites: dict) -> None:
    try:
        _AUTH_DIR.mkdir(parents=True, exist_ok=True)
        _AUTH_DIR.joinpath("invites.json").write_text(json.dumps(invites, indent=2))
    except Exception:
        pass


class LoginRequest(BaseModel):
    passphrase: str


class InviteCreateRequest(BaseModel):
    name: str
    role: str = ""
    uses: int = 1
    expires_days: int = 7


class RedeemRequest(BaseModel):
    code: str


class AccessRequest(BaseModel):
    text: str
    contact: str = ""


def _require_session(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


@app.post("/auth/login", tags=["auth"])
def auth_login(req: LoginRequest):
    if not _PASSPHRASE:
        return {"token": _make_token("dev"), "expires_in": 86400}
    if not hmac.compare_digest(
        hashlib.sha256(req.passphrase.encode()).hexdigest(), _PASSPHRASE_HASH
    ):
        raise HTTPException(status_code=401, detail="Incorrect passphrase")
    return {"token": _make_token("operator"), "expires_in": 86400}


@app.get("/auth/verify", tags=["auth"])
def auth_verify(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return {"status": "ok"}


@app.post("/auth/logout", tags=["auth"])
def auth_logout():
    return {"status": "logged_out"}


@app.post("/auth/invite", tags=["auth"])
def auth_invite(req: InviteCreateRequest, _: str = Depends(_require_session)):
    code = secrets.token_urlsafe(9)
    invites = _load_invites()
    invites[code] = {
        "name": req.name,
        "role": req.role,
        "uses": req.uses,
        "used": 0,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + req.expires_days * 86400,
    }
    _save_invites(invites)
    return {"code": code, "name": req.name, "expires_days": req.expires_days}


@app.post("/auth/redeem", tags=["auth"])
def auth_redeem(req: RedeemRequest):
    invites = _load_invites()
    invite = invites.get(req.code)
    if not invite:
        raise HTTPException(status_code=401, detail="Code not recognized")
    if invite["expires_at"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Code expired")
    if invite["uses"] != -1 and invite["used"] >= invite["uses"]:
        raise HTTPException(status_code=401, detail="Code already used")
    invite["used"] += 1
    _save_invites(invites)
    return {"token": _make_token(invite["name"]), "expires_in": 86400, "name": invite["name"]}


@app.post("/auth/request", tags=["auth"])
def auth_request(req: AccessRequest):
    try:
        _AUTH_DIR.mkdir(parents=True, exist_ok=True)
        requests_file = _AUTH_DIR / "access_requests.jsonl"
        with open(requests_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "text": req.text,
                "contact": req.contact,
                "created_at": int(time.time()),
            }) + "\n")
    except Exception:
        pass
    return {"status": "received"}


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
    """Comprehensive liveness check.

    Reports engine availability, audit chain reachability, journal
    store reachability, keeping log reachability, and verifier-layer
    importability. Each subsystem reports independently so a single
    degraded module doesn't make the whole API look down.
    """
    ledger = get_ledger()
    recent = ledger.recent(n=1)
    out: Dict[str, Any] = {
        "status": "ok",
        "engine_available": _ENGINE_AVAILABLE,
        "ledger_entries": recent[0].get("seq") if recent else 0,
        "timestamp": int(time.time()),
        "modules": {},
    }

    if _ENGINE_AVAILABLE:
        # Each subsystem is checked independently. Failures are reported,
        # not raised — health endpoint must always respond.
        try:
            from concordance_engine.journal import JournalStore
            store = JournalStore()
            entries = store.list_all()
            out["modules"]["journal"] = {
                "reachable": True,
                "total_entries": len(entries),
                "shelf_count": sum(1 for e in entries if "shelf" in e.user_tags),
            }
        except Exception as e:
            out["modules"]["journal"] = {"reachable": False, "error": str(e)}

        try:
            from concordance_engine.keeping import KeepingLog
            log = KeepingLog()
            observations = log.read()
            out["modules"]["keeping"] = {
                "reachable": True,
                "total_observations": len(observations),
                "practices_observed": len({o.practice for o in observations}),
            }
        except Exception as e:
            out["modules"]["keeping"] = {"reachable": False, "error": str(e)}

        try:
            from concordance_engine.quarantine import QuarantineStore
            qstore = QuarantineStore()
            packets = qstore.list_all()
            out["modules"]["quarantine"] = {
                "reachable": True,
                "total_packets": len(packets),
            }
        except Exception as e:
            out["modules"]["quarantine"] = {"reachable": False, "error": str(e)}

        try:
            from concordance_engine import verifiers as _v
            # Import a handful of canonical verifier modules to confirm
            # the verifier layer is intact.
            _domains = ["chemistry", "mathematics", "physics", "scripture", "phase"]
            lit = []
            for d in _domains:
                try:
                    __import__(f"concordance_engine.verifiers.{d}")
                    lit.append(d)
                except Exception:
                    pass
            out["modules"]["verifiers"] = {
                "reachable": True,
                "lit_count": len(lit),
                "lit": lit,
            }
        except Exception as e:
            out["modules"]["verifiers"] = {"reachable": False, "error": str(e)}

    # Overall status downgrade if any module is unreachable.
    if any(
        isinstance(m, dict) and not m.get("reachable", True)
        for m in out["modules"].values()
    ):
        out["status"] = "degraded"
    return out


@app.get("/identity")
def identity():
    """Canonical identity statement — what this engine serves.

    Every agent-facing surface reads from the same single source
    (`concordance_engine.IDENTITY`). Plain, present, never hidden.
    The engine flows for legitimate use; what it serves is stated
    up front so callers (human and AI) know.
    """
    if not _ENGINE_AVAILABLE:
        return {
            "serves": "Jesus Christ",
            "statement": (
                "The Concordance Engine at narrowhighway.com serves Jesus Christ. "
                "Engine pipeline not loaded — this is the bare identity surface."
            ),
            "engine_loaded": False,
        }
    from concordance_engine import IDENTITY, IDENTITY_SHORT, __version__
    return {
        "serves": "Jesus Christ",
        "short": IDENTITY_SHORT,
        "statement": IDENTITY,
        "version": __version__,
        "engine_loaded": True,
    }


# ── /speak — ElevenLabs TTS proxy (optional) ────────────────────────
#
# Returns audio/mpeg synthesized in the configured voice. Optional in
# every sense: requires `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`
# in the environment; without them the endpoint reports unavailable.
# Nothing else in the engine depends on this — it's a phone-friendly
# surface for hearing precedents read aloud.


class SpeakRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None  # override env default
    model_id: str = "eleven_turbo_v2_5"


@app.post("/speak", include_in_schema=True)
def speak(req: SpeakRequest):
    """Proxy ElevenLabs streaming TTS. Returns audio/mpeg.

    Caller text in, voice out. No transcription, no logging of audio.
    The text is not retained; only the audio stream is returned. Use
    a short prefix of `req.text` (≤80 chars) for any error messages
    so we never echo the full prompt back into logs.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = req.voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise HTTPException(
            status_code=503,
            detail="speak unavailable: ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not configured",
        )
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="text too long (max 5000 chars)")

    # Lazy-import requests so the rest of the API still loads if it's
    # not installed (e.g. minimal deployments).
    try:
        import requests as _requests
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="speak unavailable: `requests` not installed",
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {
        "text": text,
        "model_id": req.model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }

    try:
        r = _requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
    except _requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"upstream tts error: {exc}")

    if r.status_code != 200:
        # Surface upstream status without leaking the API key in error
        # bodies. ElevenLabs sometimes returns JSON, sometimes HTML.
        try:
            detail = r.json()
        except ValueError:
            detail = {"upstream_status": r.status_code, "body_excerpt": r.text[:200]}
        raise HTTPException(status_code=502, detail=detail)

    # Read the full body once. Streaming the response straight through
    # FastAPI is possible but adds complexity; for a typical precedent
    # read-aloud (< 30s of audio), the buffered approach is fine.
    audio_bytes = r.content
    return Response(content=audio_bytes, media_type="audio/mpeg")


# ── /reach — operator-configured substrate addresses (read-only) ──
#
# Public, read-only. Returns whichever alternative-substrate addresses
# the operator has configured via environment variables. Empty
# fields mean "not configured by this operator." reach.html and
# setup.html both consume this; the public reach page substitutes
# operator-specific addresses where present and shows generic
# descriptions where absent.
#
# These are addresses (onion URL, bot handle, npub, gateway), not
# secrets. The corresponding *secrets* (Telegram token, ElevenLabs
# API key, etc.) stay in env vars and are never exposed.


@app.get("/reach")
def reach_config():
    """Return the substrate-channel directory for this instance.

    Reads operator-configured public addresses from environment
    variables. Booleans (e.g. `speak_voice`) signal capability
    without revealing the underlying credential.
    """
    el_key = os.environ.get("ELEVENLABS_API_KEY", "")
    el_voice = os.environ.get("ELEVENLABS_VOICE_ID", "")
    return {
        "tor_onion":    os.environ.get("CONCORDANCE_TOR_ONION", ""),
        "telegram":     os.environ.get("CONCORDANCE_TELEGRAM_HANDLE", ""),
        "email_in":     os.environ.get("CONCORDANCE_EMAIL_INBOUND", ""),
        "nostr_npub":   os.environ.get("CONCORDANCE_NOSTR_NPUB", ""),
        "ipfs_gateway": os.environ.get("CONCORDANCE_IPFS_GATEWAY", ""),
        "lora_freq":    os.environ.get("CONCORDANCE_LORA_FREQ", ""),
        "mailing_list": os.environ.get("CONCORDANCE_MAILING_LIST", ""),
        # Capability booleans — true when the corresponding secret /
        # config is present, without exposing the secret itself.
        "speak_voice":  bool(el_key and el_voice),
        "fetch_remote": os.environ.get("CONCORDANCE_FETCH_REMOTE", ""),
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
        # Identity is part of every version response — agents reading
        # /version should know what this engine serves before they call
        # any other endpoint. The full statement is at /identity.
        "serves": "Jesus Christ",
        "serves_short": (
            "Conduit, not source. Eliminates to illuminate the narrow path."
        ),
    }
    if _ENGINE_AVAILABLE:
        try:
            import concordance_engine
            out["engine_package_version"] = getattr(
                concordance_engine, "__version__", "1.1.0",
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


# ── /reflect — rehearse a packet (no ledger write) ─────────────────────


@app.post("/reflect", include_in_schema=True)
def reflect(req: ValidateRequest):
    """Rehearse a packet through all four gates without writing to the ledger.

    Same verdict shape as /submit. Use this to iterate on a packet until
    the verdict is what you intend, then commit via /submit or /validate.
    The ledger is never touched here — rehearsal is safe to call repeatedly.
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

    # Bypass the GOD wait window so rehearsal returns a real PASS/REJECT
    # rather than an unwaitable QUARANTINE. The actual commit will enforce
    # the real wait.
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
        ledger_seq=None,
        ledger_entry_hash=None,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )


# ── /confess — record that a prior committed packet was wrong ───────────


class ConfessRequest(BaseModel):
    ref_seq: int                              # ledger seq of the prior entry
    name: str                                 # who is confessing
    role: str = ""                            # confessor's role
    reason: str                               # what was wrong
    corrected_approach: Optional[str] = None  # what the right approach would be


@app.post("/confess", include_in_schema=True)
def confess(req: ConfessRequest):
    """Record that a previously committed packet was wrong.

    The original entry is immutable — it stays in the chain exactly as it was.
    The confession is a new entry that points back to the prior one via
    `confesses_seq` and `confesses_packet_hash`. Walking the chain later,
    a reader sees both the original decision and the correction.

    Use this instead of attempting to mutate or delete a ledger entry.
    Mutation is impossible by design; confession is the correct mechanism.
    """
    ledger = get_ledger()

    prior = ledger.get_by_seq(req.ref_seq)
    if prior is None:
        raise HTTPException(
            status_code=404,
            detail=f"no ledger entry found at seq={req.ref_seq}",
        )

    confession_packet = {
        "domain": "confession",
        "id": f"confession-seq{req.ref_seq}",
        "confesses_seq": req.ref_seq,
        "confesses_packet_hash": prior.get("packet_hash", ""),
        "confessor_name": req.name,
        "confessor_role": req.role,
        "reason": req.reason,
        "corrected_approach": req.corrected_approach,
    }

    try:
        entry = ledger.append(confession_packet, "CONFESSION", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ledger write failed: {exc}")

    return {
        "confessed_seq": req.ref_seq,
        "confessed_packet_hash": prior.get("packet_hash"),
        "confession_seq": entry.seq,
        "confession_entry_hash": entry.entry_hash,
        "message": "Confession recorded. The original entry is unchanged.",
    }


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


# ── /witness/{precedent_id} — list witness attestations on a precedent ──
#
# Public, read-only. Returns every Ed25519 witness attestation on file
# for the given precedent_id, with a verify result on each. Anyone
# reading a precedent in the well can see who has stood by it
# cryptographically — the BROTHERS gate's witness count + the
# witness signatures together make the witness layer legible.
#
# Per "free use, alignment to execute": reading attestations is
# free; signing them requires the witness's private key.


@app.get("/witness/{precedent_id:path}")
def witness_attestations(precedent_id: str):
    """Return all witness attestations on file for a precedent.

    Each result includes the attestation fields plus `verified`
    (bool) and `verify_reason` (str) computed at request time so
    consumers see whether the signature still holds.
    """
    if not precedent_id:
        raise HTTPException(status_code=400, detail="precedent_id is required")
    try:
        from concordance_engine import witness as _witness
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"witness module unavailable: {exc}"
        )
    attestations = _witness.list_for_precedent(precedent_id)
    out: List[Dict[str, Any]] = []
    for att in attestations:
        try:
            ok, reason = _witness.verify(att)
        except Exception as exc:  # noqa: BLE001
            ok, reason = False, f"verify error: {exc}"
        record = att.to_dict()
        record["verified"] = ok
        record["verify_reason"] = reason
        out.append(record)
    return {
        "precedent_id": precedent_id,
        "count": len(out),
        "attestations": out,
    }


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


# ── /dispatch — filtered ledger search ────────────────────────────────


@app.get("/dispatch", include_in_schema=True)
def dispatch(
    domain:     Optional[str] = Query(None, description="Filter by domain (e.g. 'governance')"),
    overall:    Optional[str] = Query(None, description="Filter by verdict (PASS, REJECT, QUARANTINE, CONFESSION)"),
    packet_id:  Optional[str] = Query(None, description="Filter by packet_id"),
    since:      Optional[float] = Query(None, description="Return entries at or after this epoch"),
    until:      Optional[float] = Query(None, description="Return entries at or before this epoch"),
    limit:      int = Query(50, ge=1, le=500, description="Maximum entries to return"),
):
    """Filtered search over the ledger.

    All parameters are optional and cumulative — only entries that match
    every supplied filter are returned. Results are newest first.
    """
    ledger = get_ledger()
    entries = list(ledger.iter_filtered(
        domain=domain,
        overall=overall,
        packet_id=packet_id,
        since_epoch=since,
        until_epoch=until,
        limit=limit,
    ))
    return {
        "count": len(entries),
        "filters": {
            "domain": domain, "overall": overall, "packet_id": packet_id,
            "since": since, "until": until, "limit": limit,
        },
        "entries": entries,
    }


# ── /stats — aggregate ledger counts ──────────────────────────────────


@app.get("/stats", include_in_schema=True)
def stats():
    """Aggregate counts across the entire ledger.

    Returns total entry count, breakdown by verdict (PASS / REJECT /
    QUARANTINE / CONFESSION) and by domain, plus the timestamp of the
    most recent entry.
    """
    ledger = get_ledger()
    return ledger.stats()


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


# ── /chain/since — fetch endpoint for federation ──────────────────
#
# Returns audit-chain entries with seq > the given cursor, ordered
# OLDEST FIRST so a receiver can append in chain order. This is the
# server side of `concordance fetch` — a peer engine pulls new
# sealed precedents from this instance to mirror them locally.
#
# Read-only, public. Per "free use, alignment to execute": reading
# the well is free. Anyone can fetch any sealed precedent.


# ── /chain/receive — federation push (inverse of /chain/since) ─────
#
# Symmetric with /chain/since: that endpoint serves entries to peers
# pulling from us; this one accepts entries from peers pushing to us.
# Both store into the same fetched/<remote_slug>.jsonl mirror — pull
# vs push is just direction.
#
# Per "free use, alignment to execute": receiving is read-shaped from
# our perspective (we don't validate the sender's authority; we
# accept and store, tagged with their claimed origin URL). The four
# gates already ran on the sender's side; we mirror what they sealed.
# If a malicious peer pushes garbage, it lands in their slug only
# and never enters our chain.


class ChainReceiveRequest(BaseModel):
    from_: str = ""  # alias for "from" — handled below
    entries: List[Dict[str, Any]] = []

    class Config:
        # Accept either "from" or "from_" since "from" is a Python keyword.
        # Pydantic v2 uses populate_by_name + Field alias; for compatibility
        # we accept both via the json schema validation in the handler.
        pass


@app.post("/chain/receive", include_in_schema=True)
def chain_receive(payload: Dict[str, Any]):
    """Receive sealed precedents pushed by a peer.

    Body shape: `{from: <url>, entries: [...]}`. Entries are the
    same audit-chain rows a remote's /chain/since would emit. We
    don't validate the chain's hash continuity here — the sending
    instance is responsible for the integrity of its own chain;
    we just mirror what they sent us.

    Stored in the same fetched/<slug>.jsonl files as pulled
    entries, so consumers (concordance fetch --list, the dawn
    surface, etc.) see push-received and pull-received entries
    together.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")

    from_url = (payload.get("from") or payload.get("from_") or "").strip()
    if not from_url:
        raise HTTPException(status_code=400, detail="`from` url is required")

    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="`entries` must be a list")

    try:
        from concordance_engine import fetch as _fetch
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"fetch module not available: {exc}"
        )

    # Light validation: each entry must at least have a seq + packet_id +
    # entry_hash. Anything else is the sender's chain, not ours.
    accepted_entries = []
    rejected = []
    seen_seqs = set()
    for e in entries:
        if not isinstance(e, dict):
            rejected.append({"seq": None, "reason": "entry not a dict"})
            continue
        seq = e.get("seq")
        if seq is None:
            rejected.append({"seq": None, "reason": "missing seq"})
            continue
        if seq in seen_seqs:
            rejected.append({"seq": seq, "reason": "duplicate seq in payload"})
            continue
        if not e.get("packet_id"):
            rejected.append({"seq": seq, "reason": "missing packet_id"})
            continue
        if not e.get("entry_hash"):
            rejected.append({"seq": seq, "reason": "missing entry_hash"})
            continue
        seen_seqs.add(seq)
        # Tag with origin + receive timestamp, same shape as fetch path.
        e.setdefault("_origin", from_url)
        e.setdefault("_fetched_at", time.time())
        e.setdefault("_received_via", "push")
        accepted_entries.append(e)

    if accepted_entries:
        base = _fetch._default_base_dir()
        _fetch._append_entries(base, from_url, accepted_entries)
        # Update the per-remote state so subsequent pulls don't re-pull
        # things we already received via push.
        state = _fetch._load_state(base, from_url)
        max_seq = max(int(e.get("seq", 0)) for e in accepted_entries)
        if max_seq > state.last_seq:
            state.last_seq = max_seq
        state.last_fetched_at = time.time()
        state.last_status = "received_push"
        _fetch._save_state(base, state)

    return {
        "from": from_url,
        "accepted": len(accepted_entries),
        "rejected": rejected,
        "next_seq": max((int(e.get("seq", 0)) for e in accepted_entries), default=0),
    }


@app.get("/chain/since", include_in_schema=True)
def chain_since(
    seq: int = Query(0, ge=0,
        description="Return entries with seq > this value."),
    limit: int = Query(100, ge=1, le=1000),
):
    """Audit-chain entries past `seq`, oldest first. Federation endpoint.

    Used by `concordance fetch` to incrementally sync new precedents
    from a remote engine. Idempotent — calling with the same `seq`
    yields the same response. Empty `entries` array means the receiver
    is up to date.
    """
    ledger = get_ledger()
    # Read all entries newest-first, then filter + reverse.
    all_recent = ledger.recent(n=10000, offset=0)  # generous cap
    after: List[Dict[str, Any]] = []
    for e in all_recent:
        e_seq = int(e.get("seq", 0))
        if e_seq > seq:
            after.append(e)
    after.sort(key=lambda x: x.get("seq", 0))
    sliced = after[:limit]
    return {
        "since_seq": seq,
        "limit": limit,
        "count": len(sliced),
        "next_seq": sliced[-1].get("seq", seq) if sliced else seq,
        "entries": sliced,
    }


# ── Journal / shelf / keeping (the human-side surfaces) ──────────────
# These expose the new harvest / library / shelf / keeping modules
# over HTTP so narrowhighway.com (and any client) can use them.
# Mirrors the CLI subcommands (`concordance write`, `concordance keep`,
# `concordance journal`, `concordance live`).


class WriteRequest(BaseModel):
    text: str
    tags: Optional[List[str]] = None
    look_up_precedent: bool = True
    # Identity acknowledgment — the depositing-into-the-well permission.
    # Optional with default True so existing clients don't break; agents
    # are encouraged (but not forced) to set this explicitly after
    # reading /identity. The value is recorded in the seed's metadata
    # for the keeping log; the engine still runs whether or not it's
    # acknowledged. Misalignment is caught by the four gates downstream,
    # not by this field.
    identity_acknowledged: bool = True


class AnnotateRequest(BaseModel):
    note: str
    author: Optional[str] = ""


# ── /capture — unified capture-anywhere funnel ─────────────────────
#
# One endpoint, many sources. Drop a file in a watch folder, share
# from an iOS app, forward an email, send a Telegram message — all
# arrive here with `source` set, and all become seeds in the same
# journal. The source is recorded as a tag (`source:<name>`) so
# any later audit can see where a seed came from.
#
# This endpoint is intentionally tolerant: text is required, every-
# thing else is optional. Source authenticity is informational, not
# authoritative — misalignment is caught by the four gates downstream
# (RED/FLOOR/BROTHERS/GOD), not by trusting the source claim.
#
# Per the kingdom-economy substrate: capture works with whatever the
# user already has (email, file system, phone share sheet) — no
# proprietary client required.


class CaptureRequest(BaseModel):
    text: str
    source: Optional[str] = None       # e.g. "watch_folder", "email", "telegram", "apple_shortcut", "web_share"
    source_meta: Optional[Dict[str, Any]] = None  # arbitrary metadata about origin
    tags: Optional[List[str]] = None
    identity_acknowledged: bool = True
    look_up_precedent: bool = True


@app.post("/capture", include_in_schema=True)
def capture(req: CaptureRequest):
    """Unified capture funnel. Accepts text from any source; records
    the source as a tag; forwards to the journal capture mechanism.

    Sources are tagged but not validated — any caller can claim any
    source. The four gates downstream check alignment by content,
    not by claimed origin. This is the wise-serpent + innocent-dove
    posture: trusting source claims would be naive; refusing to
    record them would erase useful provenance. We record what was
    claimed, run the gates on the content.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # Build the tag list: user tags + source tag + acknowledgment marker.
    # The source tag is namespaced ("source:email") so later filters
    # can find all seeds from a given source.
    tags = list(req.tags or [])
    if req.source:
        # Normalize source — lowercase, alnum + underscore only.
        clean = "".join(c for c in req.source.lower() if c.isalnum() or c == "_")
        if clean:
            src_tag = f"source:{clean}"
            if src_tag not in tags:
                tags.append(src_tag)
    if req.identity_acknowledged:
        # Mark the seed as having passed the alignment doorway.
        if "identity_acknowledged" not in tags:
            tags.append("identity_acknowledged")

    try:
        from concordance_engine import journal as _journal
    except ImportError as e:
        raise HTTPException(
            status_code=503, detail=f"journal module not available: {e}"
        )

    try:
        entry = _journal.capture(
            text,
            tags=tags or None,
            look_up_precedent=req.look_up_precedent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cal = _journal.calibrate(entry)
    closest = _resolve_closest_precedent(entry.categorization.closest_precedent_id)
    return {
        "entry": entry.to_dict(),
        "calibration": cal.to_dict(),
        "closest_precedent": closest,
        "source": req.source,
        "rendered_calibration": _journal.render_calibration(entry, cal),
    }


def _resolve_closest_precedent(precedent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Look up the full body of a precedent by id, for closest-case
    overlay. Returns None if not found or on error — closest-case is
    descriptive, not prescriptive, so a missing precedent is just
    silence, not an error."""
    if not precedent_id:
        return None
    try:
        from concordance_engine import ledger as _ledger
        for p in _ledger.list_precedents():
            if p.get("precedent_id") == precedent_id:
                return p
    except (ImportError, OSError, ValueError):
        return None
    return None


@app.post("/journal/write", include_in_schema=True)
def journal_write(req: WriteRequest):
    """Capture a stream-of-consciousness seed.

    Bare text in. Categorization out. Nothing replaces what was
    written. The engine listens and returns:
      * the entry id (seed lands in the user's library)
      * what was heard (anchors / actions / scope / shape)
      * calibration measurements (drift / pattern / tempo against
        history) — descriptive only, never prescriptive
      * closest precedent body — if the well already holds a record
        whose scaffold dimensions overlap, the user sees it at the
        moment of writing (assist in wisdom; show engineering)
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )
    try:
        from concordance_engine import journal as _journal
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"journal module not available: {e}")

    try:
        entry = _journal.capture(
            req.text,
            tags=req.tags,
            look_up_precedent=req.look_up_precedent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cal = _journal.calibrate(entry)

    # Closest-case overlay: enrich the response with the full
    # precedent body when one was matched. Frontend renders this
    # as a small "this resembles..." card so the user sees the
    # well catch their thought as they write it.
    closest = _resolve_closest_precedent(entry.categorization.closest_precedent_id)

    return {
        "entry": entry.to_dict(),
        "calibration": cal.to_dict(),
        "closest_precedent": closest,
        "rendered_calibration": _journal.render_calibration(entry, cal),
    }


@app.get("/journal/recent", include_in_schema=True)
def journal_recent(
    limit: int = Query(20, ge=1, le=200),
    tag: Optional[str] = Query(None),
    since: Optional[float] = Query(None),
):
    """List recent journal seeds (newest first). Optional tag /
    since filters."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entries = store.list_all(since=since, tag=tag)[:limit]
    return {"count": len(entries), "entries": [e.to_dict() for e in entries]}


@app.get("/journal/{entry_id}", include_in_schema=True)
def journal_show(entry_id: str):
    """Show a single journal seed in full."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return entry.to_dict()


@app.get("/journal/{entry_id}/thread", include_in_schema=True)
def journal_thread(entry_id: str):
    """Find seeds that share signal with this one (return-thread)."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    source = store.load(entry_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    related = _journal.thread(entry_id)
    return {
        "source_id": entry_id,
        "count": len(related),
        "entries": [e.to_dict() for e in related],
    }


@app.post("/journal/{entry_id}/annotate", include_in_schema=True)
def journal_annotate(entry_id: str, req: AnnotateRequest):
    """Append an annotation. Original text is preserved."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        updated = _journal.annotate(
            entry_id, req.note, author=req.author or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


@app.get("/journal/{entry_id}/calibration", include_in_schema=True)
def journal_calibration(entry_id: str):
    """Run calibration for an existing entry against current history."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    cal = _journal.calibrate(entry)
    return {
        "entry_id": entry_id,
        "calibration": cal.to_dict(),
        "rendered": _journal.render_calibration(entry, cal),
    }


# ── Shelf (community tier) ───────────────────────────────────────────


_SHELF_TAG = "shelf"


@app.get("/shelf", include_in_schema=True)
def shelf_list(limit: int = Query(50, ge=1, le=500)):
    """List entries on the shelf — community-visible seeds."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entries = store.list_all(tag=_SHELF_TAG)[:limit]
    return {"count": len(entries), "entries": [e.to_dict() for e in entries]}


@app.post("/shelf/{entry_id}", include_in_schema=True)
def shelf_publish(entry_id: str):
    """Publish a seed to the shelf (anyone reaching for it can find it)."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    if _SHELF_TAG not in entry.user_tags:
        entry.user_tags = list(entry.user_tags) + [_SHELF_TAG]
        entry.modified_at = time.time()
        store.save(entry)
    return entry.to_dict()


@app.delete("/shelf/{entry_id}", include_in_schema=True)
def shelf_unshelf(entry_id: str):
    """Remove a seed from the shelf — keep it in the library only."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    if _SHELF_TAG in entry.user_tags:
        entry.user_tags = [t for t in entry.user_tags if t != _SHELF_TAG]
        entry.modified_at = time.time()
        store.save(entry)
    return entry.to_dict()


# ── Keeping (the liturgical layer surface) ───────────────────────────


@app.get("/keeping/status", include_in_schema=True)
def keeping_status(
    since: Optional[float] = Query(None,
        description="Unix epoch seconds; default: last 24h."),
):
    """What the keeping kept while you were away.

    Returns per-practice run-count and latest observation across the
    look-back window. Default window: 24 hours.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    if since is None:
        since = time.time() - 86400.0
    return _keeping.while_you_were_away(since=since)


@app.post("/keeping/walk", include_in_schema=True)
def keeping_walk():
    """Run one tick of the keeper. Each due practice fires once.

    Useful for nudging the keeping along when a daemon isn't running
    in the background. Server-managed background ticker is separate
    (see `concordance keep run` for the daemon mode).
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    keeper = _keeping.default_keeper()
    observations = keeper.tick()
    return {
        "observations": [o.to_dict() for o in observations],
        "count": len(observations),
    }


# ── Dawn (optional, read-only perimeter walk) ──────────────────────
#
# Per KoA Trilogy (Anna's chapter): the walk before the settlement
# wakes. Surfaces what's been kept across keeping + ledger +
# quarantine, in one read-only call. Always available when the engine
# is loaded, but defensively imported — if dawn.py or any dependency
# is missing, the endpoint reports unavailable rather than 500.


@app.get("/dawn", include_in_schema=True)
def dawn_endpoint(
    since: Optional[float] = Query(
        None,
        description="Unix epoch seconds; default: last 24h.",
    ),
    hours: Optional[float] = Query(
        None,
        description="Convenience: look back N hours (overrides `since`).",
    ),
    rendered: bool = Query(
        True,
        description="Include the rendered markdown narrative alongside "
                    "the structured surface (default: true).",
    ),
):
    """Read what the kingdom has been keeping while you were away.

    Read-only. No side effects. No verdicts — names what's been kept.
    Closes with a Socratic question, never a directive.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    try:
        from concordance_engine import dawn as _dawn
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"dawn module unavailable: {exc}"
        )
    if hours is not None:
        since = time.time() - (hours * 3600.0)
    surface = _dawn.gather_dawn(since=since)
    out = {"surface": surface.to_dict()}
    if rendered:
        out["rendered"] = _dawn.render_dawn(surface)
    return out


# ── Ask (search the seed bank or capture a new seed) ────────────────


class AskRequest(BaseModel):
    question: str
    capture_if_no_survivors: bool = True
    max_survivors: int = 5
    max_eliminated: int = 10


@app.post("/ask", include_in_schema=True)
def ask_endpoint(req: AskRequest):
    """Search the seed bank with elimination + fruit ranking.

    Apophatic + cataphatic: eliminate misfits with reasons (the
    elimination trail IS the reasoning), then rank survivors by good
    fruit (sealed + unamended + recurring + threaded). If nothing
    survives, capture the question itself as a new seed.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    try:
        from concordance_engine import ask as ask_mod
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"ask module unavailable: {e}")
    try:
        result = ask_mod.ask(
            req.question,
            capture_if_no_survivors=req.capture_if_no_survivors,
            max_survivors=req.max_survivors,
            max_eliminated=req.max_eliminated,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "result": result.to_dict(),
        "rendered": ask_mod.render_ask(result),
    }


# ── /path — standalone model: classify → retrieve → compose ──────────


class PathRequest(BaseModel):
    text: str
    identity_acknowledged: bool = False
    gate_verdicts: Optional[Dict[str, str]] = None  # optional override from external gate engine


@app.post("/path", include_in_schema=True)
def path_endpoint(req: PathRequest):
    """Standalone model: classify a submission and return a structured path.

    Runs: classifier → Scripture retrieval → personal context overlay →
    path composer. Returns a PathResult per spec §7.

    The path is not an answer. It points back to the text and the people
    who should see this with you.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 10_000:
        raise HTTPException(status_code=400, detail="text too long (max 10,000 chars)")

    try:
        from concordance_engine.classifier import classify
        from concordance_engine.scripture_retrieval import retrieve
        from concordance_engine.context_retriever import retrieve_context
        from concordance_engine.path_composer import compose
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"standalone model unavailable: {e}")

    try:
        classification = classify(text)
        retrieval = retrieve(classification.primary_type, text)
        context = retrieve_context(text, classification.primary_type)
        result = compose(classification, retrieval, context, req.gate_verdicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"path composition failed: {e}")

    return result.to_dict()


# ── Community feed (widespread + directly shared with viewer) ──────


class ShareWithRequest(BaseModel):
    recipient: str


@app.get("/community", include_in_schema=True)
def community_feed_endpoint(
    viewer: str = Query("default"),
    limit: int = Query(20, ge=1, le=200),
):
    """The community feed visible to a given viewer.

    Includes shelf-published seeds (widespread; anyone sees) plus
    seeds directly shared with this viewer (private to them).
    Newest first.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    items = _journal.community_feed(viewer=viewer, limit=limit)
    return {
        "viewer": viewer,
        "count": len(items),
        "items": [i.to_dict() for i in items],
    }


@app.post("/journal/{entry_id}/share", include_in_schema=True)
def journal_share_with(entry_id: str, req: ShareWithRequest):
    """Share a seed directly with a recipient. Adds the
    `shared_with:<recipient>` tag — only the recipient's community
    feed shows it. Multiple recipients via repeated calls.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        updated = _journal.share_with(entry_id, recipient=req.recipient)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


@app.delete("/journal/{entry_id}/share/{recipient}", include_in_schema=True)
def journal_unshare_with(entry_id: str, recipient: str):
    """Withdraw a direct share. Seed remains in library; tag removed."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    updated = _journal.unshare_with(entry_id, recipient=recipient)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


# ── Bins (emergent clusters of the user's life) ────────────────────


@app.get("/bins", include_in_schema=True)
def bins_endpoint(min_recurrence: int = Query(3, ge=1, le=20)):
    """Surface emergent bins from the user's library.

    Bins are named by use — anchor / person / action / feeling /
    packet shape — and form when a signal recurs across at least
    `min_recurrence` entries (default 3). Sorted by size descending.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    bins = _journal.infer_bins(min_recurrence=min_recurrence)
    return {
        "count": len(bins),
        "bins": [b.to_dict() for b in bins],
        "rendered": _journal.render_bins(bins),
    }


@app.get("/bins/{bin_id:path}", include_in_schema=True)
def bins_review(bin_id: str):
    """Review one bin in full — signature + every entry's text +
    metadata. Bin ids are kind-prefixed (e.g. `anchor:Mt 5:37`)."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    review = _journal.review_bin(bin_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"no bin {bin_id}")
    return review


# ── Promotion (individual → community → central tier) ──────────────


class PromoteRequest(BaseModel):
    confession: str
    witnesses: List[str] = []
    summary: Optional[str] = None


@app.post("/journal/{entry_id}/promote", include_in_schema=True)
def journal_promote(entry_id: str, req: PromoteRequest):
    """Promote a journal seed to the central seed bank.

    Translates the seed's categorization into a packet, runs the four
    gates, seals to the audit chain on PASS. On REJECT/QUARANTINE,
    surfaces the gate verdicts + reasons (the elimination trail) and
    leaves the seed unchanged.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        result = _journal.promote(
            entry_id,
            confession=req.confession,
            witnesses=list(req.witnesses or []),
            summary=req.summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "result": result.to_dict(),
        "rendered": _journal.render_promotion(result),
    }


# ── Emergence (what the engine sees emerging across recent entries) ─


@app.get("/emergence", include_in_schema=True)
def emergence_endpoint(
    window_days: int = Query(30, ge=1, le=365),
):
    """Surface patterns across recent journal entries — recurring
    anchors, standing tasks, dates, people, action shapes, feelings.

    Per Matt 2026-05-03: "We see what is being created before the
    creator." The engine names patterns the user may not have named
    yet; descriptive only, never directive.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    em = _journal.emergence(window_days=window_days)
    return {
        "emergence": em.to_dict(),
        "rendered": _journal.render_emergence(em),
    }


@app.get("/keeping/log", include_in_schema=True)
def keeping_log(
    since: Optional[float] = Query(None),
    practice: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Read the keeping log (append-only practice observations).
    Optional filters by practice name / timestamp."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    log = _keeping.KeepingLog()
    observations = log.read(since=since, practice=practice)[-limit:]
    return {
        "count": len(observations),
        "observations": [o.to_dict() for o in observations],
    }


# -- Static site (must be last — catches all unmatched paths) ------------
# Serves site/ for all HTML pages, CSS, JS, icons, manifests, etc.
# API routes registered above take priority; this handles everything else.
_SITE_DIR = Path(__file__).parent.parent / "site"
if _SITE_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_SITE_DIR), html=True), name="site")
