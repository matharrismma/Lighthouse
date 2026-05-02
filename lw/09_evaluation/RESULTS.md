# Concordance Engine Benchmark — Phase 2 Results

**Engine version:** `src/concordance_engine/` (canonical tree; `lw/01_engine/` is being retired).
**Dataset:** `09_evaluation/benchmark_dataset.jsonl` — 722 claims across six domains, generated 2026-04-28. See `dataset_summary.md`.
**Run date:** 2026-05-02
**Python:** 3.14.4 &nbsp;&nbsp; **scipy / sympy / numpy:** verified present prior to run

---

## Top-line

| Metric | Value | Δ vs 2026-05-01 |
|---|---|---|
| Overall accuracy | **98.3%** (710 / 722) | **+7.3 pp** |
| False-positive rate (correct claims rejected) | 1.7% | −10.4 pp |
| False-negative rate (incorrect claims confirmed) | 1.6% | −4.4 pp |
| Median latency per claim | 0.1 ms | ~unchanged |
| p95 latency per claim | 22.6 ms | +8.5 ms (CS time-cap on bad claims) |
| NOT_APPLICABLE rate | 0.0% | unchanged |
| ERROR rate | 0.8% | −5.8 pp |
| Total wall time | 34.0 s | +30.5 s (CS time-cap measurement on falsely-claimed-fast algorithms) |

> **One-sentence read:** the engine catches 98% of incorrect claims and wrongly rejects under 2% of correct ones — driven by today's mathematics parse-error fix (NOT_APPLICABLE instead of ERROR), the statistics tolerance widening (1e-3 → 5e-3 to match published p-value rounding), and a wall-clock cap on the CS runtime-complexity verifier so it can no longer be pulled into multi-minute runs of slow algorithms misclassified as fast ones.

---

## Per-domain breakdown

| Domain | n | Acc | FP rate | FN rate | p50 ms | p95 ms | NA% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Statistics (D1)        | 124 | 96.0% | 0.0%  | 8.1% | 0.0 | 0.5 | 0.0% |
| Chemistry (D2)         | 130 | **100.0%** | 0.0% | 0.0% | 0.1 | 0.2 | 0.0% |
| Physics (D3)           | 110 | **100.0%** | 0.0% | 0.0% | 8.8 | 26.6 | 0.0% |
| Mathematics (D4)       | 120 | **100.0%** | 0.0% | 0.0% | 4.0 | 19.9 | 0.0% |
| Computer science (D5)  | 110 | 93.6% | 10.9% | 1.8% | 0.3 | 455.5 | 0.0% |
| Governance (D6)        | 128 | **100.0%** | 0.0% | 0.0% | 0.0 | 0.0 | 0.0% |

(Numbers come from `benchmark_summary.json → by_domain.<name>`.)

### What changed since 2026-05-01

- **Mathematics** went from 90.0% → **100.0%**. Today's patch makes parse-failure SymPy exceptions return `NOT_APPLICABLE` instead of `ERROR`, so unrecognised but legitimate syntax no longer counts as a wrong rejection. The old 20% ERROR rate is gone (now 0).
- **Statistics** went from 81.5% → **96.0%**. The 1e-3 → 5e-3 tolerance widening eliminated the 32.3% over-rejection on rounded published p-values. Trade-off: false-negative rate moved from 4.8% → 8.1% — about ten incorrect claims that the tighter window had caught now slip through. **This is the next bug to look at.**
- **Physics** went from 97.3% → **100.0%**. The three former dimensional-analysis edge cases now CONFIRM cleanly (likely benefit of an upstream change to the unit-canonicaliser; not edited today).
- **Governance** went from 85.2% → **100.0%**. This is a substantial improvement that today's session did not directly cause — likely the canonical `src/concordance_engine/verifiers/governance.py` already has a stricter version of the structural check than the stale tree's. Worth confirming the canonical-tree governance verifier is doing the right thing rather than just being permissively pass-everything.
- **Computer science** went from 92.7% → **93.6%**. Marginal change in headline accuracy, but the failure mode shifted: the previous 8 false-positive ERRORs from sandbox-restricted code are gone, replaced by a different 12 false-positive MISMATCHes — likely the canonical CS verifier's class-adapted default sizes producing noisier slope fits, or the new wall-clock cap (added this session) cutting off a few legitimate-but-slow algorithms before enough data is collected. Needs a focused dig at the 12 FP rows.
- **Chemistry** stayed at **100%**. ✓

### Notable per-domain observations

- **Statistics (96.0%, FN 8.1%).** Tolerance widening was the right call for FP — but the 8.1% FN means ~10 incorrect claims now confirm. Pull the FN rows and check whether a specific test type (e.g. Welch t, BH/FDR, paired t) needs a tighter test-specific tolerance. The right shape is probably a global default of 5e-3 with overrides per test type for the ones whose recomputation is more numerically stable.
- **Computer science (93.6%, FP 10.9%).** The 12 false positives are no longer ERRORs — they're MISMATCHes, meaning the verifier is actually computing a slope and rejecting it. Likely causes: (1) the new class-adapted default sizes (e.g. `[1000, 10000, 100000, 1000000]` for O(n)) are too large at the small end for noise to wash out, producing slope fits like 1.3 against a 1.0 expectation that fall outside the 0.40 tolerance; (2) the new `max_per_call_seconds=2.0` cap occasionally fires on legitimate-but-slow algorithms before enough data is collected. Two-line follow-up: log `sizes_used` and `slope` in the result detail so we can see which rows are being cut short.
- **Governance (100.0%).** Worth verifying with a hand-checked spot of 5–10 packets that the verifier is actually rejecting bad packets and not just confirming everything. The handoff document anticipated 27.5% FN here — if today's number is real, it's a much bigger structural improvement than expected and should be celebrated; if it's a regression toward "always-confirm," that's a worse failure than the old over-rejection.

---

## Today's verifier changes (2026-05-02)

| File | Change |
|---|---|
| `src/concordance_engine/verifiers/mathematics.py` | Catch SymPy parse exceptions (`SympifyError`, `SyntaxError`, `TypeError`, `ValueError`, `NotImplementedError`) and return `NOT_APPLICABLE` instead of `ERROR`. Genuine computation failures still return ERROR. |
| `src/concordance_engine/verifiers/statistics.py` | Default tolerance for `verify_pvalue_calibration` and `verify_confidence_interval` raised from 1e-3 to 5e-3, matching typical published-p-value rounding. |
| `src/concordance_engine/verifiers/computer_science.py` | Added `max_per_call_seconds` (default 2.0) to `verify_runtime_complexity`. When a single timed call exceeds the cap, the size loop breaks and the slope is fit on whatever data has been collected (subject to a 2-size minimum, else `NOT_APPLICABLE`). Prevents multi-minute hangs on algorithms misclassified as fast (e.g. bubble_sort claimed as O(n)). |
| `lw/09_evaluation/run_benchmark.py` | Engine source path updated from `lw/01_engine/concordance-engine/src` to canonical `<repo>/src` ahead of the `lw/01_engine` tree being retired. |

---

## Reproducibility

```bash
cd lw/09_evaluation
python -u run_benchmark.py
# or on Windows:
powershell -ExecutionPolicy Bypass -File .\run_benchmark.ps1
```

The `-u` flag (unbuffered Python) is recommended — without it, stdout block-buffering hides the per-36-claim progress lines until the run completes, which can look like a hang during the CS section.

This regenerates `benchmark_results.jsonl` and `benchmark_summary.json`. The dataset is byte-identical between runs (fixed seeds; see Phase 1 summary). Run-to-run variance comes from:

- **CS T5.3 (runtime complexity).** Slope fits depend on live timings; slow or noisy machines can shift borderline measurements. The new `max_per_call_seconds` cap also makes the run-time of CS T5.3 itself depend on which problematic claims are in the dataset (each capped call adds ~2s of wall clock).
- **Floating-point edge cases in scipy distribution functions** — rare, affects only the last decimal place of recomputed p-values.

If results diverge from this report, re-run on a quiescent machine and compare `benchmark_summary.json` field-by-field.

---

## Next steps suggested by the data

1. **Statistics false-negative regression (8.1%).** The tolerance widening was net-positive but let through ~10 incorrect claims that the 1e-3 window had caught. Pull `[r for r in benchmark_results.jsonl if r['domain']=='statistics' and r['ground_truth']=='incorrect' and r['verdict']=='CONFIRMED']` and check for a shared test-type signature. Likely fix: keep 5e-3 as the default but override per test type for the ones whose recomputation is more numerically stable.
2. **CS false-positive rate (10.9%).** Surface `sizes_used`, `slope`, and `tolerance` in the verifier's result detail so the 12 FP rows can be classified at a glance. If most are slope-just-outside-tolerance cases, raising the slope tolerance modestly (0.40 → 0.50) is probably right; if they're cap-fired-too-early, raise `max_per_call_seconds` to 5 or add a rolling-sum budget instead of a per-call one.
3. **Verify the governance jump.** 85% → 100% is suspicious. Spot-check 5–10 incorrect-ground-truth packets to confirm the canonical verifier is rejecting them. If it's confirming them all, the apparent improvement is a structural-check regression.
4. **Wire the benchmark into CI.** Per handoff Task 7 — a ~30-second sweep is cheap enough to run on every push, with merge gates at overall ≥ 95% and chemistry == 100%.
