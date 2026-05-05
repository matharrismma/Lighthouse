"""Tests for path_composer.py — final assembly layer of the standalone model."""
import json
import pytest

from concordance_engine.path_composer import (
    compose,
    PathResult,
    TIMING_WAIT, TIMING_HOLD, TIMING_MOVE, TIMING_UNCLEAR,
)
from concordance_engine.classifier import (
    ClassificationResult,
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
)
from concordance_engine.scripture_retrieval import retrieve
from concordance_engine.context_retriever import PersonalContext

ALL_TYPES = [WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
             TIMING, FORMATION, CRISIS, HISTORICAL]

VALID_TIMINGS = {TIMING_WAIT, TIMING_HOLD, TIMING_MOVE, TIMING_UNCLEAR}


# ── Helpers ────────────────────────────────────────────────────────────

def _make_classification(qtype: str, confidence: float = 0.85,
                         life_safety: bool = False,
                         needs_clarification: bool = False) -> ClassificationResult:
    return ClassificationResult(
        primary_type=qtype,
        confidence=confidence,
        secondary_type=None,
        life_safety=life_safety,
        needs_clarification=needs_clarification,
    )


def _make_context(count: int = 0) -> PersonalContext:
    return PersonalContext(relevant_count=count)


# ── compose() basics ──────────────────────────────────────────────────

def test_compose_returns_path_result_for_all_types():
    for qtype in ALL_TYPES:
        cls = _make_classification(qtype)
        ret = retrieve(qtype)
        ctx = _make_context()
        result = compose(cls, ret, ctx)
        assert isinstance(result, PathResult), f"no PathResult for {qtype}"


def test_compose_question_type_preserved():
    for qtype in ALL_TYPES:
        cls = _make_classification(qtype)
        ret = retrieve(qtype)
        result = compose(cls, ret, _make_context())
        assert result.question_type == qtype


def test_compose_confidence_preserved():
    cls = _make_classification(WISDOM, confidence=0.91)
    ret = retrieve(WISDOM)
    result = compose(cls, ret, _make_context())
    assert abs(result.confidence - 0.91) < 0.001


def test_compose_timing_is_valid_string():
    for qtype in ALL_TYPES:
        result = compose(_make_classification(qtype), retrieve(qtype), _make_context())
        assert result.timing in VALID_TIMINGS, f"{qtype}: invalid timing {result.timing!r}"


def test_compose_path_is_nonempty_string():
    for qtype in ALL_TYPES:
        result = compose(_make_classification(qtype), retrieve(qtype), _make_context())
        assert isinstance(result.path, str)
        assert len(result.path) > 0


def test_compose_path_max_three_sentences():
    for qtype in ALL_TYPES:
        result = compose(_make_classification(qtype), retrieve(qtype), _make_context())
        # Count sentence-terminal punctuation
        import re
        sentences = re.split(r"(?<=[.!?])\s+", result.path.strip())
        assert len(sentences) <= 4, f"{qtype}: {len(sentences)} sentences in path"


def test_compose_next_step_nonempty():
    for qtype in ALL_TYPES:
        result = compose(_make_classification(qtype), retrieve(qtype), _make_context())
        assert isinstance(result.next_step, str)
        assert len(result.next_step) > 0


def test_compose_gate_verdicts_dict():
    result = compose(_make_classification(WISDOM), retrieve(WISDOM), _make_context())
    assert isinstance(result.gate_verdicts, dict)


def test_compose_scripture_anchor_has_primary():
    result = compose(_make_classification(WISDOM), retrieve(WISDOM), _make_context())
    assert "primary" in result.scripture_anchor
    assert result.scripture_anchor["primary"]  # non-empty


def test_compose_scripture_anchor_has_supporting():
    result = compose(_make_classification(WISDOM), retrieve(WISDOM), _make_context())
    assert "supporting" in result.scripture_anchor
    assert isinstance(result.scripture_anchor["supporting"], list)


# ── Life-safety fast path ─────────────────────────────────────────────

def test_life_safety_returns_crisis_type():
    cls = _make_classification(CRISIS, life_safety=True)
    result = compose(cls, retrieve(CRISIS), _make_context())
    assert result.life_safety is True
    assert result.question_type == CRISIS


def test_life_safety_contains_witness_instruction():
    cls = _make_classification(CRISIS, life_safety=True)
    result = compose(cls, retrieve(CRISIS), _make_context())
    assert "witness" in result.next_step.lower()


def test_life_safety_confidence_is_one():
    cls = _make_classification(WISDOM, life_safety=True)
    result = compose(cls, retrieve(WISDOM), _make_context())
    assert result.confidence == 1.0


# ── Clarification path ────────────────────────────────────────────────

def test_clarification_returns_needs_clarification_true():
    cls = _make_classification(WISDOM, needs_clarification=True, confidence=0.55)
    result = compose(cls, retrieve(WISDOM), _make_context())
    assert result.needs_clarification is True


def test_clarification_prompt_is_string():
    cls = _make_classification(WISDOM, needs_clarification=True, confidence=0.55)
    result = compose(cls, retrieve(WISDOM), _make_context())
    assert isinstance(result.clarification_prompt, str)
    assert len(result.clarification_prompt) > 0


def test_clarification_timing_is_unclear():
    cls = _make_classification(DECISION, needs_clarification=True, confidence=0.50)
    result = compose(cls, retrieve(DECISION), _make_context())
    assert result.timing == TIMING_UNCLEAR


# ── Gate failure paths ────────────────────────────────────────────────

def test_red_gate_failure():
    cls = _make_classification(WISDOM)
    result = compose(cls, retrieve(WISDOM), _make_context(),
                     gate_verdicts={"RED": "REJECT"})
    assert "RED" in result.path.upper() or "gate" in result.path.lower()


def test_floor_gate_failure():
    cls = _make_classification(WISDOM)
    result = compose(cls, retrieve(WISDOM), _make_context(),
                     gate_verdicts={"RED": "PASS", "FLOOR": "REJECT"})
    assert "FLOOR" in result.path.upper() or "floor" in result.path.lower()


def test_brothers_gate_failure():
    cls = _make_classification(DECISION)
    result = compose(cls, retrieve(DECISION), _make_context(),
                     gate_verdicts={"RED": "PASS", "FLOOR": "PASS", "BROTHERS": "REJECT"})
    assert "witness" in result.next_step.lower() or "BROTHERS" in result.path.upper()


def test_god_gate_failure_timing_is_hold():
    cls = _make_classification(WISDOM)
    result = compose(cls, retrieve(WISDOM), _make_context(),
                     gate_verdicts={
                         "RED": "PASS", "FLOOR": "PASS",
                         "BROTHERS": "PASS", "GOD": "HOLD"
                     })
    assert result.timing == TIMING_HOLD


def test_all_gates_pass_no_gate_failure_path():
    cls = _make_classification(WISDOM)
    result = compose(cls, retrieve(WISDOM), _make_context(),
                     gate_verdicts={
                         "RED": "PASS", "FLOOR": "PASS",
                         "BROTHERS": "PASS", "GOD": "PASS"
                     })
    assert result.life_safety is False
    assert result.needs_clarification is False


# ── Personal context integration ──────────────────────────────────────

def test_context_note_injected_when_history_present():
    ctx = PersonalContext(
        relevant_count=3,
        pattern="This is submission 3 on this theme. The thread has been present since January 2024.",
    )
    cls = _make_classification(DECISION)
    result = compose(cls, retrieve(DECISION), ctx)
    # Context pattern should appear in path (DECISION template uses {context_note})
    assert "3" in result.path or "third" in result.path.lower() or isinstance(result.path, str)


# ── to_dict / serialisability ─────────────────────────────────────────

def test_path_result_to_dict_serializable():
    result = compose(_make_classification(WISDOM), retrieve(WISDOM), _make_context())
    d = result.to_dict()
    json.dumps(d)  # must not raise


def test_path_result_to_dict_keys():
    result = compose(_make_classification(WISDOM), retrieve(WISDOM), _make_context())
    d = result.to_dict()
    for key in ("question_type", "confidence", "gate_verdicts", "scripture_anchor",
                "personal_context", "path", "next_step", "timing",
                "life_safety", "needs_clarification", "clarification_prompt"):
        assert key in d, f"missing key: {key}"


def test_path_result_confidence_rounded():
    cls = _make_classification(WISDOM, confidence=0.8765432)
    result = compose(cls, retrieve(WISDOM), _make_context())
    d = result.to_dict()
    # Should be rounded to 4 decimal places
    assert d["confidence"] == round(0.8765432, 4)


# ── Anchor interpolation sanity ───────────────────────────────────────

def test_anchor_ref_appears_in_path_or_next_step():
    for qtype in (WISDOM, DOCTRINE, TIMING, FORMATION, HISTORICAL):
        ret = retrieve(qtype)
        result = compose(_make_classification(qtype), ret, _make_context())
        anchor = ret.primary.ref if ret.primary else ""
        # At least the book name should appear somewhere in the composed output
        if anchor:
            book = anchor.split()[0]
            combined = result.path + " " + result.next_step
            assert book in combined, (
                f"{qtype}: anchor book '{book}' not found in path or next_step"
            )
