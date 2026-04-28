from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .packet import EngineResult, GateResult, DecisionStatus
from .gates import reject, quarantine, ok
from .domains import load_domain_validator
from . import verifiers as _verifiers

WAIT_WINDOWS = {
    "adapter": 60 * 60,          # 1 hour
    "mesh": 24 * 60 * 60,        # 24 hours
    "canon": 7 * 24 * 60 * 60,   # 7 days
}

HARD_GATES = ("RED", "FLOOR")

@dataclass(frozen=True)
class EngineConfig:
    schema_path: str
    default_scope: str = "adapter"
    run_verifiers: bool = True   # set False to skip computational checks

def _scope_seconds(scope: str) -> int:
    s = (scope or "").lower()
    return WAIT_WINDOWS.get(s, WAIT_WINDOWS["adapter"])

def validate_packet(packet: Dict[str, Any], *, now_epoch: int | None = None, config: EngineConfig) -> EngineResult:
    """
    Deterministic engine:
      - RED: domain attestation checks (validator) + verifier computational checks
      - FLOOR: domain protective checks (validator)
      - BROTHERS: requires witness_count >= required_witnesses
      - GOD: requires elapsed_seconds >= wait_window(scope)

    Verifier MISMATCH or ERROR rejects on RED — the underlying artifact contradicts
    the claim or is malformed, which is a stronger failure than missing attestation.
    """
    gate_results: List[GateResult] = []

    domain = (packet.get("domain") or "").lower()
    dv = load_domain_validator(domain)

    # RED — attestation
    if dv:
        gate_results.extend(dv.validate_red(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "RED"):
            return EngineResult(overall="REJECT", gate_results=gate_results)
    else:
        gate_results.append(ok("RED", {"note": "no domain validator registered"}))

    # RED — verification (actual computation on supplied artifacts)
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

    # FLOOR
    if dv:
        gate_results.extend(dv.validate_floor(packet))
        if any(gr.status == "REJECT" for gr in gate_results if gr.gate == "FLOOR"):
            return EngineResult(overall="REJECT", gate_results=gate_results)
    else:
        gate_results.append(ok("FLOOR", {"note": "no domain validator registered"}))

    # BROTHERS
    required = int(packet.get("required_witnesses") or 0)
    have = int(packet.get("witness_count") or 0)
    if required > 0 and have < required:
        gate_results.append(quarantine("BROTHERS", f"witnesses {have}/{required}"))
        return EngineResult(overall="QUARANTINE", gate_results=gate_results)
    gate_results.append(ok("BROTHERS", {"witnesses": have, "required": required}))

    # GOD
    scope = (packet.get("scope") or config.default_scope)
    wait_s = _scope_seconds(scope)
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
