"""Tests for schema validation in validate_and_seal.

Schema validation is a structural floor: a packet that's not even
well-formed JSON-shape never reaches the four gates. Without this,
malformed packets sealed clean as if the engine had verified them.
This is the fix for the audit's #1 weakness.

The schema enforces *shape*; the engine enforces *content*. Unknown
domains pass shape (the regex `^[a-z][a-z0-9_]*$`) and are handled by
the engine as "no validator registered." Missing required fields,
wrong types, malformed nested structures all fail at the schema gate.
"""
from __future__ import annotations

import pytest

from concordance_engine.engine import (
    EngineConfig, validate_packet, validate_and_seal,
)
from concordance_engine.witness_record import WitnessRecord


def _config(skip=False) -> EngineConfig:
    return EngineConfig(schema_path="", default_scope="adapter",
                        run_verifiers=True,
                        skip_schema_validation=skip)


# ── Schema rejects malformed packets BEFORE the four gates ─────────────

def test_packet_missing_domain_fails_schema():
    """The schema requires `domain`. Missing it should produce a RED
    reject from the schema gate, not a downstream gate."""
    rec = validate_and_seal(
        {},  # no domain
        config=_config(),
    )
    assert rec.overall == "REJECT"
    # The reject should come from RED, before any other gate.
    red_rejects = [gr for gr in rec.gate_results
                   if gr.gate == "RED" and gr.status == "REJECT"]
    assert red_rejects
    # The reason should mention schema validation.
    reasons = " ".join(red_rejects[0].reasons)
    assert "schema" in reasons.lower()


def test_packet_with_wrong_type_for_required_field_fails_schema():
    """`domain` must be a string. An int violates the schema."""
    rec = validate_and_seal(
        {"domain": 42},
        config=_config(),
    )
    assert rec.overall == "REJECT"
    red_rejects = [gr for gr in rec.gate_results
                   if gr.gate == "RED" and gr.status == "REJECT"]
    assert red_rejects


def test_packet_with_uppercase_domain_fails_schema_pattern():
    """Schema pattern is lowercase-only — `Mathematics` should fail."""
    rec = validate_and_seal(
        {"domain": "Mathematics"},
        config=_config(),
    )
    assert rec.overall == "REJECT"


def test_packet_with_negative_witness_count_fails_schema():
    """`witness_count` minimum is 0 — negative should fail schema."""
    rec = validate_and_seal(
        {"domain": "chemistry", "witness_count": -1},
        config=_config(),
    )
    assert rec.overall == "REJECT"


def test_packet_with_negative_created_epoch_fails_schema():
    rec = validate_and_seal(
        {"domain": "chemistry", "created_epoch": -100},
        config=_config(),
    )
    assert rec.overall == "REJECT"


# ── Unknown but well-formed domains pass schema, hit the engine path ───

def test_unknown_domain_passes_schema_but_handled_by_engine():
    """The schema dropped its enum constraint; unknown domains pass
    schema validation. The engine then hits the "no validator registered"
    path. Locks in: schema enforces shape, engine enforces content."""
    rec = validate_and_seal(
        {"domain": "underwater_basket_weaving",
         "claims": ["x"],
         "created_epoch": 10**9 - 7200,
         "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    # No domain validator → RED passes with note → all gates fire
    assert rec.overall in ("PASS", "QUARANTINE")
    # Verify it didn't get schema-rejected
    schema_rejects = [
        gr for gr in rec.gate_results
        if gr.status == "REJECT" and gr.reasons
        and any("schema" in r.lower() for r in gr.reasons)
    ]
    assert not schema_rejects


# ── New axes (added after the original schema enum) work ───────────────

def test_witness_domain_passes_schema():
    """The 36th axis (witness) was added long after the original
    schema's enum. Pre-fix, it would have failed schema. Now passes."""
    rec = validate_and_seal(
        {"domain": "witness",
         "WIT_VERIFY": {"declared_no_answer": True},
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    # Should pass schema; gate outcome depends on packet content but
    # we don't expect schema rejection.
    schema_rejects = [
        gr for gr in rec.gate_results
        if gr.status == "REJECT" and gr.reasons
        and any("schema" in r.lower() for r in gr.reasons)
    ]
    assert not schema_rejects


def test_geography_domain_passes_schema():
    """Another post-enum axis — locks in that the schema fix works for
    all 25+ axes added after the original enum was written."""
    rec = validate_and_seal(
        {"domain": "geography", "claims": ["Paris is in France"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    schema_rejects = [
        gr for gr in rec.gate_results
        if gr.status == "REJECT" and gr.reasons
        and any("schema" in r.lower() for r in gr.reasons)
    ]
    assert not schema_rejects


# ── skip_schema_validation flag ────────────────────────────────────────

def test_skip_schema_validation_lets_malformed_packet_through():
    """Callers who've validated upstream can pass skip=True. Used by
    the CLI's `validate` subcommand (which validates before invoking
    the engine) and by tests with deliberately-malformed packets."""
    # No domain — would fail schema but skip should let it through to
    # the engine's own no-domain handling.
    rec = validate_and_seal(
        {"created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(skip=True),
    )
    # Without schema enforcement, we go to the engine — no domain →
    # "no validator registered" RED note → continues. Outcome is now
    # PASS or QUARANTINE depending on later gates, NOT a schema reject.
    schema_rejects = [
        gr for gr in rec.gate_results
        if gr.status == "REJECT" and gr.reasons
        and any("schema" in r.lower() for r in gr.reasons)
    ]
    assert not schema_rejects


def test_skip_schema_validation_default_is_false():
    """The default for skip_schema_validation should be False — the
    engine validates by default."""
    cfg = EngineConfig(schema_path="")
    assert cfg.skip_schema_validation is False


# ── validate_packet (legacy entry point) also gets schema validation ───

def test_validate_packet_legacy_path_also_validates_schema():
    """validate_packet shares _run_validation — it should also catch
    schema failures."""
    res = validate_packet({}, config=_config())  # missing domain
    assert res.overall == "REJECT"
    schema_rejects = [
        gr for gr in res.gate_results
        if gr.status == "REJECT" and gr.reasons
        and any("schema" in r.lower() for r in gr.reasons)
    ]
    assert schema_rejects


# ── Schema file resolution ─────────────────────────────────────────────

def test_engine_finds_schema_via_default_path_when_config_path_blank():
    """When config.schema_path is empty, the engine should still find
    the bundled schema via the default path. Otherwise validation
    silently skips."""
    # Empty schema_path → engine falls back to the repo-level default.
    rec = validate_and_seal(
        {},  # missing domain
        config=EngineConfig(schema_path=""),
    )
    # If the default schema was found and applied, we should see a
    # schema-driven REJECT here.
    assert rec.overall == "REJECT"
