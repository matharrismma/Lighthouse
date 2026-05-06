"""Oceanography verifier (physical-substance + time-sequence grid axes).

Pressure at depth, salinity classification, wave speed, tidal range,
and pelagic zone classification.
Public-domain (NOAA, standard physical oceanography textbooks).

Checks:
  * oceanography.pressure_at_depth              — P = P_atm + ρ·g·d
  * oceanography.salinity_classification        — fresh/brackish/marine/hypersaline
  * oceanography.deep_water_wave_speed          — c = √(g·λ / 2π)
  * oceanography.tidal_range_classification     — micro/meso/macrotidal
  * oceanography.thermocline_depth_classification — pelagic zone by depth

OCEAN_VERIFY shape (any subset):
    {
      "depth_m": 100,
      "claimed_pressure_Pa": 1114825,
      # or: "claimed_pressure_atm": 11.006,

      "salinity_ppt": 35,
      "claimed_classification": "marine",

      "wavelength_m": 100,
      "claimed_wave_speed_m_per_s": 12.48,

      "tidal_range_m": 3.0,
      "claimed_tidal_type": "mesotidal",

      "depth_m": 500,
      "claimed_zone": "mesopelagic",
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

# Physical constants
_RHO_SEAWATER = 1025.0   # kg/m³ standard seawater density
_G = 9.81                 # m/s²
_P_ATM = 101325.0         # Pa (1 atm)


def verify_pressure_at_depth(spec: Dict[str, Any]) -> VerifierResult:
    """P = P_atm + ρ_seawater · g · d.

    Accepts either claimed_pressure_Pa or claimed_pressure_atm.
    """
    name = "oceanography.pressure_at_depth"
    depth = spec.get("depth_m")
    claimed_pa = spec.get("claimed_pressure_Pa")
    claimed_atm = spec.get("claimed_pressure_atm")
    if depth is None or (claimed_pa is None and claimed_atm is None):
        return na(name)
    try:
        df = float(depth)
    except (TypeError, ValueError):
        return error(name, "depth_m must be numeric")
    if df < 0:
        return error(name, f"depth_m must be non-negative, got {df}")
    actual_pa = _P_ATM + _RHO_SEAWATER * _G * df
    actual_atm = actual_pa / _P_ATM
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))

    if claimed_pa is not None:
        try:
            c = float(claimed_pa)
        except (TypeError, ValueError):
            return error(name, "claimed_pressure_Pa must be numeric")
        actual = actual_pa
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "P = P_atm + ρ·g·d",
                "depth_m": df, "rho_seawater_kg_m3": _RHO_SEAWATER, "g_m_s2": _G,
                "P_atm_Pa": _P_ATM, "actual_pressure_Pa": actual_pa,
                "actual_pressure_atm": actual_atm,
                "claimed_pressure_Pa": c, "diff": diff}
        if diff <= threshold:
            return confirm(name,
                           f"P = {_P_ATM} + {_RHO_SEAWATER}·{_G}·{df} = {actual_pa:.6g} Pa "
                           f"(matches claim {c})",
                           data)
        return mismatch(name,
                        f"actual P {actual_pa:.6g} Pa, claimed {c} Pa (diff {diff:.6g})",
                        data)

    # claimed_pressure_atm
    try:
        c = float(claimed_atm)
    except (TypeError, ValueError):
        return error(name, "claimed_pressure_atm must be numeric")
    actual = actual_atm
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "P = (P_atm + ρ·g·d) / P_atm  [in atm]",
            "depth_m": df, "rho_seawater_kg_m3": _RHO_SEAWATER, "g_m_s2": _G,
            "P_atm_Pa": _P_ATM, "actual_pressure_Pa": actual_pa,
            "actual_pressure_atm": actual_atm,
            "claimed_pressure_atm": c, "diff": diff}
    if diff <= threshold:
        return confirm(name,
                       f"P = {actual_pa:.6g} Pa = {actual_atm:.6g} atm (matches claim {c} atm)",
                       data)
    return mismatch(name,
                    f"actual P {actual_atm:.6g} atm, claimed {c} atm (diff {diff:.6g})",
                    data)


def verify_salinity_classification(spec: Dict[str, Any]) -> VerifierResult:
    """Classify salinity: fresh <0.5 ppt, brackish 0.5–30, marine 30–40, hypersaline >40."""
    name = "oceanography.salinity_classification"
    sal = spec.get("salinity_ppt")
    claimed = spec.get("claimed_classification")
    if sal is None or claimed is None:
        return na(name)
    try:
        sf = float(sal)
    except (TypeError, ValueError):
        return error(name, "salinity_ppt must be numeric")
    if sf < 0:
        return error(name, f"salinity_ppt must be non-negative, got {sf}")
    valid = {"fresh", "brackish", "marine", "hypersaline"}
    if str(claimed).lower() not in valid:
        return error(name, f"claimed_classification must be one of {sorted(valid)}, got '{claimed}'")
    if sf < 0.5:
        actual = "fresh"
    elif sf <= 30:
        actual = "brackish"
    elif sf <= 40:
        actual = "marine"
    else:
        actual = "hypersaline"
    data = {"salinity_ppt": sf, "actual_classification": actual,
            "claimed_classification": str(claimed).lower(),
            "thresholds": "fresh:<0.5, brackish:0.5-30, marine:30-40, hypersaline:>40 (ppt)"}
    if actual == str(claimed).lower():
        return confirm(name,
                       f"{sf} ppt → '{actual}' (matches claim)",
                       data)
    return mismatch(name,
                    f"{sf} ppt → '{actual}', claimed '{str(claimed).lower()}'",
                    data)


def verify_deep_water_wave_speed(spec: Dict[str, Any]) -> VerifierResult:
    """Phase velocity c = √(g·λ / 2π) for deep water (depth > λ/2)."""
    name = "oceanography.deep_water_wave_speed"
    lam = spec.get("wavelength_m")
    claimed = spec.get("claimed_wave_speed_m_per_s")
    if lam is None or claimed is None:
        return na(name)
    try:
        lamf, c = float(lam), float(claimed)
    except (TypeError, ValueError):
        return error(name, "wavelength_m and claimed_wave_speed_m_per_s must be numeric")
    if lamf <= 0:
        return error(name, f"wavelength_m must be positive, got {lamf}")
    actual = math.sqrt(_G * lamf / (2 * math.pi))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "c = √(g·λ / 2π)",
            "wavelength_m": lamf, "g_m_s2": _G,
            "actual_wave_speed_m_per_s": actual,
            "claimed_wave_speed_m_per_s": c, "diff": diff,
            "note": "valid for deep water only (depth > λ/2)"}
    if diff <= threshold:
        return confirm(name,
                       f"c = √({_G}·{lamf}/2π) = {actual:.6g} m/s (matches claim {c})",
                       data)
    return mismatch(name,
                    f"actual c {actual:.6g} m/s, claimed {c} m/s (diff {diff:.6g})",
                    data)


def verify_tidal_range_classification(spec: Dict[str, Any]) -> VerifierResult:
    """Microtidal <2 m, mesotidal 2–4 m, macrotidal >4 m."""
    name = "oceanography.tidal_range_classification"
    tr = spec.get("tidal_range_m")
    claimed = spec.get("claimed_tidal_type")
    if tr is None or claimed is None:
        return na(name)
    try:
        trf = float(tr)
    except (TypeError, ValueError):
        return error(name, "tidal_range_m must be numeric")
    if trf < 0:
        return error(name, f"tidal_range_m must be non-negative, got {trf}")
    valid = {"microtidal", "mesotidal", "macrotidal"}
    if str(claimed).lower() not in valid:
        return error(name, f"claimed_tidal_type must be one of {sorted(valid)}, got '{claimed}'")
    if trf < 2:
        actual = "microtidal"
    elif trf <= 4:
        actual = "mesotidal"
    else:
        actual = "macrotidal"
    data = {"tidal_range_m": trf, "actual_tidal_type": actual,
            "claimed_tidal_type": str(claimed).lower(),
            "thresholds": "microtidal:<2 m, mesotidal:2-4 m, macrotidal:>4 m"}
    if actual == str(claimed).lower():
        return confirm(name,
                       f"{trf} m tidal range → '{actual}' (matches claim)",
                       data)
    return mismatch(name,
                    f"{trf} m → '{actual}', claimed '{str(claimed).lower()}'",
                    data)


def verify_thermocline_depth_classification(spec: Dict[str, Any]) -> VerifierResult:
    """Pelagic zone classification by depth.

    Epipelagic: 0–200 m, Mesopelagic: 200–1000 m,
    Bathypelagic: 1000–4000 m, Abyssopelagic: 4000–6000 m, Hadopelagic: >6000 m.
    """
    name = "oceanography.thermocline_depth_classification"
    depth = spec.get("depth_m")
    claimed = spec.get("claimed_zone")
    if depth is None or claimed is None:
        return na(name)
    try:
        df = float(depth)
    except (TypeError, ValueError):
        return error(name, "depth_m must be numeric")
    if df < 0:
        return error(name, f"depth_m must be non-negative, got {df}")
    valid = {"epipelagic", "mesopelagic", "bathypelagic", "abyssopelagic", "hadopelagic"}
    if str(claimed).lower() not in valid:
        return error(name,
                     f"claimed_zone must be one of {sorted(valid)}, got '{claimed}'")
    if df <= 200:
        actual = "epipelagic"
    elif df <= 1000:
        actual = "mesopelagic"
    elif df <= 4000:
        actual = "bathypelagic"
    elif df <= 6000:
        actual = "abyssopelagic"
    else:
        actual = "hadopelagic"
    data = {"depth_m": df, "actual_zone": actual,
            "claimed_zone": str(claimed).lower(),
            "thresholds": ("epipelagic:0-200 m, mesopelagic:200-1000 m, "
                           "bathypelagic:1000-4000 m, abyssopelagic:4000-6000 m, "
                           "hadopelagic:>6000 m")}
    if actual == str(claimed).lower():
        return confirm(name,
                       f"{df} m depth → '{actual}' (matches claim)",
                       data)
    return mismatch(name,
                    f"{df} m → '{actual}', claimed '{str(claimed).lower()}'",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ov = packet.get("OCEAN_VERIFY") or {}

    if ov.get("depth_m") is not None and (
            ov.get("claimed_pressure_Pa") is not None
            or ov.get("claimed_pressure_atm") is not None):
        results.append(verify_pressure_at_depth(ov))

    if all(ov.get(k) is not None for k in ("salinity_ppt", "claimed_classification")):
        results.append(verify_salinity_classification(ov))

    if all(ov.get(k) is not None for k in ("wavelength_m", "claimed_wave_speed_m_per_s")):
        results.append(verify_deep_water_wave_speed(ov))

    if all(ov.get(k) is not None for k in ("tidal_range_m", "claimed_tidal_type")):
        results.append(verify_tidal_range_classification(ov))

    # thermocline: depth_m overlaps with pressure check; distinguish by claimed_zone
    if all(ov.get(k) is not None for k in ("depth_m", "claimed_zone")):
        results.append(verify_thermocline_depth_classification(ov))

    if not results:
        results.append(na("oceanography", "no OCEAN_VERIFY artifacts present"))
    return results
