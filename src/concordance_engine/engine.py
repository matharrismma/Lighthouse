from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path

from .packet import EngineResult, GateResult, DecisionStatus
from .gates import reject, quarantine, ok
from .domains import load_domain_validator
from .verifiers.base import VerifierResult
from . import verifiers as _verifiers
from .witness_record import (
    WitnessRecord, Anchor, ClosestCase, axis_coords_for, build_record,
)
from .validate import load_schema, validate_against_schema

WAIT_WINDOWS = {
    "adapter": 60 * 60,
    "mesh": 24 * 60 * 60,
    "canon": 7 * 24 * 60 * 60,
}

HARD_GATES = ("RED", "FLOOR")

_GOVERNANCE_DOMAINS = {"governance", "business", "household", "education", "church"}

_DP_TRIGGER_FIELDS = (
    "red_items", "floor_items", "way_path", "execution_steps", "witnesses",
)
_DP_ALL_FIELDS = _DP_TRIGGER_FIELDS + (
    "title", "scope", "scripture_anchors", "wait_window_seconds",
)


@dataclass(frozen=True)
class EngineConfig:
    schema_path: str
    default_scope: str = "adapter"
    run_verifiers: bool = True
    # When True, the engine validates packets against the JSON schema
    # before running gates. Default-on for the sealed-record path
    # (validate_and_seal); opt-out via skip_schema_validation=True for
    # callers that have already validated upstream (e.g. CLI's
    # `validate` subcommand, tests with deliberately-malformed packets,
    # MCP server falling back from the hosted API).
    skip_schema_validation: bool = False


# Cached default schema path: the bundled schema at <repo>/schema/packet.schema.json.
# Resolved once at import time so each call doesn't re-walk parents[2].
_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schema" / "packet.schema.json"
)


# Memoized schema load — the file rarely changes within a process.
_LOADED_SCHEMA: Dict[str, Any] | None = None


def _get_schema(config: EngineConfig) -> Dict[str, Any] | None:
    """Resolve the schema for validation. Returns None if no schema is
    configured or the file isn't present (graceful degradation —
    validation is best-effort for callers who haven't pinned a schema).
    """
    global _LOADED_SCHEMA
    if _LOADED_SCHEMA is not None:
        return _LOADED_SCHEMA
    candidate = config.schema_path or str(_DEFAULT_SCHEMA_PATH)
    if not candidate:
        return None
    try:
        _LOADED_SCHEMA = load_schema(Path(candidate))
        return _LOADED_SCHEMA
    except (OSError, ValueError):
        return None


def _scope_seconds(scope):
    s = (scope or "").lower()
    return WAIT_WINDOWS.get(s, WAIT_WINDOWS["adapter"])


def _normalize_governance_packet(packet):
    """Auto-wrap flat governance packets so verifier sees DECISION_PACKET.
    Synthesizes ``text`` for keyword scan and derives ``witness_count`` if absent.
    Returns a new dict; does not mutate input.
    """
    domain = (packet.get("domain") or "").lower()
    if domain not in _GOVERNANCE_DOMAINS:
        return packet
    out = dict(packet)
    if "DECISION_PACKET" not in out and any(f in out for f in _DP_TRIGGER_FIELDS):
        out["DECISION_PACKET"] = {f: out[f] for f in _DP_ALL_FIELDS if f in out}
    if "witness_count" not in out:
        wits = out.get("witnesses")
        if wits is None and isinstance(out.get("DECISION_PACKET"), dict):
            wits = out["DECISION_PACKET"].get("witnesses")
        if isinstance(wits, list):
            out["witness_count"] = len(wits)
    if not out.get("text") and not out.get("description"):
        dp = out.get("DECISION_PACKET") or {}
        chunks = []
        if dp.get("title"):
            chunks.append(str(dp["title"]))
        if dp.get("way_path"):
            chunks.append(str(dp["way_path"]))
        for step in dp.get("execution_steps") or []:
            chunks.append(str(step))
        for item in dp.get("red_items") or []:
            chunks.append(str(item))
        for item in dp.get("floor_items") or []:
            chunks.append(str(item))
        if chunks:
            out["text"] = " ".join(chunks)
    return out


def _run_validation(
    packet: Dict[str, Any],
    *,
    now_epoch: Optional[int],
    config: EngineConfig,
) -> Tuple[List[GateResult], Tuple[VerifierResult, ...], DecisionStatus]:
    """Run RED → FLOOR → BROTHERS → GOD plus verifier dispatch, returning
    the gate verdicts, the verifier results, and the overall status.

    Internal helper shared by `validate_packet` (which keeps the legacy
    `EngineResult` shape) and `validate_and_seal` (which packs into a
    `WitnessRecord`). Both surfaces walk the same gates; only the return
    shape differs.

    Schema validation runs before any gate fires (unless explicitly
    skipped via config). A schema failure is a structural REJECT — the
    packet doesn't even have a well-formed shape, so the four gates
    don't get a chance to opine.
    """
    gate_results: List[GateResult] = []
    verifier_results: List[VerifierResult] = []

    if not config.skip_schema_validation:
        schema = _get_schema(config)
        if schema is not None:
            try:
                validate_against_schema(packet, schema)
            except Exception as e:  # jsonschema.ValidationError or ValueError
                # Schema failure surfaces as a RED reject before the
                # domain validator gets a turn. The reason carries the
                # validation error message verbatim for the human to
                # see what's malformed.
                gate_results.append(reject(
                    "RED", f"schema validation failed: {e}",
                    details={"validation_error": str(e)},
                ))
                return gate_results, tuple(verifier_results), "REJECT"

    packet = _normalize_governance_packet(packet)

    domain = (packet.get("domain") or "").lower()
    dv = load_domain_validator(domain)

    if dv:
        gate_results.extend(dv.validate_red(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "RED"):
            return gate_results, tuple(verifier_results), "REJECT"
    else:
        gate_results.append(ok("RED", {"note": "no domain validator registered"}))

    if config.run_verifiers:
        ver_results = _verifiers.run_for_domain(domain, packet)
        verifier_results.extend(ver_results)
        ver_failures = [v for v in ver_results if v.failed]
        ver_passes = [v for v in ver_results if v.passed]
        ver_na = [v for v in ver_results if not v.applicable]
        if ver_failures:
            reasons = [f"{v.name}: {v.detail}" for v in ver_failures]
            gate_results.append(reject(
                "RED",
                *reasons,
                details={
                    "verifier_failures": [v.__dict__ for v in ver_failures],
                    "verifier_passes": [v.__dict__ for v in ver_passes],
                },
            ))
            return gate_results, tuple(verifier_results), "REJECT"
        if ver_passes:
            gate_results.append(ok(
                "RED",
                {"verified": [f"{v.name}: {v.detail}" for v in ver_passes],
                 "not_applicable": [v.name for v in ver_na]},
            ))

    if dv:
        gate_results.extend(dv.validate_floor(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "FLOOR"):
            return gate_results, tuple(verifier_results), "REJECT"
    else:
        gate_results.append(ok("FLOOR", {"note": "no domain validator registered"}))

    required = int(packet.get("required_witnesses") or 0)
    have = int(packet.get("witness_count") or 0)
    if required > 0 and have < required:
        gate_results.append(quarantine("BROTHERS", f"witnesses {have}/{required}"))
        return gate_results, tuple(verifier_results), "QUARANTINE"
    gate_results.append(ok("BROTHERS", {"witnesses": have, "required": required}))

    scope = (packet.get("scope") or config.default_scope)
    try:
        packet_wait = int(packet.get("wait_window_seconds") or 0)
    except (TypeError, ValueError):
        packet_wait = 0
    wait_s = max(_scope_seconds(scope), packet_wait)
    created = int(packet.get("created_epoch") or 0)
    if now_epoch is None:
        import time
        now_epoch = int(time.time())
    elapsed = max(0, now_epoch - created)
    if created == 0:
        gate_results.append(quarantine("GOD", "created_epoch missing"))
        return gate_results, tuple(verifier_results), "QUARANTINE"
    if elapsed < wait_s:
        gate_results.append(quarantine("GOD", f"wait {elapsed}/{wait_s} seconds"))
        return gate_results, tuple(verifier_results), "QUARANTINE"

    gate_results.append(ok("GOD", {"elapsed": elapsed, "required": wait_s}))
    return gate_results, tuple(verifier_results), "PASS"


def validate_packet(packet, *, now_epoch=None, config) -> EngineResult:
    """Run RED, FLOOR, BROTHERS, GOD gates. See domain doc.

    Returns an `EngineResult` with overall status + gate verdicts. For
    the canonical sealed-record shape (with verifier results, anchors,
    and grid coordinates first-class), use `validate_and_seal`.
    """
    gate_results, _verifier_results, overall = _run_validation(
        packet, now_epoch=now_epoch, config=config
    )
    return EngineResult(overall=overall, gate_results=gate_results)


def validate_and_seal(
    packet: Dict[str, Any],
    *,
    now_epoch: Optional[int] = None,
    config: EngineConfig,
    anchors: Tuple[Anchor, ...] = (),
    closest_case: Optional[ClosestCase] = None,
    packet_id: Optional[str] = None,
) -> WitnessRecord:
    """Run the four gates and produce a sealed `WitnessRecord`.

    This is the canonical entry point both audiences (agents and humans)
    consume. The record carries every gate verdict, every verifier
    result, anchors with source-hierarchy `layer`, the packet's
    coordinates on the dimensional scaffold, and an optional
    closest-case overlay — but no fabricated answer field. The
    `witness` verifier's `no_fabricated_answer` check enforces that
    invariant against any record sealed here.

    Anchors and closest_case are passed in by the caller because their
    sources (the user's citations, the Evidence Ledger lookup) live
    outside this engine. The engine fills in everything else.
    """
    gate_results, verifier_results, overall = _run_validation(
        packet, now_epoch=now_epoch, config=config
    )
    # Defensive: schema validation might have rejected on a non-string
    # `domain`, in which case axis_coords lookup would crash. When the
    # packet is malformed we just don't fill in axis_coords.
    domain_raw = packet.get("domain") if isinstance(packet, dict) else None
    domain = domain_raw.lower() if isinstance(domain_raw, str) else ""
    return WitnessRecord(
        overall=overall,
        gate_results=tuple(gate_results),
        verifier_results=verifier_results,
        anchors=tuple(anchors),
        axis_coords=axis_coords_for(domain),
        closest_case=closest_case,
        packet_id=packet_id,
    )
