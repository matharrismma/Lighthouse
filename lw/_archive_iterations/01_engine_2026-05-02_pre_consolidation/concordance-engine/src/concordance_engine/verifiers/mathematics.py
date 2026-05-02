"""
verifiers/mathematics.py — Symbolic math verification via SymPy.
"""
from __future__ import annotations
from typing import Any, Dict, List
from .base import VerifierResult


def _sympify(expr_str: str, variables: List[str] = None):
    import sympy as sp
    syms = {}
    if variables:
        for v in variables:
            syms[v] = sp.Symbol(v)
    # Common math functions
    syms.update({k: getattr(sp, k) for k in
                 ["sin", "cos", "tan", "exp", "log", "sqrt", "atan",
                  "asin", "acos", "pi", "E", "I", "oo", "zoo"]
                 if hasattr(sp, k)})
    return sp.sympify(expr_str, locals=syms)


def verify_equality(spec: Dict[str, Any]) -> VerifierResult:
    name = "mathematics.equality"
    try:
        import sympy as sp
        variables = spec.get("variables", [])
        a = _sympify(str(spec["expr_a"]), variables)
        b = _sympify(str(spec["expr_b"]), variables)
        diff = sp.simplify(a - b)
        if diff == 0:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"{spec['expr_a']} == {spec['expr_b']} (verified symbolically)")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"{spec['expr_a']} ≠ {spec['expr_b']}; simplified diff = {diff}")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_derivative(spec: Dict[str, Any]) -> VerifierResult:
    name = "mathematics.derivative"
    try:
        import sympy as sp
        var = spec["variable"]
        x = sp.Symbol(var)
        f = _sympify(str(spec["function"]), [var])
        computed = sp.diff(f, x)
        claimed = _sympify(str(spec["claimed_derivative"]), [var])
        diff = sp.simplify(computed - claimed)
        if diff == 0:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"d/d{var}({spec['function']}) = {computed} (confirmed)")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Computed d/d{var}({spec['function']}) = {computed}, "
                                     f"claimed = {spec['claimed_derivative']}")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_integral(spec: Dict[str, Any]) -> VerifierResult:
    name = "mathematics.integral"
    try:
        import sympy as sp
        var = spec["variable"]
        x = sp.Symbol(var)
        integrand = _sympify(str(spec["integrand"]), [var])
        claimed = _sympify(str(spec["claimed_antiderivative"]), [var])
        # Verify by differentiating the claimed antiderivative
        computed_diff = sp.diff(claimed, x)
        diff = sp.simplify(computed_diff - integrand)
        if diff == 0:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"∫{spec['integrand']}d{var} antiderivative verified.")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"d/d{var}({spec['claimed_antiderivative']}) = {computed_diff}, "
                                     f"not {spec['integrand']}")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_limit(spec: Dict[str, Any]) -> VerifierResult:
    name = "mathematics.limit"
    try:
        import sympy as sp
        var = spec["variable"]
        x = sp.Symbol(var)
        f = _sympify(str(spec["function"]), [var])
        point = spec["point"]
        if point in ("oo", "inf", float("inf")):
            pt = sp.oo
        elif point in ("-oo", "-inf", float("-inf")):
            pt = -sp.oo
        else:
            pt = sp.sympify(str(point))
        computed = sp.limit(f, x, pt)
        claimed = _sympify(str(spec["claimed_limit"]), [var])
        diff = sp.simplify(computed - claimed)
        if diff == 0:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"lim_{var}→{point} {spec['function']} = {computed} (confirmed)")
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Computed limit = {computed}, claimed = {spec['claimed_limit']}")
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def verify_solve(spec: Dict[str, Any]) -> VerifierResult:
    name = "mathematics.solve"
    try:
        import sympy as sp
        var = spec["variable"]
        x = sp.Symbol(var)
        eq = _sympify(str(spec["equation"]), [var])
        solutions = sp.solve(eq, x)
        claimed = [sp.sympify(str(s)) for s in spec["claimed_solutions"]]
        # Check each claimed solution is in computed solutions (up to simplification)
        missing = []
        for c in claimed:
            if not any(sp.simplify(c - s) == 0 for s in solutions):
                missing.append(str(c))
        extra = []
        for s in solutions:
            if not any(sp.simplify(s - c) == 0 for c in claimed):
                extra.append(str(s))
        if not missing and not extra:
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"Solutions {claimed} verified for {spec['equation']}=0")
        detail = ""
        if missing:
            detail += f"Missing claimed solutions: {missing}. "
        if extra:
            detail += f"Unclaimed computed solutions: {extra}."
        return VerifierResult(name=name, status="MISMATCH", detail=detail.strip())
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def run(packet: dict) -> list:
    results = []
    verify = packet.get("MATH_VERIFY") or {}
    if not verify:
        return results
    if "expr_a" in verify and "expr_b" in verify:
        results.append(verify_equality(verify))
    elif "function" in verify and "claimed_derivative" in verify:
        results.append(verify_derivative(verify))
    elif "integrand" in verify and "claimed_antiderivative" in verify:
        results.append(verify_integral(verify))
    elif "function" in verify and "claimed_limit" in verify:
        results.append(verify_limit(verify))
    elif "equation" in verify and "claimed_solutions" in verify:
        results.append(verify_solve(verify))
    return results
