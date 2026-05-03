"""Tests for the witness verifier — the 36th axis, key to the gate."""
from __future__ import annotations

from concordance_engine.verifiers import witness as wit


# ── witness.gate_chain_complete ────────────────────────────────────────

def test_gate_chain_all_four_pass():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
        {"gate": "GOD", "status": "PASS"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "CONFIRMED"


def test_gate_chain_short_circuit_at_red_reject():
    # RED REJECT legitimately ends the chain — later gates absent is fine.
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "REJECT"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "CONFIRMED"
    assert r.data["short_circuit_at_gate"] == "RED"


def test_gate_chain_short_circuit_at_brothers_quarantine():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "BROTHERS", "status": "QUARANTINE"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "CONFIRMED"
    assert r.data["short_circuit_at_gate"] == "BROTHERS"


def test_gate_chain_missing_god_after_all_pass():
    # All passing but GOD is absent — that's a real gap, not a short-circuit.
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "MISMATCH"
    assert "GOD" in r.data["missing"]


def test_gate_chain_invalid_status_errors():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED", "status": "MAYBE"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "ERROR"


def test_gate_chain_missing_status_errors():
    p = {"WIT_VERIFY": {"claimed_gate_verdicts": [
        {"gate": "RED"},
    ]}}
    r = wit.verify_gate_chain_complete(p)
    assert r.status == "ERROR"


def test_gate_chain_no_verdicts_returns_na():
    r = wit.verify_gate_chain_complete({"WIT_VERIFY": {}})
    assert r.status == "NOT_APPLICABLE"


# ── witness.reasoning_trace_present ────────────────────────────────────

def test_trace_all_results_have_data_with_formula():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "math.equality", "status": "CONFIRMED",
         "data": {"formula": "a + b = c", "rule": "..."}},
        {"name": "physics.dim", "status": "MISMATCH",
         "data": {"formula": "F = ma"}},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "CONFIRMED"


def test_trace_na_and_error_results_dont_need_trace():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "x", "status": "NOT_APPLICABLE"},
        {"name": "y", "status": "ERROR", "message": "bad input"},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "CONFIRMED"


def test_trace_confirmed_without_data_mismatches():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "math.equality", "status": "CONFIRMED"},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "MISMATCH"
    assert any(u["name"] == "math.equality" for u in r.data["untraced"])


def test_trace_mismatch_with_data_lacking_formula_or_rule():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "x", "status": "MISMATCH", "data": {"unrelated": 1}},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "MISMATCH"


def test_trace_empty_data_block_mismatches():
    p = {"WIT_VERIFY": {"claimed_verifier_results": [
        {"name": "x", "status": "CONFIRMED", "data": {}},
    ]}}
    r = wit.verify_reasoning_trace_present(p)
    assert r.status == "MISMATCH"


# ── witness.anchors_resolve ────────────────────────────────────────────

def test_anchors_all_resolve_to_hierarchy():
    p = {"WIT_VERIFY": {"claimed_anchors": [
        {"ref": "Mat 5:37", "layer": "jesus_words"},
        {"ref": "Rom 12:1", "layer": "apostles"},
        {"ref": "Gen 1:1", "layer": "bible"},
    ]}}
    r = wit.verify_anchors_resolve(p)
    assert r.status == "CONFIRMED"


def test_anchors_unknown_layer_mismatches():
    p = {"WIT_VERIFY": {"claimed_anchors": [
        {"ref": "Some Quote", "layer": "wikipedia"},
    ]}}
    r = wit.verify_anchors_resolve(p)
    assert r.status == "MISMATCH"


def test_anchors_missing_layer_mismatches():
    p = {"WIT_VERIFY": {"claimed_anchors": [
        {"ref": "Mat 5:37"},  # no layer
    ]}}
    r = wit.verify_anchors_resolve(p)
    assert r.status == "MISMATCH"


def test_anchors_recognized_elders_layer_passes():
    p = {"WIT_VERIFY": {"claimed_anchors": [
        {"ref": "Augustine, On Christian Teaching", "layer": "recognized_elders"},
    ]}}
    r = wit.verify_anchors_resolve(p)
    assert r.status == "CONFIRMED"


def test_anchors_empty_list_confirms():
    # Zero anchors is valid — not every packet needs one.
    p = {"WIT_VERIFY": {"claimed_anchors": []}}
    r = wit.verify_anchors_resolve(p)
    assert r.status == "CONFIRMED"


# ── witness.no_fabricated_answer ───────────────────────────────────────

def test_no_fabricated_answer_clean_packet():
    p = {"WIT_VERIFY": {"declared_no_answer": True}, "domain": "witness"}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "CONFIRMED"


def test_no_fabricated_answer_final_answer_field_present_mismatches():
    p = {"WIT_VERIFY": {}, "final_answer": "the answer is 42"}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "MISMATCH"
    assert "final_answer" in r.data["fabricated_fields_present"]


def test_no_fabricated_answer_answer_field_present_mismatches():
    p = {"WIT_VERIFY": {}, "answer": "yes"}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "MISMATCH"


def test_no_fabricated_answer_empty_answer_field_passes():
    # An empty/null field doesn't count as a fabricated answer.
    p = {"WIT_VERIFY": {}, "final_answer": None}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "CONFIRMED"


def test_no_fabricated_answer_engine_answer_field_caught():
    p = {"WIT_VERIFY": {}, "engine_answer": "computed"}
    r = wit.verify_no_fabricated_answer(p)
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_run_dispatches_all_checks():
    """Witness now runs 5 checks when the full WIT_VERIFY block is
    present: gate_chain, reasoning_trace, rule_anchors_resolve,
    anchors_resolve, and no_fabricated_answer. The rule_anchors check
    is opt-in — it runs whenever claimed_verifier_results is present
    but reports NA when no verifier rule has declared an anchor."""
    p = {
        "domain": "witness",
        "WIT_VERIFY": {
            "claimed_gate_verdicts": [
                {"gate": "RED", "status": "PASS"},
                {"gate": "FLOOR", "status": "PASS"},
                {"gate": "BROTHERS", "status": "PASS"},
                {"gate": "GOD", "status": "PASS"},
            ],
            "claimed_verifier_results": [
                {"name": "math.equality", "status": "CONFIRMED",
                 "data": {"formula": "a + b = c"}},
            ],
            "claimed_anchors": [
                {"ref": "Mat 5:37", "layer": "jesus_words"},
            ],
            "declared_no_answer": True,
        },
    }
    results = wit.run(p)
    assert len(results) == 5
    statuses = {r.name: r.status for r in results}
    # Four of five should CONFIRM; the rule_anchors check is NA when
    # no rule declared an anchor.
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.reasoning_trace_present"] == "CONFIRMED"
    assert statuses["witness.rule_anchors_resolve"] == "NOT_APPLICABLE"
    assert statuses["witness.anchors_resolve"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "CONFIRMED"


def test_run_full_record_with_short_circuit_red_reject():
    # Realistic shape: a packet that REJECTed at RED. Gate chain should
    # confirm via short-circuit; trace check is NA-style (no verifier
    # results were produced); no answer present.
    p = {
        "domain": "witness",
        "WIT_VERIFY": {
            "claimed_gate_verdicts": [
                {"gate": "RED", "status": "REJECT"},
            ],
            "declared_no_answer": True,
        },
    }
    results = wit.run(p)
    assert len(results) == 2
    statuses = {r.name: r.status for r in results}
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "CONFIRMED"


def test_run_no_artifacts_returns_na():
    results = wit.run({"domain": "witness"})
    assert len(results) == 1 and results[0].status == "NOT_APPLICABLE"


def test_run_catches_fabricated_answer_even_when_other_checks_pass():
    p = {
        "domain": "witness",
        "WIT_VERIFY": {
            "claimed_gate_verdicts": [
                {"gate": "RED", "status": "PASS"},
                {"gate": "FLOOR", "status": "PASS"},
                {"gate": "BROTHERS", "status": "PASS"},
                {"gate": "GOD", "status": "PASS"},
            ],
        },
        "final_answer": "engine snuck this in",
    }
    results = wit.run(p)
    statuses = {r.name: r.status for r in results}
    assert statuses["witness.gate_chain_complete"] == "CONFIRMED"
    assert statuses["witness.no_fabricated_answer"] == "MISMATCH"
