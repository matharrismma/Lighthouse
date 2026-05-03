"""Tests for the verifier-rule → anchor link convention.

Audit weakness #3: verifier rules float free of the source hierarchy.
The doctrine says Jesus' words are primary, but mechanically nothing
connected `governance.witness_count_consistency` to Mt 18:16.

The fix establishes an opt-in convention: a verifier's `data` dict
may carry an `anchor` field of shape:

    {"ref": "Mt 18:16",
     "layer": "jesus_words",  # one of the source-hierarchy layers
     "derivation": "one-line how-this-rule-derives-from-the-anchor"}

The witness verifier's new `rule_anchors_resolve` check validates
declared anchors. The walkthrough renderer surfaces them inline.
This V1 increment annotates two flagship verifiers
(governance.witness_count_consistency, scripture.canon_membership)
as worked examples; future iterations roll out to all 36+ axes.
"""
from __future__ import annotations

from concordance_engine.engine import EngineConfig, validate_and_seal
from concordance_engine.gates import ok
from concordance_engine.verifiers import (
    governance, scripture, witness as wit,
)
from concordance_engine.verifiers.base import confirm, mismatch
from concordance_engine.walkthrough import render_walkthrough
from concordance_engine.witness_record import (
    SOURCE_LAYERS, WitnessRecord, axis_coords_for,
)


# ── Annotated verifiers carry anchor metadata ──────────────────────────

def test_governance_witness_count_carries_mt_18_16_anchor():
    """The witness-count-consistency rule cites Mt 18:16 (plural
    witness). Verifies the annotation is reachable from the verifier
    output."""
    spec = {"witnesses": ["Alice", "Bob"]}
    packet = {"witness_count": 2}
    result = governance.verify_witness_count_consistency(spec, packet)
    assert result.status == "CONFIRMED"
    assert isinstance(result.data, dict)
    anchor = result.data.get("anchor")
    assert anchor is not None
    assert anchor["ref"] == "Mt 18:16"
    assert anchor["layer"] == "jesus_words"
    assert "derivation" in anchor


def test_governance_witness_count_anchor_present_on_mismatch():
    """Anchor is on the rule itself, not gated by status — must
    appear on MISMATCH too so the human can see why the rule fired."""
    spec = {"witnesses": ["Alice"]}  # 1 witness
    packet = {"witness_count": 5}    # claims 5
    result = governance.verify_witness_count_consistency(spec, packet)
    assert result.status == "MISMATCH"
    assert isinstance(result.data, dict)
    assert result.data.get("anchor", {}).get("ref") == "Mt 18:16"


def test_scripture_canon_membership_carries_2_tim_3_16_anchor():
    """canon_membership cites 2 Tim 3:16 (all Scripture is breathed
    out by God)."""
    result = scripture.verify_canon_membership(["Mt 5:37"])
    assert result.status == "CONFIRMED"
    anchor = result.data.get("anchor")
    assert anchor is not None
    assert anchor["ref"] == "2 Tim 3:16"
    assert anchor["layer"] == "apostles"


def test_anchor_layer_is_in_source_hierarchy_for_all_annotated():
    """Every annotated verifier's anchor.layer must be in the source
    hierarchy. If a future verifier gets annotated with a typo'd
    layer, this test catches it."""
    # Sweep the two known annotated verifiers
    samples = [
        governance.verify_witness_count_consistency(
            {"witnesses": ["A"]}, {"witness_count": 1},
        ),
        scripture.verify_canon_membership(["Mt 5:37"]),
    ]
    for r in samples:
        if not isinstance(r.data, dict):
            continue
        anchor = r.data.get("anchor")
        if anchor is None:
            continue
        assert anchor["layer"] in SOURCE_LAYERS, (
            f"{r.name}: anchor.layer {anchor['layer']!r} not in {SOURCE_LAYERS}"
        )


# ── Witness check: verify_rule_anchors_resolve ─────────────────────────

def test_witness_rule_anchors_check_passes_when_all_valid():
    """Verifier results with valid anchors should resolve clean."""
    p = {"WIT_VERIFY": {
        "claimed_verifier_results": [
            {"name": "v1", "status": "CONFIRMED",
             "data": {
                 "anchor": {"ref": "Mt 5:37", "layer": "jesus_words"},
                 "rule": "...",
             }},
        ],
    }}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "CONFIRMED"
    assert r.data["checked_count"] == 1


def test_witness_rule_anchors_check_na_when_no_anchors_declared():
    """Verifiers without anchor fields are silently passed (opt-in)."""
    p = {"WIT_VERIFY": {
        "claimed_verifier_results": [
            {"name": "v1", "status": "CONFIRMED", "data": {"rule": "..."}},
            {"name": "v2", "status": "CONFIRMED", "data": {"formula": "x"}},
        ],
    }}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "NOT_APPLICABLE"


def test_witness_rule_anchors_check_catches_wrong_layer():
    """A verifier annotated with a layer outside the source hierarchy
    should fail this check."""
    p = {"WIT_VERIFY": {
        "claimed_verifier_results": [
            {"name": "v1", "status": "CONFIRMED",
             "data": {
                 "anchor": {"ref": "Mt 5:37", "layer": "wikipedia"},
                 "rule": "...",
             }},
        ],
    }}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "MISMATCH"
    assert any("wikipedia" in str(b.get("reason", ""))
               for b in r.data["bad_anchors"])


def test_witness_rule_anchors_check_catches_missing_ref():
    p = {"WIT_VERIFY": {
        "claimed_verifier_results": [
            {"name": "v1", "status": "CONFIRMED",
             "data": {
                 "anchor": {"layer": "jesus_words"},  # no ref
                 "rule": "...",
             }},
        ],
    }}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "MISMATCH"


def test_witness_rule_anchors_check_catches_non_dict_anchor():
    p = {"WIT_VERIFY": {
        "claimed_verifier_results": [
            {"name": "v1", "status": "CONFIRMED",
             "data": {"anchor": "Mt 5:37"}},  # bare string instead of dict
        ],
    }}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "MISMATCH"


def test_witness_rule_anchors_returns_na_when_no_verifier_results():
    p = {"WIT_VERIFY": {}}
    r = wit.verify_rule_anchors_resolve(p)
    assert r.status == "NOT_APPLICABLE"


# ── Walkthrough surfaces the anchor ────────────────────────────────────

def test_walkthrough_trace_displays_anchor_with_derivation():
    """When a verifier's data carries an anchor, the trace section
    must show the ref, the layer, and the derivation note."""
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD")),
        verifier_results=(
            confirm("governance.witness_count_consistency", "matches", {
                "anchor": {
                    "ref": "Mt 18:16",
                    "layer": "jesus_words",
                    "derivation": "Plural witness consistency (Mt 18:16).",
                },
                "rule": "named witnesses must equal declared count",
            }),
        ),
        anchors=(),
        axis_coords=axis_coords_for("governance"),
        packet_id="pkt://test/1",
    )
    md = render_walkthrough(rec, expand_traces=True)
    assert "Derives from" in md
    assert "Mt 18:16" in md
    assert "jesus_words" in md
    assert "Plural witness consistency" in md


def test_walkthrough_trace_omits_anchor_section_when_absent():
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD")),
        verifier_results=(
            confirm("math.equality", "matches",
                    {"formula": "a + b = c", "rule": "..."}),
        ),
        anchors=(),
        axis_coords=axis_coords_for("mathematics"),
        packet_id="pkt://test/2",
    )
    md = render_walkthrough(rec, expand_traces=True)
    assert "Derives from" not in md


# ── End-to-end: governance packet shows annotated rule with anchor ─────

def test_e2e_governance_packet_carries_anchor_through_to_walkthrough():
    """A governance DECISION_PACKET that triggers
    witness_count_consistency should produce a sealed record whose
    rendered walkthrough surfaces the Mt 18:16 anchor in the
    verifier traces section."""
    packet = {
        "domain": "governance",
        "DECISION_PACKET": {
            "title": "Test decision",
            "scope": "adapter",
            "red_items": ["no theft"],
            "floor_items": ["affirm consent"],
            "way_path": "consult elders",
            "execution_steps": ["step 1"],
            "witnesses": ["Alice", "Bob"],
        },
        "witness_count": 2,
        "scope": "adapter",
        "created_epoch": 10**9 - 7200,
        "wait_window_seconds": 0,
    }
    rec = validate_and_seal(
        packet, now_epoch=10**9,
        config=EngineConfig(schema_path="", run_verifiers=True),
    )
    md = render_walkthrough(rec, expand_traces=True)
    # The witness_count_consistency verifier should have fired and
    # surfaced its Mt 18:16 anchor.
    assert "Mt 18:16" in md
    assert "jesus_words" in md
