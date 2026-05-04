"""dawn.py — The human's perimeter walk.

A surface that isn't packet-submission-shaped. The user enters at
dawn (or any time of day) and reads what the kingdom has been
keeping while they were away.

Per KoA Trilogy (The Keeping, Anna's chapter):

> *"Someone walks the outer edge of Lookout before the settlement
> wakes... When they stop walking it, someone else begins. Nobody
> assigns the walk."*

The keeping layer (`keeping.py`) does the engine's continuous
body-practice. The audit chain (`ledger.py`) records sealed
decisions. The quarantine airlock (`quarantine.py`) holds packets
in process. None of those is the human surface for *checking on the
kingdom*.

That surface is here. `gather_dawn()` collects the state across all
three; `render_dawn()` produces a human-readable narrative; the CLI
exposes it as `concordance dawn`.

Design constraints:

  * **Read-only.** Dawn does not run practices, seal precedents, or
    admit quarantine packets. It reports what's already been kept.
  * **No-verdict rendering.** Per the engine's doctrine ("the keeping
    is the substrate"), output names what's been kept, never what
    was decided. No PASS/FAIL anywhere in the dawn render.
  * **Honors explicit absence.** Empty kingdom renders as "quiet" —
    not as "OK" or "all good." Quiet is a real state.
  * **Closes with a question.** The Socratic mechanism applies here
    too: a dawn read ends with "what do you want to keep today?"
    not with a directive.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import keeping as _keeping
from . import ledger as _ledger
from . import quarantine as _quarantine


# Default look-back: 24 hours. Tuned to the cadence of a daily walk.
DEFAULT_SINCE_SECONDS = 86400.0


# ── Gathered state ───────────────────────────────────────────────────


@dataclass
class DawnSurface:
    """Snapshot of what the kingdom has been keeping.

    Each field is descriptive of state at gather-time. None of the
    values are decisions — no PASS/FAIL anywhere. The renderer turns
    this into narrative; consumers who prefer structured access can
    use the dataclass directly.
    """
    since_epoch: float
    gathered_at: float
    # Keeping observations summarized per practice.
    keeping_summary: Dict[str, Any] = field(default_factory=dict)
    # Practices that emitted error notes — drift signals, not failures.
    drift_observations: List[Dict[str, Any]] = field(default_factory=list)
    # Recent precedents (audit chain, sealed_at >= since).
    recent_precedents: List[Dict[str, Any]] = field(default_factory=list)
    # Quarantine packets currently held outside CORE.
    held_packets: List[Dict[str, Any]] = field(default_factory=list)
    # Total counts for the "at a glance" summary.
    audit_chain_total: int = 0
    quarantine_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "since_epoch": self.since_epoch,
            "gathered_at": self.gathered_at,
            "keeping_summary": self.keeping_summary,
            "drift_observations": self.drift_observations,
            "recent_precedents": self.recent_precedents,
            "held_packets": self.held_packets,
            "audit_chain_total": self.audit_chain_total,
            "quarantine_total": self.quarantine_total,
        }


# ── Gather ───────────────────────────────────────────────────────────


def gather_dawn(
    *,
    since: Optional[float] = None,
    keeping_dir: Optional[Path] = None,
    ledger_dir: Optional[Path] = None,
    quarantine_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> DawnSurface:
    """Collect the kingdom's recent state. Read-only.

    Args:
      since: Unix epoch seconds; only include observations / precedents
        sealed after this time. Default: now - 24h.
      keeping_dir / ledger_dir / quarantine_dir: directory overrides for
        tests or alternate deployments. Each falls back to the module's
        canonical default.
      now: logical current time (override for tests/replay).

    Returns:
      DawnSurface with summarized keeping, drift signals, recent
      precedents, and held packets.
    """
    now_epoch = now if now is not None else time.time()
    since_epoch = since if since is not None else (now_epoch - DEFAULT_SINCE_SECONDS)

    # ── Keeping summary
    keeping_summary = _keeping.while_you_were_away(
        since=since_epoch, base_dir=keeping_dir,
    )

    # ── Drift observations: practices that recorded an error in the note.
    log = _keeping.KeepingLog(base_dir=keeping_dir)
    drift_observations: List[Dict[str, Any]] = []
    for obs in log.read(since=since_epoch):
        if obs.note:
            drift_observations.append({
                "practice": obs.practice,
                "started_at": obs.started_at,
                "note": obs.note,
                "kept": obs.kept,
            })

    # ── Audit chain: precedents sealed since the cutoff.
    all_precedents = _ledger.list_precedents(ledger_dir)
    recent_precedents: List[Dict[str, Any]] = []
    for p in all_precedents:
        sealed_at = p.get("sealed_at")
        if isinstance(sealed_at, (int, float)) and sealed_at >= since_epoch:
            recent_precedents.append({
                "precedent_id": p.get("precedent_id", "(no id)"),
                "axis": p.get("axis", "unknown"),
                "summary": p.get("summary", ""),
                "sealed_at": sealed_at,
            })
    # Newest first.
    recent_precedents.sort(key=lambda x: x["sealed_at"], reverse=True)

    # ── Quarantine: anything held outside CORE.
    store = _quarantine.QuarantineStore(base_dir=quarantine_dir)
    all_packets = store.list_all()
    held_packets: List[Dict[str, Any]] = []
    for pkt in all_packets:
        if pkt.zone != _quarantine.Zone.CORE.value:
            held_packets.append({
                "id": pkt.id,
                "zone": pkt.zone,
                "hypothesis": pkt.hypothesis or pkt.normalized[:80],
                "decision": pkt.decision,
                "rejection_reason": pkt.rejection_reason,
                "modified_at": pkt.modified_at,
            })
    held_packets.sort(key=lambda x: x["modified_at"], reverse=True)

    return DawnSurface(
        since_epoch=since_epoch,
        gathered_at=now_epoch,
        keeping_summary=keeping_summary,
        drift_observations=drift_observations,
        recent_precedents=recent_precedents,
        held_packets=held_packets,
        audit_chain_total=len(all_precedents),
        quarantine_total=len(all_packets),
    )


# ── Render ───────────────────────────────────────────────────────────


def _format_epoch(t: float) -> str:
    """Human-readable timestamp for the render. UTC for portability."""
    if not t:
        return "(never)"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t))
    except (ValueError, OSError):
        return f"epoch {t}"


def _format_window(since: float, now: float) -> str:
    """Render the look-back window."""
    duration = max(0.0, now - since)
    if duration < 3600:
        return f"the last {duration / 60:.0f} minutes"
    if duration < 86400:
        return f"the last {duration / 3600:.1f} hours"
    return f"the last {duration / 86400:.1f} days"


def render_dawn(surface: DawnSurface) -> str:
    """Render a DawnSurface as human-readable markdown.

    Sections (each omitted when empty):
      1. The kingdom at a glance — counts + window
      2. What the keeping kept — per-practice summary
      3. Drift the keeping noticed — practices that recorded errors
      4. New precedents — what was sealed in the window
      5. Held packets — quarantine status
      6. Closing question — Socratic
    """
    lines: List[str] = []
    window = _format_window(surface.since_epoch, surface.gathered_at)

    # ── Header
    lines.append("# Dawn")
    lines.append("")
    lines.append(
        f"You've stepped onto the perimeter at "
        f"{_format_epoch(surface.gathered_at)}. "
        f"This is what's been kept across {window}."
    )
    lines.append("")

    # ── At a glance
    lines.append("## At a glance")
    lines.append("")
    lines.append(
        f"- **{surface.audit_chain_total}** precedents currently in the "
        f"audit chain"
    )
    lines.append(
        f"- **{surface.quarantine_total}** packets in the quarantine airlock"
    )
    practices_observed = surface.keeping_summary.get("practices_observed", 0)
    total_observations = surface.keeping_summary.get("total_observations", 0)
    if total_observations:
        lines.append(
            f"- **{total_observations}** keeping observations across "
            f"**{practices_observed}** practices in the window"
        )
    else:
        lines.append("- _The keeping log is quiet for this window._")
    lines.append("")

    # ── What the keeping kept
    by_practice = surface.keeping_summary.get("by_practice", {})
    if by_practice:
        lines.append("## What the keeping kept")
        lines.append("")
        for practice_name in sorted(by_practice.keys()):
            data = by_practice[practice_name]
            runs = data.get("runs", 0)
            latest_at = _format_epoch(data.get("latest_at", 0))
            lines.append(f"### `{practice_name}` — {runs} run(s)")
            lines.append(f"Latest: {latest_at}")
            kept = data.get("latest_kept") or {}
            if kept:
                lines.append("")
                for k, v in kept.items():
                    lines.append(f"- **{k}**: `{_summarize(v)}`")
            note = data.get("latest_note")
            if note:
                lines.append("")
                lines.append(f"_Note: {note}_")
            lines.append("")

    # ── Drift the keeping noticed
    if surface.drift_observations:
        lines.append("## Drift the keeping noticed")
        lines.append("")
        lines.append(
            "_These are practices that recorded an error during the window. "
            "Drift is visibility, not failure — surfacing here so it can be "
            "addressed._"
        )
        lines.append("")
        for d in surface.drift_observations:
            lines.append(
                f"- `{d['practice']}` at {_format_epoch(d['started_at'])}: "
                f"{d['note']}"
            )
        lines.append("")

    # ── New precedents
    if surface.recent_precedents:
        lines.append("## New precedents in the window")
        lines.append("")
        for p in surface.recent_precedents:
            lines.append(
                f"- **`{p['precedent_id']}`** ({p['axis']}) — "
                f"{p['summary']}"
            )
            lines.append(f"  _sealed_ {_format_epoch(p['sealed_at'])}")
        lines.append("")

    # ── Held packets
    if surface.held_packets:
        lines.append("## Packets in the airlock")
        lines.append("")
        by_zone: Dict[str, List[Dict[str, Any]]] = {}
        for pkt in surface.held_packets:
            by_zone.setdefault(pkt["zone"], []).append(pkt)
        for zone in sorted(by_zone.keys()):
            count = len(by_zone[zone])
            lines.append(f"### {zone} ({count})")
            for pkt in by_zone[zone]:
                detail = pkt.get("hypothesis") or "(no hypothesis yet)"
                lines.append(f"- `{pkt['id']}` — {detail}")
                if pkt.get("rejection_reason"):
                    lines.append(f"  _rejected:_ {pkt['rejection_reason']}")
            lines.append("")

    # ── Socratic close
    lines.append("## What do you want to keep today?")
    lines.append("")
    if not by_practice and not surface.recent_precedents and not surface.held_packets:
        lines.append(
            "The kingdom is quiet. That is itself a kept state. The next "
            "move is yours."
        )
    elif surface.drift_observations:
        lines.append(
            "Drift was visible in the window — that is what the keeping is "
            "for. The next move is yours: address the drift, or note that "
            "it's known and continue."
        )
    elif surface.held_packets:
        lines.append(
            "There are packets in the airlock waiting on you — for "
            "decontamination, for a Guide decision, or for further work. "
            "The next move is yours."
        )
    else:
        lines.append(
            "The keeping ran while you were away. The kingdom is held. "
            "The next move is yours."
        )
    lines.append("")

    return "\n".join(lines)


def _summarize(value: Any) -> str:
    """Compress a kept value into a one-liner for the bullet list."""
    if isinstance(value, dict):
        if len(value) > 3:
            return f"({len(value)} fields)"
        return ", ".join(f"{k}={_short(v)}" for k, v in value.items())
    if isinstance(value, list):
        return f"[{len(value)} items]"
    return _short(value)


def _short(value: Any) -> str:
    s = str(value)
    if len(s) > 60:
        return s[:57] + "..."
    return s


__all__ = [
    "DawnSurface",
    "DEFAULT_SINCE_SECONDS",
    "gather_dawn",
    "render_dawn",
]
