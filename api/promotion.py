"""promotion.py — Card promotion engine (LOOP 15).

The substrate self-organizes: cards rise and fall by signal. The operator
approves the loud transitions; everything quiet auto-updates.

Quality signals that drive promotion:
  paperclips_count   strongest signal that a card is useful
  helpful_count      thumbs-up
  cite_count         how many OTHER cards reference this one (citation graph)
  walks_through_count how often Shepherd surfaced it on a walk the user followed through
  flagged_count      concerns raised
  trust_weighted_score votes weighted by per-voter trust (computed)
  tip_total_usd      tips received (read but does NOT drive promotion — gratitude isn't a vote)

Lifecycle transitions:
  Quiet (auto, no approval):
    - private  -> shared       once shared with another household
    - shared   -> public_review on author request
    - public   -> fading       no walks-through in 90 days AND no recent paperclips
    - fading   -> archived     90 days fading
  Loud (operator approval queue):
    - quarantine -> private    promote from quarantine
    - public_review -> public  the alignment-gate moment
    - public -> featured       elevated as exemplar
    - any -> archived          if flagged or low quality
    - retract entirely

The operator NEVER deletes — only archives. Archived cards stay recoverable
for 90 days (per quarantine policy), then surface for hard-delete review.

Endpoints:
  POST  /cards/{id}/helpful              vote helpful
  POST  /cards/{id}/not-helpful          vote not helpful
  POST  /cards/{id}/flag                 raise a concern
  POST  /cards/{id}/cite                 declare this card cited (atomic counter)
  GET   /promotion/queue                 operator queue of cards needing decision
  POST  /promotion/approve               operator approves a queued transition
  POST  /promotion/reject                operator rejects a queued transition
  POST  /promotion/scan                  run the auto-fade/auto-archive sweep
  GET   /promotion/health                library-health summary
"""
from __future__ import annotations
import json
import re
import threading
import time
from datetime import datetime, timezone, timedelta
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
PROMOTION_QUEUE = REPO / "data" / "promotion_queue.json"
VOTES_LOG = REPO / "data" / "votes_log.jsonl"


# Module-scope health snapshot cache (was inside get_router closure).
# Two-layer invalidation: 10s TTL + dir-mtime check. Single-flight rebuild.
_HEALTH_CACHE: dict = {"snapshot": None, "dir_mtime": 0.0, "checked_at": 0.0}
# TTL = 30s, paired with the periodic warmer (api/app.py, 25s interval)
_HEALTH_TTL_SECONDS = 30.0
_HEALTH_REBUILD_LOCK = threading.Lock()


def _compute_health_snapshot() -> dict:
    """Walk all card files and compute library-health summary. Called only
    from cold-path inside _HEALTH_REBUILD_LOCK; takes ~5-10s at 11k cards."""
    if not CARDS_DIR.exists():
        return {"total_cards": 0}
    by_stage: dict = {}
    by_shelf: dict = {}
    flagged_cards = 0
    retracted_cards = 0
    total_metrics = {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0}
    n = 0
    for f in CARDS_DIR.glob("*.json"):
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        n += 1
        stage = card.get("lifecycle_stage", "?")
        by_stage[stage] = by_stage.get(stage, 0) + 1
        shelf = card.get("shelf", "?")
        by_shelf[shelf] = by_shelf.get(shelf, 0) + 1
        if (card.get("metrics") or {}).get("flagged_count", 0) > 0:
            flagged_cards += 1
        if card.get("retracted"):
            retracted_cards += 1
        for k in total_metrics:
            total_metrics[k] += (card.get("metrics") or {}).get(k, 0)
    return {
        "total_cards": n,
        "by_lifecycle_stage": by_stage,
        "by_shelf": by_shelf,
        "flagged_cards": flagged_cards,
        "retracted_cards": retracted_cards,
        "total_metrics": total_metrics,
    }


def _get_health_snapshot() -> dict:
    """Return cached health snapshot; rebuild on TTL expiry + dir-mtime change.
    Single-flight: only one thread rebuilds; others wait."""
    now = time.time()
    if _HEALTH_CACHE["snapshot"] is not None and (now - _HEALTH_CACHE["checked_at"]) < _HEALTH_TTL_SECONDS:
        return _HEALTH_CACHE["snapshot"]
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _HEALTH_CACHE["snapshot"] is not None and abs(dir_mtime - _HEALTH_CACHE["dir_mtime"]) < 1.0:
        _HEALTH_CACHE["checked_at"] = now
        return _HEALTH_CACHE["snapshot"]
    with _HEALTH_REBUILD_LOCK:
        # Re-check after acquiring lock
        now = time.time()
        if _HEALTH_CACHE["snapshot"] is not None and (now - _HEALTH_CACHE["checked_at"]) < _HEALTH_TTL_SECONDS:
            return _HEALTH_CACHE["snapshot"]
        _HEALTH_CACHE["snapshot"] = _compute_health_snapshot()
        _HEALTH_CACHE["dir_mtime"] = dir_mtime
        _HEALTH_CACHE["checked_at"] = time.time()
    return _HEALTH_CACHE["snapshot"]


def warm_cache():
    """Prime the promotion health snapshot."""
    try:
        snap = _get_health_snapshot()
        return {"warmed": True, "total_cards": snap.get("total_cards", 0)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}

# Thresholds (tunable; conservative for the first 1000 households)
FADE_DAYS_NO_WALKS = 90
ARCHIVE_DAYS_FADING = 90
SUGGEST_FEATURE_PAPERCLIPS = 25
SUGGEST_FEATURE_HELPFUL = 50
SUGGEST_FLAG_REVIEW = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _card_path(card_id: str) -> Path:
    return CARDS_DIR / f"{card_id}.json"


def _read_card(card_id: str) -> Optional[dict]:
    p = _card_path(card_id)
    if not p.exists():
        # Adapter fallback
        try:
            from api.cards import _all_cards_unified  # type: ignore
            return _all_cards_unified().get(card_id)
        except Exception:
            return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _persist_card(card: dict):
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    _card_path(card["id"]).write_text(json.dumps(card, indent=2), encoding="utf-8")
    try:
        from api.cards import working_set as _ws  # type: ignore
        _ws().put(card["id"], card)
    except Exception:
        pass


def _bump_metric(card_id: str, metric: str, delta: int = 1) -> Optional[dict]:
    card = _read_card(card_id)
    if card is None:
        return None
    m = card.get("metrics") or {}
    m[metric] = max(0, m.get(metric, 0) + delta)
    card["metrics"] = m
    card["updated_at"] = _now()
    _persist_card(card)
    return card


def _log_vote(card_id: str, vote: str, voter: str, reason: Optional[str] = None):
    VOTES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with VOTES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": _now(),
            "card_id": card_id,
            "vote": vote,
            "voter": voter[:32] if voter else "anon",
            "reason": (reason or "")[:300],
        }) + "\n")


def _load_queue() -> list:
    if not PROMOTION_QUEUE.exists():
        return []
    try:
        return json.loads(PROMOTION_QUEUE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(q: list):
    PROMOTION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    PROMOTION_QUEUE.write_text(json.dumps(q, indent=2), encoding="utf-8")


def _enqueue(card_id: str, suggested: str, reason: str):
    q = _load_queue()
    # Dedupe: skip if same card+suggested already pending
    for item in q:
        if item.get("card_id") == card_id and item.get("suggested") == suggested and item.get("status") == "pending":
            return
    q.append({
        "card_id": card_id,
        "suggested": suggested,
        "reason": reason,
        "created_at": _now(),
        "status": "pending",
    })
    _save_queue(q)


def _trust_weighted_score(metrics: dict) -> float:
    """Composite score driving promotion suggestions. Conservative for now;
    learned weights land when we have enough vote data."""
    paperclips = metrics.get("paperclips_count", 0)
    helpful = metrics.get("helpful_count", 0)
    not_helpful = metrics.get("not_helpful_count", 0)
    cites = metrics.get("cite_count", 0)
    walks = metrics.get("walks_through_count", 0)
    flagged = metrics.get("flagged_count", 0)
    # Weighted sum with diminishing returns on each signal
    import math
    score = (
        2.0 * math.log(paperclips + 1) +
        1.0 * math.log(helpful + 1) +
        2.5 * math.log(cites + 1) +
        0.5 * math.log(walks + 1) -
        1.5 * math.log(not_helpful + 1) -
        2.0 * math.log(flagged + 1)
    )
    return round(score, 3)


def _age_days(ts_str: str) -> float:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
    except Exception:
        return 0.0


# ---------- Auto-promotion scanner ----------

def scan_for_promotions() -> dict:
    """Walk every card, compute its trust-weighted score, queue suggestions
    for the operator. Quiet transitions apply automatically."""
    if not CARDS_DIR.exists():
        return {"scanned": 0, "queued": 0, "auto_faded": 0, "auto_unfaded": 0}
    scanned = 0
    queued = 0
    auto_faded = 0
    auto_unfaded = 0
    for f in CARDS_DIR.glob("*.json"):
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        scanned += 1
        m = card.get("metrics") or {}
        m["trust_weighted_score"] = _trust_weighted_score(m)
        card["metrics"] = m
        stage = card.get("lifecycle_stage", "quarantine")
        flagged = m.get("flagged_count", 0)
        paperclips = m.get("paperclips_count", 0)
        helpful = m.get("helpful_count", 0)
        walks = m.get("walks_through_count", 0)
        cid = card["id"]

        # 1. Auto-fade: public cards with no walks for 90 days AND no paperclips this period
        if stage == "public":
            updated_age = _age_days(card.get("updated_at") or card.get("created_at") or "")
            if updated_age > FADE_DAYS_NO_WALKS and walks == 0 and paperclips == 0:
                card["lifecycle_stage"] = "fading"
                card["updated_at"] = _now()
                _persist_card(card)
                auto_faded += 1
                continue

        # 2. Un-fade: fading cards that got new engagement
        if stage == "fading" and (walks > 0 or paperclips > 0):
            card["lifecycle_stage"] = "public"
            card["updated_at"] = _now()
            _persist_card(card)
            auto_unfaded += 1
            continue

        # 3. Suggest archive: fading for 90 days
        if stage == "fading":
            faded_age = _age_days(card.get("updated_at") or "")
            if faded_age > ARCHIVE_DAYS_FADING:
                _enqueue(cid, "archived", f"Fading for {faded_age:.0f} days; no engagement.")
                queued += 1
                continue

        # 4. Suggest featured: public card with strong metrics
        if stage == "public" and (paperclips >= SUGGEST_FEATURE_PAPERCLIPS or helpful >= SUGGEST_FEATURE_HELPFUL):
            _enqueue(cid, "featured", f"Strong signal: {paperclips} paperclips, {helpful} helpful.")
            queued += 1
            continue

        # 5. Suggest archived: flagged repeatedly
        if flagged >= SUGGEST_FLAG_REVIEW:
            _enqueue(cid, "archived", f"Flagged {flagged} times; operator review.")
            queued += 1
            continue

        # 6. Suggest public_review → public: card in public_review for >7 days
        if stage == "public_review":
            review_age = _age_days(card.get("updated_at") or "")
            if review_age > 7:
                _enqueue(cid, "public", f"In public_review for {review_age:.0f} days. Approve or send back.")
                queued += 1
                continue

        # 7. Persist updated metrics
        _persist_card(card)

    return {"scanned": scanned, "queued": queued, "auto_faded": auto_faded, "auto_unfaded": auto_unfaded}


# ---------- Request schemas ----------

if APIRouter is not None:
    class VoteIn(BaseModel):
        voter: Optional[str] = "anon"
        reason: Optional[str] = None

    class FlagIn(BaseModel):
        voter: Optional[str] = "anon"
        reason: str

    class QueueDecision(BaseModel):
        card_id: str
        suggested: str  # the suggested target stage
        operator_note: Optional[str] = None


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/cards/{card_id}/helpful")
    def vote_helpful(card_id: str, payload: VoteIn):
        card = _read_card(card_id)
        if card is None:
            raise HTTPException(404, "No such card")
        c = _bump_metric(card_id, "helpful_count", +1)
        _log_vote(card_id, "helpful", payload.voter or "anon")
        return {"status": "ok", "helpful_count": c["metrics"]["helpful_count"]}

    @router.post("/cards/{card_id}/not-helpful")
    def vote_not_helpful(card_id: str, payload: VoteIn):
        card = _read_card(card_id)
        if card is None:
            raise HTTPException(404, "No such card")
        c = _bump_metric(card_id, "not_helpful_count", +1)
        _log_vote(card_id, "not_helpful", payload.voter or "anon", payload.reason)
        return {"status": "ok", "not_helpful_count": c["metrics"]["not_helpful_count"]}

    @router.post("/cards/{card_id}/flag")
    def flag_card(card_id: str, payload: FlagIn):
        card = _read_card(card_id)
        if card is None:
            raise HTTPException(404, "No such card")
        if not payload.reason or len(payload.reason.strip()) < 5:
            raise HTTPException(400, "A reason is required for flags (min 5 chars).")
        c = _bump_metric(card_id, "flagged_count", +1)
        _log_vote(card_id, "flag", payload.voter or "anon", payload.reason)
        # Surface for operator immediately if flag threshold crossed
        if c and (c.get("metrics") or {}).get("flagged_count", 0) >= SUGGEST_FLAG_REVIEW:
            _enqueue(card_id, "archived", f"Flagged {c['metrics']['flagged_count']} times. Latest: {payload.reason[:120]}")
        return {"status": "ok", "flagged_count": c["metrics"]["flagged_count"]}

    @router.post("/cards/{card_id}/cite")
    def cite_card(card_id: str):
        """Atomic counter increment. Called by the system when a connection
        card is authored linking TO this card."""
        c = _bump_metric(card_id, "cite_count", +1)
        if c is None:
            raise HTTPException(404, "No such card")
        return {"status": "ok", "cite_count": c["metrics"]["cite_count"]}

    @router.get("/promotion/queue")
    def get_queue(status: Optional[str] = "pending"):
        q = _load_queue()
        if status:
            q = [i for i in q if i.get("status") == status]
        # Enrich with card titles
        out = []
        for item in q:
            c = _read_card(item["card_id"])
            out.append({
                **item,
                "card_title": (c or {}).get("title"),
                "card_current_stage": (c or {}).get("lifecycle_stage"),
                "card_metrics": (c or {}).get("metrics"),
            })
        # Newest first
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"count": len(out), "items": out}

    @router.post("/promotion/approve")
    def approve(payload: QueueDecision):
        q = _load_queue()
        found = None
        for item in q:
            if (item.get("card_id") == payload.card_id
                and item.get("suggested") == payload.suggested
                and item.get("status") == "pending"):
                found = item
                break
        if not found:
            raise HTTPException(404, "No matching pending queue item")
        # Apply the transition via cards.py promote logic by direct file write
        card = _read_card(payload.card_id)
        if card is None:
            raise HTTPException(404, "Card not found")
        prev = card.get("lifecycle_stage", "quarantine")
        card["lifecycle_stage"] = payload.suggested
        card["updated_at"] = _now()
        if payload.suggested == "featured":
            card["featured_at"] = card["updated_at"]
        if payload.suggested == "archived":
            card["archived_at"] = card["updated_at"]
        if payload.suggested in ("public", "featured"):
            card["visibility"] = "public"
        _persist_card(card)
        found["status"] = "approved"
        found["approved_at"] = _now()
        found["operator_note"] = (payload.operator_note or "")[:300]
        _save_queue(q)
        return {"status": "approved", "card_id": payload.card_id, "from": prev, "to": payload.suggested}

    @router.post("/promotion/reject")
    def reject(payload: QueueDecision):
        q = _load_queue()
        found = None
        for item in q:
            if (item.get("card_id") == payload.card_id
                and item.get("suggested") == payload.suggested
                and item.get("status") == "pending"):
                found = item
                break
        if not found:
            raise HTTPException(404, "No matching pending queue item")
        found["status"] = "rejected"
        found["rejected_at"] = _now()
        found["operator_note"] = (payload.operator_note or "")[:300]
        _save_queue(q)
        return {"status": "rejected", "card_id": payload.card_id, "suggested": payload.suggested}

    @router.post("/promotion/scan")
    def run_scan():
        return scan_for_promotions()

    @router.get("/promotion/health")
    def health():
        # Snapshot is module-scope so the startup warmer can prime it.
        # _get_health_snapshot() handles TTL + dir-mtime + single-flight.
        snapshot = _get_health_snapshot()
        # Queue count is always live (small file read)
        q = _load_queue()
        pending = sum(1 for i in q if i.get("status") == "pending")
        return {**snapshot, "pending_promotions": pending}

    return router
