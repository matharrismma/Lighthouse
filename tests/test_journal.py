"""Tests for the journal — the calibration tool for humans.

Per Matt 2026-05-03: "It's a calibration tool for humans." Stream of
consciousness in. Calibration out. Nothing replaces what the user
wrote. Each calibration measurement is descriptive, never
prescriptive.
"""
from __future__ import annotations

import json
import time

import pytest

from concordance_engine.journal import (
    Annotation,
    Calibration,
    Categorization,
    JournalEntry,
    JournalStore,
    annotate,
    calibrate,
    capture,
    categorize,
    render_calibration,
    thread,
)


# ── categorize (pure function) ───────────────────────────────────────


def test_categorize_empty_returns_empty():
    cat = categorize("")
    assert cat.detected_anchors == []
    assert cat.detected_action_shapes == []
    assert cat.detected_scope is None


def test_categorize_detects_scripture_refs():
    cat = categorize("I keep coming back to Mt 5:37 and Prov 30:5.")
    assert "Mt 5:37" in cat.detected_anchors
    assert "Prov 30:5" in cat.detected_anchors


def test_categorize_detects_action_shapes():
    cat = categorize("I want to build something but maybe I should hold and wait.")
    assert "Build" in cat.detected_action_shapes
    assert "Hold" in cat.detected_action_shapes


def test_categorize_detects_personal_scope():
    cat = categorize("I am thinking about my next move. I don't know yet.")
    assert cat.detected_scope == "personal"


def test_categorize_detects_family_scope():
    cat = categorize("My wife and I are thinking about our kids' school.")
    assert cat.detected_scope == "family"


def test_categorize_picks_most_specific_scope():
    """When multiple scope hints fire, the most specific (last in
    the dict) wins."""
    cat = categorize("My family and our community both shape how I see this.")
    assert cat.detected_scope == "community"


def test_categorize_does_not_mutate_text():
    """The text is sacred — categorization is additive metadata."""
    text = "I am thinking about Mt 5:37 and what it means to build."
    cat = categorize(text)
    # Categorize is a pure function — it doesn't return text.
    # Verify this by checking that the categorization references
    # the text via its findings, not by carrying a copy.
    assert hasattr(cat, "detected_anchors")
    assert not hasattr(cat, "text")


def test_categorize_handles_packet_parser_failure_silently():
    """A malformed input that breaks nl_to_packet should not crash."""
    # Some pathological inputs may cause downstream parsers to error
    # internally; categorize should still succeed.
    weird = "\x00\x01\x02 \udc80 unbalanced (((((( $$"
    cat = categorize(weird)
    assert isinstance(cat, Categorization)


# ── JournalEntry / Categorization roundtrip ──────────────────────────


def test_journal_entry_dict_roundtrip():
    entry = JournalEntry(
        id="j-test123",
        text="Original sacred text.",
        written_at=100.0,
        modified_at=100.0,
        user_tags=["draft", "morning"],
        categorization=Categorization(
            detected_anchors=["Mt 5:37"],
            detected_action_shapes=["Hold"],
            detected_scope="personal",
        ),
    )
    d = entry.to_dict()
    e2 = JournalEntry.from_dict(d)
    assert e2.id == entry.id
    assert e2.text == entry.text
    assert e2.user_tags == ["draft", "morning"]
    assert e2.categorization.detected_anchors == ["Mt 5:37"]


# ── Store ────────────────────────────────────────────────────────────


def test_store_save_and_load(tmp_path):
    store = JournalStore(base_dir=tmp_path)
    entry = JournalEntry(
        id="j-abc",
        text="Test entry.",
        written_at=100.0,
        modified_at=100.0,
    )
    store.save(entry)
    loaded = store.load("j-abc")
    assert loaded is not None
    assert loaded.text == "Test entry."


def test_store_load_missing_returns_none(tmp_path):
    store = JournalStore(base_dir=tmp_path)
    assert store.load("j-nonexistent") is None


def test_store_list_all_newest_first(tmp_path):
    store = JournalStore(base_dir=tmp_path)
    for i, t in enumerate([100.0, 300.0, 200.0]):
        store.save(JournalEntry(
            id=f"j-{i}",
            text=f"entry {i}",
            written_at=t,
            modified_at=t,
        ))
    entries = store.list_all()
    assert [e.written_at for e in entries] == [300.0, 200.0, 100.0]


def test_store_filter_by_tag(tmp_path):
    store = JournalStore(base_dir=tmp_path)
    store.save(JournalEntry(
        id="j-a", text="x", written_at=100.0, modified_at=100.0,
        user_tags=["draft"],
    ))
    store.save(JournalEntry(
        id="j-b", text="y", written_at=200.0, modified_at=200.0,
        user_tags=["final"],
    ))
    drafts = store.list_all(tag="draft")
    assert len(drafts) == 1
    assert drafts[0].id == "j-a"


def test_store_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j_env"))
    store = JournalStore()  # no explicit base_dir
    assert store.base_dir == tmp_path / "j_env"


# ── capture ──────────────────────────────────────────────────────────


def test_capture_persists_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    entry = capture(
        "I am thinking about Mt 5:37 today. What does 'yes mean yes' mean for me?"
    )
    assert entry.id.startswith("j-")
    assert entry.text.startswith("I am thinking about Mt 5:37")
    assert "Mt 5:37" in entry.categorization.detected_anchors
    assert entry.categorization.detected_scope == "personal"
    # File on disk.
    store = JournalStore(base_dir=tmp_path / "j")
    loaded = store.load(entry.id)
    assert loaded is not None
    assert loaded.text == entry.text


def test_capture_rejects_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    with pytest.raises(ValueError):
        capture("")
    with pytest.raises(ValueError):
        capture("   \n\t  ")


def test_capture_emits_keeping_observation(tmp_path, monkeypatch):
    """Capture should record the writing event in the keeping log."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    capture("A short entry.")
    from concordance_engine.keeping import KeepingLog
    log = KeepingLog()
    observations = log.read(practice="journal_capture")
    assert len(observations) == 1
    assert observations[0].kept["text_length"] == len("A short entry.")


def test_capture_preserves_text_verbatim(tmp_path, monkeypatch):
    """Doctrinal: the text is sacred. No paraphrase, no compression."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    weird_text = (
        "Multiple lines.\n"
        "  Indentation.\n"
        "Special chars: ' \" — em-dash, λόγος in Greek.\n"
        "Trailing space.   "
    )
    entry = capture(weird_text)
    assert entry.text == weird_text


# ── annotate ─────────────────────────────────────────────────────────


def test_annotate_appends_without_mutating_text(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    entry = capture("Original text I shall not change.")
    original_text = entry.text
    updated = annotate(entry.id, "Reflecting later: I think I was wrong.")
    assert updated is not None
    assert updated.text == original_text  # original preserved
    assert len(updated.annotations) == 1
    assert updated.annotations[0].note == "Reflecting later: I think I was wrong."


def test_annotate_missing_entry_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    result = annotate("j-nonexistent", "note")
    assert result is None


def test_annotate_rejects_empty_note(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    entry = capture("text")
    with pytest.raises(ValueError):
        annotate(entry.id, "")


# ── thread ───────────────────────────────────────────────────────────


def test_thread_finds_entries_sharing_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    e1 = capture("Mt 5:37 is on my mind today.")
    e2 = capture("Reading Prov 30:5 alongside Mt 5:37.")
    e3 = capture("Something else entirely. Random thoughts about lunch.")
    related = thread(e1.id)
    assert any(e.id == e2.id for e in related)
    assert not any(e.id == e3.id for e in related)


def test_thread_finds_entries_sharing_action_shape(tmp_path, monkeypatch):
    """Use third-person fixture text so scope-detection doesn't
    artificially link the entries; isolate the action-shape signal."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    e1 = capture("Want to build a new thing today.")
    e2 = capture("Building this idea up over time.")
    e3 = capture("Considering a hold on the matter.")  # Hold, not Build
    related = thread(e1.id)
    assert any(e.id == e2.id for e in related), \
        "thread should include e2 (shares Build action shape)"
    # e3 has different action shape and no shared scope/anchor.
    assert not any(e.id == e3.id for e in related), \
        "thread should not include e3 (no shared signal)"


# ── calibrate (the calibration measurements) ─────────────────────────


def test_calibrate_first_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    e = capture("First entry into the kingdom.")
    cal = calibrate(e)
    assert cal.total_entries_to_date == 1
    assert cal.entries_in_last_7_days == 0  # first one excluded from history
    assert cal.previous_scope is None
    assert cal.seconds_since_previous is None
    assert cal.scope_shifted is False


def test_calibrate_records_tempo(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    store = JournalStore()
    # Plant two historical entries at known times.
    for i, t in enumerate([100.0, 200.0]):
        store.save(JournalEntry(
            id=f"j-h{i}", text=f"history {i}",
            written_at=t, modified_at=t,
        ))
    new_entry = JournalEntry(
        id="j-new", text="new entry", written_at=300.0, modified_at=300.0,
    )
    store.save(new_entry)

    cal = calibrate(new_entry, now=300.0)
    assert cal.total_entries_to_date == 3
    assert cal.seconds_since_previous == 100.0  # 300 - 200


def test_calibrate_detects_scope_shift(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    store = JournalStore()
    store.save(JournalEntry(
        id="j-prev", text="my family decision",
        written_at=100.0, modified_at=100.0,
        categorization=Categorization(detected_scope="family"),
    ))
    new_entry = JournalEntry(
        id="j-new", text="just my own thoughts",
        written_at=200.0, modified_at=200.0,
        categorization=Categorization(detected_scope="personal"),
    )
    store.save(new_entry)
    cal = calibrate(new_entry, now=200.0)
    assert cal.scope_shifted is True
    assert cal.previous_scope == "family"


def test_calibrate_recurring_anchors(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    store = JournalStore()
    store.save(JournalEntry(
        id="j-h1", text="x", written_at=100.0, modified_at=100.0,
        categorization=Categorization(detected_anchors=["Mt 5:37", "Prov 3:5"]),
    ))
    store.save(JournalEntry(
        id="j-h2", text="y", written_at=200.0, modified_at=200.0,
        categorization=Categorization(detected_anchors=["Mt 5:37"]),
    ))
    new_entry = JournalEntry(
        id="j-n", text="z", written_at=300.0, modified_at=300.0,
        categorization=Categorization(detected_anchors=["Mt 5:37", "Heb 11:1"]),
    )
    store.save(new_entry)

    cal = calibrate(new_entry, now=300.0)
    assert "Mt 5:37" in cal.recurring_anchors
    assert "Heb 11:1" in cal.anchors_first_appearance
    assert "Prov 3:5" not in cal.recurring_anchors  # not in this entry


def test_calibrate_action_pattern_note(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    store = JournalStore()
    now = 1000000.0
    # Plant 4 Hold-shape entries in last 30 days.
    for i in range(4):
        store.save(JournalEntry(
            id=f"j-h{i}",
            text="x",
            written_at=now - (i + 1) * 86400,
            modified_at=now - (i + 1) * 86400,
            categorization=Categorization(detected_action_shapes=["Hold"]),
        ))
    # New entry has Build shape — diverges from pattern.
    new_entry = JournalEntry(
        id="j-new", text="y",
        written_at=now, modified_at=now,
        categorization=Categorization(detected_action_shapes=["Build"]),
    )
    store.save(new_entry)
    cal = calibrate(new_entry, now=now)
    assert cal.action_shape_counts_30d.get("Hold") == 4
    assert "Hold" in cal.action_pattern_note
    assert "Build" in cal.action_pattern_note


# ── render_calibration (markdown surface) ────────────────────────────


def test_render_calibration_first_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    e = capture("First entry. Mt 5:37 on my mind.")
    cal = calibrate(e)
    rendered = render_calibration(e, cal)
    assert "first entry" in rendered.lower() or "the keeping has begun" in rendered.lower()
    assert "Mt 5:37" in rendered  # surfaced in "Anchors heard"


def test_render_calibration_no_judgment_words(tmp_path, monkeypatch):
    """Doctrinal: calibration is descriptive, never prescriptive.
    No 'good', 'bad', 'should', 'must' in render."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    e = capture("I want to build something. My family thinks I should wait. I keep returning to Mt 5:37.")
    cal = calibrate(e)
    rendered = render_calibration(e, cal).lower()
    # The rendering should not push the user toward a verdict.
    forbidden = ["good", "bad", "you should", "you must"]
    for word in forbidden:
        assert word not in rendered, f"render contains prescriptive word: {word!r}"
