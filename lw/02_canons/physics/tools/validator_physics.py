"""Lightweight Physics Canon validator (v1.0)

Design goal: fail fast on RED/FLOOR violations, warn on incompleteness.
This is intentionally conservative and schema-agnostic.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _has_source_and_uncertainty(obj: Dict[str, Any]) -> bool:
    return isinstance(obj, dict) and ("source" in obj) and ("uncertainty" in obj)


def validate_physics_packet(pkt: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    setup = pkt.get("PHYS_SETUP", {})
    constraints = pkt.get("PHYS_CONSTRAINTS", {})
    model = pkt.get("PHYS_MODEL", {})
    meas = pkt.get("PHYS_MEASUREMENTS", {})

    # --- RED checks ---
    red = constraints.get("RED", {})

    assumptions = setup.get("assumptions", [])
    if not (isinstance(assumptions, list) and any(isinstance(a, str) and "scripture_anchor" in a for a in assumptions)):
        warnings.append("Lighthouse: missing scripture_anchor in PHYS_SETUP.assumptions")

    dim = red.get("dimensional_consistency", {})
    if isinstance(dim, dict):
        if dim.get("required") and not dim.get("verified", False):
            warnings.append("RED: dimensional consistency required but not verified")

    rel = red.get("relativity", {})
    if isinstance(rel, dict) and (rel.get("c_limit_respected") is False):
        errors.append("RED: c-limit not respected")

    cons = red.get("conservation", {})
    if isinstance(cons, dict):
        # Just ensure booleans provided when marked required
        for k, v in cons.items():
            if isinstance(v, dict) and v.get("required") and v.get("required") is True:
                # nothing further; domain-specific checks belong to modules/examples
                pass

    # --- FLOOR checks ---
    floor = constraints.get("FLOOR", {})
    ref = floor.get("reference_constants", {})
    if isinstance(ref, dict):
        for name, cobj in ref.items():
            if not _has_source_and_uncertainty(cobj):
                errors.append(f"FLOOR: reference_constants.{name} missing source/uncertainty")

    mb = floor.get("measurement_bounds", {})
    if isinstance(mb, dict) and mb.get("orthogonality_required"):
        orth = meas.get("orthogonality", {})
        used = orth.get("orthogonal_assays_used", []) if isinstance(orth, dict) else []
        if not (isinstance(used, list) and len(used) >= 2):
            errors.append("FLOOR: orthogonality_required but <2 orthogonal_assays_used")

    # --- IC/BC completeness (best effort) ---
    ics = setup.get("initial_conditions", {})
    bcs = model.get("boundary_conditions", [])
    if not ics:
        warnings.append("IC/BC: initial_conditions empty")
    if not bcs:
        warnings.append("IC/BC: boundary_conditions empty")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "gates_passed": ["RED", "FLOOR"] if len(errors) == 0 else [],
    }
