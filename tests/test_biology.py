"""Tests for the biology verifier — focused on the BIO_CONTROL block.

The replicates / assay-classes / dose-response / power / hardy-weinberg /
primer / molarity / mendelian checks are exercised by the existing
benchmark + canon tests; this file targets the nested-health-control
block that was ported from the 2026-04-30 archive.
"""
from __future__ import annotations

from concordance_engine.verifiers import biology as bio
from concordance_engine.verifiers.base import VerifierResult


# ── failure_mode_taxonomy ───────────────────────────────────────────────

def test_failure_mode_known_recognized():
    r = bio.verify_failure_mode_known({"failure_mode": "setpoint_drift"})
    assert r.status == "CONFIRMED"


def test_failure_mode_known_unknown_is_mismatch():
    r = bio.verify_failure_mode_known({"failure_mode": "vibe_collapse"})
    assert r.status == "MISMATCH"
    assert "vibe_collapse" in r.detail


def test_failure_mode_known_absent_is_skip_confirm():
    """Absent failure_mode is a skip (CONFIRMED with 'check skipped')."""
    r = bio.verify_failure_mode_known({})
    assert r.status == "CONFIRMED"


# ── control_layer_match ─────────────────────────────────────────────────

def test_control_layer_match_intervention_above_failure_passes():
    r = bio.verify_control_layer_match({
        "failure_layer": "L4",
        "intervention_layers": ["L4", "L5"],
    })
    assert r.status == "CONFIRMED"


def test_control_layer_match_intervention_below_failure_mismatches():
    r = bio.verify_control_layer_match({
        "failure_layer": "L4",
        "intervention_layers": ["L1", "L2"],
    })
    assert r.status == "MISMATCH"
    assert "L1" in r.detail or "L2" in r.detail


def test_control_layer_match_unknown_layer_is_error():
    r = bio.verify_control_layer_match({
        "failure_layer": "L99",
        "intervention_layers": ["L1"],
    })
    assert r.status == "ERROR"


def test_control_layer_match_no_layers_is_skip():
    r = bio.verify_control_layer_match({})
    assert r.status == "CONFIRMED"


# ── cross_layer_override / setpoint_drift / sensor_failure ──────────────

def test_cross_layer_override_addressed_passes():
    r = bio.verify_cross_layer_override({
        "failure_mode": "cross_layer_override",
        "upper_layer_driver_addressed": True,
    })
    assert r.status == "CONFIRMED"


def test_cross_layer_override_not_addressed_mismatches():
    r = bio.verify_cross_layer_override({
        "failure_mode": "cross_layer_override",
        "upper_layer_driver_addressed": False,
    })
    assert r.status == "MISMATCH"


def test_cross_layer_override_other_mode_skips():
    r = bio.verify_cross_layer_override({
        "failure_mode": "setpoint_drift",
    })
    assert r.status == "CONFIRMED"


def test_setpoint_mechanism_stated_passes():
    r = bio.verify_setpoint_mechanism({
        "failure_mode": "setpoint_drift",
        "setpoint_shift_mechanism_stated": True,
    })
    assert r.status == "CONFIRMED"


def test_setpoint_mechanism_not_stated_mismatches():
    r = bio.verify_setpoint_mechanism({
        "failure_mode": "setpoint_drift",
        "setpoint_shift_mechanism_stated": False,
    })
    assert r.status == "MISMATCH"


def test_sensor_failure_plan_present_passes():
    r = bio.verify_sensor_failure_plan({
        "failure_mode": "sensor_failure",
        "sensor_recalibration_plan": True,
    })
    assert r.status == "CONFIRMED"


def test_sensor_failure_plan_missing_mismatches():
    r = bio.verify_sensor_failure_plan({
        "failure_mode": "sensor_failure",
    })
    assert r.status == "MISMATCH"


# ── End-to-end run() dispatch ───────────────────────────────────────────

def test_run_dispatches_bio_control_full_path():
    """A correctly-attested BIO_CONTROL packet for cross_layer_override."""
    packet = {
        "domain": "biology",
        "BIO_CONTROL": {
            "failure_mode": "cross_layer_override",
            "failure_layer": "L4",
            "intervention_layers": ["L4", "L5"],
            "upper_layer_driver_addressed": True,
        },
    }
    results = bio.run(packet)
    statuses = [(r.name, r.status) for r in results]
    # taxonomy + layer_match + cross_layer_override = 3 checks
    assert len(results) == 3, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_run_catches_setpoint_drift_without_mechanism():
    packet = {
        "domain": "biology",
        "BIO_CONTROL": {
            "failure_mode": "setpoint_drift",
            "failure_layer": "L3",
            "intervention_layers": ["L3"],
            # setpoint_shift_mechanism_stated intentionally missing
        },
    }
    results = bio.run(packet)
    by_name = {r.name: r for r in results}
    assert by_name["biology.setpoint_mechanism"].status == "MISMATCH"


def test_run_combined_bio_verify_and_bio_control():
    """Both BIO_VERIFY and BIO_CONTROL blocks are dispatched."""
    packet = {
        "domain": "biology",
        "BIO_VERIFY": {
            "n_replicates": 4,
            "min_replicates": 3,
        },
        "BIO_CONTROL": {
            "failure_mode": "loop_saturation",
            "failure_layer": "L2",
            "intervention_layers": ["L2"],
        },
    }
    results = bio.run(packet)
    names = [r.name for r in results]
    assert "biology.replicates" in names
    assert "biology.failure_mode_taxonomy" in names
    assert "biology.control_layer_match" in names
