"""Thermodynamics verifier (conservation/balance + physical-substance grid axes).

Carnot efficiency, ideal gas law, specific heat, entropy change.
Public-domain (standard thermodynamics textbook physics, NIST constants).

Checks:
  * thermodynamics.carnot_efficiency  — η = 1 − T_cold / T_hot
  * thermodynamics.ideal_gas_law      — PV = nRT  (R = 8.314 J/mol·K)
  * thermodynamics.specific_heat      — Q = m × c × ΔT
  * thermodynamics.entropy_change     — ΔS = Q / T (reversible process)

THERMO_VERIFY shape (any subset):
    {
      "T_hot_K": 600.0,
      "T_cold_K": 300.0,
      "claimed_efficiency": 0.5,

      "pressure_Pa": 101325.0,
      "volume_m3": 0.0224,
      "moles": 1.0,
      "temperature_K": 273.15,
      "claimed_pressure_Pa": 101325.0,
      # OR "claimed_volume_m3": ...,
      # OR "claimed_temperature_K": ...,

      "mass_kg": 1.0,
      "specific_heat_J_per_kgK": 4186.0,
      "delta_T_K": 10.0,
      "claimed_heat_J": 41860.0,

      "heat_J": 1000.0,
      "temperature_K": 300.0,
      "claimed_entropy_change_J_per_K": 3.333,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

_R = 8.314  # J / (mol · K)


def verify_carnot_efficiency(spec: Dict[str, Any]) -> VerifierResult:
    """η = 1 − T_cold / T_hot (temperatures in Kelvin)."""
    name = "thermodynamics.carnot_efficiency"
    T_hot = spec.get("T_hot_K")
    T_cold = spec.get("T_cold_K")
    claimed = spec.get("claimed_efficiency")
    if T_hot is None or T_cold is None or claimed is None:
        return na(name)
    try:
        Th, Tc, c = float(T_hot), float(T_cold), float(claimed)
    except (TypeError, ValueError):
        return error(name, "T_hot_K, T_cold_K, and claimed_efficiency must be numeric")
    if Tc <= 0:
        return error(name, f"T_cold_K must be > 0 K, got {Tc}")
    if Th <= Tc:
        return error(name, f"T_hot_K ({Th}) must be greater than T_cold_K ({Tc})")
    actual = 1.0 - Tc / Th
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "T_hot_K": Th,
        "T_cold_K": Tc,
        "actual_efficiency": actual,
        "claimed_efficiency": c,
        "diff": diff,
        "formula": "η = 1 − T_cold / T_hot",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"1 − {Tc}/{Th} = {actual:.6g} (matches claim {c})",
            data,
        )
    return mismatch(
        name,
        f"actual efficiency {actual:.6g}, claimed {c} (diff {diff:.6g})",
        data,
    )


def verify_ideal_gas_law(spec: Dict[str, Any]) -> VerifierResult:
    """PV = nRT; compute whichever claimed_* key is present."""
    name = "thermodynamics.ideal_gas_law"
    P = spec.get("pressure_Pa")
    V = spec.get("volume_m3")
    n = spec.get("moles")
    T = spec.get("temperature_K")

    # Determine which variable is being claimed
    if spec.get("claimed_pressure_Pa") is not None:
        claimed_key = "claimed_pressure_Pa"
        mode = "pressure"
        required = (V, n, T)
        required_names = ("volume_m3", "moles", "temperature_K")
    elif spec.get("claimed_volume_m3") is not None:
        claimed_key = "claimed_volume_m3"
        mode = "volume"
        required = (P, n, T)
        required_names = ("pressure_Pa", "moles", "temperature_K")
    elif spec.get("claimed_temperature_K") is not None:
        claimed_key = "claimed_temperature_K"
        mode = "temperature"
        required = (P, V, n)
        required_names = ("pressure_Pa", "volume_m3", "moles")
    else:
        return na(name, "no claimed_pressure_Pa / claimed_volume_m3 / claimed_temperature_K provided")

    if any(v is None for v in required):
        missing = [k for k, v in zip(required_names, required) if v is None]
        return na(name, f"missing required fields for {mode} check: {missing}")

    claimed = spec.get(claimed_key)
    try:
        claimed_f = float(claimed)
        vals = [float(v) for v in required]
    except (TypeError, ValueError):
        return error(name, "all PV=nRT inputs must be numeric")

    if mode == "pressure":
        Vf, nf, Tf = vals
        if Vf <= 0 or nf <= 0 or Tf <= 0:
            return error(name, "volume_m3, moles, and temperature_K must be positive")
        actual = nf * _R * Tf / Vf
        formula = "P = nRT / V"
    elif mode == "volume":
        Pf, nf, Tf = vals
        if Pf <= 0 or nf <= 0 or Tf <= 0:
            return error(name, "pressure_Pa, moles, and temperature_K must be positive")
        actual = nf * _R * Tf / Pf
        formula = "V = nRT / P"
    else:  # temperature
        Pf, Vf, nf = vals
        if Pf <= 0 or Vf <= 0 or nf <= 0:
            return error(name, "pressure_Pa, volume_m3, and moles must be positive")
        actual = Pf * Vf / (nf * _R)
        formula = "T = PV / (nR)"

    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - claimed_f)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "mode": mode,
        "R_J_per_molK": _R,
        f"actual_{mode}": actual,
        claimed_key: claimed_f,
        "diff": diff,
        "formula": formula,
        "PV_equals_nRT": True,
    }
    if diff <= threshold:
        return confirm(
            name,
            f"PV=nRT ({mode}): computed {actual:.6g} matches claim {claimed_f}",
            data,
        )
    return mismatch(
        name,
        f"PV=nRT ({mode}): actual {actual:.6g}, claimed {claimed_f} (diff {diff:.6g})",
        data,
    )


def verify_specific_heat(spec: Dict[str, Any]) -> VerifierResult:
    """Q = m × c × ΔT."""
    name = "thermodynamics.specific_heat"
    mass = spec.get("mass_kg")
    c_heat = spec.get("specific_heat_J_per_kgK")
    delta_T = spec.get("delta_T_K")
    claimed = spec.get("claimed_heat_J")
    if mass is None or c_heat is None or delta_T is None or claimed is None:
        return na(name)
    try:
        mf, cf, dTf, cl = float(mass), float(c_heat), float(delta_T), float(claimed)
    except (TypeError, ValueError):
        return error(name, "mass_kg, specific_heat_J_per_kgK, delta_T_K, claimed_heat_J must be numeric")
    if mf < 0 or cf < 0:
        return error(name, "mass_kg and specific_heat_J_per_kgK must be non-negative")
    actual = mf * cf * dTf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "mass_kg": mf,
        "specific_heat_J_per_kgK": cf,
        "delta_T_K": dTf,
        "actual_heat_J": actual,
        "claimed_heat_J": cl,
        "diff": diff,
        "formula": "Q = m × c × ΔT",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{mf} × {cf} × {dTf} = {actual:.6g} J (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual Q = {actual:.6g} J, claimed {cl} J (diff {diff:.6g})",
        data,
    )


def verify_entropy_change(spec: Dict[str, Any]) -> VerifierResult:
    """ΔS = Q / T (reversible process, T in Kelvin)."""
    name = "thermodynamics.entropy_change"
    Q = spec.get("heat_J")
    T = spec.get("temperature_K")
    claimed = spec.get("claimed_entropy_change_J_per_K")
    if Q is None or T is None or claimed is None:
        return na(name)
    try:
        Qf, Tf, cl = float(Q), float(T), float(claimed)
    except (TypeError, ValueError):
        return error(name, "heat_J, temperature_K, and claimed_entropy_change_J_per_K must be numeric")
    if Tf <= 0:
        return error(name, f"temperature_K must be > 0 K, got {Tf}")
    actual = Qf / Tf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "heat_J": Qf,
        "temperature_K": Tf,
        "actual_entropy_change_J_per_K": actual,
        "claimed_entropy_change_J_per_K": cl,
        "diff": diff,
        "formula": "ΔS = Q / T",
        "process": "reversible",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{Qf} / {Tf} = {actual:.6g} J/K (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual ΔS = {actual:.6g} J/K, claimed {cl} J/K (diff {diff:.6g})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    tv = packet.get("THERMO_VERIFY") or {}

    if all(tv.get(k) is not None for k in ("T_hot_K", "T_cold_K", "claimed_efficiency")):
        results.append(verify_carnot_efficiency(tv))

    # Ideal gas: dispatch if any claimed_* key present alongside enough known vars
    if (tv.get("claimed_pressure_Pa") is not None
            or tv.get("claimed_volume_m3") is not None
            or tv.get("claimed_temperature_K") is not None):
        results.append(verify_ideal_gas_law(tv))

    if all(tv.get(k) is not None for k in ("mass_kg", "specific_heat_J_per_kgK",
                                             "delta_T_K", "claimed_heat_J")):
        results.append(verify_specific_heat(tv))

    if all(tv.get(k) is not None for k in ("heat_J", "temperature_K",
                                             "claimed_entropy_change_J_per_K")):
        results.append(verify_entropy_change(tv))

    # Phase-point claims (water boils at 100°C, iron melts at 1538°C) used to
    # be table-lookup checks. They are MEASURED values, not derivable from
    # constants of truth — they don't meet the engine's bar. Removed; on the
    # build queue at data/build_queue/queue.jsonl until first-principles
    # phase-equilibrium math (Clausius-Clapeyron with substance-specific
    # latent heats) is wired up.

    if not results:
        # NA, not error — verifier doesn't apply to this spec shape.
        results.append(na("thermodynamics"))
    return results
