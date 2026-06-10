"""rebalance.py — Rebalance queue endpoint (LOOP 32).

The nightly rebalancer writes proposals to `data/rebalance_queue.json`.
This module exposes operator-facing read + decide endpoints.

Endpoints:
  GET   /rebalance/queue                pending suggestions
  POST  /rebalance/approve              accept a suggestion (apply it)
  POST  /rebalance/reject               mark suggestion as rejected
  GET   /rebalance/reports              recent run reports (data/rebalance/*.json)
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore

REPO = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO / "data" / "rebalance_queue.json"
REPORTS_DIR = REPO / "data" / "rebalance"
CARDS_DIR = REPO / "data" / "cards"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_queue() -> list:
    if not QUEUE_PATH.exists():
        return []
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(q: list):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(q, indent=2), encoding="utf-8")


def _read_card(cid: str) -> Optional[dict]:
    p = CARDS_DIR / f"{cid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _persist_card(c: dict):
    (CARDS_DIR / f"{c['id']}.json").write_text(json.dumps(c, indent=2), encoding="utf-8")


if APIRouter is not None:
    class Decision(BaseModel):
        kind: str  # the suggestion kind (archive_orphan, merge_duplicate, split_box, canonize_walk)
        card_ids: list[str]
        operator_note: Optional[str] = None


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/rebalance/queue")
    def get_queue(status: Optional[str] = "pending"):
        q = _load_queue()
        if status:
            q = [i for i in q if i.get("status") == status]
        return {"count": len(q), "items": q}

    @router.post("/rebalance/approve")
    def approve(payload: Decision):
        q = _load_queue()
        target_ids = sorted(payload.card_ids)
        item = None
        for x in q:
            if x.get("status") == "pending" and x.get("kind") == payload.kind and sorted(x.get("card_ids", [])) == target_ids:
                item = x
                break
        if not item:
            raise HTTPException(404, "No matching pending suggestion")

        applied = {}
        if payload.kind == "archive_orphan":
            if payload.card_ids:
                cid = payload.card_ids[0]
                c = _read_card(cid)
                if c:
                    c["lifecycle_stage"] = "archived"
                    c["archived_at"] = _now()
                    c["archived_reason"] = "rebalancer:orphan"
                    _persist_card(c)
                    applied["archived"] = cid
        elif payload.kind == "canonize_walk":
            if payload.card_ids:
                cid = payload.card_ids[0]
                c = _read_card(cid)
                if c:
                    c["lifecycle_stage"] = "public"
                    c["visibility"] = "public"
                    c["updated_at"] = _now()
                    _persist_card(c)
                    applied["canonized"] = cid
        elif payload.kind == "split_box":
            # We don't auto-split; operator must do this manually. Just acknowledge.
            applied["split_box_acknowledged"] = item.get("box")
        elif payload.kind == "merge_duplicate":
            # Never auto-merge. Operator must do it. Just acknowledge.
            applied["merge_acknowledged"] = payload.card_ids

        item["status"] = "approved"
        item["approved_at"] = _now()
        item["operator_note"] = (payload.operator_note or "")[:300]
        item["applied"] = applied
        _save_queue(q)
        return {"status": "approved", "applied": applied}

    @router.post("/rebalance/reject")
    def reject(payload: Decision):
        q = _load_queue()
        target_ids = sorted(payload.card_ids)
        item = None
        for x in q:
            if x.get("status") == "pending" and x.get("kind") == payload.kind and sorted(x.get("card_ids", [])) == target_ids:
                item = x
                break
        if not item:
            raise HTTPException(404, "No matching pending suggestion")
        item["status"] = "rejected"
        item["rejected_at"] = _now()
        item["operator_note"] = (payload.operator_note or "")[:300]
        _save_queue(q)
        return {"status": "rejected"}

    @router.get("/rebalance/reports")
    def get_reports(limit: int = 10):
        if not REPORTS_DIR.exists():
            return {"count": 0, "items": []}
        files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        out = []
        for f in files:
            try:
                out.append({"path": str(f.relative_to(REPO)), "content": json.loads(f.read_text(encoding="utf-8"))})
            except Exception:
                continue
        return {"count": len(out), "items": out}

    return router
