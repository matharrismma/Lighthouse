"""Geometry domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class GeometryValidator:
    domain = "geometry"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        gv = packet.get("GEOM_VERIFY") or {}
        if not gv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Geometry packets must include either GEOM_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("tri_a", "tri_b", "tri_c", "pyth_a", "pyth_b", "pyth_c",
                    "circle_radius", "claimed_circle_area",
                    "claimed_circle_circumference", "claimed_interior_angle_sum_deg"):
            if fld in gv:
                try:
                    float(gv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        if "polygon_n" in gv:
            try:
                n = int(gv["polygon_n"])
                if n < 3:
                    errors.append(f"polygon_n must be >= 3, got {n}")
            except (TypeError, ValueError):
                errors.append("polygon_n must be an integer")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        gv = packet.get("GEOM_VERIFY") or {}
        if gv:
            verifiable = ("claimed_valid_triangle", "claimed_right_triangle",
                          "claimed_interior_angle_sum_deg",
                          "claimed_circle_area", "claimed_circle_circumference")
            if not any(k in gv for k in verifiable):
                return [reject("FLOOR", "GEOM_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Geometry packets without GEOM_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
