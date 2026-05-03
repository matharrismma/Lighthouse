"""live.py — The ongoing companion. The harvester at the door.

One tool. Persistent. Never reloads. Its job is to remember, to be an
ear, to be a guide that doesn't stray, and to harvest seeds from the
disorder of writing.

Per Matt 2026-05-03 (in three pieces):

  *"We need to make this a practical tool. Something that gets the
   full features of the work in a simple tool. This is an ongoing
   tool. It never reloads. Its job is to remember and be an ear and
   a guide that doesn't stray."*

  *"God delivers wisdom in packets. Knowledge. Seeds scattered. We
   are harvesting the seeds and creating a seed bank. The bank can
   lead to growth around the world."*

  *"We have your library, but we also have a shelf that is external.
   Anyone can reach for. You create community by showing your
   interests."*

  *"It's 3 tier. Our central is the smallest. The community and the
   individual."*

This is the harvest surface. The user pours out (stream of
consciousness); the engine listens, identifies what shape the seeds
carry, and adds harvested seeds to the user's library. From there
seeds move upward through three tiers, each smaller and more rigorously
gated than the last:

```
  CENTRAL (smallest)  →  the seed bank; sealed precedents in the
                          audit chain; each one survived the four gates
            ▲
            │  /seal — future move; promotion requires gate-survival
            │
  COMMUNITY (middle)  →  the shelf; published seeds that other people
                          can reach for; community forms around shared
                          anchors and themes
            ▲
            │  /publish
            │
  INDIVIDUAL (largest) →  your library; every raw harvested seed,
                          private to you
```

Promotion is by *survival*. A seed reaches the shelf when you choose
to publish it. A seed reaches central when it survives the four
gates and is sealed to the audit chain.

This module ships INDIVIDUAL + COMMUNITY tiers in the live tool.
CENTRAL tier promotion (`/seal`) is queued for the next iteration —
it requires translating a journal seed into a packet and running it
through the gate pipeline. Until then, the live tool exposes
read-only access to the central tier via `/precedent` (closest-case
overlay against existing sealed precedents).

Architecture stays simple: shelf membership is encoded as the user
tag `shelf`. No new schema. `/publish <id>` adds the tag; `/unshelf
<id>` removes it; `/shelf` lists what's currently on your shelf.

This module is the *single* human-facing surface that brings together
the engine's pieces:

  * Stream-of-consciousness writing → journal capture + calibration
  * Threading entries that share signal (recurring anchors,
    action shapes, scope)
  * The keeping running in the background (signal hum, perimeter
    walk, forge lighting, roll keeping) — never reloads, never
    pauses while the session is open
  * Scripture anchor resolution (Layer 0 lookups when present)
  * Closest-precedent overlay against the audit chain
  * "What's been kept while you were away" surface

What the live session does NOT do:

  * Generate answer text. The engine reads what's there. It surfaces
    shape, precedent, calibration. It never speaks AS the user.
  * Push toward decisions. Calibration is measurement, not verdict.
  * Drift into authority-answers. The conduit doctrine: the engine
    is Mercel's father's instruments — they read what's there.

Architecture:

  * Main thread: the REPL loop. Reads a line at a time. Bare text
    is captured as a journal entry. Commands prefixed with `/` are
    explicit operations.
  * Background thread: the Keeper running its four canonical
    practices on their cadences (Signal hum every 60s, etc.).
    Practices write to the keeping log silently; the REPL is not
    interrupted.
  * State on disk: everything persists in lw/journal/, lw/keeping/,
    lw/ledger/, lw/quarantine/. Closing the session and reopening
    picks up exactly where you left off. The tool never reloads
    because it never needs to.

Multi-line writing: a bare line of text is captured as a single-line
entry. `/write` enters multi-line mode — type until you put `.` on
its own line, and the whole block becomes a single entry.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import journal as _journal
from . import keeping as _keeping


# ── Configuration ────────────────────────────────────────────────────


@dataclass
class LiveConfig:
    """Tunables for the live session. Defaults are conservative."""
    # Background keeper tick interval. Practice cadences are still
    # canonical (60s / 1h / 1h / 1d); tick checks if any are due.
    tick_interval_seconds: float = 30.0
    # Whether to launch the background keeper. Off in tests.
    run_keeper: bool = True
    # Number of recent entries shown by `/recent` default.
    default_recent_count: int = 5
    # Look-back window (seconds) for `/keeping`.
    default_keeping_window: float = 86400.0


# ── Session state ────────────────────────────────────────────────────


@dataclass
class LiveSession:
    """In-memory state for one ongoing session.

    The session itself is ephemeral; everything load-bearing lives on
    disk. The session just keeps a few breadcrumbs for command
    shortcuts (e.g. `/thread` with no id threads the most recent entry).
    """
    config: LiveConfig = field(default_factory=LiveConfig)
    # The id of the most recently captured entry; used as default
    # when a command (thread, show, annotate) takes no entry id.
    last_entry_id: Optional[str] = None
    # The session's start time, so /keeping can default to "since I
    # opened this session" rather than fixed 24h.
    started_at: float = field(default_factory=time.time)
    # Background keeper handle (set when run() starts the keeper).
    _keeper_thread: Optional[threading.Thread] = None
    _keeper_stop: Optional[threading.Event] = None


# ── Output rendering ─────────────────────────────────────────────────


def _print(s: str = "") -> None:
    """Write to stdout with explicit newline handling. Wrapper exists
    so tests can swap I/O."""
    print(s)


def _render_capture(entry: _journal.JournalEntry,
                    cal: _journal.Calibration) -> str:
    """Compact rendering of a fresh capture for the live session.
    Shorter than the full `render_calibration` so the REPL stays
    breathable."""
    lines: List[str] = []
    lines.append(f"  [{entry.id}] kept.")
    cat = entry.categorization
    pieces: List[str] = []
    if cat.detected_anchors:
        pieces.append(f"anchors: {', '.join(cat.detected_anchors)}")
    if cat.detected_action_shapes:
        pieces.append(f"actions: {', '.join(cat.detected_action_shapes)}")
    if cat.detected_scope:
        pieces.append(f"scope: {cat.detected_scope}")
    if pieces:
        lines.append("  " + " | ".join(pieces))
    # Calibration breadcrumbs — only what's load-bearing for this entry.
    cal_pieces: List[str] = []
    if cal.recurring_anchors:
        cal_pieces.append(
            f"return to {', '.join(cal.recurring_anchors)}"
        )
    if cal.scope_shifted:
        cal_pieces.append(
            f"scope shifted from {cal.previous_scope} → "
            f"{cat.detected_scope}"
        )
    if cal.action_pattern_note:
        cal_pieces.append(cal.action_pattern_note)
    if cal_pieces:
        lines.append("  · " + "; ".join(cal_pieces))
    elif cal.total_entries_to_date == 1:
        lines.append("  · first entry. The keeping has begun.")
    return "\n".join(lines)


def _render_thread(source_id: str,
                   source: _journal.JournalEntry,
                   related: List[_journal.JournalEntry]) -> str:
    if not related:
        return f"  (no entries thread with {source_id})"
    src_anchors = set(source.categorization.detected_anchors)
    src_actions = set(source.categorization.detected_action_shapes)
    src_scope = source.categorization.detected_scope
    lines: List[str] = [f"  Threading with `{source_id}`:"]
    for e in related:
        preview = e.text.replace("\n", " ").strip()[:70]
        shared: List[str] = []
        if src_anchors & set(e.categorization.detected_anchors):
            shared.append(
                "anchors: "
                + ", ".join(src_anchors & set(e.categorization.detected_anchors))
            )
        if src_actions & set(e.categorization.detected_action_shapes):
            shared.append(
                "actions: "
                + ", ".join(src_actions & set(e.categorization.detected_action_shapes))
            )
        if (src_scope and src_scope == e.categorization.detected_scope):
            shared.append(f"scope: {src_scope}")
        shared_str = " | ".join(shared) if shared else "(via persistence)"
        lines.append(f"    {e.id}  {preview}")
        lines.append(f"        shared → {shared_str}")
    return "\n".join(lines)


def _render_keeping(summary: Dict) -> str:
    if not summary.get("by_practice"):
        return "  (the keeping log is quiet for this window)"
    lines: List[str] = ["  What's been kept:"]
    for practice in sorted(summary["by_practice"].keys()):
        data = summary["by_practice"][practice]
        runs = data.get("runs", 0)
        kept = data.get("latest_kept") or {}
        # Compress the latest kept payload to a one-liner.
        kept_summary = ", ".join(
            f"{k}={_short(v)}" for k, v in kept.items()
        )
        if len(kept_summary) > 70:
            kept_summary = kept_summary[:67] + "..."
        lines.append(f"    {practice}: {runs} run(s) — {kept_summary}")
    return "\n".join(lines)


def _short(value) -> str:
    s = str(value)
    if len(s) > 30:
        return s[:27] + "..."
    return s


# ── Commands ─────────────────────────────────────────────────────────


_SHELF_TAG = "shelf"


def _cmd_help(_session: LiveSession, _args: str) -> str:
    return """  Commands (prefix with /). Bare text = harvest a seed.

  INDIVIDUAL — your library (every seed harvested):
    /write              Multi-line writing. End with `.` on its own line.
    /thread [id]        Seeds that share signal with this one (default: last).
    /show [id]          Show a seed in full.
    /recent [N]         The N most recent seeds (default 5).
    /keeping [hours]    What the keeping has observed (default: 24h).

  COMMUNITY — your shelf (published seeds; anyone can reach for them):
    /shelf              List what's currently on your shelf.
    /publish [id]       Put a seed on the shelf (default: last).
    /unshelf [id]       Take a seed off the shelf (default: last).

  CENTRAL — the seed bank (sealed precedents; survived the four gates):
    /precedent          Closest precedent for the last seed (read-only).
    /anchor <ref>       Look up a scripture reference against Layer 0.

  Session:
    /help               This.
    /quit               Leave. The keeping continues."""


def _cmd_thread(session: LiveSession, args: str) -> str:
    entry_id = args.strip() or session.last_entry_id
    if not entry_id:
        return "  (no entry to thread; capture one first or pass /thread <id>)"
    store = _journal.JournalStore()
    source = store.load(entry_id)
    if source is None:
        return f"  (no entry found with id {entry_id})"
    related = _journal.thread(entry_id)
    return _render_thread(entry_id, source, related)


def _cmd_show(session: LiveSession, args: str) -> str:
    entry_id = args.strip() or session.last_entry_id
    if not entry_id:
        return "  (no entry to show; capture one first or pass /show <id>)"
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return f"  (no entry found with id {entry_id})"
    lines: List[str] = [f"  [{entry.id}]"]
    ts = time.strftime("%Y-%m-%d %H:%M:%S",
                       time.gmtime(entry.written_at))
    lines.append(f"  written: {ts}")
    if entry.user_tags:
        lines.append(f"  tags: {', '.join(entry.user_tags)}")
    lines.append("")
    for line in entry.text.splitlines() or [entry.text]:
        lines.append(f"  | {line}")
    cat = entry.categorization
    lines.append("")
    lines.append("  what was heard:")
    if cat.detected_anchors:
        lines.append(f"    anchors: {', '.join(cat.detected_anchors)}")
    if cat.detected_action_shapes:
        lines.append(f"    actions: {', '.join(cat.detected_action_shapes)}")
    if cat.detected_scope:
        lines.append(f"    scope: {cat.detected_scope}")
    if entry.annotations:
        lines.append("")
        lines.append(f"  annotations ({len(entry.annotations)}):")
        for a in entry.annotations:
            ats = time.strftime("%Y-%m-%d %H:%M:%S",
                                time.gmtime(a.timestamp))
            lines.append(f"    {ats}: {a.note}")
    return "\n".join(lines)


def _cmd_recent(session: LiveSession, args: str) -> str:
    n_str = args.strip()
    n = session.config.default_recent_count
    if n_str:
        try:
            n = max(1, int(n_str))
        except ValueError:
            return f"  (could not parse '{n_str}' as a count)"
    store = _journal.JournalStore()
    entries = store.list_all()[:n]
    if not entries:
        return "  (no entries yet)"
    lines: List[str] = [f"  Most recent {len(entries)} entries:"]
    for e in entries:
        ts = time.strftime("%Y-%m-%d %H:%M",
                           time.gmtime(e.written_at))
        preview = e.text.replace("\n", " ").strip()[:70]
        lines.append(f"    {e.id}  {ts}  {preview}")
    return "\n".join(lines)


def _cmd_keeping(session: LiveSession, args: str) -> str:
    hours_str = args.strip()
    window_seconds = session.config.default_keeping_window
    if hours_str:
        try:
            window_seconds = max(60.0, float(hours_str) * 3600.0)
        except ValueError:
            return f"  (could not parse '{hours_str}' as hours)"
    since = time.time() - window_seconds
    summary = _keeping.while_you_were_away(since=since)
    return _render_keeping(summary)


def _cmd_anchor(_session: LiveSession, args: str) -> str:
    ref = args.strip()
    if not ref:
        return "  (usage: /anchor <reference>, e.g. /anchor Mt 5:37)"
    try:
        from .verifiers.scripture import resolve_ref
        result = resolve_ref(ref)
    except Exception as e:
        return f"  (could not resolve anchor: {type(e).__name__}: {e})"
    status = result.get("status", "unknown")
    if status == "ok" and result.get("web_text"):
        text = result["web_text"]
        # Truncate so the terminal doesn't blow up on long passages.
        if len(text) > 600:
            text = text[:597] + "..."
        return f"  {ref} (WEB):\n    {text}"
    if status == "source_missing":
        return (
            f"  ({ref}: Layer 0 source not provisioned. "
            "Run lw/00_source/fetch_sources.py to enable lookups.)"
        )
    return f"  ({ref}: {status})"


def _cmd_precedent(session: LiveSession, _args: str) -> str:
    if not session.last_entry_id:
        return "  (no entry yet; capture one first)"
    store = _journal.JournalStore()
    entry = store.load(session.last_entry_id)
    if entry is None:
        return f"  (last entry {session.last_entry_id} not found on disk)"
    if entry.categorization.closest_precedent_id:
        pid = entry.categorization.closest_precedent_id
        dist = entry.categorization.closest_precedent_distance
        line = f"  closest precedent for {entry.id}: {pid}"
        if dist is not None:
            line += f" (distance {dist})"
        return line
    return f"  (no closest precedent found for {entry.id})"


def _cmd_shelf(_session: LiveSession, _args: str) -> str:
    """List entries currently on the shelf (tagged `shelf`)."""
    store = _journal.JournalStore()
    entries = store.list_all(tag=_SHELF_TAG)
    if not entries:
        return "  (your shelf is empty)"
    lines: List[str] = [f"  Your shelf ({len(entries)} seed(s) — others can reach for these):"]
    for e in entries:
        ts = time.strftime("%Y-%m-%d", time.gmtime(e.written_at))
        preview = e.text.replace("\n", " ").strip()[:70]
        anchors_str = ""
        if e.categorization.detected_anchors:
            anchors_str = "  ↳ " + ", ".join(e.categorization.detected_anchors)
        lines.append(f"    {e.id}  {ts}  {preview}")
        if anchors_str:
            lines.append("        " + anchors_str)
    return "\n".join(lines)


def _cmd_publish(session: LiveSession, args: str) -> str:
    """Add the `shelf` tag to an entry — publish to your shelf."""
    entry_id = args.strip() or session.last_entry_id
    if not entry_id:
        return "  (no seed to publish; capture one first or pass /publish <id>)"
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return f"  (no seed found with id {entry_id})"
    if _SHELF_TAG in entry.user_tags:
        return f"  ({entry_id} is already on the shelf)"
    entry.user_tags = list(entry.user_tags) + [_SHELF_TAG]
    entry.modified_at = time.time()
    store.save(entry)
    return f"  {entry_id} → shelf. Anyone can now reach for it."


def _cmd_unshelf(session: LiveSession, args: str) -> str:
    """Remove the `shelf` tag from an entry — take it off your shelf."""
    entry_id = args.strip() or session.last_entry_id
    if not entry_id:
        return "  (no seed; pass /unshelf <id>)"
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return f"  (no seed found with id {entry_id})"
    if _SHELF_TAG not in entry.user_tags:
        return f"  ({entry_id} is not on the shelf)"
    entry.user_tags = [t for t in entry.user_tags if t != _SHELF_TAG]
    entry.modified_at = time.time()
    store.save(entry)
    return f"  {entry_id} → library only. No longer on the shelf."


_COMMANDS: Dict[str, Callable[[LiveSession, str], str]] = {
    "help":      _cmd_help,
    "?":         _cmd_help,
    "thread":    _cmd_thread,
    "show":      _cmd_show,
    "recent":    _cmd_recent,
    "keeping":   _cmd_keeping,
    "kept":      _cmd_keeping,
    "anchor":    _cmd_anchor,
    "precedent": _cmd_precedent,
    "shelf":     _cmd_shelf,
    "publish":   _cmd_publish,
    "unshelf":   _cmd_unshelf,
}


# ── Dispatch (one input line) ────────────────────────────────────────


def handle_line(session: LiveSession, line: str) -> Optional[str]:
    """Process one input line. Returns the rendered output (or None
    if the line should be silently ignored, e.g. blank line outside
    of multi-line write mode).

    Returns the special string `__QUIT__` when the user asks to quit.
    """
    stripped = line.strip()
    if not stripped:
        return None
    if stripped in ("/quit", "/exit", "/bye"):
        return "__QUIT__"
    if stripped.startswith("/"):
        # Command dispatch.
        parts = stripped[1:].split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        handler = _COMMANDS.get(cmd)
        if handler is None:
            return f"  (unknown command /{cmd}; try /help)"
        return handler(session, args)
    # Bare text → capture as a journal entry.
    try:
        entry = _journal.capture(line)
    except ValueError as e:
        return f"  ({e})"
    session.last_entry_id = entry.id
    cal = _journal.calibrate(entry)
    return _render_capture(entry, cal)


# ── Multi-line capture (one whole entry, terminated by `.`) ──────────


def collect_multiline(read_line: Callable[[], str]) -> str:
    """Read lines until `.` on its own line (or EOF). Returns the
    concatenated text. Intended for `/write` mode in the REPL."""
    parts: List[str] = []
    while True:
        try:
            line = read_line()
        except EOFError:
            break
        if line.strip() == ".":
            break
        parts.append(line)
    return "\n".join(parts)


# ── REPL loop ────────────────────────────────────────────────────────


def run(
    config: Optional[LiveConfig] = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = _print,
) -> int:
    """Run the live session. Returns an exit code.

    `input_fn` and `output_fn` are injected for tests / alternate
    front-ends (e.g. a TUI or a web layer that wraps this same loop).
    """
    config = config or LiveConfig()
    session = LiveSession(config=config)

    # Start the keeper in the background so the keeping doesn't pause
    # while the user writes. The keeper writes to its own log; nothing
    # spills into the REPL output.
    if config.run_keeper:
        keeper = _keeping.default_keeper(
            tick_interval_seconds=config.tick_interval_seconds,
        )
        stop_event = threading.Event()
        t = threading.Thread(
            target=keeper.run_forever,
            kwargs={"stop_event": stop_event},
            daemon=True,
        )
        t.start()
        session._keeper_thread = t
        session._keeper_stop = stop_event

    output_fn("Lighthouse — listening. Type to write. /help for commands.")
    output_fn("")

    try:
        while True:
            try:
                line = input_fn("> ")
            except (EOFError, KeyboardInterrupt):
                output_fn("")
                break

            # Multi-line write mode is a special inline command; it
            # consumes additional input until the user types `.`.
            if line.strip() == "/write":
                output_fn("  (multi-line write — end with `.` on its own line)")
                text = collect_multiline(lambda: input_fn(". "))
                if not text.strip():
                    output_fn("  (empty entry; nothing kept)")
                    continue
                try:
                    entry = _journal.capture(text)
                except ValueError as e:
                    output_fn(f"  ({e})")
                    continue
                session.last_entry_id = entry.id
                cal = _journal.calibrate(entry)
                output_fn(_render_capture(entry, cal))
                continue

            output = handle_line(session, line)
            if output == "__QUIT__":
                break
            if output is not None:
                output_fn(output)
    finally:
        if session._keeper_stop is not None:
            session._keeper_stop.set()

    output_fn("")
    output_fn("Lighthouse — stopping. The keeping continues.")
    return 0


__all__ = [
    "LiveConfig",
    "LiveSession",
    "handle_line",
    "collect_multiline",
    "run",
]
