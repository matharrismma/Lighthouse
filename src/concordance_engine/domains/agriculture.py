"""Agriculture domain validator — RED/FLOOR for the AG_VERIFY block.

RED: hardiness zone identifiers must match the USDA pattern; soil pH
must be in physical range; stocking density must be non-negative.
FLOOR: the packet either declares an AG_VERIFY block with at least
one verifiable claim or attaches reference artifacts.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


_VALID_ZONE = re.compile(r"^([1-9]|1[0-3])[ab]?$")


class AgricultureValidator:
    domain = "agriculture"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("AG_VERIFY") or {}

        if not av:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Agriculture packets must include either AG_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        if "claimed_zone" in av:
            z = str(av["claimed_zone"]).lower()
            if not _VALID_ZONE.match(z):
                errors.append(
                    f"claimed_zone {av['claimed_zone']!r} is not a valid USDA hardiness zone "
                    f"(expected '1a' through '13b')"
                )
        if "soil_ph" in av:
            try:
                ph = float(av["soil_ph"])
                if not (0.0 <= ph <= 14.0):
                    errors.append(f"soil_ph must be in [0, 14], got {ph}")
            except (TypeError, ValueError):
                errors.append(f"soil_ph must be numeric, got {av['soil_ph']!r}")
        if "stocking_per_acre" in av:
            try:
                per = float(av["stocking_per_acre"])
                if per < 0:
                    errors.append(f"stocking_per_acre cannot be negative ({per})")
            except (TypeError, ValueError):
                errors.append(f"stocking_per_acre must be numeric, got {av['stocking_per_acre']!r}")
        if "rotation" in av and not isinstance(av["rotation"], (list, tuple)):
            errors.append(f"rotation must be a list, got {type(av['rotation']).__name__}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        av = packet.get("AG_VERIFY") or {}

        if av:
            verifiable_keys = (
                "claimed_zone", "soil_ph", "rotation", "stocking_per_acre",
            )
            if not any(k in av for k in verifiable_keys):
                errors.append("AG_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
            # Paired-field requirements
            if "claimed_zone" in av and "crop" not in av:
                errors.append("AG_VERIFY.claimed_zone requires a sibling 'crop' field")
            if "soil_ph" in av and "crop" not in av:
                errors.append("AG_VERIFY.soil_ph requires a sibling 'crop' field")
            if "stocking_per_acre" in av and "animal" not in av:
                errors.append("AG_VERIFY.stocking_per_acre requires a sibling 'animal' field")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Agriculture packets without AG_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
