"""Tests for acoustics + optics verifiers."""
from __future__ import annotations

from concordance_engine.verifiers import acoustics as acou, optics as opt


# ── Acoustics: wave relation ───────────────────────────────────────────

def test_wave_relation_a440_in_air():
    # c = 343 m/s, f = 440 Hz, λ = 343/440 = 0.7795 m
    r = acou.verify_wave_relation({
        "speed_of_wave": 343, "frequency_hz": 440, "wavelength_m": 0.7795,
    })
    assert r.status == "CONFIRMED"


def test_wave_relation_inconsistent():
    r = acou.verify_wave_relation({
        "speed_of_wave": 343, "frequency_hz": 440, "wavelength_m": 1.0,
    })
    assert r.status == "MISMATCH"


# ── Acoustics: dB ──────────────────────────────────────────────────────

def test_db_intensity_120_dbspl_threshold_of_pain():
    # 1 W/m² over reference 1e-12 W/m² → 10·log10(1e12) = 120 dB
    r = acou.verify_decibel_ratio({
        "value": 1.0, "reference": 1e-12, "claimed_db": 120,
        "db_kind": "intensity",
    })
    assert r.status == "CONFIRMED"


def test_db_pressure_doubling_is_6db():
    # Pressure doubled: 20·log10(2) ≈ 6.02 dB
    r = acou.verify_decibel_ratio({
        "value": 2.0, "reference": 1.0, "claimed_db": 6.02,
        "db_kind": "pressure",
    })
    assert r.status == "CONFIRMED"


def test_db_wrong_claim():
    r = acou.verify_decibel_ratio({
        "value": 10.0, "reference": 1.0, "claimed_db": 100,
        "db_kind": "intensity",
    })
    assert r.status == "MISMATCH"


# ── Acoustics: Doppler ─────────────────────────────────────────────────

def test_doppler_observer_moving_toward_stationary_source():
    # f_src=440, v_obs=10, v_src=0, c=343 → f_obs = 440 · (353/343) = 452.83
    r = acou.verify_doppler_shift({
        "f_source_hz": 440, "v_observer_mps": 10, "v_source_mps": 0,
        "speed_medium_mps": 343, "claimed_f_observed_hz": 452.83,
    })
    assert r.status == "CONFIRMED"


def test_doppler_no_motion_no_shift():
    r = acou.verify_doppler_shift({
        "f_source_hz": 440, "v_observer_mps": 0, "v_source_mps": 0,
        "speed_medium_mps": 343, "claimed_f_observed_hz": 440,
    })
    assert r.status == "CONFIRMED"


# ── Acoustics: harmonic ────────────────────────────────────────────────

def test_harmonic_4th_of_a110():
    r = acou.verify_harmonic_frequency({
        "fundamental_hz": 110, "harmonic_n": 4, "claimed_harmonic_hz": 440,
    })
    assert r.status == "CONFIRMED"


def test_harmonic_wrong_claim():
    r = acou.verify_harmonic_frequency({
        "fundamental_hz": 110, "harmonic_n": 4, "claimed_harmonic_hz": 200,
    })
    assert r.status == "MISMATCH"


# ── Optics: Snell ──────────────────────────────────────────────────────

def test_snell_air_to_glass():
    # n1=1.0 (air), n2=1.5 (glass), θ1=30° → sin θ2 = (1/1.5)·sin(30°) = 0.333 → θ2 ≈ 19.47°
    r = opt.verify_snell_law({
        "n1": 1.0, "n2": 1.5, "theta1_deg": 30,
        "claimed_theta2_deg": 19.47,
    })
    assert r.status == "CONFIRMED"


def test_snell_glass_to_air_total_internal_reflection():
    # n1=1.5, n2=1.0, θ1=60°. critical angle is asin(1/1.5) ≈ 41.8°. TIR.
    r = opt.verify_snell_law({
        "n1": 1.5, "n2": 1.0, "theta1_deg": 60,
        "claimed_theta2_deg": "TIR",
    })
    assert r.status == "CONFIRMED"


def test_snell_wrong_claim():
    r = opt.verify_snell_law({
        "n1": 1.0, "n2": 1.5, "theta1_deg": 30,
        "claimed_theta2_deg": 30,
    })
    assert r.status == "MISMATCH"


# ── Optics: thin lens ──────────────────────────────────────────────────

def test_thin_lens_object_at_2f_image_at_2f():
    # f=0.05, d_o=0.10, d_i=0.10: 1/f = 1/0.05 = 20; 1/0.10 + 1/0.10 = 20. Match.
    r = opt.verify_thin_lens({
        "focal_length_m": 0.05,
        "object_distance_m": 0.10, "image_distance_m": 0.10,
        "claimed_thin_lens_consistent": True,
    })
    assert r.status == "CONFIRMED"


def test_thin_lens_inconsistent():
    r = opt.verify_thin_lens({
        "focal_length_m": 0.05,
        "object_distance_m": 0.10, "image_distance_m": 0.20,
        "claimed_thin_lens_consistent": True,
    })
    assert r.status == "MISMATCH"


# ── Optics: magnification ──────────────────────────────────────────────

def test_magnification_unity_inverted():
    # d_o = d_i → M = -1 (real, same size, inverted)
    r = opt.verify_magnification({
        "object_distance_for_M": 0.10, "image_distance_for_M": 0.10,
        "claimed_magnification": -1.0,
    })
    assert r.status == "CONFIRMED"


def test_magnification_wrong():
    r = opt.verify_magnification({
        "object_distance_for_M": 0.10, "image_distance_for_M": 0.20,
        "claimed_magnification": 2.0,  # should be -2
    })
    assert r.status == "MISMATCH"


# ── Optics: Rayleigh diffraction ───────────────────────────────────────

def test_rayleigh_visible_through_10cm_aperture():
    # λ=550 nm, D=10 cm → θ_min = 1.22 · 5.5e-7 / 0.1 = 6.71e-6 rad
    r = opt.verify_rayleigh_diffraction({
        "wavelength_m": 5.5e-7, "aperture_m": 0.1,
        "claimed_diffraction_rad": 6.71e-6,
    })
    assert r.status == "CONFIRMED"


def test_rayleigh_wrong_claim():
    r = opt.verify_rayleigh_diffraction({
        "wavelength_m": 5.5e-7, "aperture_m": 0.1,
        "claimed_diffraction_rad": 1e-3,
    })
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_acoustics_run_dispatches_all():
    packet = {
        "domain": "acoustics",
        "ACOUS_VERIFY": {
            "speed_of_wave": 343, "frequency_hz": 440, "wavelength_m": 0.7795,
            "value": 1.0, "reference": 1e-12, "claimed_db": 120,
            "db_kind": "intensity",
            "f_source_hz": 440, "v_observer_mps": 0, "v_source_mps": 0,
            "speed_medium_mps": 343, "claimed_f_observed_hz": 440,
            "fundamental_hz": 110, "harmonic_n": 4, "claimed_harmonic_hz": 440,
        },
    }
    results = acou.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)


def test_optics_run_dispatches_all():
    packet = {
        "domain": "optics",
        "OPT_VERIFY": {
            "n1": 1.0, "n2": 1.5, "theta1_deg": 30, "claimed_theta2_deg": 19.47,
            "focal_length_m": 0.05,
            "object_distance_m": 0.10, "image_distance_m": 0.10,
            "claimed_thin_lens_consistent": True,
            "object_distance_for_M": 0.10, "image_distance_for_M": 0.10,
            "claimed_magnification": -1.0,
            "wavelength_m": 5.5e-7, "aperture_m": 0.1,
            "claimed_diffraction_rad": 6.71e-6,
        },
    }
    results = opt.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)
