"""Apothecary Journal — server-side mirror of per-visitor compounds.

Mirrors `coach_journal` in shape: append-only JSONL per visitor at
`data/apothecary_compounds/<visitor_id>.jsonl`. Each record stores the
condition the visitor named and the compound that was prepared, so on
return the visitor can re-open last week's compound for anxiety, anger,
forgiveness, etc.

Privacy: visitor_id is opaque 12-hex. No PII. Visitors who want pure
Lockdown can simply not POST — the page degrades to localStorage-only.

The keeping is the substrate.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "apothecary_compounds"

# 12-hex token. Validate strictly to avoid path traversal.
_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_COMPOUND_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

MAX_COMPOUNDS_PER_VISITOR = 500
MAX_CONDITION_LEN = 500


def _valid_visitor_id(vid: str) -> bool:
    if not isinstance(vid, str):
        return False
    return bool(_VISITOR_RE.match(vid.strip().lower()))


def _valid_compound_id(cid: str) -> bool:
    if not isinstance(cid, str):
        return False
    return bool(_COMPOUND_ID_RE.match(cid))


def _visitor_file(visitor_id: str) -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"{visitor_id.strip().lower()}.jsonl"


def save_compound(
    visitor_id: str,
    compound_id: str,
    condition: str,
    compound: Dict[str, Any],
) -> Dict[str, Any]:
    if not _valid_visitor_id(visitor_id):
        raise ValueError("invalid visitor_id")
    if not _valid_compound_id(compound_id):
        raise ValueError("invalid compound_id")
    if not isinstance(condition, str):
        raise ValueError("condition must be a string")
    condition = condition.strip()[:MAX_CONDITION_LEN]
    if not condition:
        raise ValueError("condition is required")

    rec = {
        "compound_id": compound_id,
        "visitor_id":  visitor_id.strip().lower(),
        "condition":   condition,
        "compound":    compound or {},
        "saved_at":    int(time.time()),
    }
    path = _visitor_file(visitor_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _read_records(visitor_id: str) -> List[Dict[str, Any]]:
    path = _visitor_file(visitor_id)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines():
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


def list_compounds(visitor_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return latest-record-per-compound_id, newest first, limited."""
    if not _valid_visitor_id(visitor_id):
        return []
    records = _read_records(visitor_id)
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in records:
        cid = r.get("compound_id")
        if not cid:
            continue
        by_id[cid] = r  # later record overrides earlier
    # Drop tombstones (latest record marks the compound deleted)
    live = [r for r in by_id.values() if not r.get("deleted") and r.get("compound") is not None]
    items = sorted(live, key=lambda r: r.get("saved_at", 0), reverse=True)
    return items[:max(1, min(MAX_COMPOUNDS_PER_VISITOR, limit))]


def get_compound(visitor_id: str, compound_id: str) -> Optional[Dict[str, Any]]:
    if not _valid_visitor_id(visitor_id) or not _valid_compound_id(compound_id):
        return None
    latest = None
    for r in _read_records(visitor_id):
        if r.get("compound_id") == compound_id:
            latest = r
    return latest


def delete_compound(visitor_id: str, compound_id: str) -> bool:
    """Append a tombstone record. On read, tombstone-with-null-compound wins.

    Same delete model as coach_journal: never rewrite history, just append
    the new latest record with compound=null so list_compounds filters it.
    """
    if not _valid_visitor_id(visitor_id) or not _valid_compound_id(compound_id):
        return False
    if get_compound(visitor_id, compound_id) is None:
        return False
    rec = {
        "compound_id": compound_id,
        "visitor_id":  visitor_id.strip().lower(),
        "condition":   "",
        "compound":    None,
        "saved_at":    int(time.time()),
        "deleted":     True,
    }
    path = _visitor_file(visitor_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True
