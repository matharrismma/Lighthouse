"""Curriculum + Recipe submission endpoints. Mirrors api/user_content.py.

POST /intake/curriculum   — accept curriculum lesson submission
POST /intake/recipe       — accept recipe submission
GET  /intake/curriculum   — list (status filter optional)
GET  /intake/recipe       — list
POST /intake/curriculum/{sid}/approve  — operator
POST /intake/curriculum/{sid}/reject
POST /intake/recipe/{sid}/approve
POST /intake/recipe/{sid}/reject

Storage: data/user_submissions/<type>_<id>.json so all family submissions
sit in one searchable directory the operator can sweep.
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
SUB_DIR = REPO / "data" / "user_submissions"
SUB_DIR.mkdir(parents=True, exist_ok=True)


# Pydantic models at module scope so FastAPI's OpenAPI schema generation
# can introspect them. Defining them inside get_router() makes them
# ForwardRefs that openapi.json can't resolve (returns 500).
if APIRouter is not None:
    class CurriculumSubmission(BaseModel):
        title: str
        age_tier: str
        subject: str
        summary: str
        content: str
        minutes: int | str | None = None
        creator_name: str
        creator_email: str
        wallet_address: Optional[str] = None
        align_christian: Optional[str] = None
        align_family: Optional[str] = None
        align_factual: Optional[str] = None
        align_rights: Optional[str] = None
        align_review: Optional[str] = None
        source: Optional[str] = None
        submitted_at: Optional[str] = None
        status: Optional[str] = None

    class RecipeSubmission(BaseModel):
        title: str
        course: str
        yield_text: Optional[str] = None
        time_text: Optional[str] = None
        source: str
        ingredients: str
        method: str
        family_note: Optional[str] = None
        ingredients_list: Optional[list] = None
        method_steps: Optional[list] = None
        creator_name: str
        creator_email: str
        wallet_address: Optional[str] = None
        align_rights: Optional[str] = None
        align_safety: Optional[str] = None
        align_tested: Optional[str] = None
        align_review: Optional[str] = None
        source_type: Optional[str] = None
        submitted_at: Optional[str] = None
        status: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _save(rec: dict, kind: str) -> None:
    p = SUB_DIR / f"{kind}_{rec['id']}.json"
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")


def _load(sid: str, kind: str) -> dict | None:
    p = SUB_DIR / f"{kind}_{sid}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _list(kind: str, status: Optional[str]) -> list:
    out = []
    for f in sorted(SUB_DIR.glob(f"{kind}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and rec.get("status") != status:
            continue
        rec_redacted = dict(rec)
        rec_redacted.pop("creator_email", None)
        rec_redacted.pop("wallet_address", None)
        out.append(rec_redacted)
    return out


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    # ----- Curriculum --------------------------------------------------------

    @router.post("/intake/curriculum")
    def submit_curriculum(s: CurriculumSubmission, request: Request):
        sid = _gen_id("cur")
        rec = {
            "id": sid,
            "kind": "curriculum",
            "status": "quarantined",
            "submitted_at": s.submitted_at or _now(),
            **s.model_dump(),
        }
        _save(rec, "curriculum")
        return {"id": sid, "status": "quarantined",
                "message": "Submitted for operator review. We'll email within 2 weeks."}

    @router.get("/intake/curriculum")
    def list_curriculum(status: Optional[str] = Query(None)):
        return {"submissions": _list("curriculum", status)}

    @router.post("/intake/curriculum/{sid}/approve")
    def approve_curriculum(sid: str, body: dict = Body(default={})):
        rec = _load(sid, "curriculum")
        if not rec:
            raise HTTPException(404)
        rec["status"] = "approved"
        rec["approved_at"] = _now()
        rec["approver_note"] = body.get("note", "")
        _save(rec, "curriculum")
        return {"id": sid, "status": "approved"}

    @router.post("/intake/curriculum/{sid}/reject")
    def reject_curriculum(sid: str, body: dict = Body(default={})):
        rec = _load(sid, "curriculum")
        if not rec:
            raise HTTPException(404)
        rec["status"] = "rejected"
        rec["rejected_at"] = _now()
        rec["rejector_note"] = body.get("note", "")
        _save(rec, "curriculum")
        return {"id": sid, "status": "rejected"}

    # ----- Recipe -----------------------------------------------------------

    @router.post("/intake/recipe")
    def submit_recipe(s: RecipeSubmission, request: Request):
        sid = _gen_id("rec")
        rec = {
            "id": sid,
            "kind": "recipe",
            "status": "quarantined",
            "submitted_at": s.submitted_at or _now(),
            **s.model_dump(),
        }
        _save(rec, "recipe")
        return {"id": sid, "status": "quarantined",
                "message": "Submitted for operator review."}

    @router.get("/intake/recipe")
    def list_recipe(status: Optional[str] = Query(None)):
        return {"submissions": _list("recipe", status)}

    @router.post("/intake/recipe/{sid}/approve")
    def approve_recipe(sid: str, body: dict = Body(default={})):
        rec = _load(sid, "recipe")
        if not rec:
            raise HTTPException(404)
        rec["status"] = "approved"
        rec["approved_at"] = _now()
        rec["approver_note"] = body.get("note", "")
        _save(rec, "recipe")
        return {"id": sid, "status": "approved"}

    @router.post("/intake/recipe/{sid}/reject")
    def reject_recipe(sid: str, body: dict = Body(default={})):
        rec = _load(sid, "recipe")
        if not rec:
            raise HTTPException(404)
        rec["status"] = "rejected"
        rec["rejected_at"] = _now()
        rec["rejector_note"] = body.get("note", "")
        _save(rec, "recipe")
        return {"id": sid, "status": "rejected"}

    return router
