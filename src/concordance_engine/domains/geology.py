"""Geology domain validator."""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class GeologyValidator:
    domain = "geology"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        gv = packet.get("GEO_VERIFY") or {}
        if not gv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Geology packets must include either GEO_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("isotope_half_life_years", "elapsed_years", "initial_amount"):
            if fld in gv:
                try:
                    v = float(gv[fld])
                    if v < 0 and fld != "initial_amount":
                        errors.append(f"{fld} must be non-negative")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        for fld in ("harder_mineral_mohs", "softer_mineral_mohs"):
            if fld in gv:
                try:
                    v = float(gv[fld])
                    if not (1 <= v <= 10):
                        errors.append(f"{fld} must be in Mohs range 1-10, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        gv = packet.get("GEO_VERIFY") or {}
        if gv:
            keys = ("claimed_remaining_amount", "claimed_can_scratch", "claimed_amplitude_ratio")
            if not any(k in gv for k in keys):
                return [reject("FLOOR", "GEO_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Geology packets without GEO_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
