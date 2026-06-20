"""
verifiers/scripture.py — Scripture reference resolver and anchor verifier.

Wires the Layer 0 WORD source (lw/00_source/) into the engine. Resolves
reference strings ("Jn3:16", "Pr4:23") to WEB text and Strong's data, and
verifies that any scripture_anchors declared in a packet are genuine
references rather than fabrications.

When a CONCORDANCE_LSP_PATH env var points at an LSPCorpus JSON, an
additional integrity layer runs: each anchor is resolved against the
corpus's ref-index, the containing chunks are located, and the chunk
hashes are recomputed. This catches drift between the WEB DB and the
canonical hash baseline — the LSP layer is silent when not provisioned.

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

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# Anchors come in two canonical forms:
#   * legacy bare string:  "Mat 5:37"
#   * Anchor-dict form:    {"ref": "Mat 5:37", "layer": "jesus_words", ...}
#
# The dict form is the canonical shape per witness_record.Anchor, but
# legacy callers and string-anchor packets still flow through here.
# Every reference-iterating verifier in this module normalizes via
# `_anchor_to_ref` before attempting to parse the ref text.
def _anchor_to_ref(raw: Any) -> Optional[str]:
    """Extract the bare reference string from an anchor in either form.

    Returns None if the anchor doesn't carry a parseable ref — caller
    should treat that as a failure / unparseable for its own reporting.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        ref = raw.get("ref")
        if isinstance(ref, str):
            return ref
    return None

from .base import VerifierResult

# Tradition-aware canon layer (concordance_engine.canon). Disputed books are
# reported on their OWN layer, never merged into the undisputed 66.
# canon.canon_status(book) tells us who holds a book + the honest historical
# frame. Sovereign / stdlib-only. Imported LAZILY via `_get_canon()` to avoid
# an import cycle: canon.py derives its UNDISPUTED_66 from this module's
# `_CANON_BOOKS` (defined later in this file), so a top-level import here would
# make canon fall back to a names-only mirror that loses abbreviations.


@lru_cache(maxsize=1)
def _get_canon():
    """Lazy import of the canon layer. Deferring to call time lets this module
    finish defining `_CANON_BOOKS` before canon.py reads it (one source of
    truth for the 66). Returns the canon module, or None if unavailable."""
    try:
        from .. import canon as _canon_mod
        return _canon_mod
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Locate lw/00_source from the canonical top-level engine.
# ---------------------------------------------------------------------------
# This file lives at:   <repo>/src/concordance_engine/verifiers/scripture.py
# We need:              <repo>/lw/00_source/
# So go up four parents (verifiers/, concordance_engine/, src/, repo) and
# then descend into lw/00_source.
_REPO_ROOT  = Path(__file__).resolve().parent.parent.parent.parent
_SOURCE_DIR = _REPO_ROOT / "lw" / "00_source"


@lru_cache(maxsize=1)
def _get_source_layer():
    """Lazy-load SourceLayer from lw/00_source/triangulation/lookup.py.

    Cached at module level: SourceLayer holds an open sqlite3 connection,
    and re-instantiating on every packet costs ~370µs/packet for the
    sqlite3.connect alone. The cache makes that a one-time startup cost.

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


@lru_cache(maxsize=1)
def _get_concordance():
    """Lazy-load Concordance from lw/00_source/triangulation/concordance.py.
    Cached for the same reason as _get_source_layer."""
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


# ── Reference rotation (canonical §3: assume input error) ────────────
# Per 00_CANON/PRIMARY_RULESET.md §3:
#   "If a reference does not fit perfectly, assume input error rather
#    than bending Scripture. Rotate context left/right until the
#    anchor fits exactly."
#
# When a ref fails to resolve, we don't just call it invalid — we try
# small rotations (±radius verses, common book-name corrections) and
# surface candidates so the human can pick the right one.

# Minimal verse-max table for chapters that frequently appear in
# packets. Not a full Bible database — extend as new collisions arise.
# Source: standard Protestant canon verse counts.
_VERSE_MAX: Dict[Tuple[str, int], int] = {
    ("genesis", 1): 31, ("genesis", 3): 24,
    ("exodus", 20): 17,
    ("deuteronomy", 6): 25, ("deuteronomy", 17): 20, ("deuteronomy", 19): 21,
    ("psalms", 1): 6, ("psalms", 23): 6, ("psalms", 127): 5,
    ("proverbs", 3): 35, ("proverbs", 10): 32, ("proverbs", 19): 29, ("proverbs", 30): 33,
    ("ecclesiastes", 3): 22,
    ("isaiah", 55): 13,
    ("micah", 6): 16,
    ("matthew", 5): 48, ("matthew", 6): 34, ("matthew", 7): 29,
    ("matthew", 18): 35, ("matthew", 23): 39,
    ("mark", 7): 37,
    ("luke", 6): 49, ("luke", 17): 37,
    ("john", 1): 51, ("john", 3): 36, ("john", 6): 71, ("john", 14): 31, ("john", 15): 27,
    ("acts", 7): 60, ("acts", 15): 41,
    ("romans", 12): 21,
    ("1 corinthians", 14): 40, ("2 corinthians", 1): 24,
    ("hebrews", 1): 14,
    ("1 thessalonians", 4): 18, ("1 thessalonians", 5): 28,
    ("2 timothy", 3): 17,
    ("1 peter", 5): 14,
    ("revelation", 22): 21,
}

# Common book-name typos / abbreviations not handled by the canon
# matcher. Maps misspellings to the canonical lower-cased name.
_BOOK_TYPOS = {
    "matt.": "matthew",
    "mt.": "matthew",
    "matt": "matthew",
    "mathew": "matthew",
    "psalm": "psalms",
    "ps.": "psalms",
    "rom.": "romans",
    "cor.": "corinthians",
}

# Book-name canonicalization: maps the short forms _extract_book_chapter
# returns ("mt", "matt", "ps", "1cor") to the full lowercase names used
# as keys in _VERSE_MAX. Built from the existing _CANON_BOOKS set with
# explicit short-form mappings; extend as needed.
_BOOK_CANONICAL = {
    "mt": "matthew", "matt": "matthew", "matthew": "matthew",
    "mk": "mark", "mark": "mark", "mar": "mark",
    "lk": "luke", "luke": "luke", "luk": "luke",
    "jn": "john", "john": "john", "jhn": "john",
    "acts": "acts", "act": "acts",
    "rom": "romans", "romans": "romans",
    "1cor": "1 corinthians", "1 cor": "1 corinthians",
    "1corinthians": "1 corinthians", "1 corinthians": "1 corinthians",
    "2cor": "2 corinthians", "2 cor": "2 corinthians",
    "2corinthians": "2 corinthians", "2 corinthians": "2 corinthians",
    "heb": "hebrews", "hebrews": "hebrews",
    "ps": "psalms", "psa": "psalms", "psalm": "psalms", "psalms": "psalms",
    "prov": "proverbs", "pr": "proverbs", "proverbs": "proverbs",
    "gen": "genesis", "ge": "genesis", "genesis": "genesis",
    "deut": "deuteronomy", "dt": "deuteronomy", "deuteronomy": "deuteronomy",
    "isa": "isaiah", "is": "isaiah", "isaiah": "isaiah",
    "1thess": "1 thessalonians", "1 thess": "1 thessalonians",
    "1thessalonians": "1 thessalonians", "1 thessalonians": "1 thessalonians",
    "2tim": "2 timothy", "2 tim": "2 timothy",
    "2timothy": "2 timothy", "2 timothy": "2 timothy",
    "1pet": "1 peter", "1 pet": "1 peter",
    "1peter": "1 peter", "1 peter": "1 peter",
    "rev": "revelation", "revelation": "revelation",
    "ex": "exodus", "exo": "exodus", "exodus": "exodus",
    "ecc": "ecclesiastes", "ec": "ecclesiastes",
    "ecclesiastes": "ecclesiastes",
    "mic": "micah", "micah": "micah",
}


def _rotation_suggestions(bare_ref: str, radius: int = 3) -> List[str]:
    """Generate plausible corrections for a ref that didn't resolve.

    Strategy:
      1. Parse book + chapter + verse from the ref.
      2. If the book name is a known typo, suggest the corrected form.
      3. If the verse is out of range for the chapter, suggest verses
         within range (±radius around the input verse, clamped to
         [1, max_verse]).
      4. Suggestions are ordered by closeness to the original.

    Returns an empty list if the ref can't be parsed or no rotation
    table data is available.
    """
    book, chapter = _extract_book_chapter(bare_ref)
    if book is None or chapter is None:
        return []

    # Canonicalize the book name (mt → matthew) so we can look up
    # _VERSE_MAX, which keys on full lowercase names.
    canonical_book = _BOOK_CANONICAL.get(book, _BOOK_TYPOS.get(book, book))

    # Surface a typo correction if the input form was a clear typo.
    suggestions: List[str] = []
    if book in _BOOK_TYPOS:
        parts = bare_ref.split(":", 1)
        if len(parts) == 2:
            verse_part = parts[1]
            cap_book = canonical_book.title() if canonical_book.islower() else canonical_book
            suggestions.append(f"{cap_book} {chapter}:{verse_part}")

    # Verse-range rotation: extract the input verse number
    import re as _re_local
    m = _re_local.search(r":(\d+)", bare_ref)
    if not m:
        return suggestions
    input_verse = int(m.group(1))
    max_verse = _VERSE_MAX.get((canonical_book, chapter))
    if max_verse is None:
        return suggestions

    # Suggest verses within ±radius, clamped to valid range.
    cap = canonical_book.title() if canonical_book.islower() else canonical_book
    seen: set = set()
    for offset in range(0, radius + 1):
        # Try +/- offsets, alternating to keep "closeness" order.
        for sign in (-1, 1) if offset > 0 else (1,):
            candidate = input_verse + (sign * offset)
            if 1 <= candidate <= max_verse:
                key = (cap, chapter, candidate)
                if key not in seen:
                    seen.add(key)
                    suggestions.append(f"{cap} {chapter}:{candidate}")
    # Ensure the chapter's last verse is in the suggestions if input
    # was wildly out of range.
    last_key = (cap, chapter, max_verse)
    if input_verse > max_verse and last_key not in seen:
        suggestions.append(f"{cap} {chapter}:{max_verse}")

    # Dedupe while preserving order (typo correction + verse rotation
    # can produce the same suggestion twice).
    deduped: List[str] = []
    seen_str: set = set()
    for s in suggestions:
        if s not in seen_str:
            seen_str.add(s)
            deduped.append(s)
    return deduped[:6]  # cap to keep the output readable


@lru_cache(maxsize=2048)
def _cached_anchor_lookup(bare_ref: str):
    """Per-bare-ref lookup against the source layer, memoized at module
    scope. Same bare ref across many packets shares one DB query.

    Returns whatever SourceLayer.lookup() returned (a dict), or None if
    sources aren't provisioned. Caller is responsible for handling None.

    Cache keys are bare references like "Mt 5:37" / "Gen 1:1" — anchor
    text variants ("Mat 5:37", "Mt 5:37 — let your yes be yes") all
    normalize to the same bare ref via _extract_ref before reaching here.
    """
    layer = _get_source_layer()
    if layer is None:
        return None
    return layer.lookup(bare_ref)


@lru_cache(maxsize=1)
def _get_drift_checker():
    """Lazy-load DriftChecker from lw/00_source/triangulation/drift_check.py.

    Used by the deep-mode triangulation check that compares an
    interpretation claim against the original-language Strong's
    definitions for the verse. Returns None if Layer 0 isn't
    provisioned. Cached for the same reason as _get_source_layer."""
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


# ── LSP corpus integration (Full LSP) ─────────────────────────────────
# When CONCORDANCE_LSP_PATH points at an LSPCorpus JSON file, anchor
# verification runs an additional integrity check against the corpus:
# resolve ref → chunk(s) → recompute hashes. This is the canonical
# "verifiable address" promise of LSP. Silent / no-op when the env var
# is unset or the file isn't readable.


@lru_cache(maxsize=1)
def _get_lsp_corpus():
    path_str = os.environ.get("CONCORDANCE_LSP_PATH")
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_file():
        return None
    try:
        from ..lsp import LSPCorpus
        return LSPCorpus.load(path)
    except (OSError, ValueError, KeyError):
        return None


def _verify_against_lsp(bare_ref: str) -> Optional[Dict[str, Any]]:
    """Run LSP integrity check for a single bare ref. Returns None when
    no corpus is provisioned (caller skips the check); otherwise returns
    the corpus's verify_anchor() result dict."""
    corpus = _get_lsp_corpus()
    if corpus is None:
        return None
    return corpus.verify_anchor(bare_ref)


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


_SCRIPTURE_ANCHORS_ANCHOR = {
    "ref": "Prov 30:5-6",
    "layer": "bible",
    "derivation": (
        "Anchor authenticity: 'Every word of God proves true; he is a "
        "shield to those who take refuge in him. Do not add to his words, "
        "lest he rebuke you and you be found a liar.' Citing references "
        "that don't actually appear in Scripture is exactly the addition "
        "Prov 30:6 forbids — this verifier rejects fabricated anchors so "
        "no claim is built on words God didn't say."
    ),
}


def verify_scripture_anchors(anchors: List[Union[str, Dict[str, Any]]]) -> VerifierResult:
    """Verify each ref in `anchors` resolves to a real WEB verse.

    Used to ensure DECISION_PACKET.scripture_anchors and Entry.refs cite
    genuine references rather than invented ones — the most common
    LLM-fabrication failure mode in this domain. Anchored in Prov 30:5-6.

    Anchors may be bare strings ("Mat 5:37") or Anchor-dict form
    ({"ref": "Mat 5:37", "layer": "jesus_words"}). Both are accepted;
    the original form is preserved in `data.resolved` / `data.failed`
    so callers can carry through layer provenance.

    Returns CONFIRMED if all resolve, MISMATCH if any fail, SKIPPED if
    the source data has not been provisioned (run fetch_sources.py).
    """
    name = "scripture.anchors"
    if not anchors:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail="No scripture anchors to verify.",
            data={"anchor": _SCRIPTURE_ANCHORS_ANCHOR},
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
            data={"anchor": _SCRIPTURE_ANCHORS_ANCHOR, "anchors": anchors},
        )

    # Anchors are commonly formatted with the verse text or commentary
    # appended to the reference, e.g. "Mic 6:8 — to act justly..."  or
    # "Mic 6:8: to act justly...". The lookup only understands the bare
    # reference (book + chapter:verse[-end]), so extract that prefix
    # before lookup.
    import re
    _REF_PATTERN = re.compile(
        r"^\s*("                       # capture group: the bare reference
        r"(?:[1-3]\s*)?"               # optional leading 1/2/3 (book number)
        r"[A-Za-z][A-Za-z\.]*"         # book name (letters and dots)
        r"\s*\d+"                      # chapter
        r"(?::\d+(?:-\d+)?)?"          # optional :verse or :verse-end
        r")"
    )
    def _extract_ref(s):
        m = _REF_PATTERN.match(s)
        return m.group(1).strip() if m else s

    resolved = []
    failed = []
    deuterocanonical: List[Dict[str, Any]] = []  # SEPARATE layer (canon §: discern)
    rotation_offers: List[Dict[str, Any]] = []  # canonical §3: assume input error
    lsp_checks: List[Dict[str, Any]] = []  # populated only if LSP corpus is provisioned
    lsp_tampered: List[Dict[str, Any]] = []
    canon_mod = _get_canon()
    for raw in anchors:
        ref_str = _anchor_to_ref(raw)
        if ref_str is None:
            failed.append(raw)
            continue
        bare_ref = _extract_ref(ref_str)
        # Hits the per-bare-ref cache; same anchor across many packets
        # shares one DB query.
        result = _cached_anchor_lookup(bare_ref)
        if result is not None and result.get("status") == "ok" and result.get("web_text"):
            resolved.append({"ref": raw, "text": result["web_text"][:120]})
        else:
            # The WEB Bible holds only the undisputed 66, so a ref can fail to
            # resolve for two very different reasons: (a) it's a real
            # deuterocanonical / tradition-held book the WEB simply doesn't
            # carry, or (b) it's a fabrication / typo. We must NOT treat (a) as
            # (b): rejecting "Tobit 1:1" as fabricated would falsely reject a
            # Catholic/Ethiopian believer's Scripture. So consult the canon
            # layer FIRST and, when the book is held by a tradition, report it
            # on a SEPARATE layer (shown for discernment, never merged into the
            # 66). Only genuinely unknown books fall through to `failed`.
            book, _chap = _extract_book_chapter(ref_str)
            status = canon_mod.canon_status(book) if (canon_mod and book) else None
            if status is not None and status.get("held_by") and not status.get("in_undisputed_66"):
                deuterocanonical.append({
                    "ref": raw,
                    "book": status.get("canonical_name") or book,
                    "held_by": status["held_by"],
                    "historical_note": status["historical_note"],
                })
            else:
                failed.append(raw)
                # Reference rotation: assume input error, suggest corrections.
                suggestions = _rotation_suggestions(bare_ref)
                if suggestions:
                    rotation_offers.append({
                        "ref": raw,
                        "bare_ref": bare_ref,
                        "did_you_mean": suggestions,
                    })

        # LSP integrity check (silent when no corpus provisioned).
        lsp_result = _verify_against_lsp(bare_ref)
        if lsp_result is not None:
            lsp_checks.append(lsp_result)
            if lsp_result.get("status") == "tampered":
                lsp_tampered.append(lsp_result)

    data = {
        "anchor": _SCRIPTURE_ANCHORS_ANCHOR,
        "rule": (
            "every cited reference must resolve to an actual verse in "
            "the public-domain WEB Bible (Prov 30:5-6 — every word of "
            "God proves true). When a ref doesn't resolve, the engine "
            "assumes input error and offers rotations (canon §3). "
            "References OUTSIDE the undisputed 66 that are held by a "
            "Christian tradition (deuterocanon) are reported on a SEPARATE "
            "layer — shown honestly and historically framed for the user to "
            "discern, never merged into the validated 66, and never falsely "
            "rejected as fabrications."
        ),
        "resolved": resolved, "failed": failed, "total": len(anchors),
        "rotation_offers": rotation_offers,
    }
    # Separate canon layer: never merged into `resolved` (the validated 66).
    if deuterocanonical:
        data["deuterocanonical"] = deuterocanonical
    if lsp_checks:
        data["lsp_checks"] = lsp_checks
        data["lsp_tampered"] = lsp_tampered

    # LSP tampering is a hard failure even if WEB resolution passed —
    # the chunk hash is the canonical integrity baseline.
    if lsp_tampered:
        tamper_refs = [t.get("ref") for t in lsp_tampered]
        return VerifierResult(
            name=name, status="MISMATCH",
            detail=(
                f"{len(lsp_tampered)} anchor(s) failed LSP integrity check "
                f"(chunk hash mismatch — drift detected): {tamper_refs}. "
                "The canonical hash baseline does not match the current "
                "corpus text."
            ),
            data=data,
        )
    # Honest, non-judging note about the separate deuterocanon layer. The
    # engine does not crown a canon (conduit, not source): it reports who holds
    # each disputed book and the history, and lets the user discern.
    def _deutero_note() -> str:
        traditions = sorted({t for d in deuterocanonical for t in d["held_by"]})
        labels = [
            (canon_mod.tradition_label(t) if canon_mod else t)
            for t in traditions
        ]
        return (
            f"{len(deuterocanonical)} reference(s) outside the undisputed 66 — "
            f"held canonical by [{', '.join(labels)}]; shown for discernment, "
            "not merged with the 66."
        )

    if not failed:
        # The undisputed 66 are intact and nothing is a fabrication. Any
        # deuterocanonical refs are reported on their own layer — they do NOT
        # turn this into a failure (that would falsely reject a Catholic /
        # Ethiopian believer's Scripture). The validated core still verified.
        resolved_count = len(resolved)
        if deuterocanonical:
            detail = (
                f"{resolved_count} reference(s) resolved in the undisputed 66 "
                f"(WEB). {_deutero_note()}"
            )
        else:
            detail = f"All {len(anchors)} scripture anchor(s) resolved in WEB."
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail=detail,
            data=data,
        )
    # There ARE genuine failures (not in any known canon — likely typos or
    # fabrications). Build a detail message that includes rotation offers when
    # we have suggestions — helps the human spot input errors without bending
    # Scripture (canon §3). If deuterocanon refs are also present, surface that
    # SEPARATELY so the disputed books aren't lumped in with the fabrications.
    if rotation_offers:
        offer_strs = [
            f"{o['ref']} → did you mean: {', '.join(o['did_you_mean'][:3])}"
            for o in rotation_offers
        ]
        detail = (
            f"{len(failed)} anchor(s) not found in any known canon "
            f"(likely input errors; rotation offered): {'; '.join(offer_strs)}"
        )
    else:
        detail = (
            f"{len(failed)} anchor(s) not found in any known canon: {failed}. "
            "Verify references are genuine before citing them."
        )
    if deuterocanonical:
        detail = f"{detail} Separately: {_deutero_note()}"
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=detail,
        data=data,
    )


# ── Canonical 66-book set (Protestant canon, public domain) ─────────────
# Lower-cased, common abbreviations included. The pattern matcher accepts
# any of these forms before chapter:verse.
_CANON_BOOKS = {
    # OT
    "genesis", "gen", "ge",
    "exodus", "exo", "ex",
    "leviticus", "lev", "lv",
    "numbers", "num", "nu",
    "deuteronomy", "deut", "dt",
    "joshua", "josh", "jos",
    "judges", "judg", "jdg",
    "ruth", "ru",
    "1 samuel", "1samuel", "1sam", "1sa", "1 sam",
    "2 samuel", "2samuel", "2sam", "2sa", "2 sam",
    "1 kings", "1kings", "1kgs", "1ki",
    "2 kings", "2kings", "2kgs", "2ki",
    "1 chronicles", "1chronicles", "1chr", "1ch",
    "2 chronicles", "2chronicles", "2chr", "2ch",
    "ezra", "ezr",
    "nehemiah", "neh", "ne",
    "esther", "est", "es",
    "job",
    "psalms", "psalm", "ps", "psa",
    "proverbs", "prov", "pr", "pro",
    "ecclesiastes", "eccl", "ecc", "ec", "qoh",
    "song of solomon", "song of songs", "song", "sos", "ss",
    "isaiah", "isa", "is",
    "jeremiah", "jer", "je",
    "lamentations", "lam", "la",
    "ezekiel", "ezek", "eze", "ezk",
    "daniel", "dan", "da", "dn",
    "hosea", "hos", "ho",
    "joel", "joe", "jl",
    "amos", "am",
    "obadiah", "obad", "ob",
    "jonah", "jon",
    "micah", "mic", "mi",
    "nahum", "nah", "na",
    "habakkuk", "hab", "hb",
    "zephaniah", "zeph", "zep",
    "haggai", "hag", "hg",
    "zechariah", "zech", "zec",
    "malachi", "mal",
    # NT
    "matthew", "matt", "mt",
    "mark", "mk", "mar",
    "luke", "lk", "luk",
    "john", "jn", "jhn",
    "acts", "ac", "act",
    "romans", "rom", "ro",
    "1 corinthians", "1corinthians", "1cor", "1co",
    "2 corinthians", "2corinthians", "2cor", "2co",
    "galatians", "gal", "ga",
    "ephesians", "eph",
    "philippians", "phil", "php",
    "colossians", "col",
    "1 thessalonians", "1thess", "1th",
    "2 thessalonians", "2thess", "2th",
    "1 timothy", "1tim", "1ti",
    "2 timothy", "2tim", "2ti",
    "titus", "tit",
    "philemon", "phlm", "phm",
    "hebrews", "heb",
    "james", "jas", "jam",
    "1 peter", "1pet", "1pe",
    "2 peter", "2pet", "2pe",
    "1 john", "1jn", "1jo",
    "2 john", "2jn", "2jo",
    "3 john", "3jn", "3jo",
    "jude", "jud",
    "revelation", "rev", "re",
}

# Books that are predominantly red-letter (Jesus speaking in person).
# Matthew, Mark, Luke, John = the four Gospels.
_GOSPEL_BOOKS = {
    "matthew", "matt", "mt",
    "mark", "mk", "mar",
    "luke", "lk", "luk",
    "john", "jn", "jhn",
}

import re as _re

# Match the reference prefix, allowing trailing content (commentary,
# verse text). We only use the first chapter:verse hit and ignore what
# follows.
_BOOK_PATTERN = _re.compile(
    r"^\s*((?:[1-3]\s*)?[A-Za-z][A-Za-z\.\s]*?)\s*(\d+)(?::\d+(?:-\d+)?)?(?=\s|$|[—–\-,;:.])"
)


def _extract_book_chapter(ref: str):
    """Return (book_lower, chapter) for a reference, or (None, None).

    Accepts commentary-annotated forms like "Mic 6:8 — to act justly..."
    by anchoring only the reference prefix.
    """
    if not ref:
        return None, None
    s = str(ref)
    # Trim any commentary that follows an em-dash, en-dash, or hyphen-with-spaces.
    for sep in (" — ", " – ", " - "):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    m = _BOOK_PATTERN.match(s)
    if not m:
        return None, None
    book = m.group(1).strip().lower()
    book = _re.sub(r"\s+", " ", book).rstrip(".").strip()
    try:
        chapter = int(m.group(2))
    except (TypeError, ValueError):
        return None, None
    return book, chapter


_CANON_MEMBERSHIP_ANCHOR = {
    "ref": "2 Tim 3:16",
    "layer": "apostles",
    "derivation": (
        "Canon as a layered witness: 'All Scripture is breathed out by "
        "God and profitable...' The undisputed 66 are the validated core "
        "shared by all major traditions and form this engine's verified "
        "boundary. Books held only by some traditions (the deuterocanon) "
        "are not merged into the 66 nor rejected as fabrications — they "
        "are reported on a SEPARATE layer, historically framed, for the "
        "user to discern. References in no known canon are flagged as "
        "likely errors. The engine reports; it does not crown a canon."
    ),
}


def verify_canon_membership(refs):
    """Classify references by canon LAYER, keeping the 66 separate.

    Anchored in 2 Tim 3:16. The 66-book undisputed core is the validated
    boundary; references outside it that are held by a Christian tradition
    (deuterocanon) are reported on a SEPARATE layer — historically framed,
    never merged into the 66, never falsely rejected. References in NO known
    canon are flagged as likely errors. The engine does not judge which canon
    is correct; it shows who holds what and lets the user discern.

    The anchor is surfaced in the verifier's `data` payload so the walkthrough
    renderer (and downstream consumers) can display the derivation.
    """
    name = "scripture.canon_membership"
    if not refs:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="no references to check")
    canon_mod = _get_canon()
    inside = []            # in the undisputed 66
    deuterocanonical = []  # SEPARATE layer: held by a tradition, not the 66
    outside = []           # in no known canon (likely typo / fabrication)
    unparseable = []
    for raw in refs:
        ref_str = _anchor_to_ref(raw)
        if ref_str is None:
            unparseable.append(raw)
            continue
        book, _ = _extract_book_chapter(ref_str)
        if book is None:
            unparseable.append(raw)
        elif book in _CANON_BOOKS:
            inside.append(raw)
        else:
            # Not in the 66 — consult the canon layer before judging.
            status = canon_mod.canon_status(book) if canon_mod else None
            if status is not None and status.get("held_by") and not status.get("in_undisputed_66"):
                deuterocanonical.append({
                    "ref": raw,
                    "book": status.get("canonical_name") or book,
                    "held_by": status["held_by"],
                    "historical_note": status["historical_note"],
                })
            else:
                outside.append(raw)
    data = {
        "anchor": _CANON_MEMBERSHIP_ANCHOR,
        "rule": (
            "the undisputed 66 are the validated core (2 Tim 3:16); "
            "deuterocanonical books are reported on a SEPARATE layer, "
            "historically framed, for discernment — not merged with the 66 "
            "and not rejected as fabrications; references in no known canon "
            "are flagged as likely errors"
        ),
        "inside": inside, "outside": outside, "unparseable": unparseable,
        "total": len(refs),
    }
    if deuterocanonical:
        data["deuterocanonical"] = deuterocanonical

    def _deutero_note() -> str:
        traditions = sorted({t for d in deuterocanonical for t in d["held_by"]})
        labels = [
            (canon_mod.tradition_label(t) if canon_mod else t)
            for t in traditions
        ]
        return (
            f"{len(deuterocanonical)} reference(s) outside the undisputed 66 — "
            f"held canonical by [{', '.join(labels)}]; shown for discernment, "
            "not merged with the 66."
        )

    # Only references in NO known canon are a genuine MISMATCH. Deuterocanon
    # refs are NOT a failure — that would falsely reject a Catholic / Ethiopian
    # believer's Scripture. The undisputed 66 remain the validated layer.
    if outside:
        detail = f"{len(outside)} reference(s) not in any known canon (likely errors): {outside}"
        if deuterocanonical:
            detail = f"{detail}. Separately: {_deutero_note()}"
        return VerifierResult(name=name, status="MISMATCH",
                              detail=detail,
                              data=data)
    if unparseable and not inside and not deuterocanonical:
        return VerifierResult(name=name, status="ERROR",
                              detail=f"could not parse any reference: {unparseable}",
                              data=data)
    # No genuine non-canon refs. The 66-book core is clean. If deuterocanon
    # refs are present they are reported on the separate layer (CONFIRMED, not
    # a failure — the validated core verified and the rest is shown to discern).
    if deuterocanonical:
        if inside:
            detail = (
                f"{len(inside)} reference(s) in the undisputed 66. "
                f"Separately: {_deutero_note()}"
            )
        else:
            detail = _deutero_note()
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=detail, data=data)
    return VerifierResult(name=name, status="CONFIRMED",
                          detail=f"all {len(inside)} reference(s) in canonical 66 books",
                          data=data)


_RED_LETTER_PRIORITY_ANCHOR = {
    "ref": "Heb 1:1-2",
    "layer": "apostles",
    "derivation": (
        "Source-hierarchy primacy: 'Long ago, at many times and in many "
        "ways, God spoke to our fathers by the prophets, but in these "
        "last days he has spoken to us by his Son.' The Son's recorded "
        "words (the Gospels) are the highest-tier authority; all other "
        "Scripture is secondary witness. This verifier classifies refs "
        "so weight can be given accordingly."
    ),
}


def verify_red_letter_priority(refs):
    """Surface which references are from Gospel books (Jesus's recorded words).

    Per `00_CANON/SOURCE_HIERARCHY.md`: Jesus' words (RED) are primary
    authority; all other Scripture is secondary witness. Anchored in
    Heb 1:1-2. This verifier annotates each reference with whether it
    points to a Gospel book, so downstream consumers can weight
    accordingly. Returns CONFIRMED in either case (it's a classification,
    not a pass/fail), but the `data` payload tells the caller which
    refs are top-tier authority.
    """
    name = "scripture.red_letter_priority"
    if not refs:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="no references to classify",
                              data={"anchor": _RED_LETTER_PRIORITY_ANCHOR})
    gospel_refs = []
    other_refs = []
    for raw in refs:
        ref_str = _anchor_to_ref(raw)
        if ref_str is None:
            other_refs.append(raw)
            continue
        book, _ = _extract_book_chapter(ref_str)
        if book and book in _GOSPEL_BOOKS:
            gospel_refs.append(raw)
        else:
            other_refs.append(raw)
    data = {
        "anchor": _RED_LETTER_PRIORITY_ANCHOR,
        "rule": (
            "classify refs as Gospel (Jesus' recorded words, primary "
            "authority) vs other Scripture (secondary). Heb 1:1-2 — "
            "in these last days God has spoken by his Son."
        ),
        "gospel_refs": gospel_refs, "other_refs": other_refs,
        "total": len(refs), "gospel_count": len(gospel_refs),
    }
    if gospel_refs:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail=f"{len(gospel_refs)} of {len(refs)} reference(s) are from Gospels "
                   f"(red-letter priority): {gospel_refs}",
            data=data,
        )
    return VerifierResult(
        name=name, status="CONFIRMED",
        detail=f"no Gospel references among {len(refs)} citation(s); "
               f"all are secondary-tier per source hierarchy",
        data=data,
    )


# ── Quotation / allusion detection (textual overlap, NOT interpretation) ──
# Closes bq-scripture-quotation. Computes the textual relationship between two
# verses on the WEB text — a contiguous shared phrase and a token-overlap
# coefficient. This is math on the text, not a theological judgment: the
# engine confirms quotation/allusion but DECLINES "fulfills" (interpretation).

_QWORD_RE = re.compile(r"[a-z0-9]+")

# Stripped before the overlap coefficient so shared function words ("the",
# "and", "of") can't manufacture an allusion. The contiguous-phrase metric
# keeps stopwords — a genuine shared phrase includes them.
_STOPWORDS = set(
    "a an and are as at be by for from he her him his i in is it its me my "
    "no nor not o of on or our shall so that the thee their them then they "
    "thine thou thy to unto up upon us was we what when where which who will "
    "with you your".split()
)


def _tokenize_verse(text: str) -> List[str]:
    return _QWORD_RE.findall((text or "").lower())


def _longest_contiguous(a: List[str], b: List[str]) -> int:
    """Length of the longest token run that appears contiguously in both."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def _overlap_coefficient(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def verify_scripture_quotation(spec: Dict[str, Any]) -> VerifierResult:
    """Confirm a textual quotation/allusion between two verses on the WEB text.

        relation strength: quotation ⊇ allusion ⊇ none
        - longest shared contiguous phrase ≥ min_phrase tokens → quotation
        - else token overlap coefficient ≥ quote_threshold     → quotation
        - else overlap ≥ allude_threshold                      → allusion
        - else                                                 → none

    A claim of 'alludes' is satisfied by quotation-or-allusion; 'quotes' needs
    quotation strength. 'fulfills' is DECLINED — fulfillment is interpretation,
    not text overlap; the engine reports the measured overlap as evidence but
    will not confirm it.
    """
    name = "scripture.quotation"
    ref_a = spec.get("verse_a") or spec.get("a") or spec.get("ref_a")
    ref_b = spec.get("verse_b") or spec.get("b") or spec.get("ref_b")
    relation = (spec.get("relation") or "quotes").strip().lower()
    if not ref_a or not ref_b:
        return VerifierResult(name=name, status="NOT_APPLICABLE",
                              detail="needs verse_a and verse_b")
    ra = resolve_ref(str(ref_a))
    rb = resolve_ref(str(ref_b))
    if ra.get("status") == "source_missing" or rb.get("status") == "source_missing":
        return VerifierResult(name=name, status="SKIPPED",
                              detail="Layer 0 WEB source not provisioned")
    if (ra.get("status") != "ok" or not ra.get("web_text")
            or rb.get("status") != "ok" or not rb.get("web_text")):
        return VerifierResult(name=name, status="NOT_APPLICABLE",
                              detail=f"could not resolve both verses ({ref_a}, {ref_b})")
    ta = _tokenize_verse(ra["web_text"])
    tb = _tokenize_verse(rb["web_text"])
    contiguous = _longest_contiguous(ta, tb)
    # Overlap on CONTENT words (stopwords stripped) so shared function words
    # don't inflate an allusion that isn't really there.
    overlap = _overlap_coefficient([t for t in ta if t not in _STOPWORDS],
                                   [t for t in tb if t not in _STOPWORDS])
    min_phrase = int(spec.get("min_phrase_tokens", 4))
    quote_thr = float(spec.get("quote_threshold", 0.6))
    allude_thr = float(spec.get("allude_threshold", 0.3))
    if contiguous >= min_phrase or overlap >= quote_thr:
        measured = "quotation"
    elif overlap >= allude_thr:
        measured = "allusion"
    else:
        measured = "none"
    data = {
        "verse_a": ra.get("ref"), "verse_b": rb.get("ref"),
        "claimed_relation": relation, "measured_relation": measured,
        "longest_contiguous_tokens": contiguous,
        "overlap_coefficient": round(overlap, 3),
        "thresholds": {"min_phrase_tokens": min_phrase,
                       "quote_threshold": quote_thr, "allude_threshold": allude_thr},
        "method": "WEB-text token overlap + longest contiguous shared phrase",
    }
    if relation in ("fulfills", "fulfillment", "fulfilled", "fulfil"):
        data["note"] = ("Fulfillment is a theological judgment, not a textual "
                        "computation. Reporting the measured overlap as evidence "
                        "only; the engine does not confirm fulfillment.")
        return VerifierResult(name=name, status="NOT_APPLICABLE", detail=data["note"], data=data)
    rank = {"none": 0, "allusion": 1, "quotation": 2}
    need = 2 if relation in ("quotes", "quotation", "quote") else 1
    if rank[measured] >= need:
        return VerifierResult(
            name=name, status="CONFIRMED",
            detail=(f"{ra.get('ref')} ↔ {rb.get('ref')}: measured {measured} "
                    f"(contiguous {contiguous} tokens, overlap {overlap:.2f}) satisfies '{relation}'"),
            data=data)
    return VerifierResult(
        name=name, status="MISMATCH",
        detail=(f"{ra.get('ref')} ↔ {rb.get('ref')}: claimed '{relation}' but measured {measured} "
                f"(contiguous {contiguous}, overlap {overlap:.2f})"),
        data=data)


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

    # Canon membership + red-letter priority run on whatever refs are
    # present (anchors first, fall back to refs).
    all_refs = list(anchors) + list(refs)
    if all_refs:
        results.append(verify_canon_membership(all_refs))
        results.append(verify_red_letter_priority(all_refs))

    # Quotation / allusion between two verses (textual overlap on the WEB text)
    q = packet.get("QUOTATION_VERIFY")
    if isinstance(q, dict) and (q.get("verse_a") or q.get("a") or q.get("ref_a")):
        results.append(verify_scripture_quotation(q))
    for qq in (packet.get("quotations") or []):
        if isinstance(qq, dict):
            results.append(verify_scripture_quotation(qq))

    return results
