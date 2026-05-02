"""Integration tests for `engine.validate_and_seal`.

The new canonical entry point: runs the four gates and returns a sealed
WitnessRecord. Both agent and human surfaces consume the record; these
tests lock in the contract that ties the engine, the schema, and the
witness verifier together.
"""
from __future__ import annotations

import pytest

from concordance_engine.engine import (
    EngineConfig, validate_packet, validate_and_seal,
)
from concordance_engine.witness_record import (
    Anchor, ClosestCase, WitnessRecord,
)
from concordance_engine.verifiers import witness as witness_verifier


def _config(run_verifiers=True):
    return EngineConfig(schema_path="", default_scope="adapter",
                        run_verifiers=run_verifiers)


# ── Backward compat: validate_packet still returns EngineResult ────────

def test_validate_packet_unchanged_pass_path():
    packet = {
        "domain": "chemistry",
        "claims": ["sodium chloride is NaCl"],
        "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
    }
    result = validate_packet(packet, now_epoch=10**9, config=_config())
    # EngineResult shape
    assert hasattr(result, "overall")
    assert hasattr(result, "gate_results")
    assert result.overall == "PASS"


def test_validate_packet_unchanged_reject_path():
    # Empty packet with no domain triggers the no-domain-validator path,
    # which passes RED with a note. Force a real REJECT by giving a
    # chemistry packet without claims (RED-rejected by the validator).
    result = validate_packet(
        {"domain": "chemistry"},
        now_epoch=10**9, config=_config(),
    )
    assert result.overall == "REJECT"


# ── validate_and_seal: PASS path ───────────────────────────────────────

def test_seal_pass_path_returns_witness_record():
    packet = {
        "domain": "chemistry",
        "claims": ["sodium chloride is NaCl"],
        "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
    }
    rec = validate_and_seal(packet, now_epoch=10**9, config=_config())
    assert isinstance(rec, WitnessRecord)
    assert rec.overall == "PASS"
    assert rec.passed
    assert len(rec.gate_results) == 4
    # All four gates fired in order
    gates = [gr.gate for gr in rec.gate_results]
    assert gates == ["RED", "FLOOR", "BROTHERS", "GOD"]


def test_seal_includes_axis_coords_for_known_domain():
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"], "created_epoch": 0,
         "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    assert rec.axis_coords is not None
    assert rec.axis_coords.axis == "chemistry"
    assert "physical_substance" in rec.axis_coords.dimensions


def test_seal_axis_coords_detects_umbrella_for_subsystem():
    rec = validate_and_seal(
        {"domain": "genetics", "claims": ["dna is a polymer"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(run_verifiers=False),
    )
    assert rec.axis_coords is not None
    assert rec.axis_coords.umbrella == "biology"


def test_seal_axis_coords_none_for_unknown_domain():
    rec = validate_and_seal(
        {"domain": "underwater_basket_weaving", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    # Unknown domain: gates pass (no validator registered), axis_coords None.
    assert rec.axis_coords is None


# ── validate_and_seal: REJECT short-circuit ────────────────────────────

def test_seal_red_reject_short_circuits():
    rec = validate_and_seal(
        {"domain": "chemistry"},  # no claims → RED reject
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "REJECT"
    # Only RED was reached; FLOOR / BROTHERS / GOD not fired.
    gates = [gr.gate for gr in rec.gate_results]
    assert "RED" in gates
    assert "GOD" not in gates


def test_seal_quarantine_at_brothers():
    rec = validate_and_seal(
        {
            "domain": "chemistry", "claims": ["x"],
            "required_witnesses": 3, "witness_count": 1,
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "QUARANTINE"
    # BROTHERS should be the gate that quarantined.
    brothers = [gr for gr in rec.gate_results if gr.gate == "BROTHERS"]
    assert brothers and brothers[0].status == "QUARANTINE"


# ── verifier results surfaced as first-class ───────────────────────────

def test_seal_carries_verifier_results():
    """Verifier results, previously buried in gate-result `details`, are
    now first-class fields on the WitnessRecord."""
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    # At minimum the cross-cutting scripture verifier ran (it short-
    # circuits to no-op when there are no anchors, but it doesn't add
    # a result in that case — the chemistry verifier may add one).
    # Either way, verifier_results is a tuple, not None.
    assert isinstance(rec.verifier_results, tuple)


def test_seal_carries_verifier_results_for_witness_domain():
    rec = validate_and_seal(
        {
            "domain": "witness",
            "WIT_VERIFY": {
                "claimed_gate_verdicts": [
                    {"gate": "RED", "status": "PASS"},
                    {"gate": "FLOOR", "status": "PASS"},
                    {"gate": "BROTHERS", "status": "PASS"},
                    {"gate": "GOD", "status": "PASS"},
                ],
                "declared_no_answer": True,
            },
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    # Witness domain runs the 4 witness checks; gate_chain_complete and
    # no_fabricated_answer fire when WIT_VERIFY is present.
    names = {v.name for v in rec.verifier_results}
    assert "witness.gate_chain_complete" in names
    assert "witness.no_fabricated_answer" in names


# ── caller-supplied anchors / closest_case / packet_id pass through ────

def test_seal_passes_through_anchors():
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
        anchors=(
            Anchor(ref="Mt 5:37", layer="jesus_words"),
            Anchor(ref="Gen 1:1", layer="bible"),
        ),
    )
    assert len(rec.anchors) == 2
    assert rec.anchors[0].layer == "jesus_words"
    assert rec.anchors[1].layer == "bible"


def test_seal_passes_through_closest_case():
    cc = ClosestCase(
        precedent_id="ledger://precedent/0042",
        shared_dimensions=frozenset({"physical_substance", "metabolism"}),
        distance=0.21,
    )
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
        closest_case=cc,
    )
    assert rec.closest_case == cc


def test_seal_passes_through_packet_id():
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
        packet_id="pkt://test/seal/1",
    )
    assert rec.packet_id == "pkt://test/seal/1"


def test_seal_explicit_no_precedent_when_none_supplied():
    """A caller without a precedent passes None — the field stays None,
    not silently invented. Honors the closest-case overlay doctrine."""
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    assert rec.closest_case is None


# ── No-fabricated-answer invariant — round-trip through witness ────────

def test_seal_record_passes_witness_verification():
    """The contract: a sealed record's testimony passes every witness
    check. Locks in schema + meta-axis consistency end-to-end."""
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
        anchors=(Anchor(ref="Mt 5:37", layer="jesus_words"),),
    )
    packet_for_witness = {"WIT_VERIFY": rec.to_wit_verify_block()}
    results = witness_verifier.run(packet_for_witness)
    statuses = {r.name: r.status for r in results}
    # Every applicable witness check should confirm.
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.anchors_resolve"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "CONFIRMED"


def test_seal_record_to_dict_has_no_answer_field():
    """The serialized record must never carry a fabricated answer
    field. The doctrine is expressed in the absence of such a field."""
    rec = validate_and_seal(
        {"domain": "chemistry", "claims": ["x"],
         "created_epoch": 10**9 - 7200, "wait_window_seconds": 0},
        now_epoch=10**9, config=_config(),
    )
    d = rec.to_dict()
    forbidden = {"final_answer", "answer", "engine_answer", "verdict_answer"}
    assert not (forbidden & set(d.keys()))


# ── validate_packet and validate_and_seal agree on gate verdicts ───────

def test_seal_and_packet_agree_on_overall():
    """Both entry points run the same gate sequence — overall must
    match for any given packet."""
    cases = [
        {"domain": "chemistry"},  # REJECT (no claims)
        {"domain": "chemistry", "claims": ["x"], "created_epoch": 0,
         "wait_window_seconds": 0},  # PASS
        {"domain": "chemistry", "claims": ["x"], "required_witnesses": 5,
         "witness_count": 1, "created_epoch": 0,
         "wait_window_seconds": 0},  # QUARANTINE at BROTHERS
    ]
    for packet in cases:
        er = validate_packet(packet, now_epoch=10**9, config=_config())
        rec = validate_and_seal(packet, now_epoch=10**9, config=_config())
        assert er.overall == rec.overall, (
            f"disagreement on {packet}: validate_packet={er.overall} "
            f"validate_and_seal={rec.overall}"
        )
