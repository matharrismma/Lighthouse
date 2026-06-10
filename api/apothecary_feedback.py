"""Apothecary Feedback — per-visitor "did this help?" log.

Closes the loop on Apothecary compounds. After a visitor receives a
compound, they can mark it: helped / didn't_fit / walked_it / saved.
Over time the aggregate signal lets the engine show "most-helpful for
this condition" without ever profiling the individual visitor.

Storage: append-only JSONL per visitor at
`data/apothecary_feedback/<visitor_id>.jsonl`. Same shape as the other
visitor-scoped substrates (coach_journal, apothecary_journal).

Privacy: visitor_id is opaque 12-hex. No PII. The aggregate is computed
across visitors, never reveals which visitor said what.

Wisdom is what survives. The keeping is the substrate.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "apothecary_feedback"

_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_COMPOUND_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# What the visitor can say about a compound. Closed vocabulary.
VALID_RATINGS = ("helped", "didnt_fit", "walked_it", "saved")

MAX_FEEDBACK_PER_VISITOR = 1000
MAX_NOTE_LEN = 1000


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


def submit(
    visitor_id: str,
    compound_id: str,
    rating: str,
    condition: str = "",
    note: str = "",
) -> Dict[str, Any]:
    if not _valid_visitor_id(visitor_id):
        raise ValueError("invalid visitor_id")
    if not _valid_compound_id(compound_id):
        raise ValueError("invalid compound_id")
    if rating not in VALID_RATINGS:
        raise ValueError(f"rating must be one of {VALID_RATINGS}")
    rec = {
        "visitor_id":  visitor_id.strip().lower(),
        "compound_id": compound_id,
        "rating":      rating,
        "condition":   (condition or "")[:200],
        "note":        (note or "")[:MAX_NOTE_LEN],
        "submitted_at": int(time.time()),
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


def list_for_visitor(visitor_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not _valid_visitor_id(visitor_id):
        return []
    records = _read_records(visitor_id)
    records.sort(key=lambda r: r.get("submitted_at", 0), reverse=True)
    return records[: max(1, min(MAX_FEEDBACK_PER_VISITOR, limit))]


def latest_for_compound(visitor_id: str, compound_id: str) -> Optional[Dict[str, Any]]:
    """Return the most-recent rating record for a (visitor, compound) pair,
    or None if the visitor has never rated this compound."""
    if not _valid_visitor_id(visitor_id) or not _valid_compound_id(compound_id):
        return None
    latest: Optional[Dict[str, Any]] = None
    for r in _read_records(visitor_id):
        if r.get("compound_id") != compound_id:
            continue
        if latest is None or r.get("submitted_at", 0) > latest.get("submitted_at", 0):
            latest = r
    return latest


def aggregate_stats() -> Dict[str, Any]:
    """Aggregate counts across every visitor's feedback file.

    Returns counts per rating per compound_id. Used by an operator console
    later to surface which compounds resonate. Privacy-preserving — never
    discloses individual visitor data.
    """
    if not _DIR.exists():
        return {"total": 0, "per_compound": {}}
    per_compound: Dict[str, Counter] = {}
    total = 0
    for path in _DIR.glob("*.jsonl"):
        try:
            for line in path.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cid = rec.get("compound_id")
                rating = rec.get("rating")
                if not cid or rating not in VALID_RATINGS:
                    continue
                per_compound.setdefault(cid, Counter())[rating] += 1
                total += 1
        except OSError:
            continue
    return {
        "total": total,
        "per_compound": {
            cid: dict(counts) for cid, counts in per_compound.items()
        },
    }
