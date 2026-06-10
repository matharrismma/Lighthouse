"""Polymathic Session — multi-turn refinement.

A polymathic SESSION threads multiple polymathic RUNS together, so a
visitor (or agent) can iterate: run once, see what came back, refine
the situation, run again, watch the verdict tighten or split. The
session keeps the full chain so the reasoning is auditable end-to-end.

Storage: one JSONL per session at
  data/polymathic_sessions/<session_id>.jsonl

Each line is either:
  {"kind": "session_start", ...}   — opens the session
  {"kind": "turn", ...}            — a single run within the session
  {"kind": "session_end", ...}    — closes the session (optional)

Sessions are visitor-scoped via visitor_id. A visitor can have multiple
open sessions in parallel (e.g. one for marriage, one for a health
question). The session_id is opaque (16 hex chars).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_SESSIONS_DIR = _REPO / "data" / "polymathic_sessions"
_LIVE_FILE = _SESSIONS_DIR / "_live.jsonl"  # in-flight runs across the engine
_lock = Lock()

MAX_TURNS = 20
MAX_SITUATION_LEN = 4000


def _now_ms() -> int:
    return int(time.time() * 1000)


def _session_file(session_id: str) -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR / f"{session_id}.jsonl"


def open_session(visitor_id: str, initial_situation: str = "") -> Dict[str, Any]:
    """Open a new polymathic session. Returns {session_id, ...}."""
    sid = uuid.uuid4().hex[:16]
    rec = {
        "kind":               "session_start",
        "session_id":         sid,
        "visitor_id":         (visitor_id or "")[:64],
        "initial_situation":  (initial_situation or "")[:MAX_SITUATION_LEN],
        "opened_at_ms":       _now_ms(),
    }
    with _lock:
        with _session_file(sid).open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"session_id": sid, "opened": True, "opened_at_ms": rec["opened_at_ms"]}


def append_turn(session_id: str, situation: str, run_id: str,
                refinement_note: str = "") -> Dict[str, Any]:
    """Append a turn (a single polymathic run) to a session.

    The run itself is stored in the existing polymathic_journal; here
    we just keep the chain. refinement_note captures why the visitor
    is asking again (e.g. "added context about the timing").
    """
    if not session_id:
        raise ValueError("session_id required")
    path = _session_file(session_id)
    if not path.exists():
        raise ValueError(f"unknown session: {session_id!r}")
    # Count existing turns; enforce max
    try:
        n_turns = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") == "turn":
                n_turns += 1
        if n_turns >= MAX_TURNS:
            raise ValueError(f"session is full (max {MAX_TURNS} turns)")
    except OSError as e:
        raise ValueError(f"could not read session: {e}")

    rec = {
        "kind":            "turn",
        "session_id":      session_id,
        "turn_index":      n_turns + 1,
        "situation":       (situation or "")[:MAX_SITUATION_LEN],
        "run_id":          run_id,
        "refinement_note": (refinement_note or "")[:500],
        "appended_at_ms":  _now_ms(),
    }
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Return the full session chain — start + every turn."""
    path = _session_file(session_id)
    if not path.exists():
        return None
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return None
    if not records:
        return None
    start = next((r for r in records if r.get("kind") == "session_start"), {})
    turns = [r for r in records if r.get("kind") == "turn"]
    end   = next((r for r in records if r.get("kind") == "session_end"), None)
    return {
        "session_id":  session_id,
        "visitor_id":  start.get("visitor_id"),
        "opened_at_ms": start.get("opened_at_ms"),
        "initial_situation": start.get("initial_situation", ""),
        "turn_count":  len(turns),
        "turns":       turns,
        "closed":      end is not None,
        "closed_at_ms": end.get("closed_at_ms") if end else None,
    }


def list_sessions(visitor_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """All sessions for a visitor, newest first by opened_at_ms.

    Returns slim summaries — full session via get_session(id).
    """
    if not _SESSIONS_DIR.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in _SESSIONS_DIR.glob("*.jsonl"):
        if p.name == "_live.jsonl":
            continue
        try:
            first_line = ""
            n_turns = 0
            last_ms = 0
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not first_line and rec.get("kind") == "session_start":
                        if rec.get("visitor_id") != visitor_id:
                            break  # not this visitor's session
                        first_line = json.dumps(rec)
                        last_ms = rec.get("opened_at_ms", 0)
                    elif rec.get("kind") == "turn":
                        n_turns += 1
                        last_ms = max(last_ms, rec.get("appended_at_ms", 0))
            if first_line:
                start = json.loads(first_line)
                out.append({
                    "session_id":   start.get("session_id"),
                    "opened_at_ms": start.get("opened_at_ms"),
                    "initial_situation": (start.get("initial_situation") or "")[:200],
                    "turn_count":   n_turns,
                    "last_activity_ms": last_ms,
                })
        except OSError:
            continue
    out.sort(key=lambda r: r.get("last_activity_ms", 0), reverse=True)
    return out[: max(1, min(100, int(limit)))]


def close_session(session_id: str, summary: str = "") -> Dict[str, Any]:
    """Close a session. Idempotent — already-closed sessions return ok."""
    path = _session_file(session_id)
    if not path.exists():
        raise ValueError(f"unknown session: {session_id!r}")
    rec = {
        "kind":         "session_end",
        "session_id":   session_id,
        "summary":      (summary or "")[:1000],
        "closed_at_ms": _now_ms(),
    }
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ── Live in-flight view ─────────────────────────────────────────────

def record_inflight(run_id: str, situation: str, status: str = "started") -> None:
    """Append a row to the live feed when a polymathic run starts/finishes."""
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "run_id":  run_id,
        "situation": (situation or "")[:200],
        "status":  status,
        "ts_ms":   _now_ms(),
    }
    try:
        with _lock:
            with _LIVE_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            # Compact periodically
            try:
                if _LIVE_FILE.stat().st_size > 128 * 1024:
                    _compact_live_unlocked()
            except OSError:
                pass
    except OSError:
        pass


def _compact_live_unlocked() -> None:
    """Keep only the last 200 live rows."""
    if not _LIVE_FILE.exists():
        return
    try:
        lines = _LIVE_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        keep = [l for l in lines if l.strip()][-200:]
        _LIVE_FILE.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except OSError:
        pass


def live_feed(limit: int = 50) -> List[Dict[str, Any]]:
    """Recent in-flight polymathic events. Newest first."""
    if not _LIVE_FILE.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in _LIVE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    out.sort(key=lambda r: r.get("ts_ms", 0), reverse=True)
    return out[: max(1, min(200, int(limit)))]
