"""Layer 0 grounding verifier.

The engine's Layer 0 is the Bible itself — the WEB (World English
Bible, public domain) sits at the foundation, and is taken on faith.
Other layers reduce to Layer 0 or to math from constants of truth.

This verifier surfaces the textual evidence at Layer 0 for any claim
that references Scripture. It does NOT pronounce that an
interpretation is correct — it returns the actual WEB text of the
passages cited, so the visitor can read what Scripture says directly.

  CONFIRMED       — one or more referenced passages resolve to WEB
                    text, evidence shown
  MISMATCH        — a cited reference does not resolve (e.g. a
                    fabricated citation like "Hezekiah 4:21")
  NOT_APPLICABLE  — no Scripture references found in the claim

LAYER0_VERIFY shape:
    {
      "claim": "Christ rose on the third day according to 1 Cor 15:4",
      # optional: explicit refs list — bypasses extraction
      "refs": ["1 Corinthians 15:4"],
    }

This verifier does not invent connections, cross-references, or
typology. It only surfaces the WEB text of explicitly-cited passages.
For typological / parallel-passage reasoning, see the build queue
under bq-scripture-quotation — that work requires parsing actual
textual quotations between verses.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch


def verify_grounding(spec: Dict[str, Any]) -> VerifierResult:
    name = "layer_zero.grounding"
    claim = (spec.get("claim") or "").strip()
    explicit_refs = spec.get("refs") or []
    if not claim and not explicit_refs:
        return na(name)

    # Get refs either from the explicit list or by extraction from the
    # claim text using the scripture_retrieval reference parser.
    refs: List[str] = []
    if isinstance(explicit_refs, list):
        for r in explicit_refs:
            if isinstance(r, str) and r.strip():
                refs.append(r.strip())
    if claim and not refs:
        try:
            from ..scripture_retrieval import _extract_refs
            refs = _extract_refs(claim)
        except Exception:
            refs = []

    if not refs:
        return na(name)

    # Resolve each ref to its WEB passage. The resolver returns
    # {"status": ..., "web_text": ..., "ref": ...}.
    try:
        from .scripture import resolve_ref
    except ImportError:
        return na(name)

    resolved: List[Dict[str, Any]] = []
    missing: List[str] = []
    for ref in refs[:10]:
        try:
            r = resolve_ref(ref)
        except Exception:
            r = {"status": "error", "ref": ref}
        status = (r.get("status") or "").lower()
        if status == "ok" and r.get("web_text"):
            resolved.append({
                "ref": r.get("ref", ref),
                "text": r.get("web_text", ""),
                "status": "ok",
            })
        elif status == "source_missing":
            # The WEB DB isn't provisioned; that's an engine state, not
            # a misalignment with the claim. Skip.
            continue
        else:
            missing.append(ref)

    data = {
        "claim": claim[:500],
        "refs_extracted": refs,
        "passages": resolved,
        "missing": missing,
        "source": "WEB Bible (World English Bible, public domain) — Layer 0",
        "rule": "Engine surfaces Layer 0 text; does not interpret.",
    }

    if not resolved and not missing:
        # WEB DB not provisioned — engine state, not user error
        return na(name)
    if missing and not resolved:
        return mismatch(
            name,
            f"references not resolvable in WEB: {missing}",
            data,
        )
    if missing:
        return mismatch(
            name,
            f"{len(resolved)} passage(s) resolved; {len(missing)} fabricated/unresolvable: {missing}",
            data,
        )
    return confirm(
        name,
        f"{len(resolved)} Scripture passage(s) at Layer 0 anchor this claim",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    lv = packet.get("LAYER0_VERIFY") or {}
    if lv.get("claim") or lv.get("refs"):
        results.append(verify_grounding(lv))
    if not results:
        results.append(na("layer_zero_grounding"))
    return results
