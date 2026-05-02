"""Tests for the exercise_science verifier."""
from __future__ import annotations

from concordance_engine.verifiers import exercise_science as ex


# ── energy expenditure ─────────────────────────────────────────────────

def test_energy_expenditure_running_30min():
    # 9.8 MET × 70 kg × 0.5 h = 343 kcal
    r = ex.verify_energy_expenditure({
        "claimed_met": 9.8, "weight_kg": 70, "duration_hours": 0.5,
        "claimed_kcal": 343,
    })
    assert r.status == "CONFIRMED"


def test_energy_expenditure_walking_1h():
    # 3.3 MET × 80 kg × 1 h = 264
    r = ex.verify_energy_expenditure({
        "claimed_met": 3.3, "weight_kg": 80, "duration_hours": 1,
        "claimed_kcal": 264,
    })
    assert r.status == "CONFIRMED"


def test_energy_expenditure_wrong_claim():
    r = ex.verify_energy_expenditure({
        "claimed_met": 3.3, "weight_kg": 80, "duration_hours": 1,
        "claimed_kcal": 1000,
    })
    assert r.status == "MISMATCH"


def test_energy_expenditure_zero_weight_error():
    r = ex.verify_energy_expenditure({
        "claimed_met": 3.3, "weight_kg": 0, "duration_hours": 1,
        "claimed_kcal": 0,
    })
    assert r.status == "ERROR"


# ── max heart rate ─────────────────────────────────────────────────────

def test_max_hr_age_30():
    # Tanaka: 208 - 0.7*30 = 187
    r = ex.verify_max_heart_rate({"age_years": 30, "claimed_max_hr": 187})
    assert r.status == "CONFIRMED"


def test_max_hr_age_60():
    # Tanaka: 208 - 0.7*60 = 166
    r = ex.verify_max_heart_rate({"age_years": 60, "claimed_max_hr": 166})
    assert r.status == "CONFIRMED"


def test_max_hr_wrong_claim():
    r = ex.verify_max_heart_rate({"age_years": 30, "claimed_max_hr": 200})
    assert r.status == "MISMATCH"


def test_max_hr_age_out_of_range_error():
    r = ex.verify_max_heart_rate({"age_years": 999, "claimed_max_hr": 100})
    assert r.status == "ERROR"


# ── target heart rate zone ─────────────────────────────────────────────

def test_target_hr_zone_moderate():
    # age=30: HRmax = 187. resting=60. HRR = 127.
    # 50%: 60 + 0.5*127 = 123.5 ≈ 124
    # 70%: 60 + 0.7*127 = 148.9 ≈ 149
    r = ex.verify_target_heart_rate_zone({
        "age_years": 30, "resting_hr": 60,
        "intensity_low": 0.5, "intensity_high": 0.7,
        "claimed_zone_low_bpm": 124, "claimed_zone_high_bpm": 149,
    })
    assert r.status == "CONFIRMED"


def test_target_hr_zone_wrong_claim():
    r = ex.verify_target_heart_rate_zone({
        "age_years": 30, "resting_hr": 60,
        "intensity_low": 0.5, "intensity_high": 0.7,
        "claimed_zone_low_bpm": 100, "claimed_zone_high_bpm": 200,
    })
    assert r.status == "MISMATCH"


def test_target_hr_zone_intensity_out_of_range_error():
    r = ex.verify_target_heart_rate_zone({
        "age_years": 30, "resting_hr": 60,
        "intensity_low": 1.5, "intensity_high": 2.0,
        "claimed_zone_low_bpm": 0, "claimed_zone_high_bpm": 0,
    })
    assert r.status == "ERROR"


def test_target_hr_zone_inverted_intensity_error():
    r = ex.verify_target_heart_rate_zone({
        "age_years": 30, "resting_hr": 60,
        "intensity_low": 0.7, "intensity_high": 0.5,  # inverted
        "claimed_zone_low_bpm": 0, "claimed_zone_high_bpm": 0,
    })
    assert r.status == "ERROR"


# ── MET lookup ─────────────────────────────────────────────────────────

def test_met_lookup_running_6mph():
    r = ex.verify_met_lookup({"activity": "running_6mph", "claimed_met": 9.8})
    assert r.status == "CONFIRMED"


def test_met_lookup_walking_3mph():
    r = ex.verify_met_lookup({"activity": "walking_3mph", "claimed_met": 3.3})
    assert r.status == "CONFIRMED"


def test_met_lookup_wrong_value():
    r = ex.verify_met_lookup({"activity": "running_6mph", "claimed_met": 2.0})
    assert r.status == "MISMATCH"


def test_met_lookup_unknown_activity_is_na():
    r = ex.verify_met_lookup({"activity": "underwater_basket_weaving", "claimed_met": 5.0})
    assert r.status == "NOT_APPLICABLE"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = ex.run({"domain": "exercise_science"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "exercise_science",
        "EX_VERIFY": {
            "activity": "running_6mph", "claimed_met": 9.8,
            "weight_kg": 70, "duration_hours": 0.5, "claimed_kcal": 343,
            "age_years": 30, "claimed_max_hr": 187,
            "resting_hr": 60, "intensity_low": 0.5, "intensity_high": 0.7,
            "claimed_zone_low_bpm": 124, "claimed_zone_high_bpm": 149,
        },
    }
    results = ex.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 4, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_exercise_science_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "exercise_science",
        "EX_VERIFY": {"age_years": 30, "claimed_max_hr": 187},
    }
    results = run_for_domain("exercise_science", packet)
    ex_results = [r for r in results if r.name.startswith("exercise_science.")]
    assert len(ex_results) == 1
    assert ex_results[0].status == "CONFIRMED"
