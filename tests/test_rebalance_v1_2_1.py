"""Tests for the V1.2.1 rebalance subsystem additions:
chemistry (thermodynamic_feasibility, pH_classification),
physics (kinematic_motion, relativistic_speed_limit),
governance (decision_timing, rationale_alignment),
scripture (canon_membership, red_letter_priority).
"""
from __future__ import annotations

from concordance_engine.verifiers import (
    chemistry as chem,
    physics as phys,
    governance as gov,
    scripture as scr,
)


# ── chemistry.thermodynamic_feasibility ────────────────────────────────

def test_thermo_combustion_is_spontaneous():
    # Methane combustion: ΔH ≈ -890 kJ/mol, ΔS ≈ -242 J/(mol·K), at 298 K
    # ΔG = -890 - 298 * (-0.242) = -890 + 72 = -818 → spontaneous
    r = chem.verify_thermodynamic_feasibility({
        "delta_H_kJ_mol": -890,
        "delta_S_J_mol_K": -242,
        "temperature_K": 298,
        "claimed_spontaneous": True,
    })
    assert r.status == "CONFIRMED"


def test_thermo_endothermic_low_entropy_not_spontaneous():
    # ΔH = +50 kJ/mol, ΔS = -100 J/(mol·K), at 298 K
    # ΔG = 50 - 298*(-0.1) = 50 + 29.8 = +79.8 → not spontaneous
    r = chem.verify_thermodynamic_feasibility({
        "delta_H_kJ_mol": 50,
        "delta_S_J_mol_K": -100,
        "temperature_K": 298,
        "claimed_spontaneous": False,
    })
    assert r.status == "CONFIRMED"


def test_thermo_wrong_claim_caught():
    r = chem.verify_thermodynamic_feasibility({
        "delta_H_kJ_mol": -890,
        "delta_S_J_mol_K": -242,
        "temperature_K": 298,
        "claimed_spontaneous": False,  # wrong
    })
    assert r.status == "MISMATCH"


def test_thermo_zero_temperature_is_error():
    r = chem.verify_thermodynamic_feasibility({
        "delta_H_kJ_mol": 50,
        "delta_S_J_mol_K": 100,
        "temperature_K": 0,
        "claimed_spontaneous": False,
    })
    assert r.status == "ERROR"


# ── chemistry.pH_classification ────────────────────────────────────────

def test_ph_acid():
    r = chem.verify_ph_classification({"pH": 3.0, "claimed_classification": "acid"})
    assert r.status == "CONFIRMED"


def test_ph_acidic_synonym():
    r = chem.verify_ph_classification({"pH": 3.0, "claimed_classification": "acidic"})
    assert r.status == "CONFIRMED"


def test_ph_base_synonym_alkaline():
    r = chem.verify_ph_classification({"pH": 11.0, "claimed_classification": "alkaline"})
    assert r.status == "CONFIRMED"


def test_ph_neutral():
    r = chem.verify_ph_classification({"pH": 7.0, "claimed_classification": "neutral"})
    assert r.status == "CONFIRMED"


def test_ph_neutral_within_tolerance():
    r = chem.verify_ph_classification({"pH": 7.4, "claimed_classification": "neutral"})
    assert r.status == "CONFIRMED"


def test_ph_wrong_claim():
    r = chem.verify_ph_classification({"pH": 3.0, "claimed_classification": "base"})
    assert r.status == "MISMATCH"


def test_ph_out_of_range_mismatch():
    r = chem.verify_ph_classification({"pH": 15.0, "claimed_classification": "base"})
    assert r.status == "MISMATCH"


# ── physics.kinematic_motion ───────────────────────────────────────────

def test_kinematic_simple_constant_velocity():
    # v0=10, a=0, t=5: d = 10*5 = 50
    r = phys.verify_kinematic_motion({
        "v0": 10, "a": 0, "t": 5, "claimed_displacement": 50,
    })
    assert r.status == "CONFIRMED"


def test_kinematic_freefall():
    # v0=0, a=9.81, t=2: d = 0 + 0.5 * 9.81 * 4 = 19.62
    r = phys.verify_kinematic_motion({
        "v0": 0, "a": 9.81, "t": 2, "claimed_displacement": 19.62,
    })
    assert r.status == "CONFIRMED"


def test_kinematic_wrong_claim():
    r = phys.verify_kinematic_motion({
        "v0": 0, "a": 9.81, "t": 2, "claimed_displacement": 50,
    })
    assert r.status == "MISMATCH"


def test_kinematic_negative_time_is_mismatch():
    r = phys.verify_kinematic_motion({
        "v0": 0, "a": 9.81, "t": -1, "claimed_displacement": 0,
    })
    assert r.status == "MISMATCH"


# ── physics.relativistic_speed_limit ────────────────────────────────────

def test_relativistic_subluminal_passes():
    r = phys.verify_relativistic_speed_limit({"speed_m_per_s": 1.0e8})  # ~c/3
    assert r.status == "CONFIRMED"


def test_relativistic_superluminal_mismatch():
    r = phys.verify_relativistic_speed_limit({"speed_m_per_s": 4.0e8})
    assert r.status == "MISMATCH"


def test_relativistic_at_c_for_massive_is_mismatch():
    r = phys.verify_relativistic_speed_limit({
        "speed_m_per_s": 299_792_458.0, "massive": True,
    })
    assert r.status == "MISMATCH"


def test_relativistic_at_c_for_massless_is_confirmed():
    r = phys.verify_relativistic_speed_limit({
        "speed_m_per_s": 299_792_458.0, "massive": False,
    })
    assert r.status == "CONFIRMED"


def test_relativistic_negative_speed_is_error():
    r = phys.verify_relativistic_speed_limit({"speed_m_per_s": -1.0})
    assert r.status == "ERROR"


# ── governance.decision_timing ─────────────────────────────────────────

def test_governance_timing_adapter_satisfied():
    # adapter scope = 1h (3600s); elapsed 4000s >= 3600
    r = gov.verify_decision_timing({
        "scope": "adapter",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_004_000,
    })
    assert r.status == "CONFIRMED"


def test_governance_timing_adapter_too_soon():
    r = gov.verify_decision_timing({
        "scope": "adapter",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_001_000,  # 1000s < 3600
    })
    assert r.status == "MISMATCH"


def test_governance_timing_canon_7day_floor():
    r = gov.verify_decision_timing({
        "scope": "canon",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_604_000,  # +604_000s = 6.99 days, just under 7 days
    })
    assert r.status == "MISMATCH"


def test_governance_timing_acted_before_created():
    r = gov.verify_decision_timing({
        "scope": "adapter",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 999_000,
    })
    assert r.status == "MISMATCH"


def test_governance_timing_unknown_scope_error():
    r = gov.verify_decision_timing({
        "scope": "void",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_010_000,
    })
    assert r.status == "ERROR"


def test_governance_timing_wait_window_override_raises_floor():
    # adapter floor = 3600. Override = 7200. Elapsed = 5000 → not yet.
    r = gov.verify_decision_timing({
        "scope": "adapter",
        "wait_window_seconds": 7200,
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_005_000,
    })
    assert r.status == "MISMATCH"


# ── governance.rationale_alignment ─────────────────────────────────────

def test_rationale_alignment_overlap():
    r = gov.verify_rationale_alignment({
        "decision": "Approve municipal stormwater bond at $4.2M",
        "rationale": "The municipal stormwater plan is overdue; the bond cost is justified by avoided flood damage.",
    })
    assert r.status == "CONFIRMED"


def test_rationale_alignment_no_overlap():
    r = gov.verify_rationale_alignment({
        "decision": "Approve stormwater infrastructure investment",
        "rationale": "Pizza tastes good.",
    })
    assert r.status == "MISMATCH"


# ── scripture.canon_membership ─────────────────────────────────────────

def test_canon_membership_all_in():
    r = scr.verify_canon_membership(["John 3:16", "Romans 8:28", "Genesis 1:1"])
    assert r.status == "CONFIRMED"


def test_canon_membership_apocrypha_rejected():
    r = scr.verify_canon_membership(["Tobit 4:7", "John 3:16"])
    assert r.status == "MISMATCH"
    assert "Tobit" in str(r.data.get("outside", []))


def test_canon_membership_abbreviations():
    r = scr.verify_canon_membership(["Mt 5:3", "Rom 1:16", "Eph 2:8"])
    assert r.status == "CONFIRMED"


def test_canon_membership_empty():
    r = scr.verify_canon_membership([])
    assert r.status == "CONFIRMED"


# ── scripture.red_letter_priority ──────────────────────────────────────

def test_red_letter_gospel_refs_classified():
    r = scr.verify_red_letter_priority(["Matthew 5:3", "Romans 8:28"])
    assert r.status == "CONFIRMED"
    gospel = r.data.get("gospel_refs")
    assert "Matthew 5:3" in gospel
    assert "Romans 8:28" not in gospel


def test_red_letter_no_gospels():
    r = scr.verify_red_letter_priority(["Romans 8:28", "Hebrews 11:1"])
    assert r.status == "CONFIRMED"
    assert r.data.get("gospel_count") == 0


def test_red_letter_all_gospels():
    r = scr.verify_red_letter_priority(["Mt 5:3", "Mk 2:5", "Lk 6:31", "Jn 3:16"])
    assert r.status == "CONFIRMED"
    assert r.data.get("gospel_count") == 4


# ── End-to-end run() dispatch ──────────────────────────────────────────

def test_chemistry_run_dispatches_new_subsystems():
    packet = {
        "domain": "chemistry",
        "CHEM_VERIFY": {
            "delta_H_kJ_mol": -890,
            "delta_S_J_mol_K": -242,
            "temperature_K": 298,
            "claimed_spontaneous": True,
            "pH": 3.0,
            "claimed_classification": "acid",
        },
    }
    results = chem.run(packet)
    names = {r.name for r in results}
    assert "chemistry.thermodynamic_feasibility" in names
    assert "chemistry.pH_classification" in names


def test_physics_run_dispatches_new_subsystems():
    packet = {
        "domain": "physics",
        "PHYS_VERIFY": {
            "v0": 0, "a": 9.81, "t": 2, "claimed_displacement": 19.62,
            "speed_m_per_s": 1.0e8,
        },
    }
    results = phys.run(packet)
    names = {r.name for r in results}
    assert "physics.kinematic_motion" in names
    assert "physics.relativistic_speed_limit" in names


def test_governance_run_dispatches_rationale_and_timing():
    packet = {
        "domain": "governance",
        "scope": "adapter",
        "created_epoch": 1_000_000,
        "acted_at_epoch": 1_004_000,
        "DECISION_PACKET": {
            "decision": "Approve sidewalk paving project",
            "rationale": "The sidewalk replacement is overdue; project cost approved by board.",
            "witnesses": ["board_chair", "vice_chair", "secretary"],
        },
        "witness_count": 3,
    }
    results = gov.run(packet)
    names = {r.name for r in results}
    assert "governance.rationale_alignment" in names
    assert "governance.decision_timing" in names


def test_scripture_run_dispatches_canon_and_red_letter():
    packet = {
        "domain": "governance",
        "scripture_anchors": ["Matthew 6:19-21", "Proverbs 11:1"],
        "DECISION_PACKET": {
            "decision": "stewardship policy",
            "rationale": "guard against unjust gain and store treasure in heaven",
            "witnesses": ["a", "b"],
        },
        "witness_count": 2,
    }
    results = scr.run(packet)
    names = {r.name for r in results}
    assert "scripture.canon_membership" in names
    assert "scripture.red_letter_priority" in names
