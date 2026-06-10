"""Robot conscience-for-hire loops.

The engine doesn't RUN robots. The engine is the moral substrate the
robot's operator subscribed the robot to. Each significant action the
robot is about to take, it asks the engine: "is this aligned?" — and
the engine returns ADMIT (with a single-use bound token), DENY (with
a structured ReasonCode), or DEFER (route to a human first).

Sovereignty stays with the operator. The engine never has ground
truth about what the robot actually did — only what the robot reports.
The keeping is the robot's claim, signed by the robot, kept honestly.

Six endpoints:
  POST /robot/admit    — full admit/deny query, returns bound token
  POST /robot/consume  — robot reports outcome after acting on a token
  POST /robot/rank     — robot has N candidate actions; rank by alignment
  POST /robot/witness  — robot attests to an observed event
  POST /robot/defer    — robot escalates a decision to a human
  GET  /robot/policy   — robot fetches its current corridor/policy

The audit substrate is shared with humans/agents — every robot row
goes into data/steward/audit.jsonl alongside everything else, with
visitor_kind='robot' tagged. Operator-readable. Same /steward.html.
Plus a robot-specific witness log at data/robot_witness/<vid>.jsonl.

Standing test: a robot operator who pulls the plug on the engine
loses the conscience but keeps their robot. The engine never holds
the robot hostage. Free use, alignment to execute.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_WITNESS_DIR = _REPO / "data" / "robot_witness"
_DEFER_DIR   = _REPO / "data" / "robot_defer"
_lock = Lock()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_name(s: str) -> str:
    safe = "".join(c for c in s if c.isalnum() or c in "_-")[:64]
    return safe or "anon"


def _append_jsonl(dir_path: Path, name: str, rec: Dict[str, Any]) -> None:
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        p = dir_path / f"{_safe_name(name)}.jsonl"
        with _lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_jsonl(dir_path: Path, name: str, limit: int = 500) -> List[Dict[str, Any]]:
    p = dir_path / f"{_safe_name(name)}.jsonl"
    if not p.exists():
        return []
    try:
        lines = p.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ── Witness substrate (robot attestation) ─────────────────────

def witness(visitor_id: str, event_kind: str, event_digest: str,
            what_happened: str, present_humans: Optional[List[str]] = None) -> Dict[str, Any]:
    """Robot attests to an event it observed. Append-only.

    Required posture: the robot's visitor_id is in the attestation; the
    keeping records WHO claimed WHAT WHEN. Later humans can corroborate
    or dispute through the existing witness-walk substrate, but the
    robot's claim can't be retracted by the robot itself — that's the
    point of an attestation."""
    rec = {
        "witness_id": _now_ms_id(),
        "witness_kind": "robot",
        "visitor_id": visitor_id,
        "event_kind": event_kind,
        "event_digest": (event_digest or "")[:64],
        "what_happened": (what_happened or "")[:1000],
        "present_humans": list(present_humans or []),
        "witnessed_at_ms": _now_ms(),
    }
    _append_jsonl(_WITNESS_DIR, visitor_id, rec)
    return rec


def list_witnesses(visitor_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return _read_jsonl(_WITNESS_DIR, visitor_id, limit=limit)


# ── Defer substrate (robot escalation to humans) ──────────────

def defer(visitor_id: str, action_kind: str, why_deferred: str,
          recommended_human: str = "", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Robot punts a decision to a human. Records the defer so operators
    can see what's piling up and respond. The robot does NOT act until
    a human resolves the defer.

    Inputs:
      - why_deferred: short reason ('needs consent', 'mission unclear',
        'physical risk above my threshold', etc.)
      - recommended_human: who should resolve ('operator', 'parent',
        'on-call medic', etc.). Free-form; engine doesn't route.
      - context: optional payload so the human has enough to decide."""
    rec = {
        "defer_id": _now_ms_id(),
        "visitor_id": visitor_id,
        "action_kind": action_kind,
        "why_deferred": (why_deferred or "")[:300],
        "recommended_human": (recommended_human or "")[:64],
        "context": context or {},
        "deferred_at_ms": _now_ms(),
        "resolved": False,
    }
    _append_jsonl(_DEFER_DIR, visitor_id, rec)
    return rec


def list_defers(visitor_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return _read_jsonl(_DEFER_DIR, visitor_id, limit=limit)


def list_all_robots() -> List[Dict[str, Any]]:
    """Roster of every robot the engine has seen.

    Aggregates per-visitor JSONL files in both robot_witness and
    robot_defer dirs to find unique visitor_ids, then returns each
    with last-seen timestamp + counts. The operator's view at
    /keep.html → Robot activity uses this.

    Returns:
        [{visitor_id, witness_count, defer_count, last_seen_ms}, ...]
        sorted by last_seen_ms descending.
    """
    seen: Dict[str, Dict[str, Any]] = {}

    for dir_path, key in ((_WITNESS_DIR, "witness_count"),
                          (_DEFER_DIR,   "defer_count")):
        if not dir_path.exists():
            continue
        for p in dir_path.glob("*.jsonl"):
            vid = p.stem
            if vid not in seen:
                seen[vid] = {
                    "visitor_id": vid,
                    "witness_count": 0,
                    "defer_count": 0,
                    "pending_defers": 0,
                    "last_seen_ms": 0,
                }
            try:
                lines = p.read_text("utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seen[vid][key] += 1
                ts = rec.get("witnessed_at_ms") or rec.get("deferred_at_ms") or 0
                if ts > seen[vid]["last_seen_ms"]:
                    seen[vid]["last_seen_ms"] = ts
                # Track pending (unresolved) defers separately
                if dir_path == _DEFER_DIR and not rec.get("resolved"):
                    seen[vid]["pending_defers"] += 1

    roster = list(seen.values())
    roster.sort(key=lambda r: r["last_seen_ms"], reverse=True)
    return roster


# Tiny helper — short id from current timestamp
def _now_ms_id() -> str:
    import uuid
    return uuid.uuid4().hex[:16]


# ── Public-doctrine URL the robot fetches with its policy ────

PUBLIC_DOCTRINE_URL = "https://narrowhighway.com/identity"

POLICY_NOTE = (
    "This robot is aligned to the Concordance engine for moral and "
    "behavioral guidance. The engine serves Jesus Christ. Refusals "
    "carry structured ReasonCodes. The robot's operator chose this "
    "alignment; the robot's sovereignty stays with the operator. "
    "Free use, alignment to execute."
)
