"""The Hearth — a place where everyone knows your name.

A minimal synchronous-feeling community substrate. Each room is an
append-only JSONL at `data/hearth/<room>.jsonl`. Messages carry a
visitor_id, a handle (cosmetic name), a body, and a timestamp.

Posture matches the rest of the engine:
  • Floor: no accounts, no passwords, just a handle in localStorage.
  • Walk-in: anyone can step into a room. Anyone can speak.
  • Append-only: nothing is deleted. The keeping keeps.
  • Operator-moderated: the operator can flag a message via the
    standard misalignment substrate. Visible takedown happens through
    the engine's RED gate applied to itself, never silently.

Rooms are pre-declared, not user-created. That keeps the lore from
sprawling — six rooms each with a clear purpose, where regulars
accumulate inside-jokes and history. Like Cheers. Like a real bar.

Presence is the last 5 minutes of activity. No "online indicators"
that lie; just the empirical fact of who has actually spoken or
checked in recently.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_HEARTH_DIR = _REPO / "data" / "hearth"
_PRESENCE_FILE = _HEARTH_DIR / "_presence.jsonl"
_lock = Lock()

# Pre-declared rooms. Adding a new room is a deliberate move — change here.
# Each room has a slug (URL-safe), name (display), and blurb (the room's
# intent in one breath). Order = display order.
ROOMS: List[Dict[str, str]] = [
    {"slug": "front",     "name": "Front Room",
     "blurb": "Where the door opens. New here? Say hello. Old-timer? Welcome them in."},
    {"slug": "prayer",    "name": "Prayer Room",
     "blurb": "Lift a name. Carry one. Mt 18:19 — where two or three are gathered."},
    {"slug": "bible",     "name": "Bible Study",
     "blurb": "What does this passage mean? Working through Scripture together, in slow time."},
    {"slug": "family",    "name": "Family Talk",
     "blurb": "Marriage, parenting, aging parents, the small daily things. No advice unless asked."},
    {"slug": "health",    "name": "Health Talk",
     "blurb": "Body, mind, what's working, what isn't. Anchored in the Almanac's evidence."},
    {"slug": "today",     "name": "What's Going On",
     "blurb": "The news through a long lens. Argue gently; nobody's enemy is in the room."},
]

ROOM_SLUGS = {r["slug"] for r in ROOMS}
PRESENCE_WINDOW_SEC = 300  # 5 minutes
MAX_MESSAGE_LEN = 1500
HANDLE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,32}$")
VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_s() -> int:
    return int(time.time())


def _valid_visitor(vid: str) -> bool:
    return isinstance(vid, str) and bool(VISITOR_RE.match(vid.strip().lower()))


def _valid_handle(h: str) -> bool:
    return isinstance(h, str) and bool(HANDLE_RE.match(h.strip()))


def _room_file(slug: str) -> Path:
    _HEARTH_DIR.mkdir(parents=True, exist_ok=True)
    return _HEARTH_DIR / f"{slug}.jsonl"


def list_rooms_with_counts() -> List[Dict[str, Any]]:
    """Return ROOMS enriched with message + presence counts."""
    out = []
    for r in ROOMS:
        path = _room_file(r["slug"])
        msg_count = 0
        last_message_ms = 0
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg_count += 1
                    ts = rec.get("ts_ms", 0)
                    if ts > last_message_ms:
                        last_message_ms = ts
            except OSError:
                pass
        present = presence_count(r["slug"])
        out.append({
            **r,
            "message_count": msg_count,
            "last_message_ms": last_message_ms,
            "present_count": present,
        })
    return out


def post_message(room: str, visitor_id: str, handle: str, body: str) -> Dict[str, Any]:
    """Append a message to a room. Returns the stored record."""
    room = (room or "").strip().lower()
    if room not in ROOM_SLUGS:
        raise ValueError(f"unknown room: {room!r}")
    if not _valid_visitor(visitor_id):
        raise ValueError("invalid visitor_id")
    if not _valid_handle(handle):
        raise ValueError("invalid handle (2-32 chars, alphanumeric/underscore/dash)")
    body = (body or "").strip()
    if not body:
        raise ValueError("body required")
    if len(body) > MAX_MESSAGE_LEN:
        body = body[:MAX_MESSAGE_LEN]

    rec = {
        "id":         uuid.uuid4().hex[:16],
        "room":       room,
        "visitor_id": visitor_id.strip().lower(),
        "handle":     handle.strip(),
        "body":       body,
        "ts_ms":      _now_ms(),
    }
    path = _room_file(room)
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _record_presence(room, visitor_id, handle)
    return rec


def recent_messages(room: str, since_ms: int = 0, limit: int = 60) -> List[Dict[str, Any]]:
    """Read the tail of a room. since_ms filters to messages newer than
    that timestamp (for polling). limit caps the result."""
    room = (room or "").strip().lower()
    if room not in ROOM_SLUGS:
        return []
    path = _room_file(room)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    # Walk backwards; once we have `limit` messages OR hit since_ms, stop.
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since_ms and rec.get("ts_ms", 0) <= since_ms:
            break
        out.append(rec)
        if len(out) >= limit:
            break
    out.reverse()
    return out


def _record_presence(room: str, visitor_id: str, handle: str) -> None:
    """Append a presence ping. Records can age out; we keep the file
    compact by occasionally rewriting only the in-window entries."""
    rec = {
        "room":       room,
        "visitor_id": visitor_id.strip().lower(),
        "handle":     handle.strip(),
        "ts_s":       _now_s(),
    }
    _HEARTH_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        try:
            with _PRESENCE_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            return
        # Compact occasionally — every ~50 pings — to keep the file small.
        try:
            if _PRESENCE_FILE.stat().st_size > 64 * 1024:
                _compact_presence_unlocked()
        except OSError:
            pass


def _compact_presence_unlocked() -> None:
    """Rewrite presence file with only in-window entries. Caller holds lock."""
    if not _PRESENCE_FILE.exists():
        return
    cutoff = _now_s() - PRESENCE_WINDOW_SEC
    keep: List[str] = []
    try:
        for line in _PRESENCE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ts_s", 0) >= cutoff:
                keep.append(line)
    except OSError:
        return
    try:
        _PRESENCE_FILE.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    except OSError:
        pass


def presence(room: Optional[str] = None) -> List[Dict[str, Any]]:
    """Who has been active in the last 5 minutes.

    If `room` given, only that room's presence. Otherwise across all rooms.
    Returns unique entries by visitor_id, most-recently-seen first.
    """
    if not _PRESENCE_FILE.exists():
        return []
    cutoff = _now_s() - PRESENCE_WINDOW_SEC
    seen: Dict[str, Dict[str, Any]] = {}
    try:
        for line in _PRESENCE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ts_s", 0) < cutoff:
                continue
            if room and rec.get("room") != room:
                continue
            vid = rec.get("visitor_id", "")
            prior = seen.get(vid)
            if not prior or rec.get("ts_s", 0) > prior.get("ts_s", 0):
                seen[vid] = rec
    except OSError:
        return []
    out = list(seen.values())
    out.sort(key=lambda r: r.get("ts_s", 0), reverse=True)
    return out


def presence_count(room: Optional[str] = None) -> int:
    return len(presence(room))


def check_in(room: str, visitor_id: str, handle: str) -> Dict[str, Any]:
    """Mark a visitor as present in a room without posting a message.

    Called when a visitor opens the room or polls for updates. Drives
    the 'who's here' indicator. Invalid args silently no-op so polling
    never crashes the page.
    """
    if room not in ROOM_SLUGS:
        return {"checked_in": False, "reason": "unknown_room"}
    if not _valid_visitor(visitor_id):
        return {"checked_in": False, "reason": "invalid_visitor_id"}
    if not _valid_handle(handle):
        return {"checked_in": False, "reason": "invalid_handle"}
    _record_presence(room, visitor_id, handle)
    return {
        "checked_in": True,
        "room": room,
        "present_count": presence_count(room),
    }


def search_messages(q: str, room: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Find messages matching a substring. Across all rooms unless `room` given.

    This is what makes lore searchable — "what did so-and-so say about
    forgiveness six months ago?"
    """
    q = (q or "").strip().lower()
    if not q:
        return []
    rooms_to_scan = [room] if (room and room in ROOM_SLUGS) else list(ROOM_SLUGS)
    matches: List[Dict[str, Any]] = []
    for r in rooms_to_scan:
        path = _room_file(r)
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hay = (rec.get("body") or "").lower() + " " + (rec.get("handle") or "").lower()
                if q in hay:
                    matches.append(rec)
        except OSError:
            continue
    matches.sort(key=lambda r: r.get("ts_ms", 0), reverse=True)
    return matches[: max(1, min(500, int(limit)))]
