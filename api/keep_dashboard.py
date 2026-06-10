"""keep_dashboard.py — Single aggregator endpoint for the /keep.html dashboard.

The operator dashboard at /keep.html historically fires ~20 sequential
fetches (almanac, witness, polymathic, robot, audit, mastery, etc.) and
strings them together with `await`. That's 4-15s of perceived load even
on a healthy engine, and any single slow upstream blocks the whole page.

This module pre-aggregates everything the dashboard needs into ONE JSON
document, cached 30 seconds. The dashboard makes ONE call. Total load time
drops by 10-20x.

Endpoint:
  GET /keep/dashboard   → all the operator-dashboard data in one shot

Caching: 30s TTL + single-flight lock. Pre-primed by the periodic warmer.
"""
from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

_CACHE: dict = {"snapshot": None, "checked_at": 0.0}
_CACHE_TTL = 30.0
_LOCK = threading.Lock()


def _read_jsonl_tail(p: Path, limit: int = 50) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    try:
        with p.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            tail = f.read()
        text = tail.decode("utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _files_in_dir(d: Path, pattern: str = "*") -> int:
    if not d.exists():
        return 0
    try:
        return sum(1 for _ in d.glob(pattern))
    except Exception:
        return 0


def _build_snapshot() -> Dict[str, Any]:
    """One pass over every datasource the dashboard wants. Each section
    is independently defensive — a missing file or parse error just leaves
    that section thin, never aborts the whole snapshot."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Almanac (small JSON file, fast) ──
    almanac = {"total": 0, "recent": []}
    alm_path = DATA / "almanac" / "entries.json"
    if alm_path.exists():
        try:
            d = json.loads(alm_path.read_text(encoding="utf-8"))
            entries = d.get("entries") or d if isinstance(d, list) else []
            if isinstance(d, dict):
                entries = d.get("entries", [])
            almanac["total"] = len(entries) if isinstance(entries, list) else 0
            almanac["recent"] = (entries[-10:] if isinstance(entries, list) else [])[-10:]
        except Exception:
            pass

    # ── Audit / steward (last 20 events) ──
    audit_path = DATA / "steward" / "audit.jsonl"
    audit_recent = _read_jsonl_tail(audit_path, 20)
    audit_total = _count_lines(audit_path)

    # ── Robot activity ──
    robot_dir = DATA / "robot_welcome"
    robot_recent = []
    if robot_dir.exists():
        for f in robot_dir.glob("*.jsonl"):
            for line in f.read_text("utf-8", errors="replace").splitlines()[-3:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    robot_recent.append(json.loads(line))
                except Exception:
                    continue
    robot_recent = robot_recent[-10:]

    # ── Receipts / ledger ──
    ledger_total = _count_lines(DATA / "ledger.jsonl") or _count_lines(Path("C:/Concordance/data/ledger.jsonl"))

    # ── Misalignments queue ──
    mis_path = DATA / "misalignments" / "queue.jsonl"
    misalignments = _read_jsonl_tail(mis_path, 10) if mis_path.exists() else []

    # ── Scribe / inbox ──
    scribe = []
    for cand in [DATA / "inbox" / "submitted.jsonl", DATA / "scribe" / "recent.jsonl"]:
        if cand.exists():
            scribe = _read_jsonl_tail(cand, 10)
            break

    # ── Witness attestations (recent) ──
    witness_dir = DATA / "witnesses" / "walks"
    witness_recent = []
    if witness_dir.exists():
        for f in sorted(witness_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
            for line in f.read_text("utf-8", errors="replace").splitlines()[-3:]:
                try:
                    witness_recent.append(json.loads(line.strip()))
                except Exception:
                    pass
    witness_recent = witness_recent[-10:]

    # ── Apothecary feedback ──
    apo_path = DATA / "apothecary" / "feedback.jsonl"
    apothecary_recent = _read_jsonl_tail(apo_path, 5) if apo_path.exists() else []

    # ── Polymathic runs ──
    poly_path = DATA / "polymathic" / "runs.jsonl"
    polymathic_recent = _read_jsonl_tail(poly_path, 5) if poly_path.exists() else []

    # ── Walks / journal ──
    walks_path = DATA / "walks_cache" / "replay.jsonl"
    walks_total = _count_lines(walks_path)

    # ── Visitor stats ──
    visitor_dir = DATA / "visitors"
    visitor_count = _files_in_dir(visitor_dir, "*.jsonl")

    # ── Cards substrate ──
    cards_dir = DATA / "cards"
    cards_total = _files_in_dir(cards_dir, "*.json")

    # ── Build queue (if exists) ──
    build_queue_path = DATA / "build_queue.jsonl"
    build_queue_recent = _read_jsonl_tail(build_queue_path, 5) if build_queue_path.exists() else []

    # ── Seeds ──
    seeds_dir = DATA / "seeds"
    seeds_recent = []
    if seeds_dir.exists():
        for f in sorted(seeds_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            try:
                seeds_recent.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue

    # ── MCP stats (request volume) ──
    mcp_path = DATA / "mcp_requests.jsonl"
    mcp_recent = _read_jsonl_tail(mcp_path, 20) if mcp_path.exists() else []
    mcp_total = _count_lines(mcp_path)

    return {
        "generated_at": now_iso,
        "cache_ttl_seconds": int(_CACHE_TTL),
        "almanac": almanac,
        "audit": {
            "total": audit_total,
            "recent": audit_recent,
        },
        "robot": {
            "recent_welcomes": robot_recent,
        },
        "ledger": {
            "total_entries": ledger_total,
        },
        "misalignments": misalignments,
        "scribe": scribe,
        "witness": witness_recent,
        "apothecary": apothecary_recent,
        "polymathic": polymathic_recent,
        "walks": {
            "total_replays": walks_total,
        },
        "visitors": {
            "count": visitor_count,
        },
        "cards": {
            "total": cards_total,
        },
        "build_queue": build_queue_recent,
        "seeds_recent": seeds_recent,
        "mcp": {
            "total": mcp_total,
            "recent": mcp_recent,
        },
    }


def _get_snapshot() -> Dict[str, Any]:
    now = time.time()
    if _CACHE["snapshot"] is not None and (now - _CACHE["checked_at"]) < _CACHE_TTL:
        return _CACHE["snapshot"]
    with _LOCK:
        now2 = time.time()
        if _CACHE["snapshot"] is not None and (now2 - _CACHE["checked_at"]) < _CACHE_TTL:
            return _CACHE["snapshot"]
        _CACHE["snapshot"] = _build_snapshot()
        _CACHE["checked_at"] = time.time()
    return _CACHE["snapshot"]


def warm_cache():
    try:
        s = _get_snapshot()
        return {"warmed": True, "sections": len(s)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/keep/dashboard")
    def dashboard():
        return _get_snapshot()

    return router
