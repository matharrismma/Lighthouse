"""Tests for the electrical engineering verifier."""
from __future__ import annotations

from concordance_engine.verifiers import electrical as elec


# ── Ohm's law ──────────────────────────────────────────────────────────

def test_ohms_law_basic():
    # 12V across 24Ω → 0.5A
    r = elec.verify_ohms_law({"voltage_V": 12, "current_A": 0.5, "resistance_ohm": 24})
    assert r.status == "CONFIRMED"


def test_ohms_law_wrong_claim():
    r = elec.verify_ohms_law({"voltage_V": 5, "current_A": 1, "resistance_ohm": 10})
    assert r.status == "MISMATCH"


def test_ohms_law_negative_R_error():
    r = elec.verify_ohms_law({"voltage_V": 5, "current_A": 1, "resistance_ohm": -10})
    assert r.status == "ERROR"


# ── power ──────────────────────────────────────────────────────────────

def test_power_VI_form():
    # P = 12 × 0.5 = 6
    r = elec.verify_power({
        "voltage_V": 12, "current_A": 0.5, "power_W_claim": 6,
    })
    assert r.status == "CONFIRMED"


def test_power_all_three_forms_match():
    # 12V, 0.5A, 24Ω: VI=6, I²R=6, V²/R=6
    r = elec.verify_power({
        "voltage_V": 12, "current_A": 0.5, "resistance_ohm": 24,
        "power_W_claim": 6,
    })
    assert r.status == "CONFIRMED"


def test_power_wrong_claim():
    r = elec.verify_power({
        "voltage_V": 12, "current_A": 0.5, "power_W_claim": 100,
    })
    assert r.status == "MISMATCH"


# ── Kirchhoff voltage law ──────────────────────────────────────────────

def test_kvl_loop_balanced_zero():
    # 9V battery, two 4.5V drops → 9 - 4.5 - 4.5 = 0
    r = elec.verify_kirchhoff_voltage_loop({
        "voltages_in_loop": [9, -4.5, -4.5], "claimed_loop_sum_V": 0,
    })
    assert r.status == "CONFIRMED"


def test_kvl_unbalanced_loop_caught():
    r = elec.verify_kirchhoff_voltage_loop({
        "voltages_in_loop": [9, -4.5, -4.5], "claimed_loop_sum_V": 10,
    })
    assert r.status == "MISMATCH"


def test_kvl_empty_list_error():
    r = elec.verify_kirchhoff_voltage_loop({
        "voltages_in_loop": [], "claimed_loop_sum_V": 0,
    })
    assert r.status == "ERROR"


# ── RC time constant ──────────────────────────────────────────────────

def test_rc_one_tau_about_63pct():
    # RC = 1ms; t = 1ms → v = 5(1 - 1/e) ≈ 3.16
    r = elec.verify_rc_time_constant({
        "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
        "elapsed_s": 1e-3, "supply_V": 5.0,
        "claimed_capacitor_voltage_V": 3.16,
    })
    assert r.status == "CONFIRMED"


def test_rc_at_t_zero_voltage_zero():
    r = elec.verify_rc_time_constant({
        "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
        "elapsed_s": 0, "supply_V": 5.0,
        "claimed_capacitor_voltage_V": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_rc_5tau_almost_full_charge():
    # 5τ ≈ 99.3% of supply
    r = elec.verify_rc_time_constant({
        "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
        "elapsed_s": 5e-3, "supply_V": 5.0,
        "claimed_capacitor_voltage_V": 4.966,
    })
    assert r.status == "CONFIRMED"


def test_rc_wrong_claim():
    r = elec.verify_rc_time_constant({
        "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
        "elapsed_s": 1e-3, "supply_V": 5.0,
        "claimed_capacitor_voltage_V": 5.0,  # full charge claimed too soon
    })
    assert r.status == "MISMATCH"


def test_rc_zero_resistance_error():
    r = elec.verify_rc_time_constant({
        "resistance_ohm_rc": 0, "capacitance_F": 1e-6,
        "elapsed_s": 1e-3, "supply_V": 5.0,
        "claimed_capacitor_voltage_V": 5.0,
    })
    assert r.status == "ERROR"


# ── run dispatch ───────────────────────────────────────────────────────

def test_run_no_artifacts_returns_na():
    r = elec.run({"domain": "electrical"})
    assert len(r) == 1 and r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all():
    packet = {
        "domain": "electrical",
        "ELEC_VERIFY": {
            "voltage_V": 12, "current_A": 0.5, "resistance_ohm": 24,
            "power_W_claim": 6,
            "voltages_in_loop": [9, -4.5, -4.5], "claimed_loop_sum_V": 0,
            "resistance_ohm_rc": 1000, "capacitance_F": 1e-6,
            "elapsed_s": 1e-3, "supply_V": 5.0,
            "claimed_capacitor_voltage_V": 3.16,
        },
    }
    results = elec.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)
