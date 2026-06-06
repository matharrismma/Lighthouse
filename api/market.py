"""market.py — Christian Marketplace v1.

Free. No membership, no fee, no cut of any trade. A trusted directory: list a
good or a service; another finds it and sees the seller + listing vouched; the
two transact directly, off-platform. We connect and we vouch. We hold no money,
take no cut, run no escrow.  (See docs/MARKETPLACE_V1.md.)

Design notes
------------
- A listing mirrors the card SHAPE + lifecycle but lives in its OWN store
  (data/market/) so commerce never enters the knowledge substrate / walks.
- Every listing runs the floor at submit (api.floor.stand_on_floor). A RED
  disqualifier (coercion / exploitation / scam language) is rejected outright;
  if the floor is unavailable the listing is HELD for the operator, never
  auto-published (fail-safe).
- Trust attaches twice:
    * the LISTING carries the Deut 19:15 witness gate — >=2 independent
      community vouches promote a quarantined listing to active;
    * the SELLER carries an honest badge (new -> known -> trusted -> vouched,
      or 'caution' if flags were upheld) assembled from real signals, never a
      gameable star number.
- Free: no payment / escrow / membership logic here, by design.

Listing states (status):
  quarantine  submitted; pending operator approval OR >=2 community vouches
  active      published to the deck
  sold        seller marked it done
  expired     retracted / timed out
  rejected    failed the floor, or operator declined

PII / safety: e-mail is never required. Contact is the seller's OPT-IN public
value only, shown on the detail page they chose to publish; never placed in a
URL. We never contact anyone on a buyer's behalf.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Request, Query, Body
    from pydantic import BaseModel
except Exception:  # pragma: no cover - lets the module import without FastAPI
    APIRouter = None
    BaseModel = object  # type: ignore

REPO = Path(__file__).resolve().parent.parent
MARKET_DIR = REPO / "data" / "market"
LISTINGS_DIR = MARKET_DIR / "listings"
SELLERS_DIR = MARKET_DIR / "sellers"
MODERATORS_PATH = MARKET_DIR / "moderators.json"

CATEGORIES = ("goods", "services", "local")
ACTIVE = "active"
QUARANTINE = "quarantine"
VALID_STATUS = ("quarantine", "active", "sold", "expired", "rejected")
VOUCH_THRESHOLD = 2          # Deuteronomy 19:15 — at the mouth of two or three witnesses
_PRICE_UNITS = ("flat", "hr", "day", "wk", "mo")
_CONTACT_METHODS = ("in_platform", "phone", "email", "text", "other")

_LOCK = threading.Lock()


# ───────────────────────── request models (module scope) ─────────────────────
if APIRouter is not None:
    class ListingIn(BaseModel):
        title: str
        description: str = ""
        category: str = "goods"
        price: Optional[float] = None          # None = "contact for price"
        price_unit: Optional[str] = "flat"
        region: str = ""                        # optional human label (town name)
        zip: Optional[str] = ""                 # postal / ZIP — the primary locator
        country: Optional[str] = "US"           # ISO-ish 2-letter, default US
        area_code: Optional[str] = ""           # optional telephone area code (coarse)
        photos: Optional[list] = None          # list of URLs (uploads deferred)
        condition: Optional[str] = None         # goods only: new|good|fair
        contact_method: Optional[str] = "in_platform"
        contact_public: Optional[str] = ""      # opt-in public contact value
        seller_id: Optional[str] = None         # client household id; generated if absent
        seller_name: str = "A neighbor"
        seller_region: Optional[str] = None

    class VouchIn(BaseModel):
        voucher_id: str
        voucher_name: str = "A neighbor"
        note: str = ""

    class FlagIn(BaseModel):
        reason: str = ""
        by: Optional[str] = "anon"

    class SimpleBy(BaseModel):
        by: Optional[str] = "anon"


# ───────────────────────────── helpers ──────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> int:
    return int(time.time())


def _ensure_dirs():
    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SELLERS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (s or ""))[:64]


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _clean(s: Optional[str], limit: int) -> str:
    return (s or "").strip()[:limit]


def _norm_zip(s: Optional[str]) -> str:
    """Postal/ZIP code, normalized: alphanumerics only, upper, max 10.
    Works for US ZIPs ('75701'), intl postcodes ('SW1A1AA'), or a bare prefix."""
    return re.sub(r"[^A-Za-z0-9]", "", (s or "")).upper()[:10]


def _norm_country(s: Optional[str]) -> str:
    c = re.sub(r"[^A-Za-z]", "", (s or "")).upper()[:2]
    return c or "US"


def _norm_area(s: Optional[str]) -> str:
    """Telephone-style area code — digits only, a coarse locator when there's
    no ZIP granularity."""
    return re.sub(r"[^0-9]", "", (s or ""))[:5]


def _listing_path(lid: str) -> Path:
    return LISTINGS_DIR / f"{_safe_id(lid)}.json"


def _seller_path(sid: str) -> Path:
    return SELLERS_DIR / f"{_safe_id(sid)}.json"


def _read(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write(p: Path, obj: dict):
    _ensure_dirs()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(p)


def _load_listing(lid: str) -> Optional[dict]:
    return _read(_listing_path(lid))


def _save_listing(l: dict):
    _write(_listing_path(l["id"]), l)


def _iter_listings():
    _ensure_dirs()
    for f in LISTINGS_DIR.glob("lst_*.json"):
        c = _read(f)
        if c:
            yield c


# ───────────────────────────── the floor gate ───────────────────────────────
def _floor_gate(title: str, description: str) -> dict:
    """Run the listing through the floor. Returns:
        {admitted: bool, rejected: bool, verdicts: [...], red_why, held: bool}
    rejected=True only on an explicit hard reject (RED/FLOOR). If the floor is
    unavailable we set held=True (operator must approve) — we never auto-admit.
    """
    text = f"{title}\n{description}".strip()
    try:
        from api import floor as _floor
        res = _floor.stand_on_floor(text, domain="commerce", kind="listing")
        gates = (res or {}).get("gates") or {}
        verdicts = gates.get("verdicts") or []
        admitted = bool(gates.get("admitted", True))
        red = next((v for v in verdicts if v.get("gate") == "RED"), {})
        return {
            "admitted": admitted,
            "rejected": not admitted,
            "verdicts": verdicts,
            "red_why": red.get("why"),
            "held": False,
        }
    except Exception as e:  # fail-safe: hold for operator, do not auto-admit
        return {
            "admitted": False, "rejected": False, "verdicts": [],
            "red_why": None, "held": True, "error": str(e)[:200],
        }


# ───────────────────────────── sellers + trust ──────────────────────────────
def _get_or_make_seller(seller_id: Optional[str], name: str, region: str) -> dict:
    sid = _safe_id(seller_id or "") or _gen_id("slr")
    s = _read(_seller_path(sid))
    if s is None:
        s = {
            "id": sid,
            "name": _clean(name, 80) or "A neighbor",
            "region": _clean(region, 80),
            "member_since": _now(),
            "member_since_epoch": _now_epoch(),
            "operator_note": "",
            "flags_upheld": 0,
        }
        _write(_seller_path(sid), s)
    else:
        # keep display name / region fresh, but never overwrite member_since
        changed = False
        nm = _clean(name, 80)
        if nm and nm != s.get("name"):
            s["name"] = nm; changed = True
        rg = _clean(region, 80)
        if rg and not s.get("region"):
            s["region"] = rg; changed = True
        if changed:
            _write(_seller_path(sid), s)
    return s


def _seller_stats(sid: str) -> dict:
    """Assemble a seller's signals by scanning their listings (v1 scale)."""
    listings = active = sold = vouches = 0
    vouchers: set = set()
    for l in _iter_listings():
        if l.get("seller_id") != sid:
            continue
        listings += 1
        st = l.get("status")
        if st == ACTIVE:
            active += 1
        elif st == "sold":
            sold += 1
        for v in (l.get("vouches") or []):
            vid = v.get("voucher_id")
            if vid:
                vouchers.add(vid)
        vouches += len(l.get("vouches") or [])
    return {
        "listings": listings, "active": active, "sold": sold,
        "vouches": vouches, "distinct_vouchers": len(vouchers),
    }


def _badge(seller: dict, stats: dict) -> str:
    """Honest, signal-based standing — never a gameable number."""
    if (seller.get("flags_upheld") or 0) > 0:
        return "caution"
    member_days = (_now_epoch() - int(seller.get("member_since_epoch") or _now_epoch())) / 86400.0
    if stats.get("distinct_vouchers", 0) >= VOUCH_THRESHOLD or stats.get("sold", 0) >= 3:
        return "vouched"
    if member_days >= 60 and stats.get("sold", 0) >= 1:
        return "trusted"
    if member_days >= 14 and stats.get("active", 0) >= 1:
        return "known"
    return "new"


def _seller_view(sid: str) -> Optional[dict]:
    s = _read(_seller_path(sid))
    if s is None:
        return None
    stats = _seller_stats(sid)
    return {
        "id": s["id"],
        "name": s.get("name"),
        "region": s.get("region"),
        "member_since": s.get("member_since"),
        "badge": _badge(s, stats),
        "stats": stats,
    }


# ───────────────────────────── listing views ────────────────────────────────
def _public_listing(l: dict, *, with_seller: bool = True) -> dict:
    out = {
        "id": l["id"],
        "title": l.get("title"),
        "description": l.get("description"),
        "category": l.get("category"),
        "price": l.get("price"),
        "price_unit": l.get("price_unit"),
        "region": l.get("region"),
        "zip": l.get("zip"),
        "country": l.get("country") or "US",
        "area_code": l.get("area_code"),
        "photos": l.get("photos") or [],
        "condition": l.get("condition"),
        "contact": l.get("contact") or {},
        "status": l.get("status"),
        "witness_status": l.get("witness_status"),
        "vouch_count": len(l.get("vouches") or []),
        "vouches": [
            {"by": v.get("voucher_name"), "note": v.get("note"), "at": v.get("at")}
            for v in (l.get("vouches") or [])
        ],
        "created_at": l.get("created_at"),
        "published_at": l.get("published_at"),
        "seller_id": l.get("seller_id"),
    }
    if with_seller:
        out["seller"] = _seller_view(l.get("seller_id"))
    return out


def _operator_token_ok(request) -> bool:
    """If NH_OPERATOR_KEY is set, require a matching X-Operator-Key header.
    If unset, follow the existing scaffolding posture (operator on a trusted
    network) and allow. Region moderators are checked separately."""
    key = os.environ.get("NH_OPERATOR_KEY")
    if not key:
        return True
    try:
        return request.headers.get("X-Operator-Key") == key
    except Exception:
        return False


def _is_region_moderator(region: str, who: str) -> bool:
    m = _read(MODERATORS_PATH) or {}
    who = _safe_id(who or "")
    if not who:
        return False
    if who in (m.get("operators") or []):
        return True
    for r, ids in (m.get("by_region") or {}).items():
        if r and region and r.lower() in region.lower() and who in (ids or []):
            return True
    return False


# ───────────────────────────────── router ───────────────────────────────────
def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/market/listings", tags=["marketplace"])
    def create_listing(body: ListingIn):
        title = _clean(body.title, 200)
        if not title:
            raise HTTPException(400, "Title is required.")
        if body.category not in CATEGORIES:
            raise HTTPException(400, f"category must be one of {CATEGORIES}")
        desc = _clean(body.description, 4000)
        gate = _floor_gate(title, desc)

        seller = _get_or_make_seller(
            body.seller_id, body.seller_name, body.seller_region or body.region or ""
        )
        lid = _gen_id("lst")
        method = body.contact_method if body.contact_method in _CONTACT_METHODS else "in_platform"
        unit = body.price_unit if body.price_unit in _PRICE_UNITS else "flat"
        photos = [str(p)[:500] for p in (body.photos or [])][:8]

        if gate["rejected"]:
            status = "rejected"
        else:
            status = QUARANTINE  # pending operator approval or >=2 vouches
        listing = {
            "id": lid,
            "title": title,
            "description": desc,
            "category": body.category,
            "price": (round(float(body.price), 2) if body.price is not None else None),
            "price_unit": unit,
            "region": _clean(body.region, 80),
            "zip": _norm_zip(body.zip),
            "country": _norm_country(body.country),
            "area_code": _norm_area(body.area_code),
            "photos": photos,
            "condition": _clean(body.condition, 20) or None,
            "contact": {"method": method, "public": _clean(body.contact_public, 200)},
            "seller_id": seller["id"],
            "seller_name": seller["name"],
            "status": status,
            "witness_status": "self_only",
            "vouches": [],
            "flags": [],
            "helpful": 0,
            "floor": {
                "admitted": gate["admitted"],
                "held": gate.get("held", False),
                "red_why": gate.get("red_why"),
                "verdicts": gate.get("verdicts"),
            },
            "created_at": _now(),
            "updated_at": _now(),
            "published_at": None,
        }
        _save_listing(listing)
        if status == "rejected":
            return {
                "ok": False, "status": "rejected", "id": lid,
                "reason": gate.get("red_why") or "Did not pass the floor.",
                "message": "This listing didn't pass the floor and won't be published. "
                           "If you believe that's a mistake, an operator can review it.",
            }
        msg = ("Submitted. It's held for an operator to look at "
               + ("(the floor is being cautious here). " if gate.get("held") else "")
               + "or it goes live once two neighbors vouch for it.")
        return {"ok": True, "status": status, "id": lid, "message": msg,
                "listing": _public_listing(listing)}

    @router.get("/market/listings", tags=["marketplace"])
    def browse(
        category: Optional[str] = Query(None),
        zip: Optional[str] = Query(None),                 # primary locator
        scope: Optional[str] = Query(None),               # exact|nearby|area|country|all
        country: Optional[str] = Query(None),
        area_code: Optional[str] = Query(None),
        region: Optional[str] = Query(None),              # free-text label match
        q: Optional[str] = Query(None),
        status: str = Query(ACTIVE),
        limit: int = Query(60, ge=1, le=200),
    ):
        ql = (q or "").strip().lower()
        rl = (region or "").strip().lower()
        zq = _norm_zip(zip)
        cq = _norm_country(country) if country else ""
        aq = _norm_area(area_code)
        sc = (scope or ("exact" if zq else "all")).lower()
        out = []
        for l in _iter_listings():
            if status != "all" and l.get("status") != status:
                continue
            if category and l.get("category") != category:
                continue
            # ── location scope ─────────────────────────────────────────────
            lz = _norm_zip(l.get("zip"))
            lc = _norm_country(l.get("country"))
            la = _norm_area(l.get("area_code"))
            if sc == "exact" and zq:
                if lz != zq:
                    continue
            elif sc == "nearby" and zq:
                k = zq[:3] if len(zq) >= 3 else zq      # ZIP3 ≈ a region
                if not lz.startswith(k):
                    continue
            elif sc == "area" and aq:
                if la != aq:
                    continue
            elif sc == "country" and cq:
                if lc != cq:
                    continue
            # 'all' (or a scope with no matching query) → no location filter
            if rl and rl not in (l.get("region") or "").lower():
                continue
            if ql:
                hay = f"{l.get('title','')} {l.get('description','')} {l.get('region','')} {l.get('zip','')}".lower()
                if ql not in hay:
                    continue
            out.append(_public_listing(l, with_seller=True))
        out.sort(key=lambda x: (x.get("published_at") or x.get("created_at") or ""), reverse=True)
        return {"count": len(out), "scope": sc, "zip": zq, "listings": out[:limit]}

    @router.get("/market/listings/{lid}", tags=["marketplace"])
    def get_listing(lid: str):
        l = _load_listing(lid)
        if l is None or l.get("status") == "rejected":
            raise HTTPException(404, "Listing not found.")
        return _public_listing(l, with_seller=True)

    @router.post("/market/listings/{lid}/vouch", tags=["marketplace"])
    def vouch(lid: str, body: VouchIn):
        with _LOCK:
            l = _load_listing(lid)
            if l is None or l.get("status") == "rejected":
                raise HTTPException(404, "Listing not found.")
            voucher = _safe_id(body.voucher_id)
            if not voucher:
                raise HTTPException(400, "A voucher id is required.")
            if voucher == l.get("seller_id"):
                raise HTTPException(400, "A seller can't vouch for their own listing.")
            if any(v.get("voucher_id") == voucher for v in (l.get("vouches") or [])):
                raise HTTPException(409, "You've already vouched for this listing.")
            l.setdefault("vouches", []).append({
                "voucher_id": voucher,
                "voucher_name": _clean(body.voucher_name, 80) or "A neighbor",
                "note": _clean(body.note, 280),
                "at": _now(),
            })
            n = len(l["vouches"])
            l["witness_status"] = "vouched" if n >= VOUCH_THRESHOLD else "self_only"
            # Steady-phase community promotion: two witnesses publish it.
            if n >= VOUCH_THRESHOLD and l.get("status") == QUARANTINE:
                l["status"] = ACTIVE
                l["published_at"] = _now()
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "vouch_count": n, "witness_status": l["witness_status"],
                "status": l["status"]}

    @router.post("/market/listings/{lid}/flag", tags=["marketplace"])
    def flag(lid: str, body: FlagIn):
        with _LOCK:
            l = _load_listing(lid)
            if l is None:
                raise HTTPException(404, "Listing not found.")
            l.setdefault("flags", []).append({
                "reason": _clean(body.reason, 280), "by": _safe_id(body.by or "anon"),
                "at": _now(),
            })
            l["updated_at"] = _now()
            _save_listing(l)
        # Every flag is read. Notify the operator if a hook is configured.
        try:
            from api import app as _app  # _notify_operator lives on the app module
            if hasattr(_app, "_notify_operator"):
                _app._notify_operator(f"Marketplace listing flagged: {lid} — {_clean(body.reason,120)}")
        except Exception:
            pass
        return {"ok": True, "message": "Flagged for review. Every flag is read."}

    @router.post("/market/listings/{lid}/helpful", tags=["marketplace"])
    def helpful(lid: str, body: SimpleBy):
        with _LOCK:
            l = _load_listing(lid)
            if l is None:
                raise HTTPException(404, "Listing not found.")
            l["helpful"] = int(l.get("helpful") or 0) + 1
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "helpful": l["helpful"]}

    @router.post("/market/listings/{lid}/sold", tags=["marketplace"])
    def mark_sold(lid: str, body: SimpleBy):
        with _LOCK:
            l = _load_listing(lid)
            if l is None:
                raise HTTPException(404, "Listing not found.")
            who = _safe_id(body.by or "")
            if who and who != l.get("seller_id"):
                raise HTTPException(403, "Only the seller can mark this sold.")
            l["status"] = "sold"
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "status": "sold"}

    @router.post("/market/listings/{lid}/retract", tags=["marketplace"])
    def retract(lid: str, body: SimpleBy):
        with _LOCK:
            l = _load_listing(lid)
            if l is None:
                raise HTTPException(404, "Listing not found.")
            who = _safe_id(body.by or "")
            if who and who != l.get("seller_id"):
                raise HTTPException(403, "Only the seller can retract this.")
            l["status"] = "expired"
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "status": "expired"}

    @router.post("/market/listings/{lid}/promote", tags=["marketplace"])
    def promote(lid: str, request: Request, body: SimpleBy = Body(default=None)):
        l = _load_listing(lid)
        if l is None:
            raise HTTPException(404, "Listing not found.")
        who = _safe_id((body.by if body else "") or "")
        if not (_operator_token_ok(request) or _is_region_moderator(l.get("region", ""), who)):
            raise HTTPException(403, "Operator or region moderator only.")
        with _LOCK:
            l = _load_listing(lid)
            l["status"] = ACTIVE
            l["published_at"] = l.get("published_at") or _now()
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "status": ACTIVE}

    @router.post("/market/listings/{lid}/reject", tags=["marketplace"])
    def reject(lid: str, request: Request, body: FlagIn = Body(default=None)):
        if not _operator_token_ok(request):
            raise HTTPException(403, "Operator only.")
        with _LOCK:
            l = _load_listing(lid)
            if l is None:
                raise HTTPException(404, "Listing not found.")
            l["status"] = "rejected"
            l["reject_reason"] = _clean(body.reason if body else "", 280)
            l["updated_at"] = _now()
            _save_listing(l)
        return {"ok": True, "status": "rejected"}

    @router.get("/market/seller/{sid}", tags=["marketplace"])
    def seller(sid: str):
        view = _seller_view(_safe_id(sid))
        if view is None:
            raise HTTPException(404, "Seller not found.")
        listings = [
            _public_listing(l, with_seller=False)
            for l in _iter_listings()
            if l.get("seller_id") == view["id"] and l.get("status") in (ACTIVE, "sold")
        ]
        listings.sort(key=lambda x: (x.get("published_at") or x.get("created_at") or ""), reverse=True)
        view["listings"] = listings
        return view

    @router.get("/market/queue", tags=["marketplace"])
    def queue(request: Request):
        if not _operator_token_ok(request):
            raise HTTPException(403, "Operator only.")
        pending, flagged = [], []
        for l in _iter_listings():
            if l.get("status") == QUARANTINE:
                pending.append(_public_listing(l))
            if l.get("flags"):
                flagged.append({"id": l["id"], "title": l.get("title"),
                                "status": l.get("status"),
                                "flags": l.get("flags")})
        return {"pending": pending, "flagged": flagged,
                "pending_count": len(pending), "flagged_count": len(flagged)}

    @router.get("/market/stats", tags=["marketplace"])
    def stats():
        c = {s: 0 for s in VALID_STATUS}
        by_cat = {k: 0 for k in CATEGORIES}
        total = sellers = 0
        for l in _iter_listings():
            total += 1
            c[l.get("status", QUARANTINE)] = c.get(l.get("status", QUARANTINE), 0) + 1
            if l.get("status") == ACTIVE:
                by_cat[l.get("category", "goods")] = by_cat.get(l.get("category", "goods"), 0) + 1
        try:
            sellers = sum(1 for _ in SELLERS_DIR.glob("slr_*.json")) if SELLERS_DIR.exists() else 0
        except Exception:
            sellers = 0
        return {"total_listings": total, "by_status": c, "active_by_category": by_cat,
                "sellers": sellers, "free": True, "takes_no_cut": True}

    @router.get("/market/zips", tags=["marketplace"])
    def zips():
        """Where the active listings are — ZIPs (and countries) with counts, so
        the deck can offer easy jump-to-another-place."""
        z_counts: dict = {}
        c_counts: dict = {}
        for l in _iter_listings():
            if l.get("status") != ACTIVE:
                continue
            z = _norm_zip(l.get("zip"))
            if z:
                z_counts[z] = z_counts.get(z, 0) + 1
            cc = _norm_country(l.get("country"))
            c_counts[cc] = c_counts.get(cc, 0) + 1
        zlist = sorted(
            [{"zip": z, "count": n} for z, n in z_counts.items()],
            key=lambda x: (-x["count"], x["zip"]),
        )
        clist = sorted(
            [{"country": c, "count": n} for c, n in c_counts.items()],
            key=lambda x: (-x["count"], x["country"]),
        )
        return {"zips": zlist, "countries": clist, "count": len(zlist)}

    return router
