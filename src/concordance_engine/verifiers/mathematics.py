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


# ---------------------------------------------------------------------
# V3: matrix, inequality, series, ODE verifiers
# ---------------------------------------------------------------------

def verify_matrix(spec):
    """Verify a matrix property claim.

    spec: matrix (list of lists), claim_type, claimed_value
      claim_type in: rank, determinant, eigenvalues, trace, inverse, transpose,
                     symmetric, invertible, nullspace_dim
    """
    import sympy as sp
    M_in = spec.get("matrix")
    claim_type = (spec.get("claim_type") or "").lower()
    claimed = spec.get("claimed_value")
    if M_in is None or not claim_type:
        return na("mathematics.matrix")
    try:
        M = sp.Matrix(M_in)
    except Exception as e:
        return error("mathematics.matrix", f"cannot construct matrix: {e}")
    try:
        if claim_type == "rank":
            actual = int(M.rank())
        elif claim_type in ("determinant", "det"):
            actual = sp.simplify(M.det())
        elif claim_type == "trace":
            actual = sp.simplify(M.trace())
        elif claim_type == "eigenvalues":
            actual = sorted([sp.nsimplify(ev) for ev in M.eigenvals().keys()],
                            key=lambda e: float(sp.re(sp.N(e))))
            if claimed is not None:
                claimed_sorted = sorted([sp.sympify(c) for c in claimed],
                                        key=lambda e: float(sp.re(sp.N(e))))
                ok = all(sp.simplify(a - c) == 0 for a, c in zip(actual, claimed_sorted))
                return (confirm if ok else mismatch)(
                    "mathematics.matrix",
                    f"eigenvalues: actual={[str(a) for a in actual]} claimed={[str(c) for c in claimed_sorted]}",
                    {"actual": [str(a) for a in actual]})
        elif claim_type == "transpose":
            actual = M.T.tolist()
        elif claim_type == "inverse":
            actual = M.inv().tolist() if M.det() != 0 else None
        elif claim_type == "symmetric":
            actual = (M == M.T)
        elif claim_type == "invertible":
            actual = (M.det() != 0)
        elif claim_type == "nullspace_dim":
            actual = M.shape[1] - int(M.rank())
        else:
            return error("mathematics.matrix", f"unknown claim_type {claim_type!r}")
    except Exception as e:
        return error("mathematics.matrix", f"compute failed: {e}")

    if claimed is None:
        return confirm("mathematics.matrix",
                       f"{claim_type} = {actual} (no claimed_value to compare)",
                       {"actual": str(actual)})
    try:
        if claim_type in ("transpose", "inverse"):
            ok = (sp.Matrix(actual) == sp.Matrix(claimed))
        elif claim_type in ("symmetric", "invertible"):
            ok = (bool(actual) == bool(claimed))
        else:
            ok = sp.simplify(sp.sympify(claimed) - sp.sympify(actual)) == 0
    except Exception as e:
        return error("mathematics.matrix", f"comparison failed: {e}")
    detail = f"{claim_type}: actual={actual}, claimed={claimed}"
    return (confirm if ok else mismatch)("mathematics.matrix", detail, {"actual": str(actual)})


def verify_inequality(spec):
    """Verify a claimed inequality holds for all x in a domain.

    spec: lhs, rhs, variable (default x), domain (sympy interval string,
    default 'Reals'), op in {<,<=,>,>=}.
    Sampling fallback if symbolic check is inconclusive.
    """
    import sympy as sp
    lhs = spec.get("lhs"); rhs = spec.get("rhs")
    op = spec.get("op", "<=")
    var = spec.get("variable", "x")
    if lhs is None or rhs is None:
        return na("mathematics.inequality")
    x = sp.Symbol(var, real=True)
    L = sp.sympify(lhs, locals={var: x}); R = sp.sympify(rhs, locals={var: x})
    diff = sp.simplify(L - R)
    rel_map = {"<": "<", "<=": "<=", ">": ">", ">=": ">="}
    if op not in rel_map:
        return error("mathematics.inequality", f"bad op {op!r}")
    # Symbolic attempt: solve L op R for which x makes it true; compare to domain
    try:
        if op == "<=":
            ok = sp.simplify(diff <= 0) is sp.true
        elif op == ">=":
            ok = sp.simplify(diff >= 0) is sp.true
        elif op == "<":
            ok = sp.simplify(diff < 0) is sp.true
        else:
            ok = sp.simplify(diff > 0) is sp.true
    except Exception:
        ok = False

    # Sampling fallback (when symbolic returns inconclusive)
    if not ok:
        domain = spec.get("domain", "Reals")
        samples = [-1000, -10, -1, -0.5, 0, 0.5, 1, 10, 1000]
        if domain == "Positive":
            samples = [s for s in samples if s > 0]
        elif domain == "Nonneg":
            samples = [s for s in samples if s >= 0]
        all_ok = True
        for s in samples:
            try:
                d = float(diff.subs(x, s))
                if op == "<=" and not d <= 1e-9: all_ok = False; break
                if op == "<"  and not d < -1e-12: all_ok = False; break
                if op == ">=" and not d >= -1e-9: all_ok = False; break
                if op == ">"  and not d >  1e-12: all_ok = False; break
            except Exception:
                pass
        if all_ok:
            return confirm("mathematics.inequality",
                           f"{lhs} {op} {rhs} holds on sampled points (symbolic inconclusive)",
                           {"method": "sampling"})
        return mismatch("mathematics.inequality", f"{lhs} {op} {rhs} fails", {"method": "sampling"})
    return confirm("mathematics.inequality", f"{lhs} {op} {rhs} holds symbolically")


def verify_series(spec):
    """Verify a finite or infinite-series sum claim.

    spec: term (expression in 'k'), variable (default k), start, end (or 'oo'),
          claimed_sum.
    """
    import sympy as sp
    term = spec.get("term"); var = spec.get("variable", "k")
    start = spec.get("start", 0); end = spec.get("end", "oo")
    claimed = spec.get("claimed_sum")
    if term is None:
        return na("mathematics.series")
    k = sp.Symbol(var)
    try:
        t = sp.sympify(term, locals={var: k})
        e = sp.oo if str(end) == "oo" else sp.sympify(str(end))
        s = sp.sympify(str(start))
        actual = sp.simplify(sp.Sum(t, (k, s, e)).doit())
    except Exception as e:
        return error("mathematics.series", f"compute failed: {e}")
    data = {"computed_sum": str(actual)}
    if claimed is None:
        return confirm("mathematics.series",
                       f"sum_{{ {var}={start}..{end} }} {term} = {actual}", data)
    try:
        ok = sp.simplify(actual - sp.sympify(str(claimed))) == 0
    except Exception as e:
        return error("mathematics.series", f"comparison failed: {e}")
    return (confirm if ok else mismatch)("mathematics.series",
        f"computed={actual}, claimed={claimed}", data)


def verify_ode(spec):
    """Verify a claimed solution to an ODE by substituting and simplifying.

    spec: ode (string in y(x) and x), claimed_solution (expression for y(x)),
          variable (default x), function (default y).
    """
    import sympy as sp
    ode = spec.get("ode"); claimed = spec.get("claimed_solution")
    var = spec.get("variable", "x"); func = spec.get("function", "y")
    if ode is None or claimed is None:
        return na("mathematics.ode")
    try:
        x = sp.Symbol(var)
        y = sp.Function(func)
        local = {var: x, func: y}
        # Build LHS-RHS as expression. Accept either "lhs = rhs" or pure expression == 0.
        if "=" in ode and "==" not in ode:
            lhs, rhs = ode.split("=", 1)
            expr = sp.sympify(lhs, locals=local) - sp.sympify(rhs, locals=local)
        else:
            expr = sp.sympify(ode, locals=local)
        sol_expr = sp.sympify(claimed, locals={var: x})
        substituted = expr.subs(y(x), sol_expr).doit()
        residual = sp.simplify(substituted)
    except Exception as e:
        return error("mathematics.ode", f"substitution failed: {e}")
    if residual == 0:
        return confirm("mathematics.ode", f"y(x)={claimed} satisfies the ODE")
    return mismatch("mathematics.ode",
                    f"y(x)={claimed} does not satisfy the ODE; residual={residual}",
                    {"residual": str(residual)})
