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


# ── The Shepherd's ANSWER: ground it, connect the dots, point to Christ ──────
_OVERVIEW = None


def _load_overview() -> dict:
    global _OVERVIEW
    if _OVERVIEW is None:
        try:
            _OVERVIEW = json.loads((DATA / "shepherd" / "site_overview.json").read_text("utf-8"))
        except Exception:
            _OVERVIEW = {}
    return _OVERVIEW


# Meta / self questions — answered from the site overview, not the corpus.
_META_Q = ("what does this site", "what does the site", "what the site does",
           "what this site does", "what is this site", "what is this website",
           "what does this website", "what is narrow highway", "what does narrow highway",
           "what is the concordance", "what does the concordance", "what does this engine",
           "what is this engine", "what can you do", "what can i do here", "what's here",
           "whats here", "what is here", "who are you", "what are you", "how do i use this",
           "how does this site", "explain the site", "explain this site", "tell me about this site",
           "tell me about narrow highway", "what is this place", "what's this site",
           "purpose of this site", "what is this all about", "what does this place")


def _is_meta(q: str) -> bool:
    ql = " ".join(q.lower().split())
    return any(p in ql for p in _META_Q)


# Light, curated query expansion — boost recall so the right Scripture ranks (the
# lexical ranker does not know anxiety~worry). Conservative; real synonyms only.
_SYNONYMS = {
    "anxiety": "worry anxious afraid fear peace", "anxious": "worry anxiety afraid fear peace",
    "worry": "anxious anxiety afraid fear peace", "fear": "afraid anxious courage fearful",
    "afraid": "fear anxious courage", "money": "wealth riches mammon possessions",
    "marriage": "husband wife wedding spouse", "anger": "wrath angry rage patience",
    "forgive": "forgiveness mercy pardon", "forgiveness": "forgive mercy pardon",
    "suffering": "affliction trial sorrow pain tribulation", "death": "dying die grave resurrection",
    "doubt": "unbelief faith believe", "lonely": "alone loneliness comfort",
    "grief": "mourning sorrow comfort weep", "purpose": "meaning calling",
    "salvation": "saved redeemed eternal life", "sin": "transgression iniquity repent",
    "hope": "hopeful encouragement", "love": "charity beloved",
}


def _expand(q: str) -> str:
    ql = q.lower()
    extra = [v for k, v in _SYNONYMS.items() if k in ql]
    return (q + " " + " ".join(extra)) if extra else q


_ULTIMATE = ("god", "jesus", "christ", "sin", "salvation", "saved", "heaven", "hell", "soul",
             "die", "death", "meaning of life", "purpose of life", "suffering", "forgive",
             "pray", "prayer", "worship", "faith", "gospel", "eternal", "despair", "hopeless",
             "worthless", "guilt")


def _touches_ultimate(q: str) -> bool:
    ql = q.lower()
    return any(w in ql for w in _ULTIMATE)


# Scripture-reference detection — validate the book token so "Page 3" isn't a verse.
_BOOKS = {"genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges",
          "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah", "esther", "job",
          "psalm", "psalms", "proverbs", "ecclesiastes", "song", "isaiah", "jeremiah",
          "lamentations", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah",
          "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
          "matthew", "mark", "luke", "john", "acts", "romans", "corinthians", "galatians",
          "ephesians", "philippians", "colossians", "thessalonians", "timothy", "titus",
          "philemon", "hebrews", "james", "peter", "jude", "revelation"}
_REF_RE = re.compile(r"\b((?:[1-3]\s*)?[A-Za-z]+)\s+(\d{1,3})(?::(\d{1,3}))?\b")


def _detect_scripture_ref(q: str) -> Optional[str]:
    for m in _REF_RE.finditer(q):
        book = re.sub(r"[^a-z]", "", m.group(1).lower())
        if book in _BOOKS:
            ref = m.group(1).strip() + " " + m.group(2) + (":" + m.group(3) if m.group(3) else "")
            return " ".join(ref.split())
    return None


_WEAVE_SYS = (
    "You are the Shepherd, answering ONLY from the passages provided. Thread them into a "
    "short plain answer (2-4 sentences) that CONNECTS them — use only what is in the passages, "
    "and name where each point comes from. If the passages do not actually answer the question, "
    "say so plainly. You are a tool, not an authority: on ultimate questions (God, meaning, "
    "suffering, death, sin, salvation) point to Christ, Scripture, prayer, and real people — "
    "never pose as the final word. Plain text only."
)


def _weave(q: str, cards: list) -> Optional[dict]:
    """Optional synthesis: a LOCAL-model thread over the retrieved cards (Bumblebee
    — weave found pieces, never invent). Flagged drafted, never sealed. None if no
    local model is available."""
    if not cards:
        return None
    try:
        from api import local_llm
        if not local_llm.available():
            return None
        passages = "\n\n".join(
            f"[{i + 1}] {c.get('title', '')} ({c.get('source', '')}): {c.get('snippet', '')}"
            for i, c in enumerate(cards[:4]))
        out = local_llm.generate(f"Question: {q}\n\nPassages:\n{passages}\n\nThread them:",
                                 system=_WEAVE_SYS, max_tokens=180, temperature=0.2)
    except Exception:
        return None
    if not out or not out.strip():
        return None
    return {"text": " ".join(out.split()), "drafted": True,
            "note": "drafted from the cards above — not verified; the cards are the ground"}


def shepherd_answer(q: str, k: int = 5) -> dict:
    """The Shepherd ANSWERS: crisis first; meta/self questions from the site overview;
    everything else grounded in the verified keeping (corpus_search) with the dots
    connected; ultimate matters pointed to Christ. Never guesses — answers from what
    is verified, or says it doesn't know."""
    q = (q or "").strip()
    if not q:
        return {"question": q, "mode": "empty",
                "answer": "Bring a question or a situation and I'll ground it in the keeping."}

    try:
        from api import safety
        c = safety.crisis_check(q)
        if c:
            return {"question": q, "mode": "safety", "safety": c, "grounded_cards": [],
                    "answer": "You matter, and you are not alone. Please reach a person now — "
                              "real help is listed here."}
    except Exception:
        pass

    if _is_meta(q):
        ov = _load_overview()
        if ov:
            lines = [f"• {d['name']} ({d['url']}) — {d['does']}"
                     for d in ov.get("doorways", [])]
            answer = (ov.get("what", "") + "\n\nWhat's here:\n" + "\n".join(lines)
                      + "\n\n" + ov.get("mission", "")).strip()
            return {"question": q, "mode": "about", "answer": answer,
                    "doorways": ov.get("doorways", []), "grounded_cards": [],
                    "note": ov.get("honest_bounds", "")}

    cards = []
    try:
        from api.cards import corpus_search
        for c in corpus_search(_expand(q), limit=k):
            cid = c.get("id") or ""
            src = c.get("source") or {}
            cards.append({
                "source": c.get("shelf") or c.get("kind") or "card",
                "title": c.get("title") or cid,
                "ref": (src.get("label") if isinstance(src, dict) else "") or "",
                "snippet": (c.get("body") or "")[:280],
                "url": "/c/" + cid,
            })
    except Exception:
        pass

    if not cards:
        return {"question": q, "mode": "miss", "grounded_cards": [],
                "answer": "I don't have a grounded answer for that in the keeping yet. "
                          "Bring it to the Walk to verify or weigh it.",
                "note": "I won't guess — I answer from what is verified, or I say I don't know."}

    lead = cards[0]
    answer = ("From the keeping — " + lead["title"]
              + (f" ({lead['ref']})" if lead.get("ref") else "") + ": " + lead["snippet"])
    out = {"question": q, "mode": "answer", "answer": answer, "grounded_cards": cards,
           "note": "Grounded in the verified keeping; open any card for its full text + source."}
    thread = _weave(q, cards)
    if thread:
        out["thread"] = thread

    # CONNECT THE DOTS (additive, grounded) — Scripture echoes + deterministic verdicts.
    ref = _detect_scripture_ref(q)
    if ref:
        try:
            from concordance_engine.mcp_server import tools as _tools
            cr = _tools.cross_references(ref, 6)
            refs = (cr.get("cross_references") or cr.get("results") or []) if isinstance(cr, dict) else []
            if refs:
                out["scripture"] = {
                    "ref": ref, "cross_references": refs[:6],
                    "note": "where Scripture echoes Scripture — an attributed index (Treasury of "
                            "Scripture Knowledge, CC BY), not the engine's doctrine"}
        except Exception:  # noqa: BLE001
            pass

    # A checkable claim, verified DETERMINISTICALLY (rule dispatch + verifier; no
    # oracle, no guess) — attached only when a rule actually matches.
    try:
        from concordance_engine.agent.dispatch import dispatch as _nl_dispatch
        dr = _nl_dispatch(q)
        dom = getattr(dr, "domain", None) if dr is not None else None
        if dom:
            from api.agent_manifest import dispatch as _verify_dispatch
            vr = _verify_dispatch("verify_" + dom, getattr(dr, "spec", {}) or {})
            if isinstance(vr, dict) and vr.get("ok"):
                out["verified"] = {
                    "domain": dom, "result": vr.get("result"),
                    "note": "checked deterministically by the engine, not guessed"}
                out["answer"] = ("The engine checked this directly (" + dom
                                 + ", verified). " + out["answer"])
    except Exception:  # noqa: BLE001
        pass

    if _touches_ultimate(q):
        out["points_up"] = ("This touches an ultimate matter. The answer is not in the tool — it "
                            "is in Christ, in Scripture, in prayer, and in real people. Bring it to Him.")
    return out


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/shepherd/context")
    def context(q: str = Query(...), k: int = Query(5, ge=1, le=20),
                source: Optional[str] = Query(None)):
        """Grounding for the Shepherd from the WHOLE keeping. PRIMARY: the de-siloed
        corpus_search ranker (~11k verified cards — Scripture, classics, fathers,
        dictionary, ...). SUPPLEMENT: the small curated index (hymns/recipes/maker)
        to fill niche queries. Fixes the old silo that returned, e.g., the creeds
        for 'anxiety' instead of the Scripture on anxiety."""
        if not q.strip():
            return {"query": q, "results": []}
        results: list[dict] = []
        seen: set = set()
        # PRIMARY — the whole keeping, real relevance ranking.
        try:
            from api.cards import corpus_search
            for c in corpus_search(q, limit=k * 2):
                cid = c.get("id") or ""
                if source and c.get("shelf") != source and c.get("kind") != source:
                    continue
                url = "/c/" + cid
                if url in seen:
                    continue
                seen.add(url)
                src = c.get("source") or {}
                results.append({
                    "source": c.get("shelf") or c.get("kind") or "card",
                    "title": c.get("title") or cid,
                    "ref": (src.get("label") if isinstance(src, dict) else "") or "",
                    "snippet": (c.get("body") or "")[:300],
                    "url": url,
                    "score": None,
                })
                if len(results) >= k:
                    break
        except Exception:
            pass
        # SUPPLEMENT — the curated niche index (hymns/recipes/maker/...) to fill out.
        if len(results) < k:
            query_tokens = set(_tokens(q))
            scored = []
            for d in _corpus():
                if source and d.get("source") != source:
                    continue
                sc = _score_keyword(query_tokens, d["tokens"])
                if sc > 0:
                    scored.append((sc, d))
            scored.sort(key=lambda x: -x[0])
            for sc, d in scored:
                if len(results) >= k:
                    break
                if d.get("url") in seen:
                    continue
                r = dict(d)
                r.pop("tokens", None)
                r["score"] = round(sc, 3)
                results.append(r)
                seen.add(d.get("url"))
        return {"query": q, "results": results[:k], "via": "corpus_search+curated"}

    @router.get("/shepherd/answer")
    def answer(q: str = Query(...), k: int = Query(5, ge=1, le=12)):
        """The Shepherd ANSWERS — grounded in the whole keeping, dots connected,
        Christ-first. Meta questions ('what does this site do?') are answered from
        the site overview; knowledge questions are grounded in corpus_search (with
        light synonym recall) and optionally threaded by the local model (flagged);
        crisis signals are met with help first. It never guesses."""
        return shepherd_answer(q, k=k)

    @router.get("/shepherd/corpus.stats")
    def corpus_stats():
        corpus = _corpus()
        by_source = {}
        for d in corpus:
            s = d.get("source", "?")
            by_source[s] = by_source.get(s, 0) + 1
        return {"total": len(corpus), "by_source": by_source}

    return router
