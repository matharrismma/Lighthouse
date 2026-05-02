"""Tests for the agriculture verifier."""
from __future__ import annotations

from concordance_engine.verifiers import agriculture as ag


# ── hardiness zone ─────────────────────────────────────────────────────

def test_zone_to_int_basic():
    assert ag._zone_to_int("7a") == 14
    assert ag._zone_to_int("7b") == 15
    assert ag._zone_to_int("7") == 14  # default 'a'
    assert ag._zone_to_int("13b") == 27
    assert ag._zone_to_int("garbage") is None
    assert ag._zone_to_int("14a") is None  # 14 out of range


def test_hardiness_zone_match_in_range():
    r = ag.verify_hardiness_zone({"crop": "tomato", "claimed_zone": "7b"})
    assert r.status == "CONFIRMED"


def test_hardiness_zone_match_out_of_range_too_cold():
    r = ag.verify_hardiness_zone({"crop": "citrus", "claimed_zone": "5a"})
    assert r.status == "MISMATCH"


def test_hardiness_zone_invalid_zone_is_error():
    r = ag.verify_hardiness_zone({"crop": "tomato", "claimed_zone": "20z"})
    assert r.status == "ERROR"


def test_hardiness_zone_unknown_crop_is_na():
    r = ag.verify_hardiness_zone({"crop": "unobtainium", "claimed_zone": "7a"})
    assert r.status == "NOT_APPLICABLE"


# ── soil pH ─────────────────────────────────────────────────────────────

def test_soil_ph_in_range():
    r = ag.verify_soil_ph({"crop": "tomato", "soil_ph": 6.5})
    assert r.status == "CONFIRMED"


def test_soil_ph_too_acidic():
    r = ag.verify_soil_ph({"crop": "tomato", "soil_ph": 4.5})
    assert r.status == "MISMATCH"
    assert "too acidic" in r.detail


def test_soil_ph_blueberry_likes_acidic():
    # Blueberries prefer 4.5-5.5
    r = ag.verify_soil_ph({"crop": "blueberry", "soil_ph": 5.0})
    assert r.status == "CONFIRMED"


def test_soil_ph_blueberry_too_alkaline():
    r = ag.verify_soil_ph({"crop": "blueberry", "soil_ph": 7.0})
    assert r.status == "MISMATCH"
    assert "too alkaline" in r.detail


def test_soil_ph_out_of_physical_range_is_error():
    r = ag.verify_soil_ph({"crop": "tomato", "soil_ph": 15.5})
    assert r.status == "ERROR"


def test_soil_ph_non_numeric_is_error():
    r = ag.verify_soil_ph({"crop": "tomato", "soil_ph": "alkaline"})
    assert r.status == "ERROR"


# ── rotation ────────────────────────────────────────────────────────────

def test_rotation_compatible_different_families():
    # tomato (Solanaceae) -> corn (Poaceae) -> bean (Fabaceae) is good rotation
    r = ag.verify_rotation({"rotation": ["tomato", "corn", "bean"]})
    assert r.status == "CONFIRMED"


def test_rotation_bad_same_family_adjacency():
    # tomato -> potato are both Solanaceae -> bad
    r = ag.verify_rotation({"rotation": ["tomato", "potato"]})
    assert r.status == "MISMATCH"
    assert "solanaceae" in r.detail.lower()


def test_rotation_three_year_with_same_family_in_middle():
    # corn -> wheat -> bean: corn and wheat both Poaceae -> bad adjacency
    r = ag.verify_rotation({"rotation": ["corn", "wheat", "bean"]})
    assert r.status == "MISMATCH"


def test_rotation_unknown_crop_is_na():
    r = ag.verify_rotation({"rotation": ["tomato", "unobtainium"]})
    assert r.status == "NOT_APPLICABLE"


def test_rotation_short_list_is_na():
    r = ag.verify_rotation({"rotation": ["tomato"]})
    assert r.status == "NOT_APPLICABLE"


# ── stocking density ───────────────────────────────────────────────────

def test_stocking_density_within_range():
    r = ag.verify_stocking_density({"animal": "cattle_beef", "stocking_per_acre": 1.0})
    assert r.status == "CONFIRMED"


def test_stocking_density_too_high():
    r = ag.verify_stocking_density({"animal": "cattle_beef", "stocking_per_acre": 5.0})
    assert r.status == "MISMATCH"
    assert "above" in r.detail


def test_stocking_density_too_low():
    r = ag.verify_stocking_density({"animal": "sheep", "stocking_per_acre": 0.1})
    assert r.status == "MISMATCH"
    assert "below" in r.detail


def test_stocking_density_negative_is_error():
    r = ag.verify_stocking_density({"animal": "cattle_beef", "stocking_per_acre": -1})
    assert r.status == "ERROR"


def test_stocking_density_unknown_animal_is_na():
    r = ag.verify_stocking_density({"animal": "dragon", "stocking_per_acre": 1.0})
    assert r.status == "NOT_APPLICABLE"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = ag.run({"domain": "agriculture"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "agriculture",
        "AG_VERIFY": {
            "crop": "tomato",
            "claimed_zone": "7b",
            "soil_ph": 6.5,
            "rotation": ["tomato", "corn"],
            "animal": "cattle_beef",
            "stocking_per_acre": 1.0,
        },
    }
    results = ag.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 4, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_agriculture_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "agriculture",
        "AG_VERIFY": {"crop": "tomato", "claimed_zone": "7b"},
    }
    results = run_for_domain("agriculture", packet)
    ag_results = [r for r in results if r.name.startswith("agriculture.")]
    assert len(ag_results) == 1
    assert ag_results[0].status == "CONFIRMED"
