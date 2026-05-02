"""Tests for combinatorics, geometry, meteorology verifiers."""
from __future__ import annotations

from concordance_engine.verifiers import (
    combinatorics as comb,
    geometry as geom,
    meteorology as met,
)


# ── Combinatorics: permutations ────────────────────────────────────────

def test_perm_5_choose_2():
    # P(5,2) = 5·4 = 20
    r = comb.verify_permutations({"perm_n": 5, "perm_k": 2, "claimed_permutations": 20})
    assert r.status == "CONFIRMED"


def test_perm_n_choose_n_is_factorial():
    # P(5,5) = 5! = 120
    r = comb.verify_permutations({"perm_n": 5, "perm_k": 5, "claimed_permutations": 120})
    assert r.status == "CONFIRMED"


def test_perm_k_zero_is_one():
    r = comb.verify_permutations({"perm_n": 7, "perm_k": 0, "claimed_permutations": 1})
    assert r.status == "CONFIRMED"


def test_perm_wrong_claim_mismatches():
    r = comb.verify_permutations({"perm_n": 5, "perm_k": 2, "claimed_permutations": 25})
    assert r.status == "MISMATCH"


def test_perm_k_exceeds_n_errors():
    r = comb.verify_permutations({"perm_n": 3, "perm_k": 5, "claimed_permutations": 0})
    assert r.status == "ERROR"


# ── Combinatorics: combinations ────────────────────────────────────────

def test_comb_5_choose_2_is_10():
    r = comb.verify_combinations({"comb_n": 5, "comb_k": 2, "claimed_combinations": 10})
    assert r.status == "CONFIRMED"


def test_comb_pascal_C_4_2_6():
    r = comb.verify_combinations({"comb_n": 4, "comb_k": 2, "claimed_combinations": 6})
    assert r.status == "CONFIRMED"


def test_comb_n_choose_zero_is_one():
    r = comb.verify_combinations({"comb_n": 8, "comb_k": 0, "claimed_combinations": 1})
    assert r.status == "CONFIRMED"


def test_comb_wrong_claim_mismatches():
    r = comb.verify_combinations({"comb_n": 5, "comb_k": 2, "claimed_combinations": 12})
    assert r.status == "MISMATCH"


# ── Combinatorics: derangements ────────────────────────────────────────

def test_derangements_4_is_9():
    r = comb.verify_derangements({"derangement_n": 4, "claimed_derangements": 9})
    assert r.status == "CONFIRMED"


def test_derangements_5_is_44():
    r = comb.verify_derangements({"derangement_n": 5, "claimed_derangements": 44})
    assert r.status == "CONFIRMED"


def test_derangements_0_is_1():
    r = comb.verify_derangements({"derangement_n": 0, "claimed_derangements": 1})
    assert r.status == "CONFIRMED"


def test_derangements_1_is_0():
    r = comb.verify_derangements({"derangement_n": 1, "claimed_derangements": 0})
    assert r.status == "CONFIRMED"


def test_derangements_wrong_claim_mismatches():
    r = comb.verify_derangements({"derangement_n": 4, "claimed_derangements": 10})
    assert r.status == "MISMATCH"


# ── Combinatorics: multinomial ─────────────────────────────────────────

def test_multinomial_2_2_1_is_30():
    # 5! / (2!·2!·1!) = 30
    r = comb.verify_multinomial({"multinomial_groups": [2, 2, 1], "claimed_multinomial": 30})
    assert r.status == "CONFIRMED"


def test_multinomial_3_3_is_20():
    # 6! / (3!·3!) = 720/36 = 20
    r = comb.verify_multinomial({"multinomial_groups": [3, 3], "claimed_multinomial": 20})
    assert r.status == "CONFIRMED"


def test_multinomial_wrong_claim_mismatches():
    r = comb.verify_multinomial({"multinomial_groups": [2, 2, 1], "claimed_multinomial": 60})
    assert r.status == "MISMATCH"


# ── Geometry: triangle inequality ──────────────────────────────────────

def test_triangle_3_4_5_valid():
    r = geom.verify_triangle_inequality({
        "tri_a": 3, "tri_b": 4, "tri_c": 5, "claimed_valid_triangle": True,
    })
    assert r.status == "CONFIRMED"


def test_triangle_1_1_3_invalid():
    # 1+1 = 2 < 3, fails inequality
    r = geom.verify_triangle_inequality({
        "tri_a": 1, "tri_b": 1, "tri_c": 3, "claimed_valid_triangle": False,
    })
    assert r.status == "CONFIRMED"


def test_triangle_degenerate_2_3_5_invalid():
    # 2+3 = 5, NOT strictly greater
    r = geom.verify_triangle_inequality({
        "tri_a": 2, "tri_b": 3, "tri_c": 5, "claimed_valid_triangle": False,
    })
    assert r.status == "CONFIRMED"


def test_triangle_wrong_claim_mismatches():
    r = geom.verify_triangle_inequality({
        "tri_a": 1, "tri_b": 1, "tri_c": 3, "claimed_valid_triangle": True,
    })
    assert r.status == "MISMATCH"


# ── Geometry: Pythagorean ──────────────────────────────────────────────

def test_pythagorean_3_4_5():
    r = geom.verify_pythagorean({
        "pyth_a": 3, "pyth_b": 4, "pyth_c": 5, "claimed_right_triangle": True,
    })
    assert r.status == "CONFIRMED"


def test_pythagorean_5_12_13():
    r = geom.verify_pythagorean({
        "pyth_a": 5, "pyth_b": 12, "pyth_c": 13, "claimed_right_triangle": True,
    })
    assert r.status == "CONFIRMED"


def test_pythagorean_2_2_3_not_right():
    # 4+4=8 ≠ 9
    r = geom.verify_pythagorean({
        "pyth_a": 2, "pyth_b": 2, "pyth_c": 3, "claimed_right_triangle": False,
    })
    assert r.status == "CONFIRMED"


def test_pythagorean_wrong_claim_mismatches():
    r = geom.verify_pythagorean({
        "pyth_a": 2, "pyth_b": 2, "pyth_c": 3, "claimed_right_triangle": True,
    })
    assert r.status == "MISMATCH"


# ── Geometry: polygon angle sum ────────────────────────────────────────

def test_polygon_triangle_180():
    r = geom.verify_polygon_angle_sum({
        "polygon_n": 3, "claimed_interior_angle_sum_deg": 180,
    })
    assert r.status == "CONFIRMED"


def test_polygon_quad_360():
    r = geom.verify_polygon_angle_sum({
        "polygon_n": 4, "claimed_interior_angle_sum_deg": 360,
    })
    assert r.status == "CONFIRMED"


def test_polygon_hexagon_720():
    r = geom.verify_polygon_angle_sum({
        "polygon_n": 6, "claimed_interior_angle_sum_deg": 720,
    })
    assert r.status == "CONFIRMED"


def test_polygon_wrong_claim_mismatches():
    r = geom.verify_polygon_angle_sum({
        "polygon_n": 6, "claimed_interior_angle_sum_deg": 540,
    })
    assert r.status == "MISMATCH"


def test_polygon_n_lt_3_errors():
    r = geom.verify_polygon_angle_sum({
        "polygon_n": 2, "claimed_interior_angle_sum_deg": 0,
    })
    assert r.status == "ERROR"


# ── Geometry: circle properties ────────────────────────────────────────

def test_circle_area_r_5():
    # π·25 ≈ 78.5398
    r = geom.verify_circle_properties({
        "circle_radius": 5.0, "claimed_circle_area": 78.5398,
    })
    assert r.status == "CONFIRMED"


def test_circle_circumference_r_5():
    # 2π·5 ≈ 31.4159
    r = geom.verify_circle_properties({
        "circle_radius": 5.0, "claimed_circle_circumference": 31.4159,
    })
    assert r.status == "CONFIRMED"


def test_circle_both_at_once():
    r = geom.verify_circle_properties({
        "circle_radius": 5.0,
        "claimed_circle_area": 78.5398,
        "claimed_circle_circumference": 31.4159,
    })
    assert r.status == "CONFIRMED"


def test_circle_wrong_area_mismatches():
    r = geom.verify_circle_properties({
        "circle_radius": 5.0, "claimed_circle_area": 100.0,
    })
    assert r.status == "MISMATCH"


# ── Meteorology: dew point ─────────────────────────────────────────────

def test_dew_point_25c_60rh():
    # Magnus → ≈ 16.7°C
    r = met.verify_dew_point({
        "temperature_c": 25.0, "relative_humidity_pct": 60.0,
        "claimed_dew_point_c": 16.7,
    })
    assert r.status == "CONFIRMED"


def test_dew_point_100rh_equals_temp():
    # At RH=100, dew point = temperature
    r = met.verify_dew_point({
        "temperature_c": 20.0, "relative_humidity_pct": 100.0,
        "claimed_dew_point_c": 20.0,
    })
    assert r.status == "CONFIRMED"


def test_dew_point_wrong_claim_mismatches():
    r = met.verify_dew_point({
        "temperature_c": 25.0, "relative_humidity_pct": 60.0,
        "claimed_dew_point_c": 5.0,
    })
    assert r.status == "MISMATCH"


def test_dew_point_invalid_rh_errors():
    r = met.verify_dew_point({
        "temperature_c": 25.0, "relative_humidity_pct": 150.0,
        "claimed_dew_point_c": 0.0,
    })
    assert r.status == "ERROR"


# ── Meteorology: heat index ────────────────────────────────────────────

def test_heat_index_90f_70rh():
    # Rothfusz → ≈ 105.9
    r = met.verify_heat_index({
        "temperature_f": 90.0, "relative_humidity_pct_for_hi": 70.0,
        "claimed_heat_index_f": 105.9,
    })
    assert r.status == "CONFIRMED"


def test_heat_index_below_threshold_errors():
    # T < 80°F is out of valid range
    r = met.verify_heat_index({
        "temperature_f": 70.0, "relative_humidity_pct_for_hi": 70.0,
        "claimed_heat_index_f": 70.0,
    })
    assert r.status == "ERROR"


def test_heat_index_wrong_claim_mismatches():
    r = met.verify_heat_index({
        "temperature_f": 90.0, "relative_humidity_pct_for_hi": 70.0,
        "claimed_heat_index_f": 80.0,
    })
    assert r.status == "MISMATCH"


# ── Meteorology: wind chill ────────────────────────────────────────────

def test_wind_chill_20f_15mph():
    # NWS → ≈ 6.2°F
    r = met.verify_wind_chill({
        "temperature_f_for_wc": 20.0, "wind_speed_mph": 15.0,
        "claimed_wind_chill_f": 6.2,
    })
    assert r.status == "CONFIRMED"


def test_wind_chill_above_50f_errors():
    r = met.verify_wind_chill({
        "temperature_f_for_wc": 60.0, "wind_speed_mph": 15.0,
        "claimed_wind_chill_f": 60.0,
    })
    assert r.status == "ERROR"


def test_wind_chill_wrong_claim_mismatches():
    r = met.verify_wind_chill({
        "temperature_f_for_wc": 20.0, "wind_speed_mph": 15.0,
        "claimed_wind_chill_f": 30.0,
    })
    assert r.status == "MISMATCH"


# ── Meteorology: saturation vapor pressure ─────────────────────────────

def test_es_at_25c():
    # Magnus → ≈ 31.7 hPa
    r = met.verify_saturation_vapor_pressure({
        "temperature_c_for_es": 25.0,
        "claimed_saturation_vapor_pressure_hpa": 31.7,
    })
    assert r.status == "CONFIRMED"


def test_es_at_0c():
    # Magnus → ≈ 6.11 hPa at 0°C
    r = met.verify_saturation_vapor_pressure({
        "temperature_c_for_es": 0.0,
        "claimed_saturation_vapor_pressure_hpa": 6.112,
    })
    assert r.status == "CONFIRMED"


def test_es_wrong_claim_mismatches():
    r = met.verify_saturation_vapor_pressure({
        "temperature_c_for_es": 25.0,
        "claimed_saturation_vapor_pressure_hpa": 100.0,
    })
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_comb_run_dispatches_all():
    packet = {
        "domain": "combinatorics",
        "COMB_VERIFY": {
            "perm_n": 5, "perm_k": 2, "claimed_permutations": 20,
            "comb_n": 5, "comb_k": 2, "claimed_combinations": 10,
            "derangement_n": 4, "claimed_derangements": 9,
            "multinomial_groups": [2, 2, 1], "claimed_multinomial": 30,
        },
    }
    results = comb.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_geom_run_dispatches_all():
    packet = {
        "domain": "geometry",
        "GEOM_VERIFY": {
            "tri_a": 3, "tri_b": 4, "tri_c": 5, "claimed_valid_triangle": True,
            "pyth_a": 3, "pyth_b": 4, "pyth_c": 5, "claimed_right_triangle": True,
            "polygon_n": 4, "claimed_interior_angle_sum_deg": 360,
            "circle_radius": 5.0, "claimed_circle_area": 78.5398,
        },
    }
    results = geom.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_met_run_dispatches_all():
    packet = {
        "domain": "meteorology",
        "MET_VERIFY": {
            "temperature_c": 25.0, "relative_humidity_pct": 60.0,
            "claimed_dew_point_c": 16.7,
            "temperature_f": 90.0, "relative_humidity_pct_for_hi": 70.0,
            "claimed_heat_index_f": 105.9,
            "temperature_f_for_wc": 20.0, "wind_speed_mph": 15.0,
            "claimed_wind_chill_f": 6.2,
            "temperature_c_for_es": 25.0,
            "claimed_saturation_vapor_pressure_hpa": 31.7,
        },
    }
    results = met.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_comb_no_artifacts_returns_na():
    results = comb.run({"domain": "combinatorics"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"


def test_geom_no_artifacts_returns_na():
    results = geom.run({"domain": "geometry"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"


def test_met_no_artifacts_returns_na():
    results = met.run({"domain": "meteorology"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"
