"""Coach Journal — server-side mirror of per-visitor walks.

The user's localStorage is the cache; this is the substrate. A walk is
{visitor_id, walk_id, situation, gates, created_at, updated_at}. The
visitor_id is an opaque 12-hex token generated client-side, never tied
to email or account. The substrate keeps walks across device wipes
and browser switches.

Storage: append-only JSONL per visitor at data/walks/<visitor_id>.jsonl.
Read deduplicates by walk_id, keeping the latest record. Append-only
matches the rest of the project's ledger pattern and is crash-safe.

Privacy: visitor_id is opaque. No PII. Users who want Lockdown can
simply not POST — the page degrades to localStorage-only.

Wisdom is what survives. The keeping is the substrate.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_WALKS_DIR = Path(__file__).parent.parent / "data" / "walks"

# 12-hex token. Validate strictly to avoid path traversal and to keep
# storage tidy. Anything else is rejected.
_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_WALK_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# Caps to keep any single visitor from filling disk.
MAX_WALKS_PER_VISITOR = 500
MAX_SITUATION_LEN = 4000
MAX_GATE_LEN = 4000


def _valid_visitor_id(vid: str) -> bool:
    if not isinstance(vid, str):
        return False
    vid = vid.strip().lower()
    return bool(_VISITOR_RE.match(vid))


def _valid_walk_id(wid: str) -> bool:
    if not isinstance(wid, str):
        return False
    return bool(_WALK_ID_RE.match(wid))


def _visitor_file(visitor_id: str) -> Path:
    _WALKS_DIR.mkdir(parents=True, exist_ok=True)
    return _WALKS_DIR / f"{visitor_id.strip().lower()}.jsonl"


def save_walk(
    visitor_id: str,
    walk_id: str,
    situation: str,
    gates: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a walk record. Returns the saved record.

    Repeated saves with the same walk_id are correct — reads dedupe by
    walk_id keeping the latest. This matches the localStorage debounce
    pattern (every gate-edit triggers a server write).
    """
    if not _valid_visitor_id(visitor_id):
        raise ValueError("invalid visitor_id")
    if not _valid_walk_id(walk_id):
        raise ValueError("invalid walk_id")

    situation = (situation or "")[:MAX_SITUATION_LEN]
    gates_clean: Dict[str, str] = {}
    for gate, answer in (gates or {}).items():
        gate = str(gate)[:32].upper()
        if not gate:
            continue
        gates_clean[gate] = str(answer or "")[:MAX_GATE_LEN]

    record: Dict[str, Any] = {
        "walk_id": walk_id,
        "visitor_id": visitor_id,
        "situation": situation,
        "gates": gates_clean,
        "answered_count": sum(1 for v in gates_clean.values() if v.strip()),
        "updated_at": int(time.time()),
    }
    if extra and isinstance(extra, dict):
        # Carry forward string/int/bool fields the caller wanted.
        for k in ("axes", "archetypes_summary", "protocols_summary", "verdict_hint",
                  "lang", "situation_original", "mt_provider"):
            v = extra.get(k)
            if v is None:
                continue
            if isinstance(v, (str, int, bool, float)):
                record[k] = v
        # Bilingual: gates_original is a dict mirroring gates with original
        # (untranslated) text. Carry forward as-is when present and valid.
        g_orig = extra.get("gates_original")
        if isinstance(g_orig, dict) and g_orig:
            cleaned: Dict[str, str] = {}
            for gk, gv in g_orig.items():
                gk = str(gk)[:32].upper()
                if not gk:
                    continue
                cleaned[gk] = str(gv or "")[:MAX_GATE_LEN]
            if cleaned:
                record["gates_original"] = cleaned

    path = _visitor_file(visitor_id)
    # created_at: discover the earliest record for this walk_id.
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if existing.get("walk_id") == walk_id:
                        record["created_at"] = existing.get(
                            "created_at", existing.get("updated_at", record["updated_at"])
                        )
                        break
        except OSError:
            pass
    record.setdefault("created_at", record["updated_at"])

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_all(visitor_id: str) -> List[Dict[str, Any]]:
    if not _valid_visitor_id(visitor_id):
        return []
    path = _visitor_file(visitor_id)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
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


def list_walks(visitor_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List the visitor's walks, dedup-by-walk_id keeping latest, newest first.

    Tombstone records (deleted=True) win the dedup and are then filtered out.
    """
    all_records = _read_all(visitor_id)
    latest: Dict[str, Dict[str, Any]] = {}
    for rec in all_records:
        wid = rec.get("walk_id")
        if not wid:
            continue
        prev = latest.get(wid)
        if not prev or rec.get("updated_at", 0) >= prev.get("updated_at", 0):
            latest[wid] = rec
    items = [r for r in latest.values() if not r.get("deleted")]
    items.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return items[:limit]


def get_walk(visitor_id: str, walk_id: str) -> Optional[Dict[str, Any]]:
    if not _valid_walk_id(walk_id):
        return None
    for w in list_walks(visitor_id, limit=MAX_WALKS_PER_VISITOR):
        if w.get("walk_id") == walk_id:
            return w
    return None


def delete_walk(visitor_id: str, walk_id: str) -> bool:
    """Tombstone a walk by appending a deletion marker. Subsequent reads skip."""
    if not _valid_visitor_id(visitor_id) or not _valid_walk_id(walk_id):
        return False
    path = _visitor_file(visitor_id)
    if not path.exists():
        return False
    tombstone = {
        "walk_id": walk_id,
        "visitor_id": visitor_id,
        "deleted": True,
        "updated_at": int(time.time()),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    return True
