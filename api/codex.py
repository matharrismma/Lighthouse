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

import collections
import hashlib
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
CONNECTIONS_INDEX = INDEX_DIR / "connections.json"
CARDS_DEV_INDEX = INDEX_DIR / "cards_dev.json"
GRID_CONNECTIONS = REPO / "data" / "grid_connections.jsonl"
ALMANAC_ENTRIES = REPO / "data" / "almanac" / "entries.jsonl"
# Engine-generated, deterministically-verified connections (oracle-free, reversible —
# produced by tools/grow_verified.py; separate from the curated almanac).
GENERATED_VERIFIED = REPO / "data" / "almanac" / "generated_verified.jsonl"
COMPILED_DIR = REPO / "data" / "codex" / "compiled"
LATEST_ARTIFACT = COMPILED_DIR / "codex_latest.json"

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
_CONN_CACHE: Dict[str, Any] = {"mtime": 0.0, "data": None}
_CARDSDEV_CACHE: Dict[str, Any] = {"mtime": 0.0, "data": None}


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


# ── Connection graph (Phase 1: ledger + smoothing + witness tier) ───────────────
def _source_label(by: str) -> str:
    """The citing source from a cross-ref title like 'WSC Q40 ↔ Romans'."""
    if not by:
        return ""
    for sep in (" ↔ ", " <-> ", " cites ", ":"):
        if sep in by:
            return by.split(sep, 1)[0].strip()
    return by.strip()


def _verified_structural() -> List[dict]:
    """Phase 2 — the moat. An almanac entry confirmed by 2+ independent domain
    verifiers is a VERIFIED cross-domain connection: one claim, proven true by
    several deterministic verifiers at once, each with its computation trail.
    Not generated, not resonance — verified, and traceable.

    (Phase-2 pilot finding 2026-06-06: dispatching the free-text grid samples
    yielded 0% — the prose doesn't fit the structured rules. The almanac, whose
    claims are already four-gate verified, is the sound substrate instead.)"""
    out: List[dict] = []
    seen_ids = set()
    for path in (ALMANAC_ENTRIES, GENERATED_VERIFIED):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                dr = (e.get("pre_run") or {}).get("domain_results") or []
                confirmed = [d for d in dr if d.get("verdict") == "CONFIRMED" and d.get("domain")]
                doms = sorted({d["domain"] for d in confirmed})
                if len(doms) < 2:  # a cross-domain connection needs 2+ verifiers
                    continue
                eid = e.get("id")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                out.append({
                    "id": eid,
                    "title": e.get("title") or eid,
                    "domains": doms,
                    "domain_count": len(doms),
                    "axes": e.get("axes") or [],
                    "verdict": e.get("verdict"),
                    "situation": (e.get("situation") or "")[:320],
                    "tier": "verified-structural",
                    "generated": bool(e.get("generated")),
                    "trail": [{"domain": d.get("domain"), "verdict": d.get("verdict"),
                               "detail": (d.get("detail") or "")[:200]}
                              for d in confirmed],
                })
    out.sort(key=lambda x: (-x["domain_count"], x["domains"]))
    return out


def build_connection_index() -> Dict[str, Any]:
    """Unify the connection candidates into one tiered, scored ledger.

    VERIFIED (witness tier): co-citation hubs from the scripture index — a verse
    that two or more sources both cite is a *witnessed* connection between them.
    Verified, not generated: the shared citation already passed the Deut 19:15 gate.

    CANDIDATE (resonance): the Connector's grid edges (data/grid_connections.jsonl)
    smoothed — 13,953 raw edges deduped into ranked domain-pairs by shared-axis
    count and co-occurrence. Honest label: resonance, not verified.
    """
    # ── Witness tier: co-citation hubs from the scripture index ──
    scr = load_index()
    by_verse: Dict[str, Dict[str, Any]] = {}
    for book, refs in (scr.get("books") or {}).items():
        for e in refs:
            if e.get("witness_status") != "passed":
                continue
            src = _source_label(e.get("by") or "")
            for vr in (e.get("verse_refs") or []):
                key = re.sub(r"\s+", " ", str(vr).strip())
                if not key:
                    continue
                slot = by_verse.setdefault(key, {"sources": {}, "book": book})
                if src:
                    slot["sources"][src] = e.get("tier") or ""
    hubs = []
    for verse, slot in by_verse.items():
        srcs = sorted(slot["sources"].keys())
        if len(srcs) >= 2:  # a connection needs two or three
            hubs.append({"verse": verse, "book": slot["book"], "sources": srcs,
                         "source_count": len(srcs), "tier": "witnessed",
                         "witness_status": "passed"})
    hubs.sort(key=lambda h: -h["source_count"])

    # ── Candidate tier: smooth the grid edges into ranked domain pairs ──
    pairs: Dict[tuple, Dict[str, Any]] = {}
    raw_edges = 0
    if GRID_CONNECTIONS.exists():
        with GRID_CONNECTIONS.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                a, b = r.get("domain_a"), r.get("domain_b")
                if not a or not b or a == b:
                    continue
                raw_edges += 1
                key = tuple(sorted((a, b)))
                p = pairs.setdefault(key, {"domains": list(key), "axes": set(),
                                           "edges": 0, "max_axis": 0, "sample": None})
                p["axes"].update(r.get("shared_axes") or [])
                p["edges"] += 1
                p["max_axis"] = max(p["max_axis"], int(r.get("axis_count") or 0))
                if p["sample"] is None and r.get("sample_a") and r.get("sample_b"):
                    p["sample"] = {"a": str(r["sample_a"])[:240], "b": str(r["sample_b"])[:240]}
    candidates = []
    for p in pairs.values():
        axes = sorted(p["axes"])
        candidates.append({
            "domains": p["domains"],
            "shared_axes": axes,
            "axis_count": len(axes),
            "edge_count": p["edges"],
            "score": len(axes) * 10 + min(p["edges"], 50),  # deterministic
            "tier": "candidate",
            "note": "resonance (shared axes) — NOT a verified connection",
            "sample": p["sample"],
        })
    candidates.sort(key=lambda c: (-c["score"], -c["axis_count"], c["domains"]))

    # ── Verified-structural tier (Phase 2): almanac claims confirmed by 2+ verifiers ──
    vstruct = _verified_structural()

    payload = {
        "generated": _now(),
        "stats": {
            "verified_structural": len(vstruct),
            "verified_structural_pairs": len({tuple(c["domains"]) for c in vstruct}),
            "verified_hubs": len(hubs),
            "verified_sources": sum(h["source_count"] for h in hubs),
            "candidate_pairs": len(candidates),
            "raw_grid_edges": raw_edges,
            "domains": len({d for c in candidates for d in c["domains"]}),
        },
        "verified_structural": vstruct,
        "verified": hubs,
        "candidates": candidates,
    }
    with _LOCK:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONNECTIONS_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(CONNECTIONS_INDEX)
        _CONN_CACHE["data"] = payload
        _CONN_CACHE["mtime"] = CONNECTIONS_INDEX.stat().st_mtime
    return payload


def load_connections() -> Dict[str, Any]:
    if not CONNECTIONS_INDEX.exists():
        return {"generated": None, "stats": {}, "verified_structural": [], "verified": [], "candidates": []}
    try:
        mt = CONNECTIONS_INDEX.stat().st_mtime
    except OSError:
        return {"generated": None, "stats": {}, "verified_structural": [], "verified": [], "candidates": []}
    if _CONN_CACHE["data"] is not None and mt <= _CONN_CACHE["mtime"]:
        return _CONN_CACHE["data"]
    with _LOCK:
        data = _read(CONNECTIONS_INDEX) or {"generated": None, "stats": {}, "verified": [], "candidates": []}
        _CONN_CACHE["data"] = data
        _CONN_CACHE["mtime"] = mt
        return data


# ── Card development index (the method: see every card by how finished it is) ───
# Content cards (note/walk) flow through a derived lifecycle. `lifecycle_stage` in
# the data is ~100% "public" (unused as a pipeline), so we DERIVE the real stage
# from completeness: a card isn't "developed" until it has a substantive body AND
# 2+ connections AND a passed witness.
_CONTENT_KINDS = {"note", "walk"}
_BODY_FULL = 300      # chars — a substantive body
_CONN_DONE = 2        # connections — "established by two or three"


def _card_stage(body_len: int, conn: int, witnessed: bool) -> str:
    if body_len >= _BODY_FULL and conn >= _CONN_DONE and witnessed:
        return "developed"      # done
    if conn >= _CONN_DONE:
        return "connected"      # linked, but body thin / unwitnessed
    if body_len >= _BODY_FULL:
        return "drafted"        # has a body, under-connected
    return "seed"               # stub + under-connected — rawest


def build_cards_dev_index() -> Dict[str, Any]:
    """Survey content cards and stage them by development. Connection cards (edges)
    are counted separately. Writes data/codex/index/cards_dev.json."""
    stages: "collections.Counter" = collections.Counter()
    by_shelf: Dict[str, "collections.Counter"] = collections.defaultdict(collections.Counter)
    lists: Dict[str, list] = {"seed": [], "drafted": [], "connected": []}  # needs-work queues
    CAP = 500
    edges = content = 0
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob("*.json"):
            c = _read(f)
            if not c:
                continue
            if c.get("kind") not in _CONTENT_KINDS:
                edges += 1
                continue
            content += 1
            body_len = len(c.get("body") or "")
            conn = len(c.get("connections") or [])
            witnessed = c.get("witness_status") == "passed"
            st = _card_stage(body_len, conn, witnessed)
            shelf = c.get("shelf") or "?"
            stages[st] += 1
            by_shelf[shelf][st] += 1
            if st in lists and len(lists[st]) < CAP:
                missing = []
                if body_len < _BODY_FULL:
                    missing.append("body")
                if conn < _CONN_DONE:
                    missing.append("connections")
                lists[st].append({"id": c.get("id"), "title": (c.get("title") or "")[:90],
                                  "shelf": shelf, "body_len": body_len, "conn": conn,
                                  "missing": missing})
    developed = stages.get("developed", 0)
    payload = {
        "generated": _now(),
        "stats": {
            "content_cards": content,
            "edges": edges,
            "developed": developed,
            "needs_work": content - developed,
            "pct_developed": round(100 * developed / content, 1) if content else 0,
            "stages": {k: stages.get(k, 0) for k in ("seed", "drafted", "connected", "developed")},
            "by_shelf": {k: dict(v) for k, v in sorted(by_shelf.items())},
        },
        "queues": lists,
    }
    with _LOCK:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CARDS_DEV_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(CARDS_DEV_INDEX)
        _CARDSDEV_CACHE["data"] = payload
        _CARDSDEV_CACHE["mtime"] = CARDS_DEV_INDEX.stat().st_mtime
    return payload


def load_cards_dev() -> Dict[str, Any]:
    if not CARDS_DEV_INDEX.exists():
        return {"generated": None, "stats": {}, "queues": {}}
    try:
        mt = CARDS_DEV_INDEX.stat().st_mtime
    except OSError:
        return {"generated": None, "stats": {}, "queues": {}}
    if _CARDSDEV_CACHE["data"] is not None and mt <= _CARDSDEV_CACHE["mtime"]:
        return _CARDSDEV_CACHE["data"]
    with _LOCK:
        data = _read(CARDS_DEV_INDEX) or {"generated": None, "stats": {}, "queues": {}}
        _CARDSDEV_CACHE["data"] = data
        _CARDSDEV_CACHE["mtime"] = mt
        return data


# ── Signed artifact (Face 2) ────────────────────────────────────────────────────
def _sha256_file(p: Path) -> Optional[str]:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def _body_fingerprint() -> Dict[str, Any]:
    """Walk the body once: counts by shelf and authority tier, and a cheap,
    order-independent fingerprint over each card's (id, source_hash)."""
    import collections
    shelves: "collections.Counter" = collections.Counter()
    tiers: "collections.Counter" = collections.Counter()
    total = 0
    pairs: List[str] = []
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob("*.json"):
            c = _read(f)
            if not c:
                continue
            total += 1
            shelves[c.get("shelf") or "?"] += 1
            tiers[(c.get("source") or {}).get("authority_tier") or "?"] += 1
            pairs.append((c.get("id") or f.stem) + "\t" + (c.get("source_hash") or ""))
    pairs.sort()
    fp = hashlib.sha256()
    for line in pairs:
        fp.update(line.encode("utf-8"))
        fp.update(b"\n")
    return {
        "cards_total": total,
        "by_shelf": dict(shelves.most_common()),
        "by_authority_tier": dict(tiers.most_common()),
        "body_hash_sha256": fp.hexdigest(),
    }


def build_codex_artifact() -> Dict[str, Any]:
    """Seal the Codex: assemble a manifest (body fingerprint + index hashes +
    index stats), sign it with the engine's instance identity, and write it to
    data/codex/compiled/. Certifies 'the chosen body, walked and indexed by this
    engine, as of this date.' The private key never leaves the engine node."""
    body = _body_fingerprint()
    scr, thm, cn = load_index(), load_themes(), load_connections()
    manifest = {
        "kind": "codex_artifact",
        "version": "v1",
        "sealed_at": _now(),
        "serves": "Jesus Christ",
        "statement": ("This certifies the Codex — the chosen body (Scripture, the "
                      "named fathers, the confessions, and the operator's works), walked "
                      "and indexed by the engine — as of sealed_at. The body is "
                      "fingerprinted by body_hash_sha256; each index by its sha256. The "
                      "engine binds and indexes; it does not synthesize. Conduit, not source."),
        "body": body,
        "indexes": {
            "scripture": {"stats": scr.get("stats", {}), "sha256": _sha256_file(SCRIPTURE_INDEX),
                          "generated": scr.get("generated")},
            "themes": {"stats": thm.get("stats", {}), "sha256": _sha256_file(THEME_INDEX),
                       "generated": thm.get("generated")},
            "connections": {"stats": cn.get("stats", {}), "sha256": _sha256_file(CONNECTIONS_INDEX),
                            "generated": cn.get("generated")},
        },
    }
    from concordance_engine.instance_identity import sign_dict
    signed = sign_dict(manifest)  # adds _sig, _instance_pubkey, _instance_id
    with _LOCK:
        COMPILED_DIR.mkdir(parents=True, exist_ok=True)
        date = (signed.get("sealed_at") or "")[:10] or "undated"
        dated = COMPILED_DIR / f"codex_{date}.json"
        for path in (dated, LATEST_ARTIFACT):
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(signed, indent=2), encoding="utf-8")
            tmp.replace(path)
    return signed


def load_latest_artifact() -> Optional[dict]:
    if not LATEST_ARTIFACT.exists():
        return None
    return _read(LATEST_ARTIFACT)


def verify_codex_artifact() -> Dict[str, Any]:
    """Verify the latest sealed artifact: (1) the Ed25519 signature, and (2) that
    the current index files still hash to what was sealed (drift detection)."""
    art = load_latest_artifact()
    if not art:
        return {"sealed": False, "note": "No artifact sealed yet — POST /codex/seal."}
    from concordance_engine.instance_identity import verify_dict
    ok, detail = verify_dict(art)
    # drift: re-hash the live index files against the sealed hashes
    drift = []
    for name, path in (("scripture", SCRIPTURE_INDEX), ("themes", THEME_INDEX), ("connections", CONNECTIONS_INDEX)):
        sealed = (art.get("indexes", {}).get(name, {}) or {}).get("sha256")
        live = _sha256_file(path)
        if sealed and live and sealed != live:
            drift.append(name)
    return {
        "sealed": True,
        "signature_valid": ok,
        "detail": detail,
        "instance_id": art.get("_instance_id"),
        "sealed_at": art.get("sealed_at"),
        "body_hash_sha256": art.get("body", {}).get("body_hash_sha256"),
        "indexes_unchanged_since_seal": not drift,
        "drifted_indexes": drift,
    }


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

    @router.get("/codex/connections", tags=["codex"])
    def connections_summary():
        idx = load_connections()
        return {
            "generated": idx.get("generated"),
            "stats": idx.get("stats", {}),
            "verified_structural": (idx.get("verified_structural") or [])[:200],
            "verified": (idx.get("verified") or [])[:200],
            "candidates": (idx.get("candidates") or [])[:200],
            "note": "VERIFIED-STRUCTURAL = one claim confirmed by 2+ independent domain "
                    "verifiers (cross-domain, with computation trail). VERIFIED = witnessed "
                    "co-citation hubs (2+ sources share a witnessed verse). CANDIDATE = grid "
                    "resonances (shared axes), NOT verified. The trail is the trust.",
        }

    @router.get("/codex/connections/domain/{domain}", tags=["codex"])
    def connections_for_domain(domain: str):
        idx = load_connections()
        want = domain.strip().lower()
        hits = [c for c in (idx.get("candidates") or [])
                if want in [d.lower() for d in c.get("domains", [])]]
        if not hits:
            raise HTTPException(404, f"No candidate connections for domain '{domain}'.")
        return {"domain": want, "candidates": hits, "count": len(hits),
                "note": "Resonances (shared axes) — candidate, not verified."}

    @router.get("/codex/cards/dev", tags=["codex"])
    def cards_dev():
        idx = load_cards_dev()
        return {
            "generated": idx.get("generated"),
            "stats": idx.get("stats", {}),
            "queues": idx.get("queues", {}),
            "note": "Content cards by DERIVED development stage. developed = body >= 300 "
                    "chars AND 2+ connections AND witnessed; seed/drafted/connected need work.",
        }

    @router.get("/codex/index/stats", tags=["codex"])
    def stats():
        return {
            "scripture": load_index().get("stats", {}),
            "themes": load_themes().get("stats", {}),
            "connections": load_connections().get("stats", {}),
            "cards_dev": load_cards_dev().get("stats", {}),
        }

    @router.post("/codex/index/rebuild", tags=["codex"])
    def rebuild(request: Request):
        if not _operator_ok(request):
            raise HTTPException(403, "Operator only.")
        s = build_scripture_index()
        t = build_theme_index()
        cn = build_connection_index()
        cd = build_cards_dev_index()
        return {"ok": True, "scripture": s.get("stats", {}), "themes": t.get("stats", {}),
                "connections": cn.get("stats", {}), "cards_dev": cd.get("stats", {})}

    @router.get("/codex/artifact", tags=["codex"])
    def artifact():
        art = load_latest_artifact()
        if not art:
            return {"sealed": False, "note": "The Codex has not been sealed yet — POST /codex/seal."}
        return art

    @router.get("/codex/verify", tags=["codex"])
    def verify():
        return verify_codex_artifact()

    @router.post("/codex/seal", tags=["codex"])
    def seal(request: Request):
        if not _operator_ok(request):
            raise HTTPException(403, "Operator only.")
        try:
            signed = build_codex_artifact()
        except ImportError as e:
            raise HTTPException(501, f"Signing unavailable: {e}")
        return {
            "ok": True, "sealed_at": signed.get("sealed_at"),
            "instance_id": signed.get("_instance_id"),
            "body_hash_sha256": signed.get("body", {}).get("body_hash_sha256"),
        }

    return router


if __name__ == "__main__":  # python -m api.codex [seal]
    import sys
    s = build_scripture_index()
    t = build_theme_index()
    cn = build_connection_index()
    cd = build_cards_dev_index()
    out = {"scripture": s.get("stats", {}), "themes": t.get("stats", {}),
           "connections": cn.get("stats", {}), "cards_dev": cd.get("stats", {})}
    if "seal" in sys.argv[1:]:
        art = build_codex_artifact()
        out["sealed"] = {"sealed_at": art.get("sealed_at"),
                         "instance_id": art.get("_instance_id"),
                         "body_hash": art.get("body", {}).get("body_hash_sha256")}
    print(json.dumps(out, indent=2))
