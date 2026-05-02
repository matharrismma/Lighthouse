"""Tests for the Socratic walkthrough renderer.

Locks in the doctrinal commitments at the rendering boundary:
  * No `final_answer` / `answer` line ever appears in the output.
  * The walkthrough always ends with a question, not a conclusion.
  * Anchors display their `layer`.
  * No-precedent renders explicitly, never invented.
  * REJECT / QUARANTINE branches don't render misleading sections.
"""
from __future__ import annotations

from concordance_engine.gates import ok, quarantine, reject
from concordance_engine.verifiers.base import confirm, mismatch, na
from concordance_engine.walkthrough import render_walkthrough
from concordance_engine.witness_record import (
    Anchor, AxisCoordinates, ClosestCase, WitnessRecord, axis_coords_for,
)


def _pass_record(**overrides) -> WitnessRecord:
    base = dict(
        overall="PASS",
        gate_results=(
            ok("RED", {"verified": ["math.equality: 2+2=4"]}),
            ok("FLOOR"),
            ok("BROTHERS", {"witnesses": 2, "required": 2}),
            ok("GOD", {"elapsed": 86401, "required": 86400}),
        ),
        verifier_results=(
            confirm("math.equality", "matches", {"formula": "a + b = c"}),
        ),
        anchors=(
            Anchor(ref="Mt 5:37", layer="jesus_words",
                   text="Let your yes be yes"),
        ),
        axis_coords=axis_coords_for("mathematics"),
        closest_case=ClosestCase(
            precedent_id="ledger://precedent/p/1",
            shared_dimensions=frozenset({"reasoning"}),
            distance=0.13,
        ),
        packet_id="pkt://test/pass/1",
    )
    base.update(overrides)
    return WitnessRecord(**base)


# ── Doctrinal invariants ───────────────────────────────────────────────

def test_walkthrough_never_contains_answer_field():
    """The doctrine made executable at the rendering boundary: the
    walkthrough must not display a final_answer / answer / verdict
    section, no matter what the record contains."""
    md = render_walkthrough(_pass_record())
    forbidden = ("final_answer", "Final Answer", "The Answer:",
                 "Engine Answer", "engine_answer", "Verdict:")
    for word in forbidden:
        assert word not in md, f"walkthrough contained forbidden phrase {word!r}"


def test_walkthrough_ends_with_question():
    """The closing section is always a question, regardless of the
    overall verdict."""
    for overall in ("PASS", "REJECT", "QUARANTINE"):
        if overall == "PASS":
            rec = _pass_record()
        elif overall == "REJECT":
            rec = _pass_record(
                overall="REJECT",
                gate_results=(reject("RED", "no claims"),),
                verifier_results=(),
                closest_case=None,
            )
        else:
            rec = _pass_record(
                overall="QUARANTINE",
                gate_results=(
                    ok("RED"), ok("FLOOR"),
                    quarantine("BROTHERS", "witnesses 1/2"),
                ),
                closest_case=None,
            )
        md = render_walkthrough(rec)
        assert "The Socratic question" in md, f"missing Socratic close for {overall}"
        assert "?" in md.split("The Socratic question")[1], (
            f"Socratic close had no question mark for {overall}"
        )


# ── Headline + framing ─────────────────────────────────────────────────

def test_walkthrough_headline_marks_pass():
    md = render_walkthrough(_pass_record())
    assert "Witness Record" in md
    assert "PASSED through all four gates" in md
    assert "pkt://test/pass/1" in md


def test_walkthrough_headline_marks_reject():
    rec = _pass_record(overall="REJECT", closest_case=None)
    md = render_walkthrough(rec)
    assert "REJECTED" in md


def test_walkthrough_headline_marks_quarantine():
    rec = _pass_record(overall="QUARANTINE", closest_case=None)
    md = render_walkthrough(rec)
    assert "QUARANTINE" in md


# ── Scaffold ───────────────────────────────────────────────────────────

def test_walkthrough_scaffold_section_lists_dimensions():
    md = render_walkthrough(_pass_record())
    assert "scaffold" in md.lower()
    # mathematics sits on reasoning
    assert "reasoning" in md


def test_walkthrough_scaffold_omitted_when_axis_coords_none():
    rec = _pass_record(axis_coords=None)
    md = render_walkthrough(rec)
    # No scaffold section when we don't know where it sits.
    assert "Where this sits on the scaffold" not in md


def test_walkthrough_scaffold_shows_umbrella_for_subsystem():
    rec = _pass_record(axis_coords=axis_coords_for("genetics"))
    md = render_walkthrough(rec)
    assert "subsystem of the **biology**" in md


def test_walkthrough_scaffold_shows_neighbors():
    rec = _pass_record(axis_coords=axis_coords_for("witness"))
    md = render_walkthrough(rec)
    # witness shares 4 dimensions with scripture — scripture should
    # appear as a neighbor.
    assert "scripture" in md.lower()


# ── Gates ──────────────────────────────────────────────────────────────

def test_walkthrough_gates_section_lists_all_four_for_pass():
    md = render_walkthrough(_pass_record())
    assert "RED" in md and "FLOOR" in md and "BROTHERS" in md and "GOD" in md


def test_walkthrough_gates_section_truncates_for_reject():
    """REJECT at RED means later gates didn't fire — they shouldn't
    appear as if they did."""
    rec = _pass_record(
        overall="REJECT",
        gate_results=(reject("RED", "missing claims"),),
        verifier_results=(),
        closest_case=None,
    )
    md = render_walkthrough(rec)
    assert "RED" in md
    # "GOD" can appear in stock phrases; check the gate section header
    # specifically isn't present.
    assert "GOD — wait window" not in md


def test_walkthrough_gates_collapse_consecutive_same_gate_verdicts():
    """The engine emits two RED verdicts on the PASS path: one from the
    domain validator, one from the verifier dispatch step. The renderer
    must collapse them into one section, not number them as two.
    Regression test: pre-fix, the same gate appeared twice."""
    rec = _pass_record(gate_results=(
        ok("RED"),
        ok("RED", {"verified": ["math.equality: 2+2=4"]}),
        ok("FLOOR"),
        ok("BROTHERS"),
        ok("GOD"),
    ))
    md = render_walkthrough(rec)
    # Section numbering should produce 1. RED, 2. FLOOR, 3. BROTHERS, 4. GOD.
    # Not 1. RED, 2. RED, 3. FLOOR, ...
    assert "1. RED" in md
    assert "2. FLOOR" in md
    assert "3. BROTHERS" in md
    assert "4. GOD" in md
    # Make sure we didn't end up with "5." anywhere — only four logical
    # gate sections.
    assert "5. " not in md


def test_walkthrough_gates_collapse_takes_worst_status():
    """If the same gate has both a PASS and a REJECT verdict, the
    collapsed section must show REJECT (worst status wins for the
    headline). Otherwise we'd hide a real failure."""
    rec = _pass_record(
        overall="REJECT",
        gate_results=(
            ok("RED"),
            reject("RED", "verifier disagreed with claim"),
        ),
        verifier_results=(),
        closest_case=None,
    )
    md = render_walkthrough(rec)
    assert "[REJECT]" in md
    assert "verifier disagreed with claim" in md


def test_walkthrough_gates_render_quarantine_status():
    rec = _pass_record(
        overall="QUARANTINE",
        gate_results=(
            ok("RED"), ok("FLOOR"),
            quarantine("BROTHERS", "witnesses 1/2"),
        ),
        closest_case=None,
    )
    md = render_walkthrough(rec)
    assert "[QUARANTINE]" in md
    assert "witnesses 1/2" in md


# ── Verifier table ─────────────────────────────────────────────────────

def test_walkthrough_verifier_table_lists_each_verifier():
    rec = _pass_record(verifier_results=(
        confirm("math.equality", "matches", {"formula": "a + b = c"}),
        mismatch("math.derivative", "wrong", {"rule": "d/dx"}),
        na("scripture.anchors"),
    ))
    md = render_walkthrough(rec)
    assert "math.equality" in md
    assert "math.derivative" in md
    assert "scripture.anchors" in md
    assert "[OK]" in md
    assert "[MISMATCH]" in md
    assert "[N/A]" in md


def test_walkthrough_verifier_table_omitted_when_no_verifiers():
    rec = _pass_record(verifier_results=())
    md = render_walkthrough(rec)
    assert "What the verifiers actually checked" not in md


def test_walkthrough_verifier_table_escapes_pipes_in_rules():
    rec = _pass_record(verifier_results=(
        confirm("test.foo", "ok", {"rule": "a | b means OR"}),
    ))
    md = render_walkthrough(rec)
    # Pipe characters in the rule must be escaped so the markdown table
    # doesn't break.
    assert "a \\| b" in md


# ── Anchors ────────────────────────────────────────────────────────────

def test_walkthrough_anchors_show_layer():
    md = render_walkthrough(_pass_record())
    # Mt 5:37 is jesus_words — the layer label should appear.
    assert "jesus_words" in md
    assert "primary" in md  # the human-readable hint


def test_walkthrough_anchors_show_text_when_present():
    md = render_walkthrough(_pass_record())
    assert "Let your yes be yes" in md


def test_walkthrough_anchors_omitted_when_empty():
    rec = _pass_record(anchors=())
    md = render_walkthrough(rec)
    assert "Citations and their authority layer" not in md


def test_walkthrough_all_jesus_words_anchors_get_quiet_confidence_note():
    """When every anchor is primary-tier, the renderer surfaces that
    fact — humans skim the layer column quickly otherwise."""
    md = render_walkthrough(_pass_record(anchors=(
        Anchor(ref="Mt 5:37", layer="jesus_words"),
        Anchor(ref="Lk 17:3-4", layer="jesus_words"),
    )))
    assert "All citations carry primary-tier authority" in md


def test_walkthrough_mixed_layer_anchors_no_quiet_note():
    md = render_walkthrough(_pass_record(anchors=(
        Anchor(ref="Mt 5:37", layer="jesus_words"),
        Anchor(ref="Rom 12:1", layer="apostles"),
    )))
    assert "All citations carry primary-tier authority" not in md


# ── Closest case ───────────────────────────────────────────────────────

def test_walkthrough_closest_case_renders_precedent_id():
    md = render_walkthrough(_pass_record())
    assert "ledger://precedent/p/1" in md


def test_walkthrough_closest_case_omitted_when_none():
    rec = _pass_record(closest_case=None)
    md = render_walkthrough(rec)
    assert "The closest precedent we found" not in md


def test_walkthrough_closest_case_explicit_no_precedent():
    """A lookup that found nothing renders explicitly — never invented."""
    rec = _pass_record(closest_case=ClosestCase(precedent_id=None))
    md = render_walkthrough(rec)
    assert "The closest precedent we found" in md
    assert "No comparable precedent was found" in md


def test_walkthrough_closest_case_renders_reasoning_overlay():
    rec = _pass_record(closest_case=ClosestCase(
        precedent_id="ledger://p/2",
        shared_dimensions=frozenset({"reasoning"}),
        reasoning_overlay={
            "step_1": "Confession witnessed by 2+ members",
            "step_2": "Active restitution",
        },
    ))
    md = render_walkthrough(rec)
    assert "Confession witnessed by 2+ members" in md
    assert "Active restitution" in md


# ── End-to-end sanity ──────────────────────────────────────────────────

def test_walkthrough_returns_str():
    md = render_walkthrough(_pass_record())
    assert isinstance(md, str)
    assert len(md) > 100  # not a stub


def test_walkthrough_minimal_record_renders_without_crashing():
    """Lowest-information record: REJECT at RED with no domain."""
    rec = WitnessRecord(
        overall="REJECT",
        gate_results=(reject("RED", "empty packet"),),
        verifier_results=(),
    )
    md = render_walkthrough(rec)
    assert "REJECTED" in md
    assert "?" in md  # Socratic close still renders
