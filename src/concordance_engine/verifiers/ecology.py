"""Ecology verifier (metabolism + conservation/balance + information/encoding grid axes).

Logistic population growth, trophic efficiency, Shannon diversity index,
carbon footprint from transport.
Public-domain (standard ecology textbook formulas, IPCC emission factors).

Checks:
  * ecology.logistic_growth           — N(t) = K / (1 + ((K−N0)/N0) × e^(−r×t))
  * ecology.trophic_efficiency        — output = input × efficiency^levels  (10% rule)
  * ecology.shannon_diversity         — H = −Σ(p_i × ln(p_i))
  * ecology.carbon_footprint_transport — CO₂ kg = distance_km × emission_factor_kg_per_km

ECO_VERIFY shape (any subset):
    {
      "carrying_capacity_K": 1000.0,
      "initial_population_N0": 100.0,
      "growth_rate_r": 0.1,
      "time_t": 20.0,
      "claimed_population": 880.0,

      "energy_input": 10000.0,
      "trophic_levels_up": 2,
      "trophic_efficiency": 0.10,
      "claimed_energy_output": 100.0,

      "species_proportions": [0.5, 0.3, 0.2],
      "claimed_shannon_index": 1.0297,

      "distance_km": 500.0,
      "emission_factor_kg_per_km": 0.21,
      "claimed_co2_kg": 105.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_logistic_growth(spec: Dict[str, Any]) -> VerifierResult:
    """N(t) = K / (1 + ((K − N0) / N0) × e^(−r×t))."""
    name = "ecology.logistic_growth"
    K = spec.get("carrying_capacity_K")
    N0 = spec.get("initial_population_N0")
    r = spec.get("growth_rate_r")
    t = spec.get("time_t")
    claimed = spec.get("claimed_population")
    if K is None or N0 is None or r is None or t is None or claimed is None:
        return na(name)
    try:
        Kf, N0f, rf, tf, cl = float(K), float(N0), float(r), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, "carrying_capacity_K, initial_population_N0, growth_rate_r, time_t, claimed_population must be numeric")
    if Kf <= 0:
        return error(name, f"carrying_capacity_K must be positive, got {Kf}")
    if N0f <= 0:
        return error(name, f"initial_population_N0 must be positive, got {N0f}")
    if tf < 0:
        return error(name, f"time_t must be non-negative, got {tf}")
    if N0f > Kf:
        return error(name, f"initial_population_N0 ({N0f}) exceeds carrying_capacity_K ({Kf})")
    exponent = -rf * tf
    # Guard against overflow for very large exponents
    try:
        exp_term = math.exp(exponent)
    except OverflowError:
        exp_term = math.inf
    denom = 1.0 + ((Kf - N0f) / N0f) * exp_term
    if denom == 0:
        return error(name, "logistic denominator is zero; check inputs")
    actual = Kf / denom
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "carrying_capacity_K": Kf,
        "initial_population_N0": N0f,
        "growth_rate_r": rf,
        "time_t": tf,
        "actual_population": actual,
        "claimed_population": cl,
        "diff": diff,
        "formula": "N(t) = K / (1 + ((K−N0)/N0) × e^(−r×t))",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"N({tf}) = {actual:.6g} (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual N({tf}) = {actual:.6g}, claimed {cl} (diff {diff:.6g})",
        data,
    )


def verify_trophic_efficiency(spec: Dict[str, Any]) -> VerifierResult:
    """output = input × efficiency^levels  (default efficiency = 0.10, the 10% rule)."""
    name = "ecology.trophic_efficiency"
    energy_input = spec.get("energy_input")
    levels = spec.get("trophic_levels_up")
    claimed = spec.get("claimed_energy_output")
    if energy_input is None or levels is None or claimed is None:
        return na(name)
    efficiency = spec.get("trophic_efficiency", 0.10)
    try:
        Ef, lf, eff, cl = float(energy_input), float(levels), float(efficiency), float(claimed)
    except (TypeError, ValueError):
        return error(name, "energy_input, trophic_levels_up, trophic_efficiency, and claimed_energy_output must be numeric")
    if Ef < 0:
        return error(name, f"energy_input must be non-negative, got {Ef}")
    if lf < 0 or lf != int(lf):
        return error(name, f"trophic_levels_up must be a non-negative integer, got {lf}")
    if not (0.0 < eff <= 1.0):
        return error(name, f"trophic_efficiency must be in (0, 1], got {eff}")
    actual = Ef * (eff ** int(lf))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "energy_input": Ef,
        "trophic_levels_up": int(lf),
        "trophic_efficiency": eff,
        "actual_energy_output": actual,
        "claimed_energy_output": cl,
        "diff": diff,
        "formula": "output = input × efficiency^levels",
        "note": "default efficiency is 0.10 (Lindeman 10% rule)",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{Ef} × {eff}^{int(lf)} = {actual:.6g} (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual output = {actual:.6g}, claimed {cl} (diff {diff:.6g})",
        data,
    )


def verify_shannon_diversity(spec: Dict[str, Any]) -> VerifierResult:
    """H = −Σ(p_i × ln(p_i)), proportions must sum to ≈ 1.0."""
    name = "ecology.shannon_diversity"
    proportions = spec.get("species_proportions")
    claimed = spec.get("claimed_shannon_index")
    if proportions is None or claimed is None:
        return na(name)
    if not isinstance(proportions, (list, tuple)) or len(proportions) == 0:
        return error(name, "species_proportions must be a non-empty list of floats")
    try:
        props = [float(p) for p in proportions]
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "all species_proportions and claimed_shannon_index must be numeric")
    if any(p < 0 for p in props):
        return error(name, "all species_proportions must be non-negative")
    total = sum(props)
    sum_tol = float(spec.get("tolerance_absolute", 0.001))
    if abs(total - 1.0) > sum_tol:
        return error(
            name,
            f"species_proportions sum to {total:.6f}, must be ≈ 1.0 (tolerance {sum_tol})",
        )
    # Compute H; skip p=0 terms (0 × ln 0 → 0 by convention)
    H = 0.0
    for p in props:
        if p > 0:
            H -= p * math.log(p)
    actual = H
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "species_proportions": props,
        "species_count": len(props),
        "proportions_sum": total,
        "actual_shannon_index": actual,
        "claimed_shannon_index": cl,
        "diff": diff,
        "formula": "H = −Σ(p_i × ln(p_i))",
        "note": "zero-proportion terms excluded (0·ln0 = 0 by convention)",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"H = {actual:.6g} nats (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual H = {actual:.6g} nats, claimed {cl} (diff {diff:.6g})",
        data,
    )


def verify_carbon_footprint_transport(spec: Dict[str, Any]) -> VerifierResult:
    """CO₂ kg = distance_km × emission_factor_kg_per_km."""
    name = "ecology.carbon_footprint_transport"
    distance = spec.get("distance_km")
    factor = spec.get("emission_factor_kg_per_km")
    claimed = spec.get("claimed_co2_kg")
    if distance is None or factor is None or claimed is None:
        return na(name)
    try:
        df, ff, cl = float(distance), float(factor), float(claimed)
    except (TypeError, ValueError):
        return error(name, "distance_km, emission_factor_kg_per_km, and claimed_co2_kg must be numeric")
    if df < 0:
        return error(name, f"distance_km must be non-negative, got {df}")
    if ff < 0:
        return error(name, f"emission_factor_kg_per_km must be non-negative, got {ff}")
    actual = df * ff
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - cl)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {
        "distance_km": df,
        "emission_factor_kg_per_km": ff,
        "actual_co2_kg": actual,
        "claimed_co2_kg": cl,
        "diff": diff,
        "formula": "CO₂_kg = distance_km × emission_factor_kg_per_km",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{df} km × {ff} kg/km = {actual:.6g} kg CO₂ (matches claim {cl})",
            data,
        )
    return mismatch(
        name,
        f"actual CO₂ = {actual:.6g} kg, claimed {cl} kg (diff {diff:.6g})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("ECO_VERIFY") or {}

    if all(ev.get(k) is not None for k in ("carrying_capacity_K", "initial_population_N0",
                                             "growth_rate_r", "time_t", "claimed_population")):
        results.append(verify_logistic_growth(ev))

    if all(ev.get(k) is not None for k in ("energy_input", "trophic_levels_up",
                                             "claimed_energy_output")):
        results.append(verify_trophic_efficiency(ev))

    if all(ev.get(k) is not None for k in ("species_proportions", "claimed_shannon_index")):
        results.append(verify_shannon_diversity(ev))

    if all(ev.get(k) is not None for k in ("distance_km", "emission_factor_kg_per_km",
                                             "claimed_co2_kg")):
        results.append(verify_carbon_footprint_transport(ev))

    if not results:
        results.append(na("ecology", "no ECO_VERIFY artifacts present"))
    return results
