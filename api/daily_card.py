"""daily_card.py — Card of the Day (LOOP 39).

Deterministic daily rotation. Same date → same card. Tomorrow → next card.
Picks from cards with:
  - lifecycle_stage in (public, featured)
  - volatility = permanent
  - authority_tier in (scripture, catechism, creed, father, matt) — the durable stuff

The deterministic part: hash(date_iso + 'card-of-the-day') % len(pool) → index.

This is a card-of-the-day, not a random pick — every household around the world
sees the same card today. That's intentional: it gives the audience something
common to walk through.

Endpoints:
  GET /daily-card                 today's card
  GET /daily-card?date=YYYY-MM-DD specific date
  GET /daily-card/pool            stats on the eligible pool
"""
from __future__ import annotations
import hashlib
import json
import threading
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Query
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"

_ELIGIBLE_TIERS = ("scripture", "catechism", "creed", "father", "matt")
_ELIGIBLE_STAGES = ("public", "featured")

# Pool cache: two-layer invalidation.
#  - Hot path: TTL window skips disk entirely. Without this, every saved walk-card
#    bumped the cards-dir mtime and forced a full 11k-file rescan (~5s).
#  - Cold path: cheap dir-mtime check; rebuild only when substrate actually changed.
_POOL_CACHE: dict = {"pool": None, "dir_mtime": 0.0, "checked_at": 0.0}
# TTL = 30s, paired with the periodic warmer (api/app.py, 25s interval)
_CACHE_TTL_SECONDS = 30.0
# Single-flight lock to prevent thundering-herd cache rebuilds
_POOL_REBUILD_LOCK = threading.Lock()


def _build_pool() -> list[dict]:
    now = time.time()
    # Hot path: serve cached pool without touching disk
    if _POOL_CACHE["pool"] is not None and (now - _POOL_CACHE["checked_at"]) < _CACHE_TTL_SECONDS:
        return _POOL_CACHE["pool"]
    # Cold path: single-stat dir mtime
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _POOL_CACHE["pool"] is not None and abs(dir_mtime - _POOL_CACHE["dir_mtime"]) < 1.0:
        _POOL_CACHE["checked_at"] = now
        return _POOL_CACHE["pool"]

    # Single-flight rebuild
    with _POOL_REBUILD_LOCK:
        # Re-check after acquiring lock
        now = time.time()
        if _POOL_CACHE["pool"] is not None and (now - _POOL_CACHE["checked_at"]) < _CACHE_TTL_SECONDS:
            return _POOL_CACHE["pool"]
        return _rebuild_pool_locked(dir_mtime)


def _rebuild_pool_locked(dir_mtime: float) -> list[dict]:
    """Caller must hold _POOL_REBUILD_LOCK."""
    pool = []
    if not CARDS_DIR.exists():
        _POOL_CACHE["pool"] = pool
        _POOL_CACHE["dir_mtime"] = dir_mtime
        _POOL_CACHE["checked_at"] = time.time()
        return pool
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("kind") in ("connection", "search", "community_note", "stack"):
            continue
        if c.get("lifecycle_stage") not in _ELIGIBLE_STAGES:
            continue
        if c.get("volatility") != "permanent":
            continue
        tier = (c.get("source") or {}).get("authority_tier")
        if tier not in _ELIGIBLE_TIERS:
            continue
        if c.get("retracted"):
            continue
        pool.append(c)
    # Stable sort by id for reproducibility
    pool.sort(key=lambda x: x.get("id", ""))
    _POOL_CACHE["pool"] = pool
    _POOL_CACHE["checked_at"] = time.time()
    _POOL_CACHE["dir_mtime"] = dir_mtime
    return pool


def warm_cache():
    """Prime the daily-card eligible-pool cache."""
    try:
        pool = _build_pool()
        return {"warmed": True, "pool_size": len(pool)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def _date_str(d: Optional[date] = None) -> str:
    d = d or datetime.now(timezone.utc).date()
    return d.isoformat()


def _pick_for_date(date_iso: str, pool: list[dict]) -> Optional[dict]:
    if not pool:
        return None
    h = hashlib.sha256(f"{date_iso}::card-of-the-day::nh".encode("utf-8")).digest()
    idx = int.from_bytes(h[:8], "big") % len(pool)
    return pool[idx]


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/daily-card")
    def daily_card(date_param: Optional[str] = Query(None, alias="date")):
        d = date_param or _date_str()
        # Validate format
        try:
            date.fromisoformat(d)
        except Exception:
            raise HTTPException(400, "Invalid date format (expected YYYY-MM-DD)")
        pool = _build_pool()
        card = _pick_for_date(d, pool)
        if not card:
            return {"date": d, "card": None, "_note": "No eligible cards in the pool yet."}
        # Stand the day's card on the whole floor — Canon anchor + the four
        # gates + the verifier its shelf implies — so even the daily draw is
        # not a loose quote but something standing on the foundation.
        _floor_standing = None
        try:
            from api import floor as _floor
            _txt = " ".join(str(card.get(k) or "") for k in ("title", "body"))[:1000]
            _floor_standing = _floor.stand_on_floor(_txt, domain=card.get("shelf"), kind="card")
        except Exception:
            _floor_standing = None
        return {
            "date": d,
            "card": {
                "id": card.get("id"),
                "title": card.get("title"),
                "body": card.get("body"),
                "source": card.get("source"),
                "shelf": card.get("shelf"),
                "box": card.get("box"),
                "url": f"/card.html?id={card.get('id')}",
            },
            "floor": _floor_standing,
            "pool_size": len(pool),
        }

    @router.get("/daily-card/pool")
    def daily_card_pool():
        pool = _build_pool()
        by_shelf = {}
        by_tier = {}
        for c in pool:
            s = c.get("shelf", "?")
            by_shelf[s] = by_shelf.get(s, 0) + 1
            t = (c.get("source") or {}).get("authority_tier", "?")
            by_tier[t] = by_tier.get(t, 0) + 1
        return {
            "pool_size": len(pool),
            "by_shelf": by_shelf,
            "by_authority_tier": by_tier,
            "_note": "Eligible: lifecycle=public/featured, volatility=permanent, authority in (scripture/catechism/creed/father/matt).",
        }

    return router
