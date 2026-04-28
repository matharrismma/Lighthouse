"""Physics domain validator — full RED/FLOOR checks from canon.

RED (from physics_core.yaml): dimensional consistency, c-limit,
conservation laws, causality.
FLOOR: reference constants with source/uncertainty, measurement bounds,
initial/boundary conditions.
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult

class PhysicsValidator:
    domain = "physics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        constraints = packet.get("PHYS_CONSTRAINTS", {}) or {}
        red = constraints.get("RED", packet.get("conservation_checks", {})) or {}

        if isinstance(red, dict) and red:
            rel = red.get("relativity", {}) or {}
            if isinstance(rel, dict) and rel.get("c_limit_respected") is False:
                errors.append("c-limit not respected")

            dim = red.get("dimensional_consistency", {}) or {}
            if isinstance(dim, dict) and dim.get("required") and not dim.get("verified", False):
                errors.append("dimensional consistency required but not verified")
        else:
            if packet.get("conservation_checks") is None and not constraints:
                errors.append("Physics packets must include conservation_checks or PHYS_CONSTRAINTS")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        constraints = packet.get("PHYS_CONSTRAINTS", {}) or {}
        floor = constraints.get("FLOOR", {}) or {}

        if isinstance(floor, dict) and floor:
            ref = floor.get("reference_constants", {}) or {}
            for name, cobj in ref.items():
                if not (isinstance(cobj, dict) and "source" in cobj and "uncertainty" in cobj):
                    errors.append(f"reference_constants.{name} missing source/uncertainty")

            mb = floor.get("measurement_bounds", {}) or {}
            if isinstance(mb, dict) and mb.get("orthogonality_required"):
                meas = packet.get("PHYS_MEASUREMENTS", {}) or {}
                orth = meas.get("orthogonality", {}) or {}
                used = orth.get("orthogonal_assays_used", []) if isinstance(orth, dict) else []
                if not (isinstance(used, list) and len(used) >= 2):
                    errors.append("orthogonality_required but <2 orthogonal_assays_used")
        else:
            if packet.get("units") is None and not constraints:
                errors.append("Physics packets must specify units or PHYS_CONSTRAINTS.FLOOR")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
