"""Tests for the canonical result schema (WitnessRecord + helpers).

The schema is the single source of truth both surfaces render from.
These tests lock in: shape, immutability, JSON round-trip, witness-
verifier handoff, and the absence of any answer field anywhere.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from concordance_engine.gates import ok, reject
from concordance_engine.packet import EngineResult, GateResult
from concordance_engine.verifiers.base import (
    VerifierResult, confirm, mismatch, na,
)
from concordance_engine.verifiers import witness as witness_verifier
from concordance_engine.witness_record import (
    Anchor, AxisCoordinates, ClosestCase, WitnessRecord,
    SOURCE_LAYERS, axis_coords_for, build_record,
)


# ── Anchor ─────────────────────────────────────────────────────────────

def test_anchor_round_trip_with_text():
    a = Anchor(ref="Mat 5:37", layer="jesus_words", text="Let your yes be yes")
    a2 = Anchor.from_dict(a.to_dict())
    assert a == a2


def test_anchor_round_trip_without_text_omits_field():
    a = Anchor(ref="Gen 1:1", layer="bible")
    d = a.to_dict()
    assert "text" not in d
    assert Anchor.from_dict(d) == a


def test_anchor_layer_must_be_in_source_hierarchy():
    # Type system allows any string at runtime; the witness verifier
    # is what enforces. But all four layers should be valid here.
    for layer in SOURCE_LAYERS:
        a = Anchor(ref="x", layer=layer)
        assert a.layer == layer


def test_anchor_is_frozen():
    a = Anchor(ref="Mat 5:37", layer="jesus_words")
    with pytest.raises(FrozenInstanceError):
        a.ref = "changed"


# ── AxisCoordinates ────────────────────────────────────────────────────

def test_axis_coords_round_trip():
    c = AxisCoordinates(
        axis="witness",
        dimensions=frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    )
    c2 = AxisCoordinates.from_dict(c.to_dict())
    assert c == c2


def test_axis_coords_round_trip_with_umbrella():
    c = AxisCoordinates(
        axis="genetics",
        dimensions=frozenset({"encoding", "physical_substance"}),
        umbrella="biology",
    )
    c2 = AxisCoordinates.from_dict(c.to_dict())
    assert c == c2
    assert c2.umbrella == "biology"


def test_axis_coords_dict_sorts_dimensions_for_stability():
    c = AxisCoordinates(
        axis="witness",
        dimensions=frozenset({"time_sequence", "encoding", "authority_trust", "reasoning"}),
    )
    d = c.to_dict()
    assert d["dimensions"] == sorted(d["dimensions"])


# ── axis_coords_for() lookup ───────────────────────────────────────────

def test_axis_coords_for_known_axis():
    c = axis_coords_for("witness")
    assert c is not None
    assert "encoding" in c.dimensions
    assert "reasoning" in c.dimensions
    assert c.umbrella is None


def test_axis_coords_for_subsystem_detects_umbrella():
    c = axis_coords_for("genetics")
    assert c is not None
    assert c.umbrella == "biology"


def test_axis_coords_for_unknown_axis_returns_none():
    assert axis_coords_for("not_a_real_axis") is None


# ── ClosestCase ────────────────────────────────────────────────────────

def test_closest_case_with_full_payload():
    cc = ClosestCase(
        precedent_id="ledger://precedent/0042",
        shared_dimensions=frozenset({"encoding", "reasoning"}),
        distance=0.13,
        reasoning_overlay={"step_1": "..."},
    )
    cc2 = ClosestCase.from_dict(cc.to_dict())
    assert cc == cc2


def test_closest_case_explicit_no_precedent():
    """A novel claim legitimately has no precedent — the field is
    explicitly None, not silently fabricated."""
    cc = ClosestCase(precedent_id=None)
    d = cc.to_dict()
    assert d["precedent_id"] is None
    assert ClosestCase.from_dict(d) == cc


def test_closest_case_omits_optional_fields_when_none():
    cc = ClosestCase(precedent_id="ledger://p/1")
    d = cc.to_dict()
    assert "distance" not in d
    assert "reasoning_overlay" not in d
    # shared_dimensions is empty by default; omitted.
    assert "shared_dimensions" not in d


# ── WitnessRecord ──────────────────────────────────────────────────────

def _sample_engine_result() -> EngineResult:
    return EngineResult(
        overall="PASS",
        gate_results=[
            ok("RED", {"verified": ["math.equality: 2+2=4"]}),
            ok("FLOOR"),
            ok("WAY", {"note": "no way_path declared — Way check skipped"}),
            ok("BROTHERS", {"witnesses": 2, "required": 2}),
            ok("GOD", {"elapsed": 9999, "required": 60}),
        ],
    )


def _sample_verifier_results() -> tuple:
    return (
        confirm("math.equality", "matches", {"formula": "a + b = c", "rule": "..."}),
        na("scripture.anchors", "no anchors"),
    )


def test_record_round_trip_with_full_payload():
    rec = WitnessRecord(
        overall="PASS",
        gate_results=tuple(_sample_engine_result().gate_results),
        verifier_results=_sample_verifier_results(),
        anchors=(Anchor(ref="Mat 5:37", layer="jesus_words"),),
        axis_coords=axis_coords_for("mathematics"),
        closest_case=ClosestCase(
            precedent_id="ledger://p/1",
            shared_dimensions=frozenset({"reasoning"}),
        ),
        packet_id="pkt://test/1",
    )
    rec2 = WitnessRecord.from_dict(rec.to_dict())
    assert rec.overall == rec2.overall
    assert rec.packet_id == rec2.packet_id
    assert rec.anchors == rec2.anchors
    assert rec.axis_coords == rec2.axis_coords
    assert rec.closest_case == rec2.closest_case
    # gate_results and verifier_results compare elementwise via dataclass eq
    assert rec.gate_results == rec2.gate_results
    assert rec.verifier_results == rec2.verifier_results


def test_record_minimal_round_trip():
    rec = WitnessRecord(
        overall="REJECT",
        gate_results=(reject("RED", "no claims"),),
        verifier_results=(),
    )
    rec2 = WitnessRecord.from_dict(rec.to_dict())
    assert rec == rec2


def test_record_is_frozen():
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(),
        verifier_results=(),
    )
    with pytest.raises(FrozenInstanceError):
        rec.overall = "REJECT"


def test_record_passed_property():
    pass_rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    rej_rec = WitnessRecord(overall="REJECT", gate_results=(), verifier_results=())
    assert pass_rec.passed
    assert not rej_rec.passed


def test_record_hard_gate_failures_picks_red_floor_rejects_only():
    rec = WitnessRecord(
        overall="REJECT",
        gate_results=(
            reject("RED", "bad"),
            ok("FLOOR"),
            reject("BROTHERS", "few witnesses"),  # not RED/FLOOR — ignored
        ),
        verifier_results=(),
    )
    failures = rec.hard_gate_failures
    assert len(failures) == 1
    assert failures[0].gate == "RED"


def test_record_confirmed_and_failed_verifiers_partition():
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(),
        verifier_results=(
            confirm("a"),
            mismatch("b", "wrong"),
            na("c"),
        ),
    )
    assert len(rec.confirmed_verifiers()) == 1
    assert rec.confirmed_verifiers()[0].name == "a"
    assert len(rec.failed_verifiers()) == 1
    assert rec.failed_verifiers()[0].name == "b"


# ── No-fabricated-answer invariant ─────────────────────────────────────

def test_record_to_dict_has_no_answer_field():
    """The doctrine: the engine categorizes; it does not answer. No
    field named final_answer / answer / engine_answer should appear in
    the serialized record."""
    rec = WitnessRecord(
        overall="PASS",
        gate_results=tuple(_sample_engine_result().gate_results),
        verifier_results=_sample_verifier_results(),
        anchors=(Anchor(ref="Mat 5:37", layer="jesus_words"),),
    )
    d = rec.to_dict()
    forbidden = {"final_answer", "answer", "engine_answer", "verdict_answer"}
    assert not (forbidden & set(d.keys())), \
        f"WitnessRecord serialized with a forbidden answer field: {forbidden & set(d.keys())}"


# ── Witness-verifier handoff ───────────────────────────────────────────

def test_record_to_wit_verify_block_passes_witness_verifier():
    """Round-trip: a built record's WIT_VERIFY block should pass every
    witness check. This is the contract that makes the schema and the
    verifier consistent."""
    rec = WitnessRecord(
        overall="PASS",
        gate_results=tuple(_sample_engine_result().gate_results),
        verifier_results=_sample_verifier_results(),
        anchors=(Anchor(ref="Mat 5:37", layer="jesus_words"),),
    )
    packet = {"WIT_VERIFY": rec.to_wit_verify_block()}
    results = witness_verifier.run(packet)
    statuses = {r.name: r.status for r in results}
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.reasoning_trace_present"] == "CONFIRMED"
    assert statuses["witness.anchors_resolve"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "CONFIRMED"


def test_record_with_short_circuit_red_passes_witness():
    """A record that REJECTed at RED has no later gates and no verifier
    traces — witness should still seal it (gate chain short-circuited,
    no traces required for absent results)."""
    rec = WitnessRecord(
        overall="REJECT",
        gate_results=(reject("RED", "missing claims"),),
        verifier_results=(),
    )
    packet = {"WIT_VERIFY": rec.to_wit_verify_block()}
    results = witness_verifier.run(packet)
    statuses = {r.name: r.status for r in results}
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "CONFIRMED"


# ── Builder ────────────────────────────────────────────────────────────

def test_build_record_packs_engine_output():
    er = _sample_engine_result()
    rec = build_record(
        engine_result=er,
        verifier_results=_sample_verifier_results(),
        axis_coords=axis_coords_for("mathematics"),
        packet_id="pkt://1",
    )
    assert rec.overall == "PASS"
    assert len(rec.gate_results) == 5  # added WAY between FLOOR and BROTHERS
    assert len(rec.verifier_results) == 2
    assert rec.axis_coords is not None
    assert rec.axis_coords.axis == "mathematics"
    assert rec.packet_id == "pkt://1"
    # No answer field, even via the builder.
    assert "final_answer" not in rec.to_dict()


def test_build_record_minimal_no_optional_fields():
    er = EngineResult(overall="QUARANTINE", gate_results=[
        ok("RED"), ok("FLOOR"),
    ])
    rec = build_record(engine_result=er)
    assert rec.overall == "QUARANTINE"
    assert rec.anchors == ()
    assert rec.axis_coords is None
    assert rec.closest_case is None


# ── Schema 1.1 fields ──────────────────────────────────────────────────────

def test_schema_version_is_1_1():
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    assert rec.schema_version == "1.1"
    assert rec.to_dict()["schema_version"] == "1.1"


def test_content_hash_present_in_to_dict():
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    d = rec.to_dict()
    assert "content_hash" in d
    assert len(d["content_hash"]) == 64


def test_content_hash_is_stable():
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=(), packet_id="p1")
    d1 = rec.to_dict()
    d2 = rec.to_dict()
    assert d1["content_hash"] == d2["content_hash"]


def test_content_hash_changes_with_content():
    rec1 = WitnessRecord(overall="PASS", gate_results=(), verifier_results=(), packet_id="p1")
    rec2 = WitnessRecord(overall="PASS", gate_results=(), verifier_results=(), packet_id="p2")
    assert rec1.to_dict()["content_hash"] != rec2.to_dict()["content_hash"]


def test_permanent_ref_in_to_dict_when_set():
    from concordance_engine.witness_record import with_permanent_ref
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    ref_hash = "a" * 64
    rec2 = with_permanent_ref(rec, ref_hash)
    d = rec2.to_dict()
    assert d["permanent_ref"] == ref_hash


def test_permanent_ref_absent_when_not_set():
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    d = rec.to_dict()
    assert "permanent_ref" not in d


def test_permanent_ref_excluded_from_content_hash():
    """permanent_ref must not affect the content_hash — it's added after hashing."""
    from concordance_engine.witness_record import with_permanent_ref
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=(), packet_id="p1")
    rec_with_ref = with_permanent_ref(rec, "b" * 64)
    # The content_hash must be identical whether or not permanent_ref is set
    assert rec.to_dict()["content_hash"] == rec_with_ref.to_dict()["content_hash"]


def test_witness_attestations_round_trip():
    from concordance_engine.witness_record import embed_attestations
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    atts = ({"witness_id": "w1", "sig": "sig_abc"}, {"witness_id": "w2", "sig": "sig_xyz"})
    rec2 = embed_attestations(rec, atts)
    d = rec2.to_dict()
    assert len(d["witness_attestations"]) == 2
    assert d["witness_attestations"][0]["witness_id"] == "w1"
    rec3 = WitnessRecord.from_dict(d)
    assert len(rec3.witness_attestations) == 2


def test_witness_attestations_absent_when_empty():
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    d = rec.to_dict()
    assert "witness_attestations" not in d
