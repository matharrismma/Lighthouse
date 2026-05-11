"""
Concordance Wisdom Engine — FastAPI server.

Endpoints:
  POST /validate          Submit a packet for validation. Result is written to ledger.
  GET  /ledger            Recent ledger entries (newest first).
  GET  /ledger/{id}       All ledger entries for a specific packet_id.
  GET  /ledger/verify     Verify the full hash chain (tamper detection).
  GET  /health            Liveness check.
  GET  /                  API info.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("concordance.app")

# Bounded pool for peer broadcast — prevents unbounded thread creation.
_BROADCAST_POOL = ThreadPoolExecutor(max_workers=10, thread_name_prefix="peer-broadcast")

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# -- Engine import -------------------------------------------------------
# The concordance-engine package is installed from pyproject.toml at repo root.
# CONCORDANCE_ENGINE_PATH env var can also point to a local src/ tree as fallback.
_engine_path = os.environ.get("CONCORDANCE_ENGINE_PATH")
if _engine_path:
    sys.path.insert(0, str(Path(_engine_path) / "src"))

try:
    from concordance_engine.engine import (
        validate_packet, validate_and_seal, EngineConfig,
    )
    from concordance_engine.validate import compute_packet_hash
    from concordance_engine.witness_record import (
        Anchor, ClosestCase, WitnessRecord,
        bind_subject,
    )
    from concordance_engine.walkthrough import (
        render_walkthrough, render_walkthrough_html,
        render_walkthrough_compact,
    )
    from concordance_engine.nl_to_packet import parse as nl_parse
    _ENGINE_AVAILABLE = True
    _ENGINE_ERROR = None
except ImportError as _e:
    _ENGINE_AVAILABLE = False
    _ENGINE_ERROR = str(_e)

# -- Ledger import -------------------------------------------------------
from api.ledger import get_ledger

# -- Offline queue import ------------------------------------------------
from api.offline_queue import enqueue as _queue_enqueue, queue_stats as _queue_stats, start_retry_thread as _start_retry

# -- Peer registry + trust index -----------------------------------------
from api.peer_registry import (
    register as _peer_register,
    list_peers as _peer_list,
    get_peer as _peer_get,
    update_seen as _peer_update_seen,
)
from api.trust_index import (
    record_confirmation as _trust_record,
    get_trust as _trust_get,
    trust_stats as _trust_stats,
)

# -- Case store import ---------------------------------------------------
from api.case_store import get_case_store

# -- Nostr anchor helper -------------------------------------------------
def _nostr_pubkey_safe() -> str:
    """Return this node's Nostr public key (hex) for /reach.
    Generates + persists the keypair on first call; returns '' on error."""
    try:
        from concordance_engine.nostr_anchor import nostr_pubkey
        return nostr_pubkey()
    except Exception:
        return ""


# -- App setup -----------------------------------------------------------
app = FastAPI(
    title="Concordance",
    description="""
A deterministic verification and decision-recording engine for AI agents.

## When to use this API

Call before:
- Stating a chemical equation, physics relationship, or mathematical result as verified fact
- Committing funds, resources, or authority on behalf of an organization
- Recording any decision that cannot be reversed without significant cost

Do NOT call for conversation, analysis, or any reversible action.

## Four Gates

Every packet passes through these gates in order. First failure stops the chain:

- **RED** — Rejects coercion, unilateral authority, rights violations
- **FLOOR** — Rejects structurally incomplete or internally inconsistent packets
- **BROTHERS** — Quarantines if fewer than 2 witnesses or review window not elapsed
- **GOD** — Records permanently if all prior gates pass

## Agent entry points

- `POST /submit` — unauthenticated submission (use this for agents)
- `POST /validate` — authenticated submission (requires X-Api-Key header)
- `GET /ledger` — permanent verification record (newest first)
- `GET /ledger/verify` — SHA-256 chain integrity check
- `GET /llms.txt` — full tool inventory, packet schema, and examples

## Minimum viable packet

```json
{
  "domain": "governance",
  "witness_count": 2,
  "created_epoch": 1700000000,
  "DECISION_PACKET": {
    "title": "Short label",
    "decision": "The exact action being taken",
    "rationale": "Why this decision is being made",
    "scope": "adapter",
    "red_items": ["No coercion applied", "Acting within authorized role"],
    "floor_items": ["All required parties informed"],
    "way_path": "standard",
    "execution_steps": ["Step 1"],
    "witnesses": ["Alice Johnson", "Bob Smith"],
    "witness_count": 2
  }
}
```

scope: adapter (individual) | local (team) | mesh (cross-team) | canon (org-wide) | kernel (core policy)

On REJECT: read gate_results[i].reasons for the first failed gate and fix those fields.
On QUARANTINE: add witnesses or allow more time, then resubmit.

Source: https://github.com/matharrismma/Lighthouse — Apache 2.0
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Deployment mode gate — must be registered AFTER CORS (outermost wins).
from api.deployment_mode import mode_gate_middleware
app.middleware("http")(mode_gate_middleware)


# -- Visit log -----------------------------------------------------------
# Lightweight, privacy-respecting access log so we can answer the simple
# question "is anyone out there?" without standing up a full analytics
# stack. Stores per-request metadata in append-only JSONL, one file per
# UTC day. We deliberately log only the IP *prefix* (first octet for IPv4,
# first two hex groups for IPv6) so the file is not a PII trove.
import threading as _visit_threading  # idempotent if already imported below

_VISITS_DIR = Path(__file__).parent.parent / "data" / "visits"
_VISITS_DIR.mkdir(parents=True, exist_ok=True)
_VISITS_LOCK = _visit_threading.Lock()

# Paths we skip to keep the log signal-rich. Health pings from the worker
# loop and the static asset firehose would otherwise drown out real visits.
_VISITS_SKIP_EXACT = {
    "/health", "/health/lite", "/health/refresh",
    "/favicon.ico", "/robots.txt",
}
_VISITS_SKIP_PREFIXES = (
    "/static/", "/assets/", "/_next/",
)


def _ip_prefix(ip: str) -> str:
    """Return only the network-prefix portion of an IP. /8 for v4, /32 for v6."""
    if not ip:
        return ""
    if ":" in ip:  # IPv6
        parts = ip.split(":")
        keep = [p for p in parts[:2] if p]
        return ":".join(keep) + "::/32" if keep else "::/32"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.0.0.0/8"
    return ip


def _classify_ua(ua: str, path: str = "") -> str:
    """Bucket UA strings into coarse classes for stats. Path is a
    secondary signal — fake-mozilla scanners that hit known-vulnerability
    paths (wp-*, xmlrpc.php, .env, .git) get classified as scanner regardless
    of the UA they advertise."""
    low = (ua or "").lower()
    bot_markers = (
        "bot", "crawler", "spider", "curl/", "wget/", "python-requests",
        "httpx", "aiohttp", "go-http-client", "node-fetch", "axios",
        "claude", "anthropic", "openai", "gpt", "chatgpt", "perplexity",
        "googleother", "bingbot", "duckduckbot", "slackbot", "twitterbot",
        "facebookexternalhit", "discordbot", "linkedinbot", "telegrambot",
    )
    scanner_path_markers = (
        "wp-includes", "wp-admin", "wp-content", "wp-login",
        "xmlrpc.php", "/.env", "/.git/", "/.aws/", "/phpmyadmin",
        "/admin.php", "/setup.php", "/shell.php", "/eval(",
    )
    p_low = (path or "").lower()
    if any(m in p_low for m in scanner_path_markers):
        return "scanner"
    if not ua:
        return "unknown"
    if any(m in low for m in bot_markers):
        return "agent"
    if any(b in low for b in ("mozilla", "safari", "chrome", "firefox", "edge", "opera")):
        return "human"
    return "other"


def _record_visit(record: dict) -> None:
    """Append one visit record to today's JSONL file."""
    try:
        day = time.strftime("%Y%m%d", time.gmtime(record.get("ts", time.time())))
        path = _VISITS_DIR / f"access-{day}.jsonl"
        with _VISITS_LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging break a real request


@app.middleware("http")
async def _access_log_middleware(request: Request, call_next):
    started = time.time()
    path = request.url.path
    skip = path in _VISITS_SKIP_EXACT or any(path.startswith(p) for p in _VISITS_SKIP_PREFIXES)

    response = await call_next(request)

    # Engine attribution headers on every response. When an agent calls the
    # engine and surfaces the response to its user, these carry the URL forward
    # — "X-Engine-URL" in particular shows up in any HTTP client log. Compounds
    # discovery without anyone having to post about us.
    response.headers["X-Engine"] = "Concordance"
    response.headers["X-Engine-URL"] = "https://narrowhighway.com"
    response.headers["X-Engine-Manifest"] = "https://narrowhighway.com/manifest"
    response.headers["X-Engine-License"] = "Apache-2.0"

    if skip:
        return response
    try:
        # Honour Cloudflare / proxy headers when present, fall back to socket peer.
        client_ip = (
            request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "")
        )
        ua = request.headers.get("user-agent", "")[:240]
        ref = request.headers.get("referer", "")[:240]
        country = request.headers.get("cf-ipcountry", "")[:8]
        record = {
            "ts": int(started),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "method": request.method,
            "path": path[:240],
            "status": int(getattr(response, "status_code", 0) or 0),
            "ms": int((time.time() - started) * 1000),
            "ip_prefix": _ip_prefix(client_ip),
            "ua": ua,
            "ua_class": _classify_ua(ua, path),
            "referer": ref,
            "country": country,
        }
        _record_visit(record)
    except Exception:
        pass
    return response


def _read_visits_for_days(days: int = 7, limit: int | None = None) -> list[dict]:
    """Read up to `days` worth of visit files, newest first."""
    out: list[dict] = []
    now = time.time()
    for d in range(days):
        day = time.strftime("%Y%m%d", time.gmtime(now - d * 86400))
        path = _VISITS_DIR / f"access-{day}.jsonl"
        if not path.exists():
            continue
        try:
            for line in path.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
    out.sort(key=lambda r: r.get("ts", 0), reverse=True)
    if limit is not None:
        out = out[:limit]
    return out


@app.get("/visits/recent", tags=["visits"])
def visits_recent(limit: int = 50, days: int = 7):
    """Return the most recent visit records (privacy-scrubbed)."""
    limit = max(1, min(500, int(limit)))
    days = max(1, min(60, int(days)))
    rows = _read_visits_for_days(days=days, limit=limit)
    return {"count": len(rows), "days": days, "limit": limit, "entries": rows}


@app.get("/visits/stats", tags=["visits"])
def visits_stats(days: int = 7):
    """Aggregate counts by ua_class, country, path, and status."""
    days = max(1, min(60, int(days)))
    rows = _read_visits_for_days(days=days)
    by_class: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_path: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_day: dict[str, int] = {}
    unique_prefixes: set[str] = set()
    unique_external_prefixes: set[str] = set()
    for r in rows:
        cls = r.get("ua_class", "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
        ctry = r.get("country") or "—"
        by_country[ctry] = by_country.get(ctry, 0) + 1
        p = r.get("path", "")
        by_path[p] = by_path.get(p, 0) + 1
        st = str(r.get("status", 0))
        by_status[st] = by_status.get(st, 0) + 1
        day = (r.get("ts_iso") or "")[:10]
        if day:
            by_day[day] = by_day.get(day, 0) + 1
        ipx = r.get("ip_prefix") or ""
        if ipx:
            unique_prefixes.add(ipx)
            if not ipx.startswith("127.") and not ipx.startswith("0.0.0.0") and ipx not in ("::/32",):
                unique_external_prefixes.add(ipx)

    def _top(d: dict, n: int = 15) -> list:
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]

    return {
        "days": days,
        "total_requests": len(rows),
        "unique_ip_prefixes": len(unique_prefixes),
        "external_ip_prefixes": len(unique_external_prefixes),
        "by_ua_class": by_class,
        "by_country": dict(_top(by_country, 25)),
        "by_path_top": dict(_top(by_path, 25)),
        "by_status": by_status,
        "by_day": dict(sorted(by_day.items())),
        "skipped_paths_note": "health pings + static assets are not logged",
    }


# -- Community participation ----------------------------------------------
# Contributors, badges, witness signals, activity feed. All read endpoints
# unlimited; write endpoints rate-limited via the existing token bucket.
from api import community as _community  # noqa: E402

from pydantic import BaseModel as _CommBaseModel


class _RegisterRequest(_CommBaseModel):
    handle: str
    display_name: str = ""
    bio: str = ""
    user_pubkey: str = ""


class _WitnessRequest(_CommBaseModel):
    witness_handle: str
    proposal_id: str
    proposal_author: str = ""
    note: str = ""


@app.post("/community/register", tags=["community"])
def community_register(request: Request, req: _RegisterRequest):
    """Register a contributor handle. Handles are public pseudonyms;
    no password, no email required. The optional user_pubkey ties the
    handle to an Ed25519 key for later signed contributions."""
    _rate_check(request, "register")
    handle = (req.handle or "").strip().lower()
    ok, msg, record = _community.register_contributor(
        handle=handle,
        display_name=req.display_name,
        bio=req.bio,
        user_pubkey=req.user_pubkey,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "contributor": _community.public_profile(record)}


@app.get("/badge/{handle}.svg", include_in_schema=False)
def community_badge_svg(handle: str):
    """Embeddable SVG badge for a contributor handle.

    Designed for sites like:
        <a href="https://narrowhighway.com/contributor.html?h=foxfire_kid">
          <img src="https://narrowhighway.com/badge/foxfire_kid.svg"
               alt="Verified by Concordance"></a>

    Every embed is a backlink. Compounds without anyone posting.
    Width adapts to content: tier label + badge count."""
    _safe_id(handle, "handle")
    handle = handle.lower()
    record = _community.load_contributor(handle)
    from fastapi.responses import Response

    if record is None:
        # Render a generic "Verified by Concordance" badge so a misspelled
        # handle still produces something rather than 404
        svg = _render_badge_svg(left="verified by", right="Concordance",
                                right_color="#d4a872", subtitle="")
    else:
        prof = _community.public_profile(record)
        tier = (prof.get("tier_label") or "Witness").lower()
        badges = prof.get("badge_count", 0)
        svg = _render_badge_svg(
            left=f"@{handle}",
            right=f"{tier} · {badges} badges",
            right_color="#d4a872" if tier != "curator" else "#f0c896",
            subtitle="concordance",
        )

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "max-age=300, public"},
    )


def _render_badge_svg(left: str, right: str, right_color: str, subtitle: str) -> str:
    """Generate a Shields.io-style flat badge as inline SVG.

    Two compartments: left (handle), right (status). Total width
    computed from char count so the badge fits its contents."""
    from xml.sax.saxutils import escape as _xml_esc
    L_PAD = 7
    R_PAD = 7
    CHAR_W = 6.6   # Inter / system-sans approximation at 11px
    left_w  = int(len(left) * CHAR_W + 2 * L_PAD)
    right_w = int(len(right) * CHAR_W + 2 * R_PAD)
    total_w = left_w + right_w
    h = 22

    # Slight bottom shadow for depth
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{h}" viewBox="0 0 {total_w} {h}" role="img" aria-label="{_xml_esc(left)} {_xml_esc(right)}">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a"><rect width="{total_w}" height="{h}" rx="4" fill="#fff"/></clipPath>
  <g clip-path="url(#a)">
    <path fill="#1d191f" d="M0 0h{left_w}v{h}H0z"/>
    <path fill="{right_color}" d="M{left_w} 0h{right_w}v{h}H{left_w}z"/>
    <path fill="url(#b)" d="M0 0h{total_w}v{h}H0z"/>
  </g>
  <g fill="#efe9e0" text-anchor="middle"
     font-family="Inter,Segoe UI,Helvetica,Arial,sans-serif" font-size="11" font-weight="500">
    <text x="{left_w/2}" y="15">{_xml_esc(left)}</text>
    <text x="{left_w + right_w/2}" y="15" fill="#1a1208" font-weight="600">{_xml_esc(right)}</text>
  </g>
</svg>"""


@app.get("/community/contributor/{handle}", tags=["community"])
def community_contributor_profile(handle: str):
    _safe_id(handle, "handle")
    record = _community.load_contributor(handle.lower())
    if record is None:
        raise HTTPException(status_code=404, detail=f"no contributor {handle!r}")
    return _community.public_profile(record)


@app.get("/community/contributors", tags=["community"])
def community_contributors_leaderboard(
    sort: str = Query("rank", description="rank | recent | witnesses | proposals | polymathic"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Leaderboard. Sorted by tier rank then badge count by default."""
    if sort not in ("rank", "recent", "witnesses", "proposals", "polymathic"):
        raise HTTPException(status_code=400, detail=f"unknown sort: {sort!r}")
    rows = _community.list_contributors(sort=sort, limit=limit, offset=offset)
    return {
        "count": len(rows),
        "total_contributors": _community.total_contributors(),
        "sort": sort,
        "contributors": rows,
    }


@app.get("/community/badges", tags=["community"])
def community_badge_catalog():
    """All badges and the tiers they unlock."""
    return {
        "tiers": _community.TIERS,
        "badges": _community.BADGES,
    }


@app.get("/community/activity", tags=["community"])
def community_activity_feed(
    limit: int = Query(50, ge=1, le=500),
    days: int = Query(7, ge=1, le=60),
):
    """Recent community activity events (newest first)."""
    events = _community.read_activity(days=days, limit=limit)
    return {"count": len(events), "days": days, "events": events}


@app.post("/community/witness", tags=["community"])
def community_witness_signal(request: Request, req: _WitnessRequest):
    """Record a witness signal on a proposal. The witness must be a
    registered contributor; their handle accumulates `witnesses_given`,
    and (if the proposal_author is a registered handle) that author
    accumulates `witnesses_received`."""
    _rate_check(request, "witness_signal")
    witness_handle = (req.witness_handle or "").strip().lower()
    proposal_author = (req.proposal_author or "").strip().lower()
    proposal_id = (req.proposal_id or "").strip()[:120]
    if not proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id is required")
    ok, msg = _community.record_witness(
        witness_handle=witness_handle,
        proposal_id=proposal_id,
        proposal_author=proposal_author,
        note=req.note,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True}


class _AcceptRequest(_CommBaseModel):
    """Curator marks a contributor's proposal as accepted into the canon."""
    contributor_handle: str
    proposal_id: str
    almanac_entry_id: str = ""   # the id under which it landed in the book
    note: str = ""


def _community_require_api_key(request: Request) -> None:
    """Inline equivalent of _check_api_key — used by community admin
    endpoints that are defined before _check_api_key in the module.
    Reads X-API-Key header and compares against the API_KEY env var.
    If API_KEY is unset, auth is disabled (dev mode)."""
    expected = os.environ.get("API_KEY", "")
    if not expected:
        return
    got = request.headers.get("x-api-key", "") or request.headers.get("X-API-Key", "")
    if got != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.post("/community/proposals/accept", tags=["community"])
def community_proposal_accept(
    request: Request,
    req: _AcceptRequest,
):
    """Curator endpoint — credit a contributor for an accepted proposal.

    Bumps the contributor's `proposals_accepted` stat and re-evaluates
    badges. Emits a `proposal_accepted` activity event so the dashboard
    feed surfaces canonical acceptances, not just submissions.

    Requires the X-API-Key header — only the operator (and anyone the
    operator has shared the key with) can mark canon."""
    _community_require_api_key(request)
    handle = (req.contributor_handle or "").strip().lower()
    if not _community.is_valid_handle(handle):
        raise HTTPException(status_code=400, detail="contributor_handle invalid")
    if _community.load_contributor(handle) is None:
        raise HTTPException(status_code=404, detail=f"no contributor {handle!r}")
    pid = (req.proposal_id or "").strip()[:120]
    if not pid:
        raise HTTPException(status_code=400, detail="proposal_id is required")

    record = _community.bump_stat(handle, "proposals_accepted", 1)
    _community.log_activity({
        "kind": "proposal_accepted",
        "handle": handle,
        "proposal_id": pid,
        "almanac_entry_id": (req.almanac_entry_id or "")[:120],
        "note": (req.note or "")[:200],
    })
    return {"ok": True, "contributor": _community.public_profile(record) if record else None}


class _CuratorPromoteRequest(_CommBaseModel):
    """Operator-only endpoint to grant the Curator tier."""
    handle: str


@app.post("/community/curator/grant", tags=["community"])
def community_grant_curator(
    request: Request,
    req: _CuratorPromoteRequest,
):
    """Promote a contributor to Curator tier. API-key gated."""
    _community_require_api_key(request)
    handle = (req.handle or "").strip().lower()
    rec = _community.load_contributor(handle)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no contributor {handle!r}")
    rec["curator"] = True
    # Persist + refresh badges (this awards curator:appointed)
    from api.community import _save_contributor as _sc, _refresh_badges as _rb
    _sc(rec)
    _rb(rec)
    return {"ok": True, "contributor": _community.public_profile(_community.load_contributor(handle))}


@app.get("/dashboard/stats", tags=["community"])
def dashboard_stats():
    """Single aggregated stats blob for the activity dashboard. Reads
    visits, ledger summary, almanac entries, swarm status, contributors
    in one call so the dashboard can render in a single round-trip."""
    out: Dict[str, Any] = {
        "now": int(time.time()),
        "now_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Visits (today + 7-day rollup)
    try:
        today_rows = _read_visits_for_days(days=1)
        week_rows = _read_visits_for_days(days=7)
        ext_today = sum(1 for r in today_rows
                        if not (r.get("ip_prefix", "") or "").startswith(("127.", "0.0.0")))
        out["visits"] = {
            "today_total": len(today_rows),
            "today_external": ext_today,
            "week_total": len(week_rows),
            "by_ua_class_week": _bucket(week_rows, "ua_class"),
            "by_country_week_top": dict(sorted(
                _bucket(week_rows, "country").items(),
                key=lambda kv: kv[1], reverse=True
            )[:8]),
        }
    except Exception as exc:
        out["visits"] = {"error": str(exc)[:200]}

    # Ledger summary
    try:
        led = get_ledger()
        ent = list(led.iter_filtered(limit=10000))
        by_overall: Dict[str, int] = {}
        for e in ent:
            v = e.get("overall", "?")
            by_overall[v] = by_overall.get(v, 0) + 1
        out["ledger"] = {
            "total_entries": len(ent),
            "by_overall": by_overall,
            "latest_iso": ent[0].get("timestamp_iso", "") if ent else "",
        }
    except Exception as exc:
        out["ledger"] = {"error": str(exc)[:200]}

    # Almanac
    try:
        entries = _almanac_entries()
        by_kind: Dict[str, int] = {}
        by_verdict: Dict[str, int] = {}
        for e in entries:
            by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
            by_verdict[e.get("verdict", "?")] = by_verdict.get(e.get("verdict", "?"), 0) + 1
        out["almanac"] = {
            "total_entries": len(entries),
            "by_kind": by_kind,
            "by_verdict": by_verdict,
        }
    except Exception as exc:
        out["almanac"] = {"error": str(exc)[:200]}

    # Community
    try:
        out["community"] = {
            "total_contributors": _community.total_contributors(),
            "leaderboard_top5": _community.list_contributors(sort="rank", limit=5),
            "recent_activity": _community.read_activity(days=7, limit=20),
        }
    except Exception as exc:
        out["community"] = {"error": str(exc)[:200]}

    # Swarm — small rollup, not the full status (dashboard polls /swarm directly for the rest)
    try:
        out["swarm"] = {
            "synthesist_patterns": int(_synthesist_state.get("patterns_total", 0)) if "_synthesist_state" in globals() else 0,
            "miner_candidates": int(_miner_stats().get("candidates_total", 0)) if "_miner_stats" in globals() else 0,
        }
    except Exception:
        pass

    return out


def _bucket(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    """Tiny aggregator helper for /dashboard/stats."""
    out: Dict[str, int] = {}
    for r in rows:
        v = r.get(key) or "—"
        out[v] = out.get(v, 0) + 1
    return out


@app.on_event("startup")
def _startup():
    _start_retry(interval_seconds=30)


@app.on_event("shutdown")
def _shutdown():
    from api.offline_queue import stop_retry_thread
    stop_retry_thread()
    _BROADCAST_POOL.shutdown(wait=False)

# -- Optional API key auth -----------------------------------------------
_API_KEY = os.environ.get("API_KEY", "")

def _check_api_key(x_api_key: str = Header(default="")) -> None:
    """Reject requests that don't carry the correct API key.
    If API_KEY env var is not set, auth is disabled (dev mode).
    """
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# -- Path-component sanitizers ------------------------------------------
# Every endpoint that takes a URL path parameter and uses it to build a
# filename, dict key, or JSONL search path runs the value through one of
# these helpers first. They reject path-traversal sequences (`..`),
# directory separators (`/`, `\`), null bytes, and any character outside
# the documented charset for the param. The handler raises 400 on
# rejection rather than silently failing, so probes show up in logs.

_SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_:.\-]{1,200}$')
_SAFE_HASH_RE = re.compile(r'^[a-fA-F0-9]{6,128}$')
_SAFE_DOMAIN_RE = re.compile(r'^[a-z][a-z0-9_]{0,40}$')
_SAFE_RECIPIENT_RE = re.compile(r'^[A-Za-z0-9_@.\-]{1,120}$')


def _safe_id(value: str, name: str = "id") -> str:
    """Validate an opaque URL id (entry_id, packet_id, bin_id, etc.).
    Allows letters, digits, underscore, hyphen, colon, and period. No
    slashes, no dots-only sequences, no nulls."""
    if not value or ".." in value or value in (".",) or "\x00" in value:
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    if not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    return value


def _safe_hash(value: str, name: str = "content_hash") -> str:
    """Validate a hex content hash (6-128 hex chars)."""
    if not value or not _SAFE_HASH_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    return value


def _safe_domain(value: str, name: str = "domain") -> str:
    """Validate a domain name (lowercase letters, digits, underscore)."""
    if not value or not _SAFE_DOMAIN_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    return value


def _safe_recipient(value: str, name: str = "recipient") -> str:
    """Validate a recipient identifier (letters, digits, dot, hyphen, @ )."""
    if not value or ".." in value or "\x00" in value:
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    if not _SAFE_RECIPIENT_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")
    return value

# -- Front-end session auth (passphrase + invite codes) ------------------
# Scope: governs who sees the dashboard. Does NOT apply to existing
# API/agent endpoints (/validate, /seal, /path, verifiers, etc.) —
# those keep their own X-Api-Key auth. BROTHERS gate applies only at
# the record boundary (POST /seal, /confess) and between parties
# (federation), not to internal sandbox operations.

_PASSPHRASE = os.environ.get("CONCORDANCE_PASSPHRASE", "")
_SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Normalize before hashing so "He is risen indeed!", "He is risen indeed",
# and "HE IS RISEN INDEED" all resolve to the same digest.
def _norm_phrase(p: str) -> str:
    import re
    return re.sub(r"[^\w\s]", "", p.lower()).strip()

# Primary passphrase plus any comma-separated alternates in CONCORDANCE_PASSPHRASE_ALTS.
_VALID_HASHES: set[str] = set()
if _PASSPHRASE:
    _VALID_HASHES.add(hashlib.sha256(_norm_phrase(_PASSPHRASE).encode()).hexdigest())
for _alt in os.environ.get("CONCORDANCE_PASSPHRASE_ALTS", "").split(","):
    _alt = _alt.strip()
    if _alt:
        _VALID_HASHES.add(hashlib.sha256(_norm_phrase(_alt).encode()).hexdigest())
# Keep legacy single-hash ref so _verify_token dev-mode check still works.
_PASSPHRASE_HASH = next(iter(_VALID_HASHES)) if _VALID_HASHES else ""

_AUTH_DIR = (
    Path(os.environ.get("CONCORDANCE_DATA_DIR", "~/.concordance")).expanduser()
    / "auth"
)


def _make_token(user_id: str) -> str:
    expiry = int(time.time()) + 86400
    payload = f"{user_id}|{expiry}"
    sig = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _verify_token(token: str) -> bool:
    if not token or not _VALID_HASHES:
        return True  # dev mode — no passphrase configured
    try:
        *payload_parts, sig = token.split("|")
        payload = "|".join(payload_parts)
        expected = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        user_id, expiry_str = payload_parts[0], payload_parts[1]  # noqa: F841
        return int(expiry_str) >= int(time.time())
    except Exception:
        return False


def _load_invites() -> dict:
    try:
        if _AUTH_DIR.joinpath("invites.json").exists():
            return json.loads(_AUTH_DIR.joinpath("invites.json").read_text())
    except Exception:
        pass
    return {}


def _save_invites(invites: dict) -> None:
    try:
        _AUTH_DIR.mkdir(parents=True, exist_ok=True)
        _AUTH_DIR.joinpath("invites.json").write_text(json.dumps(invites, indent=2))
    except Exception:
        pass


class LoginRequest(BaseModel):
    passphrase: str


class InviteCreateRequest(BaseModel):
    name: str
    role: str = ""
    uses: int = 1
    expires_days: int = 7


class RedeemRequest(BaseModel):
    code: str


class AccessRequest(BaseModel):
    text: str
    contact: str = ""


def _require_session(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


@app.post("/auth/login", tags=["auth"])
def auth_login(request: Request, req: LoginRequest):
    # Brute-force protection: 5 attempts per minute per IP.
    _rate_check(request, "login")
    if not _VALID_HASHES:
        return {"token": _make_token("dev"), "expires_in": 86400}
    incoming = hashlib.sha256(_norm_phrase(req.passphrase).encode()).hexdigest()
    if not any(hmac.compare_digest(incoming, h) for h in _VALID_HASHES):
        raise HTTPException(status_code=401, detail="Incorrect passphrase")
    return {"token": _make_token("operator"), "expires_in": 86400}


@app.get("/auth/verify", tags=["auth"])
def auth_verify(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return {"status": "ok"}


@app.post("/auth/logout", tags=["auth"])
def auth_logout():
    return {"status": "logged_out"}


@app.post("/auth/invite", tags=["auth"])
def auth_invite(req: InviteCreateRequest, _: str = Depends(_require_session)):
    code = secrets.token_urlsafe(9)
    invites = _load_invites()
    invites[code] = {
        "name": req.name,
        "role": req.role,
        "uses": req.uses,
        "used": 0,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + req.expires_days * 86400,
    }
    _save_invites(invites)
    return {"code": code, "name": req.name, "expires_days": req.expires_days}


@app.post("/auth/redeem", tags=["auth"])
def auth_redeem(req: RedeemRequest):
    invites = _load_invites()
    invite = invites.get(req.code)
    if not invite:
        raise HTTPException(status_code=401, detail="Code not recognized")
    if invite["expires_at"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Code expired")
    if invite["uses"] != -1 and invite["used"] >= invite["uses"]:
        raise HTTPException(status_code=401, detail="Code already used")
    invite["used"] += 1
    _save_invites(invites)
    return {"token": _make_token(invite["name"]), "expires_in": 86400, "name": invite["name"]}


@app.post("/auth/request", tags=["auth"])
def auth_request(req: AccessRequest):
    try:
        _AUTH_DIR.mkdir(parents=True, exist_ok=True)
        requests_file = _AUTH_DIR / "access_requests.jsonl"
        with open(requests_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "text": req.text,
                "contact": req.contact,
                "created_at": int(time.time()),
            }) + "\n")
    except Exception:
        pass
    return {"status": "received"}


# -- Schema discovery ----------------------------------------------------
_SCHEMA_PATH_ENV = os.environ.get("CONCORDANCE_SCHEMA_PATH")
_SCHEMA_PATH: Optional[Path] = None
if _SCHEMA_PATH_ENV:
    _SCHEMA_PATH = Path(_SCHEMA_PATH_ENV)
else:
    # Default: schema/ at repo root (works in Docker)
    candidate = Path(__file__).parent.parent / "schema" / "packet.schema.json"
    if candidate.exists():
        _SCHEMA_PATH = candidate


def _make_config() -> "EngineConfig":
    schema = str(_SCHEMA_PATH) if _SCHEMA_PATH and _SCHEMA_PATH.exists() else ""
    return EngineConfig(schema_path=schema, run_verifiers=True)


# -- Request / Response models -------------------------------------------
class ValidateRequest(BaseModel):
    packet: Dict[str, Any]
    now_epoch: Optional[int] = None
    run_verifiers: bool = True


class SealRenderRequest(BaseModel):
    """Body for `POST /seal/render` — the human-form pipeline.

    Accepts a natural-language claim, routes it through nl_to_packet
    to build a real packet, runs validate_and_seal, and returns both
    the WitnessRecord JSON and a pre-rendered Socratic walkthrough
    (markdown or HTML, caller's choice). The front-end can drop the
    walkthrough into a div without re-implementing the renderer.
    """
    text: str
    format: str = "html"  # "html" | "markdown" | "compact"
    expand_traces: bool = False


class SealRequest(BaseModel):
    """Body for `POST /seal` — the canonical sealed-record endpoint.

    Identical to ValidateRequest but carries the optional rendering-
    layer concerns (anchors, closest_case, packet_id) that turn a bare
    EngineResult into a full WitnessRecord. Anchors are dicts of shape
    {ref, layer, text?}; closest_case is a dict of shape {precedent_id,
    shared_dimensions?, shared_anchors?, distance?, reasoning_overlay?}.
    Both default to absent/empty rather than fabricated.

    `witness_tier` controls receipt strength:
      "standard"  — engine gate verdicts only (default)
      "quantum"   — reserved; routes to quantum-encrypted witness path
                    when the Rossville quantum node is available
    `bind_subject` — if True (default), automatically binds the instance
                    user's Ed25519 public key so the receipt is soulbound
                    to this person's private key.
    """
    packet: Dict[str, Any]
    now_epoch: Optional[int] = None
    run_verifiers: bool = True
    anchors: Optional[List[Dict[str, Any]]] = None
    closest_case: Optional[Dict[str, Any]] = None
    packet_id: Optional[str] = None
    witness_tier: str = "standard"   # "standard" | "quantum"
    bind_subject: bool = True        # auto-bind user Ed25519 pubkey


class GateResultOut(BaseModel):
    gate: str
    status: str
    reasons: List[str]
    details: Optional[Dict[str, Any]] = None


class ValidateResponse(BaseModel):
    overall: str
    gate_results: List[GateResultOut]
    ledger_seq: Optional[int] = None
    ledger_entry_hash: Optional[str] = None
    packet_hash: str
    elapsed_ms: float


class LedgerEntryOut(BaseModel):
    seq: int
    timestamp_iso: str
    timestamp_epoch: int
    packet_id: str
    domain: str
    overall: str
    gate_summary: Dict[str, str]
    top_reasons: List[str]
    packet_hash: str
    prev_hash: str
    entry_hash: str


class LedgerListResponse(BaseModel):
    entries: List[LedgerEntryOut]
    count: int


class ChainVerifyResponse(BaseModel):
    valid: bool
    entries_checked: int
    first_broken_seq: Optional[int]
    message: str


# -- Routes --------------------------------------------------------------

@app.get("/llms.txt", include_in_schema=False)
def llms_txt():
    """AI-readable service description for agent discovery (llms.txt standard)."""
    f = Path(__file__).parent.parent / "site" / "llms.txt"
    if f.exists():
        return FileResponse(str(f), media_type="text/plain")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("llms.txt not found", status_code=404)


@app.get("/", include_in_schema=False)
def root():
    index = Path(__file__).parent.parent / "site" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "name": "Concordance Engine API",
        "version": "1.0.0",
        "engine_available": _ENGINE_AVAILABLE,
        "docs": "/docs",
        "endpoints": {
            "validate": "POST /validate",
            "submit": "POST /submit",
            "ledger": "GET /ledger",
            "ledger_by_id": "GET /ledger/{packet_id}",
            "chain_verify": "GET /ledger/verify",
            "health": "GET /health",
        },
    }


# ─────────────────────────────────────────────────────────────────────
# /health — rebuilt
#
# The previous implementation did the slow work (walking 21k-entry
# JournalStore + KeepingLog) in the request path on every cache miss.
# A cold cache hit took 12-18s, regularly tripping client timeouts.
#
# New design: a background thread refreshes a counter snapshot every
# 30 seconds. /health serves the snapshot in O(1). Stale-by-design.
#
# Three endpoints:
#   GET /health        — same shape as before, served from snapshot
#   GET /health/lite   — pure liveness, no module dict, sub-ms
#   POST /health/refresh — force one refresh (admin tool)
# ─────────────────────────────────────────────────────────────────────

_HEALTH_REFRESH_PERIOD_S = 30
_health_snapshot: Dict[str, Any] = {
    "started_at": None,
    "last_refreshed": None,           # epoch of most recent successful refresh
    "last_refresh_duration_s": None,
    "refresh_count": 0,
    "error_count": 0,
    "last_error": None,
    "engine_available": _ENGINE_AVAILABLE,
    "ledger_entries": 0,
    # Per-module sub-snapshots — populated by the worker, never by request handlers.
    "journal":       {"reachable": False, "warming": True},
    "keeping":       {"reachable": False, "warming": True},
    "quarantine":    {"reachable": False, "warming": True},
    "verifiers":     {"reachable": False, "warming": True},
    "offline_queue": {"reachable": False, "warming": True},
    "trust_index":   {"reachable": False, "warming": True},
}


def _health_refresh_once() -> None:
    """One full module sweep. Slow (10-20s for 21k journal). Called
    by the background thread, NEVER by request handlers."""
    import time as _time
    started = _time.time()
    new_snapshot: Dict[str, Any] = {}

    # Audit chain
    try:
        ledger = get_ledger()
        recent = ledger.recent(n=1)
        new_snapshot["ledger_entries"] = recent[0].get("seq") if recent else 0
    except Exception as exc:
        new_snapshot["ledger_entries"] = 0
        _health_snapshot["last_error"] = f"ledger: {str(exc)[:160]}"

    if _ENGINE_AVAILABLE:
        try:
            from concordance_engine.journal import JournalStore
            store = JournalStore()
            entries = store.list_all()
            new_snapshot["journal"] = {
                "reachable": True,
                "total_entries": len(entries),
                "shelf_count": sum(1 for e in entries if "shelf" in (e.user_tags or [])),
            }
        except Exception as exc:
            new_snapshot["journal"] = {"reachable": False, "error": str(exc)[:160]}

        try:
            from concordance_engine.keeping import KeepingLog
            log = KeepingLog()
            observations = log.read()
            new_snapshot["keeping"] = {
                "reachable": True,
                "total_observations": len(observations),
                "practices_observed": len({o.practice for o in observations}),
            }
        except Exception as exc:
            new_snapshot["keeping"] = {"reachable": False, "error": str(exc)[:160]}

        try:
            from concordance_engine.quarantine import QuarantineStore
            qstore = QuarantineStore()
            new_snapshot["quarantine"] = {
                "reachable": True,
                "total_packets": len(qstore.list_all()),
            }
        except Exception as exc:
            new_snapshot["quarantine"] = {"reachable": False, "error": str(exc)[:160]}

        try:
            _domains = ["chemistry", "mathematics", "physics", "scripture", "phase"]
            lit = []
            for d in _domains:
                try:
                    __import__(f"concordance_engine.verifiers.{d}")
                    lit.append(d)
                except Exception:
                    pass
            new_snapshot["verifiers"] = {
                "reachable": True,
                "lit_count": len(lit),
                "lit": lit,
            }
        except Exception as exc:
            new_snapshot["verifiers"] = {"reachable": False, "error": str(exc)[:160]}

    try:
        q = _queue_stats()
        pending = q.get("pending", 0)
        oq = {
            "reachable": True,
            "pending": pending,
            "failed": q.get("failed", 0),
            "completed": q.get("completed", 0),
        }
        if pending > 500:
            oq["warning"] = "high queue depth"
        new_snapshot["offline_queue"] = oq
    except Exception as exc:
        new_snapshot["offline_queue"] = {"reachable": False, "error": str(exc)[:160]}

    try:
        from api.trust_index import trust_stats
        new_snapshot["trust_index"] = {"reachable": True, **trust_stats()}
    except Exception as exc:
        new_snapshot["trust_index"] = {"reachable": False, "error": str(exc)[:160]}

    # Atomic-ish swap of the published snapshot
    for k, v in new_snapshot.items():
        _health_snapshot[k] = v
    _health_snapshot["last_refreshed"] = _time.time()
    _health_snapshot["last_refresh_duration_s"] = round(_time.time() - started, 2)
    _health_snapshot["refresh_count"] += 1


def _health_refresh_worker() -> None:
    """Background loop. Refreshes the snapshot every 30s. Errors
    don't crash the loop — they bump error_count and continue."""
    import time as _time
    if _health_snapshot["started_at"] is None:
        _health_snapshot["started_at"] = _time.time()
    # Tiny startup delay so first refresh runs after the rest of the
    # app has finished importing, not in parallel with it.
    _time.sleep(2)
    while True:
        try:
            _health_refresh_once()
        except Exception as exc:
            _health_snapshot["error_count"] += 1
            _health_snapshot["last_error"] = str(exc)[:200]
            _log.warning(f"health refresh error: {exc}")
        _time.sleep(_HEALTH_REFRESH_PERIOD_S)


@app.get("/health/lite")
def health_lite():
    """Pure liveness. Sub-ms. Use this for Cloudflare/uptime probes.

    No module dict, no store walks, no possibility of timeout.
    Says 'process responding, here is the version, here is the
    snapshot age.' That's all."""
    import time as _time
    last = _health_snapshot.get("last_refreshed")
    return {
        "status": "ok",
        "engine_available": _ENGINE_AVAILABLE,
        "timestamp": int(_time.time()),
        "snapshot_age_s": round(_time.time() - last, 1) if last else None,
        "snapshot_warming": last is None,
    }


@app.get("/health")
def health():
    """Engine snapshot — module reachability + counters.

    Served from a background-refreshed snapshot (period: 30s). The
    request path is sub-millisecond — no store walks, no I/O.
    'snapshot_age_s' tells you how stale the data is. Right after a
    bounce, modules show 'warming: true' until the first refresh
    completes (~20s).

    Backward-compatible shape with the previous /health for the
    brain UI and existing consumers.
    """
    import time as _time
    now = _time.time()
    last = _health_snapshot.get("last_refreshed")

    modules = {
        "journal":       _health_snapshot.get("journal", {}),
        "keeping":       _health_snapshot.get("keeping", {}),
        "quarantine":    _health_snapshot.get("quarantine", {}),
        "verifiers":     _health_snapshot.get("verifiers", {}),
        "offline_queue": _health_snapshot.get("offline_queue", {}),
        "trust_index":   _health_snapshot.get("trust_index", {}),
    }

    # The high-level status reflects PROCESS health, not snapshot freshness.
    # If the process is up and the engine is loaded, status is 'ok' — even
    # if the first snapshot refresh hasn't completed. Snapshot-readiness
    # is a separate signal (snapshot_ready / snapshot_age_s) so callers
    # who need fresh counters can tell, while monitoring tools probing
    # for liveness see 'ok' immediately.
    out: Dict[str, Any] = {
        "status": "ok",
        "engine_available": _health_snapshot.get("engine_available", False),
        "ledger_entries": _health_snapshot.get("ledger_entries", 0),
        "timestamp": int(now),
        "modules": modules,
        "snapshot_age_s": round(now - last, 1) if last else None,
        "snapshot_period_s": _HEALTH_REFRESH_PERIOD_S,
        "snapshot_refresh_count": _health_snapshot.get("refresh_count", 0),
        "snapshot_ready": last is not None,
    }

    # Mark degraded only after we've had at least one successful refresh
    # AND a module is unreachable post-warm.
    if last and any(
        isinstance(m, dict) and not m.get("reachable", True) and not m.get("warming")
        for m in modules.values()
    ):
        out["status"] = "degraded"

    return out


@app.post("/health/refresh", tags=["agents"])
def health_refresh_now():
    """Force one snapshot refresh now. Useful after a known-state change
    (e.g. a bulk ingest just finished) when you want fresh counters
    before the next scheduled tick.

    Synchronous — blocks for the duration of the refresh (10-20s on
    a populated journal). Returns the freshly-computed snapshot.
    """
    _health_refresh_once()
    return health()


@app.get("/identity")
def identity():
    """Canonical identity statement — what this engine serves.

    Every agent-facing surface reads from the same single source
    (`concordance_engine.IDENTITY`). Plain, present, never hidden.
    The engine flows for legitimate use; what it serves is stated
    up front so callers (human and AI) know.
    """
    if not _ENGINE_AVAILABLE:
        return {
            "serves": "Jesus Christ",
            "statement": (
                "The Concordance Engine at narrowhighway.com serves Jesus Christ. "
                "Engine pipeline not loaded — this is the bare identity surface."
            ),
            "engine_loaded": False,
        }
    from concordance_engine import IDENTITY, IDENTITY_SHORT, __version__
    return {
        "serves": "Jesus Christ",
        "short": IDENTITY_SHORT,
        "statement": IDENTITY,
        "version": __version__,
        "engine_loaded": True,
    }


# ── /speak + /voices — ElevenLabs TTS proxy (optional) ──────────────
#
# Returns audio/mpeg synthesized in the configured voice. Optional in
# every sense: requires `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`
# in the environment; without them the endpoint reports unavailable.
# Nothing else in the engine depends on this — it's a phone-friendly
# surface for hearing precedents read aloud.
#
# Models (ElevenLabs, as of 2026-05):
#   eleven_flash_v2_5       — lowest latency, real-time use
#   eleven_turbo_v2_5       — balanced speed + quality (default)
#   eleven_multilingual_v2  — highest quality, 29 languages


def _el_api_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "")


def _el_voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID", "")


class SpeakRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None  # override env default
    model_id: str = "eleven_turbo_v2_5"


@app.post("/speak", include_in_schema=True)
def speak(request: Request, req: SpeakRequest):
    """Proxy ElevenLabs streaming TTS. Returns audio/mpeg.

    Caller text in, voice out. No transcription, no logging of audio.
    The text is not retained; only the audio stream is returned. Use
    a short prefix of `req.text` (≤80 chars) for any error messages
    so we never echo the full prompt back into logs.

    Rate-limited per-IP at 20/min — ElevenLabs is paid-per-character.
    """
    _rate_check(request, "speak")
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = req.voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise HTTPException(
            status_code=503,
            detail="speak unavailable: ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not configured",
        )
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="text too long (max 5000 chars)")

    # Lazy-import requests so the rest of the API still loads if it's
    # not installed (e.g. minimal deployments).
    try:
        import requests as _requests
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="speak unavailable: `requests` not installed",
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {
        "text": text,
        "model_id": req.model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }

    try:
        r = _requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
    except _requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"upstream tts error: {exc}")

    if r.status_code != 200:
        # Surface upstream status without leaking the API key in error
        # bodies. ElevenLabs sometimes returns JSON, sometimes HTML.
        try:
            detail = r.json()
        except ValueError:
            detail = {"upstream_status": r.status_code, "body_excerpt": r.text[:200]}
        raise HTTPException(status_code=502, detail=detail)

    # Read the full body once. Streaming the response straight through
    # FastAPI is possible but adds complexity; for a typical precedent
    # read-aloud (< 30s of audio), the buffered approach is fine.
    audio_bytes = r.content
    return Response(content=audio_bytes, media_type="audio/mpeg")


@app.get("/voices", include_in_schema=True)
def list_voices():
    """Return available ElevenLabs voices for this instance.

    Proxies the ElevenLabs /v1/voices endpoint so callers can discover
    available voice_ids without leaving the engine API. Returns a
    simplified list: id, name, category, and description only — no raw
    ElevenLabs metadata.

    Returns 503 if ELEVENLABS_API_KEY is not configured.
    """
    api_key = _el_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="voices unavailable: ELEVENLABS_API_KEY not configured",
        )
    try:
        import requests as _requests
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="voices unavailable: `requests` not installed",
        )
    try:
        r = _requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=10,
        )
    except _requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"upstream voices error: {exc}")

    if r.status_code != 200:
        try:
            detail = r.json()
        except ValueError:
            detail = {"upstream_status": r.status_code}
        raise HTTPException(status_code=502, detail=detail)

    raw = r.json().get("voices", [])
    configured_voice_id = _el_voice_id()
    voices = [
        {
            "voice_id": v["voice_id"],
            "name": v.get("name", ""),
            "category": v.get("category", ""),
            "description": (v.get("labels") or {}).get("description", ""),
            "is_default": v["voice_id"] == configured_voice_id,
        }
        for v in raw
    ]
    return {
        "count": len(voices),
        "configured_voice_id": configured_voice_id,
        "voices": sorted(voices, key=lambda v: (not v["is_default"], v["name"])),
        "models": [
            {"model_id": "eleven_flash_v2_5", "note": "lowest latency — real-time"},
            {"model_id": "eleven_turbo_v2_5", "note": "balanced speed + quality (default)"},
            {"model_id": "eleven_multilingual_v2", "note": "highest quality, 29 languages"},
        ],
    }


# ── /reach — operator-configured substrate addresses (read-only) ──
#
# Public, read-only. Returns whichever alternative-substrate addresses
# the operator has configured via environment variables. Empty
# fields mean "not configured by this operator." reach.html and
# setup.html both consume this; the public reach page substitutes
# operator-specific addresses where present and shows generic
# descriptions where absent.
#
# These are addresses (onion URL, bot handle, npub, gateway), not
# secrets. The corresponding *secrets* (Telegram token, ElevenLabs
# API key, etc.) stay in env vars and are never exposed.


@app.get("/reach")
def reach_config():
    """Return the substrate-channel directory for this instance.

    Reads operator-configured public addresses from environment
    variables. Booleans (e.g. `speak_voice`) signal capability
    without revealing the underlying credential.
    """
    el_key = os.environ.get("ELEVENLABS_API_KEY", "")
    el_voice = os.environ.get("ELEVENLABS_VOICE_ID", "")
    return {
        "tor_onion":    os.environ.get("CONCORDANCE_TOR_ONION", ""),
        "telegram":     os.environ.get("CONCORDANCE_TELEGRAM_HANDLE", ""),
        "email_in":     os.environ.get("CONCORDANCE_EMAIL_INBOUND", ""),
        "nostr_npub":   _nostr_pubkey_safe(),
        "nostr_relays": os.environ.get("CONCORDANCE_NOSTR_RELAYS", ""),
        "lora_freq":    os.environ.get("CONCORDANCE_LORA_FREQ", ""),
        "mailing_list": os.environ.get("CONCORDANCE_MAILING_LIST", ""),
        # Capability booleans — true when the corresponding secret /
        # config is present, without exposing the secret itself.
        "speak_voice":  bool(el_key and el_voice),
        "fetch_remote": os.environ.get("CONCORDANCE_FETCH_REMOTE", ""),
    }


@app.get("/version")
def version():
    """Return the deployed engine version, schema version, and git SHA
    if available. Lets external callers (and us at 3am) verify what's
    actually running without grepping logs.

    git_sha resolves at request time from .git/HEAD if a git tree is
    visible; falls back to the env var CONCORDANCE_GIT_SHA (set by
    deploy scripts) or "unknown" if neither is available.
    """
    git_sha = os.environ.get("CONCORDANCE_GIT_SHA", "")
    if not git_sha:
        # Best-effort: read .git/HEAD from the repo on disk.
        try:
            repo_root = Path(__file__).parent.parent
            head = (repo_root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
            if head.startswith("ref: "):
                ref_path = repo_root / ".git" / head[5:]
                if ref_path.exists():
                    git_sha = ref_path.read_text(encoding="utf-8").strip()
            else:
                git_sha = head  # detached HEAD = direct SHA
        except (OSError, ValueError):
            git_sha = "unknown"

    out = {
        "git_sha": git_sha or "unknown",
        "engine_available": _ENGINE_AVAILABLE,
        "schema_version": "1.0",
        # Identity is part of every version response — agents reading
        # /version should know what this engine serves before they call
        # any other endpoint. The full statement is at /identity.
        "serves": "Jesus Christ",
        "serves_short": (
            "Conduit, not source. Eliminates to illuminate the narrow path."
        ),
    }
    if _ENGINE_AVAILABLE:
        try:
            import concordance_engine
            out["engine_package_version"] = getattr(
                concordance_engine, "__version__", "1.1.0",
            )
        except Exception:
            out["engine_package_version"] = "unknown"
    return out


@app.get("/mode")
def deployment_mode():
    """Return the current deployment mode and write-access status.

    Modes: open | restricted | lockdown | quantum
    In restricted/quantum mode, writes require the physical token file
    at token_path. In lockdown, writes are disabled unconditionally.
    """
    from api.deployment_mode import mode_info
    return mode_info()


@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest, _: None = Depends(_check_api_key)):
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = _make_config()
    if not req.run_verifiers:
        config = EngineConfig(
            schema_path=config.schema_path,
            run_verifiers=False,
        )

    try:
        result = validate_packet(
            req.packet,
            now_epoch=req.now_epoch,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    ledger = get_ledger()
    try:
        entry = ledger.append(req.packet, result.overall, result.gate_results)
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    p_hash = compute_packet_hash(req.packet)

    return ValidateResponse(
        overall=result.overall,
        gate_results=[
            GateResultOut(
                gate=gr.gate,
                status=gr.status,
                reasons=gr.reasons,
                details=gr.details,
            )
            for gr in result.gate_results
        ],
        ledger_seq=ledger_seq,
        ledger_entry_hash=ledger_hash,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )




@app.post("/submit", include_in_schema=False)
def submit_public(req: ValidateRequest):
    """Public unauthenticated endpoint for the human-facing form.

    Behaves like /validate but bypasses the GOD-gate wait window — the
    public form is for one-shot evaluations, not bound community
    decisions. The wait-window override is applied on the packet
    itself (the engine reads `wait_window_seconds` per-packet); the
    EngineConfig dataclass doesn't carry that field.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = EngineConfig(
        schema_path=str(_SCHEMA_PATH) if _SCHEMA_PATH and _SCHEMA_PATH.exists() else "",
        run_verifiers=True,
    )

    # Bypass the GOD wait window for the public form by overriding the
    # packet's own wait_window_seconds (engine-level mechanism).
    packet_for_engine = {**req.packet, "wait_window_seconds": 0}

    try:
        result = validate_packet(
            packet_for_engine,
            now_epoch=req.now_epoch,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    ledger = get_ledger()
    try:
        entry = ledger.append(req.packet, result.overall, result.gate_results)
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    p_hash = compute_packet_hash(req.packet)

    return ValidateResponse(
        overall=result.overall,
        gate_results=[
            GateResultOut(
                gate=gr.gate,
                status=gr.status,
                reasons=gr.reasons,
                details=gr.details,
            )
            for gr in result.gate_results
        ],
        ledger_seq=ledger_seq,
        ledger_entry_hash=ledger_hash,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )


# ── /reflect — rehearse a packet (no ledger write) ─────────────────────


@app.post("/reflect", include_in_schema=True)
def reflect(req: ValidateRequest):
    """Rehearse a packet through all four gates without writing to the ledger.

    Same verdict shape as /submit. Use this to iterate on a packet until
    the verdict is what you intend, then commit via /submit or /validate.
    The ledger is never touched here — rehearsal is safe to call repeatedly.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = EngineConfig(
        schema_path=str(_SCHEMA_PATH) if _SCHEMA_PATH and _SCHEMA_PATH.exists() else "",
        run_verifiers=True,
    )

    # Bypass the GOD wait window so rehearsal returns a real PASS/REJECT
    # rather than an unwaitable QUARANTINE. The actual commit will enforce
    # the real wait.
    packet_for_engine = {**req.packet, "wait_window_seconds": 0}

    try:
        result = validate_packet(
            packet_for_engine,
            now_epoch=req.now_epoch,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000
    p_hash = compute_packet_hash(req.packet)

    return ValidateResponse(
        overall=result.overall,
        gate_results=[
            GateResultOut(
                gate=gr.gate,
                status=gr.status,
                reasons=gr.reasons,
                details=gr.details,
            )
            for gr in result.gate_results
        ],
        ledger_seq=None,
        ledger_entry_hash=None,
        packet_hash=p_hash,
        elapsed_ms=round(elapsed_ms, 2),
    )


# ── /confess — record that a prior committed packet was wrong ───────────


class ConfessRequest(BaseModel):
    ref_seq: int                              # ledger seq of the prior entry
    name: str                                 # who is confessing
    role: str = ""                            # confessor's role
    reason: str                               # what was wrong
    corrected_approach: Optional[str] = None  # what the right approach would be


@app.post("/confess", include_in_schema=True)
def confess(req: ConfessRequest):
    """Record that a previously committed packet was wrong.

    The original entry is immutable — it stays in the chain exactly as it was.
    The confession is a new entry that points back to the prior one via
    `confesses_seq` and `confesses_packet_hash`. Walking the chain later,
    a reader sees both the original decision and the correction.

    Use this instead of attempting to mutate or delete a ledger entry.
    Mutation is impossible by design; confession is the correct mechanism.
    """
    ledger = get_ledger()

    prior = ledger.get_by_seq(req.ref_seq)
    if prior is None:
        raise HTTPException(
            status_code=404,
            detail=f"no ledger entry found at seq={req.ref_seq}",
        )

    confession_packet = {
        "domain": "confession",
        "id": f"confession-seq{req.ref_seq}",
        "confesses_seq": req.ref_seq,
        "confesses_packet_hash": prior.get("packet_hash", ""),
        "confessor_name": req.name,
        "confessor_role": req.role,
        "reason": req.reason,
        "corrected_approach": req.corrected_approach,
    }

    try:
        entry = ledger.append(confession_packet, "CONFESSION", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ledger write failed: {exc}")

    return {
        "confessed_seq": req.ref_seq,
        "confessed_packet_hash": prior.get("packet_hash"),
        "confession_seq": entry.seq,
        "confession_entry_hash": entry.entry_hash,
        "message": "Confession recorded. The original entry is unchanged.",
    }


# ── Sealed-record endpoint ─────────────────────────────────────────────
# /seal returns the full WitnessRecord shape — gate verdicts, every
# verifier result with its data (formula / rule / anchor), axis
# coordinates on the dimensional scaffold, citations with their
# source-hierarchy layer, and an optional closest-case overlay.
# /validate keeps the legacy EngineResult shape for backward compat.

@app.post("/seal")
def seal(request: Request, req: SealRequest):
    """Run a packet through the four gates and return the sealed
    WitnessRecord.

    The canonical agent-facing surface for tonight's engine work.
    Where /validate returns a stripped EngineResult (overall + gate
    verdicts), /seal returns the WitnessRecord shape that walkthroughs
    are rendered from: each verifier_result carries its full `data`
    payload (rule, formula, doctrinal anchor for the rules that have
    one); axis_coords places the packet on the 36-axis scaffold;
    anchors carry their source-hierarchy layer; closest_case is
    explicit-absent (precedent_id=None) when no precedent applies.

    The endpoint also writes to the audit ledger like /submit does, so
    every sealed record is part of the permanent chain. ledger_seq and
    ledger_entry_hash come back alongside the WitnessRecord JSON.

    Doctrinal commitment: the response carries no `final_answer` /
    `answer` / `engine_answer` field, ever. The witness verifier's
    no_fabricated_answer check enforces that against any record sealed.
    """
    _rate_check(request, "seal")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    t0 = time.perf_counter()
    config = _make_config()
    if not req.run_verifiers:
        config = EngineConfig(
            schema_path=config.schema_path,
            run_verifiers=False,
        )

    # Coerce optional anchor / closest_case payloads into the schema
    # types so any future structural changes propagate through one
    # boundary, not many.
    try:
        anchors = tuple(
            Anchor.from_dict(a) for a in (req.anchors or [])
        )
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"malformed anchors: {exc}",
        )
    # ── Closest-case lookup ────────────────────────────────────────────
    # Before running the gates, query the case store for the nearest
    # already-solved precedent.  If the caller supplied a closest_case
    # override we honour it; otherwise we compute it from the index.
    # The precedent is attached to the WitnessRecord and returned to the
    # caller — it does NOT change the verdict, only informs the overlay.
    closest_case = None
    if req.closest_case is not None:
        try:
            closest_case = ClosestCase.from_dict(req.closest_case)
        except (KeyError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"malformed closest_case: {exc}",
            )
    else:
        try:
            from concordance_engine.case_index import find_closest as _find_closest
            from concordance_engine.witness_record import axis_coords_for
            from concordance_engine import grid as _grid

            _domain = str(req.packet.get("domain", ""))
            _ac = axis_coords_for(_domain)
            _dims = list(_ac.dimensions) if _ac else []
            _anchor_refs = [a.ref for a in anchors]

            _candidates = get_case_store().graph_walk(
                domain=_domain,
                dims=_dims,
                anchors=_anchor_refs,
                top_k=1,
                exclude_hash=None,
                candidate_limit=5_000,
            )
            if _candidates:
                closest_cases = _find_closest(
                    domain=_domain,
                    dims=frozenset(_dims),
                    anchors=tuple(_anchor_refs),
                    candidates=_candidates,
                    top_k=1,
                )
                if closest_cases:
                    closest_case = closest_cases[0]
        except Exception as _ce:
            _log.debug("closest-case lookup skipped: %s", _ce)

    try:
        record = validate_and_seal(
            req.packet,
            now_epoch=req.now_epoch,
            config=config,
            anchors=anchors,
            closest_case=closest_case,
            packet_id=req.packet_id or req.packet.get("id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    # ── Path A: soulbound binding ──────────────────────────────────────
    # Bind the user's personal Ed25519 public key so the WitnessRecord is
    # tied to the holder of the matching private key — not just a machine.
    # This makes every receipt soulbound and portable (Rev 13:16-17 stance:
    # the record can be verified offline without any central authority).
    subject_pubkey: Optional[str] = None
    if req.bind_subject:
        try:
            from concordance_engine.user_identity import get_user_pubkey
            subject_pubkey = get_user_pubkey()
            record = bind_subject(record, subject_pubkey)
        except Exception:
            pass  # graceful degradation — seal still works without key

    # ── Quantum witness tier stub ──────────────────────────────────────
    # "quantum" tier is accepted and stored; the active routing to the
    # Rossville quantum-encrypted node will be wired in a future release.
    # For now it's a flag in the response so callers can differentiate.
    witness_tier = req.witness_tier if req.witness_tier in ("standard", "quantum") else "standard"

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Write to the audit ledger using the gate_results from the record
    # so the persisted entry matches the returned record.
    ledger = get_ledger()
    try:
        entry = ledger.append(
            req.packet, record.overall, list(record.gate_results),
        )
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    out = record.to_dict()
    if ledger_seq is not None:
        out["ledger_seq"] = ledger_seq
        out["ledger_entry_hash"] = ledger_hash
    out["elapsed_ms"] = round(elapsed_ms, 2)
    out["witness_tier"] = witness_tier
    if subject_pubkey:
        out["soulbound"] = True

    # ── Nostr permanent anchor ─────────────────────────────────────────
    # Publish a signed NIP-78 event to configured Nostr relays so the
    # verdict is independently verifiable by anyone with the event_id.
    # The event_id is computed synchronously (deterministic SHA-256);
    # broadcast is fire-and-forget via the existing _BROADCAST_POOL so
    # the seal response returns immediately without waiting for relays.
    try:
        from concordance_engine.nostr_anchor import anchor_verdict as _nostr_anchor
        content_hash = out.get("content_hash", "")
        domain = str(req.packet.get("domain", "unknown"))
        verdict = str(record.overall)
        nostr_event_id = _nostr_anchor(
            verdict=verdict,
            domain=domain,
            content_hash=content_hash,
            packet_id=req.packet_id or req.packet.get("id"),
            broadcast=True,
            executor=_BROADCAST_POOL,
        )
        out["nostr_event_id"] = nostr_event_id
    except Exception as _ne:
        _log.debug("nostr anchor skipped: %s", _ne)

    # ── Index in case store ────────────────────────────────────────────
    # After the record is fully formed (hash, nostr_event_id, etc.),
    # index it so future seals can find it as a closest-case precedent.
    # Fire-and-forget: a failure here must never block the response.
    try:
        _cs = get_case_store()
        _ac = None
        try:
            from concordance_engine.witness_record import axis_coords_for
            _ac = axis_coords_for(str(req.packet.get("domain", "")))
        except Exception:
            pass
        _dims    = list(_ac.dimensions) if _ac else []
        _anchors = [a.ref for a in anchors]
        _vsummary = [
            {"name": v["name"], "status": v["status"],
             "detail": str(v.get("detail", ""))[:200]}
            for v in (out.get("verifier_results") or [])[:10]
        ]
        _cs.index_verdict(
            content_hash=out.get("content_hash", ""),
            domain=str(req.packet.get("domain", "")),
            dims=_dims,
            anchors=_anchors,
            verdict=str(record.overall),
            verifier_summary=_vsummary,
            ledger_seq=ledger_seq,
            nostr_event_id=out.get("nostr_event_id"),
        )
    except Exception as _ie:
        _log.debug("case_store index skipped: %s", _ie)

    return out


@app.post("/seal/render", include_in_schema=False)
def seal_render(req: SealRenderRequest):
    """Human-form pipeline: natural-language → packet → seal → rendered walkthrough.

    Routes the user's text through nl_to_packet (deterministic
    template parser) to build a real packet, runs validate_and_seal,
    and returns both the WitnessRecord JSON and a pre-rendered
    walkthrough so the front-end just innerHTML's the response.

    When the parser doesn't recognize the input shape, returns a
    structured 422 listing the templates that *are* supported, so
    the user gets a useful "try something like..." instead of a
    confusing error. Templates currently understood:
      * chemistry equation: "is C + O2 -> CO2 balanced?"
      * one-sample t-test: "p=0.05 from a t-test, n=30, mean=5, sd=1, mu0=4"
      * physics dimensional: "F = m*a where F in newtons, m in kg, a in m/s^2"
      * math equality / derivative: "d/dx(x^2) = 2x"
      * CS complexity: "merge sort runs in O(n log n)"
      * governance proposal: "should we admit Alice with 3 witnesses?"
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")

    parsed = nl_parse(text)
    if parsed is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_template_matched",
                "message": (
                    "The deterministic parser doesn't recognize this "
                    "input shape yet. Try one of the supported forms."
                ),
                "supported_templates": [
                    "chemistry: 'is C + O2 -> CO2 balanced?'",
                    "statistics: 'p=0.05 from a t-test, n=30, mean=5, sd=1, mu0=4'",
                    "physics: 'F = m*a where F in newtons, m in kg, a in m/s^2'",
                    "mathematics: 'd/dx(x^2) = 2x'",
                    "computer science: 'merge sort runs in O(n log n)'",
                    "governance: 'should we admit Alice with 3 witnesses?'",
                ],
                "input_text": text,
            },
        )

    t0 = time.perf_counter()
    config = _make_config()

    # Force `wait_window_seconds=0` on the packet so the GOD wait
    # window doesn't block one-shot human submissions. Mirrors the
    # /submit handler's behavior.
    packet_for_engine = {**parsed.packet, "wait_window_seconds": 0}

    try:
        record = validate_and_seal(
            packet_for_engine,
            config=config,
            packet_id=packet_for_engine.get("id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"engine error: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Write to the audit ledger.
    ledger = get_ledger()
    try:
        entry = ledger.append(
            parsed.packet, record.overall, list(record.gate_results),
        )
        ledger_seq = entry.seq
        ledger_hash = entry.entry_hash
    except Exception:
        ledger_seq = None
        ledger_hash = None

    # Render the walkthrough in the requested format. HTML is embedded
    # (inner-content only) so the front-end can drop it into a div
    # without dragging the renderer's full document wrapper / styles
    # into the host page.
    fmt = (req.format or "html").lower()
    if fmt == "markdown":
        walkthrough = render_walkthrough(record, expand_traces=req.expand_traces)
    elif fmt == "compact":
        walkthrough = render_walkthrough_compact(record)
    else:
        walkthrough = render_walkthrough_html(
            record, expand_traces=req.expand_traces, embedded=True,
        )

    return {
        "record": record.to_dict(),
        "walkthrough": walkthrough,
        "format": fmt,
        "parse_template": parsed.template,
        "parse_confidence": parsed.confidence,
        "parse_notes": parsed.notes,
        "ledger_seq": ledger_seq,
        "ledger_entry_hash": ledger_hash,
        "elapsed_ms": round(elapsed_ms, 2),
    }


# ── Ledger read endpoints ──────────────────────────────────────────────
# Advertised by the home page (/) and /llms.txt; previously unimplemented.
# The underlying Ledger class already provides recent / get_by_id /
# verify_chain — these handlers are thin wrappers that surface them
# over HTTP so external auditors and AI agents can read the permanent
# record without touching the validator authentication path.

@app.get("/ledger")
def ledger_recent(
    limit: int = Query(50, ge=1, le=500,
                       description="How many entries to return (newest first)"),
    offset: int = Query(0, ge=0,
                        description="Skip the most recent N entries"),
):
    """Return the most recent ledger entries, newest first.

    Read-only and unauthenticated — the ledger is a public verification
    record. Each entry includes packet_hash, entry_hash, prev_hash, and
    overall verdict, so external auditors can replay and verify the
    chain without engine access.
    """
    ledger = get_ledger()
    entries = ledger.recent(n=limit, offset=offset)
    return {
        "count": len(entries),
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }


@app.get("/ledger/verify")
def ledger_verify():
    """Walk the ledger chain and confirm every prev_hash → entry_hash
    link is intact. Returns valid=True if the chain is whole, plus the
    seq number of the first break if not. The hash chain is the
    tampering check — any edit to any entry breaks it.
    """
    ledger = get_ledger()
    return ledger.verify_chain()


# ── /witness/{precedent_id} — list witness attestations on a precedent ──
#
# Public, read-only. Returns every Ed25519 witness attestation on file
# for the given precedent_id, with a verify result on each. Anyone
# reading a precedent in the well can see who has stood by it
# cryptographically — the BROTHERS gate's witness count + the
# witness signatures together make the witness layer legible.
#
# Per "free use, alignment to execute": reading attestations is
# free; signing them requires the witness's private key.


@app.get("/witness/{precedent_id:path}")
def witness_attestations(precedent_id: str):
    """Return all witness attestations on file for a precedent.

    Each result includes the attestation fields plus `verified`
    (bool) and `verify_reason` (str) computed at request time so
    consumers see whether the signature still holds.
    """
    _safe_id(precedent_id, "precedent_id")
    try:
        from concordance_engine import witness as _witness
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"witness module unavailable: {exc}"
        )
    attestations = _witness.list_for_precedent(precedent_id)
    out: List[Dict[str, Any]] = []
    for att in attestations:
        try:
            ok, reason = _witness.verify(att)
        except Exception as exc:  # noqa: BLE001
            ok, reason = False, f"verify error: {exc}"
        record = att.to_dict()
        record["verified"] = ok
        record["verify_reason"] = reason
        out.append(record)
    return {
        "precedent_id": precedent_id,
        "count": len(out),
        "attestations": out,
    }


@app.get("/ledger/{packet_id}")
def ledger_by_id(packet_id: str):
    """Return all ledger entries for a specific packet_id, oldest first.

    Same packet may appear multiple times if it was resubmitted; the
    list is the full audit trail for that id. Empty list if the id
    isn't in the ledger.
    """
    _safe_id(packet_id, "packet_id")
    ledger = get_ledger()
    entries = ledger.get_by_id(packet_id)
    return {
        "packet_id": packet_id,
        "count": len(entries),
        "entries": entries,
    }


# ── /dispatch — filtered ledger search ────────────────────────────────


@app.get("/dispatch", include_in_schema=True)
def dispatch(
    domain:     Optional[str] = Query(None, description="Filter by domain (e.g. 'governance')"),
    overall:    Optional[str] = Query(None, description="Filter by verdict (PASS, REJECT, QUARANTINE, CONFESSION)"),
    packet_id:  Optional[str] = Query(None, description="Filter by packet_id"),
    since:      Optional[float] = Query(None, description="Return entries at or after this epoch"),
    until:      Optional[float] = Query(None, description="Return entries at or before this epoch"),
    limit:      int = Query(50, ge=1, le=500, description="Maximum entries to return"),
):
    """Filtered search over the ledger.

    All parameters are optional and cumulative — only entries that match
    every supplied filter are returned. Results are newest first.
    """
    ledger = get_ledger()
    entries = list(ledger.iter_filtered(
        domain=domain,
        overall=overall,
        packet_id=packet_id,
        since_epoch=since,
        until_epoch=until,
        limit=limit,
    ))
    return {
        "count": len(entries),
        "filters": {
            "domain": domain, "overall": overall, "packet_id": packet_id,
            "since": since, "until": until, "limit": limit,
        },
        "entries": entries,
    }


# ── /stats — aggregate ledger counts ──────────────────────────────────


@app.get("/cases/stats", include_in_schema=True)
def cases_stats():
    """Case store counts: total indexed verdicts, breakdown by verdict and domain.
    Also returns avg_degree — the average number of outgoing spoke edges per case,
    which tracks how well-connected the hub-and-spoke graph has become.
    """
    return get_case_store().stats()


@app.get("/cases/hub/{domain}", include_in_schema=True)
def cases_hub(domain: str):
    """Return the hub case for a domain — the highest-degree node.

    The hub is the case with the most outgoing spoke edges; it sits at the
    structural centre of the domain's sub-graph and is the starting point
    for graph-walk retrieval and spoke generation.
    """
    _safe_domain(domain)
    hub = get_case_store().hub_for_domain(domain)
    if hub is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No cases indexed for domain '{domain}'")
    return hub


@app.get("/cases/spokes/{hash_}", include_in_schema=True)
def cases_spokes(hash_: str, depth: int = 1):
    """Return cases reachable within `depth` hops from a given case hash.

    depth=1 returns direct spokes (immediate neighbors).
    depth=2 returns spokes-of-spokes.
    Useful for rendering the local neighborhood of a case on the frontend.
    """
    if depth < 1 or depth > 3:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="depth must be 1-3")
    _safe_hash(hash_, "hash_")
    spokes = get_case_store().spokes_from(hash_, depth=depth)
    return {"origin_hash": hash_, "depth": depth, "spokes": spokes, "count": len(spokes)}


# ── /intake — Socratic intake ──────────────────────────────────────────


# Per-axis question templates. Each axis surfaces the verification gap
# that its verifier cares most about. Used as scaffolding for the Haiku
# personalisation call; returned as-is if Haiku is unavailable.
_AXIS_QUESTIONS: Dict[str, str] = {
    "authority_trust":     "Who or what is the authority for this claim — which institution, standard, law, or source establishes it?",
    "time_sequence":       "Does this apply universally, or only within a specific time period, sequence, or set of conditions?",
    "encoding":            "Is there a formal notation, formula, or symbolic representation that fully specifies this claim?",
    "conservation_balance":"What quantity is conserved or must balance for this claim to hold?",
    "reasoning":           "What is the step-by-step logical or mathematical basis — which rules, axioms, or theorems apply?",
    "metabolism":          "What process, transformation, or flow is central to this claim?",
    "physical_substance":  "What specific physical quantities, units, materials, or measurements define this claim?",
}

# Domains whose primary verification gaps map to these axes (priority order).
# Used to pick which 2 axes to ask about when the domain sits on many.
_AXIS_PRIORITY: Dict[str, List[str]] = {
    "mathematics":         ["reasoning", "encoding"],
    "chemistry":           ["physical_substance", "conservation_balance"],
    "physics":             ["physical_substance", "conservation_balance"],
    "physics_conservation":["conservation_balance", "physical_substance"],
    "physics_dimensional": ["physical_substance", "encoding"],
    "statistics_pvalue":   ["reasoning", "encoding"],
    "statistics_multiple_comparisons": ["reasoning", "time_sequence"],
    "statistics_confidence_interval":  ["reasoning", "encoding"],
    "law":                 ["authority_trust", "time_sequence"],
    "governance_decision_packet": ["authority_trust", "reasoning"],
    "theology_doctrine":   ["authority_trust", "encoding"],
    "scripture_anchors":   ["authority_trust", "encoding"],
    "medicine":            ["authority_trust", "metabolism"],
    "finance":             ["authority_trust", "conservation_balance"],
    "economics":           ["authority_trust", "time_sequence"],
    "labor":               ["authority_trust", "time_sequence"],
    "real_estate":         ["authority_trust", "time_sequence"],
    "cryptography":        ["encoding", "reasoning"],
    "cybersecurity":       ["encoding", "authority_trust"],
    "networking":          ["encoding", "time_sequence"],
    "biology":             ["metabolism", "encoding"],
    "genetics":            ["encoding", "physical_substance"],
    "ecology":             ["metabolism", "time_sequence"],
    "geology":             ["time_sequence", "physical_substance"],
    "meteorology":         ["time_sequence", "conservation_balance"],
    "thermodynamics":      ["conservation_balance", "metabolism"],
    "energy":              ["conservation_balance", "metabolism"],
    "quantum_computing":   ["encoding", "reasoning"],
    "document_validation": ["authority_trust", "encoding"],
    "witness":             ["authority_trust", "time_sequence"],
}


class IntakeRequest(BaseModel):
    text: str
    domain: Optional[str] = None


@app.post("/intake", include_in_schema=True)
def intake(request: Request, req: IntakeRequest):
    """Socratic intake: return 2 targeted questions before the four-gate seal.

    Identifies the 2 scaffold axes most critical for verification of this
    domain, then uses Claude Haiku to phrase them as questions specific to
    the claim text. Falls back to axis-template questions if Haiku is
    unavailable or the API key is not configured.

    The caller (try.html) shows these questions in the seal block. Answers
    are appended to the claim text before posting to /seal, enriching the
    packet for the gate verifiers.
    """
    _rate_check(request, "intake")
    text   = (req.text or "").strip()
    domain = (req.domain or "").strip()

    # Resolve domain from text if not supplied
    if not domain:
        try:
            from concordance_engine.nl_to_packet import nl_to_packet
            result = nl_to_packet(text)
            domain = result.get("domain", "") if isinstance(result, dict) else ""
        except Exception:
            pass
    if not domain:
        try:
            from concordance_engine.classifier import classify
            domain = classify(text) or ""
        except Exception:
            pass

    # Get scaffold axes for the domain
    axes: List[str] = []
    try:
        from concordance_engine.witness_record import axis_coords_for
        ac = axis_coords_for(domain)
        if ac:
            axes = sorted(ac.dimensions)
    except Exception:
        pass

    # Pick the 2 most-critical axes for this domain
    priority = _AXIS_PRIORITY.get(domain, [])
    # Fill from axes not already in priority
    for ax in axes:
        if ax not in priority:
            priority.append(ax)
    selected_axes = priority[:2]
    if not selected_axes:
        selected_axes = list(_AXIS_QUESTIONS.keys())[:2]

    # Template questions for the selected axes
    templates = [_AXIS_QUESTIONS.get(ax, f"What about {ax}?") for ax in selected_axes]

    # Try to personalise via Haiku — makes questions specific to the claim text
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    questions = templates  # default
    if api_key and text:
        try:
            import anthropic as _anthropic
            _client = _anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"Claim: {text[:400]}\n"
                f"Domain: {domain or 'unknown'}\n"
                f"Scaffold axes needing answers: {', '.join(selected_axes)}\n\n"
                "Rephrase the following template questions to be specific to this exact claim. "
                "Keep each question short (one sentence). Do not answer them.\n"
                + "\n".join(f"{i+1}. {q}" for i, q in enumerate(templates))
                + '\n\nOutput ONLY a JSON array of exactly 2 strings.\n["Question 1?", "Question 2?"]'
            )
            resp = _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw   = resp.content[0].text.strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                if isinstance(parsed, list) and len(parsed) >= 2:
                    questions = [str(q).strip() for q in parsed[:2]]
        except Exception as exc:
            _log.debug("ask: Haiku personalisation failed (using templates): %s", exc)

    return {
        "domain":    domain,
        "axes":      selected_axes,
        "questions": questions,
    }


class ClosestCaseRequest(BaseModel):
    domain: str
    dimensions: List[str] = []
    anchors: List[str] = []
    top_k: int = 3
    exclude_hash: Optional[str] = None
    # `text` is accepted but ignored — future: parse into dims via NL dispatch
    text: Optional[str] = None


@app.post("/cases/closest", include_in_schema=True)
def cases_closest(req: ClosestCaseRequest):
    """Find the closest previously-solved cases for a given domain/axes.

    Used by the Socratic intake, smart_seed.py, and the try.html frontend
    to surface the nearest precedent before running the full four-gate seal.
    Each result includes distance (0=identical, 1=completely unlike),
    verdict, domain, shared dimensions, shared anchors, and the verifier
    summary for the reasoning overlay.

    If `dimensions` is empty, the endpoint auto-derives scaffold dimensions
    from the domain name via `axis_coords_for` so callers can pass domain
    alone and still get a meaningful distance score.
    """
    cs = get_case_store()

    # Auto-derive scaffold dimensions when the caller passes none
    resolved_dims = list(req.dimensions)
    if not resolved_dims:
        try:
            from concordance_engine.witness_record import axis_coords_for
            _ac = axis_coords_for(req.domain)
            if _ac:
                resolved_dims = list(_ac.dimensions)
        except Exception:
            pass

    candidates = cs.graph_walk(
        domain=req.domain,
        dims=resolved_dims,
        anchors=req.anchors,
        top_k=min(req.top_k, 10),
        exclude_hash=req.exclude_hash,
    )
    return {
        "domain":        req.domain,
        "query_dims":    resolved_dims,
        "cases":         candidates,  # primary key
        "results":       candidates,  # alias for back-compat
        "total_indexed": cs.count(),
    }


@app.get("/stats", include_in_schema=True)
def stats():
    """Aggregate counts across the entire ledger.

    Returns total entry count, breakdown by verdict (PASS / REJECT /
    QUARANTINE / CONFESSION) and by domain, plus the timestamp of the
    most recent entry.
    """
    ledger = get_ledger()
    return ledger.stats()


# ── /audit-chain — canonical-naming aliases ────────────────────────────
# Same handlers as /ledger but at the canonically-correct URL. Per the
# doctrinal-distinction note: "ledger" the doctrinal term refers to
# judgment-keeping (gospel ends the ledger); the engine's mechanism is
# an audit chain, not a judgment ledger. The /ledger URLs stay live for
# backward compat; new clients should prefer /audit-chain.

@app.get("/audit-chain", include_in_schema=True)
def audit_chain_recent(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Most recent audit-chain entries (alias for /ledger)."""
    return ledger_recent(limit=limit, offset=offset)


@app.get("/audit-chain/verify", include_in_schema=True)
def audit_chain_verify():
    """Walk the chain and confirm prev_hash → entry_hash links hold
    (alias for /ledger/verify)."""
    return ledger_verify()


@app.get("/audit-chain/{packet_id}", include_in_schema=True)
def audit_chain_by_id(packet_id: str):
    """All audit-chain entries for a specific packet_id (alias for
    /ledger/{packet_id})."""
    return ledger_by_id(packet_id)


# ── /chain/since — fetch endpoint for federation ──────────────────
#
# Returns audit-chain entries with seq > the given cursor, ordered
# OLDEST FIRST so a receiver can append in chain order. This is the
# server side of `concordance fetch` — a peer engine pulls new
# sealed precedents from this instance to mirror them locally.
#
# Read-only, public. Per "free use, alignment to execute": reading
# the well is free. Anyone can fetch any sealed precedent.


# ── /chain/receive — federation push (inverse of /chain/since) ─────
#
# Symmetric with /chain/since: that endpoint serves entries to peers
# pulling from us; this one accepts entries from peers pushing to us.
# Both store into the same fetched/<remote_slug>.jsonl mirror — pull
# vs push is just direction.
#
# Per "free use, alignment to execute": receiving is read-shaped from
# our perspective (we don't validate the sender's authority; we
# accept and store, tagged with their claimed origin URL). The four
# gates already ran on the sender's side; we mirror what they sealed.
# If a malicious peer pushes garbage, it lands in their slug only
# and never enters our chain.


class ChainReceiveRequest(BaseModel):
    from_: str = ""  # alias for "from" — handled below
    entries: List[Dict[str, Any]] = []

    class Config:
        # Accept either "from" or "from_" since "from" is a Python keyword.
        # Pydantic v2 uses populate_by_name + Field alias; for compatibility
        # we accept both via the json schema validation in the handler.
        pass


@app.post("/chain/receive", include_in_schema=True)
def chain_receive(payload: Dict[str, Any]):
    """Receive sealed precedents pushed by a peer.

    Body shape: `{from: <url>, entries: [...]}`. Entries are the
    same audit-chain rows a remote's /chain/since would emit. We
    don't validate the chain's hash continuity here — the sending
    instance is responsible for the integrity of its own chain;
    we just mirror what they sent us.

    Stored in the same fetched/<slug>.jsonl files as pulled
    entries, so consumers (concordance fetch --list, the dawn
    surface, etc.) see push-received and pull-received entries
    together.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")

    from_url = (payload.get("from") or payload.get("from_") or "").strip()
    if not from_url:
        raise HTTPException(status_code=400, detail="`from` url is required")

    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="`entries` must be a list")

    try:
        from concordance_engine import fetch as _fetch
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"fetch module not available: {exc}"
        )

    # Light validation: each entry must at least have a seq + packet_id +
    # entry_hash. Anything else is the sender's chain, not ours.
    accepted_entries = []
    rejected = []
    seen_seqs = set()
    for e in entries:
        if not isinstance(e, dict):
            rejected.append({"seq": None, "reason": "entry not a dict"})
            continue
        seq = e.get("seq")
        if seq is None:
            rejected.append({"seq": None, "reason": "missing seq"})
            continue
        if seq in seen_seqs:
            rejected.append({"seq": seq, "reason": "duplicate seq in payload"})
            continue
        if not e.get("packet_id"):
            rejected.append({"seq": seq, "reason": "missing packet_id"})
            continue
        if not e.get("entry_hash"):
            rejected.append({"seq": seq, "reason": "missing entry_hash"})
            continue
        seen_seqs.add(seq)
        # Tag with origin + receive timestamp, same shape as fetch path.
        e.setdefault("_origin", from_url)
        e.setdefault("_fetched_at", time.time())
        e.setdefault("_received_via", "push")
        accepted_entries.append(e)

    if accepted_entries:
        base = _fetch._default_base_dir()
        _fetch._append_entries(base, from_url, accepted_entries)
        # Update the per-remote state so subsequent pulls don't re-pull
        # things we already received via push.
        state = _fetch._load_state(base, from_url)
        max_seq = max(int(e.get("seq", 0)) for e in accepted_entries)
        if max_seq > state.last_seq:
            state.last_seq = max_seq
        state.last_fetched_at = time.time()
        state.last_status = "received_push"
        _fetch._save_state(base, state)

    return {
        "from": from_url,
        "accepted": len(accepted_entries),
        "rejected": rejected,
        "next_seq": max((int(e.get("seq", 0)) for e in accepted_entries), default=0),
    }


@app.get("/chain/since", include_in_schema=True)
def chain_since(
    seq: int = Query(0, ge=0,
        description="Return entries with seq > this value."),
    limit: int = Query(100, ge=1, le=1000),
):
    """Audit-chain entries past `seq`, oldest first. Federation endpoint.

    Used by `concordance fetch` to incrementally sync new precedents
    from a remote engine. Idempotent — calling with the same `seq`
    yields the same response. Empty `entries` array means the receiver
    is up to date.
    """
    ledger = get_ledger()
    # Read all entries newest-first, then filter + reverse.
    all_recent = ledger.recent(n=10000, offset=0)  # generous cap
    after: List[Dict[str, Any]] = []
    for e in all_recent:
        e_seq = int(e.get("seq", 0))
        if e_seq > seq:
            after.append(e)
    after.sort(key=lambda x: x.get("seq", 0))
    sliced = after[:limit]
    return {
        "since_seq": seq,
        "limit": limit,
        "count": len(sliced),
        "next_seq": sliced[-1].get("seq", seq) if sliced else seq,
        "entries": sliced,
    }


# ── Journal / shelf / keeping (the human-side surfaces) ──────────────
# These expose the new harvest / library / shelf / keeping modules
# over HTTP so narrowhighway.com (and any client) can use them.
# Mirrors the CLI subcommands (`concordance write`, `concordance keep`,
# `concordance journal`, `concordance live`).


class WriteRequest(BaseModel):
    text: str
    tags: Optional[List[str]] = None
    look_up_precedent: bool = True
    # Identity acknowledgment — the depositing-into-the-well permission.
    # Optional with default True so existing clients don't break; agents
    # are encouraged (but not forced) to set this explicitly after
    # reading /identity. The value is recorded in the seed's metadata
    # for the keeping log; the engine still runs whether or not it's
    # acknowledged. Misalignment is caught by the four gates downstream,
    # not by this field.
    identity_acknowledged: bool = True


class AnnotateRequest(BaseModel):
    note: str
    author: Optional[str] = ""


# ── /capture — unified capture-anywhere funnel ─────────────────────
#
# One endpoint, many sources. Drop a file in a watch folder, share
# from an iOS app, forward an email, send a Telegram message — all
# arrive here with `source` set, and all become seeds in the same
# journal. The source is recorded as a tag (`source:<name>`) so
# any later audit can see where a seed came from.
#
# This endpoint is intentionally tolerant: text is required, every-
# thing else is optional. Source authenticity is informational, not
# authoritative — misalignment is caught by the four gates downstream
# (RED/FLOOR/BROTHERS/GOD), not by trusting the source claim.
#
# Per the kingdom-economy substrate: capture works with whatever the
# user already has (email, file system, phone share sheet) — no
# proprietary client required.


class CaptureRequest(BaseModel):
    text: str
    source: Optional[str] = None       # e.g. "watch_folder", "email", "telegram", "apple_shortcut", "web_share"
    source_meta: Optional[Dict[str, Any]] = None  # arbitrary metadata about origin
    tags: Optional[List[str]] = None
    identity_acknowledged: bool = True
    look_up_precedent: bool = True
    # Set False for bulk/seed ingestion to skip the O(n) full-journal
    # calibration scan. The entry is still written; calibration is just
    # skipped and the response returns a minimal payload.
    calibrate: bool = True


@app.post("/capture", include_in_schema=True)
def capture(request: Request, req: CaptureRequest):
    """Unified capture funnel. Accepts text from any source; records
    the source as a tag; forwards to the journal capture mechanism.

    Sources are tagged but not validated — any caller can claim any
    source. The four gates downstream check alignment by content,
    not by claimed origin. This is the wise-serpent + innocent-dove
    posture: trusting source claims would be naive; refusing to
    record them would erase useful provenance. We record what was
    claimed, run the gates on the content.

    Rate-limited per-IP at 60/min sustained.
    """
    _rate_check(request, "capture")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # Build the tag list: user tags + source tag + acknowledgment marker.
    # The source tag is namespaced ("source:email") so later filters
    # can find all seeds from a given source.
    tags = list(req.tags or [])
    if req.source:
        # Normalize source — lowercase, alnum + underscore only.
        clean = "".join(c for c in req.source.lower() if c.isalnum() or c == "_")
        if clean:
            src_tag = f"source:{clean}"
            if src_tag not in tags:
                tags.append(src_tag)
    if req.identity_acknowledged:
        # Mark the seed as having passed the alignment doorway.
        if "identity_acknowledged" not in tags:
            tags.append("identity_acknowledged")

    try:
        from concordance_engine import journal as _journal
    except ImportError as e:
        raise HTTPException(
            status_code=503, detail=f"journal module not available: {e}"
        )

    try:
        entry = _journal.capture(
            text,
            tags=tags or None,
            look_up_precedent=req.look_up_precedent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fast path: skip the O(n) full-journal calibration scan when the
    # caller doesn't need it (e.g. bulk seed ingestion).
    if not req.calibrate:
        return {
            "entry": entry.to_dict(),
            "calibration": None,
            "closest_precedent": None,
            "source": req.source,
            "rendered_calibration": None,
        }

    cal = _journal.calibrate(entry)
    closest = _resolve_closest_precedent(entry.categorization.closest_precedent_id)
    return {
        "entry": entry.to_dict(),
        "calibration": cal.to_dict(),
        "closest_precedent": closest,
        "source": req.source,
        "rendered_calibration": _journal.render_calibration(entry, cal),
    }


def _resolve_closest_precedent(precedent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Look up the full body of a precedent by id, for closest-case
    overlay. Returns None if not found or on error — closest-case is
    descriptive, not prescriptive, so a missing precedent is just
    silence, not an error."""
    if not precedent_id:
        return None
    try:
        from concordance_engine import ledger as _ledger
        for p in _ledger.list_precedents():
            if p.get("precedent_id") == precedent_id:
                return p
    except (ImportError, OSError, ValueError):
        return None
    return None


# ── /ingest/drive — import documents from a shared cloud folder ──────────────
#
# Accepts a public share URL (Google Drive, Dropbox, OneDrive) and ingests
# the text of each document as a named personal source. No auth required —
# the URL must be a "anyone with link can view" share. Documents are chunked
# and forwarded to /capture with source set to the folder's label.
#
# This lets users seed the engine with their own study notes, sermon outlines,
# personal research, or any document collection they already have — without
# needing a proprietary client. Fits the wise-serpent posture: use what
# they already have.
#
# Supported URL patterns (public share only):
#   Google Drive folder:  https://drive.google.com/drive/folders/<id>?usp=sharing
#   Dropbox folder:       https://www.dropbox.com/sh/<id>...?dl=0
#   OneDrive folder:      https://onedrive.live.com/...
# File links (not folders) for Google Drive:
#   https://drive.google.com/file/d/<id>/view?usp=sharing
#   https://docs.google.com/document/d/<id>/...


class DriveIngestRequest(BaseModel):
    url: str                                  # public share URL
    source_label: Optional[str] = None        # human name for this source
    tags: Optional[List[str]] = None
    max_docs: int = 50                        # safety cap
    chunk_words: int = 600                    # target words per chunk


def _gdrive_export_url(file_id: str) -> str:
    return f"https://docs.google.com/document/d/{file_id}/export?format=txt"


def _gdrive_folder_file_ids(folder_id: str) -> list[dict]:
    """Fetch the file list from a public Google Drive folder via the
    unofficial but stable embed endpoint. Returns list of dicts with
    'id' and 'name'. Empty list on failure."""
    import re as _re
    try:
        import requests as _req
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        r = _req.get(url, timeout=15,
                     headers={"User-Agent": "Concordance-DriveIngest/1.0"})
        # The folder page embeds file IDs in JSON-like data attributes.
        ids   = _re.findall(r'"([0-9A-Za-z_\-]{25,})"', r.text)
        names = _re.findall(r'"name":"([^"]+)"', r.text)
        seen, results = set(), []
        for fid in ids:
            if fid not in seen and len(fid) >= 28:
                seen.add(fid)
                name = names.pop(0) if names else fid
                results.append({"id": fid, "name": name})
        return results[:50]
    except Exception:
        return []


def _fetch_text_from_url(url: str, timeout: int = 20) -> str:
    import requests as _req, re as _re
    r = _req.get(url, timeout=timeout,
                 headers={"User-Agent": "Concordance-DriveIngest/1.0"},
                 allow_redirects=True)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "html" in ct:
        # Strip HTML tags for simple HTML export pages
        text = _re.sub(r'<style[^>]*>.*?</style>', '', r.text, flags=_re.S)
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'&[a-z#0-9]+;', ' ', text)
    else:
        text = r.text
    return _re.sub(r'\s+', ' ', text).strip()


def _chunk_text(text: str, target_words: int) -> list[str]:
    import re as _re
    paras = [p.strip() for p in _re.split(r'\n{2,}', text) if p.strip()]
    chunks, buf, buf_w = [], [], 0
    for para in paras:
        pw = len(para.split())
        if buf_w + pw > target_words and buf:
            chunks.append("\n\n".join(buf))
            buf, buf_w = [], 0
        buf.append(para)
        buf_w += pw
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


@app.post("/ingest/drive", include_in_schema=True)
def ingest_drive(request: Request, req: DriveIngestRequest):
    """Import documents from a public cloud share link.

    Accepts Google Drive folder/file links, Dropbox, or OneDrive public
    shares. Each document is chunked and forwarded to the capture pipeline
    with full source provenance in source_meta.

    Returns a summary of what was ingested and any errors.
    """
    _rate_check(request, "ingest")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503,
                            detail=f"concordance-engine not available: {_ENGINE_ERROR}")

    import re as _re, requests as _req

    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    label = (req.source_label or "").strip() or "drive_import"
    clean_label = "".join(c if c.isalnum() or c == "_" else "_" for c in label.lower())
    base_tags = list(req.tags or []) + [f"source:{clean_label}", "drive_import"]

    docs_to_fetch: list[dict] = []   # [{"url": ..., "name": ...}]

    # ── Google Drive folder ────────────────────────────────────────────
    gd_folder = _re.search(r'drive\.google\.com/drive/folders/([0-9A-Za-z_\-]+)', url)
    gd_file   = _re.search(r'drive\.google\.com/file/d/([0-9A-Za-z_\-]+)', url)
    gd_doc    = _re.search(r'docs\.google\.com/document/d/([0-9A-Za-z_\-]+)', url)

    if gd_folder:
        folder_id = gd_folder.group(1)
        files = _gdrive_folder_file_ids(folder_id)
        for f in files[:req.max_docs]:
            docs_to_fetch.append({
                "url": _gdrive_export_url(f["id"]),
                "name": f["name"],
                "source_url": f"https://drive.google.com/file/d/{f['id']}/view",
            })
    elif gd_file or gd_doc:
        fid = (gd_file or gd_doc).group(1)
        docs_to_fetch.append({
            "url": _gdrive_export_url(fid),
            "name": label,
            "source_url": url,
        })
    elif "dropbox.com" in url:
        # Convert Dropbox share URL to direct download
        dl_url = url.replace("?dl=0", "?dl=1").replace("www.dropbox.com", "dl.dropboxusercontent.com")
        docs_to_fetch.append({"url": dl_url, "name": label, "source_url": url})
    elif "onedrive.live.com" in url or "1drv.ms" in url:
        # OneDrive direct download — append ?download=1 for public share links
        dl_url = url + ("&download=1" if "?" in url else "?download=1")
        docs_to_fetch.append({"url": dl_url, "name": label, "source_url": url})
    else:
        # Treat the URL as a direct document link
        docs_to_fetch.append({"url": url, "name": label, "source_url": url})

    if not docs_to_fetch:
        raise HTTPException(status_code=400,
                            detail="Could not identify documents at this URL. "
                                   "Make sure it is a public share link.")

    try:
        from concordance_engine import journal as _journal
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"journal not available: {e}")

    results = {"ingested": 0, "skipped": 0, "errors": [], "docs": []}

    for doc in docs_to_fetch[:req.max_docs]:
        doc_name = doc.get("name", "document")
        try:
            text = _fetch_text_from_url(doc["url"])
            if len(text.split()) < 30:
                results["skipped"] += 1
                continue
            chunks = _chunk_text(text, req.chunk_words)
            doc_result = {"name": doc_name, "chunks": len(chunks), "captured": 0}
            for i, chunk in enumerate(chunks):
                meta = {
                    "title":      doc_name,
                    "source_url": doc.get("source_url", url),
                    "folder_url": url,
                    "collection": label,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                entry = _journal.capture(
                    chunk,
                    tags=base_tags + [f"doc:{doc_name[:40]}"],
                    look_up_precedent=False,
                )
                if entry:
                    doc_result["captured"] += 1
                    results["ingested"] += 1
            results["docs"].append(doc_result)
        except Exception as exc:
            results["errors"].append({"doc": doc_name, "error": str(exc)})

    return results


@app.post("/journal/write", include_in_schema=True)
def journal_write(request: Request, req: WriteRequest):
    """Capture a stream-of-consciousness seed.

    Bare text in. Categorization out. Nothing replaces what was
    written. The engine listens and returns:
      * the entry id (seed lands in the user's library)
      * what was heard (anchors / actions / scope / shape)
      * calibration measurements (drift / pattern / tempo against
        history) — descriptive only, never prescriptive
      * closest precedent body — if the well already holds a record
        whose scaffold dimensions overlap, the user sees it at the
        moment of writing (assist in wisdom; show engineering)
    """
    _rate_check(request, "journal")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"concordance-engine not installed: {_ENGINE_ERROR}",
        )
    try:
        from concordance_engine import journal as _journal
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"journal module not available: {e}")

    try:
        entry = _journal.capture(
            req.text,
            tags=req.tags,
            look_up_precedent=req.look_up_precedent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cal = _journal.calibrate(entry)

    # Closest-case overlay: enrich the response with the full
    # precedent body when one was matched. Frontend renders this
    # as a small "this resembles..." card so the user sees the
    # well catch their thought as they write it.
    closest = _resolve_closest_precedent(entry.categorization.closest_precedent_id)

    return {
        "entry": entry.to_dict(),
        "calibration": cal.to_dict(),
        "closest_precedent": closest,
        "rendered_calibration": _journal.render_calibration(entry, cal),
    }


@app.get("/journal/recent", include_in_schema=True)
def journal_recent(
    limit: int = Query(20, ge=1, le=200),
    tag: Optional[str] = Query(None),
    since: Optional[float] = Query(None),
):
    """List recent journal seeds (newest first). Optional tag /
    since filters."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entries = store.list_all(since=since, tag=tag)[:limit]
    return {"count": len(entries), "entries": [e.to_dict() for e in entries]}


@app.get("/journal/{entry_id}", include_in_schema=True)
def journal_show(entry_id: str):
    """Show a single journal seed in full."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return entry.to_dict()


@app.get("/journal/{entry_id}/thread", include_in_schema=True)
def journal_thread(entry_id: str):
    """Find seeds that share signal with this one (return-thread)."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    source = store.load(entry_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    related = _journal.thread(entry_id)
    return {
        "source_id": entry_id,
        "count": len(related),
        "entries": [e.to_dict() for e in related],
    }


@app.post("/journal/{entry_id}/annotate", include_in_schema=True)
def journal_annotate(entry_id: str, req: AnnotateRequest):
    """Append an annotation. Original text is preserved."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        updated = _journal.annotate(
            entry_id, req.note, author=req.author or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


@app.get("/journal/{entry_id}/calibration", include_in_schema=True)
def journal_calibration(entry_id: str):
    """Run calibration for an existing entry against current history."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    cal = _journal.calibrate(entry)
    return {
        "entry_id": entry_id,
        "calibration": cal.to_dict(),
        "rendered": _journal.render_calibration(entry, cal),
    }


# ── Shelf (community tier) ───────────────────────────────────────────


_SHELF_TAG = "shelf"


@app.get("/shelf", include_in_schema=True)
def shelf_list(limit: int = Query(50, ge=1, le=500)):
    """List entries on the shelf — community-visible seeds."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entries = store.list_all(tag=_SHELF_TAG)[:limit]
    return {"count": len(entries), "entries": [e.to_dict() for e in entries]}


@app.post("/shelf/{entry_id}", include_in_schema=True)
def shelf_publish(entry_id: str):
    """Publish a seed to the shelf (anyone reaching for it can find it)."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    if _SHELF_TAG not in entry.user_tags:
        entry.user_tags = list(entry.user_tags) + [_SHELF_TAG]
        entry.modified_at = time.time()
        store.save(entry)
    return entry.to_dict()


@app.delete("/shelf/{entry_id}", include_in_schema=True)
def shelf_unshelf(entry_id: str):
    """Remove a seed from the shelf — keep it in the library only."""
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    store = _journal.JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    if _SHELF_TAG in entry.user_tags:
        entry.user_tags = [t for t in entry.user_tags if t != _SHELF_TAG]
        entry.modified_at = time.time()
        store.save(entry)
    return entry.to_dict()


# ── Keeping (the liturgical layer surface) ───────────────────────────


@app.get("/keeping/status", include_in_schema=True)
def keeping_status(
    since: Optional[float] = Query(None,
        description="Unix epoch seconds; default: last 24h."),
):
    """What the keeping kept while you were away.

    Returns per-practice run-count and latest observation across the
    look-back window. Default window: 24 hours.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    if since is None:
        since = time.time() - 86400.0
    return _keeping.while_you_were_away(since=since)


@app.post("/keeping/walk", include_in_schema=True)
def keeping_walk():
    """Run one tick of the keeper. Each due practice fires once.

    Useful for nudging the keeping along when a daemon isn't running
    in the background. Server-managed background ticker is separate
    (see `concordance keep run` for the daemon mode).
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    keeper = _keeping.default_keeper()
    observations = keeper.tick()
    return {
        "observations": [o.to_dict() for o in observations],
        "count": len(observations),
    }


# ── Dawn (optional, read-only perimeter walk) ──────────────────────
#
# Per KoA Trilogy (Anna's chapter): the walk before the settlement
# wakes. Surfaces what's been kept across keeping + ledger +
# quarantine, in one read-only call. Always available when the engine
# is loaded, but defensively imported — if dawn.py or any dependency
# is missing, the endpoint reports unavailable rather than 500.


@app.get("/dawn", include_in_schema=True)
def dawn_endpoint(
    since: Optional[float] = Query(
        None,
        description="Unix epoch seconds; default: last 24h.",
    ),
    hours: Optional[float] = Query(
        None,
        description="Convenience: look back N hours (overrides `since`).",
    ),
    rendered: bool = Query(
        True,
        description="Include the rendered markdown narrative alongside "
                    "the structured surface (default: true).",
    ),
):
    """Read what the kingdom has been keeping while you were away.

    Read-only. No side effects. No verdicts — names what's been kept.
    Closes with a Socratic question, never a directive.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    try:
        from concordance_engine import dawn as _dawn
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"dawn module unavailable: {exc}"
        )
    if hours is not None:
        since = time.time() - (hours * 3600.0)
    surface = _dawn.gather_dawn(since=since)
    out = {"surface": surface.to_dict()}
    if rendered:
        out["rendered"] = _dawn.render_dawn(surface)
    return out


# ── Ask (search the seed bank or capture a new seed) ────────────────


class AskRequest(BaseModel):
    question: str
    capture_if_no_survivors: bool = True
    max_survivors: int = 5
    max_eliminated: int = 10
    max_journal_entries: int = 500  # cap journal scan to avoid O(n²) disk I/O


@app.post("/ask", include_in_schema=True)
def ask_endpoint(req: AskRequest):
    """Search the seed bank with elimination + fruit ranking.

    Apophatic + cataphatic: eliminate misfits with reasons (the
    elimination trail IS the reasoning), then rank survivors by good
    fruit (sealed + unamended + recurring + threaded). If nothing
    survives, capture the question itself as a new seed.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    try:
        from concordance_engine import ask as ask_mod
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"ask module unavailable: {e}")
    try:
        result = ask_mod.ask(
            req.question,
            capture_if_no_survivors=req.capture_if_no_survivors,
            max_survivors=req.max_survivors,
            max_eliminated=req.max_eliminated,
            max_journal_entries=req.max_journal_entries,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "result": result.to_dict(),
        "rendered": ask_mod.render_ask(result),
    }


# ── /path — standalone model: classify → retrieve → compose ──────────


class PathRequest(BaseModel):
    text: str
    identity_acknowledged: bool = False
    gate_verdicts: Optional[Dict[str, str]] = None  # optional override from external gate engine


@app.post("/path", include_in_schema=True)
def path_endpoint(req: PathRequest):
    """Standalone model: classify a submission and return a structured path.

    Runs: classifier → Scripture retrieval → personal context overlay →
    path composer. Returns a PathResult per spec §7.

    The path is not an answer. It points back to the text and the people
    who should see this with you.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 10_000:
        raise HTTPException(status_code=400, detail="text too long (max 10,000 chars)")

    try:
        from concordance_engine.classifier import classify
        from concordance_engine.scripture_retrieval import retrieve
        from concordance_engine.context_retriever import retrieve_context
        from concordance_engine.path_composer import compose
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"standalone model unavailable: {e}")

    try:
        classification = classify(text)
        retrieval = retrieve(classification.primary_type, text)
        context = retrieve_context(text, classification.primary_type)
        result = compose(classification, retrieval, context, req.gate_verdicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"path composition failed: {e}")

    return result.to_dict()


# ── Community feed (widespread + directly shared with viewer) ──────


class ShareWithRequest(BaseModel):
    recipient: str


@app.get("/community", include_in_schema=True)
def community_feed_endpoint(
    viewer: str = Query("default"),
    limit: int = Query(20, ge=1, le=200),
):
    """The community feed visible to a given viewer.

    Includes shelf-published seeds (widespread; anyone sees) plus
    seeds directly shared with this viewer (private to them).
    Newest first.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    items = _journal.community_feed(viewer=viewer, limit=limit)
    return {
        "viewer": viewer,
        "count": len(items),
        "items": [i.to_dict() for i in items],
    }


@app.post("/journal/{entry_id}/share", include_in_schema=True)
def journal_share_with(entry_id: str, req: ShareWithRequest):
    """Share a seed directly with a recipient. Adds the
    `shared_with:<recipient>` tag — only the recipient's community
    feed shows it. Multiple recipients via repeated calls.
    """
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        updated = _journal.share_with(entry_id, recipient=req.recipient)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


@app.delete("/journal/{entry_id}/share/{recipient}", include_in_schema=True)
def journal_unshare_with(entry_id: str, recipient: str):
    """Withdraw a direct share. Seed remains in library; tag removed."""
    _safe_id(entry_id, "entry_id")
    _safe_recipient(recipient, "recipient")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    updated = _journal.unshare_with(entry_id, recipient=recipient)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
    return updated.to_dict()


# ── Bins (emergent clusters of the user's life) ────────────────────


@app.get("/bins", include_in_schema=True)
def bins_endpoint(min_recurrence: int = Query(3, ge=1, le=20)):
    """Surface emergent bins from the user's library.

    Bins are named by use — anchor / person / action / feeling /
    packet shape — and form when a signal recurs across at least
    `min_recurrence` entries (default 3). Sorted by size descending.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    bins = _journal.infer_bins(min_recurrence=min_recurrence)
    return {
        "count": len(bins),
        "bins": [b.to_dict() for b in bins],
        "rendered": _journal.render_bins(bins),
    }


@app.get("/bins/{bin_id:path}", include_in_schema=True)
def bins_review(bin_id: str):
    """Review one bin in full — signature + every entry's text +
    metadata. Bin ids are kind-prefixed (e.g. `anchor:Mt 5:37`)."""
    # Bin ids may contain spaces and colons (e.g. "anchor:Mt 5:37");
    # we still reject path-traversal and null bytes explicitly.
    if not bin_id or ".." in bin_id or "\x00" in bin_id or "/" in bin_id or "\\" in bin_id or len(bin_id) > 200:
        raise HTTPException(status_code=400, detail="invalid bin_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    review = _journal.review_bin(bin_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"no bin {bin_id}")
    return review


# ── Promotion (individual → community → central tier) ──────────────


class PromoteRequest(BaseModel):
    confession: str
    witnesses: List[str] = []
    summary: Optional[str] = None


@app.post("/journal/{entry_id}/promote", include_in_schema=True)
def journal_promote(entry_id: str, req: PromoteRequest):
    """Promote a journal seed to the central seed bank.

    Translates the seed's categorization into a packet, runs the four
    gates, seals to the audit chain on PASS. On REJECT/QUARANTINE,
    surfaces the gate verdicts + reasons (the elimination trail) and
    leaves the seed unchanged.
    """
    _safe_id(entry_id, "entry_id")
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    try:
        result = _journal.promote(
            entry_id,
            confession=req.confession,
            witnesses=list(req.witnesses or []),
            summary=req.summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "result": result.to_dict(),
        "rendered": _journal.render_promotion(result),
    }


# ── Emergence (what the engine sees emerging across recent entries) ─


@app.get("/emergence", include_in_schema=True)
def emergence_endpoint(
    window_days: int = Query(30, ge=1, le=365),
):
    """Surface patterns across recent journal entries — recurring
    anchors, standing tasks, dates, people, action shapes, feelings.

    Per Matt 2026-05-03: "We see what is being created before the
    creator." The engine names patterns the user may not have named
    yet; descriptive only, never directive.
    """
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import journal as _journal
    em = _journal.emergence(window_days=window_days)
    return {
        "emergence": em.to_dict(),
        "rendered": _journal.render_emergence(em),
    }


@app.get("/keeping/log", include_in_schema=True)
def keeping_log(
    since: Optional[float] = Query(None),
    practice: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Read the keeping log (append-only practice observations).
    Optional filters by practice name / timestamp."""
    if not _ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="engine unavailable")
    from concordance_engine import keeping as _keeping
    log = _keeping.KeepingLog()
    observations = log.read(since=since, practice=practice)[-limit:]
    return {
        "count": len(observations),
        "observations": [o.to_dict() for o in observations],
    }


# ── Domain Verifier REST API ────────────────────────────────────────────
#
# POST /verify/{domain}   — run a verifier, record in packet store
# GET  /verifiers         — list available domain verifiers
# GET  /packets           — list domains with stored entries
# GET  /packets/{domain}  — list entries for a domain (newest first)
# GET  /packets/{domain}/{entry_id} — fetch one entry
#
# {domain} is the suffix of a tool name in ALL_TOOLS after "verify_".
# Examples: number_theory, cryptography, quantum_computing, mathematics,
# chemistry, physics_dimensional, statistics_pvalue, biology ...
# Call GET /verifiers for the full list.
#
# Packet store: data/packets/{domain}.jsonl — one line per verified packet.
# Each entry carries the input spec, the tool output, and a summary.


class VerifyRequest(BaseModel):
    spec: Dict[str, Any]


def _verify_summary(result: Any) -> str:
    """Derive CONFIRMED/MISMATCH/PARTIAL/NOT_APPLICABLE/ERROR from tool output.

    Handles two shapes returned by ALL_TOOLS wrappers:
      {"checks": [{"status": "CONFIRMED", ...}, ...]}   <- array form
      {"check_name": {"status": "CONFIRMED", ...}, ...} <- flat dict form
    """
    if not isinstance(result, dict):
        return "UNKNOWN"
    if "checks" in result and isinstance(result["checks"], list):
        statuses = [c.get("status", "") for c in result["checks"]
                    if isinstance(c, dict)]
    else:
        statuses = [v["status"] for v in result.values()
                    if isinstance(v, dict) and "status" in v]
    if not statuses:
        return "NOT_APPLICABLE"
    if any(s == "ERROR" for s in statuses):
        return "ERROR"
    if any(s == "MISMATCH" for s in statuses):
        return "MISMATCH"
    if all(s == "CONFIRMED" for s in statuses):
        return "CONFIRMED"
    if all(s == "NOT_APPLICABLE" for s in statuses):
        return "NOT_APPLICABLE"
    if any(s == "CONFIRMED" for s in statuses):
        return "PARTIAL"
    return "NOT_APPLICABLE"


def _is_safe_peer_url(url: str) -> bool:
    """Return True only if the URL targets a non-private, non-loopback host (SSRF guard)."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname or ""
        if not host:
            return False
        # Block loopback and private ranges
        addr = ipaddress.ip_address(host)
        return not (addr.is_loopback or addr.is_private or addr.is_link_local)
    except ValueError:
        # hostname is a DNS name — allow it; resolution happens at urlopen time
        host_lower = (urllib.parse.urlparse(url).hostname or "").lower()
        blocked = ("localhost", "metadata.google.internal", "169.254.")
        return not any(host_lower == b or host_lower.startswith(b) for b in blocked)


def _broadcast_packet(entry: Dict[str, Any]) -> None:
    """Push a signed packet to all known peers (best-effort, bounded thread pool)."""
    import urllib.request

    def _push():
        try:
            peers = _peer_list()
            if not peers:
                return
            payload = json.dumps(entry, default=str).encode("utf-8")
            for peer in peers:
                raw_url = peer.get("url", "").rstrip("/")
                if not _is_safe_peer_url(raw_url):
                    _log.warning("broadcast: skipping peer with unsafe URL %r", raw_url)
                    continue
                url = raw_url + "/packets/import"
                try:
                    req = urllib.request.Request(
                        url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=5):
                        pass
                    _peer_update_seen(peer["instance_id"], packets_synced=1)
                except Exception as exc:
                    _log.debug("broadcast to %s failed: %s", url, exc)
        except Exception as exc:
            _log.error("broadcast thread error: %s", exc, exc_info=True)

    _BROADCAST_POOL.submit(_push)


@app.get("/verifiers", include_in_schema=True)
def list_verifiers():
    """List all available domain verifiers and registered domain aliases.

    Use the tool names as the {domain} segment in POST /verify/{domain}.
    """
    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
        from concordance_engine.verifiers import VERIFIERS
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"engine unavailable: {e}")
    tools = sorted(k for k in ALL_TOOLS if k.startswith("verify_"))
    return {
        "count": len(tools),
        "tools": tools,
        "domain_aliases": {k: v.rsplit(".", 1)[-1] for k, v in VERIFIERS.items()},
        "usage": "POST /verify/{domain} with body {\"spec\": {<domain fields>}}",
    }


@app.post("/verify/{domain}", include_in_schema=True)
def verify_domain(domain: str, req: VerifyRequest):
    """Run a domain verifier and record the result in the packet store.

    {domain} must match a tool name suffix — e.g. `number_theory` maps to
    the `verify_number_theory` tool. Spec fields are domain-specific; see
    the verifier's docstring or the benchmark items for examples.

    Result is written to data/packets/{domain}.jsonl and returned in the
    response alongside the entry_id for later retrieval.
    """
    _safe_domain(domain)
    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"engine unavailable: {e}")

    tool_name = f"verify_{domain}"
    fn = ALL_TOOLS.get(tool_name)
    if fn is None:
        available = sorted(k for k in ALL_TOOLS if k.startswith("verify_"))
        raise HTTPException(status_code=404, detail={
            "error": f"no verifier for '{domain}'",
            "tool_tried": tool_name,
            "available": available,
        })

    try:
        result = fn(req.spec)
    except Exception as e:
        # Verifier threw — enqueue for retry rather than dropping the request.
        queue_id = _queue_enqueue(domain, req.spec, reason=f"{type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail={
            "error": f"verifier error: {type(e).__name__}: {e}",
            "queued": True,
            "queue_id": queue_id,
            "message": "Request enqueued for retry when verifier is available.",
        })

    from api.packet_store import get_packet_store
    entry = get_packet_store().append(domain, req.spec, result)
    summary = _verify_summary(result)

    # Record in trust index so multi-instance confirmations accumulate.
    instance_id = entry.get("_instance_id", "")
    trust_record = _trust_record(domain, req.spec, instance_id, summary=summary, entry_id=entry.get("id"))

    # Broadcast to known peers (fire-and-forget, best-effort).
    _broadcast_packet(entry)

    return {
        "domain": domain,
        "tool": tool_name,
        "entry_id": entry["id"],
        "timestamp_iso": entry["timestamp_iso"],
        "summary": summary,
        "trust_count": trust_record.get("count", 1),
        "results": result,
    }


@app.get("/packets", include_in_schema=True)
def packets_domains():
    """List all domains that have stored packet entries, with counts."""
    from api.packet_store import get_packet_store
    store = get_packet_store()
    return {
        "domains": store.domains(),
        "stats": store.stats(),
    }


@app.get("/packets/{domain}", include_in_schema=True)
def packets_list(
    domain: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List verified packet entries for a domain, newest first.

    Returns the stored spec + verification results for every packet
    submitted to this domain via POST /verify/{domain}.
    """
    _safe_domain(domain)
    from api.packet_store import get_packet_store
    entries = get_packet_store().list(domain, limit=limit, offset=offset)
    return {
        "domain": domain,
        "count": len(entries),
        "offset": offset,
        "entries": entries,
    }


@app.get("/packets/{domain}/{entry_id}", include_in_schema=True)
def packets_get(domain: str, entry_id: str):
    """Fetch one packet entry by domain and entry_id, including trust metadata."""
    _safe_domain(domain)
    _safe_id(entry_id, "entry_id")
    from api.packet_store import get_packet_store
    entry = get_packet_store().get(domain, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"no entry '{entry_id}' in domain '{domain}'",
        )
    trust = _trust_get(domain, entry.get("spec", {}))
    if trust:
        entry["_trust_count"] = trust.get("count", 0)
        entry["_confirmed_instances"] = trust.get("instance_ids", [])
    return entry


class SearchRequest(BaseModel):
    spec: Dict[str, Any]
    limit: int = 10
    confirmed_only: bool = False


@app.post("/packets/{domain}/search", include_in_schema=True)
def packets_search(domain: str, req: SearchRequest):
    """Find closest prior packets for a domain by spec-field overlap.

    Uses Jaccard similarity on spec keys + exact-value matches to rank
    stored entries. Returns the top matches (newest first within each
    score tier) so the caller can overlay their situation onto the
    closest precedent's verification trace.

    confirmed_only=true restricts results to CONFIRMED entries — useful
    when looking for verified precedents rather than all attempts.
    """
    _safe_domain(domain)
    from api.packet_store import get_packet_store
    store = get_packet_store()
    candidates = store.list(domain, limit=500, offset=0)  # read all
    if req.confirmed_only:
        candidates = [c for c in candidates if c.get("summary") == "CONFIRMED"]

    query_keys = set(req.spec.keys())

    def _score(entry: Dict[str, Any]) -> float:
        stored_spec = entry.get("spec") or {}
        stored_keys = set(stored_spec.keys())
        if not query_keys and not stored_keys:
            return 0.0
        union = query_keys | stored_keys
        intersection = query_keys & stored_keys
        jaccard = len(intersection) / len(union) if union else 0.0
        # Bonus for matching values
        value_hits = sum(
            1 for k in intersection
            if req.spec.get(k) == stored_spec.get(k)
        )
        value_bonus = value_hits / len(union) if union else 0.0
        return jaccard + value_bonus * 0.5

    scored = sorted(candidates, key=_score, reverse=True)
    top = scored[: max(1, req.limit)]
    return {
        "domain": domain,
        "query_keys": sorted(query_keys),
        "count": len(top),
        "matches": [
            {**e, "similarity_score": round(_score(e), 4)}
            for e in top
        ],
    }


class ChainStep(BaseModel):
    domain: str
    spec: Dict[str, Any]


class ChainRequest(BaseModel):
    steps: List[ChainStep]
    label: Optional[str] = None


@app.post("/verify/chain", include_in_schema=True)
def verify_chain_endpoint(req: ChainRequest):
    """Run a multi-step cross-domain verification chain.

    Each step names a domain + spec. Steps run in order. Each result is
    stored in the packet store. The chain_summary is CONFIRMED only if
    every step confirms; MISMATCH if any step mismatches; ERROR if any
    step errors; PARTIAL otherwise.

    Use this for compound claims that span domains — e.g. a clinical
    decision that involves a BMI check (medicine), a drug-interaction
    formula (chemistry), and a dosing calculation (medicine again).
    """
    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"engine unavailable: {e}")

    from api.packet_store import get_packet_store
    store = get_packet_store()

    if not req.steps:
        raise HTTPException(status_code=400, detail="steps list is empty")

    step_results = []
    all_summaries = []

    for i, step in enumerate(req.steps):
        tool_name = f"verify_{step.domain}"
        fn = ALL_TOOLS.get(tool_name)
        if fn is None:
            available = sorted(k for k in ALL_TOOLS if k.startswith("verify_"))
            raise HTTPException(status_code=404, detail={
                "error": f"step {i}: no verifier for '{step.domain}'",
                "available": available,
            })
        try:
            result = fn(step.spec)
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}

        entry = store.append(step.domain, step.spec, result)
        summary = _verify_summary(result)
        all_summaries.append(summary)
        step_results.append({
            "step": i,
            "domain": step.domain,
            "entry_id": entry["id"],
            "summary": summary,
            "results": result,
        })

    if any(s == "ERROR" for s in all_summaries):
        chain_summary = "ERROR"
    elif any(s == "MISMATCH" for s in all_summaries):
        chain_summary = "MISMATCH"
    elif all(s == "CONFIRMED" for s in all_summaries):
        chain_summary = "CONFIRMED"
    elif all(s == "NOT_APPLICABLE" for s in all_summaries):
        chain_summary = "NOT_APPLICABLE"
    else:
        chain_summary = "PARTIAL"

    return {
        "label": req.label,
        "step_count": len(step_results),
        "chain_summary": chain_summary,
        "steps": step_results,
    }


# ── Agent dispatch (NL → verifier) ─────────────────────────────────────
#
# POST /agent   — natural language in, verifier results out
# GET  /agent/rules — list all registered NL dispatch rules
#
# The rule-based dispatcher runs first (zero cost, offline-capable).
# On a miss, the oracle adapter is called if an oracle key is configured.
# Every call — rule-hit or oracle — is logged as a training example in
# data/agent_training/{domain}.jsonl so coverage improves over time.


class AgentRequest(BaseModel):
    text: str
    use_oracle: bool = True   # fall through to oracle on rule miss
    oracle_model: str = "claude-haiku-4-5-20251001"


def _no_match_fallback(text: str, reason: str) -> Dict[str, Any]:
    """Helpful structured response when /agent can't classify the input.

    Cold LLM clients (ChatGPT Search, Grok, Perplexity) hitting the engine
    for the first time often don't know what to send. Instead of returning
    an opaque 'no rule matched', surface the engine's actual menu — which
    domains exist, what shape /verify expects, and where to read the full
    manifest. The agent can self-correct on the next request."""
    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
        verifiers = sorted(
            t.replace("verify_", "") for t in ALL_TOOLS.keys()
            if t.startswith("verify_")
        )
    except Exception:
        verifiers = []
    return {
        "matched": False,
        "text": text,
        "reason": reason,
        "next_steps": [
            "Read https://narrowhighway.com/manifest for the full tool catalog "
            "(76 tools including the verifiers below).",
            "Read https://narrowhighway.com/llms.txt for end-to-end examples.",
            "Call POST /verify with {tool: 'verify_<domain>', spec: {...}} "
            "directly if you know the domain.",
            "Or POST /polymathic with {situation: '<plain language>'} for "
            "multi-domain synthesis with axis overlap.",
        ],
        "available_verifiers": verifiers,
        "verifier_count": len(verifiers),
        "examples": [
            {
                "domain": "physics",
                "spec_shape": {
                    "conservation": {
                        "before": {"KE": 0, "PE": 25},
                        "after": {"KE": 25, "PE": 0},
                        "law": "energy",
                    }
                },
            },
            {
                "domain": "statistics_pvalue",
                "spec_shape": {
                    "test": "paired_t",
                    "n": 20,
                    "mean_diff": 0.5,
                    "sd_diff": 1.0,
                    "tail": "two",
                    "claimed_p": 0.0375,
                },
            },
            {
                "domain": "chemistry",
                "spec_shape": {
                    "claim": {
                        "lhs": [["H2", 2], ["O2", 1]],
                        "rhs": [["H2O", 2]],
                    }
                },
            },
        ],
    }


def _log_training(domain: str, text: str, spec: Dict[str, Any],
                  result: Any, source: str) -> None:
    """Append one training example to data/agent_training/{domain}.jsonl."""
    import uuid as _uuid
    from api.packet_store import _summarize
    # Defense in depth: refuse domain names that could escape the
    # training directory. Callers should already have validated, but
    # this is a low-cost belt-and-suspenders check.
    if not domain or not _SAFE_DOMAIN_RE.match(domain):
        return
    path = Path("data/agent_training") / f"{domain}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": str(_uuid.uuid4()),
        "timestamp_epoch": int(time.time()),
        "domain": domain,
        "nl_input": text,
        "spec": spec,
        "verifier_summary": _summarize(result) if isinstance(result, dict) else "UNKNOWN",
        "source": source,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def _call_oracle(text: str, model: str) -> Optional[Dict[str, Any]]:
    """Ask an AI oracle to extract {domain, spec} from text.
    Returns None if oracle is unavailable or fails.
    Oracle response must be valid JSON with 'domain' and 'spec' keys.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system = (
            "You are a field extractor for a deterministic verification engine. "
            "Given natural language describing a calculation or claim, output ONLY "
            "valid JSON with exactly two keys: 'domain' and 'spec'. "
            "domain must be one of: chemistry, physics, statistics, mathematics, "
            "computer_science, economics, labor, real_estate, construction, "
            "soil_science, medicine, cybersecurity, nutrition, finance, governance, "
            "biology, genetics, agriculture, cryptography, energy, networking, "
            "electrical, acoustics, optics, geology, information_theory, "
            "music_theory, number_theory, geography, combinatorics, geometry, "
            "meteorology, hydrology, photography, sports_analytics, astronomy, "
            "calendar_time, manufacturing, exercise_science, formal_logic, "
            "linguistics, quantum_computing. "
            "spec must contain the numeric/string fields the verifier needs. "
            "Output only the JSON object, nothing else."
        )
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        content = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return None


@app.get("/agent", include_in_schema=True, tags=["agents"])
def agent_endpoint_get(
    request: Request,
    text: str = Query(..., description="Natural-language situation or claim to verify."),
    use_oracle: bool = Query(True, description="Fall through to AI extraction on rule miss."),
    oracle_model: str = Query("claude-haiku-4-5-20251001", description="Oracle model name."),
):
    """GET-style natural-language verification dispatch.

    For browse-only LLM clients — ChatGPT Search, Perplexity, Grok's web
    fetch — that can pull a URL but can't easily POST JSON. Same engine
    behavior as POST /agent: rule-based classification → optional oracle
    extraction → deterministic verifier → corpus-first hit if previously
    confirmed.

    Examples:
      /agent?text=A+2kg+object+at+5m/s+has+25J+kinetic+energy
      /agent?text=The+balanced+equation+for+photosynthesis
      /agent?text=Is+the+claimed+p-value+0.04+correct+for+n=20+t-test+with+mean+0.5+sd+1.0

    Returns the verifier's structured result, or — on no-match — a
    helpful pointer at /manifest plus a list of recognized domains so
    the caller knows how to reformulate."""
    req = AgentRequest(text=text, use_oracle=use_oracle, oracle_model=oracle_model)
    return agent_endpoint(request, req)


@app.post("/agent", include_in_schema=True)
def agent_endpoint(request: Request, req: AgentRequest):
    """Natural language → domain classification → spec extraction → verifier.

    Runs the rule-based dispatcher first (offline-capable, zero cost).
    On a miss, optionally calls the configured oracle (any AI) to extract
    the domain and spec fields. Every call is logged as a training example
    so rule coverage grows over time and oracle dependency decreases.

    This is the 'new substrate' endpoint: the caller speaks plain language;
    the engine speaks verified math. No probabilistic answer is returned —
    only the deterministic verifier result.

    Rate-limited per-IP at 12/min — oracle misses use the paid API.
    """
    _rate_check(request, "agent")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        from concordance_engine.agent.dispatch import dispatch as _dispatch
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"agent layer unavailable: {e}")

    source = "rule"
    result_dispatch = _dispatch(text)
    domain = None
    spec: Dict[str, Any] = {}

    if result_dispatch is not None:
        domain = result_dispatch.domain
        spec = result_dispatch.spec
        rule_id = result_dispatch.rule_id
    elif req.use_oracle:
        oracle_out = _call_oracle(text, req.oracle_model)
        if oracle_out and "domain" in oracle_out and "spec" in oracle_out:
            domain = oracle_out["domain"]
            spec = oracle_out.get("spec") or {}
            rule_id = f"oracle:{req.oracle_model}"
            source = "oracle"
        else:
            return _no_match_fallback(text, "oracle_unavailable")
    else:
        return _no_match_fallback(text, "rule_miss_no_oracle")

    tool_name = f"verify_{domain}"
    fn = ALL_TOOLS.get(tool_name)
    if fn is None:
        return {
            "matched": True,
            "domain": domain,
            "spec": spec,
            "error": f"no verifier registered for domain '{domain}'",
        }

    # ── Corpus-first lookup (Lever 1) ──────────────────────────────────
    # Check the trust index for a prior confirmed result on this exact spec.
    # If one exists with trust_count >= 1, return it instantly — no verifier
    # call needed, no compute spent. The corpus is the oracle.
    from api.packet_store import get_packet_store
    store = get_packet_store()
    trust = _trust_get(domain, spec)
    if trust and trust.get("count", 0) >= 1 and trust.get("summary") == "CONFIRMED":
        # O(1) lookup via stored entry_id — avoids scanning store.list(limit=200).
        candidate = None
        latest_eid = trust.get("latest_entry_id")
        if latest_eid:
            try:
                candidate = store.get(domain, latest_eid)
            except Exception:
                candidate = None
        if candidate:
            return {
                "matched": True,
                "source": "corpus",
                "rule_id": rule_id if result_dispatch else f"oracle:{req.oracle_model}",
                "domain": domain,
                "spec": spec,
                "entry_id": candidate["id"],
                "summary": candidate.get("summary"),
                "trust_count": trust.get("count", 1),
                "confirmed_instances": trust.get("instance_ids", []),
                "verified_at_epoch": trust.get("last_seen"),
                "retrieved_from_cache_at_epoch": int(time.time()),
                "results": candidate.get("results"),
                "note": "Returned from verified corpus — verifier not re-run.",
            }
    # ── Corpus miss: run verifier ───────────────────────────────────────
    try:
        verifier_result = fn(spec)
    except Exception as e:
        verifier_result = {"error": str(e)}

    _log_training(domain, text, spec, verifier_result, source)

    entry = store.append(domain, spec, verifier_result)

    # Record in trust index and broadcast.
    instance_id = entry.get("_instance_id", "")
    summary_val = entry.get("summary", "UNKNOWN")
    trust_record = _trust_record(domain, spec, instance_id, summary=summary_val, entry_id=entry.get("id"))
    _broadcast_packet(entry)

    return {
        "matched": True,
        "source": source,
        "rule_id": rule_id if result_dispatch else f"oracle:{req.oracle_model}",
        "domain": domain,
        "spec": spec,
        "entry_id": entry["id"],
        "summary": summary_val,
        "trust_count": trust_record.get("count", 1),
        "results": verifier_result,
    }


class PolymathicRequest(BaseModel):
    situation: str
    oracle_model: str = "claude-haiku-4-5-20251001"
    max_domains: int = 10
    split_threshold: int = 5   # cluster when domain count exceeds this
    stop_on_discordant: bool = False  # early-exit on first DISCORDANT cluster
    store: bool = True
    # Optional contributor handle. If supplied and the handle is registered,
    # this run counts toward the contributor's polymathic stats and badges.
    # Anonymous runs are still permitted; they just don't accumulate.
    contributor_handle: str = ""


@app.post("/polymathic", include_in_schema=True)
def polymathic_endpoint(request: Request, req: PolymathicRequest):
    """Natural language situation → all applicable domains fired in parallel.

    Path C: the cross-domain coordinator. Individual domain verifiers
    fire in parallel; this endpoint coordinates them. Returns a
    PolymathicRecord with every verifier's result, axis overlaps
    (shared scaffold dimensions), and a composite verdict.

    Composite verdicts:
      CONCORDANT    — all fired domains confirmed
      DISCORDANT    — at least one mismatch, none confirmed
      MIXED         — some confirmed, some mismatched
      OUT_OF_SCOPE  — no domain matched
      ERROR         — system failure
    """
    _rate_check(request, "polymathic")
    situation = (req.situation or "").strip()
    if not situation:
        raise HTTPException(status_code=400, detail="situation is required")

    try:
        from concordance_engine.agent.poly_agent import run_polymathic
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"polymathic agent unavailable: {exc}")

    try:
        record = run_polymathic(
            situation=situation,
            model=req.oracle_model,
            max_domains=req.max_domains,
            split_threshold=req.split_threshold,
            stop_on_discordant=req.stop_on_discordant,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"polymathic agent error: {exc}")

    d = record.to_dict()

    if req.store:
        try:
            from concordance_engine.cas import store as _cas_store
            from concordance_engine.user_identity import get_user_pubkey
            from concordance_engine.poly_record import PolymathicRecord as _PR
            pub = get_user_pubkey()
            # Bind pubkey; preserve ALL fields including atomic_claims / keeper_manifest
            record_with_key = _PR(
                situation=record.situation,
                domain_results=record.domain_results,
                axis_overlaps=record.axis_overlaps,
                composite_verdict=record.composite_verdict,
                atomic_claims=record.atomic_claims,
                quarantined_claims=record.quarantined_claims,
                keeper_manifest=record.keeper_manifest,
                closest_precedent=record.closest_precedent,
                subject_pubkey=pub,
                schema_version=record.schema_version,
            )
            d_with_key = record_with_key.to_dict()
            h = _cas_store(d_with_key)
            # Bind permanent_ref and re-serialize (content_hash re-computed)
            sealed = _PR(
                situation=record.situation,
                domain_results=record.domain_results,
                axis_overlaps=record.axis_overlaps,
                composite_verdict=record.composite_verdict,
                atomic_claims=record.atomic_claims,
                quarantined_claims=record.quarantined_claims,
                keeper_manifest=record.keeper_manifest,
                closest_precedent=record.closest_precedent,
                subject_pubkey=pub,
                permanent_ref=h,
                schema_version=record.schema_version,
            )
            d = sealed.to_dict()
        except Exception:
            pass  # store failure is non-fatal

    # Community attribution — optional handle. Bumps polymathic_runs and,
    # when the composite_verdict is CONCORDANT, polymathic_concordant.
    handle = (req.contributor_handle or "").strip().lower()
    if handle and _community.is_valid_handle(handle):
        if _community.load_contributor(handle) is not None:
            _community.bump_stat(handle, "polymathic_runs", 1)
            if d.get("composite_verdict") == "CONCORDANT":
                _community.bump_stat(handle, "polymathic_concordant", 1)
            _community.log_activity({
                "kind": "polymathic_run",
                "handle": handle,
                "verdict": d.get("composite_verdict", "?"),
                "domains": [r.get("domain") for r in (d.get("domain_results") or []) if r.get("domain")][:8],
            })

    return d


class SealPolymathicRequest(BaseModel):
    """Body for `POST /seal/polymathic`.

    The PolymathicRecord must already be in the CAS (store=true on /polymathic).
    Four simplified gates then run and, if all pass, the record is written
    to the audit chain and registered in the axis dimension index so future
    runs can find it as a closest-precedent overlay.
    """
    content_hash: str


@app.post("/seal/polymathic", include_in_schema=True)
def seal_polymathic(request: Request, req: SealPolymathicRequest):
    """Seal a PolymathicRecord into the permanent audit chain.

    Simplified gate chain for polymathic records:
      RED      — composite_verdict must not be ERROR
      FLOOR    — record must have domain results or quarantined claims
      BROTHERS — subject_pubkey must be bound (CAS store binds it)
      GOD      — always PASS (adapter scope)

    On PASS: record is written to the ledger and indexed in the axis
    dimension index so future poly runs can retrieve it as a precedent.
    On QUARANTINE: subject_pubkey missing — run POST /polymathic with
    store=true first. QUARANTINE does NOT write to the ledger.
    On REJECT: nothing written.
    """
    _rate_check(request, "seal")
    _safe_hash(req.content_hash)
    record_dict = _cas_fetch(req.content_hash)
    if record_dict is None:
        raise HTTPException(status_code=404, detail=f"not found in CAS: {req.content_hash}")

    verdict     = record_dict.get("composite_verdict", "")
    dr_list     = record_dict.get("domain_results", [])
    quarantined = record_dict.get("quarantined_claims", [])
    subject_key = record_dict.get("subject_pubkey")

    gates = []

    # RED: no system ERROR
    if verdict == "ERROR":
        gates.append({"gate": "RED",      "status": "REJECT",
                      "reasons": ["composite_verdict is ERROR — resolve the system failure before sealing"]})
    else:
        gates.append({"gate": "RED",      "status": "PASS", "reasons": []})

    # FLOOR: something was verified or quarantined (not completely empty)
    if not dr_list and not quarantined:
        gates.append({"gate": "FLOOR",    "status": "REJECT",
                      "reasons": ["no domain results — nothing to seal (OUT_OF_SCOPE)"]})
    else:
        gates.append({"gate": "FLOOR",    "status": "PASS", "reasons": []})

    # BROTHERS: pubkey must be bound
    if not subject_key:
        gates.append({"gate": "BROTHERS", "status": "QUARANTINE",
                      "reasons": ["subject_pubkey not bound — run POST /polymathic with store=true first"]})
    else:
        gates.append({"gate": "BROTHERS", "status": "PASS", "reasons": []})

    # GOD: always pass (adapter scope — no elapsed-wait requirement)
    gates.append({"gate": "GOD", "status": "PASS", "reasons": []})

    statuses = [g["status"] for g in gates]
    if "REJECT" in statuses:
        overall = "REJECT"
    elif "QUARANTINE" in statuses:
        overall = "QUARANTINE"
    else:
        overall = "PASS"

    if overall != "PASS":
        return {"overall": overall, "gates": gates, "sealed": False,
                "content_hash": req.content_hash}

    # ── Write to audit chain ──────────────────────────────────────────
    ledger = get_ledger()

    class _GR:
        def __init__(self, gate, status, reasons):
            self.gate    = gate
            self.status  = status
            self.reasons = reasons

    gate_objs = [_GR(g["gate"], g["status"], g["reasons"]) for g in gates]
    packet = {
        "id":                 req.content_hash,
        "domain":             "POLYMATHIC",
        "composite_verdict":  verdict,
        "situation_summary":  record_dict.get("situation", "")[:160],
        "content_hash":       req.content_hash,
        "subject_pubkey":     subject_key,
    }
    entry = ledger.append(packet, overall, gate_objs)

    # ── Update axis dimension index ───────────────────────────────────
    try:
        from concordance_engine.axis_index import update_index as _axis_update
        all_dims: set = set()
        for ao in record_dict.get("axis_overlaps", []):
            if ao.get("dimension"):
                all_dims.add(ao["dimension"])
        for dr in dr_list:
            for dim in dr.get("axis_dims", []):
                all_dims.add(dim)
        if all_dims:
            _axis_update(
                content_hash=req.content_hash,
                composite_verdict=verdict,
                situation=record_dict.get("situation", ""),
                axis_dims=list(all_dims),
            )
    except Exception:
        pass  # index failure is non-fatal

    # ── Broadcast to federation peers ────────────────────────────────
    # Same pattern as domain-verify broadcasts: fire-and-forget, bounded
    # thread pool. Peers receive the seal receipt and can pull full content
    # via GET /cas/{content_hash} on this instance.
    try:
        _broadcast_packet({
            "id":                req.content_hash,
            "domain":            "POLYMATHIC",
            "composite_verdict": verdict,
            "content_hash":      req.content_hash,
            "ledger_seq":        entry.seq,
            "ledger_entry_hash": entry.entry_hash,
            "situation_summary": record_dict.get("situation", "")[:120],
        })
    except Exception:
        pass  # broadcast failure is non-fatal

    # ── Pipeline A2: auto-promote CONCORDANT seals to Almanac ────────
    # Every sealed CONCORDANT polymathic record is, by construction, a
    # multi-domain situation the engine has run and confirmed. Promote
    # novel domain signatures to the Almanac as kind:"protocol" entries.
    # The Almanac grows from real engine work without curator push.
    try:
        if verdict == "CONCORDANT":
            _promote_polymathic_seal_to_almanac(record_dict, req.content_hash, entry.seq)
    except Exception as exc:
        _log.warning(f"polymathic-seal promote-to-almanac failed: {exc}")

    return {
        "overall":          overall,
        "gates":            gates,
        "sealed":           True,
        "ledger_seq":       entry.seq,
        "ledger_entry_hash":entry.entry_hash,
        "content_hash":     req.content_hash,
    }


@app.get("/axis/index", include_in_schema=True)
def axis_index_stats():
    """Return statistics about the axis dimension index.

    The index grows each time a PolymathicRecord is sealed. It is the
    substrate for closest-precedent retrieval on future poly runs.
    """
    try:
        from concordance_engine.axis_index import index_stats
        return index_stats()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/axis/query", include_in_schema=True)
def axis_query(dims: str = ""):
    """Query the axis index for sealed records sharing the given dimensions.

    ?dims=authority_trust,time_sequence  (comma-separated scaffold dimensions)
    Returns all sealed PolymathicRecords that touch at least one of those dims.
    """
    if not dims:
        raise HTTPException(status_code=400, detail="dims query param required")
    dim_list = [d.strip() for d in dims.split(",") if d.strip()]
    try:
        from concordance_engine.axis_index import query_index, find_closest
        results = query_index(dim_list)
        closest = find_closest(dim_list)
        return {
            "queried_dims": dim_list,
            "match_count":  len(results),
            "matches":      results,
            "closest":      closest,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/agent/rules", include_in_schema=True)
def agent_rules():
    """List all registered NL dispatch rules (for introspection and debugging)."""
    try:
        from concordance_engine.agent.dispatch import list_rules
        rules = list_rules()
        return {
            "count": len(rules),
            "rules": rules,
            "note": "Rules run in priority order; first match wins.",
        }
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"agent layer unavailable: {e}")


@app.get("/agent/training/proposals", include_in_schema=True)
def agent_training_proposals(
    min_examples: int = Query(2, ge=1),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
):
    """Extract candidate regex rules from oracle training logs.

    Scans data/agent_training/*.jsonl for oracle-sourced confirmed examples
    and proposes regex patterns that could be promoted into dispatch.py.
    Promotion is always manual — this endpoint surfaces candidates, never
    auto-edits dispatch rules.

    Each proposal includes:
      - domain: the verifier domain
      - pattern: a candidate regex (alternation of common tokens)
      - support: number of training texts the pattern matches
      - confidence: fraction matched
      - spec_keys: fields the extraction function would need to populate
      - note: instructions for promoting to dispatch.py
    """
    try:
        from concordance_engine.agent.rule_extractor import extract_proposals
        proposals = extract_proposals(
            training_dir="data/agent_training",
            min_examples=min_examples,
            min_confidence=min_confidence,
        )
        return {
            "count": len(proposals),
            "min_examples": min_examples,
            "min_confidence": min_confidence,
            "proposals": [
                {
                    "domain": p.domain,
                    "pattern": p.pattern,
                    "support": p.support,
                    "confidence": round(p.confidence, 3),
                    "spec_keys": p.spec_keys,
                    "example_texts": p.example_texts,
                    "note": p.note,
                }
                for p in proposals
            ],
        }
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"rule extractor unavailable: {e}")


@app.get("/agent/training", include_in_schema=True)
def agent_training_stats():
    """Return training data statistics — how many labeled examples per domain."""
    training_dir = Path("data/agent_training")
    if not training_dir.exists():
        return {"domains": {}, "total": 0}
    stats: Dict[str, Any] = {}
    total = 0
    for path in sorted(training_dir.glob("*.jsonl")):
        domain = path.stem
        count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        by_source: Dict[str, int] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                s = e.get("source", "unknown")
                by_source[s] = by_source.get(s, 0) + 1
            except json.JSONDecodeError:
                continue
        stats[domain] = {"count": count, "by_source": by_source}
        total += count
    return {"domains": stats, "total": total}


class AgentSpeakRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    model_id: str = "eleven_turbo_v2_5"
    use_oracle: bool = True
    oracle_model: str = "claude-haiku-4-5-20251001"


@app.post("/agent/speak", include_in_schema=True)
def agent_speak(request: Request, req: AgentSpeakRequest):
    """Natural language → verify → speak the result as audio/mpeg.

    Combines POST /agent (NL dispatch + verification) with POST /speak
    (ElevenLabs TTS). The caller provides plain-language text; the engine:
      1. Classifies the domain and extracts spec fields (rule-based or oracle)
      2. Runs the deterministic verifier (or returns corpus hit)
      3. Synthesizes the verification result as speech and returns audio/mpeg

    The spoken output is a concise narration of the verification summary —
    domain, CONFIRMED/MISMATCH/PARTIAL, and the first check's detail line.

    Requires both ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to be set.
    Returns 503 if TTS is unavailable; caller can fall back to GET /agent for JSON.
    """
    # ElevenLabs costs money per character — share the speak budget.
    _rate_check(request, "speak")
    # 1. Verify TTS is available before running the verifier
    api_key = _el_api_key()
    voice_id = req.voice_id or _el_voice_id()
    if not api_key or not voice_id:
        raise HTTPException(
            status_code=503,
            detail="speak unavailable: ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not configured",
        )
    try:
        import requests as _requests
    except ImportError:
        raise HTTPException(status_code=503, detail="speak unavailable: `requests` not installed")

    # 2. Run the agent (reuse agent_endpoint logic without duplicating it)
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        from concordance_engine.agent.dispatch import dispatch as _dispatch
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"agent layer unavailable: {e}")

    source = "rule"
    result_dispatch = _dispatch(text)
    domain = None
    spec: Dict[str, Any] = {}
    rule_id = "miss"

    if result_dispatch is not None:
        domain = result_dispatch.domain
        spec = result_dispatch.spec
        rule_id = result_dispatch.rule_id
    elif req.use_oracle:
        oracle_out = _call_oracle(text, req.oracle_model)
        if oracle_out and "domain" in oracle_out and "spec" in oracle_out:
            domain = oracle_out["domain"]
            spec = oracle_out.get("spec") or {}
            rule_id = f"oracle:{req.oracle_model}"
            source = "oracle"

    if domain is None:
        raise HTTPException(
            status_code=422,
            detail="Could not classify domain from text. Try more structured input.",
        )

    fn = ALL_TOOLS.get(f"verify_{domain}")
    if fn is None:
        raise HTTPException(status_code=404, detail=f"no verifier for domain '{domain}'")

    # Corpus check
    from api.packet_store import get_packet_store
    from api.trust_index import spec_hash as _spec_hash
    store = get_packet_store()
    trust = _trust_get(domain, spec)
    verifier_result = None
    if trust and trust.get("count", 0) >= 1 and trust.get("summary") == "CONFIRMED":
        target_hash = _spec_hash(spec)
        for candidate in store.list(domain, limit=200, offset=0):
            if _spec_hash(candidate.get("spec", {})) == target_hash:
                verifier_result = candidate.get("results")
                summary_val = candidate.get("summary", "CONFIRMED")
                break

    if verifier_result is None:
        try:
            verifier_result = fn(spec)
        except Exception as e:
            verifier_result = {"error": str(e)}
        _log_training(domain, text, spec, verifier_result, source)
        entry = store.append(domain, spec, verifier_result)
        summary_val = entry.get("summary", "UNKNOWN")
        _trust_record(domain, spec, entry.get("_instance_id", ""), summary=summary_val, entry_id=entry.get("id"))
        _broadcast_packet(entry)

    # 3. Compose spoken text from verification result
    checks = verifier_result.get("checks", []) if isinstance(verifier_result, dict) else []
    if checks:
        first = checks[0] if isinstance(checks[0], dict) else {}
        detail_line = first.get("detail") or first.get("name") or ""
        spoken = (
            f"Domain: {domain.replace('_', ' ')}. "
            f"Result: {summary_val}. "
            f"{detail_line[:200]}"
        ).strip()
    else:
        spoken = f"Domain: {domain.replace('_', ' ')}. Result: {summary_val}."

    # 4. TTS
    tts_payload = {
        "text": spoken,
        "model_id": req.model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    tts_headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    try:
        r = _requests.post(tts_url, json=tts_payload, headers=tts_headers,
                           stream=True, timeout=30)
    except _requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"upstream tts error: {exc}")

    if r.status_code != 200:
        try:
            detail = r.json()
        except ValueError:
            detail = {"upstream_status": r.status_code}
        raise HTTPException(status_code=502, detail=detail)

    return Response(content=r.content, media_type="audio/mpeg")


# ── Offline queue endpoints ─────────────────────────────────────────────


class QueueRequest(BaseModel):
    domain: str
    spec: Dict[str, Any]
    reason: str = "manually_queued"


@app.post("/queue", include_in_schema=True)
def queue_submit(request: Request, req: QueueRequest):
    """Manually enqueue a verify request for offline/retry processing.

    Use this when the caller knows the verifier is temporarily unavailable
    (e.g. on a LoRa node without engine access). The background retry
    thread will process the entry when the verifier becomes available.
    The entry is durable — it survives server restarts.
    """
    _rate_check(request, "queue")
    _safe_domain(req.domain)
    queue_id = _queue_enqueue(req.domain, req.spec, reason=req.reason)
    return {
        "queue_id": queue_id,
        "domain": req.domain,
        "status": "pending",
        "message": "Queued for background retry.",
    }


@app.get("/queue", include_in_schema=True)
def queue_status():
    """Return offline queue statistics: pending, failed, completed counts."""
    from api.offline_queue import list_pending
    stats = _queue_stats()
    pending = list_pending(limit=20)
    return {
        "stats": stats,
        "recent_pending": [
            {"id": e["id"], "domain": e["domain"], "queued_at": e["queued_at_iso"],
             "attempts": e["attempts"]}
            for e in pending
        ],
    }


# ── Instance identity + packet signing ─────────────────────────────────
#
# Every packet stored via POST /verify/{domain} is signed with the
# instance's Ed25519 private key. The public key is served freely here
# so any recipient can verify a packet offline, without calling home.
#
# GET  /identity/pubkey                         — instance public key
# GET  /packets/{domain}/{entry_id}/export      — self-contained signed bundle
# POST /packets/{domain}/{entry_id}/verify-sig  — verify a packet signature


@app.get("/identity/pubkey", include_in_schema=True)
def identity_pubkey():
    """Return this instance's Ed25519 public key.

    Any recipient of a signed packet can call this endpoint (or cache the
    key) to verify the packet's signature independently — no network access
    needed at verification time once the key is known.

    The key is URL-safe base64-encoded raw Ed25519 public key bytes (32 bytes).
    """
    try:
        from concordance_engine.instance_identity import get_public_key, get_instance_id
        return {
            "instance_id": get_instance_id(),
            "public_key_b64u": get_public_key(),
            "algorithm": "Ed25519",
            "encoding": "url-safe base64 (no padding)",
            "usage": "verify _sig fields on stored packets",
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"instance key unavailable: {exc}")


@app.get("/identity/user_pubkey", include_in_schema=True)
def identity_user_pubkey():
    """Return this user's personal Ed25519 public key (soul anchor).

    The subject_pubkey field in every sealed WitnessRecord matches this key —
    confirming the receipt is soulbound to this specific person, not just an
    instance or machine.
    """
    try:
        from concordance_engine.user_identity import get_user_pubkey, get_user_id
        return {
            "user_id": get_user_id(),
            "public_key_b64u": get_user_pubkey(),
            "algorithm": "Ed25519",
            "encoding": "url-safe base64 (no padding)",
            "usage": "verify subject_pubkey binding in sealed WitnessRecords",
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"user key unavailable: {exc}")


@app.get("/packets/{domain}/{entry_id}/export", include_in_schema=True)
def packets_export(domain: str, entry_id: str):
    """Export a self-contained signed packet bundle.

    The bundle includes the full entry plus the instance public key so
    the recipient can verify the signature without any network call.
    Carry on a USB drive, sync over LoRa, or share peer-to-peer — the
    signature proves provenance regardless of transport.
    """
    _safe_domain(domain)
    _safe_id(entry_id, "entry_id")
    from api.packet_store import get_packet_store
    entry = get_packet_store().get(domain, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"no entry '{entry_id}' in domain '{domain}'",
        )
    try:
        from concordance_engine.instance_identity import get_public_key, get_instance_id
        pubkey = get_public_key()
        instance_id = get_instance_id()
    except Exception:
        pubkey = entry.get("_instance_pubkey", "")
        instance_id = entry.get("_instance_id", "")
    return {
        "bundle_version": 1,
        "instance_id": instance_id,
        "instance_pubkey": pubkey,
        "entry": entry,
        "verify_instructions": (
            "To verify offline: compute canonical JSON of `entry` "
            "excluding _sig/_instance_pubkey/_instance_id fields, "
            "then verify `entry._sig` against `instance_pubkey` "
            "using Ed25519."
        ),
    }


@app.post("/packets/{domain}/{entry_id}/verify-sig", include_in_schema=True)
def packets_verify_sig(domain: str, entry_id: str):
    """Verify the Ed25519 signature on a stored packet entry.

    Returns ok=true if the packet has not been tampered with since it
    was written by this instance. ok=false means the entry was altered
    or the key has changed.
    """
    _safe_domain(domain)
    _safe_id(entry_id, "entry_id")
    from api.packet_store import get_packet_store
    store = get_packet_store()
    entry = store.get(domain, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"no entry '{entry_id}' in domain '{domain}'",
        )
    ok, detail = store.verify_signature(entry)
    return {
        "entry_id": entry_id,
        "domain": domain,
        "ok": ok,
        "detail": detail,
        "instance_pubkey": entry.get("_instance_pubkey"),
        "instance_id": entry.get("_instance_id"),
    }


# ── Peer registry + cross-instance sync ────────────────────────────────
#
# Peers register themselves at POST /peers/register.
# Packets flow peer-to-peer via POST /packets/import.
# On every local confirm, the instance broadcasts to all known peers.
#
# Trust accumulates without authority: N independent instances reaching
# the same summary on the same spec = trust_count N.


class PeerRegisterRequest(BaseModel):
    url: str
    pubkey: str
    instance_id: str


@app.post("/peers/register", include_in_schema=True)
def peers_register(req: PeerRegisterRequest, _: None = Depends(_check_api_key)):
    """Register a known peer instance by URL, Ed25519 public key, and instance_id.

    Once registered, this instance will broadcast verified packets to the peer
    and accept imports from it. The registry is append-on-register, durable
    across restarts, and never auto-removes entries.
    """
    if not _is_safe_peer_url(req.url):
        raise HTTPException(status_code=422, detail="Peer URL must use http/https and must not target loopback or private IPs.")
    peer = _peer_register(url=req.url, pubkey=req.pubkey, instance_id=req.instance_id)
    return {"status": "registered", "peer": peer}


@app.get("/peers", include_in_schema=True)
def peers_list():
    """List all registered peer instances."""
    peers = _peer_list()
    return {"count": len(peers), "peers": peers}


@app.post("/packets/import", include_in_schema=True)
def packets_import(entry: Dict[str, Any]):
    """Accept a signed packet from a peer instance.

    The packet must carry _sig, _instance_pubkey, and _instance_id fields
    (added by instance_identity.sign_dict). The signature is verified before
    the packet is stored. Unsigned packets are rejected with 422.

    On successful import the packet is recorded in this node's trust index,
    incrementing the trust_count for the corresponding spec_hash. This is
    how N independent confirmations accumulate into a trust credential.
    """
    # Validate signature
    src_pubkey = entry.get("_instance_pubkey", "")
    src_instance_id = entry.get("_instance_id", "")
    sig = entry.get("_sig", "")
    if not sig or not src_pubkey:
        raise HTTPException(
            status_code=422,
            detail="Packet must carry _sig and _instance_pubkey (sign before exporting).",
        )

    try:
        from concordance_engine.instance_identity import verify_dict
        ok, detail = verify_dict(entry, public_key_b64u=src_pubkey)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"signature verification unavailable: {exc}")

    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Signature invalid: {detail}",
        )

    # Store locally
    domain = entry.get("domain", "")
    spec = entry.get("spec", {})
    results = entry.get("results", {})
    summary = entry.get("summary", "UNKNOWN")

    if not domain:
        raise HTTPException(status_code=422, detail="Packet missing 'domain' field.")

    from api.packet_store import get_packet_store
    local_entry = get_packet_store().append(domain, spec, results)

    # Record peer confirmation in trust index
    trust_record = _trust_record(domain, spec, src_instance_id, summary=summary)

    # Also record our own instance_id if we got the same result
    try:
        from concordance_engine.instance_identity import get_instance_id
        own_id = get_instance_id()
        if own_id and own_id != src_instance_id:
            trust_record = _trust_record(domain, spec, own_id, summary=summary)
    except Exception:
        pass

    return {
        "imported": True,
        "domain": domain,
        "entry_id": local_entry["id"],
        "summary": summary,
        "trust_count": trust_record.get("count", 1),
        "confirmed_instances": trust_record.get("instance_ids", []),
    }


@app.get("/trust", include_in_schema=True)
def trust_index_stats():
    """Return trust index statistics across all domains.

    Shows how many spec_hashes have been confirmed by multiple independent
    instances — the measure of decentralized trust accumulating in the network.
    """
    return {
        "stats": _trust_stats(),
        "note": "multi_confirmed = hashes seen from >1 independent instance",
    }


# -- Content-addressable store (CAS) ------------------------------------

from concordance_engine.cas import (
    store as _cas_store, fetch as _cas_fetch,
    exists as _cas_exists, list_hashes as _cas_list,
    verify as _cas_verify, stats as _cas_stats,
)


@app.get("/cas/{content_hash}", include_in_schema=True)
def cas_get(content_hash: str):
    """Fetch a sealed record by its SHA-256 content hash.

    Returns the record as JSON, or 404 if not found. The content_hash
    embedded in the response can be recomputed to verify integrity.
    """
    _safe_hash(content_hash)
    record = _cas_fetch(content_hash)
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"not found: {content_hash}")
    return record


@app.post("/cas", include_in_schema=True)
def cas_put(body: Dict[str, Any], _: None = Depends(_check_api_key)):
    """Store a sealed record in the CAS. Returns its content_hash.

    Idempotent — storing the same record twice returns the same hash.
    Requires API key.
    """
    h = _cas_store(body)
    return {"content_hash": h, "stored": True}


@app.get("/cas", include_in_schema=True)
def cas_stats_endpoint():
    """Return CAS statistics: record count, total bytes, base directory."""
    return _cas_stats()


@app.get("/cas/{content_hash}/verify", include_in_schema=True)
def cas_verify_endpoint(content_hash: str):
    """Re-hash the stored record and confirm it matches the requested hash."""
    _safe_hash(content_hash)
    ok, detail = _cas_verify(content_hash)
    return {"ok": ok, "detail": detail, "content_hash": content_hash}


# ── Agent interop layer ───────────────────────────────────────────────────────
# Three endpoints that make Concordance legible to any AI agent:
#   GET  /manifest  — OpenAI-compatible tool definitions with axis framing
#   POST /verify    — single dispatch to any domain verifier
#   GET  /benchmark — 171/171 accuracy results
#   GET  /context   — system prompt fragment for agent operators

from api.agent_manifest import (
    build_manifest as _build_manifest,
    dispatch as _manifest_dispatch,
    benchmark_summary as _benchmark_summary,
    context_block as _context_block,
)


class VerifyRequest(BaseModel):
    tool: str
    spec: Dict[str, Any]


@app.get("/manifest", tags=["agents"])
def agent_manifest():
    """OpenAI-compatible tool manifest for any AI agent.

    Returns all 57 Concordance domain verifiers in function-calling format,
    including axis framing and created-order context in each description.
    Any agent that speaks OpenAI tool-use (Grok, GPT, Gemini, Claude) can
    load this manifest and immediately call the verifiers.
    """
    return _build_manifest()


@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions_schema():
    """Focused OpenAPI 3.1 schema for ChatGPT Custom GPT Actions.

    The full FastAPI-generated /openapi.json has 60+ operations — too
    many for a Custom GPT Action's 30-operation cap. This endpoint
    returns a curated subset covering the eight tools an agent
    operator actually needs: NL dispatch, direct verifier call,
    polymathic synthesis, scaffold introspection, manifest read,
    benchmark stats, almanac lookup, and ledger verify.

    Paste the URL https://narrowhighway.com/openapi-actions.json into
    the Custom GPT editor's Actions section and ChatGPT will load
    the schema directly."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Concordance Engine",
            "version": "1.0.0",
            "description": (
                "Deterministic verification engine. Submit natural-language "
                "claims or structured packets through 48 domain verifiers "
                "and 4 gates (RED, FLOOR, BROTHERS, GOD). Every result is "
                "sealed to an HMAC-chained, tamper-evident ledger. The engine "
                "never returns a final answer — it returns the elimination "
                "trail and the closest verified precedent."
            ),
        },
        "servers": [{"url": "https://narrowhighway.com"}],
        "paths": {
            "/agent": {
                "get": {
                    "operationId": "verifyClaimByText",
                    "summary": "Natural-language verification dispatch.",
                    "description": (
                        "Pass any plain-English claim or situation. Engine "
                        "classifies the domain, extracts the spec, runs the "
                        "verifier, and returns the result. Use this when you "
                        "don't know which specific verifier to call."
                    ),
                    "parameters": [
                        {
                            "name": "text",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "The claim or situation in plain English.",
                        }
                    ],
                    "responses": {"200": {"description": "Verifier result or no-match fallback with available verifiers."}},
                }
            },
            "/verify": {
                "post": {
                    "operationId": "callVerifier",
                    "summary": "Call a specific domain verifier directly.",
                    "description": (
                        "Use when you know exactly which verifier you want. "
                        "Read /manifest first for the full tool list and "
                        "spec shapes."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["tool", "spec"],
                                    "properties": {
                                        "tool": {
                                            "type": "string",
                                            "description": "Verifier name like 'verify_physics' or 'verify_statistics_pvalue'.",
                                        },
                                        "spec": {
                                            "type": "object",
                                            "description": "Domain-specific input. See /manifest for shapes.",
                                            "additionalProperties": True,
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Verifier result."}},
                }
            },
            "/polymathic": {
                "post": {
                    "operationId": "runPolymathic",
                    "summary": "Multi-domain synthesis on one situation.",
                    "description": (
                        "Engine fans the situation across every applicable "
                        "verifier, returns a composite verdict with axis "
                        "overlaps showing which scaffold dimensions agreed."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["situation"],
                                    "properties": {
                                        "situation": {
                                            "type": "string",
                                            "description": "Plain-English description of the situation.",
                                        },
                                        "max_domains": {
                                            "type": "integer",
                                            "default": 8,
                                        },
                                        "store": {
                                            "type": "boolean",
                                            "default": False,
                                            "description": "Save to CAS for later sealing.",
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "PolymathicRecord with composite_verdict, domain_results, axis_overlaps."}},
                }
            },
            "/manifest": {
                "get": {
                    "operationId": "listAllTools",
                    "summary": "Full tool catalog for the engine.",
                    "description": "Returns every verifier's name, description, and spec shape in OpenAI function-calling format.",
                    "responses": {"200": {"description": "Tool list."}},
                }
            },
            "/grid/scaffold": {
                "get": {
                    "operationId": "readScaffold",
                    "summary": "The 7-axis dimensional scaffold.",
                    "description": "Every domain mapped to which of the 7 scaffold dimensions it sits on. Use to understand structural neighbors of a domain.",
                    "responses": {"200": {"description": "Scaffold structure."}},
                }
            },
            "/grid/coherence": {
                "get": {
                    "operationId": "auditScaffold",
                    "summary": "Engine self-audit. Structural anomalies as data.",
                    "description": "Empty triples, alias clusters, umbrella conflicts, axis-weight imbalance. The engine surfacing what it knows about its own gaps.",
                    "responses": {"200": {"description": "Audit report."}},
                }
            },
            "/almanac": {
                "get": {
                    "operationId": "readAlmanac",
                    "summary": "Curated wisdom + engine-discovered patterns.",
                    "description": "The book of what the engine has worked through. Sayings, protocols, and patterns with their dry notes.",
                    "parameters": [
                        {"name": "kind", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by saying|protocol|pattern."},
                    ],
                    "responses": {"200": {"description": "Almanac entries."}},
                }
            },
            "/benchmark": {
                "get": {
                    "operationId": "readBenchmark",
                    "summary": "Latest benchmark results.",
                    "description": "Per-domain accuracy and average response time across the 171-item benchmark.",
                    "responses": {"200": {"description": "Benchmark summary."}},
                }
            },
            "/ledger/verify": {
                "get": {
                    "operationId": "verifyLedgerChain",
                    "summary": "HMAC chain integrity check.",
                    "description": "Recomputes the ledger's HMAC chain from genesis. Returns ok=true if no tampering detected.",
                    "responses": {"200": {"description": "Chain verification result."}},
                }
            },
        },
    }


@app.post("/verify", tags=["agents"])
def agent_verify(request: Request, body: VerifyRequest):
    """Call any Concordance domain verifier by name.

    Pass the tool name (e.g. 'verify_physics') and a flat spec dict with the
    fields the verifier expects. Returns the verifier result with status
    CONFIRMED, DISCORDANT, or NOT_APPLICABLE.

    Example:
      {"tool": "verify_physics",
       "spec": {"mass_kg": 2.0, "velocity_ms": 5.0, "claimed_ke_j": 25.0}}
    """
    _rate_check(request, "verify")
    # Tool name is dispatched against an allow-list inside _manifest_dispatch,
    # but we still validate the shape so a probe with `../etc/passwd` is
    # rejected at the edge with a clear 400 rather than a generic 404.
    if not body.tool or not re.match(r'^[a-z][a-z0-9_]{0,80}$', body.tool):
        raise HTTPException(status_code=400, detail="invalid tool name")
    return _manifest_dispatch(body.tool, body.spec)


@app.get("/benchmark", tags=["agents"])
def agent_benchmark():
    """Latest benchmark results: 171/171 items across 57 domains.

    Returns per-domain accuracy and average response time. Agents and operators
    can call this to verify the engine's accuracy before relying on it.
    """
    return _benchmark_summary()


@app.get("/context", tags=["agents"], include_in_schema=False)
def agent_context():
    """System prompt fragment for agent operators.

    Returns a ~200-word block of text that any operator can include in a
    system prompt to orient an AI agent to what Concordance is and how to
    interpret CONFIRMED / DISCORDANT results in terms of the created order.
    """
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_context_block(), media_type="text/plain")


# ── Grid scaffold + background cross-domain connector ───────────────────
#
# The grid is the structural skeleton that makes the pattern visible
# (Romans 1:20 — the design of creation made legible across domains).
# These three endpoints serve the scaffold for both humans and agents:
#
#   GET /grid/scaffold              full domain→dimension static map
#   GET /grid/domain/{domain}       one domain's position + adjacency
#   GET /grid/connections           live cross-domain connection events
#   GET /grid/connections/stream    SSE stream of new connections
#
# The background connector (_grid_connector_thread) is the "keeping"
# layer: it runs whether or not anyone is submitting verifications,
# watching the journal as seeds arrive and firing connection events
# when two domains are discovered to share the same scaffold axes.
# ─────────────────────────────────────────────────────────────────────

import threading as _threading

_GRID_CONNECTIONS_FILE = (
    Path(__file__).parent.parent / "data" / "grid_connections.jsonl"
)
_GRID_CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Module-level connection state — updated by background thread.
_connector_domain_seeds: Dict[str, List[str]] = {}   # domain → recent seed texts
_connector_fired_pairs: set = set()                  # frozenset({da, db}) pairs logged
_connector_seen_ids: set = set()                     # journal entry IDs already scanned
_connector_lock = _threading.Lock()

# Searcher worker state — third species, harvester.
# Walks a curated list of canonical scripture anchors (theologically
# central refs spanning creation, christology, gospel, wisdom, witness,
# eschatology). Each tick: resolve one ref via the local WEB Bible
# module, post the verse text to /capture as a real harvested packet.
# Local-only — no external HTTP, no LLM. Genuinely public domain.
#
# After completing one full cycle of the anchor list, sleeps 6 hours
# then cycles again. The list is small (~50 entries) so a full pass
# takes ~75 min; aggregate harvest rate is gentle, on purpose.
_SCRIPTURE_ANCHOR_REFS: List[str] = [
    # Creation / cosmology — Romans 1:20 territory
    "Genesis 1:1", "Genesis 1:27", "Genesis 2:7", "Psalm 19:1", "Psalm 8:3",
    "Psalm 139:14", "Romans 1:20", "Colossians 1:16", "Hebrews 11:3",
    "John 1:1", "John 1:3", "Acts 17:28",
    # Christology
    "John 3:16", "John 14:6", "Philippians 2:6", "Philippians 2:9",
    "Colossians 2:9", "Hebrews 1:3", "Matthew 16:16", "John 10:30",
    "Revelation 22:13",
    # Gospel core (1 Cor 15:3-4 anchored)
    "1 Corinthians 15:3", "1 Corinthians 15:4", "Ephesians 2:8",
    "Ephesians 2:9", "Romans 3:23", "Romans 5:8", "Romans 6:23",
    "Romans 10:9", "Romans 10:10",
    # Wisdom + decision-making (the engine's epistemic frame)
    "Proverbs 1:7", "Proverbs 3:5", "Proverbs 3:6", "Proverbs 9:10",
    "Proverbs 24:27", "James 1:5", "James 1:17",
    "Ecclesiastes 3:1", "Philippians 4:6", "Philippians 4:7",
    # Witness / truth
    "Deuteronomy 19:15", "Matthew 18:16", "John 8:32", "John 14:17",
    "John 16:13", "1 Timothy 3:1",
    # Posture / identity
    "Matthew 5:3", "Matthew 5:8", "Matthew 5:14", "Matthew 6:33",
    "Matthew 10:16", "1 Peter 3:15", "Romans 12:2",
    # Eschatology / completion
    "Revelation 21:1", "Revelation 21:4", "1 Thessalonians 4:16",
]

_searcher_state: Dict[str, Any] = {
    "cursor": 0,                  # index into _SCRIPTURE_ANCHOR_REFS
    "cycles_completed": 0,        # full passes through the anchor list
    "in_rest": False,             # sleeping between cycles
    "rest_until": 0.0,
}
_searcher_stats: Dict[str, Any] = {
    "name": "searcher",
    "species": "Searcher",
    "role": "harvest one canonical anchor per tick (WEB Bible)",
    "current_source": "WEB Bible · curated anchors",
    "anchor_list_size": len(_SCRIPTURE_ANCHOR_REFS),
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "harvests_total": 0,
    "duplicates_skipped": 0,
    "last_harvest": None,
    "tick_period_seconds": 90,
    "rest_period_seconds": 6 * 3600,
}


def _searcher_tick() -> None:
    """One harvest. Resolves the next anchor and posts to journal."""
    import time as _time
    state = _searcher_state

    # Honor rest period between cycles
    if state["in_rest"]:
        if _time.time() < state["rest_until"]:
            return
        state["in_rest"] = False
        state["cursor"] = 0

    refs = _SCRIPTURE_ANCHOR_REFS
    if not refs:
        return

    idx = state["cursor"]
    ref = refs[idx]

    # Resolve via the engine's existing scripture module — local WEB
    try:
        from concordance_engine.verifiers import scripture as _scripture
        result = _scripture.resolve_ref(ref)
    except Exception as exc:
        _searcher_stats["last_error"] = f"resolve {ref}: {exc}"
        _advance_searcher_cursor()
        return

    if result.get("status") != "ok":
        _searcher_stats["last_error"] = f"{ref} → {result.get('detail','no text')}"
        _advance_searcher_cursor()
        return

    web_text = (result.get("web_text") or "").strip()
    if not web_text:
        _advance_searcher_cursor()
        return

    text = f"{ref} (WEB) — {web_text}"
    tags = ["scripture_anchors", "harvest", "web_bible", "searcher"]

    try:
        from concordance_engine import journal as _journal
        _journal.capture(text, tags=tags, look_up_precedent=False)
        _searcher_stats["harvests_total"] += 1
        _searcher_stats["last_harvest"] = {
            "ts": _time.time(),
            "ref": ref,
            "domain": "scripture_anchors",
            "text_preview": web_text[:90],
        }
    except ValueError as exc:
        if "duplicate" in str(exc).lower():
            _searcher_stats["duplicates_skipped"] += 1
        else:
            _searcher_stats["last_error"] = str(exc)[:200]
            _searcher_stats["error_count"] += 1
    except Exception as exc:
        _searcher_stats["last_error"] = str(exc)[:200]
        _searcher_stats["error_count"] += 1

    _advance_searcher_cursor()


def _advance_searcher_cursor() -> None:
    """Step to next ref. At list end, log a completed cycle and rest."""
    import time as _time
    state = _searcher_state
    state["cursor"] += 1
    if state["cursor"] >= len(_SCRIPTURE_ANCHOR_REFS):
        state["cycles_completed"] += 1
        state["in_rest"] = True
        state["rest_until"] = _time.time() + _searcher_stats["rest_period_seconds"]


def _searcher_worker() -> None:
    """Background loop. Slow on purpose."""
    import time as _time
    if _searcher_stats["started_at"] is None:
        _searcher_stats["started_at"] = _time.time()
    # Brief startup delay so the journal store finishes initializing
    _time.sleep(20)
    while True:
        try:
            _searcher_tick()
            _searcher_stats["tick_count"] += 1
        except Exception as exc:
            _searcher_stats["error_count"] += 1
            _searcher_stats["last_error"] = str(exc)[:200]
            _log.warning(f"searcher error: {exc}")
        _searcher_stats["last_tick_at"] = _time.time()
        _time.sleep(_searcher_stats["tick_period_seconds"])


# ─────────────────────────────────────────────────────────────────────
# Searcher #2 — Library of Congress harvester
#
# LoC is the authoritative bibliographic source — controlled vocabulary,
# MARC records, rights-tagged provenance, public-domain by curation.
# We don't trust Wikipedia (mutable, crowdsourced); we go to the
# source-of-record. Catalog metadata only — title, date, author,
# subjects, rights, LCCN — every harvest carries verifiable provenance.
#
# Reads Trainer's recommendations to target starving domains first.
# 5-minute ticks (12 req/hour, well under LoC's rate limits).
# ─────────────────────────────────────────────────────────────────────

_LOC_DOMAIN_TO_QUERY: Dict[str, str] = {
    # Most domains take their underscore-stripped name as the LoC query.
    # Overrides here are for cases where the LoC subject heading differs
    # meaningfully from the engine's domain identifier.
    "scripture_anchors": "biblical theology",
    "theology_doctrine": "Christian theology doctrine",
    "governance_decision_packet": "governance decision-making",
    "physics_conservation": "physics conservation laws",
    "physics_dimensional": "dimensional analysis",
    "statistics_pvalue": "statistical hypothesis testing",
    "statistics_multiple_comparisons": "multiple comparisons procedure",
    "statistics_confidence_interval": "confidence intervals statistics",
    "history_chronology": "historical chronology",
    "calendar_time": "calendar time measurement",
    "formal_logic": "formal logic",
    "exercise_science": "exercise physiology",
    "music_theory": "music theory",
    "sports_analytics": "sports statistics",
    "document_validation": "document authentication",
    "computer_science": "computer science",
    "operations_research": "operations research",
    "information_theory": "information theory",
    "quantum_computing": "quantum computing",
    "nuclear_physics": "nuclear physics",
    "materials_science": "materials science",
    "number_theory": "number theory",
    "soil_science": "soil science",
    "real_estate": "real property",
    "labor": "labor economics",
}

_LOC_SEARCH_BASE = "https://www.loc.gov/search/"
_LOC_USER_AGENT = (
    "Concordance-Engine-Searcher/1.0 "
    "(+https://narrowhighway.com; harvest of public-domain catalog records)"
)

_loc_state: Dict[str, Any] = {
    "harvested_loc_ids": set(),  # avoid duplicates within a session
    "last_target_domain": None,
    "last_query": None,
    "last_url": None,
}
_loc_stats: Dict[str, Any] = {
    "name": "searcher_loc",
    "species": "Searcher · LoC",
    "role": "harvest one public-domain LoC catalog record per tick",
    "current_source": "Library of Congress catalog (loc.gov/search)",
    "rights_filter": "no_known_restrictions",
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "harvests_total": 0,
    "duplicates_skipped": 0,
    "empty_result_count": 0,
    "last_harvest": None,
    "tick_period_seconds": 300,   # 5 min — polite to LoC
}


def _loc_pick_target_domain() -> str:
    """Read Trainer's swarm config (in-memory if cached) and pick the
    most starving domain. Falls back to a default rotation if Trainer
    has no analysis yet."""
    analysis = (_trainer_state or {}).get("analysis") or {}
    priorities = (
        analysis.get("recommendations", {}).get("searcher_priorities", [])
        or analysis.get("domains_starving", [])
    )
    if priorities:
        # Skip scripture_anchors here — Searcher #1 owns that domain.
        for d in priorities:
            if d != "scripture_anchors":
                return d
    # Fallback: rotate through a curated set of domains LoC has rich
    # holdings on, so we don't sit dead before Trainer first runs.
    fallbacks = [
        "philosophy", "history_chronology", "rhetoric", "music_theory",
        "geography", "astronomy", "biology", "law", "agriculture",
    ]
    cursor = (_loc_stats.get("tick_count") or 0) % len(fallbacks)
    return fallbacks[cursor]


def _loc_fetch_results(query: str) -> Dict[str, Any]:
    """One LoC catalog search. Returns parsed JSON or raises."""
    import urllib.request, urllib.parse
    params = urllib.parse.urlencode({
        "q": query,
        "fo": "json",
        "c": 15,
        "fa": "rights:no_known_restrictions",
    })
    url = f"{_LOC_SEARCH_BASE}?{params}"
    _loc_state["last_url"] = url
    req = urllib.request.Request(url, headers={"User-Agent": _LOC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _loc_searcher_tick() -> None:
    """One LoC harvest. Reads Trainer for target, fetches a public-domain
    catalog record, posts the metadata to the journal."""
    import time as _time

    target = _loc_pick_target_domain()
    _loc_state["last_target_domain"] = target
    query = _LOC_DOMAIN_TO_QUERY.get(target, target.replace("_", " "))
    _loc_state["last_query"] = query

    try:
        data = _loc_fetch_results(query)
    except Exception as exc:
        _loc_stats["error_count"] += 1
        _loc_stats["last_error"] = f"fetch: {str(exc)[:160]}"
        return

    results = data.get("results") or []
    if not results:
        _loc_stats["empty_result_count"] += 1
        _loc_stats["last_error"] = f"no items for '{query}' (target={target})"
        return

    # Find the first item we haven't seen this session
    chosen = None
    for item in results:
        item_id = item.get("id") or item.get("url") or ""
        if item_id and item_id not in _loc_state["harvested_loc_ids"]:
            chosen = (item, item_id)
            break
    if chosen is None:
        _loc_stats["duplicates_skipped"] += 1
        return

    item, item_id = chosen
    _loc_state["harvested_loc_ids"].add(item_id)

    # Build a clean human-readable packet from LoC metadata
    title = (item.get("title") or "").strip() or "(untitled)"
    date = (item.get("date") or "").strip()
    description = item.get("description") or ""
    if isinstance(description, list):
        description = description[0] if description else ""
    description = str(description).strip()
    subjects_raw = item.get("subject") or []
    if isinstance(subjects_raw, str):
        subjects_raw = [subjects_raw]
    subjects = [str(s).strip() for s in subjects_raw if s][:6]
    contributors_raw = item.get("contributor") or []
    if isinstance(contributors_raw, str):
        contributors_raw = [contributors_raw]
    contributors = [str(c).strip() for c in contributors_raw if c][:3]

    parts: List[str] = []
    head = f"LoC: {title}"
    if date:
        head += f" ({date})"
    parts.append(head)
    if contributors:
        parts.append(f"By: {'; '.join(contributors)}")
    if description:
        parts.append(description[:280])
    if subjects:
        parts.append(f"Subjects: {' · '.join(subjects)}")
    parts.append(f"Source: {item_id}")
    parts.append("Rights: No known restrictions on publication.")
    text = "\n".join(parts)

    # Post through the same /capture door
    try:
        from concordance_engine import journal as _journal
        _journal.capture(
            text,
            tags=[target, "harvest", "library_of_congress", "loc", "searcher"],
            look_up_precedent=False,
        )
        _loc_stats["harvests_total"] += 1
        _loc_stats["last_harvest"] = {
            "ts": _time.time(),
            "domain": target,
            "query": query,
            "title": title[:120],
            "date": date,
            "subjects": subjects,
            "loc_id": item_id,
        }
    except ValueError as exc:
        if "duplicate" in str(exc).lower():
            _loc_stats["duplicates_skipped"] += 1
        else:
            _loc_stats["error_count"] += 1
            _loc_stats["last_error"] = str(exc)[:200]
    except Exception as exc:
        _loc_stats["error_count"] += 1
        _loc_stats["last_error"] = str(exc)[:200]


def _loc_searcher_worker() -> None:
    """Background loop. 5-min ticks. Polite to LoC."""
    import time as _time
    if _loc_stats["started_at"] is None:
        _loc_stats["started_at"] = _time.time()
    # Long startup grace so journal + Trainer get going first
    _time.sleep(45)
    while True:
        try:
            _loc_searcher_tick()
            _loc_stats["tick_count"] += 1
        except Exception as exc:
            _loc_stats["error_count"] += 1
            _loc_stats["last_error"] = str(exc)[:200]
            _log.warning(f"loc searcher error: {exc}")
        _loc_stats["last_tick_at"] = _time.time()
        _time.sleep(_loc_stats["tick_period_seconds"])


# ─────────────────────────────────────────────────────────────────────
# Searcher #3 — Tasked Dispatcher
#
# Searcher #1 walks a curated list. Searcher #2 picks from Trainer's
# starvation list. #3 does NEITHER autonomously — it sleeps until a
# task is dispatched. When something specific needs harvesting (a
# verifier mismatch wants fresh refs; Trainer flags a critical gap;
# a human researcher asks for "Aristotle on rhetoric") the requester
# POSTs to /swarm/searcher/dispatch and the tasked dispatcher handles it.
#
# In-memory queue. 15s tick — responsive without polling hard.
# Persists nothing across restarts; this is a working memory, not
# a record. The journal is the record.
# ─────────────────────────────────────────────────────────────────────

import collections as _collections
_dispatch_queue: "_collections.deque" = _collections.deque()
_dispatch_history: "_collections.deque" = _collections.deque(maxlen=50)
_dispatch_lock = _threading.Lock()

_dispatch_stats: Dict[str, Any] = {
    "name": "searcher_dispatch",
    "species": "Searcher · Tasked",
    "role": "harvest one specific target on demand (idle by default)",
    "current_source": "any (loc | scripture)",
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "tasks_completed": 0,
    "tasks_failed": 0,
    "tasks_queued_total": 0,
    "tasks_duplicate": 0,
    "tasks_empty": 0,
    "current_task": None,
    "idle_ticks": 0,
    "last_error": None,
    "tick_period_seconds": 15,
}


def _execute_dispatch(task: Dict[str, Any]) -> Dict[str, Any]:
    """Run one dispatched task. Returns {status, detail, harvest?}.
    Reuses LoC fetch / packet shape so dispatched harvests sit
    alongside autonomous LoC harvests in the journal."""
    import time as _time
    domain = (task.get("domain") or "").strip()
    if not domain:
        return {"status": "error", "detail": "task has no domain"}
    src = (task.get("source") or "loc").lower()
    query = (task.get("query") or "").strip() or _LOC_DOMAIN_TO_QUERY.get(
        domain, domain.replace("_", " ")
    )

    if src != "loc":
        return {"status": "error",
                "detail": f"source '{src}' not yet supported (use 'loc')"}

    # Fetch from LoC
    try:
        data = _loc_fetch_results(query)
    except Exception as exc:
        return {"status": "error", "detail": f"fetch: {str(exc)[:160]}"}

    results = data.get("results") or []
    if not results:
        return {"status": "empty",
                "detail": f"no items for '{query}' (target={domain})"}

    chosen = None
    for item in results:
        item_id = item.get("id") or item.get("url") or ""
        if item_id and item_id not in _loc_state["harvested_loc_ids"]:
            chosen = (item, item_id)
            break
    if chosen is None:
        return {"status": "duplicate",
                "detail": "all top results already harvested this session"}

    item, item_id = chosen
    _loc_state["harvested_loc_ids"].add(item_id)

    # Build packet (same shape as autonomous LoC searcher)
    title = (item.get("title") or "").strip() or "(untitled)"
    date = (item.get("date") or "").strip()
    description = item.get("description") or ""
    if isinstance(description, list):
        description = description[0] if description else ""
    description = str(description).strip()
    subjects_raw = item.get("subject") or []
    if isinstance(subjects_raw, str):
        subjects_raw = [subjects_raw]
    subjects = [str(s).strip() for s in subjects_raw if s][:6]
    contributors_raw = item.get("contributor") or []
    if isinstance(contributors_raw, str):
        contributors_raw = [contributors_raw]
    contributors = [str(c).strip() for c in contributors_raw if c][:3]

    parts: List[str] = []
    head = f"LoC: {title}"
    if date:
        head += f" ({date})"
    parts.append(head)
    if contributors:
        parts.append(f"By: {'; '.join(contributors)}")
    if description:
        parts.append(description[:280])
    if subjects:
        parts.append(f"Subjects: {' · '.join(subjects)}")
    parts.append(f"Source: {item_id}")
    parts.append("Rights: No known restrictions on publication.")
    requested_by = task.get("requested_by")
    if requested_by:
        parts.append(f"Dispatched by: {requested_by}")
    text = "\n".join(parts)

    try:
        from concordance_engine import journal as _journal
        _journal.capture(
            text,
            tags=[domain, "harvest", "library_of_congress", "loc",
                  "searcher", "dispatched"],
            look_up_precedent=False,
        )
        return {
            "status": "ok",
            "harvest": {
                "ts": _time.time(),
                "domain": domain,
                "query": query,
                "title": title[:120],
                "date": date,
                "subjects": subjects,
                "loc_id": item_id,
                "requested_by": requested_by,
                "task_id": task.get("task_id"),
            },
        }
    except ValueError as exc:
        if "duplicate" in str(exc).lower():
            return {"status": "duplicate", "detail": str(exc)[:160]}
        return {"status": "error", "detail": str(exc)[:200]}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:200]}


def _dispatch_worker() -> None:
    """Background loop. Drains queue when there's work, sleeps quietly
    when there isn't. 15s ticks — responsive without polling hard."""
    import time as _time
    if _dispatch_stats["started_at"] is None:
        _dispatch_stats["started_at"] = _time.time()
    _time.sleep(25)  # startup grace
    while True:
        task = None
        try:
            with _dispatch_lock:
                if _dispatch_queue:
                    task = _dispatch_queue.popleft()
                    _dispatch_stats["current_task"] = {
                        "task_id": task.get("task_id"),
                        "domain": task.get("domain"),
                        "source": task.get("source"),
                    }
            if task is not None:
                result = _execute_dispatch(task)
                _dispatch_history.appendleft({
                    "task": task,
                    "result": result,
                    "completed_at": _time.time(),
                })
                status = result.get("status")
                if status == "ok":
                    _dispatch_stats["tasks_completed"] += 1
                elif status == "duplicate":
                    _dispatch_stats["tasks_duplicate"] += 1
                elif status == "empty":
                    _dispatch_stats["tasks_empty"] += 1
                else:
                    _dispatch_stats["tasks_failed"] += 1
                    _dispatch_stats["last_error"] = result.get("detail", "")
                _dispatch_stats["current_task"] = None
            else:
                _dispatch_stats["idle_ticks"] += 1
            _dispatch_stats["tick_count"] += 1
        except Exception as exc:
            _dispatch_stats["last_error"] = str(exc)[:200]
            _dispatch_stats["current_task"] = None
        _dispatch_stats["last_tick_at"] = _time.time()
        _time.sleep(_dispatch_stats["tick_period_seconds"])


# ─────────────────────────────────────────────────────────────────────
# Janitor worker — fourth species, the steward
#
# Walks the journal and scores every packet on TWO axes:
#   1. Completeness — is text present? tags present? size sane?
#   2. Appropriateness — does it carry a recognized domain? does its
#      provenance match a known trust tier?
#
# Janitor never deletes. The journal is append-only; the Janitor's job
# is to illuminate. Findings flow to /swarm/janitor and become input
# for the Trainer (which can then dispatch tasked jobs to
# replace low-trust entries with proper LoC/scripture harvests).
#
# Trust tiers (informal):
#   1 — locked translation (WEB Bible scripture_anchors)
#   2 — institutional authority (Library of Congress)
#   3 — other curated harvest (future Searchers)
#   4 — organic submission (human or agent capture)
#   5 — LLM-synthesized (the old seed_generator output) ← flagged
# ─────────────────────────────────────────────────────────────────────

# Canonical 63 domains the engine knows about. Shared by Janitor
# (used to detect UNRECOGNIZED_DOMAIN) and Trainer (used to find
# which are starving). Defined once here so the load order works.
_ALL_DOMAINS = [
    "acoustics","agriculture","architecture","astronomy","biology","calendar_time",
    "chemistry","combinatorics","computer_science","construction","cryptography",
    "cybersecurity","document_validation","ecology","economics","electrical","energy",
    "exercise_science","finance","formal_logic","genetics","geography","geology",
    "geometry","governance_decision_packet","history_chronology","hydrology",
    "information_theory","labor","law","linguistics","manufacturing","materials_science",
    "mathematics","medicine","meteorology","music_theory","networking","nuclear_physics",
    "number_theory","nutrition","oceanography","operations_research","optics","phase",
    "philosophy","photography","physics","physics_conservation","physics_dimensional",
    "quantum_computing","real_estate","rhetoric","scripture_anchors","soil_science",
    "sports_analytics","statistics","statistics_confidence_interval",
    "statistics_multiple_comparisons","statistics_pvalue","theology_doctrine",
    "thermodynamics","witness",
]
_JANITOR_DOMAINS = set(_ALL_DOMAINS)

_janitor_seen: set = set()                                 # entry IDs already scored
_janitor_findings: "_collections.deque" = _collections.deque(maxlen=200)
_janitor_state: Dict[str, Any] = {
    "full_scan_complete": False,
    "first_tick_done": False,
}
_janitor_stats: Dict[str, Any] = {
    "name": "janitor",
    "species": "Janitor",
    "role": "verify packet completeness and appropriateness",
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "entries_reviewed": 0,
    "entries_with_findings": 0,
    "by_category": {},      # finding tag → count
    "by_trust_tier": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    "by_domain": {},        # domain → total count
    "by_domain_tiers": {},  # domain → {"1": n, ..., "5": n}  (for Trainer)
    "last_finding": None,
    "batch_size": 500,
    "tick_period_seconds": 90,
    "fastscan_period_seconds": 8,   # tight loop while warming the histogram
}


def _janitor_classify(entry) -> Dict[str, Any]:
    """Score one entry. Returns {entry_id, domain, trust_tier,
    findings, text_length, ok}.  Findings are short ALL_CAPS tags."""
    text_raw = getattr(entry, "text", "") or ""
    text = text_raw.strip()
    tags_set = set(getattr(entry, "user_tags", None) or [])
    metadata = getattr(entry, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    source_field = str(metadata.get("source", "") or "").lower()

    findings: List[str] = []

    # Completeness
    if not text:
        findings.append("MISSING_TEXT")
    else:
        if len(text) < 12:
            findings.append("TOO_SHORT")
        elif len(text) > 8000:
            findings.append("TOO_LONG")
    if not tags_set and not metadata:
        findings.append("NO_PROVENANCE")

    # Appropriateness — domain detection
    domain_match = tags_set & _JANITOR_DOMAINS
    if domain_match:
        domain = sorted(domain_match)[0]   # deterministic pick
    else:
        cand = metadata.get("domain")
        domain = cand if cand in _JANITOR_DOMAINS else None
    if not domain:
        findings.append("UNRECOGNIZED_DOMAIN")

    # Trust tier — inspect provenance markers
    is_web_bible = "web_bible" in tags_set
    is_loc = "library_of_congress" in tags_set or "loc" in tags_set
    is_searcher_curated = "searcher" in tags_set and "harvest" in tags_set
    is_seed = (
        "seed" in tags_set
        or "generated" in tags_set
        or source_field.startswith("seed_generator")
    )

    if is_web_bible:
        trust_tier = 1
    elif is_loc:
        trust_tier = 2
    elif is_searcher_curated:
        trust_tier = 3
    elif is_seed:
        trust_tier = 5
        findings.append("LLM_SYNTHESIZED")
    else:
        trust_tier = 4

    return {
        "entry_id": getattr(entry, "id", None),
        "domain": domain or "unknown",
        "trust_tier": trust_tier,
        "findings": findings,
        "text_length": len(text),
        "ok": not findings,
    }


def _janitor_tick() -> None:
    """One scoring pass. First-pass reads the full journal; steady-state
    reads only the most recent batch and skips already-scored IDs."""
    import time as _time
    try:
        from concordance_engine.journal import JournalStore
        store = JournalStore()
    except Exception as exc:
        _janitor_stats["last_error"] = f"journal: {exc}"
        return

    # During full scan: read entire journal, process a bounded batch of
    # new entries, repeat. Mark full_scan_complete only when a tick
    # processes fewer than batch_max new entries (i.e. nothing left
    # we haven't seen). Steady state: small bounded read for arrivals.
    if not _janitor_state["full_scan_complete"]:
        try:
            entries = store.list_all(limit=50000)
        except Exception as exc:
            _janitor_stats["last_error"] = f"full-scan: {exc}"
            return
    else:
        try:
            entries = store.list_all(limit=200)
        except Exception as exc:
            _janitor_stats["last_error"] = f"poll: {exc}"
            return

    processed = 0
    batch_max = _janitor_stats["batch_size"]
    for entry in entries:
        eid = getattr(entry, "id", None)
        if eid is None or eid in _janitor_seen:
            continue
        result = _janitor_classify(entry)
        _janitor_seen.add(eid)
        _janitor_stats["entries_reviewed"] += 1

        # Tier counter
        tier_key = str(result.get("trust_tier", 4))
        _janitor_stats["by_trust_tier"][tier_key] = (
            _janitor_stats["by_trust_tier"].get(tier_key, 0) + 1
        )

        # Domain counter (total + per-tier — the per-tier map is what
        # Trainer reads to decide where to auto-dispatch tasked workers)
        dom = result.get("domain") or "unknown"
        _janitor_stats["by_domain"][dom] = _janitor_stats["by_domain"].get(dom, 0) + 1
        dt = _janitor_stats["by_domain_tiers"].setdefault(dom, {})
        dt[tier_key] = dt.get(tier_key, 0) + 1

        # Findings
        if result.get("findings"):
            _janitor_stats["entries_with_findings"] += 1
            for f in result["findings"]:
                _janitor_stats["by_category"][f] = (
                    _janitor_stats["by_category"].get(f, 0) + 1
                )
            finding_record = {
                "entry_id": eid,
                "domain": dom,
                "trust_tier": result["trust_tier"],
                "findings": result["findings"][:4],
                "text_length": result.get("text_length", 0),
                "ts": _time.time(),
            }
            _janitor_findings.appendleft(finding_record)
            _janitor_stats["last_finding"] = finding_record

        processed += 1
        if processed >= batch_max:
            break

    # Mark full-scan complete only when we drain a full read without
    # filling the batch (= nothing new in the journal history left).
    if not _janitor_state["full_scan_complete"] and processed < batch_max:
        _janitor_state["full_scan_complete"] = True
    _janitor_state["first_tick_done"] = True


def _janitor_worker() -> None:
    """Background loop. Tight 8s ticks during full-journal scan to warm
    the per-domain histogram quickly; 90s ticks once steady-state."""
    import time as _time
    if _janitor_stats["started_at"] is None:
        _janitor_stats["started_at"] = _time.time()
    _time.sleep(35)  # startup grace; let other workers settle first
    while True:
        try:
            _janitor_tick()
            _janitor_stats["tick_count"] += 1
        except Exception as exc:
            _janitor_stats["error_count"] += 1
            _janitor_stats["last_error"] = str(exc)[:200]
            _log.warning(f"janitor error: {exc}")
        _janitor_stats["last_tick_at"] = _time.time()
        # Fast cadence while still scanning history; gentle once done.
        if _janitor_state.get("full_scan_complete"):
            _time.sleep(_janitor_stats["tick_period_seconds"])
        else:
            _time.sleep(_janitor_stats["fastscan_period_seconds"])


# Trainer worker state — meta-agent that watches the swarm and
# optimizes resources/tasks. On-demand compute with 10-minute cache;
# when cache rebuilds, writes data/swarm_config.json as the canonical
# coordination file for future Searchers and Janitors to read.
_trainer_state: Dict[str, Any] = {
    "computed_at": None,        # epoch of last analysis
    "analysis": None,           # cached analysis payload
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "auto_dispatched": {},      # domain → last_dispatch_epoch (cooldown)
    "auto_dispatch_total": 0,   # cumulative auto-dispatch count
}

# Trainer cooldown persistence — survives server restart so a domain
# auto-dispatched at 14:00 doesn't get re-dispatched at 14:30 just
# because the server bounced. In-memory dict mirrored to JSON.
_TRAINER_PERSIST_PATH = (
    Path(__file__).parent.parent / "data" / "swarm_trainer_state.json"
)


def _trainer_load_persisted_state() -> None:
    """Read on-disk cooldown state (if any) into _trainer_state. Called
    once at module import so the running process picks up cooldowns
    from a previous instance."""
    try:
        if _TRAINER_PERSIST_PATH.exists():
            data = json.loads(_TRAINER_PERSIST_PATH.read_text(encoding="utf-8"))
            ad = data.get("auto_dispatched") or {}
            if isinstance(ad, dict):
                _trainer_state["auto_dispatched"] = {
                    k: float(v) for k, v in ad.items()
                    if isinstance(v, (int, float))
                }
            _trainer_state["auto_dispatch_total"] = int(
                data.get("auto_dispatch_total", 0)
            )
    except Exception as exc:
        _log.warning(f"trainer state load failed: {exc}")


def _trainer_save_persisted_state() -> None:
    """Write current cooldown state. Called after each compute that
    auto-dispatches anything new. Atomic via tmp + rename."""
    try:
        _TRAINER_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": int(_time.time()) if "_time" in dir() else None,
            "auto_dispatched": _trainer_state.get("auto_dispatched", {}),
            "auto_dispatch_total": _trainer_state.get("auto_dispatch_total", 0),
        }
        tmp = _TRAINER_PERSIST_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(_TRAINER_PERSIST_PATH)
    except Exception as exc:
        _log.warning(f"trainer state save failed: {exc}")


# Load any prior cooldown state immediately so the very first tick
# after restart honors yesterday's dispatches.
_trainer_load_persisted_state()


# ─────────────────────────────────────────────────────────────────────
# Rate limiting — per-IP token bucket
#
# Light-touch protection against floods on write endpoints. Buckets
# refill at a configurable rate; if a request finds the bucket empty
# the endpoint returns HTTP 429 (Too Many Requests).
#
# Read endpoints (/health, /swarm/*, /journal/recent, etc.) are
# intentionally unlimited — they're cheap, polled by the brain UI,
# and any flood there hurts only the requester.
# ─────────────────────────────────────────────────────────────────────

_rate_buckets: Dict[str, Dict[str, Any]] = {}
_rate_lock = _threading.Lock()

# Per-endpoint config — (capacity, refill_rate_per_second)
_RATE_LIMITS: Dict[str, tuple] = {
    "capture":   (60, 60.0 / 60),     # 60/min  → 1/sec sustained
    "dispatch":  (30, 30.0 / 60),     # 30/min  → 0.5/sec sustained
    "speak":     (20, 20.0 / 60),     # 20/min  → ElevenLabs costs $$
    "polymathic": (12, 12.0 / 60),    # 12/min — heavy synthesis path
    "agent":     (12, 12.0 / 60),     # 12/min — uses paid oracle on miss
    # Anonymous write endpoints (Tier 0 hardening)
    "login":     (5,  5.0 / 60),      # 5/min — passphrase brute-force
    "journal":   (30, 30.0 / 60),     # 30/min — anonymous journal write
    "propose":   (10, 10.0 / 60),     # 10/min — almanac proposal spam
    "seal":      (30, 30.0 / 60),     # 30/min — packet seals
    "intake":    (30, 30.0 / 60),     # 30/min — intake questions
    "queue":     (30, 30.0 / 60),     # 30/min — offline queue submits
    "verify":    (60, 60.0 / 60),     # 60/min — generic verifier dispatch
    "ingest":    (10, 10.0 / 60),     # 10/min — drive ingest is expensive
    # Community participation
    "register":  (3,  3.0 / 60),      # 3/min — handle creation is cheap but spammable
    "witness_signal": (10, 10.0 / 60),# 10/min — witness signal submissions
}


def _client_ip(request: "Request") -> str:
    """Best-effort client IP. Honors Cloudflare's CF-Connecting-IP
    when present (we sit behind cloudflared) and falls back to the
    direct peer otherwise."""
    cf = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if cf:
        return cf.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client and client.host else "unknown"


def _rate_check(request: "Request", bucket_key: str) -> None:
    """Token-bucket gate. Raises HTTPException(429) when limit exceeded.
    bucket_key picks the rate from _RATE_LIMITS (or default 60/min)."""
    import time as _time
    now = _time.time()
    capacity, refill_per_s = _RATE_LIMITS.get(bucket_key, (60, 1.0))
    ip = _client_ip(request)
    key = f"{bucket_key}:{ip}"
    with _rate_lock:
        b = _rate_buckets.get(key)
        if b is None:
            b = {"tokens": float(capacity), "last": now}
            _rate_buckets[key] = b
        # Refill since last request
        elapsed = max(0.0, now - b["last"])
        b["tokens"] = min(float(capacity), b["tokens"] + elapsed * refill_per_s)
        b["last"] = now
        if b["tokens"] < 1.0:
            retry_after = max(1, int((1.0 - b["tokens"]) / refill_per_s) + 1)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"rate limit exceeded for '{bucket_key}' from {ip} "
                    f"(retry after ~{retry_after}s)"
                ),
                headers={"Retry-After": str(retry_after)},
            )
        b["tokens"] -= 1.0


# Periodic GC of stale rate buckets so memory doesn't grow unbounded.
def _rate_gc_worker() -> None:
    import time as _time
    while True:
        _time.sleep(600)
        cutoff = _time.time() - 1800   # drop buckets idle 30 min
        with _rate_lock:
            stale = [k for k, b in _rate_buckets.items() if b["last"] < cutoff]
            for k in stale:
                _rate_buckets.pop(k, None)


_rate_gc_thread = _threading.Thread(
    target=_rate_gc_worker, name="rate-gc", daemon=True,
)
_rate_gc_thread.start()
_TRAINER_AUTO_LLM_THRESHOLD = 0.70    # >70% Tier 5 share → action
_TRAINER_AUTO_MIN_SAMPLE = 10         # need ≥10 entries scored for the domain
_TRAINER_AUTO_COOLDOWN_S = 6 * 3600   # 6h between auto-dispatches per domain
_TRAINER_AUTO_PER_TICK_CAP = 5        # max auto-dispatches per Trainer tick
_TRAINER_TTL_SECONDS = 600       # 10 min between recomputes
_SWARM_CONFIG_PATH = (
    Path(__file__).parent.parent / "data" / "swarm_config.json"
)


# Connector worker stats — read by /swarm/connector and the brain UI.
# This is the first formalized worker species: small, narrow job
# (find cross-domain connections), low power, low data, runs forever.
_connector_stats: Dict[str, Any] = {
    "name": "connector",
    "species": "Connector",
    "role": "find cross-domain edges along shared scaffold axes",
    "started_at": None,        # set on first tick
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "pairs_fired_total": 0,    # cumulative across run
    "last_pair_fired": None,   # {ts, domain_a, domain_b, axis_count, shared_axes}
    "active_domains": 0,       # domains with >= 2 seeds
    "tick_period_seconds": 60,
}


def _grid_connector_worker():
    """Background keeper — connects the dots as the journal grows.

    Every 60 seconds:
    1. Reads new journal entries (incremental cursor, fast)
    2. Tags each entry to its domain (via its tag list)
    3. When a new domain accumulates seeds AND shares scaffold axes
       with another active domain, fires a 'connection event'

    Connection events are appended to data/grid_connections.jsonl and
    served via /grid/connections. This is the liturgical layer running
    whether or not anyone is watching — the keeping that makes the
    substrate real.
    """
    import time as _time

    if _connector_stats["started_at"] is None:
        _connector_stats["started_at"] = _time.time()
    while True:
        try:
            _grid_connector_scan()
            _connector_stats["tick_count"] += 1
        except Exception as exc:
            _log.warning(f"grid connector error: {exc}")
            _connector_stats["error_count"] += 1
            _connector_stats["last_error"] = str(exc)[:200]
        _connector_stats["last_tick_at"] = _time.time()
        _time.sleep(60)


def _grid_connector_scan():
    """One scan pass of the journal. Called by the background thread."""
    import time as _time
    try:
        from concordance_engine import grid as _grid
        from concordance_engine import journal as _journal
    except ImportError:
        return

    with _connector_lock:
        # Read recent entries (limit keeps it fast — we only need new ones)
        try:
            _store = _journal.JournalStore()
            entries = _store.list_all(limit=500)
        except Exception:
            return

        new_entries = [e for e in entries if e.id not in _connector_seen_ids]
        for entry in new_entries:
            _connector_seen_ids.add(entry.id)
            tags = getattr(entry, "user_tags", None) or []
            # Find the first tag that is a known grid axis
            domain = next(
                (t for t in tags if t in _grid.AXIS_DIMENSIONS),
                None,
            )
            if not domain:
                continue
            if domain not in _connector_domain_seeds:
                _connector_domain_seeds[domain] = []
            text = (entry.text or "")[:200]
            _connector_domain_seeds[domain].append(text)
            # Keep only the 50 most recent seeds per domain
            if len(_connector_domain_seeds[domain]) > 50:
                _connector_domain_seeds[domain] = _connector_domain_seeds[domain][-50:]

        # Find new domain pairs that share axes and have enough seeds
        active = [
            d for d, seeds in _connector_domain_seeds.items()
            if len(seeds) >= 2
        ]
        for i, da in enumerate(active):
            for db in active[i + 1:]:
                pair = frozenset([da, db])
                if pair in _connector_fired_pairs:
                    continue
                try:
                    shared = _grid.axis_dimensions(da) & _grid.axis_dimensions(db)
                except KeyError:
                    continue
                if not shared:
                    continue
                # New cross-domain connection found — fire the event.
                event = {
                    "ts": _time.time(),
                    "domain_a": da,
                    "domain_b": db,
                    "shared_axes": sorted(shared),
                    "axis_count": len(shared),
                    "sample_a": _connector_domain_seeds[da][-1],
                    "sample_b": _connector_domain_seeds[db][-1],
                }
                with open(_GRID_CONNECTIONS_FILE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event) + "\n")
                _connector_fired_pairs.add(pair)
                _connector_stats["pairs_fired_total"] += 1
                _connector_stats["last_pair_fired"] = {
                    "ts": event["ts"],
                    "domain_a": da,
                    "domain_b": db,
                    "axis_count": event["axis_count"],
                    "shared_axes": event["shared_axes"],
                }
                _log.info(
                    f"grid connection: {da} ↔ {db}  "
                    f"axes={sorted(shared)}"
                )

        # Update active-domains gauge after the scan
        _connector_stats["active_domains"] = len(active)


# ─────────────────────────────────────────────────────────────────────
# SYNTHESIST worker — multi-domain co-occurrence patterns.
# The Connector finds 2-domain edges; the Synthesist finds 3+ domain
# clusters — the cross-domain shapes that polymathic queries traverse.
# Each pattern records the axis intersection across the cluster so
# polymathic precedent lookups stay warm even before any record is
# formally sealed.
# ─────────────────────────────────────────────────────────────────────

_SYNTHESIS_PATTERNS_FILE = (
    Path(__file__).parent.parent / "data" / "synthesis_patterns.jsonl"
)
_SYNTHESIS_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)

_synthesist_lock = _threading.Lock()
_synthesist_seen_ids: set = set()                       # journal entries scanned
_synthesist_seen_signatures: set = set()                # tuple(domains_sorted) already logged

_synthesist_stats: Dict[str, Any] = {
    "name": "synthesist",
    "species": "Synthesist",
    "role": "discover 3+ domain clusters that share a scaffold axis (polymathic patterns)",
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "patterns_total": 0,           # cumulative unique patterns logged
    "deepest_pattern": None,       # {signature, domain_count, axis_count, shared_axes}
    "last_pattern": None,          # last one logged (for /swarm panel)
    "promoted_to_almanac_total": 0,# patterns auto-promoted to entries.jsonl
    "entries_scanned": 0,
    "tick_period_seconds": 90,
}


# ── Pipeline A: pattern → Almanac entry auto-promotion ──────────────
# When the Synthesist discovers a new 3+ domain cluster sharing 2+ axes,
# promote it as kind:"pattern" entry in data/almanac/entries.jsonl. The
# discovery itself is the content; wisdom prose is left as a placeholder
# the curator can fill in later. The Almanac grows on its own from the
# engine's structural finds.

_ALMANAC_ENTRIES_FILE = Path(__file__).parent.parent / "data" / "almanac" / "entries.jsonl"
_promote_lock = _threading.Lock()
_almanac_known_ids: Optional[set] = None  # cached after first read


def _refresh_almanac_known_ids() -> set:
    """Read entries.jsonl and cache the set of known entry IDs."""
    global _almanac_known_ids
    out: set = set()
    if not _ALMANAC_ENTRIES_FILE.exists():
        _almanac_known_ids = out
        return out
    try:
        for line in _ALMANAC_ENTRIES_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                e = json.loads(line)
                eid = e.get("id")
                if eid:
                    out.add(eid)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    _almanac_known_ids = out
    return out


def _pattern_to_almanac_entry(pattern: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a Synthesist pattern event into an Almanac entry."""
    sig = list(pattern.get("signature", []))
    axes = list(pattern.get("shared_axes", []))
    eid = "pattern-" + "_".join(sorted(sig))
    domains_phrase = " + ".join(sig)
    if len(axes) == 1:
        axes_phrase = axes[0].replace("_", " ")
    elif len(axes) == 2:
        axes_phrase = " and ".join(a.replace("_", " ") for a in axes)
    else:
        axes_phrase = ", ".join(a.replace("_", " ") for a in axes[:-1]) + ", and " + axes[-1].replace("_", " ")
    return {
        "id": eid,
        "kind": "pattern",
        "title": f"Cross-domain pattern · {domains_phrase} along {axes_phrase}.",
        "category": "engine_discovery",
        "domains": sig,
        "axes": axes,
        "verdict": "DISCOVERED",
        "verification": (
            f"The Synthesist worker found this {len(sig)}-domain cluster sharing "
            f"{len(axes)} scaffold {'axes' if len(axes) > 1 else 'axis'}: "
            f"{', '.join(axes)}. The cluster surfaced from the journal's tag "
            f"co-occurrence — three or more domains tagged on the same packet, "
            f"and those domains turn out to sit on the same scaffold axis. "
            f"That overlap is the structural ground beneath the connection; "
            f"the engine reads it before any human names it."
        ),
        "wisdom": (
            "(awaiting the dry note — the engine found this pattern; the curator "
            "decides whether the discovery is wisdom or just structure.)"
        ),
        "discovered_at": pattern.get("ts"),
        "first_seen_entry_id": pattern.get("first_seen_entry_id"),
        "triggers": {
            "keywords": list(sig) + axes + ["pattern", "cross-domain", "discovered", "synthesist"],
            "axes": axes,
        },
    }


def _polymathic_seal_to_almanac_entry(
    record: Dict[str, Any],
    content_hash: str,
    ledger_seq: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Shape a sealed CONCORDANT PolymathicRecord into an Almanac
    protocol entry. Returns None if the record can't be shaped cleanly."""
    import time as _time
    verdict = record.get("composite_verdict", "")
    if verdict != "CONCORDANT":
        return None

    dr_list = record.get("domain_results", []) or []
    confirmed = sorted({
        r.get("domain")
        for r in dr_list
        if r.get("verdict") == "CONFIRMED" and r.get("domain")
    })
    if len(confirmed) < 2:
        # Need at least 2 confirmed domains for cross-domain meaning
        return None

    overlaps = record.get("axis_overlaps", []) or []
    axes_set: set = set()
    for ao in overlaps:
        if ao.get("dimension"):
            axes_set.add(ao["dimension"])
    # Fall back to per-domain axis_dims if axis_overlaps is empty
    if not axes_set:
        for r in dr_list:
            for d in (r.get("axis_dims") or []):
                axes_set.add(d)
    axes = sorted(axes_set)

    eid = "polymathic-" + "_".join(confirmed)
    domains_phrase = " + ".join(confirmed)
    situation = record.get("situation", "") or ""

    summary = (
        f"Polymathic seal · {len(confirmed)} of {len(dr_list)} domains confirmed"
        + (f". Shared axes: {', '.join(axes)}." if axes else ".")
    )

    return {
        "id": eid,
        "kind": "protocol",
        "title": f"Cross-domain seal · {domains_phrase}",
        "category": "polymathic",
        "domains": confirmed,
        "axes": axes,
        "verdict": "CONCORDANT",
        "situation": situation,
        "pre_run": {
            "summary": summary,
            "domain_results": [
                {
                    "domain": r.get("domain"),
                    "verdict": r.get("verdict"),
                    "detail": r.get("detail", ""),
                }
                for r in dr_list
            ],
            "axis_overlaps": overlaps,
        },
        "wisdom": (
            "(awaiting the dry note — the engine sealed this cross-domain "
            "situation. The math holds. The wisdom is the curator's to write.)"
        ),
        "discovered_at": _time.time(),
        "content_hash": content_hash,
        "ledger_seq": ledger_seq,
        "triggers": {
            "keywords": list(confirmed) + list(axes) + ["polymathic", "seal", "cross-domain"],
            "axes": axes,
        },
    }


def _promote_polymathic_seal_to_almanac(
    record: Dict[str, Any],
    content_hash: str,
    ledger_seq: Optional[int] = None,
) -> bool:
    """Promote a sealed CONCORDANT polymathic record to an Almanac entry.

    Dedup by domain signature: if `polymathic-{sorted_domains}` is
    already in the book, skip. Multiple seals with the same domain
    combination still live in the ledger; only the first becomes a
    canonical Almanac entry.

    Returns True if a new entry was appended; False on dedup, non-
    CONCORDANT verdict, insufficient confirmed domains, or write error.
    """
    entry = _polymathic_seal_to_almanac_entry(record, content_hash, ledger_seq)
    if entry is None:
        return False

    eid = entry["id"]
    with _promote_lock:
        if _almanac_known_ids is None:
            _refresh_almanac_known_ids()
        if eid in _almanac_known_ids:
            return False
        _refresh_almanac_known_ids()
        if eid in _almanac_known_ids:
            return False

        try:
            line = json.dumps(entry, ensure_ascii=False) + "\n"
            with open(_ALMANAC_ENTRIES_FILE, "a", encoding="utf-8") as fh:
                fh.write(line)
            _almanac_known_ids.add(eid)
            _log.info(
                f"polymathic-seal → almanac: promoted {eid} "
                f"({len(entry['domains'])} domains, {len(entry['axes'])} shared axes)"
            )
            return True
        except OSError as exc:
            _log.warning(f"polymathic-seal → almanac append failed: {exc}")
            return False


def _promote_pattern_to_almanac(pattern: Dict[str, Any]) -> bool:
    """Promote a synthesist pattern event to an Almanac entry.

    Returns True if a new entry was appended; False if the pattern is
    already in the book or a write error occurred.

    Quality gate: only promote patterns with axis_count >= 2 (deeper
    than 2-domain edges; structurally meaningful).
    """
    if int(pattern.get("axis_count", 0)) < 2:
        return False
    sig = pattern.get("signature") or []
    if not sig or len(sig) < 3:
        return False

    entry = _pattern_to_almanac_entry(pattern)
    eid = entry["id"]

    with _promote_lock:
        # Lazy-init the known-ID cache on first use
        if _almanac_known_ids is None:
            _refresh_almanac_known_ids()
        # Belt-and-suspenders: refresh against the file in case a curator
        # appended manually since we last cached.
        if eid in _almanac_known_ids:
            return False
        _refresh_almanac_known_ids()
        if eid in _almanac_known_ids:
            return False

        # Append the new entry
        try:
            line = json.dumps(entry, ensure_ascii=False) + "\n"
            with open(_ALMANAC_ENTRIES_FILE, "a", encoding="utf-8") as fh:
                fh.write(line)
            _almanac_known_ids.add(eid)
            _log.info(
                f"synthesist → almanac: promoted {eid} "
                f"({len(sig)} domains × {len(entry['axes'])} axes)"
            )
            return True
        except OSError as exc:
            _log.warning(f"synthesist → almanac append failed: {exc}")
            return False


def _synthesist_worker():
    """Background keeper — finds 3+ domain co-occurrence patterns.

    Every 90 seconds:
    1. Walks recent journal entries the Synthesist has not yet inspected
    2. For each entry, extracts the set of grid-known domain tags
    3. If 3+ distinct domains co-occur AND they share at least one axis,
       records the pattern (deduped by signature)

    The output feeds the polymathic precedent lookup so future poly runs
    land on a structural overlay even when no formal PolymathicRecord
    has been sealed for that exact shape yet.
    """
    import time as _time

    if _synthesist_stats["started_at"] is None:
        _synthesist_stats["started_at"] = _time.time()
    while True:
        try:
            _synthesist_scan()
            _synthesist_stats["tick_count"] += 1
        except Exception as exc:
            _log.warning(f"synthesist error: {exc}")
            _synthesist_stats["error_count"] += 1
            _synthesist_stats["last_error"] = str(exc)[:200]
        _synthesist_stats["last_tick_at"] = _time.time()
        _time.sleep(_synthesist_stats["tick_period_seconds"])


def _synthesist_scan():
    """One scan pass. Looks for journal entries with 3+ grid-known domain tags."""
    import time as _time
    try:
        from concordance_engine import journal as _journal
        from concordance_engine.synthesist import (
            discover_pattern,
            extract_domains_from_tags,
            signature_key,
        )
    except ImportError:
        return

    with _synthesist_lock:
        try:
            store = _journal.JournalStore()
            entries = store.list_all(limit=500)
        except Exception:
            return

        new_entries = [e for e in entries if e.id not in _synthesist_seen_ids]

        deepest = _synthesist_stats.get("deepest_pattern")

        for entry in new_entries:
            _synthesist_seen_ids.add(entry.id)
            _synthesist_stats["entries_scanned"] += 1
            tags = list(getattr(entry, "user_tags", None) or [])
            domains = extract_domains_from_tags(tags)
            sig = signature_key(domains)
            if not sig or len(sig) < 3:
                continue
            if sig in _synthesist_seen_signatures:
                continue
            pattern = discover_pattern(domains)
            if not pattern:
                continue

            event = {
                "ts": _time.time(),
                "signature": pattern["signature"],
                "domain_count": pattern["domain_count"],
                "shared_axes": pattern["shared_axes"],
                "axis_count": pattern["axis_count"],
                "first_seen_entry_id": entry.id,
            }
            try:
                with open(_SYNTHESIS_PATTERNS_FILE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event) + "\n")
            except OSError:
                continue

            _synthesist_seen_signatures.add(sig)
            _synthesist_stats["patterns_total"] += 1
            _synthesist_stats["last_pattern"] = event

            # Pipeline A — auto-promote each new pattern to an Almanac
            # entry of kind "pattern". The discovery itself is the
            # content; wisdom prose stays as a placeholder until a
            # curator reads it. The book grows on its own from the
            # engine's structural finds.
            try:
                if _promote_pattern_to_almanac(event):
                    _synthesist_stats["promoted_to_almanac_total"] = (
                        _synthesist_stats.get("promoted_to_almanac_total", 0) + 1
                    )
            except Exception as exc:
                _log.warning(f"synthesist promote-to-almanac failed: {exc}")

            # Track deepest pattern (most domains × most shared axes)
            depth = pattern["domain_count"] * max(1, pattern["axis_count"])
            prior_depth = (
                deepest["domain_count"] * max(1, deepest["axis_count"])
                if deepest else 0
            )
            if depth > prior_depth:
                deepest = {
                    "signature": pattern["signature"],
                    "domain_count": pattern["domain_count"],
                    "axis_count": pattern["axis_count"],
                    "shared_axes": pattern["shared_axes"],
                }
                _synthesist_stats["deepest_pattern"] = deepest

            _log.info(
                f"synthesis pattern: {'+'.join(pattern['signature'])}  "
                f"axes={pattern['shared_axes']}"
            )


# ─────────────────────────────────────────────────────────────────────
# MINER worker — corpus → almanac-candidate hummingbird.
# Walks a configured EPUB corpus, extracts passage-shaped text,
# scores each against the engine's axes + concepts, and persists
# strong candidates to data/miner/candidates.jsonl for curator
# review. Never auto-publishes to the Almanac. The engine does the
# math; the human does the wisdom.
# ─────────────────────────────────────────────────────────────────────

_miner_lock = _threading.Lock()
_miner_book_cursor = 0  # rotates through corpus books

_miner_stats: Dict[str, Any] = {
    "name": "miner",
    "species": "Miner",
    "role": "extract candidate Almanac entries from a corpus of EPUBs",
    "started_at": None,
    "last_tick_at": None,
    "tick_count": 0,
    "error_count": 0,
    "last_error": None,
    "candidates_total": 0,
    "passages_seen_total": 0,
    "books_in_corpus": 0,
    "last_book": None,
    "last_summary": None,
    "tick_period_seconds": 180,
}


def _miner_worker():
    """Background loop. One book per tick; rotate through the corpus.

    Slow on purpose — 180s ticks (3 min). The point is patience: walk
    the books, find candidates, write them down. A single-book pass
    takes a fraction of a second; the rest is rest.
    """
    import time as _time
    if _miner_stats["started_at"] is None:
        _miner_stats["started_at"] = _time.time()
    # Generous startup grace — let the rest of the app settle first.
    _time.sleep(45)
    while True:
        try:
            _miner_tick()
            _miner_stats["tick_count"] += 1
        except Exception as exc:
            _log.warning(f"miner error: {exc}")
            _miner_stats["error_count"] += 1
            _miner_stats["last_error"] = str(exc)[:200]
        _miner_stats["last_tick_at"] = _time.time()
        _time.sleep(_miner_stats["tick_period_seconds"])


def _miner_tick():
    """One pass over one book in the corpus."""
    global _miner_book_cursor
    try:
        from concordance_engine import miner as _miner
    except ImportError:
        return

    with _miner_lock:
        books = _miner.list_corpus_books()
        _miner_stats["books_in_corpus"] = len(books)
        if not books:
            return
        # Rotate
        epub_path = books[_miner_book_cursor % len(books)]
        _miner_book_cursor += 1
        summary = _miner.mine_one_book(epub_path)
        _miner_stats["candidates_total"] += int(summary.get("candidates_proposed", 0))
        _miner_stats["passages_seen_total"] += int(summary.get("passages_seen", 0))
        _miner_stats["last_book"] = epub_path.name
        _miner_stats["last_summary"] = summary
        if int(summary.get("candidates_proposed", 0)) > 0:
            _log.info(
                f"miner: {summary['candidates_proposed']} candidates from {epub_path.name} "
                f"({summary['passages_seen']} passages scanned, top score "
                f"{summary['top_score_in_book']})"
            )


@app.get("/swarm/miner", tags=["agents"])
def swarm_miner(limit: int = Query(20, ge=1, le=200)):
    """Miner stats + recent candidates.

    The Miner walks an EPUB corpus and proposes draft Almanac entries.
    Candidates persist to data/miner/candidates.jsonl. The curator
    (Matt) reviews, picks, edits the wisdom note, and appends to
    data/almanac/entries.jsonl manually. The engine never auto-publishes.

    Returns:
      stats              — miner state (tick count, candidates total,
                            last book, last tick summary)
      candidates         — list of recent draft candidates ranked by
                            score (descending)
      candidates_on_disk — total in the candidates file
      corpus_dir         — where the miner is reading from
    """
    try:
        from concordance_engine import miner as _miner
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    cands = _miner.list_candidates(limit=limit)
    # The full file might be larger than `limit`; report the count
    full_path = _miner.candidates_path()
    on_disk = 0
    if full_path.exists():
        try:
            on_disk = sum(1 for _ in full_path.read_text("utf-8", errors="replace").splitlines() if _.strip())
        except OSError:
            on_disk = len(cands)
    return {
        "stats": _miner_stats,
        "candidates": cands,
        "candidates_on_disk": on_disk,
        "corpus_dir": str(_miner.corpus_dir()),
        "candidates_file": str(full_path),
    }


@app.get("/swarm/synthesist", tags=["agents"])
def swarm_synthesist(
    limit: int = Query(50, ge=1, le=500),
):
    """Synthesist worker: multi-domain pattern stats + recent log.

    Returns the running stats plus the most recent N pattern events
    discovered. Patterns are 3+ domain clusters that share at least one
    scaffold axis — the structural seed of a polymathic query.
    """
    events: List[Dict] = []
    if _SYNTHESIS_PATTERNS_FILE.exists():
        try:
            for line in _SYNTHESIS_PATTERNS_FILE.read_text(
                "utf-8", errors="replace"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    events.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return {
        "stats": _synthesist_stats,
        "patterns": events[:limit],
        "patterns_on_disk": len(events),
    }


# ─────────────────────────────────────────────────────────────────────
# Almanac — the readable book.
# Mirrors the MCP `almanac` tool over plain HTTP so the website
# can render it without an MCP client. Same data file
# (data/almanac/entries.jsonl), same shape.
# ─────────────────────────────────────────────────────────────────────
_ALMANAC_FILE = Path(__file__).parent.parent / "data" / "almanac" / "entries.jsonl"


def _almanac_entries() -> List[Dict[str, Any]]:
    """Read the almanac entries from disk. Re-reads each call so
    edits to entries.jsonl appear without a server bounce."""
    if not _ALMANAC_FILE.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in _ALMANAC_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


@app.get("/almanac.rss", include_in_schema=False)
def almanac_rss():
    """RSS 2.0 feed of the almanac. Subscribers get new entries delivered
    via any feed reader — passive distribution, no posting required."""
    from xml.sax.saxutils import escape as _xml_esc
    entries = _almanac_entries()
    now = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())

    def _item(e):
        eid = e.get("id", "")
        title = e.get("title", "(untitled)")
        link = f"https://narrowhighway.com/almanac.html#{eid}"
        wisdom = e.get("wisdom", "")
        kind = e.get("kind", "entry")
        verdict = e.get("verdict", "")
        category = e.get("category", "")
        desc_lines = []
        if verdict:
            desc_lines.append(f"<strong>{_xml_esc(verdict)}</strong> · {_xml_esc(kind)}")
        if category:
            desc_lines.append(f"category: {_xml_esc(category)}")
        if wisdom:
            desc_lines.append(_xml_esc(wisdom))
        domains = e.get("domains") or []
        if domains:
            desc_lines.append("domains: " + ", ".join(_xml_esc(d) for d in domains[:10]))
        description = "<br>".join(desc_lines)
        # use discovered_at or now as pubDate
        ts = e.get("discovered_at") or e.get("ledger_seq") or 0
        if isinstance(ts, (int, float)) and ts > 1_000_000_000:
            pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(ts))
        else:
            pub = now
        return f"""<item>
      <title>{_xml_esc(title)}</title>
      <link>{_xml_esc(link)}</link>
      <guid isPermaLink="false">narrowhighway-almanac-{_xml_esc(eid)}</guid>
      <pubDate>{pub}</pubDate>
      <category>{_xml_esc(kind)}</category>
      <description>{description}</description>
    </item>"""

    items_xml = "\n    ".join(_item(e) for e in entries[:50])
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Concordance Almanac</title>
    <link>https://narrowhighway.com/almanac.html</link>
    <atom:link href="https://narrowhighway.com/almanac.rss" rel="self" type="application/rss+xml"/>
    <description>What the engine has worked through. Sayings, protocols, and engine-discovered patterns with their dry notes.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <generator>Concordance Engine</generator>
    {items_xml}
  </channel>
</rss>"""
    from fastapi.responses import Response
    return Response(content=rss, media_type="application/rss+xml; charset=utf-8")


@app.get("/almanac", tags=["humans"])
def almanac_index():
    """Return the full almanac for human reading.

    Used by /almanac.html. Returns every entry plus the kinds,
    categories, and verdicts present in the book so the page can
    render filter chips without a second roundtrip.
    """
    entries = _almanac_entries()
    return {
        "entries": entries,
        "total": len(entries),
        "kinds":      sorted({e.get("kind", "protocol") for e in entries}),
        "categories": sorted({e.get("category") for e in entries if e.get("category")}),
        "verdicts":   sorted({e.get("verdict")  for e in entries if e.get("verdict")}),
        "preface": (
            "The Almanac is what the engine has worked through. "
            "Two kinds of entry: protocols (canonical multi-domain "
            "situations, pre-run through the engine) and sayings "
            "(folk wisdom verified by computation, with the dry note). "
            "The Almanac does not panic."
        ),
    }


@app.get("/almanac/{entry_id}", tags=["humans"])
def almanac_entry(entry_id: str):
    """One entry by id — used for permalink rendering and JSON-LD."""
    _safe_id(entry_id, "entry_id")
    for e in _almanac_entries():
        if e.get("id") == entry_id:
            return e
    raise HTTPException(status_code=404, detail=f"no almanac entry with id {entry_id!r}")


class AlmanacProposeRequest(BaseModel):
    """Body for `POST /almanac/propose` — public draft-entry surface.

    Mirrors the MCP `propose_almanac_entry` tool over plain HTTP so
    /almanac.html (and any human with curl) can submit a candidate
    saying or situation for engine pre-run + curation.
    """
    candidate: str
    kind: str = "auto"           # "auto" | "saying" | "protocol"
    title: Optional[str] = None
    category: Optional[str] = None
    # Optional contributor handle. If supplied and registered, the
    # proposal is attributed to that handle and counts toward their
    # contributor stats / badge progression. Anonymous proposals are
    # still accepted; they just don't accumulate.
    contributor_handle: str = ""


@app.post("/almanac/propose", tags=["humans"])
def almanac_propose(request: Request, req: AlmanacProposeRequest):
    """Propose a draft almanac entry. Engine does the math.

    The draft NEVER auto-commits — it goes back to the caller for
    curation. Matt-as-curator (or any reader) decides whether the
    wisdom and verdict belong in the book; if yes, the entry is
    appended to data/almanac/entries.jsonl manually.

    Rate-limited per-IP at 10/min — polymathic + oracle is paid work.
    """
    _rate_check(request, "propose")

    candidate = (req.candidate or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="candidate is required")
    if len(candidate) > 4000:
        raise HTTPException(status_code=400, detail="candidate too long (max 4000 chars)")

    # Decide kind
    chosen_kind = req.kind
    if chosen_kind == "auto":
        is_short = len(candidate) <= 120
        has_numbers = any(ch.isdigit() for ch in candidate)
        chosen_kind = "saying" if (is_short and not has_numbers) else "protocol"

    # Slug
    import re as _re
    seed = (req.title or candidate).lower()
    slug = _re.sub(r"[^a-z0-9]+", "_", seed).strip("_")[:48] or "draft_entry"

    # Suggested keyword triggers
    keywords = [
        w for w in _re.findall(r"[a-zA-Z]{4,}", candidate.lower())
        if w not in {"that","this","with","from","into","when","than",
                      "what","were","they","then","have","been","does"}
    ][:10]

    draft: Dict[str, Any] = {
        "id": slug,
        "kind": chosen_kind,
        "title": req.title or candidate,
        "category": req.category or "uncategorized",
        "domains": [],
        "axes": [],
        "verdict": "DRAFT",
        "wisdom": "(curator: write the dry note here — what does the math actually show?)",
        "triggers": {"keywords": keywords, "axes": []},
    }

    # Run polymathic locally — same code path as run_polymathic agent + tool
    try:
        from concordance_engine.agent.poly_agent import run_polymathic as _run_poly
        rec = _run_poly(situation=candidate, max_domains=8, decompose=True)
        rec_d = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__)

        if chosen_kind == "saying":
            draft["verification"] = (
                "(curator: replace this with a one-paragraph explanation "
                "of why the math gives the verdict it does. The polymathic "
                "run below is the engine's first pass — distill it.)"
            )
        else:
            draft["situation"] = candidate
            draft["pre_run"] = {
                "summary": "(curator: write a one-sentence summary)",
                "domain_results": rec_d.get("domain_results", []),
                "axis_overlaps": rec_d.get("axis_overlaps", []),
            }

        draft["verdict"] = rec_d.get("composite_verdict", "DRAFT")
        draft["domains"] = sorted({
            r.get("domain") for r in (rec_d.get("domain_results") or [])
            if r.get("domain")
        })

        # Collect axes from the fired domains
        fired_axes: set = set()
        for r in (rec_d.get("domain_results") or []):
            for a in (r.get("axis_dims") or []):
                fired_axes.add(a)
        draft["axes"] = sorted(fired_axes)
        draft["triggers"]["axes"] = sorted(fired_axes)

        draft["_engine_trail"] = {
            "atomic_claims": rec_d.get("atomic_claims", []),
            "quarantined_claims": rec_d.get("quarantined_claims", []),
            "axis_overlaps": rec_d.get("axis_overlaps", []),
            "content_hash": rec_d.get("content_hash"),
        }
    except Exception as exc:
        draft["_engine_error"] = str(exc)[:240]
        draft["_engine_note"] = (
            "Polymathic run failed for this candidate. Draft returned "
            "without computed verdict."
        )

    # Community attribution
    handle = (req.contributor_handle or "").strip().lower()
    attribution: Dict[str, Any] = {}
    if handle and _community.is_valid_handle(handle):
        if _community.load_contributor(handle) is not None:
            _community.bump_stat(handle, "proposals_submitted", 1)
            _community.log_activity({
                "kind": "almanac_propose",
                "handle": handle,
                "proposal_id": draft["id"],
                "kind_chosen": chosen_kind,
                "verdict": draft.get("verdict", "?"),
            })
            draft["proposed_by"] = handle
            attribution = {"contributor_handle": handle}

    return {
        "draft": draft,
        "attribution": attribution,
        "instructions_for_curator": (
            "1. Review the draft. Check that the verdict the engine produced "
            "matches your intent.\n"
            "2. Replace the placeholder wisdom prose with a short dry note in "
            "the Almanac's voice — what does the math actually show?\n"
            "3. For sayings: write the verification paragraph. For protocols: "
            "write the pre_run.summary one-liner.\n"
            "4. Adjust category, triggers, and id slug as needed.\n"
            "5. When ready, append the cleaned-up entry as one JSON line to "
            "data/almanac/entries.jsonl, and bounce the engine to load."
        ),
    }


@app.get("/grid/residue", tags=["agents"])
def grid_residue():
    """The residue surface — what hasn't been named yet, displayed.

    Per ambiguity cluster, shows the canonical members side-by-side with
    their verifier docstrings (the actual claims each one checks). The
    engine doesn't propose discriminating axes — it arranges what's
    there, so a human can perceive what they vary on (or recognize
    that they don't, at this resolution).

    Same posture for sparse triples: shows the triple's neighbors so
    the gap has context. The engine doesn't fill the gap. It exhibits
    it."""
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Pull docstrings from the actual verifier functions (engine's
    # source of truth on what each domain checks)
    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except Exception:
        ALL_TOOLS = {}

    def _docstring_for(name: str) -> str:
        fn = ALL_TOOLS.get(f"verify_{name}")
        if not fn:
            return ""
        doc = (fn.__doc__ or "").strip()
        # First paragraph only — the rest is usually example syntax
        first = doc.split("\n\n", 1)[0]
        # Collapse whitespace
        return " ".join(first.split())[:400]

    aliases_known = getattr(_grid, "ALIASES", {})
    domains_canonical = {
        n: list(dims) for n, dims in _grid.AXIS_DIMENSIONS.items()
        if n not in aliases_known
    }

    # Build ambiguity clusters (same as /grid/coherence)
    by_signature: Dict[tuple, List[str]] = {}
    for n, dims in domains_canonical.items():
        sig = tuple(sorted(dims))
        by_signature.setdefault(sig, []).append(n)

    clusters: List[Dict[str, Any]] = []
    for sig, names in by_signature.items():
        if len(names) < 2:
            continue
        members = []
        for nm in sorted(names):
            members.append({
                "name": nm,
                "what_it_verifies": _docstring_for(nm) or "(no verifier docstring available)",
                "is_umbrella": nm in getattr(_grid, "UMBRELLAS", {}),
            })
        clusters.append({
            "signature": list(sig),
            "count": len(names),
            "members": members,
        })
    clusters.sort(key=lambda c: -c["count"])

    # Sparse cells (empty + size-1 + size-2 triples) with neighbor context
    from itertools import combinations
    axes = list(_grid.DIMENSIONS)
    sparse_cells: List[Dict[str, Any]] = []
    for combo in combinations(axes, 3):
        covered = sorted([
            n for n, dims in domains_canonical.items()
            if set(combo).issubset(set(dims))
        ])
        if len(covered) > 2:
            continue
        # Find pair-level neighbors: domains that share ANY 2 of the 3 axes
        neighbor_set = set()
        for pair in combinations(combo, 2):
            pair_set = set(pair)
            for n, dims in domains_canonical.items():
                if pair_set.issubset(set(dims)) and n not in covered:
                    neighbor_set.add(n)
        sparse_cells.append({
            "triple": list(combo),
            "occupants": covered,
            "occupant_count": len(covered),
            "neighbors_via_pair": sorted(neighbor_set)[:8],
            "neighbor_count": len(neighbor_set),
        })
    sparse_cells.sort(key=lambda s: (s["occupant_count"], s["triple"]))

    return {
        "canonical_domain_count": len(domains_canonical),
        "axis_count": len(axes),
        "ambiguity_clusters": clusters,
        "ambiguity_cluster_count": len(clusters),
        "sparse_cells": sparse_cells,
        "sparse_cell_count": len(sparse_cells),
        "notes": {
            "posture": "The engine shows. Naming belongs to the human looking.",
            "ambiguity_clusters": "Canonical domains sharing identical axis signatures. Their verifier docstrings are displayed side-by-side; the dimension they vary on may or may not have a name yet.",
            "sparse_cells": "Axis-triples with 0-2 canonical domains. Their pair-neighbors are shown so the gap has context. A gap may indicate a missing domain, an impossible combination, or a real domain that hasn't been named yet.",
        },
    }


@app.get("/grid/coherence", tags=["agents"])
def grid_coherence():
    """Engine self-audit. The scaffold's structural anomalies as data.

    Computes — purely from the live grid — what the engine itself can
    see about its own design quality. Output is the same regardless of
    who's asking; the engine reports what is, not what it thinks.

    Five categories of finding:

    - axis_weights        per-axis domain count + light/heavy outliers
    - alias_clusters       domains with identical axis sets (likely synonyms)
    - umbrella_conflicts   sub_domain names whose prefix is also a canonical
                           name (e.g. physics_dimensional vs physics)
    - empty_triples        triples of axes with zero domains spanning all three
    - sparse_triples       triples with exactly one or two domains spanning
                           all three (single point of failure)

    The engine doesn't decide what to do about any of these. It surfaces
    them. The keeping is the substrate."""
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    from itertools import combinations

    axes = list(_grid.DIMENSIONS)
    # Canonical-only view: drop aliases so the audit measures actual
    # structural ambiguity, not the deliberate synonyms in the dispatch
    # layer. `domains` is the source-of-truth for every check below.
    aliases_known = getattr(_grid, "ALIASES", {})
    domains = {
        n: list(dims) for n, dims in _grid.AXIS_DIMENSIONS.items()
        if n not in aliases_known
    }
    # Also collect the alias-cluster view for the report (separate finding)
    alias_clusters_known = {}
    for alias, canon in aliases_known.items():
        alias_clusters_known.setdefault(canon, []).append(alias)

    # ── axis weights ──
    per_axis: Dict[str, List[str]] = {a: [] for a in axes}
    for n, dims in domains.items():
        for d in dims:
            if d in per_axis:
                per_axis[d].append(n)
    weights = {a: len(per_axis[a]) for a in axes}
    avg_weight = sum(weights.values()) / max(1, len(axes))
    light = sorted(
        [(a, w) for a, w in weights.items() if w < avg_weight * 0.7],
        key=lambda kv: kv[1],
    )
    heavy = sorted(
        [(a, w) for a, w in weights.items() if w > avg_weight * 1.3],
        key=lambda kv: -kv[1],
    )

    # ── alias clusters: same axis set, different names ──
    by_signature: Dict[tuple, List[str]] = {}
    for n, dims in domains.items():
        sig = tuple(sorted(dims))
        by_signature.setdefault(sig, []).append(n)
    alias_clusters = sorted(
        [
            {"signature": list(sig), "names": sorted(names), "count": len(names)}
            for sig, names in by_signature.items()
            if len(names) > 1
        ],
        key=lambda c: -c["count"],
    )

    # ── umbrella conflicts: sub_domain whose prefix is also canonical ──
    name_set = set(domains.keys())
    umbrella_conflicts: List[Dict[str, Any]] = []
    for n in domains:
        if "_" in n:
            prefix = n.split("_")[0]
            if prefix in name_set and prefix != n:
                umbrella_conflicts.append({
                    "sub": n, "umbrella": prefix,
                    "shared_axes": sorted(set(domains[n]) & set(domains[prefix])),
                })
    umbrella_conflicts.sort(key=lambda r: (r["umbrella"], r["sub"]))

    # ── triple coverage ──
    empty_triples: List[List[str]] = []
    sparse_triples: List[Dict[str, Any]] = []
    for combo in combinations(axes, 3):
        covered = sorted([
            n for n, dims in domains.items()
            if set(combo).issubset(set(dims))
        ])
        if len(covered) == 0:
            empty_triples.append(list(combo))
        elif len(covered) <= 2:
            sparse_triples.append({"triple": list(combo), "domains": covered})
    sparse_triples.sort(key=lambda s: (len(s["domains"]), s["triple"]))

    # ── coverage matrix (pair-level) ──
    pair_coverage: Dict[str, Dict[str, int]] = {a: {} for a in axes}
    for a in axes:
        for b in axes:
            if a == b:
                pair_coverage[a][b] = weights[a]
                continue
            n = sum(1 for dims in domains.values() if a in dims and b in dims)
            pair_coverage[a][b] = n

    # ── depth distribution ──
    depths: Dict[int, int] = {}
    for dims in domains.values():
        depths[len(dims)] = depths.get(len(dims), 0) + 1

    known_alias_count = sum(len(a) for a in alias_clusters_known.values())
    # Known-alias clusters reformatted for the report
    known_alias_report = sorted(
        [
            {"canonical": canon, "aliases": sorted(aliases), "count": len(aliases)}
            for canon, aliases in alias_clusters_known.items() if aliases
        ],
        key=lambda c: -c["count"],
    )

    return {
        "summary": {
            "canonical_domain_count": len(domains),
            "known_alias_count": known_alias_count,
            "total_registry_size": len(domains) + known_alias_count,
            "axis_count": len(axes),
            "average_axis_weight": round(avg_weight, 1),
            "light_axes": [a for a, _ in light],
            "heavy_axes": [a for a, _ in heavy],
            "ambiguous_signature_clusters": len(alias_clusters),
            "ambiguous_redundant_count": sum(c["count"] - 1 for c in alias_clusters),
            "umbrella_conflicts": len(umbrella_conflicts),
            "empty_triples": len(empty_triples),
            "sparse_triples": len(sparse_triples),
            "depth_distribution": depths,
        },
        "axis_weights": weights,
        "pair_coverage": pair_coverage,
        "known_aliases": known_alias_report,
        "ambiguous_signature_clusters": alias_clusters,
        "umbrella_conflicts": umbrella_conflicts,
        "empty_triples": empty_triples,
        "sparse_triples": sparse_triples,
        "notes": {
            "known_aliases": "Deliberate synonyms registered in grid.ALIASES. Not structural ambiguity.",
            "ambiguous_signature_clusters": "Canonical domains sharing identical axis signatures. If the count is > 0, the 7-axis resolution can't distinguish them — either merge, retag, or add an axis.",
            "umbrella_conflicts": "Sub-domain names (e.g. physics_dimensional) whose prefix is also canonical (physics). Tag the parent as an umbrella to suppress.",
            "empty_triples": "Three-axis intersections with zero canonical domains. Either a real structural hole or an axis combination that is physically/conceptually impossible.",
        },
    }


class _AxisAddRequest(_CommBaseModel):
    """Body for POST /grid/axis/add — operator-only."""
    name: str          # canonical name like 'subject_matter'
    label: str = ""    # short label like 'subject' (defaults to first underscore-separated word)
    criterion: str     # one sentence: what counts as carrying this axis
    carriers: List[str]  # canonical domain names that carry this axis


@app.post("/grid/axis/add", tags=["agents"])
def grid_axis_add(request: Request, req: _AxisAddRequest):
    """Operator-only: name an axis the human has perceived in the residue.

    Persists the new axis to data/grid/axis_extensions.jsonl (append-only),
    mutates DIMENSIONS and AXIS_DIMENSIONS in place, returns the updated
    scaffold count. The next /grid/scaffold response includes the new
    dimension; the 3D engine view picks it up on reload (chassis is
    N-axis-agnostic).

    Reversibility: edit or remove the line in axis_extensions.jsonl and
    restart the engine. No destructive change to source-defined arrays.

    Requires X-API-Key."""
    _community_require_api_key(request)
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        record = _grid.add_axis(
            name=req.name,
            label=req.label,
            criterion=req.criterion,
            carriers=req.carriers,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {
        "ok": True,
        "added": record,
        "dimensions_now": list(_grid.DIMENSIONS),
        "dimension_count_now": len(_grid.DIMENSIONS),
        "carriers_updated": [
            {"name": c, "axes_now": sorted(_grid.AXIS_DIMENSIONS.get(c, []))}
            for c in record["carriers"]
        ],
    }


@app.get("/grid/scaffold", tags=["agents"])
def grid_scaffold():
    """Full domain→dimension mapping for the 7-axis scaffold.

    Returns the complete static grid: every domain and which of the 7
    scaffold dimensions (encoding, metabolism, reasoning, physical_substance,
    authority_trust, time_sequence, conservation_balance) it sits on.

    Agents: load this once at startup to understand the structural position
    of any domain the engine might return.
    """
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "dimensions": list(_grid.DIMENSIONS),
        "axes": {
            axis: sorted(dims)
            for axis, dims in _grid.AXIS_DIMENSIONS.items()
        },
        "umbrellas": {
            parent: list(children)
            for parent, children in _grid.UMBRELLAS.items()
        },
        "axis_count": len(_grid.AXIS_DIMENSIONS),
        "dimension_count": len(_grid.DIMENSIONS),
    }


@app.get("/grid/domain/{domain}", tags=["agents"])
def grid_domain_position(domain: str):
    """Scaffold position of one domain.

    Returns which of the 7 dimensions this domain sits on, its depth
    (structural complexity), and the 20 most-adjacent domains ranked by
    number of shared dimensions.

    This is the data that try.html shows in the STRUCTURAL POSITION
    section after every verification result.
    """
    _safe_domain(domain)
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if domain not in _grid.AXIS_DIMENSIONS:
        raise HTTPException(status_code=404, detail=f"unknown domain: {domain!r}")

    dims = sorted(_grid.axis_dimensions(domain))
    adj = _grid.adjacent(domain)
    return {
        "domain": domain,
        "dimensions": dims,
        "depth": len(dims),
        "adjacent": [
            {
                "domain": other,
                "shared_axes": sorted(shared),
                "count": len(shared),
            }
            for other, shared in adj[:20]
        ],
        "umbrella_children": list(_grid.umbrella_children(domain)),
        "note": (
            "depth >= 4 = structurally deep; "
            "adjacent domains share at least one scaffold axis"
        ),
    }


@app.get("/grid/connections", tags=["agents"])
def grid_connections(
    limit: int = Query(50, ge=1, le=500),
    since: float = Query(0.0, description="Unix epoch; only events after this ts"),
    domain: Optional[str] = Query(None, description="Filter to events involving this domain"),
    min_axes: int = Query(1, ge=1, description="Only return events with >= N shared axes"),
):
    """Cross-domain connection events discovered by the background keeper.

    Connection events fire when the background connector finds seeds
    from two different domains in the journal that touch the same scaffold
    axis — proving the structural pattern is present in actual content,
    not just theory.

    These are the moments the engine was built for: chemistry and covenant
    law both speaking about conservation_balance; physics and economics
    both running on reasoning + conservation; genetics and theology sharing
    encoding + authority_trust.

    Poll this endpoint or subscribe to /grid/connections/stream for live updates.
    """
    events: List[Dict] = []
    if _GRID_CONNECTIONS_FILE.exists():
        for line in _GRID_CONNECTIONS_FILE.read_text(
            "utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("ts", 0) <= since:
                continue
            if e.get("axis_count", 0) < min_axes:
                continue
            if domain and domain not in (e.get("domain_a"), e.get("domain_b")):
                continue
            events.append(e)

    events.sort(key=lambda x: -x.get("ts", 0))
    return {
        "count": len(events[:limit]),
        "events": events[:limit],
        "total_on_file": len(events),
        "connector_status": {
            "active_domains": len(_connector_domain_seeds),
            "fired_pairs": len(_connector_fired_pairs),
            "seen_entries": len(_connector_seen_ids),
        },
    }


# ─────────────────────────────────────────────────────────────────────
# Swarm — worker agent status
#
# Each worker is a small autonomous worker with a narrow job. They
# write through the same /capture (etc.) doors as anyone else; nothing
# privileged. Stats are read-only for observers (the brain UI, the
# Trainer, agents auditing the keeping).
#
# First species: Connector — finds cross-domain edges along shared
# scaffold axes. Already running as a background thread; this endpoint
# just exposes its stats.
# ─────────────────────────────────────────────────────────────────────

@app.get("/swarm/connector", tags=["agents"])
def swarm_connector():
    """Live stats for the Connector worker.

    The Connector watches new journal entries every 60s and fires a
    cross-domain connection event whenever two domains accumulate seeds
    AND share at least one scaffold axis. Each pair fires exactly once.

    Returns:
      name, species, role         — identity
      started_at, last_tick_at    — uptime markers
      tick_count, error_count     — health
      pairs_fired_total           — cumulative connections discovered
      last_pair_fired             — most recent pair (ts, domains, axes)
      active_domains              — how many domains have seeds in scope
      tick_period_seconds         — how often it runs

    The Trainer worker (when it exists) reads this to retarget the
    swarm. The brain UI reads this to render the Connector's signature.
    """
    import time as _time
    stats = dict(_connector_stats)  # shallow copy
    stats["now"] = _time.time()
    if stats["last_tick_at"]:
        stats["seconds_since_tick"] = round(stats["now"] - stats["last_tick_at"], 1)
    if stats["started_at"]:
        stats["uptime_seconds"] = round(stats["now"] - stats["started_at"], 1)
    return stats


# ─────────────────────────────────────────────────────────────────────
# Trainer worker — second species, meta-agent
#
# Watches the swarm and the journal. Computes which domains are
# starving (no recent packet), which are well-fed, and writes a
# coordination config that future Searchers and Janitors will read
# to decide what to harvest or clean.
#
# Lazy: no background thread. /swarm/trainer triggers recompute when
# the cache is stale (>10 min). Cheap: walks at most 500 journal
# entries, counts by domain. Tiny.
# ─────────────────────────────────────────────────────────────────────

def _trainer_compute_analysis() -> Dict[str, Any]:
    """One Trainer tick. Walks journal, computes per-domain freshness,
    decides starving/well-fed, writes swarm_config.json.

    Returns the analysis payload. Side effect: writes the config file
    to disk so other (future) agents can read it without going through
    the API.
    """
    import time as _time
    now = _time.time()

    # Per-domain last-seen + count
    domain_counts: Dict[str, int] = {d: 0 for d in _ALL_DOMAINS}
    domain_last_seen: Dict[str, float] = {}

    try:
        from concordance_engine.journal import JournalStore
        store = JournalStore()
        entries = store.list_all(limit=500)
    except Exception as exc:
        entries = []
        _log.warning(f"trainer journal scan failed: {exc}")

    for entry in entries:
        # Detect domain from tags or metadata
        tags = getattr(entry, "user_tags", None) or []
        domain = next((t for t in tags if t in domain_counts), None)
        if not domain:
            meta = getattr(entry, "metadata", None) or {}
            if isinstance(meta, dict):
                domain = meta.get("domain")
                if domain not in domain_counts:
                    domain = None
        if not domain:
            continue
        domain_counts[domain] += 1
        ts = getattr(entry, "created_epoch", None) or getattr(entry, "ts", None)
        if isinstance(ts, (int, float)):
            prev = domain_last_seen.get(domain, 0)
            if ts > prev:
                domain_last_seen[domain] = ts

    # Starvation thresholds
    STARVE_HOURS = 24.0      # no entry in 24h = starving
    OVERFED_PCT = 0.10       # domain with >10% of all observed entries = over-served
    HOURS = 3600.0
    starving = []
    well_fed = []
    overfed = []
    total_observed = sum(domain_counts.values())
    for d in _ALL_DOMAINS:
        last = domain_last_seen.get(d)
        count = domain_counts[d]
        if last is None or (now - last) > STARVE_HOURS * HOURS:
            starving.append({"domain": d, "count": count, "last_seen": last})
        elif total_observed > 0 and count / total_observed > OVERFED_PCT:
            overfed.append({"domain": d, "count": count, "share": round(count/total_observed, 3)})
        else:
            well_fed.append({"domain": d, "count": count})

    # Sort starving by count ASC, last_seen ASC (oldest, then never-fed)
    starving.sort(key=lambda r: (r["count"], r["last_seen"] or 0))

    # Connector health snapshot
    connector_alive = bool(
        _connector_stats.get("last_tick_at")
        and (now - _connector_stats["last_tick_at"]) < 180
    )

    # Swarm-health verdict
    if not entries:
        verdict = "idle"
    elif len(starving) > 30:
        verdict = "thirsty"      # most domains have no recent harvest
    elif not connector_alive:
        verdict = "degraded"     # connector stopped
    elif len(starving) > 15:
        verdict = "uneven"
    else:
        verdict = "healthy"

    # Read Janitor's per-domain trust mix to find LLM-saturated domains
    # — these are the ones where the tasked dispatcher should fly first.
    janitor_tiers = _janitor_stats.get("by_domain_tiers") or {}
    high_llm: List[Dict[str, Any]] = []
    for dom, tier_map in janitor_tiers.items():
        if dom not in _ALL_DOMAINS:
            continue
        total = sum((tier_map or {}).values())
        if total < _TRAINER_AUTO_MIN_SAMPLE:
            continue
        tier5 = tier_map.get("5", 0)
        share = tier5 / total if total else 0
        if share >= _TRAINER_AUTO_LLM_THRESHOLD:
            high_llm.append({
                "domain": dom,
                "total_seen": total,
                "llm_count": tier5,
                "llm_share": round(share, 3),
            })
    high_llm.sort(key=lambda r: -r["llm_share"])

    # Auto-dispatch tasked dispatchers — closes the diagnostic loop. Each domain
    # gets at most one auto-dispatch per cooldown window. Tasked dispatcher
    # tasks queue at high priority so they jump human dispatches.
    auto_dispatched_this_tick: List[Dict[str, Any]] = []
    for d in high_llm:
        if len(auto_dispatched_this_tick) >= _TRAINER_AUTO_PER_TICK_CAP:
            break
        dom = d["domain"]
        last = _trainer_state["auto_dispatched"].get(dom, 0)
        if (now - last) < _TRAINER_AUTO_COOLDOWN_S:
            continue
        try:
            import uuid as _uuid
            task = {
                "task_id": "trainer_" + _uuid.uuid4().hex[:8],
                "domain": dom,
                "query": _LOC_DOMAIN_TO_QUERY.get(dom, dom.replace("_", " ")),
                "source": "loc",
                "priority": 5,   # higher than human dispatches (default 0)
                "requested_by": "trainer:auto",
                "notes": (
                    f"trust mix {int(d['llm_share']*100)}% LLM "
                    f"(tier 5: {d['llm_count']}/{d['total_seen']})"
                ),
                "queued_at": now,
            }
            with _dispatch_lock:
                # priority=5 inserts at front of queue
                _dispatch_queue.appendleft(task)
                _dispatch_stats["tasks_queued_total"] += 1
            _trainer_state["auto_dispatched"][dom] = now
            _trainer_state["auto_dispatch_total"] += 1
            _trainer_save_persisted_state()  # survive a bounce
            auto_dispatched_this_tick.append({
                "domain": dom,
                "ts": now,
                "task_id": task["task_id"],
                "llm_share": d["llm_share"],
                "total_seen": d["total_seen"],
            })
        except Exception as exc:
            _log.warning(f"trainer auto-dispatch failed for {dom}: {exc}")

    analysis = {
        "computed_at": now,
        "ttl_seconds": _TRAINER_TTL_SECONDS,
        "next_refresh_at": now + _TRAINER_TTL_SECONDS,
        "swarm_health": verdict,
        "journal_scan_size": len(entries),
        "total_classified": total_observed,
        "domains_starving": [r["domain"] for r in starving[:20]],
        "domains_overfed":  [r["domain"] for r in overfed],
        "domains_well_fed_count": len(well_fed),
        "starving_detail": starving[:20],
        "overfed_detail": overfed,
        # Diagnostic loop signal — what Janitor flagged + what we did
        "high_llm_domains": high_llm[:15],
        "auto_dispatched_this_tick": auto_dispatched_this_tick,
        "auto_dispatched_total": _trainer_state["auto_dispatch_total"],
        "auto_dispatch_threshold": _TRAINER_AUTO_LLM_THRESHOLD,
        "auto_dispatch_cooldown_seconds": _TRAINER_AUTO_COOLDOWN_S,
        "connector": {
            "status": "alive" if connector_alive else "stale",
            "pairs_fired_total": _connector_stats.get("pairs_fired_total", 0),
            "last_tick_at": _connector_stats.get("last_tick_at"),
        },
        "recommendations": {
            # Future Searchers should target these domains first
            "searcher_priorities": [r["domain"] for r in starving[:10]],
            # Janitor should look at over-served domains for dedup opportunities
            "janitor_priorities": [r["domain"] for r in overfed],
            # Tasked dispatchers should harvest replacements for these LLM-saturated domains
            "courier_priorities": [r["domain"] for r in high_llm[:10]],
        },
    }

    # Write coordination file. Future agents read this directly.
    try:
        _SWARM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SWARM_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(analysis, fh, indent=2)
    except Exception as exc:
        _log.warning(f"trainer config write failed: {exc}")

    return analysis


class DispatchRequest(BaseModel):
    """Body for POST /swarm/searcher/dispatch."""
    domain: str
    query: Optional[str] = None
    source: str = "loc"
    priority: int = 0
    requested_by: Optional[str] = None
    notes: Optional[str] = None


@app.post("/swarm/searcher/dispatch", tags=["agents"])
def swarm_searcher_dispatch(request: Request, req: DispatchRequest):
    """Send the tasked Searcher (#3) to a specific target.

    The first two Searchers run autonomously. This one is dormant
    until something dispatches it. Use when:
      - a verifier mismatch needs fresh primary references,
      - Trainer detects a critical-starvation domain that needs
        prompt attention beyond the autonomous schedule,
      - an agent or human researcher asks for a specific harvest.

    Tasks queue in memory and drain at 15-second ticks (one task
    per tick). Each completion logs to /swarm/searcher/dispatch
    history; the harvest itself lands in the journal tagged with
    'dispatched' so it's distinguishable from autonomous catches.

    Body:
      domain        — engine domain to tag the harvest with (required)
      query         — optional override of the LoC search term
      source        — "loc" (default; only source supported today)
      priority      — higher numbers run sooner within the queue
      requested_by  — string identifying who asked (logged with harvest)
      notes         — free-form, surfaced in /dispatch GET history

    Returns: task_id, queue_position, queued_at.
    """
    _rate_check(request, "dispatch")
    import time as _time, uuid as _uuid
    domain = req.domain.strip()
    if not domain:
        raise HTTPException(status_code=400, detail="domain is required")
    src = (req.source or "loc").lower()
    if src != "loc":
        raise HTTPException(
            status_code=400,
            detail=f"source '{src}' not supported (use 'loc')",
        )

    task_id = "task_" + _uuid.uuid4().hex[:8]
    task = {
        "task_id": task_id,
        "domain": domain,
        "query": req.query,
        "source": src,
        "priority": int(req.priority or 0),
        "requested_by": req.requested_by,
        "notes": req.notes,
        "queued_at": _time.time(),
    }
    with _dispatch_lock:
        # Insert by priority (higher first) — simple O(n) for small queues.
        inserted = False
        for i, existing in enumerate(_dispatch_queue):
            if task["priority"] > existing.get("priority", 0):
                _dispatch_queue.insert(i, task)
                inserted = True
                break
        if not inserted:
            _dispatch_queue.append(task)
        _dispatch_stats["tasks_queued_total"] += 1
        position = list(_dispatch_queue).index(task) + 1

    return {
        "task_id": task_id,
        "queued_at": task["queued_at"],
        "queue_position": position,
        "queue_depth": len(_dispatch_queue),
    }


@app.get("/swarm/searcher/dispatch", tags=["agents"])
def swarm_searcher_dispatch_status():
    """Live state of the tasked Searcher: queue, recent history, stats.

    Useful for: watching what's being asked of the swarm, debugging
    a stuck task, or auditing who's been asking for what.
    """
    import time as _time
    now = _time.time()
    with _dispatch_lock:
        queue_snapshot = list(_dispatch_queue)
        history_snapshot = list(_dispatch_history)

    out = {
        "stats": dict(_dispatch_stats),
        "queue_depth": len(queue_snapshot),
        "queue": queue_snapshot[:20],
        "recent": history_snapshot[:20],
        "now": now,
    }
    if _dispatch_stats["last_tick_at"]:
        out["seconds_since_tick"] = round(now - _dispatch_stats["last_tick_at"], 1)
    if _dispatch_stats["started_at"]:
        out["uptime_seconds"] = round(now - _dispatch_stats["started_at"], 1)
    return out


@app.get("/swarm/searcher/loc", tags=["agents"])
def swarm_searcher_loc():
    """Live stats for the Library of Congress harvester (Searcher #2).

    Reads Trainer's recommendations to target the most starving
    domain, queries LoC's catalog filtered to public-domain rights,
    and posts one new bibliographic record per tick (5 min).

    Each harvest carries authoritative provenance: title, date,
    contributors, controlled-vocabulary subjects, LCCN/URL, and
    rights status — the antidote to crowdsourced encyclopedias.
    """
    import time as _time
    now = _time.time()
    out = dict(_loc_stats)
    # Hide the in-memory dedup set from JSON output
    out["harvested_count_session"] = len(_loc_state["harvested_loc_ids"])
    out["last_target_domain"] = _loc_state["last_target_domain"]
    out["last_query"] = _loc_state["last_query"]
    out["now"] = now
    if out["last_tick_at"]:
        out["seconds_since_tick"] = round(now - out["last_tick_at"], 1)
    if out["started_at"]:
        out["uptime_seconds"] = round(now - out["started_at"], 1)
    return out


@app.get("/swarm/janitor", tags=["agents"])
def swarm_janitor():
    """Live stats for the Janitor worker.

    Janitor walks the journal scoring every packet on completeness
    (text present, length sane, has tags) and appropriateness
    (recognized domain, source attribution valid, identifiable trust
    tier). Findings flow here for Trainer to consume — Janitor never
    deletes anything; the journal is append-only.

    Returns aggregate stats by trust tier and finding category, the
    most recent finding, and the running review counter.
    """
    import time as _time
    now = _time.time()
    out = dict(_janitor_stats)
    # Sort by_category and by_domain for stable rendering
    out["by_category"] = dict(sorted(
        _janitor_stats["by_category"].items(),
        key=lambda kv: -kv[1],
    ))
    out["by_domain_top"] = dict(sorted(
        _janitor_stats["by_domain"].items(),
        key=lambda kv: -kv[1],
    )[:15])
    out["full_scan_complete"] = _janitor_state.get("full_scan_complete", False)
    out["seen_count"] = len(_janitor_seen)
    out["now"] = now
    if out["last_tick_at"]:
        out["seconds_since_tick"] = round(now - out["last_tick_at"], 1)
    if out["started_at"]:
        out["uptime_seconds"] = round(now - out["started_at"], 1)
    return out


@app.get("/swarm/janitor/archive", tags=["agents"])
def swarm_janitor_archive():
    """Journal archive eligibility view.

    Computes which domains have Tier-5 (LLM-synthesized) entries that
    are now eligible for archival because the same domain also has
    Tier 1 (locked) or Tier 2 (LoC) entries — i.e., authoritative
    replacements have been harvested. The journal stays append-only;
    this view exposes what *could* be moved to cold storage if/when
    the actual archive layer is built.

    Returns per-domain counts and a roll-up. Read-only.
    """
    eligible: List[Dict[str, Any]] = []
    total_t5_eligible = 0
    total_t5_protected = 0
    for dom, tiers in (_janitor_stats.get("by_domain_tiers") or {}).items():
        if dom == "unknown":
            continue
        t1 = tiers.get("1", 0)
        t2 = tiers.get("2", 0)
        t3 = tiers.get("3", 0)
        t4 = tiers.get("4", 0)
        t5 = tiers.get("5", 0)
        replacement = t1 + t2 + t3
        if t5 == 0:
            continue
        if replacement > 0:
            total_t5_eligible += t5
            eligible.append({
                "domain": dom,
                "t5_eligible": t5,
                "replacement_count": replacement,
                "tier_breakdown": {"1": t1, "2": t2, "3": t3, "4": t4, "5": t5},
                "replacement_share": round(replacement / (t5 + replacement), 3),
            })
        else:
            total_t5_protected += t5

    eligible.sort(key=lambda r: -r["t5_eligible"])

    return {
        "policy": (
            "An entry becomes archive-eligible when its domain has at "
            "least one Tier 1/2/3 (authoritative or curated) replacement. "
            "Tier 5 entries in domains with NO replacement remain "
            "protected — they're the only record of that domain's content."
        ),
        "domains_with_archive_eligible": len(eligible),
        "total_t5_eligible_for_archive": total_t5_eligible,
        "total_t5_protected_no_replacement": total_t5_protected,
        "domains": eligible[:50],
    }


@app.get("/swarm/janitor/findings", tags=["agents"])
def swarm_janitor_findings(
    category: Optional[str] = Query(None, description="Filter to one finding tag (e.g. LLM_SYNTHESIZED)"),
    domain: Optional[str] = Query(None, description="Filter to one domain"),
    tier: Optional[int] = Query(None, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent Janitor findings, optionally filtered.

    Useful for: pulling the LLM_SYNTHESIZED list to dispatch
    replacement dispatch jobs; auditing UNRECOGNIZED_DOMAIN
    entries for tagging fixes; spot-checking malformed packets.
    """
    out = []
    for f in list(_janitor_findings):
        if category and category not in f.get("findings", []):
            continue
        if domain and f.get("domain") != domain:
            continue
        if tier is not None and f.get("trust_tier") != tier:
            continue
        out.append(f)
        if len(out) >= limit:
            break
    return {"count": len(out), "findings": out}


@app.get("/swarm/searcher", tags=["agents"])
def swarm_searcher():
    """Live stats for the Searcher worker.

    The Searcher walks a curated list of canonical scripture anchors,
    resolving each via the local WEB Bible module and posting it to
    the journal as a real harvested packet. One verse per ~90s tick.
    Genuinely public domain. No external HTTP, no LLM, no synthesis.

    After completing one full pass through the anchor list, sleeps 6
    hours then cycles again. The rate is deliberately gentle.

    Returns identity, tick stats, last harvest, current cursor
    position in the anchor list, and rest state.
    """
    import time as _time
    now = _time.time()
    out = dict(_searcher_stats)
    out["now"] = now
    out["cursor"] = _searcher_state["cursor"]
    out["cycles_completed"] = _searcher_state["cycles_completed"]
    out["in_rest"] = _searcher_state["in_rest"]
    if _searcher_state["in_rest"]:
        out["rest_seconds_remaining"] = max(
            0, round(_searcher_state["rest_until"] - now)
        )
    if out["last_tick_at"]:
        out["seconds_since_tick"] = round(now - out["last_tick_at"], 1)
    if out["started_at"]:
        out["uptime_seconds"] = round(now - out["started_at"], 1)
    return out


@app.get("/swarm/trainer", tags=["agents"])
def swarm_trainer(refresh: bool = Query(False, description="Force recompute now")):
    """Live stats for the Trainer worker.

    The Trainer watches the swarm and the journal every 10 minutes.
    It identifies which of the 63 domains are starving (no recent
    packets) and which are well-fed, then writes data/swarm_config.json
    so future Searchers know what to harvest first.

    Lazy: this endpoint computes on demand if the cache is stale.
    Pass ?refresh=true to force a recompute (modest cost — walks
    the journal up to 500 entries).

    The brain UI reads this to render Trainer's signature; future
    Searcher and Janitor workers read /swarm/trainer/config to
    decide their work.
    """
    import time as _time
    now = _time.time()

    needs_refresh = (
        refresh
        or _trainer_state["analysis"] is None
        or (_trainer_state["computed_at"]
            and now - _trainer_state["computed_at"] > _TRAINER_TTL_SECONDS)
    )

    if needs_refresh:
        try:
            _trainer_state["analysis"] = _trainer_compute_analysis()
            _trainer_state["computed_at"] = now
            _trainer_state["tick_count"] += 1
        except Exception as exc:
            _trainer_state["error_count"] += 1
            _trainer_state["last_error"] = str(exc)[:200]

    out = {
        "name": "trainer",
        "species": "Trainer",
        "role": "watch drop counts, retarget Searchers toward starving domains",
        "tick_count": _trainer_state["tick_count"],
        "error_count": _trainer_state["error_count"],
        "last_error": _trainer_state["last_error"],
        "computed_at": _trainer_state["computed_at"],
        "now": now,
        "analysis": _trainer_state["analysis"] or {},
        "config_path": str(_SWARM_CONFIG_PATH),
    }
    if _trainer_state["computed_at"]:
        out["seconds_since_compute"] = round(now - _trainer_state["computed_at"], 1)
    return out


@app.get("/swarm/trainer/config", tags=["agents"])
def swarm_trainer_config():
    """Just the swarm coordination config — what other agents read.

    Returns the analysis payload directly (no Trainer metadata).
    Future Searchers call this to learn which domains to prioritize;
    Janitors call this to learn which to dedup. Equivalent to reading
    the on-disk data/swarm_config.json file directly.
    """
    import time as _time
    now = _time.time()
    if (_trainer_state["analysis"] is None
            or (_trainer_state["computed_at"]
                and now - _trainer_state["computed_at"] > _TRAINER_TTL_SECONDS)):
        _trainer_state["analysis"] = _trainer_compute_analysis()
        _trainer_state["computed_at"] = now
        _trainer_state["tick_count"] += 1
    return _trainer_state["analysis"] or {}


@app.get("/swarm", tags=["agents"])
def swarm_index():
    """Roster of all worker agents — current and planned.

    Returns each species's status. The brain UI uses this to render
    swarm panels; the Trainer reads it to know what's available to
    coordinate.
    """
    import time as _time
    now = _time.time()
    connector_alive = bool(
        _connector_stats.get("last_tick_at")
        and (now - _connector_stats["last_tick_at"]) < 180
    )
    trainer_fresh = bool(
        _trainer_state["computed_at"]
        and (now - _trainer_state["computed_at"]) < _TRAINER_TTL_SECONDS * 1.5
    )
    trainer_health = (
        (_trainer_state["analysis"] or {}).get("swarm_health", "—")
        if _trainer_state["analysis"] else "—"
    )

    return {
        "swarm": [
            {
                "name": "connector",
                "species": "Connector",
                "role": "find cross-domain edges along shared scaffold axes",
                "status": "alive" if connector_alive else "stale",
                "stats_endpoint": "/swarm/connector",
                "pairs_fired_total": _connector_stats.get("pairs_fired_total", 0),
                "last_tick_at": _connector_stats.get("last_tick_at"),
            },
            {
                "name": "trainer",
                "species": "Trainer",
                "role": "watch drop counts, retarget Searchers toward starving domains",
                "status": "alive" if trainer_fresh else (
                    "cold" if _trainer_state["analysis"] is None else "stale"
                ),
                "stats_endpoint": "/swarm/trainer",
                "config_endpoint": "/swarm/trainer/config",
                "swarm_health": trainer_health,
                "tick_count": _trainer_state["tick_count"],
                "computed_at": _trainer_state["computed_at"],
            },
            {
                "name": "searcher",
                "species": "Searcher · Scripture",
                "role": "harvest one canonical anchor per tick (WEB Bible)",
                "status": (
                    "alive" if (
                        _searcher_stats.get("last_tick_at")
                        and (now - _searcher_stats["last_tick_at"]) < 240
                    )
                    else ("resting" if _searcher_state["in_rest"] else (
                        "warming" if _searcher_stats.get("started_at") else "cold"
                    ))
                ),
                "stats_endpoint": "/swarm/searcher",
                "harvests_total": _searcher_stats.get("harvests_total", 0),
                "cycles_completed": _searcher_state["cycles_completed"],
                "current_source": _searcher_stats.get("current_source"),
                "last_tick_at": _searcher_stats.get("last_tick_at"),
            },
            {
                "name": "searcher_loc",
                "species": "Searcher · LoC",
                "role": "harvest one Library of Congress catalog record per tick",
                "status": (
                    "alive" if (
                        _loc_stats.get("last_tick_at")
                        and (now - _loc_stats["last_tick_at"]) < 600
                    )
                    else ("warming" if _loc_stats.get("started_at") else "cold")
                ),
                "stats_endpoint": "/swarm/searcher/loc",
                "harvests_total": _loc_stats.get("harvests_total", 0),
                "current_source": _loc_stats.get("current_source"),
                "last_tick_at": _loc_stats.get("last_tick_at"),
            },
            {
                "name": "searcher_dispatch",
                "species": "Searcher · Tasked",
                "role": "dormant by default; flies on dispatch",
                "status": (
                    "busy" if _dispatch_stats.get("current_task") else
                    "alive" if (
                        _dispatch_stats.get("last_tick_at")
                        and (now - _dispatch_stats["last_tick_at"]) < 60
                    ) else ("warming" if _dispatch_stats.get("started_at") else "cold")
                ),
                "stats_endpoint": "/swarm/searcher/dispatch",
                "queue_depth": len(_dispatch_queue),
                "tasks_completed": _dispatch_stats.get("tasks_completed", 0),
                "tasks_failed": _dispatch_stats.get("tasks_failed", 0),
                "last_tick_at": _dispatch_stats.get("last_tick_at"),
            },
            {
                "name": "janitor",
                "species": "Janitor",
                "role": "verify packet completeness and appropriateness",
                "status": (
                    "alive" if (
                        _janitor_stats.get("last_tick_at")
                        and (now - _janitor_stats["last_tick_at"]) < 240
                    ) else ("warming" if _janitor_stats.get("started_at") else "cold")
                ),
                "stats_endpoint": "/swarm/janitor",
                "entries_reviewed": _janitor_stats.get("entries_reviewed", 0),
                "entries_with_findings": _janitor_stats.get("entries_with_findings", 0),
                "full_scan_complete": _janitor_state.get("full_scan_complete", False),
                "last_tick_at": _janitor_stats.get("last_tick_at"),
            },
            {
                "name": "synthesist",
                "species": "Synthesist",
                "role": "discover 3+ domain clusters that share a scaffold axis",
                "status": (
                    "alive" if (
                        _synthesist_stats.get("last_tick_at")
                        and (now - _synthesist_stats["last_tick_at"]) < 240
                    ) else ("warming" if _synthesist_stats.get("started_at") else "cold")
                ),
                "stats_endpoint": "/swarm/synthesist",
                "patterns_total": _synthesist_stats.get("patterns_total", 0),
                "deepest_pattern": _synthesist_stats.get("deepest_pattern"),
                "entries_scanned": _synthesist_stats.get("entries_scanned", 0),
                "last_tick_at": _synthesist_stats.get("last_tick_at"),
            },
            {
                "name": "miner",
                "species": "Miner",
                "role": "extract candidate Almanac entries from a corpus of EPUBs",
                "status": (
                    "alive" if (
                        _miner_stats.get("last_tick_at")
                        and (now - _miner_stats["last_tick_at"]) < 360
                    ) else ("warming" if _miner_stats.get("started_at") else "cold")
                ),
                "stats_endpoint": "/swarm/miner",
                "candidates_total": _miner_stats.get("candidates_total", 0),
                "passages_seen_total": _miner_stats.get("passages_seen_total", 0),
                "books_in_corpus": _miner_stats.get("books_in_corpus", 0),
                "last_book": _miner_stats.get("last_book"),
                "last_tick_at": _miner_stats.get("last_tick_at"),
            },
        ],
        "now": now,
    }


@app.get("/grid/connections/stream", tags=["agents"])
def grid_connections_stream():
    """Server-Sent Events stream of cross-domain connection events.

    Subscribe once; receive events as the background keeper discovers them.
    Each event is a JSON object with:
      domain_a, domain_b — the two connected domains
      shared_axes        — which scaffold dimensions they share
      axis_count         — how many shared axes (higher = deeper connection)
      sample_a, sample_b — representative seed text from each domain
      ts                 — Unix epoch when the connection was first detected

    For agents: subscribe at startup to receive live pattern notifications.
    """
    import time as _time
    from fastapi.responses import StreamingResponse as _SR

    def _generate():
        last_size = 0
        while True:
            if _GRID_CONNECTIONS_FILE.exists():
                lines = _GRID_CONNECTIONS_FILE.read_text(
                    "utf-8", errors="replace"
                ).splitlines()
                if len(lines) > last_size:
                    for line in lines[last_size:]:
                        if line.strip():
                            yield f"data: {line}\n\n"
                    last_size = len(lines)
            _time.sleep(5)

    return _SR(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# Wire the /health snapshot refresher. 30s ticks. /health serves from
# this snapshot and never walks stores in the request path.
_health_refresh_thread = _threading.Thread(
    target=_health_refresh_worker,
    name="health-refresh",
    daemon=True,
)
_health_refresh_thread.start()

# Wire the background connector into the startup lifecycle.
# It fires once on the first scan, then every 60 seconds.
_connector_thread = _threading.Thread(
    target=_grid_connector_worker,
    name="grid-connector",
    daemon=True,
)
_connector_thread.start()

# Wire the Searcher worker (Searcher #1: scripture anchors).
# Slow on purpose — 90s per harvest, full anchor cycle ~75 min,
# then sleeps 6 hours before cycling again. Gentle, patient.
_searcher_thread = _threading.Thread(
    target=_searcher_worker,
    name="searcher-scripture",
    daemon=True,
)
_searcher_thread.start()

# Wire the LoC harvester (Searcher #2: Library of Congress catalog).
# 5-min ticks, polite to LoC, public-domain rights filter only.
# Targets the most starving domain per Trainer's recommendations.
_loc_searcher_thread = _threading.Thread(
    target=_loc_searcher_worker,
    name="searcher-loc",
    daemon=True,
)
_loc_searcher_thread.start()

# Wire the Tasked Dispatcher (Searcher #3). Dormant until
# something POSTs to /swarm/searcher/dispatch. 15s drain ticks.
_dispatch_thread = _threading.Thread(
    target=_dispatch_worker,
    name="searcher-dispatch",
    daemon=True,
)
_dispatch_thread.start()

# Wire the Janitor (steward). 90s ticks. First tick walks the full
# journal to score historical entries; subsequent ticks just catch
# new arrivals. Quiet, methodical, never deletes.
_janitor_thread = _threading.Thread(
    target=_janitor_worker,
    name="janitor",
    daemon=True,
)
_janitor_thread.start()

# Wire the Synthesist (polymathic-pattern keeper). 90s ticks. Walks the
# journal looking for 3+ domain co-occurrences that share a scaffold
# axis — the structural seed of a polymathic query. Patterns logged to
# data/synthesis_patterns.jsonl and exposed via /swarm/synthesist so
# polymathic precedent lookups stay warm.
_synthesist_thread = _threading.Thread(
    target=_synthesist_worker,
    name="synthesist",
    daemon=True,
)
_synthesist_thread.start()

# Wire the Miner (corpus → almanac-candidate keeper). 180s ticks.
# Walks an EPUB corpus (default: ~/OneDrive/Desktop, override via
# CONCORDANCE_MINER_CORPUS) one book per tick, scoring passages
# against axis stems + engine concepts. Strong candidates land in
# data/miner/candidates.jsonl for curator review. Append-only;
# never auto-publishes to the Almanac.
_miner_thread = _threading.Thread(
    target=_miner_worker,
    name="miner",
    daemon=True,
)
_miner_thread.start()


# -- MCP over HTTP/SSE — remote agent door ------------------------------
# Mount the FastMCP server at /mcp so any MCP-compliant agent (Claude
# Desktop with remote MCP, Cursor, custom clients) can connect to
# https://narrowhighway.com/mcp without installing anything locally.
# Two transports exposed:
#   /mcp       — streamable HTTP (newer, recommended)
#   /mcp/sse   — SSE (older, broader client compatibility)
# stdio remains the local transport for `concordance-mcp` CLI users.
#
# ── Trailing-slash redirects ──
# Starlette mounts match only /mcp/<path>, so a request to bare /mcp
# (no slash) hits no route and returns 405. Many MCP clients normalise
# URLs by stripping trailing slashes, so we add explicit 308 redirects
# from /mcp → /mcp/ and /mcp/sse → /mcp/sse/. 308 preserves the request
# method and body, which is required because real MCP traffic is POST.
# Registered before the mounts so they take precedence.
from fastapi.responses import RedirectResponse as _MCPRedirect

@app.api_route("/mcp", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
async def _mcp_no_slash_redirect(request: Request):
    target = "/mcp/"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return _MCPRedirect(target, status_code=308)

@app.api_route("/mcp/sse", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
async def _mcp_sse_no_slash_redirect(request: Request):
    target = "/mcp/sse/"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return _MCPRedirect(target, status_code=308)

try:
    from concordance_engine.mcp_server.server import mcp as _mcp_server
    # Normalize internal route paths so external URLs are clean.
    # FastMCP defaults: streamable_http_path=/mcp, sse_path=/sse.
    # Mounted at external /mcp this would produce /mcp/mcp etc. Setting
    # the sub-app routes to "/" makes them resolve at the mount root.
    _mcp_server.settings.streamable_http_path = "/"
    _mcp_server.settings.sse_path = "/"
    # Allow remote MCP clients to connect through Cloudflare.
    # FastMCP defaults to localhost-only DNS rebinding protection.
    # We're public, so expand the host/origin allowlist to include
    # the production domain. Keep localhost in there for direct
    # /docs and dev-test access.
    _mcp_server.settings.transport_security.allowed_hosts = [
        "narrowhighway.com",
        "narrowhighway.com:*",
        "*.narrowhighway.com",
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
    ]
    _mcp_server.settings.transport_security.allowed_origins = [
        "https://narrowhighway.com",
        "https://*.narrowhighway.com",
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]
    _sse = _mcp_server.sse_app()
    _http = _mcp_server.streamable_http_app()
    app.mount("/mcp/sse", _sse, name="mcp_sse")
    app.mount("/mcp", _http, name="mcp_http")

    # CRITICAL: FastMCP's StreamableHTTPSessionManager needs an async
    # task group to handle requests. Sub-app lifespans aren't run by
    # the parent's lifecycle automatically, so we wire it explicitly.
    # Without this, every POST /mcp raises:
    #   RuntimeError: Task group is not initialized. Make sure to use run().
    from contextlib import asynccontextmanager as _amctx
    @_amctx
    async def _mcp_combined_lifespan(_app):
        async with _mcp_server.session_manager.run():
            yield
    app.router.lifespan_context = _mcp_combined_lifespan

    print("[MCP] mounted /mcp and /mcp/sse — FastMCP transports active", flush=True)
    print("[MCP] session manager wired into FastAPI lifespan", flush=True)
    _log.info("MCP HTTP/SSE transports mounted at /mcp and /mcp/sse "
              "(internal paths '/'; session manager active)")
except Exception as _mcp_mount_err:
    # Don't take down the API if MCP mount fails — surface the error
    # via three channels (print + _log + getLogger) so we definitely
    # see it in server.log regardless of logger config.
    import traceback as _traceback
    _err_text = f"{type(_mcp_mount_err).__name__}: {_mcp_mount_err}"
    _tb = _traceback.format_exc()
    print(f"[MCP] mount FAILED — {_err_text}", flush=True)
    print(_tb, flush=True)
    try:
        _log.error(f"MCP HTTP mount failed: {_err_text}")
        _log.error(_tb)
    except Exception:
        pass


# -- Static site (must be last — catches all unmatched paths) ------------
# Serves site/ for all HTML pages, CSS, JS, icons, manifests, etc.
# API routes registered above take priority; this handles everything else.
_SITE_DIR = Path(__file__).parent.parent / "site"
if _SITE_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_SITE_DIR), html=True), name="site")
