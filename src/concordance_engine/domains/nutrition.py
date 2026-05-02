"""Nutrition domain validator (biology umbrella sibling)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class NutritionValidator:
    domain = "nutrition"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        nv = packet.get("NUT_VERIFY") or {}

        if not nv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Nutrition packets must include either NUT_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("carb_g", "protein_g", "fat_g", "alcohol_g",
                    "intake_mg", "intake_kcal", "expenditure_kcal",
                    "weight_kg", "height_m"):
            if fld in nv:
                try:
                    v = float(nv[fld])
                    if v < 0 and fld not in ("claimed_balance_kcal",):
                        errors.append(f"{fld} cannot be negative ({v})")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {nv[fld]!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        nv = packet.get("NUT_VERIFY") or {}

        if nv:
            verifiable_keys = (
                "calories_claimed", "claimed_status",
                "claimed_balance_kcal", "claimed_bmi_class",
            )
            if not any(k in nv for k in verifiable_keys):
                errors.append("NUT_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Nutrition packets without NUT_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
