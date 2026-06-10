"""atlas.py — The book of paths (LOOP 17).

Walks are first-class cards. The Atlas is the shelf where they live. A walk
carries the title (the question that was asked), the body (Shepherd's
narration of the path), and a connections list that traverses the cards in
order. Walks are tradeable like every other card — paperclip, share, fork,
tip.

Two kinds of walks distinguished by lifecycle:
  - WALK CARDS (auto-generated) — saved when a user finishes a walk with
    save_as_walk=true. Land in quarantine. Operator promotes the durable ones
    to `public_review` → `public` → `featured`.
  - ATLAS PATHS (operator-curated) — Matt authors these directly. Canonical
    walks the family should take: "How to read Romans," "The Trinity in 5
    cards," "A child's first catechism walk." Start at `public_review` and
    quickly promote.

This module surfaces:
  - List all walks (kind=walk) on the Atlas shelf
  - Promote a walk to canonical Atlas path
  - "Replay a walk" — re-walk the same cards as a session, with prefetch
  - Author an operator-curated Atlas path

Endpoints:
  GET   /atlas/paths                   list all walks/paths
  GET   /atlas/paths/featured          only featured paths
  GET   /atlas/paths/{walk_card_id}    full walk: cards in order, narration
  POST  /atlas/paths                   author a curated path (operator)
  POST  /atlas/paths/{id}/canonize     fast-promote walk → public
  POST  /atlas/paths/{id}/replay       re-walk; warms prefetch
"""
from __future__ import annotations
import json
import threading
import time
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
CARDS_DIR = REPO / "data" / "cards"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _card_path(cid: str) -> Path:
    return CARDS_DIR / f"{cid}.json"


def _read_card(cid: str) -> Optional[dict]:
    p = _card_path(cid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _persist_card(card: dict):
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    _card_path(card["id"]).write_text(json.dumps(card, indent=2), encoding="utf-8")


# Cache walk-cards. Two-layer invalidation:
#  - Hot path: short TTL (10s) skip-the-mtime-check. Most requests bypass disk
#    entirely. Without this, every walk-save bumped the cards-dir mtime and
#    forced a full 11k-file rescan on the next /atlas/paths call (~1.7s).
#  - Cold path: when TTL expires, do the cheap dir-mtime check; if substrate
#    actually changed, rebuild from disk.
_WALK_CACHE: dict = {"walks": None, "dir_mtime": 0.0, "checked_at": 0.0}
# TTL = 30s. Paired with the periodic background warmer (api/app.py) that
# refreshes caches every 25s, this keeps user requests on the hot path
# always — rebuilds happen in the warmer thread, never on the request path.
_CACHE_TTL_SECONDS = 30.0
# Single-flight lock: when N requests hit a cold cache simultaneously, only
# one thread rebuilds; the others wait at the lock and then read the populated
# cache. Without this, concurrent first-callers each did an 11k-file scan.
_WALK_REBUILD_LOCK = threading.Lock()


def _all_walk_cards():
    if not CARDS_DIR.exists():
        return
    now = time.time()
    # Hot path: serve from cache without touching disk for TTL window
    if _WALK_CACHE["walks"] is not None and (now - _WALK_CACHE["checked_at"]) < _CACHE_TTL_SECONDS:
        for w in _WALK_CACHE["walks"]:
            yield w
        return
    # Cold path: dir-mtime check (single stat, microsecond cost)
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime
    except Exception:
        dir_mtime = 0.0
    if _WALK_CACHE["walks"] is not None and abs(dir_mtime - _WALK_CACHE["dir_mtime"]) < 1.0:
        _WALK_CACHE["checked_at"] = now
        for w in _WALK_CACHE["walks"]:
            yield w
        return
    # Rebuild — substrate has actually changed. Single-flight: only one thread
    # does the work; concurrent callers wait at the lock and read the result.
    with _WALK_REBUILD_LOCK:
        # Re-check after acquiring lock (another thread may have just rebuilt)
        now = time.time()
        if _WALK_CACHE["walks"] is not None and (now - _WALK_CACHE["checked_at"]) < _CACHE_TTL_SECONDS:
            for w in _WALK_CACHE["walks"]:
                yield w
            return
        walks = []
        for f in CARDS_DIR.glob("*.json"):
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
                if c.get("kind") == "walk":
                    walks.append(c)
            except Exception:
                continue
        _WALK_CACHE["walks"] = walks
        _WALK_CACHE["dir_mtime"] = dir_mtime
        _WALK_CACHE["checked_at"] = time.time()
    # Yield outside lock — we already have a coherent snapshot
    for w in _WALK_CACHE["walks"]:
        yield w


def warm_cache():
    """Prime the walk-card cache. Safe to call from startup or admin endpoints.
    Triggers a rebuild only if the cache isn't already hot."""
    try:
        list(_all_walk_cards())
        return {"warmed": True, "walks": len(_WALK_CACHE["walks"] or [])}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


if APIRouter is not None:
    class AtlasPathIn(BaseModel):
        title: str
        narration: str  # the body — what Shepherd says about this walk
        card_ids: list[str]  # ordered list of cards on the walk
        bands: Optional[list[str]] = None
        per_step_narration: Optional[list[str]] = None
        box: Optional[str] = "curated"
        volatility: Optional[str] = "permanent"


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/atlas/paths")
    def list_paths(lifecycle: Optional[str] = None, limit: int = 100):
        out = []
        for w in _all_walk_cards():
            if lifecycle and w.get("lifecycle_stage") != lifecycle:
                continue
            ex = w.get("extra") or {}
            out.append({
                "card_id": w.get("id"),
                "title": w.get("title"),
                "body": w.get("body", "")[:300],
                "shelf": w.get("shelf", "atlas"),
                "box": w.get("box", "walks"),
                "step_count": ex.get("walk_total_steps") or len(ex.get("cards_surfaced") or []),
                "lifecycle_stage": w.get("lifecycle_stage"),
                "author": w.get("author"),
                "created_at": w.get("created_at"),
                "metrics": w.get("metrics", {}),
                "asked_by": ex.get("asked_by"),
                "query": ex.get("query"),
            })
        # Sort: featured first, then public, then newest
        stage_order = {"featured": 0, "public": 1, "public_review": 2, "private": 3, "shared": 4, "quarantine": 5, "fading": 6, "archived": 9}
        out.sort(key=lambda x: (stage_order.get(x.get("lifecycle_stage", "?"), 7), -1 * (x.get("metrics", {}).get("paperclips_count", 0))))
        return {"count": len(out[:limit]), "total": len(out), "paths": out[:limit]}

    @router.get("/atlas/paths/featured")
    def featured(limit: int = 30):
        out = []
        for w in _all_walk_cards():
            if w.get("lifecycle_stage") == "featured":
                ex = w.get("extra") or {}
                out.append({
                    "card_id": w.get("id"),
                    "title": w.get("title"),
                    "body": w.get("body", "")[:300],
                    "step_count": ex.get("walk_total_steps") or len(ex.get("cards_surfaced") or []),
                    "author": w.get("author"),
                    "created_at": w.get("created_at"),
                })
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"count": len(out[:limit]), "paths": out[:limit]}

    @router.get("/atlas/paths/{walk_card_id}")
    def get_path(walk_card_id: str):
        walk = _read_card(walk_card_id)
        if walk is None or walk.get("kind") != "walk":
            raise HTTPException(404, "Walk not found")
        ex = walk.get("extra") or {}
        # Hydrate each card in the walk
        cards = []
        ordered_ids = ex.get("cards_surfaced") or []
        step_narrations = {s.get("card_id"): s.get("narration") for s in (ex.get("walk_steps") or []) if isinstance(s, dict)}
        for cid in ordered_ids:
            c = _read_card(cid)
            if c:
                cards.append({
                    "card_id": cid,
                    "title": c.get("title"),
                    "body": (c.get("body") or "")[:600],
                    "source": c.get("source") or {},
                    "shelf": c.get("shelf"),
                    "box": c.get("box"),
                    "narration": step_narrations.get(cid, ""),
                })
        return {
            "card_id": walk.get("id"),
            "title": walk.get("title"),
            "body": walk.get("body"),
            "author": walk.get("author"),
            "lifecycle_stage": walk.get("lifecycle_stage"),
            "step_count": len(cards),
            "cards": cards,
            "query": ex.get("query"),
        }

    @router.post("/atlas/paths")
    def author_path(payload: AtlasPathIn):
        """Operator authors a curated Atlas path. Goes straight to public_review."""
        try:
            from api.cards import _make_card_id, _compute_source_hash, _save_card  # type: ignore
        except Exception:
            raise HTTPException(500, "Cards module unavailable")
        # Validate cards exist
        valid_ids = []
        for cid in payload.card_ids:
            if _read_card(cid):
                valid_ids.append(cid)
        if not valid_ids:
            raise HTTPException(400, "No valid cards in card_ids")
        per_step = payload.per_step_narration or []
        steps = []
        for i, cid in enumerate(valid_ids):
            narr = per_step[i] if i < len(per_step) else ""
            steps.append({"card_id": cid, "narration": narr})
        now = _now()
        wid = _make_card_id("walk", f"atlas::{payload.title}::{now[:10]}")
        walk_card = {
            "id": wid,
            "kind": "walk",
            "title": payload.title[:200],
            "body": payload.narration[:4000],
            "source": {
                "label": "Operator-curated Atlas path",
                "url": "",
                "ref": "",
                "authority_tier": "matt",
            },
            "shelf": "atlas",
            "box": payload.box or "curated",
            "bands": payload.bands or ["atlas", "curated"],
            "connections": [{"to_card_id": cid, "relationship": "cites"} for cid in valid_ids],
            "author": "matt",
            "created_at": now,
            "updated_at": now,
            "visibility": "public",
            "lifecycle_stage": "public_review",
            "volatility": payload.volatility or "permanent",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "extra": {
                "query": payload.title,
                "asked_by": "matt",
                "walk_steps": steps,
                "walk_total_steps": len(steps),
                "cards_surfaced": valid_ids,
                "curated": True,
            },
        }
        walk_card["source_hash"] = _compute_source_hash(walk_card)
        _save_card(walk_card)
        return {"status": "authored", "card_id": wid, "step_count": len(steps), "lifecycle_stage": "public_review"}

    @router.post("/atlas/paths/{walk_card_id}/canonize")
    def canonize(walk_card_id: str):
        """Operator approval — promote walk to public + mark visibility public."""
        walk = _read_card(walk_card_id)
        if walk is None or walk.get("kind") != "walk":
            raise HTTPException(404, "Walk not found")
        prev = walk.get("lifecycle_stage", "quarantine")
        walk["lifecycle_stage"] = "public"
        walk["visibility"] = "public"
        walk["updated_at"] = _now()
        _persist_card(walk)
        return {"status": "canonized", "card_id": walk_card_id, "from": prev}

    @router.post("/atlas/paths/{walk_card_id}/replay")
    def replay(walk_card_id: str):
        """Re-walk: increment walks_through_count, warm prefetch for the path's cards."""
        walk = _read_card(walk_card_id)
        if walk is None or walk.get("kind") != "walk":
            raise HTTPException(404, "Walk not found")
        m = walk.get("metrics") or {}
        m["walks_through_count"] = m.get("walks_through_count", 0) + 1
        walk["metrics"] = m
        walk["updated_at"] = _now()
        _persist_card(walk)
        # Warm prefetch — pre-load the working set with the path's cards
        try:
            from api.cards import working_set as _ws  # type: ignore
            for cid in ((walk.get("extra") or {}).get("cards_surfaced") or []):
                c = _read_card(cid)
                if c:
                    _ws().put(cid, c)
        except Exception:
            pass
        ex = walk.get("extra") or {}
        return {
            "status": "replayed",
            "card_id": walk_card_id,
            "title": walk.get("title"),
            "card_ids": ex.get("cards_surfaced") or [],
            "walks_through_count": m["walks_through_count"],
        }

    return router
