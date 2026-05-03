"""Tests for the keeping layer.

The keeping is the engine's liturgical body-practice layer — runs
between gate firings, distinct from on-demand verification. Each
practice keeps something; none returns a decision.

Per KoA Trilogy (The Keeping, Book Three): "We are for keeping each
other." These tests verify the keeping does what it says — runs at
its own rhythm, survives broken practices, fills the log whether or
not anyone reads it.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from concordance_engine.keeping import (
    ForgeLighting,
    Keeper,
    KeepingLog,
    KeepingObservation,
    KeepingPractice,
    PerimeterWalk,
    RollKeeping,
    SignalHum,
    default_keeper,
    while_you_were_away,
)


# ── KeepingPractice base behavior ────────────────────────────────────


class _NoOpPractice(KeepingPractice):
    """Test fixture: returns a static payload."""
    name = "test_noop"

    def __init__(self, cadence_seconds: float = 1.0, payload=None):
        super().__init__(cadence_seconds=cadence_seconds)
        self.payload = payload or {"kept": True}

    def _do_run(self):
        return dict(self.payload)


class _FailingPractice(KeepingPractice):
    """Test fixture: always raises."""
    name = "test_failing"

    def __init__(self, cadence_seconds: float = 1.0):
        super().__init__(cadence_seconds=cadence_seconds)

    def _do_run(self):
        raise RuntimeError("forge would not light")


def test_practice_rejects_zero_cadence():
    with pytest.raises(ValueError):
        _NoOpPractice(cadence_seconds=0)


def test_practice_first_run_is_due():
    p = _NoOpPractice(cadence_seconds=60.0)
    assert p.due(now=0.0)


def test_practice_run_returns_observation():
    p = _NoOpPractice(payload={"x": 42})
    obs = p.run(now=100.0)
    assert isinstance(obs, KeepingObservation)
    assert obs.practice == "test_noop"
    assert obs.kept == {"x": 42}
    assert obs.note == ""
    assert obs.started_at == 100.0
    assert obs.duration_seconds >= 0


def test_practice_due_after_cadence():
    p = _NoOpPractice(cadence_seconds=10.0)
    p.run(now=0.0)
    assert not p.due(now=5.0)
    assert p.due(now=11.0)


def test_practice_survives_internal_failure():
    """A practice that raises should not break the keeping. The
    observation captures the error in its note field."""
    p = _FailingPractice()
    obs = p.run(now=0.0)
    assert obs.practice == "test_failing"
    assert "forge would not light" in obs.kept.get("error", "")
    assert obs.kept.get("exception_type") == "RuntimeError"
    assert "RuntimeError" in obs.note


def test_practice_consecutive_runs_increment():
    p = _NoOpPractice()
    assert p.consecutive_runs == 0
    p.run(now=0.0)
    p.run(now=10.0)
    p.run(now=20.0)
    assert p.consecutive_runs == 3


# ── SignalHum ────────────────────────────────────────────────────────


def test_signal_hum_runs():
    hum = SignalHum(cadence_seconds=1.0)
    obs = hum.run(now=0.0)
    assert obs.practice == "signal_hum"
    assert obs.kept["heartbeat"] is True
    assert obs.kept["consecutive_runs"] == 1


def test_signal_hum_does_not_decide():
    """Per doctrine: the signal does not know it is being received.
    Output should be descriptive, not pass/fail."""
    hum = SignalHum(cadence_seconds=1.0)
    obs = hum.run()
    # No 'status', 'verdict', 'pass', 'fail' keys.
    forbidden = {"status", "verdict", "pass", "fail", "ok"}
    assert not (forbidden & set(obs.kept.keys()))


# ── PerimeterWalk ────────────────────────────────────────────────────


def test_perimeter_walk_with_empty_ledger(tmp_path):
    """An empty ledger walks fine — perimeter walk doesn't fail on
    a quiet kingdom."""
    walk = PerimeterWalk(cadence_seconds=1.0, ledger_dir=tmp_path)
    obs = walk.run()
    assert obs.kept["total_precedents"] == 0
    assert obs.kept["chain_intact"] is True
    assert obs.kept["tampered_count"] == 0


def test_perimeter_walk_observes_drift(tmp_path):
    """A tampered ledger surfaces drift in the kept payload — but the
    walk does not raise."""
    bad = tmp_path / "tampered.json"
    bad.write_text(
        json.dumps({
            "precedent_id": "ledger://test/x",
            "axis": "test",
            "summary": "test precedent",
            "content_hash": "deadbeef" * 8,
            "prev_hash": "GENESIS",
            "sealed_at": 1000.0,
        }),
        encoding="utf-8",
    )
    walk = PerimeterWalk(cadence_seconds=1.0, ledger_dir=tmp_path)
    obs = walk.run()
    # The kept payload reports drift descriptively.
    assert obs.kept["total_precedents"] == 1
    assert obs.kept["chain_intact"] is False
    assert obs.kept["tampered_count"] >= 1


# ── ForgeLighting ────────────────────────────────────────────────────


def test_forge_lighting_runs():
    forge = ForgeLighting(cadence_seconds=1.0)
    obs = forge.run()
    assert obs.practice == "forge_lighting"
    assert "verifiers_lit" in obs.kept
    assert "all_lit" in obs.kept


def test_forge_lighting_default_domains_light():
    forge = ForgeLighting(cadence_seconds=1.0)
    obs = forge.run()
    # All canonical verifier modules import cleanly.
    assert obs.kept["all_lit"] is True
    assert obs.kept["cold_count"] == 0


def test_forge_lighting_handles_missing_module():
    """A non-existent verifier module is reported as 'cold', not raised."""
    forge = ForgeLighting(cadence_seconds=1.0, domains=["definitely_not_a_real_domain"])
    obs = forge.run()
    assert obs.kept["all_lit"] is False
    assert obs.kept["cold_count"] == 1
    assert "cold" in obs.kept["verifiers_lit"]["definitely_not_a_real_domain"]


# ── RollKeeping ──────────────────────────────────────────────────────


def test_roll_keeping_with_empty_ledger(tmp_path):
    keeping_dir = tmp_path / "keeping"
    roll = RollKeeping(
        cadence_seconds=1.0,
        ledger_dir=tmp_path / "ledger_empty",
        keeping_dir=keeping_dir,
    )
    obs = roll.run()
    assert obs.kept["total"] == 0
    assert obs.kept["by_axis"] == {}
    # Roll snapshot was written to disk.
    assert (keeping_dir / "roll.json").exists()


def test_roll_keeping_indexes_precedents(tmp_path):
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    for i, axis in enumerate(["governance", "chemistry", "governance"]):
        (ledger_dir / f"prec_{i}.json").write_text(
            json.dumps({
                "precedent_id": f"ledger://test/{i}",
                "axis": axis,
                "dimensions": ["reasoning", "authority_trust"],
                "summary": "test",
                "sealed_at": 1000.0 + i,
            }),
            encoding="utf-8",
        )
    keeping_dir = tmp_path / "keeping"
    roll = RollKeeping(
        cadence_seconds=1.0,
        ledger_dir=ledger_dir,
        keeping_dir=keeping_dir,
    )
    obs = roll.run()
    assert obs.kept["total"] == 3
    assert obs.kept["by_axis"] == {"chemistry": 1, "governance": 2}
    assert obs.kept["by_dimension"] == {"reasoning": 3, "authority_trust": 3}
    # Disk snapshot matches.
    snap = json.loads((keeping_dir / "roll.json").read_text(encoding="utf-8"))
    assert snap["total"] == 3


# ── KeepingLog ───────────────────────────────────────────────────────


def test_keeping_log_append_and_read(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    obs1 = KeepingObservation(
        practice="signal_hum",
        started_at=100.0,
        duration_seconds=0.001,
        kept={"heartbeat": True},
    )
    obs2 = KeepingObservation(
        practice="perimeter_walk",
        started_at=200.0,
        duration_seconds=0.05,
        kept={"total_precedents": 7},
    )
    log.append(obs1)
    log.append(obs2)
    all_obs = log.read()
    assert len(all_obs) == 2
    assert all_obs[0].practice == "signal_hum"
    assert all_obs[1].kept == {"total_precedents": 7}


def test_keeping_log_filter_by_practice(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    for p in ("signal_hum", "perimeter_walk", "signal_hum", "forge_lighting"):
        log.append(KeepingObservation(
            practice=p, started_at=time.time(), duration_seconds=0.0, kept={},
        ))
    hum_only = log.read(practice="signal_hum")
    assert len(hum_only) == 2
    assert all(o.practice == "signal_hum" for o in hum_only)


def test_keeping_log_filter_by_since(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    for t in (100.0, 200.0, 300.0, 400.0):
        log.append(KeepingObservation(
            practice="signal_hum", started_at=t, duration_seconds=0.0, kept={},
        ))
    recent = log.read(since=250.0)
    assert len(recent) == 2
    assert recent[0].started_at == 300.0
    assert recent[1].started_at == 400.0


def test_keeping_log_skips_malformed_lines(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    log.append(KeepingObservation(
        practice="signal_hum", started_at=100.0, duration_seconds=0.0, kept={},
    ))
    # Inject a bad line.
    path = log._path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write("not valid json\n")
        fh.write("\n")  # blank line
    log.append(KeepingObservation(
        practice="signal_hum", started_at=200.0, duration_seconds=0.0, kept={},
    ))
    obs = log.read()
    assert len(obs) == 2  # malformed + blank skipped silently


# ── Keeper orchestrator ──────────────────────────────────────────────


def test_keeper_tick_runs_only_due_practices(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    fast = _NoOpPractice(cadence_seconds=1.0, payload={"name": "fast"})
    fast.name = "fast"
    slow = _NoOpPractice(cadence_seconds=10000.0, payload={"name": "slow"})
    slow.name = "slow"
    keeper = Keeper([fast, slow], log=log, tick_interval_seconds=0.1)

    # First tick: both are due (last_run_at == 0).
    obs = keeper.tick(now=0.0)
    assert len(obs) == 2

    # Second tick at +5s: fast is due, slow is not.
    obs = keeper.tick(now=5.0)
    assert len(obs) == 1
    assert obs[0].practice == "fast"


def test_keeper_continues_through_failing_practice(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    fail = _FailingPractice(cadence_seconds=1.0)
    ok = _NoOpPractice(cadence_seconds=1.0, payload={"ok": True})
    ok.name = "ok_practice"
    keeper = Keeper([fail, ok], log=log, tick_interval_seconds=0.1)
    obs = keeper.tick(now=0.0)
    assert len(obs) == 2
    practice_names = {o.practice for o in obs}
    assert practice_names == {"test_failing", "ok_practice"}
    # The OK practice's payload is intact even though the other failed.
    ok_obs = next(o for o in obs if o.practice == "ok_practice")
    assert ok_obs.kept == {"ok": True}
    assert ok_obs.note == ""


def test_keeper_logs_observations(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    p = _NoOpPractice(cadence_seconds=1.0)
    keeper = Keeper([p], log=log, tick_interval_seconds=0.1)
    keeper.tick(now=0.0)
    keeper.tick(now=2.0)
    keeper.tick(now=4.0)
    logged = log.read()
    assert len(logged) == 3


def test_keeper_run_forever_stops_on_event(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    p = _NoOpPractice(cadence_seconds=0.01)
    keeper = Keeper([p], log=log, tick_interval_seconds=0.01)

    stop = threading.Event()
    captured: list = []

    def _on_tick(observations):
        captured.append(len(observations))
        if len(captured) >= 2:
            stop.set()

    t = threading.Thread(
        target=keeper.run_forever,
        kwargs={"stop_event": stop, "on_tick": _on_tick},
    )
    t.start()
    t.join(timeout=2.0)
    assert not t.is_alive(), "Keeper.run_forever did not stop on event"
    assert len(captured) >= 2


# ── while_you_were_away ──────────────────────────────────────────────


def test_while_you_were_away_summary(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    log.append(KeepingObservation(
        practice="signal_hum", started_at=100.0, duration_seconds=0.0,
        kept={"heartbeat": True, "consecutive_runs": 1},
    ))
    log.append(KeepingObservation(
        practice="signal_hum", started_at=200.0, duration_seconds=0.0,
        kept={"heartbeat": True, "consecutive_runs": 2},
    ))
    log.append(KeepingObservation(
        practice="perimeter_walk", started_at=150.0, duration_seconds=0.0,
        kept={"total_precedents": 5, "chain_intact": True},
    ))

    summary = while_you_were_away(since=0.0, base_dir=tmp_path)
    assert summary["total_observations"] == 3
    assert summary["practices_observed"] == 2
    assert summary["by_practice"]["signal_hum"]["runs"] == 2
    assert summary["by_practice"]["signal_hum"]["latest_kept"]["consecutive_runs"] == 2
    assert summary["by_practice"]["perimeter_walk"]["runs"] == 1


def test_while_you_were_away_respects_since(tmp_path):
    log = KeepingLog(base_dir=tmp_path)
    for t in (100.0, 200.0, 300.0):
        log.append(KeepingObservation(
            practice="signal_hum", started_at=t, duration_seconds=0.0,
            kept={"heartbeat": True},
        ))
    summary = while_you_were_away(since=250.0, base_dir=tmp_path)
    assert summary["total_observations"] == 1
    assert summary["by_practice"]["signal_hum"]["runs"] == 1


# ── default_keeper ───────────────────────────────────────────────────


def test_default_keeper_has_four_canonical_practices(tmp_path):
    keeper = default_keeper(
        ledger_dir=tmp_path / "ledger",
        keeping_dir=tmp_path / "keeping",
    )
    practice_names = [p.name for p in keeper.practices]
    assert practice_names == [
        "signal_hum",
        "perimeter_walk",
        "forge_lighting",
        "roll_keeping",
    ]


def test_default_keeper_runs_one_tick(tmp_path):
    """End-to-end: build the default keeper, tick once, every practice
    fires (all are due on first tick), each emits a non-empty kept
    payload."""
    keeper = default_keeper(
        ledger_dir=tmp_path / "ledger",
        keeping_dir=tmp_path / "keeping",
    )
    observations = keeper.tick(now=0.0)
    assert len(observations) == 4
    # Every practice produced something.
    for obs in observations:
        assert obs.kept, f"practice {obs.practice} produced empty kept payload"
        # Honors the doctrinal invariant: no decision-shaped output.
        forbidden = {"status", "verdict", "pass", "fail"}
        assert not (forbidden & set(obs.kept.keys())), \
            f"practice {obs.practice} returned a decision: {obs.kept}"


def test_env_var_keeping_dir(tmp_path, monkeypatch):
    """CONCORDANCE_KEEPING_DIR overrides the default location."""
    target = tmp_path / "env_keeping"
    monkeypatch.setenv("CONCORDANCE_KEEPING_DIR", str(target))
    log = KeepingLog()  # no explicit base_dir
    assert log.base_dir == target
    log.append(KeepingObservation(
        practice="signal_hum", started_at=0.0, duration_seconds=0.0, kept={},
    ))
    assert (target / "log.jsonl").exists()
