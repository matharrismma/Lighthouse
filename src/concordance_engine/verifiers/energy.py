"""Energy verifier — power systems, off-grid sizing, conservation.

Engineering / physical-substance grid axis sibling to electrical,
manufacturing, hydrology. Distinct from `physics` (which checks
arbitrary equations for dimensional consistency) and `electrical`
(which checks circuit-level laws on a small scale): this verifier
operates at the *system* scale — a daily energy budget, a battery
bank, a solar array, a wire run between them.

Per the kingdom-economy substrate doctrine: those who refuse the
mark may need off-grid power. An energy verifier that can check
"does this system actually meet that load" turns napkin arithmetic
into deterministic verification.

Checks performed:

  * energy.power_balance
      Generation (kWh/day) − consumption − losses = surplus/deficit.
      First law of thermodynamics applied at the daily-budget level.

  * energy.battery_sizing
      required_Ah = (daily_kWh × days_autonomy × 1000) / (V × DoD).
      Matches claim within tolerance.

  * energy.solar_daily_yield
      daily_kWh = panel_W × peak_sun_hours × system_efficiency / 1000.
      Standard PV system sizing formula.

  * energy.wire_voltage_drop
      Vdrop = 2 × I × resistance_per_m × length (DC round-trip).
      Compared to claim or to a percentage of system voltage.

  * energy.kwh_wh_consistency
      kWh × 1000 = Wh. Trivial dimensional check that catches
      paste-error mistakes between energy unit scales.

  * energy.efficiency
      η = output / input. Must equal claim AND be ≤ 1.0 (no
      perpetual motion). Heat pump COP can exceed 1.0 (handled
      separately via cop flag).

  * energy.runtime
      runtime_hours = battery_capacity_Wh / load_W. The standard
      "how long can this system run my fridge?" calculation.

  * energy.peak_load_vs_inverter
      Peak instantaneous load ≤ inverter continuous rating. Common
      off-grid sizing failure mode (sized for daily kWh but not
      for peak draw).

Packet shape (any subset; missing fields yield NOT_APPLICABLE):

    {
      "domain": "energy",
      "ENERGY_VERIFY": {
        "generation_kwh_day": 12.0,
        "consumption_kwh_day": 8.5,
        "losses_kwh_day": 1.5,
        "claimed_balance_kwh_day": 2.0,

        "daily_load_kwh": 5.0,
        "days_autonomy": 2,
        "depth_of_discharge": 0.5,
        "system_voltage_V": 24,
        "claimed_battery_Ah": 833,

        "panel_W": 400,
        "peak_sun_hours": 5.0,
        "system_efficiency": 0.85,
        "claimed_daily_kwh": 1.7,

        "wire_resistance_ohm_per_m": 0.0033,
        "distance_m": 10.0,
        "current_A": 30.0,
        "system_V_for_drop": 24,
        "claimed_drop_V": 1.98,

        "kwh": 5.0,
        "claimed_wh": 5000,

        "input_W": 1000,
        "output_W": 850,
        "claimed_efficiency": 0.85,
        "is_heat_pump": false,

        "battery_wh": 1200,
        "load_W": 100,
        "claimed_runtime_hours": 12,

        "peak_load_W": 2400,
        "inverter_continuous_W": 3000
      }
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


def _close(actual: float, claimed: float, rel_tol: float = 1e-3,
           abs_tol: float = 1e-6) -> bool:
    """Tolerance comparison: pass if either rel or abs threshold satisfied."""
    return abs(actual - claimed) <= max(abs_tol, rel_tol * abs(actual))


def _num(value: Any) -> Optional[float]:
    """Best-effort numeric coerce. Returns None if not coerceable."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── 1. Power balance ───────────────────────────────────────────────


def verify_power_balance(spec: Dict[str, Any]) -> VerifierResult:
    """Generation − consumption − losses = claimed balance."""
    name = "energy.power_balance"
    gen = _num(spec.get("generation_kwh_day"))
    cons = _num(spec.get("consumption_kwh_day"))
    losses = _num(spec.get("losses_kwh_day")) or 0.0
    claimed = _num(spec.get("claimed_balance_kwh_day"))
    if gen is None or cons is None or claimed is None:
        return na(name)
    if gen < 0 or cons < 0 or losses < 0:
        return error(name,
                     f"all values must be non-negative; "
                     f"got gen={gen}, cons={cons}, losses={losses}")
    actual = gen - cons - losses
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-3
    abs_tol = _num(spec.get("tolerance_absolute")) or 1e-3
    threshold = max(abs_tol, rel_tol * max(abs(actual), 1.0))
    diff = abs(actual - claimed)
    data = {
        "generation_kwh_day": gen,
        "consumption_kwh_day": cons,
        "losses_kwh_day": losses,
        "actual_balance_kwh_day": actual,
        "claimed_balance_kwh_day": claimed,
        "diff": diff,
        "formula": "balance = generation - consumption - losses",
        "kingdom_economy_note": (
            "negative balance means the system underproduces; "
            "kingdom-economy-aligned design has positive balance "
            "with margin for cloudy days"
        ),
    }
    if diff <= threshold:
        sign = "surplus" if actual > 0 else ("deficit" if actual < 0 else "exact")
        return confirm(name,
                       f"balance = {gen} - {cons} - {losses} = "
                       f"{actual:.4g} kWh/day ({sign}; matches claim {claimed})",
                       data)
    return mismatch(name,
                    f"balance = {actual:.4g} kWh/day, claimed {claimed} "
                    f"(diff {diff:.4g})",
                    data)


# ── 2. Battery sizing ──────────────────────────────────────────────


def verify_battery_sizing(spec: Dict[str, Any]) -> VerifierResult:
    """required_Ah = (daily_kWh × days_autonomy × 1000) / (V × DoD)."""
    name = "energy.battery_sizing"
    daily_kwh = _num(spec.get("daily_load_kwh"))
    days = _num(spec.get("days_autonomy"))
    dod = _num(spec.get("depth_of_discharge"))
    sys_v = _num(spec.get("system_voltage_V"))
    claimed = _num(spec.get("claimed_battery_Ah"))
    if any(x is None for x in (daily_kwh, days, dod, sys_v, claimed)):
        return na(name)
    if daily_kwh <= 0 or days <= 0:
        return error(name, "daily_load_kwh and days_autonomy must be positive")
    if not (0 < dod <= 1.0):
        return error(name,
                     f"depth_of_discharge must be in (0, 1.0]; got {dod}")
    if sys_v <= 0:
        return error(name, f"system_voltage_V must be positive; got {sys_v}")
    actual_ah = (daily_kwh * days * 1000.0) / (sys_v * dod)
    rel_tol = _num(spec.get("tolerance_relative")) or 5e-3
    threshold = max(0.5, rel_tol * actual_ah)  # ≥0.5 Ah floor
    diff = abs(actual_ah - claimed)
    data = {
        "daily_load_kwh": daily_kwh,
        "days_autonomy": days,
        "depth_of_discharge": dod,
        "system_voltage_V": sys_v,
        "actual_required_Ah": actual_ah,
        "claimed_battery_Ah": claimed,
        "diff_Ah": diff,
        "formula": "Ah = (daily_kWh × days × 1000) / (V × DoD)",
    }
    if diff <= threshold:
        return confirm(name,
                       f"required Ah = ({daily_kwh}·{days}·1000)/({sys_v}·{dod}) "
                       f"= {actual_ah:.1f} Ah (matches claim {claimed})",
                       data)
    return mismatch(name,
                    f"required Ah = {actual_ah:.1f}, claimed {claimed} "
                    f"(diff {diff:.1f} Ah)",
                    data)


# ── 3. Solar daily yield ───────────────────────────────────────────


def verify_solar_daily_yield(spec: Dict[str, Any]) -> VerifierResult:
    """daily_kWh = panel_W × peak_sun_hours × η / 1000."""
    name = "energy.solar_daily_yield"
    panel = _num(spec.get("panel_W"))
    psh = _num(spec.get("peak_sun_hours"))
    eta = _num(spec.get("system_efficiency"))
    claimed = _num(spec.get("claimed_daily_kwh"))
    if any(x is None for x in (panel, psh, eta, claimed)):
        return na(name)
    if panel <= 0 or psh < 0:
        return error(name,
                     f"panel_W must be positive and peak_sun_hours non-negative; "
                     f"got panel={panel}, psh={psh}")
    if not (0 < eta <= 1.0):
        return error(name,
                     f"system_efficiency must be in (0, 1.0]; got {eta}")
    actual = (panel * psh * eta) / 1000.0
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-3
    threshold = max(1e-3, rel_tol * actual)
    diff = abs(actual - claimed)
    data = {
        "panel_W": panel,
        "peak_sun_hours": psh,
        "system_efficiency": eta,
        "actual_kwh_day": actual,
        "claimed_daily_kwh": claimed,
        "diff": diff,
        "formula": "kWh = (panel_W · peak_sun_hours · η) / 1000",
    }
    if diff <= threshold:
        return confirm(name,
                       f"daily yield = ({panel}·{psh}·{eta})/1000 = "
                       f"{actual:.3f} kWh (matches claim {claimed})",
                       data)
    return mismatch(name,
                    f"daily yield = {actual:.3f} kWh, claimed {claimed} "
                    f"(diff {diff:.3f})",
                    data)


# ── 4. Wire voltage drop ───────────────────────────────────────────


def verify_wire_voltage_drop(spec: Dict[str, Any]) -> VerifierResult:
    """DC voltage drop: Vdrop = 2 × I × R_per_m × length."""
    name = "energy.wire_voltage_drop"
    r_per_m = _num(spec.get("wire_resistance_ohm_per_m"))
    length = _num(spec.get("distance_m"))
    current = _num(spec.get("current_A"))
    if any(x is None for x in (r_per_m, length, current)):
        return na(name)
    if r_per_m < 0 or length < 0 or current < 0:
        return error(name, "all values must be non-negative")
    # Round-trip: factor of 2 for DC out-and-back through the wire pair.
    actual_drop = 2.0 * current * r_per_m * length
    sys_v = _num(spec.get("system_V_for_drop"))
    actual_pct = (actual_drop / sys_v * 100.0) if sys_v else None

    claimed_drop = _num(spec.get("claimed_drop_V"))
    claimed_pct = _num(spec.get("claimed_drop_pct"))
    if claimed_drop is None and claimed_pct is None:
        return na(name, "need claimed_drop_V or claimed_drop_pct")
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-2
    data = {
        "wire_resistance_ohm_per_m": r_per_m,
        "distance_m": length,
        "current_A": current,
        "actual_drop_V": actual_drop,
        "actual_drop_pct": actual_pct,
        "system_V_for_drop": sys_v,
        "formula": "Vdrop = 2 · I · R_per_m · length (DC round-trip)",
    }
    if claimed_drop is not None:
        diff = abs(actual_drop - claimed_drop)
        threshold = max(1e-3, rel_tol * abs(actual_drop))
        data["claimed_drop_V"] = claimed_drop
        data["diff_V"] = diff
        if diff > threshold:
            return mismatch(name,
                            f"Vdrop = {actual_drop:.4f} V, claimed {claimed_drop} "
                            f"(diff {diff:.4f})",
                            data)
    if claimed_pct is not None and actual_pct is not None:
        diff = abs(actual_pct - claimed_pct)
        threshold = max(0.05, rel_tol * abs(actual_pct))
        data["claimed_drop_pct"] = claimed_pct
        data["diff_pct"] = diff
        if diff > threshold:
            return mismatch(name,
                            f"Vdrop% = {actual_pct:.2f}%, claimed {claimed_pct}% "
                            f"(diff {diff:.2f}%)",
                            data)
    return confirm(name,
                   f"Vdrop = {actual_drop:.4f} V"
                   + (f" ({actual_pct:.2f}% of {sys_v} V)" if actual_pct else "")
                   + " — matches claim",
                   data)


# ── 5. kWh ↔ Wh consistency ────────────────────────────────────────


def verify_kwh_wh_consistency(spec: Dict[str, Any]) -> VerifierResult:
    """1 kWh = 1000 Wh. Trivial check that catches paste errors."""
    name = "energy.kwh_wh_consistency"
    kwh = _num(spec.get("kwh"))
    wh = _num(spec.get("claimed_wh"))
    if kwh is None or wh is None:
        return na(name)
    actual_wh = kwh * 1000.0
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-6
    threshold = max(1e-3, rel_tol * abs(actual_wh))
    diff = abs(actual_wh - wh)
    data = {"kwh": kwh, "actual_wh": actual_wh, "claimed_wh": wh,
            "diff": diff, "formula": "Wh = kWh × 1000"}
    if diff <= threshold:
        return confirm(name,
                       f"{kwh} kWh = {actual_wh:.0f} Wh (matches claim {wh})",
                       data)
    return mismatch(name,
                    f"{kwh} kWh × 1000 = {actual_wh:.0f} Wh, claimed {wh} "
                    f"(diff {diff:.4g})",
                    data)


# ── 6. Efficiency ──────────────────────────────────────────────────


def verify_efficiency(spec: Dict[str, Any]) -> VerifierResult:
    """η = output / input. Must equal claim and be ≤ 1.0 (no perpetual
    motion), unless `is_heat_pump=True` (heat pumps have COP > 1)."""
    name = "energy.efficiency"
    inp = _num(spec.get("input_W"))
    out = _num(spec.get("output_W"))
    claimed = _num(spec.get("claimed_efficiency"))
    if any(x is None for x in (inp, out, claimed)):
        return na(name)
    if inp <= 0:
        return error(name, f"input_W must be positive; got {inp}")
    if out < 0:
        return error(name, f"output_W must be non-negative; got {out}")
    actual = out / inp
    is_hp = bool(spec.get("is_heat_pump"))
    if not is_hp and actual > 1.0 + 1e-9:
        return error(name,
                     f"efficiency = {out}/{inp} = {actual:.4f} > 1.0 "
                     "(perpetual motion violation; if this is a heat pump, "
                     "set is_heat_pump=true)")
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-3
    threshold = max(1e-4, rel_tol * abs(actual))
    diff = abs(actual - claimed)
    label = "COP" if is_hp else "efficiency η"
    data = {"input_W": inp, "output_W": out,
            "actual_efficiency": actual,
            "claimed_efficiency": claimed,
            "is_heat_pump": is_hp,
            "diff": diff,
            "formula": "η = output / input"}
    if diff <= threshold:
        return confirm(name,
                       f"{label} = {out}/{inp} = {actual:.4f} "
                       f"(matches claim {claimed})",
                       data)
    return mismatch(name,
                    f"{label} = {actual:.4f}, claimed {claimed} "
                    f"(diff {diff:.4f})",
                    data)


# ── 7. Runtime ─────────────────────────────────────────────────────


def verify_runtime(spec: Dict[str, Any]) -> VerifierResult:
    """runtime_hours = battery_Wh / load_W."""
    name = "energy.runtime"
    bat = _num(spec.get("battery_wh"))
    load = _num(spec.get("load_W"))
    claimed = _num(spec.get("claimed_runtime_hours"))
    if any(x is None for x in (bat, load, claimed)):
        return na(name)
    if bat < 0:
        return error(name, f"battery_wh must be non-negative; got {bat}")
    if load <= 0:
        return error(name, f"load_W must be positive; got {load}")
    actual = bat / load
    rel_tol = _num(spec.get("tolerance_relative")) or 1e-3
    threshold = max(1e-3, rel_tol * actual)
    diff = abs(actual - claimed)
    data = {"battery_wh": bat, "load_W": load,
            "actual_runtime_hours": actual,
            "claimed_runtime_hours": claimed,
            "diff_hours": diff,
            "formula": "runtime = battery_Wh / load_W"}
    if diff <= threshold:
        return confirm(name,
                       f"runtime = {bat}/{load} = {actual:.2f} h "
                       f"(matches claim {claimed})",
                       data)
    return mismatch(name,
                    f"runtime = {actual:.2f} h, claimed {claimed} "
                    f"(diff {diff:.2f} h)",
                    data)


# ── 8. Peak load vs inverter ──────────────────────────────────────


def verify_peak_load_vs_inverter(spec: Dict[str, Any]) -> VerifierResult:
    """Peak instantaneous load ≤ inverter continuous rating.
    A common off-grid sizing failure (system meets daily kWh but
    trips on inrush)."""
    name = "energy.peak_load_vs_inverter"
    peak = _num(spec.get("peak_load_W"))
    inv = _num(spec.get("inverter_continuous_W"))
    if peak is None or inv is None:
        return na(name)
    if peak < 0 or inv <= 0:
        return error(name, "peak_load_W must be ≥0 and inverter_W must be >0")
    margin = inv - peak
    margin_pct = (margin / inv) * 100.0
    data = {"peak_load_W": peak, "inverter_continuous_W": inv,
            "margin_W": margin, "margin_pct": margin_pct,
            "formula": "peak_load_W ≤ inverter_continuous_W"}
    if peak <= inv:
        return confirm(name,
                       f"peak load {peak} W ≤ inverter {inv} W "
                       f"(margin {margin:.0f} W, {margin_pct:.1f}%)",
                       data)
    return mismatch(name,
                    f"peak load {peak} W exceeds inverter {inv} W "
                    f"(over by {-margin:.0f} W)",
                    data)


# ── Entry point ────────────────────────────────────────────────────


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("ENERGY_VERIFY") or {}

    # Each check fires when its full input set is present. Missing
    # artifacts → NOT_APPLICABLE silently (the verifier doesn't
    # complain about absence; verification is opt-in per check).
    if all(ev.get(k) is not None
           for k in ("generation_kwh_day", "consumption_kwh_day",
                     "claimed_balance_kwh_day")):
        results.append(verify_power_balance(ev))
    if all(ev.get(k) is not None
           for k in ("daily_load_kwh", "days_autonomy",
                     "depth_of_discharge", "system_voltage_V",
                     "claimed_battery_Ah")):
        results.append(verify_battery_sizing(ev))
    if all(ev.get(k) is not None
           for k in ("panel_W", "peak_sun_hours",
                     "system_efficiency", "claimed_daily_kwh")):
        results.append(verify_solar_daily_yield(ev))
    if all(ev.get(k) is not None
           for k in ("wire_resistance_ohm_per_m", "distance_m",
                     "current_A")):
        if "claimed_drop_V" in ev or "claimed_drop_pct" in ev:
            results.append(verify_wire_voltage_drop(ev))
    if "kwh" in ev and "claimed_wh" in ev:
        results.append(verify_kwh_wh_consistency(ev))
    if all(k in ev for k in ("input_W", "output_W", "claimed_efficiency")):
        results.append(verify_efficiency(ev))
    if all(k in ev for k in ("battery_wh", "load_W", "claimed_runtime_hours")):
        results.append(verify_runtime(ev))
    if "peak_load_W" in ev and "inverter_continuous_W" in ev:
        results.append(verify_peak_load_vs_inverter(ev))

    if not results:
        results.append(na("energy", "no ENERGY_VERIFY artifacts present"))
    return results
