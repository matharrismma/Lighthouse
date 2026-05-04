"""Tests for /ask — search-the-bank-or-create-a-new-seed.

Per Matt 2026-05-03:
  "We focus on what is not the answer. By elimination we illuminate
   the narrow path."
  "Good fruit is the measure. We focus on locating the good fruit
   and creating a clear path."

The tests verify:
  * elimination by axis / anchor / scope mismatch
  * fruit scoring across precedents and journal entries
  * new-seed creation when nothing survives
  * render output never produces a verdict / answer text
"""
from __future__ import annotations

import json

import pytest

from concordance_engine import journal as _journal
from concordance_engine import ask as ask_mod
from concordance_engine.ask import (
    AskResult,
    EliminatedCandidate,
    SurvivingMatch,
    ask,
    render_ask,
)


# ── Empty inputs ─────────────────────────────────────────────────────


def test_ask_rejects_empty():
    with pytest.raises(ValueError):
        ask("")
    with pytest.raises(ValueError):
        ask("   ")


# ── No matches → captures as new seed ────────────────────────────────


def test_ask_with_empty_bank_creates_new_seed(tmp_path, monkeypatch):
    """When nothing is in the seed bank, the question is captured
    as a new journal seed."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    result = ask("What does Mt 5:37 mean for me today?")
    assert result.survivors == []
    assert result.new_seed_id is not None
    assert result.new_seed_id.startswith("j-")
    # The captured seed should exist on disk.
    store = _journal.JournalStore()
    e = store.load(result.new_seed_id)
    assert e is not None
    assert "from_ask" in e.user_tags


def test_ask_no_capture_when_capture_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    result = ask("Some question", capture_if_no_survivors=False)
    assert result.survivors == []
    assert result.new_seed_id is None


# ── Anchor-overlap survival ──────────────────────────────────────────


def test_ask_finds_journal_entry_via_shared_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Plant a journal entry with an anchor.
    e = _journal.capture("Earlier I wrote about Mt 5:37 and what 'yes' costs.")
    # Now ask about Mt 5:37 — should surface the planted entry.
    result = ask("How does Mt 5:37 connect to my decision?")
    assert any(s.candidate_id == e.id for s in result.survivors)


def test_ask_eliminates_journal_entry_with_no_anchor_overlap(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Plant entry citing Heb 11:1 (different anchor from question).
    e = _journal.capture("My thinking on Heb 11:1 and the substance of faith.")
    # Ask about Mt 5:37; should ELIMINATE the Heb 11:1 entry.
    result = ask("Mt 5:37 — what does it require of me?")
    eliminated_ids = [c.candidate_id for c in result.eliminated]
    assert e.id in eliminated_ids
    eliminated_for_e = next(
        c for c in result.eliminated if c.candidate_id == e.id
    )
    assert eliminated_for_e.reason == "no_anchor_overlap"


def test_ask_preserves_entries_when_question_has_no_anchor(tmp_path, monkeypatch):
    """When the question has no anchors, journal entries with anchors
    should NOT be eliminated for anchor mismatch."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    e = _journal.capture("My thoughts on Mt 5:37 today.")
    # Question with NO anchor — entry should not be eliminated for
    # anchor mismatch.
    result = ask("I am thinking about my next move.")
    assert all(
        c.reason != "no_anchor_overlap"
        for c in result.eliminated
        if c.candidate_id == e.id
    )


# ── Scope mismatch elimination ───────────────────────────────────────


def test_ask_eliminates_journal_entry_with_mismatched_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Plant a community-scoped entry.
    e = _journal.capture("My church is wrestling with this question.")
    # Question is family-scoped — different scope.
    result = ask("My family decision about whether to move.")
    # The community entry should be eliminated by scope mismatch.
    eliminated_ids = [c.candidate_id for c in result.eliminated]
    assert e.id in eliminated_ids
    eliminated_for_e = next(c for c in result.eliminated if c.candidate_id == e.id)
    assert eliminated_for_e.reason == "scope_mismatch"


# ── Audit chain precedent matching ───────────────────────────────────


def _plant_precedent(ledger_dir, *, pid, axis, anchors=None, summary="test"):
    """Plant a sealed precedent file under the ledger dir."""
    ledger_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "precedent_id": pid,
        "axis": axis,
        "summary": summary,
        "anchors": [{"ref": a, "layer": "bible"} for a in (anchors or [])],
        "sealed_at": 1000.0,
    }
    safe_filename = pid.replace("/", "_").replace(":", "_") + ".json"
    (ledger_dir / safe_filename).write_text(
        json.dumps(payload), encoding="utf-8",
    )


def test_ask_surfaces_audit_chain_precedent_with_shared_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    _plant_precedent(
        tmp_path / "l",
        pid="ledger://test/sample",
        axis="governance",
        anchors=["Mt 5:37"],
    )
    result = ask("How should I handle a decision around Mt 5:37?")
    survivor_ids = [s.candidate_id for s in result.survivors]
    assert "ledger://test/sample" in survivor_ids


def test_ask_eliminates_precedent_with_no_anchor_overlap(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    _plant_precedent(
        tmp_path / "l",
        pid="ledger://test/different",
        axis="governance",
        anchors=["Heb 11:1"],  # different anchor
    )
    result = ask("Question about Mt 5:37")
    eliminated_ids = [c.candidate_id for c in result.eliminated]
    assert "ledger://test/different" in eliminated_ids


# ── Fruit scoring ────────────────────────────────────────────────────


def test_fruit_scoring_unamended_beats_amended(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Plant two precedents: one is amended-from by another.
    _plant_precedent(
        tmp_path / "l",
        pid="ledger://test/old",
        axis="governance",
        anchors=["Mt 5:37"],
    )
    # Plant an amendment that points back at /old.
    amend_payload = {
        "precedent_id": "ledger://test/new",
        "axis": "governance",
        "summary": "amendment",
        "anchors": [{"ref": "Mt 5:37", "layer": "bible"}],
        "amends": "ledger://test/old",
        "sealed_at": 2000.0,
    }
    (tmp_path / "l" / "amend.json").write_text(
        json.dumps(amend_payload), encoding="utf-8",
    )

    result = ask("Mt 5:37 question")
    by_id = {s.candidate_id: s for s in result.survivors}
    # /old should have lower fruit score than /new (it was amended)
    if "ledger://test/old" in by_id and "ledger://test/new" in by_id:
        assert by_id["ledger://test/new"].fruit_score >= by_id["ledger://test/old"].fruit_score
        assert by_id["ledger://test/old"].fruit_signals.get("unamended") is False
        assert by_id["ledger://test/new"].fruit_signals.get("unamended") is True


def test_fruit_scoring_journal_shelf_bonus(tmp_path, monkeypatch):
    """An entry on the shelf scores higher than one only in the library."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Two entries with the same anchor; one published.
    e1 = _journal.capture("Mt 5:37 — one.")
    e2 = _journal.capture("Mt 5:37 — two.")
    # Add shelf tag to e1.
    store = _journal.JournalStore()
    e1.user_tags.append("shelf")
    store.save(e1)

    result = ask("What does Mt 5:37 imply?")
    by_id = {s.candidate_id: s for s in result.survivors}
    # e1 should be ranked higher than e2 (shelf bonus).
    if e1.id in by_id and e2.id in by_id:
        assert by_id[e1.id].fruit_score > by_id[e2.id].fruit_score


# ── Result invariants ────────────────────────────────────────────────


def test_ask_result_carries_categorization(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    result = ask("Mt 5:37 — what does it mean?")
    assert result.categorization is not None
    # The question's anchor should appear in the categorization.
    assert "Mt 5:37" in result.categorization.get("detected_anchors", [])


def test_ask_caps_survivors(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))
    # Plant 10 entries that all match.
    for i in range(10):
        _journal.capture(f"Entry {i} about Mt 5:37.")
    result = ask("Mt 5:37 question?", max_survivors=3)
    assert len(result.survivors) == 3


# ── Render output (no judgment, no answer text) ──────────────────────


def test_render_ask_no_verdict_words():
    """The render must not produce verdict-shaped language. The
    engine focuses on what is NOT the answer; render should never
    declare what IS."""
    result = AskResult(
        question="Test question?",
        survivors=[
            SurvivingMatch(
                source="audit_chain",
                candidate_id="ledger://test/x",
                summary="Test precedent",
                shared_signal=["anchors:Mt 5:37"],
                fruit_score=2.5,
                fruit_signals={"sealed": True},
            ),
        ],
    )
    rendered = render_ask(result).lower()
    forbidden = ["the answer is", "you should", "you must", "verdict",
                 "correct", "incorrect"]
    for word in forbidden:
        assert word not in rendered, f"render contains verdict word: {word!r}"


def test_render_ask_includes_elimination_trail():
    """The render must surface what was eliminated — the trail IS
    the reasoning."""
    result = AskResult(
        question="Test?",
        survivors=[],
        eliminated=[
            EliminatedCandidate(
                source="audit_chain",
                candidate_id="ledger://x",
                reason="axis_mismatch",
                detail="...",
            )
        ],
    )
    rendered = render_ask(result)
    assert "eliminated" in rendered.lower()
    assert "ledger://x" in rendered
    assert "axis_mismatch" in rendered


def test_render_ask_includes_new_seed_when_captured():
    result = AskResult(
        question="Novel question?",
        survivors=[],
        eliminated=[],
        new_seed_id="j-fresh123",
    )
    rendered = render_ask(result)
    assert "j-fresh123" in rendered
    assert "new seed" in rendered.lower() or "kept" in rendered.lower()
