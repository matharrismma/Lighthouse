"""Electrical engineering verifier (engineering / physical-substance grid axis
sibling to chemistry, physics, manufacturing, astronomy).

Deterministic checks against canonical electrical-circuits laws:
Ohm's law, electrical power, Kirchhoff's voltage/current laws, and
RC time constants. All formulas are public-domain.

Checks performed:

  * electrical.ohms_law
      V = I·R. Given any two of (V, I, R), the third must match claim
      within tolerance.
  * electrical.power
      P = V·I = I²·R = V²/R. Three forms cross-checked against claim.
  * electrical.kirchhoff_voltage_loop
      Sum of EMF/voltage drops around any closed loop = 0. Given
      a list of signed voltages, the sum must equal claim within tol.
  * electrical.rc_time_constant
      τ = R·C (seconds). Capacitor voltage v(t) = V·(1 - e^(-t/τ)).
      Given R, C, and t, the claimed fraction-of-final must match.

ELEC_VERIFY packet shape (any subset of fields):
    {
      "voltage_V": 12.0, "current_A": 0.5, "resistance_ohm": 24.0,

      "power_W_claim": 6.0,

      "voltages_in_loop": [9, -4.5, -4.5],
      "claimed_loop_sum_V": 0.0,

      "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
      "elapsed_s": 1e-3,
      "supply_V": 5.0,
      "claimed_capacitor_voltage_V": 3.16,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _close(actual: float, claimed: float, rel_tol: float = 1e-3, abs_tol: float = 1e-6) -> bool:
    return abs(actual - claimed) <= max(abs_tol, rel_tol * abs(actual))


def verify_ohms_law(spec: Dict[str, Any]) -> VerifierResult:
    """V = I·R. Provide two of three; the verifier checks the third."""
    name = "electrical.ohms_law"
    V = spec.get("voltage_V")
    I = spec.get("current_A")
    R = spec.get("resistance_ohm")
    provided = sum(1 for x in (V, I, R) if x is not None)
    if provided < 3:
        return na(name, "ohms_law needs all three of (voltage_V, current_A, resistance_ohm)")
    try:
        Vf, If, Rf = float(V), float(I), float(R)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if Rf < 0 or If < 0 and Vf > 0:
        # Negative R/I flips sign convention but still computes; only error on R<0.
        if Rf < 0:
            return error(name, f"resistance must be non-negative, got {Rf}")
    actual_V = If * Rf
    diff = abs(actual_V - Vf)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    threshold = max(1e-6, rel_tol * abs(actual_V) if actual_V else 1e-6)
    data = {"voltage_V": Vf, "current_A": If, "resistance_ohm": Rf,
            "actual_V_from_IR": actual_V, "diff_V": diff,
            "formula": "V = I · R"}
    if diff <= threshold:
        return confirm(name, f"V = {If}·{Rf} = {actual_V} (matches claim {Vf})", data)
    return mismatch(name,
                    f"V = {If}·{Rf} = {actual_V}, claimed {Vf} (diff {diff})",
                    data)


def verify_power(spec: Dict[str, Any]) -> VerifierResult:
    """P = V·I (or I²R or V²/R) matches claim."""
    name = "electrical.power"
    V = spec.get("voltage_V")
    I = spec.get("current_A")
    R = spec.get("resistance_ohm")
    claimed = spec.get("power_W_claim")
    if claimed is None:
        return na(name)
    # Need at least two of (V, I, R).
    forms = []
    if V is not None and I is not None:
        try:
            forms.append(("V·I", float(V) * float(I)))
        except (TypeError, ValueError):
            return error(name, "V/I must be numeric")
    if I is not None and R is not None:
        try:
            Rf = float(R)
            forms.append(("I²·R", float(I) ** 2 * Rf))
        except (TypeError, ValueError):
            return error(name, "I/R must be numeric")
    if V is not None and R is not None:
        try:
            Rf = float(R)
            if Rf == 0:
                return error(name, "cannot compute V²/R with R=0")
            forms.append(("V²/R", float(V) ** 2 / Rf))
        except (TypeError, ValueError):
            return error(name, "V/R must be numeric")
    if not forms:
        return na(name, "need at least two of (voltage_V, current_A, resistance_ohm)")
    try:
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"power_W_claim must be numeric, got {claimed!r}")
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    matches = [(label, p, abs(p - c)) for (label, p) in forms]
    all_match = all(_close(p, c, rel_tol=rel_tol) for (_, p, _) in matches)
    data = {"forms": [{"label": label, "value": p, "diff": d} for (label, p, d) in matches],
            "claimed_W": c, "tolerance_relative": rel_tol,
            "formulas": "P = V·I = I²·R = V²/R"}
    if all_match:
        return confirm(name,
                       f"P forms {[f'{label}={p:.4g}' for (label, p, _) in matches]} all match claim {c}",
                       data)
    return mismatch(name,
                    f"power forms {[(label, p) for (label, p, _) in matches]} vs claim {c}",
                    data)


def verify_kirchhoff_voltage_loop(spec: Dict[str, Any]) -> VerifierResult:
    """Sum of signed voltages around a loop equals claim (typically 0)."""
    name = "electrical.kirchhoff_voltage_loop"
    voltages = spec.get("voltages_in_loop")
    claimed = spec.get("claimed_loop_sum_V")
    if voltages is None or claimed is None:
        return na(name)
    if not isinstance(voltages, (list, tuple)) or not voltages:
        return error(name, "voltages_in_loop must be a non-empty list")
    try:
        vs = [float(v) for v in voltages]
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "voltages must be numeric")
    actual = sum(vs)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-6))
    threshold = max(abs_tol, rel_tol * max(abs(actual), 1.0))
    diff = abs(actual - c)
    data = {"voltages_in_loop": vs, "actual_sum": actual, "claimed_sum": c,
            "diff": diff, "formula": "ΣV = 0 (KVL)"}
    if diff <= threshold:
        return confirm(name,
                       f"ΣV = {actual:.6g} (matches claim {c}, diff {diff:.6g})",
                       data)
    return mismatch(name,
                    f"ΣV = {actual:.6g}, claimed {c} (diff {diff:.6g} > {threshold:.6g})",
                    data)


def verify_rc_time_constant(spec: Dict[str, Any]) -> VerifierResult:
    """RC charging: v(t) = V·(1 - e^(-t/RC))."""
    name = "electrical.rc_time_constant"
    R = spec.get("resistance_ohm_rc")
    C = spec.get("capacitance_F")
    t = spec.get("elapsed_s")
    V = spec.get("supply_V")
    claimed = spec.get("claimed_capacitor_voltage_V")
    if R is None or C is None or t is None or V is None or claimed is None:
        return na(name)
    try:
        Rf, Cf, tf, Vf, cf = float(R), float(C), float(t), float(V), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if Rf <= 0 or Cf <= 0:
        return error(name, f"R and C must be positive, got R={Rf}, C={Cf}")
    if tf < 0:
        return error(name, f"elapsed time cannot be negative, got {tf}")
    tau = Rf * Cf
    actual = Vf * (1.0 - math.exp(-tf / tau))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-3))
    threshold = max(abs_tol, rel_tol * abs(actual))
    diff = abs(actual - cf)
    data = {"R": Rf, "C": Cf, "elapsed_s": tf, "supply_V": Vf,
            "tau": tau, "actual_v": actual, "claimed_v": cf,
            "diff": diff, "formula": "v(t) = V(1 − e^(−t/RC))"}
    if diff <= threshold:
        return confirm(name,
                       f"v({tf}) = {Vf}·(1 − e^(−{tf}/{tau:.3g})) = {actual:.4f} V (matches claim {cf})",
                       data)
    return mismatch(name,
                    f"v({tf}) = {actual:.4f} V, claimed {cf} (diff {diff:.4f})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("ELEC_VERIFY") or {}

    if all(ev.get(k) is not None for k in ("voltage_V", "current_A", "resistance_ohm")):
        results.append(verify_ohms_law(ev))
    if "power_W_claim" in ev:
        results.append(verify_power(ev))
    if "voltages_in_loop" in ev and "claimed_loop_sum_V" in ev:
        results.append(verify_kirchhoff_voltage_loop(ev))
    if all(k in ev for k in ("resistance_ohm_rc", "capacitance_F", "elapsed_s",
                             "supply_V", "claimed_capacitor_voltage_V")):
        results.append(verify_rc_time_constant(ev))

    if not results:
        results.append(na("electrical", "no ELEC_VERIFY artifacts present"))
    return results
