"""Witness domain validator — meta-axis for sealed records.

Witness packets are unusual: they don't carry a domain claim, they carry
a *testimony* about an already-run verification. RED checks that the
testimony's structural fields are well-typed; FLOOR checks that at least
one verifiable element is present.
"""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class WitnessValidator:
    domain = "witness"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        wv = packet.get("WIT_VERIFY") or {}
        if not wv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Witness packets must include either WIT_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]

        verdicts = wv.get("claimed_gate_verdicts")
        if verdicts is not None and not isinstance(verdicts, list):
            errors.append("claimed_gate_verdicts must be a list")
        results = wv.get("claimed_verifier_results")
        if results is not None and not isinstance(results, list):
            errors.append("claimed_verifier_results must be a list")
        anchors = wv.get("claimed_anchors")
        if anchors is not None and not isinstance(anchors, list):
            errors.append("claimed_anchors must be a list")

        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        wv = packet.get("WIT_VERIFY") or {}
        if wv:
            verifiable = ("claimed_gate_verdicts", "claimed_verifier_results",
                          "claimed_anchors", "declared_no_answer")
            if not any(k in wv for k in verifiable):
                return [reject("FLOOR", "WIT_VERIFY block must contain at least one verifiable element")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Witness packets without WIT_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
