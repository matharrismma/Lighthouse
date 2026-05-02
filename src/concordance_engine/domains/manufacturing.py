"""Manufacturing domain validator (engineering umbrella sibling)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class ManufacturingValidator:
    domain = "manufacturing"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        mv = packet.get("MFG_VERIFY") or {}

        if not mv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append(
                    "Manufacturing packets must include either MFG_VERIFY{} or non-empty claims[]"
                )
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("dpmo", "sigma", "process_sigma"):
            if fld in mv:
                try:
                    v = float(mv[fld])
                    if v < 0:
                        errors.append(f"{fld} must be non-negative, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {mv[fld]!r}")

        if "tolerances" in mv:
            t = mv["tolerances"]
            if not isinstance(t, (list, tuple)) or not t:
                errors.append("tolerances must be a non-empty list")

        if "usl" in mv and "lsl" in mv:
            try:
                u = float(mv["usl"])
                l = float(mv["lsl"])
                if u <= l:
                    errors.append(f"usl ({u}) must be > lsl ({l})")
            except (TypeError, ValueError):
                pass

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        mv = packet.get("MFG_VERIFY") or {}

        if mv:
            verifiable_keys = ("claimed_sigma", "claimed_ucl", "claimed_cp_capable", "claimed_rss")
            if not any(k in mv for k in verifiable_keys):
                errors.append("MFG_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Manufacturing packets without MFG_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
