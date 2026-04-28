# Concordance Verifier Schemas

For each verifier: required fields, optional fields, status values, and one minimal call. All examples were exercised on 2026-04-27 and the actual outputs are captured in `training_set.json`.

---

## verify_mathematics

Sympy-based math verification across five modes.

**Shape:** `{mode, params}` — note this is the only verifier with a nested `mode/params` shape.

| mode | required params |
|---|---|
| equality | `expr_a`, `expr_b`, `variables: [...]` |
| derivative | `function`, `variable`, `claimed_derivative` |
| integral | `integrand`, `variable`, `claimed_antiderivative` |
| limit | `function`, `variable`, `point`, `claimed_limit` |
| solve | `equation`, `variable`, `claimed_solutions: [...]` |

Returns: `CONFIRMED` or `MISMATCH`.

```json
{"mode": "derivative", "params": {"function": "sin(x**2)", "variable": "x", "claimed_derivative": "2*x*cos(x**2)"}}
```

---

## verify_physics_dimensional

Reduces both sides of an equation to base SI and compares.

**Required:** `equation` (string), `symbols` (dict of variable -> unit name).

Returns: `CONFIRMED` or `MISMATCH`. On confirm, returns the reduced units in `data.lhs_units` / `data.rhs_units`.

```json
{"equation": "F = m*a", "symbols": {"F": "newton", "m": "kilogram", "a": "meter/second**2"}}
```

---

## verify_physics_conservation

Checks each named conserved quantity is preserved.

**Required:** `before` (dict), `after` (dict). Keys are quantity names; values are numeric.
**Optional:** `tolerance_relative` (default 1e-6), `tolerance_absolute` (default 0).

A quantity passes if rel_diff ≤ rel_tol OR abs_diff ≤ abs_tol.

```json
{"before": {"momentum_x": 5, "energy": 100}, "after": {"momentum_x": 5, "energy": 100}}
```

---

## verify_chemistry

Verifies a chemical equation balances atoms and charge.

**Required:** `equation` (e.g., `"2 H2 + O2 -> 2 H2O"`).
**Optional:** `temperature_K` (must be positive).

On MISMATCH, returns the correctly balanced coefficients in `data.balanced_lhs` / `balanced_rhs`. **Useful debugging behavior** — copy the balanced form and re-run.

```json
{"equation": "2 H2 + O2 -> 2 H2O"}
```

---

## verify_biology

Multiple optional checks; whichever inputs you pass, the matching check runs.

**Optional:**
- `n_replicates` + `min_replicates` (default 3)
- `assay_classes` (list) + `min_assay_classes` (default 2)
- `dose_response`: `{doses, responses, expected_direction: "increasing"|"decreasing"}`
- `power_analysis`: `{effect_size, alpha, n_per_group, target_power}`

Returns a list of per-check CONFIRMED/MISMATCH results.

```json
{"n_replicates": 5, "assay_classes": ["binding_assay", "cell_viability"], "dose_response": {"doses": [0,1,5,10,50], "responses": [0.1,0.3,0.55,0.7,0.9], "expected_direction": "increasing"}}
```

---

## verify_computer_science

Static termination scan + optional functional/complexity checks.

**Required:** `code` (Python source).
**Optional:** `function_name`, `test_cases`, `input_generator`, `claimed_class` (e.g., `"O(n)"`), `sizes`, `tolerance`.

> **⚠ Known issue:** `test_cases` does not unpack list-valued `input` as positional args. See `known_issues.md` issue #2. As a workaround, write your function to accept a single argument, e.g., `def add(args): a, b = args; return a + b`.

```json
{"code": "def square(x):\n    return x*x", "function_name": "square", "test_cases": [{"input": 3, "expected": 9}]}
```

---

## verify_statistics_pvalue

Recomputes a p-value from inputs and compares against `claimed_p`.

**Required:** `spec` containing `test` and the test's inputs.

| test | inputs |
|---|---|
| two_sample_t | n1, n2, mean1, mean2, sd1, sd2, [tail] |
| one_sample_t | n, mean, sd, [mu0, tail] |
| z | z, [tail] |
| chi2 | statistic, df |
| f | statistic, df1, df2 |

**Optional:** `claimed_p`, `tolerance` (default 1e-3).

> **⚠ Known issue:** `tail: "two"` returns `cdf(t)` instead of `2·sf(|t|)`. Correct claims may be flagged MISMATCH. See `known_issues.md` issue #1. Workaround: compute the two-tailed p yourself and verify against `tail` not being passed.

```json
{"spec": {"test": "two_sample_t", "n1": 30, "n2": 30, "mean1": 5.2, "mean2": 4.8, "sd1": 1.1, "sd2": 1.0, "claimed_p": 0.15}}
```

---

## verify_statistics_confidence_interval

Checks that low ≤ estimate ≤ high.

**Required:** `estimate`, `ci_low`, `ci_high`.

```json
{"estimate": 10.5, "ci_low": 9.2, "ci_high": 11.8}
```

---

## verify_statistics_multiple_comparisons

Applies Bonferroni or BH correction and verifies the rejection set at alpha.

**Required:** `raw_p_values` (list), `method` (`"bonferroni"` or `"bh"`).
**Optional:** `alpha` (default 0.05), `claimed_rejected_indices`.

Returns adjusted p-values and the indices the engine *would* reject.

```json
{"raw_p_values": [0.001, 0.01, 0.03, 0.04, 0.5], "method": "bonferroni", "alpha": 0.05, "claimed_rejected_indices": [0, 1]}
```

---

## verify_governance_decision_packet

Single-domain governance check (shape + witness consistency only — no RED/FLOOR/BROTHERS/GOD gates).

**Required (in `decision_packet`):** `title`, `scope`, `red_items`, `floor_items`, `way_path`, `execution_steps`, `witnesses`.
**Optional:** `scripture_anchors`, `wait_window_seconds`. Top-level `witness_count` cross-checks the witnesses array.

> **⚠ Known issue:** This verifier and `validate_packet` accept *different* schemas for the same logical packet. See `known_issues.md` issue #3. For the full-engine flow, use the schema documented under `validate_packet` below.

---

## validate_packet (full engine — RED, FLOOR, BROTHERS, GOD)

**Required:** `packet` with at minimum a `domain` field. Beyond that the engine routes to the matching domain validator.

**For governance packets, observed contract** (different from `verify_governance_decision_packet`):
- Needs a `text` field (or other free-text fields) for RED/FLOOR scanning. Structured `red_items`/`floor_items` arrays are not enough on their own.
- Needs `created_epoch` (Unix seconds) for the GOD gate, otherwise QUARANTINE.
- BROTHERS counts witnesses from a field shape that does *not* match what `verify_governance_decision_packet` expects.

Returns: `{overall: PASS|REJECT|QUARANTINE, gate_results: [...]}`.

**Scope-based GOD defaults (observed, not yet documented in engine):**
- `adapter`: ~3600s (1 hour) minimum wait
- `mesh`: longer (likely 86400s / 1 day, not yet measured)
- `canon`: longer still (likely 604800s / 1 week, not yet measured)

The packet's own `wait_window_seconds` does not appear to lower these defaults. See `known_issues.md` issue #4.

**Optional `now_epoch` parameter** on the `validate_packet` call: if omitted, defaults to wall-clock time. Pass it explicitly for reproducible test runs.

See `decision_packet_template.json` for the recommended packet shape that satisfies both verifiers.
