"""Linguistics verifier.

Strengthens the scripture / source-hierarchy path with deterministic checks
on original-language claims. Per `00_CANON/PRIMARY_RULESET.md §5`: original
source languages first; English is explanatory only. The linguistics
verifier puts that rule into computational form by checking claims against
Strong's lexicon (Layer 0 bridge between original-language text and the
WEB English translation).

Checks performed:

  * `linguistics.strongs_resolution` — a Strong's number resolves to a
    real lexicon entry (G1-G5624 Greek NT, H1-H8674 Hebrew OT).
  * `linguistics.word_count` — a claimed occurrence count matches the
    corpus count for that Strong's number.
  * `linguistics.transliteration` — a claimed Romanization matches the
    lexicon's transliteration (after diacritic-stripping normalization).
  * `linguistics.gloss_consistency` — a claimed English gloss has at
    least one substantive (≥3-char) token in common with the Strong's
    short / KJV definition.
  * `linguistics.cognate` — two Strong's numbers share a derivational
    root (either appears in the other's `derivation` field, or their
    lemmas share a common 4-char prefix after diacritic stripping).

LING_VERIFY packet shape (any subset of fields, all optional):
    {
      "strongs": "G26",                       # for strongs_resolution
      "claimed_count": 36,                    # paired with strongs
      "transliteration_claim": "agape",       # paired with strongs
      "gloss_claim": "love",                  # paired with strongs
      "cognate_pair": ["G25", "G26"],         # for cognate (independent)
    }

Layer 0 dependence: this verifier delegates lookup to
`scripture.word_study(strongs)`. If the Layer 0 source has not been
provisioned (no `lw/00_source/web/web.db` etc.) the lookup returns
`source_missing` and every linguistics check returns NOT_APPLICABLE
rather than ERROR — same graceful-degradation contract scripture uses.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


_STRONGS_PATTERN = re.compile(r"^[GHgh]\d+$")
_TRANSLIT_NONALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_translit(s: Optional[str]) -> str:
    """Lowercase, strip combining marks, drop non-alphanumeric.

    Lets us accept ``'agape'`` as equivalent to ``'agápē'``, ``'agápe'``,
    or ``'AGAPE'``. The lexicon uses the diacritical form; published
    claims usually use the bare ASCII form.
    """
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    no_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    return _TRANSLIT_NONALNUM.sub("", no_marks.lower())


def _is_valid_strongs(s: Any) -> bool:
    return bool(s and _STRONGS_PATTERN.match(str(s)))


def _word_study(strongs: str) -> Dict[str, Any]:
    """Look up a Strong's number via the scripture verifier's helper.

    Imported lazily so this module loads even when scripture's Layer 0
    hooks aren't available (e.g. during unit tests that exercise
    transliteration normalization without touching the DB).
    """
    from . import scripture as _scr
    return _scr.word_study(strongs) or {}


def _layer0_unavailable(info: Dict[str, Any]) -> bool:
    """True when the lexicon lookup returned no usable content.

    The scripture layer's `word_study` returns ``status='source_missing'``
    when the WEB / Strong's database isn't provisioned, and
    ``status='not_found'`` when it couldn't find verse occurrences in the
    corpus — but the latter case can still have a populated lexicon entry
    (word, transliteration, definition, derivation), which is exactly what
    the linguistics verifier needs. Treat 'source_missing' as fatal; for
    everything else, fall back to checking whether at least one lexicon
    field is populated.
    """
    if not info:
        return True
    if info.get("status") == "source_missing":
        return True
    if (info.get("word") or info.get("transliteration")
            or info.get("definition") or info.get("derivation")):
        return False
    return True


def verify_strongs_resolution(strongs: str) -> VerifierResult:
    """A Strong's number must resolve to a real lexicon entry."""
    name = "linguistics.strongs_resolution"
    if not strongs:
        return na(name)
    if not _is_valid_strongs(strongs):
        return mismatch(name,
                        f"{strongs!r} is not a valid Strong's identifier "
                        f"(expected 'G####' for Greek NT or 'H####' for Hebrew OT)",
                        {"strongs": strongs})
    try:
        result = _word_study(strongs)
    except Exception as e:
        return error(name, f"word_study failed: {type(e).__name__}: {e}")
    if _layer0_unavailable(result):
        return na(name, f"Strong's data unavailable for {strongs}")
    word = result.get("word") or ""
    translit = result.get("transliteration") or ""
    if word or translit:
        return confirm(
            name,
            f"{strongs} resolves to {word!r} ({translit!r})",
            {"strongs": strongs, "word": word, "transliteration": translit},
        )
    return mismatch(name, f"{strongs} did not resolve (lookup returned no word/translit)",
                    {"strongs": strongs, "raw": result})


def verify_word_count(strongs: str, claimed_count: Any) -> VerifierResult:
    """A claimed occurrence count must match the corpus count."""
    name = "linguistics.word_count"
    if not strongs or claimed_count is None:
        return na(name)
    if not _is_valid_strongs(strongs):
        return mismatch(name,
                        f"{strongs!r} is not a valid Strong's identifier",
                        {"strongs": strongs})
    try:
        claimed = int(claimed_count)
    except (TypeError, ValueError):
        return error(name, f"claimed_count must be an integer, got {claimed_count!r}")
    try:
        result = _word_study(strongs)
    except Exception as e:
        return error(name, f"word_study failed: {type(e).__name__}: {e}")
    if _layer0_unavailable(result):
        return na(name, f"Strong's data unavailable for {strongs}")
    actual = result.get("occurrence_count")
    if actual is None:
        return na(name, f"no occurrence_count available for {strongs}")
    if claimed == actual:
        return confirm(name,
                       f"{strongs} occurs {actual} times in the corpus, matching claim",
                       {"strongs": strongs, "claimed": claimed, "actual": actual})
    return mismatch(name,
                    f"{strongs} claimed {claimed} occurrences, corpus has {actual}",
                    {"strongs": strongs, "claimed": claimed, "actual": actual})


def verify_transliteration(strongs: str, claimed: str) -> VerifierResult:
    """A claimed transliteration must match the lexicon's after normalization."""
    name = "linguistics.transliteration"
    if not strongs or not claimed:
        return na(name)
    if not _is_valid_strongs(strongs):
        return mismatch(name,
                        f"{strongs!r} is not a valid Strong's identifier",
                        {"strongs": strongs})
    try:
        result = _word_study(strongs)
    except Exception as e:
        return error(name, f"word_study failed: {type(e).__name__}: {e}")
    if _layer0_unavailable(result):
        return na(name, "Strong's data unavailable")
    actual = result.get("transliteration") or ""
    if not actual:
        defn = result.get("definition") or {}
        if isinstance(defn, dict):
            actual = defn.get("translit") or ""
    if not actual:
        return na(name, f"no transliteration available for {strongs}")
    if _normalize_translit(claimed) == _normalize_translit(actual):
        return confirm(name,
                       f"{strongs} transliteration {claimed!r} matches lexicon {actual!r}",
                       {"strongs": strongs, "claimed": claimed, "lexicon": actual})
    return mismatch(name,
                    f"{strongs} claimed transliteration {claimed!r} != lexicon {actual!r}",
                    {"strongs": strongs, "claimed": claimed, "lexicon": actual})


def verify_gloss(strongs: str, claimed_gloss: str) -> VerifierResult:
    """Token overlap between claimed gloss and lexicon definition."""
    name = "linguistics.gloss_consistency"
    if not strongs or not claimed_gloss:
        return na(name)
    if not _is_valid_strongs(strongs):
        return mismatch(name,
                        f"{strongs!r} is not a valid Strong's identifier",
                        {"strongs": strongs})
    try:
        result = _word_study(strongs)
    except Exception as e:
        return error(name, f"word_study failed: {type(e).__name__}: {e}")
    if _layer0_unavailable(result):
        return na(name, "Strong's data unavailable")
    defn = result.get("definition") or {}
    haystack_parts = []
    if isinstance(defn, dict):
        haystack_parts.append(defn.get("strongs_def", "") or "")
        haystack_parts.append(defn.get("kjv_def", "") or "")
    haystack = " ".join(haystack_parts).lower()
    needle = str(claimed_gloss).lower().strip()
    tokens = re.findall(r"[a-z]{3,}", needle)
    if not tokens:
        return na(name, "claimed_gloss has no substantive tokens (≥3 chars)")
    matched = [t for t in tokens if t in haystack]
    if matched:
        return confirm(name,
                       f"{strongs} gloss {claimed_gloss!r} matches lexicon "
                       f"(token overlap: {matched})",
                       {"strongs": strongs, "claimed": claimed_gloss,
                        "matched_tokens": matched})
    return mismatch(name,
                    f"{strongs} claimed gloss {claimed_gloss!r} has no token overlap "
                    f"with lexicon definition",
                    {"strongs": strongs, "claimed": claimed_gloss,
                     "lexicon_excerpt": haystack[:200]})


def _root_prefix(s: Optional[str], n: int = 4) -> str:
    """First n chars of a word after lowercasing + stripping combining marks.

    Used as a rough cognate signal when neither side's `derivation` field
    explicitly names the other.
    """
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    no_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_marks.lower()[:n]


def verify_cognate(pair: List[str]) -> VerifierResult:
    """Two Strong's are cognate if either's derivation references the other,
    or their lemmas share a common 4-char prefix after normalization."""
    name = "linguistics.cognate"
    if not pair or not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return na(name)
    a, b = pair[0], pair[1]
    if not _is_valid_strongs(a) or not _is_valid_strongs(b):
        return mismatch(name,
                        f"cognate pair members must be valid Strong's identifiers, "
                        f"got {a!r} and {b!r}",
                        {"a": a, "b": b})
    try:
        info_a = _word_study(a)
        info_b = _word_study(b)
    except Exception as e:
        return error(name, f"word_study failed: {type(e).__name__}: {e}")
    if _layer0_unavailable(info_a):
        return na(name, f"Strong's data unavailable for {a}")
    if _layer0_unavailable(info_b):
        return na(name, f"Strong's data unavailable for {b}")
    deriv_a = info_a.get("derivation") or ""
    deriv_b = info_b.get("derivation") or ""
    word_a = info_a.get("word") or ""
    word_b = info_b.get("word") or ""
    a_in_b = a in deriv_b
    b_in_a = b in deriv_a
    same_root = bool(word_a and word_b and _root_prefix(word_a) == _root_prefix(word_b))
    reasons = []
    if a_in_b:
        reasons.append(f"{b} derivation references {a}")
    if b_in_a:
        reasons.append(f"{a} derivation references {b}")
    if same_root and not (a_in_b or b_in_a):
        reasons.append(f"{word_a!r} and {word_b!r} share a 4-char root prefix")
    data = {"a": a, "b": b, "word_a": word_a, "word_b": word_b,
            "derivation_a": deriv_a, "derivation_b": deriv_b}
    if reasons:
        return confirm(name, "cognate: " + "; ".join(reasons), data)
    return mismatch(name,
                    f"{a} ({word_a!r}) and {b} ({word_b!r}) show no shared root in either derivation",
                    data)


def verify_transliteration_normalized_match(a: str, b: str) -> VerifierResult:
    """Check whether two transliterations are equivalent after diacritic normalization.

    DB-free: compares purely via _normalize_translit (strip combining marks + non-alphanumeric).
    Useful for confirming that 'agape' is an acceptable normalized form of 'agapē'.
    """
    name = "linguistics.transliteration_normalized_match"
    if not a or not b:
        return na(name, "both transliteration_a and transliteration_b required")
    na_a = _normalize_translit(a)
    na_b = _normalize_translit(b)
    match = na_a == na_b
    data = {"transliteration_a": a, "transliteration_b": b,
            "normalized_a": na_a, "normalized_b": na_b, "match": match}
    if match:
        return confirm(name,
                       f"{a!r} and {b!r} are equivalent after diacritic normalization",
                       data)
    return mismatch(name,
                    f"{a!r} ({na_a!r}) ≠ {b!r} ({na_b!r}) after diacritic normalization",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch every applicable linguistics check for the packet's LING_VERIFY block."""
    results: List[VerifierResult] = []
    lv = packet.get("LING_VERIFY") or {}

    strongs = lv.get("strongs")
    if strongs:
        results.append(verify_strongs_resolution(strongs))
        if "claimed_count" in lv:
            results.append(verify_word_count(strongs, lv["claimed_count"]))
        if "transliteration_claim" in lv:
            results.append(verify_transliteration(strongs, lv["transliteration_claim"]))
        if "gloss_claim" in lv:
            results.append(verify_gloss(strongs, lv["gloss_claim"]))

    if "cognate_pair" in lv:
        results.append(verify_cognate(lv["cognate_pair"]))

    if "transliteration_a" in lv and "transliteration_b" in lv:
        results.append(verify_transliteration_normalized_match(
            lv["transliteration_a"], lv["transliteration_b"]
        ))

    if not results:
        results.append(na("linguistics", "no LING_VERIFY artifacts present"))
    return results
