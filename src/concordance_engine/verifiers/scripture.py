"""
verifiers/scripture.py — Scripture reference resolver and anchor verifier.

Wires the Layer 0 WORD source (lw/00_source/) into the engine. Resolves
reference strings ("Jn3:16", "Pr4:23") to WEB text and Strong's data, and
verifies that any scripture_anchors declared in a packet are genuine
references rather than fabrications.

Layer 0 architecture:
- Hebrew OT  — Westminster Leningrad Codex (morphhb, OSIS XML)
- Greek NT   — MorphGNT (morphologically tagged Greek NT)
- Bridge     — Strong's lexicon (H1-H8674 / G1-G5624)
- English    — World English Bible (WEB), public domain

The data files live under lw/00_source/ and are populated by running
`python lw/00_source/fetch_sources.py` once. They are gitignored because
they are large; this verifier degrades gracefully (returns SKIPPED, not
ERROR) when the data is not present, so a fresh clone of the engine
package can run without the WEB database.

Usage (standalone):
    from concordance_engine.verifiers.scripture import (
        resolve_ref, verify_scripture_anchors, word_study
    )
    resolve_ref("Jn3:16")        # → {ref, web_text, status}
    word_study("G26")            # → agape definition + all verses
    verify_scripture_anchors(["Prov 22:16", "Mic 6:8"])  # → VerifierResult

Engine integration:
    The engine's run-for-domain pipeline calls scripture.run(packet) on
    every packet (regardless of domain) so that any packet carrying
    scripture_anchors or kernel-style refs gets them verified against
    the WEB. A packet without scripture references gets a no-op pass.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import VerifierResult

# ---------------------------------------------------------------------------
# Locate lw/00_source from the canonical top-level engine.
# ---------------------------------------------------------------------------
# This file lives at:   <repo>/src/concordance_engine/verifiers/scripture.py
# We need:              <repo>/lw/00_source/
# So go up four parents (verifiers/, concordance_engine/, src/, repo) and
# then descend into lw/00_source.
_REPO_ROOT  = Path(__file__).resolve().parent.parent.parent.parent
_SOURCE_DIR = _REPO_ROOT / "lw" / "00_source"


def _get_source_layer():
    """Lazy-load SourceLayer from lw/00_source/triangulation/lookup.py.

    Returns None if the data has not been provisioned. Callers must handle
    None and degrade to SKIPPED rather than crashing.
    """
    src_str = str(_SOURCE_DIR)
    if not _SOURCE_DIR.is_dir():
        return None
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    try:
        from triangulation.lookup import SourceLayer  # type: ignore[import-not-found]
        return SourceLayer()
    except Exception:
        return None


def _get_concordance():
    """Lazy-load Concordance from lw/00_source/triangulation/concordance.py."""
    src_str = str(_SOURCE_DIR)
    if not _SOURCE_DIR.is_dir():
        return None
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    try:
        from triangulation.concordance import Concordance  # type: ignore[import-not-found]
        return Concordance()
    except Exception:
        return None


def _get_drift_checker():
    """Lazy-load DriftChecker from lw/00_source/triangulation/drift_check.py.

    Used by the deep-mode triangulation check that compares an
    interpretation claim against the original-language Strong's
    definitions for the verse. Returns None if Layer 0 isn't
    provisioned."""
    src_str = str(_SOURCE_DIR)
    if not _SOURCE_DIR.is_dir():
        return None
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    try:
        from triangulation.drift_check import DriftChecker  # type: ignore[import-not-found]
        return DriftChecker()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_ref(ref: str) -> Dict[str, Any]:
    """Resolve a scripture reference string to WEB text and Strong's data.

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
            "ref": ref,
            "web_text": "",
            "status": "source_missing",
            "detail": (
                "Layer 0 source not provisioned. Run "
                "`python lw/00_source/fetch_sources.py` "
                "to build the WEB database."
            ),
        }
    return layer.lookup(ref)


def triangulate_claim(ref: str, claim: str,
                      strongs_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Triangulate an interpretation claim against the WEB text and the
    original-language Strong's definitions for the verse.

    A claim survives triangulation if it does not require any key
    original-language word to mean something outside its attested
    semantic range.

    Args:
        ref:          Scripture reference string, e.g. "Jn15:2"
        claim:        The interpretation being checked
        strongs_keys: Optional list of Strong's numbers for key terms.
                      If omitted, returns the WEB text + a NEEDS_MANUAL_VERIFICATION
                      status with instructions for completing the check.

    Returns the DriftChecker result dict with `status`, `verdict`,
    `web_text`, optional `strongs_analysis`, and source-missing fallback.
    """
    dc = _get_drift_checker()
    if dc is None:
        return {
            "ref": ref,
            "claim": claim,
            "status": "source_missing",
            "detail": (
                "Layer 0 source not provisioned. Run "
                "`python lw/00_source/fetch_sources.py` first."
            ),
        }
    return dc.check(ref, claim, strongs_keys=strongs_keys)


def word_study(strongs_num: str) -> Dict[str, Any]:
    """Complete word study for a Strong's number.

    `strongs_num` like "G26" (agape), "H2617" (chesed), "G2222" (zoe).

    Returns dict including: word, transliteration, definition, derivation,
    verses (list of refs where the word appears), occurrence_count.
    """
    conc = _get_concordance()
    if conc is None:
        return {
            "strongs": strongs_num,
            "status": "source_missing",
            "detail": (
                "Layer 0 source not provisioned. Run "
                "`python lw/00_source/fetch_sources.py` first."
            ),
        }
    return conc.word_study(strongs_num)


def verify_scripture_anchors(anchors: List[str]) -> VerifierResult:
    """Verify each ref in `anchors` resolves to a real WEB verse.

    Used to ensure DECISION_PACKET.scripture_anchors and Entry.refs cite
    genuine references rather than invented ones — the most common
    LLM-fabrication failure mode in this domain.

    Returns CONFIRMED if all resolve, MISMATCH if any fail, SKIPPED if
    the source data has not been provisioned (run fetch_sources.py).
    """
    name = "scripture.anchors"
    if not anchors:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail="No scripture anchors to verify."
        )

    layer = _get_source_layer()
    if layer is None:
        return VerifierResult(
            name=name, status="SKIPPED",
            detail=(
                "WEB source not available. Run "
                "`python lw/00_source/fetch_sources.py` "
                "to enable anchor verification."
            ),
            data={"anchors": anchors},
        )

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
            data=data,
        )
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=(
            f"{len(failed)} anchor(s) not found in WEB: {failed}. "
            "Verify references are genuine before citing them."
        ),
        data=data,
    )


def run(packet: dict) -> list:
    """Run scripture verification for every ref-bearing field in a packet.

    Called by the engine for any packet that contains scripture_anchors,
    DECISION_PACKET.scripture_anchors, or kernel-style Entry.refs. A
    packet with no scripture references is a no-op (returns []).
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
        from dataclasses import replace as _dc_replace
        vr = verify_scripture_anchors(list(refs))
        # Rename for clarity when both fields are present (VerifierResult is frozen)
        vr = _dc_replace(vr, name="scripture.entry_refs")
        results.append(vr)

    return results
