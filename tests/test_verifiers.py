"""Unit tests for the verifier layer.

These tests exercise each verifier directly, without the engine wrapper.
Run: PYTHONPATH=src python tests/test_verifiers.py
"""
from concordance_engine.verifiers.chemistry import verify_equation, verify_temperature
from concordance_engine.verifiers.physics import (
    verify_dimensional_consistency, verify_conservation,
)
from concordance_engine.verifiers.mathematics import (
    verify_equality, verify_derivative, verify_integral,
    verify_limit, verify_solve,
)
from concordance_engine.verifiers.statistics import (
    verify_pvalue_calibration, verify_significance_consistency,
    verify_effect_size_present, verify_multiple_comparisons,
    verify_confidence_interval,
)
from concordance_engine.verifiers.computer_science import (
    verify_static_termination, verify_functional_correctness,
    verify_runtime_complexity,
)
from concordance_engine.verifiers.biology import (
    verify_replicates, verify_orthogonal_assays,
    verify_dose_response_monotonicity, verify_sample_size_powered,
)
from concordance_engine.verifiers.governance import (
    verify_decision_packet_shape, verify_witness_count_consistency,
)


PASS = 0
FAIL = 0


def expect(name, result, expected_status):
    global PASS, FAIL
    actual = result.status
    ok = actual == expected_status
    icon = "✓" if ok else "✗"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    detail = result.detail[:80]
    print(f"  {icon} [{actual:<14}] {name}: {detail}")


# ── Chemistry ──
print("Chemistry verifier:")
expect("balanced 2H2 + O2 -> 2H2O",
       verify_equation("2 H2 + O2 -> 2 H2O"), "CONFIRMED")
expect("unbalanced H2 + O2 -> H2O (auto-balances)",
       verify_equation("H2 + O2 -> H2O"), "MISMATCH")
expect("propane combustion",
       verify_equation("C3H8 + 5 O2 -> 3 CO2 + 4 H2O"), "CONFIRMED")
expect("permanganate redox in acid",
       verify_equation("MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O"),
       "CONFIRMED")
expect("ionic dissolution NaCl -> Na+ + Cl-",
       verify_equation("NaCl -> Na+ + Cl-"), "CONFIRMED")
expect("nested groups Cu(OH)2 -> CuO + H2O",
       verify_equation("Cu(OH)2 -> CuO + H2O"), "CONFIRMED")
expect("temperature 298 K", verify_temperature(298.15), "CONFIRMED")
expect("temperature 0 K", verify_temperature(0), "MISMATCH")
expect("temperature -10 K", verify_temperature(-10), "MISMATCH")

# ── Physics ──
print("\nPhysics verifier:")
expect("F = m*a (newton)",
       verify_dimensional_consistency(
           "F = m * a",
           {"F": "newton", "m": "kilogram", "a": "meter/second**2"}),
       "CONFIRMED")
expect("E = m*c^2 (joule)",
       verify_dimensional_consistency(
           "E = m * c**2",
           {"E": "joule", "m": "kilogram", "c": "meter/second"}),
       "CONFIRMED")
expect("KE = m*v^2/2",
       verify_dimensional_consistency(
           "KE = m * v**2 / 2",
           {"KE": "joule", "m": "kilogram", "v": "meter/second"}),
       "CONFIRMED")
expect("F = m*v (wrong)",
       verify_dimensional_consistency(
           "F = m * v",
           {"F": "newton", "m": "kilogram", "v": "meter/second"}),
       "MISMATCH")
expect("conservation identical",
       verify_conservation({"p": 12.5}, {"p": 12.5}), "CONFIRMED")
expect("conservation small drift relaxed tol",
       verify_conservation({"p": 12.5}, {"p": 12.4999},
                           tolerance_relative=1e-3), "CONFIRMED")
expect("conservation big drift",
       verify_conservation({"p": 12.5}, {"p": 11.0}), "MISMATCH")

# ── Mathematics ──
print("\nMathematics verifier:")
expect("(x+1)^2 == x^2+2x+1",
       verify_equality({"expr_a": "(x+1)**2",
                        "expr_b": "x**2 + 2*x + 1",
                        "variables": ["x"]}), "CONFIRMED")
expect("(x+1)^2 != x^2+x+1",
       verify_equality({"expr_a": "(x+1)**2",
                        "expr_b": "x**2 + x + 1",
                        "variables": ["x"]}), "MISMATCH")
expect("d/dx sin(x) = cos(x)",
       verify_derivative({"function": "sin(x)", "variable": "x",
                          "claimed_derivative": "cos(x)"}), "CONFIRMED")
expect("d/dx sin(x) ≠ -cos(x)",
       verify_derivative({"function": "sin(x)", "variable": "x",
                          "claimed_derivative": "-cos(x)"}), "MISMATCH")
expect("integral of 2x is x^2 + C",
       verify_integral({"integrand": "2*x", "variable": "x",
                        "claimed_antiderivative": "x**2 + 7"}), "CONFIRMED")
expect("integral of 1/(1+x^2) is atan(x)",
       verify_integral({"integrand": "1/(1+x**2)", "variable": "x",
                        "claimed_antiderivative": "atan(x)"}), "CONFIRMED")
expect("lim x->0 sin(x)/x = 1",
       verify_limit({"function": "sin(x)/x", "variable": "x",
                     "point": 0, "claimed_limit": 1}), "CONFIRMED")
expect("solve x^2 - 5x + 6 = {2, 3}",
       verify_solve({"equation": "x**2 - 5*x + 6", "variable": "x",
                     "claimed_solutions": [2, 3]}), "CONFIRMED")

# ── Statistics ──
print("\nStatistics verifier:")
expect("two-sample t recompute",
       verify_pvalue_calibration({
           "test": "two_sample_t", "n1": 30, "n2": 30,
           "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
           "claimed_p": 0.0003, "tolerance": 0.001}), "CONFIRMED")
expect("two-sample t wrong claim",
       verify_pvalue_calibration({
           "test": "two_sample_t", "n1": 30, "n2": 30,
           "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
           "claimed_p": 0.05}), "MISMATCH")
expect("chi2 recompute",
       verify_pvalue_calibration({
           "test": "chi2", "statistic": 7.81, "df": 3, "claimed_p": 0.05,
           "tolerance": 0.01}), "CONFIRMED")
expect("Bonferroni rejection set correct",
       verify_multiple_comparisons({
           "raw_p_values": [0.001, 0.008, 0.04, 0.05, 0.5],
           "method": "bonferroni", "alpha": 0.05,
           "claimed_rejected_indices": [0, 1]}), "CONFIRMED")
expect("Bonferroni rejection set wrong",
       verify_multiple_comparisons({
           "raw_p_values": [0.001, 0.008, 0.04, 0.05, 0.5],
           "method": "bonferroni", "alpha": 0.05,
           "claimed_rejected_indices": [0]}), "MISMATCH")
expect("BH/FDR rejection set",
       verify_multiple_comparisons({
           "raw_p_values": [0.001, 0.008, 0.04, 0.05, 0.5],
           "method": "bh", "alpha": 0.05,
           "claimed_rejected_indices": [0, 1]}), "CONFIRMED")
expect("significance consistent",
       verify_significance_consistency({"p_value": 0.001, "alpha": 0.05,
                                        "claimed_significance": "significant"}),
       "CONFIRMED")
expect("significance inconsistent",
       verify_significance_consistency({"p_value": 0.06, "alpha": 0.05,
                                        "claimed_significance": "significant"}),
       "MISMATCH")
expect("CI containing estimate",
       verify_confidence_interval({"estimate": 5.0, "ci_low": 4.5, "ci_high": 5.5}),
       "CONFIRMED")
expect("CI not containing estimate",
       verify_confidence_interval({"estimate": 5.0, "ci_low": 5.5, "ci_high": 6.0}),
       "MISMATCH")

# ── Tail-spec aliasing (regression: 'two' was silently misrouted to one-tailed) ──
print("\nStatistics tail aliasing:")
_two_sided_aliases = ["two-sided", "two_sided", "twosided", "two", "both", "2"]
for alias in _two_sided_aliases:
    expect(f"two-sample t with tail={alias!r} accepts as two-sided",
           verify_pvalue_calibration({
               "test": "two_sample_t", "n1": 30, "n2": 30,
               "mean1": 5.2, "mean2": 4.8, "sd1": 1.1, "sd2": 1.0,
               "tail": alias, "claimed_p": 0.146, "tolerance": 0.005}),
           "CONFIRMED")
expect("z-test tail='right' accepts as greater",
       verify_pvalue_calibration({"test": "z", "z": 1.96, "tail": "right",
                                  "claimed_p": 0.025, "tolerance": 0.005}),
       "CONFIRMED")
expect("z-test tail='upper' accepts as greater",
       verify_pvalue_calibration({"test": "z", "z": 1.96, "tail": "upper",
                                  "claimed_p": 0.025, "tolerance": 0.005}),
       "CONFIRMED")

# ── Computer Science ──
print("\nComputer Science verifier:")
expect("factorial recursive",
       verify_static_termination("def fact(n):\n    if n <= 1: return 1\n    return n * fact(n-1)"),
       "CONFIRMED")
expect("factorial ternary",
       verify_static_termination("def fact(n):\n    return 1 if n <= 1 else n * fact(n-1)"),
       "CONFIRMED")
expect("infinite while True",
       verify_static_termination("def loop():\n    while True:\n        x = 1"),
       "MISMATCH")
expect("unguarded recursion",
       verify_static_termination("def silly(n):\n    return silly(n) + 1"),
       "MISMATCH")
expect("functional correctness pass",
       verify_functional_correctness({
           "code": "def add(a, b): return a + b",
           "function_name": "add",
           "test_cases": [{"args": [2, 3], "expected": 5},
                          {"args": [-1, 1], "expected": 0}]}),
       "CONFIRMED")
expect("functional correctness fail",
       verify_functional_correctness({
           "code": "def add(a, b): return a - b",
           "function_name": "add",
           "test_cases": [{"args": [2, 3], "expected": 5}]}),
       "MISMATCH")

# ── input alias (regression: list-valued input wasn't splatted) ──
expect("functional correctness with input=list (splatted)",
       verify_functional_correctness({
           "code": "def add(a, b): return a + b",
           "function_name": "add",
           "test_cases": [{"input": [2, 3], "expected": 5},
                          {"input": [-1, 1], "expected": 0}]}),
       "CONFIRMED")
expect("functional correctness with input=dict (kwargs)",
       verify_functional_correctness({
           "code": "def add(a, b): return a + b",
           "function_name": "add",
           "test_cases": [{"input": {"a": 2, "b": 3}, "expected": 5}]}),
       "CONFIRMED")
expect("functional correctness with input=scalar (single arg)",
       verify_functional_correctness({
           "code": "def square(x): return x * x",
           "function_name": "square",
           "test_cases": [{"input": 5, "expected": 25}]}),
       "CONFIRMED")

# Skipping runtime complexity — covered via the engine integration tests.

# ── Biology ──
print("\nBiology verifier:")
expect("4 replicates >= 3", verify_replicates({"n_replicates": 4}), "CONFIRMED")
expect("2 replicates < 3", verify_replicates({"n_replicates": 2}), "MISMATCH")
expect("3 distinct assays",
       verify_orthogonal_assays({"assay_classes": ["qPCR", "WB", "imaging"]}),
       "CONFIRMED")
expect("1 distinct assay",
       verify_orthogonal_assays({"assay_classes": ["qPCR", "qPCR"]}), "MISMATCH")
expect("monotonic increasing",
       verify_dose_response_monotonicity({"dose_response": {
           "doses": [0, 1, 5, 25], "responses": [0.1, 0.3, 0.5, 0.8],
           "expected_direction": "increasing"}}),
       "CONFIRMED")
expect("non-monotonic with reversal",
       verify_dose_response_monotonicity({"dose_response": {
           "doses": [0, 1, 5, 25], "responses": [0.1, 0.3, 0.2, 0.8],
           "expected_direction": "increasing"}}),
       "MISMATCH")
expect("powered n=64 d=0.5",
       verify_sample_size_powered({"power_analysis": {
           "effect_size": 0.5, "alpha": 0.05, "n_per_group": 64}}),
       "CONFIRMED")
expect("underpowered n=20 d=0.5",
       verify_sample_size_powered({"power_analysis": {
           "effect_size": 0.5, "alpha": 0.05, "n_per_group": 20}}),
       "MISMATCH")

# ── Governance ──
print("\nGovernance verifier:")
complete_dp = {
    "title": "Approve grant",
    "scope": "mesh",
    "red_items": ["no exploitation"],
    "floor_items": ["budget within tolerance"],
    "way_path": "Disburse against milestone reports per the agreement.",
    "execution_steps": ["Verify milestones", "Sign disbursement"],
    "witnesses": ["Board Chair", "Treasurer"],
}
expect("complete decision packet",
       verify_decision_packet_shape(complete_dp), "CONFIRMED")
expect("empty decision packet",
       verify_decision_packet_shape({"title": "", "scope": "x",
                                     "red_items": [], "floor_items": [],
                                     "way_path": "", "execution_steps": [],
                                     "witnesses": []}),
       "MISMATCH")
expect("invalid scope",
       verify_decision_packet_shape({**complete_dp, "scope": "everywhere"}),
       "MISMATCH")
expect("witness count match",
       verify_witness_count_consistency(complete_dp, {"witness_count": 2}),
       "CONFIRMED")
expect("witness count mismatch",
       verify_witness_count_consistency(complete_dp, {"witness_count": 5}),
       "MISMATCH")

# ── Summary ──
print(f"\n{'=' * 60}")
if FAIL:
    print(f"FAIL: {PASS} passed, {FAIL} failed.")
    raise SystemExit(1)
else:
    print(f"All {PASS} verifier tests passed.")
print(f"{'=' * 60}")
