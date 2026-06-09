"""card_ssr.py — Server-side-rendered card pages at /c/{card_id}.

/card.html is a JS SPA — empty skeleton until the browser executes JS to
fetch /cards/{id}. That works for humans but loses non-JS crawlers (most
AI crawlers, Bing, social-card preview bots) — they see an empty page.

This endpoint returns full HTML for each card. Page contains:
  - <title>, <meta description>, OpenGraph, Twitter cards
  - <link rel="canonical"> to /c/{id}
  - <script type="application/ld+json"> schema.org Article markup
  - The card body, source, witnesses, connections — all in HTML
  - A discreet "Open interactive view →" link to the SPA /card.html?id=X
    for humans who want full interactivity (paperclip, vote, etc.)

This is the URL we put in the sitemap. Crawlers index THIS page; humans
land on it via Google/social and can click through to the interactive
version if they want.

Endpoint:
  GET /c/{card_id}    → text/html (full SSR page)

Caching: per-card HTML cached for 5 minutes (the underlying card mutates
rarely; cache invalidation via the existing cards-dir mtime is overkill
for this surface).
"""
from __future__ import annotations

import html
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape as xml_escape

try:
    from fastapi import APIRouter, HTTPException, Response
except Exception:
    APIRouter = None
    Response = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
SITE_BASE = "https://narrowhighway.com"
LOGO_URL = f"{SITE_BASE}/img/channel-narrow-highway.png"

_PAGE_CACHE: dict = {}  # card_id → (html_text, expires_at)
_PAGE_TTL = 300.0
_LOCK = threading.Lock()


def _esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=True)


def _read_card(card_id: str) -> Optional[dict]:
    safe = card_id.replace("/", "").replace("\\", "")
    p = CARDS_DIR / f"{safe}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _render_card_html(c: dict) -> str:
    """Render a single card as full HTML, crawler-friendly."""
    cid = c.get("id") or ""
    title = (c.get("title") or "Card")[:200]
    body = c.get("body") or ""
    body_excerpt = body[:240].replace("\n", " ").strip()
    src = c.get("source") or {}
    source_label = src.get("label") or ""
    source_ref = src.get("ref") or ""
    source_url = src.get("url") or ""
    tier = src.get("authority_tier") or ""
    stage = c.get("lifecycle_stage") or ""
    author = c.get("author") or ""
    created = c.get("created_at") or ""
    updated = c.get("updated_at") or created
    canonical = f"{SITE_BASE}/c/{cid}"
    interactive_url = f"{SITE_BASE}/card.html?id={cid}"

    witnesses = c.get("witnesses") or []
    connections = c.get("connections") or []

    # Schema.org Article JSON-LD
    citations = []
    for w in witnesses[:6]:
        citations.append({
            "@type": "CreativeWork",
            "name": (w.get("label") or w.get("ref") or "")[:200],
            **({"url": w["url"]} if w.get("url") else {}),
        })
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": body_excerpt,
        "mainEntityOfPage": canonical,
        "url": canonical,
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "author": {
            "@type": "Organization",
            "name": author or "Narrow Highway",
            "url": SITE_BASE,
        },
        "publisher": {
            "@type": "Organization",
            "name": "Narrow Highway",
            "url": SITE_BASE,
            "logo": {"@type": "ImageObject", "url": LOGO_URL},
        },
        "isPartOf": {
            "@type": "CreativeWorkSeries",
            "name": "Narrow Highway Concordance",
            "url": f"{SITE_BASE}/codex.html",
        },
    }
    if created:
        ld["datePublished"] = created
    if updated:
        ld["dateModified"] = updated
    if citations:
        ld["citation"] = citations
    ld_str = json.dumps(ld, ensure_ascii=False)

    # Render witnesses as visible list (crawler-readable)
    witness_html = ""
    if witnesses:
        witness_html = '<section class="witnesses"><h2>Witnesses (Deuteronomy 19:15)</h2><ul>'
        for w in witnesses:
            label = _esc(w.get("label") or w.get("ref") or "")
            wclass = _esc(w.get("class") or "")
            wurl = w.get("url") or ""
            if wurl:
                witness_html += f'<li><span class="wclass">{wclass}:</span> <a href="{_esc(wurl)}" rel="nofollow">{label}</a></li>'
            else:
                witness_html += f'<li><span class="wclass">{wclass}:</span> {label}</li>'
        witness_html += "</ul></section>"

    # Connections
    conn_html = ""
    if connections:
        conn_html = '<section class="connections"><h2>Connections</h2><ul>'
        for cn in connections[:50]:
            if not isinstance(cn, dict):
                continue
            tid = cn.get("to_card_id") or cn.get("from_card_id") or ""
            rel = _esc(cn.get("relationship") or "see also")
            conn_html += (
                f'<li><span class="rel">{rel}</span> → '
                f'<a href="/c/{_esc(tid)}">{_esc(tid)}</a></li>'
            )
        conn_html += "</ul></section>"

    # Source line
    source_html = ""
    if source_label or source_ref:
        source_html = '<p class="source"><strong>Source:</strong> '
        if source_url:
            source_html += f'<a href="{_esc(source_url)}" rel="nofollow">{_esc(source_label or source_ref)}</a>'
        else:
            source_html += _esc(source_label or source_ref)
        if source_ref and source_label:
            source_html += f' (<code>{_esc(source_ref)}</code>)'
        if tier:
            source_html += f' · <span class="tier">{_esc(tier)}</span>'
        source_html += "</p>"

    # Product-card render: spec table + affiliate disclosure (FTC requirement)
    # Kicks in when kind == "product"; otherwise empty.
    product_html = ""
    if c.get("kind") == "product":
        specs = (c.get("extra") or {}).get("specs") or c.get("specs") or {}
        category = (c.get("extra") or {}).get("category") or ""
        affiliate_url = (c.get("extra") or {}).get("affiliate_url") or ""
        affiliate_network = (c.get("extra") or {}).get("affiliate_network") or ""
        price_usd = (c.get("extra") or {}).get("price_usd")

        spec_rows = ""
        for k, v in specs.items():
            label = _esc(k.replace("_", " ").title())
            spec_rows += f'<tr><td>{label}</td><td>{_esc(v)}</td></tr>'

        product_html = '<section class="product">'
        if category:
            product_html += f'<p class="meta">Category: {_esc(category)}</p>'
        if spec_rows:
            product_html += '<h2>Specifications</h2>'
            product_html += '<table class="specs"><tbody>' + spec_rows + '</tbody></table>'
        if affiliate_url:
            product_html += '<div class="affiliate-cta">'
            if price_usd is not None:
                product_html += f'<p class="price">${_esc(price_usd)}</p>'
            product_html += (
                f'<a class="affiliate-btn" href="{_esc(affiliate_url)}" '
                f'rel="nofollow sponsored noopener" target="_blank">'
                f'Buy on {_esc(affiliate_network or "retailer")} →</a>'
            )
            product_html += (
                '<p class="affiliate-disclosure">'
                'As an Amazon Associate (and other affiliate networks), '
                'Narrow Highway may earn a commission from qualifying purchases. '
                'The product was vetted through our witness gate — at least two '
                'independent expert reviews before publishing. We never accept '
                'payment for product placement.'
                '</p>'
            )
            product_html += '</div>'
        product_html += '</section>'

    # Build the body HTML — preserve paragraph breaks
    body_html = ""
    for paragraph in body.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            body_html += f"<p>{_esc(paragraph)}</p>"

    # Description meta (escaped)
    meta_desc = _esc(body_excerpt or title)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — Narrow Highway</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{_esc(canonical)}">
<link rel="alternate" href="{_esc(interactive_url)}" title="Interactive view">

<meta property="og:title" content="{_esc(title)}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{_esc(canonical)}">
<meta property="og:site_name" content="Narrow Highway">
<meta property="og:image" content="{LOGO_URL}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc(title)}">
<meta name="twitter:description" content="{meta_desc}">
<meta name="twitter:image" content="{LOGO_URL}">

<link rel="icon" href="/img/favicon.ico">
<link rel="apple-touch-icon" href="/img/apple_touch_icon.png">

<script type="application/ld+json">{ld_str}</script>

<style>
  body {{ font-family: Georgia, serif; max-width: 720px; margin: 0 auto; padding: 1em 1.2em 3em; background: #fafaf6; color: #2a2a28; line-height: 1.55; }}
  nav.top {{ font-size: 0.9em; padding: 0.8em 0; }}
  nav.top a {{ color: #1a3a52; text-decoration: none; margin-right: 1em; }}
  h1 {{ font-family: Georgia, serif; font-weight: normal; color: #1a3a52; }}
  h2 {{ font-family: Georgia, serif; font-weight: normal; font-size: 1.1em; color: #806010; border-bottom: 1px solid #d4c8a5; padding-bottom: 0.3em; margin-top: 2em; }}
  .meta {{ font-family: 'Courier New', monospace; font-size: 0.8em; color: #6a5a3a; letter-spacing: 0.05em; }}
  .source {{ background: #fffef7; border-left: 3px solid #c9b48a; padding: 0.6em 1em; font-size: 0.95em; }}
  .source .tier {{ font-family: 'Courier New', monospace; font-size: 0.78em; color: #806010; letter-spacing: 0.1em; text-transform: uppercase; }}
  .witnesses ul, .connections ul {{ list-style: none; padding-left: 0; }}
  .witnesses li, .connections li {{ padding: 0.3em 0; border-bottom: 1px dotted #d4c8a5; }}
  .wclass, .rel {{ font-family: 'Courier New', monospace; font-size: 0.78em; color: #806010; letter-spacing: 0.1em; text-transform: uppercase; margin-right: 0.5em; }}
  .interactive {{ margin-top: 2em; padding: 1em; background: #fffef7; border: 1px dashed #c9b48a; border-radius: 4px; text-align: center; }}
  .interactive a {{ color: #1a3a52; font-weight: 600; }}
  code {{ background: #f0ead0; padding: 0.1em 0.4em; border-radius: 2px; font-size: 0.9em; }}

  /* Product cards */
  .product {{ margin-top: 1.5em; }}
  .product table.specs {{ width: 100%; border-collapse: collapse; margin: 0.5em 0 1em; font-size: 0.95em; }}
  .product table.specs td {{ padding: 0.4em 0.6em; border-bottom: 1px dotted #d4c8a5; }}
  .product table.specs td:first-child {{ color: #806010; font-family: 'Courier New', monospace; font-size: 0.85em; letter-spacing: 0.05em; text-transform: uppercase; width: 38%; }}
  .affiliate-cta {{ background: #fffef7; border: 1px solid #c9b48a; border-radius: 4px; padding: 1em 1.2em; margin-top: 1em; }}
  .affiliate-cta .price {{ font-size: 1.4em; font-weight: 600; color: #1a3a52; margin-bottom: 0.6em; }}
  .affiliate-btn {{ display: inline-block; background: #1a3a52; color: #f4ecd5; padding: 0.6em 1.2em; border-radius: 4px; text-decoration: none; font-weight: 600; }}
  .affiliate-btn:hover {{ background: #2a5570; }}
  .affiliate-disclosure {{ font-size: 0.78em; color: #6a5a3a; margin-top: 0.8em; line-height: 1.4; font-style: italic; }}
</style>
</head>
<body>

<nav class="top">
  <a href="/">Narrow Highway</a> ·
  <a href="/atlas.html">Atlas</a> ·
  <a href="/walk.html">Walk</a> ·
  <a href="/live.html">Live</a> ·
  <a href="/codex.html">Codex</a>
</nav>

<article>
  <h1>{_esc(title)}</h1>
  <p class="meta">
    {_esc(stage)} · {_esc(author or 'unknown')} · {_esc((created or '')[:10])}
  </p>

  {source_html}

  <section class="body">
    {body_html}
  </section>

  {product_html}

  {witness_html}

  {conn_html}

  <div class="interactive">
    <a href="{_esc(interactive_url)}">Open the interactive card view →</a>
    <br><span class="meta">paperclip · vote · add note · share</span>
  </div>
</article>

</body>
</html>
"""


def _get_cached(card_id: str) -> Optional[str]:
    e = _PAGE_CACHE.get(card_id)
    if not e:
        return None
    txt, expires = e
    if time.time() < expires:
        return txt
    return None


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/c/{card_id}")
    def card_ssr(card_id: str):
        # Sanitize
        card_id = (card_id or "").replace("/", "").replace("\\", "")[:128]
        # Hot cache
        cached = _get_cached(card_id)
        if cached is not None:
            return Response(content=cached, media_type="text/html; charset=utf-8")
        # Build (with single-flight per card_id implicit via _LOCK)
        with _LOCK:
            cached = _get_cached(card_id)
            if cached is not None:
                return Response(content=cached, media_type="text/html; charset=utf-8")
            c = _read_card(card_id)
            if c is None:
                raise HTTPException(404, f"No card {card_id}")
            html_text = _render_card_html(c)
            _PAGE_CACHE[card_id] = (html_text, time.time() + _PAGE_TTL)
        return Response(content=html_text, media_type="text/html; charset=utf-8")

    return router
