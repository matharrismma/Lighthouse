"""Polymathic Journal — server-side per-visitor record of polymathic runs.

Same shape as `coach_journal` and `apothecary_journal`. Each run gets
saved to an append-only JSONL at `data/polymathic_runs/<visitor_id>.jsonl`
when the caller passes a valid visitor_id. Lets a visitor open the same
multi-domain question again later, compare results across days, or just
remember what they asked.

Privacy: visitor_id is opaque 12-hex. No PII. Visitors who prefer Lockdown
mode simply don't pass a visitor_id — the page degrades to localStorage-
only, no server-side keeping.

The keeping is the substrate.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "polymathic_runs"

_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

MAX_RUNS_PER_VISITOR = 500
MAX_SITUATION_LEN = 4000


def _valid_visitor_id(vid: str) -> bool:
    if not isinstance(vid, str):
        return False
    return bool(_VISITOR_RE.match(vid.strip().lower()))


def _valid_run_id(rid: str) -> bool:
    if not isinstance(rid, str):
        return False
    return bool(_RUN_ID_RE.match(rid))


def _visitor_file(visitor_id: str) -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"{visitor_id.strip().lower()}.jsonl"


def save_run(
    visitor_id: str,
    run_id: str,
    situation: str,
    result: Dict[str, Any],
    lang: str = "en",
    situation_original: Optional[str] = None,
    mt_provider: Optional[str] = None,
) -> Dict[str, Any]:
    if not _valid_visitor_id(visitor_id):
        raise ValueError("invalid visitor_id")
    if not _valid_run_id(run_id):
        raise ValueError("invalid run_id")
    situation = (situation or "")[:MAX_SITUATION_LEN]
    if not situation:
        raise ValueError("situation required")

    rec = {
        "run_id":     run_id,
        "visitor_id": visitor_id.strip().lower(),
        "situation":  situation,
        "result":     result or {},
        "lang":       (lang or "en").strip().lower() or "en",
        "saved_at":   int(time.time()),
    }
    if situation_original:
        rec["situation_original"] = situation_original[:MAX_SITUATION_LEN]
    if mt_provider:
        rec["mt_provider"] = mt_provider

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


def list_runs(visitor_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Latest-record-per-run_id, newest first."""
    if not _valid_visitor_id(visitor_id):
        return []
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in _read_records(visitor_id):
        rid = r.get("run_id")
        if not rid:
            continue
        by_id[rid] = r
    live = [r for r in by_id.values() if not r.get("deleted") and r.get("result") is not None]
    items = sorted(live, key=lambda r: r.get("saved_at", 0), reverse=True)
    return items[: max(1, min(MAX_RUNS_PER_VISITOR, limit))]


def all_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """Recent runs across all visitors. Used by /polymathic/recent.

    Walks every per-visitor JSONL, takes the latest record per run_id,
    collapses tombstones, sorts newest-first by saved_at. Truncates the
    situation/result to summary fields so the response stays compact.
    """
    if not _DIR.exists():
        return []
    everything: List[Dict[str, Any]] = []
    for p in _DIR.glob("*.jsonl"):
        vid = p.stem
        by_id: Dict[str, Dict[str, Any]] = {}
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = rec.get("run_id")
                if not rid:
                    continue
                by_id[rid] = rec
        except OSError:
            continue
        for rec in by_id.values():
            if rec.get("deleted") or rec.get("result") is None:
                continue
            result = rec.get("result") or {}
            # Slim summary — full record still accessible via /polymathic/run/{id}
            everything.append({
                "run_id":    rec.get("run_id"),
                "visitor_id": (vid or "")[:12],
                "situation": (rec.get("situation") or "")[:200],
                "verdict":   result.get("composite_verdict") or result.get("verdict") or "",
                "domains":   list(result.get("domains_seen") or result.get("domains") or [])[:6],
                "saved_at":  rec.get("saved_at", 0),
            })
    everything.sort(key=lambda r: r.get("saved_at", 0), reverse=True)
    return everything[: max(1, min(500, int(limit)))]


def get_run(visitor_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    if not _valid_visitor_id(visitor_id) or not _valid_run_id(run_id):
        return None
    latest = None
    for r in _read_records(visitor_id):
        if r.get("run_id") == run_id:
            latest = r
    return latest


def delete_run(visitor_id: str, run_id: str) -> bool:
    """Tombstone delete."""
    if not _valid_visitor_id(visitor_id) or not _valid_run_id(run_id):
        return False
    if get_run(visitor_id, run_id) is None:
        return False
    rec = {
        "run_id": run_id, "visitor_id": visitor_id.strip().lower(),
        "situation": "", "result": None, "saved_at": int(time.time()), "deleted": True,
    }
    with _visitor_file(visitor_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True
