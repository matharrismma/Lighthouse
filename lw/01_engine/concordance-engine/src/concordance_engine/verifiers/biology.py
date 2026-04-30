"""
verifiers/biology.py — Replicates, assay diversity, dose-response, power analysis.
"""
from __future__ import annotations
from typing import Any, Dict, List
from .base import VerifierResult

MIN_REPLICATES = 3
MIN_ASSAY_CLASSES = 2


def verify_replicates(spec: Dict[str, Any]) -> VerifierResult:
    name = "biology.replicates"
    n = int(spec.get("n_replicates", 0))
    minimum = int(spec.get("min_replicates", MIN_REPLICATES))
    if n >= minimum:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"{n} replicates ≥ minimum {minimum}.",
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
                              detail=f"{distinct} distinct assay classes ≥ minimum {minimum}.",
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
            violations.append(f"Reversal at index {i}: {responses[i-1]} → {responses[i]}")
        elif direction == "decreasing" and delta > 0:
            violations.append(f"Reversal at index {i}: {responses[i-1]} → {responses[i]}")

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
                                  detail=f"n={n_per_group} ≥ required {n_required} for power={target_power}.",
                                  data=data)
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"n={n_per_group} < required {n_required} for d={effect_size}, α={alpha}, power={target_power}.",
                              data=data)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def run(packet: dict) -> list:
    results = []
    verify = packet.get("BIO_VERIFY") or {}
    if not verify:
        return results
    if "n_replicates" in verify:
        results.append(verify_replicates(verify))
    if "assay_classes" in verify:
        results.append(verify_orthogonal_assays(verify))
    if "dose_response" in verify:
        results.append(verify_dose_response_monotonicity(verify))
    if "power_analysis" in verify:
        results.append(verify_sample_size_powered(verify))
    return results
