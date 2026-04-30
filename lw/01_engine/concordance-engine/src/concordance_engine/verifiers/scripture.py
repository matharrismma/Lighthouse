"""
verifiers/scripture.py — Scripture reference resolver and anchor verifier.

Wires the Layer 0 WORD source (lw/00_source/) into the engine.
Resolves Entry.refs strings ("Jn3:16", "Pr4:23") to WEB text + Strong's definitions,
and verifies that any scripture_anchors declared in a governance packet are genuine
references rather than fabrications.

Usage (standalone):
    from concordance_engine.verifiers.scripture import (
        resolve_ref, verify_scripture_anchors, word_study
    )
    resolve_ref("Jn3:16")        # → {ref, web_text, status}
    word_study("G26")            # → agape definition + all verses
    verify_scripture_anchors(["Prov 22:16", "Mic 6:8"])  # → VerifierResult

Engine integration:
    Packets that include scripture_anchors (typically governance packets with
    DECISION_PACKET.scripture_anchors) automatically have their refs resolved.
    Any ref that cannot be found in the WEB is flagged as a drift risk.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import VerifierResult

# ---------------------------------------------------------------------------
# Locate lw/00_source relative to this file
# ---------------------------------------------------------------------------

_ENGINE_SRC = Path(__file__).parent.parent.parent.parent  # .../lw/01_engine/concordance-engine/src
_LW_ROOT    = _ENGINE_SRC.parent.parent                    # .../lw
_SOURCE_DIR = _LW_ROOT / "00_source"

def _get_source_layer():
    """Lazy-load SourceLayer from lw/00_source/triangulation/lookup.py."""
    src_str = str(_SOURCE_DIR)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    try:
        from triangulation.lookup import SourceLayer
        return SourceLayer()
    except Exception:
        return None

def _get_concordance():
    """Lazy-load Concordance from lw/00_source/triangulation/concordance.py."""
    src_str = str(_SOURCE_DIR)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    try:
        from triangulation.concordance import Concordance
        return Concordance()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_ref(ref: str) -> Dict[str, Any]:
    """
    Resolve a scripture reference string to WEB text and Strong's data.

    Accepts: "Jn3:16", "John 3:16", "Pr4:23", "Gen1:1", "1Co13:4", etc.

    Returns:
        {
            "ref": str,              # normalized form
            "web_text": str,         # WEB verse text (empty if not found)
            "status": "ok" | "not_found" | "source_missing",
            "detail": str,
        }
    """
    layer = _get_source_layer()
    if layer is None:
        return {
            "ref": ref, "web_text": "", "status": "source_missing",
            "detail": "Run lw/00_source/fetch_sources.py to build the WEB database."
        }
    result = layer.lookup(ref)
    return result


def word_study(strongs_num: str) -> Dict[str, Any]:
    """
    Complete word study: definition + all verses where the word appears.

    strongs_num: "G26" (agape), "H2617" (chesed), etc.

    Returns dict from Concordance.word_study() including:
        word, transliteration, definition, derivation, verses, occurrence_count
    """
    conc = _get_concordance()
    if conc is None:
        return {"strongs": strongs_num, "status": "source_missing",
                "detail": "Run lw/00_source/fetch_sources.py first."}
    return conc.word_study(strongs_num)


def verify_scripture_anchors(anchors: List[str]) -> VerifierResult:
    """
    Verify that each scripture reference in anchors resolves to a real WEB verse.

    Used by the governance verifier to ensure DECISION_PACKET.scripture_anchors
    cite genuine references rather than invented ones.

    Returns CONFIRMED if all resolve, MISMATCH if any fail, ERROR if source missing.
    """
    name = "scripture.anchors"
    if not anchors:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="No scripture anchors to verify.")

    layer = _get_source_layer()
    if layer is None:
        return VerifierResult(name=name, status="SKIPPED",
                              detail="WEB source not available — run fetch_sources.py to enable anchor verification.",
                              data={"anchors": anchors})

    resolved = []
    failed = []
    for ref in anchors:
        result = layer.lookup(ref)
        if result.get("status") == "ok" and result.get("web_text"):
            resolved.append({"ref": ref, "text": result["web_text"][:120]})
        else:
            failed.append(ref)

    data = {"resolved": resolved, "failed": failed, "total": len(anchors)}
    if not failed:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail=f"All {len(anchors)} scripture anchor(s) resolved in WEB.",
            data=data
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=f"{len(failed)} anchor(s) not found in WEB: {failed}. "
               f"Verify references are genuine before citing them.",
        data=data
    )


def run(packet: dict) -> list:
    """
    Run scripture verification for refs in a packet.
    Called by the engine for packets that contain scripture_anchors.
    """
    results = []

    # Governance DECISION_PACKET.scripture_anchors
    dp = packet.get("DECISION_PACKET") or {}
    anchors = dp.get("scripture_anchors") or packet.get("scripture_anchors") or []
    if anchors:
        results.append(verify_scripture_anchors(list(anchors)))

    # Kernel entry refs (Entry.refs list, e.g. ["Jn15:2", "Pr4:23"])
    refs = packet.get("refs") or []
    if refs:
        vr = verify_scripture_anchors(list(refs))
        # Rename for clarity
        vr.name = "scripture.entry_refs"
        results.append(vr)

    return results
