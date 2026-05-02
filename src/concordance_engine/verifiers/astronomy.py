"""Astronomy verifier (engineering / physical-substance grid axis).

Deterministic checks against canonical celestial-mechanics formulas:
Kepler's 3rd law, Newtonian gravity, stellar parallax distance, and
the apparent-magnitude inverse-square law.

Public-domain references (NASA, IAU, generic textbooks). All physical
constants embedded as Python module constants.

Checks performed:

  * astronomy.kepler_third_law
      For solar-system orbits: T² (years²) = a³ (AU³). For arbitrary
      central masses, use the gravitational form: T² = 4π²·a³/(G·M).
  * astronomy.gravitational_force
      F = G·m₁·m₂ / r² matches claim.
  * astronomy.parallax_distance
      d (parsecs) = 1 / p (arcseconds). The fundamental stellar-distance
      formula.
  * astronomy.apparent_magnitude_distance
      Magnitude difference m - M = 5·log₁₀(d) - 5 (where d is in pc).
      Used to convert apparent → absolute magnitude given distance.

ASTRO_VERIFY packet shape (any subset of fields):
    {
      "orbital_period_years": 1.0,
      "semi_major_axis_au": 1.0,
      "claimed_kepler_consistent": true,

      "mass_1_kg": 5.972e24,
      "mass_2_kg": 7.342e22,
      "separation_m": 3.84e8,
      "claimed_gravitational_force_N": 1.98e20,

      "parallax_arcsec": 0.769,
      "claimed_distance_parsec": 1.30,

      "apparent_magnitude": 5.0,
      "absolute_magnitude": 4.83,
      "claimed_distance_parsec": 10.8,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# Newtonian gravitational constant (SI: m³ kg⁻¹ s⁻²). CODATA 2018.
_G = 6.67430e-11

# 1 parsec in meters (IAU 2015 nominal).
_PARSEC_M = 3.0856775814913673e16


def verify_kepler_third_law(spec: Dict[str, Any]) -> VerifierResult:
    """Solar-system simplification: T² (yr²) ≈ a³ (AU³).

    The claim is binary: 'is this orbit consistent with Kepler's 3rd law
    for the Sun?' True iff |T² - a³| / a³ <= tolerance_relative.
    """
    name = "astronomy.kepler_third_law"
    T = spec.get("orbital_period_years")
    a = spec.get("semi_major_axis_au")
    claimed = spec.get("claimed_kepler_consistent")
    if T is None or a is None or claimed is None:
        return na(name)
    try:
        Tf = float(T)
        af = float(a)
    except (TypeError, ValueError):
        return error(name, "orbital_period_years and semi_major_axis_au must be numeric")
    if Tf <= 0 or af <= 0:
        return error(name, f"period and semi-major axis must be positive, got T={Tf}, a={af}")
    T_squared = Tf * Tf
    a_cubed = af ** 3
    rel_diff = abs(T_squared - a_cubed) / a_cubed
    tol = float(spec.get("tolerance_relative", 0.05))
    consistent = rel_diff <= tol
    data = {"orbital_period_years": Tf, "semi_major_axis_au": af,
            "T_squared": T_squared, "a_cubed": a_cubed,
            "relative_diff": rel_diff, "tolerance_relative": tol,
            "actual_consistent": consistent, "claimed_consistent": bool(claimed),
            "reference": "Kepler's 3rd law (heliocentric, solar-system units)"}
    if consistent == bool(claimed):
        return confirm(name,
                       f"T²={T_squared:.4f} vs a³={a_cubed:.4f} (rel diff {rel_diff:.4f}); "
                       f"consistent={consistent} matches claim",
                       data)
    return mismatch(name,
                    f"T²={T_squared:.4f}, a³={a_cubed:.4f}, rel diff {rel_diff:.4f} > tol {tol}; "
                    f"actual consistent={consistent}, claimed {bool(claimed)}",
                    data)


def verify_gravitational_force(spec: Dict[str, Any]) -> VerifierResult:
    """Newton's law of universal gravitation: F = G·m₁·m₂ / r²."""
    name = "astronomy.gravitational_force"
    m1 = spec.get("mass_1_kg")
    m2 = spec.get("mass_2_kg")
    r = spec.get("separation_m")
    claimed = spec.get("claimed_gravitational_force_N")
    if m1 is None or m2 is None or r is None or claimed is None:
        return na(name)
    try:
        m1f = float(m1)
        m2f = float(m2)
        rf = float(r)
        cf = float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if m1f <= 0 or m2f <= 0:
        return error(name, f"masses must be positive (got {m1f}, {m2f})")
    if rf <= 0:
        return error(name, f"separation must be positive (got {rf})")
    actual = _G * m1f * m2f / (rf * rf)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    diff = abs(actual - cf)
    threshold = rel_tol * abs(actual)
    data = {"mass_1_kg": m1f, "mass_2_kg": m2f, "separation_m": rf,
            "actual_force_N": actual, "claimed_force_N": cf, "diff_N": diff,
            "G": _G, "formula": "F = G·m₁·m₂/r²"}
    if diff <= threshold:
        return confirm(name,
                       f"F = G·m₁·m₂/r² = {actual:.4e} N (matches claim {cf:.4e})",
                       data)
    return mismatch(name,
                    f"F = {actual:.4e} N, claimed {cf:.4e} N (diff {diff:.4e} > {threshold:.4e})",
                    data)


def verify_parallax_distance(spec: Dict[str, Any]) -> VerifierResult:
    """d (parsecs) = 1 / p (arcseconds)."""
    name = "astronomy.parallax_distance"
    p = spec.get("parallax_arcsec")
    claimed = spec.get("claimed_distance_parsec")
    if p is None or claimed is None:
        return na(name)
    try:
        pf = float(p)
        cf = float(claimed)
    except (TypeError, ValueError):
        return error(name, "parallax and claimed_distance must be numeric")
    if pf <= 0:
        return error(name, f"parallax must be positive, got {pf}")
    actual = 1.0 / pf
    rel_tol = float(spec.get("tolerance_relative", 1e-2))
    diff = abs(actual - cf)
    threshold = max(0.01, rel_tol * abs(actual))
    data = {"parallax_arcsec": pf, "actual_distance_parsec": actual,
            "claimed_distance_parsec": cf, "diff_pc": diff,
            "formula": "d (pc) = 1 / p (arcsec)"}
    if diff <= threshold:
        return confirm(name,
                       f"d = 1/{pf}″ = {actual:.4f} pc (matches claim {cf})",
                       data)
    return mismatch(name,
                    f"d = {actual:.4f} pc, claimed {cf} (diff {diff:.4f})",
                    data)


def verify_distance_modulus(spec: Dict[str, Any]) -> VerifierResult:
    """m - M = 5·log₁₀(d) - 5, where d is in parsecs.

    Given apparent_magnitude m and absolute_magnitude M, derive distance
    and compare to the claim.
    """
    name = "astronomy.apparent_magnitude_distance"
    m = spec.get("apparent_magnitude")
    M = spec.get("absolute_magnitude")
    claimed = spec.get("claimed_distance_parsec")
    if m is None or M is None or claimed is None:
        return na(name)
    try:
        mf = float(m)
        Mf = float(M)
        cf = float(claimed)
    except (TypeError, ValueError):
        return error(name, "magnitudes and distance must be numeric")
    # m - M = 5·log10(d) - 5  ⇒  d = 10^((m - M + 5) / 5)
    actual = 10.0 ** ((mf - Mf + 5.0) / 5.0)
    rel_tol = float(spec.get("tolerance_relative", 5e-2))
    diff = abs(actual - cf)
    threshold = max(0.5, rel_tol * abs(actual))
    data = {"apparent_magnitude": mf, "absolute_magnitude": Mf,
            "actual_distance_parsec": actual, "claimed_distance_parsec": cf,
            "diff_pc": diff,
            "formula": "d = 10^((m - M + 5) / 5)"}
    if diff <= threshold:
        return confirm(name,
                       f"d = 10^(({mf}-{Mf}+5)/5) = {actual:.4f} pc (matches claim {cf})",
                       data)
    return mismatch(name,
                    f"d = {actual:.4f} pc, claimed {cf} (diff {diff:.4f})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    av = packet.get("ASTRO_VERIFY") or {}

    if all(k in av for k in ("orbital_period_years", "semi_major_axis_au", "claimed_kepler_consistent")):
        results.append(verify_kepler_third_law(av))
    if all(k in av for k in ("mass_1_kg", "mass_2_kg", "separation_m", "claimed_gravitational_force_N")):
        results.append(verify_gravitational_force(av))
    if "parallax_arcsec" in av and "claimed_distance_parsec" in av:
        # Disambiguate: if magnitudes are also present, the claimed_distance
        # is for the magnitude path. parallax check only runs when
        # magnitude fields are absent.
        if not ("apparent_magnitude" in av and "absolute_magnitude" in av):
            results.append(verify_parallax_distance(av))
    if all(k in av for k in ("apparent_magnitude", "absolute_magnitude", "claimed_distance_parsec")):
        results.append(verify_distance_modulus(av))

    if not results:
        results.append(na("astronomy", "no ASTRO_VERIFY artifacts present"))
    return results
