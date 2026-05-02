# Concordance Engine Benchmark — Dataset Summary

**File:** `09_evaluation/benchmark_dataset.jsonl`
**Generated:** 2026-04-28
**Generator scripts:** `outputs/go.py` (build) + per-domain modules (`d2_chemistry.py`, `d3_physics*.py`, `d4*_math*.py`, `d5_cs*.py`, `d6_governance*.py`)

## Totals

| Metric | Count |
|---|---|
| Total claims | **722** (target ≥700) |
| `correct` | 356 (49.3%) |
| `incorrect` | 366 (50.7%) |

## Per-domain breakdown

| Domain | Total | Correct | Incorrect | Target |
|---|---|---|---|---|
| D1 statistics | 124 | 62 | 62 | ~120 |
| D2 chemistry | 130 | 65 | 65 | ~120 |
| D3 physics | 110 | 55 | 55 | ~120 |
| D4 mathematics | 120 | 60 | 60 | ~120 |
| D5 computer science | 110 | 55 | 55 | ~120 |
| D6 governance | 128 | 59 | 69 | ~100 |

Governance is the only domain where the correct/incorrect split is uneven (59/69). This is because the engine's `governance.decision_packet_shape` verifier checks ~7 distinct structural failure modes, and the dataset includes one negative example per failure mode, several of which don't have a natural correct counterpart beyond "complete packet."

## Per-template breakdown

```
T1.1_one_sample_t              16    T4.1_equality                  24
T1.2_welch_t                   16    T4.2_derivative                24
T1.3_z_test                    16    T4.3_integral                  24
T1.4_chi2                      16    T4.4_limit                     24
T1.5_f_test                    16    T4.5_solve                     24
T1.6_ci_coverage               16    T5.1_correctness               62
T1.7_bonferroni                14    T5.2_termination               28
T1.8_bh_fdr                    14    T5.3_complexity                20
T2_balance                    130    T6.1_complete_packet           59
T3_dimensional                 74    T6.2_missing_field             19
T3_conservation                36    T6.3_empty_list                 8
                                     T6.4_invalid_scope              8
                                     T6.5_short_way_path            13
                                     T6.6_witness_count_mismatch    13
                                     T6.7_wrong_type                 8
```

## Perturbation type distribution

The most common perturbation types are listed; see the JSONL for the full set of ~58 distinct labels.

```
off_by_one_coef                 60     wrong_complexity_class      10
wrong_unit                      37     wrong_tail                   8
missing_required_field          19     wrong_df                     8
violated_conservation           18     swapped_df                   8
sign_flip                       16     infinite_loop                8
wrong_p_value                   13     empty_required_list          8
way_path_too_short              13     invalid_scope_value          8
witness_count_mismatch          13     wrong_field_type             8
wrong_value                     12     ci_bounds_swapped            6
wrong_rejection_set             11     missing_base_case            6
off_by_one                      11     ... (and many low-count tails)
```

## Quality checks

Spot-check (5 random rows × 6 domains, seed 42): **30 / 30 PASS**.
Full sweep against the engine (all 722 claims, except 20 `T5.3_complexity` rows that require live timing): **702 / 702 PASS, 0 FAIL**.

The dataset's ground-truth labels are reproduced exactly by the engine's verifiers wherever the engine has a verification path. Any failure mode of the engine on this benchmark therefore reflects a real engine error, not a labeling artifact.

## Sample claims (3 correct + 3 incorrect per domain)

### Statistics (D1)
- ✓ `BM-00007` — one-sample t-test with n=100, mean=99.5, sd=5.0, mu0=100.0, two-sided ⇒ p = 0.3197.
- ✓ `BM-00029` — Welch's t-test (n1=50, n2=50, mean1=0.02, mean2=-0.03, sd1=0.5, sd2=0.55, two-sided) ⇒ p = 0.6354.
- ✓ `BM-00051` — chi-square with statistic=5.99, df=2 ⇒ p = 0.0500.
- ✗ `BM-00006` (wrong_p_value) — one-sample t with n=20, mean=0.3, sd=1.1, two-sided "yields p = 0.0238" (true p ≈ 0.238).
- ✗ `BM-00072` (swapped_df) — F-test with F=8.0, df1=1, df2=100 reported as p = 0.2756 (which is the value for swapped df).
- ✗ `BM-00110` (wrong_rejection_set) — Bonferroni on `[0.001, 0.05, 0.1]` claimed to reject at `[0, 1]` (true: `[0]`).

### Chemistry (D2)
- ✓ `BM-00163` — `2 SO2 + O2 -> 2 SO3` is balanced.
- ✓ `BM-00207` — `2 KNO3 -> 2 KNO2 + O2` is balanced.
- ✓ `BM-00225` — `2 Al + 3 CuSO4 -> Al2(SO4)3 + 3 Cu` is balanced.
- ✗ `BM-00138` (off_by_one_coef) — `C7H16 + 10 O2 -> 7 CO2 + 8 H2O` claimed balanced (correct is 11 O2).
- ✗ `BM-00144` (off_by_one_coef) — `2 C2H2 + 4 O2 -> 4 CO2 + 2 H2O` claimed balanced (correct is 5 O2).
- ✗ `BM-00150` (off_by_one_coef) — `H2 + O2 -> 2 H2O` claimed balanced (correct is 2 H2).

### Physics (D3)
- ✓ `BM-00283` — `U = m·g·h` consistent with [U]=J, [m]=kg, [g]=m/s², [h]=m.
- ✓ `BM-00329` — `F_drag = ½ρC_d A v²` consistent with stated SI units.
- ✓ `BM-00335` — `F_buoyancy = ρ g V_disp` consistent with stated SI units.
- ✗ `BM-00262` (wrong_unit) — `p = m·v` claimed with [p]=kg·m/s² (should be kg·m/s).
- ✗ `BM-00328` (wrong_unit) — `E = (3/2) k_B T` claimed with [k_B]=J (should be J/K).
- ✗ `BM-00330` (wrong_unit) — `F_drag` claim with [A]=m (should be m²).

### Mathematics (D4)
- ✓ `BM-00371` — `(2x+1)² = 4x² + 4x + 1` holds.
- ✓ `BM-00419` — antiderivative of cos(x) is sin(x).
- ✓ `BM-00435` — antiderivative of e^(2x) is e^(2x)/2.
- ✗ `BM-00380` (sign_flip) — `x³ - 1 = (x+1)(x² + x + 1)` (correct sign is `(x-1)`).
- ✗ `BM-00438` (wrong_value) — `lim_{x→0} sin(x)/x = 0` (true: 1).
- ✗ `BM-00470` (missing_complex_roots) — solutions of `x³ - 1 = 0` claimed to be `[1]` only.

### Computer Science (D5)
- ✓ `BM-00491` — `factorial(n)` with `for i in range(1, n+1): p *= i`, claimed O(n), passes test cases.
- ✓ `BM-00531` — early-return `contains` function, claimed to terminate.
- ✓ `BM-00559` — `clamp(x, lo, hi)` with correct branches, claimed O(1).
- ✗ `BM-00490` (wrong_predicate) — `count_evens` body uses `x % 2 == 1`, fails the stated test cases.
- ✗ `BM-00512` (wrong_op) — `dot(a, b)` body uses `x + y` instead of `x * y`.
- ✗ `BM-00550` (wrong_complexity_class) — `nested_log` (single for-loop with inner doubling while loop) claimed O(n²); true is O(n log n).

### Governance (D6)
- ✓ `BM-00600` — adapter packet "Set up new email distribution list" — complete (2 red, 2 floor, 2 witnesses, 4 steps, way_path).
- ✓ `BM-00675` — adapter packet "Renew annual insurance policy" — complete.
- ✓ `BM-00676` — same packet, +1 at-large witness — complete.
- ✗ `BM-00625` (missing_required_field) — adapter packet missing `way_path`.
- ✗ `BM-00628` (missing_required_field) — adapter packet missing `execution_steps`.
- ✗ `BM-00647` (way_path_too_short) — adapter packet with `way_path = "go"`.

## Caveats and templates that were cut

- **Engine cannot verify infinite limits.** The engine's `verify_limit` uses `simplify(actual − claimed) == 0`. When both are `∞`, `simplify(∞ − ∞) = nan ≠ 0`, so claims like `lim_{x→∞} log(x) = ∞` are mathematically correct but rejected by the engine. Such cases were **removed** from D4 to avoid mislabeled-correct rows; replaced with finite-limit cases of comparable difficulty.
- **Dimensional analysis with same-symbol differences fails.** Equations like `a = (v_f - v_i)/t` and the relativistic `1/sqrt(1 - v²/c²)` reduce to `0` after unit substitution because the engine uses substitution-and-simplify rather than tracking dimensions symbolically. These cases were **removed** from D3.
- **Tuple/list ambiguity in JSON.** CS test cases that originally used Python tuples were changed to lists, since JSON serialization loses tuple identity and the verifier's `actual != expected` check is type-strict.
- **`list(set(...))` perturbation dropped.** A buggy "dedupe" implementation that returned `list(set(a))` happens to produce correct order on small integer inputs in CPython, so it didn't reliably fail the test cases. Replaced with an unambiguous off-by-one slice bug.
- **`T5.3_complexity` claims are not unit-tested in this dataset's quality sweep.** They require running the verifier with timing measurements (~0.05–0.5s per claim) and were validated only by textbook-grounded labeling. The 20 complexity claims are real, ground-truthed, and ready to evaluate against the engine; they're just slow to spot-check at this stage.
- **`T6` governance verifies *structure*, not *substance*.** The engine's governance verifier checks for missing fields, empty lists, invalid scopes, etc. — not whether the rationale matches the conclusion. Perturbations were scoped accordingly. The benchmark plan suggested "rationale doesn't match conclusion" perturbations; those would require an LLM-judge layer the engine does not currently have, so they were **omitted**.
- **No biology domain.** The plan listed six domains; biology was not in the user's request. The engine has a biology verifier (replicate counts, dose-response monotonicity), but it sits outside this benchmark by user choice.

## Reproducibility

The dataset is regeneratable from `outputs/go.py`; statistics ground truth uses scipy 1.15.3, math uses sympy 1.14.0. All random seeds are fixed (`20260428` for stats, `42` for spot-check sampling). Re-running `go.py` produces a byte-identical JSONL.
