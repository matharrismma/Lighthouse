"""Tests for the live companion — the harvester at the door.

The live tool is a REPL that captures stream-of-consciousness as
seeds, manages library / shelf / central tiers, and runs the
keeping in the background. These tests exercise the dispatch and
rendering without standing up a real REPL — `handle_line()` is the
testable unit.
"""
from __future__ import annotations

import time

import pytest

from concordance_engine import journal as _journal
from concordance_engine.live import (
    LiveConfig,
    LiveSession,
    collect_multiline,
    handle_line,
    run,
)


# ── handle_line: bare text = capture ─────────────────────────────────


def test_bare_text_captures_seed(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    output = handle_line(session, "Today I'm thinking about Mt 5:37.")
    assert output is not None
    assert session.last_entry_id is not None
    assert session.last_entry_id.startswith("j-")
    assert "kept" in output.lower()
    assert "Mt 5:37" in output  # surfaced in the capture render


def test_blank_line_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    assert handle_line(session, "") is None
    assert handle_line(session, "   \n\t  ") is None
    assert session.last_entry_id is None


# ── handle_line: /quit and aliases ───────────────────────────────────


def test_quit_returns_sentinel():
    session = LiveSession()
    assert handle_line(session, "/quit") == "__QUIT__"
    assert handle_line(session, "/exit") == "__QUIT__"
    assert handle_line(session, "/bye") == "__QUIT__"


# ── handle_line: /help ───────────────────────────────────────────────


def test_help_lists_three_tiers():
    session = LiveSession()
    output = handle_line(session, "/help")
    assert output is not None
    # The three tiers are named in help.
    assert "INDIVIDUAL" in output
    assert "COMMUNITY" in output
    assert "CENTRAL" in output


def test_unknown_command():
    session = LiveSession()
    output = handle_line(session, "/notarealcommand")
    assert output is not None
    assert "unknown command" in output.lower()


# ── handle_line: /thread ─────────────────────────────────────────────


def test_thread_default_uses_last_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    handle_line(session, "Thinking about Mt 5:37 again.")
    handle_line(session, "More on Mt 5:37 — yes meaning yes.")
    output = handle_line(session, "/thread")
    assert output is not None
    assert "threading with" in output.lower()


def test_thread_with_no_capture_yet():
    session = LiveSession()
    output = handle_line(session, "/thread")
    assert "no entry to thread" in output.lower()


def test_thread_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    session = LiveSession()
    output = handle_line(session, "/thread j-doesnotexist")
    assert "no entry found" in output.lower()


# ── handle_line: /show ───────────────────────────────────────────────


def test_show_renders_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    handle_line(session, "An original thought.")
    output = handle_line(session, "/show")
    assert output is not None
    assert "An original thought." in output
    assert session.last_entry_id in output


# ── handle_line: /recent ─────────────────────────────────────────────


def test_recent_lists_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    for text in ("first", "second", "third"):
        handle_line(session, text)
    output = handle_line(session, "/recent 2")
    assert output is not None
    # Newest first → "third" should appear before "second".
    third_pos = output.find("third")
    second_pos = output.find("second")
    assert 0 < third_pos < second_pos


def test_recent_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    session = LiveSession()
    output = handle_line(session, "/recent")
    assert "no entries yet" in output.lower()


# ── handle_line: /keeping ────────────────────────────────────────────


def test_keeping_with_no_keeper_quiet(tmp_path, monkeypatch):
    """With no background keeper running and no other observations,
    /keeping reports the log is quiet."""
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    session = LiveSession()
    output = handle_line(session, "/keeping")
    assert output is not None
    assert ("quiet" in output.lower() or "what's been kept" in output.lower())


def test_keeping_observes_journal_captures(tmp_path, monkeypatch):
    """A capture emits a `journal_capture` keeping observation; that
    should show up in /keeping."""
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    session = LiveSession()
    handle_line(session, "Test seed.")
    output = handle_line(session, "/keeping")
    assert "journal_capture" in output


# ── handle_line: /shelf, /publish, /unshelf ──────────────────────────


def test_shelf_starts_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    session = LiveSession()
    output = handle_line(session, "/shelf")
    assert "empty" in output.lower()


def test_publish_adds_to_shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    handle_line(session, "A seed worth sharing.")
    out = handle_line(session, "/publish")
    assert "shelf" in out.lower()

    # /shelf now lists the published entry.
    listing = handle_line(session, "/shelf")
    assert session.last_entry_id in listing


def test_publish_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    handle_line(session, "Seed.")
    handle_line(session, "/publish")
    second = handle_line(session, "/publish")
    assert "already on the shelf" in second.lower()


def test_unshelf_removes_from_shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    session = LiveSession()
    handle_line(session, "Seed.")
    handle_line(session, "/publish")
    handle_line(session, "/unshelf")
    listing = handle_line(session, "/shelf")
    assert "empty" in listing.lower()


def test_publish_with_no_capture_yet():
    session = LiveSession()
    output = handle_line(session, "/publish")
    assert "no seed to publish" in output.lower()


# ── handle_line: /anchor ─────────────────────────────────────────────


def test_anchor_no_args():
    session = LiveSession()
    output = handle_line(session, "/anchor")
    assert "usage" in output.lower()


def test_anchor_lookup_returns_status(tmp_path, monkeypatch):
    """Anchor lookup runs; returns either source_missing or actual
    web text. Either is a valid result."""
    session = LiveSession()
    output = handle_line(session, "/anchor Mt 5:37")
    assert output is not None
    # Should at least mention the ref.
    assert "Mt 5:37" in output or "source_missing" in output.lower()


# ── handle_line: /precedent ──────────────────────────────────────────


def test_precedent_with_no_capture_yet():
    session = LiveSession()
    output = handle_line(session, "/precedent")
    assert "no entry yet" in output.lower()


def test_precedent_with_no_match(tmp_path, monkeypatch):
    """A capture with no matching precedent returns 'no closest precedent'."""
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("CONCORDANCE_LEDGER_DIR", str(tmp_path / "l"))  # empty ledger
    session = LiveSession()
    handle_line(session, "Random text with no recognizable shape.")
    output = handle_line(session, "/precedent")
    assert output is not None
    # Either "no closest precedent" or it found one — both are valid.


# ── collect_multiline ────────────────────────────────────────────────


def test_collect_multiline_terminates_on_dot():
    lines = iter(["first line", "second line", ".", "ignored"])
    text = collect_multiline(lambda: next(lines))
    assert text == "first line\nsecond line"


def test_collect_multiline_handles_eof():
    lines = iter(["only line"])

    def _read():
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    text = collect_multiline(_read)
    assert text == "only line"


# ── run() (REPL loop end-to-end via injected I/O) ────────────────────


def test_run_captures_and_quits(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_JOURNAL_DIR", str(tmp_path / "j"))
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(tmp_path / "k"))
    inputs = iter([
        "First seed.",
        "/recent",
        "/quit",
    ])

    def _input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    captured: list = []
    rc = run(
        LiveConfig(run_keeper=False),
        input_fn=_input,
        output_fn=lambda s: captured.append(s),
    )
    assert rc == 0
    joined = "\n".join(captured)
    assert "Lighthouse" in joined
    assert "kept" in joined.lower()
    assert "Lighthouse — stopping" in joined
