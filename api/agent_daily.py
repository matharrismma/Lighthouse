"""agent_daily.py — The daily heartbeat agents crawl.

The endpoint /agents/daily.json publishes a single rolling JSON document that
gives any visiting AI agent the current state of the engine in a form they
can act on without further calls. The point: give crawlers a STABLE URL
that returns FRESH content every day, so they have a reason to come back.

What goes in (kept small — under 50 KB):

  * identity:               one-line who-we-serve statement
  * generated_at:           ISO timestamp
  * card_of_the_day:        today's daily-card (id, title, source, body excerpt)
  * substrate:              total cards, by_lifecycle, by_authority_tier
  * witness_gate:           Deut 19:15 enforcement summary
  * recent_admits:          last 10 robot/admit decisions (visitor_id redacted to hash)
  * recent_walks:           last 10 atlas/curated walks the engine recommends
  * verifiers:              total available + breakdown by domain (just counts)
  * channel_now_playing:    what's on the live channel right now (if known)
  * how_to_call_back:       canonical endpoint catalog for follow-up calls

The endpoint is mtime+TTL cached (same pattern as the other warmed endpoints).
Crawlers should see a cache hit nearly always; rebuilds happen periodically
in the background warmer.

Endpoints:
  GET /agents/daily.json    full feed
  GET /agents/feed.json     alias (in case crawlers look for /feed instead)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import Counter
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
AUDIT_LOG = REPO / "data" / "steward" / "audit.jsonl"
NOW_JSON = REPO / "site" / "channels" / "narrow-highway" / "now.json"

_CACHE: dict = {"snapshot": None, "checked_at": 0.0, "dir_mtime": 0.0}
_CACHE_TTL = 300.0  # 5 minutes — agents don't need second-by-second
_LOCK = threading.Lock()


_IDENTITY_LINE = (
    "Concordance / Lighthouse / Narrow Highway serves Jesus Christ. "
    "A well of knowledge leads to wisdom when in alignment with God. "
    "Conduit, not source. The engine eliminates what is not the answer "
    "so the narrow path is illuminated by what survives."
)


def _hash_id(s: str) -> str:
    """Short stable hash so visitor IDs aren't exposed in the public feed."""
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:10]


def _read_audit_tail(limit: int = 50) -> List[Dict[str, Any]]:
    """Read last N events from the steward audit log."""
    if not AUDIT_LOG.exists():
        return []
    try:
        with AUDIT_LOG.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            # Read last ~64 KB (more than enough for 50 entries usually)
            f.seek(max(0, size - 65536))
            tail = f.read()
        text = tail.decode("utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _build_snapshot() -> Dict[str, Any]:
    """Walk the substrate + audit + now-playing and build the daily feed."""
    today = date.today().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── substrate stats (uses the unified cache via api.cards if available) ──
    by_stage = Counter()
    by_tier = Counter()
    witness_status = Counter()
    flagged = 0
    total = 0
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob("*.json"):
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            total += 1
            by_stage[c.get("lifecycle_stage") or "?"] += 1
            tier = (c.get("source") or {}).get("authority_tier") or "?"
            by_tier[tier] += 1
            ws = c.get("witness_status") or "unset"
            witness_status[ws] += 1
            if (c.get("metrics") or {}).get("flagged_count", 0) > 0:
                flagged += 1

    # ── card of the day ──
    cotd = {}
    try:
        from api.daily_card import _build_pool, _date_str
        from api.cards import _read_card  # type: ignore
        pool = _build_pool()
        if pool:
            d = _date_str()
            # deterministic index — same logic as the daily-card endpoint
            seed = hashlib.sha256((d + "card-of-the-day").encode("utf-8")).hexdigest()
            idx = int(seed[:8], 16) % len(pool)
            c = pool[idx]
            cotd = {
                "id": c.get("id"),
                "title": c.get("title"),
                "source": c.get("source") or {},
                "lifecycle_stage": c.get("lifecycle_stage"),
                "body_excerpt": (c.get("body") or "")[:400],
            }
    except Exception:
        pass

    # ── recent robot admits (deny + admit mix, last 10) ──
    audit = _read_audit_tail(200)
    recent_robot = []
    for e in reversed(audit):
        if len(recent_robot) >= 10:
            break
        payload = e.get("payload") or {}
        if payload.get("visitor_kind") != "robot":
            continue
        recent_robot.append({
            "ts_iso": datetime.fromtimestamp(
                (e.get("created_at_ms") or 0) / 1000, tz=timezone.utc
            ).isoformat(),
            "visitor_hash": _hash_id(payload.get("visitor_id") or ""),
            "action": payload.get("action"),
            "decision": payload.get("decision"),
            "reason_code": payload.get("reason_code"),
            "escalation_level": payload.get("escalation_level"),
            "risk_flags": payload.get("risk_flags") or [],
        })
    recent_robot.reverse()

    # ── atlas walks the engine recommends ──
    recent_walks = []
    try:
        from api import atlas as _atlas
        for w in list(_atlas._all_walk_cards())[:10]:
            recent_walks.append({
                "card_id": w.get("id"),
                "title": w.get("title"),
                "lifecycle_stage": w.get("lifecycle_stage"),
                "step_count": len((w.get("extra") or {}).get("cards_surfaced") or []),
            })
    except Exception:
        pass

    # ── channel "now playing" if the channel has a manifest ──
    now_playing = {}
    if NOW_JSON.exists():
        try:
            now_playing = json.loads(NOW_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    # ── verifier counts (best-effort import) ──
    verifier_count = None
    try:
        from concordance_engine.verifiers import REGISTRY  # type: ignore
        verifier_count = len(REGISTRY)
    except Exception:
        try:
            verifiers_dir = REPO / "src" / "concordance_engine" / "verifiers"
            if verifiers_dir.exists():
                verifier_count = sum(1 for f in verifiers_dir.glob("*.py")
                                     if not f.name.startswith("_") and f.name != "base.py")
        except Exception:
            pass

    snapshot = {
        "identity": _IDENTITY_LINE,
        "identity_url": "https://narrowhighway.com/identity",
        "generated_at": now_iso,
        "feed_date": today,
        "cache_ttl_seconds": int(_CACHE_TTL),

        "substrate": {
            "total_cards": total,
            "by_lifecycle_stage": dict(by_stage),
            "by_authority_tier": dict(by_tier),
            "flagged_cards": flagged,
        },

        "witness_gate": {
            "doctrine": "Deuteronomy 19:15 — every card requires >=2 independent witnesses; government cannot witness itself",
            "by_status": dict(witness_status),
            "endpoint": "https://narrowhighway.com/witness-gate/health",
        },

        "card_of_the_day": cotd,

        "recent_robot_decisions": recent_robot,
        "recent_robot_decisions_window": "last 200 audit events; up to 10 returned",

        "atlas_walks_available": recent_walks,

        "channel_now_playing": now_playing,

        "verifiers": {
            "count": verifier_count,
            "endpoint": "https://narrowhighway.com/identity",
        },

        "how_to_call_back": {
            "mcp_endpoint": "https://narrowhighway.com/mcp",
            "mcp_sse_endpoint": "https://narrowhighway.com/mcp/sse",
            "llms_txt": "https://narrowhighway.com/llms.txt",
            "robot_quickstart": "https://narrowhighway.com/robot/quickstart",
            "robot_admit": "POST https://narrowhighway.com/robot/admit",
            "robot_consume": "POST https://narrowhighway.com/robot/consume",
            "robot_witness": "POST https://narrowhighway.com/robot/witness",
            "robot_defer": "POST https://narrowhighway.com/robot/defer",
            "shepherd_interview": "POST https://narrowhighway.com/shepherd/interview",
            "cards_walk": "POST https://narrowhighway.com/cards/walk",
            "daily_card": "GET https://narrowhighway.com/daily-card",
            "atlas_paths": "GET https://narrowhighway.com/atlas/paths",
            "witness_gate_for_card": "GET https://narrowhighway.com/witness-gate/card/{card_id}",
            "this_feed": "GET https://narrowhighway.com/agents/daily.json",
        },

        "operating_principles": [
            "Categorize, don't answer. The engine surfaces precedent and runs verifiers; it does not generate verdicts.",
            "Read the elimination trail — the trail is the reasoning.",
            "Every card carries its source. Every claim has 2-3 witnesses (Deut 19:15).",
            "Government sources cannot witness themselves.",
            "Operator approves consequential transitions. Free use, alignment to execute.",
            "Free to call. No accounts required. No tracking.",
        ],
    }
    return snapshot


def _get_snapshot() -> Dict[str, Any]:
    """Cached snapshot with TTL + dir-mtime + single-flight rebuild."""
    now = time.time()
    if _CACHE["snapshot"] is not None and (now - _CACHE["checked_at"]) < _CACHE_TTL:
        return _CACHE["snapshot"]
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _CACHE["snapshot"] is not None and abs(dir_mtime - _CACHE["dir_mtime"]) < 1.0:
        _CACHE["checked_at"] = now
        return _CACHE["snapshot"]
    with _LOCK:
        now2 = time.time()
        if _CACHE["snapshot"] is not None and (now2 - _CACHE["checked_at"]) < _CACHE_TTL:
            return _CACHE["snapshot"]
        _CACHE["snapshot"] = _build_snapshot()
        _CACHE["dir_mtime"] = dir_mtime
        _CACHE["checked_at"] = time.time()
    return _CACHE["snapshot"]


def warm_cache():
    """Prime the daily-agent-feed cache. Called by periodic warmer."""
    try:
        s = _get_snapshot()
        return {"warmed": True, "total_cards": s.get("substrate", {}).get("total_cards", 0)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/agents/daily.json")
    def agents_daily():
        return _get_snapshot()

    @router.get("/agents/feed.json")
    def agents_feed():
        # Alias — same payload, different conventional URL
        return _get_snapshot()

    return router
