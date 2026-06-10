"""Daily devotion — two-pillar Word + Body anchor for the day.

Each day (deterministic from UTC date) the engine surfaces:
  - one Floor of Discovery section (10-section rotation)
  - one Body layer (Nested Control Systems Framework, 5-layer rotation)
  - one Parable (50+ seeds, longer rotation)
  - one Scripture protocol (26 protocols, longer rotation)
  - one Almanac wisdom entry tagged with shared axes

The pick is deterministic per day so reload returns the same. Pass
?day=<N> (unix-day index) for any historical day. The day-zero epoch
is 1970-01-01 UTC.

Two pillars:
  WORD — Floor section + Scripture + Parable + Protocol
  BODY — Body layer + falsifiable check + scripture anchor

Together: soul-and-body check-in, repeatable, anchored.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_FLOOR_FILE   = _REPO / "data" / "floor" / "sections.jsonl"
_BODY_FILE    = _REPO / "data" / "body" / "layers.jsonl"
_MIND_FILE    = _REPO / "data" / "mind" / "practices.jsonl"
_PARABLE_FILE = _REPO / "data" / "parables" / "seeds.jsonl"
_PROTO_FILE   = _REPO / "data" / "protocols" / "scripture_protocols.jsonl"
_ALMANAC_FILE = _REPO / "data" / "almanac" / "entries.jsonl"
_DEVO_FILE    = _REPO / "data" / "devotionals" / "reflections.jsonl"
_SERMON_FILE  = _REPO / "data" / "sermons" / "sermons.jsonl"

_CACHE: Dict[str, Any] = {
    "mtime": 0.0,
    "floors": [], "bodies": [], "minds": [],
    "parables": [], "protocols": [], "almanac": [],
    "devotionals": [], "sermons": [],
}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _latest_mtime() -> float:
    latest = 0.0
    for p in (_FLOOR_FILE, _BODY_FILE, _MIND_FILE, _PARABLE_FILE,
              _PROTO_FILE, _ALMANAC_FILE, _DEVO_FILE, _SERMON_FILE):
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _load_all() -> None:
    mtime = _latest_mtime()
    if _CACHE["floors"] and mtime <= _CACHE["mtime"]:
        return
    _CACHE["floors"]      = _read_jsonl(_FLOOR_FILE)
    _CACHE["bodies"]      = _read_jsonl(_BODY_FILE)
    _CACHE["minds"]       = _read_jsonl(_MIND_FILE)
    _CACHE["parables"]    = _read_jsonl(_PARABLE_FILE)
    _CACHE["protocols"]   = _read_jsonl(_PROTO_FILE)
    _CACHE["almanac"]     = _read_jsonl(_ALMANAC_FILE)
    _CACHE["devotionals"] = _read_jsonl(_DEVO_FILE)
    _CACHE["sermons"]     = _read_jsonl(_SERMON_FILE)
    _CACHE["mtime"] = mtime


def _day_index_for(when: Optional[float] = None) -> int:
    """Days since 1970-01-01 UTC. Deterministic."""
    return int((when if when is not None else time.time()) // 86400)


def _deterministic_pick(items: List[Dict[str, Any]], salt: str, day: int) -> Optional[Dict[str, Any]]:
    """Pick one item from a list, deterministically by day + salt.

    Uses sha256 of "{salt}|{day}" mod len(items). Sorting items by id
    first ensures the pick is stable across JSONL row order changes.
    """
    if not items:
        return None
    sorted_items = sorted(items, key=lambda x: x.get("id", ""))
    h = hashlib.sha256(f"{salt}|{day}".encode("utf-8")).digest()
    idx = int.from_bytes(h[:8], "big") % len(sorted_items)
    return sorted_items[idx]


def _shared_axes(*recs: Optional[Dict[str, Any]]) -> List[str]:
    """Axes that appear in two or more of the passed records."""
    seen: Dict[str, int] = {}
    for r in recs:
        if not r:
            continue
        for a in (r.get("axes") or []):
            seen[a] = seen.get(a, 0) + 1
    return sorted([a for a, c in seen.items() if c >= 2])


def _almanac_by_axes(axes: List[str], day: int, fallback_pick: bool = True) -> Optional[Dict[str, Any]]:
    """Pick an almanac entry whose axes intersect with `axes`. Falls
    back to a deterministic almanac pick if no intersection found."""
    if not axes:
        if fallback_pick:
            return _deterministic_pick(_CACHE["almanac"], "almanac_fallback", day)
        return None
    ax_set = {a.lower() for a in axes}
    candidates = []
    for e in _CACHE["almanac"]:
        e_axes = {a.lower() for a in (e.get("axes") or [])}
        if e_axes & ax_set:
            candidates.append(e)
    if not candidates:
        return _deterministic_pick(_CACHE["almanac"], "almanac_fallback", day) if fallback_pick else None
    return _deterministic_pick(candidates, "almanac_axed", day)


def for_day(day: Optional[int] = None, lang: str = "en") -> Dict[str, Any]:
    """Compose the daily devotion for the given day index (or today).

    Three pillars: Mind, Body, Spirit (Floor of Discovery). Plus sub-cards
    for parable, protocol, almanac, devotional (Matt's own reflections),
    and sermon (Matt's own writings).

    When `lang` is non-English and a parallel PD Bible is ingested, the
    devotional's scripture_text field swaps to the parallel translation.
    Engine-authored prose (parable narrations, body anchor commentary,
    Floor sections, devotional reflections) stays English here — the MT
    layer handles those when wired.
    """
    _load_all()
    if day is None:
        day = _day_index_for()

    floor    = _deterministic_pick(_CACHE["floors"],    "floor",    day)
    body     = _deterministic_pick(_CACHE["bodies"],    "body",     day)
    mind     = _deterministic_pick(_CACHE["minds"],     "mind",     day)
    parable  = _deterministic_pick(_CACHE["parables"],  "parable",  day)
    protocol = _deterministic_pick(_CACHE["protocols"], "protocol", day)
    devotional = _deterministic_pick(_CACHE["devotionals"], "devo",  day)
    sermon   = _deterministic_pick(_CACHE["sermons"],   "sermon",   day) if _CACHE["sermons"] else None

    shared = _shared_axes(floor, mind, parable, protocol)
    almanac = _almanac_by_axes(shared, day)

    # Date strings — keep timezone-explicit and human-readable.
    epoch = day * 86400
    iso_date = time.strftime("%Y-%m-%d", time.gmtime(epoch))
    weekday  = time.strftime("%A", time.gmtime(epoch))

    result = {
        "day_index": day,
        "iso_date": iso_date,
        "weekday": weekday,
        "lang": (lang or "en").strip().lower() or "en",
        "shared_axes": shared,
        "mind":   _mind_view(mind),
        "body":   _body_view(body),
        "spirit": _floor_view(floor),
        "extras": {
            "parable": _parable_view(parable),
            "protocol": _protocol_view(protocol),
            "almanac": _almanac_view(almanac),
            "devotional": _devotional_view(devotional),
            "sermon": _sermon_view(sermon),
        },
    }

    # Scripture-quote swap: where a sub-card pairs a ref with a quoted verse,
    # swap to the parallel translation. Engine-authored prose stays English
    # until the MT layer is wired.
    lang_norm = result["lang"]
    if lang_norm != "en":
        try:
            from api import scripture_lookup as _scripture_lookup
            devo = result["extras"].get("devotional")
            if devo and devo.get("scripture_ref") and devo.get("scripture_text"):
                # Single-verse refs (e.g., "James 5:16") swap cleanly.
                parsed = _scripture_lookup.parse_ref(devo["scripture_ref"])
                if parsed:
                    swapped = None
                    if parsed.get("verse_start") is None:
                        swapped = _scripture_lookup.lookup_chapter(
                            lang_norm, parsed["book"], parsed["chapter"])
                    elif parsed.get("verse_end") and parsed["verse_end"] > parsed["verse_start"]:
                        swapped = _scripture_lookup.lookup_range(
                            lang_norm, parsed["book"], parsed["chapter"],
                            parsed["verse_start"], parsed["verse_end"])
                    else:
                        swapped = _scripture_lookup.lookup_verse(
                            lang_norm, parsed["book"], parsed["chapter"],
                            parsed["verse_start"])
                    if swapped:
                        devo["scripture_text"] = swapped
                        devo["scripture_translation"] = _scripture_lookup.translation_label(lang_norm)
        except Exception:
            # Translation failure must not break the response.
            pass

    return result


def _mind_view(m: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not m:
        return None
    return {
        "id": m.get("id"),
        "number": m.get("number"),
        "title": m.get("title"),
        "summary": m.get("summary"),
        "scripture": m.get("scripture") or [],
        "practice": m.get("practice"),
        "axes": m.get("axes") or [],
        "closing": m.get("closing"),
    }


def _devotional_view(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not d:
        return None
    return {
        "id": d.get("id"),
        "title": d.get("title"),
        "date": d.get("date"),
        "body": d.get("body"),
        "scripture_ref": d.get("scripture_ref"),
        "scripture_text": d.get("scripture_text"),
        "author": d.get("author"),
    }


def _sermon_view(s: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    body = s.get("body") or ""
    return {
        "id": s.get("id"),
        "title": s.get("title"),
        "format": s.get("format"),
        "primary_scripture": s.get("primary_scripture"),
        "preview": body[:600],
        "truncated": len(body) > 600,
        "author": s.get("author"),
    }


def _floor_view(s: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    return {
        "id": s.get("id"),
        "number": s.get("number"),
        "title": s.get("title"),
        "summary": s.get("summary"),
        "scripture": s.get("scripture") or [],
        "axes": s.get("axes") or [],
        "closing": s.get("closing"),
    }


def _body_view(b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not b:
        return None
    return {
        "id": b.get("id"),
        "number": b.get("number"),
        "title": b.get("title"),
        "function": b.get("function"),
        "failures": b.get("failures") or [],
        "falsifiable_check": b.get("falsifiable_check"),
        "scripture_anchor": b.get("scripture_anchor"),
        "axes": b.get("axes") or [],
        "license": b.get("license"),
    }


def _parable_view(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "gate": p.get("gate"),
        "text": p.get("parable"),
        "question": p.get("question"),
        "wisdom": p.get("wisdom"),
        "axes": p.get("axes") or [],
    }


def _protocol_view(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "scripture": p.get("scripture") or [],
        "summary": p.get("summary"),
        "step_count": len(p.get("steps") or []),
        "first_step": (p.get("steps") or [{}])[0] if p.get("steps") else None,
    }


def _almanac_view(e: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not e:
        return None
    return {
        "id": e.get("id"),
        "title": e.get("title") or e.get("situation"),
        "verdict": e.get("verdict"),
        "wisdom": e.get("wisdom"),
        "axes": e.get("axes") or [],
        "permalink": f"/almanac.html?q={e.get('id', '')}",
    }
