"""Optics verifier (engineering / physical-substance grid axis).

Snell's law, thin-lens equation, magnification, and Rayleigh diffraction
limit. All formulas public-domain.

Checks:
  * optics.snell_law          — n1·sin(θ1) = n2·sin(θ2)
  * optics.thin_lens          — 1/f = 1/d_o + 1/d_i
  * optics.magnification      — M = -d_i / d_o
  * optics.rayleigh_diffraction — θ_min ≈ 1.22·λ/D

OPT_VERIFY shape (any subset):
    {
      "n1": 1.0, "n2": 1.5, "theta1_deg": 30,
      "claimed_theta2_deg": 19.47,

      "focal_length_m": 0.05,
      "object_distance_m": 0.10, "image_distance_m": 0.10,
      "claimed_thin_lens_consistent": true,

      "object_distance_for_M": 0.10, "image_distance_for_M": 0.10,
      "claimed_magnification": -1.0,

      "wavelength_m": 5.5e-7, "aperture_m": 0.1,
      "claimed_diffraction_rad": 6.71e-6,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _close(a, b, rel_tol=1e-3, abs_tol=1e-9):
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), 1.0))


def verify_snell_law(spec: Dict[str, Any]) -> VerifierResult:
    """n1·sin(θ1) = n2·sin(θ2)."""
    name = "optics.snell_law"
    n1 = spec.get("n1")
    n2 = spec.get("n2")
    t1 = spec.get("theta1_deg")
    claimed = spec.get("claimed_theta2_deg")
    if n1 is None or n2 is None or t1 is None or claimed is None:
        return na(name)
    # Accept 'TIR' / 'tir' as the explicit total-internal-reflection claim.
    claimed_is_tir = isinstance(claimed, str) and claimed.lower() == "tir"
    try:
        n1f, n2f, t1f = float(n1), float(n2), float(t1)
        c = None if claimed_is_tir else float(claimed)
    except (TypeError, ValueError):
        return error(name, "n1/n2/theta1_deg must be numeric, claimed_theta2_deg numeric or 'TIR'")
    if n1f <= 0 or n2f <= 0:
        return error(name, "refractive indices must be positive")
    sin_t2 = (n1f / n2f) * math.sin(math.radians(t1f))
    if abs(sin_t2) > 1:
        if claimed_is_tir:
            return confirm(name, "total internal reflection (no real θ₂); matches TIR claim",
                           {"sin_theta2": sin_t2, "n1": n1f, "n2": n2f, "theta1_deg": t1f,
                            "claimed": "TIR"})
        return mismatch(name,
                        f"total internal reflection (sin θ₂ = {sin_t2:.3f} > 1); "
                        f"no real θ₂ to compare against claim {c}",
                        {"sin_theta2": sin_t2, "claimed": c})
    actual = math.degrees(math.asin(sin_t2))
    if claimed_is_tir:
        return mismatch(name,
                        f"refraction occurs (θ₂={actual:.3f}°), claimed TIR",
                        {"actual_theta2_deg": actual, "claimed": "TIR"})
    diff = abs(actual - c)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    threshold = max(0.05, rel_tol * abs(actual))
    data = {"n1": n1f, "n2": n2f, "theta1_deg": t1f,
            "actual_theta2_deg": actual, "claimed_theta2_deg": c,
            "diff_deg": diff, "formula": "n1·sin(θ1) = n2·sin(θ2)"}
    if diff <= threshold:
        return confirm(name,
                       f"θ₂ = arcsin(({n1f}/{n2f})·sin({t1f}°)) = {actual:.3f}° (matches claim {c})",
                       data)
    return mismatch(name,
                    f"θ₂ = {actual:.3f}°, claimed {c}° (diff {diff:.3f}°)",
                    data)


def verify_thin_lens(spec: Dict[str, Any]) -> VerifierResult:
    """1/f = 1/d_o + 1/d_i."""
    name = "optics.thin_lens"
    f = spec.get("focal_length_m")
    do = spec.get("object_distance_m")
    di = spec.get("image_distance_m")
    claimed = spec.get("claimed_thin_lens_consistent")
    if f is None or do is None or di is None or claimed is None:
        return na(name)
    try:
        ff, dof, dif = float(f), float(do), float(di)
    except (TypeError, ValueError):
        return error(name, "focal_length / distances must be numeric")
    if ff == 0 or dof == 0 or dif == 0:
        return error(name, "focal_length and distances must be non-zero")
    rhs = (1.0 / dof) + (1.0 / dif)
    lhs = 1.0 / ff
    diff = abs(lhs - rhs)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    threshold = max(1e-6, rel_tol * abs(lhs))
    consistent = diff <= threshold
    data = {"focal_length": ff, "object_distance": dof, "image_distance": dif,
            "1_over_f": lhs, "1_over_do_plus_di": rhs, "diff": diff,
            "actual_consistent": consistent, "claimed_consistent": bool(claimed),
            "formula": "1/f = 1/d_o + 1/d_i"}
    if consistent == bool(claimed):
        return confirm(name,
                       f"1/f = {lhs:.6g}, 1/d_o + 1/d_i = {rhs:.6g}; consistent={consistent} matches claim",
                       data)
    return mismatch(name,
                    f"1/f = {lhs:.6g}, 1/d_o+1/d_i = {rhs:.6g}, diff {diff:.6g}; actual={consistent}, claimed {bool(claimed)}",
                    data)


def verify_magnification(spec: Dict[str, Any]) -> VerifierResult:
    """M = -d_i / d_o (sign convention: real image inverted)."""
    name = "optics.magnification"
    do = spec.get("object_distance_for_M")
    di = spec.get("image_distance_for_M")
    claimed = spec.get("claimed_magnification")
    if do is None or di is None or claimed is None:
        return na(name)
    try:
        dof, dif, c = float(do), float(di), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if dof == 0:
        return error(name, "object distance cannot be zero")
    actual = -dif / dof
    diff = abs(actual - c)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    threshold = max(1e-3, rel_tol * abs(actual))
    data = {"object_distance": dof, "image_distance": dif,
            "actual_magnification": actual, "claimed_magnification": c,
            "diff": diff, "formula": "M = −d_i / d_o"}
    if diff <= threshold:
        return confirm(name,
                       f"M = -{dif}/{dof} = {actual:.4f} (matches claim {c})",
                       data)
    return mismatch(name,
                    f"M = {actual:.4f}, claimed {c} (diff {diff:.4f})",
                    data)


def verify_rayleigh_diffraction(spec: Dict[str, Any]) -> VerifierResult:
    """θ_min ≈ 1.22 · λ / D (Rayleigh's criterion for circular aperture)."""
    name = "optics.rayleigh_diffraction"
    lam = spec.get("wavelength_m")
    D = spec.get("aperture_m")
    claimed = spec.get("claimed_diffraction_rad")
    if lam is None or D is None or claimed is None:
        return na(name)
    try:
        lf, Df, c = float(lam), float(D), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if lf <= 0 or Df <= 0:
        return error(name, "wavelength and aperture must be positive")
    actual = 1.22 * lf / Df
    diff = abs(actual - c)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    threshold = max(1e-9, rel_tol * abs(actual))
    data = {"wavelength_m": lf, "aperture_m": Df,
            "actual_diffraction_rad": actual, "claimed_diffraction_rad": c,
            "diff": diff, "formula": "θ_min = 1.22·λ/D"}
    if diff <= threshold:
        return confirm(name,
                       f"θ_min = 1.22·{lf:.3g}/{Df:.3g} = {actual:.3e} rad (matches claim)",
                       data)
    return mismatch(name,
                    f"θ_min = {actual:.3e} rad, claimed {c:.3e} (diff {diff:.3e})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ov = packet.get("OPT_VERIFY") or {}

    if all(ov.get(k) is not None for k in ("n1", "n2", "theta1_deg", "claimed_theta2_deg")):
        results.append(verify_snell_law(ov))
    if all(ov.get(k) is not None for k in ("focal_length_m", "object_distance_m",
                                            "image_distance_m", "claimed_thin_lens_consistent")):
        results.append(verify_thin_lens(ov))
    if all(ov.get(k) is not None for k in ("object_distance_for_M", "image_distance_for_M", "claimed_magnification")):
        results.append(verify_magnification(ov))
    if all(ov.get(k) is not None for k in ("wavelength_m", "aperture_m", "claimed_diffraction_rad")):
        results.append(verify_rayleigh_diffraction(ov))

    if not results:
        results.append(na("optics", "no OPT_VERIFY artifacts present"))
    return results
