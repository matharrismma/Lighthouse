"""Meteorology domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class MeteorologyValidator:
    domain = "meteorology"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        mv = packet.get("MET_VERIFY") or {}
        if not mv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Meteorology packets must include either MET_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("temperature_c", "temperature_f", "temperature_f_for_wc",
                    "temperature_c_for_es", "wind_speed_mph"):
            if fld in mv:
                try:
                    float(mv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        for fld in ("relative_humidity_pct", "relative_humidity_pct_for_hi"):
            if fld in mv:
                try:
                    v = float(mv[fld])
                    if v <= 0 or v > 100:
                        errors.append(f"{fld} must be in (0, 100], got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        mv = packet.get("MET_VERIFY") or {}
        if mv:
            verifiable = ("claimed_dew_point_c", "claimed_heat_index_f",
                          "claimed_wind_chill_f",
                          "claimed_saturation_vapor_pressure_hpa")
            if not any(k in mv for k in verifiable):
                return [reject("FLOOR", "MET_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Meteorology packets without MET_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
