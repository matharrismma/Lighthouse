"""Information theory domain validator."""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class InformationTheoryValidator:
    domain = "information_theory"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        iv = packet.get("INFO_VERIFY") or {}
        if not iv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Info-theory packets must include either INFO_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        if "probabilities" in iv:
            ps = iv["probabilities"]
            if not isinstance(ps, (list, tuple)) or not ps:
                errors.append("probabilities must be a non-empty list")
            else:
                for p in ps:
                    try:
                        v = float(p)
                        if v < 0 or v > 1:
                            errors.append(f"each probability must be in [0, 1], got {v}")
                    except (TypeError, ValueError):
                        errors.append("probabilities must be numeric")
        if "bsc_error_rate" in iv:
            try:
                v = float(iv["bsc_error_rate"])
                if not (0 <= v <= 1):
                    errors.append(f"bsc_error_rate must be in [0, 1], got {v}")
            except (TypeError, ValueError):
                errors.append("bsc_error_rate must be numeric")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        iv = packet.get("INFO_VERIFY") or {}
        if iv:
            keys = ("claimed_entropy_bits", "claimed_capacity_bits", "claimed_hamming")
            if not any(k in iv for k in keys):
                return [reject("FLOOR", "INFO_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Info-theory packets without INFO_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
