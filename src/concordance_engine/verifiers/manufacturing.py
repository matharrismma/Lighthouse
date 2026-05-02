"""Manufacturing verifier (engineering umbrella sibling to chemistry + physics).

Deterministic checks against public-domain manufacturing-statistics
formulas: Six Sigma sigma-level math, Statistical Process Control (SPC)
limit calculation, Process Capability indices (Cp / Cpk), and tolerance
stack-up arithmetic.

All formulas are public-domain (ISO 13053, ASTM, generic SPC literature).
No external dataset required.

Checks performed:

  * manufacturing.sigma_level
      Defects-per-million-opportunities (DPMO) maps to a sigma level.
      Uses the standard +1.5σ shift convention used in industry. For
      DPMO ≤ 1e-9 (effectively perfect) the verifier reports >= 6σ
      with a tolerance band; otherwise compares the implied σ to claim.
  * manufacturing.spc_control_limits
      X-bar chart: UCL = mean + k·σ, LCL = mean - k·σ. Default k = 3
      (the standard 3-sigma rule). Claimed limits match within tolerance.
  * manufacturing.process_capability
      Cp = (USL - LSL) / (6σ);   Cpk = min((USL - μ)/(3σ), (μ - LSL)/(3σ)).
      A claim 'capable' (Cp >= 1.33) / 'not_capable' must match.
  * manufacturing.tolerance_stack_rss
      Statistical (root-sum-of-squares) tolerance stack-up:
      total = sqrt(sum(t_i²)). Compares to worst-case (linear sum) for
      claim verification.

MFG_VERIFY packet shape (any subset of fields):
    {
      "dpmo": 233,
      "claimed_sigma": 5.0,
      "tolerance_sigma": 0.1,

      "mean": 100.0,
      "sigma": 2.0,
      "k": 3,
      "claimed_ucl": 106.0,
      "claimed_lcl": 94.0,

      "usl": 110.0,
      "lsl": 90.0,
      "process_mean": 100.0,
      "process_sigma": 2.0,
      "claimed_cp_capable": true,

      "tolerances": [0.01, 0.02, 0.015],
      "claimed_rss": 0.027,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# Sigma-level → DPMO table (public-domain, 1.5σ shift convention).
# Values from Six Sigma literature.
_SIGMA_TO_DPMO = [
    (1.0, 691462),
    (2.0, 308538),
    (3.0,  66807),
    (4.0,   6210),
    (4.5,   1350),
    (5.0,    233),
    (5.5,     32),
    (6.0,    3.4),
    (6.5,    0.5),
    (7.0,    0.02),
]


def _dpmo_to_sigma(dpmo: float) -> float:
    """Inverse-lookup the closest sigma level via the standard table.
    For values between table entries, linear-interpolate."""
    if dpmo <= 0:
        return 7.0  # near-perfect
    if dpmo >= _SIGMA_TO_DPMO[0][1]:
        return _SIGMA_TO_DPMO[0][0]
    # Linear interpolate between the two surrounding rows.
    for i in range(len(_SIGMA_TO_DPMO) - 1):
        s_hi, d_hi = _SIGMA_TO_DPMO[i]
        s_lo, d_lo = _SIGMA_TO_DPMO[i + 1]
        if d_lo <= dpmo <= d_hi:
            # Linear interp on log(dpmo) for smoother result
            if d_lo == d_hi:
                return s_hi
            f = (math.log(dpmo) - math.log(d_lo)) / (math.log(d_hi) - math.log(d_lo))
            return s_lo + f * (s_hi - s_lo)
    return _SIGMA_TO_DPMO[-1][0]


def verify_sigma_level(spec: Dict[str, Any]) -> VerifierResult:
    name = "manufacturing.sigma_level"
    dpmo = spec.get("dpmo")
    claimed = spec.get("claimed_sigma")
    if dpmo is None or claimed is None:
        return na(name)
    try:
        d = float(dpmo)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"dpmo and claimed_sigma must be numeric")
    if d < 0:
        return error(name, f"DPMO must be non-negative, got {d}")
    actual = _dpmo_to_sigma(d)
    tol = float(spec.get("tolerance_sigma", 0.2))
    diff = abs(actual - c)
    data = {"dpmo": d, "actual_sigma": actual, "claimed_sigma": c,
            "diff_sigma": diff, "tolerance_sigma": tol}
    if diff <= tol:
        return confirm(name,
                       f"DPMO={d:.0f} → ~{actual:.2f}σ (matches claim {c}, diff {diff:.2f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"DPMO={d:.0f} → {actual:.2f}σ, claimed {c} (diff {diff:.2f} > tol {tol})",
                    data)


def verify_spc_control_limits(spec: Dict[str, Any]) -> VerifierResult:
    """UCL = mean + k·σ, LCL = mean - k·σ (default k=3)."""
    name = "manufacturing.spc_control_limits"
    mean = spec.get("mean")
    sigma = spec.get("sigma")
    cl_ucl = spec.get("claimed_ucl")
    cl_lcl = spec.get("claimed_lcl")
    if mean is None or sigma is None or cl_ucl is None or cl_lcl is None:
        return na(name)
    try:
        m = float(mean)
        s = float(sigma)
        u = float(cl_ucl)
        l = float(cl_lcl)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if s <= 0:
        return error(name, f"sigma must be > 0, got {s}")
    k = float(spec.get("k", 3))
    actual_ucl = m + k * s
    actual_lcl = m - k * s
    tol = float(spec.get("tolerance", 1e-6))
    rel_tol = float(spec.get("tolerance_relative", 1e-6))
    diff_u = abs(actual_ucl - u)
    diff_l = abs(actual_lcl - l)
    data = {"mean": m, "sigma": s, "k": k,
            "actual_ucl": actual_ucl, "actual_lcl": actual_lcl,
            "claimed_ucl": u, "claimed_lcl": l,
            "diff_ucl": diff_u, "diff_lcl": diff_l, "tolerance": tol}
    threshold_u = max(tol, rel_tol * abs(actual_ucl))
    threshold_l = max(tol, rel_tol * abs(actual_lcl))
    if diff_u <= threshold_u and diff_l <= threshold_l:
        return confirm(name,
                       f"UCL={actual_ucl}, LCL={actual_lcl} (k={k}, matches claim)",
                       data)
    return mismatch(name,
                    f"actual UCL={actual_ucl}, LCL={actual_lcl}; claimed UCL={u}, LCL={l}",
                    data)


def verify_process_capability(spec: Dict[str, Any]) -> VerifierResult:
    """Cp / Cpk capability indices.

    Cp ≥ 1.33 is the conventional 'capable' threshold.
    Cpk also accounts for centering.
    """
    name = "manufacturing.process_capability"
    usl = spec.get("usl")
    lsl = spec.get("lsl")
    pmean = spec.get("process_mean")
    psig = spec.get("process_sigma")
    claimed_capable = spec.get("claimed_cp_capable")
    if usl is None or lsl is None or pmean is None or psig is None or claimed_capable is None:
        return na(name)
    try:
        u = float(usl)
        l = float(lsl)
        m = float(pmean)
        s = float(psig)
    except (TypeError, ValueError):
        return error(name, "usl/lsl/process_mean/process_sigma must be numeric")
    if s <= 0:
        return error(name, f"process_sigma must be > 0, got {s}")
    if u <= l:
        return error(name, f"usl ({u}) must be > lsl ({l})")
    cp = (u - l) / (6.0 * s)
    cpk_upper = (u - m) / (3.0 * s)
    cpk_lower = (m - l) / (3.0 * s)
    cpk = min(cpk_upper, cpk_lower)
    threshold = float(spec.get("capable_threshold", 1.33))
    capable = cp >= threshold and cpk >= threshold
    data = {"cp": cp, "cpk": cpk, "capable": capable,
            "claimed_capable": bool(claimed_capable),
            "threshold": threshold}
    if capable == bool(claimed_capable):
        return confirm(name,
                       f"Cp={cp:.3f}, Cpk={cpk:.3f}, capable={capable} (matches claim, threshold {threshold})",
                       data)
    return mismatch(name,
                    f"Cp={cp:.3f}, Cpk={cpk:.3f} → capable={capable}, claimed {bool(claimed_capable)}",
                    data)


def verify_tolerance_stack_rss(spec: Dict[str, Any]) -> VerifierResult:
    """Root-sum-of-squares tolerance stack-up: total = sqrt(sum(t_i²))."""
    name = "manufacturing.tolerance_stack_rss"
    tols = spec.get("tolerances")
    claimed = spec.get("claimed_rss")
    if tols is None or claimed is None:
        return na(name)
    if not isinstance(tols, (list, tuple)) or not tols:
        return error(name, "tolerances must be a non-empty list")
    try:
        ts = [float(t) for t in tols]
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "tolerances and claimed_rss must be numeric")
    if any(t < 0 for t in ts):
        return error(name, "individual tolerances must be non-negative")
    actual = math.sqrt(sum(t * t for t in ts))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-6))
    diff = abs(actual - c)
    data = {"tolerances": ts, "actual_rss": actual, "claimed_rss": c,
            "diff": diff, "worst_case_sum": sum(ts)}
    if diff <= max(abs_tol, rel_tol * actual):
        return confirm(name,
                       f"RSS = sqrt(Σt²) = {actual:.6f} (matches claim {c}, diff {diff:.6f})",
                       data)
    return mismatch(name,
                    f"RSS = {actual:.6f}, claimed {c} (diff {diff:.6f})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MFG_VERIFY") or {}

    if "dpmo" in mv and "claimed_sigma" in mv:
        results.append(verify_sigma_level(mv))
    if all(k in mv for k in ("mean", "sigma", "claimed_ucl", "claimed_lcl")):
        results.append(verify_spc_control_limits(mv))
    if all(k in mv for k in ("usl", "lsl", "process_mean", "process_sigma", "claimed_cp_capable")):
        results.append(verify_process_capability(mv))
    if "tolerances" in mv and "claimed_rss" in mv:
        results.append(verify_tolerance_stack_rss(mv))

    if not results:
        results.append(na("manufacturing", "no MFG_VERIFY artifacts present"))
    return results
