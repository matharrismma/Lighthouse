"""Photography domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class PhotographyValidator:
    domain = "photography"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        pv = packet.get("PHOTO_VERIFY") or {}
        if not pv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Photography packets must include either PHOTO_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("f_number", "shutter_seconds",
                    "focal_length_mm", "sensor_dimension_mm",
                    "focal_length_mm_for_h", "f_number_for_h",
                    "circle_of_confusion_mm"):
            if fld in pv:
                try:
                    v = float(pv[fld])
                    if v <= 0:
                        errors.append(f"{fld} must be positive, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        for fld in ("settings_a", "settings_b"):
            if fld in pv:
                v = pv[fld]
                if not (isinstance(v, (list, tuple)) and len(v) == 2):
                    errors.append(f"{fld} must be a [f_number, shutter_s] pair")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        pv = packet.get("PHOTO_VERIFY") or {}
        if pv:
            verifiable = ("claimed_exposure_value", "claimed_equivalent",
                          "claimed_angle_of_view_deg",
                          "claimed_hyperfocal_distance_m")
            if not any(k in pv for k in verifiable):
                return [reject("FLOOR", "PHOTO_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Photography packets without PHOTO_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
