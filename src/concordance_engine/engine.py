from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .packet import EngineResult, GateResult, DecisionStatus
from .gates import reject, quarantine, ok
from .domains import load_domain_validator
from . import verifiers as _verifiers

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


def validate_packet(packet, *, now_epoch=None, config):
    """Run RED, FLOOR, BROTHERS, GOD gates. See domain doc."""
    gate_results = []

    packet = _normalize_governance_packet(packet)

    domain = (packet.get("domain") or "").lower()
    dv = load_domain_validator(domain)

    if dv:
        gate_results.extend(dv.validate_red(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "RED"):
            return EngineResult(overall="REJECT", gate_results=gate_results)
    else:
        gate_results.append(ok("RED", {"note": "no domain validator registered"}))

    if config.run_verifiers:
        ver_results = _verifiers.run_for_domain(domain, packet)
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
            return EngineResult(overall="REJECT", gate_results=gate_results)
        if ver_passes:
            gate_results.append(ok(
                "RED",
                {"verified": [f"{v.name}: {v.detail}" for v in ver_passes],
                 "not_applicable": [v.name for v in ver_na]},
            ))

    if dv:
        gate_results.extend(dv.validate_floor(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "FLOOR"):
            return EngineResult(overall="REJECT", gate_results=gate_results)
    else:
        gate_results.append(ok("FLOOR", {"note": "no domain validator registered"}))

    required = int(packet.get("required_witnesses") or 0)
    have = int(packet.get("witness_count") or 0)
    if required > 0 and have < required:
        gate_results.append(quarantine("BROTHERS", f"witnesses {have}/{required}"))
        return EngineResult(overall="QUARANTINE", gate_results=gate_results)
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
        return EngineResult(overall="QUARANTINE", gate_results=gate_results)
    if elapsed < wait_s:
        gate_results.append(quarantine("GOD", f"wait {elapsed}/{wait_s} seconds"))
        return EngineResult(overall="QUARANTINE", gate_results=gate_results)

    gate_results.append(ok("GOD", {"elapsed": elapsed, "required": wait_s}))
    return EngineResult(overall="PASS", gate_results=gate_results)
