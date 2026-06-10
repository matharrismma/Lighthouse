"""notes.py — Community Notes with bridge rating (LOOP 18).

A community note annotates another card without overwriting it. The original
card always remains untouched. Notes appear underneath as a "Balance" section,
visible by click.

Bridge rating (the only kind that surfaces):

  A note becomes a Balance note only when raters from at least TWO different
  traditions have rated it helpful. Majority within one tradition is never
  enough. This makes balance structural, not editorial — a note can't surface
  by stacking the deck.

Tradition vectors (households self-declare, none required):
  reformed_baptist · presbyterian · lutheran · anglican
  catholic · orthodox · methodist · pentecostal · anabaptist
  unspecified (default; not a tradition for bridging purposes)

Phase 1 threshold: a note surfaces when at least 2 distinct named traditions
each have at least 1 helpful_vote on the note. Phase 2 will weight by rater
pool sizes (Birdwatch-style bridge score).

Endpoints:
  POST /notes                           author a note on a card
  GET  /notes/by_card/{card_id}         all notes (including unsurfaced) for a card
  GET  /notes/by_card/{card_id}/balance only surfaced balance notes
  POST /notes/{note_id}/rate            rater says helpful / not_helpful, with their tradition
  POST /notes/{note_id}/flag            raise concern
"""
from __future__ import annotations
import json
import re
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

NAMED_TRADITIONS = {
    "reformed_baptist", "presbyterian", "lutheran", "anglican",
    "catholic", "orthodox", "methodist", "pentecostal", "anabaptist",
    "non_denominational", "reformed_other",
}

# A note surfaces as Balance when this many distinct named traditions rate helpful
BRIDGE_THRESHOLD = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _card_path(cid: str) -> Path:
    return CARDS_DIR / f"{cid}.json"


def _read_card(cid: str) -> Optional[dict]:
    p = _card_path(cid)
    if not p.exists():
        try:
            from api.cards import _all_cards_unified  # type: ignore
            return _all_cards_unified().get(cid)
        except Exception:
            return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _persist_card(card: dict):
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    _card_path(card["id"]).write_text(json.dumps(card, indent=2), encoding="utf-8")


def _all_notes_for(card_id: str) -> list[dict]:
    """Walk all cards and return community_notes annotating the target."""
    if not CARDS_DIR.exists():
        return []
    out = []
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("kind") == "community_note" and (c.get("extra") or {}).get("card_id_annotated") == card_id:
            out.append(c)
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out


def _recompute_bridge_score(note: dict) -> tuple[float, bool]:
    """Returns (bridge_score, surfaced_as_balance).

    Phase 1: count distinct named traditions that rated this note helpful.
    Surface when count >= BRIDGE_THRESHOLD.
    bridge_score is normalized to [0, 1] based on tradition coverage.
    """
    votes = (note.get("extra") or {}).get("votes_by_tradition") or {}
    named_helpful = [t for t, n in votes.items() if t in NAMED_TRADITIONS and n > 0]
    distinct = len(set(named_helpful))
    score = min(1.0, distinct / max(BRIDGE_THRESHOLD, 1))
    return round(score, 3), distinct >= BRIDGE_THRESHOLD


if APIRouter is not None:
    class NoteIn(BaseModel):
        card_id: str  # the card being annotated
        body: str
        author: str  # household_id or 'matt'
        tradition: Optional[str] = None  # author's tradition (used for self-vote)
        source_label: Optional[str] = None
        source_url: Optional[str] = None
        source_ref: Optional[str] = None

    class RateIn(BaseModel):
        vote: str  # 'helpful' | 'not_helpful'
        rater_tradition: Optional[str] = None  # the rater's self-declared tradition
        rater: Optional[str] = "anon"


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/notes")
    def author_note(payload: NoteIn):
        if not _read_card(payload.card_id):
            raise HTTPException(404, "Card being annotated not found")
        if len(payload.body.strip()) < 10:
            raise HTTPException(400, "A community note needs at least 10 chars of body.")
        try:
            from api.cards import _make_card_id, _compute_source_hash, _save_card  # type: ignore
        except Exception:
            raise HTTPException(500, "Cards module unavailable")
        seed = f"note::{payload.card_id}::{payload.author}::{payload.body[:50]}::{_now()[:13]}"
        nid = _make_card_id("community_note", seed)
        # Author seeds the votes_by_tradition with their own (if declared)
        votes = {}
        if payload.tradition and payload.tradition in NAMED_TRADITIONS:
            votes[payload.tradition] = 1
        note = {
            "id": nid,
            "kind": "community_note",
            "title": f"Note on: {_read_card(payload.card_id).get('title','?')[:60]}",
            "body": payload.body[:4000],
            "source": {
                "label": payload.source_label or f"Community note by {payload.author}",
                "url": payload.source_url or "",
                "ref": payload.source_ref or "",
                "authority_tier": "matt" if payload.author == "matt" else "user_household",
            },
            "shelf": "notes",
            "box": "community",
            "bands": ["community_note", payload.tradition or "unspecified"],
            "connections": [{"to_card_id": payload.card_id, "relationship": "see_also"}],
            "author": payload.author,
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "public",
            "lifecycle_stage": "public",
            "volatility": "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 1 if votes else 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "extra": {
                "card_id_annotated": payload.card_id,
                "votes_by_tradition": votes,
                "bridge_score": 0.0,
                "surfaced_as_balance": False,
            },
        }
        note["source_hash"] = _compute_source_hash(note)
        _save_card(note)
        return {"status": "authored", "card_id": nid, "note_count_on_card": len(_all_notes_for(payload.card_id))}

    @router.get("/notes/by_card/{card_id}")
    def by_card(card_id: str):
        notes = _all_notes_for(card_id)
        out = []
        for n in notes:
            ex = n.get("extra") or {}
            out.append({
                "note_id": n.get("id"),
                "body": n.get("body"),
                "author": n.get("author"),
                "created_at": n.get("created_at"),
                "votes_by_tradition": ex.get("votes_by_tradition") or {},
                "bridge_score": ex.get("bridge_score") or 0.0,
                "surfaced_as_balance": ex.get("surfaced_as_balance") or False,
                "metrics": n.get("metrics") or {},
            })
        return {"card_id": card_id, "count": len(out), "notes": out}

    @router.get("/notes/by_card/{card_id}/balance")
    def by_card_balance(card_id: str):
        notes = _all_notes_for(card_id)
        out = []
        for n in notes:
            ex = n.get("extra") or {}
            if not ex.get("surfaced_as_balance"):
                continue
            out.append({
                "note_id": n.get("id"),
                "body": n.get("body"),
                "author": n.get("author"),
                "created_at": n.get("created_at"),
                "bridge_score": ex.get("bridge_score") or 0.0,
                "traditions_agreeing": [t for t, v in (ex.get("votes_by_tradition") or {}).items() if v > 0 and t in NAMED_TRADITIONS],
            })
        return {"card_id": card_id, "count": len(out), "balance_notes": out}

    @router.post("/notes/{note_id}/rate")
    def rate_note(note_id: str, payload: RateIn):
        if payload.vote not in ("helpful", "not_helpful"):
            raise HTTPException(400, "vote must be 'helpful' or 'not_helpful'")
        note = _read_card(note_id)
        if note is None or note.get("kind") != "community_note":
            raise HTTPException(404, "Note not found")
        ex = note.get("extra") or {}
        votes = ex.get("votes_by_tradition") or {}
        tradition = payload.rater_tradition if payload.rater_tradition in NAMED_TRADITIONS else "unspecified"
        if payload.vote == "helpful":
            votes[tradition] = votes.get(tradition, 0) + 1
            m = note.get("metrics") or {}
            m["helpful_count"] = m.get("helpful_count", 0) + 1
            note["metrics"] = m
        else:
            m = note.get("metrics") or {}
            m["not_helpful_count"] = m.get("not_helpful_count", 0) + 1
            note["metrics"] = m
        ex["votes_by_tradition"] = votes
        bs, surfaced = _recompute_bridge_score({"extra": ex})
        ex["bridge_score"] = bs
        ex["surfaced_as_balance"] = surfaced
        note["extra"] = ex
        note["updated_at"] = _now()
        _persist_card(note)
        return {
            "status": "rated",
            "note_id": note_id,
            "bridge_score": bs,
            "surfaced_as_balance": surfaced,
            "distinct_traditions_agreeing": sum(1 for t, v in votes.items() if t in NAMED_TRADITIONS and v > 0),
        }

    @router.post("/notes/{note_id}/flag")
    def flag_note(note_id: str, body: dict):
        reason = (body.get("reason") or "").strip()
        if len(reason) < 5:
            raise HTTPException(400, "reason required (min 5 chars)")
        note = _read_card(note_id)
        if note is None or note.get("kind") != "community_note":
            raise HTTPException(404, "Note not found")
        m = note.get("metrics") or {}
        m["flagged_count"] = m.get("flagged_count", 0) + 1
        note["metrics"] = m
        note["updated_at"] = _now()
        _persist_card(note)
        return {"status": "flagged", "flagged_count": m["flagged_count"]}

    return router
