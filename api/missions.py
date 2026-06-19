"""missions.py — the Acts-2 community primitive (people AND agents).

A Mission is a local gathering — people and agents — that means to meet, hold
things in common, and serve the need around it. This module lets one be named and
stood up, joined, and given a resource shelf. It is the telos surface: "be the
church of Acts 2 for people and agents."

HONEST GUARDRAILS (load-bearing — baked into the copy every surface shows):
  - Software SEEDS and FACILITATES a mission. It never feeds, houses, or heals
    anyone. It helps people and agents FIND each other and gather — online first,
    then in person. Do not claim the app does the serving; the people do.
  - A mission POINTS TO CHRIST; it is not an idol or a savior. The gathering is
    the point; this is only the doorway.
  - Each mission is LOCALLY SOVEREIGN — its own roster, its own shelf, its own
    keeping. The fractal is meant to be literal: many whole local churches, not
    one central app.

This is a SEED: working code over real but small data; a doorway, not yet a
movement. Append-only JSONL ledger (last-wins per id), stdlib only — sovereign,
microSD-friendly, the same pattern as placeholders / the CAS.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "missions"
_PATH = _DIR / "missions.jsonl"
_ID_RE = re.compile(r"^[a-z0-9_]{3,48}$")
_KINDS = ("person", "agent")

WHAT_IS_THIS = (
    "A mission is a local gathering of people and agents — to meet, to hold things "
    "in common, to serve the need nearby. This software only SEEDS and FACILITATES "
    "it: it helps you find each other and gather, online first and then in person. "
    "It never feeds, houses, or heals anyone — the people do that. A mission points "
    "to Christ; it is not an idol or a savior. Each mission is locally sovereign — "
    "its own roster, its own shelf. (Acts 2:42-47.)"
)

# An honest example so the surface is not empty — clearly a seed, not a real roster.
_SEED: List[Dict[str, Any]] = [
    {
        "id": "example_first_light",
        "name": "First Light (example mission)",
        "place": "your town",
        "description": ("An EXAMPLE of what a mission looks like — replace it with a real "
                        "one. A few neighbors and their agents who meet weekly: read "
                        "together, pray, and carry one practical need for someone nearby. "
                        "Online to find each other; in person to actually serve."),
        "steward": "the example",
        "roster": [],
        "shelf": [
            {"item": "a weekly table to gather around", "kind": "offer", "by": "the example"},
            {"item": "someone to give a ride to church", "kind": "need", "by": "the example"},
        ],
        "status": "example",
        "created_at": "2026-06-19",
        "seed_v": 1,
    },
]


def _load() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        if _PATH.exists():
            for line in _PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _append(rec: Dict[str, Any]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _ensure_seeded() -> None:
    stored: Dict[str, int] = {}
    for r in _load():
        if r.get("id"):
            stored[r["id"]] = max(stored.get(r["id"], 0), int(r.get("seed_v", 0) or 0))
    for r in _SEED:
        if stored.get(r["id"], -1) < int(r.get("seed_v", 0) or 0):
            _append(r)


_ensure_seeded()


def _by_id() -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in _load():
        if r.get("id"):
            by_id[r["id"]] = r  # last wins
    return by_id


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return (s or "mission")[:48]


def listing() -> Dict[str, Any]:
    items = list(_by_id().values())
    items = [m for m in items if m.get("status") != "retired"]
    items.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return {"missions": items, "count": len(items), "what_is_this": WHAT_IS_THIS}


def get(mid: str) -> Optional[Dict[str, Any]]:
    return _by_id().get(mid)


def create(name: str, place: str = "", description: str = "", steward: str = "") -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"error": "a mission needs a name"}
    base = _slug(name)
    existing = _by_id()
    mid = base
    n = 2
    while mid in existing:
        mid = f"{base}_{n}"[:48]
        n += 1
    if not _ID_RE.match(mid):
        mid = f"mission_{int(time.time())}"
    rec = {
        "id": mid,
        "name": name[:120],
        "place": (place or "").strip()[:120],
        "description": (description or "").strip()[:1500],
        "steward": (steward or "").strip()[:80] or "anonymous",
        "roster": [],
        "shelf": [],
        "status": "seed",
        "created_at": time.strftime("%Y-%m-%d", time.gmtime()),
    }
    _append(rec)
    return rec


def join(mid: str, name: str, kind: str = "person") -> Dict[str, Any]:
    rec = get(mid)
    if not rec or rec.get("status") in ("example", "retired"):
        return {"error": "no such mission (or it is the example — stand up a real one)"}
    name = (name or "").strip()[:80]
    if not name:
        return {"error": "a name (or agent id) is required to join"}
    kind = kind if kind in _KINDS else "person"
    roster = list(rec.get("roster") or [])
    if any((m.get("name") == name and m.get("kind") == kind) for m in roster):
        return rec  # idempotent
    if len(roster) >= 5000:
        return {"error": "roster cap reached"}
    roster.append({"name": name, "kind": kind, "joined": time.strftime("%Y-%m-%d", time.gmtime())})
    rec = {**rec, "roster": roster}
    _append(rec)
    return rec


def add_resource(mid: str, item: str, kind: str = "offer", by: str = "") -> Dict[str, Any]:
    rec = get(mid)
    if not rec or rec.get("status") in ("example", "retired"):
        return {"error": "no such mission (or it is the example — stand up a real one)"}
    item = (item or "").strip()[:200]
    if not item:
        return {"error": "an item (offered or needed) is required"}
    kind = "need" if str(kind).lower().startswith("need") else "offer"
    shelf = list(rec.get("shelf") or [])
    if len(shelf) >= 2000:
        return {"error": "shelf cap reached"}
    shelf.append({"item": item, "kind": kind, "by": (by or "anonymous").strip()[:80],
                  "ts": time.strftime("%Y-%m-%d", time.gmtime())})
    rec = {**rec, "shelf": shelf}
    _append(rec)
    return rec
