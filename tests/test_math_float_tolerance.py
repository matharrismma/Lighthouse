"""Regression: the mathematics verifiers must tolerate floating-point residue.

A claim like "0.1 + 0.2 == 0.3" is TRUE, but IEEE-754 carries a ~5.55e-17
residue, so an exact `simplify(a - b) == 0` check used to report a false
MISMATCH. These tests pin the tolerant behaviour while proving that genuinely
different numbers, removable singularities, and exact symbolic identities are
all unaffected.
"""
from concordance_engine.verifiers.mathematics import (
    verify_equality, verify_derivative, verify_integral,
    verify_limit, verify_solve,
)


# ── the reported defect: float roundoff must not be a MISMATCH ──────────

def test_equality_float_roundoff_confirms():
    r = verify_equality({"expr_a": "0.1 + 0.2", "expr_b": "0.3"})
    assert r.status == "CONFIRMED"
    assert r.data and r.data.get("exact") is False  # honest: approximate, not exact


def test_equality_rational_vs_float_confirms():
    r = verify_equality({"expr_a": "1/3", "expr_b": "0.3333333333333333"})
    assert r.status == "CONFIRMED"


def test_equality_scale_relative_confirms():
    # Residue scales with magnitude; tolerance is relative to the larger side.
    r = verify_equality({"expr_a": "1e12 + 0.1 + 0.2", "expr_b": "1e12 + 0.3"})
    assert r.status == "CONFIRMED"


# ── the fix must NOT loosen real comparisons ────────────────────────────

def test_equality_real_difference_still_mismatches():
    # A 1e-5 gap is a real difference, not roundoff.
    r = verify_equality({"expr_a": "0.1 + 0.2", "expr_b": "0.30001"})
    assert r.status == "MISMATCH"


def test_equality_removable_singularity_still_mismatches():
    # x/x cancels to 1 but is undefined at x=0 — must stay MISMATCH.
    r = verify_equality({"expr_a": "x/x", "expr_b": "1", "variables": ["x"]})
    assert r.status == "MISMATCH"


def test_equality_exact_symbolic_reports_exact():
    r = verify_equality({"expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1",
                         "variables": ["x"]})
    assert r.status == "CONFIRMED"
    # exact identities carry no approximate-residual data payload
    assert not (r.data and r.data.get("exact") is False)


def test_equality_custom_tolerance_override():
    # Tightening atol/rtol below the residue turns the match back into a miss.
    r = verify_equality({"expr_a": "0.1 + 0.2", "expr_b": "0.3",
                         "rtol": 0.0, "atol": 0.0})
    assert r.status == "MISMATCH"


# ── the same fix applies to the sibling verifiers ───────────────────────

def test_derivative_float_confirms():
    r = verify_derivative({"function": "0.5*x**2", "variable": "x",
                           "claimed_derivative": "0.5*2*x"})
    assert r.status == "CONFIRMED"


def test_integral_float_confirms():
    r = verify_integral({"integrand": "0.3", "variable": "x",
                         "claimed_antiderivative": "0.1*x + 0.2*x"})
    assert r.status == "CONFIRMED"


def test_limit_float_confirms():
    r = verify_limit({"function": "sin(x)/x", "variable": "x",
                      "point": "0", "claimed_limit": "1.0"})
    assert r.status == "CONFIRMED"


def test_solve_float_confirms():
    r = verify_solve({"equation": "x - 0.3 = 0.1 + 0.2 - 0.3", "variable": "x",
                      "claimed_solutions": ["0.3"]})
    assert r.status == "CONFIRMED"
