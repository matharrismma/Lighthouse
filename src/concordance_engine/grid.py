"""Grid registry — make the pattern visible.

The 36 axes form a graph along seven dimensional axes. Domains that
share a dimension are *adjacent*. Domains that sit on three or more
dimensions are *structurally deep*. This module exposes the mapping as
data so other surfaces (CLI, future web UI, agent JSON) can render it.

The mapping is a proposal, not a closed claim. Discovery, not design:
when an axis sits clearly on a dimension, mark it; when it doesn't,
leave it off. Surface the cluster the data shows; don't force one.

Run as a CLI:
    python -m concordance_engine.grid              # matrix
    python -m concordance_engine.grid depth        # axes ranked by dimension count
    python -m concordance_engine.grid adjacent X   # axes that share a dimension with X
    python -m concordance_engine.grid dimension D  # axes on dimension D
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List, Tuple


# The seven dimensional axes (Matt 2026-05-02 grid_connections framing).
DIMENSIONS: Tuple[str, ...] = (
    "encoding",            # information / symbols / codes
    "metabolism",          # lifecycle / transformation / flow of substance
    "reasoning",           # formal manipulation / proof / counting
    "physical_substance",  # space / matter / energy / spatial form
    "authority_trust",     # who-says-so / consensus / source hierarchy
    "time_sequence",       # ordering / period / when-it-happens
    "conservation_balance",# what-must-balance / equilibrium / invariants
)


# Each axis → frozenset of dimensions it sits on. Empty set is allowed in
# principle but typically signals the mapping is incomplete; no axis
# should remain there for long.
AXIS_DIMENSIONS: Dict[str, FrozenSet[str]] = {
    # Foundational
    "chemistry":           frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "physics":             frozenset({"physical_substance", "conservation_balance"}),
    "mathematics":         frozenset({"reasoning"}),
    "statistics":          frozenset({"reasoning"}),
    "computer_science":    frozenset({"encoding", "reasoning", "time_sequence"}),
    "biology":             frozenset({"encoding", "metabolism", "physical_substance", "conservation_balance"}),
    "governance":          frozenset({"reasoning", "authority_trust", "time_sequence"}),
    "scripture":           frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    "linguistics":         frozenset({"encoding", "reasoning"}),
    "formal_logic":        frozenset({"reasoning"}),

    # Applied / engineering
    "cryptography":        frozenset({"encoding", "reasoning", "authority_trust"}),
    "manufacturing":       frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
    "finance":             frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
    "astronomy":           frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
    "calendar_time":       frozenset({"time_sequence"}),
    "networking":          frozenset({"encoding", "physical_substance", "authority_trust", "time_sequence"}),
    "electrical":          frozenset({"physical_substance", "conservation_balance"}),
    "acoustics":           frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
    "optics":              frozenset({"physical_substance", "conservation_balance"}),
    "document_validation": frozenset({"encoding", "authority_trust"}),
    "photography":         frozenset({"encoding", "physical_substance"}),

    # Earth / physical-substance
    "geology":             frozenset({"metabolism", "physical_substance", "time_sequence"}),
    "geography":           frozenset({"physical_substance"}),
    "meteorology":         frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
    "hydrology":           frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),

    # Formal / counting
    "number_theory":       frozenset({"reasoning"}),
    "combinatorics":       frozenset({"reasoning"}),
    "geometry":            frozenset({"reasoning", "physical_substance"}),
    "music_theory":        frozenset({"encoding", "reasoning", "physical_substance"}),

    # Information
    "information_theory":  frozenset({"encoding", "reasoning"}),

    # Statistics application
    "sports_analytics":    frozenset({"reasoning", "time_sequence"}),

    # Biology umbrella subsystems
    "genetics":            frozenset({"encoding", "physical_substance"}),
    "agriculture":         frozenset({"metabolism", "physical_substance", "time_sequence"}),
    "nutrition":           frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "exercise_science":    frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),

    # Meta — the 36th axis. Witness sits on the dimensions it enforces:
    # encoding (the result schema), reasoning (the trace), authority_trust
    # (the source hierarchy), and time_sequence (the gate chain order).
    "witness":             frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
}


# Umbrella relationships — these are the structural parents documented in
# the discovery_not_design memory. Subsystems remain first-class axes but
# the umbrella connects them.
UMBRELLAS: Dict[str, Tuple[str, ...]] = {
    "biology":    ("genetics", "agriculture", "nutrition", "exercise_science"),
    "governance": (),  # business / household / education / church are aliases of governance, not separate axes
}


# ── API ────────────────────────────────────────────────────────────────

def axis_dimensions(axis: str) -> FrozenSet[str]:
    """Dimensions an axis sits on. Raises KeyError for unknown axes."""
    return AXIS_DIMENSIONS[axis]


def dimension_axes(dimension: str) -> List[str]:
    """All axes that sit on a given dimension."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}; valid: {DIMENSIONS}")
    return sorted(a for a, ds in AXIS_DIMENSIONS.items() if dimension in ds)


def depth(axis: str) -> int:
    """Number of dimensions an axis sits on. ≥3 = structurally deep."""
    return len(AXIS_DIMENSIONS[axis])


def adjacent(axis: str) -> List[Tuple[str, FrozenSet[str]]]:
    """Other axes that share at least one dimension with this axis,
    paired with the shared-dimension set. Sorted by overlap descending."""
    src = AXIS_DIMENSIONS[axis]
    out: List[Tuple[str, FrozenSet[str]]] = []
    for other, dims in AXIS_DIMENSIONS.items():
        if other == axis:
            continue
        shared = src & dims
        if shared:
            out.append((other, shared))
    out.sort(key=lambda t: (-len(t[1]), t[0]))
    return out


def deep_axes(min_dimensions: int = 3) -> List[Tuple[str, int]]:
    """Axes ranked by dimension count, descending."""
    ranked = [(a, len(d)) for a, d in AXIS_DIMENSIONS.items() if len(d) >= min_dimensions]
    ranked.sort(key=lambda t: (-t[1], t[0]))
    return ranked


def umbrella_children(parent: str) -> Tuple[str, ...]:
    """Subsystems under an umbrella axis, or () if none."""
    return UMBRELLAS.get(parent, ())


# ── Rendering ──────────────────────────────────────────────────────────

def render_matrix() -> str:
    """Markdown matrix: rows = axes (alphabetical), cols = dimensions."""
    axes = sorted(AXIS_DIMENSIONS.keys())
    short = {
        "encoding": "enc",
        "metabolism": "met",
        "reasoning": "rsn",
        "physical_substance": "phy",
        "authority_trust": "aut",
        "time_sequence": "tim",
        "conservation_balance": "csv",
    }
    header = "| axis | " + " | ".join(short[d] for d in DIMENSIONS) + " | depth |"
    sep = "|------|" + "|".join(["----"] * len(DIMENSIONS)) + "|------:|"
    rows = []
    for a in axes:
        dims = AXIS_DIMENSIONS[a]
        cells = [" x  " if d in dims else "    " for d in DIMENSIONS]
        rows.append(f"| {a:<22} | " + " | ".join(cells) + f" | {len(dims):>5} |")
    return "\n".join([header, sep, *rows])


def render_depth() -> str:
    """Axes ranked by dimensional depth."""
    ranked = sorted(AXIS_DIMENSIONS.items(), key=lambda t: (-len(t[1]), t[0]))
    lines = [f"{len(dims)}  {axis:<22} {' '.join(sorted(dims))}" for axis, dims in ranked]
    return "\n".join(lines)


def render_adjacent(axis: str) -> str:
    """Adjacency report for a single axis."""
    if axis not in AXIS_DIMENSIONS:
        return f"unknown axis: {axis}"
    own = sorted(AXIS_DIMENSIONS[axis])
    lines = [f"{axis} sits on: {', '.join(own)}", "", "shares dimensions with:"]
    for other, shared in adjacent(axis):
        lines.append(f"  {len(shared)}  {other:<22} {' '.join(sorted(shared))}")
    return "\n".join(lines)


def render_dimension(dim: str) -> str:
    """All axes on a given dimension."""
    if dim not in DIMENSIONS:
        return f"unknown dimension: {dim}; valid: {', '.join(DIMENSIONS)}"
    axes = dimension_axes(dim)
    return f"axes on {dim} ({len(axes)}):\n" + "\n".join(f"  {a}" for a in axes)


# ── CLI ────────────────────────────────────────────────────────────────

def _main(argv: List[str]) -> int:
    if len(argv) <= 1:
        print(render_matrix())
        return 0
    cmd = argv[1]
    if cmd == "depth":
        print(render_depth())
        return 0
    if cmd == "adjacent" and len(argv) >= 3:
        print(render_adjacent(argv[2]))
        return 0
    if cmd == "dimension" and len(argv) >= 3:
        print(render_dimension(argv[2]))
        return 0
    print("usage: python -m concordance_engine.grid [depth | adjacent <axis> | dimension <dim>]")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv))
