"""Mathematics domain validator — full RED/FLOOR checks from canon.

RED (from mathematics_core.yaml): well-formedness, type safety,
definitional integrity, inference integrity.
FLOOR: axiom selection, numerical policy, scripture anchor.
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult

class MathematicsValidator:
    domain = "mathematics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        red = packet.get("MATH_RED", {}) or {}

        if red:
            wf = red.get("well_formedness", {}) or {}
            ts = red.get("type_safety", {}) or {}
            di = red.get("definitional_integrity", {}) or {}
            ii = red.get("inference_integrity", {}) or {}

            if not wf.get("symbols_defined", False):
                errors.append("undefined symbols (symbols_defined=false)")
            if not wf.get("quantifiers_scoped", False):
                errors.append("unscoped quantifiers")
            if not wf.get("domains_declared", False):
                errors.append("missing domain declarations")
            if not ts.get("objects_typed", False):
                errors.append("objects not typed")
            if not ts.get("operations_valid", False):
                errors.append("operations invalid for types")
            if not di.get("no_circular_definitions", True):
                errors.append("circular definitions detected")
            if not ii.get("rules_named", False):
                errors.append("inference rules not named")
            if not ii.get("steps_justified", False):
                errors.append("proof steps not justified")
        else:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Mathematics packets must include non-empty claims[]")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        floor = packet.get("MATH_FLOOR", {}) or {}

        if floor:
            if not (floor.get("axioms_selected") or []):
                errors.append("no axioms_selected provided")
            num = floor.get("numerical_policy", {}) or {}
            if "tolerance" not in num:
                errors.append("numerical_policy.tolerance not set")
            if num.get("stability_checks") is False:
                errors.append("stability_checks disabled")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Mathematics packets must include artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
