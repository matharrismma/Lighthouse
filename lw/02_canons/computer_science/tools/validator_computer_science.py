"""Computer Science canon validator wrapper.

This is a thin wrapper around the canonical validator at
01_engine/concordance-engine/src/concordance_engine/domains/computer_science.py.
It exists so the canon directory has a runnable tool that matches the
mathematics/physics/biology pattern. The engine package is the source of
truth; this file is the canon-side entrypoint.

Usage:
    python validator_computer_science.py            # runs self-test
    from validator_computer_science import validate_cs_packet
"""
from __future__ import annotations

from typing import Any, Dict, List


def _attest(block: Dict[str, Any], key: str, default: bool = False) -> bool:
    """Read attestation field; missing is treated as default (usually False)."""
    v = block.get(key, default)
    return bool(v) if v is not None else default


def validate_cs_packet(pkt: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a CS packet against the canon RED and FLOOR constraints.

    Mirrors the engine validator at
    concordance_engine.domains.computer_science.ComputerScienceValidator.
    """
    errors: List[str] = []
    warnings: List[str] = []

    red = pkt.get("CS_RED", {}) or {}
    floor = pkt.get("CS_FLOOR", {}) or {}
    complexity = pkt.get("CS_COMPLEXITY", {}) or {}

    # ---- RED ----
    if red.get("termination_proven") is False:
        errors.append("RED: algorithm termination unproven (add loop variant or classify as non-terminating).")
    if red.get("complexity_variable_defined") is False:
        errors.append("RED: complexity claim missing input variable (state what n represents).")
    if complexity and not complexity.get("input_variable") and (complexity.get("time_bound") or complexity.get("space_bound")):
        errors.append("RED: CS_COMPLEXITY block present but input_variable not defined.")
    if red.get("no_undefined_behavior") is False:
        errors.append("RED: undefined behavior present (OOB, null deref, race, type error).")
    if red.get("reduction_direction_stated") is False:
        errors.append("RED: reduction direction not stated (A reduces to B means B is at least as hard as A).")
    if red.get("encoding_bijectivity_stated") is False:
        errors.append("RED: encoding bijectivity not stated (declare injective/surjective/bijective).")
    if red.get("formal_model_specified") is False:
        errors.append("RED: formal language claim without model of computation (specify DFA/PDA/TM/LBA).")
    if red.get("consistency_model_cited") is False:
        errors.append("RED: distributed consistency claim without formal model (cite linearizability/SC/causal/eventual).")

    for d in (pkt.get("diagnostics") or []):
        if isinstance(d, dict):
            diag = str(d.get("diagnosis", "")).upper()
            if diag in ("TERMINATION_UNPROVEN", "UNDEFINED_BEHAVIOR_RISK"):
                errors.append(f"RED diagnostic: {diag} — {d.get('action', '')}")

    if not red and not complexity:
        claims = pkt.get("claims", [])
        if not isinstance(claims, list) or len(claims) == 0:
            warnings.append("CS packet has no CS_RED, CS_COMPLEXITY, or claims[]; nothing to attest.")

    # ---- FLOOR ----
    if floor or complexity:
        if floor.get("input_output_declared") is False:
            errors.append("FLOOR: input/output domains not declared.")
        if floor.get("case_analysis_stated") is False:
            errors.append("FLOOR: complexity case not stated (worst/average/best/amortized).")
        if complexity and not complexity.get("case"):
            errors.append("FLOOR: CS_COMPLEXITY missing case field.")
        if floor.get("space_complexity_stated") is False:
            errors.append("FLOOR: space complexity not stated.")
        if floor.get("proof_technique_named") is False:
            errors.append("FLOOR: correctness proof technique not named.")
        if floor.get("fault_model_declared") is False:
            errors.append("FLOOR: distributed system fault model not declared.")
        if floor.get("memory_model_cited") is False:
            errors.append("FLOOR: concurrent system memory model not cited.")

        for d in (pkt.get("diagnostics") or []):
            if isinstance(d, dict):
                diag = str(d.get("diagnosis", "")).upper()
                if diag in ("COMPLEXITY_UNDERSPECIFIED", "CONSISTENCY_UNSPECIFIED"):
                    errors.append(f"FLOOR diagnostic: {diag} — {d.get('action', '')}")

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
    sample = {
        "CS_RED": {
            "termination_proven": True,
            "complexity_variable_defined": True,
            "no_undefined_behavior": True,
            "reduction_direction_stated": True,
            "encoding_bijectivity_stated": True,
            "formal_model_specified": True,
            "consistency_model_cited": True,
        },
        "CS_FLOOR": {
            "input_output_declared": True,
            "case_analysis_stated": True,
            "space_complexity_stated": True,
            "proof_technique_named": True,
            "fault_model_declared": True,
            "memory_model_cited": True,
        },
        "CS_COMPLEXITY": {
            "input_variable": "n = number of input elements",
            "case": "worst",
            "time_bound": "O(n log n)",
            "space_bound": "O(n)",
        },
    }
    print(validate_cs_packet(sample))

    bad = {"CS_RED": {"termination_proven": False, "complexity_variable_defined": False}}
    print(validate_cs_packet(bad))
