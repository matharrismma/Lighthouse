"""well_retriever.py — high-precision TF-IDF retrieval over the WELL's wisdom.

The narrowing (offices.narrow) hands a fixed PROTOCOL when one fits. When none
does, it should still draw the well — but a naive keyword merge surfaces noise
(common words like 'god' flood it; the Easton dictionary + factual entries match
on a single proper noun). This retriever fixes that, with NO model install
(pure-python TF-IDF, numpy-free):

  - WISDOM KINDS ONLY: scripture/psalm/almanac/protocol/parable/fieldkit + the
    patristics & devotional reflections. Drops the dictionary (Easton),
    geography (place), and genealogy noise.
  - TF-IDF: rare, discriminative words (lonely, forgive) outweigh common ones
    (god, more). This is the precise fix for the keyword-merge flooding.
  - REQUIRE >=2 distinct query terms to match: kills single-proper-noun hits, so
    it stays SILENT rather than hand a false trail. Honesty over coverage.

Synonymy (afraid != anxiety) is the recall ceiling here; local embeddings
(Gemma/Ollama, on-box, no data leak) are the future upgrade — same interface.
"""
from __future__ import annotations

import math
import re
import threading
from collections import Counter
from typing import Any, Dict, List, Optional

_WISDOM_KINDS = {
    "scripture", "psalm", "proverbs", "ecclesiastes", "almanac", "protocol",
    "parable", "fieldkit_card", "sermon", "pilgrim", "imitation_christ",
    "pirkei_avot", "augustine_confessions", "boethius_consolation", "aurelius",
    "polycarp", "clement1", "didache", "barnabas", "james", "ignatius_eph",
    "ignatius_mag", "ignatius_rom", "ignatius_tra", "ignatius_smy", "ignatius_phild",
    "ignatius_polyc", "martyrdom_polycarp",
}

_STOP = set((
    "i a an the and or but if is am are was were be been being to of in on at for "
    "with from into over under not no nor do does did how what why when where who "
    "whom which that this these those it its he she they them we you your my our "
    "their as by so too very can could should would will just about him her us me "
    "also have has had get got out up down off than then there here all any more "
    "need feel want know like make made one two new now"
).split())

_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, Any]] = None


def _toks(s: str) -> List[str]:
    return [w for w in re.findall(r"[a-z']{3,}", (s or "").lower()) if w not in _STOP]


def _build() -> Dict[str, Any]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        from api import packets_index as _pi
        docs = []
        df: Counter = Counter()
        by_id: Dict[str, Any] = {}
        for p in _pi.load_all():
            if (p.get("kind") or "") not in _WISDOM_KINDS:
                continue
            text = (p.get("title") or "") + " " + (p.get("summary") or "") + " " + (p.get("body") or "")
            c = Counter(_toks(text))
            if not c:
                continue
            pid = p.get("id")
            docs.append((p, c))
            by_id[pid] = p
            for w in c:
                df[w] += 1
        n = max(1, len(docs))
        idf = {w: math.log(n / (1 + df[w])) for w in df}
        _CACHE = {"docs": docs, "idf": idf, "by_id": by_id, "n": n}
        return _CACHE


def reload() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None


def search(query: str, limit: int = 5, min_terms: int = 2) -> List[Dict[str, Any]]:
    """Return the well's most relevant WISDOM packets for a free-form need, or []
    (honest silence) when nothing clears the bar. Each result: id/title/summary/
    kind/scripture/score."""
    idx = _build()
    qc = Counter(_toks(query))
    if not qc:
        return []
    idf = idx["idf"]
    out = []
    for p, c in idx["docs"]:
        matched = [w for w in qc if c.get(w, 0)]
        if len(matched) < min_terms:
            continue
        score = sum(c.get(w, 0) * idf.get(w, 0.0) * qn for w, qn in qc.items())
        if score <= 0:
            continue
        out.append((score, p))
    out.sort(key=lambda x: -x[0])
    res = []
    for score, p in out[:limit]:
        res.append({"id": p.get("id"), "title": p.get("title") or p.get("id"),
                    "summary": p.get("summary") or "", "kind": p.get("kind"),
                    "scripture": p.get("scripture"), "score": round(score, 1)})
    return res


def get(pid: str) -> Optional[Dict[str, Any]]:
    return _build()["by_id"].get(pid)
