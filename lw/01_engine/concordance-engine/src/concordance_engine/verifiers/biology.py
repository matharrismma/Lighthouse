"""
verifiers/biology.py — Replicates, assay diversity, dose-response, power analysis,
and nested health control systems (BIO_CONTROL block).

BIO_CONTROL block schema:
    {
      "failure_mode": one of
          setpoint_drift | loop_saturation | compensation_collapse |
          cross_layer_override | sensor_failure,
      "failure_layer": "L1" … "L6",
      "intervention_layers": ["L1", "L3", ...],
      "upper_layer_driver_addressed": bool,   # required for cross_layer_override
      "setpoint_shift_mechanism_stated": bool, # required for setpoint_drift
      "sensor_recalibration_plan": bool        # required for sensor_failure
    }
"""
from __future__ import annotations
from typing import Any, Dict, List
from .base import VerifierResult

MIN_REPLICATES = 3
MIN_ASSAY_CLASSES = 2

_VALID_FAILURE_MODES = {
    "setpoint_drift",
    "loop_saturation",
    "compensation_collapse",
    "cross_layer_override",
    "sensor_failure",
}

_LAYER_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5, "L6": 6}


def verify_replicates(spec: Dict[str, Any]) -> VerifierResult:
    name = "biology.replicates"
    n = int(spec.get("n_replicates", 0))
    minimum = int(spec.get("min_replicates", MIN_REPLICATES))
    if n >= minimum:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"{n} replicates \u2265 minimum {minimum}.",
                              data={"n_replicates": n, "minimum": minimum})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Only {n} replicates; minimum is {minimum}.",
                          data={"n_replicates": n, "minimum": minimum})


def verify_orthogonal_assays(spec: Dict[str, Any]) -> VerifierResult:
    name = "biology.orthogonal_assays"
    assays = spec.get("assay_classes", [])
    minimum = int(spec.get("min_assay_classes", MIN_ASSAY_CLASSES))
    distinct = len(set(assays))
    if distinct >= minimum:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"{distinct} distinct assay classes \u2265 minimum {minimum}.",
                              data={"distinct": distinct, "assays": assays})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Only {distinct} distinct assay class(es); minimum is {minimum}.",
                          data={"distinct": distinct, "assays": assays})


def verify_dose_response_monotonicity(spec: Dict[str, Any]) -> VerifierResult:
    name = "biology.dose_response"
    dr = spec.get("dose_response") or spec
    doses = list(dr.get("doses", []))
    responses = list(dr.get("responses", []))
    direction = str(dr.get("expected_direction", "increasing")).lower()

    if len(doses) != len(responses) or len(doses) < 2:
        return VerifierResult(name=name, status="ERROR",
                              detail="Need at least 2 dose-response pairs.")

    violations = []
    for i in range(1, len(responses)):
        delta = responses[i] - responses[i - 1]
        if direction == "increasing" and delta < 0:
            violations.append(f"Reversal at index {i}: {responses[i-1]} \u2192 {responses[i]}")
        elif direction == "decreasing" and delta > 0:
            violations.append(f"Reversal at index {i}: {responses[i-1]} \u2192 {responses[i]}")

    if not violations:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"Dose-response is monotonically {direction}.",
                              data={"direction": direction})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Non-monotonic response ({direction}): {'; '.join(violations)}",
                          data={"violations": violations, "direction": direction})


def verify_sample_size_powered(spec: Dict[str, Any]) -> VerifierResult:
    name = "biology.power_analysis"
    pa = spec.get("power_analysis") or spec
    try:
        effect_size = float(pa["effect_size"])
        alpha = float(pa.get("alpha", 0.05))
        n_per_group = int(pa["n_per_group"])
        target_power = float(pa.get("target_power", 0.80))

        # Use scipy for power calculation (two-sample t-test)
        from scipy.stats import norm
        import math

        z_alpha = norm.ppf(1 - alpha / 2)
        z_beta = norm.ppf(target_power)
        n_required = ((z_alpha + z_beta) / effect_size) ** 2 * 2
        n_required = math.ceil(n_required)

        data = {"n_per_group": n_per_group, "n_required": n_required,
                "effect_size": effect_size, "alpha": alpha, "target_power": target_power}

        if n_per_group >= n_required:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"n={n_per_group} \u2265 required {n_required} for power={target_power}.",
                                  data=data)
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"n={n_per_group} < required {n_required} for d={effect_size}, \u03b1={alpha}, power={target_power}.",
                              data=data)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_control_layer_match(spec: Dict[str, Any]) -> VerifierResult:
    """
    Check that at least one intervention layer is >= the failure layer.
    A failure at L4 (whole-body) cannot be resolved by L1/L2 interventions alone.
    """
    name = "biology.control_layer_match"
    failure_layer = str(spec.get("failure_layer", "")).upper()
    intervention_layers = [str(l).upper() for l in spec.get("intervention_layers", [])]

    if not failure_layer or not intervention_layers:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="No failure_layer/intervention_layers declared — skipping layer check.")

    if failure_layer not in _LAYER_ORDER:
        return VerifierResult(name=name, status="ERROR",
                              detail=f"Unknown failure_layer '{failure_layer}'. Must be L1\u2013L6.")

    fl_rank = _LAYER_ORDER[failure_layer]
    il_ranks = [_LAYER_ORDER.get(il, 0) for il in intervention_layers]
    max_il_rank = max(il_ranks) if il_ranks else 0

    if max_il_rank >= fl_rank:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail=f"Highest intervention layer ({intervention_layers[il_ranks.index(max_il_rank)]}) "
                   f">= failure layer ({failure_layer}). Layer match satisfied.",
            data={"failure_layer": failure_layer, "intervention_layers": intervention_layers}
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=f"All interventions ({intervention_layers}) are below failure layer ({failure_layer}). "
               f"Upper-layer drivers will not be addressed — outcome unlikely to hold.",
        data={"failure_layer": failure_layer, "intervention_layers": intervention_layers,
              "max_intervention_rank": max_il_rank, "failure_rank": fl_rank}
    )


def verify_cross_layer_override(spec: Dict[str, Any]) -> VerifierResult:
    """
    If failure_mode is cross_layer_override, upper_layer_driver_addressed must be True.
    """
    name = "biology.cross_layer_override"
    failure_mode = str(spec.get("failure_mode", "")).lower()
    if failure_mode != "cross_layer_override":
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="Not a cross_layer_override failure — check skipped.")

    addressed = spec.get("upper_layer_driver_addressed")
    if addressed is True:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail="cross_layer_override: upper_layer_driver_addressed = True.",
            data={"upper_layer_driver_addressed": True}
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail="cross_layer_override failure mode declared but upper_layer_driver_addressed "
               "is not True. The intervention plan must explicitly address the overriding "
               "upper-layer driver, or the lower-loop fix will not hold.",
        data={"upper_layer_driver_addressed": addressed}
    )


def verify_setpoint_mechanism(spec: Dict[str, Any]) -> VerifierResult:
    """
    If failure_mode is setpoint_drift, setpoint_shift_mechanism_stated must be True.
    """
    name = "biology.setpoint_mechanism"
    failure_mode = str(spec.get("failure_mode", "")).lower()
    if failure_mode != "setpoint_drift":
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="Not a setpoint_drift failure — check skipped.")

    stated = spec.get("setpoint_shift_mechanism_stated")
    if stated is True:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail="setpoint_drift: setpoint_shift_mechanism_stated = True.",
            data={"setpoint_shift_mechanism_stated": True}
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail="setpoint_drift failure mode declared but setpoint_shift_mechanism_stated "
               "is not True. The biological mechanism driving the setpoint change "
               "(e.g., RAAS remodeling, leptin resistance, epigenetic locking) must be stated.",
        data={"setpoint_shift_mechanism_stated": stated}
    )


def verify_sensor_failure_plan(spec: Dict[str, Any]) -> VerifierResult:
    """
    If failure_mode is sensor_failure, sensor_recalibration_plan must be True.
    """
    name = "biology.sensor_failure_plan"
    failure_mode = str(spec.get("failure_mode", "")).lower()
    if failure_mode != "sensor_failure":
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="Not a sensor_failure mode — check skipped.")

    plan = spec.get("sensor_recalibration_plan")
    if plan is True:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail="sensor_failure: sensor_recalibration_plan = True.",
            data={"sensor_recalibration_plan": True}
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail="sensor_failure mode declared but sensor_recalibration_plan is not True. "
               "Without restoring the sensing mechanism, the control loop cannot close "
               "and downstream damage will continue silently.",
        data={"sensor_recalibration_plan": plan}
    )


def verify_failure_mode_known(spec: Dict[str, Any]) -> VerifierResult:
    """Check that failure_mode is one of the recognised taxonomy values."""
    name = "biology.failure_mode_taxonomy"
    failure_mode = str(spec.get("failure_mode", "")).lower()
    if not failure_mode:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="No failure_mode declared — taxonomy check skipped.")
    if failure_mode in _VALID_FAILURE_MODES:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"failure_mode '{failure_mode}' is a recognised taxonomy value.",
                              data={"failure_mode": failure_mode})
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=f"Unknown failure_mode '{failure_mode}'. "
               f"Must be one of: {sorted(_VALID_FAILURE_MODES)}.",
        data={"failure_mode": failure_mode, "valid": sorted(_VALID_FAILURE_MODES)}
    )


def run(packet: dict) -> list:
    results = []

    # \u2500\u2500 Standard BIO_VERIFY block \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    verify = packet.get("BIO_VERIFY") or {}
    if verify:
        if "n_replicates" in verify:
            results.append(verify_replicates(verify))
        if "assay_classes" in verify:
            results.append(verify_orthogonal_assays(verify))
        if "dose_response" in verify:
            results.append(verify_dose_response_monotonicity(verify))
        if "power_analysis" in verify:
            results.append(verify_sample_size_powered(verify))

    # \u2500\u2500 Nested health / control systems block \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    ctrl = packet.get("BIO_CONTROL") or {}
    if ctrl:
        results.append(verify_failure_mode_known(ctrl))
        results.append(verify_control_layer_match(ctrl))

        failure_mode = str(ctrl.get("failure_mode", "")).lower()
        if failure_mode == "cross_layer_override":
            results.append(verify_cross_layer_override(ctrl))
        if failure_mode == "setpoint_drift":
            results.append(verify_setpoint_mechanism(ctrl))
        if failure_mode == "sensor_failure":
            results.append(verify_sensor_failure_plan(ctrl))

    return results
