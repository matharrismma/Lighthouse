"""Tests for the energy verifier — system-scale power, off-grid sizing,
conservation. Per kingdom-economy substrate: those refusing the mark
may need off-grid power; this verifier turns napkin arithmetic into
deterministic verification.

Each sub-check is tested for: a CONFIRMED case, a MISMATCH case, and
edge cases (zeros, negatives, missing fields). The verifier's run()
function is also tested for the partial-input pattern (missing
artifacts → NOT_APPLICABLE silently).
"""
from __future__ import annotations

import pytest

from concordance_engine.verifiers import energy
from concordance_engine.verifiers.base import VerifierResult


# ── Power balance ──────────────────────────────────────────────────


def test_power_balance_confirmed_surplus():
    r = energy.verify_power_balance({
        "generation_kwh_day": 12.0,
        "consumption_kwh_day": 8.5,
        "losses_kwh_day": 1.5,
        "claimed_balance_kwh_day": 2.0,
    })
    assert r.status == "CONFIRMED"
    assert r.data["actual_balance_kwh_day"] == 2.0


def test_power_balance_mismatch():
    r = energy.verify_power_balance({
        "generation_kwh_day": 10.0,
        "consumption_kwh_day": 8.0,
        "losses_kwh_day": 1.0,
        "claimed_balance_kwh_day": 5.0,  # actual is 1.0
    })
    assert r.status == "MISMATCH"


def test_power_balance_negative_inputs_error():
    r = energy.verify_power_balance({
        "generation_kwh_day": -1.0,
        "consumption_kwh_day": 8.5,
        "claimed_balance_kwh_day": 0,
    })
    assert r.status == "ERROR"


def test_power_balance_missing_returns_na():
    r = energy.verify_power_balance({"generation_kwh_day": 10.0})
    assert r.status == "NOT_APPLICABLE"


# ── Battery sizing ────────────────────────────────────────────────


def test_battery_sizing_confirmed():
    # 5 kWh/day × 2 days × 1000 / (24V × 0.5) = 833.33 Ah
    r = energy.verify_battery_sizing({
        "daily_load_kwh": 5.0,
        "days_autonomy": 2,
        "depth_of_discharge": 0.5,
        "system_voltage_V": 24,
        "claimed_battery_Ah": 833.33,
    })
    assert r.status == "CONFIRMED"
    assert abs(r.data["actual_required_Ah"] - 833.33) < 1.0


def test_battery_sizing_mismatch_undersized():
    r = energy.verify_battery_sizing({
        "daily_load_kwh": 5.0,
        "days_autonomy": 2,
        "depth_of_discharge": 0.5,
        "system_voltage_V": 24,
        "claimed_battery_Ah": 200,  # way too small
    })
    assert r.status == "MISMATCH"


def test_battery_sizing_invalid_dod_errors():
    """DoD must be in (0, 1.0]. Outside that range is a config error,
    not a calculation mismatch."""
    r = energy.verify_battery_sizing({
        "daily_load_kwh": 5.0,
        "days_autonomy": 2,
        "depth_of_discharge": 1.5,  # invalid: >100%
        "system_voltage_V": 24,
        "claimed_battery_Ah": 100,
    })
    assert r.status == "ERROR"


def test_battery_sizing_zero_voltage_errors():
    r = energy.verify_battery_sizing({
        "daily_load_kwh": 5.0,
        "days_autonomy": 2,
        "depth_of_discharge": 0.5,
        "system_voltage_V": 0,
        "claimed_battery_Ah": 100,
    })
    assert r.status == "ERROR"


# ── Solar daily yield ─────────────────────────────────────────────


def test_solar_yield_confirmed():
    # 400 W × 5 PSH × 0.85 / 1000 = 1.7 kWh
    r = energy.verify_solar_daily_yield({
        "panel_W": 400,
        "peak_sun_hours": 5.0,
        "system_efficiency": 0.85,
        "claimed_daily_kwh": 1.7,
    })
    assert r.status == "CONFIRMED"


def test_solar_yield_mismatch():
    r = energy.verify_solar_daily_yield({
        "panel_W": 400,
        "peak_sun_hours": 5.0,
        "system_efficiency": 0.85,
        "claimed_daily_kwh": 5.0,  # too high
    })
    assert r.status == "MISMATCH"


def test_solar_yield_zero_psh_handles_cleanly():
    """Zero peak sun hours = no production. Not an error, a fact."""
    r = energy.verify_solar_daily_yield({
        "panel_W": 400,
        "peak_sun_hours": 0.0,
        "system_efficiency": 0.85,
        "claimed_daily_kwh": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_solar_yield_efficiency_above_one_errors():
    r = energy.verify_solar_daily_yield({
        "panel_W": 400,
        "peak_sun_hours": 5.0,
        "system_efficiency": 1.5,  # impossible
        "claimed_daily_kwh": 3.0,
    })
    assert r.status == "ERROR"


# ── Wire voltage drop ─────────────────────────────────────────────


def test_wire_drop_confirmed_volts():
    # Vdrop = 2 × 30 A × 0.0033 Ω/m × 10 m = 1.98 V
    r = energy.verify_wire_voltage_drop({
        "wire_resistance_ohm_per_m": 0.0033,
        "distance_m": 10.0,
        "current_A": 30.0,
        "claimed_drop_V": 1.98,
    })
    assert r.status == "CONFIRMED"


def test_wire_drop_confirmed_pct():
    r = energy.verify_wire_voltage_drop({
        "wire_resistance_ohm_per_m": 0.0033,
        "distance_m": 10.0,
        "current_A": 30.0,
        "system_V_for_drop": 24.0,
        "claimed_drop_pct": 8.25,
    })
    assert r.status == "CONFIRMED"


def test_wire_drop_mismatch():
    r = energy.verify_wire_voltage_drop({
        "wire_resistance_ohm_per_m": 0.0033,
        "distance_m": 10.0,
        "current_A": 30.0,
        "claimed_drop_V": 0.5,  # actual is ~1.98
    })
    assert r.status == "MISMATCH"


def test_wire_drop_no_claim_returns_na():
    r = energy.verify_wire_voltage_drop({
        "wire_resistance_ohm_per_m": 0.0033,
        "distance_m": 10.0,
        "current_A": 30.0,
    })
    assert r.status == "NOT_APPLICABLE"


# ── kWh ↔ Wh consistency ──────────────────────────────────────────


def test_kwh_wh_confirmed():
    r = energy.verify_kwh_wh_consistency({"kwh": 5.0, "claimed_wh": 5000})
    assert r.status == "CONFIRMED"


def test_kwh_wh_mismatch():
    r = energy.verify_kwh_wh_consistency({"kwh": 5.0, "claimed_wh": 50})
    assert r.status == "MISMATCH"


# ── Efficiency ────────────────────────────────────────────────────


def test_efficiency_confirmed():
    r = energy.verify_efficiency({
        "input_W": 1000, "output_W": 850,
        "claimed_efficiency": 0.85,
    })
    assert r.status == "CONFIRMED"


def test_efficiency_perpetual_motion_blocked():
    """η > 1.0 violates first law — must error, not just mismatch."""
    r = energy.verify_efficiency({
        "input_W": 100, "output_W": 150,
        "claimed_efficiency": 1.5,
    })
    assert r.status == "ERROR"
    assert "perpetual motion" in r.detail.lower()


def test_efficiency_heat_pump_cop_above_one_allowed():
    """Heat pumps have COP > 1. With is_heat_pump=True, the >1 check
    is bypassed."""
    r = energy.verify_efficiency({
        "input_W": 100, "output_W": 350,  # COP 3.5 — typical for ASHP
        "claimed_efficiency": 3.5,
        "is_heat_pump": True,
    })
    assert r.status == "CONFIRMED"


def test_efficiency_zero_input_errors():
    r = energy.verify_efficiency({
        "input_W": 0, "output_W": 100, "claimed_efficiency": 1.0,
    })
    assert r.status == "ERROR"


# ── Runtime ───────────────────────────────────────────────────────


def test_runtime_confirmed():
    r = energy.verify_runtime({
        "battery_wh": 1200, "load_W": 100,
        "claimed_runtime_hours": 12,
    })
    assert r.status == "CONFIRMED"


def test_runtime_mismatch():
    r = energy.verify_runtime({
        "battery_wh": 1200, "load_W": 100,
        "claimed_runtime_hours": 24,
    })
    assert r.status == "MISMATCH"


def test_runtime_zero_load_errors():
    r = energy.verify_runtime({
        "battery_wh": 1200, "load_W": 0,
        "claimed_runtime_hours": 1,
    })
    assert r.status == "ERROR"


# ── Peak load vs inverter ─────────────────────────────────────────


def test_peak_load_within_inverter_confirmed():
    r = energy.verify_peak_load_vs_inverter({
        "peak_load_W": 2400, "inverter_continuous_W": 3000,
    })
    assert r.status == "CONFIRMED"
    assert r.data["margin_W"] == 600


def test_peak_load_exceeds_inverter_mismatch():
    r = energy.verify_peak_load_vs_inverter({
        "peak_load_W": 3500, "inverter_continuous_W": 3000,
    })
    assert r.status == "MISMATCH"
    assert r.data["margin_W"] == -500


# ── Run() entry point ────────────────────────────────────────────


def test_run_no_artifacts_returns_na():
    r = energy.run({"domain": "energy"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_only_applicable_checks_fire():
    """If only solar fields are present, only the solar check runs."""
    packet = {"ENERGY_VERIFY": {
        "panel_W": 400,
        "peak_sun_hours": 5.0,
        "system_efficiency": 0.85,
        "claimed_daily_kwh": 1.7,
    }}
    results = energy.run(packet)
    names = [r.name for r in results]
    assert "energy.solar_daily_yield" in names
    # No battery fields present, so no battery check.
    assert "energy.battery_sizing" not in names


def test_run_full_off_grid_system_all_pass():
    """A coherent off-grid spec where every claim is correct yields all CONFIRMED."""
    packet = {"ENERGY_VERIFY": {
        # solar: 400W × 5 PSH × 0.85 / 1000 = 1.7
        "panel_W": 400, "peak_sun_hours": 5.0, "system_efficiency": 0.85,
        "claimed_daily_kwh": 1.7,
        # battery: 5 kWh × 2d / (24V × 0.5) = 833.3 Ah
        "daily_load_kwh": 5.0, "days_autonomy": 2,
        "depth_of_discharge": 0.5, "system_voltage_V": 24,
        "claimed_battery_Ah": 833.3,
        # wire: 2 × 30 × 0.0033 × 10 = 1.98 V
        "wire_resistance_ohm_per_m": 0.0033, "distance_m": 10.0,
        "current_A": 30.0, "system_V_for_drop": 24,
        "claimed_drop_V": 1.98,
        # kWh: 5 × 1000 = 5000
        "kwh": 5.0, "claimed_wh": 5000,
        # eff: 850/1000 = 0.85
        "input_W": 1000, "output_W": 850, "claimed_efficiency": 0.85,
        # runtime: 1200/100 = 12
        "battery_wh": 1200, "load_W": 100, "claimed_runtime_hours": 12,
        # inverter: 2400 ≤ 3000
        "peak_load_W": 2400, "inverter_continuous_W": 3000,
        # balance: 12 - 8.5 - 1.5 = 2
        "generation_kwh_day": 12.0, "consumption_kwh_day": 8.5,
        "losses_kwh_day": 1.5, "claimed_balance_kwh_day": 2.0,
    }}
    results = energy.run(packet)
    # 8 checks should fire.
    assert len(results) == 8
    for r in results:
        assert r.status == "CONFIRMED", f"{r.name} expected CONFIRMED, got {r.status}: {r.detail}"


# ── MCP tool integration ──────────────────────────────────────────


def test_mcp_verify_energy_returns_checks_list():
    from concordance_engine.mcp_server import tools
    out = tools.verify_energy({
        "panel_W": 400, "peak_sun_hours": 5.0,
        "system_efficiency": 0.85, "claimed_daily_kwh": 1.7,
    })
    assert "checks" in out
    assert isinstance(out["checks"], list)
    assert len(out["checks"]) == 1
    assert out["checks"][0]["status"] == "CONFIRMED"


# ── Grid integration ─────────────────────────────────────────────


def test_energy_axis_in_grid():
    """The energy axis must be registered in grid.AXIS_DIMENSIONS so
    `find_closest` can locate precedents on the energy axis."""
    from concordance_engine import grid
    assert "energy" in grid.AXIS_DIMENSIONS
    dims = grid.AXIS_DIMENSIONS["energy"]
    # Energy sits on physical_substance and conservation_balance at
    # minimum. The first law and the substrate-of-power both demand it.
    assert "physical_substance" in dims
    assert "conservation_balance" in dims


def test_energy_registered_in_verifier_registry():
    """The verifier registry must route 'energy' (and aliases) to the
    energy module."""
    from concordance_engine.verifiers import VERIFIERS
    assert "energy" in VERIFIERS
    # Common-language aliases should also resolve.
    assert "power" in VERIFIERS
    assert "off_grid" in VERIFIERS
    assert VERIFIERS["energy"].endswith("verifiers.energy")


def test_run_for_domain_energy_routes_correctly():
    from concordance_engine.verifiers import run_for_domain
    results = run_for_domain("energy", {"ENERGY_VERIFY": {
        "kwh": 1.0, "claimed_wh": 1000,
    }})
    energy_checks = [r for r in results if r.name.startswith("energy.")]
    assert len(energy_checks) >= 1
    assert energy_checks[0].status == "CONFIRMED"
