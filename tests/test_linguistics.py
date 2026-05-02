"""Tests for the linguistics verifier.

Exercises Strong's resolution, word-count, transliteration, gloss, and
cognate checks against the live Layer 0 lexicon when available, falling
back to NA verdicts when the lexicon isn't provisioned. The tests mostly
cover the canonical agápē / agapáō (G26 / G25) pair which is the
worked example in the verifier docstring.
"""
from __future__ import annotations

from concordance_engine.verifiers import linguistics as ling
from concordance_engine.verifiers.base import VerifierResult


def _layer0_available() -> bool:
    """True if the WEB / Strong's data is provisioned. Most tests degrade
    gracefully to NA when this is False."""
    info = ling._word_study("G26")
    return bool(info and info.get("status") not in ("source_missing", "not_found")
                and (info.get("word") or info.get("transliteration")))


# ── Pure utility tests (no Layer 0 dependence) ─────────────────────────

def test_normalize_translit_strips_diacritics_and_case():
    assert ling._normalize_translit("agápē") == "agape"
    assert ling._normalize_translit("AGAPE") == "agape"
    assert ling._normalize_translit("agápe") == "agape"
    assert ling._normalize_translit("  agápē  ") == "agape"
    assert ling._normalize_translit(None) == ""
    assert ling._normalize_translit("") == ""


def test_is_valid_strongs_pattern():
    assert ling._is_valid_strongs("G26")
    assert ling._is_valid_strongs("H1")
    assert ling._is_valid_strongs("G5624")
    assert ling._is_valid_strongs("g26")  # case-insensitive intentional
    assert not ling._is_valid_strongs("Greek26")
    assert not ling._is_valid_strongs("26")
    assert not ling._is_valid_strongs("")
    assert not ling._is_valid_strongs(None)


def test_root_prefix():
    # NFKD on ἀγάπη decomposes the precomposed accented chars and the
    # combining marks (breathing, accent) get stripped, leaving plain
    # lowercase Greek letters. First 4: αγαπ.
    assert ling._root_prefix("ἀγάπη", n=4) == "αγαπ"
    # Same input → same prefix
    assert ling._root_prefix("agape") == ling._root_prefix("agape")
    assert ling._root_prefix(None) == ""
    assert ling._root_prefix("") == ""


# ── Strong's-pattern validation (no Layer 0 needed) ────────────────────

def test_strongs_resolution_rejects_invalid_pattern():
    r = ling.verify_strongs_resolution("not-a-strongs")
    assert isinstance(r, VerifierResult)
    assert r.status == "MISMATCH"
    assert "not a valid Strong's identifier" in r.detail


def test_word_count_rejects_invalid_pattern():
    r = ling.verify_word_count("xyz", 36)
    assert r.status == "MISMATCH"


def test_transliteration_rejects_invalid_pattern():
    r = ling.verify_transliteration("garbage", "agape")
    assert r.status == "MISMATCH"


def test_cognate_rejects_invalid_pattern():
    r = ling.verify_cognate(["G25", "not-a-strongs"])
    assert r.status == "MISMATCH"


def test_cognate_handles_short_pair():
    r = ling.verify_cognate(["G25"])
    assert r.status == "NOT_APPLICABLE"


def test_run_with_no_artifacts_returns_na():
    r = ling.run({"domain": "linguistics"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


# ── Layer 0-dependent tests (skip if data missing) ─────────────────────

def test_strongs_resolution_real_lookup():
    if not _layer0_available():
        r = ling.verify_strongs_resolution("G26")
        assert r.status == "NOT_APPLICABLE"
        return
    r = ling.verify_strongs_resolution("G26")
    assert r.status == "CONFIRMED", f"expected CONFIRMED, got {r.status}: {r.detail}"


def test_word_count_correct_match():
    if not _layer0_available():
        return  # NA path covered by other tests
    r = ling.verify_word_count("G26", 36)
    assert r.status == "CONFIRMED", f"expected CONFIRMED, got {r.status}: {r.detail}"


def test_word_count_wrong_count_is_mismatch():
    if not _layer0_available():
        return
    r = ling.verify_word_count("G26", 116)
    assert r.status == "MISMATCH"
    assert "claimed 116" in r.detail


def test_transliteration_accepts_ascii_form():
    if not _layer0_available():
        return
    r = ling.verify_transliteration("G26", "agape")
    assert r.status == "CONFIRMED", f"got {r.status}: {r.detail}"


def test_transliteration_rejects_wrong_word():
    if not _layer0_available():
        return
    r = ling.verify_transliteration("G26", "phobos")
    assert r.status == "MISMATCH"


def test_gloss_token_overlap():
    if not _layer0_available():
        return
    # 'love' should appear in the strongs_def for G26 ('love, i.e. affection...')
    r = ling.verify_gloss("G26", "love")
    assert r.status == "CONFIRMED", f"got {r.status}: {r.detail}"


def test_gloss_no_overlap_is_mismatch():
    if not _layer0_available():
        return
    r = ling.verify_gloss("G26", "hatred")
    assert r.status == "MISMATCH"


def test_cognate_g25_g26_share_root():
    if not _layer0_available():
        return
    # G26 (ἀγάπη) derives from G25 (ἀγαπάω) — derivation field references G25.
    r = ling.verify_cognate(["G25", "G26"])
    assert r.status == "CONFIRMED", f"got {r.status}: {r.detail}"


def test_run_dispatches_all_applicable_checks():
    if not _layer0_available():
        return
    packet = {
        "domain": "linguistics",
        "LING_VERIFY": {
            "strongs": "G26",
            "claimed_count": 36,
            "transliteration_claim": "agape",
            "gloss_claim": "love",
            "cognate_pair": ["G25", "G26"],
        },
    }
    results = ling.run(packet)
    statuses = [r.status for r in results]
    # 5 checks dispatched: resolution, count, translit, gloss, cognate
    assert len(results) == 5
    assert statuses.count("CONFIRMED") == 5, f"expected 5 CONFIRMED, got {statuses}"


def test_engine_dispatches_linguistics_domain():
    """Smoke test that the engine's run_for_domain finds the linguistics module."""
    from concordance_engine.verifiers import run_for_domain
    if not _layer0_available():
        return
    packet = {
        "domain": "linguistics",
        "LING_VERIFY": {"strongs": "G26", "claimed_count": 36},
    }
    results = run_for_domain("linguistics", packet)
    # Should have linguistics.* results plus scripture.* (cross-cutting, no anchors -> no result)
    ling_results = [r for r in results if r.name.startswith("linguistics.")]
    assert len(ling_results) >= 2, f"expected linguistics results, got {[r.name for r in results]}"
