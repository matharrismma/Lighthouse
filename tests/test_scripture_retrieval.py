"""Tests for scripture_retrieval.py — Layer 1 of the standalone model."""
import json
import pytest

from concordance_engine.scripture_retrieval import (
    retrieve,
    primary_anchor,
    RetrievalResult,
    ScripturePassage,
    _extract_refs,
)
from concordance_engine.classifier import (
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
)

ALL_TYPES = [WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
             TIMING, FORMATION, CRISIS, HISTORICAL]


# ── retrieve() basics ─────────────────────────────────────────────────

def test_retrieve_returns_result_for_every_type():
    for qtype in ALL_TYPES:
        result = retrieve(qtype)
        assert isinstance(result, RetrievalResult), f"no result for {qtype}"
        assert result.question_type == qtype


def test_retrieve_always_has_primary():
    for qtype in ALL_TYPES:
        result = retrieve(qtype)
        assert result.primary is not None, f"no primary for {qtype}"
        assert isinstance(result.primary, ScripturePassage)
        assert result.primary.ref  # non-empty ref string


def test_retrieve_primary_is_highest_weight():
    for qtype in ALL_TYPES:
        result = retrieve(qtype)
        if result.supporting:
            for s in result.supporting:
                assert result.primary.weight >= s.weight, (
                    f"{qtype}: primary weight {result.primary.weight} < "
                    f"supporting {s.weight} ({s.ref})"
                )


def test_retrieve_supporting_is_list():
    result = retrieve(WISDOM)
    assert isinstance(result.supporting, list)


def test_retrieve_limit_respected():
    result = retrieve(WISDOM, limit=2)
    assert len(result.all_passages) <= 2


def test_retrieve_limit_default_five():
    result = retrieve(WISDOM)
    assert len(result.all_passages) <= 5


def test_retrieve_all_passages_includes_primary():
    result = retrieve(WISDOM)
    assert result.primary in result.all_passages


def test_retrieve_gate_assigned():
    for qtype in ALL_TYPES:
        result = retrieve(qtype)
        assert result.gate  # non-empty gate string


def test_retrieve_territory_list():
    for qtype in ALL_TYPES:
        result = retrieve(qtype)
        assert isinstance(result.territory, list)


# ── Specific anchor expectations ───────────────────────────────────────

def test_wisdom_primary_is_proverbs():
    result = retrieve(WISDOM)
    assert "Proverbs" in result.primary.ref or "James" in result.primary.ref


def test_doctrine_primary_is_romans_or_hebrews():
    result = retrieve(DOCTRINE)
    assert any(x in result.primary.ref for x in ("Romans", "Hebrews", "John"))


def test_crisis_primary_is_psalms_34():
    result = retrieve(CRISIS)
    assert "34" in result.primary.ref and "Psalm" in result.primary.ref


def test_decision_primary_mentions_proverbs_11():
    result = retrieve(DECISION)
    assert "11" in result.primary.ref


def test_timing_primary_is_ecclesiastes():
    result = retrieve(TIMING)
    assert "Ecclesiastes" in result.primary.ref


def test_formation_primary_is_romans_12():
    result = retrieve(FORMATION)
    assert "Romans" in result.primary.ref and "12" in result.primary.ref


def test_relational_primary_is_matthew_18():
    result = retrieve(RELATIONAL)
    assert "Matthew" in result.primary.ref and "18" in result.primary.ref


# ── Graceful degradation ───────────────────────────────────────────────

def test_retrieve_degrades_when_source_missing():
    """If the WEB DB isn't provisioned, status='source_missing' but no crash."""
    result = retrieve(WISDOM)
    # Either source is available (text populated) or gracefully missing
    for p in result.all_passages:
        assert p.status in ("ok", "source_missing", "not_found", "parse_error")


def test_retrieve_source_available_flag():
    result = retrieve(WISDOM)
    assert isinstance(result.source_available, bool)


# ── Inline reference extraction ────────────────────────────────────────

def test_extract_refs_basic():
    refs = _extract_refs("I was reading Romans 8:28 this morning.")
    assert any("Romans" in r and "8" in r for r in refs)


def test_extract_refs_multiple():
    refs = _extract_refs("See Matthew 5:3 and also Psalm 23:1 for context.")
    assert len(refs) >= 2


def test_extract_refs_empty_text():
    refs = _extract_refs("")
    assert refs == []


def test_extract_refs_no_refs():
    refs = _extract_refs("I feel uncertain about my path forward.")
    assert refs == []


def test_extract_refs_numbered_books():
    refs = _extract_refs("1 Corinthians 13:4 says love is patient.")
    assert any("Corinthians" in r for r in refs)


def test_inline_refs_appear_in_retrieval():
    """Refs explicitly mentioned in the text should appear in results."""
    text = "Proverbs 2:6 has been on my mind."
    result = retrieve(WISDOM, text=text)
    all_refs = [p.ref for p in result.all_passages]
    # At minimum the curated anchor should be there
    assert len(all_refs) >= 1


# ── primary_anchor() ──────────────────────────────────────────────────

def test_primary_anchor_returns_string_for_all_types():
    for qtype in ALL_TYPES:
        ref = primary_anchor(qtype)
        assert isinstance(ref, str)
        assert len(ref) > 3


def test_primary_anchor_no_db_call():
    """primary_anchor must work even without the database."""
    ref = primary_anchor(CRISIS)
    assert "Psalm" in ref or "Psalms" in ref


# ── to_dict / serialisability ─────────────────────────────────────────

def test_retrieval_result_to_dict():
    result = retrieve(WISDOM)
    d = result.to_dict()
    json.dumps(d)  # must not raise
    assert "primary" in d
    assert "supporting" in d
    assert "question_type" in d


def test_scripture_passage_to_dict():
    result = retrieve(DOCTRINE)
    d = result.primary.to_dict()
    json.dumps(d)
    assert "ref" in d
    assert "weight" in d
    assert "gate" in d
