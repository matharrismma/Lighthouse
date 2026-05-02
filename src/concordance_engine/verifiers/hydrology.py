"""Hydrology verifier (physical-substance grid axis — water/fluid flow).

Manning's equation, Darcy's law, rational runoff, Bernoulli head.
Public-domain civil-engineering / water-resources formulas.

Checks:
  * hydrology.manning_velocity   — V = (1/n) · R^(2/3) · S^(1/2)  (SI; m/s)
  * hydrology.darcy_velocity     — q = K · i  (Darcy flux)
  * hydrology.rational_runoff    — Q = C · i · A  (rational method)
  * hydrology.bernoulli_head     — total head h = z + p/(ρg) + v²/(2g)

HYD_VERIFY shape (any subset):
    {
      "manning_n": 0.013, "hydraulic_radius_m": 1.0, "slope": 0.001,
      "claimed_velocity_m_s": 2.43,

      "darcy_K_m_s": 1.0e-4, "hydraulic_gradient": 0.01,
      "claimed_darcy_velocity_m_s": 1.0e-6,

      "runoff_coefficient": 0.7, "rainfall_intensity": 50.0,
      "drainage_area": 100.0, "claimed_runoff": 3500.0,

      "elevation_m": 10.0, "pressure_pa": 101325.0,
      "velocity_m_s": 2.0, "fluid_density_kg_m3": 1000.0,
      "claimed_total_head_m": 20.534,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_G = 9.80665  # standard gravity m/s²


def verify_manning_velocity(spec: Dict[str, Any]) -> VerifierResult:
    name = "hydrology.manning_velocity"
    n = spec.get("manning_n")
    R = spec.get("hydraulic_radius_m")
    S = spec.get("slope")
    claimed = spec.get("claimed_velocity_m_s")
    if any(v is None for v in (n, R, S, claimed)):
        return na(name)
    try:
        nf, Rf, Sf, c = float(n), float(R), float(S), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if nf <= 0 or Rf <= 0 or Sf < 0:
        return error(name, "n>0, R>0, S>=0 required")
    actual = (1.0 / nf) * (Rf ** (2.0 / 3.0)) * (Sf ** 0.5)
    rel_tol = float(spec.get("tolerance_relative", 0.01))
    diff = abs(actual - c)
    threshold = max(1e-6, rel_tol * actual) if actual > 0 else 1e-6
    data = {"n": nf, "R_m": Rf, "S": Sf,
            "actual_v_m_s": actual, "claimed_v_m_s": c, "diff": diff,
            "formula": "V = (1/n)·R^(2/3)·S^(1/2)  [SI]"}
    if diff <= threshold:
        return confirm(name, f"V = {actual:.4f} m/s (matches claim)", data)
    return mismatch(name, f"V = {actual:.4f} m/s, claimed {c} (diff {diff:.4f})", data)


def verify_darcy_velocity(spec: Dict[str, Any]) -> VerifierResult:
    name = "hydrology.darcy_velocity"
    K = spec.get("darcy_K_m_s")
    i = spec.get("hydraulic_gradient")
    claimed = spec.get("claimed_darcy_velocity_m_s")
    if any(v is None for v in (K, i, claimed)):
        return na(name)
    try:
        Kf, ig, c = float(K), float(i), float(claimed)
    except (TypeError, ValueError):
        return error(name, "K, i, and claim must be numeric")
    if Kf < 0:
        return error(name, "hydraulic conductivity must be non-negative")
    actual = Kf * ig
    rel_tol = float(spec.get("tolerance_relative", 0.01))
    diff = abs(actual - c)
    threshold = max(1e-15, rel_tol * abs(actual)) if actual != 0 else 1e-15
    data = {"K_m_s": Kf, "i": ig,
            "actual_q_m_s": actual, "claimed_q_m_s": c, "diff": diff,
            "formula": "q = K · i  (Darcy's law, magnitude)"}
    if diff <= threshold:
        return confirm(name, f"q = {actual:.6e} m/s (matches claim)", data)
    return mismatch(name, f"q = {actual:.6e} m/s, claimed {c} (diff {diff:.6e})", data)


def verify_rational_runoff(spec: Dict[str, Any]) -> VerifierResult:
    """Q = C · i · A. Units depend on convention; we just verify the product."""
    name = "hydrology.rational_runoff"
    C = spec.get("runoff_coefficient")
    i = spec.get("rainfall_intensity")
    A = spec.get("drainage_area")
    claimed = spec.get("claimed_runoff")
    if any(v is None for v in (C, i, A, claimed)):
        return na(name)
    try:
        Cf, If, Af, c = float(C), float(i), float(A), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if not (0 <= Cf <= 1):
        return error(name, f"runoff coefficient must be in [0, 1], got {Cf}")
    if If < 0 or Af < 0:
        return error(name, "rainfall intensity and area must be non-negative")
    actual = Cf * If * Af
    rel_tol = float(spec.get("tolerance_relative", 0.01))
    diff = abs(actual - c)
    threshold = max(1e-6, rel_tol * actual) if actual > 0 else 1e-6
    data = {"C": Cf, "i": If, "A": Af,
            "actual_runoff": actual, "claimed_runoff": c, "diff": diff,
            "formula": "Q = C · i · A  (rational method)"}
    if diff <= threshold:
        return confirm(name, f"Q = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"Q = {actual:.4f}, claimed {c} (diff {diff:.4f})", data)


def verify_bernoulli_head(spec: Dict[str, Any]) -> VerifierResult:
    """Total head h = z + p/(ρg) + v²/(2g)."""
    name = "hydrology.bernoulli_head"
    z = spec.get("elevation_m")
    p = spec.get("pressure_pa")
    v = spec.get("velocity_m_s")
    rho = spec.get("fluid_density_kg_m3")
    claimed = spec.get("claimed_total_head_m")
    if any(x is None for x in (z, p, v, rho, claimed)):
        return na(name)
    try:
        zf, pf, vf, rf, c = float(z), float(p), float(v), float(rho), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if rf <= 0:
        return error(name, "fluid density must be positive")
    actual = zf + pf / (rf * _G) + (vf * vf) / (2 * _G)
    rel_tol = float(spec.get("tolerance_relative", 0.01))
    diff = abs(actual - c)
    threshold = max(1e-3, rel_tol * abs(actual)) if actual != 0 else 1e-3
    data = {"z_m": zf, "p_pa": pf, "v_m_s": vf, "rho_kg_m3": rf,
            "actual_head_m": actual, "claimed_head_m": c, "diff_m": diff,
            "formula": "h = z + p/(ρg) + v²/(2g)"}
    if diff <= threshold:
        return confirm(name, f"head = {actual:.4f} m (matches claim)", data)
    return mismatch(name, f"head = {actual:.4f} m, claimed {c} (diff {diff:.4f})", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    hv = packet.get("HYD_VERIFY") or {}
    if all(k in hv for k in ("manning_n", "hydraulic_radius_m", "slope", "claimed_velocity_m_s")):
        results.append(verify_manning_velocity(hv))
    if all(k in hv for k in ("darcy_K_m_s", "hydraulic_gradient", "claimed_darcy_velocity_m_s")):
        results.append(verify_darcy_velocity(hv))
    if all(k in hv for k in ("runoff_coefficient", "rainfall_intensity", "drainage_area", "claimed_runoff")):
        results.append(verify_rational_runoff(hv))
    if all(k in hv for k in ("elevation_m", "pressure_pa", "velocity_m_s",
                              "fluid_density_kg_m3", "claimed_total_head_m")):
        results.append(verify_bernoulli_head(hv))
    if not results:
        results.append(na("hydrology", "no HYD_VERIFY artifacts present"))
    return results
