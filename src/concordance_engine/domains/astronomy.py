"""Astronomy domain validator (engineering / physical-substance umbrella)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class AstronomyValidator:
    domain = "astronomy"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("ASTRO_VERIFY") or {}

        if not av:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Astronomy packets must include either ASTRO_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("orbital_period_years", "semi_major_axis_au",
                    "mass_1_kg", "mass_2_kg", "separation_m",
                    "parallax_arcsec", "apparent_magnitude",
                    "absolute_magnitude", "claimed_distance_parsec",
                    "claimed_gravitational_force_N"):
            if fld in av:
                try:
                    v = float(av[fld])
                    # Negative ok for magnitudes; positive required elsewhere.
                    if fld not in ("apparent_magnitude", "absolute_magnitude") and v <= 0:
                        errors.append(f"{fld} must be positive, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {av[fld]!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("ASTRO_VERIFY") or {}

        if av:
            verifiable_keys = (
                "claimed_kepler_consistent",
                "claimed_gravitational_force_N",
                "claimed_distance_parsec",
            )
            if not any(k in av for k in verifiable_keys):
                errors.append("ASTRO_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Astronomy packets without ASTRO_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
