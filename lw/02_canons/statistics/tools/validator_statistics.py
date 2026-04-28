"""Statistics canon validator wrapper.

Thin wrapper around the canonical validator at
01_engine/concordance-engine/src/concordance_engine/domains/statistics.py.
The engine package is the source of truth; this file is the canon-side
entrypoint matching the mathematics/physics pattern.

Usage:
    python validator_statistics.py            # runs self-test
    from validator_statistics import validate_stats_packet
"""
from __future__ import annotations

from typing import Any, Dict, List


def validate_stats_packet(pkt: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a Statistics packet against the canon RED and FLOOR constraints.

    Mirrors concordance_engine.domains.statistics.StatisticsValidator.
    """
    errors: List[str] = []
    warnings: List[str] = []

    red = pkt.get("STAT_RED", {}) or {}
    floor = pkt.get("STAT_FLOOR", {}) or {}
    inference = pkt.get("STAT_INFERENCE", {}) or {}

    # ---- RED ----
    if red.get("probabilities_valid") is False:
        errors.append("RED: probability axiom violation (must be non-negative and sum/integrate to 1).")
    if red.get("pvalue_interpreted_correctly") is False:
        errors.append("RED: p-value misinterpretation (p is P(data|H0), NOT P(H0|data)).")
    if inference.get("pvalue_is_prob_null") is True:
        errors.append("RED: p-value stated as probability null is true (Wasserstein & Lazar 2016).")
    if red.get("effect_size_reported") is False:
        errors.append("RED: effect size not reported (significance without magnitude is incomplete).")

    p_val = inference.get("p_value")
    alpha = inference.get("alpha", 0.05)
    if p_val is not None and float(p_val) <= float(alpha):
        if not inference.get("effect_size") and not inference.get("effect_size_type"):
            errors.append("RED: significant p-value reported without effect size (add Cohen's d, eta-squared, r, or equivalent).")

    if red.get("hypothesis_prespecified") is False:
        errors.append("RED: hypothesis not pre-specified (post-hoc generation on the same data is circular).")
    if red.get("causal_identification_stated") is False:
        errors.append("RED: causal claim without identification strategy (RCT/IV/RDD/DiD/etc.).")
    if red.get("multiple_comparisons_corrected") is False:
        errors.append("RED: multiple comparisons not corrected (apply Bonferroni/BH or pre-register).")
    if red.get("confidence_interval_interpretation_correct") is False:
        errors.append("RED: CI misinterpretation (95% CI describes procedure, not P(value in interval)).")

    if not red and not inference:
        claims = pkt.get("claims", [])
        if not isinstance(claims, list) or len(claims) == 0:
            warnings.append("Statistics packet has no STAT_RED, STAT_INFERENCE, or claims[].")

    # ---- FLOOR ----
    if floor or inference:
        if floor.get("sampling_mechanism_stated") is False:
            errors.append("FLOOR: sampling mechanism not stated (SRS/stratified/cluster/convenience).")
        if floor.get("distributional_assumptions_tested") is False:
            errors.append("FLOOR: distributional assumptions not tested (QQ, residuals, Levene, robust).")
        if floor.get("sample_size_justified") is False:
            errors.append("FLOOR: sample size not justified (power analysis or pre-registration).")
        if floor.get("missing_data_mechanism_declared") is False:
            errors.append("FLOOR: missing-data mechanism not declared (MCAR/MAR/MNAR).")
        if floor.get("prior_justified") is False:
            errors.append("FLOOR: Bayesian prior not justified (state choice rationale + sensitivity).")
        if inference:
            has_es = inference.get("effect_size") or inference.get("effect_size_type")
            has_ci = inference.get("confidence_interval")
            if has_es and not has_ci:
                errors.append("FLOOR: effect size reported without confidence interval.")
        if floor.get("power_computed") is False:
            errors.append("FLOOR: statistical power not computed (specify effect size, alpha, n).")

        for d in (pkt.get("diagnostics") or []):
            if isinstance(d, dict):
                diag = str(d.get("diagnosis", "")).upper()
                if diag in ("ASSUMPTION_UNSTATED", "SAMPLING_MISMATCH", "MULTIPLICITY_ERROR"):
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
        "STAT_RED": {
            "probabilities_valid": True,
            "pvalue_interpreted_correctly": True,
            "effect_size_reported": True,
            "hypothesis_prespecified": True,
            "causal_identification_stated": True,
            "multiple_comparisons_corrected": True,
            "confidence_interval_interpretation_correct": True,
        },
        "STAT_FLOOR": {
            "sampling_mechanism_stated": True,
            "distributional_assumptions_tested": True,
            "sample_size_justified": True,
            "missing_data_mechanism_declared": True,
            "prior_justified": True,
            "power_computed": True,
        },
        "STAT_INFERENCE": {
            "framework": "frequentist",
            "p_value": 0.0034,
            "alpha": 0.05,
            "effect_size_type": "cohens_d",
            "effect_size": 0.42,
            "confidence_interval": [0.18, 0.66],
            "pvalue_is_prob_null": False,
        },
    }
    print(validate_stats_packet(sample))

    bad = {"STAT_RED": {"hypothesis_prespecified": False, "multiple_comparisons_corrected": False}}
    print(validate_stats_packet(bad))
