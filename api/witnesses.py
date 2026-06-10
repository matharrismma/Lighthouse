"""witnesses.py — Source-witness API (Deut 19:15 at the source layer).

Surfaces the witness chain (>=2 independent corroborating sources) attached
to each card by tools/source_witness_gate.py. Also exposes channel pool
witness data so the FAST channel UI can render the provenance trail.

The gate runs offline (cron); this API just reads what's on disk.

Endpoints:
  GET /witness-gate/health             distribution of witness_status over all cards
  GET /witness-gate/card/{card_id}     witnesses for a specific card
  GET /witness-gate/missing            cards still at self_only / insufficient (operator queue)
  GET /witness-gate/channel/{ch_id}    pool item witness distribution

Reading from disk every call would walk 11k files; cache via the same
mtime-aware pattern used elsewhere (atlas.py, daily_card.py).
"""
from __future__ import annotations
import json
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
CHANNELS_DIR = REPO / "content" / "channels"

_CACHE: dict = {"snapshot": None, "checked_at": 0.0, "dir_mtime": 0.0}
_CACHE_TTL = 30.0
_LOCK = threading.Lock()


def _read_card(cid: str) -> Optional[dict]:
    p = CARDS_DIR / f"{cid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_snapshot() -> dict:
    """Walk all cards, tally witness_status + by tier."""
    status = Counter()
    by_tier_status: dict = {}
    missing = []
    total = 0
    if not CARDS_DIR.exists():
        return {"total_cards": 0, "by_status": {}, "by_tier_status": {}, "missing_count": 0}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        ws = c.get("witness_status") or "unset"
        tier = (c.get("source") or {}).get("authority_tier") or "unset"
        status[ws] += 1
        by_tier_status.setdefault(tier, Counter())[ws] += 1
        if ws in ("self_only", "insufficient", "gov_only", "unset"):
            if len(missing) < 200:
                missing.append({
                    "card_id": c.get("id"),
                    "title": (c.get("title") or "")[:120],
                    "tier": tier,
                    "label": ((c.get("source") or {}).get("label") or "")[:120],
                    "witness_status": ws,
                    "reason": c.get("witness_status_reason"),
                })
    return {
        "total_cards": total,
        "by_status": dict(status),
        "by_tier_status": {t: dict(c) for t, c in by_tier_status.items()},
        "missing_count": len(missing),
        "missing_sample": missing,
    }


def _get_snapshot() -> dict:
    now = time.time()
    if _CACHE["snapshot"] is not None and (now - _CACHE["checked_at"]) < _CACHE_TTL:
        return _CACHE["snapshot"]
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _CACHE["snapshot"] is not None and abs(dir_mtime - _CACHE["dir_mtime"]) < 1.0:
        _CACHE["checked_at"] = now
        return _CACHE["snapshot"]
    with _LOCK:
        now2 = time.time()
        if _CACHE["snapshot"] is not None and (now2 - _CACHE["checked_at"]) < _CACHE_TTL:
            return _CACHE["snapshot"]
        _CACHE["snapshot"] = _build_snapshot()
        _CACHE["dir_mtime"] = dir_mtime
        _CACHE["checked_at"] = time.time()
    return _CACHE["snapshot"]


def warm_cache():
    try:
        s = _get_snapshot()
        return {"warmed": True, "total_cards": s.get("total_cards", 0)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/witness-gate/health")
    def health():
        s = _get_snapshot()
        return {
            "deuteronomy_19_15": "every card requires >=2 independent witnesses; government cannot witness itself",
            "total_cards": s["total_cards"],
            "by_status": s["by_status"],
            "by_tier_status": s["by_tier_status"],
            "missing_count": s["missing_count"],
        }

    @router.get("/witness-gate/card/{card_id}")
    def card_witnesses(card_id: str):
        c = _read_card(card_id)
        if c is None:
            raise HTTPException(404, "card not found")
        return {
            "card_id": c.get("id"),
            "title": c.get("title"),
            "source": c.get("source") or {},
            "witnesses": c.get("witnesses") or [],
            "witness_status": c.get("witness_status"),
            "witness_status_reason": c.get("witness_status_reason"),
        }

    @router.get("/witness-gate/missing")
    def missing(limit: int = 50):
        s = _get_snapshot()
        return {
            "count": s["missing_count"],
            "operator_queue": s["missing_sample"][:limit],
            "note": "these cards have not satisfied the 2-witness rule; promote witnesses via tools/witness_registry.py",
        }

    @router.get("/witness-gate/channel/{channel_id}")
    def channel_pool_witnesses(channel_id: str):
        path = CHANNELS_DIR / f"narrow_highway.json"
        # Currently only one channel manifest; can branch on channel_id later
        if not path.exists():
            raise HTTPException(404, "channel manifest not found")
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise HTTPException(500, f"could not read channel manifest: {e}")
        pool = m.get("content_pool") or {}
        status_count = Counter()
        by_key = {}
        for k, items in pool.items():
            cnt = Counter()
            for it in items:
                ws = it.get("witness_status") or "unset"
                status_count[ws] += 1
                cnt[ws] += 1
            by_key[k] = dict(cnt)
        return {
            "channel_id": channel_id,
            "total_pool_items": sum(len(v) for v in pool.values()),
            "by_status": dict(status_count),
            "by_pool_key": by_key,
        }

    return router
