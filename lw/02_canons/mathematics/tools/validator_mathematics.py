from __future__ import annotations

from typing import Any, Dict, List


def validate_math_packet(pkt: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    # --- RED layer checks ---
    red = pkt.get("MATH_RED", {}) or {}
    wf = red.get("well_formedness", {}) or {}
    ts = red.get("type_safety", {}) or {}
    di = red.get("definitional_integrity", {}) or {}
    ii = red.get("inference_integrity", {}) or {}

    if not wf.get("symbols_defined", False):
        errors.append("RED: undefined symbols (symbols_defined=false)")
    if not wf.get("quantifiers_scoped", False):
        errors.append("RED: unscoped quantifiers (quantifiers_scoped=false)")
    if not wf.get("domains_declared", False):
        errors.append("RED: missing domains (domains_declared=false)")
    if not ts.get("objects_typed", False):
        errors.append("RED: objects not typed (objects_typed=false)")
    if not ts.get("operations_valid", False):
        errors.append("RED: invalid operations for types (operations_valid=false)")
    if not di.get("no_circular_definitions", True):
        errors.append("RED: circular definitions detected (no_circular_definitions=false)")
    if not di.get("definitions_total", True):
        warnings.append("RED: definitions may be partial/undefined (definitions_total=false)")
    if not ii.get("rules_named", False):
        errors.append("RED: inference rules not named (rules_named=false)")
    if not ii.get("steps_justified", False):
        errors.append("RED: steps not justified (steps_justified=false)")

    # --- FLOOR layer checks (soft unless you add hard rules later) ---
    floor = pkt.get("MATH_FLOOR", {}) or {}
    axioms = floor.get("axioms_selected", []) or []
    if not axioms:
        warnings.append("FLOOR: no axioms_selected provided")

    num = floor.get("numerical_policy", {}) or {}
    if "tolerance" not in num:
        warnings.append("FLOOR: numerical_policy.tolerance not set")
    if num.get("conditioning_reporting") is False:
        warnings.append("FLOOR: conditioning_reporting disabled (may hide instability)")
    if num.get("stability_checks") is False:
        warnings.append("FLOOR: stability_checks disabled (may hide divergence)")

    # --- Project integration check (anchor pattern) ---
    assumptions = (pkt.get("MATH_SETUP", {}) or {}).get("assumptions", []) or []
    has_scripture_anchor = any(
        isinstance(a, dict) and (
            (a.get("class") == "axiom" and "scripture" in (a.get("assumption", "").lower()))
            or ("scripture_anchor" in (a.get("assumption", "").lower()))
        )
        for a in assumptions
    )
    if not has_scripture_anchor:
        warnings.append("Project: Scripture RED anchor missing or not explicit (add MATH_SETUP.assumptions entry).")

    gates_passed: List[str] = []
    if len(errors) == 0:
        gates_passed.extend(["RED", "FLOOR"])

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "gates_passed": gates_passed,
    }


if __name__ == "__main__":
    # Minimal self-test with template-like packet.
    sample = {
        "MATH_SETUP": {
            "assumptions": [
                {"class": "axiom", "assumption": "scripture_anchor: external authority acknowledged (project-level RED anchor)"}
            ]
        },
        "MATH_RED": {
            "well_formedness": {"symbols_defined": True, "quantifiers_scoped": True, "domains_declared": True},
            "type_safety": {"objects_typed": True, "operations_valid": True},
            "definitional_integrity": {"no_circular_definitions": True, "definitions_total": True},
            "inference_integrity": {"rules_named": True, "steps_justified": True},
        },
        "MATH_FLOOR": {"axioms_selected": ["ZFC"], "numerical_policy": {"tolerance": 1e-12, "conditioning_reporting": True, "stability_checks": True}},
    }
    print(validate_math_packet(sample))
