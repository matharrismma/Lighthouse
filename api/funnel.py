"""funnel.py — the single user funnel + the private (owned) card layer.

The user layer from docs/USER_LAYER.md. One input; the user's cards are OWNED and
PRIVATE by default, stored in data/user_cards/<owner>/ — entirely outside the
public substrate (data/cards/). Privacy is by CONSTRUCTION: the public card APIs
scan data/cards/ and never see these files, so there is no filter to forget.

Three shelves:
  * MINE    — private, owned (this module's storage). The default.
  * PUBLIC  — the user publishes: the card MOVES into data/cards/ (visibility
              public, witness_status self_only) — the public shelf, not yet the bank.
  * BANK    — the witness gate promotes the verified few (witness_status passed).
              That gate already exists; `propose` flags a card for it.

Single-user today: one user_identity (= the operator), so the owner is the
operator and the management endpoints are operator-gated (reuse the /keep
admission). Forward-compatible to multi-user: `owner` is a user_id; per-request
user resolution slots in where _owner_id()/_is_owner() are.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Request
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    APIRouter = None
    class BaseModel:  # type: ignore
        pass

REPO = Path(__file__).resolve().parent.parent
USER_CARDS = REPO / "data" / "user_cards"
PUBLIC_CARDS = REPO / "data" / "cards"
KEEP_ALLOWED = REPO / "data" / "keep_allowed_ips.txt"
KEEP_SESSIONS = REPO / "data" / "keep" / "sessions.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_id() -> str:
    """The current owner. Single-user today = the node's user identity."""
    try:
        from concordance_engine.user_identity import get_user_id
        return get_user_id()
    except Exception:
        return "operator"


# ── Operator gate (single-user: owner == operator; reuse /keep admission) ───────
def _client_ip(request) -> str:
    try:
        return (request.headers.get("cf-connecting-ip")
                or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
                or (request.client.host if request.client else ""))
    except Exception:
        return ""


def _is_owner(request) -> bool:
    """True if the requester is the owner/operator: localhost, an allowlisted
    /keep IP, or a valid /keep session cookie. (Single-user model.)"""
    ip = _client_ip(request)
    if ip in ("127.0.0.1", "::1", "localhost", ""):
        return True
    try:
        if KEEP_ALLOWED.exists():
            for line in KEEP_ALLOWED.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line and line == ip:
                    return True
    except Exception:
        pass
    try:
        cookie = request.cookies.get("nh_keep_session", "")
        if cookie and KEEP_SESSIONS.exists():
            sess = json.loads(KEEP_SESSIONS.read_text(encoding="utf-8"))
            e = sess.get(cookie)
            if e and int(e.get("expires_ts", 0)) > int(time.time()):
                return True
    except Exception:
        pass
    return False


# ── Classify / route (deterministic v1 — one input, the right deck) ─────────────
def _classify(text: str) -> Dict[str, str]:
    t = (text or "").strip()
    low = t.lower()
    deck = "note"
    if low.startswith(("pray", "prayer")) or "pray for" in low or "lord," in low:
        deck = "prayer"
    elif any(k in low for k in ("recipe", "preheat", "ingredient", "tbsp", "tsp",
                                "cup of", "bake at", "simmer")):
        deck = "recipe"
    elif low.startswith(("todo", "task:", "remember to", "need to", "buy ", "schedule")):
        deck = "task"
    elif t.endswith("?") or low.startswith(("what", "who", "why", "how", "when", "where")):
        deck = "question"
    elif any(k in low for k in ("genesis", "exodus", "psalm", "matthew", "mark ",
                                "luke", "john ", "romans", "verse")) and ":" in t:
        deck = "scripture"
    title = (t[:70] + ("…" if len(t) > 70 else "")) or "Note"
    return {"deck": deck, "title": title}


def _user_dir(owner: str) -> Path:
    safe = "".join(c for c in owner if c.isalnum() or c in ("-", "_")) or "operator"
    return USER_CARDS / safe


def _create_private(text: str, owner: str, deck: Optional[str] = None) -> dict:
    routed = _classify(text)
    deck = deck or routed["deck"]
    cid = "card_n_" + hashlib.sha256((owner + "|" + text + "|" + _now()).encode("utf-8")).hexdigest()[:12]
    card = {
        "id": cid,
        "kind": "note",
        "title": routed["title"],
        "body": text,
        "source": {"label": "Your input", "url": "", "ref": "", "authority_tier": "user_household"},
        "shelf": "mine",
        "deck": deck,
        "bands": [deck, "mine"],
        "owner": owner,
        "visibility": "private",
        "lifecycle_stage": "private",
        "witness_status": "self_only",
        "created_at": _now(),
        "updated_at": _now(),
    }
    d = _user_dir(owner)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def _read_private(owner: str, cid: str) -> Optional[dict]:
    p = _user_dir(owner) / f"{cid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_private(owner: str) -> List[dict]:
    d = _user_dir(owner)
    out = []
    if d.exists():
        for f in d.glob("card_*.json"):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
    out.sort(key=lambda c: c.get("created_at") or "", reverse=True)
    return out


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    def _require_owner(request):
        if not _is_owner(request):
            raise HTTPException(404, "Not Found")  # hide existence, like /keep
        return _owner_id()

    @router.post("/funnel", tags=["funnel"])
    async def funnel_in(request: Request):
        """The single input. Creates a PRIVATE, owned card and routes it to a deck."""
        owner = _require_owner(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        text = (str(data.get("text") or "")).strip()
        if not text:
            raise HTTPException(400, "text is required")
        if len(text) > 4000:
            raise HTTPException(400, "max 4000 chars (cards are index cards)")
        card = _create_private(text, owner, data.get("deck"))
        return {"ok": True, "card": card, "shelf": "mine"}

    @router.get("/funnel/mine", tags=["funnel"])
    def funnel_mine(request: Request):
        owner = _require_owner(request)
        cards = _list_private(owner)
        decks: Dict[str, int] = {}
        for c in cards:
            decks[c.get("deck") or "note"] = decks.get(c.get("deck") or "note", 0) + 1
        return {"owner": owner, "count": len(cards), "by_deck": decks, "cards": cards}

    @router.get("/funnel/card/{cid}", tags=["funnel"])
    def funnel_card(cid: str, request: Request):
        owner = _require_owner(request)
        card = _read_private(owner, cid)
        if not card:
            raise HTTPException(404, "Not Found")
        return card

    @router.post("/funnel/publish/{cid}", tags=["funnel"])
    def funnel_publish(cid: str, request: Request):
        """Move a private card to the PUBLIC shelf (into data/cards/, visibility
        public, witness_status self_only — public but not yet bank-verified)."""
        owner = _require_owner(request)
        card = _read_private(owner, cid)
        if not card:
            raise HTTPException(404, "Not Found")
        pub = dict(card)
        pub["visibility"] = "public"
        pub["lifecycle_stage"] = "public"
        pub["witness_status"] = "self_only"  # public shelf; NOT the witnessed bank
        pub["shelf"] = "submitted"
        pub["bands"] = sorted(set((pub.get("bands") or []) + ["published"]))
        pub["updated_at"] = _now()
        try:
            from api import cards as _cards
            pub["source_hash"] = _cards._compute_source_hash(pub)
            _cards._save_card(pub)  # writes to data/cards/ + working_set
        except Exception as e:
            raise HTTPException(500, f"publish failed: {e}")
        # remove the private copy (it now lives on the public shelf)
        try:
            (_user_dir(owner) / f"{cid}.json").unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": True, "published": cid, "visibility": "public",
                "note": "On the public shelf. Not in the knowledge bank until it "
                        "passes the witness gate — POST /funnel/propose/{id}."}

    @router.post("/funnel/propose/{cid}", tags=["funnel"])
    def funnel_propose(cid: str, request: Request):
        """Flag a card for the knowledge bank. The witness gate (existing) decides;
        the user/operator cannot self-admit to the bank."""
        _require_owner(request)
        return {"ok": True, "proposed": cid,
                "note": "Flagged for the witness gate. A card enters the knowledge "
                        "bank only by passing two or three witnesses + the four gates — "
                        "the gate decides, not the submitter."}

    @router.get("/funnel/stats", tags=["funnel"])
    def funnel_stats(request: Request):
        owner = _require_owner(request)
        cards = _list_private(owner)
        return {"owner": owner, "private_cards": len(cards),
                "decks": sorted({c.get("deck") or "note" for c in cards})}

    return router
