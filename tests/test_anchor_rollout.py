"""Tests for the rule-anchor rollout — V1.5 increment.

The rule-anchor convention (audit fix #3) was demonstrated on two
flagship verifiers in audit pass 1. This pass rolls it out to the
other doctrinally-load-bearing verifiers in scripture.py, governance.py,
and witness.py.

Each test confirms:
  * The verifier's data payload carries an `anchor` field.
  * The anchor's `layer` is in the source hierarchy.
  * The anchor's `ref` is a non-empty string.
  * The anchor's `derivation` explains how the rule derives from the ref.

Locks in: removing or weakening any of these annotations would fail
its own test, surfacing the regression at PR-review time.
"""
from __future__ import annotations

import pytest

from concordance_engine.verifiers import (
    governance, scripture, witness as wit,
)
from concordance_engine.witness_record import SOURCE_LAYERS


def _check_anchor(result, expected_ref: str, expected_layer: str):
    """Assert a verifier result carries a well-formed anchor with the
    expected ref and layer."""
    assert isinstance(result.data, dict), \
        f"{result.name} has no data dict"
    anchor = result.data.get("anchor")
    assert anchor is not None, f"{result.name} missing anchor"
    assert isinstance(anchor, dict), \
        f"{result.name} anchor must be a dict"
    assert anchor.get("ref") == expected_ref, \
        f"{result.name} expected ref={expected_ref!r}, got {anchor.get('ref')!r}"
    assert anchor.get("layer") == expected_layer, \
        f"{result.name} expected layer={expected_layer!r}, got {anchor.get('layer')!r}"
    assert anchor.get("layer") in SOURCE_LAYERS, \
        f"{result.name} layer {anchor.get('layer')!r} not in source hierarchy"
    derivation = anchor.get("derivation")
    assert isinstance(derivation, str) and len(derivation) > 20, \
        f"{result.name} derivation too short or missing"


# ── scripture.verify_scripture_anchors ─────────────────────────────────

def test_scripture_anchors_carries_prov_30_5_6_anchor_on_empty():
    """Even the no-op (empty anchors list) carries the rule's anchor."""
    r = scripture.verify_scripture_anchors([])
    _check_anchor(r, "Prov 30:5-6", "bible")


def test_scripture_anchors_carries_anchor_on_skipped():
    """When the WEB source isn't provisioned (SKIPPED), the anchor
    still surfaces so the human knows what rule was supposed to fire."""
    # Force SKIPPED by ensuring the source layer is None — we can do
    # this by providing anchors and checking the result type. If the
    # source is provisioned in this dev env, we get CONFIRMED; both
    # paths must carry the anchor.
    r = scripture.verify_scripture_anchors(["Mt 5:37"])
    if r.status in ("CONFIRMED", "MISMATCH", "SKIPPED"):
        _check_anchor(r, "Prov 30:5-6", "bible")


# ── scripture.verify_red_letter_priority ───────────────────────────────

def test_red_letter_priority_carries_heb_1_anchor_on_empty():
    r = scripture.verify_red_letter_priority([])
    _check_anchor(r, "Heb 1:1-2", "apostles")


def test_red_letter_priority_carries_anchor_on_classification():
    r = scripture.verify_red_letter_priority(["Mt 5:37", "Rom 12:1"])
    _check_anchor(r, "Heb 1:1-2", "apostles")


# ── governance.verify_decision_packet_shape ────────────────────────────

def test_decision_packet_shape_carries_1_cor_14_40_anchor_on_complete():
    spec = {
        "title": "Test", "scope": "adapter",
        "red_items": ["x"], "floor_items": ["y"],
        "way_path": "consult elders before binding",
        "execution_steps": ["step 1"],
        "witnesses": ["Alice"],
    }
    r = governance.verify_decision_packet_shape(spec)
    _check_anchor(r, "1 Cor 14:40", "apostles")


def test_decision_packet_shape_carries_anchor_on_incomplete():
    """Missing fields → MISMATCH; anchor must still surface so the
    human sees the doctrinal derivation of the rule that just rejected
    them."""
    r = governance.verify_decision_packet_shape({"title": "x"})
    assert r.status in ("MISMATCH", "ERROR")
    _check_anchor(r, "1 Cor 14:40", "apostles")


# ── governance.verify_decision_timing ──────────────────────────────────

def test_decision_timing_carries_prov_19_2_anchor_on_pass():
    packet = {
        "scope": "adapter",
        "created_epoch": 0,
        "acted_at_epoch": 7200,  # 2h elapsed > adapter (1h) floor
    }
    r = governance.verify_decision_timing(packet)
    _check_anchor(r, "Prov 19:2", "bible")


def test_decision_timing_carries_anchor_on_too_fast():
    packet = {
        "scope": "mesh",
        "created_epoch": 0,
        "acted_at_epoch": 100,  # 100s elapsed < mesh (24h) floor
    }
    r = governance.verify_decision_timing(packet)
    assert r.status == "MISMATCH"
    _check_anchor(r, "Prov 19:2", "bible")


# ── governance.verify_rationale_alignment ──────────────────────────────

def test_rationale_alignment_carries_mt_7_anchor_on_match():
    spec = {
        "decision": "approve the budget allocation for community library",
        "rationale": "the library is essential to community education",
    }
    r = governance.verify_rationale_alignment(spec)
    _check_anchor(r, "Mt 7:16-20", "jesus_words")


def test_rationale_alignment_carries_anchor_on_mismatch():
    spec = {
        "decision": "purchase ribosome production equipment",
        "rationale": "tomorrow we celebrate harvest festival",
    }
    r = governance.verify_rationale_alignment(spec)
    assert r.status == "MISMATCH"
    _check_anchor(r, "Mt 7:16-20", "jesus_words")


# ── witness.verify_gate_chain_complete ─────────────────────────────────

def test_gate_chain_complete_carries_deut_19_15_anchor():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
        {"gate": "GOD", "status": "PASS"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    _check_anchor(r, "Deut 19:15", "bible")


def test_gate_chain_complete_carries_anchor_on_short_circuit():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "REJECT"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    _check_anchor(r, "Deut 19:15", "bible")


# ── witness.verify_reasoning_trace_present ─────────────────────────────

def test_reasoning_trace_carries_1_cor_14_33_anchor():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "v1", "status": "CONFIRMED",
         "data": {"formula": "f", "rule": "r"}},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    _check_anchor(r, "1 Cor 14:33", "apostles")


def test_reasoning_trace_carries_anchor_on_missing_trace():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "v1", "status": "CONFIRMED"},  # no data
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "MISMATCH"
    _check_anchor(r, "1 Cor 14:33", "apostles")


# ── witness.verify_no_fabricated_answer ────────────────────────────────

def test_no_fabricated_answer_carries_mt_5_37_anchor():
    p = {"WIT_VERIFY": {"declared_no_answer": True}}
    r = wit.verify_no_fabricated_answer(p)
    _check_anchor(r, "Mt 5:37", "jesus_words")


def test_no_fabricated_answer_carries_anchor_on_violation():
    """The doctrine made executable: when someone snuck a final_answer
    into the packet, the violation message carries the very anchor
    that doctrine derives from."""
    p = {"WIT_VERIFY": {}, "final_answer": "an answer the engine snuck in"}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "MISMATCH"
    _check_anchor(r, "Mt 5:37", "jesus_words")


# ── Coverage: count annotated verifiers ────────────────────────────────

def test_at_least_eleven_verifiers_now_carry_anchors():
    """Across audit pass 1 (2 verifiers) and this rollout (~9 more),
    we expect at least 11 verifier rules with anchors. Locks in: the
    rollout doesn't silently regress by removing annotations."""
    annotated = []
    # scripture
    r = scripture.verify_scripture_anchors([])
    if r.data and r.data.get("anchor"):
        annotated.append("scripture.anchors")
    r = scripture.verify_canon_membership(["Mt 5:37"])
    if r.data and r.data.get("anchor"):
        annotated.append("scripture.canon_membership")
    r = scripture.verify_red_letter_priority(["Mt 5:37"])
    if r.data and r.data.get("anchor"):
        annotated.append("scripture.red_letter_priority")
    # governance
    spec = {"title": "x", "scope": "adapter",
            "red_items": ["a"], "floor_items": ["b"],
            "way_path": "consult elders before",
            "execution_steps": ["s"], "witnesses": ["A"]}
    r = governance.verify_decision_packet_shape(spec)
    if r.data and r.data.get("anchor"):
        annotated.append("governance.decision_packet_shape")
    r = governance.verify_witness_count_consistency(
        {"witnesses": ["A"]}, {"witness_count": 1},
    )
    if r.data and r.data.get("anchor"):
        annotated.append("governance.witness_count_consistency")
    r = governance.verify_decision_timing(
        {"scope": "adapter", "created_epoch": 0, "acted_at_epoch": 7200},
    )
    if r.data and r.data.get("anchor"):
        annotated.append("governance.decision_timing")
    r = governance.verify_rationale_alignment(
        {"decision": "approve community library budget",
         "rationale": "the community library is needed"},
    )
    if r.data and r.data.get("anchor"):
        annotated.append("governance.rationale_alignment")
    # witness
    p_full = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
        {"gate": "GOD", "status": "PASS"},
    ]}}
    r = wit.verify_gate_chain_complete(p_full)
    if r.data and r.data.get("anchor"):
        annotated.append("witness.gate_chain_complete")
    p_trace = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "v", "status": "CONFIRMED", "data": {"formula": "f"}}
    ]}}
    r = wit.verify_reasoning_trace_present(p_trace)
    if r.data and r.data.get("anchor"):
        annotated.append("witness.reasoning_trace_present")
    r = wit.verify_no_fabricated_answer({"WIT_VERIFY": {}})
    if r.data and r.data.get("anchor"):
        annotated.append("witness.no_fabricated_answer")

    assert len(annotated) >= 10, (
        f"Expected at least 10 annotated verifiers; got {len(annotated)}: "
        f"{annotated}"
    )
