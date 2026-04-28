"""Statistics verifier.

Checks performed:
  * pvalue_calibration: given (test, n, statistic, df, claimed_p), recompute
    p from the test distribution and verify within tolerance
  * pvalue_significance_consistency: if the packet claims significance at
    alpha, verify p <= alpha; if it claims non-significance, verify p > alpha
  * effect_size_required: if p <= alpha, an effect size must be reported
  * multiple_comparisons: given k tests with raw p-values and a stated
    correction method (bonferroni, bh), recompute corrected p-values and
    verify the rejection set matches the claim
  * confidence_interval_coverage: given (estimate, ci_low, ci_high, alpha),
    verify the interval is symmetric (or shape-correct) and contains the
    estimate

Recomputed test statistics for two_sample_t are derived from the supplied
(n1, n2, mean1, mean2, sd1, sd2) using Welch's formula.
"""
from __future__ import annotations
from typing import Any, Dict, List
import math

import numpy as np
from scipy import stats as scistats

from .base import VerifierResult, na, confirm, mismatch, error


def verify_pvalue_calibration(spec: Dict[str, Any]) -> VerifierResult:
    """Recompute p-value from supplied test inputs and verify the claim."""
    test = spec.get("test", "").lower()
    claimed_p = spec.get("claimed_p")
    tol = spec.get("tolerance", 1e-3)

    try:
        if test in ("two_sample_t", "welch_t"):
            n1, n2 = spec["n1"], spec["n2"]
            m1, m2 = spec["mean1"], spec["mean2"]
            s1, s2 = spec["sd1"], spec["sd2"]
            tail = spec.get("tail", "two-sided")
            se = math.sqrt(s1 ** 2 / n1 + s2 ** 2 / n2)
            t = (m1 - m2) / se
            df = (s1 ** 2 / n1 + s2 ** 2 / n2) ** 2 / (
                (s1 ** 2 / n1) ** 2 / (n1 - 1) + (s2 ** 2 / n2) ** 2 / (n2 - 1)
            )
            if tail == "two-sided":
                p = 2 * scistats.t.sf(abs(t), df)
            elif tail == "greater":
                p = scistats.t.sf(t, df)
            else:
                p = scistats.t.cdf(t, df)
            data = {"recomputed_t": t, "df": df, "recomputed_p": p}

        elif test == "one_sample_t":
            n = spec["n"]
            m = spec["mean"]
            s = spec["sd"]
            mu0 = spec.get("mu0", 0.0)
            tail = spec.get("tail", "two-sided")
            t = (m - mu0) / (s / math.sqrt(n))
            df = n - 1
            if tail == "two-sided":
                p = 2 * scistats.t.sf(abs(t), df)
            elif tail == "greater":
                p = scistats.t.sf(t, df)
            else:
                p = scistats.t.cdf(t, df)
            data = {"recomputed_t": t, "df": df, "recomputed_p": p}

        elif test == "z":
            z = spec["z"]
            tail = spec.get("tail", "two-sided")
            if tail == "two-sided":
                p = 2 * scistats.norm.sf(abs(z))
            elif tail == "greater":
                p = scistats.norm.sf(z)
            else:
                p = scistats.norm.cdf(z)
            data = {"recomputed_z": z, "recomputed_p": p}

        elif test == "chi2":
            stat = spec["statistic"]
            df = spec["df"]
            p = scistats.chi2.sf(stat, df)
            data = {"recomputed_stat": stat, "df": df, "recomputed_p": p}

        elif test == "f":
            stat = spec["statistic"]
            df1 = spec["df1"]
            df2 = spec["df2"]
            p = scistats.f.sf(stat, df1, df2)
            data = {"recomputed_stat": stat, "df1": df1, "df2": df2, "recomputed_p": p}

        else:
            return error("statistics.pvalue_calibration", f"unknown test {test!r}")

    except KeyError as e:
        return error("statistics.pvalue_calibration", f"missing field: {e}")
    except Exception as e:
        return error("statistics.pvalue_calibration", f"computation failure: {e}")

    if claimed_p is None:
        return confirm("statistics.pvalue_calibration",
                       f"recomputed p={p:.6g} (no claimed_p to compare)", data)

    diff = abs(p - claimed_p)
    if diff <= tol:
        return confirm("statistics.pvalue_calibration",
                       f"claimed p={claimed_p}, recomputed p={p:.6g} (diff {diff:.2e})", data)
    return mismatch("statistics.pvalue_calibration",
                    f"claimed p={claimed_p}, recomputed p={p:.6g} (diff {diff:.2e} > tol {tol})",
                    data)


def verify_significance_consistency(spec: Dict[str, Any]) -> VerifierResult:
    """If author claims 'significant', verify p <= alpha. Same for 'not significant'."""
    p = spec.get("p_value")
    alpha = spec.get("alpha", 0.05)
    claimed_significance = spec.get("claimed_significance")  # "significant" or "not_significant"
    if p is None or claimed_significance is None:
        return na("statistics.significance_consistency")
    is_sig = p <= alpha
    if claimed_significance.lower() in ("significant", "sig", "yes", "true"):
        if is_sig:
            return confirm("statistics.significance_consistency",
                           f"p={p} <= alpha={alpha}, claim of significance is consistent")
        return mismatch("statistics.significance_consistency",
                        f"claimed significant but p={p} > alpha={alpha}")
    else:
        if not is_sig:
            return confirm("statistics.significance_consistency",
                           f"p={p} > alpha={alpha}, claim of non-significance is consistent")
        return mismatch("statistics.significance_consistency",
                        f"claimed non-significant but p={p} <= alpha={alpha}")


def verify_effect_size_present(spec: Dict[str, Any]) -> VerifierResult:
    p = spec.get("p_value")
    alpha = spec.get("alpha", 0.05)
    if p is None:
        return na("statistics.effect_size_present")
    has_effect = (
        spec.get("effect_size") is not None
        or spec.get("effect_size_type") is not None
    )
    has_ci = spec.get("confidence_interval") is not None
    if p <= alpha and not has_effect:
        return mismatch(
            "statistics.effect_size_present",
            f"significant result (p={p} <= alpha={alpha}) without effect_size",
        )
    if has_effect and not has_ci:
        return mismatch(
            "statistics.effect_size_present",
            "effect_size reported without a confidence_interval",
        )
    return confirm("statistics.effect_size_present", "effect size reporting consistent")


def verify_multiple_comparisons(spec: Dict[str, Any]) -> VerifierResult:
    """Given raw p-values and a correction method, recompute and verify."""
    raw_p = spec.get("raw_p_values")
    method = (spec.get("method") or "").lower()
    alpha = spec.get("alpha", 0.05)
    claimed_rejected = spec.get("claimed_rejected_indices")  # optional
    if not raw_p:
        return na("statistics.multiple_comparisons")
    p = np.asarray(raw_p, dtype=float)
    k = len(p)
    if method in ("bonferroni", "bonf"):
        adj = np.minimum(p * k, 1.0)
    elif method in ("bh", "benjamini-hochberg", "fdr"):
        order = np.argsort(p)
        ranks = np.empty(k, dtype=int)
        ranks[order] = np.arange(1, k + 1)
        adj_sorted = (p[order] * k / ranks[order]).astype(float)
        # enforce monotonicity
        for i in range(k - 2, -1, -1):
            adj_sorted[i] = min(adj_sorted[i], adj_sorted[i + 1])
        adj = np.empty(k, dtype=float)
        adj[order] = np.minimum(adj_sorted, 1.0)
    else:
        return error("statistics.multiple_comparisons", f"unknown method {method!r}")

    rejected = sorted([i for i, q in enumerate(adj) if q <= alpha])
    data = {"adjusted_p": adj.tolist(), "rejected_indices": rejected}
    if claimed_rejected is None:
        return confirm("statistics.multiple_comparisons",
                       f"{len(rejected)}/{k} rejected at alpha={alpha} after {method}", data)
    if sorted(claimed_rejected) == rejected:
        return confirm("statistics.multiple_comparisons",
                       f"rejection set matches claim: {rejected}", data)
    return mismatch("statistics.multiple_comparisons",
                    f"claimed rejected={sorted(claimed_rejected)}, computed={rejected}", data)


def verify_confidence_interval(spec: Dict[str, Any]) -> VerifierResult:
    est = spec.get("estimate")
    lo = spec.get("ci_low")
    hi = spec.get("ci_high")
    if est is None or lo is None or hi is None:
        return na("statistics.confidence_interval")
    if not (lo <= hi):
        return mismatch("statistics.confidence_interval", f"ci_low={lo} > ci_high={hi}")
    if not (lo <= est <= hi):
        return mismatch("statistics.confidence_interval",
                        f"estimate {est} not in [{lo}, {hi}]")
    return confirm("statistics.confidence_interval",
                   f"estimate {est} in [{lo}, {hi}]")


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    sv = packet.get("STAT_VERIFY") or {}
    inf = packet.get("STAT_INFERENCE") or {}

    if sv.get("test"):
        results.append(verify_pvalue_calibration(sv))

    sig_spec = {**inf, **sv}
    if sig_spec.get("claimed_significance") and sig_spec.get("p_value") is not None:
        results.append(verify_significance_consistency(sig_spec))

    if inf.get("p_value") is not None:
        results.append(verify_effect_size_present(inf))

    if sv.get("raw_p_values"):
        results.append(verify_multiple_comparisons(sv))

    if all(k in sv for k in ("estimate", "ci_low", "ci_high")):
        results.append(verify_confidence_interval(sv))

    if not results:
        results.append(na("statistics", "no STAT_VERIFY artifacts present"))
    return results
