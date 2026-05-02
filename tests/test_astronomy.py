"""Tests for the astronomy verifier."""
from __future__ import annotations

from concordance_engine.verifiers import astronomy as astro


# ── Kepler's third law ─────────────────────────────────────────────────

def test_kepler_earth_consistent():
    # Earth: T = 1 yr, a = 1 AU. T²=1, a³=1. Consistent.
    r = astro.verify_kepler_third_law({
        "orbital_period_years": 1.0, "semi_major_axis_au": 1.0,
        "claimed_kepler_consistent": True,
    })
    assert r.status == "CONFIRMED"


def test_kepler_jupiter_consistent():
    # Jupiter: T ≈ 11.86 yr, a ≈ 5.2 AU. T²=140.6, a³=140.6. Consistent.
    r = astro.verify_kepler_third_law({
        "orbital_period_years": 11.86, "semi_major_axis_au": 5.2,
        "claimed_kepler_consistent": True,
    })
    assert r.status == "CONFIRMED"


def test_kepler_inconsistent_orbit_caught():
    r = astro.verify_kepler_third_law({
        "orbital_period_years": 1.0, "semi_major_axis_au": 5.0,  # wildly off
        "claimed_kepler_consistent": True,
    })
    assert r.status == "MISMATCH"


def test_kepler_inconsistent_correctly_claimed():
    r = astro.verify_kepler_third_law({
        "orbital_period_years": 1.0, "semi_major_axis_au": 5.0,
        "claimed_kepler_consistent": False,
    })
    assert r.status == "CONFIRMED"


def test_kepler_negative_period_error():
    r = astro.verify_kepler_third_law({
        "orbital_period_years": -1.0, "semi_major_axis_au": 1.0,
        "claimed_kepler_consistent": True,
    })
    assert r.status == "ERROR"


# ── gravitational force ────────────────────────────────────────────────

def test_gravity_earth_moon_force():
    # Earth-Moon: m1=5.972e24, m2=7.342e22, r=3.84e8
    # F = 6.674e-11 * 5.972e24 * 7.342e22 / (3.84e8)² ≈ 1.984e20 N
    r = astro.verify_gravitational_force({
        "mass_1_kg": 5.972e24, "mass_2_kg": 7.342e22, "separation_m": 3.84e8,
        "claimed_gravitational_force_N": 1.984e20,
    })
    assert r.status == "CONFIRMED"


def test_gravity_two_kg_one_meter():
    # 1 kg + 1 kg @ 1 m: F = 6.674e-11 N
    r = astro.verify_gravitational_force({
        "mass_1_kg": 1.0, "mass_2_kg": 1.0, "separation_m": 1.0,
        "claimed_gravitational_force_N": 6.674e-11,
    })
    assert r.status == "CONFIRMED"


def test_gravity_wrong_claim():
    r = astro.verify_gravitational_force({
        "mass_1_kg": 5.972e24, "mass_2_kg": 7.342e22, "separation_m": 3.84e8,
        "claimed_gravitational_force_N": 9.8,  # surface gravity ≠ orbital force
    })
    assert r.status == "MISMATCH"


def test_gravity_zero_separation_error():
    r = astro.verify_gravitational_force({
        "mass_1_kg": 1.0, "mass_2_kg": 1.0, "separation_m": 0,
        "claimed_gravitational_force_N": 0,
    })
    assert r.status == "ERROR"


# ── parallax distance ──────────────────────────────────────────────────

def test_parallax_proxima_centauri():
    # Proxima Centauri: parallax ≈ 0.769″ → 1.30 pc
    r = astro.verify_parallax_distance({
        "parallax_arcsec": 0.769,
        "claimed_distance_parsec": 1.30,
    })
    assert r.status == "CONFIRMED"


def test_parallax_one_parsec():
    # By definition: 1 arcsec parallax = 1 parsec
    r = astro.verify_parallax_distance({
        "parallax_arcsec": 1.0, "claimed_distance_parsec": 1.0,
    })
    assert r.status == "CONFIRMED"


def test_parallax_wrong_claim():
    r = astro.verify_parallax_distance({
        "parallax_arcsec": 0.5, "claimed_distance_parsec": 1.0,
    })
    assert r.status == "MISMATCH"


def test_parallax_zero_arcsec_error():
    r = astro.verify_parallax_distance({
        "parallax_arcsec": 0, "claimed_distance_parsec": 1.0,
    })
    assert r.status == "ERROR"


# ── distance modulus (m - M) ───────────────────────────────────────────

def test_distance_modulus_10_pc():
    # m=M means d=10pc by definition (M is at 10 pc).
    r = astro.verify_distance_modulus({
        "apparent_magnitude": 5.0, "absolute_magnitude": 5.0,
        "claimed_distance_parsec": 10.0,
    })
    assert r.status == "CONFIRMED"


def test_distance_modulus_sun_at_au():
    # Sun apparent ≈ -26.7, absolute ≈ 4.83 → distance ≈ 4.84e-6 pc ≈ 1 AU
    # 10^(((-26.7)-4.83+5)/5) = 10^(-26.53/5) = 10^(-5.306) = 4.94e-6 pc
    r = astro.verify_distance_modulus({
        "apparent_magnitude": -26.7, "absolute_magnitude": 4.83,
        "claimed_distance_parsec": 4.94e-6,
    })
    assert r.status == "CONFIRMED"


def test_distance_modulus_wrong_claim():
    r = astro.verify_distance_modulus({
        "apparent_magnitude": 5.0, "absolute_magnitude": 5.0,
        "claimed_distance_parsec": 100.0,
    })
    assert r.status == "MISMATCH"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = astro.run({"domain": "astronomy"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "astronomy",
        "ASTRO_VERIFY": {
            "orbital_period_years": 1.0, "semi_major_axis_au": 1.0,
            "claimed_kepler_consistent": True,
            "mass_1_kg": 5.972e24, "mass_2_kg": 7.342e22,
            "separation_m": 3.84e8,
            "claimed_gravitational_force_N": 1.984e20,
            "apparent_magnitude": 5.0, "absolute_magnitude": 5.0,
            "claimed_distance_parsec": 10.0,
        },
    }
    results = astro.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 3, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_astronomy_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "astronomy",
        "ASTRO_VERIFY": {
            "parallax_arcsec": 1.0, "claimed_distance_parsec": 1.0,
        },
    }
    results = run_for_domain("astronomy", packet)
    astro_results = [r for r in results if r.name.startswith("astronomy.")]
    assert len(astro_results) == 1
    assert astro_results[0].status == "CONFIRMED"
