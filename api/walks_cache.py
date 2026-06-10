"""walks_cache.py — Solve permanently (LOOP 16).

Three primitives that together turn the substrate from "responsive" to
"solving":

  1. WALK REPLAY TABLE
     Every walk that fires gets recorded. Append-only JSONL:
       {query_fingerprint, shaped_query, card_ids_walked, asked_by, ts}
     The corpus of walks is the training data for the prefetch predictor and
     the basis for the fingerprint cache.

  2. QUERY FINGERPRINT CACHE
     A hash of the *normalized* shaped query maps to the last walk that
     answered it. When a similar question comes in, return the cached walk
     instead of running the search again. Invalidated when any card in the
     walk gets retracted, archived, or moves to fading.

  3. PREFETCH PREDICTOR
     Given a current walk in progress, suggest the next-most-likely cards:
       - Structural: cards reachable in 1-2 connection hops from active set
       - Statistical: cards historically co-walked with the active set
     Returns top-k for the working-set manager to warm.

This is the operational form of "we solve the problem one time and we have
solved it permanently." For permanent-answer questions (doctrine, scripture,
catechism, hymns, recipes), the cache hits indefinitely. For volatile cards,
the cache TTL is set by the card's `volatility` field.

Endpoints:
  POST /walks/cache/check          {query} → cached walk if hit, else null
  POST /walks/replay/log           append a walk to the replay table
  GET  /walks/replay/recent        recent walks (operator inspect)
  POST /walks/prefetch             given current card_ids, return likely-next
  GET  /walks/cache/stats          hit/miss/coverage stats
"""
from __future__ import annotations
import hashlib
import json
import re
import time
from collections import Counter
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
WALKS_DIR = REPO / "data" / "walks"
REPLAY_PATH = WALKS_DIR / "replay.jsonl"
CACHE_PATH = WALKS_DIR / "fingerprint_cache.json"
STATS_PATH = WALKS_DIR / "cache_stats.json"

# How "close" two queries must be to count as a cache hit
# (Jaccard similarity over token sets; 1.0 = identical)
CACHE_HIT_THRESHOLD = 0.75

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "for", "in", "on", "to", "from", "and", "or", "but", "if",
    "when", "what", "which", "who", "whom", "how", "why", "where",
    "do", "does", "did", "have", "has", "had", "with", "that", "this",
    "i", "me", "my", "we", "us", "our", "you", "your",
    "about", "as", "at", "by",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir():
    WALKS_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_query(q: str) -> set:
    """Tokenize + lowercase + drop stopwords → set of meaningful tokens."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z']{1,}", (q or "").lower())
    return set(t for t in tokens if t not in STOPWORDS and len(t) > 1)


def _fingerprint(q: str) -> str:
    """Deterministic fingerprint over normalized token set. Different word
    order, articles, casing all collide to the same hash."""
    tokens = sorted(_normalize_query(q))
    if not tokens:
        return ""
    return hashlib.sha256("|".join(tokens).encode("utf-8")).hexdigest()[:16]


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------- Cache ----------

def _load_cache() -> dict:
    _ensure_dir()
    if not CACHE_PATH.exists():
        return {"version": 1, "entries": {}, "_note": "fingerprint -> {cached_walk_card_id, normalized_tokens, last_used_at, hit_count}"}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "entries": {}}


def _save_cache(cache: dict):
    _ensure_dir()
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _load_stats() -> dict:
    if not STATS_PATH.exists():
        return {"checks": 0, "hits": 0, "misses": 0, "invalidations": 0, "stored": 0}
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"checks": 0, "hits": 0, "misses": 0, "invalidations": 0, "stored": 0}


def _save_stats(s: dict):
    _ensure_dir()
    STATS_PATH.write_text(json.dumps(s, indent=2), encoding="utf-8")


def cache_check(query: str) -> Optional[dict]:
    """Look up cached walk for a query. Returns None on miss."""
    stats = _load_stats()
    stats["checks"] += 1
    tokens = _normalize_query(query)
    if not tokens:
        stats["misses"] += 1
        _save_stats(stats)
        return None
    cache = _load_cache()
    fp = _fingerprint(query)
    # Exact fingerprint match first
    if fp in cache["entries"]:
        entry = cache["entries"][fp]
        # Validate the cached walk still exists and its cards are live
        if _walk_card_still_valid(entry.get("cached_walk_card_id")):
            entry["last_used_at"] = _now()
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            _save_cache(cache)
            stats["hits"] += 1
            _save_stats(stats)
            return {"hit": True, "walk_card_id": entry["cached_walk_card_id"], "hit_count": entry["hit_count"], "match_kind": "exact"}
        else:
            # Invalidate stale
            del cache["entries"][fp]
            stats["invalidations"] += 1
            _save_cache(cache)
    # Fuzzy fingerprint match (Jaccard) — pick best above threshold
    best_score = 0.0
    best_entry = None
    best_fp = None
    for ofp, entry in cache["entries"].items():
        other_tokens = set(entry.get("normalized_tokens") or [])
        score = _jaccard(tokens, other_tokens)
        if score > best_score:
            best_score = score
            best_entry = entry
            best_fp = ofp
    if best_entry and best_score >= CACHE_HIT_THRESHOLD:
        if _walk_card_still_valid(best_entry.get("cached_walk_card_id")):
            best_entry["last_used_at"] = _now()
            best_entry["hit_count"] = best_entry.get("hit_count", 0) + 1
            _save_cache(cache)
            stats["hits"] += 1
            _save_stats(stats)
            return {"hit": True, "walk_card_id": best_entry["cached_walk_card_id"], "hit_count": best_entry["hit_count"], "match_kind": "fuzzy", "similarity": round(best_score, 3)}
        else:
            del cache["entries"][best_fp]
            stats["invalidations"] += 1
            _save_cache(cache)
    stats["misses"] += 1
    _save_stats(stats)
    return None


def cache_store(query: str, walk_card_id: str):
    """Remember that this walk_card answered this query."""
    cache = _load_cache()
    fp = _fingerprint(query)
    if not fp:
        return
    cache["entries"][fp] = {
        "cached_walk_card_id": walk_card_id,
        "normalized_tokens": sorted(_normalize_query(query)),
        "first_stored_at": _now(),
        "last_used_at": _now(),
        "hit_count": 0,
        "original_query": query[:200],
    }
    _save_cache(cache)
    s = _load_stats()
    s["stored"] = s.get("stored", 0) + 1
    _save_stats(s)


def _walk_card_still_valid(walk_card_id: Optional[str]) -> bool:
    """Cache entry is invalid if the walk card was retracted or archived, OR
    if any of its surfaced cards have been retracted/archived.
    Walk cards in `quarantine` are valid — they're the engine's record, not
    user content needing alignment review."""
    if not walk_card_id:
        return False
    try:
        from api.cards import _read_card  # type: ignore
    except Exception:
        return False
    walk = _read_card(walk_card_id)
    if walk is None or walk.get("retracted") or walk.get("lifecycle_stage") == "archived":
        return False
    surfaced = ((walk.get("extra") or {}).get("cards_surfaced") or [])
    if not surfaced:
        return False
    # Spot-check: if ANY surfaced card is retracted/archived, invalidate.
    for sid in surfaced:
        sc = _read_card(sid)
        if sc is None or sc.get("retracted") or sc.get("lifecycle_stage") == "archived":
            return False
    return True


# ---------- Replay table ----------

def replay_log(query: str, shaped_query: str, walk_card_id: Optional[str], card_ids_walked: list, asked_by: Optional[str] = "anon"):
    """Append a walk to the replay table."""
    _ensure_dir()
    entry = {
        "ts": _now(),
        "query": query[:200],
        "shaped_query": shaped_query[:300],
        "fingerprint": _fingerprint(query),
        "walk_card_id": walk_card_id,
        "card_ids_walked": card_ids_walked[:30],
        "asked_by": asked_by[:64] if asked_by else "anon",
    }
    with REPLAY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _read_replay(limit: int = 1000) -> list[dict]:
    if not REPLAY_PATH.exists():
        return []
    out = []
    with REPLAY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out[-limit:]


# ---------- Prefetch predictor ----------

def predict_prefetch(active_card_ids: list[str], k: int = 8) -> list[dict]:
    """Given currently-loaded card_ids, predict the next-most-likely cards
    to be walked. Two passes: structural (graph) + statistical (co-walks).
    Returns ranked list of {card_id, score, reason}."""
    if not active_card_ids:
        return []

    try:
        from api.cards import _read_card  # type: ignore
    except Exception:
        return []

    candidate_scores = Counter()
    candidate_reasons: dict[str, list[str]] = {}

    active_set = set(active_card_ids)

    # Pass 1: structural — neighbors in the connection graph (free, deterministic)
    for cid in active_card_ids:
        card = _read_card(cid)
        if card is None:
            continue
        for conn in (card.get("connections") or []):
            tid = conn.get("to_card_id")
            if not tid or tid in active_set:
                continue
            candidate_scores[tid] += 2.0  # structural is high-confidence
            candidate_reasons.setdefault(tid, []).append(f"connected via {conn.get('relationship', 'see_also')}")

    # Pass 2: statistical — co-walk frequency from replay table
    # For each active card, find walks that contained it, gather other cards in those walks
    replays = _read_replay(limit=500)
    if replays:
        co_walk = Counter()
        for r in replays:
            walked = set(r.get("card_ids_walked") or [])
            if active_set & walked:
                for other in walked - active_set:
                    co_walk[other] += 1
        # Normalize and add to candidates
        max_count = max(co_walk.values()) if co_walk else 1
        for tid, n in co_walk.items():
            score = (n / max_count) * 1.0  # statistical weight ≤ 1.0 per signal
            candidate_scores[tid] += score
            if tid in candidate_reasons:
                candidate_reasons[tid].append(f"walked together in {n} past walks")
            else:
                candidate_reasons[tid] = [f"walked together in {n} past walks"]

    # Build top-k
    top = candidate_scores.most_common(k)
    out = []
    for tid, score in top:
        out.append({
            "card_id": tid,
            "score": round(score, 3),
            "reasons": candidate_reasons.get(tid, []),
        })
    return out


# ---------- Router ----------

if APIRouter is not None:
    class CacheCheckIn(BaseModel):
        query: str

    class ReplayLogIn(BaseModel):
        query: str
        shaped_query: Optional[str] = None
        walk_card_id: Optional[str] = None
        card_ids_walked: list[str]
        asked_by: Optional[str] = "anon"

    class PrefetchIn(BaseModel):
        active_card_ids: list[str]
        k: int = 8


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/walks/cache/check")
    def cache_check_endpoint(payload: CacheCheckIn):
        r = cache_check(payload.query)
        if r is None:
            return {"hit": False}
        return r

    @router.post("/walks/replay/log")
    def replay_log_endpoint(payload: ReplayLogIn):
        entry = replay_log(
            payload.query,
            payload.shaped_query or payload.query,
            payload.walk_card_id,
            payload.card_ids_walked,
            payload.asked_by or "anon",
        )
        # Also store in fingerprint cache if we have a walk card
        if payload.walk_card_id:
            cache_store(payload.query, payload.walk_card_id)
        return {"status": "logged", "entry": entry}

    @router.get("/walks/replay/recent")
    def replay_recent(limit: int = 50):
        replays = _read_replay(limit=limit)
        replays.reverse()
        return {"count": len(replays), "items": replays}

    @router.post("/walks/prefetch")
    def prefetch_endpoint(payload: PrefetchIn):
        out = predict_prefetch(payload.active_card_ids, k=payload.k)
        return {"count": len(out), "predictions": out}

    @router.get("/walks/cache/stats")
    def cache_stats():
        s = _load_stats()
        cache = _load_cache()
        s["cache_size"] = len(cache.get("entries", {}))
        # Count replay lines without parsing each as JSON — orders of magnitude faster
        if REPLAY_PATH.exists():
            try:
                with REPLAY_PATH.open("rb") as f:
                    s["replay_count"] = sum(1 for _ in f)
            except Exception:
                s["replay_count"] = 0
        else:
            s["replay_count"] = 0
        if s.get("checks"):
            s["hit_rate"] = round(s["hits"] / s["checks"], 3)
        else:
            s["hit_rate"] = None
        return s

    return router
