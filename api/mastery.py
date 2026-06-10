"""Mastery tracking — visitor-keyed, append-only.

Records when a visitor marks a curriculum unit as worked-through.
The prerequisites field on each unit finally has something to
enforce: if `prerequisites: [math_counting_to_20]` and the visitor
hasn't marked counting complete, the dashboard can dim the next
unit (or, depending on Steward corridor strictness, deny it).

The keeping is the substrate — mastery records are kept like any
other packet. Per-visitor JSONL at data/mastery/<visitor_id>.jsonl;
the unified index can surface them later as a kind:`mastery_mark`.

Three states:
  • working — the visitor has started but not finished
  • mastered — the visitor marked complete (the only state with real
    meaning today; later: an engine-side check might confirm)
  • set_aside — the visitor abandoned (no shame, kept for the trail)

Reset is supported: a visitor can clear a mark. Reset is recorded as
its own row so the chronology is honest — we don't pretend mastery
never happened, we record that it was reset on date X.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_MASTERY_DIR = _REPO / "data" / "mastery"
_lock = Lock()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _file_for(visitor_id: str) -> Path:
    """Per-visitor JSONL. Visitor IDs are opaque hex; we lightly
    sanitize to avoid path traversal."""
    safe = "".join(c for c in visitor_id if c.isalnum() or c in "_-")[:64]
    if not safe:
        safe = "anon"
    return _MASTERY_DIR / f"{safe}.jsonl"


def _read_all(visitor_id: str) -> List[Dict[str, Any]]:
    p = _file_for(visitor_id)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _append(visitor_id: str, record: Dict[str, Any]) -> None:
    """Append a mastery row. Never raises — recording failures must
    not break the engine."""
    try:
        _MASTERY_DIR.mkdir(parents=True, exist_ok=True)
        p = _file_for(visitor_id)
        with _lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def mark(visitor_id: str, unit_id: str, state: str = "mastered",
         note: str = "") -> Dict[str, Any]:
    """Record a mastery state for a unit. State must be one of:
    'working', 'mastered', 'set_aside', 'reset'. Returns the
    recorded row."""
    if state not in {"working", "mastered", "set_aside", "reset"}:
        state = "mastered"
    rec = {
        "visitor_id": visitor_id,
        "unit_id": unit_id,
        "state": state,
        "note": (note or "")[:200],
        "recorded_at_ms": _now_ms(),
    }
    _append(visitor_id, rec)
    return rec


def current_state(visitor_id: str) -> Dict[str, str]:
    """Reduce the append-only log to a {unit_id: latest_state} map.
    Used by the dashboard to dim/highlight units. Reset rows return
    state='not_started' (the same as never having marked it)."""
    out: Dict[str, str] = {}
    for row in _read_all(visitor_id):
        uid = row.get("unit_id")
        st = row.get("state")
        if not uid or not st:
            continue
        if st == "reset":
            out.pop(uid, None)
        else:
            out[uid] = st
    return out


def list_visitor(visitor_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Full mastery log for one visitor (chronological tail)."""
    rows = _read_all(visitor_id)
    return rows[-limit:]


def can_attempt(visitor_id: str, unit_id: str,
                prerequisites: List[str]) -> Dict[str, Any]:
    """Check if a visitor can attempt a unit given its prerequisites.

    Returns {"allowed": bool, "missing": [unit_ids], "current": state}.
    The dashboard renders this client-side so prerequisites are
    visible, not just enforced. Today this is advisory only — no
    endpoint denies a unit; the Steward could later wire it in."""
    state_map = current_state(visitor_id)
    missing = [p for p in (prerequisites or []) if state_map.get(p) != "mastered"]
    return {
        "allowed": not missing,
        "missing": missing,
        "current": state_map.get(unit_id, "not_started"),
    }
