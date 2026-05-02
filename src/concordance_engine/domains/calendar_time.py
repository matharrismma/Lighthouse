"""Calendar / time domain validator (cross-cutting infrastructure)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class CalendarTimeValidator:
    domain = "calendar_time"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        cv = packet.get("CAL_VERIFY") or {}

        if not cv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Calendar/time packets must include either CAL_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        if "year" in cv:
            try:
                int(cv["year"])
            except (TypeError, ValueError):
                errors.append(f"year must be an integer, got {cv['year']!r}")
        if "duration_seconds" in cv:
            try:
                float(cv["duration_seconds"])
            except (TypeError, ValueError):
                errors.append(f"duration_seconds must be numeric, got {cv['duration_seconds']!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        cv = packet.get("CAL_VERIFY") or {}

        if cv:
            verifiable_keys = (
                "claimed_leap", "claimed_iso8601_valid",
                "claimed_day_of_week", "claimed_end_iso",
            )
            if not any(k in cv for k in verifiable_keys):
                errors.append("CAL_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Calendar/time packets without CAL_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
