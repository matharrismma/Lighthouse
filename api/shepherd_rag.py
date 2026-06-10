"""shepherd_rag.py — Substrate-grounded retrieval for the Shepherd conversational layer.

When a family member asks Shepherd a question, this endpoint returns the
top-k most relevant passages from the substrate (Codex packets, Almanac
entries, hymns, daily devotionals, the engine queue's approved items).

Shepherd then composes its answer FROM those passages, citing each one.
No external LLM call required — the engine has the substrate; this just
surfaces the right rows.

Endpoint:
  GET /shepherd/context?q=<question>&k=<5>
  -> {
      "query": "...",
      "results": [
        {"source": "codex|almanac|hymn|engine", "title": "...", "ref": "...",
         "snippet": "...", "url": "/canon.html?ref=...", "score": 0.85}
      ]
  }

Scoring: simple keyword TF-IDF for Phase 1. Real semantic search is a future
upgrade (sentence-transformers + FAISS or similar).
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Query
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
DATA = REPO / "data"
CONTENT = REPO / "content"

# Cache the substrate corpora in memory (small enough for Phase 1)
_CORPUS_CACHE = None
_CORPUS_MTIME = 0


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z']{1,}", (text or "").lower())


def _score_keyword(query_tokens: set, doc_tokens: list[str]) -> float:
    """Simple TF-IDF-ish score: how many query terms appear in the doc, weighted."""
    if not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    common = query_tokens & doc_set
    if not common:
        return 0.0
    # Density: how rare these terms are in the doc vs total
    counts = {t: 0 for t in common}
    for t in doc_tokens:
        if t in counts:
            counts[t] += 1
    # Sum of (count / log(len(doc) + 10))
    import math
    score = sum(counts.values()) / math.log(len(doc_tokens) + 10)
    # Boost if all query terms present
    if len(common) == len(query_tokens):
        score *= 1.5
    return float(score)


def _load_corpus() -> list[dict]:
    """Walk the substrate and produce a flat list of indexed documents.

    Each doc: {source, title, ref, snippet, url, tokens}
    """
    docs = []

    # 1. Hymns
    hymns_path = SITE / "hymns.json"
    if hymns_path.exists():
        try:
            j = json.loads(hymns_path.read_text(encoding="utf-8"))
            for h in (j.get("hymns") or []):
                text = (h.get("title", "") + ' ' + (h.get("text") or '') + ' ' + ' '.join(h.get("topic") or []))
                docs.append({
                    "source": "hymn",
                    "title": h.get("title", ""),
                    "ref": h.get("author", "") + ' · ' + str(h.get("year", "")),
                    "snippet": (h.get("text") or "")[:300],
                    "url": "/hymns.html?slug=" + (h.get("slug") or ''),
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    # 2. Recipes (substrate they can ask cooking questions of)
    recipes_path = CONTENT / "recipes.json"
    if recipes_path.exists():
        try:
            j = json.loads(recipes_path.read_text(encoding="utf-8"))
            for r in (j.get("recipes") or []):
                text = (r.get("title", "") + ' ' + ' '.join(r.get("ingredients") or []) +
                        ' ' + ' '.join(r.get("method") or []) + ' ' + ' '.join(r.get("tags") or []) +
                        ' ' + (r.get("family_note") or ''))
                docs.append({
                    "source": "recipe",
                    "title": r.get("title", ""),
                    "ref": r.get("source", ""),
                    "snippet": (r.get("family_note") or "") or (r.get("title") or ''),
                    "url": "/recipes.html#" + (r.get("slug") or ''),
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    # 3. Maker projects
    projects_path = CONTENT / "projects.json"
    if projects_path.exists():
        try:
            j = json.loads(projects_path.read_text(encoding="utf-8"))
            for p in (j.get("projects") or []):
                text = (p.get("title", "") + ' ' + (p.get("summary") or '') +
                        ' ' + ' '.join(p.get("materials") or []))
                docs.append({
                    "source": "maker",
                    "title": p.get("title", ""),
                    "ref": p.get("primary_source", ""),
                    "snippet": (p.get("summary") or "")[:240],
                    "url": "/maker.html#" + (p.get("slug") or ''),
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    # 4. Approved engine-queue items (devotionals, almanac entries)
    queue_dir = DATA / "engine_queue"
    if queue_dir.exists():
        for f in queue_dir.glob("*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                if rec.get("status") != "approved":
                    continue
                if rec.get("kind") == "devotional":
                    text = (rec.get("scripture_ref", "") + ' ' + (rec.get("scripture_text") or '') +
                            ' ' + (rec.get("reflection") or ''))
                    docs.append({
                        "source": "devotional",
                        "title": rec.get("scripture_ref", "Devotional"),
                        "ref": rec.get("scripture_ref", ""),
                        "snippet": (rec.get("reflection") or "")[:300],
                        "url": "/daily.html?id=" + (rec.get("id") or ''),
                        "tokens": _tokens(text),
                    })
                elif rec.get("kind") == "almanac_entry":
                    text = (rec.get("claim", "") + ' ' + (rec.get("domain") or '') +
                            ' ' + ' '.join(rec.get("sources") or []))
                    docs.append({
                        "source": "almanac",
                        "title": (rec.get("claim") or "")[:80],
                        "ref": rec.get("verdict", "") + ' · ' + (rec.get("domain") or ''),
                        "snippet": (rec.get("claim") or "")[:300],
                        "url": "/almanac.html?id=" + (rec.get("id") or ''),
                        "tokens": _tokens(text),
                    })
            except Exception:
                continue

    # 5. Curriculum subjects (the index, not the per-lesson body)
    curr_path = SITE / "curriculum.html"
    if curr_path.exists():
        text = curr_path.read_text(encoding="utf-8", errors="ignore")
        # Strip HTML tags for the index pass
        plain = re.sub(r"<[^>]+>", " ", text)
        docs.append({
            "source": "curriculum",
            "title": "Homeschool curriculum",
            "ref": "K-12 · 10 subjects",
            "snippet": "Daily curriculum across Bible, Reading, Writing, Math, History, Science, Music, Art, Latin/Greek, Practical.",
            "url": "/curriculum.html",
            "tokens": _tokens(plain[:5000]),
        })

    # 6. Bible book index — each book becomes one searchable document
    books_path = CONTENT / "codex" / "bible_books.json"
    if books_path.exists():
        try:
            j = json.loads(books_path.read_text(encoding="utf-8"))
            for b in (j.get("books") or []):
                text = b.get("book", "") + ' ' + (b.get("theme") or '') + ' ' + (b.get("author") or '') + ' ' + (b.get("section") or '')
                docs.append({
                    "source": "bible_book",
                    "title": b.get("book", ""),
                    "ref": (b.get("testament", "") + ' · ' + (b.get("section") or '') + ' · ' + str(b.get("chapters", 0)) + ' chapters'),
                    "snippet": b.get("theme") or '',
                    "url": "/canon.html?ref=" + (b.get("book") or '').replace(' ', '%20') + "%201",
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    # 7. Catechism Q&A (Westminster Shorter)
    cat_path = CONTENT / "codex" / "catechism_westminster_shorter.json"
    if cat_path.exists():
        try:
            j = json.loads(cat_path.read_text(encoding="utf-8"))
            for q in (j.get("questions") or []):
                text = q.get("question", "") + ' ' + (q.get("answer") or '') + ' ' + ' '.join(q.get("proof_texts") or [])
                docs.append({
                    "source": "catechism",
                    "title": "Westminster Shorter Catechism Q" + str(q.get("q", "")),
                    "ref": "Q" + str(q.get("q", "")) + " · " + (q.get("question") or '')[:60],
                    "snippet": (q.get("answer") or '')[:300],
                    "url": "/canon.html?ref=catechism-q" + str(q.get("q", "")),
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    # 8. Creeds + foundational confessional texts
    creeds_path = CONTENT / "codex" / "creeds.json"
    if creeds_path.exists():
        try:
            j = json.loads(creeds_path.read_text(encoding="utf-8"))
            for c in (j.get("creeds") or []):
                text = (c.get("title", "") + ' ' + (c.get("use") or '') + ' ' +
                        (c.get("text") or '') + ' ' + ' '.join(c.get("anchored_to") or []))
                docs.append({
                    "source": "creed",
                    "title": c.get("title", ""),
                    "ref": c.get("era", ""),
                    "snippet": (c.get("text") or '')[:300],
                    "url": "/canon.html?creed=" + (c.get("slug") or ''),
                    "tokens": _tokens(text),
                })
        except Exception:
            pass

    return docs


def _corpus():
    global _CORPUS_CACHE, _CORPUS_MTIME
    # Reload if any of the watched files changed
    watched = [
        SITE / "hymns.json",
        CONTENT / "recipes.json",
        CONTENT / "projects.json",
        CONTENT / "codex" / "bible_books.json",
        CONTENT / "codex" / "catechism_westminster_shorter.json",
        CONTENT / "codex" / "creeds.json",
        DATA / "engine_queue",
    ]
    latest = 0
    for w in watched:
        if w.exists():
            latest = max(latest, w.stat().st_mtime if w.is_file() else
                                  max((f.stat().st_mtime for f in w.glob("*.json")), default=0))
    if _CORPUS_CACHE is None or latest > _CORPUS_MTIME:
        _CORPUS_CACHE = _load_corpus()
        _CORPUS_MTIME = latest
    return _CORPUS_CACHE


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/shepherd/context")
    def context(q: str = Query(...), k: int = Query(5, ge=1, le=20),
                source: Optional[str] = Query(None)):
        query_tokens = set(_tokens(q))
        if not query_tokens:
            return {"query": q, "results": []}
        corpus = _corpus()
        scored = []
        for d in corpus:
            if source and d.get("source") != source:
                continue
            sc = _score_keyword(query_tokens, d["tokens"])
            if sc > 0:
                scored.append((sc, d))
        scored.sort(key=lambda x: -x[0])
        out = []
        for sc, d in scored[:k]:
            r = dict(d)
            r.pop("tokens", None)
            r["score"] = round(sc, 3)
            out.append(r)
        return {"query": q, "results": out, "corpus_size": len(corpus)}

    @router.get("/shepherd/corpus.stats")
    def corpus_stats():
        corpus = _corpus()
        by_source = {}
        for d in corpus:
            s = d.get("source", "?")
            by_source[s] = by_source.get(s, 0) + 1
        return {"total": len(corpus), "by_source": by_source}

    return router
