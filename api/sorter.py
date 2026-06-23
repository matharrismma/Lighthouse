"""sorter.py — the workspace 'trash sorter': one inlet, any input, sorted.

Matt's vision: the central workspace takes in ANYTHING, strips it to cards and
tasks, directs traffic to the right tool, and returns with context. The
differentiator is DISCERNMENT, not generation — "AI has no judgement." So the
sort is DETERMINISTIC: segment, classify by rules, route to the engine's real
tools, and attach context from the verified keeping. No oracle/LLM is called
here at all — this is pure judgement on rules + the corpus.

Christ first: the crisis net runs FIRST (at the endpoint), fragments that touch
ultimate matters are FLAGGED to point UP (Christ, Scripture, prayer, real
people), and the tool never poses as the source — it is the flexible connector,
never the idol.

Sovereign: stdlib only + corpus_search (the keeping).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ── segmentation ────────────────────────────────────────────────────────────
_BULLET = re.compile(r"^\s*(?:[-*•·▪◦]|\d+[.)]|\(\d+\)|\[[ xX]?\])\s+")
_SENT = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9\"'])")


def _segment(text: str) -> List[str]:
    """Split a blob into atomic fragments: by line/bullet first, then long prose
    lines into sentences. Deterministic — the same input always sorts the same."""
    frags: List[str] = []
    lines = [ln.strip() for ln in text.splitlines()]
    real_lines = [ln for ln in lines if ln]
    # A single long paragraph (no line structure) → split into sentences.
    if len(real_lines) <= 1 and len(text) > 160:
        for s in _SENT.split(text.strip()):
            s = _BULLET.sub("", s).strip()
            if s:
                frags.append(s)
        return frags or [text.strip()]
    for ln in real_lines:
        ln = _BULLET.sub("", ln).strip()
        if not ln:
            continue
        if len(ln) > 220 and len(_SENT.split(ln)) > 1:
            for s in _SENT.split(ln):
                s = s.strip()
                if s:
                    frags.append(s)
        else:
            frags.append(ln)
    return frags


# ── classification (the judgement) ──────────────────────────────────────────
_NOISE = {"ok", "okay", "k", "hi", "hello", "hey", "thanks", "thank you", "yes",
          "no", "yep", "nope", "um", "uh", "lol", "done", "n/a", "na", "test"}
# Filler words: a fragment whose words are ALL filler is trash to discard.
_FILLER = _NOISE | {"great", "cool", "nice", "sure", "maybe", "fine", "good",
                    "right", "yeah", "yup", "just", "really", "very", "etc",
                    "also", "so", "well", "anyway", "and", "the", "a", "an",
                    "of", "to", "thx", "ty", "please", "pls", "thank", "you"}
# Common words that don't signal topical relevance (for the context guard).
_STOP = {"this", "that", "with", "from", "what", "when", "where", "your", "you",
         "have", "will", "about", "into", "than", "then", "them", "they",
         "there", "their", "would", "could", "should", "being", "does", "the"}
_TASK_VERBS = {
    "call", "email", "text", "message", "write", "build", "fix", "buy", "schedule",
    "send", "finish", "draft", "create", "make", "plan", "book", "pay", "read",
    "review", "research", "ask", "set", "add", "remove", "update", "clean",
    "organize", "prepare", "submit", "order", "sign", "renew", "cancel", "print",
    "deploy", "ship", "launch", "publish", "record", "study", "memorize",
    "practice", "stretch", "pray", "tithe", "give", "forgive", "apologize",
    "thank", "back", "backup", "install", "download", "upload", "register",
}
_TASK_PHRASES = ("need to", "needs to", "have to", "has to", "must ", "got to",
                 "gotta", "to-do", "todo", "remember to", "don't forget",
                 "dont forget", "make sure", "follow up", "follow-up", "deadline",
                 "due ", "by tomorrow", "by today", "by monday", "by tuesday",
                 "by wednesday", "by thursday", "by friday", "by next", "asap")
_Q_STARTS = ("who ", "what", "when", "where", "why", "how", "which", "is ", "are ",
             "can ", "could ", "should ", "does ", "do ", "will ", "would ",
             "was ", "were ", "did ", "whom", "whose", "may i", "should i")
_CHECKABLE = ("calculate", "compute", "how much", "how many", "percent", "%",
              "square root", "derivative", "integral", "prime", "equation",
              "convert", "=", "how far", "how long", "how fast", "probability")
_ULTIMATE = ("meaning of life", "purpose of life", "why am i here", "is there a god",
             "does god", "heaven", "hell", "afterlife", "my soul", "salvation",
             "forgiven", "worthless", "no reason to", "want to die", "end my life",
             "hate myself", "despair", "hopeless", "what happens when we die",
             "is jesus", "who is jesus", "born again", "eternal")


def _is_noise(t: str) -> bool:
    s = t.strip().strip(".!?,")
    if len(s) <= 2:
        return True
    words = re.findall(r"[a-z']+", s.lower())
    if not words:
        return True  # pure punctuation / a bare number standing alone
    return all(w in _FILLER for w in words)


def _is_question(t: str) -> bool:
    tl = t.lower()
    return t.rstrip().endswith("?") or tl.startswith(_Q_STARTS)


def _is_task(t: str) -> bool:
    tl = t.lower()
    if any(p in tl for p in _TASK_PHRASES):
        return True
    first = re.sub(r"[^a-z]", "", tl.split(" ", 1)[0]) if tl else ""
    return first in _TASK_VERBS


def _touches_ultimate(t: str) -> bool:
    tl = t.lower()
    return any(p in tl for p in _ULTIMATE)


# ── routing (direct the traffic to the engine's real tools) ─────────────────
_WHEN = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
         "sunday", "tomorrow", "today", "tonight", "next week", "this week",
         "next month", "o'clock", "noon", "midnight", "a.m", "p.m",
         "schedule", "calendar", "appointment", "remind", "meeting", "book a",
         "due ", "deadline")


def _route_task(t: str) -> Dict[str, str]:
    tl = t.lower()
    if any(w in tl for w in ("research", "paper", "papers", "study", "studies",
                             "literature", "journal")) or re.search(r"10\.\d{4,9}/", t):
        return {"tool": "scholar", "why": "asks for the research literature",
                "endpoint": "GET /scholar/lookup"}
    if any(w in tl for w in ("verify", "check that", "is it true", "calculate",
                             "compute", "prove", "fact-check", "fact check")):
        return {"tool": "verify", "why": "a checkable claim/computation",
                "endpoint": "POST /derivation/verify"}
    if any(w in tl for w in ("learn", "teach me", "how do i", "how does",
                             "understand", "explain")):
        return {"tool": "learn", "why": "wants to be taught",
                "endpoint": "POST /workspace/learn"}
    if any(w in tl for w in ("write", "draft", "email", "letter", "book",
                             "chapter", "post", "blog", "essay", "sermon", "speech")):
        return {"tool": "draft", "why": "composition — the assistant drafts, you keep authorship",
                "endpoint": "POST /workspace/intake", "note": "generation: drafted, not verified"}
    if any(w in tl for w in ("build", "site", "website", "app", "tool", "code",
                             "deploy", "landing page", "feature")):
        return {"tool": "build", "why": "a build task — scope it into steps",
                "endpoint": "POST /workspace/intake", "note": "generation: drafted, not verified"}
    # Financial BEFORE schedule: a purchase with a time is still yours to perform.
    if any(w in tl for w in ("buy", "order", "purchase", "pay", "transfer", "send money")):
        return {"tool": "reminder", "why": "a purchase/payment — kept as a reminder for YOU to do",
                "endpoint": "(you act)", "note": "financial actions are yours to perform, not the tool's"}
    if any(w in tl for w in _WHEN):
        return {"tool": "schedule", "why": "time-bound — put it on the calendar",
                "endpoint": "(your calendar)"}
    if any(w in tl for w in ("look up", "find", "search", "what is", "who is")):
        return {"tool": "search", "why": "a lookup against the keeping",
                "endpoint": "GET /search?q="}
    return {"tool": "task", "why": "an action to keep on the list",
            "endpoint": "(the keeping — tasks)"}


def _route_question(t: str) -> Dict[str, str]:
    tl = t.lower()
    if re.search(r"10\.\d{4,9}/", t) or any(w in tl for w in
                                            ("paper", "study", "literature", "research")):
        return {"tool": "scholar", "why": "research question",
                "endpoint": "GET /scholar/lookup"}
    if any(w in tl for w in _CHECKABLE):
        return {"tool": "verify", "why": "a checkable / computational question",
                "endpoint": "POST /derivation/verify"}
    return {"tool": "search", "why": "answerable from the keeping",
            "endpoint": "GET /search?q="}


def _relevant(query: str, card: Dict[str, Any]) -> bool:
    """A relevance floor so we never attach MISLEADING context (the keeping is a
    Christian/knowledge corpus; a physics question has no answer here and must not
    get Scripture pinned to it). Require the card to actually contain the query's
    substantive words — most of them when there are several, all when there's one.
    The map never launders, not even by association."""
    q = {w for w in re.findall(r"[a-z0-9]+", query.lower())
         if len(w) >= 4 and w not in _STOP}
    if not q:
        return True  # nothing substantive to gate on — let the ranker stand
    blob = ((card.get("title") or "") + " " + (card.get("body") or "")[:400]).lower()
    hits = sum(1 for w in q if w in blob)
    need = 2 if len(q) >= 2 else 1
    return hits >= need


def _context_for(text: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Real, RELEVANT context from the verified keeping — never generated, never
    pinned where it does not belong."""
    try:
        from api.cards import corpus_search
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, Any]] = []
    try:
        for c in corpus_search(text, limit=limit + 3):
            if not _relevant(text, c):
                continue
            cid = c.get("id")
            out.append({"id": cid, "title": c.get("title") or cid,
                        "shelf": c.get("shelf"),
                        "url": "/c/" + (cid or "")})
            if len(out) >= limit:
                break
    except Exception:  # noqa: BLE001
        return []
    return out


_UP_NOTE = ("This touches an ultimate matter. The tool can hold it, but the answer is "
            "not in the tool — it is in Christ, in Scripture, in prayer, and in real "
            "people (a pastor, your church). If this is heavy, reach a person today.")


def sort(text: str, context_budget: int = 8) -> Dict[str, Any]:
    """One inlet → cards + tasks, routed, with context. Deterministic discernment.

    context_budget caps how many fragments get a live corpus lookup, so a big
    brain-dump stays fast; everything is still classified and routed."""
    text = (text or "").strip()
    if not text:
        return {"summary": "nothing brought", "tasks": [], "questions": [],
                "cards": [], "discarded": []}
    frags = _segment(text)
    tasks: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []
    discarded: List[str] = []
    christ_first: List[Dict[str, str]] = []
    spent = 0

    for f in frags:
        if _is_noise(f):
            discarded.append(f)
            continue
        ultimate = _touches_ultimate(f)
        if ultimate:
            christ_first.append({"text": f, "note": _UP_NOTE})
        if _is_question(f):
            r = _route_question(f)
            item: Dict[str, Any] = {"text": f, **r}
            if r["tool"] == "search" and spent < context_budget:
                item["context"] = _context_for(f)
                spent += 1
            questions.append(item)
        elif _is_task(f):
            tasks.append({"text": f, **_route_task(f)})
        else:
            # a fact / idea / reference worth keeping → a card, with real context
            card: Dict[str, Any] = {"text": f}
            if spent < context_budget:
                card["context"] = _context_for(f)
                spent += 1
            cards.append(card)

    parts = []
    if tasks:
        parts.append(f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}")
    if questions:
        parts.append(f"{len(questions)} question{'s' if len(questions) != 1 else ''}")
    if cards:
        parts.append(f"{len(cards)} card{'s' if len(cards) != 1 else ''} kept")
    if discarded:
        parts.append(f"{len(discarded)} discarded")
    summary = "Sorted " + (", ".join(parts) if parts else "nothing actionable") + "."

    out: Dict[str, Any] = {
        "summary": summary,
        "tasks": tasks,
        "questions": questions,
        "cards": cards,
        "discarded": discarded,
        "engine": ("deterministic — sorted by judgement on rules + the verified keeping, "
                   "no generation. The tool is the connector, never the source."),
    }
    if christ_first:
        out["christ_first"] = christ_first
    return out
