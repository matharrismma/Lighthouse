"""Classify a card's witnesses into INDEPENDENT external corroboration vs
INHERITED / structural support.

Why this exists (Principle B — never launder the unverifiable):
A card can pass the witness gate by *inheriting* its parents' witnesses
("inherited from 2 parent cards"). That is structural lineage, not an independent
mouth. Deuteronomy 19:15 establishment requires >=2 DISTINCT INDEPENDENT witness
classes. If the UI renders an inherited witness under the same "Witnesses
(Deuteronomy 19:15)" heading as a manuscript tradition or a critical edition, it
launders structure as independent corroboration. This module is the ONE place
that draws the line, so every surface (SSR card page, JSON, future codex trail)
draws it the same way.

`established` is the strong claim: it is True only when >=2 distinct INDEPENDENT
classes are present. Inherited / self / unrecognized classes never count toward
it. The engine never confirms itself.
"""
from __future__ import annotations
from typing import Any, Dict, List

# Genuine INDEPENDENT external corroboration — distinct mouths outside the engine.
INDEPENDENT_CLASSES = {
    "manuscript_tradition",   # the text's own transmission witnesses
    "critical_edition",       # a scholarly edition with apparatus
    "translation",            # an independent rendering tradition
    "republication",          # an independent republisher (Gutenberg, a press)
    "citation_tradition",     # secondary scholarship that cites the work
    "non_government_archive", # an archive that is not the work's own publisher/state
    "peer_review",            # independent expert review
    "operator_signature",     # the operator's signed attestation (a named human)
    "proof_text",             # an external Scripture anchor the card rests on
}

# Structural / non-independent — cannot, alone, establish anything.
STRUCTURAL_CLASSES = {
    "inherited",  # rests on parent cards' witnesses (lineage, not a new mouth)
    "self",       # the engine confirming itself (forbidden as establishment)
}


def _cls(w: Dict[str, Any]) -> str:
    return (w.get("class") or "").strip().lower()


def classify_witnesses(card: Dict[str, Any]) -> Dict[str, Any]:
    """Split a card's witnesses and judge establishment honestly.

    Returns:
      independent  — witnesses that are genuine external corroboration
      structural   — inherited / self witnesses (lineage, not independent)
      other        — witnesses whose class is unrecognized (shown, never counted)
      distinct_independent_classes — sorted unique independent class names
      established  — True iff >=2 distinct INDEPENDENT classes (Deut 19:15)
      inherited_only — passed/standing only on structural witnesses
    """
    ws = card.get("witnesses") or []
    independent: List[Dict[str, Any]] = []
    structural: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for w in ws:
        if not isinstance(w, dict):
            continue
        cl = _cls(w)
        if cl in INDEPENDENT_CLASSES:
            independent.append(w)
        elif cl in STRUCTURAL_CLASSES:
            structural.append(w)
        else:
            other.append(w)
    distinct = sorted({_cls(w) for w in independent})
    return {
        "independent": independent,
        "structural": structural,
        "other": other,
        "distinct_independent_classes": distinct,
        "established": len(distinct) >= 2,
        "inherited_only": (not independent and bool(structural)),
    }
