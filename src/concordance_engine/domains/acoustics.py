"""Acoustics domain validator (engineering / physical-substance umbrella)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class AcousticsValidator:
    domain = "acoustics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("ACOUS_VERIFY") or {}
        if not av:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Acoustics packets must include either ACOUS_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]
        for fld in ("speed_of_wave", "frequency_hz", "wavelength_m",
                    "value", "reference",
                    "f_source_hz", "speed_medium_mps", "fundamental_hz"):
            if fld in av:
                try:
                    v = float(av[fld])
                    if v <= 0:
                        errors.append(f"{fld} must be positive, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {av[fld]!r}")
        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("ACOUS_VERIFY") or {}
        if av:
            verifiable_keys = ("speed_of_wave", "claimed_db",
                               "claimed_f_observed_hz", "claimed_harmonic_hz")
            if not any(k in av for k in verifiable_keys):
                errors.append("ACOUS_VERIFY block must contain at least one verifiable claim")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Acoustics packets without ACOUS_VERIFY must declare artifacts{}")
        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
