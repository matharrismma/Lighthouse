"""Geology verifier (physical-substance + time-sequence grid axes).

Radiometric dating, Mohs hardness comparisons, Richter magnitude.
Public-domain (USGS, generic textbook physics).

Checks:
  * geology.radiometric_decay   — N(t) = N₀ · 2^(-t/T_half)
  * geology.mohs_scratch        — harder material scratches softer
  * geology.richter_amplitude   — A2/A1 = 10^(M2 - M1)

GEO_VERIFY shape (any subset):
    {
      "isotope_half_life_years": 5730,
      "elapsed_years": 5730,
      "initial_amount": 1.0,
      "claimed_remaining_amount": 0.5,

      "harder_mineral_mohs": 7,
      "softer_mineral_mohs": 5,
      "claimed_can_scratch": true,

      "richter_M1": 5.0,
      "richter_M2": 7.0,
      "claimed_amplitude_ratio": 100.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_radiometric_decay(spec: Dict[str, Any]) -> VerifierResult:
    name = "geology.radiometric_decay"
    T = spec.get("isotope_half_life_years")
    t = spec.get("elapsed_years")
    N0 = spec.get("initial_amount")
    claimed = spec.get("claimed_remaining_amount")
    if T is None or t is None or N0 is None or claimed is None:
        return na(name)
    try:
        Tf, tf, N0f, c = float(T), float(t), float(N0), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if Tf <= 0:
        return error(name, f"half-life must be positive, got {Tf}")
    if tf < 0 or N0f < 0:
        return error(name, "elapsed_years and initial_amount must be non-negative")
    actual = N0f * (0.5 ** (tf / Tf))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"half_life_years": Tf, "elapsed_years": tf,
            "initial_amount": N0f, "actual_remaining": actual,
            "claimed_remaining": c, "diff": diff,
            "n_half_lives": tf / Tf,
            "formula": "N(t) = N₀ · 2^(−t/T_½)"}
    if diff <= threshold:
        return confirm(name,
                       f"{N0f} · 2^(−{tf}/{Tf}) = {actual:.6g} after {tf/Tf:.3g} half-lives "
                       f"(matches claim {c})",
                       data)
    return mismatch(name,
                    f"actual {actual:.6g}, claimed {c} (diff {diff:.6g})",
                    data)


def verify_mohs_scratch(spec: Dict[str, Any]) -> VerifierResult:
    name = "geology.mohs_scratch"
    h = spec.get("harder_mineral_mohs")
    s = spec.get("softer_mineral_mohs")
    claimed = spec.get("claimed_can_scratch")
    if h is None or s is None or claimed is None:
        return na(name)
    try:
        hf, sf = float(h), float(s)
    except (TypeError, ValueError):
        return error(name, "Mohs values must be numeric")
    if not (1 <= hf <= 10) or not (1 <= sf <= 10):
        return error(name, "Mohs scale is 1-10 (talc to diamond)")
    actual = hf > sf  # strictly harder
    data = {"harder_mohs": hf, "softer_mohs": sf,
            "actual_can_scratch": actual,
            "claimed_can_scratch": bool(claimed),
            "rule": "harder mineral scratches softer mineral (strict inequality)"}
    if actual == bool(claimed):
        return confirm(name,
                       f"Mohs {hf} {'>' if actual else '≤'} {sf} → can_scratch={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"Mohs {hf} vs {sf} → can_scratch={actual}, claimed {bool(claimed)}",
                    data)


def verify_richter_amplitude(spec: Dict[str, Any]) -> VerifierResult:
    """A2/A1 = 10^(M2 − M1). +1 magnitude = 10× amplitude."""
    name = "geology.richter_amplitude"
    M1 = spec.get("richter_M1")
    M2 = spec.get("richter_M2")
    claimed = spec.get("claimed_amplitude_ratio")
    if M1 is None or M2 is None or claimed is None:
        return na(name)
    try:
        M1f, M2f, c = float(M1), float(M2), float(claimed)
    except (TypeError, ValueError):
        return error(name, "magnitudes and claimed_amplitude_ratio must be numeric")
    actual = 10.0 ** (M2f - M1f)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    diff = abs(actual - c)
    threshold = max(1e-6, rel_tol * abs(actual))
    data = {"M1": M1f, "M2": M2f, "actual_ratio": actual,
            "claimed_ratio": c, "diff": diff,
            "formula": "A₂/A₁ = 10^(M₂−M₁)"}
    if diff <= threshold:
        return confirm(name,
                       f"10^({M2f}−{M1f}) = {actual:.4g} (matches claim {c})",
                       data)
    return mismatch(name,
                    f"A2/A1 = {actual:.4g}, claimed {c} (diff {diff:.4g})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    gv = packet.get("GEO_VERIFY") or {}
    if all(gv.get(k) is not None for k in ("isotope_half_life_years", "elapsed_years",
                                            "initial_amount", "claimed_remaining_amount")):
        results.append(verify_radiometric_decay(gv))
    if all(gv.get(k) is not None for k in ("harder_mineral_mohs", "softer_mineral_mohs", "claimed_can_scratch")):
        results.append(verify_mohs_scratch(gv))
    if all(gv.get(k) is not None for k in ("richter_M1", "richter_M2", "claimed_amplitude_ratio")):
        results.append(verify_richter_amplitude(gv))
    if not results:
        results.append(na("geology", "no GEO_VERIFY artifacts present"))
    return results
