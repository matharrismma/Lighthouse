"""Tests for music_theory, number_theory, geography verifiers."""
from __future__ import annotations

from concordance_engine.verifiers import (
    music_theory as mus,
    number_theory as num,
    geography as geo,
)


# ── Music theory: interval semitones ───────────────────────────────────

def test_interval_c4_to_g4_seven_semitones():
    r = mus.verify_interval_semitones({
        "note_a": "C4", "note_b": "G4", "claimed_semitones": 7,
    })
    assert r.status == "CONFIRMED"


def test_interval_c4_to_c5_octave():
    r = mus.verify_interval_semitones({
        "note_a": "C4", "note_b": "C5", "claimed_semitones": 12,
    })
    assert r.status == "CONFIRMED"


def test_interval_descending_negative():
    # G4 → C4 = -7 semitones (signed)
    r = mus.verify_interval_semitones({
        "note_a": "G4", "note_b": "C4", "claimed_semitones": -7,
    })
    assert r.status == "CONFIRMED"


def test_interval_wrong_claim_mismatches():
    r = mus.verify_interval_semitones({
        "note_a": "C4", "note_b": "G4", "claimed_semitones": 5,
    })
    assert r.status == "MISMATCH"


def test_interval_unparseable_note_errors():
    r = mus.verify_interval_semitones({
        "note_a": "Q4", "note_b": "G4", "claimed_semitones": 7,
    })
    assert r.status == "ERROR"


# ── Music theory: frequency ratio ──────────────────────────────────────

def test_freq_ratio_octave_440_880():
    r = mus.verify_frequency_ratio({
        "freq_a": 440, "freq_b": 880, "claimed_interval": "octave",
    })
    assert r.status == "CONFIRMED"


def test_freq_ratio_fifth_3_2():
    # Just-intonation fifth: 1.5
    r = mus.verify_frequency_ratio({
        "freq_a": 440, "freq_b": 660, "claimed_interval": "fifth",
    })
    assert r.status == "CONFIRMED"


def test_freq_ratio_unison_same_freq():
    r = mus.verify_frequency_ratio({
        "freq_a": 440, "freq_b": 440, "claimed_interval": "unison",
    })
    assert r.status == "CONFIRMED"


def test_freq_ratio_mismatch():
    r = mus.verify_frequency_ratio({
        "freq_a": 440, "freq_b": 880, "claimed_interval": "fifth",
    })
    assert r.status == "MISMATCH"


# ── Music theory: equal temperament ────────────────────────────────────

def test_eq_temp_a4_440():
    r = mus.verify_equal_temperament_freq({
        "midi_note": 69, "claimed_frequency_hz": 440.0,
    })
    assert r.status == "CONFIRMED"


def test_eq_temp_c4_261_63():
    # MIDI 60 = C4 ≈ 261.6256 Hz
    r = mus.verify_equal_temperament_freq({
        "midi_note": 60, "claimed_frequency_hz": 261.63,
    })
    assert r.status == "CONFIRMED"


def test_eq_temp_a5_880():
    r = mus.verify_equal_temperament_freq({
        "midi_note": 81, "claimed_frequency_hz": 880.0,
    })
    assert r.status == "CONFIRMED"


def test_eq_temp_wrong_claim_mismatches():
    r = mus.verify_equal_temperament_freq({
        "midi_note": 69, "claimed_frequency_hz": 220.0,
    })
    assert r.status == "MISMATCH"


# ── Music theory: scale membership ─────────────────────────────────────

def test_scale_e_in_c_major():
    r = mus.verify_scale_membership({
        "key": "C", "mode": "major", "note": "E", "claimed_in_scale": True,
    })
    assert r.status == "CONFIRMED"


def test_scale_fsharp_not_in_c_major():
    r = mus.verify_scale_membership({
        "key": "C", "mode": "major", "note": "F#", "claimed_in_scale": False,
    })
    assert r.status == "CONFIRMED"


def test_scale_eb_in_c_minor():
    r = mus.verify_scale_membership({
        "key": "C", "mode": "minor", "note": "Eb", "claimed_in_scale": True,
    })
    assert r.status == "CONFIRMED"


def test_scale_wrong_claim_mismatches():
    r = mus.verify_scale_membership({
        "key": "C", "mode": "major", "note": "F#", "claimed_in_scale": True,
    })
    assert r.status == "MISMATCH"


# ── Number theory: primality ───────────────────────────────────────────

def test_primality_17_prime():
    r = num.verify_primality({"n_prime": 17, "claimed_prime": True})
    assert r.status == "CONFIRMED"


def test_primality_2_prime():
    r = num.verify_primality({"n_prime": 2, "claimed_prime": True})
    assert r.status == "CONFIRMED"


def test_primality_15_not_prime():
    r = num.verify_primality({"n_prime": 15, "claimed_prime": False})
    assert r.status == "CONFIRMED"


def test_primality_1_not_prime():
    r = num.verify_primality({"n_prime": 1, "claimed_prime": False})
    assert r.status == "CONFIRMED"


def test_primality_wrong_claim_mismatches():
    r = num.verify_primality({"n_prime": 9, "claimed_prime": True})
    assert r.status == "MISMATCH"


def test_primality_negative_errors():
    r = num.verify_primality({"n_prime": -3, "claimed_prime": True})
    assert r.status == "ERROR"


# ── Number theory: gcd ─────────────────────────────────────────────────

def test_gcd_12_18():
    r = num.verify_gcd({"gcd_a": 12, "gcd_b": 18, "claimed_gcd": 6})
    assert r.status == "CONFIRMED"


def test_gcd_coprime_one():
    r = num.verify_gcd({"gcd_a": 7, "gcd_b": 11, "claimed_gcd": 1})
    assert r.status == "CONFIRMED"


def test_gcd_with_zero():
    # gcd(0, n) = n
    r = num.verify_gcd({"gcd_a": 0, "gcd_b": 14, "claimed_gcd": 14})
    assert r.status == "CONFIRMED"


def test_gcd_wrong_claim_mismatches():
    r = num.verify_gcd({"gcd_a": 12, "gcd_b": 18, "claimed_gcd": 4})
    assert r.status == "MISMATCH"


# ── Number theory: factorial ───────────────────────────────────────────

def test_factorial_5_120():
    r = num.verify_factorial({"factorial_n": 5, "claimed_factorial": 120})
    assert r.status == "CONFIRMED"


def test_factorial_0_1():
    r = num.verify_factorial({"factorial_n": 0, "claimed_factorial": 1})
    assert r.status == "CONFIRMED"


def test_factorial_10_3628800():
    r = num.verify_factorial({"factorial_n": 10, "claimed_factorial": 3628800})
    assert r.status == "CONFIRMED"


def test_factorial_wrong_claim_mismatches():
    r = num.verify_factorial({"factorial_n": 5, "claimed_factorial": 100})
    assert r.status == "MISMATCH"


def test_factorial_negative_errors():
    r = num.verify_factorial({"factorial_n": -1, "claimed_factorial": 1})
    assert r.status == "ERROR"


# ── Number theory: modular inverse ─────────────────────────────────────

def test_mod_inverse_3_11():
    # 3·4 = 12 ≡ 1 (mod 11)
    r = num.verify_modular_inverse({"mod_a": 3, "mod_m": 11, "claimed_inverse": 4})
    assert r.status == "CONFIRMED"


def test_mod_inverse_7_26():
    # 7·15 = 105 = 4·26 + 1 ≡ 1 (mod 26)
    r = num.verify_modular_inverse({"mod_a": 7, "mod_m": 26, "claimed_inverse": 15})
    assert r.status == "CONFIRMED"


def test_mod_inverse_no_inverse_when_not_coprime():
    # gcd(2, 4) = 2 → no inverse exists
    r = num.verify_modular_inverse({"mod_a": 2, "mod_m": 4, "claimed_inverse": 1})
    assert r.status == "MISMATCH"


def test_mod_inverse_wrong_claim_mismatches():
    r = num.verify_modular_inverse({"mod_a": 3, "mod_m": 11, "claimed_inverse": 5})
    assert r.status == "MISMATCH"


# ── Geography: lat/lon validity ────────────────────────────────────────

def test_latlon_valid_in_range():
    r = geo.verify_lat_lon_validity({
        "lat": 35.0, "lon": -85.0, "claimed_coords_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_latlon_invalid_lat_too_high():
    r = geo.verify_lat_lon_validity({
        "lat": 91.0, "lon": 0.0, "claimed_coords_valid": False,
    })
    assert r.status == "CONFIRMED"


def test_latlon_invalid_lon_too_low():
    r = geo.verify_lat_lon_validity({
        "lat": 0.0, "lon": -181.0, "claimed_coords_valid": False,
    })
    assert r.status == "CONFIRMED"


def test_latlon_wrong_claim_mismatches():
    r = geo.verify_lat_lon_validity({
        "lat": 91.0, "lon": 0.0, "claimed_coords_valid": True,
    })
    assert r.status == "MISMATCH"


# ── Geography: haversine distance ──────────────────────────────────────

def test_haversine_equator_one_degree_lon():
    # 1° of longitude at equator ≈ 111.195 km on R=6371
    r = geo.verify_haversine_distance({
        "lat1": 0.0, "lon1": 0.0, "lat2": 0.0, "lon2": 1.0,
        "claimed_distance_km": 111.195,
    })
    assert r.status == "CONFIRMED"


def test_haversine_zero_distance_same_point():
    r = geo.verify_haversine_distance({
        "lat1": 35.0, "lon1": -85.0, "lat2": 35.0, "lon2": -85.0,
        "claimed_distance_km": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_haversine_nyc_to_la_approx():
    # NYC (40.7128, -74.0060) → LA (34.0522, -118.2437) ≈ 3935 km
    r = geo.verify_haversine_distance({
        "lat1": 40.7128, "lon1": -74.0060,
        "lat2": 34.0522, "lon2": -118.2437,
        "claimed_distance_km": 3935.0,
    })
    assert r.status == "CONFIRMED"


def test_haversine_wrong_claim_mismatches():
    r = geo.verify_haversine_distance({
        "lat1": 0.0, "lon1": 0.0, "lat2": 0.0, "lon2": 1.0,
        "claimed_distance_km": 500.0,
    })
    assert r.status == "MISMATCH"


# ── Geography: initial bearing ─────────────────────────────────────────

def test_bearing_due_north_zero():
    r = geo.verify_initial_bearing({
        "lat1": 0.0, "lon1": 0.0, "lat2": 10.0, "lon2": 0.0,
        "claimed_bearing_deg": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_bearing_due_east_ninety():
    r = geo.verify_initial_bearing({
        "lat1": 0.0, "lon1": 0.0, "lat2": 0.0, "lon2": 10.0,
        "claimed_bearing_deg": 90.0,
    })
    assert r.status == "CONFIRMED"


def test_bearing_wrong_claim_mismatches():
    r = geo.verify_initial_bearing({
        "lat1": 0.0, "lon1": 0.0, "lat2": 10.0, "lon2": 0.0,
        "claimed_bearing_deg": 90.0,
    })
    assert r.status == "MISMATCH"


# ── Geography: UTM zone ────────────────────────────────────────────────

def test_utm_zone_minus_85_is_16():
    r = geo.verify_utm_zone({
        "longitude_for_utm": -85.0, "claimed_utm_zone": 16,
    })
    assert r.status == "CONFIRMED"


def test_utm_zone_zero_is_31():
    r = geo.verify_utm_zone({
        "longitude_for_utm": 0.0, "claimed_utm_zone": 31,
    })
    assert r.status == "CONFIRMED"


def test_utm_zone_minus_180_is_1():
    r = geo.verify_utm_zone({
        "longitude_for_utm": -180.0, "claimed_utm_zone": 1,
    })
    assert r.status == "CONFIRMED"


def test_utm_zone_180_clamps_to_60():
    r = geo.verify_utm_zone({
        "longitude_for_utm": 180.0, "claimed_utm_zone": 60,
    })
    assert r.status == "CONFIRMED"


def test_utm_zone_wrong_claim_mismatches():
    r = geo.verify_utm_zone({
        "longitude_for_utm": -85.0, "claimed_utm_zone": 17,
    })
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_music_run_dispatches_all():
    packet = {
        "domain": "music_theory",
        "MUS_VERIFY": {
            "note_a": "C4", "note_b": "G4", "claimed_semitones": 7,
            "freq_a": 440, "freq_b": 880, "claimed_interval": "octave",
            "midi_note": 69, "claimed_frequency_hz": 440.0,
            "key": "C", "mode": "major", "note": "E", "claimed_in_scale": True,
        },
    }
    results = mus.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_number_run_dispatches_all():
    packet = {
        "domain": "number_theory",
        "NUM_VERIFY": {
            "n_prime": 17, "claimed_prime": True,
            "gcd_a": 12, "gcd_b": 18, "claimed_gcd": 6,
            "factorial_n": 5, "claimed_factorial": 120,
            "mod_a": 3, "mod_m": 11, "claimed_inverse": 4,
        },
    }
    results = num.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_geo_run_dispatches_all():
    packet = {
        "domain": "geography",
        "GEO_LOC_VERIFY": {
            "lat": 35.0, "lon": -85.0, "claimed_coords_valid": True,
            "lat1": 0.0, "lon1": 0.0, "lat2": 0.0, "lon2": 1.0,
            "claimed_distance_km": 111.195,
            "claimed_bearing_deg": 90.0,
            "longitude_for_utm": -85.0, "claimed_utm_zone": 16,
        },
    }
    results = geo.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_music_run_no_artifacts_returns_na():
    results = mus.run({"domain": "music_theory"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"


def test_number_run_no_artifacts_returns_na():
    results = num.run({"domain": "number_theory"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"


def test_geo_run_no_artifacts_returns_na():
    results = geo.run({"domain": "geography"})
    assert len(results) == 1
    assert results[0].status == "NOT_APPLICABLE"
