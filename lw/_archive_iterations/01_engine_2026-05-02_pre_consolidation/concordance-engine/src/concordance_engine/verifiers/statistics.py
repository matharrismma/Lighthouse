"""
verifiers/statistics.py — Statistical claim recomputation via scipy.
"""
from __future__ import annotations
from typing import Any, Dict, List
from .base import VerifierResult


def verify_pvalue_calibration(spec: Dict[str, Any]) -> VerifierResult:
    name = "statistics.pvalue"
    try:
        from scipy import stats as sps
        test = spec.get("test", "")
        claimed_p = float(spec.get("claimed_p", 0))
        tol = float(spec.get("tolerance", 0.005))

        if test == "two_sample_t":
            n1, n2 = int(spec["n1"]), int(spec["n2"])
            m1, m2 = float(spec["mean1"]), float(spec["mean2"])
            s1, s2 = float(spec["sd1"]), float(spec["sd2"])
            t_stat, p = sps.ttest_ind_from_stats(m1, s1, n1, m2, s2, n2,
                                                  equal_var=False)
            recomputed = p

        elif test == "one_sample_t":
            n = int(spec["n"])
            m, mu = float(spec["mean"]), float(spec.get("mu", 0))
            sd = float(spec["sd"])
            import math
            t_stat = (m - mu) / (sd / math.sqrt(n))
            recomputed = float(sps.t.sf(abs(t_stat), df=n-1) * 2)

        elif test == "z":
            z = float(spec["z_statistic"])
            recomputed = float(sps.norm.sf(abs(z)) * 2)

        elif test == "chi2":
            chi2_stat = float(spec["statistic"])
            df = int(spec["df"])
            recomputed = float(sps.chi2.sf(chi2_stat, df))

        elif test == "f":
            f_stat = float(spec["statistic"])
            df1, df2 = int(spec["df1"]), int(spec["df2"])
            recomputed = float(sps.f.sf(f_stat, df1, df2))

        else:
            return VerifierResult(name=name, status="ERROR",
                                  detail=f"Unknown test type: {test!r}")

        diff = abs(recomputed - claimed_p)
        data = {"recomputed_p": recomputed, "claimed_p": claimed_p, "diff": diff}
        if diff <= tol:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"p={recomputed:.6g} matches claimed {claimed_p:.6g} (tol={tol})",
                                  data=data)
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Recomputed p={recomputed:.6g}, claimed {claimed_p:.6g}, diff={diff:.6g}",
                              data=data)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_significance_consistency(spec: Dict[str, Any]) -> VerifierResult:
    name = "statistics.significance"
    try:
        p = float(spec["p_value"])
        alpha = float(spec.get("alpha", 0.05))
        claimed = str(spec.get("claimed_significance", "")).lower()
        is_sig = p < alpha
        claimed_sig = "significant" in claimed and "not" not in claimed
        if is_sig == claimed_sig:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"p={p} vs alpha={alpha}: {'significant' if is_sig else 'not significant'} — consistent with claim")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"p={p} vs alpha={alpha} is {'significant' if is_sig else 'not significant'}, but claimed {claimed!r}")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_effect_size_present(spec: Dict[str, Any]) -> VerifierResult:
    name = "statistics.effect_size_present"
    p = float(spec.get("p_value", 1.0))
    alpha = float(spec.get("alpha", 0.05))
    effect = spec.get("effect_size")
    if p < alpha and effect is None:
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Result is significant (p={p} < alpha={alpha}) but no effect size reported.")
    return VerifierResult(name=name, status="CONFIRMED",
                          detail="Effect size present or result not significant.")


def verify_multiple_comparisons(spec: Dict[str, Any]) -> VerifierResult:
    name = "statistics.multiple_comparisons"
    try:
        raw_p = list(spec["raw_p_values"])
        method = str(spec.get("method", "bonferroni")).lower()
        alpha = float(spec.get("alpha", 0.05))
        claimed_idx = sorted(spec.get("claimed_rejected_indices", []))
        n = len(raw_p)

        if method == "bonferroni":
            threshold = alpha / n
            computed_idx = sorted(i for i, p in enumerate(raw_p) if p < threshold)
        elif method in ("bh", "fdr", "benjamini-hochberg"):
            sorted_p = sorted(enumerate(raw_p), key=lambda x: x[1])
            computed_idx = []
            last_reject = -1
            for rank, (orig_i, p) in enumerate(sorted_p, start=1):
                if p <= rank / n * alpha:
                    last_reject = rank - 1
            for rank, (orig_i, p) in enumerate(sorted_p, start=1):
                if rank - 1 <= last_reject:
                    computed_idx.append(orig_i)
            computed_idx = sorted(computed_idx)
        else:
            return VerifierResult(name=name, status="ERROR",
                                  detail=f"Unknown correction method: {method!r}")

        data = {"computed_rejected": computed_idx, "claimed_rejected": claimed_idx,
                "method": method, "alpha": alpha}
        if computed_idx == claimed_idx:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"{method} rejected indices {computed_idx} match claim",
                                  data=data)
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"{method} should reject {computed_idx}, claimed {claimed_idx}",
                              data=data)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_confidence_interval(spec: Dict[str, Any]) -> VerifierResult:
    name = "statistics.confidence_interval"
    try:
        est = float(spec["estimate"])
        lo = float(spec["ci_low"])
        hi = float(spec["ci_high"])
        if lo <= est <= hi:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"Estimate {est} is in CI [{lo}, {hi}]")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Estimate {est} is outside CI [{lo}, {hi}]")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def run(packet: dict) -> list:
    results = []
    verify = packet.get("STAT_VERIFY") or {}
    if not verify:
        return results
    if "test" in verify and "claimed_p" in verify:
        results.append(verify_pvalue_calibration(verify))
    if "p_value" in verify and "claimed_significance" in verify:
        results.append(verify_significance_consistency(verify))
    if "raw_p_values" in verify and "method" in verify:
        results.append(verify_multiple_comparisons(verify))
    if "estimate" in verify and "ci_low" in verify:
        results.append(verify_confidence_interval(verify))
    return results
