"""feed_walks.py — RSS 2.0 feed of recent Atlas walks.

Atlas walks (curated card-paths) are the canonical "thing to watch" on the
substrate side. Publishing them as RSS gives every kind of consumer a way
to subscribe:
  - Human readers via Feedly, Inoreader, NetNewsWire
  - AI crawlers that watch RSS feeds for new content
  - Aggregators (Reelgood, JustWatch style) that ingest RSS
  - Anyone who wants to embed "latest walks" in their site via an RSS widget

Endpoint:
  GET /feed/walks.rss      → application/rss+xml  (RSS 2.0)

Cached via the periodic warmer (same pattern as the other endpoints).
"""
from __future__ import annotations

import html
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from xml.sax.saxutils import escape as xml_escape

try:
    from fastapi import APIRouter, Response
except Exception:
    APIRouter = None
    Response = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"

_CACHE: dict = {"xml": None, "checked_at": 0.0, "dir_mtime": 0.0}
_CACHE_TTL = 300.0
_LOCK = threading.Lock()

SITE_BASE = "https://narrowhighway.com"


def _rfc822(dt_iso: str) -> str:
    """Convert ISO 8601 string to RFC-822 (RSS date format)."""
    if not dt_iso:
        return ""
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except Exception:
        return ""


def _build_rss() -> str:
    """Render the RSS XML from atlas walk cards."""
    try:
        from api import atlas as _atlas
        walks = list(_atlas._all_walk_cards())
    except Exception:
        walks = []
    # Sort newest first by created_at
    walks.sort(key=lambda w: w.get("created_at") or "", reverse=True)
    # Cap to 50 items
    walks = walks[:50]

    now_rfc822 = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    items_xml = []
    for w in walks:
        wid = w.get("id") or ""
        title = (w.get("title") or "Untitled walk")[:200]
        body = (w.get("body") or "")[:1200]
        author = w.get("author") or "engine"
        created = _rfc822(w.get("created_at") or "")
        lifecycle = w.get("lifecycle_stage") or "?"
        ex = w.get("extra") or {}
        step_count = ex.get("walk_total_steps") or len(ex.get("cards_surfaced") or [])
        link = f"{SITE_BASE}/atlas/paths/{wid}"
        # Use <description> with HTML-escaped content; RSS readers handle it
        desc = (
            f"<p>{xml_escape(body)}</p>"
            f"<p><strong>Steps:</strong> {step_count} · "
            f"<strong>Lifecycle:</strong> {xml_escape(lifecycle)} · "
            f"<strong>Author:</strong> {xml_escape(author)}</p>"
            f"<p><a href=\"{link}\">View walk →</a></p>"
        )
        items_xml.append(
            "    <item>\n"
            f"      <title>{xml_escape(title)}</title>\n"
            f"      <link>{link}</link>\n"
            f"      <guid isPermaLink=\"true\">{link}</guid>\n"
            + (f"      <pubDate>{created}</pubDate>\n" if created else "")
            + f"      <description><![CDATA[{desc}]]></description>\n"
            f"      <author>noreply@narrowhighway.com ({xml_escape(author)})</author>\n"
            f"      <category>{xml_escape(lifecycle)}</category>\n"
            "    </item>"
        )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>Narrow Highway — Atlas Walks</title>\n"
        f"    <link>{SITE_BASE}/atlas.html</link>\n"
        f"    <atom:link href=\"{SITE_BASE}/feed/walks.rss\" rel=\"self\" type=\"application/rss+xml\" />\n"
        "    <description>Curated card-paths through the Concordance substrate. Every walk traverses 2-3 witnessed cards in order; the connections between them are the lesson. Free, family-safe, alignment-gated.</description>\n"
        "    <language>en-us</language>\n"
        f"    <lastBuildDate>{now_rfc822}</lastBuildDate>\n"
        f"    <pubDate>{now_rfc822}</pubDate>\n"
        f"    <generator>Concordance Engine</generator>\n"
        f"    <managingEditor>matt@narrowhighway.com (Matt Harris)</managingEditor>\n"
        f"    <webMaster>matt@narrowhighway.com (Matt Harris)</webMaster>\n"
        + "\n".join(items_xml)
        + "\n  </channel>\n"
        "</rss>\n"
    )
    return rss


def _get_rss() -> str:
    """TTL + dir-mtime + single-flight cached XML."""
    now = time.time()
    if _CACHE["xml"] is not None and (now - _CACHE["checked_at"]) < _CACHE_TTL:
        return _CACHE["xml"]
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime if CARDS_DIR.exists() else 0.0
    except Exception:
        dir_mtime = 0.0
    if _CACHE["xml"] is not None and abs(dir_mtime - _CACHE["dir_mtime"]) < 1.0:
        _CACHE["checked_at"] = now
        return _CACHE["xml"]
    with _LOCK:
        now2 = time.time()
        if _CACHE["xml"] is not None and (now2 - _CACHE["checked_at"]) < _CACHE_TTL:
            return _CACHE["xml"]
        _CACHE["xml"] = _build_rss()
        _CACHE["dir_mtime"] = dir_mtime
        _CACHE["checked_at"] = time.time()
    return _CACHE["xml"]


def warm_cache():
    try:
        xml = _get_rss()
        return {"warmed": True, "size_bytes": len(xml)}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/feed/walks.rss")
    def walks_rss():
        xml = _get_rss()
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    return router
