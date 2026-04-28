"""Mathematics verifier.

Checks performed:
  * symbolic_equality: claim "expr_a == expr_b" verified via simplify(a-b)==0
  * derivative: claim "d/dx of f = g" verified symbolically
  * integral: claim "integral of f dx = g" verified symbolically (indefinite)
  * limit: claim "lim_{x->a} f(x) = L" verified
  * solve: claim "solutions of eq for x are S" verified

Each check accepts string expressions parsed by sympy.
"""
from __future__ import annotations
from typing import Any, Dict, List

import sympy
from sympy import (
    sympify, simplify, diff, integrate, limit, solve, Symbol, oo, S, expand
)

from .base import VerifierResult, na, confirm, mismatch, error


def _parse(expr: str, var_names: List[str] = None):
    locals_ = {n: Symbol(n) for n in (var_names or [])}
    # Allow common aliases
    locals_.setdefault("oo", oo)
    locals_.setdefault("inf", oo)
    return sympify(expr, locals=locals_)


def verify_equality(spec: Dict[str, Any]) -> VerifierResult:
    a = spec.get("expr_a")
    b = spec.get("expr_b")
    var_names = spec.get("variables", [])
    if a is None or b is None:
        return na("mathematics.equality")
    try:
        ea = _parse(a, var_names)
        eb = _parse(b, var_names)
        diff_ = simplify(ea - eb)
        if diff_ == 0:
            return confirm("mathematics.equality", f"{a} == {b} simplifies to zero")
        # Try expand in case simplify didn't normalize
        if expand(ea - eb) == 0:
            return confirm("mathematics.equality", f"{a} == {b} after expand")
        return mismatch("mathematics.equality", f"{a} - ({b}) simplifies to {diff_}")
    except Exception as e:
        return error("mathematics.equality", f"parse/simplify failure: {e}")


def verify_derivative(spec: Dict[str, Any]) -> VerifierResult:
    f = spec.get("function")
    var = spec.get("variable", "x")
    claimed = spec.get("claimed_derivative")
    if f is None or claimed is None:
        return na("mathematics.derivative")
    try:
        x = Symbol(var)
        ef = _parse(f, [var])
        ec = _parse(claimed, [var])
        actual = diff(ef, x)
        if simplify(actual - ec) == 0:
            return confirm("mathematics.derivative",
                           f"d/d{var} of {f} = {actual}, matches {claimed}")
        return mismatch("mathematics.derivative",
                        f"d/d{var} of {f} = {actual}, but claimed {claimed}",
                        {"computed": str(actual), "claimed": str(ec)})
    except Exception as e:
        return error("mathematics.derivative", f"failure: {e}")


def verify_integral(spec: Dict[str, Any]) -> VerifierResult:
    f = spec.get("integrand")
    var = spec.get("variable", "x")
    claimed = spec.get("claimed_antiderivative")
    if f is None or claimed is None:
        return na("mathematics.integral")
    try:
        x = Symbol(var)
        ef = _parse(f, [var])
        ec = _parse(claimed, [var])
        # Differentiate the claimed antiderivative and check it equals the integrand
        derivative = diff(ec, x)
        if simplify(derivative - ef) == 0:
            return confirm("mathematics.integral",
                           f"d/d{var} of claimed antiderivative {claimed} = {ef} ✓")
        return mismatch("mathematics.integral",
                        f"d/d{var} of {claimed} = {derivative}, expected {ef}",
                        {"derivative_of_claim": str(derivative), "integrand": str(ef)})
    except Exception as e:
        return error("mathematics.integral", f"failure: {e}")


def verify_limit(spec: Dict[str, Any]) -> VerifierResult:
    f = spec.get("function")
    var = spec.get("variable", "x")
    point = spec.get("point")
    claimed = spec.get("claimed_limit")
    if f is None or point is None or claimed is None:
        return na("mathematics.limit")
    try:
        x = Symbol(var)
        ef = _parse(f, [var])
        ep = _parse(str(point), [var])
        ec = _parse(str(claimed), [var])
        actual = limit(ef, x, ep)
        if simplify(actual - ec) == 0:
            return confirm("mathematics.limit",
                           f"lim_{{{var}->{point}}} {f} = {actual}, matches {claimed}")
        return mismatch("mathematics.limit",
                        f"lim_{{{var}->{point}}} {f} = {actual}, claimed {claimed}",
                        {"computed": str(actual), "claimed": str(ec)})
    except Exception as e:
        return error("mathematics.limit", f"failure: {e}")


def verify_solve(spec: Dict[str, Any]) -> VerifierResult:
    eq = spec.get("equation")
    var = spec.get("variable", "x")
    claimed = spec.get("claimed_solutions")
    if eq is None or claimed is None:
        return na("mathematics.solve")
    try:
        x = Symbol(var)
        # Allow "lhs = rhs" syntax by converting to lhs - rhs
        if "=" in eq and "==" not in eq:
            lhs, rhs = eq.split("=", 1)
            eq_expr = _parse(lhs, [var]) - _parse(rhs, [var])
        else:
            eq_expr = _parse(eq, [var])
        actual = sorted(solve(eq_expr, x), key=lambda s: str(s))
        claimed_set = sorted([_parse(str(c), [var]) for c in claimed], key=lambda s: str(s))
        # Compare as sets (sympy may return solutions in different forms)
        if len(actual) != len(claimed_set):
            return mismatch("mathematics.solve",
                            f"solutions count mismatch: actual {actual} vs claimed {claimed_set}")
        for a, c in zip(actual, claimed_set):
            if simplify(a - c) != 0:
                return mismatch("mathematics.solve",
                                f"solution {a} != claimed {c}",
                                {"computed": [str(s) for s in actual],
                                 "claimed": [str(s) for s in claimed_set]})
        return confirm("mathematics.solve",
                       f"solutions {[str(s) for s in actual]} match claim")
    except Exception as e:
        return error("mathematics.solve", f"failure: {e}")


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MATH_VERIFY") or {}

    if "expr_a" in mv and "expr_b" in mv:
        results.append(verify_equality(mv))
    if "function" in mv and "claimed_derivative" in mv:
        results.append(verify_derivative(mv))
    if "integrand" in mv and "claimed_antiderivative" in mv:
        results.append(verify_integral(mv))
    if "function" in mv and "point" in mv and "claimed_limit" in mv:
        results.append(verify_limit(mv))
    if "equation" in mv and "claimed_solutions" in mv:
        results.append(verify_solve(mv))

    if not results:
        results.append(na("mathematics", "no MATH_VERIFY artifacts present"))
    return results
