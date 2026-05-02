"""Hydrology domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class HydrologyValidator:
    domain = "hydrology"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        hv = packet.get("HYD_VERIFY") or {}
        if not hv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Hydrology packets must include either HYD_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("manning_n", "hydraulic_radius_m", "slope",
                    "darcy_K_m_s", "hydraulic_gradient",
                    "runoff_coefficient", "rainfall_intensity", "drainage_area",
                    "elevation_m", "pressure_pa", "velocity_m_s",
                    "fluid_density_kg_m3"):
            if fld in hv:
                try:
                    float(hv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        if "runoff_coefficient" in hv:
            try:
                C = float(hv["runoff_coefficient"])
                if not (0 <= C <= 1):
                    errors.append(f"runoff_coefficient must be in [0, 1], got {C}")
            except (TypeError, ValueError):
                pass
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        hv = packet.get("HYD_VERIFY") or {}
        if hv:
            verifiable = ("claimed_velocity_m_s", "claimed_darcy_velocity_m_s",
                          "claimed_runoff", "claimed_total_head_m")
            if not any(k in hv for k in verifiable):
                return [reject("FLOOR", "HYD_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Hydrology packets without HYD_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
