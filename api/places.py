"""Places lens — Bible geography from Easton's Bible Dictionary (1897, PD).

Three things exposed:
  - GET /places           → list all places (920) with first sentence + ref count
  - GET /places/{slug}    → full place entry
  - GET /places/by-ref?ref=Matthew+5:3-12 → which places appear in this verse?
  - GET /easton/{slug}    → full Easton entry (any category — people, concepts, objects)

Source: data/places/entries.jsonl (geographic subset) and
        data/easton/entries.jsonl (all 3,962 entries).

Cross-link: place entries' `scripture_refs` array enables the Atlas of Bibles
parallel viewer to surface "what happened HERE" — click a place → see
references in 20 PD translations.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).parent.parent
_PLACES_FILE = _REPO / "data" / "places"  / "entries.jsonl"
_EASTON_FILE = _REPO / "data" / "easton"  / "entries.jsonl"

# Mtime-cached in-memory indexes
_PLACES_INDEX: Dict[str, Dict[str, Any]] = {}
_PLACES_MTIME: float = 0.0
_EASTON_INDEX: Dict[str, Dict[str, Any]] = {}
_EASTON_MTIME: float = 0.0


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return out
    return out


def _places_index() -> Dict[str, Dict[str, Any]]:
    global _PLACES_INDEX, _PLACES_MTIME
    if not _PLACES_FILE.exists():
        return {}
    mtime = _PLACES_FILE.stat().st_mtime
    if _PLACES_INDEX and mtime == _PLACES_MTIME:
        return _PLACES_INDEX
    idx: Dict[str, Dict[str, Any]] = {}
    for rec in _load_jsonl(_PLACES_FILE):
        pid = rec.get("id", "")
        slug = pid.replace("place_", "", 1) if pid.startswith("place_") else pid
        if slug:
            idx[slug] = rec
    _PLACES_INDEX = idx
    _PLACES_MTIME = mtime
    return idx


def _easton_index() -> Dict[str, Dict[str, Any]]:
    global _EASTON_INDEX, _EASTON_MTIME
    if not _EASTON_FILE.exists():
        return {}
    mtime = _EASTON_FILE.stat().st_mtime
    if _EASTON_INDEX and mtime == _EASTON_MTIME:
        return _EASTON_INDEX
    idx: Dict[str, Dict[str, Any]] = {}
    for rec in _load_jsonl(_EASTON_FILE):
        eid = rec.get("id", "")
        slug = eid.replace("easton_", "", 1) if eid.startswith("easton_") else eid
        if slug:
            idx[slug] = rec
    _EASTON_INDEX = idx
    _EASTON_MTIME = mtime
    return idx


def list_places(letter: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
    """Return all places, optionally filtered by initial letter or substring."""
    idx = _places_index()
    items: List[Dict[str, Any]] = []
    needle = (search or "").strip().lower()
    init = (letter or "").strip().upper()[:1]
    for slug, rec in sorted(idx.items()):
        name = rec.get("name") or slug
        if init and not name.upper().startswith(init):
            continue
        if needle and needle not in name.lower() and needle not in (rec.get("text") or "").lower():
            continue
        text = rec.get("text") or ""
        # first sentence — bounded to keep response small
        first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:240]
        items.append({
            "slug":     slug,
            "name":     name,
            "preview":  first_sentence,
            "ref_count": len(rec.get("scripture_refs") or []),
        })
    return {"total": len(items), "items": items}


def get_place(slug: str) -> Optional[Dict[str, Any]]:
    """Return full entry for one place (or None)."""
    idx = _places_index()
    rec = idx.get(slug.strip().lower())
    if rec is None:
        # Fall back: any Easton entry by slug
        rec = _easton_index().get(slug.strip().lower())
    return rec


def by_reference(ref: str) -> Dict[str, Any]:
    """Given a Scripture reference, list places that mention it.

    Matching is exact-string against the normalized references in
    `scripture_refs` (the neuu format normalizes to e.g. "Genesis 35:16").
    Substring fallback included so "Matthew 5" matches "Matthew 5:3" entries.
    """
    ref_norm = (ref or "").strip()
    if not ref_norm:
        return {"ref": ref_norm, "total": 0, "places": []}
    idx = _places_index()
    out: List[Dict[str, Any]] = []
    for slug, rec in idx.items():
        refs = rec.get("scripture_refs") or []
        hit = False
        for r in refs:
            if r == ref_norm or r.startswith(ref_norm + ":") or r.startswith(ref_norm + " "):
                hit = True
                break
        if hit:
            text = rec.get("text") or ""
            first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:240]
            out.append({
                "slug":    slug,
                "name":    rec.get("name") or slug,
                "preview": first,
            })
    out.sort(key=lambda x: x["name"])
    return {"ref": ref_norm, "total": len(out), "places": out}


def stats() -> Dict[str, Any]:
    """Quick counts for the lens header."""
    p = _places_index()
    e = _easton_index()
    by_cat: Dict[str, int] = {}
    for rec in e.values():
        c = rec.get("category") or "other"
        by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "places":          len(p),
        "easton_total":    len(e),
        "by_category":     by_cat,
        "source":          "Easton's Bible Dictionary (1897, PD)",
        "parse_attribution": "neuu-org/bible-dictionary-dataset (CC-BY 4.0)",
    }
