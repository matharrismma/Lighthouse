"""Optics domain validator (engineering / physical-substance umbrella)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class OpticsValidator:
    domain = "optics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ov = packet.get("OPT_VERIFY") or {}
        if not ov:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Optics packets must include either OPT_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]
        for fld in ("n1", "n2", "wavelength_m", "aperture_m"):
            if fld in ov:
                try:
                    v = float(ov[fld])
                    if v <= 0:
                        errors.append(f"{fld} must be positive, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {ov[fld]!r}")
        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ov = packet.get("OPT_VERIFY") or {}
        if ov:
            verifiable_keys = ("claimed_theta2_deg", "claimed_thin_lens_consistent",
                               "claimed_magnification", "claimed_diffraction_rad")
            if not any(k in ov for k in verifiable_keys):
                errors.append("OPT_VERIFY block must contain at least one verifiable claim")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Optics packets without OPT_VERIFY must declare artifacts{}")
        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
