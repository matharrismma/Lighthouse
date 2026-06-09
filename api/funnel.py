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

try:
    from api import offices as _offices
except Exception:  # pragma: no cover
    import offices as _offices  # type: ignore

try:
    from api import coach_journal as _coach_journal
except Exception:  # pragma: no cover
    import coach_journal as _coach_journal  # type: ignore

REPO = Path(__file__).resolve().parent.parent
USER_CARDS = REPO / "data" / "user_cards"
PUBLIC_CARDS = REPO / "data" / "cards"

# Where each Shepherd-routed tool lives (only pages that exist; else the walk).
_TOOL_URL = {
    "walk": "/walk.html",
    "discern": "/walk.html",
    "verify": "/poly.html",
    "teach": "/learn.html",
    "scripture": "/walk.html",
    "draft": "/scribe.html",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Person identity (capability model — like the keep token; no passwords) ──────
# The canonical resolution lives in api/person_identity.py so EVERY surface (this
# funnel + the four-gates walk) resolves the same person. A household id
# (NHHousehold) is 64-bit crypto-random: possession IS the key. Each household
# gets its own private shelf + its own Shepherd; the operator (localhost / keep)
# is one such person and wins when present. This is what makes the Shepherd
# per-user. The `_`-aliases keep the rest of this module unchanged.
try:
    from api import person_identity as _pid
except Exception:  # pragma: no cover
    import person_identity as _pid  # type: ignore

_owner_id = _pid.owner_id
_is_owner = _pid.is_owner
_household_id = _pid.household_id
_person_id = _pid.person_id


def _recall_walk(person: str, situation: str):
    """The Shepherd's memory spans surfaces. Gather this person's prior four-gates
    WALKS (coach_journal, across every walk identity linked to them) and surface the
    one that most resonates with what they bring now — so the funnel can say 'you
    walked something like this before; here is what the gates showed you.' Reuses
    the same deterministic overlap as card recall. Best-effort; None when nothing
    resonates."""
    try:
        vids = _pid.visitors_for(person)
    except Exception:
        vids = []
    if not vids:
        return None
    shaped, by_id = [], {}
    for vid in vids:
        try:
            walks = _coach_journal.list_walks(vid, limit=50)
        except Exception:
            walks = []
        for w in walks:
            wid = w.get("walk_id")
            if not wid or wid in by_id:
                continue
            gates = w.get("gates") or {}
            ts = w.get("updated_at") or w.get("created_at")
            when = ""
            if isinstance(ts, (int, float)):
                try:
                    when = datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    when = ""
            shaped.append({
                "id": wid,
                "title": w.get("situation") or "",
                "body": (w.get("situation") or "") + " " + " ".join(str(v) for v in gates.values()),
                "created_at": when,
            })
            by_id[wid] = w
    if not shaped:
        return None
    wr = _offices.recall_connection(situation, shaped)
    if not wr:
        return None
    w = by_id.get(wr.get("id")) or {}
    gates = w.get("gates") or {}
    # the gate answers are the fruit of that walk — surface a couple beside the recall
    wr["situation"] = w.get("situation") or wr.get("title") or ""
    wr["gates"] = {k: v for k, v in gates.items() if str(v).strip()}
    wr["answered"] = w.get("answered_count") or len(wr["gates"])
    return wr


# ── Title (the deck + routing now come from the Shepherd, in api/offices.py) ─────
def _title(text: str) -> str:
    t = (text or "").strip()
    return (t[:70] + ("…" if len(t) > 70 else "")) or "Note"


def _user_dir(owner: str) -> Path:
    safe = "".join(c for c in owner if c.isalnum() or c in ("-", "_")) or "operator"
    return USER_CARDS / safe


def _create_private(text: str, owner: str, deck: Optional[str] = None,
                    shep: Optional[dict] = None, patterns: Optional[list] = None) -> dict:
    """Create a private, owned card. The Shepherd (offices.shepherd_route) decides
    the deck and whether to suggest a tool; an explicit `deck` override wins.
    `patterns` = the floor's candidate-pattern ids for this share, kept on the card
    so the Shepherd can see recurrence over time (the thread you keep returning to)."""
    shep = shep or _offices.shepherd_route(text)
    deck = deck or shep.get("deck") or "note"
    cid = "card_n_" + hashlib.sha256((owner + "|" + text + "|" + _now()).encode("utf-8")).hexdigest()[:12]
    card = {
        "id": cid,
        "kind": "note",
        "title": _title(text),
        "body": text,
        "source": {"label": "Your input", "url": "", "ref": "", "authority_tier": "user_household"},
        "shelf": "mine",
        "deck": deck,
        "bands": [deck, "mine"],
        "owner": owner,
        "visibility": "private",
        "lifecycle_stage": "private",
        "witness_status": "self_only",
        # the Shepherd's discernment, kept on the card so the shelf can show it
        "shepherd": {"action": shep.get("action"), "say": shep.get("say", ""),
                     "tool": shep.get("tool"), "via": shep.get("via")},
        "patterns": list(patterns or []),
        "created_at": _now(),
        "updated_at": _now(),
    }
    if shep.get("action") == "route" and shep.get("tool"):
        card["routed_to"] = shep["tool"]
    d = _user_dir(owner)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def _read_any(owner: str, cid: str) -> Optional[dict]:
    """A card from the private shelf, or — if already published — from the public
    substrate. (propose can run before or after publish.)"""
    card = _read_private(owner, cid)
    if card:
        return card
    p = PUBLIC_CARDS / f"{cid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


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
        # OPERATOR only — for substrate-affecting actions (publish, propose, retrain).
        if not _is_owner(request):
            raise HTTPException(404, "Not Found")  # hide existence, like /keep
        return _owner_id()

    def _require_person(request):
        # the PERSON (household capability id, or the operator) — for their OWN
        # private shelf + their Shepherd. This is what makes the funnel multi-user.
        pid = _person_id(request)
        if not pid:
            raise HTTPException(404, "Not Found")  # hide existence
        return pid

    def _history_from(data):
        """Build the conversation history from the request. Accepts a running
        thread `messages: [{role,content}]` (the Socratic exchange) or a single
        `text` (a fresh deposit). Bounded for safety."""
        msgs = data.get("messages")
        if isinstance(msgs, list) and msgs:
            hist = []
            for m in msgs[-12:]:  # bound the thread
                role = "assistant" if m.get("role") == "assistant" else "user"
                content = str(m.get("content") or "").strip()[:4000]
                if content:
                    hist.append({"role": role, "content": content})
            return hist
        text = (str(data.get("text") or "")).strip()
        if not text:
            raise HTTPException(400, "text is required")
        if len(text) > 4000:
            raise HTTPException(400, "max 4000 chars (cards are index cards)")
        return [{"role": "user", "content": text}]

    @router.post("/funnel", tags=["funnel"])
    async def funnel_in(request: Request):
        """The ONE front door, now conversational. Every input runs through the
        three offices: the SHEPHERD discerns through its full learning stack
        (keep · office-model · Steward-gated oracle · keyword floor) and may ask
        ONE Socratic question to clarify intent; the STEWARD gates + records any
        oracle spend; on resolution the card is kept on your private shelf and,
        if routed, the proper tool is offered. The Shepherd asking is what lets
        deposit.html retire — this door now carries the conversation."""
        owner = _require_person(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        history = _history_from(data)

        # Oracle is ON here (Steward-gated): this is the one door, so it must be
        # able to ask. Tier 0 (keep) catches quick captures for free; the oracle
        # only fires for genuinely ambiguous, non-capture input, and the Steward
        # caps the spend. Each call also trains the local model -> it shrinks.
        shep = _offices.shepherd_discern(history, allow_keep=True, allow_oracle=True)
        steward = _offices.steward_check(shep.get("tool", ""))
        _offices.log_office_pair("steward", json.dumps({"tool": shep.get("tool"),
                                                        "action": shep.get("action")}),
                                 json.dumps(steward, ensure_ascii=False))

        # ASK — hold the thread, no card yet. The browser shows the question and
        # POSTs back the extended `messages`.
        if shep.get("action") == "ask":
            new_history = history + [{"role": "assistant", "content": shep.get("say", "")}]
            return {"ok": True, "status": "asking", "say": shep.get("say", ""),
                    "messages": new_history,
                    "steward": {"budget_remaining_usd": steward["budget_remaining_usd"]}}

        # KEEP / ROUTE — resolve. The card body is the ORIGINAL intent (first
        # user turn), even after a clarifying exchange.
        original = next((m["content"] for m in history if m["role"] == "user"),
                        history[-1]["content"] if history else "")

        # The narrowing (rung 2) — computed FIRST so the card carries its candidate
        # patterns (the Shepherd reads them later to see recurrence). Offered for ANY
        # capture the floor recognizes a pattern for; self-gating (notes/recipes won't
        # trigger it). The card is kept regardless; wisdom is offered beside it.
        nz, patterns = None, []
        try:
            nz = _offices.narrow(original)
            patterns = [c.get("id") for c in (nz.get("cards") or nz.get("choices") or []) if c.get("id")]
        except Exception:
            nz = None

        card = _create_private(original, owner, data.get("deck"), shep, patterns=patterns)

        resp = {"ok": True, "status": shep.get("action"), "card": card, "shelf": "mine",
                "shepherd": {"action": shep.get("action"), "say": shep.get("say", ""),
                             "tool": shep.get("tool")},
                "steward": {"budget_remaining_usd": steward["budget_remaining_usd"]}}
        if shep.get("action") == "route" and shep.get("tool"):
            resp["route"] = {"tool": shep["tool"],
                             "query": shep.get("query", original),
                             "url": _TOOL_URL.get(shep["tool"], "/walk.html")}
        if nz and (nz.get("narrowable") or nz.get("arrived")):
            resp["narrow"] = nz
            resp["query"] = original

        # The Shepherd never forgets, and his memory spans every surface.
        # (1) recall a prior CARD share that resonates; (2) see RECURRENCE — a
        # pattern you keep returning to (the unseen thread); (3) recall a prior
        # WALK (four-gates) that resonates — connecting the funnel to what the
        # gates already showed you elsewhere.
        try:
            prior = [c for c in _list_private(owner) if c.get("id") != card.get("id")]
            rc = _offices.recall_connection(original, prior)
            if rc:
                resp["recall"] = rc
            rec = _offices.recall_recurrence(patterns, prior)
            if rec:
                rec["name"] = next((c.get("name") for c in (nz.get("cards") or nz.get("choices") or [])
                                    if c.get("id") == rec["pattern_id"]), rec["pattern_id"]) if nz else rec["pattern_id"]
                resp["recurring"] = rec
            wr = _recall_walk(owner, original)
            if wr:
                resp["recall_walk"] = wr
        except Exception:
            pass
        return resp

    @router.get("/funnel/mine", tags=["funnel"])
    def funnel_mine(request: Request):
        owner = _require_person(request)
        cards = _list_private(owner)
        decks: Dict[str, int] = {}
        for c in cards:
            decks[c.get("deck") or "note"] = decks.get(c.get("deck") or "note", 0) + 1
        # publish/propose touch the SHARED substrate, so they stay operator-only
        # (anti-spam, privacy). Households keep + walk their private shelf; only
        # the operator can promote a card outward. The UI hides the buttons unless
        # this is true, so households don't see actions that would 404 on them.
        return {"owner": owner, "count": len(cards), "by_deck": decks, "cards": cards,
                "can_publish": _is_owner(request)}

    @router.get("/funnel/card/{cid}", tags=["funnel"])
    def funnel_card(cid: str, request: Request):
        owner = _require_person(request)
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
        # the Scribe records the publication (training pair)
        _offices.log_office_pair("scribe", str(card.get("body", ""))[:2000],
                                 json.dumps({"published": cid, "shelf": "public"},
                                            ensure_ascii=False))
        return {"ok": True, "published": cid, "visibility": "public",
                "note": "On the public shelf. Not in the knowledge bank until it "
                        "passes the witness gate — POST /funnel/propose/{id}."}

    @router.post("/funnel/propose/{cid}", tags=["funnel"])
    def funnel_propose(cid: str, request: Request):
        """Send a card to the knowledge bank — via the SCRIBE. The Scribe records
        it into the same intake queue the witness gate reads; the gate (two or
        three witnesses + the four gates) decides admission, never the submitter."""
        owner = _require_owner(request)
        card = _read_any(owner, cid)
        if not card:
            raise HTTPException(404, "Not Found")
        body = str(card.get("body") or card.get("text") or "").strip()
        if not body:
            raise HTTPException(400, "card has no text to propose")
        try:
            receipt = _offices.scribe_submit(text=body, title=str(card.get("title") or ""),
                                             visitor_id=owner)
        except Exception as e:
            raise HTTPException(500, f"propose failed: {e}")
        _offices.log_office_pair("scribe", body[:2000],
                                 json.dumps({"proposed": cid, "intake_id": receipt.get("id")},
                                            ensure_ascii=False))
        return {"ok": True, "proposed": cid, "scribe": receipt,
                "note": "The Scribe has recorded it. A card enters the knowledge "
                        "bank only by passing two or three witnesses + the four "
                        "gates — the gate decides, not the submitter."}

    @router.get("/funnel/stats", tags=["funnel"])
    def funnel_stats(request: Request):
        owner = _require_person(request)
        cards = _list_private(owner)
        return {"owner": owner, "private_cards": len(cards),
                "decks": sorted({c.get("deck") or "note" for c in cards})}

    @router.post("/offices/retrain", tags=["funnel"])
    def offices_retrain(request: Request):
        """Operator-only: close the learning loop (FREE). Fold high-quality live
        decisions into the train set, retrain the local office models, reload them.
        The teacher-distill bootstrap (which spends oracle budget) is run from the
        CLI: `python -m tools.office_corpus --balanced --apply` then this."""
        _require_owner(request)
        return _offices.retrain("all")

    @router.get("/offices/stats", tags=["funnel"])
    def offices_stats(days: int = 30):
        """The offices' oracle-dependence (public, read-only) — the Shepherd
        shrinking with use, measured from the minted training pairs."""
        return _offices.office_stats(days=days)

    @router.post("/narrow", tags=["guide"])
    async def narrow_in(request: Request):
        """The Guide's narrowing (PUBLIC, read-only) — THE_GUIDE rung 2. First call
        surfaces the floor's candidate patterns for a need; pass chosen_id to descend
        to the answer + the elimination trail + the Christ reference. Retrieval is
        choosing, not generating. This is where knowledge meets discernment."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        situation = str(data.get("situation") or data.get("text") or "").strip()
        if not situation:
            raise HTTPException(400, "situation is required")
        if len(situation) > 4000:
            raise HTTPException(400, "situation too long")
        chosen = data.get("chosen_id")
        reply = data.get("reply")
        result = _offices.narrow(situation,
                                 reply=(str(reply)[:2000] if reply else None),
                                 chosen_id=(str(chosen) if chosen else None))
        # Memoryful when the soul is known. The Guide stays PUBLIC + stateless for
        # strangers (no identity -> nothing attached), but for a person carrying a
        # capability id (or the operator) the Shepherd connects today's need to their
        # prior shares + walks — the same recall the funnel gives, now on the open
        # guide. Only on the OPENING call (when they first state the situation), not
        # on every reply/descent. Best-effort; never blocks the narrowing.
        if isinstance(result, dict) and not reply and not chosen:
            try:
                person = _person_id(request)
                if person:
                    rc = _offices.recall_connection(situation, _list_private(person))
                    if rc:
                        result["recall"] = rc
                    wr = _recall_walk(person, situation)
                    if wr:
                        result["recall_walk"] = wr
            except Exception:
                pass
        return result

    return router
