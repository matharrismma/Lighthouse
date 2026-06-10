"""
The question ladder — never a dead-end (Matt 2026-06-10, the never-no-answer rule).

When the well holds no card that genuinely weighs a real question, we do NOT
shrug. The question is captured here as a TICKET and the ladder runs:
  answer -> research -> Shepherd asks + craft together -> ticket (community)
  -> Matt as LAST resort -> the answer is returned to the asker AND captured
  as a card (the wisdom flywheel). See project_wisdom_flywheel_2026-06-10.

ARCHITECTURE NOTE (the unified picture, project_unified_picture_2026-06-10):
an OPEN ticket is intake sitting in the AIRLOCK — a real question we don't yet
have a verified card for. When it is answered, the answer ELEVATES into the card
substrate (verified -> a card -> rises by verification + use). So this store is
the airlock for questions; the card substrate is the destination. It is
deliberately a small JSONL queue (like build_queue / almanac_proposals /
testimony), not a parallel knowledge store.

DEMAND IS FRUIT (project_mapping_reality_2026-06-10): a repeatedly-asked
question bumps `also_asked` instead of duplicating — demand is a truth/priority
signal, so the operator works the most-asked gaps first.

Writes are lock-guarded + atomic (temp + os.replace) so concurrent appends and
operator status-changes never tear the file (heeds the scale-readiness audit,
project_scale_bottlenecks_2026-06-10).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_TICKETS_DIR = Path(__file__).parent.parent / "data" / "tickets"
_QUEUE_PATH = _TICKETS_DIR / "queue.jsonl"
_LOCK = threading.Lock()

# research -> community -> matt : Matt is the LAST resort, never the first.
STATUSES = ("open", "researching", "answered", "closed")
TIERS = ("research", "community", "matt")
_MAX_Q = 2000
_MAX_E = 8000


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_all() -> List[Dict[str, Any]]:
    if not _QUEUE_PATH.exists():
        return []
    out: List[Dict[str, Any]] = []
    for ln in _QUEUE_PATH.read_text("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _atomic_write(rows: List[Dict[str, Any]]) -> None:
    _TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _QUEUE_PATH.with_suffix(".tmp")
    content = "".join(
        json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows
    )
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(_QUEUE_PATH)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _norm(q: str) -> str:
    return " ".join((q or "").lower().split())


def create_ticket(question: str, elaboration: str = "", source: str = "",
                  asked_by: str = "", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Capture a real question we can't yet answer. Returns the ticket.

    If an OPEN ticket with the same normalized question already exists we do NOT
    duplicate — we bump its `also_asked` count (demand = a priority signal) and
    return it. This keeps the store clean and surfaces the most-wanted answers.
    """
    question = (question or "").strip()[:_MAX_Q]
    if not question:
        raise ValueError("empty question")
    elaboration = (elaboration or "").strip()[:_MAX_E]
    nq = _norm(question)
    with _LOCK:
        rows = _read_all()
        for r in rows:
            if r.get("status") == "open" and _norm(r.get("question", "")) == nq:
                r["also_asked"] = int(r.get("also_asked", 0)) + 1
                r["updated_at"] = _now()
                if elaboration and not r.get("elaboration"):
                    r["elaboration"] = elaboration
                _atomic_write(rows)
                return r
        tk = {
            "id": "tk_" + uuid.uuid4().hex[:12],
            "question": question,
            "elaboration": elaboration,
            "source": (source or "")[:120],
            "asked_by": (asked_by or "anon")[:24],
            "status": "open",
            "tier": "research",
            "also_asked": 0,
            "answer": None,
            "answered_by": None,
            "answer_card_id": None,
            "context": context or {},
            "created_at": _now(),
            "updated_at": _now(),
        }
        rows.append(tk)
        _atomic_write(rows)
        return tk


def list_tickets(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    rows = _read_all()
    if status:
        rows = [r for r in rows if str(r.get("status", "")).lower() == status.lower()]
    # Most-asked first, then most-recently-touched: the operator works the
    # highest-demand gaps first (demand = fruit).
    rows.sort(key=lambda r: (int(r.get("also_asked", 0)), r.get("updated_at", "")),
              reverse=True)
    return rows[:max(1, min(500, limit))]


def get_ticket(tid: str) -> Optional[Dict[str, Any]]:
    for r in _read_all():
        if r.get("id") == tid:
            return r
    return None


def resolve_ticket(tid: str, answer: str = "", answered_by: str = "matt",
                   status: str = "answered",
                   answer_card_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Operator: attach an answer + advance status. Atomic rewrite.

    Does NOT itself create a card — capturing the resolved answer as a card (the
    flywheel) is the next ladder rung; resolve leaves `answer_card_id` as a clean
    hook for it. Returns the updated ticket, or None if the id isn't found.
    """
    if status not in STATUSES:
        status = "answered"
    with _LOCK:
        rows = _read_all()
        hit = None
        for r in rows:
            if r.get("id") == tid:
                if answer:
                    r["answer"] = answer.strip()[:_MAX_E]
                r["answered_by"] = (answered_by or "matt")[:40]
                r["status"] = status
                if answer_card_id:
                    r["answer_card_id"] = answer_card_id
                r["updated_at"] = _now()
                hit = r
                break
        if hit is None:
            return None
        _atomic_write(rows)
        return hit


def set_tier(tid: str, tier: str) -> Optional[Dict[str, Any]]:
    """Operator: escalate a ticket research -> community -> matt (last resort)."""
    if tier not in TIERS:
        return None
    with _LOCK:
        rows = _read_all()
        hit = None
        for r in rows:
            if r.get("id") == tid:
                r["tier"] = tier
                r["updated_at"] = _now()
                hit = r
                break
        if hit is None:
            return None
        _atomic_write(rows)
        return hit


def stats() -> Dict[str, Any]:
    rows = _read_all()
    by_status: Dict[str, int] = {}
    by_tier: Dict[str, int] = {}
    for r in rows:
        s = str(r.get("status", "open")).lower()
        by_status[s] = by_status.get(s, 0) + 1
        t = str(r.get("tier", "research")).lower()
        by_tier[t] = by_tier.get(t, 0) + 1
    return {"total": len(rows), "open": by_status.get("open", 0),
            "by_status": by_status, "by_tier": by_tier}
