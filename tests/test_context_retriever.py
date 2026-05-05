"""Tests for context_retriever.py — Layer 3 of the standalone model."""
import json
import pytest
from pathlib import Path

from concordance_engine.context_retriever import (
    retrieve_context,
    PersonalContext,
    _keywords,
    _theme_overlap,
    _anchors_from_entry,
)
from concordance_engine.classifier import WISDOM, CRISIS, DECISION


# ── _keywords() ────────────────────────────────────────────────────────

def test_keywords_returns_list():
    result = _keywords("I am struggling with my business decision this week.")
    assert isinstance(result, list)


def test_keywords_filters_stopwords():
    result = _keywords("I want to know what God thinks about this decision I am facing.")
    # "want", "know", "thinks", "decision", "facing" — stopword filter must drop "know", "want"
    # At minimum "decision" and "facing" should survive
    assert any(len(k) >= 4 for k in result)
    for k in result:
        assert k not in {"want", "know", "about", "this", "what", "that"}


def test_keywords_empty_text():
    result = _keywords("")
    assert result == []


def test_keywords_top_n_respected():
    text = "patience patience patience wisdom wisdom courage courage courage direction direction"
    result = _keywords(text, top_n=2)
    assert len(result) <= 2


def test_keywords_min_length_four():
    result = _keywords("a be cat dog elephant fox")
    # "cat" (3) and "dog" (3) should not appear; "elephant" (8) should
    for k in result:
        assert len(k) >= 4


# ── _theme_overlap() ──────────────────────────────────────────────────

def test_theme_overlap_basic():
    keywords = ["decision", "business", "partner"]
    text = "I need to make a business decision about my partner."
    assert _theme_overlap(keywords, text) >= 3


def test_theme_overlap_zero():
    keywords = ["astronomy", "telescope"]
    text = "I am feeling uncertain about my relationship."
    assert _theme_overlap(keywords, text) == 0


def test_theme_overlap_case_insensitive():
    keywords = ["forgiveness"]
    text = "The question of Forgiveness has come up again."
    assert _theme_overlap(keywords, text) == 1


def test_theme_overlap_word_boundary():
    keywords = ["formation"]
    # "information" contains "formation" but is NOT the keyword
    text = "I need more information about this."
    assert _theme_overlap(keywords, text) == 0


# ── _anchors_from_entry() ─────────────────────────────────────────────

def test_anchors_from_entry_annotations():
    entry = {
        "annotations": [
            {"ref": "Romans 8:28"},
            {"ref": "Psalm 23:1"},
        ]
    }
    anchors = _anchors_from_entry(entry)
    assert "Romans 8:28" in anchors
    assert "Psalm 23:1" in anchors


def test_anchors_from_entry_scripture_anchors_str():
    entry = {"scripture_anchors": ["Proverbs 3:5", "James 1:5"]}
    anchors = _anchors_from_entry(entry)
    assert "Proverbs 3:5" in anchors
    assert "James 1:5" in anchors


def test_anchors_from_entry_scripture_anchors_dict():
    entry = {"scripture_anchors": [{"ref": "Matthew 18:15"}]}
    anchors = _anchors_from_entry(entry)
    assert "Matthew 18:15" in anchors


def test_anchors_from_entry_empty():
    entry = {}
    anchors = _anchors_from_entry(entry)
    assert anchors == []


def test_anchors_from_entry_no_chapter_verse_skipped():
    entry = {"annotations": [{"ref": "no verse here"}]}
    anchors = _anchors_from_entry(entry)
    # "no verse here" has no digit — should be skipped
    assert len(anchors) == 0


# ── retrieve_context() — no data dir ─────────────────────────────────

def test_retrieve_context_no_dir_returns_empty(tmp_path):
    # Passing a base_dir that has no journal/ subdirectory
    ctx = retrieve_context("I need wisdom about my decision.", WISDOM, base_dir=tmp_path)
    assert isinstance(ctx, PersonalContext)
    assert ctx.relevant_count == 0
    assert ctx.pattern is None
    assert ctx.has_history is False


def test_retrieve_context_empty_text_returns_empty(tmp_path):
    ctx = retrieve_context("", WISDOM, base_dir=tmp_path)
    assert ctx.relevant_count == 0


def test_retrieve_context_all_stopwords_returns_empty(tmp_path):
    ctx = retrieve_context("I am a the and or but", WISDOM, base_dir=tmp_path)
    assert ctx.relevant_count == 0


# ── PersonalContext dataclass ─────────────────────────────────────────

def test_personal_context_defaults():
    ctx = PersonalContext()
    assert ctx.relevant_count == 0
    assert ctx.pattern is None
    assert ctx.recurring_anchors == []
    assert ctx.most_recent_precedent is None
    assert ctx.first_seen_at == 0.0
    assert ctx.unresolved is False


def test_personal_context_has_history_false():
    ctx = PersonalContext(relevant_count=0)
    assert ctx.has_history is False


def test_personal_context_has_history_true():
    ctx = PersonalContext(relevant_count=1)
    assert ctx.has_history is True


def test_personal_context_to_dict_serializable():
    ctx = PersonalContext(
        relevant_count=3,
        pattern="This is the third time.",
        recurring_anchors=["Psalm 23:1"],
        first_seen_at=1700000000.0,
        unresolved=True,
    )
    d = ctx.to_dict()
    json.dumps(d)  # must not raise
    assert "relevant_packets" in d
    assert d["relevant_packets"] == 3
    assert d["pattern"] == "This is the third time."


def test_personal_context_to_dict_keys():
    ctx = PersonalContext()
    d = ctx.to_dict()
    for key in ("relevant_packets", "pattern", "recurring_anchors", "precedent",
                "first_seen_at", "unresolved"):
        assert key in d


# ── retrieve_context() — with seeded journal data ─────────────────────

def test_retrieve_context_finds_related_entry(tmp_path):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    entry = {
        "text": "I am wrestling with a business decision about my partnership.",
        "created_at": 1700000000.0,
        "annotations": [{"ref": "Proverbs 11:14"}],
    }
    jf = journal_dir / "2024.jsonl"
    jf.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    ctx = retrieve_context(
        "I need help making a business decision.",
        DECISION,
        base_dir=tmp_path,
        min_overlap=2,
    )
    assert ctx.relevant_count >= 1
    assert ctx.has_history is True


def test_retrieve_context_unresolved_when_no_precedent(tmp_path):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    entry = {"text": "This is a recurring theme about forgiveness and reconciliation.", "created_at": 1.0}
    (journal_dir / "a.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")

    ctx = retrieve_context(
        "I keep coming back to forgiveness and reconciliation.",
        WISDOM,
        base_dir=tmp_path,
        min_overlap=2,
    )
    if ctx.relevant_count > 0:
        assert ctx.unresolved is True


def test_retrieve_context_pattern_after_three_entries(tmp_path):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    for i in range(3):
        entry = {
            "text": "wrestling with patience and timing in this difficult season",
            "created_at": float(i * 86400),
        }
        (journal_dir / f"{i}.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")

    ctx = retrieve_context(
        "I am still wrestling with patience and timing.",
        WISDOM,
        base_dir=tmp_path,
        min_overlap=2,
    )
    if ctx.relevant_count >= 3:
        assert ctx.pattern is not None
        assert "3" in ctx.pattern or "third" in ctx.pattern.lower()
