"""The Coach OS — orchestrate a guided walk through a situation.

This module is not a verifier; it's an orchestration layer. Given a
situation text, it composes existing engine machinery into a single
guided experience:

  1. PATTERNS    — which archetypes does this situation resemble?
  2. SCRIPTURE   — what does Layer 0 say on this point?
  3. PROTOCOL    — does a Scripture-defined sequence apply
                   (Mt 18 conflict, discernment, confession, witness,
                   test-spirits, reproof)?
  4. PRECEDENT   — has the engine seen a similar case before?
  5. THE WALK    — the four gates as prompts the user answers
                   themselves (RED → FLOOR → BROTHERS → GOD)

The engine does not tell the user what to do. It surfaces the field
and asks the questions. The user walks.

Engine shows. Human names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROTOCOLS_FILE = Path(__file__).parent.parent / "data" / "protocols" / "scripture_protocols.jsonl"

_PROTOCOL_CACHE: Dict[str, Any] = {"mtime": 0.0, "items": []}


def _load_protocols() -> List[Dict[str, Any]]:
    """mtime-cached protocol load."""
    if not _PROTOCOLS_FILE.exists():
        return []
    try:
        mtime = _PROTOCOLS_FILE.stat().st_mtime
    except OSError:
        return []
    if _PROTOCOL_CACHE["items"] and mtime <= _PROTOCOL_CACHE["mtime"]:
        return _PROTOCOL_CACHE["items"]
    items: List[Dict[str, Any]] = []
    try:
        with _PROTOCOLS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                items.append(rec)
    except OSError:
        return []
    _PROTOCOL_CACHE["mtime"] = mtime
    _PROTOCOL_CACHE["items"] = items
    return items


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def recognize_protocols(situation: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Return protocols whose triggers match the situation, sorted by
    match strength. Match strength = number of distinct triggers hit."""
    norm = _normalize(situation)
    if not norm:
        return []
    scored: List[tuple] = []
    for proto in _load_protocols():
        triggers = proto.get("triggers") or []
        hits: List[str] = []
        for trig in triggers:
            t = _normalize(trig)
            if t and t in norm:
                hits.append(trig)
        if hits:
            scored.append((len(hits), proto, hits))
    scored.sort(key=lambda t: t[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for hits_count, proto, hits in scored[:max_results]:
        out.append({
            "id": proto.get("id"),
            "name": proto.get("name"),
            "scripture": proto.get("scripture", []),
            "summary": proto.get("summary", ""),
            "steps": proto.get("steps", []),
            "failure_modes": proto.get("failure_modes", []),
            "matched_triggers": hits,
            "match_strength": hits_count,
        })
    return out


# ── Four-gate walk prompts (always present; user answers themselves) ────

_FOUR_GATES = [
    {
        "gate": "RED",
        "scripture": "John 14:6",
        "scripture_text": "I am the way, the truth, and the life.",
        "question": "What is the verifiable claim at the heart of this situation? Run it. If the math doesn't close, the situation falls here and goes no further.",
    },
    {
        "gate": "FLOOR",
        "scripture": "Exodus 20",
        "scripture_text": "The Ten Commandments — the floor on which any true claim has to stand.",
        "question": "What principle is this resting on? Name the floor. If you can't name it, the claim is unanchored.",
    },
    {
        "gate": "BROTHERS",
        "scripture": "Deuteronomy 19:15 / Matthew 18:16 / 2 Corinthians 13:1",
        "scripture_text": "In the mouth of two or three witnesses every word shall be established.",
        "question": "Who are the two or three witnesses? Who has tested this with you and found it sound? Without witnesses, the claim is solo and waits.",
    },
    {
        "gate": "GOD",
        "scripture": "Psalm 27:14",
        "scripture_text": "Wait on the LORD: be of good courage, and He shall strengthen thine heart: wait, I say, on the LORD.",
        "question": "Have you waited? Is there peace? Acting before God has confirmed is the most common failure. If you cannot wait, you do not yet trust.",
    },
]


def four_gates_walk() -> List[Dict[str, Any]]:
    """Return the four-gate walk. Static structure — the user answers
    each gate themselves. Engine never answers for them."""
    return [dict(g) for g in _FOUR_GATES]


# ── Orchestration ──────────────────────────────────────────────────────

def walk(situation: str, *, include_polymathic: bool = True) -> Dict[str, Any]:
    """Compose the guided walk for a situation.

    Returns a structured response with all five layers:
      patterns, scripture, protocols, precedent, the_walk

    The polymathic + archetype + layer-0 pieces are loaded lazily so this
    module stays usable even if those subsystems are degraded.
    """
    out: Dict[str, Any] = {
        "situation": situation,
        "patterns": None,
        "scripture": None,
        "protocols": [],
        "precedent": None,
        "the_walk": four_gates_walk(),
        "notes": [],
    }

    # 1. Pattern recognition (archetypes)
    try:
        from api import archetypes as _archetypes
        rec = _archetypes.recognize(situation, top_k=3)
        if rec.get("candidates"):
            out["patterns"] = {
                "combination": rec.get("combination"),
                "candidates": rec.get("candidates", [])[:3],
                "note": rec.get("note"),
            }
    except Exception as exc:
        out["notes"].append(f"archetype recognition unavailable: {str(exc)[:120]}")

    # 2. Scripture grounding (Layer 0)
    try:
        from concordance_engine.verifiers import layer_zero_grounding as _l0
        results = _l0.run({"LAYER0_VERIFY": {"claim": situation}})
        if results and results[0].data:
            d = results[0].data
            passages = d.get("passages") or []
            if passages:
                out["scripture"] = {
                    "passages": passages,
                    "missing": d.get("missing", []),
                    "source": d.get("source"),
                }
    except Exception as exc:
        out["notes"].append(f"layer-0 grounding unavailable: {str(exc)[:120]}")

    # 3. Protocols
    out["protocols"] = recognize_protocols(situation, max_results=3)

    # 4. Closest precedent (axis-based retrieval against sealed records)
    try:
        from concordance_engine.axis_index import find_closest as _find_closest
        # Without classifying first, use a coarse signature: just check for
        # any precedent in the index. A richer integration would
        # classify the situation first and use those axes; for now this
        # surfaces any nearby sealed case.
        prec = _find_closest([])  # empty axes returns nothing meaningful
        if prec:
            out["precedent"] = prec
    except Exception:
        pass

    # 5. (Optional) full polymathic run for atomic-claim verification.
    # Disabled by default since it can be slow; opt in via flag. The
    # operator console / future page can call /polymathic directly.
    if include_polymathic:
        out["notes"].append(
            "for atomic-claim verification of any specific factual statements in "
            "the situation, run them through /run or /polymathic separately."
        )

    return out
