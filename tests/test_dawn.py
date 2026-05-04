"""Tests for the dawn surface — the optional perimeter-walk reader.

Dawn is read-only: it gathers across keeping, ledger, and quarantine
and renders a narrative. These tests verify it produces structured
data and rendered markdown without side effects, handles empty state
gracefully, and surfaces the three categories (kept / drift / held)
distinctly.

Per KoA Trilogy (Anna's chapter): "Someone walks the outer edge of
Lookout before the settlement wakes." The walk reads what's been
kept; it does not assign work.
"""
from __future__ import annotations

import json
import time

import pytest

from concordance_engine import dawn as _dawn
from concordance_engine.keeping import KeepingLog, KeepingObservation


# ── gather_dawn ─────────────────────────────────────────────────────


def test_gather_returns_dawn_surface(tmp_path):
    """The default gather call returns a DawnSurface with all fields."""
    keeping_dir = tmp_path / "keeping"
    ledger_dir = tmp_path / "ledger"
    quarantine_dir = tmp_path / "quarantine"

    surface = _dawn.gather_dawn(
        keeping_dir=keeping_dir,
        ledger_dir=ledger_dir,
        quarantine_dir=quarantine_dir,
    )

    assert isinstance(surface, _dawn.DawnSurface)
    assert surface.keeping_summary["total_observations"] == 0
    assert surface.drift_observations == []
    assert surface.recent_precedents == []
    assert surface.held_packets == []
    assert surface.audit_chain_total == 0
    assert surface.quarantine_total == 0


def test_gather_picks_up_recent_keeping_observations(tmp_path):
    """Observations after the cutoff appear in the surface."""
    keeping_dir = tmp_path / "keeping"
    log = KeepingLog(base_dir=keeping_dir)
    now = time.time()

    log.append(KeepingObservation(
        practice="signal_hum",
        started_at=now - 600,  # 10 min ago — well within 24h
        duration_seconds=1.0,
        kept={"heartbeat": "ok"},
        note=None,
    ))

    surface = _dawn.gather_dawn(
        keeping_dir=keeping_dir,
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
        now=now,
    )

    assert surface.keeping_summary["total_observations"] == 1
    by_practice = surface.keeping_summary.get("by_practice", {})
    assert "signal_hum" in by_practice
    assert by_practice["signal_hum"]["runs"] == 1


def test_gather_drift_observations_surface_separately(tmp_path):
    """Observations carrying a `note` are surfaced as drift signals."""
    keeping_dir = tmp_path / "keeping"
    log = KeepingLog(base_dir=keeping_dir)
    now = time.time()

    log.append(KeepingObservation(
        practice="forge_lighting",
        started_at=now - 100,
        duration_seconds=1.0,
        kept={},
        note="checksum mismatch",
    ))

    surface = _dawn.gather_dawn(
        keeping_dir=keeping_dir,
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
        now=now,
    )
    assert len(surface.drift_observations) == 1
    drift = surface.drift_observations[0]
    assert drift["practice"] == "forge_lighting"
    assert drift["note"] == "checksum mismatch"


def test_gather_respects_since_window(tmp_path):
    """Observations older than `since` are excluded from drift +
    keeping_summary.total_observations."""
    keeping_dir = tmp_path / "keeping"
    log = KeepingLog(base_dir=keeping_dir)
    now = time.time()

    log.append(KeepingObservation(
        practice="signal_hum",
        started_at=now - 86400 * 7,  # 7 days ago
        duration_seconds=1.0,
        kept={"heartbeat": "ok"},
        note=None,
    ))
    # And a recent one.
    log.append(KeepingObservation(
        practice="signal_hum",
        started_at=now - 30,
        duration_seconds=1.0,
        kept={"heartbeat": "ok"},
        note=None,
    ))

    surface = _dawn.gather_dawn(
        keeping_dir=keeping_dir,
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
        since=now - 3600,  # last hour only
        now=now,
    )
    assert surface.keeping_summary["total_observations"] == 1


# ── render_dawn ─────────────────────────────────────────────────────


def test_render_includes_header_and_socratic_close(tmp_path):
    """Every render carries the header and the closing question."""
    surface = _dawn.gather_dawn(
        keeping_dir=tmp_path / "keeping",
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
    )
    md = _dawn.render_dawn(surface)
    assert md.startswith("# Dawn")
    assert "What do you want to keep today?" in md


def test_render_empty_kingdom_is_quiet_not_ok(tmp_path):
    """An empty kingdom renders as 'quiet', not as success."""
    surface = _dawn.gather_dawn(
        keeping_dir=tmp_path / "keeping",
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
    )
    md = _dawn.render_dawn(surface)
    assert "quiet" in md.lower()
    # No verdict language — dawn is descriptive, not evaluative.
    assert "PASS" not in md
    assert "FAIL" not in md


def test_render_drift_section_appears_when_drift_present(tmp_path):
    keeping_dir = tmp_path / "keeping"
    log = KeepingLog(base_dir=keeping_dir)
    now = time.time()
    log.append(KeepingObservation(
        practice="forge_lighting",
        started_at=now - 60,
        duration_seconds=1.0,
        kept={},
        note="lamp out",
    ))
    surface = _dawn.gather_dawn(
        keeping_dir=keeping_dir,
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
        now=now,
    )
    md = _dawn.render_dawn(surface)
    assert "Drift the keeping noticed" in md
    assert "lamp out" in md
    # Closing message acknowledges drift specifically.
    assert "Drift was visible" in md or "drift" in md.lower()


# ── Serialization ───────────────────────────────────────────────────


def test_to_dict_round_trips_through_json(tmp_path):
    surface = _dawn.gather_dawn(
        keeping_dir=tmp_path / "keeping",
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
    )
    payload = surface.to_dict()
    # Must be JSON-serializable.
    s = json.dumps(payload, default=str)
    assert "since_epoch" in s
    assert "keeping_summary" in s


# ── Optionality ─────────────────────────────────────────────────────


def test_gather_is_read_only(tmp_path):
    """Gathering twice produces equivalent state; no writes."""
    args = dict(
        keeping_dir=tmp_path / "keeping",
        ledger_dir=tmp_path / "ledger",
        quarantine_dir=tmp_path / "quarantine",
    )
    s1 = _dawn.gather_dawn(**args)
    s2 = _dawn.gather_dawn(**args)
    # Same totals; gather should not have created any files.
    assert s1.audit_chain_total == s2.audit_chain_total
    assert s1.quarantine_total == s2.quarantine_total
    # The dirs should not have been auto-created by gather.
    assert not (tmp_path / "keeping").exists() or not any(
        (tmp_path / "keeping").iterdir()
    )
