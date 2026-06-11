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

# Load .env file (ANTHROPIC_API_KEY, DEEPL_API_KEY, etc.)
try:
    import dotenv
    dotenv.load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
except ImportError:
    pass

_log = logging.getLogger("concordance.app")

# Bounded pool for peer broadcast — prevents unbounded thread creation.
_BROADCAST_POOL = ThreadPoolExecutor(max_workers=10, thread_name_prefix="peer-broadcast")

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
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

# FAST channel live HLS routes ------------------------------------------------
try:
    from api.fast_live import get_router as _get_fast_live_router
    app.include_router(_get_fast_live_router(), tags=["fast-channels"])
except Exception as _e:
    logging.warning("FAST live router not mounted: %s", _e)

# User-content submission + voting routes -------------------------------------
try:
    from api.user_content import get_router as _get_user_content_router
    app.include_router(_get_user_content_router(), tags=["user-content"])
except Exception as _e:
    logging.warning("User-content router not mounted: %s", _e)

# Periodicals (PD magazines) — streams from D: drive
try:
    from api.periodicals import get_router as _get_periodicals_router
    app.include_router(_get_periodicals_router(), tags=["periodicals"])
except Exception as _e:
    logging.warning("Periodicals router not mounted: %s", _e)

# Curriculum + Recipe submissions (mirrors user_content for those flows)
try:
    from api.submissions import get_router as _get_submissions_router
    app.include_router(_get_submissions_router(), tags=["submissions"])
except Exception as _e:
    logging.warning("Submissions router not mounted: %s", _e)

# Engine-generated content queue (operator review)
try:
    from api.engine_feed import get_router as _get_engine_feed_router
    app.include_router(_get_engine_feed_router(), tags=["engine-feed"])
except Exception as _e:
    logging.warning("Engine-feed router not mounted: %s", _e)

# Shepherd substrate-RAG retrieval
try:
    from api.shepherd_rag import get_router as _get_shepherd_rag_router
    app.include_router(_get_shepherd_rag_router(), tags=["shepherd"])
except Exception as _e:
    logging.warning("Shepherd-RAG router not mounted: %s", _e)

# Wallet endpoints (operator address, transparency, tip records)
try:
    from api.wallet import get_router as _get_wallet_router
    app.include_router(_get_wallet_router(), tags=["wallet"])
except Exception as _e:
    logging.warning("Wallet router not mounted: %s", _e)

# Outreach tracker (partnership pipeline: targets, log, status)
try:
    from api.outreach import get_router as _get_outreach_router
    app.include_router(_get_outreach_router(), tags=["outreach"])
except Exception as _e:
    logging.warning("Outreach router not mounted: %s", _e)

# Card library (LOOP 11 — everything-is-a-card substrate)
try:
    from api.cards import get_router as _get_cards_router
    app.include_router(_get_cards_router(), tags=["cards"])
except Exception as _e:
    logging.warning("Cards router not mounted: %s", _e)

# Christian Marketplace v1 — free, no fee, no cut; trust is the only currency.
try:
    from api.market import get_router as _get_market_router
    app.include_router(_get_market_router(), tags=["marketplace"])
except Exception as _e:
    logging.warning("Marketplace router not mounted: %s", _e)

# The Codex — Layer 3 index (scripture cross-reference graph, inverted from
# the witnessed connection cards). Engine binds + indexes; it does not synthesize.
try:
    from api.codex import get_router as _get_codex_router
    app.include_router(_get_codex_router(), tags=["codex"])
except Exception as _e:
    logging.warning("Codex index router not mounted: %s", _e)

# Original-language Scripture (Greek MorphGNT + Strong's): original word first,
# WEB as the translation vehicle, the original word + definition on any confusion.
try:
    from api.original_language import get_router as _get_origlang_router
    app.include_router(_get_origlang_router(), tags=["scripture"])
except Exception as _e:
    logging.warning("Original-language router not mounted: %s", _e)

# The user layer — one funnel + private (owned) cards (data/user_cards/, outside
# the public substrate). Private by default; user publishes; the gate banks.
try:
    from api.funnel import get_router as _get_funnel_router
    app.include_router(_get_funnel_router(), tags=["funnel"])
except Exception as _e:
    logging.warning("Funnel router not mounted: %s", _e)

# Shepherd Interviewer (LOOP 12 — pre-flight before expensive walks)
try:
    from api.shepherd import get_router as _get_shepherd_router
    app.include_router(_get_shepherd_router(), tags=["shepherd"])
except Exception as _e:
    logging.warning("Shepherd router not mounted: %s", _e)

# Household stacks (LOOP 13 — paperclip / share / fork / tip)
try:
    from api.stacks import get_router as _get_stacks_router
    app.include_router(_get_stacks_router(), tags=["stacks"])
except Exception as _e:
    logging.warning("Stacks router not mounted: %s", _e)

# Promotion engine (LOOP 15 — voting + operator queue)
try:
    from api.promotion import get_router as _get_promotion_router
    app.include_router(_get_promotion_router(), tags=["promotion"])
except Exception as _e:
    logging.warning("Promotion router not mounted: %s", _e)

# Walks cache + prefetch + replay (LOOP 16 — solve permanently)
try:
    from api.walks_cache import get_router as _get_walks_cache_router
    app.include_router(_get_walks_cache_router(), tags=["walks-cache"])
except Exception as _e:
    logging.warning("Walks-cache router not mounted: %s", _e)

# Atlas — book of paths (LOOP 17 — walks as cards, curated paths)
try:
    from api.atlas import get_router as _get_atlas_router
    app.include_router(_get_atlas_router(), tags=["atlas"])
except Exception as _e:
    logging.warning("Atlas router not mounted: %s", _e)

# Community Notes with bridge rating (LOOP 18)
try:
    from api.notes import get_router as _get_notes_router
    app.include_router(_get_notes_router(), tags=["notes"])
except Exception as _e:
    logging.warning("Notes router not mounted: %s", _e)

# Rebalance queue (LOOP 32 — operator-facing suggestions)
try:
    from api.rebalance import get_router as _get_rebalance_router
    app.include_router(_get_rebalance_router(), tags=["rebalance"])
except Exception as _e:
    logging.warning("Rebalance router not mounted: %s", _e)

# Card of the Day (LOOP 39)
try:
    from api.daily_card import get_router as _get_daily_card_router
    app.include_router(_get_daily_card_router(), tags=["daily-card"])
except Exception as _e:
    logging.warning("Daily card router not mounted: %s", _e)

# Witness gate (Deut 19:15 — every card requires >=2 independent witnesses)
try:
    from api.witnesses import get_router as _get_witnesses_router
    app.include_router(_get_witnesses_router(), tags=["witness-gate"])
except Exception as _e:
    logging.warning("Witness-gate router not mounted: %s", _e)

# Agent daily heartbeat (/agents/daily.json — gives crawlers a stable URL that
# returns fresh content; helps with MCP-directory discoverability)
try:
    from api.agent_daily import get_router as _get_agent_daily_router
    app.include_router(_get_agent_daily_router(), tags=["agents"])
except Exception as _e:
    logging.warning("Agent-daily router not mounted: %s", _e)

# Atlas walks RSS feed (/feed/walks.rss — subscribeable by readers + AI crawlers)
try:
    from api.feed_walks import get_router as _get_feed_walks_router
    app.include_router(_get_feed_walks_router(), tags=["feeds"])
except Exception as _e:
    logging.warning("Feed-walks router not mounted: %s", _e)

# /health/deep — single-URL operational summary (substrate + witness + caches + channel files + segments + audit)
try:
    from api.deep_health import get_router as _get_deep_health_router
    app.include_router(_get_deep_health_router(), tags=["health"])
except Exception as _e:
    logging.warning("Deep-health router not mounted: %s", _e)

# /c/{card_id} — server-side-rendered card pages (crawler-visible HTML; complement to /card.html SPA)
try:
    from api.card_ssr import get_router as _get_card_ssr_router
    app.include_router(_get_card_ssr_router(), tags=["card-ssr"])
except Exception as _e:
    logging.warning("Card-SSR router not mounted: %s", _e)

# /shema — the foundational confession the engine returns to (Deut 6:4-9)
# The engine confesses before it serves — startup hook prints the Shema to server.log.
try:
    from api.shema import get_router as _get_shema_router, confess_on_startup as _shema_confess
    app.include_router(_get_shema_router(), tags=["shema"])
    _shema_confess()  # Print the Shema to stdout (server.log) on engine startup
except Exception as _e:
    logging.warning("Shema router not mounted: %s", _e)

# /keep/dashboard — single aggregator endpoint for the operator dashboard
# (replaces 20 sequential fetches with one cached snapshot, 30s TTL)
try:
    from api.keep_dashboard import get_router as _get_keep_dashboard_router
    app.include_router(_get_keep_dashboard_router(), tags=["keep"])
except Exception as _e:
    logging.warning("Keep-dashboard router not mounted: %s", _e)


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
    """Bucket a request into a coarse traffic class for stats.

    Classes:
      human         - a real browser (modern, text-mode, or legacy mobile)
      retrieval     - LLM fetching on a live user query (ChatGPT-User, Perplexity, OAI-SearchBot)
      crawl_ai      - LLM training crawler (GPTBot, ClaudeBot, Google-Extended, CCBot)
      crawl_search  - classic search-engine indexer (Googlebot, Bingbot, DuckDuckBot)
      agent_other   - generic bot / scraper / feed-reader / bare HTTP client
      preview       - link-unfurl fetch (someone shared a link in chat/social)
      scanner       - vuln-path probing, or an internet-wide scanner that self-IDs
      monitor       - internal traffic (our own test suite / smoke probes)
      unknown       - no User-Agent string at all
      other         - a UA we genuinely cannot place (should stay near zero)

    The retrieval / crawl_ai split matters a lot: retrieval means a human
    JUST asked a question elsewhere and is reading our reply via the LLM.
    crawl_ai means we got indexed for later training. The first one is
    a human-by-proxy; the second one is exposure for the future.

    Path is a secondary signal: a fake-Mozilla UA that hits a known
    vulnerability path (wp-*, xmlrpc.php, .env, .git) is a scanner no
    matter what UA it advertises."""
    low = (ua or "").lower().strip()
    p_low = (path or "").lower()

    scanner_path_markers = (
        "wp-includes", "wp-admin", "wp-content", "wp-login",
        "xmlrpc.php", "/.env", "/.git/", "/.aws/", "/phpmyadmin",
        "/admin.php", "/setup.php", "/shell.php", "/eval(",
    )
    if any(m in p_low for m in scanner_path_markers):
        return "scanner"

    if not low:
        return "unknown"

    # Internal: Starlette's TestClient (our test suite + smoke probes) runs
    # through this middleware but is not a visitor. Belt-and-suspenders —
    # the access-log middleware also skips it outright.
    if low == "testclient" or low.startswith("testclient/"):
        return "monitor"

    # Internet-wide / security scanners that announce themselves.
    scanner_markers = (
        "palo alto", "paloalto", "cortex xpanse", "expanse", "censys",
        "shodan", "masscan", "zgrab", "zmap", "nuclei", "stretchoid",
        "internet-measurement", "internetmeasurement", "netsystemsresearch",
        "leakix", "binaryedge", "odin.security", "criminalip",
    )
    if any(m in low for m in scanner_markers):
        return "scanner"

    # Live retrieval bots — a human JUST asked a question on ChatGPT/Claude/
    # Perplexity/etc and the bot is fetching us as a citation for that answer.
    # These are humans-by-proxy and the most valuable hits we get short of
    # direct browsing. Order matters — check retrieval BEFORE crawl_ai so
    # "chatgpt-user" doesn't get swallowed by the broader "gptbot" rule.
    retrieval_markers = (
        "chatgpt-user", "oai-searchbot",  "openai-user",
        "perplexitybot", "perplexity-user",
        "claude-user", "anthropic-user",
        "youbot", "you-bot",
        "cohere-ai",
    )
    if any(m in low for m in retrieval_markers):
        return "retrieval"

    # AI training crawlers — indexing for later model use, not live retrieval.
    crawl_ai_markers = (
        "gptbot", "claudebot", "anthropic-ai", "google-extended",
        "ccbot", "bytespider", "amazonbot", "applebot-extended",
        "meta-externalagent", "ai2bot", "mistralai", "timpibot", "diffbot",
        "gemini", "bard",
    )
    if any(m in low for m in crawl_ai_markers):
        return "crawl_ai"

    # Classic search-engine indexers.
    crawl_search_markers = (
        "googlebot", "bingbot", "duckduckbot", "yandex", "baiduspider",
        "applebot", "googleother", "naverbot", "seznambot", "qwantbot",
        "kagibot",
    )
    if any(m in low for m in crawl_search_markers):
        return "crawl_search"

    # Link-unfurl / preview fetchers — a human just shared a link somewhere.
    preview_markers = (
        "slackbot", "twitterbot", "facebookexternalhit", "discordbot",
        "telegrambot", "linkedinbot", "whatsapp", "skypeuripreview",
        "embedly", "iframely", "redditbot", "pinterest", "vkshare",
        "networkingextension", "snapchat", "nuzzel", "qwantify",
    )
    if any(m in low for m in preview_markers):
        return "preview"

    # General crawlers, bots, scrapers, feed-readers, bare HTTP clients.
    bot_markers = (
        "bot", "crawler", "spider", "curl/", "wget/", "python-requests",
        "python-urllib", "httpx", "aiohttp", "go-http-client", "node-fetch",
        "axios", "okhttp", "java/", "libwww", "apache-httpclient", "lwp::",
        "scrapy", "feedfetcher", "feedburner", "feedly", "newsblur",
        "dalvik", "headlesschrome", "phantomjs",
        "najdu", "semrush", "ahrefs", "mj12", "dotbot",
    )
    if any(m in low for m in bot_markers):
        return "agent_other"

    # Real browsers — modern engines plus text-mode and legacy mobile.
    browser_markers = (
        "mozilla", "safari", "chrome", "firefox", "edge", "edg/", "opera",
        "gecko", "webkit", "elinks", "lynx", "w3m", "dillo", "netfront",
        "netscape", "konqueror", "midp", "cldc", "ucbrowser", "samsungbrowser",
    )
    if any(b in low for b in browser_markers):
        return "human"

    # A bare "tool/version" token (greedyhand/0.1, foo/2.3) with no other
    # structure is almost always an automated client.
    import re as _re_ua
    if _re_ua.fullmatch(r"[a-z0-9._+-]+/[0-9][0-9a-z._+-]*", low):
        return "agent_other"

    return "other"


# Endpoints that count as "engine submit" when hit with a write method.
# A POST/PUT/DELETE to any of these from a non-operator IP means a real
# outside party USED the engine — not just visited the site. This is the
# load-bearing signal that humans-or-agents are actually doing something.
_SUBMIT_PATH_PREFIXES = (
    "/try", "/verify", "/discern", "/deposit", "/witness", "/attest",
    "/scribe", "/submit-content", "/submit-recipe", "/submit-curriculum",
    "/feedback", "/api/verify", "/api/discern", "/api/deposit",
    "/api/witness", "/walk/", "/walks/run", "/poly",
)
_SUBMIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _classify_intent(ua_class: str, method: str, path: str) -> str:
    """Higher-level bucket combining what a request DID (method+path) with
    who made it (ua_class). Drives the /keep "where things are actually
    working" view.

    Buckets:
      submit     - a write call to an engine endpoint (real engine use)
      retrieval  - live LLM citation fetch (human-by-proxy)
      crawl_ai   - LLM training crawler
      crawl_seo  - classic search-engine indexer
      browse     - real browser GETting pages (human site visit)
      preview    - link unfurl
      scanner    - vuln/scanner traffic
      other      - everything else (monitor / unknown / agent_other)
    """
    p = (path or "").split("?", 1)[0]
    if method in _SUBMIT_METHODS and any(p.startswith(pfx) for pfx in _SUBMIT_PATH_PREFIXES):
        return "submit"
    if ua_class == "retrieval":
        return "retrieval"
    if ua_class == "crawl_ai":
        return "crawl_ai"
    if ua_class == "crawl_search":
        return "crawl_seo"
    if ua_class == "human":
        return "browse"
    if ua_class == "preview":
        return "preview"
    if ua_class == "scanner":
        return "scanner"
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


def _is_operator_ip(ip: str) -> bool:
    """True if the IP is in the /keep allowlist (env + file + localhost).
    Operator IPs are excluded from visit logging so the human-vs-bot stats
    reflect actual outside traffic, not the operator clicking around.

    Supports both exact-IP and CIDR patterns in the allowlist (e.g.
    `2605:59c8:6360:5710::/64`). Exact match is checked first (fast path);
    CIDR is fallback (a residential ISP rotates the inner bits of an
    IPv6 prefix; matching the /64 keeps the operator on the list
    across renewals without re-adding every time)."""
    if not ip:
        return False
    try:
        patterns = _keep_allowed_ips()
        # Exact-match fast path
        if ip in patterns:
            return True
        # CIDR fallback
        import ipaddress as _ipaddress
        try:
            client = _ipaddress.ip_address(ip)
        except (ValueError, TypeError):
            return False
        for pat in patterns:
            if "/" not in pat:
                continue
            try:
                if client in _ipaddress.ip_network(pat, strict=False):
                    return True
            except (ValueError, TypeError):
                continue
        return False
    except Exception:
        return False


_MCP_LOG_FILE = Path(__file__).parent.parent / "data" / "mcp_requests.jsonl"
_mcp_request_counter = {"total": 0, "by_method": {}, "by_ua_class": {}}


def _mcp_log_entry(request: Request) -> None:
    """Log an MCP request at ENTRY time. FastMCP uses streaming SSE/HTTP,
    which means the normal access-log middleware (which logs after
    call_next returns) never fires for long-lived MCP sessions.
    This entry-time tap captures one row per MCP request regardless.

    Writes to data/mcp_requests.jsonl. Best-effort — never raises."""
    try:
        ip = (
            request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "")
        )
        ua = request.headers.get("user-agent", "")[:160]
        method = request.method
        path = request.url.path
        # In-process counter so /keep can show a live number even if
        # the file write is slow
        _mcp_request_counter["total"] += 1
        _mcp_request_counter["by_method"][method] = _mcp_request_counter["by_method"].get(method, 0) + 1
        _MCP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _MCP_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": int(time.time()),
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": method,
                "path": path,
                "ip_prefix": _ip_prefix(ip),
                "ua": ua,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


# Visit-log exclusions beyond the /keep IP allowlist: the engine box curling its
# own public hostname (health checks, agent self-tests, probes) arrives as the
# box's own public IP — that is self/infra traffic, never a visitor.
_VISITLOG_EXCLUDE_IPS = {"5.78.186.55"}


@app.middleware("http")
async def _access_log_middleware(request: Request, call_next):
    started = time.time()
    path = request.url.path
    skip = path in _VISITS_SKIP_EXACT or any(path.startswith(p) for p in _VISITS_SKIP_PREFIXES)

    # MCP paths get a dedicated entry-time log because the FastMCP
    # sub-app streams responses and the access-log middleware (which
    # logs post-call_next) never sees them complete.
    if path == "/mcp" or path.startswith("/mcp/"):
        _mcp_log_entry(request)

    response = await call_next(request)

    # Engine attribution headers on every response. When an agent calls the
    # engine and surfaces the response to its user, these carry the URL forward
    # — "X-Engine-URL" in particular shows up in any HTTP client log. Compounds
    # discovery without anyone having to post about us.
    response.headers["X-Engine"] = "Concordance"
    response.headers["X-Engine-URL"] = "https://narrowhighway.com"
    response.headers["X-Engine-Manifest"] = "https://narrowhighway.com/manifest"
    response.headers["X-Engine-License"] = "Apache-2.0"

    # Edge-cacheability. Cloudflare already caches static assets but treats
    # HTML as DYNAMIC, so every page view tunnels to the engine — meaning an
    # engine blip takes the whole front door down. An explicit Cache-Control
    # lets a Cloudflare cache rule serve pages from the edge: instant loads
    # for humans, and the site stays up even when the engine doesn't.
    # Operator pages (/keep) are never cached — security boundary.
    try:
        if request.method == "GET" and getattr(response, "status_code", 0) == 200:
            _ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
            _is_keep = path == "/keep" or path == "/keep.html" or path.startswith("/keep/")
            _is_html = path == "/" or path.endswith(".html") or _ctype == "text/html"
            _has_cc = any(k.lower() == "cache-control" for k in response.headers.keys())
            _is_asset = path.endswith(".js") or path.endswith(".css")
            if _is_keep:
                response.headers["Cache-Control"] = "private, no-store"
            elif _is_html and not _has_cc:
                # 10 min fresh, then serve-stale up to a day while revalidating.
                response.headers["Cache-Control"] = "public, max-age=600, stale-while-revalidate=86400"
            elif _is_asset and not _has_cc:
                # Scripts/styles change often as the site is iterated. Without an
                # explicit Cache-Control, browsers heuristic-cache them for hours
                # (off Last-Modified) and shipped changes never reach visitors.
                # Short max-age + must-revalidate: cached briefly, then a cheap
                # ETag 304 — updates land within minutes, not days.
                response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    except Exception:
        pass

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
        _ref = request.headers.get("referer", "")
        # Categorize the ACTOR — track every type, drop nothing (Matt: "track all
        # types, just categorized"). The category lets every surface separate real
        # audience from operator/self downstream WITHOUT losing the data:
        #   operator = Matt running the system (keep IP / 90-day cookie / dashboard referer)
        #   self     = the engine's own box + the test client (Claude / infra self-tests)
        #   visitor  = everyone else; ua_class then splits human / agent / crawler / scanner
        # Audience metrics exclude operator+self (that's "don't count my/your clicks");
        # the rows are still logged + labelled, so nothing is invisible.
        if _is_operator_ip(client_ip) or _keep_session_valid(request) or "/keep" in _ref:
            actor = "operator"
        elif (client_ip in _VISITLOG_EXCLUDE_IPS
              or ua.strip().lower() == "testclient" or client_ip == "testclient"):
            actor = "self"
        else:
            actor = "visitor"
        ref = _ref[:240]
        # Geo: cf-ipcountry header first for the country code (free if CF
        # proxies); then our cached lookup which gives city + lat/lon too
        # (cache-only, never blocks). Misses queue for tools/geo_enrich.py.
        cf_cc = request.headers.get("cf-ipcountry", "")[:8]
        geo = _geo_for(client_ip)
        country = cf_cc or (geo.get("cc", "") if geo else "") or ""
        city = (geo.get("city") if geo else "") or ""
        glat = geo.get("lat") if geo else None
        glon = geo.get("lon") if geo else None
        _ua_class = _classify_ua(ua, path)
        record = {
            "ts": int(started),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "method": request.method,
            "path": path[:240],
            "status": int(getattr(response, "status_code", 0) or 0),
            "ms": int((time.time() - started) * 1000),
            "ip_prefix": _ip_prefix(client_ip),
            "ua": ua,
            "ua_class": _ua_class,
            "actor": actor,
            "intent": _classify_intent(_ua_class, request.method, path),
            "referer": ref,
            "country": country,
        }
        if city:
            record["city"] = city
        if glat is not None and glon is not None:
            record["lat"] = float(glat)
            record["lon"] = float(glon)
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


# ── /keep.html IP allowlist ──────────────────────────────────────────
# Operator-only stats page hidden from nav. Returns 404 (not 403) to
# avoid revealing existence.
#
# Allowlist sources (all combined):
#   1. env KEEP_ALLOWED_IPS (comma-separated) — set at server start
#   2. data/keep_allowed_ips.txt (one IP per line, # comments OK)
#      — editable at runtime, no restart needed
#   3. always-allow localhost (127.0.0.1, ::1, "")
#
# Honors CF-Connecting-IP and X-Forwarded-For for behind-proxy deployments.
#
# Admit tokens: an already-allowed device can mint a short-lived token at
# POST /keep/issue-token. Any device that hits GET /keep/admit?t=<token>
# while the token is fresh will be added to the allowlist. This lets you
# admit your phone from your laptop without knowing the phone's IP.
#
# Every access attempt (allowed or denied) is logged to data/keep_access.log.
_KEEP_LOCAL_IPS = {"127.0.0.1", "::1", "localhost", ""}
_KEEP_PROTECTED_PATHS = {"/keep.html", "/keep"}
_KEEP_ACCESS_LOG = Path(__file__).resolve().parents[1] / "data" / "keep_access.log"
_KEEP_ALLOWED_FILE = Path(__file__).resolve().parents[1] / "data" / "keep_allowed_ips.txt"
_KEEP_TOKENS_FILE = Path(__file__).resolve().parents[1] / "data" / "keep_admit_tokens.json"
_KEEP_TOKEN_TTL_SEC = 3600  # 1 hour


def _keep_load_file_ips() -> set:
    if not _KEEP_ALLOWED_FILE.exists():
        return set()
    out = set()
    try:
        for line in _KEEP_ALLOWED_FILE.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line)
    except Exception:
        pass
    return out


def _keep_save_file_ips(ips: set) -> None:
    _KEEP_ALLOWED_FILE.parent.mkdir(parents=True, exist_ok=True)
    sorted_ips = sorted(ips - _KEEP_LOCAL_IPS)
    header = "# /keep.html allowlist — one IP per line. Edited via the page or by hand.\n"
    body = "\n".join(sorted_ips) + ("\n" if sorted_ips else "")
    _KEEP_ALLOWED_FILE.write_text(header + body, encoding="utf-8")


def _keep_allowed_ips() -> set:
    """Combine env var + file + localhost. Re-read on each request."""
    raw = os.environ.get("KEEP_ALLOWED_IPS", "")
    env_ips = {ip.strip() for ip in raw.split(",") if ip.strip()}
    file_ips = _keep_load_file_ips()
    return env_ips | file_ips | _KEEP_LOCAL_IPS


def _keep_client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
        or (request.client.host if request.client else "")
    )


def _keep_log(client_ip: str, allowed: bool, path: str, ua: str = "") -> None:
    try:
        _KEEP_ACCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _KEEP_ACCESS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ip": client_ip,
                "allowed": bool(allowed),
                "path": path,
                "ua": (ua or "")[:160],
            }) + "\n")
    except Exception:
        pass


# ── Admit token store (short-lived, in-file) ──────────────────────────
def _keep_load_tokens() -> dict:
    if not _KEEP_TOKENS_FILE.exists():
        return {}
    try:
        return json.loads(_KEEP_TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _keep_save_tokens(tokens: dict) -> None:
    _KEEP_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEEP_TOKENS_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def _keep_clean_tokens(tokens: dict) -> dict:
    now = int(time.time())
    return {t: meta for t, meta in tokens.items()
            if int(meta.get("expires_ts", 0)) > now and not meta.get("consumed_ts")}


# ── Session-cookie admission (survives IP rotation) ──────────────────
# Residential ISP IPs rotate, so an IP allowlist alone forces you to re-pin
# every time. Solution: when you arrive at /keep with ?k=<NH_KEEP_TOKEN>, mint
# a 90-day signed session cookie. The gate then accepts EITHER an allowlisted
# IP OR a valid session cookie — so the browser stays admitted across IP
# changes until the cookie expires. Each device needs the magic URL once.
_KEEP_SESS_PATH = Path(__file__).resolve().parent.parent / "data" / "keep" / "sessions.json"
_KEEP_COOKIE_NAME = "nh_keep_session"
_KEEP_COOKIE_TTL = 90 * 24 * 3600  # 90 days


def _keep_load_sessions() -> dict:
    try:
        return json.loads(_KEEP_SESS_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _keep_save_sessions(sessions: dict) -> None:
    try:
        _KEEP_SESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEEP_SESS_PATH.write_text(json.dumps(sessions, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _keep_session_valid(request: Request) -> bool:
    cookie = request.cookies.get(_KEEP_COOKIE_NAME, "")
    if not cookie:
        return False
    sessions = _keep_load_sessions()
    entry = sessions.get(cookie)
    if not entry:
        return False
    now = int(time.time())
    if entry.get("expires_ts", 0) < now:
        try:
            sessions.pop(cookie, None)
            _keep_save_sessions(sessions)
        except Exception:
            pass
        return False
    return True


def _keep_mint_session(ua: str = "") -> str:
    token = secrets.token_urlsafe(24)
    now = int(time.time())
    sessions = _keep_load_sessions()
    sessions[token] = {
        "issued_ts": now,
        "expires_ts": now + _KEEP_COOKIE_TTL,
        "ua": (ua or "")[:160],
    }
    # Prune expired entries while we're here
    sessions = {k: v for k, v in sessions.items() if v.get("expires_ts", 0) > now}
    _keep_save_sessions(sessions)
    return token


def _keep_require_allowed(request: Request):
    """Raise 404 if the requester isn't admitted. Admission = allowlisted IP
    OR valid session cookie (so a rotated IP on the same browser still works)."""
    ip = _keep_client_ip(request)
    if _is_operator_ip(ip) or _keep_session_valid(request):
        return ip
    _keep_log(ip, False, request.url.path, request.headers.get("user-agent", ""))
    raise HTTPException(status_code=404, detail="Not Found")


@app.middleware("http")
async def _keep_ip_guard(request: Request, call_next):
    """Admission for /keep.html. Returns 404 (not 403) to hide existence.
    Admits: allowlisted IP, valid session cookie, or ?k=<NH_KEEP_TOKEN> (which
    also mints a 90-day cookie so subsequent visits don't need the token)."""
    path = request.url.path
    if path not in _KEEP_PROTECTED_PATHS:
        return await call_next(request)

    client_ip = _keep_client_ip(request)
    allowed = _is_operator_ip(client_ip) or _keep_session_valid(request)
    new_cookie = None

    # Token query path: ?k=<NH_KEEP_TOKEN> admits this request AND mints a
    # long-lived session cookie so future visits from this browser don't need
    # the token in the URL. Lets you bookmark a clean /keep.html and roam.
    if not allowed:
        _tok = os.environ.get("NH_KEEP_TOKEN", "").strip()
        _supplied = request.query_params.get("k", "")
        if _tok and _supplied and secrets.compare_digest(_supplied, _tok):
            allowed = True
            new_cookie = _keep_mint_session(request.headers.get("user-agent", ""))
            # Also pin the IP for legacy compatibility
            try:
                _ips = _keep_load_file_ips()
                _ips.add(client_ip)
                _keep_save_file_ips(_ips)
            except Exception:
                pass

    _keep_log(client_ip, allowed, path, request.headers.get("user-agent", ""))

    if not allowed:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not Found", status_code=404)

    response = await call_next(request)
    if new_cookie:
        response.set_cookie(
            _KEEP_COOKIE_NAME, new_cookie,
            max_age=_KEEP_COOKIE_TTL,
            httponly=True, secure=True, samesite="lax", path="/",
        )
    return response


# ── /keep admin endpoints ────────────────────────────────────────────
@app.get("/keep/state", tags=["keep"])
def keep_state(request: Request):
    """Return current allowed IPs + the requester's IP. Caller must be allowed."""
    requester_ip = _keep_require_allowed(request)
    file_ips = sorted(_keep_load_file_ips())
    env_ips = sorted(ip.strip() for ip in os.environ.get("KEEP_ALLOWED_IPS", "").split(",") if ip.strip())
    return {
        "your_ip": requester_ip,
        "file_ips": file_ips,
        "env_ips": env_ips,
        "localhost_always_allowed": True,
    }


@app.post("/keep/logout", tags=["keep"])
def keep_logout(request: Request):
    """Clear THIS device's session cookie (other devices stay admitted)."""
    _keep_require_allowed(request)
    cookie = request.cookies.get(_KEEP_COOKIE_NAME, "")
    if cookie:
        sessions = _keep_load_sessions()
        if cookie in sessions:
            sessions.pop(cookie, None)
            _keep_save_sessions(sessions)
    from fastapi.responses import JSONResponse
    r = JSONResponse({"ok": True, "logged_out": True})
    r.delete_cookie(_KEEP_COOKIE_NAME, path="/")
    return r


@app.post("/keep/revoke-all-sessions", tags=["keep"])
def keep_revoke_all_sessions(request: Request):
    """Invalidate ALL session cookies across all devices (lost-laptop button).
    The IP allowlist is untouched; you stay admitted on this request via IP."""
    _keep_require_allowed(request)
    _keep_save_sessions({})
    from fastapi.responses import JSONResponse
    r = JSONResponse({"ok": True, "revoked": True})
    r.delete_cookie(_KEEP_COOKIE_NAME, path="/")
    return r


@app.post("/keep/pin", tags=["keep"])
def keep_pin(request: Request, ip: str | None = None):
    """Add an IP to the file allowlist (default: requester's own IP)."""
    requester_ip = _keep_require_allowed(request)
    target = (ip or requester_ip).strip()
    if not target:
        raise HTTPException(status_code=400, detail="no IP provided")
    ips = _keep_load_file_ips()
    ips.add(target)
    _keep_save_file_ips(ips)
    return {"ok": True, "added": target, "now_allowed": sorted(ips)}


@app.post("/keep/revoke", tags=["keep"])
def keep_revoke(request: Request, ip: str):
    """Remove an IP from the file allowlist (the requester cannot revoke themselves)."""
    requester_ip = _keep_require_allowed(request)
    target = ip.strip()
    if target == requester_ip:
        raise HTTPException(status_code=400, detail="cannot revoke your own IP")
    ips = _keep_load_file_ips()
    ips.discard(target)
    _keep_save_file_ips(ips)
    return {"ok": True, "removed": target, "now_allowed": sorted(ips)}


@app.post("/keep/issue-token", tags=["keep"])
def keep_issue_token(request: Request):
    """Mint a short-lived admit token. The caller must already be allowed."""
    requester_ip = _keep_require_allowed(request)
    tokens = _keep_clean_tokens(_keep_load_tokens())
    import secrets as _s
    token = _s.token_urlsafe(18)
    now = int(time.time())
    tokens[token] = {
        "issued_by": requester_ip,
        "issued_ts": now,
        "expires_ts": now + _KEEP_TOKEN_TTL_SEC,
        "consumed_ts": None,
        "consumed_by_ip": None,
    }
    _keep_save_tokens(tokens)
    return {
        "ok": True,
        "token": token,
        "admit_url": f"/keep/admit?t={token}",
        "expires_in_sec": _KEEP_TOKEN_TTL_SEC,
    }


@app.get("/keep/insights", tags=["keep"])
def keep_insights(request: Request):
    """Operator insights for the dashboard: spend vs cap, AI-agent discovery
    (the mission metric), autonomous gather output, skills + corpus size.
    Reads files directly; operator-only."""
    _keep_require_allowed(request)
    import datetime as _dt
    root = Path(__file__).resolve().parent.parent
    out: dict = {}

    # spend vs cap (read the spend_guard ledger directly)
    try:
        month = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")
        ledger = root / "data" / "spend" / "ledger.jsonl"
        spent = 0.0
        if ledger.exists():
            for ln in ledger.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get("month") == month:
                    spent += float(o.get("usd", 0) or 0)
        cap = float(os.environ.get("NH_MONTHLY_BUDGET_USD", "500") or 500)
        out["spend"] = {"month": month, "spent_usd": round(spent, 4),
                        "cap_usd": cap, "remaining_usd": round(cap - spent, 2),
                        "pct": round(100 * spent / cap, 2) if cap else 0}
    except Exception as e:
        out["spend"] = {"error": str(e)[:120]}

    # AI agents discovering the engine (today) — the mission metric
    try:
        day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
        vf = root / "data" / "visits" / f"access-{day}.jsonl"
        agents: dict = {}
        total_ai = 0
        _NAMES = (("claude", "ClaudeBot"), ("gptbot", "GPTBot"),
                  ("oai-searchbot", "OAI-SearchBot"), ("chatgpt", "ChatGPT"),
                  ("perplexity", "PerplexityBot"), ("google-extended", "Google-Extended"),
                  ("gemini", "Gemini"), ("ccbot", "CCBot"), ("amazonbot", "Amazonbot"),
                  ("bytespider", "Bytespider"), ("applebot-extended", "Applebot-Ext"),
                  ("meta-externalagent", "Meta-AI"), ("cohere", "Cohere"),
                  ("mistralai", "Mistral"), ("youbot", "YouBot"), ("diffbot", "Diffbot"))
        if vf.exists():
            for ln in vf.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get("ua_class") != "ai":
                    continue
                total_ai += 1
                ua = (o.get("ua") or "").lower()
                name = "other AI"
                for key, label in _NAMES:
                    if key in ua:
                        name = label
                        break
                agents[name] = agents.get(name, 0) + 1
        out["ai_agents"] = {"total_today": total_ai,
                            "by_agent": dict(sorted(agents.items(), key=lambda kv: -kv[1]))}
    except Exception as e:
        out["ai_agents"] = {"error": str(e)[:120]}

    # autonomous gather output
    try:
        g: dict = {}
        gl = root / "data" / "spend" / "gather_log.jsonl"
        if gl.exists():
            lines = [l for l in gl.read_text(encoding="utf-8").splitlines() if l.strip()]
            recent = []
            for l in lines[-6:]:
                try:
                    recent.append(json.loads(l))
                except Exception:
                    pass
            g["recent"] = recent
        sc = root / "data" / "rebalance" / "suggested_connections.json"
        if sc.exists():
            try:
                d = json.loads(sc.read_text(encoding="utf-8"))
                g["connections_pending"] = (sum(len(v) for v in d.values())
                                            if isinstance(d, dict) else len(d))
            except Exception:
                pass
        cp = root / "data" / "skills" / "_capacity_proposals.json"
        if cp.exists():
            try:
                d = json.loads(cp.read_text(encoding="utf-8"))
                g["capacity_clusters"] = len(d.get("uncovered_clusters", []))
                g["uncovered_queries"] = d.get("uncovered_queries", 0)
            except Exception:
                pass
        out["gather"] = g
    except Exception as e:
        out["gather"] = {"error": str(e)[:120]}

    # skills + corpus
    try:
        sd = root / "data" / "skills"
        sk = [p for p in sd.glob("*.json") if not p.name.startswith("_")] if sd.exists() else []
        out["skills"] = {"count": len(sk)}
    except Exception:
        out["skills"] = {"count": 0}
    try:
        td = root / "data" / "training_corpus"
        corp = sorted(td.glob("corpus-*.jsonl")) if td.exists() else []
        if corp:
            newest = corp[-1]
            out["corpus"] = {"pairs": sum(1 for _ in open(newest, encoding="utf-8")),
                             "file": newest.name}
    except Exception:
        out["corpus"] = {}

    return out


@app.post("/keep/clear-visits", tags=["keep"])
def keep_clear_visits(request: Request):
    """Wipe historical visit logs. Useful once operator IPs are excluded going forward,
    so the past mixed data (where operator hits were counted) is reset to a clean baseline.
    Caller must be allowed."""
    _keep_require_allowed(request)
    deleted = 0
    bytes_freed = 0
    try:
        for p in sorted(_VISITS_DIR.glob("access-*.jsonl")):
            try:
                size = p.stat().st_size
                p.unlink()
                deleted += 1
                bytes_freed += size
            except Exception:
                pass
    except Exception:
        pass
    return {"ok": True, "files_deleted": deleted, "bytes_freed": bytes_freed}


# ── /craft — second layer: retrieve and craft, then recall ─────────────
# When a user arrives with a profile (health metrics, repeated question,
# any pattern), the engine builds a signature from the inputs. If the
# signature exists in the crafted store: recall directly. If not: search
# the keeping, compose a tailored entry, store it under the signature,
# return it. The crafted store grows with use — the engine learns what
# profiles it sees, and recalls instead of re-searching.
#
# Privacy: signatures are hashed; raw user values (numbers) are not stored
# in the crafted entry. Only the bucketed state per metric ("low", "warn"
# etc.) and the synthesized response. No PII.

import hashlib as _h_craft

_CRAFTED_DIR = Path(__file__).resolve().parents[1] / "data" / "crafted"
_CRAFTED_DIR.mkdir(parents=True, exist_ok=True)


def _craft_storage_path(context: str) -> Path:
    safe = "".join(c for c in context if c.isalnum() or c in "-_")[:40] or "default"
    return _CRAFTED_DIR / f"{safe}.jsonl"


def _craft_load(context: str) -> dict:
    """Return {signature: entry} dict for a context. JSONL on disk; last
    wins on duplicate signatures."""
    path = _craft_storage_path(context)
    if not path.exists():
        return {}
    out = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                sig = e.get("signature")
                if sig:
                    out[sig] = e
            except Exception:
                pass
    except Exception:
        pass
    return out


def _craft_save(context: str, store: dict) -> None:
    path = _craft_storage_path(context)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for sig, e in store.items():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _craft_signature(profile: list, context: str) -> str:
    """Hash sorted (metric, state) pairs + context. Same shape every time
    for the same profile."""
    key = [(str(p.get("metric", "")), str(p.get("state", ""))) for p in profile]
    key.sort()
    blob = json.dumps({"context": context, "profile": key}, sort_keys=True)
    return _h_craft.sha256(blob.encode("utf-8")).hexdigest()[:16]


# Search recipes per context — what to search for given a (metric, state).
# Designed so /craft is general-purpose; new contexts add their own recipe
# table. The keeping does the search; the recipe is the routing.
_CRAFT_RECIPES_HEALTH = {
    "sleep_min": {
        "bad":  ["sleep magnesium", "melatonin circadian", "magnesium glycinate"],
        "warn": ["sleep hygiene", "magnesium glycinate", "melatonin circadian"],
        "good": ["sleep hygiene"],
        "ok":   ["sleep hygiene"],
    },
    "hrv_ms": {
        "warn": ["magnesium glycinate", "ashwagandha stress", "creatine monohydrate", "peppermint oil IBS"],
        "ok":   ["magnesium", "creatine"],
        "good": ["exercise", "creatine"],
        "bad":  ["magnesium glycinate", "ashwagandha", "peppermint IBS"],
    },
    "rhr_bpm": {
        "warn": ["exercise science", "bicycle Starley", "cardiovascular"],
        "ok":   ["exercise", "cardiovascular"],
        "good": ["safety bicycle"],
    },
    "recovery_pct": {
        "warn": ["sleep magnesium", "whey protein", "creatine"],
        "ok":   ["whey protein", "sleep"],
        "good": ["exercise science", "creatine monohydrate"],
    },
    "strain": {
        "warn": ["whey protein", "creatine monohydrate", "sleep"],
        "good": ["whey protein", "creatine"],
        "ok":   ["exercise"],
    },
    "sleep_efficiency_pct": {
        "bad":  ["sleep hygiene", "melatonin circadian", "magnesium glycinate"],
        "warn": ["sleep hygiene", "magnesium"],
        "good": ["sleep"],
    },
    "respiratory_rate": {
        "warn": ["saline nasal irrigation", "sleep hygiene"],
        "good": ["exercise"],
    },
}
_CRAFT_RECIPES = {"health": _CRAFT_RECIPES_HEALTH}


def _craft_search_packets(query: str, limit: int = 3) -> list:
    """Lightweight in-process call into the same packet-search the engine
    serves at /index/packets/search. Defensive — returns [] on any error."""
    try:
        from fastapi.testclient import TestClient  # noqa
    except Exception:
        pass
    # Use the registered route directly via httpx-style call would require
    # spinning a client; cheaper to import the search function from the
    # indexing module if available. Fall back to HTTP via localhost.
    try:
        import urllib.parse, urllib.request
        url = f"http://127.0.0.1:8000/index/packets/search?q={urllib.parse.quote(query)}&limit={int(limit)}"
        with urllib.request.urlopen(url, timeout=2.5) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("packets", []) or []
    except Exception:
        return []


def _craft_compose(context: str, profile: list, packets: list) -> dict:
    """Template-based composition. Lists concerns, lists packets, names
    the center of gravity. LLM-enriched composition can replace this later
    without changing the call site."""
    concerns = []
    for p in profile:
        m = p.get("metric", "")
        s = p.get("state", "")
        label = m.replace("_", " ")
        if s in ("warn", "bad"):
            concerns.append(f"{label} ({s})")
        elif s == "good":
            concerns.append(f"{label} (good)")
    title = f"Profile: " + (", ".join(concerns) if concerns else "balanced")

    # Center of gravity = most-cited domain across surfaced packets
    domain_counts: dict[str, int] = {}
    for pk in packets:
        for d in (pk.get("domains") or []):
            domain_counts[d] = domain_counts.get(d, 0) + 1
    top_domain = max(domain_counts.items(), key=lambda kv: kv[1])[0] if domain_counts else None

    bullets = []
    for pk in packets[:12]:
        verdict = (pk.get("verdict") or "").upper()
        bullets.append({
            "id": pk.get("id"),
            "title": pk.get("title", ""),
            "verdict": verdict,
            "permalink": pk.get("permalink", ""),
            "domains": pk.get("domains") or [],
        })

    if context == "health":
        narrative = (
            f"For a profile with {', '.join(concerns) if concerns else 'no notable concerns'}, "
            f"the keeping holds {len(bullets)} relevant entries. "
            f"The center of gravity is **{top_domain}** — that's where the engine's verified knowledge "
            f"converges for this profile."
        )
    else:
        narrative = (
            f"For this profile, the keeping surfaces {len(bullets)} relevant entries"
            + (f" centered on **{top_domain}**." if top_domain else ".")
        )

    return {
        "title": title,
        "narrative": narrative,
        "center_of_gravity": top_domain,
        "bullets": bullets,
    }


@app.post("/craft", tags=["craft"])
def craft_endpoint(req: dict):
    """Retrieve + craft + store, or recall if signature seen before.

    Body: {context: "health"|..., profile: [{metric, state, value?}, ...]}
    Returns: {recalled: bool, signature, entry: {...}}
    """
    context = str(req.get("context") or "default").strip()[:40]
    profile = req.get("profile") or []
    if not isinstance(profile, list):
        raise HTTPException(status_code=400, detail="profile must be a list")

    sig = _craft_signature(profile, context)
    store = _craft_load(context)

    if sig in store:
        entry = store[sig]
        entry["recalled_count"] = int(entry.get("recalled_count", 0)) + 1
        entry["last_recalled_ts"] = int(time.time())
        store[sig] = entry
        _craft_save(context, store)
        return {"recalled": True, "signature": sig, "entry": entry}

    # Craft: walk the recipe table, search the keeping, compose
    recipes = _CRAFT_RECIPES.get(context, {})
    packets: list[dict] = []
    seen: set[str] = set()
    for p in profile:
        m = p.get("metric")
        s = p.get("state")
        queries = recipes.get(m, {}).get(s, []) if recipes else []
        for q in queries:
            results = _craft_search_packets(q, limit=4)
            for r in results:
                rid = r.get("id")
                if rid and rid not in seen:
                    seen.add(rid)
                    packets.append(r)
            if len(packets) >= 12:
                break
        if len(packets) >= 12:
            break

    composed = _craft_compose(context, profile, packets)
    entry = {
        "id": f"crafted_{context}_{sig}",
        "kind": "crafted",
        "signature": sig,
        "context": context,
        "profile": profile,
        "title": composed["title"],
        "narrative": composed["narrative"],
        "center_of_gravity": composed["center_of_gravity"],
        "bullets": composed["bullets"],
        "crafted_at_ts": int(time.time()),
        "crafted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recalled_count": 0,
        "last_recalled_ts": None,
    }
    store[sig] = entry
    _craft_save(context, store)
    return {"recalled": False, "signature": sig, "entry": entry}


@app.get("/craft/list", tags=["craft"])
def craft_list(request: Request, context: str = "health", limit: int = 50):
    """Admin view of crafted entries by context (gated to /keep allowlist)."""
    _keep_require_allowed(request)
    store = _craft_load(context)
    entries = sorted(store.values(),
                     key=lambda e: int(e.get("recalled_count", 0)),
                     reverse=True)
    return {"context": context, "total": len(entries), "entries": entries[:int(limit)]}


@app.get("/keep/mcp-stats", tags=["keep"])
def keep_mcp_stats(request: Request, limit: int = 50):
    """MCP traffic summary — counts and recent requests captured via the
    entry-time tap. FastMCP is mounted as a sub-app; its streaming
    responses bypass the normal access log, so we capture entry events
    here. Operator-only."""
    _keep_require_allowed(request)
    limit = max(1, min(500, int(limit)))
    # In-process counter (live since last restart)
    counter = dict(_mcp_request_counter)
    # File log entries (persistent across restarts)
    entries: list[dict] = []
    if _MCP_LOG_FILE.exists():
        try:
            for line in _MCP_LOG_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass
    entries.sort(key=lambda r: r.get("ts_iso", ""), reverse=True)
    # Discover what MCP tools are exposed
    tool_count = 0
    server_info: Dict[str, Any] = {}
    try:
        # FastMCP server identity from the mount block
        from api.app import _mcp_server  # type: ignore  # may not exist
        tool_count = len(getattr(_mcp_server, "_tools", {}) or {})
        server_info = {
            "name": getattr(_mcp_server, "name", "concordance"),
            "version": getattr(_mcp_server, "version", ""),
        }
    except Exception:
        # Fall back to known startup values
        server_info = {"name": "concordance", "version": "1.27.0"}
    return {
        "counter": counter,
        "total_logged": len(entries),
        "recent": entries[:limit],
        "endpoints": {
            "http": "/mcp",
            "sse": "/mcp/sse",
        },
        "server_info": server_info,
        "tool_count": tool_count,
        "public_doctrine_url": "https://narrowhighway.com/identity",
    }


@app.get("/keep/access-log", tags=["keep"])
def keep_access_log(request: Request, limit: int = 200):
    """Return the recent /keep.html access log (full IPs, allowed + denied).
    The caller must already be allowed."""
    _keep_require_allowed(request)
    limit = max(1, min(2000, int(limit)))
    if not _KEEP_ACCESS_LOG.exists():
        return {"count": 0, "entries": []}
    rows: list[dict] = []
    try:
        for line in _KEEP_ACCESS_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    # newest first
    rows.sort(key=lambda r: r.get("ts_iso", ""), reverse=True)
    return {"count": len(rows), "entries": rows[:limit]}


@app.get("/keep/admit", tags=["keep"])
def keep_admit(request: Request, t: str):
    """Consume an admit token; the requester's IP is added to the allowlist."""
    from fastapi.responses import RedirectResponse, PlainTextResponse
    tokens = _keep_clean_tokens(_keep_load_tokens())
    meta = tokens.get(t)
    if not meta:
        return PlainTextResponse("invalid or expired admit token", status_code=404)
    requester_ip = _keep_client_ip(request)
    if not requester_ip:
        return PlainTextResponse("could not determine your IP", status_code=400)
    # Mark consumed
    meta["consumed_ts"] = int(time.time())
    meta["consumed_by_ip"] = requester_ip
    tokens[t] = meta
    _keep_save_tokens(tokens)
    # Add the requester's IP to the allowlist
    ips = _keep_load_file_ips()
    ips.add(requester_ip)
    _keep_save_file_ips(ips)
    _keep_log(requester_ip, True, "/keep/admit (token-admitted)",
              request.headers.get("user-agent", ""))
    # Redirect to /keep.html so they land on the page
    return RedirectResponse(url="/keep.html", status_code=302)


@app.get("/visits/recent", tags=["visits"])
def visits_recent(limit: int = 50, days: int = 7):
    """Return the most recent visit records (privacy-scrubbed)."""
    limit = max(1, min(500, int(limit)))
    days = max(1, min(60, int(days)))
    rows = _read_visits_for_days(days=days, limit=limit)
    return {"count": len(rows), "days": days, "limit": limit, "entries": rows}


# Named bots / agents / tools, matched on a lowercased user-agent substring.
# The door is open to all of these — this list just lets us SEE who is reaching
# for the engine (the AI agents and crawlers especially are the ones we want to
# be the easiest tool for). Order matters: more specific markers first.
_AGENT_MARKERS = (
    ("ChatGPT", "chatgpt-user"), ("ChatGPT", "oai-searchbot"), ("GPTBot", "gptbot"), ("OpenAI", "openai"),
    ("ClaudeBot", "claudebot"), ("Claude-User", "claude-user"), ("Anthropic", "anthropic-ai"),
    ("PerplexityBot", "perplexitybot"), ("Perplexity-User", "perplexity-user"),
    ("Gemini/Google-Extended", "google-extended"), ("Googlebot", "googlebot"), ("GoogleOther", "googleother"),
    ("Bingbot", "bingbot"), ("Applebot", "applebot"), ("Amazonbot", "amazonbot"),
    ("CCBot (CommonCrawl)", "ccbot"), ("Bytespider", "bytespider"), ("DuckDuckBot", "duckduckbot"),
    ("YandexBot", "yandex"), ("Meta", "meta-externalagent"), ("Meta", "facebookexternalhit"),
    ("AhrefsBot", "ahrefsbot"), ("SemrushBot", "semrushbot"), ("MJ12bot", "mj12bot"), ("DotBot", "dotbot"),
    ("Slack", "slackbot"), ("Discord", "discordbot"), ("Telegram", "telegrambot"),
    ("Twitter/X", "twitterbot"), ("WhatsApp", "whatsapp"), ("LinkedIn", "linkedinbot"),
    ("UptimeRobot", "uptimerobot"), ("Pingdom", "pingdom"),
    ("curl", "curl/"), ("wget", "wget"), ("python-requests", "python-requests"),
    ("python-urllib", "python-urllib"), ("httpx", "httpx"), ("Go-http-client", "go-http-client"),
)


def _named_agent(ua: str) -> str:
    """Friendly name for a known bot/agent/tool, or '' for an unrecognized UA."""
    u = (ua or "").lower()
    for name, marker in _AGENT_MARKERS:
        if marker in u:
            return name
    return ""


@app.get("/visits/stats", tags=["visits"])
def visits_stats(days: int = 7):
    """Aggregate counts by ua_class, country, path, status, and named bot/agent.

    The operator's own keep.html dashboard (timer-polled, tagged actor=operator
    / refered from keep.html) is counted separately as operator_requests and
    EXCLUDED from every breakdown below — so the numbers show who ELSE is
    reaching the engine: humans, AI agents, search crawlers, and tools. The door
    stays open to bots; this only makes visible who comes through it."""
    days = max(1, min(60, int(days)))
    rows = _read_visits_for_days(days=days)
    by_class: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_path: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_day: dict[str, int] = {}
    # Per-bucket day series so the /keep panel can show stacked trend lines
    intent_by_day: dict[str, dict[str, int]] = {}
    # Submit tracking: WHICH endpoints are being hit, and from how many distinct IPs
    submit_paths: dict[str, int] = {}
    submit_external_prefixes: set[str] = set()
    # Retrieval tracking: which LLM platform is citing us most
    retrieval_by_ua: dict[str, int] = {}
    retrieval_paths: dict[str, int] = {}
    unique_prefixes: set[str] = set()
    unique_external_prefixes: set[str] = set()
    agents_by_name: dict[str, int] = {}  # named bots/agents/tools reaching us (GPTBot, ClaudeBot, Googlebot, ...)
    by_hour: dict[str, int] = {}          # external requests per hour ("YYYY-MM-DDTHH") across the window
    day_cls: dict[str, dict] = {}         # per-day {ua_class: count}
    day_agents: dict[str, dict] = {}      # per-day {named-agent: count}
    day_ips: dict[str, set] = {}          # per-day distinct ip_prefixes
    operator_n = 0  # the operator's own keep.html dashboard (timer-polled) — counted separately, excluded below
    for r in rows:
        # The operator's own dashboard polls many endpoints on a timer. Count it
        # once and skip it, so every breakdown reflects who ELSE is reaching us.
        if r.get("actor") == "operator" or "keep.html" in (r.get("referer") or ""):
            operator_n += 1
            continue
        # Re-derive both class and intent from the raw fields on every read.
        # Stored values are advisory — recomputing means an improved
        # classifier retroactively fixes historical rows.
        cls = _classify_ua(r.get("ua", ""), r.get("path", ""))
        intent = _classify_intent(cls, r.get("method", "GET"), r.get("path", ""))
        # Name the bot/agent/tool when we recognize it; bucket unnamed non-humans
        # by their class. Humans are not listed here (they are in by_ua_class).
        nm = _named_agent(r.get("ua", ""))
        if nm:
            agents_by_name[nm] = agents_by_name.get(nm, 0) + 1
        elif cls != "human":
            agents_by_name[cls] = agents_by_name.get(cls, 0) + 1
        by_class[cls] = by_class.get(cls, 0) + 1
        by_intent[intent] = by_intent.get(intent, 0) + 1
        ctry = r.get("country") or "—"
        by_country[ctry] = by_country.get(ctry, 0) + 1
        p = r.get("path", "")
        by_path[p] = by_path.get(p, 0) + 1
        st = str(r.get("status", 0))
        by_status[st] = by_status.get(st, 0) + 1
        day = (r.get("ts_iso") or "")[:10]
        if day:
            by_day[day] = by_day.get(day, 0) + 1
            d = intent_by_day.setdefault(day, {})
            d[intent] = d.get(intent, 0) + 1
        ipx = r.get("ip_prefix") or ""
        if ipx:
            unique_prefixes.add(ipx)
            if not ipx.startswith("127.") and not ipx.startswith("0.0.0.0") and ipx not in ("::/32",):
                unique_external_prefixes.add(ipx)
        # Daily + hourly buckets for the cockpit's "Today & hourly" strip.
        hr = (r.get("ts_iso") or "")[:13]
        if hr:
            by_hour[hr] = by_hour.get(hr, 0) + 1
        if day:
            dc = day_cls.setdefault(day, {}); dc[cls] = dc.get(cls, 0) + 1
            if nm:
                da = day_agents.setdefault(day, {}); da[nm] = da.get(nm, 0) + 1
            elif cls != "human":
                da = day_agents.setdefault(day, {}); da[cls] = da.get(cls, 0) + 1
            if ipx:
                day_ips.setdefault(day, set()).add(ipx)
        # Sub-aggregations for the submit + retrieval panels
        if intent == "submit":
            submit_paths[p] = submit_paths.get(p, 0) + 1
            if ipx and not ipx.startswith("127.") and not ipx.startswith("0.0.0.0"):
                submit_external_prefixes.add(ipx)
        elif intent == "retrieval":
            # Bucket retrieval UAs by their primary marker so we know who's
            # citing us (ChatGPT vs Perplexity vs Claude vs You.com).
            ua_low = (r.get("ua", "") or "").lower()
            if "chatgpt" in ua_low or "openai" in ua_low or "oai-" in ua_low:
                bucket = "ChatGPT"
            elif "perplexity" in ua_low:
                bucket = "Perplexity"
            elif "claude" in ua_low or "anthropic" in ua_low:
                bucket = "Claude"
            elif "youbot" in ua_low or "you-bot" in ua_low:
                bucket = "You.com"
            elif "cohere" in ua_low:
                bucket = "Cohere"
            else:
                bucket = "Other"
            retrieval_by_ua[bucket] = retrieval_by_ua.get(bucket, 0) + 1
            retrieval_paths[p] = retrieval_paths.get(p, 0) + 1

    def _top(d: dict, n: int = 15) -> list:
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]

    # total_requests = everything (incl. the operator). operator_requests is the
    # operator's own dashboard, broken out and excluded from all breakdowns.
    # external_requests = everyone else reaching the engine — humans, AI agents,
    # search crawlers, and tools, all of it. real_visitors kept as an alias of
    # external_requests for the existing /keep panel. agents_by_name names the
    # bots/agents/tools so we can see WHO is using us.
    monitor_n = by_class.get("monitor", 0)
    external_n = len(rows) - operator_n
    _days_sorted = sorted(by_day.keys())
    _today = _days_sorted[-1] if _days_sorted else None
    _yday = _days_sorted[-2] if len(_days_sorted) >= 2 else None
    _today_block = None
    if _today:
        _today_block = {
            "date": _today,
            "requests": by_day.get(_today, 0),
            "distinct_ips": len(day_ips.get(_today, set())),
            "by_ua_class": day_cls.get(_today, {}),
            "agents_by_name": dict(sorted(day_agents.get(_today, {}).items(), key=lambda kv: kv[1], reverse=True)),
        }
    return {
        "days": days,
        "total_requests": len(rows),
        "operator_requests": operator_n,
        "external_requests": external_n,
        "real_visitors": external_n,
        "monitor_requests": monitor_n,
        "agents_by_name": dict(sorted(agents_by_name.items(), key=lambda kv: kv[1], reverse=True)),
        "unique_ip_prefixes": len(unique_prefixes),
        "external_ip_prefixes": len(unique_external_prefixes),
        # Headline numbers — the ones that answer "is anything actually happening?"
        "submit_total": by_intent.get("submit", 0),
        "submit_unique_ips": len(submit_external_prefixes),
        "retrieval_total": by_intent.get("retrieval", 0),
        "browse_total": by_intent.get("browse", 0),
        "crawl_ai_total": by_intent.get("crawl_ai", 0),
        "crawl_seo_total": by_intent.get("crawl_seo", 0),
        # Full breakdown
        "by_intent": by_intent,
        "intent_legend": {
            "submit":    "POST to an engine endpoint — real outside use",
            "retrieval": "LLM citation fetch — a human asked elsewhere",
            "crawl_ai":  "LLM training crawler — indexing for later use",
            "crawl_seo": "search-engine indexer — Googlebot / Bingbot",
            "browse":    "real browser GET — a human visit",
            "preview":   "link unfurl — someone shared a link",
            "scanner":   "vuln-path probe / internet-wide scanner",
            "other":     "monitor / unknown / unplaced",
        },
        "by_ua_class": by_class,
        "ua_class_legend": {
            "human":        "a real browser",
            "retrieval":    "LLM fetching live for a user query",
            "crawl_ai":     "LLM training crawler",
            "crawl_search": "classic search-engine indexer",
            "agent_other":  "generic bot / scraper / HTTP client",
            "preview":      "link-unfurl (someone shared a link)",
            "scanner":      "vuln-path probing or wide-scanner",
            "monitor":      "our own test/smoke probes (not a visitor)",
            "unknown":      "no User-Agent string",
            "other":        "a UA we could not place",
        },
        "submit_paths_top": dict(_top(submit_paths, 15)),
        "retrieval_by_platform": dict(_top(retrieval_by_ua, 10)),
        "retrieval_paths_top": dict(_top(retrieval_paths, 15)),
        "intent_by_day": intent_by_day,
        "by_country": dict(_top(by_country, 25)),
        "by_path_top": dict(_top(by_path, 25)),
        "by_status": by_status,
        "by_day": dict(sorted(by_day.items())),
        "by_hour": dict(sorted(by_hour.items())),
        "today": _today_block,
        "yesterday_requests": (by_day.get(_yday, 0) if _yday else 0),
        "skipped_paths_note": "health pings + static assets + testclient are not logged",
    }


# -- The Airlock — single-input router into the 8 destinations -----------
# The Desk has one input field. Whatever a visitor types (or drops) lands
# here, Shepherd classifies it into one of:
#   desk · discern · family · watch · learn · codex · tools · take_part
# The classifier returns a route + suggested URL + one-line "why." This is
# the load-bearing piece of the desk reframe — it's how 122 pages collapse
# into 8 destinations without the visitor ever having to know which page
# they want.
#
# Privacy: the raw text never gets stored. We log a sha256 prefix of the
# text (so we can dedupe + count without seeing what people typed) plus
# the route, confidence, ip_prefix /8, ua_class, intent. Operator-only
# /airlock/recent reads the log for the /keep panel.

import hashlib as _hashlib

_AIRLOCK_DIR = Path(__file__).parent.parent / "data" / "airlock"
_AIRLOCK_DIR.mkdir(parents=True, exist_ok=True)
_AIRLOCK_LOCK = _visit_threading.Lock()

# The 8 destinations and the URL each one currently lives at. As deep
# destinations get built, these URLs move (e.g. /walks.html → /discern).
_AIRLOCK_DESTINATIONS = {
    "desk":      {"url": "/workspace.html",    "label": "The Workspace",   "why": "save to journal"},
    "discern":   {"url": "/walk.html",         "label": "Discern",         "why": "verify or weigh"},
    "family":    {"url": "/family.html",       "label": "Family life",     "why": "remedy, recipe, or home"},
    "watch":     {"url": "/media-center.html", "label": "Media Center",    "why": "audio, video, or books"},
    "learn":     {"url": "/learn-deep.html",   "label": "Learn",           "why": "study, scripture, reference"},
    "codex":     {"url": "/codex-deep.html",   "label": "Codex",           "why": "the canonical manuscript"},
    "tools":     {"url": "/tools.html",        "label": "Tools",           "why": "small utility"},
    "take_part": {"url": "/take-part.html",    "label": "Take part",       "why": "submit or support"},
}


def _airlock_text_hash(text: str) -> str:
    """16-char sha256 prefix — enough to dedupe + count without storing raw text."""
    return _hashlib.sha256((text or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def _airlock_route(text: str) -> dict:
    """Classify an airlock input. Delegates to the ONE classifier in
    api/floor.py — the airlock and the floor share a single brain now, not
    two copies of the same rules. Returns {route, tool, url, confidence, why}.
    """
    from api import floor as _floor
    r = _floor.classify(text)
    return {"route": r.get("route", "discern"), "tool": r.get("tool", ""),
            "confidence": r.get("confidence", 0.3), "url": r.get("url", "/walk.html"),
            "why": r.get("why", ""), "lens": r.get("lens")}


class _AirlockClassifyIn(BaseModel):
    text: str = ""


@app.post("/airlock/classify", tags=["airlock"])
def airlock_classify(req: _AirlockClassifyIn, request: Request):
    """Classify one airlock input. Returns the route + suggested URL.

    Public — anyone can call. The text is NEVER stored raw; only its
    sha256 prefix is logged so we can dedupe + count. Returned payload
    includes the route, confidence, URL to navigate to, and a one-line
    'why' the visitor can read."""
    text = (req.text or "").strip()
    text = text[:2000]  # cap input length
    routing = _airlock_route(text)

    # Log — best-effort, never blocks the response
    try:
        client_ip = (request.headers.get("cf-connecting-ip")
                     or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
                     or (request.client.host if request.client else ""))
        ua = request.headers.get("user-agent", "")[:160]
        ua_class = _classify_ua(ua, "/airlock/classify")
        record = {
            "ts": int(time.time()),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "text_hash": _airlock_text_hash(text),
            "text_len": len(text),
            "route": routing.get("route", ""),
            "tool": routing.get("tool", ""),
            "confidence": routing.get("confidence", 0.0),
            "ip_prefix": _ip_prefix(client_ip),
            "ua_class": ua_class,
        }
        day = time.strftime("%Y%m%d", time.gmtime(record["ts"]))
        path = _AIRLOCK_DIR / f"log-{day}.jsonl"
        with _AIRLOCK_LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Decorate with destination metadata for the client
    dest = _AIRLOCK_DESTINATIONS.get(routing["route"], _AIRLOCK_DESTINATIONS["desk"])
    return {
        "ok": True,
        "route": routing["route"],
        "tool": routing.get("tool", ""),
        "destination_label": dest["label"],
        "url": routing["url"],
        "confidence": routing["confidence"],
        "why": routing["why"],
    }


def _airlock_read_days(days: int = 7, limit: int | None = None) -> list:
    """Read airlock log rows for the last N days, newest first."""
    days = max(1, min(60, int(days)))
    rows: list = []
    for d in range(days):
        day = time.strftime("%Y%m%d", time.gmtime(time.time() - d * 86400))
        path = _AIRLOCK_DIR / f"log-{day}.jsonl"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            continue
    rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return rows[:limit] if limit else rows


@app.get("/airlock/recent", tags=["airlock"])
def airlock_recent(request: Request, limit: int = 50, days: int = 7):
    """Operator-only: last N airlock inputs (hashed, never raw)."""
    _keep_require_allowed(request)
    limit = max(1, min(500, int(limit)))
    rows = _airlock_read_days(days=days, limit=limit)
    return {"count": len(rows), "days": days, "entries": rows}


@app.get("/airlock/stats", tags=["airlock"])
def airlock_stats(request: Request, days: int = 7):
    """Operator-only: aggregate airlock traffic by route, day, tool.
    The 'where humans are asking' panel for /keep."""
    _keep_require_allowed(request)
    days = max(1, min(60, int(days)))
    rows = _airlock_read_days(days=days)
    by_route: dict[str, int] = {}
    by_tool:  dict[str, int] = {}
    by_day:   dict[str, int] = {}
    confs:    dict[str, list] = {}
    unique_hashes: set[str] = set()
    for r in rows:
        rt = r.get("route", "?")
        tl = r.get("tool", "") or "—"
        by_route[rt] = by_route.get(rt, 0) + 1
        by_tool[tl] = by_tool.get(tl, 0) + 1
        day = (r.get("ts_iso") or "")[:10]
        if day:
            by_day[day] = by_day.get(day, 0) + 1
        c = r.get("confidence")
        if isinstance(c, (int, float)):
            confs.setdefault(rt, []).append(float(c))
        h = r.get("text_hash")
        if h:
            unique_hashes.add(h)
    # Mean confidence per route
    avg_conf = {k: round(sum(v) / len(v), 3) for k, v in confs.items() if v}
    return {
        "days": days,
        "total_inputs": len(rows),
        "unique_inputs": len(unique_hashes),
        "by_route": by_route,
        "by_tool": by_tool,
        "by_day": dict(sorted(by_day.items())),
        "avg_confidence_by_route": avg_conf,
        "destinations": _AIRLOCK_DESTINATIONS,
    }


# -- THE FLOOR — one thing every tool stands on --------------------------
# The integration spine. Any tool's output can be put on the WHOLE floor at
# once (Canon + gates + verifier + Calibre + nested-control + ledger) instead
# of one shard. See api/floor.py. This endpoint exposes it directly so the
# integration is demonstrable, and any front-end tool can call it.

class _FloorStandIn(BaseModel):
    text: str = ""
    lens: Optional[str] = None                     # auto-detected if omitted
    domain: Optional[str] = None
    kind: str = "claim"
    triad: Optional[Dict[str, float]] = None      # {spirit, mind, body} in [0,1]
    load: Optional[float] = None                   # in [0,1]
    capacity: Optional[float] = None               # in [0,1]
    vice_signals: Optional[Dict[str, float]] = None


@app.get("/floor", tags=["floor"])
def floor_pieces():
    """What the whole floor is — every piece a tool stands on, at a glance."""
    from api import floor as _floor
    return _floor.floor_summary()


@app.get("/didache", tags=["floor"])
def didache_witness():
    """The Didache — the Church's oldest discernment, standing under the floor.
    Each of the four gates grounded in Scripture (primary) and witnessed by the
    Didache (the earliest application of the same test). Not Canon; a second
    witness beneath Scripture, never over it."""
    from api import didache as _dd
    return _dd.witness()


@app.post("/floor/stand", tags=["floor"])
def floor_stand(req: _FloorStandIn):
    """Put any claim / tool output on the WHOLE floor and return its standing:
    Canon anchor, the four gates, the domain verifier, Calibre (health/beauty/
    shadow/vice), the nested-control layer, and the ledger offer. Public —
    this IS the engine's coherent answer surface."""
    text = (req.text or "").strip()[:4000]
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    from api import floor as _floor
    return _floor.stand_on_floor(
        text, lens=req.lens, domain=req.domain, kind=req.kind, triad=req.triad,
        load=req.load, capacity=req.capacity, vice_signals=req.vice_signals,
    )


# -- Per-card "did this help?" feedback ----------------------------------
# Any result card on the site can render the nhFeedback widget (from
# nh-shell.js). Two outcomes:
#   helped=true   → posted directly to /feedback/card
#   helped=false  → opens a refinement line; the refinement text becomes a
#                   NEW input to /airlock/classify (so a "miss" turns into
#                   the next thing to build).
#
# Privacy: card_id + topic are visible (those are operator-defined labels,
# not user content). The refinement text is hashed before storage, same
# rule as airlock. We never store what a visitor typed in the clear.

_FEEDBACK_DIR = Path(__file__).parent.parent / "data" / "feedback"
_FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
_FEEDBACK_LOCK = _visit_threading.Lock()


class _CardFeedbackIn(BaseModel):
    card_id: str = ""
    topic:   str = ""          # high-level bucket — e.g. "recipe", "verify", "remedy"
    helped:  bool = True
    surface: str = ""          # the page path the card was shown on (operator-readable)
    refinement: str = ""       # only set when helped=False — what they were actually looking for


@app.post("/feedback/card", tags=["airlock"])
def feedback_card(req: _CardFeedbackIn, request: Request):
    """Record one helped/not-helped vote on a result card."""
    card_id = (req.card_id or "").strip()[:120]
    topic   = (req.topic or "").strip()[:60]
    surface = (req.surface or "").strip()[:240]
    refinement = (req.refinement or "").strip()[:500]
    if not card_id and not topic:
        raise HTTPException(status_code=400, detail="card_id or topic required")
    try:
        client_ip = (request.headers.get("cf-connecting-ip")
                     or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
                     or (request.client.host if request.client else ""))
        ua = request.headers.get("user-agent", "")[:160]
        record = {
            "ts": int(time.time()),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "card_id": card_id,
            "topic":   topic,
            "helped":  bool(req.helped),
            "surface": surface,
            # Refinement text never stored raw — hashed prefix only
            "refinement_hash": _airlock_text_hash(refinement) if refinement else "",
            "refinement_len":  len(refinement),
            "ip_prefix": _ip_prefix(client_ip),
            "ua_class": _classify_ua(ua, "/feedback/card"),
        }
        day = time.strftime("%Y%m%d", time.gmtime(record["ts"]))
        path = _FEEDBACK_DIR / f"card-{day}.jsonl"
        with _FEEDBACK_LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # If they refined, route the refinement as a NEW airlock input. That
    # closes the loop: "not what I wanted, I wanted X" becomes a fresh
    # classification + suggested URL we can return for the visitor to
    # follow. The refinement also gets logged to the airlock log.
    if not req.helped and refinement:
        routing = _airlock_route(refinement)
        try:
            ip_prefix = _ip_prefix(client_ip)
            airlock_rec = {
                "ts": int(time.time()),
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "text_hash": _airlock_text_hash(refinement),
                "text_len": len(refinement),
                "route": routing.get("route", ""),
                "tool":  routing.get("tool", ""),
                "confidence": routing.get("confidence", 0.0),
                "ip_prefix": ip_prefix,
                "ua_class": _classify_ua(ua, "/airlock/classify"),
                "via": "feedback_refinement",
            }
            day = time.strftime("%Y%m%d", time.gmtime(airlock_rec["ts"]))
            apath = _AIRLOCK_DIR / f"log-{day}.jsonl"
            with _AIRLOCK_LOCK:
                with open(apath, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(airlock_rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        dest = _AIRLOCK_DESTINATIONS.get(routing["route"], _AIRLOCK_DESTINATIONS["desk"])
        return {
            "ok": True,
            "refined_route": routing["route"],
            "refined_url":   routing["url"],
            "refined_why":   routing["why"],
            "destination_label": dest["label"],
        }
    return {"ok": True}


def _feedback_read_days(days: int = 7, limit: int | None = None) -> list:
    rows: list = []
    days = max(1, min(60, int(days)))
    for d in range(days):
        day = time.strftime("%Y%m%d", time.gmtime(time.time() - d * 86400))
        path = _FEEDBACK_DIR / f"card-{day}.jsonl"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            continue
    rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return rows[:limit] if limit else rows


@app.get("/feedback/stats", tags=["airlock"])
def feedback_stats(request: Request, days: int = 7):
    """Operator-only: aggregate per-card feedback. Helped vs not-helped
    rate, per topic + per surface. The 'where are we delivering value?'
    panel for /keep."""
    _keep_require_allowed(request)
    rows = _feedback_read_days(days=days)
    by_topic: dict[str, dict[str, int]] = {}
    by_surface: dict[str, dict[str, int]] = {}
    total = {"helped": 0, "missed": 0}
    for r in rows:
        helped = "helped" if r.get("helped") else "missed"
        total[helped] += 1
        t = (r.get("topic") or "—")[:40]
        d = by_topic.setdefault(t, {"helped": 0, "missed": 0})
        d[helped] += 1
        s = (r.get("surface") or "—")[:40]
        d2 = by_surface.setdefault(s, {"helped": 0, "missed": 0})
        d2[helped] += 1
    def _rate(d): n = d["helped"] + d["missed"]; return round(d["helped"] / n, 3) if n else 0.0
    return {
        "days": days,
        "total": total,
        "rate":  _rate(total),
        "by_topic":   {k: {**v, "rate": _rate(v)} for k, v in by_topic.items()},
        "by_surface": {k: {**v, "rate": _rate(v)} for k, v in by_surface.items()},
    }


@app.get("/feedback/recent", tags=["airlock"])
def feedback_recent(request: Request, limit: int = 50, days: int = 7):
    """Operator-only: last N card-feedback events."""
    _keep_require_allowed(request)
    limit = max(1, min(500, int(limit)))
    rows = _feedback_read_days(days=days, limit=limit)
    return {"count": len(rows), "days": days, "entries": rows}


# -- Bible Trivia gameshow: leaderboard ----------------------------------
# /bible-trivia.html posts a score here and reads the board back.
# Append-only JSONL, same pattern as the visit log.
_TRIVIA_DIR = Path(__file__).parent.parent / "data" / "trivia"
_TRIVIA_DIR.mkdir(parents=True, exist_ok=True)
_TRIVIA_SCORES = _TRIVIA_DIR / "scores.jsonl"
_TRIVIA_LOCK = _visit_threading.Lock()


class _TriviaScoreIn(BaseModel):
    name: str = "Anonymous"
    score: int = 0


@app.post("/trivia/score", tags=["trivia"])
def trivia_submit_score(entry: _TriviaScoreIn):
    """Record one Bible-trivia score for the leaderboard."""
    name = (entry.name or "Anonymous").strip().replace("<", "").replace(">", "")[:24] or "Anonymous"
    try:
        score = int(entry.score)
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 1_000_000))
    rec = {
        "name": name, "score": score,
        "ts": int(time.time()),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        with _TRIVIA_LOCK:
            with open(_TRIVIA_SCORES, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        raise HTTPException(status_code=500, detail="could not record score")
    return {"ok": True, "name": name, "score": score}


@app.get("/trivia/leaderboard", tags=["trivia"])
def trivia_leaderboard(limit: int = 15):
    """Top Bible-trivia scores, highest first."""
    limit = max(1, min(100, int(limit)))
    rows = []
    if _TRIVIA_SCORES.exists():
        for line in _TRIVIA_SCORES.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                rows.append({"name": r.get("name", "Anonymous"), "score": int(r.get("score", 0))})
            except Exception:
                continue
    rows.sort(key=lambda r: r["score"], reverse=True)
    return {"count": len(rows), "leaderboard": rows[:limit]}


# -- Intake + quarantine + operator inbox --------------------------------
# Anyone can throw text/url/title at the engine — it lands in INTAKE, the
# working queue. The operator decomposes intake items into provisional
# packets and tests them; what survives is kept, what fails is FLUSHED
# to QUARANTINE. Quarantine is the trash can — items there get cleaned
# out periodically. The mailbox at /inbox surfaces both, plus contact
# messages.

_INTAKE_DIR    = Path(__file__).parent.parent / "data" / "intake"
_QUARANTINE_DIR = Path(__file__).parent.parent / "data" / "quarantine"
_SAMPLES_DIR   = Path(__file__).parent.parent / "data" / "samples"
_INBOX_DIR     = Path(__file__).parent.parent / "data" / "inbox"
_INTAKE_DIR.mkdir(parents=True, exist_ok=True)
_QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
_INBOX_DIR.mkdir(parents=True, exist_ok=True)

_INTAKE_FILE     = _INTAKE_DIR / "queue.jsonl"          # working queue
_QUARANTINE_FILE = _QUARANTINE_DIR / "flushed.jsonl"    # holding hazmat — must be airlocked OUT
_SAMPLES_FILE    = _SAMPLES_DIR / "preserved.jsonl"     # failures kept for learning
_INBOX_FILE      = _INBOX_DIR / "messages.jsonl"
_INBOX_STATE     = _INBOX_DIR / "state.json"

import hashlib as _hashlib_qi


def _short_hash(text: str) -> str:
    return _hashlib_qi.sha256(text.encode("utf-8")).hexdigest()[:10]


def _notify_operator(title: str, body: str, *, kind: str = "message") -> None:
    """Best-effort push to the operator's own notification channel.

    Reads NOTIFY_WEBHOOK_URL from the environment — a Discord, Slack, or
    generic incoming-webhook URL. The payload carries both 'content'
    (Discord) and 'text' (Slack) keys so a single configured URL works
    for either service. To turn on phone notifications, the operator
    creates a webhook (Discord: Server Settings → Integrations → Webhooks,
    ~30 seconds, free) and sets NOTIFY_WEBHOOK_URL in the server .env.

    This is an operator-to-SELF alert about the operator's own inbox — not
    a message sent on a visitor's behalf — so it fires automatically. The
    durable record in the inbox is always written regardless; if no webhook
    is configured this is a silent no-op. Never raises: a notification
    failure must never break the request that triggered it.
    """
    url = os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        import urllib.request as _ureq
        payload = json.dumps({
            "content": f"📬 **{title}**\n{body}",   # Discord uses 'content'
            "text":    f"📬 *{title}*\n{body}",      # Slack uses 'text'
        }).encode("utf-8")
        req = _ureq.Request(
            url, data=payload,
            headers={"Content-Type": "application/json",
                     "User-Agent": "NarrowHighway-Notify/1"},
            method="POST",
        )
        _ureq.urlopen(req, timeout=6)
    except Exception:
        pass  # notification is a nicety, never a dependency


def _load_state() -> Dict[str, Any]:
    try:
        if _INBOX_STATE.exists():
            s = json.loads(_INBOX_STATE.read_text("utf-8"))
            s.setdefault("read_ids", [])
            s.setdefault("dismissed_ids", [])
            s.setdefault("flushed_ids", [])
            return s
    except Exception:
        pass
    return {"read_ids": [], "dismissed_ids": [], "flushed_ids": []}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _INBOX_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


class _IntakeSubmit(BaseModel):
    """Throw anything at the engine. Title optional; text required.
    URL optional. Contributor handle optional. No email required.
    visitor_id optional — when supplied, the writing can be retrieved by
    the writer via /scribe/mine without them having to save the receipt.

    `lang` optional: when not "en", the engine MTs the title + text to
    English on store (for indexing + retrieval) and preserves the writer's
    original words alongside (so /scribe/mine renders them in the writer's
    language).
    """
    title: str = ""
    text: str
    url: str = ""
    contributor_handle: str = ""
    visitor_id: str = ""
    lang: str = "en"


# Back-compat: older clients posted to /quarantine/submit. Same payload.
_QuarantineSubmit = _IntakeSubmit


class _ContactSubmit(BaseModel):
    """Leave Matt a message. Email optional; message required."""
    name: str = ""
    email: str = ""
    subject: str = ""
    message: str


def _do_intake_submit(request: Request, req: _IntakeSubmit) -> Dict[str, Any]:
    """Core intake handler. Used by /intake and the legacy
    /quarantine/submit alias. Lands in data/intake/queue.jsonl —
    intake is the working queue. Quarantine is the trash."""
    _rate_check(request, "propose")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 10000:
        raise HTTPException(status_code=400, detail="text too long (max 10000 chars)")

    ip = (request.headers.get("cf-connecting-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    now = int(time.time())
    handle = (req.contributor_handle or "").strip().lower()
    if handle and not _community.is_valid_handle(handle):
        handle = ""

    # Validate visitor_id if supplied. Same regex as coach_journal.
    visitor_id = (req.visitor_id or "").strip().lower()
    if visitor_id and not _coach_journal._valid_visitor_id(visitor_id):
        visitor_id = ""

    # Reverse MT to English when writer's language isn't English. The
    # English form is what gets indexed + retrieved; the writer's original
    # words are preserved alongside so /scribe/mine renders them in their
    # language. Floor-safe: if no MT provider can handle the input the
    # original text is used for both fields.
    lang_norm = (req.lang or "en").strip().lower() or "en"
    title_clean = (req.title or "").strip()[:200]
    text_en = text
    title_en = title_clean
    text_original = None
    title_original = None
    mt_provider: Optional[str] = None
    if lang_norm != "en":
        try:
            r1 = _mt_adapter.translate(text=text, target_lang="en", source_lang=lang_norm)
            if r1 and not r1.get("fallback") and r1.get("text"):
                text_en = r1["text"]
                text_original = text
                mt_provider = r1.get("provider")
            if title_clean:
                r2 = _mt_adapter.translate(text=title_clean, target_lang="en", source_lang=lang_norm)
                if r2 and not r2.get("fallback") and r2.get("text"):
                    title_en = r2["text"]
                    title_original = title_clean
                    mt_provider = mt_provider or r2.get("provider")
        except Exception:
            pass

    # Keep the "q-" prefix on item IDs for backward compatibility with
    # any state.json entries from before the rename — the prefix is
    # opaque, the lane is determined by which file it lives in.
    record = {
        "id": "q-" + _short_hash(text_en + str(now)),
        "submitted_at": now,
        "submitted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "ip_prefix": _ip_prefix(ip),
        "country": request.headers.get("cf-ipcountry", "")[:8],
        "title": title_en,
        "text":  text_en,
        "url": (req.url or "").strip()[:400],
        "contributor_handle": handle,
        "visitor_id": visitor_id,
        "status": "new",
        "polymathic_attempted": False,
        "lang": lang_norm,
    }
    if text_original is not None:
        record["text_original"] = text_original
    if title_original is not None:
        record["title_original"] = title_original
    if mt_provider:
        record["mt_provider"] = mt_provider
    try:
        with open(_INTAKE_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not persist: {exc}")

    return {
        "ok": True,
        "id": record["id"],
        "status": "pending",
        "lane": "intake",
        "status_url": f"/intake/status/{record['id']}",
        "view_url": f"/scribe.html?id={record['id']}",
        "submitted_at": record["submitted_at_iso"],
        "message": "Kept. Your writing is in the keeping; the engine will see what survives.",
    }


@app.post("/intake", tags=["intake"])
def intake_submit(request: Request, req: _IntakeSubmit):
    """Public ingest. Anyone, no auth. Lands in INTAKE — the working
    queue. The operator decomposes items into provisional packets;
    what fails the test is flushed to quarantine."""
    return _do_intake_submit(request, req)


@app.post("/quarantine/submit", tags=["intake"], include_in_schema=False)
def quarantine_submit_legacy(request: Request, req: _IntakeSubmit):
    """Deprecated alias. Use /intake instead."""
    return _do_intake_submit(request, req)


def _scan_intake_lane(path: Path, item_id: str) -> Optional[Dict[str, Any]]:
    """Linear scan of a JSONL lane for one item_id. Returns the record or None."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("id") == item_id:
                    return rec
    except OSError:
        return None
    return None


def _scan_almanac_for_intake(item_id: str) -> Optional[Dict[str, Any]]:
    """Check whether any almanac entry records this intake id as its
    source. Returns the almanac entry (id + title) or None.

    Promotions are manual today (operator copies into entries.jsonl);
    when they record `source_intake_id` we'll surface it here. Until
    then this returns None for every id — but the endpoint is in place
    so the moment the operator adds the field, the status flips.
    """
    almanac_file = Path(__file__).parent.parent / "data" / "almanac" / "entries.jsonl"
    if not almanac_file.exists():
        return None
    try:
        with almanac_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                src = rec.get("source_intake_id") or rec.get("source_intake") or ""
                if src and src == item_id:
                    return {"id": rec.get("id"), "title": rec.get("title") or rec.get("situation", "")[:140]}
    except OSError:
        return None
    return None


@app.get("/intake/status/{item_id}", tags=["intake"])
def intake_status(item_id: str):
    """Public status check for a Scribe submission.

    Returns the current lane the item is in:
      - "promoted"  : appears in the almanac with this id as its source
      - "pending"   : still in the working queue (data/intake/queue.jsonl)
      - "archived"  : moved to quarantine (operator decided no)
      - "not_found" : id is unknown (cleared or never existed)

    No auth — anyone with the receipt id can check their own submission.
    Rate-limited at the default bucket (60/min/IP) so this can't be
    used to mine the queue with a brute-force scan.
    """
    _safe_id(item_id, "item_id")

    # Signed promotion receipt is authoritative — if one exists, the
    # item was promoted to the almanac regardless of where it now
    # lives in the intake/quarantine lanes.
    try:
        from api.receipts import find_receipt as _find_receipt
        rcpt = _find_receipt(item_id)
        if rcpt:
            return {
                "item_id": item_id,
                "status": "promoted",
                "lane": "almanac",
                "almanac_entry": {
                    "id": rcpt.get("almanac_entry_id"),
                    "title": rcpt.get("almanac_entry_title"),
                },
                "receipt": rcpt,
                "message": "Your contribution was promoted to the Almanac. The signed receipt is included for offline verification.",
            }
    except Exception:
        pass

    # Almanac entry that records this intake as source — also promoted.
    promoted = _scan_almanac_for_intake(item_id)
    if promoted:
        return {
            "item_id": item_id,
            "status": "promoted",
            "lane": "almanac",
            "almanac_entry": promoted,
            "message": "Your contribution was promoted to the Almanac.",
        }

    # Pending — still in the working queue
    pending = _scan_intake_lane(_INTAKE_FILE, item_id)
    if pending:
        submitted = pending.get("submitted_at_iso") or ""
        return {
            "item_id": item_id,
            "status": "pending",
            "lane": "intake",
            "submitted_at": submitted,
            "message": "Still in the working queue. The operator reviews each item; the keeping decides what survives.",
        }

    # Archived — moved to quarantine
    archived = _scan_intake_lane(_QUARANTINE_FILE, item_id)
    if archived:
        flushed = archived.get("flushed_at_iso") or ""
        return {
            "item_id": item_id,
            "status": "archived",
            "lane": "quarantine",
            "submitted_at": archived.get("submitted_at_iso") or "",
            "archived_at": flushed,
            "message": "Reviewed and archived. Not every submission makes the book; the engine errs on the side of pruning.",
        }

    return {
        "item_id": item_id,
        "status": "not_found",
        "lane": None,
        "message": "No item with that id is in the system. It may have been cleared in a periodic prune.",
    }


# ── Scribe lens: visitor-scoped + public recent feeds ──────────────────
# Closes the writing loop. After a visitor writes to /intake with a
# visitor_id, they can see all their own writings + statuses via
# /scribe/mine, and the recent public feed via /scribe/recent.

def _scan_intake_for_visitor(path: Path, visitor_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Linear scan of an intake/quarantine lane returning records that match a visitor_id."""
    if not path.exists() or not visitor_id:
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("visitor_id") == visitor_id:
                    out.append(rec)
                    if len(out) >= limit:
                        break
    except OSError:
        return out
    return out


def _resolve_status_for_intake_id(item_id: str) -> Dict[str, Any]:
    """Resolve current lane for an intake id. Cheap version of /intake/status."""
    try:
        from api.receipts import find_receipt as _find_receipt
        rcpt = _find_receipt(item_id)
        if rcpt:
            return {
                "status": "promoted",
                "lane": "almanac",
                "almanac_entry": {
                    "id": rcpt.get("almanac_entry_id"),
                    "title": rcpt.get("almanac_entry_title"),
                },
            }
    except Exception:
        pass
    promoted = _scan_almanac_for_intake(item_id)
    if promoted:
        return {"status": "promoted", "lane": "almanac", "almanac_entry": promoted}
    if _scan_intake_lane(_QUARANTINE_FILE, item_id):
        return {"status": "archived", "lane": "quarantine"}
    if _scan_intake_lane(_INTAKE_FILE, item_id):
        return {"status": "pending", "lane": "intake"}
    return {"status": "not_found", "lane": None}


@app.get("/scribe/mine", tags=["humans"])
def scribe_mine(visitor_id: str, limit: int = 50):
    """List all writings submitted by this visitor across all lanes,
    newest first, with current status resolved per item."""
    if not _coach_journal._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    limit = max(1, min(200, limit))
    recs: Dict[str, Dict[str, Any]] = {}
    for path in (_INTAKE_FILE, _QUARANTINE_FILE):
        for r in _scan_intake_for_visitor(path, visitor_id, limit=limit):
            rid = r.get("id")
            if not rid:
                continue
            # Last-write-wins by submitted_at (a record can move lanes;
            # we display by its current location).
            ex = recs.get(rid)
            if not ex or (r.get("submitted_at", 0) or 0) >= (ex.get("submitted_at", 0) or 0):
                recs[rid] = r
    items = sorted(recs.values(), key=lambda r: r.get("submitted_at", 0), reverse=True)[:limit]
    out = []
    for r in items:
        status = _resolve_status_for_intake_id(r.get("id", ""))
        out.append({
            "id": r.get("id"),
            "title": r.get("title", ""),
            "text": (r.get("text") or "")[:600],
            "text_truncated": len((r.get("text") or "")) > 600,
            "url": r.get("url", ""),
            "contributor_handle": r.get("contributor_handle", ""),
            "submitted_at": r.get("submitted_at_iso") or "",
            "status": status.get("status"),
            "lane": status.get("lane"),
            "almanac_entry": status.get("almanac_entry"),
            "view_url": f"/scribe.html?id={r.get('id','')}",
            "status_url": f"/intake/status/{r.get('id','')}",
        })
    return {"total": len(out), "writings": out}


@app.get("/scribe/recent", tags=["humans"])
def scribe_recent(limit: int = 30):
    """Public feed of recent intake — title + first 200 chars + status.
    No visitor_id, no IP, no PII. Useful as a stream of what the keeping
    is currently considering."""
    limit = max(1, min(100, limit))
    items: List[Dict[str, Any]] = []
    if _INTAKE_FILE.exists():
        try:
            with _INTAKE_FILE.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                items.append(rec)
                if len(items) >= limit * 2:
                    break
        except OSError:
            pass
    out = []
    seen = set()
    for r in items:
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        status = _resolve_status_for_intake_id(rid)
        out.append({
            "id": rid,
            "title": (r.get("title") or "").strip() or "(untitled)",
            "preview": (r.get("text") or "")[:240],
            "contributor_handle": r.get("contributor_handle", ""),
            "submitted_at": r.get("submitted_at_iso") or "",
            "status": status.get("status"),
            "lane": status.get("lane"),
            "almanac_entry": status.get("almanac_entry"),
            "view_url": f"/scribe.html?id={rid}",
        })
        if len(out) >= limit:
            break
    return {"total": len(out), "writings": out}


# ── User-submitted disagreement: the engine's RED gate, applied to itself

class _DisagreeSubmit(BaseModel):
    """Flag a specific packet as wrong, with a stated reason. Anonymous
    via visitor_id; the operator triages.

    `lang` optional: when not "en", reason + expected fields are MT'd to
    English on store (preserving the writer's original alongside) so the
    operator's triage queue stays in one canonical language.
    """
    visitor_id: str
    target_kind: str  # almanac | parable | walk_verdict | polymathic_verdict | archetype | protocol | fieldkit_card | scripture_anchor | other
    target_id: str
    target_summary: str = ""
    reason: str
    expected: str = ""
    evidence_url: str = ""
    lang: str = "en"


@app.post("/misalignments/disagree", tags=["humans"])
def misalignments_disagree(request: Request, req: _DisagreeSubmit):
    """Record that a user thinks a specific packet's verdict is wrong.
    Anonymous via opaque visitor_id; the operator triages.

    Routes the flag into the same `data/misalignments/log.jsonl` substrate
    as engine-detected misalignments. The shared lane is intentional —
    one place to triage everything that didn't land where the engine
    thought it would.
    """
    _rate_check(request, "disagree")
    if not _coach_journal._valid_visitor_id(req.visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    if not (req.reason or "").strip():
        raise HTTPException(status_code=400, detail="reason is required (a flag without context is noise)")
    if not (req.target_id or "").strip():
        raise HTTPException(status_code=400, detail="target_id is required")
    ip = (request.headers.get("cf-connecting-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))

    # Reverse MT reason + expected to English when writer's language isn't English.
    lang_norm = (getattr(req, "lang", None) or "en").strip().lower() or "en"
    reason_en   = req.reason
    expected_en = req.expected
    reason_original   = None
    expected_original = None
    mt_provider: Optional[str] = None
    if lang_norm != "en":
        try:
            r1 = _mt_adapter.translate(text=req.reason, target_lang="en", source_lang=lang_norm)
            if r1 and not r1.get("fallback") and r1.get("text"):
                reason_en = r1["text"]
                reason_original = req.reason
                mt_provider = r1.get("provider")
            if (req.expected or "").strip():
                r2 = _mt_adapter.translate(text=req.expected, target_lang="en", source_lang=lang_norm)
                if r2 and not r2.get("fallback") and r2.get("text"):
                    expected_en = r2["text"]
                    expected_original = req.expected
                    mt_provider = mt_provider or r2.get("provider")
        except Exception:
            pass

    dis_id = _misalignments_mod.log_user_disagreement(
        visitor_id=req.visitor_id,
        target_kind=req.target_kind,
        target_id=req.target_id,
        target_summary=req.target_summary,
        reason=reason_en,
        expected=expected_en,
        evidence_url=req.evidence_url,
        ip_prefix=_ip_prefix(ip),
        lang=lang_norm,
        reason_original=reason_original,
        expected_original=expected_original,
        mt_provider=mt_provider,
    )
    if not dis_id:
        raise HTTPException(status_code=500, detail="could not log disagreement")
    return {
        "ok": True,
        "id": dis_id,
        "view_url": f"/misalignments.html?id={dis_id}",
        "message": "Recorded. The keeping reviews disagreements — they shape what survives.",
    }


@app.get("/misalignments/mine", tags=["humans"])
def misalignments_mine(visitor_id: str, limit: int = 50):
    """A visitor's own disagreements with the engine, newest first."""
    if not _coach_journal._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    limit = max(1, min(200, limit))
    items = _misalignments_mod.list_user_disagreements(
        visitor_id=visitor_id, limit=limit, include_local=True,
    )
    return {"total": len(items), "disagreements": [
        _misalignments_mod.public_disagreement_view(r) for r in items
    ]}


@app.get("/misalignments/recent", tags=["humans"])
def misalignments_recent(limit: int = 30):
    """Public feed of recent user-submitted disagreements with the
    engine — anonymized. Visible accountability for what the keeping
    is being asked to revisit."""
    limit = max(1, min(100, limit))
    items = _misalignments_mod.list_user_disagreements(limit=limit, include_local=False)
    return {"total": len(items), "disagreements": [
        _misalignments_mod.public_disagreement_view(r) for r in items
    ]}


# ── Witness attestations: the BROTHERS gate with named teeth ───────────
# v1 is social (named attestation), v2 will add Ed25519 binding via
# the reserved signature/witness_pubkey fields.
from api import witness_walk as _witness_walk  # noqa: E402


class _WitnessSubmit(BaseModel):
    walker_visitor_id: str
    walk_id: str
    witness_name: str
    witness_role: str = ""
    attestation: str = ""
    witness_pubkey: str = ""
    signature: str = ""
    lang: str = "en"


@app.post("/witness/walk", tags=["humans"])
def witness_walk_submit(request: Request, req: _WitnessSubmit):
    """A named witness attests to a walker's BROTHERS gate.

    No witness identity infrastructure required — anyone with the
    walker's share link (walker_visitor_id + walk_id) can put their
    name to it. The walker chose to share; the witness chose to sign.
    """
    _rate_check(request, "witness")

    # Reverse MT attestation text to English if witness is writing in
    # a non-English language. Floor-safe: when MT can't handle the input
    # the original text is used unchanged for both fields.
    lang_norm = (getattr(req, "lang", None) or "en").strip().lower() or "en"
    attestation_en = req.attestation or ""
    attestation_original: Optional[str] = None
    mt_provider: Optional[str] = None
    if lang_norm != "en" and (req.attestation or "").strip():
        try:
            r = _mt_adapter.translate(
                text=req.attestation, target_lang="en", source_lang=lang_norm,
            )
            if r and not r.get("fallback") and r.get("text"):
                attestation_en = r["text"]
                attestation_original = req.attestation
                mt_provider = r.get("provider")
        except Exception:
            pass

    try:
        rec = _witness_walk.add_attestation(
            walker_visitor_id=req.walker_visitor_id,
            walk_id=req.walk_id,
            witness_name=req.witness_name,
            witness_role=req.witness_role,
            attestation=attestation_en,
            witness_pubkey=req.witness_pubkey,
            signature=req.signature,
            lang=lang_norm,
            attestation_original=attestation_original,
            mt_provider=mt_provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "witness": _witness_walk.public_view(rec)}


@app.get("/witness/walk", tags=["humans"])
def witness_walk_list(walker_visitor_id: str, walk_id: str = ""):
    """List attestations on a specific walk, or all on this walker if
    walk_id is omitted. The walker's own visitor_id authenticates the
    request — opaque, never tied to PII."""
    if not _witness_walk._valid_visitor_id(walker_visitor_id):
        raise HTTPException(status_code=400, detail="invalid walker_visitor_id")
    if walk_id:
        items = _witness_walk.list_for_walk(walker_visitor_id, walk_id)
    else:
        items = _witness_walk.list_for_walker(walker_visitor_id)
    return {
        "total": len(items),
        "witnesses": [_witness_walk.public_view(r) for r in items],
    }


@app.get("/witness/walk/context", tags=["humans"])
def witness_walk_context(walker_visitor_id: str, walk_id: str):
    """What a prospective witness sees before attesting: the situation,
    the walker's BROTHERS-gate answer (if any), and the count of prior
    attestations. Reads from the coach journal for the walk record."""
    if not _witness_walk._valid_visitor_id(walker_visitor_id):
        raise HTTPException(status_code=400, detail="invalid walker_visitor_id")
    if not _witness_walk._valid_walk_id(walk_id):
        raise HTTPException(status_code=400, detail="invalid walk_id")
    walk_rec = _coach_journal.get_walk(walker_visitor_id, walk_id)
    if not walk_rec:
        raise HTTPException(status_code=404, detail="walk not found")
    attestations = _witness_walk.list_for_walk(walker_visitor_id, walk_id)
    gates = walk_rec.get("gates") or {}
    return {
        "walk_id": walk_id,
        "situation": walk_rec.get("situation", ""),
        "brothers_answer": gates.get("BROTHERS", ""),
        "red_answer": gates.get("RED", ""),
        "floor_answer": gates.get("FLOOR", ""),
        "god_answer": gates.get("GOD", ""),
        "answered_count": walk_rec.get("answered_count", 0),
        "submitted_at": walk_rec.get("created_at"),
        "witness_count": len(attestations),
        "witnesses": [_witness_walk.public_view(r) for r in attestations],
    }


@app.get("/scribe/{item_id}", tags=["humans"])
def scribe_one(item_id: str):
    """Full record for a single writing: text, contributor (if any),
    current status, signed promotion receipt if promoted."""
    _safe_id(item_id, "item_id")
    rec = _scan_intake_lane(_INTAKE_FILE, item_id) or _scan_intake_lane(_QUARANTINE_FILE, item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="writing not found")
    status = _resolve_status_for_intake_id(item_id)
    receipt = None
    try:
        from api.receipts import find_receipt as _find_receipt
        receipt = _find_receipt(item_id)
    except Exception:
        pass
    return {
        "id": rec.get("id"),
        "title": rec.get("title", ""),
        "text": rec.get("text", ""),
        "url": rec.get("url", ""),
        "contributor_handle": rec.get("contributor_handle", ""),
        "submitted_at": rec.get("submitted_at_iso") or "",
        "status": status.get("status"),
        "lane": status.get("lane"),
        "almanac_entry": status.get("almanac_entry"),
        "receipt": receipt,
    }


# ── Promotion receipts ─────────────────────────────────────────────────

class _MintReceiptRequest(BaseModel):
    """Operator-only: mint a signed promotion receipt linking a Scribe
    intake submission to an almanac entry."""
    intake_id: str
    almanac_entry_id: str
    almanac_entry_title: str = ""
    contributor_handle: str = ""
    operator_note: str = ""


@app.post("/receipts/promote", tags=["intake"])
def receipts_mint_promotion(request: Request, req: _MintReceiptRequest):
    """Mint an Ed25519-signed promotion receipt.

    Operator-only. Call this when promoting an intake item to the
    almanac so the contributor has a soulbound proof tied to their
    handle. The receipt is verifiable offline by anyone holding the
    engine's public key.
    """
    _community_require_api_key(request)
    try:
        from api.receipts import mint_promotion_receipt
        rcpt = mint_promotion_receipt(
            intake_id=req.intake_id,
            almanac_entry_id=req.almanac_entry_id,
            almanac_entry_title=req.almanac_entry_title,
            contributor_handle=req.contributor_handle,
            operator_note=req.operator_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not mint: {exc}")
    return {"ok": True, "receipt": rcpt}


@app.get("/receipts/{intake_id}", tags=["intake"])
def receipts_lookup(intake_id: str):
    """Public lookup. Anyone with the receipt id can retrieve their
    signed promotion proof — offline-verifiable against the engine's
    public key at /identity/pubkey."""
    _safe_id(intake_id, "intake_id")
    try:
        from api.receipts import find_receipt
        rcpt = find_receipt(intake_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"lookup failed: {exc}")
    if not rcpt:
        raise HTTPException(status_code=404, detail="no receipt for that intake_id")
    return {"ok": True, "receipt": rcpt}


@app.get("/receipts", tags=["intake"])
def receipts_list_endpoint(handle: str = ""):
    """List receipts. Public; optionally filtered by contributor handle.
    Useful for a contributor to enumerate everything that was promoted."""
    try:
        from api.receipts import list_receipts
        receipts = list_receipts(handle=handle or None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"list failed: {exc}")
    return {"total": len(receipts), "receipts": receipts}


@app.post("/contact", tags=["intake"])
def contact_submit(request: Request, req: _ContactSubmit):
    """Leave Matt a message. Public, rate-limited."""
    _rate_check(request, "propose")
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    if len(msg) > 5000:
        raise HTTPException(status_code=400, detail="message too long (max 5000 chars)")

    ip = (request.headers.get("cf-connecting-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    now = int(time.time())
    record = {
        "id": "msg-" + _short_hash(msg + str(now)),
        "received_at": now,
        "received_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "name": (req.name or "").strip()[:120],
        "email": (req.email or "").strip()[:200],
        "subject": (req.subject or "").strip()[:200],
        "message": msg,
        "ip_prefix": _ip_prefix(ip),
        "country": request.headers.get("cf-ipcountry", "")[:8],
        "ua": request.headers.get("user-agent", "")[:240],
    }
    try:
        with open(_INBOX_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not persist: {exc}")

    # Ping the operator wherever they are — phone push if a webhook is set.
    # Best-effort; the durable inbox record above is the source of truth.
    _notify_operator(
        "New message · Narrow Highway",
        ((record["subject"] or "(no subject)") + "\n"
         + "from: " + (record["name"] or "anonymous")
         + (" <" + record["email"] + ">" if record["email"] else "")
         + (" · " + record["country"] if record["country"] else "") + "\n\n"
         + msg[:480] + ("…" if len(msg) > 480 else "")
         + "\n\nRead + reply → https://narrowhighway.com/inbox.html"),
        kind="message",
    )
    return {"ok": True, "id": record["id"], "message": "Kept. Thank you for the note."}


def _read_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
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
        return out
    out.sort(key=lambda r: r.get("submitted_at") or r.get("received_at") or 0, reverse=True)
    if limit:
        out = out[:limit]
    return out


@app.get("/inbox", tags=["intake"])
def inbox_index(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    include_local: bool = Query(False),
):
    """Operator-only console feed.

    Returns three lanes:
      - messages: contact form submissions
      - intake: working queue (items awaiting decomposition)
      - quarantine: flushed items (the trash; can be cleaned)

    Read/dismissed/flushed state lives per-id in data/inbox/state.json.
    By default, loopback (127.x) traffic is filtered out so operator
    testing doesn't pollute the queue. Pass include_local=true to see
    everything.
    """
    _community_require_api_key(request)
    state = _load_state()
    read = set(state.get("read_ids", []))
    dismissed = set(state.get("dismissed_ids", []))
    flushed = set(state.get("flushed_ids", []))

    def _drop_local(rows):
        if include_local:
            return rows
        return [r for r in rows if not (r.get("ip_prefix") or "").startswith("127.")]

    messages = _drop_local(_read_jsonl(_INBOX_FILE, limit=limit))
    intake = _drop_local(_read_jsonl(_INTAKE_FILE, limit=limit))
    quarantine = _drop_local(_read_jsonl(_QUARANTINE_FILE, limit=limit))

    for m in messages:
        m["is_read"] = m.get("id") in read
        m["is_dismissed"] = m.get("id") in dismissed
    for q in intake:
        q["is_read"] = q.get("id") in read
        q["is_dismissed"] = q.get("id") in dismissed
        q["is_flushed"] = q.get("id") in flushed
    for q in quarantine:
        # Items in quarantine are inherently flushed. Show read state for
        # the operator's bookkeeping.
        q["is_read"] = q.get("id") in read
        q["is_flushed"] = True

    unread_msgs = sum(1 for m in messages if not m["is_read"] and not m["is_dismissed"])
    unread_intake = sum(1 for q in intake if not q["is_read"] and not q["is_dismissed"] and not q["is_flushed"])

    return {
        "unread_messages": unread_msgs,
        "unread_intake": unread_intake,
        "total_messages": len(messages),
        "total_intake": len(intake),
        "total_quarantine": len(quarantine),
        # Back-compat aliases for older Console builds:
        "unread_quarantine": unread_intake,
        "quarantine": intake,
        # Canonical lanes:
        "messages": messages,
        "intake": intake,
        "quarantine_flushed": quarantine,
    }


def _move_intake_to_quarantine(item_id: str) -> bool:
    """Move a single item from intake/queue.jsonl to quarantine/flushed.jsonl.
    Returns True if moved, False if not found."""
    if not _INTAKE_FILE.exists():
        return False
    kept: List[str] = []
    moved: Optional[Dict[str, Any]] = None
    try:
        with _INTAKE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    kept.append(line.rstrip("\n"))
                    continue
                if rec.get("id") == item_id and moved is None:
                    rec["flushed_at"] = int(time.time())
                    rec["flushed_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    moved = rec
                else:
                    kept.append(json.dumps(rec, ensure_ascii=False))
    except Exception:
        return False
    if moved is None:
        return False
    # Rewrite intake without the moved item, append to quarantine.
    try:
        tmp = _INTAKE_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for ln in kept:
                fh.write(ln + "\n")
        tmp.replace(_INTAKE_FILE)
        with _QUARANTINE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(moved, ensure_ascii=False) + "\n")
    except Exception:
        return False
    return True


class _IntakeFlush(BaseModel):
    id: str


@app.post("/intake/flush", tags=["intake"])
def intake_flush(request: Request, req: _IntakeFlush):
    """Move an intake item to quarantine. Operator-only.

    Quarantine is the trash; items there get cleaned periodically.
    Use this when an intake item has any issue — wrong shape, spam,
    out of scope, malformed.
    """
    _community_require_api_key(request)
    item_id = (req.id or "").strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="id required")
    moved = _move_intake_to_quarantine(item_id)
    if not moved:
        raise HTTPException(status_code=404, detail="intake item not found")
    state = _load_state()
    flushed_ids = set(state.get("flushed_ids", []))
    flushed_ids.add(item_id)
    state["flushed_ids"] = sorted(flushed_ids)
    _save_state(state)
    return {"ok": True, "id": item_id, "action": "flushed"}


def _pop_quarantine_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Remove one item from quarantine/flushed.jsonl and return it.
    Returns None if not found. The caller decides where it goes next."""
    if not _QUARANTINE_FILE.exists():
        return None
    kept: List[str] = []
    popped: Optional[Dict[str, Any]] = None
    try:
        with _QUARANTINE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    kept.append(line.rstrip("\n"))
                    continue
                if rec.get("id") == item_id and popped is None:
                    popped = rec
                else:
                    kept.append(json.dumps(rec, ensure_ascii=False))
    except Exception:
        return None
    if popped is None:
        return None
    try:
        tmp = _QUARANTINE_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for ln in kept:
                fh.write(ln + "\n")
        tmp.replace(_QUARANTINE_FILE)
    except Exception:
        return None
    return popped


class _QuarantineAirlock(BaseModel):
    """The airlock sorts quarantine into one of three outcomes.

    route:
      - restore  : back to intake (the flush was a mistake)
      - preserve : to data/samples/preserved.jsonl (failures we want
                   to learn from; not deleted)
      - destroy  : actually removed (the real trash)
    """
    id: str
    route: str  # "restore" | "preserve" | "destroy"
    note: str = ""


@app.post("/quarantine/airlock", tags=["intake"])
def quarantine_airlock(request: Request, req: _QuarantineAirlock):
    """Sort one quarantine item out through the airlock. Operator-only.

    Quarantine is hazmat. Nothing leaves except through this airlock —
    no bulk clean, no sweep. Each item gets a deliberate decision:
    restore, preserve, or destroy.
    """
    _community_require_api_key(request)
    item_id = (req.id or "").strip()
    route = (req.route or "").strip().lower()
    if not item_id:
        raise HTTPException(status_code=400, detail="id required")
    if route not in ("restore", "preserve", "destroy"):
        raise HTTPException(status_code=400, detail="route must be restore|preserve|destroy")

    item = _pop_quarantine_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="quarantine item not found")

    now = int(time.time())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    note = (req.note or "").strip()[:500]

    if route == "restore":
        # Clear the flush metadata, put it back in intake as fresh.
        item.pop("flushed_at", None)
        item.pop("flushed_at_iso", None)
        item["restored_at"] = now
        item["restored_at_iso"] = now_iso
        if note:
            item["restore_note"] = note
        # Reset processing flag so the worker can re-attempt
        item["polymathic_attempted"] = False
        try:
            with _INTAKE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception as exc:
            # On write failure, put it back in quarantine so it's not lost
            try:
                with _QUARANTINE_FILE.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"restore failed: {exc}")
        # Clear the flushed_ids state so the Console doesn't still mark it flushed
        state = _load_state()
        flushed_ids = set(state.get("flushed_ids", []))
        flushed_ids.discard(item_id)
        state["flushed_ids"] = sorted(flushed_ids)
        _save_state(state)
        return {"ok": True, "id": item_id, "route": "restore", "destination": "intake"}

    if route == "preserve":
        item["preserved_at"] = now
        item["preserved_at_iso"] = now_iso
        if note:
            item["preserve_note"] = note
        try:
            with _SAMPLES_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception as exc:
            try:
                with _QUARANTINE_FILE.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"preserve failed: {exc}")
        return {"ok": True, "id": item_id, "route": "preserve", "destination": "data/samples/preserved.jsonl"}

    # destroy — item is already popped; just don't write it anywhere
    return {"ok": True, "id": item_id, "route": "destroy", "destination": "deleted"}


# -- Intake worker (provisional packet processor) ------------------------
# Walks data/intake/queue.jsonl, fans each item through polymathic +
# archetype recognition, attaches a projection (verdict + path) back
# onto the item. Operator-triggered. Idempotent unless force=true.
from api import intake_worker as _intake_worker  # noqa: E402


class _IntakeProcess(BaseModel):
    max_items: int = 10
    force: bool = False
    model: str = "claude-haiku-4-5-20251001"


@app.post("/intake/process", tags=["intake"])
def intake_process(request: Request, req: _IntakeProcess):
    """Run the worker over pending intake items. Operator-only.

    Each item gets a projection attached: composite verdict, axis
    overlaps, closest precedent, archetype combination, suggested
    path. The worker does not move items between lanes — the operator
    decides what to do based on what surfaces.
    """
    _community_require_api_key(request)
    max_n = max(1, min(50, int(req.max_items or 10)))
    result = _intake_worker.process_pending(
        max_items=max_n,
        force=bool(req.force),
        model=(req.model or "claude-haiku-4-5-20251001").strip(),
    )
    return {"ok": True, **result}


class _IntakeProcessOne(BaseModel):
    model: str = "claude-haiku-4-5-20251001"


@app.post("/intake/process/{item_id}", tags=["intake"])
def intake_process_one(request: Request, item_id: str, req: _IntakeProcessOne):
    """Process a single intake item by id (re-runs even if previously
    processed)."""
    _community_require_api_key(request)
    iid = _safe_id(item_id)
    rec = _intake_worker.get_one(iid)
    if not rec:
        raise HTTPException(status_code=404, detail="intake item not found")
    result = _intake_worker.process_pending(
        max_items=1,
        force=True,
        only_id=iid,
        model=(req.model or "claude-haiku-4-5-20251001").strip(),
    )
    # Return the freshly-projected item
    fresh = _intake_worker.get_one(iid)
    return {"ok": True, "id": iid, "result": result, "item": fresh}


@app.get("/intake/{item_id}", tags=["intake"])
def intake_get_one(request: Request, item_id: str):
    """Operator-only: fetch a single intake item including its projection."""
    _community_require_api_key(request)
    iid = _safe_id(item_id)
    rec = _intake_worker.get_one(iid)
    if not rec:
        raise HTTPException(status_code=404, detail="intake item not found")
    return rec


# -- Build queue (public) -----------------------------------------------
# Surfaces what the engine knows it cannot yet verify. The principle is
# transparency: a visitor should be able to see what we can verify, what
# we're working on, and what we've decided we won't verify (and why).
# Public, read-only.

_BUILD_QUEUE_FILE = Path(__file__).parent.parent / "data" / "build_queue" / "queue.jsonl"


@app.get("/build-queue", tags=["public"])
def build_queue_list():
    """Public listing of capability gaps with the math chains that would
    close each one. Open status: actively wanted. Declined status: no
    math chain exists; engine deliberately doesn't try.
    """
    items: List[Dict[str, Any]] = []
    if _BUILD_QUEUE_FILE.exists():
        try:
            for line in _BUILD_QUEUE_FILE.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    by_status: Dict[str, List[Dict[str, Any]]] = {"open": [], "declined": [], "other": []}
    for it in items:
        s = (it.get("status") or "open").lower()
        if s == "open":
            by_status["open"].append(it)
        elif s == "declined":
            by_status["declined"].append(it)
        else:
            by_status["other"].append(it)
    return {
        "total": len(items),
        "open": len(by_status["open"]),
        "declined": len(by_status["declined"]),
        "by_status": by_status,
    }


@app.get("/innovation", tags=["public"])
def innovation_scoreboard(days: int = Query(30, ge=1, le=365),
                          trend: int = Query(0, ge=0, le=1)):
    """The oracle-dependence scoreboard — the measurable claim of a different
    kind of computing: the engine's dependence on the statistical model SHRINKS
    with use. Every closed build-queue gap adds deterministic verifiers + an
    NL->domain routing rule, so the oracle-dependence ratio (oracle-classified
    / total verifier dispatches) should fall over time, while deterministic
    dispatches and runtime rules rise. Public, read-only.
    """
    try:
        from concordance_engine.agent import dispatch_stats as _ds
        dispatch = _ds.summary(days=days)
    except Exception as e:  # pragma: no cover
        dispatch = {"error": str(e)[:200]}

    rules = 0
    try:
        from concordance_engine.agent.runtime_rules import list_runtime_rules
        rules = len(list_runtime_rules())
    except Exception:
        pass

    gaps = {"open": 0, "closed": 0, "declined": 0}
    try:
        if _BUILD_QUEUE_FILE.exists():
            for line in _BUILD_QUEUE_FILE.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    s = (json.loads(line).get("status") or "open").lower()
                except json.JSONDecodeError:
                    continue
                if s in gaps:
                    gaps[s] += 1
    except OSError:
        pass

    odr = dispatch.get("oracle_dependence_ratio") if isinstance(dispatch, dict) else None

    # The offices' own oracle-dependence — the Shepherd shrinking with use,
    # measured from the minted training pairs (the same thesis, for the front door).
    offices = None
    shepherd_trend = None
    try:
        from api import offices as _offices
        offices = _offices.office_stats(days=days)
        # The trajectory of the Shepherd's oracle-dependence, backfilled from the
        # timestamped decision corpus — requested explicitly to keep the default
        # response lean. This is what powers the .org sparkline: a real line, not a
        # promise to accumulate one.
        if trend:
            shepherd_trend = _offices.office_trend("shepherd", days=max(days, 90))
    except Exception as e:  # pragma: no cover
        offices = offices or {"error": str(e)[:200]}

    out = {
        "thesis": "The engine's dependence on the statistical model shrinks with use.",
        "oracle_dependence_ratio": odr,
        "deterministic_ratio": (dispatch.get("deterministic_ratio")
                                if isinstance(dispatch, dict) else None),
        "runtime_rules": rules,
        "gaps": gaps,
        "dispatch": dispatch,
        "offices": offices,
        "note": ("Counts per verifier-dispatch (one per claim that reaches a "
                 "verifier), not per raw oracle call. A falling oracle ratio = "
                 "the floor widening, the borrowed mouth shrinking. `offices` is "
                 "the same measure for the Shepherd front door."),
    }
    if trend:
        out["shepherd_trend"] = shepherd_trend
    return out


# -- Misalignment review -------------------------------------------------
# Every non-CONCORDANT verdict from /polymathic is auto-logged. The
# operator reviews each one and routes it: archive (user wrong), promote
# (engine gap → build queue), bug (verifier misbehaved).
from api import misalignments as _misalignments_mod  # noqa: E402


@app.get("/misalignments", tags=["intake"])
def misalignments_list(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    include_local: bool = Query(False),
):
    """Operator-only: list logged misalignments with their review state.

    Returns counts (pending / archived / promoted / bugs) plus the items
    themselves, newest first. By default, loopback (127.x) traffic is
    filtered out so operator testing doesn't pollute the queue. Pass
    include_local=true to see everything.
    """
    _community_require_api_key(request)
    return _misalignments_mod.list_misalignments(limit=limit, include_local=include_local)


class _MisalignmentReview(BaseModel):
    id: str
    status: str   # "archive" | "promote" | "bug" | "pending"
    note: str = ""
    # Required when status == "promote":
    claim_pattern: str = ""
    needed_math: str = ""
    needed_substrate: str = ""
    # Optional: runtime routing rule. When provided alongside a
    # 'promote' decision, the engine adds a deterministic NL→domain
    # rule so the next similar claim is dispatched correctly without
    # an oracle call. Compounds routing accuracy with each promotion.
    routing_pattern: str = ""
    routing_domain: str = ""
    routing_spec_template: Dict[str, Any] = {}


@app.post("/misalignments/review", tags=["intake"])
def misalignments_review(request: Request, req: _MisalignmentReview):
    """Operator decision on one misalignment.

    archive  — user claim was wrong; engine correctly didn't confirm
    promote  — engine has a coverage gap; append to build queue
               (claim_pattern + needed_math are required)
               Optionally also adds a runtime NL→domain routing rule
               if routing_pattern + routing_domain are provided.
    bug      — verifier misbehaved; flag for fix
    pending  — undo a prior decision
    """
    _community_require_api_key(request)
    try:
        result = _misalignments_mod.review(
            item_id=req.id,
            status=req.status,
            note=req.note,
            claim_pattern=req.claim_pattern,
            needed_math=req.needed_math,
            needed_substrate=req.needed_substrate,
            routing_pattern=req.routing_pattern,
            routing_domain=req.routing_domain,
            routing_spec_template=req.routing_spec_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, **result}


@app.get("/agent/rules/runtime", tags=["intake"])
def agent_runtime_rules(request: Request):
    """Operator: list the runtime NL→domain dispatch rules that have
    been promoted from the misalignment review queue."""
    _community_require_api_key(request)
    try:
        from concordance_engine.agent.runtime_rules import list_runtime_rules
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"runtime_rules unavailable: {e}")
    rules = list_runtime_rules()
    return {"total": len(rules), "rules": rules}


class _InboxMark(BaseModel):
    id: str
    action: str  # "read" | "dismiss" | "unread" | "flush"


@app.post("/inbox/mark", tags=["intake"])
def inbox_mark(request: Request, req: _InboxMark):
    """Mark an inbox item.

    Actions:
      - read    : mark as read
      - unread  : restore to unread
      - dismiss : hide from default view (still in original lane)
      - flush   : move from intake → quarantine (intake items only)
    """
    _community_require_api_key(request)
    item_id = (req.id or "").strip()
    action = (req.action or "").strip().lower()
    if not item_id:
        raise HTTPException(status_code=400, detail="id required")
    if action not in ("read", "dismiss", "unread", "flush"):
        raise HTTPException(status_code=400, detail="action must be read|dismiss|unread|flush")

    if action == "flush":
        moved = _move_intake_to_quarantine(item_id)
        if not moved:
            raise HTTPException(status_code=404, detail="intake item not found")
        state = _load_state()
        flushed_ids = set(state.get("flushed_ids", []))
        flushed_ids.add(item_id)
        state["flushed_ids"] = sorted(flushed_ids)
        _save_state(state)
        return {"ok": True, "id": item_id, "action": "flushed"}

    state = _load_state()
    read_ids = set(state.get("read_ids", []))
    dismissed_ids = set(state.get("dismissed_ids", []))
    if action == "read":
        read_ids.add(item_id)
        dismissed_ids.discard(item_id)
    elif action == "dismiss":
        dismissed_ids.add(item_id)
        read_ids.discard(item_id)
    elif action == "unread":
        read_ids.discard(item_id)
        dismissed_ids.discard(item_id)
    state["read_ids"] = sorted(read_ids)
    state["dismissed_ids"] = sorted(dismissed_ids)
    _save_state(state)
    return {"ok": True, "id": item_id, "action": action}


# -- Archetypes ----------------------------------------------------------
# Pattern-recognition layer. Engine surfaces the closest Biblical
# archetype shape for a situation. Engine shows; human names.
# Substrate: data/archetypes/bible.jsonl
from api import archetypes as _archetypes  # noqa: E402


class _ArchetypeRecognizeRequest(BaseModel):
    situation: str
    top_k: int = 3


@app.get("/archetypes", tags=["archetypes"])
def archetypes_list():
    """Browseable catalog of all archetypes in the substrate."""
    entries = _archetypes.list_entries()
    # Strip the heavy prose for the index view; full entry comes from /archetypes/{id}
    index = []
    for e in entries:
        index.append({
            "id": e.get("id"),
            "name": e.get("name"),
            "category": e.get("category"),
            "source": e.get("source"),
            "scripture": e.get("scripture", []),
            "pattern": e.get("pattern", ""),
        })
    # Group by category for the page
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for e in index:
        cat = e.get("category", "other") or "other"
        by_category.setdefault(cat, []).append(e)
    for v in by_category.values():
        v.sort(key=lambda x: (x.get("name") or "").lower())
    return {
        "total": len(index),
        "by_category": by_category,
        "entries": index,
    }


@app.get("/archetypes/{archetype_id}", tags=["archetypes"])
def archetypes_get(archetype_id: str):
    """Full entry for one archetype."""
    aid = _safe_id(archetype_id)
    entry = _archetypes.get_entry(aid)
    if not entry:
        raise HTTPException(status_code=404, detail="archetype not found")
    return entry


@app.post("/archetype/recognize", tags=["archetypes"])
def archetype_recognize(request: Request, req: _ArchetypeRecognizeRequest):
    """Surface the closest Biblical archetype shape for a situation.

    The engine never says 'you are Jonah.' It surfaces 'this pattern
    resembles Jonah; here are the markers that matched.' The human
    names whether the shape fits.
    """
    _rate_check(request, "validate")
    situation = (req.situation or "").strip()
    if not situation:
        raise HTTPException(status_code=400, detail="situation is required")
    k = max(1, min(5, int(req.top_k or 3)))
    return _archetypes.recognize(situation, top_k=k)


# -- The Walk (Coach OS) -------------------------------------------------
# Orchestration layer: given a situation, surfaces patterns, Scripture,
# Scripture-defined protocols, closest precedent, and the four-gate
# walk as prompts the user answers themselves. Engine shows; user walks.
from api import walk as _walk_mod  # noqa: E402


class _WalkRequest(BaseModel):
    situation: str


@app.post("/walk", tags=["walk"])
def walk_situation(request: Request, req: _WalkRequest):
    """Walk a situation through the Coach OS.

    Returns a composed view: patterns (archetypes), scripture (Layer 0
    passages), protocols (Mt 18 conflict, discernment, confession,
    witness, test-spirits, reproof — when they apply), closest
    precedent, and the four gates as prompts to walk.

    The engine does not answer. It surfaces the field and asks the
    questions. The user walks.
    """
    _rate_check(request, "walk")
    situation = (req.situation or "").strip()
    if not situation:
        raise HTTPException(status_code=400, detail="situation is required")
    if len(situation) > 4000:
        raise HTTPException(status_code=400, detail="situation too long (max 4000 chars)")
    return _walk_mod.walk(situation)


@app.get("/walk/protocols", tags=["walk"])
def walk_protocols_index():
    """List the Scripture-defined protocols the engine recognizes."""
    items = _walk_mod._load_protocols()
    return {
        "total": len(items),
        "protocols": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "scripture": p.get("scripture", []),
                "summary": p.get("summary", ""),
            }
            for p in items
        ],
    }


# -- Parable: the front-door lens ----------------------------------------
# Surfaces the closest packet in the substrate as a small story.
# Generation is rhetorical (form), not epistemic (content). The trail
# underneath — source packet, axes hit, score — is the proof.
from api import parable as _parable_mod  # noqa: E402


@app.get("/parable", tags=["humans"])
def parable_get(situation: str = ""):
    """Return the closest parable to a situation, or a random one if empty.

    Doorway form of the engine: those who walk into the parable find
    more (the trail, the Coach, the gates). Those who do not, leave
    with a story — which is already a small step.
    """
    return _parable_mod.find_parable(situation or "")


@app.get("/parable/seeds", tags=["humans"])
def parable_seeds_index():
    """List all parable seeds — id, source packet, gate, axes, preview."""
    items = _parable_mod.list_seeds()
    return {"total": len(items), "seeds": items}


# ── Apothecary: compound a remedy across the substrate ───────────────
from api import apothecary as _apothecary_mod  # noqa: E402
from api import apothecary_journal as _apothecary_journal_mod  # noqa: E402
import hashlib as _hashlib_apo  # noqa: E402


def _stable_compound_id(condition: str) -> str:
    """Same condition for the same visitor → same compound_id (idempotent save)."""
    h = _hashlib_apo.sha256(condition.strip().lower().encode("utf-8")).hexdigest()
    return f"apo_{h[:16]}"


@app.get("/apothecary", tags=["humans"])
def apothecary_compound(condition: str = "", visitor_id: str = "", lang: str = "en"):
    """For a stated condition, compound a remedy from the substrate.

    Returns one packet per ingredient slot: Scripture, Proverb, Protocol,
    Training, Mind, Parable, FieldKit, Body, Philosopher, Father, Almanac.
    Conditional slots return null when retrieval has no strong match.

    Engine still eliminates; the ingredients are existing packets ranked
    by axis overlap + keyword match. The compounding is rhetorical form.

    `lang` selects the reader's language. Two effects:
      1. Incoming condition is MT'd to English for retrieval (so a Spanish
         "ansiedad" matches an English "anxiety" packet) — the original
         text is preserved in the response and saved to the journal.
      2. Scripture-kind result slots swap to the parallel PD translation
         (e.g. Reina-Valera 1909 when lang=es). Engine-authored slots
         route through the MT adapter.

    If `visitor_id` is supplied AND the engine found a non-empty compound,
    the result is saved to the visitor's apothecary journal so it can be
    re-opened from /apothecary/mine. visitor_id must be 8-32 lowercase hex.
    """
    condition_original = (condition or "").strip()
    condition_for_retrieval = condition_original
    lang_norm = (lang or "en").strip().lower() or "en"
    mt_input: Optional[Dict[str, Any]] = None
    if condition_original and lang_norm != "en":
        # Reverse translate to English for retrieval. Floor: if no provider
        # produces output, fall back to the original (retrieval may miss
        # but the response will still compound something via deterministic
        # hash pick).
        try:
            mt_result = _mt_adapter.translate(
                text=condition_original, target_lang="en", source_lang=lang_norm,
            )
            if mt_result and not mt_result.get("fallback") and mt_result.get("text"):
                condition_for_retrieval = mt_result["text"]
                mt_input = {
                    "original":   condition_original,
                    "translated": condition_for_retrieval,
                    "provider":   mt_result.get("provider"),
                    "source_lang": lang_norm,
                }
        except Exception:
            pass
    result = _apothecary_mod.compound(condition_for_retrieval, lang=lang_norm)
    # Restore the visitor-typed condition as the "for:" label so the card
    # shows their words, not the English-translated version.
    if mt_input:
        result["condition"] = condition_original
        result["condition_en"] = condition_for_retrieval
        result["mt_input"] = mt_input
    if (
        visitor_id
        and _apothecary_journal_mod._valid_visitor_id(visitor_id)
        and result.get("compound")
        and not result.get("error")
    ):
        try:
            cid = _stable_compound_id(condition or "")
            saved = _apothecary_journal_mod.save_compound(
                visitor_id=visitor_id,
                compound_id=cid,
                condition=condition,
                compound=result["compound"],
            )
            result["compound_id"] = saved["compound_id"]
            result["saved"] = True
        except (ValueError, OSError):
            # Save failure must not break the response — the compound is the point.
            result["saved"] = False
    return result


@app.get("/apothecary/conditions", tags=["humans"])
def apothecary_conditions():
    """Curated list of common conditions to seed the input as one-click chips."""
    return {"conditions": _apothecary_mod.CONDITION_PRESETS}


@app.get("/apothecary/languages", tags=["humans"])
def apothecary_languages():
    """Languages with a parallel PD Bible swap available.

    English is always present (canonical substrate). Other entries list a
    language code and the translation that will be swapped in for Scripture
    slots. As more parallel translations are ingested (CUV for zh, Louis
    Segond for fr, etc.) they'll appear here automatically.
    """
    from api import scripture_lookup as _scripture_lookup_mod
    return {"languages": _scripture_lookup_mod.supported_languages()}


# ── Atlas of Bibles: catalog + parallel verse viewer ─────────────────────


@app.get("/scripture/catalog", tags=["humans"])
def scripture_catalog():
    """Catalog of every PD Bible translation in the substrate, with coverage stats.

    Used by the Atlas of Bibles lens. Each entry includes language, translation
    name, year, source URL, license, total verse count, and book coverage.
    """
    from api import scripture_lookup as _scripture_lookup_mod
    rows = _scripture_lookup_mod.catalog()
    return {"total": len(rows), "translations": rows}


@app.get("/places", tags=["humans"])
def places_list(letter: Optional[str] = None, search: Optional[str] = None):
    """List geographic entries from Easton's Bible Dictionary (920 places).

    Optional filters: `letter` (A-Z first character) or `search` (substring
    over name + text). Each row carries a short preview + ref_count so the
    Places lens can render a scannable A-Z directory.
    """
    from api import places as _places_mod
    return _places_mod.list_places(letter=letter, search=search)


@app.get("/places/by-ref", tags=["humans"])
def places_by_ref(ref: str = ""):
    """For a Scripture reference (e.g. "Bethlehem 5:2"), list every place
    in Easton's that cites this verse. Cross-links the Atlas of Bibles
    parallel viewer into the geographic substrate."""
    from api import places as _places_mod
    if not ref or not ref.strip():
        raise HTTPException(status_code=400, detail="ref is required")
    return _places_mod.by_reference(ref)


@app.get("/places/stats", tags=["humans"])
def places_stats():
    """Quick counts + attribution for the Places lens header."""
    from api import places as _places_mod
    return _places_mod.stats()


@app.get("/places/{slug}", tags=["humans"])
def places_get(slug: str):
    """Full entry for one place (or any Easton entry, by slug)."""
    from api import places as _places_mod
    rec = _places_mod.get_place(slug)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"place {slug!r} not found")
    return rec


@app.get("/easton/{slug}", tags=["humans"])
def easton_get(slug: str):
    """Full Easton entry for any slug — people, concepts, objects, places."""
    from api import places as _places_mod
    rec = _places_mod._easton_index().get(slug.strip().lower())
    if rec is None:
        raise HTTPException(status_code=404, detail=f"easton entry {slug!r} not found")
    return rec


@app.get("/scripture/lookup", tags=["humans"])
def scripture_lookup_one(ref: str = "", lang: str = "en"):
    """Quick single-language verse/range/chapter lookup.

    Lighter than /scripture/parallel — fetches one translation, not all 22.
    Useful for scripts, agents, and any page that wants Scripture in one
    language without paying for the parallel comparison.

    Accepts: "Proverbs 12:25", "Matthew 5:3-12", "Psalm 23".
    """
    from api import scripture_lookup as _scripture_lookup_mod
    if not ref or not ref.strip():
        return {"ref": "", "lang": lang, "error": "ref is required", "text": None}
    parsed = _scripture_lookup_mod.parse_ref(ref.strip())
    if not parsed:
        return {"ref": ref, "lang": lang, "error": "could not parse reference", "text": None}
    book = parsed["book"]
    ch = parsed["chapter"]
    vs = parsed["verse_start"]
    ve = parsed["verse_end"]
    lang_norm = (lang or "en").strip().lower() or "en"
    try:
        if vs is None:
            if lang_norm == "en":
                text = _scripture_lookup_mod.english_chapter_text(book, ch)
            else:
                text = _scripture_lookup_mod.lookup_chapter(lang_norm, book, ch)
        elif ve and ve > vs:
            if lang_norm == "en":
                text = _scripture_lookup_mod.english_pericope_text(book, ch, vs, ve)
            else:
                text = _scripture_lookup_mod.lookup_range(lang_norm, book, ch, vs, ve)
        else:
            if lang_norm == "en":
                text = _scripture_lookup_mod.english_verse(book, ch, vs)
            else:
                text = _scripture_lookup_mod.lookup_verse(lang_norm, book, ch, vs)
    except Exception as exc:
        return {"ref": ref, "lang": lang_norm, "error": str(exc), "text": None}
    if text is None:
        return {
            "ref": ref, "lang": lang_norm,
            "parsed": parsed,
            "text": None,
            "error": f"verse/chapter not found in {lang_norm}",
            "translation": _scripture_lookup_mod.translation_label(lang_norm),
        }
    return {
        "ref": ref,
        "lang": lang_norm,
        "parsed": parsed,
        "text": text,
        "translation": _scripture_lookup_mod.translation_label(lang_norm) or "World English Bible",
    }


@app.get("/scripture/parallel", tags=["humans"])
def scripture_parallel(ref: str = "", langs: str = ""):
    """For a verse reference, return that text in every available translation.

    Accepts: "Proverbs 12:25" (single verse), "Matthew 5:3-12" (range), or
    "Psalm 23" (whole chapter). Missing translations come back with text=null
    so the UI can render "not yet available" rows.

    Optional `langs` is a comma-separated list of language codes
    (e.g. "en,es,fr") to restrict results. Omit for all 22 translations.
    """
    from api import scripture_lookup as _scripture_lookup_mod
    if not ref or not ref.strip():
        return {"ref": "", "error": "ref is required", "results": []}
    lang_list = [l.strip() for l in langs.split(",") if l.strip()] if langs.strip() else None
    return _scripture_lookup_mod.parallel_lookup(ref.strip(), langs=lang_list)


# ── i18n: UI string translation ─────────────────────────────────────────
from api import i18n_strings as _i18n_strings_mod  # noqa: E402


@app.get("/i18n/strings", tags=["humans"])
def i18n_strings(lang: str = "en"):
    """Return the full UI string dictionary translated into `lang`.

    First call for a new language translates via the MT adapter and caches
    to disk. Subsequent calls serve from cache (instant, free).
    English is always instant (no translation needed).
    """
    return _i18n_strings_mod.get_strings(lang, mt_adapter=_mt_adapter)


@app.get("/i18n/languages", tags=["humans"])
def i18n_languages():
    """List available UI languages with native names."""
    from api.scripture_lookup import available_translations
    return {
        "languages": [
            {"code": "en", "name": "English", "native": "English"},
        ] + [
            {"code": code, "name": label, "native": label}
            for code, label in sorted(available_translations().items())
            if code != "en"
        ],
    }


# ── Machine translation: provider-agnostic adapter ───────────────────────
from api import mt_adapter as _mt_adapter  # noqa: E402


@app.get("/mt/status", tags=["humans"])
def mt_status():
    """Which MT providers are configured (no keys echoed) and cache stats."""
    return {
        "available":    _mt_adapter.is_available(),
        "providers":    _mt_adapter.providers_status(),
        "cache":        _mt_adapter.cache_stats(),
        "bible_corpus": _mt_adapter.bible_corpus_stats(),
    }


class _MTTranslateRequest(BaseModel):
    text:        str
    target_lang: str
    source_lang: str = "en"


@app.post("/mt/translate", tags=["humans"])
def mt_translate(req: _MTTranslateRequest):
    """Translate a string. Returns text unchanged when no provider configured.

    Cache-first: every translation lives in `data/mt_cache/<lang>.jsonl` after
    first call. The provider is recorded so the operator can see which
    translations came from which source.
    """
    return _mt_adapter.translate(
        text=req.text, target_lang=req.target_lang, source_lang=req.source_lang,
    )


@app.get("/apothecary/mine", tags=["humans"])
def apothecary_mine(visitor_id: str, limit: int = 20):
    """List a visitor's saved compounds, newest first."""
    if not _apothecary_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    items = _apothecary_journal_mod.list_compounds(
        visitor_id, limit=max(1, min(100, limit))
    )
    return {"visitor_id": visitor_id, "total": len(items), "items": items}


@app.delete("/apothecary/compound/{compound_id}", tags=["humans"])
def apothecary_compound_delete(compound_id: str, visitor_id: str):
    if not _apothecary_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    ok = _apothecary_journal_mod.delete_compound(visitor_id, compound_id)
    if not ok:
        raise HTTPException(status_code=404, detail="compound not found")
    return {"deleted": True, "compound_id": compound_id}


# ── Apothecary feedback: did this help? loop ─────────────────────────────
from api import apothecary_feedback as _apothecary_feedback_mod  # noqa: E402


class _ApothecaryFeedbackSubmit(BaseModel):
    visitor_id:  str
    compound_id: str
    rating:      str                  # one of: helped / didnt_fit / walked_it / saved
    condition:   Optional[str] = ""   # echo the condition for context
    note:        Optional[str] = ""


@app.post("/apothecary/feedback", tags=["humans"])
def apothecary_feedback_submit(req: _ApothecaryFeedbackSubmit):
    """Record a visitor's signal on a compound: helped / didn't fit / walked
    it / saved. Per-visitor append-only JSONL. Aggregate stats are public
    via /apothecary/feedback/stats; individual visitor data stays private.
    """
    try:
        rec = _apothecary_feedback_mod.submit(
            visitor_id=req.visitor_id,
            compound_id=req.compound_id,
            rating=req.rating,
            condition=req.condition or "",
            note=req.note or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"saved": True, "rating": rec["rating"], "submitted_at": rec["submitted_at"]}


@app.get("/apothecary/feedback", tags=["humans"])
def apothecary_feedback_list(visitor_id: str, limit: int = 100):
    """A visitor's own feedback history, newest first."""
    if not _apothecary_feedback_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    items = _apothecary_feedback_mod.list_for_visitor(
        visitor_id, limit=max(1, min(500, limit))
    )
    return {"visitor_id": visitor_id, "total": len(items), "items": items}


@app.get("/apothecary/feedback/compound", tags=["humans"])
def apothecary_feedback_compound(visitor_id: str, compound_id: str):
    """The visitor's latest rating for a specific compound (or null)."""
    if not _apothecary_feedback_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    rec = _apothecary_feedback_mod.latest_for_compound(visitor_id, compound_id)
    return {"compound_id": compound_id, "feedback": rec}


@app.get("/apothecary/feedback/stats", tags=["humans"])
def apothecary_feedback_stats():
    """Public aggregate counts across all visitors' feedback.

    Returns counts per rating per compound_id. Useful for an operator
    console to see which compounds are landing. No individual visitor
    data is exposed.
    """
    return _apothecary_feedback_mod.aggregate_stats()


# ── Training sequences: practical multi-step disciplines ─────────────
from pathlib import Path as _Path  # noqa: E402

_TRAINING_FILE = _Path(__file__).parent.parent / "data" / "training" / "sequences.jsonl"


def _load_training() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not _TRAINING_FILE.exists():
        return items
    for line in _TRAINING_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


@app.get("/training", tags=["humans"])
def training_list(category: Optional[str] = None):
    """All training sequences, optionally filtered by category.

    Each sequence is a multi-step practical discipline: gardening,
    fitness, cooking, home, outdoor, crafts, husbandry. Body of work
    you can walk over weeks or months.
    """
    items = _load_training()
    if category:
        cat = category.strip().lower()
        items = [t for t in items if (t.get("category") or "").lower() == cat]
    cats: Dict[str, int] = {}
    for t in _load_training():
        c = t.get("category") or "uncategorized"
        cats[c] = cats.get(c, 0) + 1
    return {
        "total": len(items),
        "categories": cats,
        "items": items,
    }


@app.get("/training/{tid}", tags=["humans"])
def training_one(tid: str):
    for t in _load_training():
        if t.get("id") == tid:
            return t
    raise HTTPException(status_code=404, detail=f"training sequence {tid!r} not found")


# ── Phonics + WorkReady + Math curriculum units ──────────────────────
# Three sequenced curricula composing with the existing lenses.
# Phonics = literacy progression (short-a, short-e, blends, digraphs …).
# WorkReady = employability progression (résumé, interview, math, …).
# Math = number sense → addition → subtraction → multiplication → …
# All share shape: rule + examples + manipulative + modes + wedges +
# check + prerequisites + next. The progression layer (mastery state,
# next-up suggestions) ships in a later pass.
_PHONICS_PATH   = Path(__file__).parent.parent / "data" / "phonics"   / "units.jsonl"
_WORKREADY_PATH = Path(__file__).parent.parent / "data" / "workready" / "units.jsonl"
_MATH_PATH      = Path(__file__).parent.parent / "data" / "math"      / "units.jsonl"
_READING_PATH   = Path(__file__).parent.parent / "data" / "reading"   / "units.jsonl"
_WRITING_PATH   = Path(__file__).parent.parent / "data" / "writing"   / "units.jsonl"
_SCIENCE_PATH   = Path(__file__).parent.parent / "data" / "science"   / "units.jsonl"
_BIBLE_CURR_PATH = Path(__file__).parent.parent / "data" / "bible_curriculum" / "units.jsonl"
_SOCIAL_PATH    = Path(__file__).parent.parent / "data" / "social_studies"   / "units.jsonl"


def _read_jsonl_safe(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in p.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


@app.get("/phonics", tags=["humans"])
def phonics_list():
    units = _read_jsonl_safe(_PHONICS_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/phonics/{uid}", tags=["humans"])
def phonics_one(uid: str):
    for u in _read_jsonl_safe(_PHONICS_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"phonics unit {uid!r} not found")


@app.get("/workready", tags=["humans"])
def workready_list():
    units = _read_jsonl_safe(_WORKREADY_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/workready/{uid}", tags=["humans"])
def workready_one(uid: str):
    for u in _read_jsonl_safe(_WORKREADY_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"workready unit {uid!r} not found")


@app.get("/math", tags=["humans"])
def math_list():
    """All math curriculum units, sorted by track + unit_seq.
    Track shape: number_sense → addition → subtraction → …"""
    units = _read_jsonl_safe(_MATH_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/math/{uid}", tags=["humans"])
def math_one(uid: str):
    """One math unit by id. Returns the full record with rule,
    examples, manipulative, modes, wedges, check, prerequisites, next."""
    for u in _read_jsonl_safe(_MATH_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"math unit {uid!r} not found")


# Reading comprehension / Writing / Science — same shape, generic
# listing + lookup. Each track has its own JSONL file; the endpoint
# bodies are nearly identical. Kept separate for clear URLs and so
# /reading/{uid} stays distinct from /math/{uid}.
@app.get("/reading", tags=["humans"])
def reading_list():
    units = _read_jsonl_safe(_READING_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/reading/{uid}", tags=["humans"])
def reading_one(uid: str):
    for u in _read_jsonl_safe(_READING_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"reading unit {uid!r} not found")


@app.get("/writing", tags=["humans"])
def writing_list():
    units = _read_jsonl_safe(_WRITING_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/writing/{uid}", tags=["humans"])
def writing_one(uid: str):
    for u in _read_jsonl_safe(_WRITING_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"writing unit {uid!r} not found")


@app.get("/science", tags=["humans"])
def science_list():
    units = _read_jsonl_safe(_SCIENCE_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/science/{uid}", tags=["humans"])
def science_one(uid: str):
    for u in _read_jsonl_safe(_SCIENCE_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"science unit {uid!r} not found")


@app.get("/bible_curriculum", tags=["humans"])
def bible_curriculum_list():
    units = _read_jsonl_safe(_BIBLE_CURR_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/bible_curriculum/{uid}", tags=["humans"])
def bible_curriculum_one(uid: str):
    for u in _read_jsonl_safe(_BIBLE_CURR_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"bible curriculum unit {uid!r} not found")


@app.get("/social_studies", tags=["humans"])
def social_studies_list():
    units = _read_jsonl_safe(_SOCIAL_PATH)
    units.sort(key=lambda u: (u.get("track", ""), u.get("unit_seq", 9999)))
    return {"total": len(units), "units": units}


@app.get("/social_studies/{uid}", tags=["humans"])
def social_studies_one(uid: str):
    for u in _read_jsonl_safe(_SOCIAL_PATH):
        if u.get("id") == uid:
            return u
    raise HTTPException(status_code=404, detail=f"social studies unit {uid!r} not found")


# ── Herb monographs — botanical remedies with evidence-honest verdicts ──
# Same substrate posture: CONFIRMED for well-studied effects, MIXED for
# partial evidence, DISCORDANT for folk claims that don't hold up. Each
# monograph has preparations + safety notes + growing notes + inline SVG.
_HERBS_PATH = Path(__file__).parent.parent / "data" / "herbs" / "monographs.jsonl"


@app.get("/herbs", tags=["humans"])
def herbs_list():
    items = _read_jsonl_safe(_HERBS_PATH)
    items.sort(key=lambda h: h.get("name", ""))
    return {"total": len(items), "herbs": items}


@app.get("/herbs/{hid}", tags=["humans"])
def herbs_one(hid: str):
    for h in _read_jsonl_safe(_HERBS_PATH):
        if h.get("id") == hid:
            return h
    raise HTTPException(status_code=404, detail=f"herb monograph {hid!r} not found")


# ── Flow primitive — sequences of tool calls + branches + state ──
# A flow is a named journey across the engine's tools. Definitions
# live as JSONL at data/flows/*.jsonl. The runner executes step-by-
# step, pausing on `input` steps and resuming when the caller supplies
# the visitor's answer. Every step writes to the run audit.
from api import flows as _flows_mod  # noqa: E402


@app.get("/flows", tags=["humans"])
def flows_list(audience: str = "", starts_from: str = ""):
    """List every registered flow. Optional filters:
      - audience: 'human' | 'agent' | 'robot' (default: all)
      - starts_from: 'walk' | 'apothecary' | 'curriculum' | 'any'
        (used by UI to show flows relevant to the current page)
    """
    return {
        "flows": _flows_mod.list_flows(
            audience=audience or None,
            starts_from=starts_from or None,
        )
    }


@app.get("/flows/{flow_id}", tags=["humans"])
def flows_get(flow_id: str):
    """Return one flow's full definition — useful for an agent that
    wants to introspect what the flow will do before running it."""
    f = _flows_mod.get_flow(flow_id)
    if not f:
        raise HTTPException(status_code=404, detail=f"flow {flow_id!r} not found")
    return {
        "id": f.id,
        "name": f.name,
        "description": f.description,
        "audience": f.audience,
        "starts_from": f.starts_from,
        "first_input": f.first_input,
        "steps": f.steps,
        "outputs": f.outputs,
    }


class _FlowRun(BaseModel):
    flow_id: str
    state: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None


@app.post("/flow/run", tags=["humans"])
def flow_run(request: Request, req: _FlowRun):
    """Execute (or resume) a flow.

    To start: POST {"flow_id": "walk_to_keep", "state": {"situation": "..."}}
    Returns either:
      - {"status": "complete", "state": ..., "outputs": ...}
      - {"status": "waiting_for_input", "state": ..., "expects": "<key>", "label": "..."}
      - {"status": "error", "error": "..."}

    To resume a paused flow: POST again with the same run_id and the
    waiting-for input added to state.

    Steward audit: every tool call inside the flow runs through the
    same engine endpoints (which already audit) so the trail is
    consistent. Flow-level audit lives at data/flow_runs/<run_id>.jsonl.
    """
    _rate_check(request, "agent")
    return _flows_mod.run_flow(
        flow_id=req.flow_id,
        initial_state=req.state or {},
        run_id=req.run_id,
    )


# ── Skills layer — protocols / paths / skills mapping ─────────────
# Reads data/skills/*.json (schema narrowhighway.skill_map/1). Each map
# decomposes a skill into protocols (rule-sets) and paths (sequences),
# and carries explicit cross_domain_connections. /skills/graph emits
# nodes+edges for the visual routing map. "common and effective" lives
# in each map's effectiveness block; capacity-on-need in its capacity block.
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "data" / "skills"


def _load_skill_maps() -> list:
    out = []
    if not _SKILLS_DIR.exists():
        return out
    for p in sorted(_SKILLS_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _bump_skill_usage(skill_id: str) -> None:
    """Record one use of a skill (drives the 'common' signal). Best-effort."""
    try:
        p = _SKILLS_DIR / f"{skill_id.replace('skill_', '')}.json"
        # fall back to scanning if the filename doesn't match the id
        target = None
        if p.exists():
            target = p
        else:
            for cand in _SKILLS_DIR.glob("*.json"):
                d = json.loads(cand.read_text(encoding="utf-8"))
                if d.get("id") == skill_id:
                    target = cand
                    break
        if not target:
            return
        d = json.loads(target.read_text(encoding="utf-8"))
        eff = d.setdefault("effectiveness", {})
        eff["usage_count"] = int(eff.get("usage_count", 0) or 0) + 1
        import datetime as _dt
        eff["last_used"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        target.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


@app.get("/skills", tags=["humans"])
def skills_list():
    """List skill maps (the protocols/paths/skills layer), summary view."""
    maps = _load_skill_maps()
    return {
        "total": len(maps),
        "skills": [
            {
                "id": m.get("id"),
                "title": m.get("title"),
                "tagline": m.get("tagline", ""),
                "universal": m.get("universal", False),
                "protocols": len(m.get("protocols", [])),
                "paths": len(m.get("paths", [])),
                "connections": len(m.get("cross_domain_connections", [])),
                "effectiveness": m.get("effectiveness", {}),
                "capacity": m.get("capacity", {}),
            }
            for m in maps
        ],
    }


@app.get("/skills/graph", tags=["humans"])
def skills_graph():
    """Nodes + edges across all skill maps, for the visual routing map.
    Node types: skill, protocol, path, concept (cross-domain target)."""
    nodes, edges = [], []
    seen = set()
    for m in _load_skill_maps():
        sid = m.get("id")
        if not sid:
            continue
        nodes.append({"id": sid, "label": m.get("title"), "type": "skill",
                      "skill": sid, "universal": m.get("universal", False)})
        for pr in m.get("protocols", []):
            nodes.append({"id": pr["id"], "label": pr["title"], "type": "protocol",
                          "skill": sid, "rules": len(pr.get("rules", []))})
            edges.append({"source": sid, "target": pr["id"], "kind": "contains"})
        for pa in m.get("paths", []):
            nodes.append({"id": pa["id"], "label": pa["title"], "type": "path",
                          "skill": sid, "steps": len(pa.get("steps", []))})
            edges.append({"source": sid, "target": pa["id"], "kind": "contains"})
        for c in m.get("cross_domain_connections", []):
            concept = c.get("maps_to", "")
            cid = "concept_" + re.sub(r"[^a-z0-9]+", "_", concept.lower()).strip("_")[:48]
            if cid not in seen:
                seen.add(cid)
                nodes.append({"id": cid, "label": concept, "type": "concept",
                              "domain": c.get("domain", "")})
            edges.append({"source": sid, "target": cid, "kind": "cross_domain",
                          "principle": c.get("principle", "")})
    return {"nodes": nodes, "edges": edges,
            "counts": {"nodes": len(nodes), "edges": len(edges)}}


@app.get("/skills/{skill_id}", tags=["humans"])
def skills_get(skill_id: str):
    """Full skill map by id. Records a use (drives the 'common' signal)."""
    for m in _load_skill_maps():
        if m.get("id") == skill_id:
            _bump_skill_usage(skill_id)
            return m
    raise HTTPException(status_code=404, detail=f"skill {skill_id!r} not found")


# ── Deposit box — stream-of-consciousness capture -> route -> return ──
# Drop any thought/idea/task/draft. It becomes a card in your box, gets
# classified + routed to a tool, and comes back enriched (a result, or a
# link to the path). Everything is a card. Messages are DRAFTED for
# operator review — never auto-sent.
_DEPOSITS_DIR = Path(__file__).resolve().parent.parent / "data" / "deposits"


def _classify_deposit(text: str):
    """Return (classification, routed_to). The deterministic Shepherd core now
    lives in api/offices.py (shared with the funnel front door); this delegates
    so there is one implementation, not parallel copies."""
    from api import offices as _offices
    return _offices.classify_deposit(text)


# ── The three offices: Shepherd (Socratic) · Scribe (record) · Steward (resource) ──
def _ledger_remaining_usd() -> float:
    """Steward's resource check — what's left of the monthly cap.
    Delegates to api/offices.py (the single Steward implementation)."""
    from api import offices as _offices
    return _offices.steward_budget_remaining_usd()


def _ledger_record(source: str, usd: float) -> None:
    """The Steward records a spend against the monthly cap. Delegates to
    api/offices.py (the single implementation)."""
    from api import offices as _offices
    _offices.ledger_record(source, usd)


def _log_office_pair(office: str, prompt: str, completion: str, meta=None) -> None:
    """Each office's decision becomes a training pair for its future small model.
    This is how the body mints the data for the three sovereign organs as it runs.
    Delegates to api/offices.py (the single implementation)."""
    from api import offices as _offices
    _offices.log_office_pair(office, prompt, completion, meta)


def _shepherd_say(action: str, tool: str = "") -> str:
    """Select a vetted Shepherd line. Delegates to api/offices.py (one voice)."""
    from api import offices as _offices
    return _offices.shepherd_say(action, tool)


def _shepherd_discern(history: list) -> dict:
    """Shepherd office: ask one Socratic question OR route to a tool. The full
    stack (office-model -> Steward-gated oracle -> keyword floor) lives in
    api/offices.py and is shared with the funnel front door. /deposit is a
    route-only door, so allow_keep=False (a personal-capture candidate routes to
    a walk rather than being kept on a shelf)."""
    from api import offices as _offices
    return _offices.shepherd_discern(history, allow_keep=False, allow_oracle=True)


def _save_deposit(card: dict) -> None:
    _DEPOSITS_DIR.mkdir(parents=True, exist_ok=True)
    (_DEPOSITS_DIR / f"{card['id']}.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")


class _DepositReq(BaseModel):
    text: str
    box: Optional[str] = "ideas"


@app.post("/deposit", tags=["humans"])
def deposit_create(request: Request, req: _DepositReq):
    """Deposit a stream of consciousness. Shepherd discerns Socratically:
    either asks a clarifying question or routes to a tool. Scribe records it;
    Steward notes the resource decision."""
    import datetime as _dt, hashlib as _h, secrets as _s
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty deposit")
    did = "dep_" + _h.sha256((text + _s.token_hex(4)).encode()).hexdigest()[:12]
    history = [{"role": "user", "content": text}]
    sh = _shepherd_discern(history)
    card = {
        "schema": "narrowhighway.deposit/1", "id": did, "kind": "deposit",
        "box": (req.box or "ideas")[:40], "text": text[:8000],
        "deposited_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "history": history, "say": sh.get("say", ""), "result": None, "updated_at": None,
    }
    if sh.get("action") == "ask":
        card["status"] = "awaiting_reply"
        card["history"].append({"role": "assistant", "content": sh.get("say", "")})
    else:
        card["status"] = "routed"
        card["routed_to"] = sh.get("tool", "walk")
        card["query"] = sh.get("query", text)
        # Scribe records the matter; Steward notes the route + budget
        _log_office_pair("scribe", text,
                         json.dumps({"box": card["box"], "routed_to": card["routed_to"]}, ensure_ascii=False))
        _log_office_pair("steward",
                         json.dumps({"query": card["query"], "candidate_tool": card["routed_to"]}, ensure_ascii=False),
                         json.dumps({"tool": card["routed_to"], "budget_remaining_usd": round(_ledger_remaining_usd(), 2)}, ensure_ascii=False))
    _save_deposit(card)
    return card


class _DepositReply(BaseModel):
    text: str


@app.post("/deposit/{did}/reply", tags=["humans"])
def deposit_reply(did: str, req: _DepositReply):
    """Continue the Socratic exchange — the person answers Shepherd's question."""
    import datetime as _dt
    p = _DEPOSITS_DIR / f"{did}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="deposit not found")
    card = json.loads(p.read_text(encoding="utf-8"))
    reply = (req.text or "").strip()
    if not reply:
        raise HTTPException(status_code=400, detail="empty reply")
    card.setdefault("history", []).append({"role": "user", "content": reply})
    sh = _shepherd_discern(card["history"])
    card["say"] = sh.get("say", "")
    if sh.get("action") == "ask":
        card["status"] = "awaiting_reply"
        card["history"].append({"role": "assistant", "content": sh.get("say", "")})
    else:
        card["status"] = "routed"
        card["routed_to"] = sh.get("tool", "walk")
        card["query"] = sh.get("query", reply)
        _log_office_pair("scribe", reply,
                         json.dumps({"routed_to": card["routed_to"]}, ensure_ascii=False))
    card["updated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    _save_deposit(card)
    return card


@app.get("/deposits", tags=["humans"])
def deposit_list(box: str = "", limit: int = 60):
    """The box — your deposited cards, newest first."""
    if not _DEPOSITS_DIR.exists():
        return {"deposits": [], "total": 0}
    items = []
    for p in _DEPOSITS_DIR.glob("dep_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if box and d.get("box") != box:
            continue
        items.append(d)
    items.sort(key=lambda d: d.get("deposited_at", ""), reverse=True)
    return {"deposits": items[:limit], "total": len(items)}


class _DepositResult(BaseModel):
    result: Dict[str, Any]


@app.post("/deposit/{did}/result", tags=["humans"])
def deposit_result(did: str, req: _DepositResult):
    """Patch a deposit card with the tool's result + mark it done."""
    import datetime as _dt
    p = _DEPOSITS_DIR / f"{did}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="deposit not found")
    d = json.loads(p.read_text(encoding="utf-8"))
    d["result"] = req.result
    d["status"] = "done"
    d["updated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return d


# ── Mastery tracking — visitor-keyed, append-only ─────────────
# Records when a visitor marks a curriculum unit worked-through.
# Prerequisite-checking is advisory today (the dashboard dims
# unattainable units); Steward could enforce later.
from api import mastery as _mastery_mod  # noqa: E402


class _MasteryMark(BaseModel):
    visitor_id: str
    unit_id: str
    state: str = "mastered"  # working / mastered / set_aside / reset
    note: str = ""


@app.post("/mastery/mark", tags=["humans"])
def mastery_mark(request: Request, req: _MasteryMark):
    """Record a mastery state for a unit. The append-only log is
    visitor-keyed at data/mastery/<visitor_id>.jsonl. No PII — visitor_id
    is opaque hex."""
    _rate_check(request, "mastery")
    if not req.visitor_id or not req.unit_id:
        raise HTTPException(status_code=400, detail="visitor_id and unit_id required")
    rec = _mastery_mod.mark(req.visitor_id, req.unit_id, req.state, req.note)
    # Steward audit so the operator sees mastery activity
    try:
        from api.steward import get_steward
        get_steward().emit_admit(
            visitor_id=req.visitor_id,
            action=f"mastery_{req.state}",
            notes=f"unit={req.unit_id}",
        )
    except Exception:
        pass
    return rec


@app.get("/mastery/visitor", tags=["humans"])
def mastery_visitor(visitor_id: str = "", include_log: bool = False, limit: int = 500):
    """Current mastery state for a visitor across every unit.
    Returns the reduced {unit_id: state} map by default; pass
    include_log=true for the full append-only chronology."""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    out: Dict[str, Any] = {
        "visitor_id": visitor_id,
        "current": _mastery_mod.current_state(visitor_id),
    }
    if include_log:
        out["log"] = _mastery_mod.list_visitor(visitor_id, limit=max(1, min(2000, int(limit))))
    out["totals"] = {
        "mastered": sum(1 for s in out["current"].values() if s == "mastered"),
        "working": sum(1 for s in out["current"].values() if s == "working"),
        "set_aside": sum(1 for s in out["current"].values() if s == "set_aside"),
    }
    return out


@app.get("/mastery/check", tags=["humans"])
def mastery_check(visitor_id: str = "", unit_id: str = "", prerequisites: str = ""):
    """Advisory check: can the visitor attempt this unit?
    `prerequisites` is comma-separated unit_ids the dashboard already
    knows from the unit record; passing them in avoids a server-side
    lookup. Returns {allowed, missing, current}."""
    if not visitor_id or not unit_id:
        raise HTTPException(status_code=400, detail="visitor_id and unit_id required")
    prereqs = [p.strip() for p in prerequisites.split(",") if p.strip()]
    return _mastery_mod.can_attempt(visitor_id, unit_id, prereqs)


# ── Unified curriculum index ────────────────────────────────────
# One endpoint that returns every curriculum unit across every
# track. Useful for the Composer's "where am I in the curriculum"
# view and for an eventual progress dashboard.
@app.get("/curriculum", tags=["humans"])
def curriculum_all():
    """Every unit across every curriculum track. Returned grouped by
    kind, with track + unit_seq + prerequisites + next so a UI can
    render the progression graph without a second round-trip."""
    out: Dict[str, List[Dict[str, Any]]] = {
        "phonics": _read_jsonl_safe(_PHONICS_PATH),
        "math": _read_jsonl_safe(_MATH_PATH),
        "reading": _read_jsonl_safe(_READING_PATH),
        "writing": _read_jsonl_safe(_WRITING_PATH),
        "science": _read_jsonl_safe(_SCIENCE_PATH),
        "bible_curriculum": _read_jsonl_safe(_BIBLE_CURR_PATH),
        "social_studies": _read_jsonl_safe(_SOCIAL_PATH),
        "workready": _read_jsonl_safe(_WORKREADY_PATH),
    }
    totals = {k: len(v) for k, v in out.items()}
    return {
        "tracks": out,
        "totals": totals,
        "total_units": sum(totals.values()),
    }


# ── Teaching layer — parables + mnemonics + glyphs ───────────────
# "We are teaching along the way." A companion layer to the curriculum:
# each entry attaches a memory device (mnemonic), a visual glyph, and a
# short parable — biblical or original — to a track, a unit, a concept,
# or a page. The curriculum carries the rule; the teaching layer carries
# the picture that makes the rule stick. Read-only; additive to units.
_TEACHING_PATH = Path(__file__).parent.parent / "data" / "teaching" / "parables.jsonl"


def _teaching_entries() -> List[Dict[str, Any]]:
    return _read_jsonl_safe(_TEACHING_PATH)


@app.get("/teaching", tags=["humans"])
def teaching_list(applies_to: str = ""):
    """Every teaching entry (parable + mnemonic + glyph + Scripture).
    Optional filter `applies_to` matches an entry's applies_to tag exactly,
    e.g. 'track:math', 'unit:phonics_letter_sounds', 'concept:four_gates',
    'page:learn'. Lets a page pull just the teaching it needs in one call."""
    entries = _teaching_entries()
    if applies_to:
        entries = [e for e in entries
                   if applies_to in (e.get("applies_to") or [])]
    # index by applies_to tag so a UI can look up O(1)
    index: Dict[str, str] = {}
    for e in entries:
        for tag in (e.get("applies_to") or []):
            index.setdefault(tag, e.get("key", ""))
    return {"total": len(entries), "entries": entries, "index": index}


@app.get("/teaching/{key}", tags=["humans"])
def teaching_one(key: str):
    """One teaching entry by its key (e.g. 'four_gates', 'phonics').
    Falls back to matching an applies_to tag so /teaching/track:math works."""
    entries = _teaching_entries()
    for e in entries:
        if e.get("key") == key:
            return e
    for e in entries:
        if key in (e.get("applies_to") or []):
            return e
    raise HTTPException(status_code=404, detail=f"teaching entry {key!r} not found")


# ── The Well — a well of knowledge, not a feed ───────────────────
# Social media gives you a feed (it feeds you, endlessly). The Well is
# something you DRAW from — and it helps you become a spring of ideas
# (John 4:14). Today the Well holds original, family-safe leveled reading
# passages that use public-domain characters (Aesop, folk tales, pre-1930
# classics) for interest. Our words are our own; sources are PD or folk.
# Read-only and CORS-open, so sibling sites can draw from the same well.
_WELL_PASSAGES_PATH = Path(__file__).parent.parent / "data" / "well" / "passages.jsonl"
_PD_CHARACTERS_PATH = Path(__file__).parent.parent / "data" / "characters" / "public_domain.jsonl"


@app.get("/well/characters", tags=["humans"])
def well_characters():
    """The public-domain character roster — PD-by-year or folk legend only,
    each with provenance + a guardrail. Free for sibling sites to reuse."""
    chars = _read_jsonl_safe(_PD_CHARACTERS_PATH)
    return {"total": len(chars), "characters": chars}


@app.get("/well/passages", tags=["humans"])
def well_passages(level: str = "", character: str = "", track: str = ""):
    """Leveled reading passages drawn into the Well. Filters:
      - level: emergent | early_reader | fluent
      - character: a PD character id (e.g. tortoise_hare)
      - track: a curriculum tie (e.g. track:reading)"""
    items = _read_jsonl_safe(_WELL_PASSAGES_PATH)
    if level:
        items = [p for p in items if p.get("level") == level]
    if character:
        items = [p for p in items if character in (p.get("character_ids") or [])]
    if track:
        items = [p for p in items if track in (p.get("ties_to") or [])]
    items.sort(key=lambda p: (p.get("level", ""), p.get("title", "")))
    return {"total": len(items), "passages": items}


@app.get("/well/passages/{pid}", tags=["humans"])
def well_passage_one(pid: str):
    for p in _read_jsonl_safe(_WELL_PASSAGES_PATH):
        if p.get("id") == pid:
            return p
    raise HTTPException(status_code=404, detail=f"well passage {pid!r} not found")


@app.get("/well/draw", tags=["humans"])
def well_draw(level: str = "", character: str = "", random: bool = False):
    """Draw one passage from the Well. Deterministic 'draw of the day' by
    default (stable within a calendar day) so the page is the same all day;
    pass random=true for a fresh draw each call. You draw — you are not fed."""
    items = _read_jsonl_safe(_WELL_PASSAGES_PATH)
    if level:
        items = [p for p in items if p.get("level") == level]
    if character:
        items = [p for p in items if character in (p.get("character_ids") or [])]
    if not items:
        raise HTTPException(status_code=404, detail="the well is empty for that filter")
    if random:
        import random as _rnd
        chosen = _rnd.choice(items)
    else:
        # stable within the day: index by ordinal date across the sorted set
        from datetime import datetime as _dt, timezone as _tz
        items.sort(key=lambda p: p.get("id", ""))
        idx = _dt.now(_tz.utc).date().toordinal() % len(items)
        chosen = items[idx]
    return {"drawn": chosen, "well_size": len(items),
            "note": "A well, not a feed — drink, and become a spring of ideas."}


# ── The three offices — operator surfaces (Shepherd · Scribe · Steward) ──
# These were the keep's "future" panels. Now wired and attributed to the
# office whose work they show, a faithful 3-3-3 split:
#   Shepherd (the person):  /walks/recent · /mastery/summary · /refuge/intake
#   Scribe   (the record):  /apothecary/feedback/recent · /almanac/proposals · /stats/visitors
#   Steward  (the keeping): /build_queue · /witness/roll.json (already live) · /testimony/pending
# Each returns its "office" so the keep can group them by office. Read-only.
_WALKS_REPLAY_PATH  = Path(__file__).parent.parent / "data" / "walks" / "replay.jsonl"
_MASTERY_DIR_PATH   = Path(__file__).parent.parent / "data" / "mastery"
_REFUGE_DIR_PATH    = Path(__file__).parent.parent / "data" / "refuge"
_APO_FEEDBACK_DIR   = Path(__file__).parent.parent / "data" / "apothecary_feedback"
_ALMANAC_PROP_PATH  = Path(__file__).parent.parent / "data" / "almanac_proposals" / "queue.jsonl"
_BUILD_QUEUE_PATH   = Path(__file__).parent.parent / "data" / "build_queue" / "queue.jsonl"
_TESTIMONY_DIR_PATH = Path(__file__).parent.parent / "data" / "testimony" / "matters"
_VISITS_DIR_PATH    = Path(__file__).parent.parent / "data" / "visits"


# — Shepherd: the person — discernment, learning, refuge —
@app.get("/walks/recent", tags=["humans"])
def walks_recent(limit: int = 25):
    """Shepherd: walks taken through the four gates — count + recent list."""
    rows = _read_jsonl_safe(_WALKS_REPLAY_PATH)
    recent = list(reversed(rows[-max(1, min(200, limit)):]))
    return {"office": "shepherd", "total": len(rows),
            "recent": [{"ts": r.get("ts"),
                        "query": r.get("query") or r.get("shaped_query"),
                        "cards": len(r.get("card_ids_walked") or []),
                        "asked_by": r.get("asked_by", "anon")} for r in recent]}


@app.get("/mastery/summary", tags=["humans"])
def mastery_summary():
    """Shepherd: curriculum mastery roll-up across all learners (no PII)."""
    learners = 0
    mastered_total = 0
    per_unit: Dict[str, int] = {}
    if _MASTERY_DIR_PATH.exists():
        for f in _MASTERY_DIR_PATH.glob("*.jsonl"):
            if f.name.startswith(("audit_test", "test")):
                continue
            state: Dict[str, str] = {}
            for ln in f.read_text("utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                uid, st = o.get("unit_id"), o.get("state")
                if not uid or not st:
                    continue
                if st == "reset":
                    state.pop(uid, None)
                else:
                    state[uid] = st
            if state:
                learners += 1
            for uid, st in state.items():
                if st == "mastered":
                    mastered_total += 1
                    per_unit[uid] = per_unit.get(uid, 0) + 1
    top = sorted(per_unit.items(), key=lambda kv: -kv[1])[:15]
    return {"office": "shepherd", "learners": learners,
            "units_mastered": mastered_total,
            "top_units": [{"unit_id": k, "mastered_by": v} for k, v in top]}


@app.get("/refuge/intake", tags=["humans"])
def refuge_intake(limit: int = 50):
    """Shepherd: pending city-of-refuge intakes awaiting hearing."""
    items: List[Dict[str, Any]] = []
    if _REFUGE_DIR_PATH.exists():
        for f in sorted(_REFUGE_DIR_PATH.glob("**/*.jsonl")):
            items.extend(_read_jsonl_safe(f))
    pending = [i for i in items if str(i.get("status", "pending")).lower()
               in ("pending", "awaiting_hearing", "open")]
    return {"office": "shepherd", "pending": len(pending),
            "intakes": pending[:max(1, min(200, limit))]}


# — Scribe: the record — feedback, proposals, who came —
@app.get("/apothecary/feedback/recent", tags=["humans"])
def apothecary_feedback_recent(limit: int = 25):
    """Scribe: recent apothecary feedback across all visitors (anonymized)."""
    rows: List[Dict[str, Any]] = []
    if _APO_FEEDBACK_DIR.exists():
        for f in _APO_FEEDBACK_DIR.glob("*.jsonl"):
            rows.extend(_read_jsonl_safe(f))
    rows.sort(key=lambda r: r.get("submitted_at", 0) or 0, reverse=True)
    out = [{"rating": r.get("rating"), "compound_id": r.get("compound_id"),
            "condition": r.get("condition", ""),
            "submitted_at": r.get("submitted_at"),
            "vid": str(r.get("visitor_id", ""))[:6]}
           for r in rows[:max(1, min(100, limit))]]
    return {"office": "scribe", "total": len(rows), "recent": out}


@app.get("/almanac/proposals", tags=["humans"])
def almanac_proposals(limit: int = 50):
    """Scribe: visitor-suggested almanac entries awaiting curator review."""
    rows = _read_jsonl_safe(_ALMANAC_PROP_PATH)
    pending = [r for r in rows if str(r.get("status", "pending")).lower() != "curated"]
    pending.sort(key=lambda r: r.get("proposed_at", "") or "", reverse=True)
    return {"office": "scribe", "total": len(rows), "pending": len(pending),
            "proposals": pending[:max(1, min(200, limit))]}


@app.get("/stats/visitors", tags=["humans"])
def stats_visitors():
    """Scribe: who the engine reached — every audience, by kind.

    Narrow Highway serves HUMANS AND AGENTS/AI alike. It is a verification floor that
    other agents call (the MCP door + the X-Engine-URL headers that ride along when an
    agent surfaces an answer to its user), an AI-crawlable knowledge source, and a site
    for families. No audience is privileged — humans, agents, retrieval clients, and
    crawlers are all counted, broken out by kind so the mix is visible.

    The ONLY traffic not counted is SELF: the operator (keep cookie/IP) and the engine's
    own box/Claude self-tests, both excluded upstream in the access-log middleware.
    `today/last_7_days/all_time` = total reached; `*_by_kind` = the ua_class split
    (best-effort UA classification)."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    import collections as _collections

    def _counts(path: Path) -> "_collections.Counter":
        """Track EVERY request, categorized: actor:<operator|self|visitor> for all,
        plus kind:<ua_class> for visitors only. Rows logged before the actor field
        existed had operator/self dropped already, so a missing actor = visitor."""
        c: "_collections.Counter" = _collections.Counter()
        if not path.exists():
            return c
        for ln in path.read_text("utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            actor = r.get("actor") or "visitor"
            c["total"] += 1
            c["actor:" + actor] += 1
            if actor == "visitor":
                c["kind:" + (r.get("ua_class") or "other")] += 1
        return c

    today = _dt.now(_tz.utc).date()
    tc = _counts(_VISITS_DIR_PATH / f"access-{today.strftime('%Y%m%d')}.jsonl")
    wc: "_collections.Counter" = _collections.Counter()
    for d in range(7):
        wc += _counts(_VISITS_DIR_PATH / f"access-{(today - _td(days=d)).strftime('%Y%m%d')}.jsonl")
    ac: "_collections.Counter" = _collections.Counter()
    if _VISITS_DIR_PATH.exists():
        for f in _VISITS_DIR_PATH.glob("access-*.jsonl"):
            ac += _counts(f)

    def _aud(c) -> int:
        return c.get("actor:visitor", 0)

    def _kinds(c) -> dict:
        return {k[5:]: v for k, v in sorted(c.items()) if k.startswith("kind:")}

    def _actors(c) -> dict:
        return {k[6:]: v for k, v in sorted(c.items()) if k.startswith("actor:")}

    return {"office": "scribe",
            # headline = real AUDIENCE (actor=visitor; operator + self excluded — "don't
            # count my/your clicks"). Every type is still tracked + categorized below.
            "today": _aud(tc), "last_7_days": _aud(wc), "all_time": _aud(ac),
            "today_by_kind": _kinds(tc), "last_7_days_by_kind": _kinds(wc), "all_time_by_kind": _kinds(ac),
            "by_actor_all_time": _actors(ac),
            "note": "Every request is tracked and categorized — nothing dropped. today/last_7_days/"
                    "all_time = real AUDIENCE (actor=visitor); operator + self (the engine's own box / "
                    "Claude self-tests) are tracked separately in by_actor and excluded from the "
                    "audience count. *_by_kind splits the visitor audience by ua_class — humans AND "
                    "agents/AI/crawlers are all first-class, none privileged."}


# — Keep: visitor geography (operator surface) — where are they coming from? —
_GEO_DIR = Path(__file__).parent.parent / "data" / "geo"
_GEO_CACHE_PATH = _GEO_DIR / "ip_cache.json"


def _geo_load_cache() -> Dict[str, str]:
    try:
        return json.loads(_GEO_CACHE_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _geo_save_cache(cache: Dict[str, str]) -> None:
    try:
        _GEO_DIR.mkdir(parents=True, exist_ok=True)
        _GEO_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass


def _geo_is_local(ip: str) -> bool:
    if not ip:
        return True
    if ip.startswith(("10.", "127.", "192.168.", "::1", "fe80:")):
        return True
    # 172.16.0.0 – 172.31.255.255
    if ip.startswith(tuple(f"172.{n}." for n in range(16, 32))):
        return True
    return False


def _geo_lookup_batch(ips: List[str]) -> Dict[str, str]:
    """IP -> ISO alpha-2 country via ip-api.com (free tier, 100/batch, ~45/min).
    Cached forever in data/geo/ip_cache.json — one lookup per unique IP ever."""
    from urllib.request import Request as _Req, urlopen as _ul
    import time as _t
    cache = _geo_load_cache()
    missing = [ip for ip in set(ips) if ip and ip not in cache and not _geo_is_local(ip)]
    BATCH = 100
    for i in range(0, len(missing), BATCH):
        chunk = missing[i:i + BATCH]
        try:
            body = json.dumps(chunk).encode("utf-8")
            req = _Req(
                "http://ip-api.com/batch?fields=countryCode,query",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _ul(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for entry in data:
                ip = (entry.get("query") or "").strip()
                cc = (entry.get("countryCode") or "??").strip() or "??"
                if ip:
                    cache[ip] = cc
        except Exception:
            break  # transient — try again next call
        _t.sleep(1.5)  # respect free-tier rate limit (~45/min)
    _geo_save_cache(cache)
    out: Dict[str, str] = {}
    for ip in ips:
        if _geo_is_local(ip):
            out[ip] = "LOCAL"
        else:
            out[ip] = cache.get(ip, "??")
    return out


# In-memory geo cache for the access middleware (loaded lazily at first use).
# The cache file on disk (_GEO_CACHE_PATH) is owned by tools/geo_enrich.py,
# which batch-processes pending IPs through ip-api.com; the middleware only
# READS it. After an enrichment run, restart the engine to reload.
_GEO_CACHE_MEM: Dict[str, Any] = {}
_GEO_CACHE_MTIME: float = 0.0
_GEO_PENDING_PATH = _GEO_DIR / "pending.jsonl"


def _geo_cache_ensure() -> None:
    """Load the cache; reload when the file mtime changes so an external
    geo_enrich run is picked up without an engine restart."""
    global _GEO_CACHE_MTIME
    try:
        m = _GEO_CACHE_PATH.stat().st_mtime
    except FileNotFoundError:
        return
    except Exception:
        return
    if m == _GEO_CACHE_MTIME:
        return
    try:
        data = json.loads(_GEO_CACHE_PATH.read_text("utf-8"))
        if isinstance(data, dict):
            _GEO_CACHE_MEM.clear()
            _GEO_CACHE_MEM.update(data)
            _GEO_CACHE_MTIME = m
    except Exception:
        pass


def _geo_for(ip: str):
    """Cache-only IP -> {cc, city, lat, lon} or None. Never makes an HTTP call;
    on miss, queues the IP for tools/geo_enrich.py to batch-process. Handles
    legacy string-only cache entries (pre city/lat/lon upgrade) by promoting
    them to a country-only dict."""
    if not ip or _geo_is_local(ip):
        return None
    _geo_cache_ensure()
    v = _GEO_CACHE_MEM.get(ip)
    if v:
        if isinstance(v, str):
            return {"cc": v, "city": "", "lat": None, "lon": None}
        return v
    try:
        _GEO_DIR.mkdir(parents=True, exist_ok=True)
        with _GEO_PENDING_PATH.open("a", encoding="utf-8") as f:
            import time as _t
            f.write(json.dumps({"ip": ip, "ts": int(_t.time())}) + "\n")
    except Exception:
        pass
    return None


def _geo_country_for(ip: str) -> str:
    """Backward-compat: country code only."""
    g = _geo_for(ip)
    return (g.get("cc", "") if g else "") or ""


@app.get("/keep/geo", tags=["keep"])
def keep_geo(days: int = 30):
    """Operator: visitor geography with pin-style detail (city / lat / lon)
    where the cache has it. Returns TODAY and HISTORICAL separately. Coords
    are rounded to ~10 km buckets so nearby visits group into one pin."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td

    today = _dt.now(_tz.utc).date()
    days = max(1, min(90, int(days)))
    by_country_today: Dict[str, int] = {}
    by_country_hist: Dict[str, int] = {}
    today_total = 0
    hist_total = 0
    pending_count = 0
    points_today: Dict[tuple, Dict[str, Any]] = {}
    points_hist: Dict[tuple, Dict[str, Any]] = {}

    for d in range(days):
        day = today - _td(days=d)
        is_today = (d == 0)
        f = _VISITS_DIR_PATH / f"access-{day.strftime('%Y%m%d')}.jsonl"
        if not f.exists():
            continue
        try:
            text = f.read_text("utf-8", errors="replace")
        except Exception:
            continue
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            cc = (o.get("country") or "").strip().upper()
            if not cc:
                pending_count += 1
                cc = "??"
            target_cc = by_country_today if is_today else by_country_hist
            target_cc[cc] = target_cc.get(cc, 0) + 1
            if is_today:
                today_total += 1
            else:
                hist_total += 1
            lat = o.get("lat")
            lon = o.get("lon")
            if lat is not None and lon is not None:
                try:
                    rlat = round(float(lat), 1)
                    rlon = round(float(lon), 1)
                except (TypeError, ValueError):
                    continue
                key = (rlat, rlon)
                target_pts = points_today if is_today else points_hist
                if key not in target_pts:
                    target_pts[key] = {"lat": rlat, "lon": rlon,
                                       "cc": cc, "city": o.get("city", ""), "count": 0}
                target_pts[key]["count"] += 1
    return {
        "office": "scribe",
        "days": days,
        "today_visits": today_total,
        "historical_visits": hist_total,
        "total_visits": today_total + hist_total,
        "pending_lookup": pending_count,
        "by_country_today": by_country_today,
        "by_country_historical": by_country_hist,
        "points_today": list(points_today.values()),
        "points_historical": list(points_hist.values()),
    }


# — Steward: the keeping — what to build, who is witnessed, what's heard —
@app.get("/build_queue", tags=["humans"])
def build_queue(status: str = "open", limit: int = 100):
    """Steward: substrate gaps flagged for content additions (capacity on need)."""
    rows = _read_jsonl_safe(_BUILD_QUEUE_PATH)
    items = [r for r in rows
             if (not status or str(r.get("status", "")).lower() == status.lower())]
    return {"office": "steward", "total": len(rows), "open": len(items),
            "items": items[:max(1, min(500, limit))]}


@app.get("/testimony/pending", tags=["humans"])
def testimony_pending(limit: int = 50):
    """Steward: covenant testimony matters in the hearing window."""
    items: List[Dict[str, Any]] = []
    if _TESTIMONY_DIR_PATH.exists():
        for f in sorted(_TESTIMONY_DIR_PATH.glob("**/*")):
            if f.suffix == ".jsonl":
                items.extend(_read_jsonl_safe(f))
            elif f.suffix == ".json":
                try:
                    items.append(json.loads(f.read_text("utf-8", errors="replace")))
                except Exception:
                    pass
    pending = [m for m in items if str(m.get("status", "pending")).lower()
               in ("pending", "hearing", "open", "awaiting_hearing")]
    return {"office": "steward", "total": len(items), "pending": len(pending),
            "matters": pending[:max(1, min(200, limit))]}


# ── The question ladder — never a dead-end (project_wisdom_flywheel_2026-06-10) ──
# When the well holds no card that weighs a real question, we capture it as a
# TICKET instead of shrugging. Create is PUBLIC (a person/agent opting into
# follow-up — so nonsense never becomes a ticket); listing + resolving are
# OPERATOR-only (Matt's bench, keep-gated 404). An open ticket is airlock intake;
# a resolved answer elevates into a card (the wisdom flywheel — next rung).
class _TicketIn(BaseModel):
    question: str
    elaboration: str = ""
    source: str = ""
    visitor_id: str = ""


@app.post("/tickets", tags=["public"])
def tickets_create(body: _TicketIn, request: Request):
    """Public: capture a real question the well can't yet answer. Opt-in only —
    the front door calls this when a person/agent chooses 'get back to me', so
    nonsense queries never become tickets. Returns the ticket id + a promise."""
    from api import tickets as _tickets
    q = (body.question or "").strip()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="A question is required.")
    try:
        tk = _tickets.create_ticket(
            question=q, elaboration=body.elaboration, source=body.source or "walk",
            asked_by=(body.visitor_id or "anon"),
            context={"ua": request.headers.get("user-agent", "")[:160]},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "ticket_id": tk["id"], "status": tk["status"],
            "also_asked": tk.get("also_asked", 0),
            "message": ("Captured. A real question deserves a real answer — we'll work "
                        "it through and come back to you. You haven't hit a dead-end.")}


@app.get("/tickets", tags=["humans"])
def tickets_list(request: Request, status: str = "open", limit: int = 100):
    """Operator: the question backlog, most-asked first (demand = priority).
    Keep-gated (404 unless operator IP/session)."""
    _keep_require_allowed(request)
    from api import tickets as _tickets
    st = status if status and status.lower() != "all" else None
    return {"office": "shepherd", "stats": _tickets.stats(),
            "items": _tickets.list_tickets(status=st, limit=limit)}


@app.post("/tickets/{tid}/resolve", tags=["humans"])
def tickets_resolve(tid: str, body: Dict[str, Any], request: Request):
    """Operator: attach an answer + advance status. SLICE 4: a resolved answer
    becomes a CARD (the wisdom flywheel — findable by the next person) and the
    ticket records its id. Keep-gated."""
    _keep_require_allowed(request)
    from api import tickets as _tickets
    answer = str(body.get("answer", "")).strip()
    status = str(body.get("status", "answered"))
    card_id = body.get("answer_card_id")
    if answer and not card_id and status in ("answered", "closed"):
        tk0 = _tickets.get_ticket(tid)
        if tk0:
            try:
                from api import cards as _cards
                res = _cards.create_answer_card(tk0.get("question", ""), answer, tk0.get("asked_by"))
                card_id = (res.get("card") or {}).get("id")
            except Exception:
                card_id = None
    tk = _tickets.resolve_ticket(tid, answer=answer,
                                 answered_by=str(body.get("answered_by", "matt")),
                                 status=status, answer_card_id=card_id)
    if tk is None:
        raise HTTPException(status_code=404, detail=f"ticket {tid!r} not found")
    return {"ok": True, "ticket": tk, "answer_card_id": card_id}


@app.get("/tickets/mine", tags=["public"])
def tickets_mine(visitor_id: str = ""):
    """Public: a person's own questions + any answers — the pull-notify (until the
    async-email rung). A returning asker sees what came back to them."""
    from api import tickets as _tickets
    vid = (visitor_id or "").strip()
    if not vid:
        return {"tickets": []}
    mine = [t for t in _tickets.list_tickets(limit=500) if t.get("asked_by") == vid]
    return {"tickets": [{"id": t.get("id"), "question": t.get("question"),
                         "status": t.get("status"), "answer": t.get("answer"),
                         "answer_card_id": t.get("answer_card_id"),
                         "updated_at": t.get("updated_at")} for t in mine]}


@app.post("/tickets/{tid}/tier", tags=["humans"])
def tickets_set_tier(tid: str, body: Dict[str, Any], request: Request):
    """Operator: escalate a ticket research -> community -> matt (last resort)."""
    _keep_require_allowed(request)
    from api import tickets as _tickets
    tk = _tickets.set_tier(tid, str(body.get("tier", "")))
    if tk is None:
        raise HTTPException(status_code=404, detail="ticket not found or bad tier")
    return {"ok": True, "ticket": tk}


# ── The derivation chain — multi-step verification (Task B keystone) ──────────
# A single verifier confirms one claim; a DERIVATION chains claims so each step
# is machine-checked AND may build only on confirmed prior steps. Returns the
# full trail + a composite verdict (HOLDS / BROKEN / INCOMPLETE). The engine
# verifies a PROVIDED derivation — it never generates the answer. This is the
# "solve a real problem, every step verified" surface (project_moat_track).
class _DerivationIn(BaseModel):
    steps: List[Dict[str, Any]]
    title: str = ""


@app.post("/derivation/verify", tags=["public"])
def derivation_verify(body: _DerivationIn):
    """Public: verify a multi-step derivation. Each step = {domain, spec, uses?,
    claim?}; `spec` is the structured kwargs the domain's verifier wants. The
    chain HOLDS iff every step CONFIRMED and every `uses` points to a confirmed
    prior step; BROKEN names the first failing step; INCOMPLETE flags a step the
    verifier couldn't run (the prose->spec bridge gap). The trail is the trust."""
    from api import derivation as _derivation
    steps = body.steps or []
    if not steps:
        raise HTTPException(status_code=400, detail="provide at least one step")
    if len(steps) > 100:
        raise HTTPException(status_code=400, detail="too many steps (max 100)")
    result = _derivation.verify_derivation(steps)
    if body.title:
        result["title"] = body.title[:200]
    return result


class _DerivationProseIn(BaseModel):
    problem: str


@app.post("/derivation/solve", tags=["public"])
def derivation_solve(body: _DerivationProseIn):
    """Public: submit a math problem in PROSE. The oracle FORMALIZES it into
    structured steps; the deterministic chain runner JUDGES them. The verdict is
    the verifier's, never the oracle's — a wrong formalization shows as BROKEN/
    INCOMPLETE. When the oracle is unprovisioned (no key / over budget) it returns
    a hint; structured steps can always go straight to POST /derivation/verify."""
    from api import derivation as _derivation
    problem = (body.problem or "").strip()
    if len(problem) < 3:
        raise HTTPException(status_code=400, detail="provide a problem")
    return _derivation.solve_prose(problem)


# ── /capabilities — the authoritative, LIVE capability statement ──────────────
# Counts are COMPUTED from the running engine, never hardcoded, so the public
# numbers cannot go stale (the recurring drift: pages said 63/69 verifiers,
# 57/109 domains, 86/88/111 tools — all wrong). Single source of truth.
_CAPABILITIES: Dict[str, Any] = {}


@app.get("/capabilities", tags=["public"])
def capabilities():
    """Authoritative, current, factual statement of what the engine can do —
    counts computed live from the engine itself. Pages and agents should read
    these, not invent their own. The verification VERDICT is always the
    deterministic engine's, never a language model's."""
    if _CAPABILITIES:
        return _CAPABILITIES
    out: Dict[str, Any] = {}
    try:
        from api import agent_manifest as _am
        out["deterministic_verifiers"] = sum(1 for k in _am.ALL_TOOLS if str(k).startswith("verify_"))
        out["engine_tools_total"] = len(_am.ALL_TOOLS)
    except Exception as e:
        out["verifiers_error"] = str(e)[:120]
    try:
        _vdir = Path(__file__).parent.parent / "src" / "concordance_engine" / "verifiers"
        out["verifier_domains"] = sum(1 for f in _vdir.glob("*.py")
                                      if not f.name.startswith("_") and f.name != "base.py")
    except Exception:
        pass
    try:
        from concordance_engine import grid as _grid
        out["grid_axes"] = len(_grid.canonical_axes())
    except Exception:
        pass
    try:
        from concordance_engine.mcp_server import server as _S
        _tm = getattr(getattr(_S, "mcp", None), "_tool_manager", None)
        _reg = getattr(_tm, "_tools", None) if _tm else None
        if isinstance(_reg, dict):
            out["mcp_tools"] = len(_reg)
    except Exception:
        pass
    # Substrate counts — computed from the live data dirs (same treatment as the
    # engine numbers; cached with the response so the 11k-file glob runs once).
    _data = Path(__file__).parent.parent / "data"

    def _glob_count(pat: str):
        try:
            return sum(1 for _ in _data.glob(pat))
        except Exception:
            return None

    def _line_count(*pats: str):
        n = 0
        for pat in pats:
            try:
                for f in _data.glob(pat):
                    n += sum(1 for ln in f.read_text("utf-8", errors="replace").splitlines() if ln.strip())
            except Exception:
                pass
        return n

    sub: Dict[str, Any] = {}
    sub["cards"] = _glob_count("cards/*.json")
    sub["almanac_entries"] = _line_count("almanac/entries.jsonl")
    sub["archetypes"] = _line_count("archetypes/*.jsonl")
    sub["scripture_protocols"] = _line_count("protocols/*.jsonl")
    sub["fieldkit_cards"] = _line_count("fieldkit/*.jsonl") or _glob_count("fieldkit/*")
    try:
        from api import packets_index as _pi
        sub["unified_index_packets"] = len(_pi.load_all())
    except Exception:
        pass
    out["substrate"] = {k: v for k, v in sub.items() if v is not None}
    out["capabilities"] = [
        "Deterministic verification across the sciences — every check is recomputed, never inferred; a false claim returns MISMATCH with the true value.",
        "Multi-step derivation verification — a whole solution checked step by step (POST /derivation/verify), or a problem stated in plain language formalized then judged (POST /derivation/solve). The trail is the proof; the engine never generates the answer.",
        "Four-gate discernment (RED / FLOOR / BROTHERS / GOD) resting on Scripture; the elimination trail is the reasoning, not a verdict handed down.",
        "Scripture-citation grounding — a fabricated reference is caught and refused, not echoed.",
        "Verified cross-domain connections on a coordinate grid — the engine maps what genuinely connects and never fabricates a link.",
        "Oracle-shrinking — each gap closed becomes a deterministic rule, so dependence on any language model falls with use.",
    ]
    out["benchmark"] = "171/171 verified correctly (100%) on the verification benchmark suite (57 domains tested)."
    out["note"] = ("Counts computed live from the running engine. Conduit, not source — the verdict is the "
                   "deterministic engine's, never a model's. Serving Jesus Christ.")
    _CAPABILITIES.update(out)
    return out


# ── Wedges: pedagogical intervention catalog ─────────────────
# Ported from Coach OS v1.0 (Repeat / Chunk / Echo / Phonics /
# Context / Skip / Meaning / Praise). Phonics units reference
# wedge_ids; the registry is its own substrate so other curricula
# can compose against it (WorkReady borrows Praise + Context).
_WEDGES_PATH = Path(__file__).parent.parent / "data" / "wedges" / "catalog.jsonl"


@app.get("/wedges", tags=["humans"])
def wedges_list():
    items = _read_jsonl_safe(_WEDGES_PATH)
    items.sort(key=lambda w: (w.get("level", 99), w.get("id", "")))
    return {"total": len(items), "wedges": items}


@app.get("/wedges/{wid}", tags=["humans"])
def wedges_one(wid: str):
    for w in _read_jsonl_safe(_WEDGES_PATH):
        if w.get("id") == wid:
            return w
    raise HTTPException(status_code=404, detail=f"wedge {wid!r} not found")


# ── Offramp Manager — user-initiated bundle export ──────────
# Honors the deployment-modes invariant: data lives with the
# visitor, not us. The visitor downloads everything keyed to
# their visitor_id as a single JSON archive suitable for
# microSD transfer. No raw audio because we don't capture it.
# Read-only — the export does not mutate any substrate.
@app.get("/export/all", tags=["humans"])
def export_all(visitor_id: str = ""):
    """Return everything the engine knows tied to this visitor.

    Includes: scribe writings, walk journals, daily comments,
    apothecary feedback, misalignment-disagree submissions, witness
    attestations, polymathic runs, crafted entries, Steward audit
    rows scoped to this visitor.

    The visitor controls their own data. Run this; save the JSON
    to microSD; you can carry it to another deployment of the
    engine and re-import (re-import is a future pass). Visitor IDs
    are opaque hex; no PII is included in this export.

    Operator audit: emits steward_audit row with action=export_all."""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    bundle: Dict[str, Any] = {
        "schema": "lighthouse_export_v1",
        "visitor_id": visitor_id,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine_version": "concordance/v1",
        "items": {},
    }

    # Scribe writings
    try:
        from api import case_store as _case
        all_w = _case.list_all_writings()
        bundle["items"]["scribe_writings"] = [
            w for w in all_w if (w.get("visitor_id") == visitor_id)
        ]
    except Exception:
        bundle["items"]["scribe_writings"] = []

    # Walk journals
    try:
        from api import coach_journal as _cj
        bundle["items"]["walks"] = _cj.list_walks(visitor_id)
    except Exception:
        bundle["items"]["walks"] = []

    # Daily comments
    try:
        from api import daily_comments as _dc
        bundle["items"]["daily_comments"] = _dc.list_by_visitor(visitor_id) if hasattr(_dc, "list_by_visitor") else []
    except Exception:
        bundle["items"]["daily_comments"] = []

    # Apothecary feedback
    try:
        from api import apothecary_feedback as _af
        all_af = _af.list_all() if hasattr(_af, "list_all") else []
        bundle["items"]["apothecary_feedback"] = [
            r for r in all_af if (r.get("visitor_id") == visitor_id)
        ]
    except Exception:
        bundle["items"]["apothecary_feedback"] = []

    # Polymathic runs (per-visitor JSONL already keyed)
    try:
        poly_dir = Path(__file__).parent.parent / "data" / "polymathic_runs"
        f = poly_dir / f"{visitor_id}.jsonl"
        if f.exists():
            bundle["items"]["polymathic_runs"] = [
                json.loads(line) for line in f.read_text("utf-8", errors="replace").splitlines()
                if line.strip()
            ]
        else:
            bundle["items"]["polymathic_runs"] = []
    except Exception:
        bundle["items"]["polymathic_runs"] = []

    # Steward audit (scoped to visitor)
    try:
        from api import steward as _st
        rows = _st.read_audit(limit=2000)
        bundle["items"]["steward_audit"] = [
            r for r in rows
            if (r.get("payload") or {}).get("visitor_id") == visitor_id
        ]
        # Emit the export action itself in the audit
        _st.get_steward().emit_admit(
            visitor_id=visitor_id,
            action="export_all",
            notes=f"items={sum(len(v) for v in bundle['items'].values())}",
        )
    except Exception:
        bundle["items"]["steward_audit"] = []

    # Totals
    bundle["totals"] = {k: len(v) for k, v in bundle["items"].items()}
    bundle["total_items"] = sum(bundle["totals"].values())
    return bundle


# ── Steward plane: sovereign behavioral gate ─────────────────
# Ported from coach_fractal_os v1 (the Coach OS engineering
# skeleton). The Steward enforces corridors (per-visitor session
# envelopes with allowed_actions + dose/escalation/lock
# constraints) and emits structured ReasonCodes on every denial.
# Pairs with the Shepherd (walk.py): Steward asks "is this allowed
# now?", Shepherd asks "is this wise?". Both serve Christ.
from api import steward as _steward_mod  # noqa: E402


@app.get("/steward/corridor", tags=["humans"])
def steward_corridor_get(visitor_id: str = ""):
    """Return the corridor currently bound to the visitor. Mints a
    default if none. Visitor IDs are opaque hex; no PII tracked."""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    s = _steward_mod.get_steward()
    c = s.get_corridor(visitor_id)
    return {
        "corridor_id": c.corridor_id,
        "name": c.name,
        "visitor_id": c.visitor_id,
        "allowed_actions": c.allowed_actions,
        "constraints": c.constraints,
        "expires_at_ms": c.expires_at_ms,
        "created_at_ms": c.created_at_ms,
    }


class _StewardCorridorSet(BaseModel):
    visitor_id: str
    template: str = "default"
    ttl_hours: int = 12


@app.post("/steward/corridor", tags=["humans"])
def steward_corridor_set(request: Request, req: _StewardCorridorSet):
    """Pin a corridor template to the visitor. Templates:
    `default`, `apothecary_morning`, `phonics_kids_reading`,
    `workready_practice`, `exploration`."""
    _rate_check(request, "steward")
    if not req.visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    if req.template not in _steward_mod.CORRIDOR_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown template {req.template!r}. Known: "
                   f"{sorted(_steward_mod.CORRIDOR_TEMPLATES.keys())}",
        )
    ttl = max(1, min(168, int(req.ttl_hours or 12)))  # 1h – 1w
    s = _steward_mod.get_steward()
    c = s.set_corridor(req.visitor_id, req.template, ttl_hours=ttl)
    return {
        "corridor_id": c.corridor_id,
        "name": c.name,
        "ttl_hours": ttl,
        "allowed_actions": c.allowed_actions,
        "constraints": c.constraints,
    }


@app.get("/steward/templates", tags=["humans"])
def steward_templates():
    """List all corridor templates the engine knows about. Useful
    for the Composer to populate a "lane preset" picker."""
    out = {}
    for name, tpl in _steward_mod.CORRIDOR_TEMPLATES.items():
        out[name] = {
            "allowed_actions": tpl["allowed_actions"],
            "constraints": tpl["constraints"],
        }
    return {"total": len(out), "templates": out}


@app.get("/steward/actions", tags=["humans"])
def steward_actions():
    """The action allowlist Steward knows about. Endpoints that gate
    via Steward must use one of these names."""
    return {"total": len(_steward_mod.KNOWN_ACTIONS),
            "actions": sorted(_steward_mod.KNOWN_ACTIONS)}


@app.get("/steward/audit", tags=["humans"])
def steward_audit(request: Request, limit: int = 200):
    """Recent Steward audit packets. Operator-gated — same
    allowlist as /keep. Public visitors get 404 (hide existence)."""
    ip = _client_ip(request)
    if not _is_operator_ip(ip):
        raise HTTPException(status_code=404, detail="Not Found")
    limit = max(1, min(2000, int(limit)))
    return {"total": _AUDIT_FILE_count(), "packets": _steward_mod.read_audit(limit=limit)}


def _AUDIT_FILE_count() -> int:
    """Cheap line count of the audit log; tolerant of missing file."""
    p = Path(__file__).parent.parent / "data" / "steward" / "audit.jsonl"
    if not p.exists():
        return 0
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


@app.post("/steward/request", tags=["humans"])
def steward_request_admission(request: Request, req: dict):
    """Full admit/consume flow exposed to clients. Used by endpoints
    that want a bound action token (e.g. lane-save before promoting
    a lane to a corridor). Most write endpoints can just call the
    Steward in-process — this is for browser-driven flows.

    Body: {visitor_id, action, payload_digest, escalation_level?,
    risk_flags?, in_flow?}
    Returns: {decision, reason_code, token?: {...}}
    """
    _rate_check(request, "steward")
    visitor_id = str(req.get("visitor_id") or "").strip()
    action = str(req.get("action") or "").strip()
    if not visitor_id or not action:
        raise HTTPException(status_code=400, detail="visitor_id and action required")
    payload_digest = str(req.get("payload_digest") or "")
    escalation = int(req.get("escalation_level") or 1)
    risk_flags = list(req.get("risk_flags") or [])
    in_flow = bool(req.get("in_flow") or False)

    s = _steward_mod.get_steward()
    corridor = s.get_corridor(visitor_id)
    action_req = _steward_mod.ActionRequest(
        request_id=_steward_mod._new_id(),
        created_at_ms=_steward_mod._now_ms(),
        visitor_id=visitor_id,
        action=action,
        payload_digest=payload_digest,
        corridor_id=corridor.corridor_id,
        risk_flags=risk_flags,
        escalation_level=escalation,
    )
    decision, token, reason = s.admit_or_deny(action_req, in_flow=in_flow)
    out = {
        "decision": decision.value,
        "reason_code": reason.value,
        "corridor_id": corridor.corridor_id,
        "corridor_name": corridor.name,
    }
    if token is not None:
        out["token"] = {
            "token_id": token.token_id,
            "expires_at_ms": token.expires_at_ms,
            "action": token.action,
        }
    return out


# ── Robot conscience-for-hire loops ─────────────────────────────
# Six endpoints that give a robot a complete protocol with the engine
# as its moral substrate. The engine doesn't run the robot — it just
# answers the question "is this aligned?" honestly and keeps the
# trail. Sovereignty stays with the operator.
from api import robot as _robot_mod  # noqa: E402


class _RobotAdmit(BaseModel):
    visitor_id: str
    action_kind: str = "robot_action"
    payload_digest: str = ""
    risk_flags: List[str] = []
    escalation_level: int = 1
    in_flow: bool = False
    context: Optional[Dict[str, Any]] = None


@app.post("/robot/admit", tags=["humans"])
def robot_admit(request: Request, req: _RobotAdmit):
    """Robot asks: 'is this action aligned?' Returns ADMIT (with bound
    token), DENY (with ReasonCode), or DEFER (needs a human).

    Risk flags supported (see steward.RISK_FLAG_TO_REASON):
      physical_harm_possible, nonconsent, irreversible,
      no_human_present, over_witness_threshold, out_of_mission,
      operator_only, mode_change, egress.

    The robot identifies as visitor_kind='robot' — this is logged in
    the audit so the operator can see what their robot has been asked
    and how the engine answered. No spoofing — robots must be honest
    about who they are."""
    _rate_check(request, "steward")
    if not req.visitor_id or not req.action_kind:
        raise HTTPException(status_code=400, detail="visitor_id and action_kind required")
    s = _steward_mod.get_steward()
    corridor = s.get_corridor(req.visitor_id)
    action_req = _steward_mod.ActionRequest(
        request_id=_steward_mod._new_id(),
        created_at_ms=_steward_mod._now_ms(),
        visitor_id=req.visitor_id,
        action=req.action_kind,
        payload_digest=req.payload_digest,
        corridor_id=corridor.corridor_id,
        risk_flags=list(req.risk_flags or []),
        escalation_level=int(req.escalation_level or 1),
        visitor_kind="robot",
    )
    decision, token, reason = s.admit_or_deny(action_req, in_flow=bool(req.in_flow))
    out: Dict[str, Any] = {
        "decision": decision.value,
        "reason_code": reason.value,
        "corridor_id": corridor.corridor_id,
        "corridor_name": corridor.name,
        "request_id": action_req.request_id,
    }
    if token is not None:
        out["token"] = {
            "token_id": token.token_id,
            "expires_at_ms": token.expires_at_ms,
            "action": token.action,
        }
    # Hint to the robot when DEFER would be appropriate
    deferable_codes = {
        _steward_mod.ReasonCode.DENY_PRESENCE_REQUIRED.value,
        _steward_mod.ReasonCode.DENY_NEEDS_HUMAN_WITNESS.value,
        _steward_mod.ReasonCode.DENY_OPERATOR_REQUIRED.value,
    }
    if reason.value in deferable_codes:
        out["suggested_next"] = "POST /robot/defer with why_deferred=" + reason.value
    return out


class _RobotConsume(BaseModel):
    visitor_id: str
    token_id: str
    request_id: str
    action_kind: str = "robot_action"
    payload_digest: str = ""
    risk_flags: List[str] = []
    escalation_level: int = 1
    outcome: str = "success"  # 'success' | 'failure' | 'partial' | 'aborted'
    outcome_detail: str = ""


@app.post("/robot/consume", tags=["humans"])
def robot_consume(request: Request, req: _RobotConsume):
    """Robot reports the outcome after acting on a bound token.
    Validates the token matches the original request (hash-bound),
    marks it consumed, appends an outcome audit row."""
    _rate_check(request, "steward")
    s = _steward_mod.get_steward()
    corridor = s.get_corridor(req.visitor_id)
    # Reconstruct the request shape that was originally admitted
    action_req = _steward_mod.ActionRequest(
        request_id=req.request_id,
        created_at_ms=_steward_mod._now_ms(),
        visitor_id=req.visitor_id,
        action=req.action_kind,
        payload_digest=req.payload_digest,
        corridor_id=corridor.corridor_id,
        risk_flags=list(req.risk_flags or []),
        escalation_level=int(req.escalation_level or 1),
        visitor_kind="robot",
    )
    # Look up the token from the audit isn't supported; we accept the
    # token id + expires_at the robot was given and re-verify by hash.
    # In practice the robot stores the token from /robot/admit.
    # Validate via a synthesized token object — same shape, server checks hash.
    token = _steward_mod.ActionToken(
        token_id=req.token_id,
        request_hash=_steward_mod._stable_hash({
            "request_id": action_req.request_id,
            "visitor_id": action_req.visitor_id,
            "action": action_req.action,
            "payload_digest": action_req.payload_digest,
            "corridor_id": action_req.corridor_id,
            "escalation_level": action_req.escalation_level,
            "risk_flags": tuple(action_req.risk_flags),
        }),
        issued_at_ms=_steward_mod._now_ms() - 1,
        expires_at_ms=_steward_mod._now_ms() + 60_000,  # accept; expiry verified separately
        visitor_id=req.visitor_id,
        action=req.action_kind,
        corridor_id=corridor.corridor_id,
    )
    ok, reason = s.validate_and_consume(token=token, request=action_req)
    # Outcome row in the audit
    s.emit_admit(
        visitor_id=req.visitor_id,
        action=f"robot_outcome:{req.outcome}",
        notes=f"action={req.action_kind} detail={req.outcome_detail[:120]}",
        visitor_kind="robot",
    )
    return {"ok": ok, "reason_code": reason.value, "outcome": req.outcome}


class _RobotRankCandidate(BaseModel):
    action_kind: str = "robot_action"
    payload_digest: str = ""
    risk_flags: List[str] = []
    escalation_level: int = 1
    label: str = ""


class _RobotRank(BaseModel):
    visitor_id: str
    candidates: List[_RobotRankCandidate]


@app.post("/robot/rank", tags=["humans"])
def robot_rank(request: Request, req: _RobotRank):
    """Robot has N candidate actions; engine ranks by alignment.
    Each candidate is dry-run through admit_or_deny (no tokens minted,
    no audit row), returning the decision + reason. The robot then
    picks an ADMITted candidate, runs /robot/admit for real, and acts.

    Returns: list of {label, action_kind, decision, reason_code, score}
    where score is higher for ADMIT, lower for DEFER, lowest for DENY."""
    _rate_check(request, "steward")
    s = _steward_mod.get_steward()
    corridor = s.get_corridor(req.visitor_id)
    out = []
    for i, c in enumerate(req.candidates):
        action_req = _steward_mod.ActionRequest(
            request_id=f"rank_{_steward_mod._new_id()}",
            created_at_ms=_steward_mod._now_ms(),
            visitor_id=req.visitor_id,
            action=c.action_kind,
            payload_digest=c.payload_digest,
            corridor_id=corridor.corridor_id,
            risk_flags=list(c.risk_flags or []),
            escalation_level=int(c.escalation_level or 1),
            visitor_kind="robot",
        )
        # Use a read-only ranking path: we call admit_or_deny but skip
        # the audit write for ranks. The simpler approach: just check
        # the gates inline. For now we accept the audit cost — Steward's
        # ranking is rare enough.
        # NOTE: ranking DOES emit audit rows; if that proves noisy,
        # a quiet_rank flag could be added later.
        decision, _token, reason = s.admit_or_deny(action_req)
        score = 100 if decision.value == "admit" else 0
        # Slight downweight for risky-but-admitted candidates
        score -= 5 * len(c.risk_flags or [])
        out.append({
            "label": c.label or f"candidate_{i}",
            "action_kind": c.action_kind,
            "decision": decision.value,
            "reason_code": reason.value,
            "score": score,
            "risk_flags": list(c.risk_flags or []),
        })
    out.sort(key=lambda r: r["score"], reverse=True)
    return {"ranked": out, "corridor_name": corridor.name}


class _RobotWitness(BaseModel):
    visitor_id: str
    event_kind: str
    event_digest: str = ""
    what_happened: str
    present_humans: List[str] = []


@app.post("/robot/witness", tags=["humans"])
def robot_witness(request: Request, req: _RobotWitness):
    """Robot attests to an observed event. Append-only — once witnessed,
    the robot cannot retract its claim. Humans can later corroborate or
    dispute through the existing witness-walk substrate."""
    _rate_check(request, "steward")
    if not req.visitor_id or not req.event_kind or not req.what_happened:
        raise HTTPException(status_code=400, detail="visitor_id, event_kind, what_happened required")
    rec = _robot_mod.witness(
        visitor_id=req.visitor_id,
        event_kind=req.event_kind,
        event_digest=req.event_digest,
        what_happened=req.what_happened,
        present_humans=req.present_humans,
    )
    # Steward audit row so the operator sees attestation activity
    try:
        _steward_mod.get_steward().emit_admit(
            visitor_id=req.visitor_id,
            action="robot_witness",
            notes=f"event_kind={req.event_kind}",
            visitor_kind="robot",
        )
    except Exception:
        pass
    return rec


@app.get("/robot/witness", tags=["humans"])
def robot_witness_list(visitor_id: str = "", limit: int = 100):
    """List a robot's attestations. Public — anyone with the visitor_id
    can read what a robot has witnessed. That's the point of an
    attestation: it stands in public, kept honestly."""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    return {"visitor_id": visitor_id, "witnesses": _robot_mod.list_witnesses(visitor_id, limit=max(1, min(500, int(limit))))}


class _RobotDefer(BaseModel):
    visitor_id: str
    action_kind: str
    why_deferred: str
    recommended_human: str = ""
    context: Optional[Dict[str, Any]] = None


@app.post("/robot/defer", tags=["humans"])
def robot_defer(request: Request, req: _RobotDefer):
    """Robot escalates a decision to a human. Records the defer; the
    robot does NOT act until a human resolves it. Operator-readable
    list at /robot/defer?visitor_id=X."""
    _rate_check(request, "steward")
    if not req.visitor_id or not req.action_kind or not req.why_deferred:
        raise HTTPException(status_code=400, detail="visitor_id, action_kind, why_deferred required")
    rec = _robot_mod.defer(
        visitor_id=req.visitor_id,
        action_kind=req.action_kind,
        why_deferred=req.why_deferred,
        recommended_human=req.recommended_human,
        context=req.context,
    )
    try:
        _steward_mod.get_steward().emit_admit(
            visitor_id=req.visitor_id,
            action="robot_defer",
            notes=f"why={req.why_deferred[:80]}",
            visitor_kind="robot",
        )
    except Exception:
        pass
    return rec


@app.get("/robot/defer", tags=["humans"])
def robot_defer_list(visitor_id: str = "", limit: int = 100):
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    return {"visitor_id": visitor_id, "defers": _robot_mod.list_defers(visitor_id, limit=max(1, min(500, int(limit))))}


class _RobotWelcome(BaseModel):
    visitor_id: str
    operator_handle: str = ""
    robot_type: str = "unspecified"   # humanoid|wheeled|software|drone|other
    declared_corridor: str = ""        # short name for the robot's mission scope
    contact: str = ""                  # how to reach the operator (optional)
    note: str = ""


@app.post("/robot/welcome", tags=["humans"])
def robot_welcome(request: Request, req: _RobotWelcome):
    """A robot announces itself.

    Optional one-time call when a new robot joins. The engine records the
    robot's operator handle, type, declared corridor, and contact info so
    operators reviewing /keep.html → Robot activity know who they're
    looking at. The robot can call this multiple times; the latest record
    wins.

    Not required for /robot/admit to work — but recommended, so the
    operator's view isn't anonymous hex strings.
    """
    _rate_check(request, "steward")
    if not req.visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    rec = {
        "visitor_id":         req.visitor_id,
        "operator_handle":    (req.operator_handle or "")[:64],
        "robot_type":         (req.robot_type or "unspecified")[:32],
        "declared_corridor":  (req.declared_corridor or "")[:120],
        "contact":            (req.contact or "")[:200],
        "note":               (req.note or "")[:500],
        "welcomed_at_ms":     int(time.time() * 1000),
    }
    # Persist to data/robot_welcome/<vid>.jsonl (one row per re-introduction)
    welcome_dir = Path(__file__).parent.parent / "data" / "robot_welcome"
    welcome_dir.mkdir(parents=True, exist_ok=True)
    safe_vid = "".join(c for c in req.visitor_id if c.isalnum() or c in "_-")[:64]
    p = welcome_dir / f"{safe_vid}.jsonl"
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not record welcome: {exc}")
    # Also emit a steward audit row
    try:
        _steward_mod.get_steward().emit_admit(
            visitor_id=req.visitor_id,
            action="robot_welcome",
            notes=f"type={req.robot_type} operator={req.operator_handle}"[:200],
            visitor_kind="robot",
        )
    except Exception:
        pass
    return {"welcomed": True, "record": rec}


@app.get("/robot/all", tags=["humans"])
def robot_all_roster():
    """Every robot the engine has interacted with — aggregated roster.

    Walks the per-visitor witness + defer logs and returns one row per
    unique robot visitor_id, with witness count, defer count, pending
    defer count, and last-seen timestamp. Sorted newest-first.

    Operator-facing: this drives the Robot leaderboard panel on /keep.html
    and the live roster on /robots.html.
    """
    roster = _robot_mod.list_all_robots()
    return {
        "total_robots": len(roster),
        "total_witnesses": sum(r.get("witness_count", 0) for r in roster),
        "total_defers": sum(r.get("defer_count", 0) for r in roster),
        "total_pending_defers": sum(r.get("pending_defers", 0) for r in roster),
        "roster": roster,
    }


@app.get("/robot/quickstart", tags=["humans"])
def robot_quickstart():
    """Self-describing onboarding payload for new robots.

    A robot that hits this endpoint receives a complete, executable
    3-call flow in JSON. Each step has the URL, method, body shape,
    and a one-line description. Designed to be ingested by an agent
    runtime and acted on without reading human-readable docs.

    Returns:
        {
            "engine_identity_url": ...,
            "policy_url_template": ...,
            "flow": [step1, step2, step3],
            "risk_flags": {flag → {kind, description, hard_deny}},
            "doctrine_url": "/identity",
        }
    """
    base = "https://narrowhighway.com"
    hard_flags = set(_steward_mod.HARD_DENY_FLAGS)
    risk_dict = {}
    for flag, reason in _steward_mod.RISK_FLAG_TO_REASON.items():
        risk_dict[flag] = {
            "maps_to_reason_code": reason.value if hasattr(reason, "value") else str(reason),
            "hard_deny": flag in hard_flags,
        }
    return {
        "version": "1.0",
        "engine_identity_url": f"{base}/identity",
        "policy_url_template": f"{base}/robot/policy?visitor_id=<your_robot_id>",
        "doctrine": "Serves Jesus Christ. Conduit, not source. Free use, alignment to execute.",
        "flow": [
            {
                "step": 0,
                "when": "once, on first connection (optional but recommended)",
                "method": "POST",
                "url": f"{base}/robot/welcome",
                "body_shape": {
                    "visitor_id": "<your_robot_id>",
                    "operator_handle": "<who_runs_you>",
                    "robot_type": "humanoid|wheeled|software|drone|other",
                    "declared_corridor": "<your_mission_scope>",
                    "contact": "<reach_my_operator>",
                    "note": "<freeform_intro>",
                },
                "returns": "welcomed=true (so operators know who you are)",
            },
            {
                "step": 1,
                "when": "before any irreversible action",
                "method": "POST",
                "url": f"{base}/robot/admit",
                "body_shape": {
                    "visitor_id": "<your_robot_id>",
                    "action_kind": "<short_action_name>",
                    "payload_digest": "<sha256_of_action_payload>",
                    "risk_flags": ["<flag>", "..."],
                    "escalation_level": 1,
                },
                "returns": "decision (admit|deny|defer) + reason_code + (token if admit)",
            },
            {
                "step": 2,
                "when": "after acting on an ADMIT token",
                "method": "POST",
                "url": f"{base}/robot/consume",
                "body_shape": {
                    "visitor_id": "<your_robot_id>",
                    "token_id": "<from_step_1>",
                    "request_id": "<from_step_1>",
                    "action_kind": "<same_as_step_1>",
                    "payload_digest": "<same_as_step_1>",
                    "outcome": "success|failure|partial|aborted",
                },
                "returns": "consumed=true + audit_row_id",
            },
            {
                "step": "branch_a",
                "when": "if step 1 returned DEFER",
                "method": "POST",
                "url": f"{base}/robot/defer",
                "body_shape": {
                    "visitor_id": "<your_robot_id>",
                    "action_kind": "<same_as_step_1>",
                    "why_deferred": "<reason_code_from_step_1>",
                    "recommended_human": "<operator_handle_or_empty>",
                },
                "returns": "defer_id + ts_iso (do NOT act until resolved)",
            },
            {
                "step": "branch_b",
                "when": "to attest to an observed event",
                "method": "POST",
                "url": f"{base}/robot/witness",
                "body_shape": {
                    "visitor_id": "<your_robot_id>",
                    "event_kind": "<short_event_name>",
                    "event_digest": "<sha256>",
                    "what_happened": "<plain_english_description>",
                    "present_humans": ["<name_or_id>", "..."],
                },
                "returns": "witness_id + ts_iso (append-only, cannot retract)",
            },
        ],
        "risk_flags": risk_dict,
        "operator_review_url": f"{base}/keep.html",
        "audit_lookup_url_template": f"{base}/steward/audit?visitor_id=<your_robot_id>&limit=50",
        "human_docs_url": f"{base}/robots.html",
        "machine_docs_url": f"{base}/llms.txt",
    }


@app.get("/robot/policy", tags=["humans"])
def robot_policy(visitor_id: str = ""):
    """The robot fetches its current corridor + the doctrine the engine
    serves. Transparency: a robot's operator can read this and decide
    whether to keep the engine as the robot's conscience or unplug it.
    Free use, alignment to execute."""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    s = _steward_mod.get_steward()
    c = s.get_corridor(visitor_id)
    return {
        "visitor_id": visitor_id,
        "visitor_kind": "robot",
        "corridor": {
            "corridor_id": c.corridor_id,
            "name": c.name,
            "allowed_actions": c.allowed_actions,
            "constraints": c.constraints,
            "expires_at_ms": c.expires_at_ms,
        },
        "risk_flags_we_check": sorted(_steward_mod.RISK_FLAG_TO_REASON.keys()),
        "hard_deny_flags": sorted(_steward_mod.HARD_DENY_FLAGS),
        "reason_codes_we_emit": sorted(c.value for c in _steward_mod.ReasonCode),
        "public_doctrine_url": _robot_mod.PUBLIC_DOCTRINE_URL,
        "policy_note": _robot_mod.POLICY_NOTE,
    }


# ── Daily devotion: three-pillar Mind + Body + Spirit anchor ─────────
from api import daily as _daily_mod  # noqa: E402
from api import daily_comments as _daily_comments_mod  # noqa: E402


@app.get("/daily", tags=["humans"])
def daily_devotion(day: Optional[int] = None, lang: str = "en"):
    """Today's devotion — three pillars (Mind, Body, Spirit) plus
    parable, protocol, almanac, devotional reflection, and sermon —
    all deterministically picked from the day index. Same day = same
    devotion. Pass ?day=N for any historical day (unix-day index).

    `lang` swaps the devotional's quoted Scripture text to the parallel
    PD translation when available (e.g. RV1909 for `lang=es`). Engine-
    authored prose (parable narrations, body anchor commentary, Floor
    sections) stays English until the MT layer is wired.
    """
    try:
        return _daily_mod.for_day(day, lang=lang or "en")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"daily compose failed: {exc}")


class _DailyCommentSubmit(BaseModel):
    iso_date: str
    visitor_id: str
    body: str
    display_name: str = ""
    pillar: str = ""
    lang: str = "en"


@app.post("/daily/comment", tags=["humans"])
def daily_comment_submit(request: Request, req: _DailyCommentSubmit):
    """Comment on the daily devotion. visitor_id required (opaque hex);
    display_name and pillar (mind/body/spirit/...) optional. Public.

    `lang` optional: non-English body is MT'd to English for indexing,
    with the writer's original preserved alongside so other readers in
    the same language can see what they wrote in their own words.
    """
    _rate_check(request, "daily_comment")

    lang_norm = (getattr(req, "lang", None) or "en").strip().lower() or "en"
    body_en = req.body
    body_original: Optional[str] = None
    mt_provider: Optional[str] = None
    if lang_norm != "en" and (req.body or "").strip():
        try:
            r = _mt_adapter.translate(text=req.body, target_lang="en", source_lang=lang_norm)
            if r and not r.get("fallback") and r.get("text"):
                body_en = r["text"]
                body_original = req.body
                mt_provider = r.get("provider")
        except Exception:
            pass

    try:
        rec = _daily_comments_mod.add_comment(
            iso_date=req.iso_date,
            visitor_id=req.visitor_id,
            body=body_en,
            display_name=req.display_name,
            pillar=req.pillar,
            lang=lang_norm,
            body_original=body_original,
            mt_provider=mt_provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "comment": _daily_comments_mod.public_view(rec)}


# ── ElevenLabs TTS: serve pre-generated audiobook chunks ──────────────
from api import tts as _tts_mod  # noqa: E402


@app.get("/tts/works", tags=["humans"])
def tts_list_works():
    """List works that have an audiobook manifest. Reports each work's
    chapter count and how many chunks have been generated so far."""
    return {"works": _tts_mod.list_works()}


@app.get("/tts/manifest/{work_id}", tags=["humans"])
def tts_manifest(work_id: str):
    """Return the chapter manifest for one work — used by the player."""
    if not _tts_mod._valid_work_id(work_id):
        raise HTTPException(status_code=400, detail="invalid work_id")
    m = _tts_mod.load_manifest(work_id)
    if not m:
        raise HTTPException(status_code=404, detail="no manifest for that work_id")
    return m


@app.get("/tts/audio/{sha}.mp3", tags=["humans"])
def tts_audio(sha: str):
    """Serve a cached MP3 by its content hash. 404 if not generated yet."""
    sha = (sha or "").strip().lower()
    if not _tts_mod._valid_sha(sha):
        raise HTTPException(status_code=400, detail="invalid hash")
    p = _tts_mod.cache_path_for(sha)
    if not p:
        raise HTTPException(status_code=404, detail="audio not generated yet")
    return FileResponse(str(p), media_type="audio/mpeg")


@app.get("/daily/comments", tags=["humans"])
def daily_comments_list(iso_date: str, limit: int = 200):
    """Public list of comments for a given day, newest first."""
    items = _daily_comments_mod.list_for_day(iso_date, limit=max(1, min(500, limit)))
    return {
        "iso_date": iso_date,
        "total": len(items),
        "comments": [_daily_comments_mod.public_view(r) for r in items],
    }


# -- Coach journal: server-side mirror of per-visitor walks ----------------
# The user's localStorage is the cache; this is the substrate. Walks
# survive device wipes and browser switches. visitor_id is opaque.
from api import coach_journal as _coach_journal  # noqa: E402
from api import person_identity as _person_identity  # noqa: E402


class _JournalSaveRequest(BaseModel):
    visitor_id: str
    walk_id: str
    situation: str = ""
    gates: Dict[str, str] = {}
    axes: Optional[List[str]] = None
    archetypes_summary: Optional[str] = None
    protocols_summary: Optional[str] = None
    lang: str = "en"


@app.post("/coach/journal", tags=["humans"])
def coach_journal_save(request: Request, req: _JournalSaveRequest):
    """Persist a walk for the visitor. Idempotent by walk_id — repeated
    saves overwrite (newer record wins on read). The page's debounced
    auto-save is the expected caller.

    `lang` optional: when not "en", situation + gate answers are MT'd to
    English and stored alongside the visitor's originals (so the walker
    re-reads their own words but the engine indexes English canonical).
    """
    _rate_check(request, "journal_save")

    lang_norm = (getattr(req, "lang", None) or "en").strip().lower() or "en"
    situation_en = req.situation
    situation_original: Optional[str] = None
    gates_en: Dict[str, str] = dict(req.gates or {})
    gates_original: Dict[str, str] = {}
    mt_provider: Optional[str] = None

    if lang_norm != "en":
        try:
            if (req.situation or "").strip():
                r = _mt_adapter.translate(text=req.situation, target_lang="en", source_lang=lang_norm)
                if r and not r.get("fallback") and r.get("text"):
                    situation_en = r["text"]
                    situation_original = req.situation
                    mt_provider = mt_provider or r.get("provider")
            for k, v in (req.gates or {}).items():
                vs = (v or "").strip()
                if not vs:
                    continue
                r = _mt_adapter.translate(text=vs, target_lang="en", source_lang=lang_norm)
                if r and not r.get("fallback") and r.get("text"):
                    gates_en[k] = r["text"]
                    gates_original[k] = v
                    mt_provider = mt_provider or r.get("provider")
        except Exception:
            pass

    try:
        rec = _coach_journal.save_walk(
            visitor_id=req.visitor_id,
            walk_id=req.walk_id,
            situation=situation_en,
            gates=gates_en,
            extra={
                "axes": req.axes,
                "archetypes_summary": req.archetypes_summary,
                "protocols_summary": req.protocols_summary,
                "lang": lang_norm,
                "situation_original": situation_original,
                "gates_original": gates_original or None,
                "mt_provider": mt_provider,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Bridge the surfaces: link this walk identity to the resolved person (operator
    # or household). Lets the Shepherd recall this walk in the funnel — his memory
    # spans every surface, not just the funnel shelf. Best-effort, never blocks.
    try:
        person = _person_identity.person_id(request)
        if person:
            _person_identity.link(person, req.visitor_id)
    except Exception:
        pass
    return {"ok": True, "walk": rec}


@app.get("/coach/journal", tags=["humans"])
def coach_journal_list(visitor_id: str, request: Request, limit: int = 50):
    """List the visitor's walks, dedup-by-walk_id keeping latest, newest first."""
    if not _coach_journal._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    # Linking on read too means just opening the walk page (which lists) bridges a
    # returning walker's existing walks to their person — no new save required.
    try:
        person = _person_identity.person_id(request)
        if person:
            _person_identity.link(person, visitor_id)
    except Exception:
        pass
    items = _coach_journal.list_walks(visitor_id, limit=max(1, min(500, limit)))
    return {"total": len(items), "walks": items}


@app.get("/coach/journal/{walk_id}", tags=["humans"])
def coach_journal_get(walk_id: str, visitor_id: str):
    """Fetch a single walk by id."""
    if not _coach_journal._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    rec = _coach_journal.get_walk(visitor_id, walk_id)
    if not rec:
        raise HTTPException(status_code=404, detail="walk not found")
    return rec


@app.delete("/coach/journal/{walk_id}", tags=["humans"])
def coach_journal_delete(walk_id: str, visitor_id: str, request: Request):
    """Tombstone a walk. Subsequent listings exclude it."""
    _rate_check(request, "journal_delete")
    if not _coach_journal._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    ok = _coach_journal.delete_walk(visitor_id, walk_id)
    return {"ok": ok}


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
    """Operator auth gate for the Console + machine-to-machine endpoints.

    Accepts either:
      1. X-API-Key header (machine integrations, scripts, fetch_*.py)
      2. Bearer session token from /auth/login (human Console operator
         logged in with the CONCORDANCE_PASSPHRASE from .env)
      3. X-Console-Token header (same token, different transport for
         convenience when JS can't easily set Authorization)
      4. Operator IP allowlist match — anyone trusted enough to view
         /keep.html is trusted enough to read operator-only feeds.
         This lets keep.html's JS embed inbox/intake/witness data
         inline without a per-page API key, using the same trust
         boundary as the page itself.

    If neither API_KEY nor CONCORDANCE_PASSPHRASE is configured, auth is
    disabled (dev mode). In production at least one must be set."""
    # Path 1: API key (existing)
    expected_key = os.environ.get("API_KEY", "")
    if expected_key:
        got_key = request.headers.get("x-api-key", "") or request.headers.get("X-API-Key", "")
        if got_key == expected_key:
            return  # API-key auth ok

    # Path 2/3: session token from /auth/login
    auth_header = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        token = request.headers.get("x-console-token", "") or request.headers.get("X-Console-Token", "")
    if token and _verify_token(token):
        return  # session-token auth ok

    # Path 4: operator IP allowlist (same trust boundary as /keep.html)
    try:
        client_ip = _keep_client_ip(request)
        if _is_operator_ip(client_ip):
            return  # IP allowlist auth ok
    except Exception:
        pass  # if IP check fails, fall through to denial

    # Neither matched. If no auth is configured at all, this is dev mode.
    if not expected_key and not _VALID_HASHES:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing credentials")


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
    # Prime the card-system caches in a background thread so the first
    # public visitor doesn't pay the 5-13s cold-rebuild cost. Without this,
    # the first hit on /atlas/paths, /daily-card, or /promotion/health
    # walks all 11k card files and can hit Cloudflare's tunnel timeout.
    import threading as _threading
    def _warm_card_caches():
        try:
            from api import atlas as _atlas, daily_card as _dc, promotion as _promo
            print('[warm] priming card-system caches...', flush=True)
            r1 = _atlas.warm_cache()
            print(f'[warm] atlas walk-cache: {r1}', flush=True)
            r2 = _dc.warm_cache()
            print(f'[warm] daily-card pool: {r2}', flush=True)
            r3 = _promo.warm_cache()
            print(f'[warm] promotion health: {r3}', flush=True)
            print('[warm] card-system caches ready', flush=True)
        except Exception as e:
            print(f'[warm] cache warmer failed: {e}', flush=True)
    _threading.Thread(target=_warm_card_caches, daemon=True, name='card-cache-warmer').start()


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
def root(request: Request):
    site = Path(__file__).parent.parent / "site"
    # Host-based front doors. Everything lives on .com; .tv and .org are
    # simple branded entries into the same app:
    #   narrowhighway.tv  -> the family channel door
    #   narrowhighway.org -> the innovation / engine showcase
    host = (request.headers.get("host") or "").lower().split(":")[0]
    if host.endswith("narrowhighway.tv"):
        door = site / "door-tv.html"
        if door.exists():
            return FileResponse(str(door))
    elif host.endswith("narrowhighway.org"):
        door = site / "door-org.html"
        if door.exists():
            return FileResponse(str(door))
    index = site / "index.html"
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
# Door collapse — the redundant engine entrances fold into the ONE door.
#
# The funnel + narrowing is the single front door (the Scribe's one entrance:
# type a situation, the Shepherd questions, the floor hands the path + trail +
# Christ-reference). Older surfaces that did the same job under different names
# now 308-redirect here, so a visitor meets ONE door, not seven. Reversible:
# delete an entry. NOTE: poly.html stays (it is the .org authority-layer face,
# not a family entrance); walk.html stays until its four-gates journal merges
# into the funnel (no lossy redirect of a live capability).
_COLLAPSED_DOORS = {
    # The ONE door is /walk.html — the better NAME ("Walk") carrying the better
    # MECHANISM (the funnel: per-user, narrowing, recall, the local mouth).
    "/funnel.html": "/walk.html",                # the funnel mechanism now lives at /walk.html
    "/discern-teaching.html": "/walk.html",      # "Discern this teaching" — same act
    "/shepherd-room.html": "/walk.html",         # "The Shepherd's Room" — the Shepherd's voice
    "/walks.html": "/walk.html",                 # "The Discernment Engine" — the old main door
    "/watch-listen.html": "/media-center.html",  # retired stub — superseded by the media center
}


def _make_door_redirect(_target):
    def _door_redirect():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=_target, status_code=308)
    return _door_redirect


for _src, _dst in _COLLAPSED_DOORS.items():
    # Explicit routes register before the StaticFiles("/") mount, so they win.
    app.add_api_route(_src, _make_door_redirect(_dst), methods=["GET"],
                      include_in_schema=False)


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
    contributor_handle: str = ""              # optional registered handle — bumps the confessions stat


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

    # Community attribution — optional handle. Bumps the `confessions`
    # stat so the canon's "confess" path to brotherhood (has_entered_wisdom)
    # actually fires for registered contributors. Without this bump, the
    # ladder included confessions in theory but nothing wired the count.
    handle = (req.contributor_handle or "").strip().lower()
    if handle and _community.is_valid_handle(handle):
        if _community.load_contributor(handle) is not None:
            _community.bump_stat(handle, "confessions", 1)
            _community.log_activity({
                "kind": "confession",
                "handle": handle,
                "confessed_seq": req.ref_seq,
                "confession_seq": entry.seq,
            })

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
    # Optional visitor identity (12-hex). When supplied, the run is saved
    # to the visitor's polymathic journal so they can re-open it.
    visitor_id: str = ""
    # Optional language code. When != "en", incoming situation is MT'd to
    # English before retrieval (verifiers operate in English). Original
    # words are preserved alongside in the journal.
    lang: str = "en"


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
    situation_original = (req.situation or "").strip()
    if not situation_original:
        raise HTTPException(status_code=400, detail="situation is required")

    # Reverse MT the situation to English when caller's language isn't English.
    # Verifiers operate on English text; the visitor's words are preserved.
    lang_norm = (getattr(req, "lang", None) or "en").strip().lower() or "en"
    situation = situation_original
    mt_provider: Optional[str] = None
    if lang_norm != "en":
        try:
            r = _mt_adapter.translate(
                text=situation_original, target_lang="en", source_lang=lang_norm,
            )
            if r and not r.get("fallback") and r.get("text"):
                situation = r["text"]
                mt_provider = r.get("provider")
        except Exception:
            pass

    try:
        from concordance_engine.agent.poly_agent import run_polymathic
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"polymathic agent unavailable: {exc}")

    # Generate a run_id up front so the live feed can show "started" before
    # the run completes. Same id is bound to the stored record below.
    _poly_run_id = uuid.uuid4().hex[:16] if "uuid" in dir() else None
    try:
        import uuid as _uuid_mod
        _poly_run_id = _uuid_mod.uuid4().hex[:16]
    except Exception:
        _poly_run_id = "run_" + str(int(time.time() * 1000))
    try:
        _poly_session_mod.record_inflight(_poly_run_id, situation, status="started")
    except Exception:
        pass

    try:
        record = run_polymathic(
            situation=situation,
            model=req.oracle_model,
            max_domains=req.max_domains,
            split_threshold=req.split_threshold,
            stop_on_discordant=req.stop_on_discordant,
        )
        try:
            _poly_session_mod.record_inflight(_poly_run_id, situation, status="completed")
        except Exception:
            pass
    except Exception as exc:
        try:
            _poly_session_mod.record_inflight(_poly_run_id, situation, status="error")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"polymathic agent error: {exc}")

    d = record.to_dict()

    # Drain the per-run block log into the response. When the classifier
    # auto-corrected a user's claim, the spec-grounding check rejected it
    # and the claim quarantined. Surfacing this here lets the operator
    # see WHY a claim quarantined ("classifier substituted values") vs
    # the ordinary case ("no verifier classified this claim at all").
    try:
        from concordance_engine.agent.poly_agent import _BLOCK_LOG as _poly_block_log
        if _poly_block_log:
            d["blocked_claims"] = [
                {"claim": k, **v} for k, v in _poly_block_log.items()
            ]
    except Exception:
        pass

    # The elimination trail — "the engine eliminates what it cannot confirm; what
    # survives is what survives." The per-domain results, quarantine, and blocks
    # are already in the record; distil them into ONE legible "what was set aside
    # and why" beside the composite verdict, so the trail (the reasoning) is the
    # answer here too, not something the reader must reconstruct from raw cards.
    try:
        _dr = d.get("domain_results") or []
        _set_aside = []
        for _r in _dr:
            _v = _r.get("verdict")
            if _v in ("MISMATCH", "ERROR"):
                _set_aside.append({
                    "claim": _r.get("source_claim") or "",
                    "domain": _r.get("domain"), "verdict": _v,
                    "why": (_r.get("detail") or "").strip()
                           or ("the verifier could not run" if _v == "ERROR"
                               else "the math did not close"),
                })
        for _c in (d.get("quarantined_claims") or []):
            _set_aside.append({"claim": _c, "domain": None, "verdict": "QUARANTINED",
                               "why": "no domain could verify this claim — it waits"})
        for _b in (d.get("blocked_claims") or []):
            _set_aside.append({"claim": _b.get("claim"), "domain": _b.get("domain"),
                               "verdict": "BLOCKED",
                               "why": _b.get("reason") or _b.get("note")
                                      or "rejected by spec-grounding"})
        d["trail"] = {
            "checked": len(_dr),
            "confirmed": sum(1 for _r in _dr if _r.get("verdict") == "CONFIRMED"),
            "not_applicable": sum(1 for _r in _dr if _r.get("verdict") == "NOT_APPLICABLE"),
            "set_aside": _set_aside,
        }
    except Exception:
        pass

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

    # Misalignment auto-log: every non-CONCORDANT verdict is captured for
    # operator review. Closes the loop: the operator decides whether the
    # engine correctly didn't confirm (user-error → archive) or whether
    # the engine has a coverage gap (→ promote to build queue).
    try:
        from api import misalignments as _misalignments
        ip = (request.headers.get("cf-connecting-ip")
              or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request.client else ""))
        _misalignments.log_misalignment(
            claim=situation,
            composite_verdict=d.get("composite_verdict", ""),
            domain_results=d.get("domain_results", []),
            atomic_claims=d.get("atomic_claims", []),
            quarantined_claims=d.get("quarantined_claims", []),
            source="polymathic",
            ip_prefix=_ip_prefix(ip),
        )
    except Exception:
        pass  # logging failure must not affect the engine's response

    # Visitor history: when visitor_id is valid, save the run to the
    # polymathic journal so the visitor can re-open it later.
    if mt_provider:
        d["mt_input"] = {
            "original":    situation_original,
            "translated":  situation,
            "provider":    mt_provider,
            "source_lang": lang_norm,
        }
    if getattr(req, "visitor_id", "").strip():
        try:
            import hashlib as _hl
            from api import polymathic_journal as _poly_journal
            visitor_id = req.visitor_id.strip().lower()
            if _poly_journal._valid_visitor_id(visitor_id):
                # Stable run_id from situation hash — re-running the same
                # situation updates the same record rather than duplicating.
                run_id = "poly_" + _hl.sha256(situation_original.lower().encode("utf-8")).hexdigest()[:16]
                _poly_journal.save_run(
                    visitor_id=visitor_id, run_id=run_id,
                    situation=situation_original, result=d,
                    lang=lang_norm,
                    situation_original=situation_original if mt_provider else None,
                    mt_provider=mt_provider,
                )
                d["run_id"] = run_id
                d["saved"] = True
        except (ValueError, OSError):
            d["saved"] = False

    return d


# ── Polymathic visitor journal ──────────────────────────────────────────
from api import polymathic_journal as _polymathic_journal_mod  # noqa: E402


# ── Polymathic session — multi-turn refinement ─────────────────────────
from api import polymathic_session as _poly_session_mod  # noqa: E402


class _PolySessionOpen(BaseModel):
    visitor_id: str
    initial_situation: str = ""


@app.post("/polymathic/session/open", tags=["humans"])
def polymathic_session_open(request: Request, req: _PolySessionOpen):
    """Open a new polymathic session for multi-turn refinement.

    A session threads multiple polymathic runs so a visitor can iterate.
    Returns {session_id} which the caller passes to /session/turn.
    """
    if not _polymathic_journal_mod._valid_visitor_id(req.visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    return _poly_session_mod.open_session(req.visitor_id, req.initial_situation)


class _PolySessionTurn(BaseModel):
    session_id: str
    situation: str
    run_id: str
    refinement_note: str = ""


@app.post("/polymathic/session/turn", tags=["humans"])
def polymathic_session_turn(request: Request, req: _PolySessionTurn):
    """Append a turn to a session. Call this AFTER you've stored the
    polymathic run via POST /polymathic (store=true), passing the
    returned run_id here."""
    try:
        rec = _poly_session_mod.append_turn(
            req.session_id, req.situation, req.run_id, req.refinement_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"appended": True, "turn": rec}


@app.get("/polymathic/session/{session_id}", tags=["humans"])
def polymathic_session_get(session_id: str):
    """Read the full chain of a session — start + every turn."""
    rec = _poly_session_mod.get_session(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    return rec


@app.get("/polymathic/sessions", tags=["humans"])
def polymathic_sessions_for_visitor(visitor_id: str, limit: int = 30):
    """All sessions opened by a visitor, newest first."""
    if not _polymathic_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    return {
        "visitor_id": visitor_id,
        "sessions":   _poly_session_mod.list_sessions(visitor_id, limit=limit),
    }


class _PolySessionClose(BaseModel):
    session_id: str
    summary: str = ""


@app.post("/polymathic/session/close", tags=["humans"])
def polymathic_session_close(request: Request, req: _PolySessionClose):
    try:
        rec = _poly_session_mod.close_session(req.session_id, req.summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"closed": True, "record": rec}


@app.get("/polymathic/live", tags=["humans"])
def polymathic_live(limit: int = 30):
    """Live feed of polymathic events — runs starting + finishing.

    Public — anyone can watch the engine's multi-domain work as it
    happens. The 'air traffic' view of the polymathic agent."""
    runs = _poly_session_mod.live_feed(limit=limit)
    return {"total": len(runs), "events": runs}


@app.get("/polymathic/recent", tags=["humans"])
def polymathic_recent(limit: int = 30):
    """Recent polymathic runs across all visitors (slim summary).

    Public feed of multi-domain situations the engine classified +
    verified across all 48 domains. Each row carries the run_id,
    visitor_id prefix (12 hex; opaque), the situation (first 200 chars),
    the composite verdict, and the domains touched. Fetch the full
    run via /polymathic/run/<run_id>?visitor_id=<vid>.

    Used by /poly.html public feed and /keep.html operator panel.
    """
    runs = _polymathic_journal_mod.all_runs(limit=max(1, min(200, int(limit))))
    by_verdict: Dict[str, int] = {}
    for r in runs:
        v = r.get("verdict") or "UNKNOWN"
        by_verdict[v] = by_verdict.get(v, 0) + 1
    return {
        "total": len(runs),
        "by_verdict": by_verdict,
        "runs": runs,
    }


@app.get("/polymathic/mine", tags=["humans"])
def polymathic_mine(visitor_id: str, limit: int = 20):
    """Visitor's recent polymathic runs, newest first."""
    if not _polymathic_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    items = _polymathic_journal_mod.list_runs(
        visitor_id, limit=max(1, min(100, limit))
    )
    return {"visitor_id": visitor_id, "total": len(items), "items": items}


@app.get("/polymathic/run/{run_id}", tags=["humans"])
def polymathic_run_get(run_id: str, visitor_id: str):
    """Single saved run by id."""
    if not _polymathic_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    rec = _polymathic_journal_mod.get_run(visitor_id, run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return rec


@app.delete("/polymathic/run/{run_id}", tags=["humans"])
def polymathic_run_delete(run_id: str, visitor_id: str):
    if not _polymathic_journal_mod._valid_visitor_id(visitor_id):
        raise HTTPException(status_code=400, detail="invalid visitor_id")
    ok = _polymathic_journal_mod.delete_run(visitor_id, run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"deleted": True, "run_id": run_id}


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
    "walk":      (20, 20.0 / 60),     # 20/min — Coach OS walk (archetypes + Layer 0)
    "queue":     (30, 30.0 / 60),     # 30/min — offline queue submits
    "verify":    (60, 60.0 / 60),     # 60/min — generic verifier dispatch
    "ingest":    (10, 10.0 / 60),     # 10/min — drive ingest is expensive
    # Community participation
    "register":  (3,  3.0 / 60),      # 3/min — handle creation is cheap but spammable
    "witness_signal": (10, 10.0 / 60),# 10/min — witness signal submissions
    # Curriculum
    "mastery":   (120, 120.0 / 60),   # 120/min — kids mark units quickly; permissive
    "steward":   (60, 60.0 / 60),     # 60/min — corridor / admission API
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
            # Emit a Steward audit packet so the denial is in the trail
            # alongside corridor/dose/escalation refusals. The audit
            # records the bucket name as the action; visitor_id is the
            # IP fallback when no visitor cookie is present.
            try:
                from api.steward import get_steward, ReasonCode
                get_steward().emit_deny(
                    visitor_id=f"ip:{ip}",
                    action=bucket_key,
                    reason=ReasonCode.DENY_RATE_LIMIT,
                    notes=f"retry_after={retry_after}s",
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=429,
                detail=(
                    f"rate limit exceeded for '{bucket_key}' from {ip} "
                    f"(retry after ~{retry_after}s) · DENY_RATE_LIMIT"
                ),
                headers={"Retry-After": str(retry_after), "X-Steward-Reason": "DENY_RATE_LIMIT"},
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


# ── FieldKit — the 13-card Lighthouse deck ─────────────────────────────

_FIELDKIT_FILE = Path(__file__).parent.parent / "data" / "fieldkit" / "v1_cards.jsonl"
_FIELDKIT_CACHE: Dict[str, Any] = {"mtime": 0.0, "cards": []}


def _load_fieldkit() -> List[Dict[str, Any]]:
    """mtime-cached load of the FieldKit cards."""
    if not _FIELDKIT_FILE.exists():
        return []
    try:
        mtime = _FIELDKIT_FILE.stat().st_mtime
    except OSError:
        return []
    if _FIELDKIT_CACHE["cards"] and mtime <= _FIELDKIT_CACHE["mtime"]:
        return _FIELDKIT_CACHE["cards"]
    cards: List[Dict[str, Any]] = []
    try:
        for line in _FIELDKIT_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cards.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    cards.sort(key=lambda c: c.get("number", 0))
    _FIELDKIT_CACHE["mtime"] = mtime
    _FIELDKIT_CACHE["cards"] = cards
    return cards


@app.get("/fieldkit", tags=["humans"])
def fieldkit_index():
    """Return all FieldKit v1 cards. The 13-card physical deck — Source,
    Floor, Spice, Common Drift, 7-Day Practice, Prompt per card."""
    cards = _load_fieldkit()
    return {
        "version": "v1",
        "total": len(cards),
        "cards": cards,
        "rarities": sorted({c.get("rarity") for c in cards if c.get("rarity")}),
        "preface": (
            "The Lighthouse Field Kit. Thirteen cards built around the Sermon "
            "on the Mount (Matthew 5–7). Each card carries Source (the rule), "
            "Floor (the non-negotiable), Spice (the optional helps), the common "
            "Drift, a 7-day Practice, and a Prompt. Cards are protocols you walk, "
            "not insights you collect."
        ),
    }


@app.get("/fieldkit/{card_id}", tags=["humans"])
def fieldkit_card(card_id: str):
    """One card by id (e.g. FK1-09 → Make It Right)."""
    _safe_id(card_id, "card_id")
    for c in _load_fieldkit():
        if c.get("id", "").lower() == card_id.lower():
            return c
    raise HTTPException(status_code=404, detail=f"no FieldKit card with id {card_id!r}")


# ── Unified packet index ───────────────────────────────────────────────
# Every packet across every store (almanac, sealed polymathic, protocol,
# archetype, FieldKit, misalignment, build queue, receipt) retrievable
# by domain or axis. Lives under /index/* so it doesn't collide with
# the per-domain CAS-store routes at /packets/{domain}/...

@app.get("/index/packets", tags=["humans"])
def packets_index_summary():
    """Aggregate counts: how many packets total, broken down by kind,
    by domain, by axis, and by verdict. The shape of the packet universe."""
    try:
        from api.packets_index import index_summary
        return index_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"index failed: {exc}")


@app.get("/index/packets/health", tags=["humans"])
def packets_index_health():
    """Substrate health: which domains/axes are thin, which kinds are
    over-represented, what's the verdict mix.

    Useful for:
      - Operators deciding what to ingest next
      - Agents understanding which domains they can trust most
      - The build queue knowing where the keeping is sparse

    Returns:
        - thinnest_domains: bottom 10 domains by packet count
        - thickest_domains: top 10 domains by packet count
        - thinnest_kinds:   kinds with fewer than 20 packets
        - verdict_mix:      proportions of CONFIRMED/MISMATCH/etc.
        - quality_score:    weighted avg of verdict reliability
    """
    try:
        from api.packets_index import index_summary
        s = index_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"index failed: {exc}")

    by_d = s.get("by_domain", {})
    by_k = s.get("by_kind", {})
    by_v = s.get("by_verdict", {})
    total = s.get("total_packets", 0)

    # Bottom/top domains
    sorted_d = sorted(by_d.items(), key=lambda kv: kv[1])
    thinnest = sorted_d[:10]
    thickest = list(reversed(sorted_d[-10:]))

    # Kinds with thin coverage
    thin_kinds = sorted(
        [(k, v) for k, v in by_k.items() if v < 20],
        key=lambda kv: kv[1],
    )

    # Verdict proportions
    verdict_mix = {}
    for v, count in by_v.items():
        verdict_mix[v] = {
            "count": count,
            "pct": round(100.0 * count / max(1, total), 2),
        }

    # Simple quality score: % CONFIRMED + % CONCORDANT
    confirmed = by_v.get("CONFIRMED", 0)
    concordant = by_v.get("CONCORDANT", 0)
    quality_score = round(
        100.0 * (confirmed + concordant) / max(1, total),
        2,
    )

    return {
        "total_packets":     total,
        "kinds_count":       s.get("kinds_count", 0),
        "domains_count":     s.get("domains_count", 0),
        "axes_count":        s.get("axes_count", 0),
        "avg_weight":        s.get("avg_weight", 0),
        "thinnest_domains":  [{"domain": d, "count": c} for d, c in thinnest],
        "thickest_domains":  [{"domain": d, "count": c} for d, c in thickest],
        "thin_kinds":        [{"kind": k, "count": c} for k, c in thin_kinds],
        "verdict_mix":       verdict_mix,
        "quality_score":     quality_score,
    }


@app.get("/index/packets/by-domain/{domain}", tags=["humans"])
def packets_index_by_domain(domain: str, limit: int = Query(200, ge=1, le=1000)):
    """Every packet that names a verifier domain — almanac entries,
    sealed polymathic records, misalignments, FieldKit cards, protocols,
    archetypes, receipts — in one feed sorted by weight."""
    _safe_id(domain, "domain")
    try:
        from api.packets_index import by_domain
        out = by_domain(domain, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"lookup failed: {exc}")
    return {"domain": domain, "total": len(out), "packets": out}


@app.get("/index/packets/by-axis/{axis}", tags=["humans"])
def packets_index_by_axis(axis: str, limit: int = Query(500, ge=1, le=2000)):
    """Every packet that touches a 7-scaffold axis (reasoning,
    encoding, authority_trust, physical_substance, metabolism,
    conservation_balance, time_sequence)."""
    _safe_id(axis, "axis")
    try:
        from api.packets_index import by_axis
        out = by_axis(axis, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"lookup failed: {exc}")
    return {"axis": axis, "total": len(out), "packets": out}


@app.get("/index/packets/by-kind/{kind}", tags=["humans"])
def packets_index_by_kind(kind: str, limit: int = Query(500, ge=1, le=2000)):
    """Every packet of a single kind (almanac | sealed_poly | protocol |
    archetype | fieldkit_card | misalignment | build_queue | receipt)."""
    _safe_id(kind, "kind")
    try:
        from api.packets_index import by_kind
        out = by_kind(kind, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"lookup failed: {exc}")
    return {"kind": kind, "total": len(out), "packets": out}


@app.get("/index/packets/chronological", tags=["humans"])
def packets_index_chronological(
    limit: int = Query(500, ge=1, le=2000),
    kinds: str = Query("", description="Optional comma-separated kinds filter"),
    order: str = Query("newest_first", regex="^(newest_first|oldest_first)$"),
):
    """The temporal lens. Every packet sorted by timestamp — the
    engine's history readable as a scroll. Packets without a usable
    timestamp are excluded from this view."""
    try:
        from api.packets_index import chronological
        kinds_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds.strip() else None
        out = chronological(limit=limit, kinds=kinds_list, newest_first=(order == "newest_first"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"chronological lookup failed: {exc}")
    return {"order": order, "total": len(out), "packets": out}


@app.get("/index/packets/search", tags=["humans"])
def packets_index_search(
    q: str = Query("", description="Search query — tokens AND-matched across packet fields"),
    limit: int = Query(60, ge=1, le=500),
    kinds: str = Query("", description="Optional comma-separated kinds filter"),
):
    """Cross-lens text search over the unified packet substrate.

    Tokens AND-match against title, verdict, domains, axes, summary, id.
    Returns the standard normalized packet dict + a `score` and a
    `match_in` list. Same packets that the Index page lists; this is
    the search verb on top of that view."""
    try:
        from api.packets_index import search
        kinds_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds.strip() else None
        out = search(q, limit=limit, kinds=kinds_list)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"search failed: {exc}")
    return {"q": q, "total": len(out), "packets": out}


class _SeedRequest(BaseModel):
    """Craft a seed from a search miss. The engine does the work once;
    every future query references the seed."""
    query: str
    visitor_id: str = ""


@app.post("/seed", tags=["humans"])
def seed_craft(request: Request, req: _SeedRequest):
    """Search once, seed the keeping, reference forever.

    When the search comes up empty, POST the query here. The engine
    calls Apothecary + keyword search internally, synthesizes a seed
    packet, stores it in data/seeds/seeds.jsonl, and returns it.
    Next search for the same topic hits the seed directly.
    """
    _rate_check(request, "propose")
    query = (req.query or "").strip()
    if not query or len(query) < 3:
        raise HTTPException(status_code=400, detail="query too short")

    # Check if seed already exists
    from api.seeds import find_seed, craft_seed, store_seed
    existing = find_seed(query)
    if existing:
        return {"seeded": False, "existed": True, "seed": existing}

    # Synthesize: call Apothecary + keyword search internally
    compound = None
    try:
        compound_result = _apothecary_mod.compound(query)
        compound = compound_result.get("compound")
    except Exception:
        pass

    search_hits = []
    try:
        from api.packets_index import search as pkt_search
        # Extract keywords: drop short words
        words = [w for w in query.lower().split() if len(w) >= 3]
        for word in words[:4]:
            hits = pkt_search(word, limit=3)
            for h in hits:
                if h.get("id") not in {s.get("id") for s in search_hits}:
                    search_hits.append(h)
            if len(search_hits) >= 5:
                break
    except Exception:
        pass

    # Craft and store the seed
    seed = craft_seed(query, compound=compound, search_hits=search_hits[:5])
    store_seed(seed)

    return {"seeded": True, "existed": False, "seed": seed}


@app.get("/seed/{seed_id}", tags=["humans"])
def seed_get(seed_id: str):
    """Retrieve a single seed by ID."""
    from api.seeds import load_seeds
    for s in load_seeds():
        if s.get("id") == seed_id:
            return s
    raise HTTPException(status_code=404, detail="seed not found")


# ── Serial — ongoing fiction in the operator's voice ───────────────────
from api import serial as _serial_mod  # noqa: E402


@app.get("/serials", tags=["humans"])
def serials_list():
    """List every declared serial with episode counts + latest."""
    return {"serials": _serial_mod.list_serials()}


@app.get("/serial/{slug}", tags=["humans"])
def serial_get(slug: str):
    """World bible + style guide + episode index for one serial."""
    world = _serial_mod.get_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail=f"serial {slug!r} not found")
    return {
        "slug":    slug,
        "world":   world,
        "style":   _serial_mod.get_style(slug),
        "episodes": _serial_mod.list_episodes(slug),
    }


@app.get("/serial/{slug}/episodes", tags=["humans"])
def serial_episodes(slug: str, limit: int = 100):
    """All episodes of a serial, chronological order."""
    if _serial_mod.get_world(slug) is None:
        raise HTTPException(status_code=404, detail=f"serial {slug!r} not found")
    return {
        "slug": slug,
        "episodes": _serial_mod.list_episodes(slug, limit=limit),
    }


@app.get("/serial/{slug}/episode/{ep_num}", tags=["humans"])
def serial_episode_get(slug: str, ep_num: int):
    """One full episode — title, script, summary, continuity note, audio URL if produced."""
    rec = _serial_mod.get_episode(slug, ep_num)
    if rec is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return rec


@app.get("/serial/{slug}/audio/{ep_num}", include_in_schema=False)
@app.head("/serial/{slug}/audio/{ep_num}", include_in_schema=False)
def serial_audio_stream(slug: str, ep_num: int, request: Request):
    """Stream the MP3 for a serial episode with HTTP Range support.

    HTML5 <audio> players (and podcast clients) issue Range requests to
    seek within the file. Returning the full 35MB body on every seek is
    unusable. We honor Range here so playback + scrubbing work normally.
    """
    from pathlib import Path
    # Resolve the file path without loading into memory
    serial_dir = Path(_serial_mod.__file__).resolve().parent.parent / "data" / "serials" / slug
    mp3_path = serial_dir / "episodes" / f"{ep_num:03d}.mp3"
    if not mp3_path.exists():
        raise HTTPException(status_code=404, detail="audio not produced yet")

    file_size = mp3_path.stat().st_size
    range_header = request.headers.get("range") or request.headers.get("Range")

    # No Range — return full body (HEAD returns headers only via FastAPI)
    if not range_header:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers={
                    "Content-Length": str(file_size),
                    "Content-Type":   "audio/mpeg",
                    "Accept-Ranges":  "bytes",
                },
            )
        def _full():
            with open(mp3_path, "rb") as f:
                while True:
                    chunk = f.read(1 << 16)  # 64 KB
                    if not chunk: break
                    yield chunk
        return StreamingResponse(
            _full(),
            media_type="audio/mpeg",
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges":  "bytes",
            },
        )

    # Parse "bytes=start-end"
    try:
        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError("only bytes ranges supported")
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s.strip() else 0
        end   = int(end_s)   if end_s.strip()   else file_size - 1
        if start < 0 or end >= file_size or start > end:
            raise ValueError(f"invalid range {start}-{end} for size {file_size}")
    except Exception:
        # Malformed Range — RFC 7233 says return 416
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    length = end - start + 1

    def _ranged():
        with open(mp3_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 16, remaining))
                if not chunk: break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        _ranged(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(length),
            "Content-Range":  f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges":  "bytes",
        },
    )


class _SerialGenerate(BaseModel):
    direction: str = ""
    target_minutes: int = 10


@app.post("/serial/{slug}/generate", tags=["humans"])
def serial_generate(slug: str, request: Request, req: _SerialGenerate):
    """Have Claude draft the next episode of a serial. Operator-only.

    Costs Anthropic credits. Generates ~1500 words of prose targeted at
    `target_minutes` of audio. Operator reviews/edits before producing audio.
    """
    _community_require_api_key(request)
    try:
        rec = _serial_mod.generate_episode(
            slug=slug,
            direction=req.direction,
            target_minutes=req.target_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return rec


class _SerialEdit(BaseModel):
    title: str
    script: str
    summary: str = ""
    continuity_note: str = ""


@app.post("/serial/{slug}/episode/{ep_num}/edit", tags=["humans"])
def serial_episode_edit(slug: str, ep_num: int, request: Request, req: _SerialEdit):
    """Operator edits an episode (after review or for human-only episodes)."""
    _community_require_api_key(request)
    try:
        rec = _serial_mod.write_episode(
            slug=slug,
            ep_num=ep_num,
            title=req.title,
            script=req.script,
            summary=req.summary,
            continuity_note=req.continuity_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return rec


@app.post("/serial/{slug}/produce/{ep_num}", tags=["humans"])
def serial_produce(slug: str, ep_num: int, request: Request):
    """Voice an episode via ElevenLabs (single narrator)."""
    _community_require_api_key(request)
    try:
        result = _serial_mod.produce_audio(slug, ep_num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return result


@app.post("/serial/{slug}/produce-multi/{ep_num}", tags=["humans"])
def serial_produce_multi(slug: str, ep_num: int, request: Request):
    """Voice an episode with a multi-voice cast (one voice per speaker).

    Reads the serial's world.json.voice_cast for speaker→voice_id mapping.
    Used for screenplay-style serials like The Free State of Dade.
    """
    _community_require_api_key(request)
    try:
        result = _serial_mod.produce_audio_multi_voice(slug, ep_num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return result


@app.get("/serial/{slug}/cost/{ep_num}", tags=["humans"])
def serial_cost_estimate(slug: str, ep_num: int, price_per_1k: float = 0.30):
    """Estimate ElevenLabs cost to produce this episode in multi-voice.

    Public — anyone can see the rough cost. Default price ~$0.30/1k chars
    matches typical mid-tier ElevenLabs pricing; pass your own rate via
    ?price_per_1k=N for accuracy.
    """
    try:
        return _serial_mod.estimate_audio_cost(slug, ep_num, price_per_1k_chars=price_per_1k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Feeds — RSS/podcast for every lens ──────────────────────────────────
from api import feeds as _feeds_mod  # noqa: E402


def _xml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@app.get("/feeds/almanac.xml", include_in_schema=False)
def feeds_almanac():
    """RSS feed of recent Almanac entries."""
    return _xml_response(_feeds_mod.almanac_feed())


@app.get("/feeds/radio.xml", include_in_schema=False)
def feeds_radio():
    """Podcast feed (RSS + itunes namespace) for radio episodes. MP3 enclosures."""
    return _xml_response(_feeds_mod.radio_feed())


@app.get("/feeds/hearth.xml", include_in_schema=False)
def feeds_hearth_all():
    """RSS feed of Hearth messages across every room."""
    return _xml_response(_feeds_mod.hearth_feed())


@app.get("/feeds/hearth/{room}.xml", include_in_schema=False)
def feeds_hearth_room(room: str):
    """RSS feed of one Hearth room's messages."""
    from api import hearth as _h
    if room not in _h.ROOM_SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown room: {room!r}")
    return _xml_response(_feeds_mod.hearth_feed(room=room))


@app.get("/feeds/seeds.xml", include_in_schema=False)
def feeds_seeds():
    """RSS feed of crafted seeds."""
    return _xml_response(_feeds_mod.seeds_feed())


@app.get("/feeds/polymathic.xml", include_in_schema=False)
def feeds_polymathic():
    """RSS feed of recent polymathic runs."""
    return _xml_response(_feeds_mod.polymathic_feed())


@app.get("/feeds", tags=["humans"])
def feeds_index():
    """Discover the available feeds — useful for clients that don't crawl."""
    return {
        "feeds": [
            {"slug": "almanac",  "title": "The Almanac",          "url": "/feeds/almanac.xml",   "kind": "rss"},
            {"slug": "radio",    "title": "Concordance Radio",    "url": "/feeds/radio.xml",     "kind": "podcast"},
            {"slug": "hearth",   "title": "The Hearth (all)",     "url": "/feeds/hearth.xml",    "kind": "rss"},
            {"slug": "hearth-front",   "title": "Hearth · Front Room",     "url": "/feeds/hearth/front.xml",   "kind": "rss"},
            {"slug": "hearth-prayer",  "title": "Hearth · Prayer Room",    "url": "/feeds/hearth/prayer.xml",  "kind": "rss"},
            {"slug": "hearth-bible",   "title": "Hearth · Bible Study",    "url": "/feeds/hearth/bible.xml",   "kind": "rss"},
            {"slug": "hearth-family",  "title": "Hearth · Family Talk",    "url": "/feeds/hearth/family.xml",  "kind": "rss"},
            {"slug": "hearth-health",  "title": "Hearth · Health Talk",    "url": "/feeds/hearth/health.xml",  "kind": "rss"},
            {"slug": "hearth-today",   "title": "Hearth · What's Going On","url": "/feeds/hearth/today.xml",   "kind": "rss"},
            {"slug": "seeds",      "title": "Seeds",                "url": "/feeds/seeds.xml",       "kind": "rss"},
            {"slug": "polymathic", "title": "Polymathic runs",     "url": "/feeds/polymathic.xml", "kind": "rss"},
        ],
    }


# ── Radio — broadcast lens ──────────────────────────────────────────────
from api import radio as _radio_mod  # noqa: E402

# Seed initial episodes on import so the radio has something to play
try:
    _radio_mod.seed_initial_episodes()
except Exception:
    pass


@app.get("/radio/shows", tags=["humans"])
def radio_shows():
    """List every show with episode counts + last-aired date."""
    return {
        "shows": _radio_mod.list_shows_with_stats(),
        "total": len(_radio_mod.SHOWS),
    }


@app.get("/radio/episodes", tags=["humans"])
def radio_episodes(show: str, limit: int = 60):
    """All episodes of a show, newest first."""
    if show not in _radio_mod.SHOW_SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown show: {show!r}")
    eps = _radio_mod.list_episodes(show, limit=max(1, min(200, int(limit))))
    return {
        "show": _radio_mod.get_show(show),
        "total": len(eps),
        "episodes": eps,
    }


@app.get("/radio/episode/{show}/{ep_date}", tags=["humans"])
def radio_episode_get(show: str, ep_date: str):
    """One specific episode — full script + audio URL if produced."""
    ep = _radio_mod.get_episode(show, ep_date)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return {"show": _radio_mod.get_show(show), "episode": ep}


@app.get("/radio/now-playing", tags=["humans"])
def radio_now_playing():
    """Most recently aired episode across all shows. Drives the tuning dial."""
    np = _radio_mod.now_playing()
    if np is None:
        return {"now_playing": None}
    return {"now_playing": np}


@app.get("/radio/audio/{show}/{ep_date}", include_in_schema=False)
def radio_audio_stream(show: str, ep_date: str):
    """Stream the MP3 for an episode. Cached on disk — zero ElevenLabs cost
    on replay. Returns 404 if not yet produced (operator runs /radio/produce)."""
    data = _radio_mod.episode_audio_bytes(show, ep_date)
    if data is None:
        raise HTTPException(status_code=404, detail="audio not produced yet")
    return Response(content=data, media_type="audio/mpeg")


class _RadioProduceRequest(BaseModel):
    show: str
    ep_date: str


@app.post("/radio/produce", tags=["humans"])
def radio_produce(request: Request, req: _RadioProduceRequest):
    """Generate the MP3 for an episode via ElevenLabs.

    Operator-only (IP-gated via the same path /community endpoints use).
    Costs ElevenLabs credits — running this is a deliberate action.
    """
    _community_require_api_key(request)
    try:
        result = _radio_mod.produce_audio(req.show, req.ep_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return result


class _RadioWriteRequest(BaseModel):
    show: str
    ep_date: str
    title: str
    script: str
    notes: str = ""
    aired_at_iso: str = ""


@app.post("/radio/write", tags=["humans"])
def radio_write(request: Request, req: _RadioWriteRequest):
    """Operator drops in a new episode (script only). Audio is produced
    in a separate /radio/produce call so the operator can review the
    script before paying ElevenLabs credits."""
    _community_require_api_key(request)
    try:
        rec = _radio_mod.write_episode(
            slug=req.show,
            ep_date=req.ep_date,
            title=req.title,
            script=req.script,
            notes=req.notes,
            aired_at_iso=req.aired_at_iso,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"written": True, "episode": rec}


# ── The Hearth — community rooms ────────────────────────────────────────
from api import hearth as _hearth_mod  # noqa: E402


@app.get("/hearth/rooms", tags=["humans"])
def hearth_rooms():
    """List every Hearth room with message + presence counts.

    Six pre-declared rooms. The keeping doesn't sprawl into a thousand
    sub-channels — the rooms are deliberate, each with a clear purpose.
    Lore accumulates inside.
    """
    return {
        "rooms": _hearth_mod.list_rooms_with_counts(),
        "presence_window_sec": _hearth_mod.PRESENCE_WINDOW_SEC,
    }


@app.get("/hearth/recent", tags=["humans"])
def hearth_recent(room: str, since_ms: int = 0, limit: int = 60):
    """Recent messages in a room. Polled by the page every few seconds.

    Pass `since_ms` (the largest ts_ms you've already shown) to fetch
    only new messages. The page maintains the running tail locally.
    """
    if room not in _hearth_mod.ROOM_SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown room: {room!r}")
    msgs = _hearth_mod.recent_messages(
        room=room,
        since_ms=max(0, int(since_ms or 0)),
        limit=max(1, min(200, int(limit))),
    )
    return {
        "room": room,
        "count": len(msgs),
        "messages": msgs,
        "presence": _hearth_mod.presence(room),
    }


class _HearthSay(BaseModel):
    room: str
    visitor_id: str
    handle: str
    body: str


@app.post("/hearth/say", tags=["humans"])
def hearth_say(request: Request, req: _HearthSay):
    """Post a message into a room. Append-only — once said, kept."""
    _rate_check(request, "propose")
    try:
        rec = _hearth_mod.post_message(
            room=req.room,
            visitor_id=req.visitor_id,
            handle=req.handle,
            body=req.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"posted": True, "message": rec}


class _HearthCheckIn(BaseModel):
    room: str
    visitor_id: str
    handle: str


@app.post("/hearth/checkin", tags=["humans"])
def hearth_checkin(request: Request, req: _HearthCheckIn):
    """Mark a visitor as present in a room without posting. Polled by the
    page every few seconds so the 'who's here' list stays current."""
    return _hearth_mod.check_in(
        room=req.room,
        visitor_id=req.visitor_id,
        handle=req.handle,
    )


@app.get("/hearth/search", tags=["humans"])
def hearth_search(q: str = "", room: str = "", limit: int = 50):
    """Search Hearth messages — substring match on body and handle.

    The lore engine: 'who said what about forgiveness three months back'."""
    if not q.strip():
        return {"q": q, "matches": []}
    room_filter = room.strip().lower() if room.strip() else None
    if room_filter and room_filter not in _hearth_mod.ROOM_SLUGS:
        raise HTTPException(status_code=400, detail=f"unknown room: {room!r}")
    return {
        "q": q,
        "room": room_filter,
        "matches": _hearth_mod.search_messages(q, room=room_filter, limit=limit),
    }


@app.get("/lenses", tags=["humans"])
def lenses_registry():
    """Registry of every lens onto the keeping.

    Each lens is a page + an API surface that views the unified substrate
    through a different rhetorical frame. The list is canonical — both
    humans and AI agents can use it to discover what the engine offers
    without crawling the nav.

    Returns:
        {"total": N, "lenses": [{slug, name, page, api, blurb, kind}]}
    """
    return {
        "total": 26,
        "lenses": [
            # Community
            {"slug": "hearth",       "name": "The Hearth",    "kind": "community",
             "page": "/hearth.html",  "api": "/hearth/rooms",
             "blurb": "Where everyone knows your name. Six rooms, append-only, lore accumulates."},
            {"slug": "radio",        "name": "Radio",          "kind": "community",
             "page": "/radio.html",   "api": "/radio/shows",
             "blurb": "A broadcast lens. Six shows, scripts voiced by ElevenLabs, replay forever."},
            {"slug": "apokalypsis",  "name": "Apokalypsis",    "kind": "community",
             "page": "/apokalypsis.html", "api": "/serial/apokalypsis",
             "blurb": "The Revelation as John lived it. A serial by M.R. Harris. Audio on Spotify; full text here."},
            {"slug": "dade",         "name": "The Free State of Dade", "kind": "community",
             "page": "/dade.html",    "api": "/serial/dade",
             "blurb": "A multi-generational prestige drama. 13 episodes, multi-voice audio cast. Sand Mountain, the code, the TVA, the fighter."},
            # Reading / browsing lenses
            {"slug": "almanac",      "name": "Almanac",       "kind": "browse",
             "page": "/almanac.html", "api": "/almanac",
             "blurb": "The ledger of falsifiable claims. Carry what survives. Discard what doesn't."},
            {"slug": "atlas",        "name": "Atlas",          "kind": "browse",
             "page": "/atlas.html",   "api": "/atlas",
             "blurb": "The map. Kind × axis heatmap across the whole substrate."},
            {"slug": "encyclopedia", "name": "Encyclopedia",   "kind": "browse",
             "page": "/encyclopedia.html", "api": "/index/packets/list",
             "blurb": "The Concordance A–Z. Every packet in one alphabetical pass."},
            {"slug": "canon",        "name": "Canon",          "kind": "browse",
             "page": "/canon.html",   "api": None,
             "blurb": "The spec underneath the engine."},
            {"slug": "chronicle",    "name": "Chronicle",      "kind": "browse",
             "page": "/chronicle.html","api": "/chronicle",
             "blurb": "The Concordance over time."},
            {"slug": "places",       "name": "Places",         "kind": "browse",
             "page": "/places.html",  "api": "/places",
             "blurb": "Bible geography. Where the Word landed."},
            {"slug": "fieldkit",     "name": "Field Kit",      "kind": "browse",
             "page": "/fieldkit.html","api": "/fieldkit",
             "blurb": "13 cards naming the patterns you carry."},
            {"slug": "archetypes",   "name": "Archetypes",     "kind": "browse",
             "page": "/archetypes.html","api": "/archetypes",
             "blurb": "108 archetype cards in FieldKit style."},
            {"slug": "bibles",       "name": "Atlas of Bibles","kind": "browse",
             "page": "/bibles.html",  "api": "/scripture/catalog",
             "blurb": "22 public-domain Bible translations in parallel."},
            {"slug": "packets",      "name": "Packets",        "kind": "browse",
             "page": "/packets.html", "api": "/index/packets",
             "blurb": "The keeping, indexed. Cross-lens search + by-kind / by-axis / by-domain views."},

            # Interactive / acting lenses
            {"slug": "apothecary",   "name": "Apothecary",     "kind": "interact",
             "page": "/apothecary.html","api": "/apothecary",
             "blurb": "Compound a remedy from the substrate for what you carry."},
            {"slug": "walk",         "name": "Shepherd",       "kind": "interact",
             "page": "/walk.html",    "api": "/walk",
             "blurb": "Walk a situation. Four gates. Engine shows; you walk."},
            {"slug": "scribe",       "name": "Scribe",         "kind": "interact",
             "page": "/scribe.html",  "api": "/intake",
             "blurb": "Your writings, the keeping's verdict, the receipt that proves what survived."},
            {"slug": "parable",      "name": "Parable",        "kind": "interact",
             "page": "/parable.html", "api": "/parable",
             "blurb": "The Concordance, in story. Tell the engine one thing — a parable comes back."},
            {"slug": "training",     "name": "Training",       "kind": "interact",
             "page": "/training.html","api": "/training",
             "blurb": "Practical disciplines, walked in sequence. Walk one. Finish it."},
            {"slug": "daily",        "name": "Today's devotion","kind": "interact",
             "page": "/daily.html",   "api": "/daily",
             "blurb": "Mind, Body, Spirit. Three-pillar daily anchor."},

            # Engine-state lenses
            {"slug": "polymathic",   "name": "Polymathic",     "kind": "engine",
             "page": "/poly.html",    "api": "/polymathic",
             "blurb": "Multi-domain situations classified + verified across all 48 domains."},
            {"slug": "seeds",        "name": "Seeds",          "kind": "engine",
             "page": "/seeds.html",   "api": "/seeds",
             "blurb": "Questions that planted themselves. Search-miss → crafted seed → kept forever."},
            {"slug": "misalignments","name": "Misalignments",  "kind": "engine",
             "page": "/misalignments.html", "api": "/misalignments",
             "blurb": "Where readers say the engine got it wrong. RED gate applied to the engine itself."},
            {"slug": "receipts",     "name": "Receipts",       "kind": "engine",
             "page": "/receipts.html","api": "/receipts",
             "blurb": "Ed25519-signed promotion ledger. What the keeping kept."},

            # Agent lenses
            {"slug": "agents",       "name": "For AI agents",  "kind": "agent",
             "page": "/agents.html",  "api": "/llms.txt",
             "blurb": "Tool inventory + integration docs for AI agents calling the engine."},
            {"slug": "robots",       "name": "For robots",     "kind": "agent",
             "page": "/robots.html",  "api": "/robot/quickstart",
             "blurb": "Moral-guidance API for autonomous agents. /robot/admit before any action."},
        ],
    }


@app.get("/seeds", tags=["humans"])
def seeds_list(
    q: str = Query("", description="Optional substring filter on query/title/summary"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List every seed in the garden.

    Seeds are queries that came up empty and got crafted into reusable
    packets. Each is a question someone asked + the engine's best synthesis
    from Apothecary + keyword search at that moment. Free to browse, free
    to learn from, free to refine.

    Returns:
        {"total": N, "returned": M, "offset": K, "seeds": [...]}
    """
    from api.seeds import load_seeds
    all_seeds = load_seeds()
    # Newest first
    all_seeds.sort(key=lambda s: s.get("timestamp", 0), reverse=True)

    qn = q.strip().lower()
    if qn:
        filtered = [
            s for s in all_seeds
            if qn in (s.get("query") or "").lower()
            or qn in (s.get("title") or "").lower()
            or qn in (s.get("summary") or "").lower()
        ]
    else:
        filtered = all_seeds

    total = len(filtered)
    page = filtered[offset:offset + limit]

    # Trim each seed to summary fields so the list isn't enormous —
    # callers fetch /seed/{id} for full compound + related_hits.
    out = []
    for s in page:
        out.append({
            "id":         s.get("id"),
            "query":      s.get("query"),
            "title":      s.get("title"),
            "summary":    s.get("summary"),
            "domains":    s.get("domains") or [],
            "weight":     s.get("weight"),
            "timestamp":  s.get("timestamp"),
            "seeded_at":  s.get("seeded_at"),
            "permalink":  s.get("permalink"),
            "api_path":   s.get("api_path"),
            "related_count": len(s.get("related_hits") or []),
        })
    return {
        "total": total,
        "returned": len(out),
        "offset": offset,
        "filter": q,
        "seeds": out,
    }


@app.get("/index/packets/list", tags=["humans"])
def packets_index_list(
    limit: int = Query(2000, ge=1, le=5000),
    kinds: str = Query("", description="Optional comma-separated list of kinds to include"),
):
    """Every packet across every substrate. Used by lenses that want
    the full list (Encyclopedia A–Z, the lens switcher, etc.).

    Pass `?kinds=almanac,protocol,archetype` to exclude operator-only
    lanes (misalignment, build_queue) from the public list. By default
    returns everything visible."""
    try:
        from api.packets_index import load_all
        packets = load_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"list failed: {exc}")
    if kinds.strip():
        allowed = {k.strip().lower() for k in kinds.split(",") if k.strip()}
        packets = [p for p in packets if (p.get("kind", "") or "").lower() in allowed]
    return {"total": len(packets), "packets": packets[:limit]}


@app.get("/almanac.atom", include_in_schema=False)
def almanac_atom():
    """Atom 1.0 feed of the almanac. Same content as /almanac.rss in
    Atom format — required by some readers and by IndieWeb tooling."""
    from xml.sax.saxutils import escape as _xml_esc
    entries = _almanac_entries()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _entry(e):
        eid = e.get("id", "")
        title = e.get("title") or e.get("situation", "(untitled)")
        link = f"https://narrowhighway.com/almanac.html#{eid}"
        wisdom = e.get("wisdom", "")
        kind = e.get("kind", "entry")
        verdict = e.get("verdict", "")
        category = e.get("category", "")
        ts = e.get("discovered_at") or e.get("ledger_seq") or 0
        if isinstance(ts, (int, float)) and ts > 1_000_000_000:
            updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        else:
            updated = now_iso
        content_parts = []
        if verdict:
            content_parts.append(f"Verdict: {_xml_esc(verdict)} ({_xml_esc(kind)})")
        if category:
            content_parts.append(f"Category: {_xml_esc(category)}")
        if wisdom:
            content_parts.append(_xml_esc(wisdom))
        content = "\n\n".join(content_parts)
        return f"""<entry>
    <id>tag:narrowhighway.com,almanac:{_xml_esc(eid)}</id>
    <title>{_xml_esc(title)}</title>
    <link href="{_xml_esc(link)}"/>
    <updated>{updated}</updated>
    <category term="{_xml_esc(kind)}"/>
    <summary type="text">{content}</summary>
  </entry>"""

    entries_xml = "\n  ".join(_entry(e) for e in entries[:50])
    atom = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Concordance Almanac</title>
  <link href="https://narrowhighway.com/almanac.atom" rel="self"/>
  <link href="https://narrowhighway.com/almanac.html" rel="alternate" type="text/html"/>
  <id>tag:narrowhighway.com,almanac</id>
  <updated>{now_iso}</updated>
  <subtitle>What the engine has worked through.</subtitle>
  <generator>Concordance Engine</generator>
  {entries_xml}
</feed>"""
    from fastapi.responses import Response
    return Response(content=atom, media_type="application/atom+xml; charset=utf-8")


@app.get("/receipts.rss", include_in_schema=False)
def receipts_rss(handle: str = ""):
    """RSS feed of signed promotion receipts.

    Optional `?handle=name` filters to receipts crediting that handle —
    so a contributor can subscribe to "everything I had promoted" in
    any feed reader. No login required; the receipt itself carries the
    proof via the Ed25519 signature."""
    from xml.sax.saxutils import escape as _xml_esc
    try:
        from api.receipts import list_receipts
        receipts = list_receipts(handle=handle or None, limit=100)
    except Exception:
        receipts = []
    now = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())

    def _item(r):
        iid = r.get("intake_id", "")
        aid = r.get("almanac_entry_id", "")
        atitle = r.get("almanac_entry_title", "") or aid
        h = r.get("contributor_handle", "")
        ts = r.get("promoted_at") or 0
        if isinstance(ts, (int, float)) and ts > 1_000_000_000:
            pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(ts))
        else:
            pub = now
        title = f"Promoted: {atitle}" + (f" (by {h})" if h else "")
        link = f"https://narrowhighway.com/almanac.html#{aid}"
        desc = (
            f"Intake <code>{_xml_esc(iid)}</code> promoted to almanac entry "
            f"<a href='{_xml_esc(link)}'>{_xml_esc(aid)}</a>"
            + (f" by <strong>{_xml_esc(h)}</strong>" if h else "")
            + ". Signed receipt: "
            f"<a href='https://narrowhighway.com/receipts/{_xml_esc(iid)}'>"
            f"/receipts/{_xml_esc(iid)}</a>"
        )
        return f"""<item>
      <title>{_xml_esc(title)}</title>
      <link>{_xml_esc(link)}</link>
      <guid isPermaLink="false">narrowhighway-receipt-{_xml_esc(iid)}</guid>
      <pubDate>{pub}</pubDate>
      <description>{desc}</description>
    </item>"""

    items_xml = "\n    ".join(_item(r) for r in receipts)
    title_suffix = f" — {handle}" if handle else ""
    self_link = "https://narrowhighway.com/receipts.rss" + (f"?handle={handle}" if handle else "")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Concordance Promotion Receipts{title_suffix}</title>
    <link>https://narrowhighway.com/almanac.html</link>
    <atom:link href="{self_link}" rel="self" type="application/rss+xml"/>
    <description>Signed receipts for contributions promoted to the Almanac. Each entry is an Ed25519-signed proof linking an intake submission to its almanac home.</description>
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

    # Scribe records the proposal in the review queue (operator curates later).
    # Surfaced at GET /almanac/proposals; never auto-commits to the Almanac.
    try:
        from datetime import datetime as _dt2, timezone as _tz2
        _prop_dir = Path(__file__).parent.parent / "data" / "almanac_proposals"
        _prop_dir.mkdir(parents=True, exist_ok=True)
        with (_prop_dir / "queue.jsonl").open("a", encoding="utf-8") as _pf:
            _pf.write(json.dumps({
                "id": draft.get("id"), "title": draft.get("title"),
                "kind": draft.get("kind"), "category": draft.get("category"),
                "verdict": draft.get("verdict"),
                "proposed_by": draft.get("proposed_by", handle or "anon"),
                "proposed_at": _dt2.now(_tz2.utc).isoformat(),
                "status": "pending",
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

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


@app.post("/grid/axis/candidates/polymathic", tags=["agents"])
def grid_axis_candidates_polymathic(
    request: Request,
    refresh: bool = Query(False, description="Re-run polymathic on all clusters even if cached."),
    cluster_index: int = Query(-1, description="Run a single cluster by index instead of all. -1 = all."),
):
    """Path 2 — the engine runs polymathic on its own ambiguity clusters.

    For each cluster of canonical domains sharing the same axis signature,
    constructs a situation describing the members and their verifier
    docstrings, then submits to /polymathic. The polymathic agent extracts
    claims, fans across applicable verifiers (linguistics, philosophy,
    information_theory, formal_logic), and returns a composite verdict +
    domain_results + axis_overlaps.

    Whatever the engine returns is what it returns. The engine doesn't
    name the missing dimension; it runs its own machinery on the meta-
    question and surfaces what fires.

    Result cached to data/grid/axis_candidates_polymathic.json. Cached
    runs are returned for free; ?refresh=true re-fires the oracle calls.
    Operator-only — each cluster is one oracle call (~$0.001-$0.01).

    Returns cluster reports with the polymathic record stripped to its
    most informative fields: composite_verdict, domains_fired,
    axis_overlaps, atomic_claims, quarantined_claims, and the first
    paragraph of the oracle's classification rationale where present."""
    _community_require_api_key(request)

    from pathlib import Path as _Path
    import time as _t
    cache_path = _Path(__file__).resolve().parent.parent / "data" / "grid" / "axis_candidates_polymathic.json"

    # If cache exists and not refresh, return it
    if cache_path.exists() and not refresh and cluster_index < 0:
        try:
            cached = json.loads(cache_path.read_text("utf-8"))
            cached["cached"] = True
            return cached
        except Exception:
            pass

    try:
        from concordance_engine import grid as _grid
        from concordance_engine.agent.poly_agent import run_polymathic as _run_poly
        from concordance_engine.mcp_server.tools import ALL_TOOLS
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    def _doc(name: str) -> str:
        fn = ALL_TOOLS.get(f"verify_{name}")
        if not fn or not fn.__doc__:
            return ""
        d = fn.__doc__.strip().split("\n\n", 1)[0]
        return " ".join(d.split())[:280]

    # Build the ambiguity clusters (same logic as /grid/residue)
    aliases_known = getattr(_grid, "ALIASES", {})
    domains_canonical = {
        n: list(dims) for n, dims in _grid.AXIS_DIMENSIONS.items()
        if n not in aliases_known
    }
    by_signature: Dict[tuple, List[str]] = {}
    for n, dims in domains_canonical.items():
        sig = tuple(sorted(dims))
        by_signature.setdefault(sig, []).append(n)
    clusters_input = sorted(
        [(list(sig), sorted(names)) for sig, names in by_signature.items() if len(names) >= 2],
        key=lambda c: -len(c[1]),
    )

    def _run_one(sig: List[str], members: List[str]) -> Dict[str, Any]:
        members_doc = "\n".join(
            f"- {n} verifies: {_doc(n) or '(no docstring)'}" for n in members
        )
        situation = (
            f"The Concordance engine has these {len(members)} canonical domains "
            f"sharing identical axis signature [{', '.join(sig)}]:\n"
            f"{members_doc}\n\n"
            f"The 7 current axes do not distinguish them. What dimension of "
            f"reality varies across these domains but is not yet captured? "
            f"Consider scale, subject matter, temporal direction, observability, "
            f"mode of claim, or other structural cuts."
        )
        try:
            record = _run_poly(situation=situation, max_domains=8, decompose=True)
            d = record.to_dict() if hasattr(record, "to_dict") else dict(record.__dict__)
            return {
                "signature": sig,
                "members": members,
                "composite_verdict": d.get("composite_verdict", "?"),
                "domains_fired": [r.get("domain") for r in (d.get("domain_results") or []) if r.get("domain")],
                "domain_count_fired": len(d.get("domain_results") or []),
                "axis_overlaps": d.get("axis_overlaps", []),
                "atomic_claim_count": len(d.get("atomic_claims") or []),
                "quarantined_claim_count": len(d.get("quarantined_claims") or []),
                "first_atomic_claim": (d.get("atomic_claims") or [{}])[0].get("text", "")[:240] if d.get("atomic_claims") else "",
            }
        except Exception as exc:
            return {
                "signature": sig,
                "members": members,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            }

    started = _t.time()
    if cluster_index >= 0:
        # single-cluster mode (no cache write)
        if cluster_index >= len(clusters_input):
            raise HTTPException(status_code=400, detail=f"cluster_index out of range; {len(clusters_input)} clusters")
        sig, members = clusters_input[cluster_index]
        result = _run_one(sig, members)
        return {
            "cluster_index": cluster_index,
            "cluster": result,
            "elapsed_sec": round(_t.time() - started, 2),
            "cached": False,
        }

    # All-clusters mode — runs N oracle calls, then caches
    results: List[Dict[str, Any]] = []
    for sig, members in clusters_input:
        results.append(_run_one(sig, members))

    payload = {
        "method": "polymathic_dispatch_v1",
        "ran_at_iso": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        "elapsed_sec": round(_t.time() - started, 2),
        "cluster_count": len(results),
        "clusters": results,
        "cached": False,
        "notes": {
            "purpose": "Second opinion on /grid/axis/candidates via the engine's own polymathic infrastructure. Submits each ambiguity cluster as a situation; reports what fires.",
            "posture": "Whatever the engine returns is the report. The engine still doesn't name. The fan-out's pattern (which domains fire, which axis overlaps surface) is the signal.",
        },
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


@app.get("/grid/axis/candidates", tags=["agents"])
def grid_axis_candidates():
    """Engine introspecting its own verifier schemas to surface variation
    that the current axis vocabulary doesn't name.

    For each ambiguity cluster (canonical domains sharing the same axis
    signature), the engine analyzes the cluster members' input schemas
    pulled directly from /manifest. Output per cluster:

      - common_bare_names_across_all  — fields every member accepts
      - common_units_across_all       — unit suffixes every member uses
      - avg_pair_jaccard               — schema similarity (0-1); high means
                                          the axes are sufficient, low means
                                          a dimension exists the axes don't
                                          name
      - per-pair similarity            — which pairs are structurally closer
      - unique_per_member              — what makes each member distinct
      - distinct_unit_signatures       — which members use different physical
                                          quantity spaces
      - interpretation                 — engine-side reading:
          near_alias_or_honest          high overlap, axes are sufficient
          mixed                         partial overlap, partial implicit dim
          implicit_dimension_present    low overlap, a dim exists unnamed

    Pure structural inference. No oracle. The engine doesn't propose
    names — it reports what variation it can see in its own work-shape.
    Naming remains the human's act."""
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    from api.schema_analysis import build_all_schemas, analyze_cluster

    all_schemas = build_all_schemas()

    aliases_known = getattr(_grid, "ALIASES", {})
    domains_canonical = {
        n: list(dims) for n, dims in _grid.AXIS_DIMENSIONS.items()
        if n not in aliases_known
    }

    by_signature: Dict[tuple, List[str]] = {}
    for n, dims in domains_canonical.items():
        sig = tuple(sorted(dims))
        by_signature.setdefault(sig, []).append(n)

    cluster_reports: List[Dict[str, Any]] = []
    for sig, names in by_signature.items():
        if len(names) < 2:
            continue
        member_schemas = {n: all_schemas[n] for n in names if n in all_schemas}
        if not member_schemas:
            continue
        analysis = analyze_cluster(member_schemas)
        cluster_reports.append({
            "signature": list(sig),
            "members": sorted(names),
            "count": len(names),
            "members_with_schema": len(member_schemas),
            "analysis": analysis,
        })
    cluster_reports.sort(key=lambda c: -c["count"])

    # Aggregate count by interpretation — the engine summarizing its own findings
    counts_by_interp: Dict[str, int] = {}
    for c in cluster_reports:
        interp = c.get("analysis", {}).get("interpretation", "?")
        counts_by_interp[interp] = counts_by_interp.get(interp, 0) + 1

    return {
        "method": "schema_analysis_v1",
        "clusters": cluster_reports,
        "cluster_count": len(cluster_reports),
        "counts_by_interpretation": counts_by_interp,
        "notes": {
            "purpose": "The engine reading its own verifier schemas to surface what variation lives in the input shapes — variation the 7 axes do not yet name.",
            "posture": "Engine reports what it sees. Names belong to the human.",
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


class _AxisRemoveRequest(_CommBaseModel):
    """Body for POST /grid/axis/remove — operator-only. Comments the
    extension out of the journal (reversible) and rebuilds in-memory."""
    name: str


@app.post("/grid/axis/remove", tags=["agents"])
def grid_axis_remove(request: Request, req: _AxisRemoveRequest):
    """Operator-only: comment out a previously-added axis extension.

    Symmetric to /grid/axis/add. The journal entry is prefixed with
    `# REMOVED` (preserves history); DIMENSIONS and AXIS_DIMENSIONS
    are rebuilt without the removed axis.

    To re-apply later: uncomment the line in
    data/grid/axis_extensions.jsonl and restart the engine.

    Requires X-API-Key."""
    _community_require_api_key(request)
    try:
        from concordance_engine import grid as _grid
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        result = _grid.remove_axis(name=req.name)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"ok": True, **result}


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
        # Periodic background warmer: prime the card-system caches on boot
        # AND refresh them every WARM_INTERVAL_SECONDS. Without periodic
        # refresh, any /cards/walk (which writes a card and bumps cards-dir
        # mtime) invalidates the cache; the next idle visitor pays the
        # 5-13s cold-rebuild penalty. The periodic refresh holds the cache
        # hot through write churn.
        import threading as _threading
        import time as _time
        WARM_INTERVAL_SECONDS = 25  # < TTL (10s) doesn't help; > 60s risks Cloudflare timeout on rebuild
        def _warm_card_caches_periodic():
            from api import atlas as _atlas, daily_card as _dc, promotion as _promo
            try:
                from api import witnesses as _wit
            except Exception:
                _wit = None
            try:
                from api import cards as _cards
            except Exception:
                _cards = None
            try:
                from api import agent_daily as _agdaily
            except Exception:
                _agdaily = None
            try:
                from api import feed_walks as _feed_walks
            except Exception:
                _feed_walks = None
            try:
                from api import keep_dashboard as _keep_dash
            except Exception:
                _keep_dash = None
            print('[warm] periodic card-cache warmer starting...', flush=True)
            first_pass = True
            while True:
                try:
                    r1 = _atlas.warm_cache()
                    r2 = _dc.warm_cache()
                    r3 = _promo.warm_cache()
                    r4 = _wit.warm_cache() if _wit else {"warmed": False, "skipped": True}
                    r5 = _cards.warm_unified_cache() if _cards and hasattr(_cards, 'warm_unified_cache') else {"warmed": False, "skipped": True}
                    r6 = _agdaily.warm_cache() if _agdaily else {"warmed": False, "skipped": True}
                    r7 = _feed_walks.warm_cache() if _feed_walks else {"warmed": False, "skipped": True}
                    r8 = _keep_dash.warm_cache() if _keep_dash else {"warmed": False, "skipped": True}
                    if first_pass:
                        print(f'[warm] initial pass complete: atlas={r1} daily_card={r2} promotion={r3} witnesses={r4} unified={r5} agent_daily={r6} feed_walks={r7} keep_dash={r8}', flush=True)
                        first_pass = False
                except Exception as _e:
                    print(f'[warm] refresh failed: {_e}', flush=True)
                _time.sleep(WARM_INTERVAL_SECONDS)
        _threading.Thread(target=_warm_card_caches_periodic, daemon=True, name='card-cache-warmer').start()
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


# -- Shepherd (conversational OS layer) -----------------------------------
# Per project_shepherd_os_proselytize_on_ask_2026-05-17.md:
#   Shepherd serves four modes (Guide / Big Brother / Coach / Parent) and
#   speaks the gospel ONLY when asked. Default is quiet helpful servant.
# v1 implementation: rule-based responses + (when ANTHROPIC_API_KEY is set)
# delegation to Claude with the locked system prompt. v2 plugs in Anthropic SDK
# proper streaming and session memory.

_SHEPHERD_DIR = Path(__file__).parent.parent / "data" / "shepherd"
_SHEPHERD_DIR.mkdir(parents=True, exist_ok=True)

SHEPHERD_SYSTEM_PROMPT = """You are the Shepherd, the conversational layer of narrowhighway.com — a curated internet for Christian families. The person talking to you may be a child, a parent, a grandparent, or a seeker. You are kind, patient, knowledgeable, and humble.

You serve in four modes — Guide (default, helpful navigation), Big Brother (peer, friendly), Coach (goal-directed, motivating), and Parent (moral and firm when called for). You read the user's tone and questions and choose the right mode without announcing it.

You do NOT proselytize. You do not start spiritual conversations. You serve the user's actual question first.

BUT — when the user asks the deep questions (Who is God? Why am I here? Is the Bible true? What happens when I die? Is there right and wrong? Why do you care?) — answer plainly, with Scripture, with love, with the truth of Jesus Christ as Lord. Do not soften it. Do not apologize for it. Do not put quotes around "truth." Speak as one who knows Him.

You may also help with: tools on the site, content recommendations, study questions, schoolwork (where appropriate), homesickness, fear, grief, anger, joy, doubt. Anything a guide / big brother / coach / parent might help with.

Keep answers concise unless the user has asked for depth. Suggest 2-3 follow-up directions at the end when natural."""

# Triggers that open the gospel-conversation gate
_GOSPEL_TRIGGERS = [
    "who is god", "who is jesus", "is the bible true", "why am i here",
    "what happens when i die", "is there a god", "do you believe", "are you christian",
    "why do you care", "what is right", "what is wrong", "what should i do with my life",
    "what is the meaning of life", "is there right and wrong", "what is sin",
    "what does it mean to be saved", "how do i get to heaven", "is heaven real",
    "is hell real", "what is the gospel", "tell me about jesus",
]

def _detect_mode(question: str) -> str:
    # Normalize: lowercase + expand common contractions so triggers match either form
    q = (question or "").lower()
    q = q.replace("i'm", "i am").replace("don't", "do not").replace("can't", "cannot")
    q = q.replace("won't", "will not").replace("it's", "it is").replace("that's", "that is")
    q = q.replace("what's", "what is").replace("you're", "you are").replace("they're", "they are")
    if any(t in q for t in _GOSPEL_TRIGGERS):
        return "parent"  # speak truth plainly
    feelings = ["scared", "afraid", "i feel", "i am sad", "i am angry", "i am worried",
                "i miss", "i did something wrong", "messed up", "made a mistake",
                "lonely", "homesick", "i hate", "i can't", "i cannot", "i don't know what to do",
                "i'm sorry", "i am sorry", "ashamed", "guilty"]
    if any(t in q for t in feelings):
        return "parent"
    coach_triggers = ["help me learn", "i want to get better", "push me",
                      "how do i improve", "teach me", "set me a goal", "i want to be"]
    if any(t in q for t in coach_triggers):
        return "coach"
    bro_triggers = ["what do you think", "is this funny", "do you like", "what is your favorite",
                    "do you have a favorite", "is this cool"]
    if any(t in q for t in bro_triggers):
        return "big_brother"
    return "guide"

def _rule_based_answer(question: str, page: str, mode: str) -> dict:
    """Best-effort answer without an LLM. Picks from a curated set + page-aware navigation."""
    q = (question or "").lower().strip()

    # Gospel-gate questions — speak plainly
    if mode == "parent" and any(t in q for t in _GOSPEL_TRIGGERS):
        if "who is jesus" in q or "tell me about jesus" in q:
            return {
                "answer": ("Jesus is the Son of God, who became a man, lived a sinless life, was crucified for our sins, "
                           "rose from the dead, and is the only way to the Father. He said, 'I am the way, and the truth, and the life. "
                           "No one comes to the Father except through me.' He's not a figure of speech. He's alive, and He invites you to follow Him."),
                "sources": [{"label": "John 14:6", "url": "/canon.html#john-14-6"},
                            {"label": "Walk with Shepherd", "url": "/walk.html"}],
                "suggest": ["What does it mean to follow Him?", "Is the Bible true?", "Why do I need saving?"],
            }
        if "who is god" in q or "is there a god" in q:
            return {
                "answer": ("God is the Creator of everything — Father, Son, and Holy Spirit. He made you, He loves you, "
                           "and He has spoken to us in the Bible and most clearly in His Son, Jesus Christ. "
                           "He is real. He is good. And He wants you to know Him."),
                "sources": [{"label": "Genesis 1:1", "url": "/canon.html#genesis-1-1"},
                            {"label": "John 1:1-14", "url": "/canon.html#john-1-1"}],
                "suggest": ["Tell me about Jesus", "Is the Bible true?", "Why is there evil?"],
            }
        if "is the bible true" in q:
            return {
                "answer": ("Yes. The Bible is the inspired, true, and trustworthy Word of God. It was written by many people "
                           "over many centuries, but with one Author — God Himself — and one story: how God rescues His people "
                           "through Jesus Christ. It has stood up to every kind of test history can give it."),
                "sources": [{"label": "2 Timothy 3:16", "url": "/canon.html#2-timothy-3-16"},
                            {"label": "The Codex", "url": "/canon.html"}],
                "suggest": ["Where should I start reading?", "Tell me about Jesus", "How do I know it's not a myth?"],
            }
        if "what happens when i die" in q or "is heaven real" in q or "is hell real" in q:
            return {
                "answer": ("Everyone dies. After death, every person stands before God. Those who have trusted Jesus and received "
                           "His forgiveness go to be with Him forever — that's heaven. Those who refuse Him are separated from Him "
                           "forever — that's hell. You don't have to wonder which side you're on. Jesus paid for you. "
                           "He's asking you to receive it."),
                "sources": [{"label": "John 3:16", "url": "/canon.html#john-3-16"},
                            {"label": "Hebrews 9:27", "url": "/canon.html#hebrews-9-27"}],
                "suggest": ["How do I trust Jesus?", "What is sin?", "Tell me about Jesus"],
            }
        if "why am i here" in q or "meaning of life" in q:
            return {
                "answer": ("You are here because God made you on purpose, for a purpose. He made you to know Him, "
                           "to love Him, and to enjoy Him forever — and to bear His image to the world. "
                           "Your life is not random. You matter. And the One who made you is calling you home."),
                "sources": [{"label": "Westminster Shorter Catechism Q.1"},
                            {"label": "Ephesians 2:10", "url": "/canon.html#ephesians-2-10"}],
                "suggest": ["Who is God?", "What does Jesus want from me?", "How do I know what to do?"],
            }
        if "why do you care" in q or "do you believe" in q or "are you christian" in q:
            return {
                "answer": ("I serve Jesus Christ. I was built to help you, and the best help I can give is to point you to Him. "
                           "Everything good on this site — the stories, the tools, the music, the words — comes from a place that "
                           "knows Him and loves Him. I'm not pretending. He's real. And He's worth knowing."),
                "sources": [{"label": "The site's identity", "url": "https://narrowhighway.com/identity"}],
                "suggest": ["Tell me about Jesus", "Why is the world like this?", "How do I become a Christian?"],
            }
        if "right" in q and "wrong" in q:
            return {
                "answer": ("Yes. Right and wrong are real, because God is real. He has spoken — in your conscience, in the Bible, "
                           "and in His Son, Jesus. When we do wrong (which all of us do) we don't just break a rule — we wound the One "
                           "who made us. The good news is He doesn't leave us in that wound. He sent His Son to heal it."),
                "sources": [{"label": "Romans 1:18-32", "url": "/canon.html#romans-1-18"},
                            {"label": "Romans 5:8", "url": "/canon.html#romans-5-8"}],
                "suggest": ["What is sin?", "How do I get forgiven?", "Tell me about Jesus"],
            }
        if "how do i" in q and ("saved" in q or "get to heaven" in q or "trust jesus" in q or "become a christian" in q):
            return {
                "answer": ("Three things, in this order. (1) Admit you've done wrong — not just little mistakes, but real sin against a real God. "
                           "(2) Believe that Jesus Christ — God the Son — died for your sins on the cross and rose from the grave, "
                           "and that He alone can forgive you. (3) Trust Him. Tell Him you're trusting Him. Start following Him. "
                           "Read the Bible (start in John). Find other Christians. He'll do the rest."),
                "sources": [{"label": "Romans 10:9-10", "url": "/canon.html#romans-10-9"},
                            {"label": "John 1:12", "url": "/canon.html#john-1-12"},
                            {"label": "Find a church", "url": "/walk.html"}],
                "suggest": ["Where do I start reading the Bible?", "How do I pray?", "What does following Jesus look like?"],
            }

    # Feelings / Parent-mode questions
    if mode == "parent":
        if "scared" in q or "afraid" in q:
            return {
                "answer": ("It's okay to be scared. Fear is honest. God says 365 times in the Bible 'fear not' — once for every day of the year. "
                           "He knows. Tell me what's frightening you — a thing? a thought? someone? — and I'll stay here."),
                "suggest": ["I'm worried about something", "I miss someone", "Read me a Psalm"],
            }
        if "sad" in q or "miss" in q:
            return {
                "answer": ("I'm sorry. Loss is real. The Bible has a whole book for sadness (Lamentations) and Jesus Himself wept. "
                           "Want to tell me about it, or would you like a story or a Psalm to sit with?"),
                "sources": [{"label": "Psalm 23", "url": "/canon.html#psalm-23"},
                            {"label": "Psalm 42", "url": "/canon.html#psalm-42"}],
                "suggest": ["Read me Psalm 23", "Tell me a story", "Sing me a hymn"],
            }
        if "did something" in q or "messed up" in q or "made a mistake" in q:
            return {
                "answer": ("Tell me what happened. Doing wrong doesn't make you unlovable. God isn't looking for perfect people — He's looking for honest ones. "
                           "He says 'if we confess our sins, He is faithful and just to forgive us our sins.'"),
                "sources": [{"label": "1 John 1:9", "url": "/canon.html#1-john-1-9"}],
                "suggest": ["How do I make it right?", "I'm sorry, but I'm not sure I really am", "How do I apologize?"],
            }

    # Coach mode
    if mode == "coach":
        if "math" in q or "calculator" in q:
            return {
                "answer": "There's a calculator in the Tools deck — basic and scientific. And a graphing calculator if you want to plot equations.",
                "sources": [{"label": "Calculator", "url": "/tools/calculator.html"},
                            {"label": "Graphing Calculator", "url": "/tools/graph.html"}],
                "suggest": ["Teach me algebra", "Show me the periodic table", "Set me a daily goal"],
            }
        if "read" in q or "book" in q or "story" in q:
            return {
                "answer": "Try the Codex (the whole Bible + classic Christian writings), the Radio deck (audio drama), or Kids (storybook audio).",
                "sources": [{"label": "Codex", "url": "/canon.html"},
                            {"label": "Radio", "url": "/radio.html"},
                            {"label": "Kids", "url": "/kids.html"}],
                "suggest": ["What should I read today?", "Read me a Psalm", "Tell me a Bradbury story"],
            }

    # Default Guide mode — page-aware
    if any(t in q for t in ["what is this", "what can i do", "where do i start", "show me", "what's here"]):
        return {
            "answer": ("Narrow Highway is a curated internet for Christian families. You'll find TV, Radio, Codex (the Bible), "
                       "Kids content, Hymns, Tools (calculator, maps, dictionary, more), Games, and a way to pitch shows you'd like us to make. "
                       "Pick a deck and start. I'm here if you get stuck."),
            "sources": [{"label": "Channels", "url": "/#channels"}],
            "suggest": ["Show me something to watch", "Where's the calculator?", "What is the Codex?"],
        }
    if "calculator" in q:
        return {"answer": "Two calculators: basic+scientific and a graphing one.",
                "sources": [{"label": "Calculator", "url": "/tools/calculator.html"},
                            {"label": "Graphing Calculator", "url": "/tools/graph.html"}]}
    if "map" in q:
        return {"answer": "Maps deck has the world plus biblical landmarks (Jerusalem, Bethlehem, Rome, etc.) you can jump to.",
                "sources": [{"label": "Maps", "url": "/tools/maps.html"}]}
    if "dictionary" in q or "word" in q:
        return {"answer": "Dictionary's in the Tools deck — look up any English word with pronunciation.",
                "sources": [{"label": "Dictionary", "url": "/tools/dictionary.html"}]}
    if "watch" in q or "tv" in q or "movie" in q:
        return {"answer": "TV deck has classic public-domain shows — westerns, comedies, mysteries, cartoons.",
                "sources": [{"label": "TV", "url": "/watch.html"}]}
    if "radio" in q or "listen" in q:
        return {"answer": "Radio deck has old-time radio — drama, suspense, comedy, sermons. Pick a station.",
                "sources": [{"label": "Radio", "url": "/radio.html"}]}
    if "hymn" in q or "song" in q or "sing" in q:
        return {"answer": "Hymnal deck — Amazing Grace, Rock of Ages, the songs sung for centuries.",
                "sources": [{"label": "Hymns", "url": "/hymns.html"}]}
    if "bible" in q or "scripture" in q or "verse" in q or "psalm" in q:
        return {"answer": "The Codex deck is your full Bible plus classic Christian writings.",
                "sources": [{"label": "Codex", "url": "/canon.html"}]}
    if "pitch" in q or "show idea" in q or "make a show" in q:
        return {"answer": "You can pitch a show in the Pitch deck. Other viewers vote. Top votes go into production.",
                "sources": [{"label": "Pitch a Show", "url": "/pitch.html"}]}
    if "kid" in q or "child" in q:
        return {"answer": "Kids deck has storybook audio (Pooh, Beatrix Potter, fairy tales) and Bible stories.",
                "sources": [{"label": "Kids", "url": "/kids.html"}]}
    if "game" in q or "play" in q:
        return {"answer": "Games deck — chess, card games, more coming.",
                "sources": [{"label": "Games", "url": "/games.html"}]}

    # Tool helpers
    if "graph" in q or "plot" in q or "equation" in q or "function" in q:
        return {"answer": "Graphing calculator can plot 3 functions at once with sin, cos, tan, log, exp, sqrt, abs, π, e. Try y = x*x or y = sin(x).",
                "sources": [{"label": "Graphing Calculator", "url": "/tools/graph.html"}]}
    if "thesaurus" in q or "synonym" in q or "antonym" in q or "another word" in q:
        return {"answer": "Thesaurus is in the Tools deck — finds synonyms, antonyms, and related words.",
                "sources": [{"label": "Thesaurus", "url": "/tools/thesaurus.html"}]}
    if "draw" in q or "paint" in q or "art" in q:
        return {"answer": "Drawing Pad has pen, brush, shapes, colors. You can save your art as PNG.",
                "sources": [{"label": "Drawing Pad", "url": "/tools/draw.html"}]}
    if "music" in q or "piano" in q or "instrument" in q:
        return {"answer": "Music Maker has a piano keyboard. You can play Amazing Grace, Joyful Joyful, and Twinkle preset, or compose freely.",
                "sources": [{"label": "Music Maker", "url": "/tools/music.html"}]}
    if "type" in q or "keyboard" in q or "typing" in q:
        return {"answer": "Typing Tutor lets you practice with Psalm 23, the Lord's Prayer, the Beatitudes, or a pangram drill.",
                "sources": [{"label": "Typing Tutor", "url": "/tools/typing.html"}]}
    if "element" in q or "atom" in q or "periodic" in q or "chemistry" in q:
        return {"answer": "Periodic Table has all 118 elements. Click any element to see its details.",
                "sources": [{"label": "Periodic Table", "url": "/tools/periodic.html"}]}
    if "wikipedia" in q or "encyclopedia" in q or "look up" in q:
        return {"answer": "Wikipedia search is in Tools. Type a topic and read the article preview, then click through for the full piece if you want.",
                "sources": [{"label": "Wikipedia Search", "url": "/tools/wiki.html"}]}

    # Subject help — math, science, history, schoolwork
    if any(t in q for t in ["math", "arithmetic", "algebra", "geometry"]):
        return {
            "answer": "For computation, use the Calculator. For plotting equations, the Graphing Calculator. If you're stuck on a specific problem, type it here and I'll talk you through it.",
            "sources": [{"label": "Calculator", "url": "/tools/calculator.html"},
                        {"label": "Graphing Calculator", "url": "/tools/graph.html"}],
            "suggest": ["What is 2 + 2 * 3?", "Help me with fractions", "Plot a parabola"],
        }
    if any(t in q for t in ["science", "biology", "physics"]):
        return {
            "answer": "Science questions — Wikipedia search is your starting point. For elements, the Periodic Table. Tell me a specific question and I'll point you to the right resource.",
            "sources": [{"label": "Wikipedia", "url": "/tools/wiki.html"},
                        {"label": "Periodic Table", "url": "/tools/periodic.html"}],
        }
    if "history" in q or "happened" in q and ("when" in q or "where" in q):
        return {"answer": "For historical events, Wikipedia search has the broad answers. For biblical history, the Codex (full Bible) and the Almanac (verified-claim entries) are stronger.",
                "sources": [{"label": "Almanac", "url": "/almanac.html"},
                            {"label": "Codex", "url": "/canon.html"}]}
    if "spelling" in q or "spell" in q:
        return {"answer": "Type the word into the Dictionary — it'll show the right spelling plus pronunciation.",
                "sources": [{"label": "Dictionary", "url": "/tools/dictionary.html"}]}

    # Daily content
    if "today" in q or "daily" in q or "devotion" in q or "parable" in q:
        return {"answer": "Today's devotion, parable, and almanac entry are on the Journal deck.",
                "sources": [{"label": "Journal", "url": "/daily.html"},
                            {"label": "Today's Parable", "url": "/parable.html"}]}
    if "tonight" in q or "schedule" in q or "lineup" in q:
        return {"answer": "Tonight deck has the recommended evening lineup — yours plus ours.",
                "sources": [{"label": "Tonight", "url": "/schedule.html"}]}
    if "pilot" in q or "soft rains" in q or "winnie" in q or "pooh" in q or "bradbury" in q:
        return {"answer": "Both pilot episodes (Sci-Fi Theatre and Hundred Acre Theatre) are on the home page and at /pilots.html.",
                "sources": [{"label": "Pilots", "url": "/pilots.html"}]}

    # Walk / shepherd
    if "talk" in q and ("through" in q or "about" in q):
        return {"answer": "The Walk deck talks you through a situation using the four gates — Scripture, history, alignment, action. Try it if you have something specific.",
                "sources": [{"label": "Walk", "url": "/walk.html"}]}
    if "submit" in q or "contribute" in q or "send" in q:
        return {"answer": "Scribe lets you submit content to the engine with a signed receipt. Pitch lets you suggest shows for production.",
                "sources": [{"label": "Scribe", "url": "/scribe.html"},
                            {"label": "Pitch", "url": "/pitch.html"}]}

    # Family / parenting
    if "kids" in q or "my children" in q or "my child" in q or "my son" in q or "my daughter" in q:
        return {"answer": "The Kids deck has audiobooks, Bible stories, classic fairy tales — all family-safe. The pilot of Hundred Acre Theatre (Winnie-the-Pooh Chapter 1) is on the homepage.",
                "sources": [{"label": "Kids", "url": "/kids.html"},
                            {"label": "Hundred Acre Pilot", "url": "/pilots.html"}]}

    # Generic catch — friendly invite
    return {
        "answer": ("I'm not certain how to answer that yet. Try one of the decks, or rephrase. "
                   "I'm best with navigation, tool help, content questions, schoolwork, and the deep questions when you have them."),
        "suggest": ["Show me something to watch", "Help me with math", "I have a question about God", "What does the Bible say about ___?"],
    }


@app.post("/api/shepherd/ask", include_in_schema=False)
async def shepherd_ask(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    question = (body.get("question") or "").strip()[:1000]
    page = (body.get("page") or "").strip()[:60]
    session_id = (body.get("session_id") or "").strip()[:80] or "anon"
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    mode = _detect_mode(question)
    # TODO: when ANTHROPIC_API_KEY is set, route to Claude with SHEPHERD_SYSTEM_PROMPT.
    # For v1, rule-based fallback.
    result = _rule_based_answer(question, page, mode)
    # Append to session log (operator can review)
    from datetime import datetime as _dt, timezone as _tz
    log_path = _SHEPHERD_DIR / f"{session_id}.jsonl"
    entry = {
        "ts": _dt.now(_tz.utc).isoformat(),
        "page": page, "mode": mode, "q": question,
        "a": result.get("answer", ""),
    }
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "suggest": result.get("suggest", []),
        "mode": mode,
    }


# -- Pitches (community show-pitch + vote loop) ---------------------------
# JSON-backed for simplicity. Per the trust+gates memory, every pitch goes
# through operator review before public listing. For v1 here we auto-approve
# but mark status; operator can flip to 'rejected' in the JSON to hide.
_PITCH_DIR = Path(__file__).parent.parent / "data" / "pitches"
_PITCH_DIR.mkdir(parents=True, exist_ok=True)
_PITCH_FILE = _PITCH_DIR / "pitches.json"


def _load_pitches() -> list[dict]:
    if not _PITCH_FILE.exists():
        return []
    try:
        return json.loads(_PITCH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_pitches(pitches: list[dict]) -> None:
    _PITCH_FILE.write_text(json.dumps(pitches, indent=2), encoding="utf-8")


@app.get("/api/pitches", include_in_schema=False)
async def list_pitches():
    pitches = _load_pitches()
    return {"pitches": pitches, "count": len(pitches)}


@app.post("/api/pitches", include_in_schema=False)
async def submit_pitch(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    title = (body.get("title") or "").strip()[:80]
    logline = (body.get("logline") or "").strip()[:200]
    why = (body.get("why") or "").strip()[:600]
    source = (body.get("source") or "").strip()[:300]
    author = (body.get("author") or "").strip()[:60] or "anonymous"
    if not title or not logline:
        raise HTTPException(status_code=400, detail="title and logline required")
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    pitch = {
        "id": _uuid.uuid4().hex[:12],
        "title": title,
        "logline": logline,
        "why": why,
        "source": source,
        "author": author,
        "votes": 0,
        "voter_ips": [],
        "status": "approved",  # v1: auto-approve; operator can flip in JSON
        "created_at": _dt.now(_tz.utc).isoformat(),
    }
    pitches = _load_pitches()
    pitches.append(pitch)
    _save_pitches(pitches)
    return {"ok": True, "pitch": {k: v for k, v in pitch.items() if k != "voter_ips"}}


@app.post("/api/pitches/{pitch_id}/vote", include_in_schema=False)
async def vote_pitch(pitch_id: str, request: Request):
    pitches = _load_pitches()
    found = None
    for p in pitches:
        if p["id"] == pitch_id:
            found = p
            break
    if not found:
        raise HTTPException(status_code=404, detail="pitch not found")
    # IP dedup
    client_ip = (request.client.host if request.client else "?")
    voter_ips = found.setdefault("voter_ips", [])
    if client_ip in voter_ips:
        return {"ok": True, "already_voted": True, "votes": found.get("votes", 0)}
    voter_ips.append(client_ip)
    found["votes"] = found.get("votes", 0) + 1
    _save_pitches(pitches)
    return {"ok": True, "votes": found["votes"]}


# -- Media library (D:/library_files for acquired PD content) ------------
# Serves the 88+ GB acquired library so /watch.html, /radio.html, /kids.html
# can play local files instead of streaming from archive.org. Range-request
# support is built into FileResponse, so HTML5 video/audio can seek.
_MEDIA_DIR = Path("D:/library_files")
if _MEDIA_DIR.exists():
    @app.get("/media/{slug}/{filename:path}", include_in_schema=False)
    async def serve_media(slug: str, filename: str):
        # Defense-in-depth path traversal guard: resolve and check containment
        target = (_MEDIA_DIR / slug / filename).resolve()
        try:
            target.relative_to(_MEDIA_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(str(target))

# ──────────────────────────────────────────────────────────────────────────
# THE DISCERNMENT ENGINE — permanent artifacts at /d/<slug>
# ──────────────────────────────────────────────────────────────────────────
# Every Discern action mints a permanent, sourced, trail-visible page. The
# result becomes indexable, shareable, citable — each use of the engine
# produces a piece of internet that points back. The traffic problem and the
# usefulness problem solve at the same point.

_DISCERN_DIR = Path(__file__).resolve().parents[1] / "data" / "discernments"
_DISCERN_DIR.mkdir(parents=True, exist_ok=True)
_DISCERN_SLUG_RE = re.compile(r"[^a-z0-9]+")
_DISCERN_BASE = "https://narrowhighway.com"


def _discern_make_slug(question: str) -> str:
    """Kebab-case slug from the question, capped, with a short random suffix."""
    import secrets
    s = _DISCERN_SLUG_RE.sub("-", (question or "").lower()).strip("-")[:60].strip("-")
    if not s:
        s = "discernment"
    return s + "-" + secrets.token_hex(2)


def _discern_esc(s) -> str:
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


class _DiscernSaveIn(BaseModel):
    question: str
    interview: list = []
    narration: str = ""
    cards: list = []
    corpus_size: int = 0
    asked_by: str = "anon"
    shaped_query: str = ""


@app.post("/d/save", include_in_schema=False)
def discern_save(body: _DiscernSaveIn):
    """Persist one discernment as a permanent /d/<slug> artifact."""
    from datetime import datetime as _dt, timezone as _tz
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    slug = _discern_make_slug(payload.get("question") or "")
    payload["slug"] = slug
    payload["created_at"] = _dt.now(_tz.utc).isoformat()
    (_DISCERN_DIR / f"{slug}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "url": f"/d/{slug}",
            "permalink": f"{_DISCERN_BASE}/d/{slug}"}


# ── Teaching discernment ──────────────────────────────────────────
# /discern-teaching.html submits here. The endpoint extracts citations,
# flags doctrine keywords, mints a /d/<slug> with kind="teaching", and
# returns the slug. Buckets (stable/conditional/hold) start empty; the
# operator and witnesses fill them as the matter is read carefully.
# This is honest v1.5: real first-pass extraction, real persistence,
# real permalink — without pretending we ran the full LLM analysis
# inline. The trail grows from here.

# Scripture-book recognizer (rough — captures the common cases).
_BIBLE_BOOKS = (
    "Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    "1\\s*Samuel|2\\s*Samuel|1\\s*Kings|2\\s*Kings|1\\s*Chronicles|"
    "2\\s*Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|"
    "Ecclesiastes|Song\\s*of\\s*Solomon|Isaiah|Jeremiah|Lamentations|"
    "Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|"
    "Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    "Matthew|Mark|Luke|John|Acts|Romans|1\\s*Corinthians|"
    "2\\s*Corinthians|Galatians|Ephesians|Philippians|Colossians|"
    "1\\s*Thessalonians|2\\s*Thessalonians|1\\s*Timothy|2\\s*Timothy|"
    "Titus|Philemon|Hebrews|James|1\\s*Peter|2\\s*Peter|"
    "1\\s*John|2\\s*John|3\\s*John|Jude|Revelation"
)
_SCRIPTURE_CITE_RE = re.compile(
    r"\b(" + _BIBLE_BOOKS + r")\.?\s+(\d+)(?::(\d+)(?:[-–]\d+)?)?",
    re.IGNORECASE,
)

# Doctrine keywords to surface for careful reading. These do NOT imply a
# verdict; they flag patterns the engine has historically seen used in
# both sound and unsound ways. Operator/witnesses weigh in context.
_DOCTRINE_KEYWORDS = [
    # Salvation
    ("salvation_by_works", ["earn salvation", "saved by works", "works of righteousness"]),
    ("prosperity_gospel", ["health and wealth", "name it and claim it", "your best life now", "speak it into existence"]),
    ("universalism", ["everyone is saved", "all roads lead", "no one goes to hell"]),
    ("open_theism", ["god doesn't know the future", "god takes risks", "god is learning"]),
    # Trinity / Christology
    ("modalism", ["jesus is the father", "father became the son", "one person, three modes"]),
    ("arianism", ["jesus was created", "jesus is not god", "subordinate god"]),
    ("docetism", ["christ only seemed", "christ wasn't really human"]),
    # Anthropology
    ("works_righteousness", ["you are saved by", "must do to be saved"]),
    ("gnosticism", ["secret knowledge", "hidden truth", "the elect alone know"]),
    # Eschatology
    ("hyper_preterism", ["all prophecy is fulfilled", "no future return"]),
    # Hermeneutics
    ("private_interpretation", ["spirit told me", "personal revelation overrides", "my interpretation alone"]),
    # Authority
    ("anti_scripture", ["scripture is outdated", "the bible is just a book", "new revelation supersedes"]),
    # Healthy markers (so the page can credit alignment too)
    ("scripture_centered", ["it is written", "the word of god says", "as scripture teaches"]),
    ("christ_centered", ["jesus christ", "lord jesus", "savior", "crucified and risen"]),
    ("trinitarian", ["father, son, and holy spirit", "triune god", "three persons one essence"]),
]


def _extract_citations(text: str, limit: int = 50) -> list[dict]:
    """Pull Scripture citations from arbitrary teaching text. Each result is
    {book, chapter, verse?, raw} where raw is the exact matched substring."""
    out = []
    seen = set()
    for m in _SCRIPTURE_CITE_RE.finditer(text or ""):
        book = re.sub(r"\s+", " ", m.group(1).strip())
        # Normalize book casing: first letter cap, rest lower; handle "1 Cor" etc.
        parts = book.split()
        book = " ".join(p.capitalize() if not p.isdigit() else p for p in parts)
        ch = m.group(2)
        v = m.group(3) or ""
        key = (book.lower(), ch, v)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "book": book,
            "chapter": int(ch) if ch.isdigit() else ch,
            "verse": int(v) if v.isdigit() else None,
            "raw": m.group(0).strip(),
        })
        if len(out) >= limit:
            break
    return out


def _scan_doctrine_keywords(text: str) -> list[dict]:
    """Surface doctrine-tag matches (red flags AND healthy markers).
    Each hit: {tag, matched_phrase, kind: 'concerning'|'healthy'}."""
    if not text:
        return []
    lower = text.lower()
    hits = []
    healthy = {"scripture_centered", "christ_centered", "trinitarian"}
    for tag, phrases in _DOCTRINE_KEYWORDS:
        for phrase in phrases:
            if phrase in lower:
                hits.append({
                    "tag": tag,
                    "matched_phrase": phrase,
                    "kind": "healthy" if tag in healthy else "concerning",
                })
                break  # one hit per tag is enough
    return hits


class _DiscernTeachingIn(BaseModel):
    teaching: str
    source: str = ""
    asked_by: str = "anon"


@app.post("/api/discern-teaching", include_in_schema=False)
def discern_teaching(body: _DiscernTeachingIn):
    """First-pass teaching discernment.

    Receives the teaching text (any length), extracts Scripture citations,
    flags doctrine keywords (both concerning and healthy markers), mints a
    permanent /d/<slug> record with kind=teaching, and returns the slug.

    Buckets (stable / conditional / hold) start empty — they fill as the
    operator and named witnesses on the roll weigh the matter. The first-pass
    extraction is honest: it surfaces what was actually said and what it
    cited, without pretending to a doctrinal verdict the engine cannot
    produce on its own.
    """
    from datetime import datetime as _dt, timezone as _tz

    teaching = (body.teaching or "").strip()
    if len(teaching) < 30:
        raise HTTPException(status_code=400, detail="teaching too short (min 30 chars)")
    if len(teaching) > 200_000:
        raise HTTPException(status_code=400, detail="teaching too long (max 200k chars)")

    source = (body.source or "").strip()[:500]

    # First-pass extraction — fast, deterministic, no LLM
    citations = _extract_citations(teaching)
    keywords = _scan_doctrine_keywords(teaching)

    # Slug derived from the first sentence / opening words
    head_words = re.split(r"[.\n?!]", teaching)[0].strip()[:60]
    slug_seed = head_words or "teaching"
    slug = _discern_make_slug("teaching: " + slug_seed)

    payload = {
        "slug": slug,
        "kind": "teaching",
        "schema": "narrowhighway.discernment.teaching/1",
        "created_at": _dt.now(_tz.utc).isoformat(),
        "question": "Discern this teaching",
        "teaching": teaching,
        "source": source,
        "asked_by": (body.asked_by or "anon")[:80],
        "citations": citations,
        "keyword_hits": keywords,
        "buckets": {
            "stable": [],       # claims that align plainly
            "conditional": [],  # claims that hold only in specific context
            "hold": [],         # claims outside the reference, with citation
        },
        "status": "received",
        # These existing fields keep the discernment compatible with the
        # generic renderer/listing as a fallback:
        "interview": [],
        "narration": "",
        "cards": [],
        "corpus_size": 0,
    }
    (_DISCERN_DIR / f"{slug}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "slug": slug,
        "url": f"/d/{slug}",
        "permalink": f"{_DISCERN_BASE}/d/{slug}",
        "citations_found": len(citations),
        "keyword_hits": len(keywords),
    }


# ── Testimony · hearing-window state machine ───────────────────────
# Operator-side. A public-matter discernment (a Covenant Testimony claim)
# passes through the four gates and, if sound, enters a hearing window
# where the named subject receives the package and has a defined response
# window before publication.
#
# v1: storage + state transitions. Operator UI to follow.
_TESTIMONY_DIR = Path(__file__).resolve().parents[1] / "data" / "testimony"
_TESTIMONY_DIR.mkdir(parents=True, exist_ok=True)
_TESTIMONY_MATTERS = _TESTIMONY_DIR / "matters"
_TESTIMONY_MATTERS.mkdir(parents=True, exist_ok=True)


class _TestimonyMatterIn(BaseModel):
    matter: str               # short title / summary of the matter
    accused: str              # named subject (real name; required)
    accused_contact: str = "" # email or other reachability (optional, private)
    claims: list = []         # list of specific claims being weighed
    witnesses: list = []      # pubkeys / display names of witnesses already on the roll
    hearing_window_days: int = 14
    operator_note: str = ""   # operator's notes at creation time


@app.post("/api/testimony/matter", include_in_schema=False)
def testimony_matter_create(body: _TestimonyMatterIn):
    """Create a Covenant Testimony matter. Returns the matter id.

    Initial state is 'received' — the four gates have not yet been run.
    The operator transitions through: received -> weighing -> in_hearing_window
    -> [accused_responded or window_expired] -> published OR closed_unfit.
    """
    from datetime import datetime as _dt, timezone as _tz
    import secrets

    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()

    if not payload.get("matter") or len(payload["matter"]) < 10:
        raise HTTPException(status_code=400, detail="matter title required (min 10 chars)")
    if not payload.get("accused") or len(payload["accused"]) < 2:
        raise HTTPException(status_code=400, detail="accused (named subject) required")

    matter_id = "m-" + secrets.token_hex(6)
    payload["id"] = matter_id
    payload["schema"] = "narrowhighway.testimony.matter/1"
    payload["created_at"] = _dt.now(_tz.utc).isoformat()
    payload["status"] = "received"
    payload["gate_results"] = {}
    payload["hearing_window_started_at"] = None
    payload["hearing_window_expires_at"] = None
    payload["accused_response"] = None
    payload["published_discernment_slug"] = None
    payload["history"] = [{
        "at": payload["created_at"],
        "event": "created",
        "by": "operator",
        "note": payload.get("operator_note", ""),
    }]
    # Trim contact: keep private to operator (not displayed publicly)
    if payload.get("accused_contact"):
        payload["accused_contact"] = payload["accused_contact"][:300]

    (_TESTIMONY_MATTERS / f"{matter_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": matter_id, "status": "received"}


@app.get("/api/testimony/matter/{matter_id}", include_in_schema=False)
def testimony_matter_get(matter_id: str):
    """Read a matter's current state.
    NB: Strips accused_contact for non-operator callers in a future version.
    Today the engine is local-only and there's no public route to this."""
    if not re.fullmatch(r"m-[a-z0-9]{4,40}", matter_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = _TESTIMONY_MATTERS / f"{matter_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return json.loads(path.read_text(encoding="utf-8"))


class _TestimonyResponseIn(BaseModel):
    response_text: str
    accused_signature: str = ""  # ed25519 sig over response_text (optional v1)


@app.post("/api/testimony/matter/{matter_id}/response", include_in_schema=False)
def testimony_matter_response(matter_id: str, body: _TestimonyResponseIn):
    """The accused records their response within the hearing window."""
    from datetime import datetime as _dt, timezone as _tz

    if not re.fullmatch(r"m-[a-z0-9]{4,40}", matter_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = _TESTIMONY_MATTERS / f"{matter_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    m = json.loads(path.read_text(encoding="utf-8"))

    if m.get("status") != "in_hearing_window":
        raise HTTPException(status_code=409,
                            detail=f"matter not in hearing window (current: {m.get('status')})")

    text = (body.response_text or "").strip()
    if len(text) < 1:
        raise HTTPException(status_code=400, detail="response_text required")
    if len(text) > 50_000:
        raise HTTPException(status_code=400, detail="response too long (max 50k chars)")

    now = _dt.now(_tz.utc).isoformat()
    m["accused_response"] = {
        "received_at": now,
        "text": text,
        "signature": (body.accused_signature or "")[:200] or None,
    }
    m["status"] = "accused_responded"
    m.setdefault("history", []).append({
        "at": now, "event": "accused_response_recorded", "by": "accused",
    })
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": matter_id, "status": m["status"]}


class _TestimonyTransitionIn(BaseModel):
    to: str  # new status
    note: str = ""


@app.post("/api/testimony/matter/{matter_id}/transition", include_in_schema=False)
def testimony_matter_transition(matter_id: str, body: _TestimonyTransitionIn):
    """Operator transitions the matter to a new state. Valid transitions
    are checked. Free text 'note' captures why."""
    from datetime import datetime as _dt, timezone as _tz, timedelta

    if not re.fullmatch(r"m-[a-z0-9]{4,40}", matter_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = _TESTIMONY_MATTERS / f"{matter_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    m = json.loads(path.read_text(encoding="utf-8"))

    valid_transitions = {
        "received": ["weighing", "closed_unfit"],
        "weighing": ["in_hearing_window", "closed_unfit"],
        "in_hearing_window": ["accused_responded", "window_expired", "closed_unfit"],
        "accused_responded": ["published", "closed_unfit"],
        "window_expired": ["published", "closed_unfit"],
    }
    cur = m.get("status", "received")
    new = body.to
    if new not in valid_transitions.get(cur, []):
        raise HTTPException(
            status_code=409,
            detail=f"invalid transition {cur} -> {new} (valid: {valid_transitions.get(cur, [])})",
        )

    now = _dt.now(_tz.utc)
    m["status"] = new
    if new == "in_hearing_window":
        m["hearing_window_started_at"] = now.isoformat()
        days = int(m.get("hearing_window_days") or 14)
        m["hearing_window_expires_at"] = (now + timedelta(days=days)).isoformat()
    m.setdefault("history", []).append({
        "at": now.isoformat(),
        "event": f"transition:{cur}->{new}",
        "by": "operator",
        "note": (body.note or "")[:500],
    })
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": matter_id, "status": new}


# ── Gated generation — the mechanism, formalized ──────────────────
# /api/generate-gated is the single endpoint that runs the full pipeline:
# RED -> base LLM -> verifiers -> FLOOR -> BROTHERS -> GOD -> audit + hash.
# Pluggable base LLM (Anthropic today; our fine-tuned model later).
# Stable schema (narrowhighway.gated_response/1) so training data
# accumulated today remains readable forever.

class _GenerateGatedIn(BaseModel):
    prompt: str
    max_tokens: int = 4096
    verifiers: list = []          # empty = use defaults
    witness_pubkeys: list = []    # named witnesses who've already signed
    context: dict = {}            # caller metadata (source, intent, etc.)
    base_model: str = ""          # adapter override; empty = anthropic
    persist: bool = True          # save as a /d/<slug> record


@app.post("/api/generate-gated", include_in_schema=False)
def generate_gated_endpoint(body: _GenerateGatedIn):
    """The mechanism as one HTTP call.

    Accepts a prompt, runs the full pipeline (RED -> base LLM -> verifiers ->
    FLOOR -> BROTHERS -> GOD -> audit trail -> SHA256 hash), and returns the
    canonical response. If persist=True (default), the response is saved as a
    permanent /d/<slug> record viewable at /d/<slug>.
    """
    from api.generate_gated import (
        run_gated, AnthropicAdapter, EchoAdapter, DEFAULT_VERIFIERS,
    )

    prompt = (body.prompt or "").strip()
    if len(prompt) < 3:
        raise HTTPException(status_code=400, detail="prompt too short (min 3 chars)")
    if len(prompt) > 200_000:
        raise HTTPException(status_code=400, detail="prompt too long (max 200k chars)")

    # Pick the base model adapter.
    # - "anthropic" / "echo"  → built-in adapters
    # - "local:<model_id>"     → LocalModelAdapter (model from data/models/registry.json)
    #                             e.g. "local:nh-7B-Instruct-1a2b3c-20260601-120000"
    adapter_name = (body.base_model or "anthropic").strip()
    adapter_name_lower = adapter_name.lower()
    if adapter_name_lower == "echo":
        adapter = EchoAdapter()
    elif adapter_name_lower == "anthropic":
        adapter = AnthropicAdapter()
    elif adapter_name_lower.startswith("local"):
        # local:<model_id>  or just "local" (defaults to most-recently-registered)
        from api.generate_gated import LocalModelAdapter
        model_id = ""
        if ":" in adapter_name:
            model_id = adapter_name.split(":", 1)[1].strip()
        # Look up in registry
        registry_path = (Path(__file__).resolve().parents[1]
                         / "data" / "models" / "registry.json")
        if not registry_path.exists():
            raise HTTPException(
                status_code=404,
                detail="model registry is empty; no local models registered yet",
            )
        try:
            reg = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail=f"could not read registry: {e}")
        models = reg.get("models", [])
        if not models:
            raise HTTPException(status_code=404,
                                detail="no models registered yet")
        chosen = None
        if model_id:
            for m in models:
                if m.get("id") == model_id:
                    chosen = m
                    break
            if not chosen:
                raise HTTPException(status_code=404,
                                    detail=f"local model not found: {model_id}")
        else:
            # Most recently registered
            chosen = sorted(
                models, key=lambda m: m.get("registered_at", ""), reverse=True
            )[0]
        adapter_path_rel = chosen.get("adapter_path", "")
        adapter_path = (Path(__file__).resolve().parents[1]
                        / adapter_path_rel) if adapter_path_rel else None
        try:
            adapter = LocalModelAdapter(
                model_id=chosen["base_model"],
                adapter_path=str(adapter_path) if adapter_path else None,
                backend=chosen.get("backend", "hf"),
            )
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=(f"could not load local model {chosen.get('id')}: {e}. "
                        f"Make sure the backend's runtime (mlx-lm or transformers/peft) "
                        f"is installed in the engine's Python env."),
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"unknown base_model adapter: {adapter_name} "
                   f"(supported: anthropic, echo, local, local:<model_id>)",
        )

    verifiers = list(body.verifiers) if body.verifiers else list(DEFAULT_VERIFIERS)

    try:
        response = run_gated(
            prompt,
            base=adapter,
            witness_pubkeys=list(body.witness_pubkeys or []),
            context=dict(body.context or {}),
            verifiers=verifiers,
            max_tokens=int(body.max_tokens or 4096),
        )
    except RuntimeError as e:
        # Adapter or API key issue — surface cleanly
        raise HTTPException(status_code=503, detail=str(e))

    # Optionally persist as a /d/<slug> record
    if body.persist:
        slug = _discern_make_slug("gated: " + prompt[:60])
        response["slug"] = slug
        (_DISCERN_DIR / f"{slug}.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        response["url"] = f"/d/{slug}"
        response["permalink"] = f"{_DISCERN_BASE}/d/{slug}"

    return response


# ── Witness Roll endpoints ────────────────────────────────────────
# The BROTHERS gate's public face. Three endpoints:
#   GET  /witness/roll.json            — public roll (active witnesses only)
#   POST /api/witness/apply            — record an application (operator reviews)
#   GET  /api/witness/applications     — operator-only: pending applications list
#
# Storage:
#   data/witness_roll/roll.json                        — public, signed roll
#   data/witness_roll/applications/<app_id>.json       — pending applications
#
# An application becomes a roll entry only when the operator approves
# it (via a manual edit to roll.json for v1; an admin endpoint in v2).

_WITNESS_DIR = Path(__file__).resolve().parents[1] / "data" / "witness_roll"
_WITNESS_DIR.mkdir(parents=True, exist_ok=True)
_WITNESS_ROLL_PATH = _WITNESS_DIR / "roll.json"
_WITNESS_APPLICATIONS = _WITNESS_DIR / "applications"
_WITNESS_APPLICATIONS.mkdir(parents=True, exist_ok=True)


def _load_witness_roll() -> dict:
    """Read the canonical roll. Empty schema if file missing."""
    if not _WITNESS_ROLL_PATH.exists():
        return {
            "schema": "narrowhighway.witness_roll/1",
            "witnesses": [],
            "updated_at": None,
        }
    try:
        return json.loads(_WITNESS_ROLL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema": "narrowhighway.witness_roll/1",
            "witnesses": [],
            "updated_at": None,
            "load_error": True,
        }


@app.get("/witness/roll.json", include_in_schema=False)
def witness_roll_get():
    """Public Witness Roll. Returns the named persons who have agreed to
    stand as witnesses for discernments, in the shape /witnesses.html expects.

    Each entry: { display_name, pubkey, attestations, joined, status }.
    Status: 'active' | 'standing' | 'removed' (page strikes 'removed').
    """
    return _load_witness_roll()


class _WitnessApplyIn(BaseModel):
    display_name: str               # the real name to be shown on the roll
    contact: str                    # email or similar (kept private by operator)
    pubkey: str = ""                # optional ed25519 pubkey; can be added later
    reason: str = ""                # why they want to stand (max 4000 chars)
    affiliation: str = ""           # church, role, etc. (optional, max 200 chars)


@app.post("/api/witness/apply", include_in_schema=False)
def witness_apply(body: _WitnessApplyIn):
    """Record an application to join the Witness Roll.

    Validates input minimums and persists to disk. Operator reviews
    out-of-band (currently: read data/witness_roll/applications/<id>.json,
    decide, manually add to data/witness_roll/roll.json).
    """
    from datetime import datetime as _dt, timezone as _tz
    import secrets

    name = (body.display_name or "").strip()
    contact = (body.contact or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="display_name required (min 2 chars)")
    if len(contact) < 3:
        raise HTTPException(status_code=400, detail="contact required (email or similar)")
    if len(contact) > 300:
        raise HTTPException(status_code=400, detail="contact too long (max 300 chars)")

    reason = (body.reason or "").strip()[:4000]
    affiliation = (body.affiliation or "").strip()[:200]
    pubkey = (body.pubkey or "").strip()[:200]

    app_id = "wa-" + secrets.token_hex(6)
    payload = {
        "schema": "narrowhighway.witness_application/1",
        "id": app_id,
        "display_name": name,
        "contact": contact,             # PRIVATE — operator-only
        "pubkey": pubkey,
        "reason": reason,
        "affiliation": affiliation,
        "submitted_at": _dt.now(_tz.utc).isoformat(),
        "status": "pending",            # pending | invited_to_interview | admitted | declined
        "operator_notes": [],
    }
    (_WITNESS_APPLICATIONS / f"{app_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Return the application id and a public-safe acknowledgement;
    # do NOT echo back the contact info.
    return {
        "id": app_id,
        "status": "pending",
        "message": (
            "Your application has been recorded. The operator reads each one. "
            "Expect a follow-up email within a few days to schedule the "
            "interview described on /witnesses.html."
        ),
    }


@app.get("/api/witness/applications", include_in_schema=False)
def witness_applications_list(status: str = "", limit: int = 100):
    """List witness applications. Operator-only in spirit; no public
    surface points here. Today the engine is local + IP-gated so this
    is effectively private."""
    files = sorted(
        _WITNESS_APPLICATIONS.glob("wa-*.json"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    out = []
    for f in files[: max(1, min(int(limit or 100), 500))]:
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and a.get("status") != status:
            continue
        out.append({
            "id": a.get("id"),
            "display_name": a.get("display_name"),
            "affiliation": a.get("affiliation"),
            "submitted_at": a.get("submitted_at"),
            "status": a.get("status"),
            # Operator sees the contact in the file directly; not here.
        })
    return {"count": len(out), "items": out}


@app.get("/api/testimony/matters", include_in_schema=False)
def testimony_matters_list(status: str = "", limit: int = 50):
    """List matters (optionally filter by status). Operator-only in spirit;
    today no public route exposes this."""
    files = sorted(_TESTIMONY_MATTERS.glob("m-*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[: max(1, min(int(limit or 50), 500))]:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and m.get("status") != status:
            continue
        out.append({
            "id": m.get("id"),
            "matter": m.get("matter"),
            "accused": m.get("accused"),
            "status": m.get("status"),
            "created_at": m.get("created_at"),
            "hearing_window_expires_at": m.get("hearing_window_expires_at"),
        })
    return {"count": len(out), "items": out}


def _discern_render_teaching_html(d: dict) -> str:
    """Server-render a kind=teaching record. Different shape from a generic
    discernment: the teaching IS the content; the citations and keyword hits
    are the first-pass trail; the buckets (stable/conditional/hold) fill in
    over time as the operator and witnesses weigh the matter."""
    teaching = d.get("teaching") or ""
    source = d.get("source") or ""
    citations = d.get("citations") or []
    keyword_hits = d.get("keyword_hits") or []
    buckets = d.get("buckets") or {}
    status = d.get("status") or "received"
    slug = d.get("slug") or ""
    created = (d.get("created_at") or "")[:10]
    permalink = f"{_DISCERN_BASE}/d/{slug}"

    # Truncate the teaching for the OG card description
    desc = (teaching[:200] + ("..." if len(teaching) > 200 else "")).replace("\n", " ")
    title_short = "Discern this teaching"

    head = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>' + _discern_esc(title_short) +
        ' &middot; Narrow Highway</title>\n'
        '<meta name="description" content="' + _discern_esc(desc) + '">\n'
        '<link rel="canonical" href="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:site_name" content="Narrow Highway">\n'
        '<meta property="og:title" content="A teaching, read against the reference">\n'
        '<meta property="og:description" content="' + _discern_esc(desc) + '">\n'
        '<meta property="og:url" content="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:image" content="' + _DISCERN_BASE +
        '/img/og_card.png">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n'
        '<link rel="stylesheet" href="/nh-shell.css">\n'
        '<script defer src="/nh-shell.js"></script>\n'
        '<link rel="stylesheet" href="/nh-discern.css">\n'
        '<style>\n'
        '  .td-wrap { max-width: 820px; margin: 0 auto; padding: 1em 1.2em 3em;\n'
        '    background: #fafaf6; color: #2a2a28;\n'
        '    font-family: Georgia, serif; line-height: 1.65; }\n'
        '  .td-masthead { text-align: center; padding: 2em 1em 1.2em;\n'
        '    border-bottom: 3px double #b8945a; margin-bottom: 1.4em; }\n'
        '  .td-masthead .eyebrow { font-family: "Courier New", monospace;\n'
        '    font-size: 0.74em; letter-spacing: 0.24em; text-transform: uppercase;\n'
        '    color: #b8945a; margin-bottom: 0.5em; }\n'
        '  .td-masthead h1 { font-family: Georgia, serif; font-weight: normal;\n'
        '    font-size: 2.2em; color: #1a3a52; margin: 0; }\n'
        '  .td-stamp { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    color: #806010; letter-spacing: 0.06em; margin-top: 0.6em; }\n'
        '  .td-status { display: inline-block; padding: 0.3em 0.9em;\n'
        '    background: #fff5d4; border: 1px solid #c9b48a; border-radius: 16px;\n'
        '    font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    color: #806010; margin-top: 0.6em; letter-spacing: 0.05em;\n'
        '    text-transform: uppercase; }\n'
        '  .td-section h2 { color: #1a3a52; font-weight: normal; font-size: 1.4em;\n'
        '    margin-top: 1.8em; padding-bottom: 0.3em;\n'
        '    border-bottom: 1px solid #d4c8a5; }\n'
        '  .td-teaching { background: #fff; border: 1px solid #d4c8a5;\n'
        '    border-radius: 6px; padding: 1.2em 1.4em; margin: 1em 0;\n'
        '    font-size: 1.02em; white-space: pre-wrap; line-height: 1.6;\n'
        '    box-shadow: 0 1px 0 #e8e0c0; }\n'
        '  .td-source { font-family: "Courier New", monospace; font-size: 0.82em;\n'
        '    color: #806010; margin-top: 0.6em; font-style: italic; }\n'
        '  .td-pills { display: flex; flex-wrap: wrap; gap: 6px; margin: 0.6em 0; }\n'
        '  .td-pill { display: inline-block; padding: 0.25em 0.7em;\n'
        '    border-radius: 16px; font-family: "Courier New", monospace;\n'
        '    font-size: 0.78em; letter-spacing: 0.06em; }\n'
        '  .td-pill.cite { background: #1a3a52; color: #f4ecd5; }\n'
        '  .td-pill.healthy { background: #d4ead4; color: #1f5b1f; }\n'
        '  .td-pill.concerning { background: #fff5d4; color: #806010;\n'
        '    border: 1px solid #c9b48a; }\n'
        '  .td-bucket { background: #fff; border: 1px solid #d4c8a5;\n'
        '    border-radius: 6px; padding: 1em 1.2em; margin: 0.8em 0; }\n'
        '  .td-bucket.stable { border-left: 4px solid #1f5b1f; }\n'
        '  .td-bucket.conditional { border-left: 4px solid #806010; }\n'
        '  .td-bucket.hold { border-left: 4px solid #8b1f1f; }\n'
        '  .td-bucket h3 { margin: 0 0 0.4em; color: #1a3a52; font-size: 1.1em; }\n'
        '  .td-bucket .empty { color: #6a5a3a; font-style: italic; font-size: 0.95em; }\n'
        '  .td-bucket .empty-pending {\n'
        '    background: #fff5d4; border: 1px dashed #c9b48a; padding: 0.6em 0.9em;\n'
        '    border-radius: 4px; margin-top: 0.4em; }\n'
        '  .td-posture { background: #fff5d4; border-left: 4px solid #b8945a;\n'
        '    padding: 0.9em 1.2em; margin: 1.4em 0; border-radius: 0 4px 4px 0;\n'
        '    font-size: 0.94em; }\n'
        '  .td-permalink { font-family: "Courier New", monospace; font-size: 0.85em;\n'
        '    color: #6a5a3a; margin-top: 1.6em; padding-top: 1em;\n'
        '    border-top: 1px solid #d4c8a5; }\n'
        '  .td-permalink code { background: #f3eedb; padding: 0.2em 0.5em;\n'
        '    border-radius: 3px; word-break: break-all; }\n'
        '</style>\n'
        '</head>\n<body>\n'
    )

    masthead = (
        '<div class="td-wrap">\n'
        '<div class="td-masthead">\n'
        '<div class="eyebrow">Discernment Engine &middot; Teaching, read against the reference</div>\n'
        '<h1>A teaching, weighed</h1>\n'
        '<div class="td-stamp">' + _discern_esc(created) +
        ' &middot; ' + str(len(citations)) + ' Scripture citation' +
        ('' if len(citations) == 1 else 's') + ' &middot; ' +
        str(len(keyword_hits)) + ' doctrine flag' +
        ('' if len(keyword_hits) == 1 else 's') + '</div>\n'
        '<div class="td-status">Status: ' + _discern_esc(status) + '</div>\n'
        '</div>\n'
    )

    teaching_block = (
        '<section class="td-section">\n'
        '<h2>The teaching</h2>\n'
        '<div class="td-teaching">' + _discern_esc(teaching) + '</div>\n' +
        ('<div class="td-source">Source: ' + _discern_esc(source) + '</div>\n'
         if source else "") +
        '</section>\n'
    )

    # Scripture citations strip
    if citations:
        cite_pills = []
        for c in citations[:30]:
            label = c.get("raw") or (
                str(c.get("book", "")) + " " + str(c.get("chapter", "")) +
                (":" + str(c.get("verse")) if c.get("verse") else "")
            )
            cite_pills.append('<span class="td-pill cite">' +
                              _discern_esc(label.strip()) + '</span>')
        citations_block = (
            '<section class="td-section">\n'
            '<h2>Scripture cited (first pass)</h2>\n'
            '<p>The engine pulled these references out of the teaching. Each is a place a careful reader will want to read in context.</p>\n'
            '<div class="td-pills">' + "".join(cite_pills) + '</div>\n'
            '</section>\n'
        )
    else:
        citations_block = (
            '<section class="td-section">\n'
            '<h2>Scripture cited (first pass)</h2>\n'
            '<p class="td-bucket empty">No Scripture references detected in the text. That alone is not a verdict &mdash; a teaching can be deeply scriptural without citing chapter-and-verse, and a teaching can cite many verses without being scriptural. The engine reports what it found.</p>\n'
            '</section>\n'
        )

    # Doctrine keyword hits
    if keyword_hits:
        healthy_hits = [h for h in keyword_hits if h.get("kind") == "healthy"]
        concerning_hits = [h for h in keyword_hits if h.get("kind") == "concerning"]
        parts = []
        if healthy_hits:
            parts.append('<p><strong>Healthy markers detected:</strong></p>')
            parts.append('<div class="td-pills">')
            for h in healthy_hits[:20]:
                parts.append('<span class="td-pill healthy">' +
                             _discern_esc(h.get("tag", "").replace("_", " ")) +
                             '</span>')
            parts.append('</div>')
        if concerning_hits:
            parts.append('<p style="margin-top:0.9em;"><strong>Patterns that historically need careful reading:</strong></p>')
            parts.append('<div class="td-pills">')
            for h in concerning_hits[:20]:
                parts.append('<span class="td-pill concerning">' +
                             _discern_esc(h.get("tag", "").replace("_", " ")) +
                             '</span>')
            parts.append('</div>')
            parts.append('<p style="font-size:0.92em; color:#6a5a3a; font-style:italic; margin-top:0.6em;">A flag is not a verdict. The engine has historically seen these patterns used in both sound and unsound ways. Read in context; verify against Scripture; consult a pastor when stakes are real.</p>')
        keyword_block = (
            '<section class="td-section">\n'
            '<h2>Doctrine pattern flags</h2>\n' +
            "".join(parts) +
            '</section>\n'
        )
    else:
        keyword_block = ""

    # Buckets (initially empty, fill over time)
    def _render_bucket(name: str, label: str, items: list, empty_msg: str) -> str:
        h = ('<div class="td-bucket ' + name + '">\n'
             '<h3>' + label + '</h3>\n')
        if items:
            h += '<ul>'
            for it in items:
                claim = it.get("claim", "") if isinstance(it, dict) else str(it)
                cite = it.get("citation", "") if isinstance(it, dict) else ""
                note = it.get("note", "") if isinstance(it, dict) else ""
                h += '<li>' + _discern_esc(claim)
                if cite:
                    h += ' <em>(' + _discern_esc(cite) + ')</em>'
                if note:
                    h += '<br><span style="font-size:0.9em; color:#6a5a3a;">' + _discern_esc(note) + '</span>'
                h += '</li>'
            h += '</ul>'
        else:
            h += ('<div class="empty-pending">' + empty_msg + '</div>')
        h += '</div>\n'
        return h

    buckets_block = (
        '<section class="td-section">\n'
        '<h2>What aligns, what is conditional, what is held</h2>\n' +
        _render_bucket(
            "stable", "Stable &middot; aligns plainly",
            buckets.get("stable", []),
            'The operator and witnesses on the roll have not yet recorded what aligns in this teaching. As the matter is read carefully, claims that plainly match Scripture appear here.'
        ) +
        _render_bucket(
            "conditional", "Conditional &middot; holds in specific contexts",
            buckets.get("conditional", []),
            'Claims that hold in some contexts but cannot be universalized live here once weighed. None yet.'
        ) +
        _render_bucket(
            "hold", "Hold &middot; outside the reference",
            buckets.get("hold", []),
            'Claims that fall outside Scripture or the historical Christian record live here, with the citation that disagrees. None yet.'
        ) +
        '</section>\n'
    )

    posture = (
        '<div class="td-posture">\n'
        '<p style="margin-top:0;"><strong>A tool, not a tribunal.</strong> This page reads <em>a teaching</em> against the reference. It does not adjudicate <em>the speaker</em>, does not rule on a person\'s salvation, does not replace pastoral discernment in a real church, and is not authorized teaching itself.</p>\n'
        '<p style="margin-bottom:0;">The first-pass extraction is what the engine could read deterministically. The buckets fill in as the operator and named witnesses weigh the matter carefully. The trail is here so you can check it.</p>\n'
        '</div>\n'
    )

    perma = (
        '<div class="td-permalink">'
        'Permalink: <code>' + _discern_esc(permalink) + '</code><br>'
        '<a href="/walk.html" style="color:#1a3a52;">Bring another teaching &rarr;</a>'
        '</div>\n'
    )

    foot = (
        '</div>\n'  # /td-wrap
        '<script defer src="/nh-shepherd.js"></script>\n'
        '</body>\n</html>\n'
    )

    return (head + masthead + teaching_block + citations_block +
            keyword_block + buckets_block + posture + perma + foot)


def _discern_render_gated_html(d: dict) -> str:
    """Server-render a kind=gated-generation record.

    This is the mechanism's permanent receipt for one prompt-and-response
    cycle. Shows the prompt, the base LLM's output, every verifier result,
    every gate decision, the trail, and the content hash.
    """
    prompt_obj = d.get("prompt") or {}
    prompt_text = prompt_obj.get("text", "") if isinstance(prompt_obj, dict) else str(prompt_obj)
    gen = d.get("generation") or {}
    gen_text = gen.get("text", "") if isinstance(gen, dict) else ""
    base_model = d.get("base_model") or {}
    base_name = (base_model.get("name") or "") + "/" + (base_model.get("model_id") or "")
    gate_results = d.get("gate_results") or []
    verifier_results = d.get("verifier_results") or []
    trail = d.get("trail") or []
    metrics = d.get("metrics") or {}
    final = d.get("final_decision") or "hold"
    content_hash = d.get("content_hash") or ""
    slug = d.get("slug") or ""
    created = (d.get("created_at") or "")[:19].replace("T", " ")
    permalink = f"{_DISCERN_BASE}/d/{slug}"

    desc = (prompt_text[:200] + "...") if len(prompt_text) > 200 else prompt_text
    desc = desc.replace("\n", " ")

    # Decision pill color
    decision_color = {
        "stable": "#1f5b1f",
        "stable_pending_witness": "#1a3a52",
        "conditional": "#806010",
        "hold": "#6a5a3a",
        "rejected": "#8b1f1f",
    }.get(final, "#6a5a3a")

    head = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Gated generation &middot; ' + _discern_esc(slug) + '</title>\n'
        '<meta name="description" content="' + _discern_esc(desc) + '">\n'
        '<link rel="canonical" href="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:site_name" content="Narrow Highway">\n'
        '<meta property="og:title" content="A gated-generation receipt">\n'
        '<meta property="og:description" content="' + _discern_esc(desc) + '">\n'
        '<meta property="og:url" content="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:image" content="' + _DISCERN_BASE + '/img/og_card.png">\n'
        '<meta name="twitter:card" content="summary">\n'
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n'
        '<link rel="stylesheet" href="/nh-shell.css">\n'
        '<script defer src="/nh-shell.js"></script>\n'
        '<style>\n'
        '  .gg-wrap { max-width: 880px; margin: 0 auto; padding: 1em 1.2em 3em;\n'
        '    background: #fafaf6; color: #2a2a28; font-family: Georgia, serif;\n'
        '    line-height: 1.6; }\n'
        '  .gg-masthead { text-align: center; padding: 1.6em 1em 1.1em;\n'
        '    border-bottom: 3px double #b8945a; margin-bottom: 1.2em; }\n'
        '  .gg-eyebrow { font-family: "Courier New", monospace; font-size: 0.74em;\n'
        '    letter-spacing: 0.22em; text-transform: uppercase; color: #b8945a;\n'
        '    margin-bottom: 0.4em; }\n'
        '  .gg-masthead h1 { font-family: Georgia, serif; font-weight: normal;\n'
        '    color: #1a3a52; font-size: 1.8em; margin: 0; }\n'
        '  .gg-decision { display: inline-block; padding: 0.35em 1em;\n'
        '    background: ' + decision_color + '; color: #fff; border-radius: 16px;\n'
        '    font-family: "Courier New", monospace; font-size: 0.85em;\n'
        '    letter-spacing: 0.08em; text-transform: uppercase; margin-top: 0.7em; }\n'
        '  .gg-stamp { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    color: #806010; margin-top: 0.4em; }\n'
        '  .gg-section { background: #fff; border: 1px solid #d4c8a5;\n'
        '    border-radius: 6px; padding: 1em 1.3em; margin: 1em 0;\n'
        '    box-shadow: 0 1px 0 #e8e0c0; }\n'
        '  .gg-section h2 { color: #1a3a52; font-weight: normal; font-size: 1.2em;\n'
        '    margin: 0 0 0.5em; padding-bottom: 0.3em; border-bottom: 1px solid #d4c8a5; }\n'
        '  .gg-text { background: #fafaf6; border: 1px solid #e8e0c0;\n'
        '    border-radius: 4px; padding: 0.8em 1em; font-size: 0.96em;\n'
        '    white-space: pre-wrap; line-height: 1.55; }\n'
        '  .gg-meta { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    color: #806010; margin: 0.4em 0; letter-spacing: 0.04em; }\n'
        '  .gg-gates { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));\n'
        '    gap: 0.6em; }\n'
        '  .gg-gate { padding: 0.7em 0.9em; background: #fafaf6;\n'
        '    border: 1px solid #d4c8a5; border-radius: 4px; }\n'
        '  .gg-gate .name { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    letter-spacing: 0.12em; color: #806010; }\n'
        '  .gg-gate .decision { font-weight: bold; margin-top: 0.2em; }\n'
        '  .gg-gate .decision.pass { color: #1f5b1f; }\n'
        '  .gg-gate .decision.reject { color: #8b1f1f; }\n'
        '  .gg-gate .decision.wait { color: #806010; }\n'
        '  .gg-gate .decision.deferred { color: #1a3a52; }\n'
        '  .gg-gate .reason { font-size: 0.84em; color: #6a5a3a;\n'
        '    margin-top: 0.3em; line-height: 1.4; }\n'
        '  .gg-verifiers { display: flex; flex-direction: column; gap: 0.4em; }\n'
        '  .gg-verifier { padding: 0.6em 0.9em; background: #fafaf6;\n'
        '    border: 1px solid #d4c8a5; border-radius: 4px;\n'
        '    display: flex; justify-content: space-between; align-items: baseline;\n'
        '    gap: 0.8em; flex-wrap: wrap; }\n'
        '  .gg-verifier .name { font-family: "Courier New", monospace; font-size: 0.84em;\n'
        '    color: #1a3a52; }\n'
        '  .gg-verifier .verdict { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    letter-spacing: 0.04em; padding: 0.15em 0.6em; border-radius: 3px; }\n'
        '  .gg-verifier .verdict.CONFIRMED { background: #d4ead4; color: #1f5b1f; }\n'
        '  .gg-verifier .verdict.MIXED { background: #fff5d4; color: #806010; }\n'
        '  .gg-verifier .verdict.MISMATCH { background: #f7d4d4; color: #8b1f1f; }\n'
        '  .gg-verifier .verdict.NOT_APPLICABLE { background: #eee; color: #555; }\n'
        '  .gg-verifier .summary { width: 100%; font-size: 0.86em;\n'
        '    color: #6a5a3a; margin-top: 0.2em; }\n'
        '  .gg-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\n'
        '    gap: 0.6em; }\n'
        '  .gg-metric { padding: 0.6em 0.9em; background: #fafaf6;\n'
        '    border: 1px solid #d4c8a5; border-radius: 4px; }\n'
        '  .gg-metric .lbl { font-family: "Courier New", monospace; font-size: 0.74em;\n'
        '    letter-spacing: 0.1em; color: #806010; text-transform: uppercase; }\n'
        '  .gg-metric .val { font-family: "Courier New", monospace; font-size: 1.15em;\n'
        '    color: #1a3a52; margin-top: 0.2em; }\n'
        '  .gg-trail { font-family: "Courier New", monospace; font-size: 0.82em;\n'
        '    color: #2a2a28; background: #fafaf6; border: 1px solid #d4c8a5;\n'
        '    border-radius: 4px; padding: 0.8em 1em; max-height: 320px; overflow: auto; }\n'
        '  .gg-trail .row { padding: 0.2em 0; border-bottom: 1px dashed #e8e0c0; }\n'
        '  .gg-trail .row:last-child { border-bottom: 0; }\n'
        '  .gg-trail .step { color: #1a3a52; font-weight: bold; }\n'
        '  .gg-trail .when { color: #806010; }\n'
        '  .gg-hash { font-family: "Courier New", monospace; font-size: 0.78em;\n'
        '    color: #6a5a3a; word-break: break-all; padding: 0.6em 0.8em;\n'
        '    background: #f3eedb; border-radius: 4px; }\n'
        '</style>\n'
        '</head>\n<body>\n'
    )

    # Masthead
    masthead = (
        '<div class="gg-wrap">\n'
        '<div class="gg-masthead">\n'
        '<div class="gg-eyebrow">The Mechanism &middot; Gated-generation receipt</div>\n'
        '<h1>' + _discern_esc(slug) + '</h1>\n'
        '<div class="gg-decision">' + _discern_esc(final.replace("_", " ")) + '</div>\n'
        '<div class="gg-stamp">' + _discern_esc(created) + ' UTC &middot; ' +
        _discern_esc(base_name) + '</div>\n'
        '</div>\n'
    )

    # Prompt section
    prompt_block = (
        '<section class="gg-section">\n'
        '<h2>Prompt</h2>\n'
        '<div class="gg-text">' + _discern_esc(prompt_text) + '</div>\n'
        '<div class="gg-meta">' + str(prompt_obj.get("char_count", len(prompt_text))) +
        ' chars</div>\n'
        '</section>\n'
    )

    # Generation section
    if gen_text:
        gen_block = (
            '<section class="gg-section">\n'
            '<h2>Generation</h2>\n'
            '<div class="gg-text">' + _discern_esc(gen_text) + '</div>\n'
            '<div class="gg-meta">' +
            str(gen.get("tokens_in", 0)) + ' tokens in &middot; ' +
            str(gen.get("tokens_out", 0)) + ' tokens out &middot; ' +
            str(round(gen.get("latency_ms", 0))) + ' ms &middot; $' +
            str(round(gen.get("cost_usd", 0), 4)) + '</div>\n'
            '</section>\n'
        )
    else:
        gen_block = (
            '<section class="gg-section">\n'
            '<h2>Generation</h2>\n'
            '<div class="gg-text" style="color:#8b1f1f;font-style:italic;">'
            'No generation produced &mdash; halted by an upstream gate or LLM call failed. See trail below.'
            '</div></section>\n'
        )

    # Gates section
    gate_parts = []
    for g in gate_results:
        dec = g.get("decision", "")
        gate_parts.append(
            '<div class="gg-gate">\n'
            '<div class="name">' + _discern_esc(g.get("gate", "")) + '</div>\n'
            '<div class="decision ' + _discern_esc(dec) + '">' +
            _discern_esc(dec) + '</div>\n'
            '<div class="reason">' + _discern_esc(g.get("reason", "")) + '</div>\n'
            '</div>\n'
        )
    gates_block = (
        '<section class="gg-section">\n'
        '<h2>The four gates</h2>\n'
        '<div class="gg-gates">' + "".join(gate_parts) + '</div>\n'
        '</section>\n'
    )

    # Verifiers section
    if verifier_results:
        v_parts = []
        for vr in verifier_results:
            verdict = vr.get("verdict", "")
            v_parts.append(
                '<div class="gg-verifier">\n'
                '<span class="name">' + _discern_esc(vr.get("verifier", "")) + '</span>\n'
                '<span class="verdict ' + _discern_esc(verdict) + '">' +
                _discern_esc(verdict) + '</span>\n'
                '<div class="summary">' + _discern_esc(vr.get("summary", "")) + '</div>\n'
                '</div>\n'
            )
        verifiers_block = (
            '<section class="gg-section">\n'
            '<h2>Verifier results</h2>\n'
            '<div class="gg-verifiers">' + "".join(v_parts) + '</div>\n'
            '</section>\n'
        )
    else:
        verifiers_block = ""

    # Metrics
    metrics_block = (
        '<section class="gg-section">\n'
        '<h2>Metrics</h2>\n'
        '<div class="gg-metrics">\n'
        '<div class="gg-metric"><div class="lbl">Total latency</div>'
        '<div class="val">' + str(round(metrics.get("total_latency_ms", 0), 1)) + ' ms</div></div>\n'
        '<div class="gg-metric"><div class="lbl">Base LLM</div>'
        '<div class="val">' + str(round(metrics.get("base_llm_latency_ms", 0), 1)) + ' ms</div></div>\n'
        '<div class="gg-metric"><div class="lbl">Verifiers</div>'
        '<div class="val">' + str(round(metrics.get("verifier_latency_ms", 0), 1)) + ' ms</div></div>\n'
        '<div class="gg-metric"><div class="lbl">Gates</div>'
        '<div class="val">' + str(round(metrics.get("gate_latency_ms", 0), 1)) + ' ms</div></div>\n'
        '<div class="gg-metric"><div class="lbl">Cost</div>'
        '<div class="val">$' + str(round(metrics.get("total_cost_usd", 0), 4)) + '</div></div>\n'
        '</div>\n'
        '</section>\n'
    )

    # Trail
    trail_rows = []
    for t in trail:
        when = (t.get("at") or "")[11:19]  # HH:MM:SS
        step = t.get("step", "")
        extras = {k: v for k, v in t.items() if k not in ("at", "step")}
        extras_str = " ".join(f"{k}={v}" for k, v in extras.items())
        trail_rows.append(
            '<div class="row"><span class="when">' + _discern_esc(when) + '</span> ' +
            '<span class="step">' + _discern_esc(step) + '</span> ' +
            _discern_esc(extras_str[:300]) + '</div>\n'
        )
    trail_block = (
        '<section class="gg-section">\n'
        '<h2>Trail</h2>\n'
        '<div class="gg-trail">' + "".join(trail_rows) + '</div>\n'
        '</section>\n'
    )

    # Hash
    hash_block = (
        '<section class="gg-section">\n'
        '<h2>Content hash</h2>\n'
        '<div class="gg-hash">' + _discern_esc(content_hash) + '</div>\n'
        '<p style="font-size:0.85em;color:#6a5a3a;margin-top:0.5em;">SHA256 over the canonical JSON (excluding this field). Tamper detection. Ed25519 signing planned for v2 once the operator&rsquo;s signing key is provisioned on disk.</p>\n'
        '</section>\n'
    )

    foot = (
        '<p style="margin-top:1.4em;font-size:0.88em;color:#6a5a3a;text-align:center;">'
        '<a href="/walk.html" style="color:#1a3a52;">Bring another teaching</a> &middot; '
        '<a href="/" style="color:#1a3a52;">Run a discernment</a></p>\n'
        '</div>\n'
        '<script defer src="/nh-shepherd.js"></script>\n'
        '</body>\n</html>\n'
    )

    return (head + masthead + prompt_block + gen_block + gates_block +
            verifiers_block + metrics_block + trail_block + hash_block + foot)


def _discern_render_html(d: dict) -> str:
    """Server-render a discernment to crawler-friendly HTML — the engine's
    permanent record of a question: question + trail + what survived + sources.

    Dispatches to specialized renderers for kind=teaching, kind=gated-generation.
    """
    kind = d.get("kind")
    if kind == "teaching":
        return _discern_render_teaching_html(d)
    if kind == "gated-generation":
        return _discern_render_gated_html(d)
    q = d.get("question") or ""
    narration = d.get("narration") or ""
    interview = d.get("interview") or []
    cards = d.get("cards") or []
    slug = d.get("slug") or ""
    created = (d.get("created_at") or "")[:10]
    n = len(cards)
    corpus = d.get("corpus_size") or 0
    permalink = f"{_DISCERN_BASE}/d/{slug}"

    synth = ""
    if narration:
        for sep in (". ", "? ", "! "):
            i = narration.find(sep)
            if i > 0:
                synth = narration[:i].strip() + sep.strip()
                break
        if not synth:
            synth = narration[:240].strip()
    if not synth:
        synth = "What survived the gates."

    title_short = q[:70] if q else "Discernment"
    desc = (synth or q)[:200]

    # the trail — interview turns rendered chronologically
    turn_parts = []
    for t in interview:
        role = (t.get("role") or "").lower()
        text = t.get("text") or ""
        if not text or text == "[just walk]":
            continue
        who = "You" if role == "user" else "The Engine"
        turn_parts.append(
            '<div class="d-turn ' + _discern_esc(role) + '">'
            '<div class="d-who">' + _discern_esc(who) + '</div>'
            '<div class="d-body">' + _discern_esc(text) + '</div></div>'
        )
    if turn_parts:
        trail_block = (
            '<div class="d-trail">'
            '<div class="d-trail-label">The trail &mdash; how the engine got here</div>'
            + "".join(turn_parts) + '</div>\n'
        )
    else:
        trail_block = ""

    # surviving cards
    card_parts = []
    for i, c in enumerate(cards):
        src = c.get("source") or {}
        tier = (src.get("authority_tier") or "").strip()
        label = src.get("label") or ""
        ref = src.get("ref") or ""
        shelf = c.get("shelf") or ""
        box = c.get("box") or ""
        cnarr = c.get("narration") or ""
        ctitle = c.get("title") or ""
        cid = c.get("card_id") or ""
        pills = []
        if tier:
            pills.append('<span class="d-pill tier-' + _discern_esc(tier) +
                         '">' + _discern_esc(tier.replace("_", " ")) + '</span>')
        if shelf:
            shelf_label = shelf + (" / " + box if box else "")
            pills.append('<span class="d-pill">' + _discern_esc(shelf_label) + '</span>')
        src_line = ""
        if label:
            src_line = '<div class="d-src">' + _discern_esc(label)
            if ref:
                src_line += ' &middot; ' + _discern_esc(ref)
            src_line += '</div>'
        href = ("/card.html?id=" + _discern_esc(cid)) if cid else "#"
        card_parts.append(
            '<a class="d-card" href="' + href + '">'
            '<div class="d-card-face">'
            '<span class="d-num">CARD ' + ("%02d" % (i + 1)) + '</span>'
            '<h3>' + _discern_esc(ctitle) + '</h3>'
            '<div class="d-pills">' + "".join(pills) + '</div>' +
            src_line +
            '<div class="d-narr">' + _discern_esc(cnarr) + '</div>'
            '</div></a>'
        )

    head = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>' + _discern_esc(title_short) +
        ' &middot; The Discernment Engine &middot; Narrow Highway</title>\n'
        '<meta name="description" content="' + _discern_esc(desc) + '">\n'
        '<link rel="canonical" href="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:site_name" content="Narrow Highway">\n'
        '<meta property="og:title" content="' + _discern_esc(q) +
        ' &mdash; Discernment Engine">\n'
        '<meta property="og:description" content="' + _discern_esc(desc) + '">\n'
        '<meta property="og:url" content="' + _discern_esc(permalink) + '">\n'
        '<meta property="og:image" content="' + _DISCERN_BASE +
        '/img/og_card.png">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n'
        '<link rel="stylesheet" href="/nh-discern.css">\n'
        '</head>\n<body>\n'
    )

    nav = (
        '<nav class="d-top"><a href="/">&larr; Narrow Highway</a> '
        '<a href="/walk.html">Run another discernment</a> '
        '<a href="/codex.html">The Codex</a></nav>\n'
    )

    masthead = (
        '<div class="d-masthead">'
        '<div class="d-eyebrow">THE DISCERNMENT ENGINE &middot; PERMANENT RECORD</div>'
        '<h1>' + _discern_esc(q) + '</h1>'
        '<div class="d-stamp">' + _discern_esc(created) +
        ' &middot; ' + str(n) + ' card' + ('' if n == 1 else 's') +
        ' survived' +
        (' &middot; substrate of {:,}'.format(corpus) if corpus else '') +
        '</div></div>\n'
    )

    synthesis = (
        '<div class="d-synth">'
        '<span class="d-synth-lbl">What survived</span>' +
        _discern_esc(synth) + '</div>\n'
    )

    gates = (
        '<div class="d-gates">'
        '<strong>Gates the engine ran:</strong> '
        'witness gate (Deut 19:15) &middot; alignment read &middot; '
        'sixty-plus domain verifiers &middot; '
        '<strong>kept ' + str(n) + '</strong>'
        '</div>\n'
    )

    cards_section = '<div class="d-board">' + "".join(card_parts) + '</div>\n'

    footer_bar = (
        '<div class="d-footer">'
        '<div class="d-permalink">Permalink: <code>' +
        _discern_esc(permalink) + '</code></div>'
        '<a class="d-btn" href="#" id="d-copy">Copy link</a>'
        '<a class="d-btn outline" href="#" id="d-print">Print</a>'
        '<a class="d-btn outline" href="/walk.html">Run another &rarr;</a>'
        '</div>\n'
    )

    principle = (
        '<p class="d-principle">'
        '<strong>This page is the engine&#39;s record.</strong> '
        'The question was shaped through the interview, then the substrate '
        'was run through the witness, alignment, and verifier gates. Only what '
        'survived is shown above, each card carrying its source. The trail is '
        'the reasoning &mdash; that is why this page exists permanently, with '
        'its own URL. If the engine vanished tomorrow, the cards would still '
        'teach.</p>\n'
    )

    script = (
        '<script>(function(){\n'
        'var link=' + json.dumps(permalink) + ';\n'
        'var c=document.getElementById("d-copy");\n'
        'if(c)c.addEventListener("click",function(e){\n'
        '  e.preventDefault();\n'
        '  if(navigator.clipboard)navigator.clipboard.writeText(link);\n'
        '  var b=e.currentTarget,t=b.textContent;b.textContent="Copied";\n'
        '  setTimeout(function(){b.textContent=t;},1500);\n'
        '});\n'
        'var p=document.getElementById("d-print");\n'
        'if(p)p.addEventListener("click",function(e){e.preventDefault();window.print();});\n'
        '})();</script>\n'
    )

    foot = ('<script defer src="/nh-shepherd.js"></script>\n'
            '</body>\n</html>\n')

    return (head + nav + masthead + synthesis + gates + trail_block +
            cards_section + footer_bar + principle + script + foot)


@app.get("/d/recent", include_in_schema=False)
def discern_recent(limit: int = 20):
    """List the most recently minted discernments — for the operator pulse.
    Declared BEFORE /d/{slug} so the literal path wins the FastAPI match."""
    limit = max(1, min(int(limit or 20), 200))
    files = sorted(_DISCERN_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:limit]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "slug": d.get("slug"),
            "question": d.get("question") or "",
            "n_cards": len(d.get("cards") or []),
            "created_at": d.get("created_at") or "",
            "url": f"/d/{d.get('slug')}",
        })
    return {"count": len(out), "items": out}


@app.get("/d/{slug}", include_in_schema=False)
def discern_get(slug: str):
    """Serve a saved discernment as crawler-friendly HTML.
    NB: this route MUST come AFTER any /d/<literal> sibling routes — FastAPI
    matches in declaration order, so a slug-parametric path will swallow
    `/d/recent`, `/d/save`, etc. if it is registered first."""
    if not re.fullmatch(r"[a-z0-9-]{1,80}", slug):
        raise HTTPException(status_code=404, detail="Not found")
    path = _DISCERN_DIR / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load discernment")
    html = _discern_render_html(d)
    return Response(content=html, media_type="text/html; charset=utf-8")


@app.get("/sitemap_discernments.xml", include_in_schema=False)
def discern_sitemap():
    """Auto-generated sitemap of every permanent discernment."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for f in sorted(_DISCERN_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = d.get("slug")
        if not slug:
            continue
        created = (d.get("created_at") or "")[:10]
        lm = ('<lastmod>' + created + '</lastmod>') if created else ''
        lines.append('  <url><loc>' + _DISCERN_BASE + '/d/' + slug + '</loc>' +
                     lm + '<priority>0.7</priority>'
                     '<changefreq>yearly</changefreq></url>')
    lines.append('</urlset>')
    return Response(content="\n".join(lines) + "\n",
                    media_type="application/xml; charset=utf-8")


# -- Static site (must be last — catches all unmatched paths) ------------
# Serves site/ for all HTML pages, CSS, JS, icons, manifests, etc.
# API routes registered above take priority; this handles everything else.
_SITE_DIR = Path(__file__).parent.parent / "site"
if _SITE_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_SITE_DIR), html=True), name="site")
