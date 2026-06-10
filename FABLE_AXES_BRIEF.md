# Fable 5 — START HERE: resolve the math/science theory axes (build-once)

**Window:** Matt has Fable 5 until **2026-06-22**. Spend it on build-once, high-reasoning,
moat-deepening work — work that, done *correctly once*, runs forever with **zero model calls**
(the oracle-shrinking thesis). This brief is **Task A: the math/science theory axes alignment** —
the foundation everything else rides on, and the one Matt pointed at first.

This is a **design + proposal** deliverable, not a deploy. The discipline below is non-negotiable.

---

## What the grid is (read the code first)

`src/concordance_engine/grid.py` — the scaffold registry. Read it in full. Summary:

- **7 hand-set DIMENSIONS** (scaffold members): `encoding · metabolism · reasoning ·
  physical_substance · authority_trust · time_sequence · conservation_balance`.
- **~36 canonical axes** (domains), each mapped to a `frozenset` of the 7 dimensions it sits on
  (`AXIS_DIMENSIONS`). `_RETAG_V2` already broke ambiguity clusters by adding discriminating
  dimensions. `UMBRELLAS` encode parent→child; `ALIASES` collapse synonyms.
- **Runtime-extensible**: `add_axis(name, label, criterion, carriers)` persists to
  `data/grid/axis_extensions.jsonl` and applies on load. **Operator-only** via `POST /grid/axis/add`
  — Fable PROPOSES, **Matt admits**. Never call add_axis yourself.

Run these to see the live state before designing anything:
```
python -m concordance_engine.grid depth     # axes ranked by dimension count
python -m concordance_engine.grid dimension reasoning
python tools/axis_coverage.py                # the under-resolution audit (read-only)
```

## The gap (verified, grounded — not a hunch)

`tools/axis_coverage.py` shows: the verifiers measure **34 distinct invariants**, but the grid has
only **7 axes** (~4.9× coarser). The starkest collapse is exactly the math/science theory space:

- **`mathematics`** checks 9 invariants — `equality, inequality, derivative, integral, limit,
  series, ode, matrix, solve` — all flattened into `{reasoning, conservation_balance}`.
- `statistics` / `statistics_pvalue` / `_confidence_interval` / `_multiple_comparisons`, `number_theory`,
  `combinatorics`, `formal_logic`, `geometry`, `physics_dimensional`, `quantum_computing` likewise
  sit on a near-identical coarse signature.

Because these axes share signatures, the engine **cannot compute the intersections** between, say,
analysis and linear algebra, or where calculus meets physics meets QM. The "stack of transparencies"
won't overlay at fine grain. **That is the thing to fix, and it only needs doing once.**

## Your task (Task A)

Propose the genuinely **orthogonal finer dimensions** the math/science theory space requires, and
re-place the math/science axes onto the expanded set so their distinct structure — and their
intersections — become computable.

Candidate finer dimensions (these are *starting candidates from the invariants the engine already
measures* — evaluate, don't assume; some may be sub-axes rather than new orthogonal DIMENSIONS):
- **equivalence/structure** (from `equality`; algebraic structure, isomorphism)
- **order** (from `inequality`; ordering, bounds, monotonicity)
- **continuity/limit** (the analysis cluster: `limit, derivative, integral, series`)
- **linear/operator structure** (`matrix, solve, ode`)
- **probability/inference** (statistics: `pvalue, confidence_interval, multiple_comparisons`)
- **dimensional consistency** and **symmetry/invariance** (physics: `dimensional`, conservation)

For each dimension you propose, deliver:
1. **name** (`[a-z][a-z0-9_]{2,31}`) + one-line **criterion**: what counts as a claim *carrying*
   this dimension (must be falsifiable — a test, not a vibe).
2. **grounding**: which verifier invariant(s) it derives from (it must already be measured; invent
   nothing).
3. **carriers**: which existing canonical domains sit on it.
4. **orthogonality argument**: why it's genuinely independent of the existing 7 + the others you
   propose (if it's not orthogonal, it's a sub-axis, not a dimension — say so).
5. **co-confirmation candidates**: name ≥1 domain-PAIR that could confirm one structured claim on
   this dimension (this is how the axis gets *verified*, below).

Then: **re-place the math/science axes** (`mathematics, statistics(+subs), physics(+subs),
number_theory, combinatorics, geometry, formal_logic, quantum_computing`) onto `{7 existing} ∪ {your
proposals}` and show the resulting intersection map — which axis-pairs now share which dimensions,
and what previously-invisible intersections become visible.

## The discipline (Deut 19:15 applied to the coordinate system — DO NOT violate)

A wrong axis is worse than none (a false trail). The established faithful method
(`memory/project_axis_discovery_2026-06-09`):

1. **PROPOSE** candidate dimensions from verifier structure (grounded; invents nothing). ← your job
2. **VERIFY** a candidate by **≥2 independent domains co-confirming one structured claim on it**
   (witnesses). The engine never self-confirms; the oracle may only *label* a cluster, never assert
   an axis exists.
3. **ADMIT**: Matt NAMES it and runs `add_axis` (operator-only).

**Coupling you must respect:** step 2 needs *structured, runnable claims* — and the real bottleneck
(`memory/project_academia_connection_atlas_2026-06-09`) is the **prose→structured-spec bridge**, not
verification capacity (the 82 verifiers run free + instantly on a structured spec). So your Task-A
deliverable is a **grounded proposal package** (dimensions + criteria + carriers + the domain-pairs
that would co-confirm each). Full *admission* waits on co-confirmation evidence, which needs the
bridge — that's **Task B** (the structuring bridge + multi-step verification chain), the keystone
Fable should build next. Do not present a proposed dimension as a verified one.

## Deliverable + where it goes

- A written proposal package (above) — the candidate dimensions, the re-placement, the intersection
  map. Capture it so it persists (the wisdom flywheel): the technical output's home is the **ATLAS**
  (`memory/project_unified_picture_2026-06-10` — the technical book of all math/verified findings).
- Hand the named-axis decisions to Matt (`add_axis` is his click).

## Context to load (memory, read these)

`project_axis_discovery_2026-06-09` · `project_academia_connection_atlas_2026-06-09` ·
`project_mapping_reality_2026-06-10` (truth absolute/inferable/fractal; the inference engine) ·
`project_moat_track_2026-06-10` (the Fable-window allocation + "solve real calculus/physics") ·
`project_unified_picture_2026-06-10` (the Atlas). Engine identity: GET https://narrowhighway.com/identity.

**Then Task B (next):** the prose→structured-spec bridge + multi-step verification chain — the
keystone that makes "we solved this whole calculus/physics problem, every step proven" real.
