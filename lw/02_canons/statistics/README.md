# Statistics Canon v1.0

Constraint language for inferential claims across all Concordance domains.

## Purpose

Statistics is the calibration layer that enforces:
- Probabilistic discipline (axioms valid, distributions specified)
- Inference honesty (effect size with significance, CIs interpreted correctly)
- Pre-specification (hypotheses fixed before data, separating exploration from confirmation)
- Causal hygiene (identification strategy named for any causal claim)
- Multiplicity control (correction applied or pre-registered comparisons)

## Structure

- `canon.yaml` → registry + entrypoints
- `core/statistics_core.yaml` → frozen nouns + RED constraints + FLOOR bounds + WAY methods + diagnostics + scripture anchors
- `schema/statistics_schema.yaml` → packet schema for Statistics submissions
- `modules/` → inference, causal_inference, experimental_design, multiple_testing, regression
- `templates/` → packet template + analysis checklist
- `tools/validator_statistics.py` → wrapper around `concordance_engine.domains.statistics`

## Canon Adjustments

- RED anchor: Scripture as ultimate authority. Honest weighing (Prov 11:1) and the falsifiability principle (1 Thess 5:21) ground the canon.
- Gates: RED → FLOOR → BROTHERS → GOD (project-wide).
- Watchmaking parallel: Crown and setting — calibration adjusts the system to reality.

## Install Order

`canon → schema → core → templates → modules → tools`

## Status

Canonical. The Python validator at `01_engine/concordance-engine/src/concordance_engine/domains/statistics.py` is the runnable form. The canon documents in this directory are the human-readable contract.

## Modules Coverage

| Module | Status | Validator Coverage |
|---|---|---|
| inference | CANONICAL | pvalue_interpreted_correctly, effect_size_reported, CI interpretation |
| causal_inference | CANONICAL | causal_identification_stated |
| experimental_design | CANONICAL | sampling_mechanism, sample_size_justified, power_computed |
| multiple_testing | CANONICAL | multiple_comparisons_corrected, hypothesis_prespecified |
| regression | CANONICAL | distributional_assumptions_tested, missing_data_mechanism |
| descriptive | DEFERRED | (covered by inference) |
| probability | DEFERRED | (covered by core RED constraint 1) |
| bayesian | DEFERRED | prior_justified (in core) |

## Companion Resource

The NHANES falsification study at `06_validation/framework_validation_v3_final/` is a worked example of this canon applied to a real pre-registered analysis. Read its ANALYSIS_PLAN.md alongside this canon.
