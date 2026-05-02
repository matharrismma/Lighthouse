"""Acoustics verifier (engineering / physical-substance grid axis).

Wave relations, decibel ratios, Doppler shift, harmonic series. All
formulas public-domain.

Checks:
  * acoustics.wave_relation       — c = f·λ
  * acoustics.decibel_ratio       — dB = 10·log10(I/I_ref) (intensity) or 20·log10(P/P_ref) (pressure)
  * acoustics.doppler_shift       — f_obs = f_src · (c + v_obs) / (c + v_src)
  * acoustics.harmonic_frequency  — f_n = n · f_fundamental

ACOUS_VERIFY shape (any subset):
    {
      "speed_of_wave": 343.0, "frequency_hz": 440, "wavelength_m": 0.7795,
      "value": 1.0, "reference": 1e-12, "claimed_db": 120,
      "db_kind": "intensity",   # 'intensity' (×10) or 'pressure' (×20)
      "f_source_hz": 440, "v_observer_mps": 10, "v_source_mps": 0,
        "speed_medium_mps": 343, "claimed_f_observed_hz": 452.83,
      "fundamental_hz": 110, "harmonic_n": 4, "claimed_harmonic_hz": 440,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _close(actual, claimed, rel_tol=1e-3, abs_tol=1e-6):
    return abs(actual - claimed) <= max(abs_tol, rel_tol * abs(actual))


def verify_wave_relation(spec: Dict[str, Any]) -> VerifierResult:
    """c = f · λ. All three supplied; verify the relation holds."""
    name = "acoustics.wave_relation"
    c = spec.get("speed_of_wave")
    f = spec.get("frequency_hz")
    lam = spec.get("wavelength_m")
    if c is None or f is None or lam is None:
        return na(name)
    try:
        cf, ff, lf = float(c), float(f), float(lam)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if cf <= 0 or ff <= 0 or lf <= 0:
        return error(name, f"speed/frequency/wavelength must be positive (got {cf}, {ff}, {lf})")
    actual = ff * lf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    diff = abs(actual - cf)
    data = {"speed": cf, "frequency": ff, "wavelength": lf,
            "f_times_lambda": actual, "diff": diff,
            "formula": "c = f · λ"}
    if _close(actual, cf, rel_tol=rel_tol):
        return confirm(name, f"f·λ = {ff}·{lf} = {actual} (matches c={cf})", data)
    return mismatch(name, f"f·λ = {actual}, c = {cf} (diff {diff})", data)


def verify_decibel_ratio(spec: Dict[str, Any]) -> VerifierResult:
    """Intensity dB: dB = 10·log10(I/I_ref). Pressure dB: dB = 20·log10(P/P_ref)."""
    name = "acoustics.decibel_ratio"
    val = spec.get("value")
    ref = spec.get("reference")
    claimed = spec.get("claimed_db")
    kind = (spec.get("db_kind") or "intensity").lower()
    if val is None or ref is None or claimed is None:
        return na(name)
    try:
        v = float(val)
        rf = float(ref)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "value, reference, claimed_db must be numeric")
    if v <= 0 or rf <= 0:
        return error(name, "value and reference must be positive for log")
    if kind not in ("intensity", "pressure", "power"):
        return error(name, f"db_kind must be 'intensity', 'pressure', or 'power'; got {kind!r}")
    multiplier = 20.0 if kind == "pressure" else 10.0
    actual = multiplier * math.log10(v / rf)
    tol = float(spec.get("tolerance_db", 0.1))
    diff = abs(actual - c)
    data = {"value": v, "reference": rf, "kind": kind,
            "actual_db": actual, "claimed_db": c, "diff_db": diff,
            "formula": f"dB = {multiplier:.0f}·log10(value/reference)"}
    if diff <= tol:
        return confirm(name,
                       f"{multiplier:.0f}·log10({v}/{rf}) = {actual:.2f} dB (matches claim {c}, diff {diff:.2f})",
                       data)
    return mismatch(name,
                    f"actual {actual:.2f} dB, claimed {c} dB (diff {diff:.2f} > tol {tol})",
                    data)


def verify_doppler_shift(spec: Dict[str, Any]) -> VerifierResult:
    """f_obs = f_src · (c + v_obs) / (c + v_src). Sign convention:
    positive velocities are toward the other party (closing).
    """
    name = "acoustics.doppler_shift"
    f_src = spec.get("f_source_hz")
    v_obs = spec.get("v_observer_mps")
    v_src = spec.get("v_source_mps")
    c_med = spec.get("speed_medium_mps")
    claimed = spec.get("claimed_f_observed_hz")
    if (f_src is None or v_obs is None or v_src is None
            or c_med is None or claimed is None):
        return na(name)
    try:
        fs, vo, vs, c, fo_c = float(f_src), float(v_obs), float(v_src), float(c_med), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if fs <= 0 or c <= 0:
        return error(name, "source frequency and medium speed must be positive")
    denom = c + vs
    if denom == 0:
        return error(name, "source moving at -c is unphysical (denominator zero)")
    actual = fs * (c + vo) / denom
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    diff = abs(actual - fo_c)
    data = {"f_source": fs, "v_observer": vo, "v_source": vs,
            "speed_medium": c, "actual_f_observed": actual,
            "claimed_f_observed": fo_c, "diff_hz": diff,
            "formula": "f_obs = f_src · (c + v_obs) / (c + v_src)"}
    if _close(actual, fo_c, rel_tol=rel_tol):
        return confirm(name,
                       f"f_obs = {fs}·({c}+{vo})/({c}+{vs}) = {actual:.3f} Hz (matches claim {fo_c})",
                       data)
    return mismatch(name,
                    f"f_obs = {actual:.3f} Hz, claimed {fo_c} (diff {diff:.3f})",
                    data)


def verify_harmonic_frequency(spec: Dict[str, Any]) -> VerifierResult:
    """f_n = n · f_fundamental for integer n >= 1."""
    name = "acoustics.harmonic_frequency"
    f1 = spec.get("fundamental_hz")
    n = spec.get("harmonic_n")
    claimed = spec.get("claimed_harmonic_hz")
    if f1 is None or n is None or claimed is None:
        return na(name)
    try:
        f1f = float(f1)
        nf = int(n)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "fundamental_hz and claimed_harmonic_hz numeric; harmonic_n integer")
    if f1f <= 0:
        return error(name, "fundamental_hz must be positive")
    if nf < 1:
        return error(name, "harmonic_n must be >= 1")
    actual = nf * f1f
    diff = abs(actual - c)
    rel_tol = float(spec.get("tolerance_relative", 1e-6))
    data = {"fundamental": f1f, "n": nf, "actual_harmonic": actual,
            "claimed_harmonic": c, "diff": diff,
            "formula": "f_n = n · f_1"}
    if _close(actual, c, rel_tol=rel_tol):
        return confirm(name,
                       f"f_{nf} = {nf}·{f1f} = {actual} Hz (matches claim {c})",
                       data)
    return mismatch(name,
                    f"f_{nf} = {actual} Hz, claimed {c} (diff {diff})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    av = packet.get("ACOUS_VERIFY") or {}

    if all(av.get(k) is not None for k in ("speed_of_wave", "frequency_hz", "wavelength_m")):
        results.append(verify_wave_relation(av))
    if all(av.get(k) is not None for k in ("value", "reference", "claimed_db")):
        results.append(verify_decibel_ratio(av))
    if all(av.get(k) is not None for k in ("f_source_hz", "v_observer_mps",
                                            "v_source_mps", "speed_medium_mps",
                                            "claimed_f_observed_hz")):
        results.append(verify_doppler_shift(av))
    if all(av.get(k) is not None for k in ("fundamental_hz", "harmonic_n", "claimed_harmonic_hz")):
        results.append(verify_harmonic_frequency(av))

    if not results:
        results.append(na("acoustics", "no ACOUS_VERIFY artifacts present"))
    return results
