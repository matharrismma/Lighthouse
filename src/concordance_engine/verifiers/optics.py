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


# Exact SI-defined constants (2019 redefinition).
_H = 6.62607015e-34   # Planck constant, J·s
_C = 299792458.0      # speed of light, m/s


def verify_double_slit(spec: Dict[str, Any]) -> VerifierResult:
    """Young's double slit: fringe spacing Δy = λ·L / d (the WAVE signature of light)."""
    name = "optics.double_slit"
    lam = spec.get("wavelength_m"); d = spec.get("slit_separation_m")
    L = spec.get("screen_distance_m"); claimed = spec.get("claimed_fringe_spacing_m")
    if lam is None or d is None or L is None or claimed is None:
        return na(name)
    try:
        lf, df, Lf, c = float(lam), float(d), float(L), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if lf <= 0 or df <= 0 or Lf <= 0:
        return error(name, "wavelength, slit separation, and screen distance must be positive")
    actual = lf * Lf / df
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"wavelength_m": lf, "slit_separation_m": df, "screen_distance_m": Lf,
            "actual_fringe_spacing_m": actual, "claimed_fringe_spacing_m": c, "formula": "Δy = λ·L/d"}
    if abs(actual - c) <= max(1e-12, rel_tol * abs(actual)):
        return confirm(name, f"Δy = λL/d = {actual:.3e} m (matches claim)", data)
    return mismatch(name, f"Δy = {actual:.3e} m, claimed {c:.3e}", data)


def verify_photon_energy(spec: Dict[str, Any]) -> VerifierResult:
    """Photon energy E = h·c/λ = h·f (the PARTICLE quantum of light)."""
    name = "optics.photon_energy"
    lam = spec.get("wavelength_m"); freq = spec.get("frequency_hz")
    claimed = spec.get("claimed_photon_energy_j")
    if claimed is None or (lam is None and freq is None):
        return na(name)
    try:
        c = float(claimed)
        if lam is not None:
            lf = float(lam)
            if lf <= 0:
                return error(name, "wavelength must be positive")
            actual, basis = _H * _C / lf, f"hc/λ (λ={lf:.3g} m)"
        else:
            ff = float(freq)
            if ff <= 0:
                return error(name, "frequency must be positive")
            actual, basis = _H * ff, f"hf (f={ff:.3g} Hz)"
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"actual_photon_energy_j": actual, "claimed_photon_energy_j": c, "formula": "E = hc/λ = hf"}
    if abs(actual - c) <= max(1e-30, rel_tol * abs(actual)):
        return confirm(name, f"E = {basis} = {actual:.3e} J (matches claim)", data)
    return mismatch(name, f"E = {actual:.3e} J, claimed {c:.3e}", data)


def verify_de_broglie(spec: Dict[str, Any]) -> VerifierResult:
    """Matter wave: λ = h / p — wave-particle duality (a particle has a wavelength)."""
    name = "optics.de_broglie"
    p = spec.get("momentum_kg_m_s"); mass = spec.get("mass_kg"); vel = spec.get("velocity_m_s")
    claimed = spec.get("claimed_de_broglie_m")
    if claimed is None:
        return na(name)
    try:
        c = float(claimed)
        if p is not None:
            pf = float(p)
        elif mass is not None and vel is not None:
            pf = float(mass) * float(vel)
        else:
            return na(name)
        if pf <= 0:
            return error(name, "momentum must be positive")
        actual = _H / pf
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"momentum_kg_m_s": pf, "actual_de_broglie_m": actual,
            "claimed_de_broglie_m": c, "formula": "λ = h/p"}
    if abs(actual - c) <= max(1e-30, rel_tol * abs(actual)):
        return confirm(name, f"λ = h/p = {actual:.3e} m (matches claim)", data)
    return mismatch(name, f"λ = {actual:.3e} m, claimed {c:.3e}", data)


def verify_critical_angle(spec: Dict[str, Any]) -> VerifierResult:
    """Total internal reflection: theta_c = arcsin(n_clad / n_core). Light at an
    angle above theta_c is fully contained — how a fiber CARRIES light."""
    name = "optics.critical_angle"
    nc = spec.get("n_core"); ncl = spec.get("n_cladding")
    claimed = spec.get("claimed_critical_angle_deg")
    if nc is None or ncl is None or claimed is None:
        return na(name)
    try:
        ncf, nclf, c = float(nc), float(ncl), float(claimed)
    except (TypeError, ValueError):
        return error(name, "indices and angle must be numeric")
    if ncf <= 0 or nclf <= 0:
        return error(name, "refractive indices must be positive")
    if nclf >= ncf:
        return mismatch(name, f"no TIR: cladding index {nclf} must be < core index {ncf}")
    actual = math.degrees(math.asin(nclf / ncf))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"n_core": ncf, "n_cladding": nclf, "actual_critical_angle_deg": actual,
            "claimed_critical_angle_deg": c, "formula": "theta_c = arcsin(n_clad/n_core)"}
    if abs(actual - c) <= max(1e-6, rel_tol * abs(actual)):
        return confirm(name, f"theta_c = arcsin({nclf}/{ncf}) = {actual:.4g} deg (matches claim)", data)
    return mismatch(name, f"theta_c = {actual:.4g} deg, claimed {c:.4g}", data)


def verify_numerical_aperture(spec: Dict[str, Any]) -> VerifierResult:
    """Light-gathering: NA = sqrt(n_core^2 - n_clad^2)."""
    name = "optics.numerical_aperture"
    nc = spec.get("n_core"); ncl = spec.get("n_cladding")
    claimed = spec.get("claimed_numerical_aperture")
    if nc is None or ncl is None or claimed is None:
        return na(name)
    try:
        ncf, nclf, c = float(nc), float(ncl), float(claimed)
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    if ncf <= nclf:
        return error(name, "core index must exceed cladding index")
    actual = math.sqrt(ncf * ncf - nclf * nclf)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"actual_numerical_aperture": actual, "claimed_numerical_aperture": c,
            "formula": "NA = sqrt(n_core^2 - n_clad^2)"}
    if abs(actual - c) <= max(1e-6, rel_tol * abs(actual)):
        return confirm(name, f"NA = sqrt({ncf}^2-{nclf}^2) = {actual:.4g} (matches claim)", data)
    return mismatch(name, f"NA = {actual:.4g}, claimed {c:.4g}", data)


def verify_fiber_attenuation(spec: Dict[str, Any]) -> VerifierResult:
    """Signal loss: loss_dB = alpha(dB/km) x length(km); or 10*log10(P_in/P_out).
    The 'light touch travels far' — a tiny loss per km over a long run."""
    name = "optics.fiber_attenuation"
    a = spec.get("attenuation_db_per_km"); L = spec.get("length_km")
    pin = spec.get("power_in_mw"); pout = spec.get("power_out_mw")
    claimed = spec.get("claimed_loss_db")
    if claimed is None:
        return na(name)
    try:
        c = float(claimed)
        if a is not None and L is not None:
            actual = float(a) * float(L); basis = f"{a} dB/km x {L} km"
        elif pin is not None and pout is not None:
            pif, pof = float(pin), float(pout)
            if pif <= 0 or pof <= 0:
                return error(name, "powers must be positive")
            actual = 10.0 * math.log10(pif / pof); basis = f"10*log10({pin}/{pout})"
        else:
            return na(name)
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"actual_loss_db": actual, "claimed_loss_db": c, "formula": "loss = alpha*L = 10log10(Pin/Pout)"}
    if abs(actual - c) <= max(1e-6, rel_tol * abs(actual)):
        return confirm(name, f"loss = {basis} = {actual:.4g} dB (matches claim)", data)
    return mismatch(name, f"loss = {actual:.4g} dB, claimed {c:.4g}", data)


def verify_wdm_capacity(spec: Dict[str, Any]) -> VerifierResult:
    """Wavelength-division multiplexing: total = num_channels x bitrate_per_channel.
    MANY independent signals (colors) through ONE fiber at once."""
    name = "optics.wdm_capacity"
    n = spec.get("num_channels"); rate = spec.get("bitrate_per_channel_gbps")
    claimed = spec.get("claimed_total_gbps")
    if n is None or rate is None or claimed is None:
        return na(name)
    try:
        nf, rf, c = float(n), float(rate), float(claimed)
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    if nf <= 0 or rf <= 0:
        return error(name, "channels and bitrate must be positive")
    actual = nf * rf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    data = {"actual_total_gbps": actual, "claimed_total_gbps": c,
            "formula": "total = num_channels x bitrate_per_channel"}
    if abs(actual - c) <= max(1e-6, rel_tol * abs(actual)):
        return confirm(name, f"{int(nf)} channels x {rf} Gbps = {actual:.6g} Gbps through one fiber (matches claim)", data)
    return mismatch(name, f"total = {actual:.6g} Gbps, claimed {c:.6g}", data)


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
    if all(ov.get(k) is not None for k in ("wavelength_m", "slit_separation_m",
                                           "screen_distance_m", "claimed_fringe_spacing_m")):
        results.append(verify_double_slit(ov))
    if ov.get("claimed_photon_energy_j") is not None and \
       (ov.get("wavelength_m") is not None or ov.get("frequency_hz") is not None):
        results.append(verify_photon_energy(ov))
    if ov.get("claimed_de_broglie_m") is not None:
        results.append(verify_de_broglie(ov))
    if all(ov.get(k) is not None for k in ("n_core", "n_cladding", "claimed_critical_angle_deg")):
        results.append(verify_critical_angle(ov))
    if all(ov.get(k) is not None for k in ("n_core", "n_cladding", "claimed_numerical_aperture")):
        results.append(verify_numerical_aperture(ov))
    if ov.get("claimed_loss_db") is not None and (
        (ov.get("attenuation_db_per_km") is not None and ov.get("length_km") is not None) or
        (ov.get("power_in_mw") is not None and ov.get("power_out_mw") is not None)):
        results.append(verify_fiber_attenuation(ov))
    if all(ov.get(k) is not None for k in ("num_channels", "bitrate_per_channel_gbps", "claimed_total_gbps")):
        results.append(verify_wdm_capacity(ov))

    if not results:
        results.append(na("optics", "no OPT_VERIFY artifacts present"))
    return results
