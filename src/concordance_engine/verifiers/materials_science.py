"""Materials Science verifier (physical-substance + encoding grid axes).

Stress/strain relationships, thermal expansion, density, and hardness.
Public-domain (standard engineering mechanics textbooks).

Checks:
  * materials_science.stress_strain       — σ = E·ε, σ = F/A, ε = σ/E
  * materials_science.thermal_expansion   — ΔL = α·L₀·ΔT
  * materials_science.density             — ρ = m/V or m = ρ·V
  * materials_science.hardness_comparison — Vickers/Brinell: higher HV/HB = harder

MAT_VERIFY shape (any subset):
    {
      "youngs_modulus_Pa": 200e9,
      "strain": 0.001,
      "claimed_stress_Pa": 200e6,

      "youngs_modulus_Pa": 200e9,
      "stress_Pa": 200e6,
      "claimed_strain": 0.001,

      "force_N": 1000,
      "area_m2": 0.01,
      "claimed_stress_Pa": 100000,

      "thermal_expansion_coeff": 12e-6,
      "original_length_m": 2.0,
      "delta_T_K": 50,
      "claimed_delta_length_m": 0.0012,

      "mass_kg": 5.0,
      "volume_m3": 0.002,
      "claimed_density_kg_per_m3": 2500,

      "density_kg_per_m3": 2500,
      "volume_m3": 0.002,
      "claimed_mass_kg": 5.0,

      "material_a_hardness": 700,
      "material_b_hardness": 400,
      "claimed_a_harder_than_b": true,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_stress_strain(spec: Dict[str, Any]) -> VerifierResult:
    """Handle three sub-cases depending on which claimed_* key is present.

    Case 1: claimed_stress_Pa with youngs_modulus_Pa + strain → σ = E·ε
    Case 2: claimed_strain with youngs_modulus_Pa + stress_Pa → ε = σ/E
    Case 3: claimed_stress_Pa with force_N + area_m2 → σ = F/A
    """
    name = "materials_science.stress_strain"
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))

    # Case 3: force → stress (check before case 1 to avoid ambiguity)
    if (spec.get("force_N") is not None and spec.get("area_m2") is not None
            and spec.get("strain") is None and spec.get("claimed_stress_Pa") is not None):
        F = spec.get("force_N")
        A = spec.get("area_m2")
        claimed = spec.get("claimed_stress_Pa")
        try:
            Ff, Af, c = float(F), float(A), float(claimed)
        except (TypeError, ValueError):
            return error(name, "force_N, area_m2, claimed_stress_Pa must be numeric")
        if Af <= 0:
            return error(name, f"area_m2 must be positive, got {Af}")
        actual = Ff / Af
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "σ = F / A", "force_N": Ff, "area_m2": Af,
                "actual_stress_Pa": actual, "claimed_stress_Pa": c, "diff": diff}
        if diff <= threshold:
            return confirm(name, f"σ = {Ff}/{Af} = {actual:.6g} Pa (matches claim {c})", data)
        return mismatch(name, f"actual σ {actual:.6g} Pa, claimed {c} Pa (diff {diff:.6g})", data)

    # Case 1: E + ε → σ
    if (spec.get("youngs_modulus_Pa") is not None and spec.get("strain") is not None
            and spec.get("claimed_stress_Pa") is not None):
        E = spec.get("youngs_modulus_Pa")
        eps = spec.get("strain")
        claimed = spec.get("claimed_stress_Pa")
        try:
            Ef, epsf, c = float(E), float(eps), float(claimed)
        except (TypeError, ValueError):
            return error(name, "youngs_modulus_Pa, strain, claimed_stress_Pa must be numeric")
        if Ef <= 0:
            return error(name, f"youngs_modulus_Pa must be positive, got {Ef}")
        actual = Ef * epsf
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "σ = E · ε", "youngs_modulus_Pa": Ef, "strain": epsf,
                "actual_stress_Pa": actual, "claimed_stress_Pa": c, "diff": diff}
        if diff <= threshold:
            return confirm(name, f"σ = {Ef:.4g}·{epsf:.4g} = {actual:.6g} Pa (matches claim {c})", data)
        return mismatch(name, f"actual σ {actual:.6g} Pa, claimed {c} Pa (diff {diff:.6g})", data)

    # Case 2: E + σ → ε
    if (spec.get("youngs_modulus_Pa") is not None and spec.get("stress_Pa") is not None
            and spec.get("claimed_strain") is not None):
        E = spec.get("youngs_modulus_Pa")
        sigma = spec.get("stress_Pa")
        claimed = spec.get("claimed_strain")
        try:
            Ef, sf, c = float(E), float(sigma), float(claimed)
        except (TypeError, ValueError):
            return error(name, "youngs_modulus_Pa, stress_Pa, claimed_strain must be numeric")
        if Ef <= 0:
            return error(name, f"youngs_modulus_Pa must be positive, got {Ef}")
        actual = sf / Ef
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "ε = σ / E", "youngs_modulus_Pa": Ef, "stress_Pa": sf,
                "actual_strain": actual, "claimed_strain": c, "diff": diff}
        if diff <= threshold:
            return confirm(name, f"ε = {sf:.4g}/{Ef:.4g} = {actual:.6g} (matches claim {c})", data)
        return mismatch(name, f"actual ε {actual:.6g}, claimed {c} (diff {diff:.6g})", data)

    return na(name)


def verify_thermal_expansion(spec: Dict[str, Any]) -> VerifierResult:
    """ΔL = α · L₀ · ΔT"""
    name = "materials_science.thermal_expansion"
    alpha = spec.get("thermal_expansion_coeff")
    L0 = spec.get("original_length_m")
    dT = spec.get("delta_T_K")
    claimed = spec.get("claimed_delta_length_m")
    if alpha is None or L0 is None or dT is None or claimed is None:
        return na(name)
    try:
        af, L0f, dTf, c = float(alpha), float(L0), float(dT), float(claimed)
    except (TypeError, ValueError):
        return error(name, "thermal_expansion_coeff, original_length_m, delta_T_K, "
                           "claimed_delta_length_m must be numeric")
    if L0f < 0:
        return error(name, f"original_length_m must be non-negative, got {L0f}")
    actual = af * L0f * dTf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "ΔL = α · L₀ · ΔT",
            "thermal_expansion_coeff": af, "original_length_m": L0f,
            "delta_T_K": dTf, "actual_delta_length_m": actual,
            "claimed_delta_length_m": c, "diff": diff}
    if diff <= threshold:
        return confirm(name,
                       f"ΔL = {af:.4g}·{L0f}·{dTf} = {actual:.6g} m (matches claim {c})",
                       data)
    return mismatch(name,
                    f"actual ΔL {actual:.6g} m, claimed {c} m (diff {diff:.6g})",
                    data)


def verify_density(spec: Dict[str, Any]) -> VerifierResult:
    """ρ = m/V or m = ρ·V depending on which claimed_* key is present."""
    name = "materials_science.density"
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))

    # Case 1: mass + volume → density
    if (spec.get("mass_kg") is not None and spec.get("volume_m3") is not None
            and spec.get("claimed_density_kg_per_m3") is not None):
        m = spec.get("mass_kg")
        V = spec.get("volume_m3")
        claimed = spec.get("claimed_density_kg_per_m3")
        try:
            mf, Vf, c = float(m), float(V), float(claimed)
        except (TypeError, ValueError):
            return error(name, "mass_kg, volume_m3, claimed_density_kg_per_m3 must be numeric")
        if Vf <= 0:
            return error(name, f"volume_m3 must be positive, got {Vf}")
        actual = mf / Vf
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "ρ = m / V", "mass_kg": mf, "volume_m3": Vf,
                "actual_density_kg_per_m3": actual, "claimed_density_kg_per_m3": c, "diff": diff}
        if diff <= threshold:
            return confirm(name, f"ρ = {mf}/{Vf} = {actual:.6g} kg/m³ (matches claim {c})", data)
        return mismatch(name, f"actual ρ {actual:.6g} kg/m³, claimed {c} (diff {diff:.6g})", data)

    # Case 2: density + volume → mass
    if (spec.get("density_kg_per_m3") is not None and spec.get("volume_m3") is not None
            and spec.get("claimed_mass_kg") is not None):
        rho = spec.get("density_kg_per_m3")
        V = spec.get("volume_m3")
        claimed = spec.get("claimed_mass_kg")
        try:
            rhof, Vf, c = float(rho), float(V), float(claimed)
        except (TypeError, ValueError):
            return error(name, "density_kg_per_m3, volume_m3, claimed_mass_kg must be numeric")
        if Vf <= 0:
            return error(name, f"volume_m3 must be positive, got {Vf}")
        actual = rhof * Vf
        diff = abs(actual - c)
        threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
        data = {"formula": "m = ρ · V", "density_kg_per_m3": rhof, "volume_m3": Vf,
                "actual_mass_kg": actual, "claimed_mass_kg": c, "diff": diff}
        if diff <= threshold:
            return confirm(name, f"m = {rhof}·{Vf} = {actual:.6g} kg (matches claim {c})", data)
        return mismatch(name, f"actual m {actual:.6g} kg, claimed {c} kg (diff {diff:.6g})", data)

    return na(name)


def verify_hardness_comparison(spec: Dict[str, Any]) -> VerifierResult:
    """Vickers/Brinell: higher HV/HB number = harder material."""
    name = "materials_science.hardness_comparison"
    ha = spec.get("material_a_hardness")
    hb = spec.get("material_b_hardness")
    claimed = spec.get("claimed_a_harder_than_b")
    if ha is None or hb is None or claimed is None:
        return na(name)
    try:
        haf, hbf = float(ha), float(hb)
    except (TypeError, ValueError):
        return error(name, "material_a_hardness and material_b_hardness must be numeric")
    actual = haf > hbf
    data = {"material_a_hardness": haf, "material_b_hardness": hbf,
            "actual_a_harder_than_b": actual,
            "claimed_a_harder_than_b": bool(claimed),
            "formula": "actual = material_a_hardness > material_b_hardness",
            "rule": "higher HV/HB number indicates harder material"}
    if actual == bool(claimed):
        return confirm(name,
                       f"HV/HB {haf} {'>' if actual else '≤'} {hbf} → a_harder={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"HV/HB {haf} vs {hbf} → a_harder={actual}, claimed {bool(claimed)}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MAT_VERIFY") or {}

    # stress_strain: triggered by any of the three sub-cases
    _stress_keys = (
        ("youngs_modulus_Pa", "strain", "claimed_stress_Pa"),
        ("youngs_modulus_Pa", "stress_Pa", "claimed_strain"),
        ("force_N", "area_m2", "claimed_stress_Pa"),
    )
    if any(all(mv.get(k) is not None for k in combo) for combo in _stress_keys):
        results.append(verify_stress_strain(mv))

    if all(mv.get(k) is not None for k in ("thermal_expansion_coeff", "original_length_m",
                                            "delta_T_K", "claimed_delta_length_m")):
        results.append(verify_thermal_expansion(mv))

    _density_keys = (
        ("mass_kg", "volume_m3", "claimed_density_kg_per_m3"),
        ("density_kg_per_m3", "volume_m3", "claimed_mass_kg"),
    )
    if any(all(mv.get(k) is not None for k in combo) for combo in _density_keys):
        results.append(verify_density(mv))

    if all(mv.get(k) is not None for k in ("material_a_hardness", "material_b_hardness",
                                            "claimed_a_harder_than_b")):
        results.append(verify_hardness_comparison(mv))

    if not results:
        results.append(na("materials_science", "no MAT_VERIFY artifacts present"))
    return results
