from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class GeographyValidator:
    domain = "geography"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        gv = packet.get("GEO_LOC_VERIFY") or {}
        if not gv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or not claims:
                errors.append("Geography packets must include either GEO_LOC_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        # Lat fields must be in [-90, 90]; lon fields in [-180, 180].
        for fld in ("lat", "lat1", "lat2"):
            if fld in gv:
                try:
                    v = float(gv[fld])
                    if not (-90 <= v <= 90):
                        errors.append(f"{fld} must be in [-90, 90], got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        for fld in ("lon", "lon1", "lon2", "longitude_for_utm"):
            if fld in gv:
                try:
                    v = float(gv[fld])
                    if not (-180 <= v <= 180):
                        errors.append(f"{fld} must be in [-180, 180], got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        gv = packet.get("GEO_LOC_VERIFY") or {}
        if gv:
            keys = ("claimed_coords_valid", "claimed_distance_km",
                    "claimed_bearing_deg", "claimed_utm_zone")
            if not any(k in gv for k in keys):
                return [reject("FLOOR", "GEO_LOC_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Geography packets without GEO_LOC_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
