"""Scaffold registry — make the pattern visible.

The 36 axes live in a *multi-dimensional scaffold* with seven members
(encoding, metabolism, reasoning, physical_substance, authority_trust,
time_sequence, conservation_balance). Each axis has coordinates along
some subset of those members. Axes that share a member are *adjacent*;
axes that sit on three or more are *structurally deep*. The renders
in this module are flat projections of that scaffold — useful for
reading, but each one collapses dimensions a higher-dimensional view
would preserve.

The mapping is a proposal, not a closed claim. Discovery, not design:
when an axis sits clearly on a member, mark it; when it doesn't,
leave it off. Surface the cluster the data shows; don't force one.

Run as a CLI (each subcommand is a different projection):
    python -m concordance_engine.grid              # matrix projection
    python -m concordance_engine.grid depth        # axes ranked by member count
    python -m concordance_engine.grid adjacent X   # neighbors on the scaffold
    python -m concordance_engine.grid dimension D  # axes on a single member
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, FrozenSet, List, Tuple


# The seven scaffold members uncovered so far. Each axis lives at a position
# in this N-dimensional space — present (1) or absent (0) along each member.
# Future axes get appended to this list via the operator-only
# /grid/axis/add endpoint, which persists them to data/grid/axis_extensions
# .jsonl and applies them on next module load.
#
# DIMENSIONS is a list (not a tuple) so it can grow at runtime without
# replacing the binding that callers have already imported. _BASE_DIMENSIONS
# preserves the original 7 for tests and historical reference.
_BASE_DIMENSIONS: Tuple[str, ...] = (
    "encoding",            # information / symbols / codes
    "metabolism",          # lifecycle / transformation / flow of substance
    "reasoning",           # formal manipulation / proof / counting
    "physical_substance",  # space / matter / energy / spatial form
    "authority_trust",     # who-says-so / consensus / source hierarchy
    "time_sequence",       # ordering / period / when-it-happens
    "conservation_balance",# what-must-balance / equilibrium / invariants
)
DIMENSIONS: List[str] = list(_BASE_DIMENSIONS)


# Each axis → frozenset of dimensions it sits on. Empty set is allowed in
# principle but typically signals the mapping is incomplete; no axis
# should remain there for long.
AXIS_DIMENSIONS: Dict[str, FrozenSet[str]] = {
    # Foundational
    "chemistry":           frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "physics":             frozenset({"physical_substance", "conservation_balance", "reasoning"}),
    "mathematics":         frozenset({"reasoning"}),
    "statistics":          frozenset({"reasoning"}),
    "computer_science":    frozenset({"encoding", "reasoning", "time_sequence"}),
    "biology":             frozenset({"encoding", "metabolism", "physical_substance", "conservation_balance", "time_sequence", "discreteness"}),
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

    # Energy — generation, storage, distribution. Sits where chemistry
    # and electrical meet at system scale: matter/fields (physical),
    # flow + transformation (metabolism), capacity-over-window (time),
    # and the first law (conservation). Adjacent to agriculture,
    # manufacturing, hydrology, meteorology, exercise_science.
    "energy":              frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),

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

    # Phase — cross-cutting classifier (Setup/Positioning/Conversion).
    # Sits primarily on time_sequence (phases unfold over time) and
    # reasoning (phase choice is a structured judgment). Doesn't carry
    # substantive content of its own; classifies WHERE in the lifecycle
    # a packet sits.
    "phase":               frozenset({"time_sequence", "reasoning"}),

    # ── New canonical axes + aliases (wave 2026-05-06/07) ─────────────

    # Architecture / construction
    "architecture":        frozenset({"physical_substance", "authority_trust", "time_sequence"}),
    "construction":        frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
    "building":            frozenset({"physical_substance", "time_sequence"}),
    "building_design":     frozenset({"physical_substance", "authority_trust"}),
    "structural":          frozenset({"physical_substance", "conservation_balance"}),

    # Law / labor / economics
    "law":                 frozenset({"reasoning", "authority_trust", "time_sequence"}),
    "legal":               frozenset({"reasoning", "authority_trust", "time_sequence"}),
    "contract":            frozenset({"reasoning", "authority_trust"}),
    "labor":               frozenset({"metabolism", "authority_trust", "time_sequence", "conservation_balance"}),
    "labour":              frozenset({"metabolism", "authority_trust", "time_sequence", "conservation_balance"}),
    "employment":          frozenset({"authority_trust", "time_sequence"}),
    "wages":               frozenset({"reasoning", "conservation_balance"}),
    "economics":           frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
    "economy":             frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
    "macro":               frozenset({"reasoning", "conservation_balance"}),
    "micro":               frozenset({"reasoning", "conservation_balance"}),

    # Real estate / property
    "real_estate":         frozenset({"physical_substance", "authority_trust", "time_sequence", "conservation_balance"}),
    "property":            frozenset({"physical_substance", "authority_trust", "time_sequence"}),
    "mortgage":            frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),

    # Medicine / health
    "medicine":            frozenset({"metabolism", "physical_substance", "authority_trust", "time_sequence"}),
    "medical":             frozenset({"metabolism", "physical_substance", "authority_trust", "time_sequence"}),
    "clinical":            frozenset({"metabolism", "physical_substance", "authority_trust"}),

    # Ecology / environment / soil / oceanography
    "ecology":             frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
    "ecosystem":           frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "environmental":       frozenset({"metabolism", "physical_substance", "time_sequence"}),
    "soil_science":        frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "soil":                frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "agronomy":            frozenset({"metabolism", "physical_substance", "time_sequence"}),
    "oceanography":        frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
    "ocean":               frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "marine_science":      frozenset({"metabolism", "physical_substance", "time_sequence"}),

    # Physics sub-axes (canonical splits)
    "physics_conservation": frozenset({"physical_substance", "conservation_balance"}),
    "physics_dimensional":  frozenset({"physical_substance", "reasoning"}),
    "thermodynamics":      frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "thermo":              frozenset({"metabolism", "physical_substance", "conservation_balance"}),
    "heat":                frozenset({"metabolism", "physical_substance", "conservation_balance"}),

    # Nuclear physics
    "nuclear_physics":     frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
    "nuclear":             frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
    "radioactivity":       frozenset({"physical_substance", "time_sequence"}),

    # Cybersecurity / infosec
    "cybersecurity":       frozenset({"encoding", "reasoning", "authority_trust"}),
    "cyber":               frozenset({"encoding", "reasoning", "authority_trust"}),
    "infosec":             frozenset({"encoding", "authority_trust"}),

    # Quantum computing
    "quantum_computing":   frozenset({"encoding", "reasoning", "physical_substance"}),
    "quantum":             frozenset({"encoding", "reasoning", "physical_substance"}),
    "qc":                  frozenset({"encoding", "reasoning", "physical_substance"}),

    # Operations research / optimization
    "operations_research": frozenset({"reasoning", "time_sequence", "conservation_balance"}),
    "optimization":        frozenset({"reasoning", "conservation_balance"}),
    "or":                  frozenset({"reasoning", "time_sequence", "conservation_balance"}),

    # Philosophy / rhetoric / argumentation
    "philosophy":          frozenset({"reasoning", "authority_trust"}),
    "epistemology":        frozenset({"reasoning", "authority_trust"}),
    "ethics":              frozenset({"reasoning", "authority_trust"}),
    "rhetoric":            frozenset({"encoding", "reasoning", "authority_trust"}),
    "argumentation":       frozenset({"encoding", "reasoning"}),
    "fallacy":             frozenset({"reasoning", "authority_trust"}),

    # Theology / doctrine / scripture sub-axes
    "theology_doctrine":   frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    "theology":            frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    "doctrine":            frozenset({"encoding", "reasoning", "authority_trust"}),
    "scripture_anchors":   frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    "scripture_doctrine":  frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
    "apologetics":         frozenset({"reasoning", "authority_trust"}),
    "eschatology":         frozenset({"reasoning", "authority_trust", "time_sequence"}),

    # Statistics sub-axes
    "statistics_pvalue":              frozenset({"reasoning"}),
    "statistics_multiple_comparisons": frozenset({"reasoning"}),
    "statistics_confidence_interval":  frozenset({"reasoning"}),

    # History / chronology
    "history_chronology":  frozenset({"reasoning", "authority_trust", "time_sequence"}),
    "history":             frozenset({"reasoning", "authority_trust", "time_sequence"}),
    "chronology":          frozenset({"time_sequence"}),

    # Materials science / metallurgy
    "materials_science":   frozenset({"physical_substance", "metabolism", "conservation_balance"}),
    "materials":           frozenset({"physical_substance", "metabolism", "conservation_balance"}),
    "metallurgy":          frozenset({"physical_substance", "metabolism"}),

    # Governance canonical name
    "governance_decision_packet": frozenset({"reasoning", "authority_trust", "time_sequence"}),

    # ── Surfaced 2026-06-10: verifiers that existed but were never placed in the
    # grid (the "we keep finding things" set). Mapped onto the EXISTING 7
    # dimensions — no new dimension is invented here (proposed finer axes like
    # continuity/discreteness/uncertainty remain operator-gated, ATLAS_AXIS_PROPOSAL.md).
    "atomic":              frozenset({"physical_substance", "reasoning", "conservation_balance"}),
    "ephemeris":           frozenset({"physical_substance", "time_sequence", "reasoning"}),
    "layer_zero_grounding": frozenset({"encoding", "authority_trust", "reasoning"}),
    "linear_algebra":      frozenset({"reasoning", "physical_substance"}),
    "periodic_table":      frozenset({"physical_substance", "reasoning", "conservation_balance"}),
    "physical_constants":  frozenset({"physical_substance", "conservation_balance", "reasoning"}),
    "probability":         frozenset({"reasoning", "conservation_balance"}),
    "molecular_geometry":  frozenset({"physical_substance", "reasoning"}),
}


# Umbrella relationships — these are the structural parents documented in
# the discovery_not_design memory. Subsystems remain first-class axes but
# the umbrella connects them.
UMBRELLAS: Dict[str, Tuple[str, ...]] = {
    "biology":    ("genetics", "agriculture", "nutrition", "exercise_science"),
    "chemistry":  ("periodic_table", "molecular_geometry"),
    "geology":    ("soil_science",),
    "governance": ("governance_decision_packet",),
    "physics":    ("physics_conservation", "physics_dimensional", "physical_constants", "atomic"),
    "statistics": (
        "statistics_pvalue",
        "statistics_multiple_comparisons",
        "statistics_confidence_interval",
    ),
    "theology":   ("theology_doctrine", "scripture_anchors", "apologetics", "eschatology"),
}


# ── The two axis-systems (2026-06-20 reclassification) ──────────────────
# The 11 conceptual DIMENSIONS were a conflation of two different KINDS of axis.
# Held apart honestly they are the two trees applied to the axes themselves:
#   MEASURE — physical/embodied axes (how science quantifies; the matrix tree)
#   MEANING — conceptual axes (how meaning structures; the organic/Word tree)
#   BRIDGE  — the math BOTH trees share. This is the harmony-of-science-and-math
#             point itself: invariance, quantization, likelihood live in physics
#             AND in abstract structure.
# NOTE (honest): `order` and `encoding` are borderline (information theory is
# math); their placement is a judgment call that shifts the per-kind counts.
DIMENSION_KIND: Dict[str, str] = {
    "physical_substance": "measure", "conservation_balance": "measure",
    "metabolism": "measure", "time_sequence": "measure",
    "reasoning": "meaning", "authority_trust": "meaning",
    "order": "meaning", "encoding": "meaning",
    "symmetry": "bridge", "discreteness": "bridge", "uncertainty": "bridge",
}

# ── MEASURES: the physical base quantities (dimensional-analysis basis) ──
# Every physical quantity is a product of powers of these. Scale (length) and
# time are two; the rest are listed. These are a DIFFERENT category from the
# conceptual dimensions above — the substrate things are measured against.
# HONEST CAVEAT: the COUNT is a unit convention, not a deep fact. `amount`
# (a mole is a count) and `luminous_intensity` (weighted by the human eye) are
# bookkeeping; the physically fundamental set reduces to ~5 (length, time, mass,
# electric_charge, temperature), and in natural units fewer still. The deep
# things are the QUANTITIES, not their number. Force, energy, momentum, pressure
# are DERIVED from these (e.g. force = mass*length/time^2) — NOT base axes.
MEASURE_AXES: Tuple[str, ...] = (
    "length",            # scale / space
    "time",
    "mass",
    "electric_charge",
    "temperature",
    "amount",            # conventional — a count of entities
    "luminous_intensity",  # conventional — anthropocentric (human photopic response)
)

# ── FORCES: the fundamental interactions (a THIRD list — how things ACT) ──
# Not measures and not meaning. Force is dimensionally DERIVED, so it is not a
# base measure-axis; but the four fundamental interactions ARE a fundamental
# set in their own right (the ones physics seeks to unify).
FORCES: Tuple[str, ...] = ("gravity", "electromagnetism", "strong_nuclear", "weak_nuclear")

# ── META_AXES: placed on the map but verified by BEING the substrate ─────
# A meta-axis is a real grid entry that has no domain verifier and is not a
# subsystem — it is the grounding layer itself (Layer 0), checked by the
# sources it carries, not by a per-domain verifier. Exempt from the
# "every grid entry has a verifier or is a subsystem" rule by design.
META_AXES: FrozenSet[str] = frozenset({"layer_zero_grounding"})


# ── Alias map ──────────────────────────────────────────────────────────
# Deliberate synonyms so natural-language dispatch ("ocean", "thermo",
# "weather") routes to canonical verifiers without forcing the caller
# to know the full name. Each alias points to its canonical.
#
# The structural audit (/grid/coherence) uses this map to distinguish
# *known* aliases (expected redundancy, not a design flaw) from
# *unknown* signature-collisions (real ambiguity — the 7-axis
# resolution can't distinguish two genuinely different things).
ALIASES: Dict[str, str] = {
    # Direct synonyms (different spelling, same thing)
    "labour":               "labor",
    "economy":              "economics",
    "medical":              "medicine",
    "legal":                "law",
    "history":              "history_chronology",

    # Module/discipline name variants
    "materials":            "materials_science",
    "soil":                 "soil_science",
    "thermo":               "thermodynamics",
    "ocean":                "oceanography",
    "cyber":                "cybersecurity",
    "infosec":              "cybersecurity",
    "qc":                   "quantum_computing",
    "quantum":              "quantum_computing",
    "or":                   "operations_research",
    "optimization":         "operations_research",
    "nuclear":              "nuclear_physics",
    "metallurgy":           "materials_science",
    "marine_science":       "oceanography",
    "agronomy":             "soil_science",

    # Concept/phenomenon (not a discipline of its own)
    "heat":                 "thermodynamics",
    "radioactivity":        "nuclear_physics",
    "ecosystem":            "ecology",
    "environmental":        "ecology",

    # Umbrella-bare-names (canonical names exist for sub-verifiers)
    "theology":             "theology_doctrine",
    "scripture":            "scripture_anchors",
    "scripture_doctrine":   "theology_doctrine",
    "doctrine":             "theology_doctrine",
    "apologetics":          "theology_doctrine",
    "eschatology":          "theology_doctrine",

    # Sub-aspects (folded into the canonical discipline)
    "macro":                "economics",
    "micro":                "economics",
    "wages":                "labor",
    "employment":           "labor",
    "mortgage":             "real_estate",
    "property":             "real_estate",
    "building":             "construction",
    "building_design":      "architecture",
    "structural":           "architecture",
    "clinical":             "medicine",
    "contract":             "law",
    "ethics":               "philosophy",
    "epistemology":         "philosophy",
    "fallacy":              "rhetoric",
    "argumentation":        "rhetoric",
    "chronology":           "history_chronology",
}


# ── Retag v2 ───────────────────────────────────────────────────────────
# Pulled directly out of the /grid/coherence audit. After looking at the
# 15 ambiguity clusters where canonical domains shared identical axis
# signatures, each retag below adds the discriminating dimension that
# was missing — chemistry actually does reason (formal lawful behavior);
# manufacturing actually does encode (specs and compliance); statistics_
# pvalue actually does live in time (alpha is preserved within a window).
#
# Applied as an additive overlay on the V1 mapping above. Reversible by
# setting any entry to an empty set or removing it entirely. Audit
# re-runs immediately.
_RETAG_V2: Dict[str, FrozenSet[str]] = {
    # Cluster: [reasoning] only — 8 domains
    "combinatorics":                       frozenset({"conservation_balance"}),
    "statistics":                          frozenset({"conservation_balance"}),
    "statistics_pvalue":                   frozenset({"conservation_balance", "time_sequence"}),
    "statistics_multiple_comparisons":     frozenset({"conservation_balance", "authority_trust"}),
    "statistics_confidence_interval":      frozenset({"conservation_balance", "time_sequence"}),

    # Cluster: [authority_trust + reasoning + time_sequence] — 4 domains
    "governance_decision_packet":          frozenset({"encoding"}),
    "history_chronology":                  frozenset({"encoding", "conservation_balance"}),
    "law":                                 frozenset({"encoding", "conservation_balance"}),

    # Cluster: [authority_trust + encoding + reasoning] — 3 domains
    "cybersecurity":                       frozenset({"physical_substance", "time_sequence"}),
    "rhetoric":                            frozenset({"time_sequence"}),

    # Cluster: [conservation + metabolism + physical + time] — 8 domains
    "construction":                        frozenset({"authority_trust", "reasoning"}),
    "ecology":                             frozenset({"reasoning"}),
    "energy":                              frozenset({"authority_trust"}),
    "exercise_science":                    frozenset({"reasoning"}),
    "manufacturing":                       frozenset({"authority_trust", "encoding"}),
    "meteorology":                         frozenset({"reasoning", "encoding"}),
    "oceanography":                        frozenset({"reasoning", "encoding"}),

    # Cluster: [conservation + metabolism + physical] — 5 domains
    "chemistry":                           frozenset({"reasoning"}),
    "materials_science":                   frozenset({"reasoning", "time_sequence"}),
    "nutrition":                           frozenset({"authority_trust"}),
    "soil_science":                        frozenset({"time_sequence"}),
    "thermodynamics":                      frozenset({"reasoning"}),

    # Cluster: [conservation + physical + time] — 3 domains
    "acoustics":                           frozenset({"reasoning"}),
    "nuclear_physics":                     frozenset({"metabolism"}),

    # Cluster: [conservation + physical] — 3 domains
    "electrical":                          frozenset({"reasoning", "time_sequence"}),
    "optics":                              frozenset({"reasoning", "time_sequence"}),

    # Cluster: [authority + encoding + reasoning + time] — 3 domains
    "witness":                             frozenset({"physical_substance"}),

    # Cluster: [encoding + reasoning] — 2 domains
    "information_theory":                  frozenset({"conservation_balance"}),

    # Cluster: [authority + conservation + reasoning + time] — economics/finance
    "finance":                             frozenset({"encoding"}),

    # Cluster: [encoding + physical] — genetics/photography
    "genetics":                            frozenset({"metabolism", "conservation_balance"}),

    # Cluster: [metabolism + physical + time] — agriculture/geology
    "agriculture":                         frozenset({"conservation_balance"}),
    "geology":                             frozenset({"conservation_balance"}),

    # Cluster: [physical + reasoning] — geometry/physics_dimensional
    "physics_dimensional":                 frozenset({"conservation_balance"}),

    # Cluster: [encoding + physical + reasoning] — music_theory/quantum_computing
    "music_theory":                        frozenset({"time_sequence", "authority_trust"}),
    "quantum_computing":                   frozenset({"time_sequence", "conservation_balance"}),

    # Cluster: [reasoning + time_sequence] — phase/sports_analytics
    "sports_analytics":                    frozenset({"conservation_balance"}),

    # Umbrella lifts — each umbrella must subsume its children's dimensions.
    # Audit fired when we retagged children (genetics+conservation,
    # exercise_science+reasoning, governance_decision_packet+encoding,
    # statistics_pvalue+time+conservation, etc.) without lifting parents.
    "biology":                             frozenset({"authority_trust", "reasoning"}),
    "governance":                          frozenset({"encoding"}),
    "statistics":                          frozenset({"authority_trust", "time_sequence", "conservation_balance"}),
}

# Apply the retag additively, in place. AXIS_DIMENSIONS now reflects v2.
AXIS_DIMENSIONS = {
    name: frozenset(dims | _RETAG_V2.get(name, frozenset()))
    for name, dims in AXIS_DIMENSIONS.items()
}


# ── Axis extensions (loaded from disk) ─────────────────────────────────
# Axes added by the human via /residue.html → POST /grid/axis/add land
# in this JSONL. Each line is an extension event with name, label,
# criterion (one sentence of what counts as carrying this axis), and
# the list of canonical domains that carry it.
#
# Reversibility: edit or delete entries in the file and restart the
# engine — there's no destructive write to the source-defined arrays.
# DIMENSIONS and AXIS_DIMENSIONS get re-extended from a clean base
# each load.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AXIS_EXT_FILE = _REPO_ROOT / "data" / "grid" / "axis_extensions.jsonl"


def _load_axis_extensions() -> List[Dict[str, object]]:
    """Read axis_extensions.jsonl. Returns a list of extension dicts
    in file order. Newer entries can supersede older ones via the
    `supersedes` field; the load logic respects insertion order."""
    if not _AXIS_EXT_FILE.exists():
        return []
    out: List[Dict[str, object]] = []
    try:
        for line in _AXIS_EXT_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return out
    return out


def _apply_axis_extensions(exts: List[Dict[str, object]]) -> None:
    """Mutate DIMENSIONS and AXIS_DIMENSIONS in place based on the
    extensions list. Called at module-load and after every successful
    add_axis() call."""
    for ext in exts:
        name = str(ext.get("name", "")).strip()
        if not name or name in DIMENSIONS:
            # If already present, just update carriers (idempotent)
            pass
        else:
            DIMENSIONS.append(name)

        carriers = ext.get("carriers", []) or []
        if not isinstance(carriers, list):
            continue
        for carrier in carriers:
            if not isinstance(carrier, str):
                continue
            if carrier not in AXIS_DIMENSIONS:
                continue
            current = set(AXIS_DIMENSIONS[carrier])
            current.add(name)
            AXIS_DIMENSIONS[carrier] = frozenset(current)


# Load extensions immediately so module consumers see the runtime grid.
_apply_axis_extensions(_load_axis_extensions())


def remove_axis(name: str) -> Dict[str, object]:
    """Comment out an extension in the journal and rebuild the in-memory
    state from the remaining non-commented entries.

    Reversibility: the commented line stays in the journal as a record
    that this axis was tried and rolled back. To restore, uncomment.

    Returns a summary dict with what was removed and the resulting
    DIMENSIONS count."""
    import re
    name = (name or "").strip().lower()
    if not re.match(r"^[a-z][a-z0-9_]{2,31}$", name):
        raise ValueError(f"invalid axis name: {name!r}")
    if not _AXIS_EXT_FILE.exists():
        raise ValueError(f"no extensions journal at {_AXIS_EXT_FILE}")

    # Read existing lines
    lines = _AXIS_EXT_FILE.read_text("utf-8", errors="replace").splitlines()
    new_lines: List[str] = []
    removed_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            new_lines.append(line)
            continue
        try:
            rec = json.loads(stripped)
        except Exception:
            new_lines.append(line)
            continue
        if rec.get("name") == name:
            # Comment it out — preserves the historical record
            new_lines.append("# REMOVED " + stripped)
            removed_count += 1
        else:
            new_lines.append(line)

    if removed_count == 0:
        raise ValueError(f"no extension entry found with name {name!r}")

    # Atomic write
    tmp = _AXIS_EXT_FILE.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(_AXIS_EXT_FILE)

    # Rebuild in-memory state: drop the dimension and rebuild carriers
    # from the rebased extensions. The base AXIS_DIMENSIONS (from grid.py
    # source) is the floor; extensions add on top.
    if name in DIMENSIONS:
        DIMENSIONS.remove(name)
    for axis_name, dims in list(AXIS_DIMENSIONS.items()):
        if name in dims:
            new_dims = frozenset(d for d in dims if d != name)
            AXIS_DIMENSIONS[axis_name] = new_dims

    return {
        "removed_axis": name,
        "removed_entries": removed_count,
        "dimensions_now": list(DIMENSIONS),
        "dimension_count_now": len(DIMENSIONS),
    }


def add_axis(name: str, label: str, criterion: str, carriers: List[str]) -> Dict[str, object]:
    """Persist a new axis to the extensions journal and apply it
    in-place. Used by POST /grid/axis/add. Returns the loaded
    extension record.

    Validation:
      - name must match [a-z][a-z0-9_]{2,31}
      - name must not be a known alias
      - name must not already be in DIMENSIONS
      - every carrier must be a known canonical name in AXIS_DIMENSIONS
      - criterion required (1 sentence of what counts)

    On success: appends a line to axis_extensions.jsonl, mutates
    DIMENSIONS and AXIS_DIMENSIONS in place, returns the record."""
    import re
    import time

    name = (name or "").strip().lower()
    label = (label or "").strip() or name.split("_")[0]
    criterion = (criterion or "").strip()

    if not re.match(r"^[a-z][a-z0-9_]{2,31}$", name):
        raise ValueError("axis name must be 3-32 chars, start with a letter, "
                         "use only lowercase letters/digits/underscore")
    if name in ALIASES:
        raise ValueError(f"{name!r} is a known alias; cannot use as axis name")
    if name in DIMENSIONS:
        raise ValueError(f"axis {name!r} already exists in DIMENSIONS")
    if not criterion:
        raise ValueError("criterion is required (one sentence of what counts as carrying this axis)")
    if not carriers:
        raise ValueError("at least one carrying domain is required")

    canonical_names = set(AXIS_DIMENSIONS.keys()) - set(ALIASES.keys())
    bad = [c for c in carriers if c not in canonical_names]
    if bad:
        raise ValueError(f"unknown canonical carriers: {bad}")

    record = {
        "name": name,
        "label": label,
        "criterion": criterion[:400],
        "carriers": sorted(set(carriers)),
        "added_at": int(time.time()),
    }

    _AXIS_EXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_AXIS_EXT_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    _apply_axis_extensions([record])
    return record


def canonical(name: str) -> str:
    """Resolve an axis name to its canonical form. Returns the input
    unchanged if no alias exists."""
    return ALIASES.get(name, name)


def is_alias(name: str) -> bool:
    """True if `name` is a known alias of another canonical axis."""
    return name in ALIASES


def canonical_axes() -> Dict[str, FrozenSet[str]]:
    """AXIS_DIMENSIONS with all aliases collapsed to their canonical
    entries. Useful for structural audits where aliases would create
    false redundancy clusters."""
    return {
        name: dims for name, dims in AXIS_DIMENSIONS.items()
        if not is_alias(name)
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


# ── Prose → dimensions (owned, deterministic) ───────────────────────────
# A keyword layer that places a plain-language claim on the scaffold: which
# dimensions it sits on. Owned (no LLM), broadened so far more real claims
# place. The own-model parser will deepen this over time; this is the floor.
# Multi-axis overlap is expected and fine. Lives here (not in the MCP server)
# so every surface — the locate tool AND the map page — shares one parser.
_AXIS_STEMS: Dict[str, Tuple[str, ...]] = {
    "encoding":              ("encod", "encrypt", "decod", "symbol", "cipher", "code", "languag",
                              "word", "letter", "alphabet", "translat", "data", "informat", "messag", "text"),
    "metabolism":            ("metabol", "growth", "decay", "nutri", "energ", "food", "digest",
                              "cell", "flow", "transform", "burn", "calorie", "grow", "ferment", "photosynth"),
    "reasoning":             ("reason", "logic", "proof", "comput", "calculat", "infer", "math",
                              "equal", "sum", "number", "theorem", "equation", "deriv", "prime",
                              "arithmetic", "prov", "deduc", "solve", "algebra"),
    "physical_substance":    ("physic", "matter", "substanc", "spatial", "geometr", "light", "speed",
                              "mass", "force", "veloci", "atom", "particle", "wave", "gravit", "heat",
                              "temperatur", "distanc", "length", "meter", "molecul", "element", "pressure", "volume"),
    "authority_trust":       ("author", "trust", "consent", "consensus", "legitim", "sign", "law",
                              "govern", "vote", "witness", "testimon", "source", "cite", "scriptur", "verse"),
    "time_sequence":         ("time", "sequenc", "before", "after", "deadline", "period", "date",
                              "year", "day", "when", "schedul", "calendar", "histor", "event", "clock", "duration"),
    "conservation_balance":  ("balanc", "conserv", "equilibri", "invariant", "preserv", "momentum",
                              "charge", "budget", "account", "ledger", "total", "sum to", "first law"),
    # Dimensions added after the original seven — synonym stems so they place.
    "uncertainty":           ("uncertain", "probab", "random", "stochast", "risk", "confidence",
                              "estimat", "chance", "odds", "likely", "p-value", "noise", "variance"),
    "discreteness":          ("discret", "integer", "countab", "quantiz", "digital", "granular",
                              "count", "whole number", "digit", "unit", "step"),
    "order":                 ("order", "rank", "sort", "hierarch", "ordinal", "precede", "greater than", "less than"),
    "symmetry":              ("symmetr", "reflect", "rotation", "mirror", "group-theor"),
}


def predict_dimensions(text: str) -> FrozenSet[str]:
    """Place a plain-language claim on the scaffold: which dimensions it sits on.

    Three owned signals, unioned: (1) per-dimension keyword stems, (2) a literal
    dimension name in the text, (3) a domain name in the text -> that domain's
    dimensions. Returns the (possibly empty) set of dimensions. Deterministic,
    no LLM. Only the runtime DIMENSIONS / AXIS_DIMENSIONS are consulted, so any
    axis added at runtime participates automatically (its stems, if any, would
    need adding here, but its NAME and its domains' dims still place it)."""
    q = (text or "").lower()
    predicted: set = set()
    if q:
        for ax, stems in _AXIS_STEMS.items():
            if any(s in q for s in stems):
                predicted.add(ax)
        for dim in DIMENSIONS:
            if dim in q or dim.replace("_", " ") in q:
                predicted.add(dim)
        for dom, dims in AXIS_DIMENSIONS.items():
            stem = dom[:6] if len(dom) >= 6 else dom
            if dom in q or (len(stem) >= 5 and stem in q):
                predicted.update(dims)
    # Only keep dimensions that actually exist in the live scaffold.
    return frozenset(d for d in predicted if d in DIMENSIONS)


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


def verify_umbrella_coherence() -> Dict[str, List[str]]:
    """Verify each umbrella's dimensions cover the union of its
    subsystems' dimensions.

    The doctrinal claim: an umbrella subsumes its subsystems. If
    `agriculture` sits on `time_sequence` but the `biology` umbrella
    doesn't, the umbrella isn't actually carrying what its children
    carry. This is a coherence break — either the umbrella needs the
    extra dimension or the subsystem doesn't really belong under it.

    Returns a dict mapping umbrella name → list of missing dimensions.
    Empty list means coherent. Empty dict means all umbrellas coherent.
    """
    breaks: Dict[str, List[str]] = {}
    for parent, children in UMBRELLAS.items():
        if not children:
            continue
        if parent not in AXIS_DIMENSIONS:
            continue
        parent_dims = AXIS_DIMENSIONS[parent]
        children_union = frozenset()
        for c in children:
            if c in AXIS_DIMENSIONS:
                children_union = children_union | AXIS_DIMENSIONS[c]
        missing = sorted(children_union - parent_dims)
        if missing:
            breaks[parent] = missing
    return breaks


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
        "uncertainty": "unc",
        "discreteness": "dsc",
        "order": "ord",
        "symmetry": "sym",
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
