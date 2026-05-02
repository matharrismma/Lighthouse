from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class NumberTheoryValidator:
    domain = "number_theory"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        nv = packet.get("NUM_VERIFY") or {}
        if not nv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or not claims:
                errors.append("Number-theory packets must include either NUM_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("n_prime", "gcd_a", "gcd_b", "factorial_n", "mod_a", "mod_m"):
            if fld in nv:
                try:
                    int(nv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be an integer, got {nv[fld]!r}")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        nv = packet.get("NUM_VERIFY") or {}
        if nv:
            keys = ("claimed_prime", "claimed_gcd", "claimed_factorial", "claimed_inverse")
            if not any(k in nv for k in keys):
                return [reject("FLOOR", "NUM_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Number-theory packets without NUM_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
