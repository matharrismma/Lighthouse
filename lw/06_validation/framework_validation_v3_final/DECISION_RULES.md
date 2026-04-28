# DECISION RULES — Hypothesis Verdict Rubric
## Version 3.1 | Frozen 2026-03-04

> **Principle:** Truth determines. The outcome categories exist before
> the data are examined. No hypothesis may be labeled SUPPORTED without
> surviving its full truth-suite.

---

## Three Outcomes

### SUPPORTED

The hypothesis passes **all** of:

1. **Primary prereg test passes** (unweighted, locked definitions)
2. **Stability suite passes** (where applicable):
   - H2: ARI ≥ 0.40 across bootstrap; cycle-consistent profiles
   - H3: Per-cycle deltas non-negative in all cycles with adequate N
3. **Sensitivity suite does not overturn:**
   - Weighted analysis preserves direction and approximate magnitude
   - If weighted ΔAUC reverses sign → cannot be SUPPORTED

### FALSIFIED

The hypothesis **fails** primary prereg criteria **AND** sensitivity
analysis does not rescue:

- H1: AUC < 0.60 OR ΔAUC ≤ 0, and weighted analysis also fails
- H2: best_k < 2 OR medication p > 0.05, and stability also fails
- H3: ΔAUC_L5 < 0.01 OR negative in any adequate cycle, and robustness
  confirms

### INCONCLUSIVE

Any of the following:

- Insufficient sample size or events for the analysis to run
- Primary test passes but stability/sensitivity suite fails or reverses
- Primary test fails but sensitivity suite rescues (signals fragility)
- Thin margins where bootstrap CI spans the decision boundary
- Layer composites have excessive missingness (>40% excluded by min-obs)

---

## Per-Hypothesis Gate Table

### H1 (Shared Manifold → 10-Year Mortality)

| Gate | Criterion | Fail → |
|------|-----------|--------|
| Eligibility | N ≥ 500, events ≥ 50 | INCONCLUSIVE |
| Primary AUC | AUC_test ≥ 0.60 | FALSIFIED (if sensitivity agrees) |
| Primary lift | ΔAUC > 0 vs age+sex | FALSIFIED (if sensitivity agrees) |
| Sensitivity | Weighted ΔAUC > 0 | INCONCLUSIVE (if primary passed) |
| Stability | Bootstrap CI excludes 0 | INCONCLUSIVE (if marginal) |

### H2 (Multi-Path Hyperglycemia)

| Gate | Criterion | Fail → |
|------|-----------|--------|
| Eligibility | N_band ≥ 500 | INCONCLUSIVE |
| Cluster count | best_k ≥ 2 | FALSIFIED |
| External valid. | medication χ² p ≤ 0.05 in test set | FALSIFIED (if stability agrees) |
| Stability | ARI ≥ 0.40 (50 bootstrap) | INCONCLUSIVE |
| Cycle consistency | Profiles not single-cycle-driven | INCONCLUSIVE |

### H3 (Layer 5 Hierarchy)

| Gate | Criterion | Fail → |
|------|-----------|--------|
| Eligibility | N ≥ 500, both classes present | INCONCLUSIVE |
| Primary lift | ΔAUC_L5 ≥ 0.015 (pooled CV) | FALSIFIED (if robustness agrees) |
| Clinical bar | ΔAUC_L5 ≥ 0.02 | INCONCLUSIVE (blocks SUPPORTED) |
| Cycle sign | ΔAUC ≥ 0 in every cycle with N ≥ 300 | FALSIFIED (strict) or INCONCLUSIVE (if N marginal) |
| Sensitivity | Weighted ΔAUC_L5 ≥ 0.015 | INCONCLUSIVE (if primary passed) |
| Brier/pAUC | Reported but does not gate verdict | Informational |

---

## Reporting Requirements

Every results JSON must include, per hypothesis:

```json
{
  "decision": "SUPPORTED | FALSIFIED | INCONCLUSIVE",
  "decision_basis": "narrative explanation of which gates passed/failed",
  "primary_result": { ... },
  "stability_result": { ... },
  "sensitivity_result": { ... },
  "gates_passed": ["eligibility", "primary_lift", ...],
  "gates_failed": [],
  "gates_skipped": []
}
```

## Amendment Protocol

Any change to these rules after the first data-touching run requires:

1. CHANGELOG.md entry with rationale
2. Version bump in ANALYSIS_PLAN.md
3. Full re-run from scratch
4. Both old and new results preserved in results/
