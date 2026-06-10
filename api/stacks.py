"""stacks.py — Per-household card stacks (LOOP 13).

Each household has its own stack — the cards they paperclipped, the cards
they authored, the cards they forked. Cards trade between households through:

  PAPERCLIP — free, default. Adds a public card to your stack. Author sees
              "+1 household paperclipped this." Pure social signal.
  SHARE     — free, scoped. Send a card or your stack to a specific household.
  FORK      — free, attributed. Take a public card, refine it, publish a new
              card with forked_from pointing at the original. Both stay.
  TIP       — optional, via the live wallet. Tips are gratitude. Never gating.

Cards are public goods. Free to read, paperclip, fork. Tips route through
api/wallet.py — no new payment infra.

Storage:
  data/stacks/{household_id}.json   one file per household

Endpoints:
  GET   /stacks/{household_id}
  POST  /stacks/{household_id}/paperclip
  POST  /stacks/{household_id}/unpaperclip
  POST  /stacks/{household_id}/share
  POST  /stacks/{household_id}/fork
  POST  /stacks/{household_id}/tip
  POST  /stacks/{household_id}/note         author a private note card into your stack
  GET   /stacks/{household_id}/inbox        cards others shared to you
  GET   /stacks/health                       counts across all stacks (operator dashboard)
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Body
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore

REPO = Path(__file__).resolve().parent.parent
STACKS_DIR = REPO / "data" / "stacks"
CARDS_DIR = REPO / "data" / "cards"

# Cap to discourage stack-as-warehouse. Stacks are reading lists, not archives.
MAX_PAPERCLIPS = 1000
HOUSEHOLD_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir():
    STACKS_DIR.mkdir(parents=True, exist_ok=True)


def _valid_household_id(hid: str) -> bool:
    return bool(hid) and bool(HOUSEHOLD_ID_RE.match(hid))


def _stack_path(hid: str) -> Path:
    return STACKS_DIR / f"{hid}.json"


def _load_stack(hid: str) -> dict:
    _ensure_dir()
    p = _stack_path(hid)
    if not p.exists():
        return {
            "household_id": hid,
            "paperclipped_card_ids": [],
            "authored_card_ids": [],
            "forked_card_ids": [],
            "tip_total_usd": 0,
            "inbox": [],  # cards/stacks shared to this household
            "created_at": _now(),
            "updated_at": _now(),
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {
            "household_id": hid,
            "paperclipped_card_ids": [],
            "authored_card_ids": [],
            "forked_card_ids": [],
            "tip_total_usd": 0,
            "inbox": [],
            "created_at": _now(),
            "updated_at": _now(),
        }


def _save_stack(stack: dict):
    _ensure_dir()
    stack["updated_at"] = _now()
    _stack_path(stack["household_id"]).write_text(json.dumps(stack, indent=2), encoding="utf-8")


def _card_path(card_id: str) -> Path:
    return CARDS_DIR / f"{card_id}.json"


def _load_card_anywhere(card_id: str) -> Optional[dict]:
    """Read a card from disk OR fall back to the substrate adapter in api.cards."""
    p = _card_path(card_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    # Adapter fallback
    try:
        from api.cards import _all_cards_unified as _unified  # type: ignore
        return _unified().get(card_id)
    except Exception:
        return None


def _persist_card(card: dict):
    """Write a card to disk. Used when paperclipping forces an adapter card to
    materialize so we can update its metrics."""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    _card_path(card["id"]).write_text(json.dumps(card, indent=2), encoding="utf-8")
    try:
        from api.cards import working_set as _ws  # type: ignore
        _ws().put(card["id"], card)
    except Exception:
        pass


def _bump_paperclips(card_id: str, delta: int = 1):
    """Materialize the card to disk if needed and bump its paperclip count."""
    card = _load_card_anywhere(card_id)
    if card is None:
        return
    metrics = card.get("metrics") or {}
    metrics["paperclips_count"] = max(0, metrics.get("paperclips_count", 0) + delta)
    card["metrics"] = metrics
    card["updated_at"] = _now()
    _persist_card(card)


# ---------- Request schemas ----------

if APIRouter is not None:
    class PaperclipIn(BaseModel):
        card_id: str

    class ShareIn(BaseModel):
        card_id: Optional[str] = None  # share a single card
        stack: bool = False  # or share the whole stack
        to_household: str
        message: Optional[str] = None

    class ForkIn(BaseModel):
        from_card_id: str
        new_title: str
        new_body: str
        new_source_label: Optional[str] = None
        new_source_url: Optional[str] = None
        new_source_ref: Optional[str] = None
        new_source_authority_tier: Optional[str] = "user_household"

    class TipIn(BaseModel):
        card_id: str
        amount_usd: float
        txid: str
        chain: str = "base"
        message: Optional[str] = None

    class NoteIn(BaseModel):
        title: str
        body: str
        source_label: Optional[str] = None
        source_url: Optional[str] = None
        source_ref: Optional[str] = None
        bands: Optional[list[str]] = None


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/stacks/health")
    def stacks_health():
        _ensure_dir()
        total = 0
        total_paperclips = 0
        total_authored = 0
        total_tipped = 0.0
        for f in STACKS_DIR.glob("*.json"):
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
                total += 1
                total_paperclips += len(s.get("paperclipped_card_ids", []))
                total_authored += len(s.get("authored_card_ids", []))
                total_tipped += float(s.get("tip_total_usd", 0))
            except Exception:
                continue
        return {
            "total_stacks": total,
            "total_paperclips_across_stacks": total_paperclips,
            "total_authored_across_stacks": total_authored,
            "total_tipped_usd_across_stacks": round(total_tipped, 2),
        }

    @router.get("/stacks/{household_id}")
    def get_stack(household_id: str):
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        stack = _load_stack(household_id)
        return stack

    @router.post("/stacks/{household_id}/paperclip")
    def paperclip(household_id: str, payload: PaperclipIn):
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        card = _load_card_anywhere(payload.card_id)
        if card is None:
            raise HTTPException(404, f"No card with id {payload.card_id}")
        stack = _load_stack(household_id)
        if len(stack["paperclipped_card_ids"]) >= MAX_PAPERCLIPS:
            raise HTTPException(400, f"Stack at max ({MAX_PAPERCLIPS}). Trim before paperclipping more.")
        if payload.card_id in stack["paperclipped_card_ids"]:
            return {"status": "already_on_stack", "card_id": payload.card_id}
        stack["paperclipped_card_ids"].append(payload.card_id)
        _save_stack(stack)
        _bump_paperclips(payload.card_id, +1)
        return {"status": "paperclipped", "card_id": payload.card_id, "stack_size": len(stack["paperclipped_card_ids"])}

    @router.post("/stacks/{household_id}/unpaperclip")
    def unpaperclip(household_id: str, payload: PaperclipIn):
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        stack = _load_stack(household_id)
        if payload.card_id not in stack["paperclipped_card_ids"]:
            return {"status": "not_on_stack", "card_id": payload.card_id}
        stack["paperclipped_card_ids"].remove(payload.card_id)
        _save_stack(stack)
        _bump_paperclips(payload.card_id, -1)
        return {"status": "unpaperclipped", "card_id": payload.card_id, "stack_size": len(stack["paperclipped_card_ids"])}

    @router.post("/stacks/{household_id}/share")
    def share(household_id: str, payload: ShareIn):
        if not _valid_household_id(household_id) or not _valid_household_id(payload.to_household):
            raise HTTPException(400, "Invalid household_id")
        if household_id == payload.to_household:
            raise HTTPException(400, "Cannot share to yourself")
        sender = _load_stack(household_id)
        recipient = _load_stack(payload.to_household)
        if payload.stack:
            recipient["inbox"].append({
                "kind": "stack",
                "from_household": household_id,
                "ts": _now(),
                "message": (payload.message or "")[:300],
                "stack_snapshot": list(sender["paperclipped_card_ids"]),
            })
        elif payload.card_id:
            card = _load_card_anywhere(payload.card_id)
            if card is None:
                raise HTTPException(404, f"No card with id {payload.card_id}")
            recipient["inbox"].append({
                "kind": "card",
                "from_household": household_id,
                "ts": _now(),
                "message": (payload.message or "")[:300],
                "card_id": payload.card_id,
                "card_title": card.get("title"),
            })
        else:
            raise HTTPException(400, "Either card_id or stack=true is required")
        _save_stack(recipient)
        return {"status": "shared", "to_household": payload.to_household}

    @router.get("/stacks/{household_id}/inbox")
    def inbox(household_id: str):
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        stack = _load_stack(household_id)
        return {"household_id": household_id, "count": len(stack.get("inbox", [])), "items": stack.get("inbox", [])}

    @router.post("/stacks/{household_id}/fork")
    def fork(household_id: str, payload: ForkIn):
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        parent = _load_card_anywhere(payload.from_card_id)
        if parent is None:
            raise HTTPException(404, f"No card with id {payload.from_card_id}")
        # Create the forked card via the cards API logic (write directly to disk)
        try:
            from api.cards import _make_card_id, _compute_source_hash, _save_card  # type: ignore
        except Exception:
            raise HTTPException(500, "Cards module unavailable")
        seed = f"fork::{household_id}::{payload.from_card_id}::{payload.new_title}"
        new_id = _make_card_id("note", seed)
        forked = {
            "id": new_id,
            "kind": "note",
            "title": payload.new_title,
            "body": payload.new_body[:4000],
            "source": {
                "label": payload.new_source_label or f"Forked from {parent.get('title', '')}",
                "url": payload.new_source_url or "",
                "ref": payload.new_source_ref or "",
                "authority_tier": payload.new_source_authority_tier or "user_household",
            },
            "shelf": parent.get("shelf", "household"),
            "box": parent.get("box"),
            "bands": parent.get("bands") or [],
            "connections": [{"to_card_id": payload.from_card_id, "relationship": "cites"}],
            "author": f"household_{household_id}",
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "private",
            "lifecycle_stage": "private",
            "volatility": "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "forked_from": payload.from_card_id,
        }
        forked["source_hash"] = _compute_source_hash(forked)
        _save_card(forked)
        stack = _load_stack(household_id)
        if new_id not in stack["forked_card_ids"]:
            stack["forked_card_ids"].append(new_id)
        if new_id not in stack["authored_card_ids"]:
            stack["authored_card_ids"].append(new_id)
        _save_stack(stack)
        return {"status": "forked", "card_id": new_id, "from_card_id": payload.from_card_id}

    @router.post("/stacks/{household_id}/note")
    def note(household_id: str, payload: NoteIn):
        """Author a household-private note card into your own stack."""
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        try:
            from api.cards import _make_card_id, _compute_source_hash, _save_card  # type: ignore
        except Exception:
            raise HTTPException(500, "Cards module unavailable")
        seed = f"note::{household_id}::{payload.title}::{_now()[:13]}"
        new_id = _make_card_id("note", seed)
        card = {
            "id": new_id,
            "kind": "note",
            "title": payload.title[:200],
            "body": (payload.body or "")[:4000],
            "source": {
                "label": payload.source_label or "household note",
                "url": payload.source_url or "",
                "ref": payload.source_ref or "",
                "authority_tier": "user_household",
            },
            "shelf": "household",
            "box": "notes",
            "bands": payload.bands or [],
            "connections": [],
            "author": f"household_{household_id}",
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "private",
            "lifecycle_stage": "private",
            "volatility": "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
        }
        card["source_hash"] = _compute_source_hash(card)
        _save_card(card)
        stack = _load_stack(household_id)
        if new_id not in stack["authored_card_ids"]:
            stack["authored_card_ids"].append(new_id)
        _save_stack(stack)
        return {"status": "authored", "card_id": new_id}

    @router.post("/stacks/{household_id}/tip")
    def tip(household_id: str, payload: TipIn):
        """Record a tip for a card author. Routes through the existing wallet
        transparency log so tips are auditable and counts roll up into card metrics."""
        if not _valid_household_id(household_id):
            raise HTTPException(400, "Invalid household_id")
        if payload.amount_usd <= 0 or payload.amount_usd > 10000:
            raise HTTPException(400, "amount_usd out of range")
        card = _load_card_anywhere(payload.card_id)
        if card is None:
            raise HTTPException(404, f"No card with id {payload.card_id}")
        # Record in wallet transparency log via wallet module
        try:
            from api.wallet import _load_log, _save_log, _valid_txid, _now as _wallet_now  # type: ignore
        except Exception:
            raise HTTPException(500, "Wallet module unavailable")
        if not _valid_txid(payload.txid):
            raise HTTPException(400, "Invalid txid format. Expected 0x + 64 hex chars.")
        log = _load_log()
        entries = log.get("entries", [])
        if any(e.get("txid") == payload.txid for e in entries):
            return {"status": "already_logged", "txid": payload.txid}
        entry = {
            "id": f"tip_{len(entries) + 1:06d}",
            "direction": "in",
            "txid": payload.txid,
            "chain": payload.chain,
            "amount_usd": payload.amount_usd,
            "token": "USDC",
            "intent": "tip-creator",
            "creator_id": card.get("author"),
            "card_id": payload.card_id,
            "from_household_redacted": household_id[-4:] if len(household_id) >= 4 else household_id,
            "message": (payload.message or "")[:200],
            "recorded_at": _wallet_now(),
            "verified_on_chain": False,
        }
        entries.append(entry)
        log["entries"] = entries
        _save_log(log)
        # Update card metric
        m = card.get("metrics") or {}
        m["tip_total_usd"] = float(m.get("tip_total_usd", 0)) + payload.amount_usd
        card["metrics"] = m
        _persist_card(card)
        # Update household tip total
        stack = _load_stack(household_id)
        stack["tip_total_usd"] = float(stack.get("tip_total_usd", 0)) + payload.amount_usd
        _save_stack(stack)
        return {
            "status": "tipped",
            "card_id": payload.card_id,
            "amount_usd": payload.amount_usd,
            "card_tip_total_usd": m["tip_total_usd"],
            "_note": "Tips are gratitude, never gating. The card stays free.",
        }

    return router
