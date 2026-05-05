"""Scripture retrieval module — Layer 1 of the standalone model.

Connects to the indexed Scripture database (WEB text + Strong's concordance,
360,652 occurrences across both testaments) and returns ranked passages
for a given question type and gate.

This is the retrieval layer, not the reasoning layer. The path composer
reads what is returned here and reasons from it. The retrieval module
never interprets; it surfaces.

Phase 1 (now): curated territory anchors per question type + WEB text fetch.
Phase 2 (when corpus has depth): add vector similarity over LSP chunks.

Architecture:
  - Primary sources: lw/00_source/web/web.db (WEB text) and
    lw/00_source/web/concordance.db (Strong's cross-reference)
  - Access via: src/concordance_engine/verifiers/scripture.resolve_ref()
  - Degrades gracefully when Layer 0 source not provisioned (returns
    references without text rather than erroring)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .classifier import (
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
    TERRITORY_MAP,
)

# ── Data types ─────────────────────────────────────────────────────────

@dataclass
class ScripturePassage:
    """A single Scripture passage returned by the retrieval module."""
    ref: str
    text: str                   # WEB verse text ("" if source not provisioned)
    weight: float               # relevance score [0.0, 1.0]
    reason: str                 # why this is load-bearing for the question type
    gate: str                   # which gate this passage primarily informs
    status: str = "ok"          # "ok" | "not_found" | "source_missing"

    def to_dict(self) -> dict:
        return {
            "ref": self.ref,
            "text": self.text,
            "weight": round(self.weight, 4),
            "reason": self.reason,
            "gate": self.gate,
            "status": self.status,
        }


@dataclass
class RetrievalResult:
    """Output of retrieve()."""
    question_type: str
    primary: Optional[ScripturePassage]         # highest-weight passage
    supporting: list[ScripturePassage]          # additional passages
    gate: str                                   # gate these passages address
    territory: list[str]                        # book territory searched
    source_available: bool = True               # False if WEB DB not provisioned

    @property
    def all_passages(self) -> list[ScripturePassage]:
        out = []
        if self.primary:
            out.append(self.primary)
        out.extend(self.supporting)
        return out

    def to_dict(self) -> dict:
        return {
            "question_type": self.question_type,
            "gate": self.gate,
            "territory": self.territory,
            "primary": self.primary.to_dict() if self.primary else None,
            "supporting": [p.to_dict() for p in self.supporting],
            "source_available": self.source_available,
        }


# ── Territory anchors ──────────────────────────────────────────────────
# Curated load-bearing references per question type. These are the
# passages the spec identifies as primary territory. Each entry is:
#   (ref, weight, reason, gate)
#
# Weight 1.0 = primary anchor (most load-bearing for this type)
# Weight 0.7 = supporting anchor
# Weight 0.5 = contextual anchor

_ANCHORS: dict[str, list[tuple[str, float, str, str]]] = {

    WISDOM: [
        ("Proverbs 2:6",   1.0, "Wisdom comes from God; the starting point is the source", "FLOOR"),
        ("James 1:5",      0.9, "Ask God for wisdom; it is given generously", "FLOOR"),
        ("Proverbs 3:5-6", 0.8, "Trust God's understanding over your own; He directs the path", "FLOOR"),
        ("Matthew 7:24",   0.7, "Wisdom is enacted, not merely observed — build on the rock", "FLOOR"),
        ("Ecclesiastes 3:11", 0.6, "God makes everything beautiful in its time; wisdom includes timing", "FLOOR"),
    ],

    DOCTRINE: [
        ("Romans 3:23",    1.0, "All have sinned; the universal condition that doctrine addresses", "RED"),
        ("Hebrews 4:12",   0.9, "Scripture is living and active; the authority test for doctrine", "RED"),
        ("John 1:1",       0.8, "The Word was God; the foundational Christological claim", "RED"),
        ("Ephesians 2:8-9",0.7, "Saved by grace through faith, not works; the gate test for grace claims", "RED"),
        ("2 Timothy 3:16", 0.6, "All Scripture is God-breathed; the authority anchor", "RED"),
    ],

    DECISION: [
        ("Proverbs 11:14", 1.0, "In the multitude of counselors there is safety; BROTHERS gate", "BROTHERS"),
        ("Psalms 37:4-5",  0.9, "Commit your way to the Lord; trust and He will act", "GOD"),
        ("Proverbs 16:9",  0.8, "The heart plans, God directs; the steps are not ours alone", "GOD"),
        ("Acts 15:28",     0.7, "Decisions made by the community in alignment with the Spirit", "BROTHERS"),
        ("James 1:5",      0.6, "Ask for wisdom before deciding; the pre-gate posture", "FLOOR"),
    ],

    RELATIONAL: [
        ("Matthew 18:15",  1.0, "Go to the person directly first; the confrontation order", "BROTHERS"),
        ("Romans 12:18",   0.9, "As much as possible, live at peace with everyone", "BROTHERS"),
        ("1 Corinthians 13:4-7", 0.8, "Love is patient, love is kind; the character standard", "BROTHERS"),
        ("Ephesians 4:29", 0.7, "Only words that build up; the speech standard", "BROTHERS"),
        ("Matthew 5:23-24",0.6, "Reconcile before you bring your offering; priority of relationship", "BROTHERS"),
    ],

    RESOURCE: [
        ("Proverbs 3:9-10",1.0, "Honor the Lord with your wealth; firstfruits principle", "FLOOR"),
        ("Luke 16:13",     0.9, "You cannot serve God and money; the loyalty test", "FLOOR"),
        ("2 Corinthians 9:7", 0.8, "God loves a cheerful giver; the heart posture for giving", "FLOOR"),
        ("Deuteronomy 8:18",0.7, "God gives the ability to produce wealth; stewardship not ownership", "FLOOR"),
        ("Matthew 6:33",   0.6, "Seek first the kingdom; resources follow alignment", "FLOOR"),
    ],

    TIMING: [
        ("Ecclesiastes 3:1",1.0, "There is a time for every purpose; timing is God's domain", "GOD"),
        ("Habakkuk 2:3",   0.9, "The vision awaits its appointed time; wait for it", "GOD"),
        ("Psalms 27:14",   0.8, "Wait on the Lord; be strong and courageous in waiting", "GOD"),
        ("Acts 1:7",       0.7, "Times and seasons are the Father's authority alone", "GOD"),
        ("Isaiah 40:31",   0.6, "Those who wait on the Lord renew their strength", "GOD"),
    ],

    FORMATION: [
        ("Romans 12:2",    1.0, "Be transformed by the renewing of your mind; the formation anchor", "ALL"),
        ("Philippians 4:11",0.9, "Contentment is learned; formation is a process not an event", "ALL"),
        ("Galatians 5:22-23",0.8, "The fruit of the Spirit is the formation outcome", "ALL"),
        ("1 John 1:9",     0.7, "Confession and cleansing; the repeated cycle of formation", "ALL"),
        ("Hebrews 12:11",  0.6, "Discipline yields the peaceful fruit of righteousness", "ALL"),
    ],

    CRISIS: [
        ("Psalms 34:18",   1.0, "The Lord is near the brokenhearted; the presence promise", "RED"),
        ("Isaiah 40:31",   0.9, "Those who wait on the Lord renew their strength", "FLOOR"),
        ("Lamentations 3:22-23", 0.8, "His mercies are new every morning; the faithfulness anchor", "FLOOR"),
        ("Psalms 46:1",    0.7, "God is our refuge and strength, a very present help in trouble", "RED"),
        ("Romans 8:38-39", 0.6, "Nothing can separate us from the love of God; the anchor in collapse", "RED"),
    ],

    HISTORICAL: [
        ("2 Timothy 3:16-17",1.0, "All Scripture is profitable for instruction; the purpose of historical texts", "RED"),
        ("Romans 15:4",    0.9, "Things written before were for our instruction and encouragement", "RED"),
        ("1 Corinthians 10:11", 0.8, "These things happened as examples for us", "RED"),
        ("Hebrews 11:1-2", 0.7, "By faith the elders received commendation; the historical witness", "RED"),
        ("Acts 17:26",     0.6, "God determined the times and boundaries of peoples; history has a purpose", "RED"),
    ],
}

# ── Reference extractor ────────────────────────────────────────────────
# Finds explicit Scripture references in submission text so they can be
# resolved and included in the retrieval result.

_REF_PATTERN = re.compile(
    r"\b(?:1|2|3|I|II|III)?\s*"
    r"(?:Gen(?:esis)?|Exod(?:us)?|Lev(?:iticus)?|Num(?:bers)?|Deut(?:eronomy)?|"
    r"Josh(?:ua)?|Judg(?:es)?|Ruth|Sam(?:uel)?|K(?:gs?|ings?)|Chr(?:on(?:icles?)?)?|"
    r"Ezr(?:a)?|Neh(?:emiah)?|Est(?:her)?|Job|Ps(?:alm)?s?|Prov(?:erbs?)?|"
    r"Eccl(?:es(?:iastes)?)?|Song|Isa(?:iah)?|Jer(?:emiah)?|Lam(?:entations?)?|"
    r"Ezek(?:iel)?|Dan(?:iel)?|Hos(?:ea)?|Joel|Amos|Obad(?:iah)?|Jon(?:ah)?|"
    r"Mic(?:ah)?|Nah(?:um)?|Hab(?:akkuk)?|Zeph(?:aniah)?|Hag(?:gai)?|"
    r"Zech(?:ariah)?|Mal(?:achi)?|"
    r"Matt(?:hew)?|Mar(?:k)?|Luke?|John?|Acts|"
    r"Romans?|Cor(?:inthians?)?|Gal(?:atians?)?|Eph(?:esians?)?|"
    r"Phil(?:ippians?)?|Col(?:ossians?)?|Thess?(?:alonians?)?|Tim(?:othy)?|"
    r"Tit(?:us)?|Phlm?|Heb(?:rews?)?|Jas(?:es?)?|Pet(?:er)?|Jude|Rev(?:elation)?)"
    r"\s*\d+(?::\d+(?:-\d+)?)?\b",
    re.IGNORECASE,
)


def _extract_refs(text: str) -> list[str]:
    """Extract Scripture references explicitly mentioned in the submission."""
    return _REF_PATTERN.findall(text)


# ── Resolver ───────────────────────────────────────────────────────────

def _resolve(ref: str, weight: float, reason: str, gate: str) -> ScripturePassage:
    """Resolve a reference string to a ScripturePassage via the existing verifier."""
    try:
        from .verifiers.scripture import resolve_ref as _r
        result = _r(ref)
        return ScripturePassage(
            ref=result.get("ref", ref),
            text=result.get("web_text", ""),
            weight=weight,
            reason=reason,
            gate=gate,
            status=result.get("status", "ok"),
        )
    except Exception:
        return ScripturePassage(
            ref=ref,
            text="",
            weight=weight,
            reason=reason,
            gate=gate,
            status="source_missing",
        )


# ── Public API ─────────────────────────────────────────────────────────

def retrieve(
    question_type: str,
    text: str = "",
    limit: int = 5,
) -> RetrievalResult:
    """Retrieve load-bearing Scripture passages for a question type.

    Args:
        question_type: One of the nine classifier types.
        text:          The raw user submission (for inline ref extraction).
        limit:         Maximum passages to return (primary + supporting combined).

    Returns:
        RetrievalResult with primary anchor + supporting passages.
    """
    anchors = _ANCHORS.get(question_type, _ANCHORS[WISDOM])
    gate = anchors[0][3] if anchors else "FLOOR"

    # Resolve territory anchors (up to limit).
    passages: list[ScripturePassage] = []
    source_available = True
    for ref, weight, reason, gate_label in anchors[:limit]:
        p = _resolve(ref, weight, reason, gate_label)
        if p.status == "source_missing":
            source_available = False
        passages.append(p)

    # Add any references explicitly mentioned in the submission text,
    # resolved against the WEB. These get moderate weight since they are
    # user-supplied, not territory-curated.
    if text:
        inline_refs = _extract_refs(text)
        for inline_ref in inline_refs[:3]:   # cap inline refs at 3
            p = _resolve(inline_ref, 0.5, "Explicitly referenced in submission", gate)
            if p.ref not in {x.ref for x in passages}:
                passages.append(p)

    # Sort descending by weight; pick primary.
    passages.sort(key=lambda p: p.weight, reverse=True)
    primary = passages[0] if passages else None
    supporting = passages[1:limit]

    return RetrievalResult(
        question_type=question_type,
        primary=primary,
        supporting=supporting,
        gate=gate,
        territory=TERRITORY_MAP.get(question_type, []),
        source_available=source_available,
    )


def primary_anchor(question_type: str) -> str:
    """Return just the primary reference for a question type (no DB lookup).

    Useful for surfaces that need the reference string without the full
    retrieval pipeline.
    """
    anchors = _ANCHORS.get(question_type, _ANCHORS[WISDOM])
    return anchors[0][0] if anchors else "Proverbs 2:6"
