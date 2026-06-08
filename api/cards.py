"""cards.py — The card library (LOOP 11).

Everything in the Narrow Highway substrate is a card. Notes, connections,
walks, searches, community notes, user stacks — one unified shape
distinguished by `kind`. The library catalogs itself.

Principles (load-bearing, do not violate):

1. Minimum on board. The working-set manager holds a bounded LRU of cards
   in memory; everything else is on disk. `cards.get(id)` is the only
   read path — it transparently warms or evicts.

2. Solve permanently. A walk that survives the alignment gate is cached by
   query-fingerprint. The next similar question hits the cached walk, not
   the search engine. (Cache implementation lands in LOOP 6; the fingerprint
   field exists from day one.)

3. Sources or it didn't happen. Every card must trace to a source with a
   link-back. Cards without sources land in quarantine and never escape it.

4. Cards are public goods. Free to read, paperclip, fork. Tips are
   gratitude, never gating.

5. Re-walkable by a human alone. If the engine vanished, the cards still
   teach. Terse content, source link, connection list — no black-box.

Endpoints (Phase 1):
    GET    /cards/{id}                  single card
    GET    /cards                       list, filterable by shelf/box/kind/lifecycle
    POST   /cards                       create (lands in quarantine pending promotion)
    POST   /cards/{id}/promote          operator-only, advance lifecycle stage
    POST   /cards/{id}/retract          author or operator
    GET    /cards/{id}/connections      outgoing + inbound
    POST   /connections                 create a connection card
    POST   /cards/walk                  search → walk-card with surfaced cards
    GET    /cards/stats                 library health
    GET    /cards/working-set           working-set manager stats

Lifecycle (state machine):
    quarantine → private → shared → public_review → public → featured
                                                      ↓
                                                  fading → archived

Storage:
    data/cards/{id}.json            one card per file
    data/quarantine/cards/{id}.json staging area; flushed on TTL
"""
from __future__ import annotations
import hashlib
import json
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Body, Query, Request
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore


# ---------- Request schemas (module-scope; FastAPI introspects these as bodies) ----------

if APIRouter is not None:
    class CardIn(BaseModel):
        kind: str
        title: str
        body: Optional[str] = ""
        source_label: Optional[str] = None
        source_url: Optional[str] = None
        source_ref: Optional[str] = None
        source_authority_tier: Optional[str] = "external_unverified"
        shelf: str
        box: Optional[str] = None
        bands: Optional[list[str]] = None
        connections: Optional[list[dict]] = None
        author: Optional[str] = "engine"
        visibility: Optional[str] = "quarantine"
        volatility: Optional[str] = "stable"
        extra: Optional[dict] = None

    class ConnectionIn(BaseModel):
        left_card_id: str
        right_card_id: str
        relationship: str
        explanation: Optional[str] = None
        bidirectional: bool = True
        author: Optional[str] = "matt"

    class RejectIn(BaseModel):
        from_card_id: str
        to_card_id: str

    class WalkIn(BaseModel):
        query: str
        k: int = 7
        asked_by: Optional[str] = "anon"
        save_as_walk: bool = False

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
QUARANTINE_CARDS_DIR = REPO / "data" / "quarantine" / "cards"
CONTENT = REPO / "content"
SITE = REPO / "site"
DATA = REPO / "data"

VALID_KINDS = ("note", "connection", "walk", "search", "community_note", "stack")
VALID_LIFECYCLE = (
    "quarantine", "private", "shared", "public_review",
    "public", "featured", "fading", "archived"
)
VALID_VISIBILITY = ("private", "shared", "public", "quarantine")
VALID_AUTHORITY = (
    "words_in_red", "scripture", "creed", "catechism", "father",
    "matt", "user_household", "external_aligned", "external_unverified",
    "engine_derived",
)
VALID_RELATIONSHIPS = (
    "proof_text", "illuminates", "fulfills", "cites", "parallels",
    "contradicts", "counterexample", "depends_on", "consequence_of", "see_also",
)
VALID_VOLATILITY = ("permanent", "stable", "seasonal", "current")


# ---------- Working-set manager ----------

class WorkingSet:
    """Bounded LRU cache for cards. Every read goes through here.

    Backed by disk on miss. Evicts least-recently-used past capacity.
    Reports hit/miss rates so we can tune capacity against real use.
    """

    def __init__(self, capacity: int = 1000):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._capacity = capacity
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._loaded_at_start = time.time()

    def get(self, card_id: str) -> Optional[dict]:
        if card_id in self._cache:
            self._cache.move_to_end(card_id)
            self._hits += 1
            return self._cache[card_id]
        self._misses += 1
        card = self._load_from_disk(card_id)
        if card is not None:
            self._put_unchecked(card_id, card)
        return card

    def put(self, card_id: str, card: dict):
        """Insert a card into working-set without disk read (for newly-created cards)."""
        self._put_unchecked(card_id, card)

    def invalidate(self, card_id: str):
        self._cache.pop(card_id, None)

    def _put_unchecked(self, card_id: str, card: dict):
        self._cache[card_id] = card
        self._cache.move_to_end(card_id)
        while len(self._cache) > self._capacity:
            self._cache.popitem(last=False)
            self._evictions += 1

    def _load_from_disk(self, card_id: str) -> Optional[dict]:
        # Live cards first
        p = CARDS_DIR / f"{card_id}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        # Quarantine fallback (cards in quarantine are still readable; just unpromoted)
        q = QUARANTINE_CARDS_DIR / f"{card_id}.json"
        if q.exists():
            try:
                return json.loads(q.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "capacity": self._capacity,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": round(self._hits / total, 3) if total else None,
            "uptime_seconds": round(time.time() - self._loaded_at_start, 1),
        }


_WORKING_SET: Optional[WorkingSet] = None


def working_set() -> WorkingSet:
    global _WORKING_SET
    if _WORKING_SET is None:
        _WORKING_SET = WorkingSet(capacity=1000)
    return _WORKING_SET


# ---------- Card storage primitives ----------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs():
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_CARDS_DIR.mkdir(parents=True, exist_ok=True)


def _slug(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40] or "x"


def _make_card_id(kind: str, seed: str) -> str:
    """Deterministic id from kind + content seed. Lets us dedupe by source_hash."""
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    kind_prefix = {
        "note": "n",
        "connection": "c",
        "walk": "w",
        "search": "s",
        "community_note": "cn",
        "stack": "st",
    }.get(kind, "x")
    return f"card_{kind_prefix}_{h}"


def _compute_source_hash(card: dict) -> str:
    """Hash the load-bearing identity fields. Used for dedup."""
    src = card.get("source") or {}
    seed = "|".join([
        card.get("title", ""),
        (card.get("body") or "")[:500],
        src.get("url", ""),
        src.get("ref", ""),
    ])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _path_for(card_id: str, lifecycle_stage: str) -> Path:
    if lifecycle_stage == "quarantine":
        return QUARANTINE_CARDS_DIR / f"{card_id}.json"
    return CARDS_DIR / f"{card_id}.json"


def _save_card(card: dict) -> Path:
    _ensure_dirs()
    p = _path_for(card["id"], card.get("lifecycle_stage", "quarantine"))
    p.write_text(json.dumps(card, indent=2), encoding="utf-8")
    working_set().put(card["id"], card)
    return p


def _read_card(card_id: str) -> Optional[dict]:
    return working_set().get(card_id)


def _iter_live_cards():
    _ensure_dirs()
    for f in CARDS_DIR.glob("*.json"):
        try:
            yield json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue


# ---------- Validation ----------

def _validate_card(c: dict) -> None:
    """Lightweight runtime validation. JSON Schema validation lives in schema/.
    Here we enforce the invariants the API contracts depend on."""
    if "id" not in c or not re.match(r"^card_[a-z0-9_]{8,60}$", c["id"]):
        raise HTTPException(400, "Invalid id (expected card_<kind>_<hash>)")
    if c.get("kind") not in VALID_KINDS:
        raise HTTPException(400, f"Invalid kind. Must be one of {VALID_KINDS}")
    if not c.get("title") or len(c["title"]) > 200:
        raise HTTPException(400, "Title required, max 200 chars")
    if len(c.get("body") or "") > 4000:
        raise HTTPException(400, "Body max 4000 chars (cards are index cards, not essays)")
    if c.get("lifecycle_stage") not in VALID_LIFECYCLE:
        raise HTTPException(400, f"Invalid lifecycle_stage")
    if c.get("visibility") not in VALID_VISIBILITY:
        raise HTTPException(400, f"Invalid visibility")
    src = c.get("source") or {}
    if src and src.get("authority_tier") and src["authority_tier"] not in VALID_AUTHORITY:
        raise HTTPException(400, f"Invalid source.authority_tier")
    for conn in (c.get("connections") or []):
        if conn.get("relationship") not in VALID_RELATIONSHIPS:
            raise HTTPException(400, f"Invalid relationship: {conn.get('relationship')}")


# ---------- Substrate adapter ----------
# Read-only view of existing substrate as cards. No data migration in LOOP 11;
# this lets /card.html and /walk.html work against real content from day one.
# LOOP 3 will do the proper migration where these become first-class on-disk cards.

_ADAPTER_CACHE: dict = {"loaded": False, "cards": {}}


def _adapter_load():
    if _ADAPTER_CACHE["loaded"]:
        return
    cards = {}

    # 1. Bible books → card per book, shelf=codex, box=<section>
    bb = CONTENT / "codex" / "bible_books.json"
    if bb.exists():
        try:
            j = json.loads(bb.read_text(encoding="utf-8"))
            for b in (j.get("books") or []):
                name = b.get("book", "")
                cid = _make_card_id("note", f"bible_book::{name}")
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": name,
                    "body": (b.get("theme") or "") + (
                        f"\n\n{b.get('chapters', 0)} chapters · {b.get('author', 'tradition')}." if b.get("chapters") else ""
                    ),
                    "source": {
                        "label": f"Bible · {name}",
                        "url": f"/canon.html?ref={name.replace(' ', '%20')}%201",
                        "ref": name,
                        "authority_tier": "scripture",
                    },
                    "shelf": "codex",
                    "box": b.get("section", "Bible"),
                    "bands": [b.get("testament", ""), b.get("section", "")],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # Heidelberg Catechism (German/Dutch Reformed tradition) — LOOP 24
    hc = CONTENT / "codex" / "catechism_heidelberg.json"
    if hc.exists():
        try:
            j = json.loads(hc.read_text(encoding="utf-8"))
            for q in (j.get("questions") or []):
                qnum = q.get("q", "")
                title = f"Heidelberg Q{qnum}"
                cid = _make_card_id("note", f"hc::{qnum}")
                proofs = q.get("proof_texts") or []
                body = (q.get("question") or "") + "\n\n" + (q.get("answer") or "")
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": body[:3800],
                    "source": {
                        "label": "Heidelberg Catechism (1563)",
                        "url": f"/codex.html#hc-q{qnum}",
                        "ref": f"Q{qnum} · Lord's Day {q.get('lords_day', '?')}",
                        "authority_tier": "catechism",
                    },
                    "shelf": "codex",
                    "box": "catechism_heidelberg",
                    "bands": ["heidelberg", "german_reformed", f"lords_day_{q.get('lords_day', '?')}"] + proofs[:3],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 1689 Baptist Confession (Reformed Baptist tradition) — LOOP 24
    cf = CONTENT / "codex" / "confession_1689_baptist.json"
    if cf.exists():
        try:
            j = json.loads(cf.read_text(encoding="utf-8"))
            for ch in (j.get("chapters") or []):
                n = ch.get("n", "")
                title = f"1689 LBCF ch. {n}: {ch.get('title', '')}"
                cid = _make_card_id("note", f"lbcf::{n}")
                proofs = ch.get("proof_texts") or []
                body = ch.get("summary") or ""
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": body[:3800],
                    "source": {
                        "label": "1689 London Baptist Confession of Faith",
                        "url": f"/codex.html#lbcf-ch{n}",
                        "ref": f"Chapter {n}",
                        "authority_tier": "creed",
                    },
                    "shelf": "codex",
                    "box": "confession_1689",
                    "bands": ["1689_baptist", "reformed_baptist", f"chapter_{n}"] + proofs[:3],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # Belgic Confession (continental Reformed) — LOOP 34
    bc = CONTENT / "codex" / "confession_belgic.json"
    if bc.exists():
        try:
            j = json.loads(bc.read_text(encoding="utf-8"))
            for art in (j.get("articles") or []):
                n = art.get("n", "")
                title = f"Belgic Art. {n}: {art.get('title', '')}"
                cid = _make_card_id("note", f"belgic::{n}")
                proofs = art.get("proof_texts") or []
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": (art.get("summary") or "")[:3800],
                    "source": {
                        "label": "Belgic Confession (1561)",
                        "url": f"/codex.html#belgic-art{n}",
                        "ref": f"Article {n}",
                        "authority_tier": "creed",
                    },
                    "shelf": "codex",
                    "box": "confession_belgic",
                    "bands": ["belgic", "continental_reformed", "three_forms_of_unity", f"article_{n}"] + proofs[:3],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # Canons of Dort (continental Reformed) — LOOP 34
    cd = CONTENT / "codex" / "canons_of_dort.json"
    if cd.exists():
        try:
            j = json.loads(cd.read_text(encoding="utf-8"))
            for head in (j.get("heads") or []):
                n = head.get("n", "")
                title = f"Canons of Dort, Head {n}: {head.get('title', '')}"
                cid = _make_card_id("note", f"dort::{n}")
                proofs = head.get("proof_texts") or []
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": (head.get("summary") or "")[:3800],
                    "source": {
                        "label": "Canons of the Synod of Dort (1618-1619)",
                        "url": f"/codex.html#dort-head{n}",
                        "ref": f"Head {n}",
                        "authority_tier": "creed",
                    },
                    "shelf": "codex",
                    "box": "canons_of_dort",
                    "bands": ["dort", "continental_reformed", "three_forms_of_unity", "tulip", f"head_{n}"] + proofs[:3],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 2. Creeds
    cp = CONTENT / "codex" / "creeds.json"
    if cp.exists():
        try:
            j = json.loads(cp.read_text(encoding="utf-8"))
            for c in (j.get("creeds") or []):
                title = c.get("title", "")
                cid = _make_card_id("note", f"creed::{title}")
                anchors = c.get("anchored_to") or []
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": (c.get("text") or "")[:3500],
                    "source": {
                        "label": title + " · " + (c.get("era") or ""),
                        "url": f"/codex.html#creed-{c.get('slug', '')}",
                        "ref": c.get("era", ""),
                        "authority_tier": "creed",
                    },
                    "shelf": "codex",
                    "box": "creeds",
                    "bands": [c.get("era", ""), "creed"] + (anchors[:3] if anchors else []),
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 3. Westminster Shorter Catechism
    cat = CONTENT / "codex" / "catechism_westminster_shorter.json"
    if cat.exists():
        try:
            j = json.loads(cat.read_text(encoding="utf-8"))
            for q in (j.get("questions") or []):
                qnum = q.get("q", "")
                title = f"Westminster Shorter Q{qnum}"
                cid = _make_card_id("note", f"wsc::{qnum}")
                proofs = q.get("proof_texts") or []
                body = (q.get("question") or "") + "\n\n" + (q.get("answer") or "")
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": body[:3500],
                    "source": {
                        "label": "Westminster Shorter Catechism (1647)",
                        "url": f"/codex.html#wsc-q{qnum}",
                        "ref": f"Q{qnum}",
                        "authority_tier": "catechism",
                    },
                    "shelf": "codex",
                    "box": "catechism",
                    "bands": ["westminster_shorter", "1647"] + proofs[:3],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 4. Hymns — primary + extras (LOOP 47)
    hymn_sources = [SITE / "hymns.json", CONTENT / "hymns" / "extra_hymns.json"]
    for hp in hymn_sources:
        if not hp.exists():
            continue
        try:
            j = json.loads(hp.read_text(encoding="utf-8"))
            for h in (j.get("hymns") or []):
                title = h.get("title", "")
                cid = _make_card_id("note", f"hymn::{title}::{h.get('author', '')}")
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": (h.get("text") or "")[:3500],
                    "source": {
                        "label": (h.get("author", "") + " (" + str(h.get("year", "")) + ")").strip(),
                        "url": f"/hymns.html?slug={h.get('slug', '')}",
                        "ref": h.get("author", ""),
                        "authority_tier": "external_aligned",
                    },
                    "shelf": "hymns",
                    "box": (h.get("topic") or ["general"])[0] if h.get("topic") else "general",
                    "bands": h.get("topic") or [],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 5. Recipes
    rp = CONTENT / "recipes.json"
    if rp.exists():
        try:
            j = json.loads(rp.read_text(encoding="utf-8"))
            for r in (j.get("recipes") or []):
                title = r.get("title", "")
                cid = _make_card_id("note", f"recipe::{title}")
                ingredients = "\n".join("· " + i for i in (r.get("ingredients") or [])[:12])
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": ((r.get("family_note") or "") + "\n\n" + ingredients)[:3500],
                    "source": {
                        "label": r.get("source", "family kitchen"),
                        "url": f"/recipes.html#{r.get('slug', '')}",
                        "ref": r.get("source", ""),
                        "authority_tier": "external_aligned",
                    },
                    "shelf": "recipes",
                    "box": (r.get("tags") or ["kitchen"])[0] if r.get("tags") else "kitchen",
                    "bands": r.get("tags") or [],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "stable",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    # 6. Maker projects
    pp = CONTENT / "projects.json"
    if pp.exists():
        try:
            j = json.loads(pp.read_text(encoding="utf-8"))
            for p in (j.get("projects") or []):
                title = p.get("title", "")
                cid = _make_card_id("note", f"project::{title}")
                cards[cid] = {
                    "id": cid,
                    "kind": "note",
                    "title": title,
                    "body": (p.get("summary") or "")[:3500],
                    "source": {
                        "label": p.get("primary_source", "maker"),
                        "url": f"/maker.html#{p.get('slug', '')}",
                        "ref": p.get("primary_source", ""),
                        "authority_tier": "external_aligned",
                    },
                    "shelf": "maker",
                    "box": (p.get("category") or "general"),
                    "bands": p.get("materials") or [],
                    "connections": [],
                    "author": "engine",
                    "created_at": "2026-05-19T00:00:00Z",
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                }
        except Exception:
            pass

    _ADAPTER_CACHE["cards"] = cards
    _ADAPTER_CACHE["loaded"] = True


import threading as _threading_unified
import time as _time_unified
_UNIFIED_CACHE: dict = {"cards": None, "dir_mtime": 0.0, "checked_at": 0.0}
_UNIFIED_TTL_SECONDS = 30.0
_UNIFIED_REBUILD_LOCK = _threading_unified.Lock()


def _all_cards_unified() -> dict:
    """Returns dict of {card_id: card} merging adapter-surfaced cards with on-disk cards.
    On-disk cards take precedence (operator authoring overrides adapter view).

    Two-layer cache (same pattern as atlas/daily_card/promotion):
      - TTL hot path: 30s window skips disk entirely
      - Cold path: single-stat dir-mtime check; rebuild only when substrate changes
      - Single-flight lock: concurrent first-callers wait, only one rebuilds
    Without TTL, the old per-call max(stat()) on 11k files cost ~200ms each
    AND any card-write invalidated the cache, making /cards/stats hang 5-15s.
    """
    now = _time_unified.time()
    # Hot path
    if _UNIFIED_CACHE["cards"] is not None and (now - _UNIFIED_CACHE["checked_at"]) < _UNIFIED_TTL_SECONDS:
        return _UNIFIED_CACHE["cards"]
    # Cold path: cheap dir-mtime
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _UNIFIED_CACHE["cards"] is not None and abs(dir_mtime - _UNIFIED_CACHE["dir_mtime"]) < 1.0:
        _UNIFIED_CACHE["checked_at"] = now
        return _UNIFIED_CACHE["cards"]
    # Single-flight rebuild
    with _UNIFIED_REBUILD_LOCK:
        now2 = _time_unified.time()
        if _UNIFIED_CACHE["cards"] is not None and (now2 - _UNIFIED_CACHE["checked_at"]) < _UNIFIED_TTL_SECONDS:
            return _UNIFIED_CACHE["cards"]
        _adapter_load()
        out = dict(_ADAPTER_CACHE["cards"])
        for c in _iter_live_cards():
            if c.get("id"):
                out[c["id"]] = c
        _UNIFIED_CACHE["cards"] = out
        _UNIFIED_CACHE["dir_mtime"] = dir_mtime
        _UNIFIED_CACHE["checked_at"] = _time_unified.time()
    return _UNIFIED_CACHE["cards"]


def warm_unified_cache():
    """Prime the unified cards cache. Safe to call from startup warmer."""
    try:
        c = _all_cards_unified()
        return {"warmed": True, "cards": len(c)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


# ---------- Walk: search → walk-card ----------

def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z']{1,}", (text or "").lower())


def _score_card_for_query(card: dict, query_tokens: set) -> float:
    """Lightweight TF-IDF-ish scoring against title + body + bands + source.ref.
    Kept for direct-scoring of small candidate sets surfaced via the index."""
    text = " ".join([
        card.get("title", ""),
        card.get("body", "")[:1000],
        " ".join(card.get("bands") or []),
        (card.get("source") or {}).get("ref", ""),
        (card.get("source") or {}).get("label", ""),
    ]).lower()
    doc_tokens = _tokens(text)
    if not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    common = query_tokens & doc_set
    if not common:
        return 0.0
    import math
    counts = {t: 0 for t in common}
    for t in doc_tokens:
        if t in counts:
            counts[t] += 1
    score = sum(counts.values()) / math.log(len(doc_tokens) + 10)
    if len(common) == len(query_tokens):
        score *= 1.5
    # Authority tier boost: scriptural sources rank higher
    tier = (card.get("source") or {}).get("authority_tier")
    tier_boost = {
        "words_in_red": 2.0, "scripture": 1.7, "creed": 1.5, "catechism": 1.5,
        "father": 1.3, "matt": 1.2, "user_household": 1.0,
        "external_aligned": 0.95, "external_unverified": 0.7, "engine_derived": 0.85,
    }.get(tier, 1.0)
    return float(score * tier_boost)


# ---------- Inverted index (LOOP 43) ----------
# token -> list of card_ids that contain it. Built lazily on first walk;
# rebuilt when the substrate mtime changes.

_INVERTED_INDEX: dict = {"built_at": 0, "by_token": {}, "card_count": 0, "watched_mtime": 0}


def _index_text_for_card(card: dict) -> list[str]:
    text = " ".join([
        card.get("title", ""),
        card.get("body", "")[:1000],
        " ".join(card.get("bands") or []),
        (card.get("source") or {}).get("ref", ""),
        (card.get("source") or {}).get("label", ""),
    ]).lower()
    return _tokens(text)


def _ensure_inverted_index(force: bool = False):
    """Build (or rebuild) the inverted index. Cheap rebuild trigger: cards-dir mtime."""
    global _INVERTED_INDEX
    cards_dir_mtime = 0.0
    try:
        if CARDS_DIR.exists():
            cards_dir_mtime = max(f.stat().st_mtime for f in CARDS_DIR.glob("*.json")) if any(CARDS_DIR.glob("*.json")) else 0
    except Exception:
        pass
    if not force and _INVERTED_INDEX["card_count"] > 0 and abs(cards_dir_mtime - _INVERTED_INDEX["watched_mtime"]) < 1.0:
        return
    by_token: dict[str, list[str]] = {}
    n = 0
    for card in _all_cards_unified().values():
        cid = card.get("id")
        if not cid:
            continue
        if card.get("retracted") or card.get("lifecycle_stage") in ("archived", "quarantine"):
            continue
        tokens = set(_index_text_for_card(card))
        for t in tokens:
            by_token.setdefault(t, []).append(cid)
        n += 1
    _INVERTED_INDEX = {
        "built_at": time.time(),
        "by_token": by_token,
        "card_count": n,
        "watched_mtime": cards_dir_mtime,
    }


def _candidates_via_index(query_tokens: set, max_candidates: int = 500) -> list[str]:
    """Use the inverted index to surface candidate card_ids for scoring."""
    _ensure_inverted_index()
    by_token = _INVERTED_INDEX["by_token"]
    candidate_counts: dict[str, int] = {}
    for qt in query_tokens:
        for cid in by_token.get(qt, []):
            candidate_counts[cid] = candidate_counts.get(cid, 0) + 1
    # Sort by how many query tokens hit; cap at max_candidates
    sorted_ids = sorted(candidate_counts.keys(), key=lambda x: -candidate_counts[x])
    return sorted_ids[:max_candidates]


# ---------- Router ----------

def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/cards/_warm")
    def warm_caches():
        """Pre-build the unified-cards cache + inverted index. Useful in startup hooks
        to avoid paying the cold-cache cost on the first user walk (LOOP 49)."""
        import time as _time
        t0 = _time.time()
        _all_cards_unified()
        t_unified = _time.time() - t0
        t0 = _time.time()
        _ensure_inverted_index(force=True)
        t_idx = _time.time() - t0
        return {
            "warmed": True,
            "unified_cache_ms": round(t_unified * 1000),
            "inverted_index_ms": round(t_idx * 1000),
            "card_count": _INVERTED_INDEX.get("card_count", 0),
            "token_count": len(_INVERTED_INDEX.get("by_token", {})),
        }

    @router.get("/cards/working-set")
    def working_set_stats():
        return working_set().stats()

    @router.get("/cards/stats")
    def library_stats():
        all_cards = _all_cards_unified()
        by_shelf = {}
        by_kind = {}
        by_lifecycle = {}
        by_authority = {}
        for c in all_cards.values():
            by_shelf[c.get("shelf", "?")] = by_shelf.get(c.get("shelf", "?"), 0) + 1
            by_kind[c.get("kind", "?")] = by_kind.get(c.get("kind", "?"), 0) + 1
            by_lifecycle[c.get("lifecycle_stage", "?")] = by_lifecycle.get(c.get("lifecycle_stage", "?"), 0) + 1
            tier = (c.get("source") or {}).get("authority_tier", "unknown")
            by_authority[tier] = by_authority.get(tier, 0) + 1
        return {
            "total": len(all_cards),
            "by_shelf": by_shelf,
            "by_kind": by_kind,
            "by_lifecycle": by_lifecycle,
            "by_authority_tier": by_authority,
            "working_set": working_set().stats(),
            "_note": "Includes adapter-surfaced cards from existing substrate + on-disk authored cards.",
        }

    @router.get("/cards/{card_id}")
    def get_card(card_id: str):
        # Try working set / disk first
        c = _read_card(card_id)
        if c is not None:
            return c
        # Fall back to adapter
        _adapter_load()
        c = _ADAPTER_CACHE["cards"].get(card_id)
        if c is None:
            raise HTTPException(404, f"No card with id {card_id}")
        return c

    @router.get("/cards")
    def list_cards(shelf: Optional[str] = Query(None),
                   box: Optional[str] = Query(None),
                   kind: Optional[str] = Query(None),
                   lifecycle: Optional[str] = Query(None),
                   limit: int = Query(50, ge=1, le=500)):
        all_cards = _all_cards_unified()
        out = []
        for c in all_cards.values():
            if shelf and c.get("shelf") != shelf:
                continue
            if box and c.get("box") != box:
                continue
            if kind and c.get("kind") != kind:
                continue
            if lifecycle and c.get("lifecycle_stage") != lifecycle:
                continue
            out.append(c)
        out.sort(key=lambda x: (x.get("shelf") or "", x.get("box") or "", x.get("title") or ""))
        return {"count": len(out[:limit]), "total_matching": len(out), "cards": out[:limit]}

    @router.post("/cards")
    def create_card(payload: CardIn):
        now = _now()
        # Build a seed for deterministic id (lets us dedupe identical cards)
        seed_parts = [payload.title, (payload.body or "")[:200], payload.source_url or "", payload.source_ref or ""]
        cid = _make_card_id(payload.kind, "::".join(seed_parts))
        card = {
            "id": cid,
            "kind": payload.kind,
            "title": payload.title,
            "body": payload.body or "",
            "source": {
                "label": payload.source_label or "",
                "url": payload.source_url or "",
                "ref": payload.source_ref or "",
                "authority_tier": payload.source_authority_tier or "external_unverified",
            },
            "shelf": payload.shelf,
            "box": payload.box,
            "bands": payload.bands or [],
            "connections": payload.connections or [],
            "author": payload.author or "engine",
            "created_at": now,
            "updated_at": now,
            "visibility": payload.visibility or "quarantine",
            "lifecycle_stage": "quarantine",
            "volatility": payload.volatility or "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "retracted": False,
            "extra": payload.extra or {},
        }
        card["source_hash"] = _compute_source_hash(card)
        _validate_card(card)
        # If a card with this id already exists (dedup), return existing
        existing = _read_card(cid)
        if existing is not None:
            return {"status": "exists", "card": existing}
        _save_card(card)
        return {"status": "created", "card": card}

    @router.post("/cards/{card_id}/promote")
    def promote_card(card_id: str, body: dict = Body(...)):
        target = body.get("to_stage")
        if target not in VALID_LIFECYCLE:
            raise HTTPException(400, f"Invalid to_stage. Must be one of {VALID_LIFECYCLE}")
        c = _read_card(card_id)
        if c is None:
            raise HTTPException(404, f"No card with id {card_id}")
        # Lifecycle state machine — refuse illegal transitions
        prev = c.get("lifecycle_stage", "quarantine")
        legal = {
            "quarantine": {"private", "public_review", "archived"},
            "private": {"shared", "public_review", "archived"},
            "shared": {"private", "public_review", "archived"},
            "public_review": {"public", "private", "archived"},
            "public": {"featured", "fading", "archived"},
            "featured": {"public", "fading", "archived"},
            "fading": {"public", "archived"},
            "archived": {"public_review"},
        }
        if target not in legal.get(prev, set()):
            raise HTTPException(400, f"Illegal transition: {prev} -> {target}. Allowed from {prev}: {sorted(legal.get(prev, set()))}")
        c["lifecycle_stage"] = target
        c["updated_at"] = _now()
        if target == "featured":
            c["featured_at"] = c["updated_at"]
        if target == "archived":
            c["archived_at"] = c["updated_at"]
        if target in ("public", "featured"):
            c["visibility"] = "public"
        # Move file if needed (quarantine ↔ live)
        old_path = _path_for(card_id, prev)
        new_path = _path_for(card_id, target)
        if old_path.exists() and old_path != new_path:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(json.dumps(c, indent=2), encoding="utf-8")
            old_path.unlink()
        else:
            _save_card(c)
        working_set().put(card_id, c)
        return {"status": "promoted", "from": prev, "to": target, "card": c}

    @router.post("/cards/{card_id}/retract")
    def retract_card(card_id: str, body: dict = Body(...)):
        reason = (body.get("reason") or "")[:500]
        c = _read_card(card_id)
        if c is None:
            raise HTTPException(404, f"No card with id {card_id}")
        c["retracted"] = True
        c["retraction_reason"] = reason
        c["updated_at"] = _now()
        _save_card(c)
        return {"status": "retracted", "card_id": card_id}

    @router.get("/cards/{card_id}/connections")
    def card_connections(card_id: str):
        c = _read_card(card_id)
        if c is None:
            _adapter_load()
            c = _ADAPTER_CACHE["cards"].get(card_id)
            if c is None:
                raise HTTPException(404, f"No card with id {card_id}")
        outgoing = c.get("connections") or []
        # Find inbound: any card that lists this one in its connections
        inbound = []
        all_cards = _all_cards_unified()
        for other in all_cards.values():
            if other.get("id") == card_id:
                continue
            for conn in (other.get("connections") or []):
                if conn.get("to_card_id") == card_id:
                    inbound.append({
                        "from_card_id": other.get("id"),
                        "from_title": other.get("title"),
                        "relationship": conn.get("relationship"),
                    })
                    break
        return {
            "card_id": card_id,
            "outgoing": outgoing,
            "inbound": inbound,
            "outgoing_count": len(outgoing),
            "inbound_count": len(inbound),
        }

    @router.post("/connections")
    def create_connection(payload: ConnectionIn):
        if payload.relationship not in VALID_RELATIONSHIPS:
            raise HTTPException(400, f"Invalid relationship. Must be one of {VALID_RELATIONSHIPS}")
        if payload.left_card_id == payload.right_card_id:
            raise HTTPException(400, "Cannot connect a card to itself")
        # Verify both cards exist
        left = _read_card(payload.left_card_id)
        right = _read_card(payload.right_card_id)
        if left is None:
            _adapter_load()
            left = _ADAPTER_CACHE["cards"].get(payload.left_card_id)
        if right is None:
            _adapter_load()
            right = _ADAPTER_CACHE["cards"].get(payload.right_card_id)
        if left is None or right is None:
            raise HTTPException(404, "One or both cards not found")
        now = _now()
        cid = _make_card_id("connection", f"conn::{payload.left_card_id}::{payload.right_card_id}::{payload.relationship}")
        conn_card = {
            "id": cid,
            "kind": "connection",
            "title": f"{left.get('title', '')[:60]} ↔ {right.get('title', '')[:60]}",
            "body": payload.explanation or "",
            "source": {
                "label": f"Connection authored by {payload.author or 'matt'}",
                "url": "",
                "ref": "",
                "authority_tier": "matt" if payload.author == "matt" else "engine_derived",
            },
            "shelf": "connections",
            "box": payload.relationship,
            "bands": [payload.relationship, left.get("shelf", ""), right.get("shelf", "")],
            "connections": [
                {"to_card_id": payload.left_card_id, "relationship": "see_also"},
                {"to_card_id": payload.right_card_id, "relationship": "see_also"},
            ],
            "author": payload.author or "matt",
            "created_at": now,
            "updated_at": now,
            "visibility": "public",
            "lifecycle_stage": "public",
            "volatility": "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "extra": {
                "left_card_id": payload.left_card_id,
                "right_card_id": payload.right_card_id,
                "relationship_kind": payload.relationship,
                "explanation": payload.explanation or "",
                "bidirectional": payload.bidirectional,
            },
        }
        conn_card["source_hash"] = _compute_source_hash(conn_card)
        _validate_card(conn_card)
        # Dedup
        existing = _read_card(cid)
        if existing is not None:
            return {"status": "exists", "card": existing}
        _save_card(conn_card)
        return {"status": "created", "card": conn_card}

    # ── The connection LOOP: review the suggesters' queues, approve/reject ─────
    # Two queues feed it: VERIFIED (shared scripture ref — provable; bulk-safe) and
    # HEURISTIC (Jaccard). The operator approves (-> POST /connections, which now
    # auto-advances the card's dev-stage) or rejects (never re-surfaces). Verified
    # proposals sort first.
    _VERIFIED_PATH = REPO / "data" / "rebalance" / "verified_connections.json"
    _SUGGEST_PATH = REPO / "data" / "rebalance" / "suggested_connections.json"
    _REJECT_PATH = REPO / "data" / "rebalance" / "rejected_connections.json"

    def _load_rejected():
        if _REJECT_PATH.exists():
            try:
                return set(tuple(x) for x in json.loads(_REJECT_PATH.read_text(encoding="utf-8")))
            except Exception:
                return set()
        return set()

    @router.get("/connections/suggested")
    def connections_suggested(request: Request, limit: int = 60, method: str = "all"):
        """The review queue: verified (shared-ref) + heuristic (jaccard) proposals,
        minus rejected, enriched + tagged for one-click review. Operator-only.
        `method`: all | verified | heuristic."""
        from api.funnel import _is_owner
        if not _is_owner(request):
            raise HTTPException(404, "Not Found")
        rejected = _load_rejected()
        out = []

        def _drain(path, tag):
            if not path.exists():
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return
            for from_id, info in (data.get("suggestions_by_card") or {}).items():
                for s in (info.get("suggestions") or []):
                    to_id = s.get("to_card_id")
                    if not to_id or tuple(sorted((from_id, to_id))) in rejected:
                        continue
                    out.append({
                        "from_card_id": from_id, "from_title": info.get("card_title"),
                        "from_shelf": info.get("shelf"),
                        "to_card_id": to_id, "to_title": s.get("to_title"),
                        "to_shelf": s.get("to_shelf"),
                        "relationship": s.get("relationship_suggested") or "see_also",
                        "method": tag,
                        "evidence": s.get("evidence"), "shared_count": s.get("shared_count"),
                        "jaccard": s.get("jaccard"), "score": s.get("score"),
                    })

        if method in ("all", "verified"):
            _drain(_VERIFIED_PATH, "verified")
        if method in ("all", "heuristic"):
            _drain(_SUGGEST_PATH, "heuristic")
        # verified first, then by score
        out.sort(key=lambda x: (0 if x["method"] == "verified" else 1, -(x.get("score") or 0)))
        return {"pending": out[:limit], "count": len(out),
                "verified_available": _VERIFIED_PATH.exists()}

    @router.post("/connections/reject")
    def connections_reject(payload: RejectIn, request: Request):
        """Operator rejects a suggested pair; it never re-surfaces."""
        from api.funnel import _is_owner
        if not _is_owner(request):
            raise HTTPException(404, "Not Found")
        rejected = list(_load_rejected())
        key = sorted((payload.from_card_id, payload.to_card_id))
        if tuple(key) not in set(tuple(x) for x in rejected):
            rejected.append(key)
        _REJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REJECT_PATH.write_text(json.dumps(rejected), encoding="utf-8")
        return {"ok": True, "rejected": key}

    @router.post("/cards/walk")
    def walk_cards(payload: WalkIn):
        """The signature operation: search → walk-card.
        First move: check the query-fingerprint cache. If we've solved this question
        before and the cached walk's cards are still live, return it — no re-search.
        Otherwise run the search, persist the walk if save_as_walk=True, and log to
        the replay table so the next similar query can hit the cache.
        """
        # ---- Cache-first lookup ----
        try:
            from api.walks_cache import cache_check, replay_log, cache_store  # type: ignore
            cached = cache_check(payload.query)
            if cached and cached.get("walk_card_id"):
                cached_walk = _read_card(cached["walk_card_id"])
                if cached_walk is not None:
                    surfaced = ((cached_walk.get("extra") or {}).get("cards_surfaced") or [])
                    cards_full = []
                    for sid in surfaced:
                        sc = _read_card(sid)
                        if sc:
                            cards_full.append(sc)
                    if cards_full:
                        steps = []
                        for c in cards_full:
                            steps.append({
                                "card_id": c.get("id"),
                                "title": c.get("title"),
                                "shelf": c.get("shelf"),
                                "box": c.get("box"),
                                "source": c.get("source") or {},
                                "score": 0.0,  # cached; rank already established
                                "narration": _narrate_card(payload.query, c),
                            })
                        return {
                            "query": payload.query,
                            "step_count": len(steps),
                            "steps": steps,
                            "narration": "Asked before. Here's the walk that survived. " + _narrate_walk(payload.query, cards_full),
                            "corpus_size": None,
                            "cache_hit": True,
                            "match_kind": cached.get("match_kind"),
                            "hit_count": cached.get("hit_count"),
                            "walk_card_id": cached["walk_card_id"],
                        }
        except Exception:
            pass

        query_tokens = set(_tokens(payload.query))
        if not query_tokens:
            return {"query": payload.query, "steps": [], "narration": "No searchable terms in query."}
        # Use inverted index to narrow candidates BEFORE scoring (LOOP 43).
        # Falls back to full corpus walk if the index returns nothing.
        all_cards = _all_cards_unified()
        candidate_ids = _candidates_via_index(query_tokens, max_candidates=400)
        if candidate_ids:
            candidates = [all_cards[cid] for cid in candidate_ids if cid in all_cards]
        else:
            candidates = list(all_cards.values())
        scored = []
        for c in candidates:
            if c.get("retracted"):
                continue
            if c.get("lifecycle_stage") in ("archived", "quarantine"):
                continue
            s = _score_card_for_query(c, query_tokens)
            if s > 0:
                scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        top = scored[:payload.k]
        steps = []
        for sc, c in top:
            steps.append({
                "card_id": c.get("id"),
                "title": c.get("title"),
                "shelf": c.get("shelf"),
                "box": c.get("box"),
                "source": c.get("source") or {},
                "score": round(sc, 3),
                "narration": _narrate_card(payload.query, c),
            })
        result = {
            "query": payload.query,
            "step_count": len(steps),
            "steps": steps,
            "narration": _narrate_walk(payload.query, [c for _, c in top]),
            "corpus_size": len(all_cards),
        }
        # Always log to replay table (even when not persisting as walk card)
        # This is the training data for prefetch + signals walks even without save.
        try:
            from api.walks_cache import replay_log as _replay_log  # type: ignore
            _replay_log(
                payload.query,
                payload.query,  # shaped_query (caller already shaped before sending)
                None,
                [s["card_id"] for s in steps if s.get("card_id")],
                payload.asked_by or "anon",
            )
        except Exception:
            pass

        if payload.save_as_walk and steps:
            now = _now()
            cid = _make_card_id("walk", f"walk::{payload.query}::{now[:10]}")
            walk_card = {
                "id": cid,
                "kind": "walk",
                "title": f"Walk: {payload.query[:80]}",
                "body": result["narration"],
                "source": {
                    "label": f"Walk authored by {payload.asked_by or 'anon'}",
                    "url": "",
                    "ref": payload.query,
                    "authority_tier": "engine_derived",
                },
                "shelf": "atlas",
                "box": "walks",
                "bands": list(query_tokens)[:8],
                "connections": [{"to_card_id": s["card_id"], "relationship": "cites"} for s in steps],
                "author": "engine",
                "created_at": now,
                "visibility": "private",
                "lifecycle_stage": "quarantine",
                "volatility": "stable",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 1, "flagged_count": 0},
                "extra": {
                    "query": payload.query,
                    "asked_by": payload.asked_by or "anon",
                    "walk_steps": [{"card_id": s["card_id"], "narration": s["narration"]} for s in steps],
                    "walk_total_steps": len(steps),
                    "cards_surfaced": [s["card_id"] for s in steps],
                },
            }
            walk_card["source_hash"] = _compute_source_hash(walk_card)
            _save_card(walk_card)
            result["walk_card_id"] = cid
            # Promote to fingerprint cache so future similar queries hit it
            try:
                from api.walks_cache import cache_store as _cache_store  # type: ignore
                _cache_store(payload.query, cid)
            except Exception:
                pass
        return result

    return router


def _narrate_card(query: str, card: dict) -> str:
    """One short line Shepherd says when surfacing this card on a walk.
    Matt's voice: declarative, plain, no AI-assistant hedging."""
    src = card.get("source") or {}
    tier = src.get("authority_tier") or "external_unverified"
    label = src.get("label") or ""
    shelf = card.get("shelf") or ""
    title = card.get("title", "")
    if tier == "words_in_red":
        return f"Christ said it. Read it first."
    if tier == "scripture":
        return f"{label}. Read it before anyone's commentary."
    if tier == "creed":
        return f"The church confessed this in {src.get('ref') or 'antiquity'}. It still holds."
    if tier == "catechism":
        ref = src.get("ref") or ""
        return f"The catechism puts it plainest. {ref}."
    if tier == "father":
        return f"{label} on this one. Worth your time."
    if tier == "matt":
        return f"From the operator's bookshelf: {label}."
    if shelf == "hymns":
        return f"And the saints have sung it: '{title}'."
    if shelf == "recipes":
        return f"From a kitchen that's used it: {label}."
    if shelf == "maker":
        return f"In the workshop: {title}."
    if tier == "external_aligned":
        return f"Outside source, brought in carefully. {label}."
    return label or "Worth a look."


def _narrate_walk(query: str, cards: list[dict]) -> str:
    """Shepherd's opening line for the walk. Matt's voice: terse, declarative."""
    if not cards:
        return (
            f"I don't have cards on this yet. "
            f"Bring me a source — a verse, an author, a recipe — and we'll start a card together."
        )
    shelves = sorted(set(c.get("shelf") or "" for c in cards if c.get("shelf")))
    n = len(cards)
    # Pick narration form based on whether the walk crosses shelves
    if len(shelves) >= 3:
        return (
            f"{n} cards. Crosses {len(shelves)} shelves — {', '.join(shelves[:3])}. "
            f"Walk them in order. Each one points to its source."
        )
    if len(shelves) == 1:
        return (
            f"{n} cards from the {shelves[0]} shelf. "
            f"Read them in order. The walk between them is the lesson."
        )
    return (
        f"{n} cards. {', '.join(shelves)}. "
        f"Pull them onto the table and read each against its source."
    )
