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
                   Walks the sealed polymathic axis_index AND the
                   almanac for the closest entry by Jaccard overlap.
  5. THE WALK    — the four gates as prompts the user answers
                   themselves (RED → FLOOR → BROTHERS → GOD)

The engine does not tell the user what to do. It surfaces the field
and asks the questions. The user walks.

Engine shows. Human names.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from api import substrate as _substrate

_PROTOCOLS_FILE = Path(__file__).parent.parent / "data" / "protocols" / "scripture_protocols.jsonl"
_ALMANAC_FILE = Path(__file__).parent.parent / "data" / "almanac" / "entries.jsonl"

_PROTOCOL_CACHE: Dict[str, Any] = {"mtime": 0.0, "items": []}
_ALMANAC_CACHE: Dict[str, Any] = {"mtime": 0.0, "items": []}

# ── Archetype-category → engine-axis map. Used to derive axes from
#    recognized archetypes when no LLM classification is available.
#    These are the 7 scaffold axes: reasoning, encoding, authority_trust,
#    physical_substance, metabolism, conservation_balance, time_sequence.
_CATEGORY_AXIS_MAP: Dict[str, List[str]] = {
    # Trust / authority categories
    "deception":    ["authority_trust", "reasoning"],
    "conflict":     ["authority_trust", "reasoning"],
    "betrayal":     ["authority_trust", "time_sequence"],
    "leadership":   ["authority_trust"],
    "obedience":    ["authority_trust"],
    "witness":      ["authority_trust", "reasoning"],
    "testimony":    ["authority_trust", "reasoning"],
    # Reasoning / discernment
    "discernment":  ["reasoning", "authority_trust"],
    "decision":     ["reasoning", "time_sequence"],
    "wisdom":       ["reasoning"],
    "doubt":        ["reasoning", "authority_trust"],
    # Time / sequence
    "waiting":      ["time_sequence", "authority_trust"],
    "timing":       ["time_sequence"],
    "season":       ["time_sequence", "metabolism"],
    "patience":     ["time_sequence", "reasoning"],
    # Metabolism (life cycles, growth, work)
    "labor":        ["metabolism", "conservation_balance"],
    "growth":       ["metabolism", "time_sequence"],
    "harvest":      ["metabolism", "conservation_balance"],
    "mourning":     ["metabolism", "time_sequence"],
    # Conservation / balance
    "stewardship":  ["conservation_balance", "authority_trust"],
    "justice":      ["conservation_balance", "authority_trust"],
    "restitution":  ["conservation_balance", "authority_trust"],
    "money":        ["conservation_balance", "reasoning"],
    # Physical / material
    "creation":     ["physical_substance"],
    "illness":      ["physical_substance", "metabolism"],
    "craft":        ["physical_substance", "reasoning"],
    # Encoding / language / identity
    "calling":      ["encoding", "authority_trust"],
    "identity":     ["encoding", "authority_trust"],
    "covenant":     ["encoding", "authority_trust"],
    "promise":      ["encoding", "authority_trust", "time_sequence"],
    # Relational (default to authority_trust + metabolism)
    "relationship": ["authority_trust", "metabolism"],
    "marriage":     ["authority_trust", "metabolism", "time_sequence"],
    "family":       ["authority_trust", "metabolism"],
    "friendship":   ["authority_trust"],
}

# ── Protocol-id → engine-axis map. Each Scripture protocol implies
#    a small set of axes the situation lives on.
_PROTOCOL_AXIS_MAP: Dict[str, List[str]] = {
    "matthew_18_conflict":   ["authority_trust", "reasoning", "time_sequence"],
    "discernment_wait":      ["reasoning", "authority_trust", "time_sequence"],
    "confession":            ["authority_trust", "conservation_balance", "time_sequence"],
    "witness_four_gates":    ["authority_trust", "reasoning"],
    "test_spirits":          ["authority_trust", "reasoning", "encoding"],
    "reproof":               ["authority_trust", "reasoning"],
    "marriage_discord":      ["authority_trust", "metabolism", "time_sequence"],
    "money_giving":          ["conservation_balance", "authority_trust", "reasoning"],
    "calling_vocation":      ["encoding", "authority_trust", "reasoning", "time_sequence"],
    "mourning":              ["metabolism", "time_sequence", "authority_trust"],
    "persecution":           ["authority_trust", "reasoning", "time_sequence"],
    "hospitality":           ["metabolism", "authority_trust", "conservation_balance"],
    "restoration_after_sin": ["authority_trust", "reasoning", "time_sequence"],
    # batch 2 (2026-05-12) — see data/protocols/scripture_protocols.jsonl
    "prayer_lords_pattern":  ["authority_trust", "encoding"],
    "anxiety_phil_4":        ["authority_trust", "reasoning", "time_sequence"],
    "temptation_escape":     ["authority_trust", "reasoning", "time_sequence"],
    "anger_eph_4":           ["authority_trust", "reasoning", "time_sequence"],
    "forgiveness_seventy_seven": ["authority_trust", "conservation_balance"],
    "fasting_secret":        ["authority_trust", "metabolism", "physical_substance"],
    "sabbath_rest":          ["time_sequence", "metabolism", "conservation_balance"],
    "vow_keeping":           ["authority_trust", "encoding", "time_sequence"],
    "submission_authority":  ["authority_trust", "reasoning"],
    "honoring_parents":      ["authority_trust", "metabolism"],
    "work_diligence":        ["metabolism", "authority_trust", "conservation_balance"],
    "fear_of_man":           ["authority_trust", "reasoning"],
    "answering_fool":        ["authority_trust", "reasoning", "encoding"],
    # batch 3 (2026-05-13)
    "restitution_zacchaeus":     ["authority_trust", "conservation_balance"],
    "boundary_pearls":           ["authority_trust", "conservation_balance"],
    "mentoring_paul_timothy":    ["authority_trust", "time_sequence", "metabolism"],
    "hard_conversation":         ["authority_trust", "reasoning", "encoding"],
    "end_of_life_care":          ["authority_trust", "time_sequence", "metabolism"],
    "apologetics_1pet_3_15":     ["authority_trust", "reasoning", "encoding"],
    "midlife_vocation":          ["authority_trust", "encoding", "time_sequence"],
    "sabbath_planning":          ["time_sequence", "conservation_balance", "metabolism"],
    "truth_telling_difficult_news": ["authority_trust", "encoding", "reasoning"],
    "financial_inheritance":     ["authority_trust", "conservation_balance", "time_sequence"],
}

# ── Keyword → axis fallback. Used when archetypes and protocols
#    don't fire but the engine can still pick out structural words.
_KEYWORD_AXIS_HITS: List[tuple] = [
    # (regex_pattern, [axes])
    (r"\bmoney|wage|debt|owe|cost|invest|loan|interest\b", ["conservation_balance", "reasoning"]),
    (r"\bwait|wait\s+for|hurry|rush|patience\b",          ["time_sequence", "authority_trust"]),
    (r"\bsick|ill|disease|symptom|doctor|hospital\b",     ["physical_substance", "metabolism"]),
    (r"\bgrow|plant|harvest|field|crop|seed\b",           ["metabolism", "time_sequence"]),
    (r"\blie|lying|deceiv|fraud|cheat|false\b",           ["authority_trust", "reasoning"]),
    (r"\bwitness|testify|evidence|proof\b",               ["authority_trust", "reasoning"]),
    (r"\bdecide|decision|choose|choice\b",                ["reasoning", "time_sequence"]),
    (r"\bword|name|covenant|promise|vow\b",               ["encoding", "authority_trust"]),
    (r"\bbuilt|build|broken|repair|structure\b",          ["physical_substance", "conservation_balance"]),
    (r"\bbalance|fair|equal|share|portion\b",             ["conservation_balance"]),
]


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
    items = _substrate.read_jsonl(_PROTOCOLS_FILE)
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
        "eliminates": "Claims whose core fact doesn't check out. If the math doesn't close, it stops here — nothing false survives the first gate.",
    },
    {
        "gate": "FLOOR",
        "scripture": "Exodus 20",
        "scripture_text": "The Ten Commandments — the floor on which any true claim has to stand.",
        "question": "What principle is this resting on? Name the floor. If you can't name it, the claim is unanchored.",
        "eliminates": "Claims resting on no nameable principle. The unanchored — true on the facts but standing on nothing — falls here.",
    },
    {
        "gate": "BROTHERS",
        "scripture": "Deuteronomy 19:15 / Matthew 18:16 / 2 Corinthians 13:1",
        "scripture_text": "In the mouth of two or three witnesses every word shall be established.",
        "question": "Who are the two or three witnesses? Who has tested this with you and found it sound? Without witnesses, the claim is solo and waits.",
        "eliminates": "Solo claims no one else has tested. They aren't false — they wait, unestablished, until two or three witnesses confirm.",
    },
    {
        "gate": "GOD",
        "scripture": "Psalm 27:14",
        "scripture_text": "Wait on the LORD: be of good courage, and He shall strengthen thine heart: wait, I say, on the LORD.",
        "question": "Have you waited? Is there peace? Acting before God has confirmed is the most common failure. If you cannot wait, you do not yet trust.",
        "eliminates": "Anything acted on without waiting for peace — haste that outran trust. The last and most common place a true path is still lost.",
    },
]


def four_gates_walk() -> List[Dict[str, Any]]:
    """Return the four-gate walk. Static structure — the user answers
    each gate themselves. Engine never answers for them."""
    return [dict(g) for g in _FOUR_GATES]


# ── Almanac loading (mtime-cached) ─────────────────────────────────────

def _load_almanac() -> List[Dict[str, Any]]:
    """mtime-cached almanac entries load. Same pattern as protocols."""
    if not _ALMANAC_FILE.exists():
        return []
    try:
        mtime = _ALMANAC_FILE.stat().st_mtime
    except OSError:
        return []
    if _ALMANAC_CACHE["items"] and mtime <= _ALMANAC_CACHE["mtime"]:
        return _ALMANAC_CACHE["items"]
    items = _substrate.read_jsonl(_ALMANAC_FILE)
    _ALMANAC_CACHE["mtime"] = mtime
    _ALMANAC_CACHE["items"] = items
    return items


# ── Axis derivation ────────────────────────────────────────────────────

def derive_axes(
    situation: str,
    archetypes_result: Optional[Dict[str, Any]] = None,
    protocols_result: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """Derive the engine's 7-axis dimensional fingerprint of a situation.

    Walks three signals in order of confidence:
      1. recognized archetype categories  → category→axes map
      2. recognized Scripture protocols   → protocol→axes map
      3. keyword regex fallback           → keyword→axes map

    Returns a deduplicated list of axes. No LLM. Offline. Deterministic.
    """
    axes: Set[str] = set()

    # 1. From archetype categories (highest signal)
    if archetypes_result and archetypes_result.get("candidates"):
        for cand in archetypes_result["candidates"]:
            cat = (cand.get("category") or "").lower().strip()
            if cat and cat in _CATEGORY_AXIS_MAP:
                axes.update(_CATEGORY_AXIS_MAP[cat])
        # Also pull from the combination signature's categories
        combo = archetypes_result.get("combination") or {}
        for cat in (combo.get("categories") or []):
            cat = (cat or "").lower().strip()
            if cat and cat in _CATEGORY_AXIS_MAP:
                axes.update(_CATEGORY_AXIS_MAP[cat])

    # 2. From matched Scripture protocols
    if protocols_result:
        for proto in protocols_result:
            pid = (proto.get("id") or "").strip()
            if pid in _PROTOCOL_AXIS_MAP:
                axes.update(_PROTOCOL_AXIS_MAP[pid])

    # 3. Keyword fallback — only consult if signals 1+2 gave nothing
    if not axes:
        lower = (situation or "").lower()
        for pattern, ax_list in _KEYWORD_AXIS_HITS:
            if re.search(pattern, lower):
                axes.update(ax_list)

    return sorted(axes)


# ── Precedent retrieval ────────────────────────────────────────────────

def _jaccard(a: Set[str], b: Set[str]) -> float:
    """Delegate to the one canonical jaccard (api/substrate.jaccard)."""
    return _substrate.jaccard(a, b)


def _extract_scripture_refs(text: str) -> Set[str]:
    """Normalize Scripture-reference tokens out of text.

    Picks up patterns like 'Matthew 18:15', 'Deut 19', 'Galatians 6:7',
    'Proverbs 27:6', 'Ps 27', '1 John 4:1', and bare book names
    in the trigger lists. Returned tokens are lower-cased book names
    only (no chapter), so 'Matthew 18:15' and 'Matthew 7' both match
    when a protocol cites either of those refs.
    """
    if not text:
        return set()
    out: Set[str] = set()
    # Standard book references with optional chapter:verse
    pattern = re.compile(
        r"\b(?:1\s+|2\s+|3\s+)?(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Deut|"
        r"Joshua|Judges|Ruth|Samuel|Sam|Kings|Chronicles|Chron|Ezra|Nehemiah|Esther|"
        r"Job|Psalms?|Ps|Proverbs|Prov|Ecclesiastes|Eccl|Song|Isaiah|Is|Jeremiah|Jer|"
        r"Lamentations|Lam|Ezekiel|Ezek|Daniel|Dan|Hosea|Joel|Amos|Obadiah|Obad|Jonah|"
        r"Micah|Nahum|Habakkuk|Hab|Zephaniah|Zeph|Haggai|Hag|Zechariah|Zech|Malachi|Mal|"
        r"Matthew|Mt|Mark|Mk|Luke|Lk|John|Jn|Acts|Romans|Rom|Corinthians|Cor|"
        r"Galatians|Gal|Ephesians|Eph|Philippians|Phil|Colossians|Col|Thessalonians|Thess|"
        r"Timothy|Tim|Titus|Philemon|Hebrews|Heb|James|Jas|Peter|Pet|Jude|Revelation|Rev)\b"
        r"(?:\s*\d+(?::\d+(?:-\d+)?)?)?",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        out.add(m.group(0).strip().lower())
    return out


def find_almanac_precedent(
    axes: List[str],
    situation: str = "",
    protocol_scriptures: Optional[List[str]] = None,
    min_score: float = 0.20,
) -> Optional[Dict[str, Any]]:
    """Walk the almanac for the closest entry by Jaccard on axes,
    with bonuses for trigger-keyword overlap and Scripture resonance
    with any matched Scripture protocol.

    Returns the closest entry (with `match` metadata) or None.
    """
    if not axes and not situation:
        return None
    pred_axes = set(axes)
    sit_lower = (situation or "").lower()
    entries = _load_almanac()
    if not entries:
        return None

    # Normalize protocol scriptures into book-name tokens for resonance.
    proto_books: Set[str] = set()
    if protocol_scriptures:
        for ref in protocol_scriptures:
            for tok in _extract_scripture_refs(ref):
                # Drop trailing chapter/verse — keep just the book token
                book = re.split(r"\s+\d", tok, maxsplit=1)[0].strip()
                if book:
                    proto_books.add(book)

    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for e in entries:
        e_axes = set(e.get("axes") or [])
        ax_score = _jaccard(pred_axes, e_axes)

        # Trigger keyword bonus: each trigger word found in the situation
        # adds a small amount. Cap so axes stay dominant.
        kw_bonus = 0.0
        triggers = (e.get("triggers") or {}).get("keywords") or []
        if sit_lower and triggers:
            hits = 0
            for kw in triggers:
                kw_l = (kw or "").lower().strip()
                if kw_l and len(kw_l) >= 3 and kw_l in sit_lower:
                    hits += 1
            if hits:
                kw_bonus = min(0.20, hits * 0.05)

        # Scripture resonance bonus: if a Scripture protocol matched
        # and this entry's title, wisdom, triggers, or category mention
        # the same book(s), boost the entry. This is what aligns the
        # Matthew-18 walk to the "two or three witnesses" entry — both
        # cite Deuteronomy 19 / Matthew 18.
        scr_bonus = 0.0
        if proto_books:
            haystack_parts = [
                e.get("title", ""),
                e.get("situation", ""),
                e.get("wisdom", ""),
                e.get("category", ""),
                " ".join(triggers),
                " ".join(e.get("scripture", []) or []),
            ]
            haystack = " ".join(haystack_parts).lower()
            entry_books = _extract_scripture_refs(haystack)
            # Reduce to book-only tokens
            entry_book_names = {re.split(r"\s+\d", t, maxsplit=1)[0].strip() for t in entry_books}
            resonant = proto_books & entry_book_names
            if resonant:
                # Strong bonus — Scripture resonance is high-confidence
                scr_bonus = min(0.35, len(resonant) * 0.20)

        score = ax_score + kw_bonus + scr_bonus
        if score > best_score:
            best_score = score
            best = e

    if not best or best_score < min_score:
        return None

    title = best.get("title") or best.get("situation") or ""
    # Normalize score to [0, 1] for display. Internal scoring stacks
    # axis Jaccard (≤1) + kw bonus (≤0.20) + scripture bonus (≤0.35),
    # so the natural ceiling is 1.55. Divide for a cleaner UI number.
    display_score = min(1.0, best_score / 1.55)
    return {
        "source": "almanac",
        "id": best.get("id"),
        "kind": best.get("kind"),
        "title": title,
        "category": best.get("category"),
        "verdict": best.get("verdict"),
        "wisdom": best.get("wisdom", ""),
        "scripture": best.get("scripture", []),
        "axes": sorted(best.get("axes") or []),
        "shared_axes": sorted(pred_axes & set(best.get("axes") or [])),
        "match_score": round(display_score, 3),
        "match_score_raw": round(best_score, 3),
    }


def find_sealed_precedent(axes: List[str]) -> Optional[Dict[str, Any]]:
    """Walk the sealed polymathic axis_index for the closest record."""
    if not axes:
        return None
    try:
        from concordance_engine.axis_index import find_closest as _find_closest
    except Exception:
        return None
    prec = _find_closest(axes, min_score=0.15)
    if not prec:
        return None
    return {
        "source": "sealed_polymathic",
        "hash": prec.get("hash"),
        "summary": prec.get("summary", ""),
        "verdict": prec.get("verdict"),
        "sealed_at": prec.get("sealed_at"),
        "axes": sorted(prec.get("dims") or []),
        "shared_axes": sorted(prec.get("shared_dims") or []),
        "match_score": prec.get("jaccard_score"),
    }


def find_precedent(
    situation: str,
    archetypes_result: Optional[Dict[str, Any]] = None,
    protocols_result: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Find the closest precedent for a situation across both stores.

    Strategy:
      - Sealed polymathic records win on tie (they are user-curated +
        signed). When no sealed precedent exists, the almanac fills in.
      - Returns the single best match with axis fingerprint, score,
        and the wisdom/summary the engine surfaces.
    """
    axes = derive_axes(situation, archetypes_result, protocols_result)
    if not axes:
        return None

    # Collect Scripture references from matched protocols — these are
    # high-confidence resonance signals when looking up the almanac.
    proto_scriptures: List[str] = []
    if protocols_result:
        for proto in protocols_result:
            for s in (proto.get("scripture") or []):
                proto_scriptures.append(s)

    sealed = find_sealed_precedent(axes)
    almanac = find_almanac_precedent(
        axes, situation=situation, protocol_scriptures=proto_scriptures
    )

    # Prefer sealed when it exists AND scores comparably to almanac
    if sealed and almanac:
        if (sealed.get("match_score") or 0) + 0.05 >= (almanac.get("match_score") or 0):
            sealed["derived_axes"] = axes
            return sealed
        almanac["derived_axes"] = axes
        return almanac
    if sealed:
        sealed["derived_axes"] = axes
        return sealed
    if almanac:
        almanac["derived_axes"] = axes
        return almanac
    return None


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
        "axes": [],
        "the_walk": four_gates_walk(),
        "notes": [],
    }

    archetype_result: Optional[Dict[str, Any]] = None

    # 1. Pattern recognition (archetypes)
    try:
        from api import archetypes as _archetypes
        archetype_result = _archetypes.recognize(situation, top_k=3)
        if archetype_result.get("candidates"):
            out["patterns"] = {
                "combination": archetype_result.get("combination"),
                "candidates": archetype_result.get("candidates", [])[:3],
                "note": archetype_result.get("note"),
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

    # 4. Axis fingerprint + closest precedent.
    #    Walks both the sealed polymathic axis_index AND the almanac;
    #    returns the single best match. The user sees the closest
    #    already-walked case overlaid on their situation — that is
    #    the "closest-case overlay" thesis in practice.
    try:
        out["axes"] = derive_axes(situation, archetype_result, out["protocols"])
        prec = find_precedent(situation, archetype_result, out["protocols"])
        if prec:
            out["precedent"] = prec
    except Exception as exc:
        out["notes"].append(f"precedent retrieval unavailable: {str(exc)[:120]}")

    # 5. Optional fused-mode: when the situation contains atomic
    #    factual claims (numbers, equations, named formulas), detect
    #    them and surface a pointer that the caller can fire
    #    /polymathic against. The walk does NOT run the polymathic
    #    pass itself — that's expensive — but it tells the caller
    #    whether it's worth firing. The Coach UI fires /polymathic
    #    in parallel when out["atomic_claims_detected"] is non-empty.
    out["atomic_claims_detected"] = _detect_atomic_signals(situation)

    if include_polymathic:
        out["notes"].append(
            "for atomic-claim verification of any specific factual statements in "
            "the situation, run them through /run or /polymathic separately."
        )

    return out


def _detect_atomic_signals(situation: str) -> List[Dict[str, Any]]:
    """Detect signals that a polymathic verifier could engage.

    Returns a list of {kind, excerpt} dicts describing each signal:
      - "number_unit"   : numeric value with a unit (e.g. "6%", "50,000 dollars", "30 minutes")
      - "equation"      : equality with at least one operator
      - "named_formula" : a known formula name (F=ma, E=mc^2, p-value, etc.)
      - "named_quantity": a known scientific quantity ("half-life", "molar mass", etc.)

    The list being non-empty is what triggers the Coach UI to fire
    /polymathic in parallel. No verifier work happens here — pure
    pattern recognition.
    """
    if not situation:
        return []
    signals: List[Dict[str, Any]] = []
    text = situation

    # Currency amounts: $50,000 or $50,000.00
    for m in re.finditer(r"\$\s?[\d,]+(?:\.\d+)?", text):
        signals.append({"kind": "number_unit", "excerpt": m.group(0).strip()})
        if len(signals) >= 8:
            break

    # Percent: 6% or 6 percent
    for m in re.finditer(r"\d+(?:\.\d+)?\s?(?:%|percent\b)", text, re.IGNORECASE):
        signals.append({"kind": "number_unit", "excerpt": m.group(0).strip()})
        if len(signals) >= 8:
            break

    # Number with a unit word (scientific or time)
    unit_word = (
        r"(?:kilograms?|grams?|meters?|kilometers?|centimeters?|millimeters?|"
        r"seconds?|minutes?|hours?|days?|weeks?|months?|years?|"
        r"newtons?|joules?|watts?|hertz|liters?|litres?|gallons?|moles?|"
        r"kelvin|celsius|fahrenheit|"
        r"dollars?|cents?|euros?|pounds?|degrees?)"
    )
    for m in re.finditer(rf"\b\d+(?:\.\d+)?\s+{unit_word}\b", text, re.IGNORECASE):
        signals.append({"kind": "number_unit", "excerpt": m.group(0).strip()})
        if len(signals) >= 8:
            break

    # Short SI unit symbols after a number (kg, m, s, J, N, K)
    for m in re.finditer(r"\b\d+(?:\.\d+)?\s?(?:kg|km|cm|mm|°C|°F|°)\b", text):
        signals.append({"kind": "number_unit", "excerpt": m.group(0).strip()})
        if len(signals) >= 8:
            break

    # Equation: anything with an = sign and at least one operator or variable on each side
    eq = re.search(r"\b([A-Za-z]\w*)\s*=\s*([A-Za-z0-9.+\-*/^()\s]{2,30})\b", text)
    if eq:
        signals.append({"kind": "equation", "excerpt": eq.group(0).strip()})

    # Named formulas / quantities
    named_patterns = [
        (r"\bF\s*=\s*m\s*[*x×·]?\s*a\b",   "named_formula"),
        (r"\bE\s*=\s*m\s*c\^?2\b",         "named_formula"),
        (r"\bp[-\s]?value\b",              "named_quantity"),
        (r"\bhalf[-\s]?life\b",            "named_quantity"),
        (r"\bmolar\s+mass\b",              "named_quantity"),
        (r"\bcompound\s+interest\b",       "named_quantity"),
        (r"\bsimple\s+interest\b",         "named_quantity"),
        (r"\bbalance(?:d)?\s+(?:equation|chemical)\b", "named_quantity"),
        (r"\baccounting\s+identity\b",     "named_quantity"),
        (r"\bcarnot\s+efficiency\b",       "named_quantity"),
        (r"\bhardy[-\s]?weinberg\b",       "named_quantity"),
    ]
    for pat, kind in named_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            signals.append({"kind": kind, "excerpt": m.group(0)})

    # Deduplicate by excerpt
    seen = set()
    out: List[Dict[str, Any]] = []
    for s in signals:
        key = s["excerpt"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:10]
