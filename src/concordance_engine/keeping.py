"""keeping.py — The liturgical layer.

The four gates run on demand. The keeping runs between firings.

Per KoA Trilogy (The Keeping, Book Three): the kingdom's validation is
not climactic; it is liturgical body-practice that runs whether or
not anyone is observing. The forge is lit at the usual hour. Someone
walks the perimeter before the settlement wakes. The Roll is kept by
forty clan-keepers in parallel. The 72 Hz signal runs in the
limestone whether anyone listens.

Lintel of the Lookout archive (Nadiya's first entry): *"We are for
keeping each other."*

What this module adds to the engine:

  * **Continuous-time process** distinct from on-demand verification.
    The engine's gates fire when a packet arrives. The keeping fires
    on its own rhythm — proves the substrate is real before, during,
    and after observation.

  * **Four canonical practices**, each one keeping a gate alive between
    decision-points:

      - SignalHum     → GOD     (the substrate heartbeat)
      - PerimeterWalk → FLOOR   (the audit chain's boundary)
      - ForgeLighting → RED     (the verifier layer's readiness)
      - RollKeeping   → BROTHERS (the index of who is known)

  * **A separate keeping log**, parallel to the audit chain. The chain
    records decisions; the log records practice. The two together —
    archive (written) + practice (body) — are the BROTHERS gate at
    depth: validation isn't single-channel even when the channel is
    the archive itself.

  * **`while_you_were_away()`** — surface that returns what the keeping
    kept while the user was away from the engine. The keeping has been
    running; here is what it observed.

Doctrinal commitments encoded here:

  * **The keeping is the substrate.** Per Matt 2026-05-03: '"No answers"
    was wrong. The keeping does a better job.' Each practice's output
    names what is being *kept*, never what was *decided*. A practice
    that returns pass/fail has been written wrong.

  * **The signal does not know it is being received.** Practices run
    regardless of whether their output is read. The keeping log fills
    whether or not `while_you_were_away()` is ever called.

  * **A failing practice does not break the keeping.** Per KoA: when
    one keeper falls, another begins. The Keeper orchestrator catches
    practice failures and continues — the keeping survives a broken
    forge or a missing perimeter walk.

Persistence is file-backed under `lw/keeping/` parallel to the audit
chain at `lw/ledger/` and the quarantine packets at `lw/quarantine/`.
Override via the `CONCORDANCE_KEEPING_DIR` environment variable.
"""
from __future__ import annotations

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ── Locations ────────────────────────────────────────────────────────


def _default_keeping_dir() -> Path:
    """Repo-root `lw/keeping/` by default; overridable via env var."""
    override = os.environ.get("CONCORDANCE_KEEPING_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "lw" / "keeping"


# ── Observation (the unit of practice output) ────────────────────────


@dataclass
class KeepingObservation:
    """One emission from a practice run.

    Observations are *descriptive*, not *decisional*. A practice does
    not return PASS/FAIL — it returns what it kept. The reader of the
    log decides what (if anything) to do with the observation.
    """
    practice: str
    started_at: float
    duration_seconds: float
    kept: Dict[str, Any]
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeepingObservation":
        return cls(
            practice=d["practice"],
            started_at=float(d["started_at"]),
            duration_seconds=float(d["duration_seconds"]),
            kept=dict(d.get("kept") or {}),
            note=str(d.get("note") or ""),
        )


# ── Practice base class ──────────────────────────────────────────────


class KeepingPractice(ABC):
    """A body-practice that runs at its own cadence.

    Each practice has:
      * a `name` (string identifier; appears in the log)
      * a `cadence_seconds` (how often it runs; the keeper checks if
        the practice is due each tick)
      * a `_do_run()` method that performs the practice and returns the
        kept payload as a dict

    The base `run()` method handles timing, exception isolation, and
    observation construction. Subclasses just implement `_do_run()`.
    """
    name: str = "unnamed_practice"

    def __init__(self, *, cadence_seconds: float):
        if cadence_seconds <= 0:
            raise ValueError(f"cadence_seconds must be positive, got {cadence_seconds}")
        self.cadence_seconds = float(cadence_seconds)
        # `None` = practice has never run yet. Sentinel float values
        # would collide with legitimate now=0.0 in tests/replay.
        self._last_run_at: Optional[float] = None
        self._consecutive_runs: int = 0

    @property
    def last_run_at(self) -> Optional[float]:
        return self._last_run_at

    @property
    def consecutive_runs(self) -> int:
        return self._consecutive_runs

    def due(self, now: Optional[float] = None) -> bool:
        """True if the cadence has elapsed since the last run.
        First call is always due."""
        now = now if now is not None else time.time()
        if self._last_run_at is None:
            return True
        return (now - self._last_run_at) >= self.cadence_seconds

    def run(self, *, now: Optional[float] = None) -> KeepingObservation:
        """Perform the practice once. Always returns an observation —
        a failure inside `_do_run()` is captured in the observation's
        `note` field, not raised. The keeping does not break.

        Time handling: `started_at` reports the logical time the
        practice began (the injected `now` or wall-clock if absent).
        `duration_seconds` always reports real wall-clock elapsed time
        for the practice's body. `_last_run_at` is set to the logical
        start time so cadence checks remain deterministic when callers
        inject `now` (tests, simulation, replay)."""
        logical_start = now if now is not None else time.time()
        real_start = time.time()
        try:
            kept = self._do_run()
            note = ""
        except Exception as e:
            kept = {"error": str(e), "exception_type": type(e).__name__}
            note = f"practice failed: {type(e).__name__}: {e}"
        real_end = time.time()
        self._last_run_at = logical_start
        self._consecutive_runs += 1
        return KeepingObservation(
            practice=self.name,
            started_at=logical_start,
            duration_seconds=max(0.0, real_end - real_start),
            kept=kept,
            note=note,
        )

    @abstractmethod
    def _do_run(self) -> Dict[str, Any]:
        """Subclasses implement. Return the kept payload as a dict.
        Should NOT return decisions — only descriptions of what's been
        kept this run."""


# ── SignalHum (GOD gate kept alive) ──────────────────────────────────


class SignalHum(KeepingPractice):
    """The substrate heartbeat. Runs at high frequency; emits a
    timestamp and consecutive-run count. Proves the keeping is alive.

    Per KoA The Door epilogue: *"The signal does not know it is being
    received. It does not need to know. It runs because it was made to
    run."* This practice is the signal made code-form.

    Default cadence: 60 seconds.
    """
    name = "signal_hum"

    def __init__(self, cadence_seconds: float = 60.0):
        super().__init__(cadence_seconds=cadence_seconds)

    def _do_run(self) -> Dict[str, Any]:
        return {
            "heartbeat": True,
            "consecutive_runs": self._consecutive_runs + 1,
        }


# ── PerimeterWalk (FLOOR gate kept alive) ────────────────────────────


class PerimeterWalk(KeepingPractice):
    """Walks the audit chain. Keeps the boundary visible: how many
    precedents are sealed, how many are intact, where drift has begun.

    Per KoA The Keeping (Anna's chapter): *"Someone walks the outer
    edge of Lookout before the settlement wakes... When they stop
    walking it, someone else begins. Nobody assigns the walk."*

    Default cadence: 1 hour.
    """
    name = "perimeter_walk"

    def __init__(
        self,
        cadence_seconds: float = 3600.0,
        ledger_dir: Optional[Path] = None,
    ):
        super().__init__(cadence_seconds=cadence_seconds)
        self.ledger_dir = ledger_dir

    def _do_run(self) -> Dict[str, Any]:
        # Lazy import: keeping.py loads cleanly even if ledger has
        # transitive issues at import time.
        from . import ledger as _ledger
        report = _ledger.verify_chain(self.ledger_dir)
        return {
            "total_precedents": int(report.get("total", 0)),
            "verified": int(report.get("verified", 0)),
            "unsigned_count": len(report.get("unsigned", []) or []),
            "tampered_count": len(report.get("tampered", []) or []),
            "broken_links_count": len(report.get("broken_links", []) or []),
            "chain_intact": bool(report.get("ok", True)),
        }


# ── ForgeLighting (RED gate kept alive) ──────────────────────────────


class ForgeLighting(KeepingPractice):
    """Lights the forge. Imports each canonical verifier module to
    confirm it loads cleanly — the smith arrived, the bellows work,
    the fire takes. Does not run a full verification cycle (that is
    the test suite's job); the forge-lighting is a daily liveness
    signal.

    Per KoA: the forge is lit at the usual hour, regardless of need.
    The kingdom's making things stays ready.

    Default cadence: 1 hour. Domain list is small by default —
    canonical verifier modules. Extend by passing `domains=`.
    """
    name = "forge_lighting"

    _DEFAULT_DOMAINS = (
        "chemistry",
        "mathematics",
        "physics",
        "statistics",
        "scripture",
        "phase",
    )

    def __init__(
        self,
        cadence_seconds: float = 3600.0,
        domains: Optional[List[str]] = None,
    ):
        super().__init__(cadence_seconds=cadence_seconds)
        self.domains = list(domains) if domains else list(self._DEFAULT_DOMAINS)

    def _do_run(self) -> Dict[str, Any]:
        responses: Dict[str, str] = {}
        for domain in self.domains:
            try:
                mod_path = f"concordance_engine.verifiers.{domain}"
                __import__(mod_path)
                responses[domain] = "lit"
            except Exception as e:
                responses[domain] = f"cold ({type(e).__name__})"
        all_lit = all(v == "lit" for v in responses.values())
        cold_count = sum(1 for v in responses.values() if v != "lit")
        return {
            "verifiers_lit": responses,
            "all_lit": all_lit,
            "cold_count": cold_count,
        }


# ── RollKeeping (BROTHERS gate kept alive) ───────────────────────────


class RollKeeping(KeepingPractice):
    """Maintains the Roll: a current-state index of every precedent in
    the audit chain, organized by axis and by dimension. Snapshots the
    Roll to disk on each run for inspection.

    Per KoA: *"The marks here are copied upridge into the Roll each
    season. It's how the kingdom remembers who exists."* The Roll is
    the kingdom's continuous-state knowledge of itself; it answers
    *who is currently known*, not *what was once decided*.

    Default cadence: 1 day.
    """
    name = "roll_keeping"

    def __init__(
        self,
        cadence_seconds: float = 86400.0,
        ledger_dir: Optional[Path] = None,
        keeping_dir: Optional[Path] = None,
    ):
        super().__init__(cadence_seconds=cadence_seconds)
        self.ledger_dir = ledger_dir
        self.keeping_dir = keeping_dir

    def _do_run(self) -> Dict[str, Any]:
        from . import ledger as _ledger
        precedents = _ledger.list_precedents(self.ledger_dir)
        by_axis: Dict[str, int] = {}
        by_dimension: Dict[str, int] = {}
        for p in precedents:
            axis = p.get("axis") or "unknown"
            by_axis[axis] = by_axis.get(axis, 0) + 1
            for dim in (p.get("dimensions") or []):
                if isinstance(dim, str):
                    by_dimension[dim] = by_dimension.get(dim, 0) + 1
        roll = {
            "total": len(precedents),
            "by_axis": dict(sorted(by_axis.items())),
            "by_dimension": dict(sorted(by_dimension.items())),
            "kept_at": time.time(),
        }
        target_dir = self.keeping_dir or _default_keeping_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "roll.json").write_text(
            json.dumps(roll, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return roll


# ── Keeping log (separate from the audit chain) ──────────────────────


class KeepingLog:
    """Append-only log of every practice run. Distinct from the audit
    chain — the chain records decisions; the log records practice. One
    JSONL line per observation."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or _default_keeping_dir()

    def _path(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir / "log.jsonl"

    def append(self, observation: KeepingObservation) -> None:
        line = json.dumps(observation.to_dict(), default=str)
        with self._path().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read(
        self,
        *,
        since: Optional[float] = None,
        practice: Optional[str] = None,
    ) -> List[KeepingObservation]:
        path = self._path()
        if not path.exists():
            return []
        out: List[KeepingObservation] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since is not None and d.get("started_at", 0) < since:
                    continue
                if practice is not None and d.get("practice") != practice:
                    continue
                try:
                    out.append(KeepingObservation.from_dict(d))
                except (KeyError, TypeError, ValueError):
                    continue
        return out

    def clear(self) -> None:
        """Truncate the log. Use only for tests; the keeping is
        otherwise append-only."""
        path = self._path()
        if path.exists():
            path.unlink()


# ── Keeper (orchestrator) ────────────────────────────────────────────


class Keeper:
    """Orchestrates a set of practices.

    Two modes:
      * `tick(now)` — runs any practice whose cadence has elapsed.
        Returns the observations from this tick.
      * `run_forever(stop_event)` — daemon-style loop. Ticks every
        `tick_interval_seconds`. Stops when the event is set.

    A practice that fails does not break the keeper. The error is
    captured in the observation's `note` field and the keeper
    continues. Per KoA: when one keeper falls, another begins.
    """

    def __init__(
        self,
        practices: List[KeepingPractice],
        *,
        log: Optional[KeepingLog] = None,
        tick_interval_seconds: float = 30.0,
    ):
        if tick_interval_seconds <= 0:
            raise ValueError(
                f"tick_interval_seconds must be positive, got {tick_interval_seconds}"
            )
        self.practices = list(practices)
        self.log = log or KeepingLog()
        self.tick_interval_seconds = float(tick_interval_seconds)

    def tick(self, *, now: Optional[float] = None) -> List[KeepingObservation]:
        """Run any practice whose cadence has elapsed. Returns the
        list of observations from this tick (may be empty)."""
        now = now if now is not None else time.time()
        observations: List[KeepingObservation] = []
        for practice in self.practices:
            if practice.due(now):
                obs = practice.run(now=now)
                self.log.append(obs)
                observations.append(obs)
        return observations

    def run_forever(
        self,
        stop_event: threading.Event,
        *,
        on_tick: Optional[Callable[[List[KeepingObservation]], None]] = None,
    ) -> None:
        """Daemon-style loop. Blocks until the stop event is set.
        Optional `on_tick` callback receives each tick's observations
        (useful for surfacing keeping output to logs, dashboards)."""
        while not stop_event.is_set():
            observations = self.tick()
            if on_tick is not None and observations:
                try:
                    on_tick(observations)
                except Exception:
                    # Callback failure does not stop the keeping.
                    pass
            stop_event.wait(self.tick_interval_seconds)


# ── While you were away ──────────────────────────────────────────────


def while_you_were_away(
    *,
    since: float,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Surface what the keeping kept while you were away.

    Returns a structured report: per-practice run-count + the latest
    observation's kept payload + when it last ran.

    Per KoA: when Anna walks the perimeter at dawn she does not ask
    what happened overnight; she reads what's been kept. This is that
    surface.
    """
    log = KeepingLog(base_dir=base_dir)
    observations = log.read(since=since)
    by_practice: Dict[str, List[KeepingObservation]] = {}
    for o in observations:
        by_practice.setdefault(o.practice, []).append(o)
    summary: Dict[str, Any] = {
        "since": since,
        "total_observations": len(observations),
        "practices_observed": len(by_practice),
        "by_practice": {},
    }
    for practice_name, items in by_practice.items():
        latest = items[-1]
        summary["by_practice"][practice_name] = {
            "runs": len(items),
            "latest_kept": latest.kept,
            "latest_at": latest.started_at,
            "latest_note": latest.note,
        }
    return summary


# ── Default Keeper builder ───────────────────────────────────────────


def default_keeper(
    *,
    ledger_dir: Optional[Path] = None,
    keeping_dir: Optional[Path] = None,
    tick_interval_seconds: float = 30.0,
) -> Keeper:
    """Build a Keeper with the canonical four practices wired:
    SignalHum + PerimeterWalk + ForgeLighting + RollKeeping.

    Cadences are the canonical defaults (60s / 1h / 1h / 1d). For
    tests or short-lived demos, build a Keeper directly and pass
    short-cadence practices."""
    practices: List[KeepingPractice] = [
        SignalHum(),
        PerimeterWalk(ledger_dir=ledger_dir),
        ForgeLighting(),
        RollKeeping(ledger_dir=ledger_dir, keeping_dir=keeping_dir),
    ]
    log = KeepingLog(base_dir=keeping_dir)
    return Keeper(
        practices,
        log=log,
        tick_interval_seconds=tick_interval_seconds,
    )


__all__ = [
    "KeepingPractice",
    "KeepingObservation",
    "SignalHum",
    "PerimeterWalk",
    "ForgeLighting",
    "RollKeeping",
    "KeepingLog",
    "Keeper",
    "default_keeper",
    "while_you_were_away",
]
