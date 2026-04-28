"""Biology canon validator.

Parallel implementation of the engine's biology validator at
01_engine/concordance-engine/src/concordance_engine/domains/biology.py,
provided here so the canon directory is self-contained and can be forked
without dragging in the full engine package.

The canon source of truth is biology_core.yaml. The engine validator and
this validator both read from that canon. If they diverge, the engine is
authoritative for production use; this file mirrors the canon for
documentation and offline reference.

Usage:
    python validator_biology.py            # runs self-test against examples/
    from validator_biology import validate_bio_packet
"""
from __future__ import annotations

from typing import Any, Dict, List


def validate_bio_packet(pkt: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a biology packet against the canon RED and FLOOR constraints."""
    errors: List[str] = []
    warnings: List[str] = []

    red = pkt.get("BIO_RED", {}) or {}
    floor = pkt.get("BIO_FLOOR", {}) or {}

    # ---- RED ----
    if red.get("non_contradiction") is False:
        errors.append("RED: contradictory claims detected (biology_core RED-1).")
    if red.get("conservation_declared") is False:
        errors.append("RED: mass/charge/energy conservation not declared "
                      "(open system requires explicit boundary fluxes).")
    if red.get("second_law_respected") is False:
        errors.append("RED: second-law violation — local order requires entropy export.")
    if red.get("causality_respected") is False:
        errors.append("RED: no mechanism stated for claimed effect; temporal ordering required.")
    if red.get("stoichiometry_balanced") is False:
        errors.append("RED: biochemical stoichiometry not balanced (elemental/charge).")
    if red.get("nonnegativity_respected") is False:
        errors.append("RED: probabilities or information measures violate non-negativity.")
    if red.get("channel_limits_respected") is False:
        errors.append("RED: signaling claim exceeds noise/bandwidth constraints.")

    # ---- FLOOR ----
    ref = floor.get("reference_conditions", {}) or {}
    if ref:
        for k in ("pH", "ionic_strength", "temperature_K"):
            if k not in ref:
                warnings.append(f"FLOOR: reference condition {k} not declared.")

    md = floor.get("measurement_doctrine", {}) or {}
    for required in ("controls_used", "calibrated", "uncertainty_reported", "replicated"):
        if md.get(required) is False:
            errors.append(f"FLOOR: measurement doctrine — {required} is False.")

    orth = floor.get("orthogonality", {}) or {}
    if orth.get("required") is True:
        used = orth.get("orthogonal_assays_used") or red.get("orthogonal_assays_used") or []
        if not isinstance(used, list) or len(used) < 2:
            errors.append(f"FLOOR: orthogonality required but <2 orthogonal_assays_used "
                          f"(got {len(used) if isinstance(used, list) else 0}).")

    if floor.get("replicates_minimum") is not None:
        n = floor.get("replicates")
        if n is None or (isinstance(n, int) and n < 3):
            errors.append("FLOOR: biological replicates n < 3 without justification.")

    if floor.get("intervention_applied") is True:
        if floor.get("viability_bounds_checked") is False:
            errors.append("FLOOR: intervention applied but viability/toxicity bounds not checked.")

    return {
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


# ---- Self-test ----
if __name__ == "__main__":
    import json

    good = {
        "BIO_RED": {
            "non_contradiction": True,
            "conservation_declared": True,
            "second_law_respected": True,
            "causality_respected": True,
            "stoichiometry_balanced": True,
            "nonnegativity_respected": True,
            "channel_limits_respected": True,
            "orthogonal_assays_used": ["qPCR", "western_blot", "imaging"],
        },
        "BIO_FLOOR": {
            "reference_conditions": {"pH": 7.4, "ionic_strength": 0.15, "temperature_K": 310},
            "measurement_doctrine": {"controls_used": True, "calibrated": True,
                                     "uncertainty_reported": True, "replicated": True},
            "orthogonality": {"required": True,
                              "orthogonal_assays_used": ["qPCR", "western_blot"]},
            "replicates_minimum": 3,
            "replicates": 4,
        },
    }
    bad = {
        "BIO_RED": {"non_contradiction": False, "conservation_declared": False},
        "BIO_FLOOR": {"replicates_minimum": 3, "replicates": 1},
    }

    for label, packet in [("good", good), ("bad", bad)]:
        result = validate_bio_packet(packet)
        print(f"{label}: passed={result['passed']}, errors={len(result['errors'])}, "
              f"warnings={len(result['warnings'])}")
        for e in result["errors"][:3]:
            print(f"  E: {e}")
        for w in result["warnings"][:3]:
            print(f"  W: {w}")
