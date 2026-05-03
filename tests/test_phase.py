"""Tests for phase metadata — Setup → Positioning → Conversion.

Per 00_CANON/PHASES_SETUP_POSITIONING_CONVERSION.md, every decision
sits in one of three canonical phases. The phase verifier is a
cross-cutting classifier that reads `packet.phase`, validates it's
one of the canonical three, and surfaces the canonical guidance for
that phase. NA when no phase is declared (optional metadata in V1).
"""
from __future__ import annotations

from concordance_engine.engine import EngineConfig, validate_and_seal
from concordance_engine.verifiers import phase as phase_verifier


def _config() -> EngineConfig:
    return EngineConfig(schema_path="", run_verifiers=True)


# ── Direct verifier behavior ───────────────────────────────────────────

def test_phase_verifier_na_when_no_phase_declared():
    r = phase_verifier.verify_phase({"domain": "chemistry"})
    assert r.status == "NOT_APPLICABLE"


def test_phase_verifier_confirms_setup():
    r = phase_verifier.verify_phase({"domain": "chemistry", "phase": "setup"})
    assert r.status == "CONFIRMED"
    assert r.data["phase"] == "setup"
    assert "secure base" in r.data["guidance"].lower()


def test_phase_verifier_confirms_positioning():
    r = phase_verifier.verify_phase({"phase": "positioning"})
    assert r.status == "CONFIRMED"
    assert r.data["phase"] == "positioning"
    assert "dominant positions" in r.data["guidance"].lower()


def test_phase_verifier_confirms_conversion():
    r = phase_verifier.verify_phase({"phase": "conversion"})
    assert r.status == "CONFIRMED"
    assert r.data["phase"] == "conversion"
    assert "lock in gains" in r.data["guidance"].lower()


def test_phase_verifier_normalizes_case():
    """Phase comparison is case-insensitive — 'Setup' / 'SETUP' / 'setup'
    all classify the same."""
    for variant in ("Setup", "SETUP", "setup", " Setup "):
        r = phase_verifier.verify_phase({"phase": variant})
        assert r.status == "CONFIRMED"
        assert r.data["phase"] == "setup"


def test_phase_verifier_rejects_unknown_phase():
    r = phase_verifier.verify_phase({"phase": "consolidation"})
    assert r.status == "MISMATCH"
    assert "consolidation" in str(r.data).lower()


def test_phase_verifier_errors_on_non_string_phase():
    r = phase_verifier.verify_phase({"phase": 123})
    assert r.status == "ERROR"


def test_phase_verifier_carries_anchor():
    r = phase_verifier.verify_phase({"phase": "setup"})
    anchor = r.data.get("anchor")
    assert anchor is not None
    assert anchor["ref"] == "Prov 24:27"
    assert anchor["layer"] == "bible"


# ── Cross-cutting integration: phase runs on every packet ──────────────

def test_phase_runs_cross_cutting_for_all_domains():
    """Phase verifier is in CROSS_CUTTING_VERIFIERS, so it fires on
    every packet — not just packets in a 'phase' domain."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["water is H2O"],
            "phase": "positioning",
            "created_epoch": 10**9 - 7200,
            "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    phase_results = [
        v for v in rec.verifier_results
        if v.name == "phase.classification"
    ]
    assert len(phase_results) == 1
    assert phase_results[0].status == "CONFIRMED"
    assert phase_results[0].data["phase"] == "positioning"


def test_phase_na_does_not_block_pass():
    """A packet that doesn't declare a phase should still pass through
    the four gates cleanly — phase is optional metadata in V1."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["water is H2O"],
            "created_epoch": 10**9 - 7200,
            "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "PASS"
    phase_results = [
        v for v in rec.verifier_results
        if v.name == "phase.classification"
    ]
    assert len(phase_results) == 1
    assert phase_results[0].status == "NOT_APPLICABLE"


def test_phase_unknown_value_causes_red_reject():
    """An unknown phase value is treated as a verifier failure, which
    rolls up as a RED reject (since failed verifiers reject at RED)."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["x"],
            "phase": "consolidation",  # not canonical
            "created_epoch": 10**9 - 7200,
            "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "REJECT"


# ── Schema integration ────────────────────────────────────────────────

def test_schema_enum_enforces_phase_values():
    """A non-canonical phase value should fail at the schema gate
    (before verifiers run) because the schema enum restricts it."""
    rec = validate_and_seal(
        {"domain": "chemistry", "phase": "consolidation"},
        config=_config(),
    )
    # Should reject at RED with a schema-validation reason.
    assert rec.overall == "REJECT"
    red = next(
        gr for gr in rec.gate_results
        if gr.gate == "RED" and gr.status == "REJECT"
    )
    assert "schema" in str(red.reasons).lower()
