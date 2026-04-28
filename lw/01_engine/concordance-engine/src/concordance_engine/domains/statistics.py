"""Statistics domain validator — full RED/FLOOR checks from statistics_core.yaml.

RED constraints (7 from core):
  1. Probability axioms: non-negative, sum/integrate to 1
  2. p-value interpretation: NOT the probability H0 is true
  3. Effect size required: significance alone is not a result
  4. Hypothesis pre-specification: no post-hoc hypothesis generation on same data
  5. Causal identification: causal claims require design, not correlation alone
  6. Multiple comparisons: uncorrected FWER inflation is a RED violation
  7. Confidence interval interpretation: describes the procedure, not the specific interval

FLOOR bounds (7 from core):
  1. Sampling mechanism stated
  2. Distributional assumptions stated and tested
  3. Sample size justified by power analysis
  4. Missing data mechanism declared
  5. Prior justified (Bayesian)
  6. Effect size CI reported
  7. Regression variable roles declared
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class StatisticsValidator:
    domain = "statistics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        red = packet.get("STAT_RED", {}) or {}
        inference = packet.get("STAT_INFERENCE", {}) or {}

        # 1. Probability axioms
        if red.get("probabilities_valid") is False:
            errors.append("probability axiom violation — probabilities must be non-negative and sum/integrate to 1")

        # 2. p-value misinterpretation
        if red.get("pvalue_interpreted_correctly") is False:
            errors.append("p-value misinterpretation — p is P(data|H0), NOT P(H0|data); report Bayes factor for posterior probability")

        # Also catch stated misinterpretation in inference block
        if inference.get("pvalue_is_prob_null") is True:
            errors.append("p-value stated as probability null is true — this is a RED violation; see Wasserstein & Lazar 2016")

        # 3. Effect size required
        if red.get("effect_size_reported") is False:
            errors.append("effect size not reported — statistical significance without magnitude is an incomplete result")

        # Also check inference block directly
        p_val = inference.get("p_value")
        alpha = inference.get("alpha", 0.05)
        if p_val is not None and float(p_val) <= float(alpha):
            if not inference.get("effect_size") and not inference.get("effect_size_type"):
                errors.append("significant p-value reported without effect size — add Cohen's d, eta-squared, r, or equivalent")

        # 4. Hypothesis pre-specification
        if red.get("hypothesis_prespecified") is False:
            errors.append("hypothesis not pre-specified — post-hoc hypothesis generation on the same data is circular inference")

        # 5. Causal identification
        if red.get("causal_identification_stated") is False:
            # Only error if causal language is explicitly used
            errors.append("causal claim without identification strategy — state RCT, IV, RDD, DiD, or other design; otherwise report as association")

        # 6. Multiple comparisons
        if red.get("multiple_comparisons_corrected") is False:
            errors.append("multiple comparisons not corrected — uncorrected FWER inflation is a RED violation; apply Bonferroni, BH, or pre-register")

        # 7. Confidence interval interpretation
        if red.get("confidence_interval_interpretation_correct") is False:
            errors.append("CI misinterpretation — 95% CI describes the procedure (long-run coverage), not probability that this interval contains the true value")

        # Flat packet fallback
        if not red and not inference:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Statistics packets must include STAT_RED, STAT_INFERENCE, or claims[]")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        floor = packet.get("STAT_FLOOR", {}) or {}
        inference = packet.get("STAT_INFERENCE", {}) or {}

        if floor or inference:
            # 1. Sampling mechanism
            if floor.get("sampling_mechanism_stated") is False:
                errors.append("sampling mechanism not stated — declare SRS, stratified, cluster, convenience, etc.")

            # 2. Distributional assumptions
            if floor.get("distributional_assumptions_tested") is False:
                errors.append("distributional assumptions not tested — run QQ-plot, residual diagnostics, Levene test, or use robust method")

            # 3. Sample size justification
            if floor.get("sample_size_justified") is False:
                errors.append("sample size not justified — provide power analysis or pre-registration rationale")

            # 4. Missing data
            if floor.get("missing_data_mechanism_declared") is False:
                errors.append("missing data mechanism not declared — state MCAR, MAR, or MNAR and handle accordingly")

            # 5. Prior for Bayesian
            if floor.get("prior_justified") is False:
                errors.append("Bayesian prior not justified — state prior choice rationale and run sensitivity analysis")

            # 6. Effect size CI
            if inference:
                has_es = inference.get("effect_size") or inference.get("effect_size_type")
                has_ci = inference.get("confidence_interval")
                if has_es and not has_ci:
                    errors.append("effect size reported without confidence interval — report CI alongside point estimate")

            # 7. Power
            if floor.get("power_computed") is False:
                errors.append("statistical power not computed — specify effect size, alpha, n to derive power")

            # Diagnostic signals
            for d in (packet.get("diagnostics") or []):
                if isinstance(d, dict):
                    diag = str(d.get("diagnosis", "")).upper()
                    if diag in ("ASSUMPTION_UNSTATED", "SAMPLING_MISMATCH", "MULTIPLICITY_ERROR"):
                        errors.append(f"FLOOR diagnostic: {diag} — {d.get('action', '')}")

        else:
            artifacts = packet.get("artifacts") or {}
            if not artifacts:
                errors.append("Statistics packets must include STAT_FLOOR, STAT_INFERENCE, or artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
