"""Nuclear physics verifier (physical-substance + time-sequence + conservation/balance grid axes).

Radioactive decay, binding energy, half-life from activity, decay constant.
Public-domain (standard nuclear physics, NIST mass constants, AME mass excess tables).

Checks:
  * nuclear_physics.radioactive_decay          — N(t) = N₀ × e^(−λt), λ = ln2 / T_half
  * nuclear_physics.binding_energy_per_nucleon — BE/A via mass defect (1 amu = 931.5 MeV)
  * nuclear_physics.half_life_from_activity    — T_half = ln(2) × N / A
  * nuclear_physics.decay_constant             — λ = ln(2) / T_half

NUCLEAR_VERIFY shape (any subset):
    {
      "half_life_seconds": 1600.0,
      "elapsed_seconds": 1600.0,
      "initial_count": 1e12,
      "claimed_remaining_count": 5e11,

      "mass_defect_amu": 0.0988,
      "nucleon_count": 56,
      "claimed_binding_energy_MeV_per_nucleon": 8.79,

      "activity_Bq": 1e10,
      "atom_count": 2.31e13,
      "claimed_half_life_seconds": 1600.0,

      "half_life_seconds": 1600.0,
      "claimed_decay_constant": 4.332e-4,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

_LN2 = math.log(2)
_AMU_TO_MEV = 931.5  # MeV per amu (unified atomic mass unit)


def verify_radioactive_decay(spec: Dict[str, Any]) -> VerifierResult:
    """N(t) = N₀ × e^(−λt), where λ = ln(2) / T_half."""
    name = "nuclear_physics.radioactive_decay"
    T_half = spec.get("half_life_seconds")
    t = spec.get("elapsed_seconds")
    N0 = spec.get("initial_count")
    claimed = spec.get("claimed_remaining_count")
    if T_half is None or t is None or N0 is None or claimed is None:
        return na(name)
    try:
        Tf, tf, N0f, cl = float(T_half), float(t), float(N0), float(claimed)
    except (TypeError, ValueError):
        return error(name, "half_life_seconds, elapsed_seconds, initial_count, claimed_remaining_count must be numeric")
    if Tf <= 0:
        return error(name, f"half_life_seconds must be positive, got {Tf}")
    if tf < 0 or N0f < 0:
        return error(name, "elapsed_seconds and initial_count must be non-negative")
    lam = _LN2 / Tf
    actual = N0f * math.exp(-lam * tf)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "half_life_seconds": Tf,
        "elapsed_seconds": tf,
        "initial_count": N0f,
        "decay_constant_per_s": lam,
        "actual_remaining_count": actual,
        "claimed_remaining_count": cl,
        "diff": diff,
        "n_half_lives": tf / Tf,
        "formula": "N(t) = N₀ × e^(−λt),  λ = ln(2) / T_half",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"N₀={N0f:.4g} × e^(−{lam:.4g}×{tf}) = {actual:.6g} (matches claim {cl:.6g})",
            data,
        )
    return mismatch(
        name,
        f"actual N(t) = {actual:.6g}, claimed {cl:.6g} (diff {diff:.6g})",
        data,
    )


def verify_binding_energy_per_nucleon(spec: Dict[str, Any]) -> VerifierResult:
    """BE/A = (mass_defect_amu × 931.5 MeV/amu) / nucleon_count."""
    name = "nuclear_physics.binding_energy_per_nucleon"
    mass_defect = spec.get("mass_defect_amu")
    A = spec.get("nucleon_count")
    claimed = spec.get("claimed_binding_energy_MeV_per_nucleon")
    if mass_defect is None or A is None or claimed is None:
        return na(name)
    try:
        mdf, Af, cl = float(mass_defect), float(A), float(claimed)
    except (TypeError, ValueError):
        return error(name, "mass_defect_amu, nucleon_count, claimed_binding_energy_MeV_per_nucleon must be numeric")
    if mdf < 0:
        return error(name, f"mass_defect_amu must be non-negative, got {mdf}")
    if Af <= 0 or Af != int(Af):
        return error(name, f"nucleon_count must be a positive integer, got {Af}")
    binding_energy_MeV = mdf * _AMU_TO_MEV
    actual = binding_energy_MeV / Af
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "mass_defect_amu": mdf,
        "nucleon_count": int(Af),
        "total_binding_energy_MeV": binding_energy_MeV,
        "actual_BE_per_nucleon_MeV": actual,
        "claimed_BE_per_nucleon_MeV": cl,
        "diff": diff,
        "amu_to_MeV": _AMU_TO_MEV,
        "formula": "BE/A = (Δm_amu × 931.5 MeV/amu) / A",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"({mdf} amu × 931.5) / {int(Af)} = {actual:.6g} MeV/nucleon (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual BE/A = {actual:.6g} MeV/nucleon, claimed {cl} (diff {diff:.6g})",
        data,
    )


def verify_half_life_from_activity(spec: Dict[str, Any]) -> VerifierResult:
    """T_half = ln(2) × N / A,  derived from A = λN = (ln2/T_half)×N."""
    name = "nuclear_physics.half_life_from_activity"
    A = spec.get("activity_Bq")
    N = spec.get("atom_count")
    claimed = spec.get("claimed_half_life_seconds")
    if A is None or N is None or claimed is None:
        return na(name)
    try:
        Af, Nf, cl = float(A), float(N), float(claimed)
    except (TypeError, ValueError):
        return error(name, "activity_Bq, atom_count, and claimed_half_life_seconds must be numeric")
    if Af <= 0:
        return error(name, f"activity_Bq must be positive, got {Af}")
    if Nf <= 0:
        return error(name, f"atom_count must be positive, got {Nf}")
    actual = _LN2 * Nf / Af
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "activity_Bq": Af,
        "atom_count": Nf,
        "actual_half_life_seconds": actual,
        "claimed_half_life_seconds": cl,
        "diff": diff,
        "formula": "T_half = ln(2) × N / A",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"ln(2) × {Nf:.4g} / {Af:.4g} = {actual:.6g} s (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual T_half = {actual:.6g} s, claimed {cl} s (diff {diff:.6g})",
        data,
    )


def verify_decay_constant(spec: Dict[str, Any]) -> VerifierResult:
    """λ = ln(2) / T_half."""
    name = "nuclear_physics.decay_constant"
    T_half = spec.get("half_life_seconds")
    claimed = spec.get("claimed_decay_constant")
    if T_half is None or claimed is None:
        return na(name)
    try:
        Tf, cl = float(T_half), float(claimed)
    except (TypeError, ValueError):
        return error(name, "half_life_seconds and claimed_decay_constant must be numeric")
    if Tf <= 0:
        return error(name, f"half_life_seconds must be positive, got {Tf}")
    actual = _LN2 / Tf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "half_life_seconds": Tf,
        "actual_decay_constant_per_s": actual,
        "claimed_decay_constant_per_s": cl,
        "diff": diff,
        "formula": "λ = ln(2) / T_half",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"ln(2) / {Tf} = {actual:.6g} s⁻¹ (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual λ = {actual:.6g} s⁻¹, claimed {cl} s⁻¹ (diff {diff:.6g})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    nv = packet.get("NUCLEAR_VERIFY") or {}

    if all(nv.get(k) is not None for k in ("half_life_seconds", "elapsed_seconds",
                                             "initial_count", "claimed_remaining_count")):
        results.append(verify_radioactive_decay(nv))

    if all(nv.get(k) is not None for k in ("mass_defect_amu", "nucleon_count",
                                             "claimed_binding_energy_MeV_per_nucleon")):
        results.append(verify_binding_energy_per_nucleon(nv))

    if all(nv.get(k) is not None for k in ("activity_Bq", "atom_count",
                                             "claimed_half_life_seconds")):
        results.append(verify_half_life_from_activity(nv))

    if all(nv.get(k) is not None for k in ("half_life_seconds", "claimed_decay_constant")):
        results.append(verify_decay_constant(nv))

    if not results:
        results.append(na("nuclear_physics", "no NUCLEAR_VERIFY artifacts present"))
    return results
