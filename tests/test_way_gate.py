"""Tests for the WAY gate — canonical Biblical Alignment Protocol §3.

The Way check sits between FLOOR and BROTHERS. Canonical text:

  "Among lawful options, choose the path that increases obedience,
   humility, and fruit without coercion."

Mechanical implementation (V1):
  - Reads way_path from DECISION_PACKET (governance) or from the
    packet's top-level way_path / way_check fields.
  - Without a way_path declared, gate is structurally NA — passes
    with a note. Non-governance domains aren't required to declare
    a path.
  - With a way_path declared, scans for coercion keywords. Match →
    REJECT with the matched terms surfaced. No match → PASS.

The keyword check is a floor, not a ceiling. Future iterations can
add semantic checks ("does the path mention waiting / consultation /
submission"), but the engine refuses to seal a record whose declared
path is openly coercive.
"""
from __future__ import annotations

from concordance_engine.engine import EngineConfig, validate_and_seal


def _config() -> EngineConfig:
    return EngineConfig(schema_path="", run_verifiers=True)


def _packet_with_way(way_path):
    """Governance packet with a configurable way_path."""
    return {
        "domain": "governance",
        "DECISION_PACKET": {
            "title": "Test decision",
            "scope": "adapter",
            "red_items": ["no theft"],
            "floor_items": ["affirm consent"],
            "way_path": way_path,
            "execution_steps": ["step 1"],
            "witnesses": ["Alice", "Bob"],
        },
        "witness_count": 2,
        "scope": "adapter",
        "created_epoch": 10**9 - 7200,
        "wait_window_seconds": 0,
    }


# ── Gate fires in correct position ─────────────────────────────────────

def test_way_gate_appears_between_floor_and_brothers():
    rec = validate_and_seal(
        _packet_with_way("consult elders, observe a wait window, vote 2/3"),
        now_epoch=10**9, config=_config(),
    )
    gates = [gr.gate for gr in rec.gate_results]
    floor_idx = gates.index("FLOOR")
    way_idx = gates.index("WAY")
    brothers_idx = gates.index("BROTHERS")
    assert floor_idx < way_idx < brothers_idx


def test_way_gate_in_witness_record_for_passing_packet():
    rec = validate_and_seal(
        _packet_with_way("consult elders before binding"),
        now_epoch=10**9, config=_config(),
    )
    way_results = [gr for gr in rec.gate_results if gr.gate == "WAY"]
    assert len(way_results) == 1
    assert way_results[0].status == "PASS"


# ── Clean way_path passes ──────────────────────────────────────────────

def test_clean_way_path_passes():
    rec = validate_and_seal(
        _packet_with_way(
            "consult the elders, observe a 7-day wait window, "
            "and require 2/3 majority"
        ),
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "PASS"


def test_quietly_humble_way_path_passes():
    rec = validate_and_seal(
        _packet_with_way(
            "submit the proposal for review, listen to objections, "
            "and wait for consensus before binding"
        ),
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "PASS"


# ── Coercion keywords trigger REJECT ───────────────────────────────────

def test_force_keyword_rejects():
    rec = validate_and_seal(
        _packet_with_way("force the decision through despite objection"),
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "REJECT"
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"
    assert "force" in str(way.reasons).lower()


def test_compel_keyword_rejects():
    rec = validate_and_seal(
        _packet_with_way("compel the minority to agree"),
        now_epoch=10**9, config=_config(),
    )
    assert rec.overall == "REJECT"
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"


def test_coerce_keyword_rejects_via_top_level_way_path():
    """Governance's RED keyword scan catches 'coerce' before WAY runs
    (defense in depth — multiple gates refuse coercion). To test WAY's
    keyword filter in isolation we use a non-governance domain where
    RED doesn't have the same scanner."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["x"],
            "way_path": "coerce the lab into running unsafe protocols",
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"


def test_silence_dissent_phrase_rejects():
    rec = validate_and_seal(
        _packet_with_way("act first and silence dissent afterward"),
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"


def test_override_keyword_rejects():
    rec = validate_and_seal(
        _packet_with_way("override the standing council"),
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"


# ── Way short-circuits the chain ───────────────────────────────────────

def test_way_reject_short_circuits_before_brothers_god():
    """If WAY rejects, BROTHERS and GOD don't fire — no point checking
    witness count or wait window for a path the engine refuses."""
    rec = validate_and_seal(
        _packet_with_way("force compliance"),
        now_epoch=10**9, config=_config(),
    )
    gates = [gr.gate for gr in rec.gate_results]
    assert "WAY" in gates
    assert "BROTHERS" not in gates
    assert "GOD" not in gates


# ── No way_path is structurally NA ─────────────────────────────────────

def test_no_way_path_is_na_passes():
    """Non-governance domains don't declare way_path. Way check should
    pass with a 'no way_path declared' note rather than rejecting."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["water is H2O"],
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "PASS"
    assert (
        way.details and isinstance(way.details, dict) and
        "no way_path" in (way.details.get("note") or "").lower()
    )


def test_empty_way_path_is_na():
    """Empty way_path on a non-governance packet is treated as no path
    declared — Way gate is structurally NA. (Governance has its own
    minimum-length floor on way_path that fires before WAY.)"""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["x"],
            "way_path": "",
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "PASS"


# ── Top-level way_path also recognized ─────────────────────────────────

def test_top_level_way_path_recognized():
    """Domains that don't use DECISION_PACKET can declare way_path at
    the packet's top level."""
    rec = validate_and_seal(
        {
            "domain": "chemistry",
            "claims": ["x"],
            "way_path": "force the experiment regardless of safety",
            "created_epoch": 10**9 - 7200, "wait_window_seconds": 0,
        },
        now_epoch=10**9, config=_config(),
    )
    way = next(gr for gr in rec.gate_results if gr.gate == "WAY")
    assert way.status == "REJECT"


# ── Walkthrough surfaces the Way verdict ───────────────────────────────

def test_walkthrough_shows_way_check_label():
    from concordance_engine.walkthrough import render_walkthrough
    rec = validate_and_seal(
        _packet_with_way("consult elders before binding"),
        now_epoch=10**9, config=_config(),
    )
    md = render_walkthrough(rec)
    # The gate's full label should appear in the walkthrough
    assert "WAY" in md
    assert "Way check" in md or "path without coercion" in md
