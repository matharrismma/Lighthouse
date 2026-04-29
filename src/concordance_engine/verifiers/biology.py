"""Biology verifier.

Checks performed (all on artifacts the packet supplies; the existing
biology validator continues to check attestation flags separately):

  * replicates_minimum: claimed n_replicates >= required minimum
    (default 3 biological replicates, configurable)
  * orthogonal_assays: at least N distinct assay classes used
    (default 2; e.g. genetic + biochemical, or imaging + functional)
  * dose_response_monotonicity: if dose-response data is supplied,
    verify the response is monotonic (increasing or decreasing) in dose,
    or that any non-monotonic pattern is explicitly justified
  * sample_size_powered: if effect_size and alpha are given, verify the
    sample size is adequate to detect that effect at 80% power for a
    two-sample t-test (z-approximation, fast)

Format expected in BIO_VERIFY:
    {
      "n_replicates": 4,
      "min_replicates": 3,
      "assay_classes": ["qPCR", "western_blot", "imaging"],
      "min_assay_classes": 2,
      "dose_response": {
          "doses": [0, 1, 5, 25, 125],
          "responses": [0.1, 0.3, 0.5, 0.8, 0.95],
          "expected_direction": "increasing"
      },
      "power_analysis": {
          "effect_size": 0.5,
          "alpha": 0.05,
          "n_per_group": 64
      }
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_replicates(spec: Dict[str, Any]) -> VerifierResult:
    n = spec.get("n_replicates")
    minimum = spec.get("min_replicates", 3)
    if n is None:
        return na("biology.replicates")
    try:
        n = int(n)
        minimum = int(minimum)
    except (ValueError, TypeError):
        return error("biology.replicates", f"non-integer values: n={n}, min={minimum}")
    if n >= minimum:
        return confirm("biology.replicates", f"n_replicates={n} >= minimum {minimum}")
    return mismatch("biology.replicates", f"n_replicates={n} below minimum {minimum}")


def verify_orthogonal_assays(spec: Dict[str, Any]) -> VerifierResult:
    assays = spec.get("assay_classes")
    minimum = spec.get("min_assay_classes", 2)
    if not assays:
        return na("biology.orthogonal_assays")
    if not isinstance(assays, list):
        return error("biology.orthogonal_assays", f"assay_classes must be a list, got {type(assays).__name__}")
    unique = sorted(set(str(a) for a in assays))
    if len(unique) >= minimum:
        return confirm("biology.orthogonal_assays",
                       f"{len(unique)} distinct assay classes: {unique} >= minimum {minimum}")
    return mismatch("biology.orthogonal_assays",
                    f"only {len(unique)} distinct assay classes ({unique}), need {minimum}")


def verify_dose_response_monotonicity(spec: Dict[str, Any]) -> VerifierResult:
    dr = spec.get("dose_response")
    if not dr:
        return na("biology.dose_response")
    doses = dr.get("doses")
    responses = dr.get("responses")
    direction = (dr.get("expected_direction") or "").lower()
    tolerance = dr.get("tolerance", 0.0)  # allow small noise

    if not doses or not responses:
        return error("biology.dose_response", "doses or responses missing")
    if len(doses) != len(responses):
        return error("biology.dose_response",
                     f"doses ({len(doses)}) and responses ({len(responses)}) length mismatch")

    # Sort by dose
    pairs = sorted(zip(doses, responses), key=lambda x: x[0])
    sorted_doses = [p[0] for p in pairs]
    sorted_resp = [p[1] for p in pairs]

    diffs = [sorted_resp[i+1] - sorted_resp[i] for i in range(len(sorted_resp) - 1)]

    # Allow zero or near-zero diffs but no sign-reversal beyond tolerance
    n_up = sum(1 for d in diffs if d > tolerance)
    n_down = sum(1 for d in diffs if d < -tolerance)
    n_flat = sum(1 for d in diffs if abs(d) <= tolerance)

    data = {"doses": sorted_doses, "responses": sorted_resp,
            "n_up": n_up, "n_down": n_down, "n_flat": n_flat}

    if direction == "increasing":
        if n_down == 0:
            return confirm("biology.dose_response",
                           f"monotonically non-decreasing: {n_up} up, {n_flat} flat", data)
        return mismatch("biology.dose_response",
                        f"non-monotonic increasing: {n_down} reversals (down) detected", data)
    elif direction == "decreasing":
        if n_up == 0:
            return confirm("biology.dose_response",
                           f"monotonically non-increasing: {n_down} down, {n_flat} flat", data)
        return mismatch("biology.dose_response",
                        f"non-monotonic decreasing: {n_up} reversals (up) detected", data)
    else:
        # No expected direction stated — flag any non-monotonic shape for investigation
        if n_up == 0 or n_down == 0:
            return confirm("biology.dose_response",
                           f"monotonic (n_up={n_up}, n_down={n_down}, n_flat={n_flat})", data)
        return mismatch("biology.dose_response",
                        f"non-monotonic without expected_direction declared "
                        f"(n_up={n_up}, n_down={n_down}); declare expected_direction "
                        f"or justify biphasic response", data)


def verify_sample_size_powered(spec: Dict[str, Any]) -> VerifierResult:
    """Approximate two-sample t-test power calculation.

    Required minimum n per group for power = 0.80, two-sided alpha:
        n = 2 * ((z_alpha/2 + z_beta) / d)^2 + 1
    """
    pa = spec.get("power_analysis")
    if not pa:
        return na("biology.power")
    d = pa.get("effect_size")
    alpha = pa.get("alpha", 0.05)
    n = pa.get("n_per_group")
    target_power = pa.get("target_power", 0.80)

    if d is None or n is None:
        return na("biology.power")

    try:
        from scipy.stats import norm
        z_alpha = norm.ppf(1 - alpha / 2.0)
        z_beta = norm.ppf(target_power)
        d = float(d)
        if d <= 0:
            return error("biology.power", f"effect_size must be positive, got {d}")
        n_required = math.ceil(2 * ((z_alpha + z_beta) / d) ** 2) + 1
    except Exception as e:
        return error("biology.power", f"computation failure: {e}")

    data = {"d": d, "alpha": alpha, "target_power": target_power,
            "n_per_group": n, "n_required": n_required}
    if n >= n_required:
        return confirm("biology.power",
                       f"n_per_group={n} >= required {n_required} for d={d}, "
                       f"alpha={alpha}, power={target_power}", data)
    return mismatch("biology.power",
                    f"n_per_group={n} below required {n_required} for d={d}, "
                    f"alpha={alpha}, power={target_power}", data)


def verify_hardy_weinberg(spec):
    """Verify observed AA/Aa/aa genotype counts are HWE-consistent."""
    obs = spec.get("counts") or spec.get("observed")
    if not obs or len(obs) != 3:
        return na("biology.hardy_weinberg")
    AA, Aa, aa = (float(obs[0]), float(obs[1]), float(obs[2]))
    n = AA + Aa + aa
    if n <= 0:
        return error("biology.hardy_weinberg", "no individuals counted")
    p = (2*AA + Aa) / (2*n)
    q = 1 - p
    exp_AA = (p*p) * n
    exp_Aa = (2*p*q) * n
    exp_aa = (q*q) * n
    chi2 = 0.0
    for o, e in zip([AA, Aa, aa], [exp_AA, exp_Aa, exp_aa]):
        if e > 0:
            chi2 += (o - e) ** 2 / e
    # df = 1 (k=3 categories - 1 estimated parameter - 1)
    from scipy import stats as _st
    pval = float(_st.chi2.sf(chi2, df=1))
    alpha = float(spec.get("alpha", 0.05))
    data = {"p_allele_freq": p, "q_allele_freq": q,
            "expected": [exp_AA, exp_Aa, exp_aa],
            "chi2": chi2, "df": 1, "p_value": pval, "alpha": alpha}
    if pval >= alpha:
        return confirm("biology.hardy_weinberg",
                       f"counts consistent with HWE (chi2={chi2:.3f}, p={pval:.3g} >= {alpha})", data)
    return mismatch("biology.hardy_weinberg",
                    f"counts inconsistent with HWE (chi2={chi2:.3f}, p={pval:.3g} < {alpha})", data)


def verify_primer(spec):
    """Sanity-check a primer sequence: GC% in [40,60], Tm in [50,65] (Wallace) or supplied range."""
    seq = (spec.get("sequence") or "").upper().strip()
    if not seq:
        return na("biology.primer")
    if not all(b in "ACGTU" for b in seq):
        return mismatch("biology.primer", f"sequence contains non-DNA characters: {seq!r}")
    s = seq.replace("U", "T")
    n = len(s)
    gc = (s.count("G") + s.count("C")) / n * 100
    a = s.count("A"); t = s.count("T")
    g = s.count("G"); c = s.count("C")
    # Wallace rule for short primers
    tm = 2 * (a + t) + 4 * (g + c)
    gc_lo, gc_hi = spec.get("gc_range", [40.0, 60.0])
    tm_lo, tm_hi = spec.get("tm_range", [50.0, 65.0])
    fails = []
    if not (gc_lo <= gc <= gc_hi):
        fails.append(f"GC%={gc:.1f} outside [{gc_lo},{gc_hi}]")
    if not (tm_lo <= tm <= tm_hi):
        fails.append(f"Tm={tm}C outside [{tm_lo},{tm_hi}]")
    if not (15 <= n <= 30):
        fails.append(f"length={n} outside [15,30]")
    data = {"length": n, "gc_percent": gc, "tm_wallace_C": tm}
    if fails:
        return mismatch("biology.primer", "; ".join(fails), data)
    return confirm("biology.primer",
                   f"primer {seq} OK: len={n}, GC={gc:.1f}%, Tm={tm}C", data)


def verify_molarity(spec):
    """Check stated molarity arithmetic: M = moles/L, or moles = mass/MW.

    spec keys: mass_g, mw_g_per_mol, volume_L, claimed_molarity (mol/L);
    OR moles, volume_L, claimed_molarity.
    """
    cl = spec.get("claimed_molarity")
    if cl is None:
        return na("biology.molarity")
    tol = float(spec.get("tolerance", 1e-3))
    try:
        if "moles" in spec:
            moles = float(spec["moles"])
        else:
            mass = float(spec["mass_g"])
            mw = float(spec["mw_g_per_mol"])
            if mw <= 0:
                return error("biology.molarity", f"non-positive MW: {mw}")
            moles = mass / mw
        v = float(spec["volume_L"])
        if v <= 0:
            return error("biology.molarity", f"non-positive volume: {v}")
        actual = moles / v
    except KeyError as e:
        return error("biology.molarity", f"missing field: {e}")
    diff = abs(actual - float(cl))
    data = {"computed_molarity": actual, "claimed_molarity": cl,
            "abs_diff": diff, "tolerance": tol}
    if diff <= tol or (cl != 0 and diff / abs(cl) <= tol):
        return confirm("biology.molarity",
                       f"computed {actual:.6g} M ~ claimed {cl} M (diff {diff:.2e})", data)
    return mismatch("biology.molarity",
                    f"computed {actual:.6g} M != claimed {cl} M (diff {diff:.2e})", data)


def verify_mendelian(spec):
    """Chi-squared test of observed counts against an expected Mendelian ratio."""
    obs = spec.get("observed")
    ratio = spec.get("expected_ratio")  # e.g. [9, 3, 3, 1]
    if not obs or not ratio:
        return na("biology.mendelian")
    if len(obs) != len(ratio):
        return error("biology.mendelian",
                     f"obs/ratio length mismatch: {len(obs)} vs {len(ratio)}")
    n = sum(obs)
    rs = sum(ratio)
    if n <= 0 or rs <= 0:
        return error("biology.mendelian", "zero total")
    expected = [n * r / rs for r in ratio]
    chi2 = sum((o - e) ** 2 / e for o, e in zip(obs, expected) if e > 0)
    from scipy import stats as _st
    df = len(obs) - 1
    pval = float(_st.chi2.sf(chi2, df=df))
    alpha = float(spec.get("alpha", 0.05))
    data = {"expected": expected, "chi2": chi2, "df": df, "p_value": pval, "alpha": alpha}
    if pval >= alpha:
        return confirm("biology.mendelian",
                       f"observed consistent with ratio {ratio} (chi2={chi2:.3f}, p={pval:.3g})", data)
    return mismatch("biology.mendelian",
                    f"observed inconsistent with ratio {ratio} (chi2={chi2:.3f}, p={pval:.3g})", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    bv = packet.get("BIO_VERIFY") or {}

    if "n_replicates" in bv:
        results.append(verify_replicates(bv))
    if "assay_classes" in bv:
        results.append(verify_orthogonal_assays(bv))
    if "dose_response" in bv:
        results.append(verify_dose_response_monotonicity(bv))
    if "power_analysis" in bv:
        results.append(verify_sample_size_powered(bv))
    if "hardy_weinberg" in bv:
        results.append(verify_hardy_weinberg(bv["hardy_weinberg"]))
    if "primer" in bv:
        results.append(verify_primer(bv["primer"]))
    if "molarity" in bv:
        results.append(verify_molarity(bv["molarity"]))
    if "mendelian" in bv:
        results.append(verify_mendelian(bv["mendelian"]))

    if not results:
        results.append(na("biology", "no BIO_VERIFY artifacts present"))
    return results
