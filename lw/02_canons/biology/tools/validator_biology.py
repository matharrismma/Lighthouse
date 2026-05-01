"""Biology canon validator.

Parallel implementation of the engine's biology validator at
01_engine/concordance-engine/src/concordance_engine/domains/biology.py,
provided here so the canon directory is self-contained and can be forked
without dragging in the full engine package.

The canon source of truth is biology_core.yaml and modules/systems_biology_control.yaml.
The engine validator and this validator both read from that canon. If they diverge,
the engine is authoritative for production use; this file mirrors the canon for
documentation and offline reference.

Includes BIO_CONTROL block validation for nested health control systems.

Usage:
    python validator_biology.py            # runs self-test against examples/
    from validator_biology import validate_bio_packet
"""
from __future__ import annotations

from typing import Any, Dict, List

_VALID_FAILURE_MODES = {
    "setpoint_drift",
    "loop_saturation",
    "compensation_collapse",
    "cross_layer_override",
    "sensor_failure",
}

_LAYER_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5, "L6": 6}


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

    # ---- BIO_CONTROL (nested health control systems) ----
    ctrl = pkt.get("BIO_CONTROL", {}) or {}
    if ctrl:
        failure_mode = str(ctrl.get("failure_mode", "")).lower()
        failure_layer = str(ctrl.get("failure_layer", "")).upper()
        intervention_layers = [str(l).upper() for l in ctrl.get("intervention_layers", [])]

        # Taxonomy check
        if failure_mode and failure_mode not in _VALID_FAILURE_MODES:
            errors.append(
                f"BIO_CONTROL: unknown failure_mode '{failure_mode}'. "
                f"Must be one of: {sorted(_VALID_FAILURE_MODES)}."
            )

        # cross_layer_override requires upper_layer_driver_addressed
        if failure_mode == "cross_layer_override":
            if ctrl.get("upper_layer_driver_addressed") is not True:
                errors.append(
                    "BIO_CONTROL: cross_layer_override declared but "
                    "upper_layer_driver_addressed is not True. "
                    "The upper-layer driver must be explicitly addressed."
                )

        # setpoint_drift requires mechanism
        if failure_mode == "setpoint_drift":
            if ctrl.get("setpoint_shift_mechanism_stated") is not True:
                errors.append(
                    "BIO_CONTROL: setpoint_drift declared but "
                    "setpoint_shift_mechanism_stated is not True. "
                    "Identify the biological mechanism (e.g., RAAS, leptin resistance)."
                )

        # sensor_failure requires recalibration plan
        if failure_mode == "sensor_failure":
            if ctrl.get("sensor_recalibration_plan") is not True:
                errors.append(
                    "BIO_CONTROL: sensor_failure declared but "
                    "sensor_recalibration_plan is not True. "
                    "Without restoring the sensor, the loop cannot close."
                )

        # Layer match: at least one intervention >= failure layer
        if failure_layer and intervention_layers and failure_layer in _LAYER_ORDER:
            fl_rank = _LAYER_ORDER[failure_layer]
            il_ranks = [_LAYER_ORDER.get(il, 0) for il in intervention_layers]
            if il_ranks and max(il_ranks) < fl_rank:
                errors.append(
                    f"BIO_CONTROL: all intervention layers {intervention_layers} are below "
                    f"failure layer {failure_layer}. "
                    f"At least one intervention must target {failure_layer} or above."
                )
        elif failure_layer and failure_layer not in _LAYER_ORDER:
            warnings.append(
                f"BIO_CONTROL: unknown failure_layer '{failure_layer}'. Must be L1\u2013L6."
            )

    return {
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


# ---- Self-test ----
if __name__ == "__main__":
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

    # BIO_CONTROL: good — cross_layer_override properly addressed
    good_ctrl = {
        "BIO_CONTROL": {
            "failure_mode": "cross_layer_override",
            "failure_layer": "L4",
            "intervention_layers": ["L3", "L4", "L5"],
            "upper_layer_driver_addressed": True,
        }
    }

    # BIO_CONTROL: bad — cross_layer_override without upper driver addressed
    bad_ctrl_no_upper = {
        "BIO_CONTROL": {
            "failure_mode": "cross_layer_override",
            "failure_layer": "L4",
            "intervention_layers": ["L1", "L2"],
            "upper_layer_driver_addressed": False,
        }
    }

    # BIO_CONTROL: bad — setpoint_drift without mechanism
    bad_ctrl_setpoint = {
        "BIO_CONTROL": {
            "failure_mode": "setpoint_drift",
            "failure_layer": "L3",
            "intervention_layers": ["L3", "L4"],
            "setpoint_shift_mechanism_stated": False,
        }
    }

    cases = [
        ("good", good),
        ("bad", bad),
        ("good_ctrl", good_ctrl),
        ("bad_ctrl_no_upper", bad_ctrl_no_upper),
        ("bad_ctrl_setpoint", bad_ctrl_setpoint),
    ]

    for label, packet in cases:
        result = validate_bio_packet(packet)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {label}: errors={len(result['errors'])}, "
              f"warnings={len(result['warnings'])}")
        for e in result["errors"]:
            print(f"  E: {e}")
        for w in result["warnings"]:
            print(f"  W: {w}")
