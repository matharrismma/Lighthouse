"""User-content intake + operator-review endpoints.

Stores submissions as one JSON file per submission under data/user_submissions/.
States: quarantined (submitted) → approved (added to primary pool) | rejected (archived).

Endpoints:
  POST /intake/user-content                  — accept a new submission
  GET  /intake/user-content?status=...       — list submissions, optionally filtered
  GET  /intake/user-content/<id>             — get one submission
  POST /intake/user-content/<id>/approve     — operator approves; adds to user_content_primary
  POST /intake/user-content/<id>/reject      — operator rejects; sets status=rejected
  POST /intake/user-content/<id>/vote        — community vote (up/down) — uses trust score

This is scaffolding. Heavy moderation work (file uploads, virus scanning,
content-type validation, distributed voting) is deferred. Operator approval
is the human gate that keeps the bar high.
"""
from __future__ import annotations
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Request, Query, Body
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore

REPO = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = REPO / "data" / "user_submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = REPO / "content" / "channels" / "narrow_highway.json"

VALID_STATUSES = {"quarantined", "approved", "rejected", "primary", "secondary", "cancelled"}
VALID_CATEGORIES = {"story", "music", "theater", "sports", "comedy", "other"}


# Pydantic models at module scope — when defined inside get_router(), FastAPI
# can't introspect them, the schema becomes a ForwardRef, and /openapi.json
# returns 500. Same fix as outreach.py and cards.py.
if APIRouter is not None:
    class Submission(BaseModel):
        title: str
        category: str
        description: str
        content_url: str
        creator_name: str
        creator_email: str
        align_family: Optional[str] = None
        align_christian: Optional[str] = None
        align_clean: Optional[str] = None
        align_rights: Optional[str] = None
        align_review: Optional[str] = None
        submitted_at: Optional[str] = None
        status: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return f"sub_{secrets.token_hex(6)}"


def _load(sid: str) -> dict | None:
    p = SUBMISSIONS_DIR / f"{sid}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _save(sub: dict) -> None:
    sid = sub["id"]
    (SUBMISSIONS_DIR / f"{sid}.json").write_text(
        json.dumps(sub, indent=2), encoding="utf-8"
    )


def _add_to_pool(sub: dict, pool_key: str = "user_content_primary") -> bool:
    """Insert a submission into the unified channel's pool."""
    if not MANIFEST_PATH.exists():
        return False
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pool = m.setdefault("content_pool", {}).setdefault(pool_key, [])
    item_id = f"user_{sub['id']}"
    if any(it.get("id") == item_id for it in pool):
        return True  # already there
    pool.append({
        "id": item_id,
        "title": sub.get("title", "Untitled"),
        "creator": sub.get("creator_name"),
        "category": sub.get("category"),
        "source_url": sub.get("content_url"),
        "submission_id": sub["id"],
        # No video/audio path yet — operator-curated rendering is a separate step.
        # When the operator ingests this content (downloads it, makes it uniform-MP4),
        # the path goes into D:/library_files/_channel_cache/narrow-highway/user_<sid>.mp4
        "video": f"D:/library_files/_channel_cache/narrow-highway/user_{sub['id']}.mp4",
    })
    MANIFEST_PATH.write_text(json.dumps(m, indent=2), encoding="utf-8")
    return True


def _remove_from_pools(sub_id: str):
    """Remove a submission's pool entry from all user_content pools."""
    if not MANIFEST_PATH.exists():
        return
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    item_id = f"user_{sub_id}"
    changed = False
    for k in ("user_content_primary", "user_content_secondary", "user_content_cancelled"):
        pool = m.get("content_pool", {}).get(k, [])
        new = [it for it in pool if it.get("id") != item_id]
        if len(new) != len(pool):
            m["content_pool"][k] = new
            changed = True
    if changed:
        MANIFEST_PATH.write_text(json.dumps(m, indent=2), encoding="utf-8")


# ----- Vote scoring (trust-weighted) -----

def _record_vote(sub: dict, direction: str, voter_id: str, trust: float = 1.0):
    """Append a vote to the submission record. Trust is 0..1; cry-wolf voters are weighted down."""
    sub.setdefault("votes", [])
    sub["votes"].append({
        "voter_id": voter_id,
        "direction": direction,  # 'up' or 'down'
        "trust": trust,
        "at": _now_iso(),
    })
    # Recompute trust-weighted score
    score = 0.0
    for v in sub["votes"]:
        sign = 1 if v["direction"] == "up" else -1
        score += sign * float(v.get("trust", 1.0))
    sub["score"] = score
    return score


# ----- FastAPI router -----

def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/intake/user-content")
    def submit(s: Submission, request: Request):
        if s.category not in VALID_CATEGORIES:
            raise HTTPException(400, f"category must be one of {sorted(VALID_CATEGORIES)}")
        sid = _gen_id()
        rec = {
            "id": sid,
            "status": "quarantined",
            "submitted_at": s.submitted_at or _now_iso(),
            "submitter_ip_prefix": (request.client.host or "").split(".")[0] if request.client else "?",
            **s.model_dump(),
        }
        _save(rec)
        return {"id": sid, "status": "quarantined",
                "message": "Submitted for operator review. We'll email you with the decision."}

    @router.get("/intake/user-content")
    def list_subs(status: Optional[str] = Query(None)):
        if status and status not in VALID_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")
        out = []
        for p in sorted(SUBMISSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if status and rec.get("status") != status:
                continue
            # Redact email in list view
            redacted = dict(rec)
            redacted.pop("creator_email", None)
            redacted.pop("submitter_ip_prefix", None)
            out.append(redacted)
        return {"submissions": out, "count": len(out)}

    @router.get("/intake/user-content/{sid}")
    def get_one(sid: str):
        rec = _load(sid)
        if not rec:
            raise HTTPException(404)
        rec_redacted = dict(rec)
        rec_redacted.pop("creator_email", None)
        return rec_redacted

    @router.post("/intake/user-content/{sid}/approve")
    def approve(sid: str, body: dict = Body(default={})):
        rec = _load(sid)
        if not rec:
            raise HTTPException(404)
        rec["status"] = "approved"
        rec["approved_at"] = _now_iso()
        rec["approver_note"] = body.get("note", "")
        _save(rec)
        _add_to_pool(rec, "user_content_primary")
        return {"id": sid, "status": "approved",
                "pool": "user_content_primary",
                "note": "Run tools/fast_channel_schedule.py to refresh today's schedule with this item."}

    @router.post("/intake/user-content/{sid}/reject")
    def reject(sid: str, body: dict = Body(default={})):
        rec = _load(sid)
        if not rec:
            raise HTTPException(404)
        rec["status"] = "rejected"
        rec["rejected_at"] = _now_iso()
        rec["rejector_note"] = body.get("note", "")
        _save(rec)
        _remove_from_pools(sid)
        return {"id": sid, "status": "rejected"}

    @router.post("/intake/user-content/{sid}/vote")
    def vote(sid: str, body: dict = Body(...)):
        rec = _load(sid)
        if not rec:
            raise HTTPException(404)
        direction = body.get("direction")
        voter_id = body.get("voter_id") or "anon"
        trust = float(body.get("trust", 1.0))
        if direction not in ("up", "down"):
            raise HTTPException(400, "direction must be 'up' or 'down'")
        score = _record_vote(rec, direction, voter_id, trust)
        _save(rec)
        return {"id": sid, "score": score, "vote_count": len(rec["votes"])}

    return router
