"""Tests for hydrology, photography, sports_analytics verifiers."""
from __future__ import annotations

from concordance_engine.verifiers import (
    hydrology as hyd,
    photography as photo,
    sports_analytics as sa,
)


# ── Hydrology: Manning velocity ────────────────────────────────────────

def test_manning_concrete_channel():
    # n=0.013, R=1m, S=0.001 → V ≈ 2.43 m/s
    r = hyd.verify_manning_velocity({
        "manning_n": 0.013, "hydraulic_radius_m": 1.0, "slope": 0.001,
        "claimed_velocity_m_s": 2.43,
    })
    assert r.status == "CONFIRMED"


def test_manning_zero_slope_zero_velocity():
    r = hyd.verify_manning_velocity({
        "manning_n": 0.013, "hydraulic_radius_m": 1.0, "slope": 0.0,
        "claimed_velocity_m_s": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_manning_wrong_claim_mismatches():
    r = hyd.verify_manning_velocity({
        "manning_n": 0.013, "hydraulic_radius_m": 1.0, "slope": 0.001,
        "claimed_velocity_m_s": 5.0,
    })
    assert r.status == "MISMATCH"


def test_manning_negative_n_errors():
    r = hyd.verify_manning_velocity({
        "manning_n": -0.013, "hydraulic_radius_m": 1.0, "slope": 0.001,
        "claimed_velocity_m_s": 2.43,
    })
    assert r.status == "ERROR"


# ── Hydrology: Darcy ───────────────────────────────────────────────────

def test_darcy_basic():
    # K=1e-4 m/s · i=0.01 → q = 1e-6 m/s
    r = hyd.verify_darcy_velocity({
        "darcy_K_m_s": 1.0e-4, "hydraulic_gradient": 0.01,
        "claimed_darcy_velocity_m_s": 1.0e-6,
    })
    assert r.status == "CONFIRMED"


def test_darcy_zero_gradient_zero_flux():
    r = hyd.verify_darcy_velocity({
        "darcy_K_m_s": 1.0e-4, "hydraulic_gradient": 0.0,
        "claimed_darcy_velocity_m_s": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_darcy_wrong_claim_mismatches():
    r = hyd.verify_darcy_velocity({
        "darcy_K_m_s": 1.0e-4, "hydraulic_gradient": 0.01,
        "claimed_darcy_velocity_m_s": 1.0e-3,
    })
    assert r.status == "MISMATCH"


# ── Hydrology: rational runoff ─────────────────────────────────────────

def test_rational_runoff_basic():
    # Q = 0.7 · 50 · 100 = 3500
    r = hyd.verify_rational_runoff({
        "runoff_coefficient": 0.7, "rainfall_intensity": 50.0,
        "drainage_area": 100.0, "claimed_runoff": 3500.0,
    })
    assert r.status == "CONFIRMED"


def test_rational_runoff_wrong_claim_mismatches():
    r = hyd.verify_rational_runoff({
        "runoff_coefficient": 0.7, "rainfall_intensity": 50.0,
        "drainage_area": 100.0, "claimed_runoff": 100.0,
    })
    assert r.status == "MISMATCH"


def test_rational_runoff_invalid_coefficient_errors():
    r = hyd.verify_rational_runoff({
        "runoff_coefficient": 1.5, "rainfall_intensity": 50.0,
        "drainage_area": 100.0, "claimed_runoff": 7500.0,
    })
    assert r.status == "ERROR"


# ── Hydrology: Bernoulli ───────────────────────────────────────────────

def test_bernoulli_total_head():
    # z=10, p=101325, v=2, ρ=1000 → h ≈ 20.54 m
    r = hyd.verify_bernoulli_head({
        "elevation_m": 10.0, "pressure_pa": 101325.0,
        "velocity_m_s": 2.0, "fluid_density_kg_m3": 1000.0,
        "claimed_total_head_m": 20.534,
    })
    assert r.status == "CONFIRMED"


def test_bernoulli_static_zero_velocity():
    # v=0 → kinetic head = 0
    r = hyd.verify_bernoulli_head({
        "elevation_m": 0.0, "pressure_pa": 0.0,
        "velocity_m_s": 0.0, "fluid_density_kg_m3": 1000.0,
        "claimed_total_head_m": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_bernoulli_wrong_claim_mismatches():
    r = hyd.verify_bernoulli_head({
        "elevation_m": 10.0, "pressure_pa": 101325.0,
        "velocity_m_s": 2.0, "fluid_density_kg_m3": 1000.0,
        "claimed_total_head_m": 5.0,
    })
    assert r.status == "MISMATCH"


# ── Photography: exposure value ────────────────────────────────────────

def test_ev_f8_one_over_250():
    # log2(64·250) ≈ 13.97
    r = photo.verify_exposure_value({
        "f_number": 8.0, "shutter_seconds": 1.0/250.0,
        "claimed_exposure_value": 13.97,
    })
    assert r.status == "CONFIRMED"


def test_ev_f1_one_second_zero():
    # log2(1 / 1) = 0
    r = photo.verify_exposure_value({
        "f_number": 1.0, "shutter_seconds": 1.0,
        "claimed_exposure_value": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_ev_wrong_claim_mismatches():
    r = photo.verify_exposure_value({
        "f_number": 8.0, "shutter_seconds": 1.0/250.0,
        "claimed_exposure_value": 5.0,
    })
    assert r.status == "MISMATCH"


# ── Photography: reciprocity ───────────────────────────────────────────

def test_reciprocity_equivalent_one_stop():
    # f/8 @ 1/250 ≡ f/11 @ 1/125 (one stop down aperture, one stop up shutter)
    r = photo.verify_reciprocity_equivalent({
        "settings_a": [8.0, 1.0/250.0],
        "settings_b": [11.0, 1.0/125.0],
        "claimed_equivalent": True,
    })
    assert r.status == "CONFIRMED"


def test_reciprocity_not_equivalent():
    # f/8 @ 1/250 vs f/8 @ 1/60 — clearly different exposures
    r = photo.verify_reciprocity_equivalent({
        "settings_a": [8.0, 1.0/250.0],
        "settings_b": [8.0, 1.0/60.0],
        "claimed_equivalent": False,
    })
    assert r.status == "CONFIRMED"


def test_reciprocity_wrong_claim_mismatches():
    r = photo.verify_reciprocity_equivalent({
        "settings_a": [8.0, 1.0/250.0],
        "settings_b": [8.0, 1.0/60.0],
        "claimed_equivalent": True,
    })
    assert r.status == "MISMATCH"


# ── Photography: angle of view ─────────────────────────────────────────

def test_aov_50mm_full_frame():
    # 50mm + 36mm sensor width → ≈ 39.6° (horizontal AOV)
    r = photo.verify_angle_of_view({
        "focal_length_mm": 50.0, "sensor_dimension_mm": 36.0,
        "claimed_angle_of_view_deg": 39.6,
    })
    assert r.status == "CONFIRMED"


def test_aov_24mm_wide():
    # 24mm + 36mm → ≈ 73.7°
    r = photo.verify_angle_of_view({
        "focal_length_mm": 24.0, "sensor_dimension_mm": 36.0,
        "claimed_angle_of_view_deg": 73.7,
    })
    assert r.status == "CONFIRMED"


def test_aov_wrong_claim_mismatches():
    r = photo.verify_angle_of_view({
        "focal_length_mm": 50.0, "sensor_dimension_mm": 36.0,
        "claimed_angle_of_view_deg": 90.0,
    })
    assert r.status == "MISMATCH"


# ── Photography: hyperfocal distance ───────────────────────────────────

def test_hyperfocal_50mm_f8():
    # f²/(N·c) + f = 2500/(8·0.03) + 50 = 10416.67 + 50 = 10466.67mm = 10.47m
    r = photo.verify_hyperfocal_distance({
        "focal_length_mm_for_h": 50.0, "f_number_for_h": 8.0,
        "circle_of_confusion_mm": 0.030,
        "claimed_hyperfocal_distance_m": 10.47,
    })
    assert r.status == "CONFIRMED"


def test_hyperfocal_wrong_claim_mismatches():
    r = photo.verify_hyperfocal_distance({
        "focal_length_mm_for_h": 50.0, "f_number_for_h": 8.0,
        "circle_of_confusion_mm": 0.030,
        "claimed_hyperfocal_distance_m": 1.0,
    })
    assert r.status == "MISMATCH"


# ── Sports analytics: Pythagorean expectation ──────────────────────────

def test_pythag_baseball_750_600():
    # 750²/(750² + 600²) ≈ 0.6098
    r = sa.verify_pythagorean_expectation({
        "runs_scored": 750, "runs_allowed": 600,
        "pythag_exponent": 2.0, "claimed_winning_pct": 0.6098,
    })
    assert r.status == "CONFIRMED"


def test_pythag_equal_rs_ra_is_500():
    # equal RS and RA → W% = 0.5
    r = sa.verify_pythagorean_expectation({
        "runs_scored": 700, "runs_allowed": 700,
        "claimed_winning_pct": 0.5,
    })
    assert r.status == "CONFIRMED"


def test_pythag_nfl_exponent():
    # Same teams under NFL exponent (2.37) — different result
    r = sa.verify_pythagorean_expectation({
        "runs_scored": 400, "runs_allowed": 300,
        "pythag_exponent": 2.37, "claimed_winning_pct": 0.6595,
    })
    assert r.status == "CONFIRMED"


def test_pythag_wrong_claim_mismatches():
    r = sa.verify_pythagorean_expectation({
        "runs_scored": 750, "runs_allowed": 600,
        "claimed_winning_pct": 0.5,
    })
    assert r.status == "MISMATCH"


# ── Sports analytics: Elo expected score ───────────────────────────────

def test_elo_expected_100_diff():
    # Higher rated by 100 → ≈ 0.6401
    r = sa.verify_elo_expected_score({
        "elo_a": 1600, "elo_b": 1500,
        "claimed_expected_score_a": 0.6401,
    })
    assert r.status == "CONFIRMED"


def test_elo_expected_equal_rating_half():
    r = sa.verify_elo_expected_score({
        "elo_a": 1500, "elo_b": 1500,
        "claimed_expected_score_a": 0.5,
    })
    assert r.status == "CONFIRMED"


def test_elo_expected_400_diff_about_91pct():
    # 400-point gap → ≈ 0.909
    r = sa.verify_elo_expected_score({
        "elo_a": 1900, "elo_b": 1500,
        "claimed_expected_score_a": 0.909,
    })
    assert r.status == "CONFIRMED"


def test_elo_expected_wrong_claim_mismatches():
    r = sa.verify_elo_expected_score({
        "elo_a": 1500, "elo_b": 1500,
        "claimed_expected_score_a": 0.8,
    })
    assert r.status == "MISMATCH"


# ── Sports analytics: Elo rating update ────────────────────────────────

def test_elo_update_underdog_wins():
    # Higher rated by 100; expected 0.6401; if higher player wins (S=1), gain = 32·0.36 ≈ 11.52
    r = sa.verify_elo_rating_update({
        "elo_a_pre": 1600, "elo_b_pre": 1500,
        "actual_score_a": 1.0, "elo_K": 32,
        "claimed_elo_a_post": 1611.52,
    })
    assert r.status == "CONFIRMED"


def test_elo_update_draw_at_equal_rating_no_change():
    r = sa.verify_elo_rating_update({
        "elo_a_pre": 1500, "elo_b_pre": 1500,
        "actual_score_a": 0.5, "elo_K": 32,
        "claimed_elo_a_post": 1500.0,
    })
    assert r.status == "CONFIRMED"


def test_elo_update_invalid_score_errors():
    r = sa.verify_elo_rating_update({
        "elo_a_pre": 1600, "elo_b_pre": 1500,
        "actual_score_a": 2.0, "elo_K": 32,  # invalid
        "claimed_elo_a_post": 1611.52,
    })
    assert r.status == "ERROR"


def test_elo_update_wrong_claim_mismatches():
    r = sa.verify_elo_rating_update({
        "elo_a_pre": 1500, "elo_b_pre": 1500,
        "actual_score_a": 0.5, "elo_K": 32,
        "claimed_elo_a_post": 1600.0,
    })
    assert r.status == "MISMATCH"


# ── Sports analytics: games behind ─────────────────────────────────────

def test_games_behind_simple_5():
    # leader 50-30, team 45-35 → GB = 5
    r = sa.verify_games_behind({
        "leader_wins": 50, "leader_losses": 30,
        "team_wins": 45, "team_losses": 35,
        "claimed_games_behind": 5.0,
    })
    assert r.status == "CONFIRMED"


def test_games_behind_zero_for_leader():
    r = sa.verify_games_behind({
        "leader_wins": 50, "leader_losses": 30,
        "team_wins": 50, "team_losses": 30,
        "claimed_games_behind": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_games_behind_half_game():
    # leader 51-30, team 50-30 → GB = ((51-50)+(30-30))/2 = 0.5
    r = sa.verify_games_behind({
        "leader_wins": 51, "leader_losses": 30,
        "team_wins": 50, "team_losses": 30,
        "claimed_games_behind": 0.5,
    })
    assert r.status == "CONFIRMED"


def test_games_behind_wrong_claim_mismatches():
    r = sa.verify_games_behind({
        "leader_wins": 50, "leader_losses": 30,
        "team_wins": 45, "team_losses": 35,
        "claimed_games_behind": 10.0,
    })
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_hyd_run_dispatches_all():
    packet = {
        "domain": "hydrology",
        "HYD_VERIFY": {
            "manning_n": 0.013, "hydraulic_radius_m": 1.0, "slope": 0.001,
            "claimed_velocity_m_s": 2.43,
            "darcy_K_m_s": 1.0e-4, "hydraulic_gradient": 0.01,
            "claimed_darcy_velocity_m_s": 1.0e-6,
            "runoff_coefficient": 0.7, "rainfall_intensity": 50.0,
            "drainage_area": 100.0, "claimed_runoff": 3500.0,
            "elevation_m": 10.0, "pressure_pa": 101325.0,
            "velocity_m_s": 2.0, "fluid_density_kg_m3": 1000.0,
            "claimed_total_head_m": 20.534,
        },
    }
    results = hyd.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_photo_run_dispatches_all():
    packet = {
        "domain": "photography",
        "PHOTO_VERIFY": {
            "f_number": 8.0, "shutter_seconds": 1.0/250.0,
            "claimed_exposure_value": 13.97,
            "settings_a": [8.0, 1.0/250.0], "settings_b": [11.0, 1.0/125.0],
            "claimed_equivalent": True,
            "focal_length_mm": 50.0, "sensor_dimension_mm": 36.0,
            "claimed_angle_of_view_deg": 39.6,
            "focal_length_mm_for_h": 50.0, "f_number_for_h": 8.0,
            "circle_of_confusion_mm": 0.030,
            "claimed_hyperfocal_distance_m": 10.47,
        },
    }
    results = photo.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_sports_run_dispatches_all():
    packet = {
        "domain": "sports_analytics",
        "SPORT_VERIFY": {
            "runs_scored": 750, "runs_allowed": 600,
            "claimed_winning_pct": 0.6098,
            "elo_a": 1600, "elo_b": 1500,
            "claimed_expected_score_a": 0.6401,
            "elo_a_pre": 1600, "elo_b_pre": 1500,
            "actual_score_a": 1.0, "elo_K": 32,
            "claimed_elo_a_post": 1611.52,
            "leader_wins": 50, "leader_losses": 30,
            "team_wins": 45, "team_losses": 35,
            "claimed_games_behind": 5.0,
        },
    }
    results = sa.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_hyd_no_artifacts_returns_na():
    results = hyd.run({"domain": "hydrology"})
    assert len(results) == 1 and results[0].status == "NOT_APPLICABLE"


def test_photo_no_artifacts_returns_na():
    results = photo.run({"domain": "photography"})
    assert len(results) == 1 and results[0].status == "NOT_APPLICABLE"


def test_sports_no_artifacts_returns_na():
    results = sa.run({"domain": "sports_analytics"})
    assert len(results) == 1 and results[0].status == "NOT_APPLICABLE"
