"""Tests for the grid registry — keeps the axis ↔ dimension mapping
in sync with the verifier registry, and locks in core API shape."""
from __future__ import annotations

import pytest

from concordance_engine import grid
from concordance_engine.verifiers import VERIFIERS, CROSS_CUTTING_VERIFIERS


# Aliases in the VERIFIERS dict that point to the same underlying module
# don't need their own grid entry — the canonical name covers them.
ALIAS_TO_CANONICAL = {
    "cs": "computer_science",
    "business": "governance",
    "household": "governance",
    "education": "governance",
    "church": "governance",
    "logic": "formal_logic",
    "cryptology": "cryptography",
    "exercise": "exercise_science",
    "calendar": "calendar_time",
    "time": "calendar_time",
    "network": "networking",
    "electrical_engineering": "electrical",
    "earth_science": "geology",
    "info_theory": "information_theory",
    "doc_validation": "document_validation",
    "music": "music_theory",
    "weather": "meteorology",
    "water": "hydrology",
    "photo": "photography",
    "sports": "sports_analytics",
    "power": "energy",
    "off_grid": "energy",
    "testimony": "witness",
}


def _canonical_axes_from_registry():
    canonical = set()
    for name in VERIFIERS:
        canonical.add(ALIAS_TO_CANONICAL.get(name, name))
    # Cross-cutting verifiers (scripture) aren't in the VERIFIERS dict
    # but are first-class axes that the grid must map.
    for mod in CROSS_CUTTING_VERIFIERS:
        canonical.add(mod.__name__.rsplit(".", 1)[-1])
    return canonical


# ── Registry sync ──────────────────────────────────────────────────────

def test_every_verifier_has_a_grid_entry():
    """Adding a new verifier must add a grid mapping. This test catches
    the case where someone wires a new domain but forgets the grid."""
    canonical = _canonical_axes_from_registry()
    missing = canonical - set(grid.AXIS_DIMENSIONS.keys())
    assert not missing, f"verifiers without grid mapping: {sorted(missing)}"


def test_every_grid_entry_has_a_verifier_or_is_a_subsystem():
    """The reverse: every grid entry should correspond to a registered
    verifier (or be a known umbrella subsystem)."""
    canonical = _canonical_axes_from_registry()
    extra = set(grid.AXIS_DIMENSIONS.keys()) - canonical
    # Subsystems of any umbrella axis are first-class axes in the grid
    # but verified via the parent module (e.g. physics_conservation via physics).
    allowed_extra: set = set()
    for children in grid.UMBRELLAS.values():
        allowed_extra.update(children)
    truly_extra = extra - allowed_extra
    assert not truly_extra, f"grid entries without a verifier: {sorted(truly_extra)}"


def test_axis_count_at_or_above_baseline():
    """The grid grows over time as new axes are discovered. The
    baseline at the V1 alignment commit is 37 (35 content axes +
    witness + phase). Future commits may add more; this test catches
    accidental losses without freezing the count."""
    assert len(grid.AXIS_DIMENSIONS) >= 37


def test_all_dimensions_have_at_least_one_axis():
    """A dimension with no axes is dead weight — either remove it or map
    something to it. Catches stale dimensions."""
    for dim in grid.DIMENSIONS:
        axes = grid.dimension_axes(dim)
        assert axes, f"dimension {dim!r} has no axes — remove or map something"


def test_every_axis_sits_on_at_least_one_dimension():
    """An axis with no dimensions is invisible to the grid view."""
    for axis, dims in grid.AXIS_DIMENSIONS.items():
        assert dims, f"axis {axis!r} sits on no dimensions"


def test_all_dimension_references_are_valid():
    """No typos in the dimension names."""
    valid = set(grid.DIMENSIONS)
    for axis, dims in grid.AXIS_DIMENSIONS.items():
        bad = dims - valid
        assert not bad, f"axis {axis!r} references unknown dimensions: {bad}"


# ── API ────────────────────────────────────────────────────────────────

def test_axis_dimensions_returns_frozenset():
    d = grid.axis_dimensions("witness")
    assert isinstance(d, frozenset)
    assert "encoding" in d


def test_axis_dimensions_unknown_raises():
    with pytest.raises(KeyError):
        grid.axis_dimensions("not_a_real_axis")


def test_dimension_axes_unknown_raises():
    with pytest.raises(ValueError):
        grid.dimension_axes("not_a_real_dimension")


def test_depth_witness_is_four():
    # Witness sits on encoding, reasoning, authority_trust, time_sequence.
    assert grid.depth("witness") == 4


def test_depth_calendar_time_is_one():
    assert grid.depth("calendar_time") == 1


def test_adjacent_witness_includes_scripture():
    # Witness and scripture share authority_trust, encoding, reasoning,
    # time_sequence — heavy overlap.
    neighbors = dict(grid.adjacent("witness"))
    assert "scripture" in neighbors
    assert len(neighbors["scripture"]) >= 3


def test_adjacent_returns_sorted_by_overlap_desc():
    adj = grid.adjacent("witness")
    overlaps = [len(s) for _, s in adj]
    assert overlaps == sorted(overlaps, reverse=True)


def test_deep_axes_excludes_shallow():
    deep = dict(grid.deep_axes(min_dimensions=4))
    assert "calendar_time" not in deep
    assert "geography" not in deep
    # Multi-axis domains should appear: biology (4), meteorology (4),
    # hydrology (4), manufacturing (4), networking (4), finance (4),
    # exercise_science (4), scripture (4), witness (4).
    assert "biology" in deep
    assert "witness" in deep


def test_umbrella_biology_has_four_subsystems():
    children = grid.umbrella_children("biology")
    assert set(children) == {"genetics", "agriculture", "nutrition", "exercise_science"}


def test_umbrella_unknown_returns_empty():
    assert grid.umbrella_children("not_an_umbrella") == ()


# ── Umbrella coherence ─────────────────────────────────────────────────

def test_all_umbrellas_are_coherent():
    """Every umbrella's dimensions must subsume its subsystems' union.
    Catches the case where a subsystem carries a dimension the umbrella
    doesn't — like the audit's biology / time_sequence finding."""
    breaks = grid.verify_umbrella_coherence()
    assert breaks == {}, (
        f"umbrella coherence breaks: {breaks}. "
        "An umbrella must carry every dimension its subsystems carry."
    )


def test_biology_carries_time_sequence_for_subsystem_coherence():
    """Locks in the audit fix: biology must include time_sequence
    because agriculture and exercise_science both sit on it. If the
    dimension is removed from biology, this test catches it."""
    biology_dims = grid.axis_dimensions("biology")
    assert "time_sequence" in biology_dims, (
        "biology umbrella must carry time_sequence — both agriculture "
        "and exercise_science (subsystems) sit on it. Removing it from "
        "biology breaks umbrella coherence."
    )


def test_biology_dimensions_cover_all_subsystem_dimensions():
    """Stronger form of the above: biology's dimension set must be a
    superset of every subsystem's dimension set."""
    biology_dims = grid.axis_dimensions("biology")
    for child in grid.umbrella_children("biology"):
        child_dims = grid.axis_dimensions(child)
        missing = child_dims - biology_dims
        assert not missing, (
            f"biology missing dimensions {sorted(missing)} that "
            f"subsystem {child!r} carries"
        )


# ── Rendering ──────────────────────────────────────────────────────────

def test_render_matrix_includes_every_axis():
    out = grid.render_matrix()
    for axis in grid.AXIS_DIMENSIONS:
        assert axis in out, f"matrix missing axis {axis!r}"


def test_render_matrix_has_header_columns_for_all_dimensions():
    out = grid.render_matrix()
    # Short codes used in the matrix header.
    for code in ("enc", "met", "rsn", "phy", "aut", "tim", "csv"):
        assert code in out


def test_render_depth_lists_all_axes():
    out = grid.render_depth()
    for axis in grid.AXIS_DIMENSIONS:
        assert axis in out


def test_render_adjacent_unknown_axis_returns_message():
    out = grid.render_adjacent("not_an_axis")
    assert "unknown axis" in out


def test_render_dimension_lists_axes_on_that_dimension():
    out = grid.render_dimension("encoding")
    # Some axes that should be on encoding.
    for axis in ("cryptography", "linguistics", "information_theory", "witness"):
        assert axis in out


def test_render_dimension_unknown_returns_message():
    out = grid.render_dimension("not_a_dim")
    assert "unknown dimension" in out
