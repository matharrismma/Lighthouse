# Atlas — Math/Science Theory Axis Resolution (PROPOSAL)

**Task A deliverable** (Fable 5, 2026-06-10). A *grounded proposal*, not a verified result. The
discipline (Deut 19:15 applied to the coordinate system): **I propose; ≥2 independent domains
co-confirm one structured claim on a dimension; Matt names it via the operator-only `add_axis`.**
Nothing below is invented — every proposed dimension is anchored to invariants the verifiers already
compute.

---

## 1. The gap, re-measured (verified: ~44×, not 4.9×)

`tools/axis_coverage.py` originally reported 34 invariants vs 7 axes (~4.9×). **That was an
undercount of ~9×.** Its regex only caught the inline form `confirm('mathematics.equality')`, but the
*dominant* idiom is variable-assigned (`name = "vector.dot_product"; confirm(name, …)`) — 276 of the
tags. After widening the regex (§5, fix shipped this session), the honest count is **307 distinct
invariants across 64 verifier files vs 7 axes — ~44× coarser.** The fix also surfaced **verifier
domains the grid does not map at all** (`linear_algebra`, `probability` → `axes: 0`) — a real
placement gap, separate from resolution. The math/science cluster, pulled directly from source:

| domain | invariants it actually checks |
|--------|-------------------------------|
| mathematics | derivative, integral, limit, series, ode, matrix, solve, equality, inequality (9) |
| formal_logic | satisfiability, tautology, contradiction, entailment, equivalence (5) |
| number_theory | primality, gcd, modular_inverse, factorial, perfect_number, sequence (6) |
| combinatorics | combinations, permutations, derangements, multinomial (4) |
| geometry | pythagorean, triangle_inequality, circle/sphere/cube/cylinder/rectangle, polygon_angle_sum (8) |
| statistics | pvalue_calibration, confidence_interval, multiple_comparisons, effect_size, significance_consistency (5) |
| information_theory | shannon_entropy, bsc_capacity, hamming_distance (3) |
| quantum_computing | qubit_normalization, quantum_fidelity, von_neumann_entropy, grover_iterations, shor_period (5) |
| physics | dimensional, conservation, named_conservation (3) |

≈ **48 invariants in the formal/physical cluster alone**, nearly all collapsed into `{reasoning}` (+
`conservation_balance` via retag). The grid cannot tell calculus from combinatorics from cryptography.
**Companion fix (recommended, build-once):** widen the `axis_coverage` regex to also match the
`name = "..."` form so the audit tells the truth.

## 2. Proposed dimensions

Each: **criterion** (falsifiable — what makes a claim *carry* it) · **grounding** (invariants it
derives from) · **carriers** (existing domains) · **orthogonality** · **co-confirm test** (the
domain-pair + claim that would establish it).

### Primary — the continuous / discrete / stochastic decomposition of the formal sciences

**D1 · `continuity`** — claim concerns limits, rates of change, convergence, or differential/integral structure.
- grounding: `mathematics.{limit, derivative, integral, series, ode}`
- carriers: mathematics, physics (calculus of motion), economics (`compound_interest`, `price_elasticity` = dy/dx, `present_value`), quantum_computing (continuous evolution), hydrology/meteorology/exercise_science (rates/flows)
- orthogonal to: counting (D2), probability (D3), equivalence (D4). The infinitesimal is a distinct structure `reasoning` was hiding.
- co-confirm: **mathematics + physics** on "d/dt of position is velocity" (`mathematics.derivative` ∧ `physics.dimensional`).

**D2 · `discreteness`** — claim concerns counting, integers, divisibility, or discrete arrangements.
- grounding: `combinatorics.{combinations, permutations, derangements, multinomial}`, `number_theory.{primality, gcd, factorial, perfect_number, sequence}`
- carriers: combinatorics, number_theory, computer_science (discrete algorithms), cryptography (modular arithmetic), information_theory (discrete codes), biology (`mendelian`, `hardy_weinberg` = discrete alleles)
- orthogonal to D1: the classic continuous/discrete divide. A domain may carry both (numerical analysis); anti-correlation with D1 across most domains is the feature that makes it a discriminator.
- co-confirm: **number_theory + cryptography** on a modular-arithmetic claim (`number_theory.modular_inverse` ∧ `cryptography.hash_match`); or **combinatorics + biology** on a Hardy-Weinberg ratio.

**D3 · `uncertainty`** — claim concerns probability distributions, statistical inference, entropy, or information content.
- grounding: `statistics.{pvalue_calibration, confidence_interval, multiple_comparisons, effect_size}`, `information_theory.{shannon_entropy, bsc_capacity}`, `quantum_computing.{von_neumann_entropy, quantum_fidelity}`, `biology.{dose_response, power, replicates}`
- carriers: statistics, information_theory, quantum_computing, biology, finance (risk), sports_analytics
- orthogonality: cleanly independent of D1/D2 — you can be deterministic-continuous, stochastic-continuous, deterministic-discrete, or stochastic-discrete (a full 2×2, which is the proof of independence). This is the single highest-leverage dimension: it cuts across the most domains and is the clearest thing `reasoning` was mislabeling.
- co-confirm: **statistics + information_theory** on the entropy of a distribution; **statistics + biology** on statistical power.

### Relational — the two fundamental relation types

**D4 · `equivalence`** — claim asserts two expressions/structures are equal or equivalent under a stated relation.
- grounding: `mathematics.equality`, `formal_logic.{equivalence, tautology}`, `number_theory.modular_inverse`, `cryptography.{hash_match, hmac_match, encoding_roundtrip}`
- carriers: mathematics, formal_logic, number_theory, cryptography
- orthogonality: equivalence relations (reflexive/symmetric/transitive) are a distinct algebraic structure from order relations (D5) — a genuine, deep mathematical split.
- co-confirm: **mathematics + formal_logic** on an identity that is both algebraic equality and a tautology; **number_theory + cryptography** on `a·a⁻¹ ≡ 1 (mod n)` ∧ a roundtrip equality.

**D5 · `order`** — claim asserts an ordering, bound, monotonicity, or optimum.
- grounding: `mathematics.inequality`, `geometry.triangle_inequality`, `statistics.confidence_interval` (bounds), `operations_research` (optimization), `economics.price_elasticity` (sign/monotonicity)
- carriers: mathematics, geometry, operations_research, economics, finance, statistics
- orthogonality: order relations vs equivalence relations (D4) — the two fundamental binary-relation families.
- co-confirm: **mathematics + operations_research** on an optimization bound; **mathematics + geometry** on the triangle inequality.

### Candidate — weaker / needs co-confirmation before proposing for naming

**D6 · `dimensional_consistency`** — claim asserts dimensional/unit homogeneity of a relation.
- grounding: `physics.dimensional`; unit-bearing checks in `chemistry.{molarity, thermodynamic_feasibility}`, `biology.molarity`
- co-confirm needed: **physics + chemistry** on a units-balance claim. If only physics ever carries it, it stays a physics sub-axis, not a dimension.

**D7 · `linearity`** — claim concerns linear systems, operators, or superposition.
- grounding: `mathematics.{matrix, solve}`, `quantum_computing.qubit_normalization` (unit vector in Hilbert space)
- co-confirm needed: **mathematics + quantum_computing** on a superposition/normalization claim; **mathematics + electrical** on circuit superposition.

## 3. Re-placement (math/science axes on the proposed dimensions)

| axis | continuity | discrete | uncertainty | equivalence | order | dimensional | linearity |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| mathematics | ✓ | ✓ | | ✓ | ✓ | | ✓ |
| formal_logic | | | | ✓ | | | |
| number_theory | | ✓ | | ✓ | ✓ | | |
| combinatorics | | ✓ | | | | | |
| geometry | | | | | ✓ | ✓ | |
| statistics | | | ✓ | | ✓ | | |
| information_theory | | ✓ | ✓ | | | | |
| quantum_computing | ✓ | | ✓ | | | | ✓ |
| physics | ✓ | | | | | ✓ | ✓ |
| economics | ✓ | | ✓ | | ✓ | | |
| cryptography | | ✓ | | ✓ | | | |

(These keep their existing 7-dimension placements; the table shows only the *new* resolution.)

## 4. The payoff — intersections that become computable

The "stack of transparencies" now overlays at fine grain. Each cell below is a *candidate verified
connection* — a domain-pair sharing a fine dimension, testable by co-confirmation:

- **cryptography = discreteness ∩ equivalence** — modular arithmetic + digest equality. Previously
  indistinguishable from any other `{encoding, reasoning, authority}` domain.
- **quantum_computing = linearity ∩ uncertainty ∩ continuity** — Hilbert-space superposition +
  entropy/fidelity + continuous evolution. Previously structurally identical to music_theory.
- **information_theory = discreteness ∩ uncertainty** AND **population genetics (biology) =
  discreteness ∩ uncertainty** — *the same cell.* Shannon entropy and Hardy-Weinberg diversity are
  the same math (entropy of a discrete distribution). **This is a falsifiable cross-domain connection
  the grid now predicts** — exactly the kind of "do what others cannot" finding the moat is for.
- **mathematical physics = continuity ∩ dimensional ∩ conservation** — calculus + units + conservation laws.
- **economics = continuity ∩ order ∩ uncertainty** — marginal analysis + optimization + risk.

## 5. Next steps (the discipline + the dependency)

1. **Co-confirmation** establishes each dimension: run the listed domain-pair tests. This needs
   *structured claims* the verifier stack can run on both domains — which is the **prose→structured-
   spec bridge (Task B)**, the real bottleneck (`project_academia_connection_atlas_2026-06-09`). So D1–D5
   are ready to verify *the moment the bridge exists*; the test specs are written above.
2. **Matt names** each confirmed dimension via `POST /grid/axis/add` (operator-only). I do not call it.
3. **Companion fix — DONE this session**: widened `tools/axis_coverage.py`'s regex to the
   `name = "..."` form; the audit now reports the honest 307 (was 34) and exposes the unmapped
   `linear_algebra`/`probability` domains.
4. The strongest three to verify first — **uncertainty, discreteness, continuity** — carry the most
   domains and partition the formal sciences cleanly.

**Verdict:** propose 5 (D1–D5, strongly grounded + orthogonal) + 2 candidates (D6–D7, pending
co-confirmation). The information-theory/population-genetics shared cell is the headline: a verifiable
connection the resolved grid *predicts*, not one a human hand-placed.
