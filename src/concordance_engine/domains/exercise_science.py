"""Exercise science domain validator (biology umbrella sibling)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class ExerciseScienceValidator:
    domain = "exercise_science"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ev = packet.get("EX_VERIFY") or {}

        if not ev:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append(
                    "Exercise-science packets must include either EX_VERIFY{} or non-empty claims[]"
                )
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("weight_kg", "duration_hours", "age_years",
                    "resting_hr", "claimed_kcal",
                    "claimed_max_hr", "claimed_met"):
            if fld in ev:
                try:
                    float(ev[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {ev[fld]!r}")

        for fld in ("intensity_low", "intensity_high"):
            if fld in ev:
                try:
                    v = float(ev[fld])
                    if not (0.0 <= v <= 1.0):
                        errors.append(f"{fld} must be a fraction in [0, 1], got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {ev[fld]!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ev = packet.get("EX_VERIFY") or {}

        if ev:
            verifiable_keys = (
                "claimed_kcal", "claimed_max_hr",
                "claimed_zone_low_bpm", "claimed_met",
            )
            if not any(k in ev for k in verifiable_keys):
                errors.append("EX_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Exercise-science packets without EX_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
