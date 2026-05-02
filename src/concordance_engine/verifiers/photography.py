"""Photography verifier (engineering grid axis — applied optics).

Exposure value, reciprocity (equivalent exposures), angle of view, and
hyperfocal distance. Public-domain photographic conventions widely
documented in optical-engineering texts.

Checks:
  * photography.exposure_value         — EV = log2(N²/t) at ISO 100
  * photography.reciprocity_equivalent — two (N,t) settings yield same EV
  * photography.angle_of_view          — AOV = 2·atan(sensor_dim/(2f))
  * photography.hyperfocal_distance    — H = f²/(N·c) + f

PHOTO_VERIFY shape (any subset):
    {
      "f_number": 8.0, "shutter_seconds": 1.0/250.0,
      "claimed_exposure_value": 13.97,  # log2(64·250) ≈ 13.97

      "settings_a": [8.0, 1.0/250.0],
      "settings_b": [11.0, 1.0/125.0],
      "claimed_equivalent": true,

      "focal_length_mm": 50.0, "sensor_dimension_mm": 36.0,
      "claimed_angle_of_view_deg": 39.6,

      "focal_length_mm_for_h": 50.0, "f_number_for_h": 8.0,
      "circle_of_confusion_mm": 0.030,
      "claimed_hyperfocal_distance_m": 10.46,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _ev(N: float, t: float) -> float:
    """EV (ISO 100) = log2(N² / t)."""
    return math.log2((N * N) / t)


def verify_exposure_value(spec: Dict[str, Any]) -> VerifierResult:
    name = "photography.exposure_value"
    N = spec.get("f_number")
    t = spec.get("shutter_seconds")
    claimed = spec.get("claimed_exposure_value")
    if N is None or t is None or claimed is None:
        return na(name)
    try:
        Nf, tf, c = float(N), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, "f-number, shutter, and claim must be numeric")
    if Nf <= 0 or tf <= 0:
        return error(name, "f-number and shutter must be positive")
    actual = _ev(Nf, tf)
    tol = float(spec.get("tolerance_ev", 0.1))
    diff = abs(actual - c)
    data = {"f_number": Nf, "shutter_seconds": tf,
            "actual_ev": actual, "claimed_ev": c, "diff": diff,
            "tolerance_ev": tol,
            "formula": "EV = log₂(N²/t)  [ISO 100]"}
    if diff <= tol:
        return confirm(name, f"EV = {actual:.3f} (matches claim)", data)
    return mismatch(name, f"EV = {actual:.3f}, claimed {c} (diff {diff:.3f})", data)


def verify_reciprocity_equivalent(spec: Dict[str, Any]) -> VerifierResult:
    """Two (N, t) settings are equivalent iff their EVs match (within tol)."""
    name = "photography.reciprocity_equivalent"
    a = spec.get("settings_a")
    b = spec.get("settings_b")
    claimed = spec.get("claimed_equivalent")
    if a is None or b is None or claimed is None:
        return na(name)
    if not (isinstance(a, (list, tuple)) and len(a) == 2 and
            isinstance(b, (list, tuple)) and len(b) == 2):
        return error(name, "settings_a and settings_b must each be [f_number, shutter_s]")
    try:
        Na, ta = float(a[0]), float(a[1])
        Nb, tb = float(b[0]), float(b[1])
    except (TypeError, ValueError):
        return error(name, "settings must be numeric")
    if Na <= 0 or ta <= 0 or Nb <= 0 or tb <= 0:
        return error(name, "f-numbers and shutters must be positive")
    eva, evb = _ev(Na, ta), _ev(Nb, tb)
    tol = float(spec.get("tolerance_ev", 0.1))
    actual = abs(eva - evb) <= tol
    data = {"settings_a": [Na, ta], "ev_a": eva,
            "settings_b": [Nb, tb], "ev_b": evb,
            "ev_diff": abs(eva - evb), "tolerance_ev": tol,
            "actual_equivalent": actual, "claimed_equivalent": bool(claimed),
            "rule": "equivalent iff EV_a = EV_b within tolerance"}
    if actual == bool(claimed):
        return confirm(name,
                       f"EV_a={eva:.3f} EV_b={evb:.3f} equivalent={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"EV_a={eva:.3f} EV_b={evb:.3f} equivalent={actual}, claimed {bool(claimed)}",
                    data)


def verify_angle_of_view(spec: Dict[str, Any]) -> VerifierResult:
    """AOV = 2·atan(d / (2f)) — d is sensor dimension, f is focal length."""
    name = "photography.angle_of_view"
    f = spec.get("focal_length_mm")
    d = spec.get("sensor_dimension_mm")
    claimed = spec.get("claimed_angle_of_view_deg")
    if f is None or d is None or claimed is None:
        return na(name)
    try:
        ff, df, c = float(f), float(d), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if ff <= 0 or df <= 0:
        return error(name, "focal length and sensor dimension must be positive")
    actual = 2.0 * math.degrees(math.atan(df / (2.0 * ff)))
    tol = float(spec.get("tolerance_deg", 0.5))
    diff = abs(actual - c)
    data = {"focal_length_mm": ff, "sensor_dim_mm": df,
            "actual_aov_deg": actual, "claimed_aov_deg": c, "diff_deg": diff,
            "tolerance_deg": tol,
            "formula": "AOV = 2·atan(d / 2f)"}
    if diff <= tol:
        return confirm(name, f"AOV = {actual:.3f}° (matches claim)", data)
    return mismatch(name, f"AOV = {actual:.3f}°, claimed {c} (diff {diff:.3f})", data)


def verify_hyperfocal_distance(spec: Dict[str, Any]) -> VerifierResult:
    """H = f² / (N·c) + f (with f and c in same length units; result in same)."""
    name = "photography.hyperfocal_distance"
    f = spec.get("focal_length_mm_for_h")
    N = spec.get("f_number_for_h")
    c_coc = spec.get("circle_of_confusion_mm")
    claimed = spec.get("claimed_hyperfocal_distance_m")
    if any(v is None for v in (f, N, c_coc, claimed)):
        return na(name)
    try:
        ff, Nf, cf, cl = float(f), float(N), float(c_coc), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if ff <= 0 or Nf <= 0 or cf <= 0:
        return error(name, "focal length, f-number, and CoC must be positive")
    H_mm = (ff * ff) / (Nf * cf) + ff
    actual_m = H_mm / 1000.0
    rel_tol = float(spec.get("tolerance_relative", 0.02))
    diff = abs(actual_m - cl)
    threshold = max(0.05, rel_tol * actual_m)
    data = {"focal_length_mm": ff, "f_number": Nf, "coc_mm": cf,
            "actual_H_m": actual_m, "claimed_H_m": cl, "diff_m": diff,
            "tolerance_relative": rel_tol,
            "formula": "H = f² / (N·c) + f"}
    if diff <= threshold:
        return confirm(name, f"H = {actual_m:.3f} m (matches claim)", data)
    return mismatch(name, f"H = {actual_m:.3f} m, claimed {cl} (diff {diff:.3f})", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    pv = packet.get("PHOTO_VERIFY") or {}
    if all(k in pv for k in ("f_number", "shutter_seconds", "claimed_exposure_value")):
        results.append(verify_exposure_value(pv))
    if all(k in pv for k in ("settings_a", "settings_b", "claimed_equivalent")):
        results.append(verify_reciprocity_equivalent(pv))
    if all(k in pv for k in ("focal_length_mm", "sensor_dimension_mm", "claimed_angle_of_view_deg")):
        results.append(verify_angle_of_view(pv))
    if all(k in pv for k in ("focal_length_mm_for_h", "f_number_for_h",
                              "circle_of_confusion_mm", "claimed_hyperfocal_distance_m")):
        results.append(verify_hyperfocal_distance(pv))
    if not results:
        results.append(na("photography", "no PHOTO_VERIFY artifacts present"))
    return results
