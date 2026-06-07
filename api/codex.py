"""codex.py — the Codex compiler + index API (Layer 3).

Per data/codex/STRUCTURE.md: the engine BINDS + INDEXES; it does not synthesize.
The cross-reference graph already lives in the card substrate as `connection`
cards (kind=connection, id card_c_*): each carries the specific verse_refs, the
two endpoints, the relationship kind, an explanation, the normalized book in its
bands, and a witness_status (Deut 19:15). This module INVERTS them into a
navigable **scripture cross-reference index** — book/verse -> every site across
the body that touches it, with its relationship and whether the cross-reference
itself passed the witness gate.

This is Layer 3's first surface and the on-ramp to verified connections: nothing
is generated here that wasn't already witnessed; we only make it navigable.

Faces:
  GET  /codex/index/scripture           summary: books with cross-ref counts
  GET  /codex/index/scripture/{book}    one book's cross-references
  GET  /codex/index/stats               compiler stats
  POST /codex/index/rebuild             (operator) recompile from the cards
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Request
except Exception:  # pragma: no cover
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
BIBLE_BOOKS = REPO / "content" / "codex" / "bible_books.json"
INDEX_DIR = REPO / "data" / "codex" / "index"
SCRIPTURE_INDEX = INDEX_DIR / "scripture.json"
THEME_INDEX = INDEX_DIR / "themes.json"

# Plumbing bands — the connection/sequence machinery, not themes. Dropped from
# the theme index. (Book-name and testament bands are dropped separately.)
_STRUCTURAL_BANDS = {
    "sequence", "cites", "auto_detected", "prev", "next", "proof_text",
    "see_also", "illuminates", "parallels", "contradicts", "counterexample",
    "depends_on", "consequence_of", "dictionary", "bible_dictionary",
    "nt", "ot", "old_testament", "new_testament",
}
# A theme must connect at least this many sites to be bound (Deut 19:15 — two or three).
_THEME_MIN_SITES = 3

# Source/work bands — these are the author/work index, not concepts. Tagged
# kind="source" so a reader can keep them apart from genuine themes.
_SOURCE_WORK_BANDS = {
    "easton", "augustine", "augustine_confessions", "confessions", "aurelius",
    "aurelius_meditations", "meditations", "bunyan", "pilgrim", "pilgrims_progress",
    "imitation_of_christ", "imitation_christ", "heidelberg", "westminster_shorter",
    "pirkei_avot", "clement_first", "clement", "1689_baptist", "belgic",
    "canons_of_dort", "creeds", "apostolic_fathers", "patristics", "classics",
    "didache", "barnabas", "polycarp", "polycarp_philippians", "martyrdom_polycarp",
    "ignatius", "ignatius_ephesians", "ignatius_magnesians", "ignatius_trallians",
    "ignatius_smyrnaeans", "ignatius_philadelphians", "ignatius_romans",
    "ignatius_to_polycarp", "koa", "the_line", "the_door", "the_keeping",
    "apokalypsis", "molasses", "a_kempis", "thomas_a_kempis", "boethius",
    "boethius_consolation", "consolation",
}
_FACET_BANDS = {"person", "place", "concept"}

# Enumeration bands (chapter_3, q21, article_5, section_10, verse_4 …) are
# structural pointers, not themes. Dropped.
_ENUM_RE = re.compile(
    r"^(chapter|chap|q|question|article|section|sect|verse|head|part|stanza|canon|book|line|no|num|n|page|para)?[_-]?\d+[a-z]?$")
# Verse-reference bands (matt 28:19, 1 cor 6:11, heb 11:3) belong to the
# scripture index, not the theme index. Dropped.
_VERSEREF_RE = re.compile(r"\d+\s*:\s*\d+")


def _theme_kind(band: str) -> str:
    if band in _FACET_BANDS:
        return "facet"
    if band in _SOURCE_WORK_BANDS:
        return "source"
    return "concept"

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"mtime": 0.0, "data": None}
_THEME_CACHE: Dict[str, Any] = {"mtime": 0.0, "data": None}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _book_slugs() -> Dict[str, str]:
    """slug -> canonical book name, for the 66 books. Slug matches the band
    form the connection cards already carry (e.g. '1_timothy')."""
    out: Dict[str, str] = {}
    j = _read(BIBLE_BOOKS) or {}
    for b in (j.get("books") or []):
        name = b.get("book")
        if name:
            out[name.lower().replace(" ", "_")] = name
    return out


# ── Compiler ────────────────────────────────────────────────────────────────
def build_scripture_index() -> Dict[str, Any]:
    """Walk the connection cards and invert them into a per-book cross-reference
    index. Writes data/codex/index/scripture.json and returns it."""
    books = _book_slugs()
    index: Dict[str, List[dict]] = {}
    n_conn = 0
    n_witnessed = 0
    n_verse = 0
    rels: Dict[str, int] = {}
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob("card_c_*.json"):
            c = _read(f)
            if not c or c.get("kind") != "connection":
                continue
            extra = c.get("extra") or {}
            src = c.get("source") or {}
            verse_refs = extra.get("verse_refs") or ([src["ref"]] if src.get("ref") else [])
            rel = (extra.get("relationship_kind")
                   or (c.get("bands") or ["cites"])[0] or "cites")
            bands = c.get("bands") or []
            book_slugs = [b for b in bands if b in books]
            if not book_slugs:  # fallback: try to read a book off a verse_ref
                for vr in verse_refs:
                    s = re.sub(r"[^a-z0-9 ]", "", (vr or "").lower())
                    for slug, _name in books.items():
                        if s.startswith(slug.replace("_", " ")):
                            book_slugs.append(slug)
                            break
            if not book_slugs:
                continue
            wit = c.get("witness_status")
            entry = {
                "by": c.get("title"),
                "relationship": rel,
                "verse_refs": verse_refs,
                "explanation": (extra.get("explanation") or c.get("body") or "")[:300],
                "witness_status": wit,
                "tier": src.get("authority_tier"),
                "card_id": c.get("id"),
            }
            n_conn += 1
            if wit == "passed":
                n_witnessed += 1
            if verse_refs:
                n_verse += 1
            rels[rel] = rels.get(rel, 0) + 1
            for bs in set(book_slugs):
                index.setdefault(books[bs], []).append(entry)

    # Order books canonically (bible_books.json order); within a book surface the
    # verse-level (verse_refs present), witnessed cross-references first.
    canon_order = list(books.values())
    ordered = {
        b: sorted(index[b], key=lambda e: (
            not e.get("verse_refs"),                 # verse-level first
            e.get("witness_status") != "passed",     # witnessed first
            e.get("relationship") or ""))
        for b in canon_order if b in index
    }
    payload = {
        "generated": _now(),
        "stats": {
            "cross_references": n_conn,
            "verse_level": n_verse,
            "witnessed": n_witnessed,
            "books_indexed": len(ordered),
            "by_relationship": dict(sorted(rels.items(), key=lambda x: -x[1])),
        },
        "books": ordered,
    }
    with _LOCK:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SCRIPTURE_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(SCRIPTURE_INDEX)
        _CACHE["data"] = payload
        _CACHE["mtime"] = SCRIPTURE_INDEX.stat().st_mtime
    return payload


def load_index() -> Dict[str, Any]:
    """Return the compiled scripture index, mtime-cached. Empty if not built."""
    if not SCRIPTURE_INDEX.exists():
        return {"generated": None, "stats": {}, "books": {}}
    try:
        mt = SCRIPTURE_INDEX.stat().st_mtime
    except OSError:
        return {"generated": None, "stats": {}, "books": {}}
    if _CACHE["data"] is not None and mt <= _CACHE["mtime"]:
        return _CACHE["data"]
    with _LOCK:
        data = _read(SCRIPTURE_INDEX) or {"generated": None, "stats": {}, "books": {}}
        _CACHE["data"] = data
        _CACHE["mtime"] = mt
        return data


# ── Theme index ───────────────────────────────────────────────────────────────
def build_theme_index() -> Dict[str, Any]:
    """Invert the conceptual card bands into a theme index — theme -> every site
    across the body that carries it. Plumbing bands (sequence/cites/prev/next...)
    and book/testament bands are dropped; a theme is bound only if it connects at
    least _THEME_MIN_SITES sites. Surfaces existing tags; nothing is generated."""
    books = set(_book_slugs().keys())  # slug form, e.g. '1_timothy'
    themes: Dict[str, dict] = {}
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob("*.json"):
            c = _read(f)
            if not c:
                continue
            shelf = c.get("shelf") or ""
            tier = (c.get("source") or {}).get("authority_tier") or ""
            entry = {"id": c.get("id"), "title": c.get("title") or "", "shelf": shelf, "tier": tier}
            for b in (c.get("bands") or []):
                low = str(b).strip().lower()
                if (not low or low in _STRUCTURAL_BANDS or low in books
                        or _ENUM_RE.match(low) or _VERSEREF_RE.search(low)):
                    continue
                t = themes.setdefault(low, {"label": str(b).strip(), "cards": [], "tiers": set()})
                t["cards"].append(entry)
                if tier:
                    t["tiers"].add(tier)
    out: Dict[str, dict] = {}
    for k, t in themes.items():
        if len(t["cards"]) < _THEME_MIN_SITES:
            continue
        out[k] = {
            "label": t["label"],
            "kind": _theme_kind(k),
            "count": len(t["cards"]),
            "tiers": sorted(t["tiers"]),
            "span": len(t["tiers"]),            # distinct authority tiers = cross-tradition reach
            "cards": t["cards"][:120],
        }
    # concepts first, then by cross-tradition span, then frequency
    _kind_rank = {"concept": 0, "facet": 1, "source": 2}
    ordered = dict(sorted(out.items(), key=lambda kv: (
        _kind_rank.get(kv[1]["kind"], 0), -kv[1]["span"], -kv[1]["count"], kv[0])))
    payload = {
        "generated": _now(),
        "stats": {
            "themes": len(ordered),
            "concepts": sum(1 for v in ordered.values() if v["kind"] == "concept"),
            "tagged_sites": sum(v["count"] for v in ordered.values()),
            "cross_tradition": sum(1 for v in ordered.values() if v["span"] >= 2),
            "min_sites": _THEME_MIN_SITES,
        },
        "themes": ordered,
    }
    with _LOCK:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        tmp = THEME_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(THEME_INDEX)
        _THEME_CACHE["data"] = payload
        _THEME_CACHE["mtime"] = THEME_INDEX.stat().st_mtime
    return payload


def load_themes() -> Dict[str, Any]:
    if not THEME_INDEX.exists():
        return {"generated": None, "stats": {}, "themes": {}}
    try:
        mt = THEME_INDEX.stat().st_mtime
    except OSError:
        return {"generated": None, "stats": {}, "themes": {}}
    if _THEME_CACHE["data"] is not None and mt <= _THEME_CACHE["mtime"]:
        return _THEME_CACHE["data"]
    with _LOCK:
        data = _read(THEME_INDEX) or {"generated": None, "stats": {}, "themes": {}}
        _THEME_CACHE["data"] = data
        _THEME_CACHE["mtime"] = mt
        return data


def _operator_ok(request) -> bool:
    key = os.environ.get("NH_OPERATOR_KEY")
    if not key:
        return True
    try:
        return request.headers.get("X-Operator-Key") == key
    except Exception:
        return False


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/codex/index/scripture", tags=["codex"])
    def scripture_summary():
        idx = load_index()
        books = idx.get("books") or {}
        return {
            "generated": idx.get("generated"),
            "stats": idx.get("stats", {}),
            "books": [{"book": b, "cross_references": len(v)} for b, v in books.items()],
            "note": "Cross-references inverted from witnessed connection cards. "
                    "GET /codex/index/scripture/{book} for one book's sites.",
        }

    @router.get("/codex/index/scripture/{book}", tags=["codex"])
    def scripture_book(book: str):
        idx = load_index()
        books = idx.get("books") or {}
        # case/space-insensitive match
        want = book.strip().lower().replace("_", " ")
        for b, refs in books.items():
            if b.lower() == want:
                return {"book": b, "cross_references": refs, "count": len(refs)}
        raise HTTPException(404, f"No cross-references indexed for '{book}'. "
                                 f"Try one of /codex/index/scripture.")

    @router.get("/codex/index/themes", tags=["codex"])
    def themes_summary():
        idx = load_themes()
        themes = idx.get("themes") or {}
        return {
            "generated": idx.get("generated"),
            "stats": idx.get("stats", {}),
            "themes": [
                {"theme": k, "label": v.get("label", k), "kind": v.get("kind", "concept"),
                 "count": v.get("count", 0), "span": v.get("span", 0), "tiers": v.get("tiers", [])}
                for k, v in themes.items()
            ],
            "note": "Concept tags inverted from card bands (plumbing/book tags dropped; "
                    "min 3 sites; span = distinct authority tiers). A coarse first index — "
                    "it surfaces existing tags, it does not synthesize. GET /codex/index/themes/{theme}.",
        }

    @router.get("/codex/index/themes/{theme}", tags=["codex"])
    def theme_sites(theme: str):
        idx = load_themes()
        themes = idx.get("themes") or {}
        want = theme.strip().lower()
        if want in themes:
            t = themes[want]
            return {"theme": want, "label": t.get("label", want), "kind": t.get("kind", "concept"),
                    "count": t.get("count", 0), "span": t.get("span", 0),
                    "tiers": t.get("tiers", []), "cards": t.get("cards", [])}
        raise HTTPException(404, f"No theme '{theme}' indexed. Try one of /codex/index/themes.")

    @router.get("/codex/index/stats", tags=["codex"])
    def stats():
        return {
            "scripture": load_index().get("stats", {}),
            "themes": load_themes().get("stats", {}),
        }

    @router.post("/codex/index/rebuild", tags=["codex"])
    def rebuild(request: Request):
        if not _operator_ok(request):
            raise HTTPException(403, "Operator only.")
        s = build_scripture_index()
        t = build_theme_index()
        return {"ok": True, "scripture": s.get("stats", {}), "themes": t.get("stats", {})}

    return router


if __name__ == "__main__":  # python -m api.codex  -> build all indexes
    s = build_scripture_index()
    t = build_theme_index()
    print(json.dumps({"scripture": s.get("stats", {}), "themes": t.get("stats", {})}, indent=2))
