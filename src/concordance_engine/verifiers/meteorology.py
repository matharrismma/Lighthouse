"""Meteorology verifier (physical-substance grid axis — atmosphere).

Dew point (Magnus), heat index (Rothfusz, US NWS), wind chill (NWS 2001),
saturation vapor pressure (Magnus). All public-domain formulas widely
documented by NWS / WMO.

Checks:
  * meteorology.dew_point                  — Magnus-Tetens approximation
  * meteorology.heat_index                 — Rothfusz regression (°F)
  * meteorology.wind_chill                 — NWS 2001 formula (°F, mph)
  * meteorology.saturation_vapor_pressure  — es(T) Magnus form (hPa)

MET_VERIFY shape (any subset):
    {
      "temperature_c": 25.0, "relative_humidity_pct": 60.0,
      "claimed_dew_point_c": 16.7,

      "temperature_f": 90.0, "relative_humidity_pct_for_hi": 70.0,
      "claimed_heat_index_f": 105.0,

      "temperature_f_for_wc": 20.0, "wind_speed_mph": 15.0,
      "claimed_wind_chill_f": 6.0,

      "temperature_c_for_es": 25.0,
      "claimed_saturation_vapor_pressure_hpa": 31.7,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_MAGNUS_A = 17.625
_MAGNUS_B = 243.04


def _saturation_vapor_pressure_hpa(T_c: float) -> float:
    """Magnus form: es(T) = 6.112 · exp((17.625·T)/(T + 243.04))."""
    return 6.112 * math.exp((_MAGNUS_A * T_c) / (T_c + _MAGNUS_B))


def verify_dew_point(spec: Dict[str, Any]) -> VerifierResult:
    name = "meteorology.dew_point"
    T = spec.get("temperature_c")
    RH = spec.get("relative_humidity_pct")
    claimed = spec.get("claimed_dew_point_c")
    if T is None or RH is None or claimed is None:
        return na(name)
    try:
        Tf, Rf, c = float(T), float(RH), float(claimed)
    except (TypeError, ValueError):
        return error(name, "T, RH, and claim must be numeric")
    if Rf <= 0 or Rf > 100:
        return error(name, f"RH must be in (0, 100], got {Rf}")
    gamma = (_MAGNUS_A * Tf) / (_MAGNUS_B + Tf) + math.log(Rf / 100.0)
    actual = (_MAGNUS_B * gamma) / (_MAGNUS_A - gamma)
    tol = float(spec.get("tolerance_c", 0.5))
    diff = abs(actual - c)
    data = {"temperature_c": Tf, "relative_humidity_pct": Rf,
            "actual_dew_point_c": actual, "claimed_dew_point_c": c,
            "diff_c": diff, "tolerance_c": tol,
            "formula": "Magnus-Tetens (a=17.625, b=243.04)"}
    if diff <= tol:
        return confirm(name,
                       f"T={Tf}°C, RH={Rf}% → dew point {actual:.2f}°C (matches claim)",
                       data)
    return mismatch(name,
                    f"dew point = {actual:.2f}°C, claimed {c} (diff {diff:.2f})",
                    data)


def verify_heat_index(spec: Dict[str, Any]) -> VerifierResult:
    """Rothfusz regression (US NWS), valid for T ≥ 80°F and RH ≥ 40%.
    HI = -42.379 + 2.04901523·T + 10.14333127·RH
         - 0.22475541·T·RH - 6.83783e-3·T² - 5.481717e-2·RH²
         + 1.22874e-3·T²·RH + 8.5282e-4·T·RH² - 1.99e-6·T²·RH²
    """
    name = "meteorology.heat_index"
    T = spec.get("temperature_f")
    RH = spec.get("relative_humidity_pct_for_hi")
    claimed = spec.get("claimed_heat_index_f")
    if T is None or RH is None or claimed is None:
        return na(name)
    try:
        Tf, Rf, c = float(T), float(RH), float(claimed)
    except (TypeError, ValueError):
        return error(name, "T, RH, and claim must be numeric")
    if Tf < 80 or Rf < 40:
        return error(name,
                     f"Rothfusz HI valid only for T ≥ 80°F and RH ≥ 40%; got T={Tf}, RH={Rf}")
    actual = (
        -42.379
        + 2.04901523 * Tf
        + 10.14333127 * Rf
        - 0.22475541 * Tf * Rf
        - 6.83783e-3 * Tf * Tf
        - 5.481717e-2 * Rf * Rf
        + 1.22874e-3 * Tf * Tf * Rf
        + 8.5282e-4 * Tf * Rf * Rf
        - 1.99e-6 * Tf * Tf * Rf * Rf
    )
    tol = float(spec.get("tolerance_f", 1.5))
    diff = abs(actual - c)
    data = {"temperature_f": Tf, "relative_humidity_pct": Rf,
            "actual_heat_index_f": actual, "claimed_heat_index_f": c,
            "diff_f": diff, "tolerance_f": tol,
            "formula": "Rothfusz regression (NWS)"}
    if diff <= tol:
        return confirm(name,
                       f"T={Tf}°F, RH={Rf}% → HI {actual:.2f}°F (matches claim)",
                       data)
    return mismatch(name,
                    f"HI = {actual:.2f}°F, claimed {c} (diff {diff:.2f})",
                    data)


def verify_wind_chill(spec: Dict[str, Any]) -> VerifierResult:
    """NWS 2001 wind-chill: WC = 35.74 + 0.6215·T - 35.75·V^0.16 + 0.4275·T·V^0.16
    Valid for T ≤ 50°F and V > 3 mph.
    """
    name = "meteorology.wind_chill"
    T = spec.get("temperature_f_for_wc")
    V = spec.get("wind_speed_mph")
    claimed = spec.get("claimed_wind_chill_f")
    if T is None or V is None or claimed is None:
        return na(name)
    try:
        Tf, Vf, c = float(T), float(V), float(claimed)
    except (TypeError, ValueError):
        return error(name, "T, V, and claim must be numeric")
    if Tf > 50 or Vf <= 3:
        return error(name,
                     f"NWS WC valid only for T ≤ 50°F and V > 3 mph; got T={Tf}, V={Vf}")
    v_pow = Vf ** 0.16
    actual = 35.74 + 0.6215 * Tf - 35.75 * v_pow + 0.4275 * Tf * v_pow
    tol = float(spec.get("tolerance_f", 1.0))
    diff = abs(actual - c)
    data = {"temperature_f": Tf, "wind_speed_mph": Vf,
            "actual_wind_chill_f": actual, "claimed_wind_chill_f": c,
            "diff_f": diff, "tolerance_f": tol,
            "formula": "NWS 2001 wind-chill"}
    if diff <= tol:
        return confirm(name,
                       f"T={Tf}°F, V={Vf} mph → WC {actual:.2f}°F (matches claim)",
                       data)
    return mismatch(name,
                    f"WC = {actual:.2f}°F, claimed {c} (diff {diff:.2f})",
                    data)


def verify_wind_chill_metric(spec: Dict[str, Any]) -> VerifierResult:
    """Environment Canada / NWS metric wind-chill formula.
    WC = 13.12 + 0.6215·T − 11.37·V^0.16 + 0.3965·T·V^0.16
    Valid for T < 10°C and V ≥ 5 km/h.
    Accepts claimed_wc_c (exact value) or claimed_below_c (threshold comparison).
    """
    name = "meteorology.wind_chill_metric"
    T = spec.get("temp_c")
    V = spec.get("wind_kmh")
    if T is None or V is None:
        return na(name)
    try:
        Tc, Vc = float(T), float(V)
    except (TypeError, ValueError):
        return error(name, "temp_c and wind_kmh must be numeric")
    if Tc >= 10 or Vc < 5:
        return error(name,
                     f"metric WC valid for T < 10°C and V ≥ 5 km/h; got T={Tc}, V={Vc}")
    v_pow = Vc ** 0.16
    wc = 13.12 + 0.6215 * Tc - 11.37 * v_pow + 0.3965 * Tc * v_pow
    data = {"temp_c": Tc, "wind_kmh": Vc, "wind_chill_c": round(wc, 2),
            "formula": "13.12 + 0.6215T − 11.37V^0.16 + 0.3965TV^0.16"}
    # Exact value check
    claimed_wc = spec.get("claimed_wc_c")
    if claimed_wc is not None:
        try:
            c = float(claimed_wc)
        except (TypeError, ValueError):
            return error(name, "claimed_wc_c must be numeric")
        tol = float(spec.get("tolerance_c", 0.5))
        diff = abs(wc - c)
        if diff <= tol:
            return confirm(name, f"WC = {wc:.2f}°C (matches claim {c})", data)
        return mismatch(name, f"WC = {wc:.2f}°C, claimed {c} (diff {diff:.2f})", data)
    # Threshold comparison
    threshold = spec.get("claimed_below_c")
    if threshold is not None:
        try:
            thresh = float(threshold)
        except (TypeError, ValueError):
            return error(name, "claimed_below_c must be numeric")
        is_below = wc < thresh
        claimed_is_below = bool(spec.get("is_below", True))
        if is_below == claimed_is_below:
            return confirm(name,
                           f"WC = {wc:.2f}°C {'<' if is_below else '>='} {thresh}°C "
                           f"(matches claim)", data)
        return mismatch(name,
                        f"WC = {wc:.2f}°C, claimed {'below' if claimed_is_below else 'at or above'} "
                        f"{thresh}°C", data)
    return na(name, "no claimed_wc_c or claimed_below_c provided")


def verify_saturation_vapor_pressure(spec: Dict[str, Any]) -> VerifierResult:
    name = "meteorology.saturation_vapor_pressure"
    T = spec.get("temperature_c_for_es")
    claimed = spec.get("claimed_saturation_vapor_pressure_hpa")
    if T is None or claimed is None:
        return na(name)
    try:
        Tf, c = float(T), float(claimed)
    except (TypeError, ValueError):
        return error(name, "T and claim must be numeric")
    actual = _saturation_vapor_pressure_hpa(Tf)
    rel_tol = float(spec.get("tolerance_relative", 0.02))  # 2%
    diff = abs(actual - c)
    threshold = max(0.05, rel_tol * actual)
    data = {"temperature_c": Tf, "actual_es_hpa": actual,
            "claimed_es_hpa": c, "diff_hpa": diff,
            "tolerance_relative": rel_tol,
            "formula": "es(T) = 6.112·exp((17.625·T)/(T + 243.04))"}
    if diff <= threshold:
        return confirm(name,
                       f"T={Tf}°C → es {actual:.3f} hPa (matches claim)",
                       data)
    return mismatch(name,
                    f"es = {actual:.3f} hPa, claimed {c} (diff {diff:.3f})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MET_VERIFY") or {}
    if all(k in mv for k in ("temperature_c", "relative_humidity_pct", "claimed_dew_point_c")):
        results.append(verify_dew_point(mv))
    if all(k in mv for k in ("temperature_f", "relative_humidity_pct_for_hi", "claimed_heat_index_f")):
        results.append(verify_heat_index(mv))
    if all(k in mv for k in ("temperature_f_for_wc", "wind_speed_mph", "claimed_wind_chill_f")):
        results.append(verify_wind_chill(mv))
    if all(k in mv for k in ("temperature_c_for_es", "claimed_saturation_vapor_pressure_hpa")):
        results.append(verify_saturation_vapor_pressure(mv))
    if "temp_c" in mv and "wind_kmh" in mv:
        results.append(verify_wind_chill_metric(mv))
    if not results:
        results.append(na("meteorology", "no MET_VERIFY artifacts present"))
    return results
