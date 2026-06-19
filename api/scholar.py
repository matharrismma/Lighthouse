"""scholar.py — scholarly grounding (the clean road to free knowledge).

Connect the engine to the OPEN scholarly ecosystem so a claim can be grounded in
the literature with an attributed, re-checkable citation AND the legitimately
free copy:

  - OpenAlex   (https://openalex.org) — ~250M works, CC0. Metadata, citation
                counts, the open-access location, and the abstract. Primary.
  - Crossref   (https://crossref.org) — the DOI registry. Metadata fallback when
                a DOI is not yet in OpenAlex.
  - Unpaywall  (https://unpaywall.org) — given a DOI, the lawful open-access copy
                (author manuscript, preprint, repository). The honest answer to
                "I want the paper for free."

WHY THIS, NOT SCI-HUB: the engine's whole value is the trustworthy seal — a
receipt that points at a real, lawful, re-checkable source. The same discipline
that refuses to launder a claim refuses to launder provenance. So we surface the
LEGAL open copy when one exists, and say plainly when one does not — we never
link a copy we have no right to redistribute. Same destination (knowledge
freed), the road that stays clean.

Sovereign by construction: stdlib urllib only — no requests, no SDK, no new
dependency on the host. Outbound only, to public open APIs (same pattern as the
ECB-FX / World Bank / USDA grounding already wired). Never raises; on any network
or parse failure it returns {"ok": False, "error": ...} so callers degrade.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

# Politeness: the open APIs ask for a contact so they can reach us about abuse
# and put us in the faster "polite pool". Not a secret — overridable by env.
MAILTO = os.environ.get("NH_SCHOLAR_MAILTO", "team@narrowhighway.com").strip()
_UA = f"NarrowHighway-Concordance/1.0 (mailto:{MAILTO}; +https://narrowhighway.com)"
_TIMEOUT = float(os.environ.get("NH_SCHOLAR_TIMEOUT", "8"))

_OPENALEX = "https://api.openalex.org"
_CROSSREF = "https://api.crossref.org"
_UNPAYWALL = "https://api.unpaywall.org/v2"

# Trim the OpenAlex payload to what we actually surface.
_SELECT = ("id,doi,title,publication_year,authorships,primary_location,"
           "open_access,best_oa_location,cited_by_count,abstract_inverted_index,type")

# Tiny in-memory cache so repeated lookups don't hammer the APIs.
_CACHE: Dict[str, Any] = {}
_CACHE_MAX = 256


def _norm_doi(doi: str) -> str:
    """Strip any URL/scheme prefix down to the bare 10.xxxx/yyyy DOI."""
    d = (doi or "").strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:", "", d, flags=re.I)
    return d.strip().strip("/")


def _get(url: str) -> Optional[Any]:
    """GET JSON with the polite UA. Returns parsed JSON or None on any failure."""
    if url in _CACHE:
        return _CACHE[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        if len(_CACHE) < _CACHE_MAX:
            _CACHE[url] = data
        return data
    except Exception:
        return None


def _abstract(work: Dict[str, Any]) -> str:
    """Reconstruct the abstract from OpenAlex's inverted index (it is the
    authors' own summary, distributed openly by OpenAlex). Truncated."""
    idx = work.get("abstract_inverted_index")
    if not isinstance(idx, dict) or not idx:
        return ""
    pos: Dict[int, str] = {}
    for word, positions in idx.items():
        if isinstance(positions, list):
            for p in positions:
                if isinstance(p, int):
                    pos[p] = word
    if not pos:
        return ""
    return " ".join(pos[i] for i in sorted(pos))[:1200]


def _oa_url(work: Dict[str, Any]) -> Optional[str]:
    """The legal open-access URL for a work, or None if there isn't one."""
    best = work.get("best_oa_location") or {}
    for k in ("pdf_url", "landing_page_url"):
        if best.get(k):
            return best[k]
    oa = work.get("open_access") or {}
    return oa.get("oa_url") or None


def _format_work(w: Dict[str, Any]) -> Dict[str, Any]:
    authors = []
    for a in (w.get("authorships") or [])[:12]:
        nm = (a.get("author") or {}).get("display_name")
        if nm:
            authors.append(nm)
    venue = None
    ploc = w.get("primary_location") or {}
    src = ploc.get("source") or {}
    if src.get("display_name"):
        venue = src["display_name"]
    doi = _norm_doi(w.get("doi") or "")
    oa = w.get("open_access") or {}
    return {
        "title": w.get("title") or "(untitled)",
        "authors": authors,
        "year": w.get("publication_year"),
        "venue": venue,
        "type": w.get("type"),
        "doi": doi or None,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "openalex": w.get("id"),
        "cited_by_count": w.get("cited_by_count"),
        "is_open_access": bool(oa.get("is_oa")),
        "open_access_url": _oa_url(w),  # the LEGAL free copy, or None
        "abstract": _abstract(w),
        "source": "openalex",
    }


def search(query: str, rows: int = 5) -> Dict[str, Any]:
    """Search the open scholarly graph (OpenAlex) for a topic or phrase."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "empty query"}
    rows = max(1, min(int(rows or 5), 25))
    url = (f"{_OPENALEX}/works?search={urllib.parse.quote(q)}"
           f"&per_page={rows}&select={_SELECT}&mailto={urllib.parse.quote(MAILTO)}")
    data = _get(url)
    if not data or "results" not in data:
        return {"ok": False, "error": "openalex unreachable or no results", "query": q}
    works = [_format_work(w) for w in data.get("results", [])]
    return {
        "ok": True,
        "query": q,
        "count": len(works),
        "total_available": (data.get("meta") or {}).get("count"),
        "results": works,
        "note": ("Grounded in OpenAlex (CC0). open_access_url is the LAWFUL free "
                 "copy where one exists; null means no legal open copy was found — "
                 "not that one was hidden."),
    }


def _crossref_meta(doi: str) -> Optional[Dict[str, Any]]:
    """Metadata fallback from Crossref when OpenAlex doesn't have the DOI."""
    url = f"{_CROSSREF}/works/{urllib.parse.quote(doi)}?mailto={urllib.parse.quote(MAILTO)}"
    data = _get(url)
    msg = (data or {}).get("message")
    if not msg:
        return None
    authors = []
    for a in (msg.get("author") or [])[:12]:
        nm = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if nm:
            authors.append(nm)
    title = (msg.get("title") or ["(untitled)"])
    venue = (msg.get("container-title") or [None])
    year = None
    try:
        year = (msg.get("issued") or {}).get("date-parts", [[None]])[0][0]
    except Exception:
        pass
    return {
        "title": title[0] if title else "(untitled)",
        "authors": authors,
        "year": year,
        "venue": venue[0] if venue else None,
        "type": msg.get("type"),
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}",
        "cited_by_count": msg.get("is-referenced-by-count"),
        "source": "crossref",
    }


def _unpaywall_oa(doi: str) -> Optional[str]:
    """The lawful open-access URL for a DOI per Unpaywall, or None."""
    if not MAILTO:
        return None
    url = f"{_UNPAYWALL}/{urllib.parse.quote(doi)}?email={urllib.parse.quote(MAILTO)}"
    data = _get(url)
    if not data:
        return None
    best = data.get("best_oa_location") or {}
    return best.get("url_for_pdf") or best.get("url") or None


def by_doi(doi: str) -> Dict[str, Any]:
    """Resolve one DOI to attributed metadata + the lawful open-access copy.

    OpenAlex first (metadata + OA + abstract + citations); Crossref as metadata
    fallback; Unpaywall as an OA fallback. Always returns the DOI link so the
    citation is re-checkable even when no open copy exists."""
    d = _norm_doi(doi)
    if not re.match(r"^10\.\d{4,9}/\S+$", d):
        return {"ok": False, "error": "not a valid DOI (expected 10.xxxx/yyyy)", "doi": d}
    work = _get(f"{_OPENALEX}/works/https://doi.org/{urllib.parse.quote(d)}"
                f"?select={_SELECT}&mailto={urllib.parse.quote(MAILTO)}")
    if isinstance(work, dict) and work.get("id"):
        rec = _format_work(work)
        if not rec.get("open_access_url"):
            uw = _unpaywall_oa(d)
            if uw:
                rec["open_access_url"] = uw
                rec["is_open_access"] = True
        return {"ok": True, "work": rec}
    # OpenAlex miss → Crossref metadata + Unpaywall OA
    meta = _crossref_meta(d)
    if meta:
        oa = _unpaywall_oa(d)
        meta["is_open_access"] = bool(oa)
        meta["open_access_url"] = oa
        meta["abstract"] = ""
        return {"ok": True, "work": meta}
    return {"ok": False, "error": "DOI not found in OpenAlex or Crossref", "doi": d}


def by_title(title: str) -> Dict[str, Any]:
    """Find the closest work to a title string (OpenAlex title search)."""
    t = (title or "").strip()
    if not t:
        return {"ok": False, "error": "empty title"}
    url = (f"{_OPENALEX}/works?filter=title.search:{urllib.parse.quote(t)}"
           f"&per_page=1&select={_SELECT}&mailto={urllib.parse.quote(MAILTO)}")
    data = _get(url)
    results = (data or {}).get("results") or []
    if not results:
        return {"ok": False, "error": "no match", "title": t}
    return {"ok": True, "work": _format_work(results[0])}


def lookup(*, doi: str = "", title: str = "", query: str = "", rows: int = 5) -> Dict[str, Any]:
    """One dispatcher used by the REST endpoint and the MCP tool. Prefers the
    most specific signal: DOI > title > free-text query."""
    if doi:
        return by_doi(doi)
    if title:
        return by_title(title)
    if query:
        return search(query, rows=rows)
    return {"ok": False, "error": "provide one of: doi, title, query"}
