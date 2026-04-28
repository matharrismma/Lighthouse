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

    if not results:
        results.append(na("biology", "no BIO_VERIFY artifacts present"))
    return results
