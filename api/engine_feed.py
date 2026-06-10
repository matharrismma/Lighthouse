"""engine_feed.py — Operator endpoints for the engine-generated content queue.

The nightly engine_daily.py drops generated items into data/engine_queue/.
The operator reviews them via /engine-queue.html (which uses these endpoints):

  GET  /engine/queue?status=quarantined  — list items
  GET  /engine/queue/{id}                 — one item
  POST /engine/queue/{id}/approve         — approve & (later) publish to substrate
  POST /engine/queue/{id}/reject          — reject with operator note

Approval is the gate. Publishing-to-substrate is deferred per kind; for now,
approval just marks status=approved and records who. A separate publishing
script reads approved items and merges them into the appropriate substrate
files (hymns.json, recipes.json, almanac packets, etc).
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Query, Body
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
QUEUE_DIR = REPO / "data" / "engine_queue"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(qid: str) -> dict | None:
    p = QUEUE_DIR / f"{qid}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _save(item: dict):
    p = QUEUE_DIR / f"{item['id']}.json"
    p.write_text(json.dumps(item, indent=2), encoding="utf-8")


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/engine/queue")
    def list_queue(status: Optional[str] = Query(None), kind: Optional[str] = Query(None)):
        if not QUEUE_DIR.exists():
            return {"items": [], "count": 0}
        items = []
        for f in sorted(QUEUE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if status and rec.get("status") != status:
                continue
            if kind and rec.get("kind") != kind:
                continue
            items.append(rec)
        return {"items": items, "count": len(items)}

    @router.get("/engine/queue/{qid}")
    def get_one(qid: str):
        rec = _load(qid)
        if not rec:
            raise HTTPException(404)
        return rec

    @router.post("/engine/queue/{qid}/approve")
    def approve(qid: str, body: dict = Body(default={})):
        rec = _load(qid)
        if not rec:
            raise HTTPException(404)
        rec["status"] = "approved"
        rec["approved_at"] = _now()
        rec["approver_note"] = body.get("note", "")
        _save(rec)
        return {"id": qid, "status": "approved", "kind": rec.get("kind")}

    @router.post("/engine/queue/{qid}/reject")
    def reject(qid: str, body: dict = Body(default={})):
        rec = _load(qid)
        if not rec:
            raise HTTPException(404)
        rec["status"] = "rejected"
        rec["rejected_at"] = _now()
        rec["rejector_note"] = body.get("note", "")
        _save(rec)
        return {"id": qid, "status": "rejected"}

    @router.get("/engine/queue.stats")
    def stats():
        counts = {"quarantined": 0, "approved": 0, "rejected": 0}
        by_kind = {}
        if QUEUE_DIR.exists():
            for f in QUEUE_DIR.glob("*.json"):
                try:
                    rec = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                s = rec.get("status", "quarantined")
                counts[s] = counts.get(s, 0) + 1
                k = rec.get("kind", "?")
                by_kind[k] = by_kind.get(k, 0) + 1
        return {"counts_by_status": counts, "counts_by_kind": by_kind}

    return router
