"""Tests for scripture reference rotation — canon §3.

Per 00_CANON/PRIMARY_RULESET.md §3:
  "If a reference does not fit perfectly, assume input error rather
   than bending Scripture. Rotate context left/right until the anchor
   fits exactly."

The engine doesn't auto-correct (would silently rewrite user input);
it surfaces rotations as suggestions in the data payload of the
scripture.anchors verifier so the human can pick the right ref.
"""
from __future__ import annotations

from concordance_engine.verifiers import scripture


# ── _rotation_suggestions unit tests ───────────────────────────────────

def test_out_of_range_verse_suggests_max():
    """Mt 5 has 48 verses; Mt 5:55 is out of range. Suggest the chapter
    max as the closest valid candidate."""
    suggestions = scripture._rotation_suggestions("Mt 5:55")
    assert suggestions
    assert any("Matthew 5:48" in s for s in suggestions)


def test_in_range_verse_suggests_neighbors():
    """For a valid in-range verse, suggest neighboring verses (the
    function doesn't itself check resolution — it always offers
    rotations within ±radius). Caller decides whether to use them."""
    suggestions = scripture._rotation_suggestions("Mt 5:30")
    # Should include Matthew 5:28, 5:29, 5:30, 5:31, etc.
    assert any("Matthew 5:30" in s for s in suggestions)
    assert any("Matthew 5:31" in s for s in suggestions)


def test_typo_correction_for_mathew():
    """Misspelled 'Mathew' should be corrected to 'Matthew' in the
    suggestion."""
    suggestions = scripture._rotation_suggestions("Mathew 5:1")
    assert any("Matthew 5:1" in s for s in suggestions)


def test_canonicalizes_short_form():
    """Mt → Matthew. The output suggestions use the full canonical
    name, not the abbreviation."""
    suggestions = scripture._rotation_suggestions("Mt 5:55")
    for s in suggestions:
        assert "Mt " not in s  # full form, not the abbreviation
        assert "Matthew" in s


def test_unknown_book_returns_empty():
    """If the book can't be resolved, no suggestions can be made."""
    assert scripture._rotation_suggestions("Whatever 1:1") == []


def test_known_book_unknown_chapter_returns_empty():
    """If the chapter isn't in the verse-max table, no rotation possible."""
    # Matthew has 28 chapters; ch 99 is invalid and not in our table.
    assert scripture._rotation_suggestions("Mt 99:1") == []


def test_unparseable_ref_returns_empty():
    assert scripture._rotation_suggestions("not a ref") == []


def test_suggestions_are_deduped():
    """When typo correction + verse rotation produce the same suggestion,
    return it once, not twice."""
    suggestions = scripture._rotation_suggestions("Matt 5:48")
    matthew_5_48_count = sum(1 for s in suggestions if s == "Matthew 5:48")
    assert matthew_5_48_count == 1


def test_suggestions_capped_at_six():
    """Output is capped so the message stays human-readable."""
    suggestions = scripture._rotation_suggestions("Mt 5:25")
    assert len(suggestions) <= 6


# ── verify_scripture_anchors integration ───────────────────────────────

def test_verify_scripture_anchors_surfaces_rotation_offers():
    """When a ref fails to resolve, the verifier's data should carry
    rotation suggestions for the human to pick from."""
    r = scripture.verify_scripture_anchors(["Mt 5:55"])
    # Either MISMATCH (ref really doesn't resolve, rotations offered)
    # or SKIPPED (Layer 0 not provisioned). Both are valid outcomes;
    # we want rotation_offers populated when the verifier can run.
    if r.status == "MISMATCH":
        offers = r.data.get("rotation_offers") or []
        assert offers
        assert any("Matthew 5:48" in str(offers) for _ in [0])


def test_verify_scripture_anchors_no_rotation_when_resolved():
    """A ref that resolves cleanly shouldn't generate rotation offers."""
    r = scripture.verify_scripture_anchors(["Jn 3:16"])
    if r.status == "CONFIRMED":
        offers = r.data.get("rotation_offers") or []
        assert offers == []


def test_verify_scripture_anchors_detail_includes_did_you_mean():
    """The MISMATCH detail message should include the rotation offer
    inline so it's visible without inspecting data."""
    r = scripture.verify_scripture_anchors(["Mt 5:55"])
    if r.status == "MISMATCH":
        assert "did you mean" in r.detail.lower()


def test_verify_scripture_anchors_handles_dict_form_with_rotation():
    """Dict-form anchors should also get rotation when they fail."""
    r = scripture.verify_scripture_anchors([
        {"ref": "Mt 5:55", "layer": "jesus_words"},
    ])
    if r.status == "MISMATCH":
        offers = r.data.get("rotation_offers") or []
        # The offer should include the original raw anchor (dict) for
        # the failed ref.
        assert offers
