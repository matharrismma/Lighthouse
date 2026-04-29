"""Computer Science verifier.

Checks performed:
  * static_termination: AST scan for obvious non-termination (`while True`
    with no break/return), missing loop variants, infinite recursion
    patterns. Static analysis cannot decide the halting problem in general,
    but it can flag the easy cases.
  * runtime_complexity: time the supplied function at increasing input
    sizes and compare measured slope against claimed O() class
  * functional_correctness: run the function on supplied (input, output)
    pairs and verify each

The runtime checks execute supplied code in a restricted namespace
(no builtins like __import__, open, eval, exec, compile). They are
intended for snippets the user controls; do not run untrusted input.
"""
from __future__ import annotations
import ast
import math
import time
from typing import Any, Callable, Dict, List, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


# ----- Static checks (AST-based) -------------------------------------------

class _TerminationLinter(ast.NodeVisitor):
    """Flags suspicious infinite loops and unguarded recursion."""

    def __init__(self):
        self.warnings: List[str] = []
        self._function_stack: List[str] = []

    def visit_While(self, node):
        # Detect `while True:` or `while 1:` without a reachable break/return
        is_constant_true = (
            (isinstance(node.test, ast.Constant) and bool(node.test.value)) or
            (isinstance(node.test, ast.NameConstant) and bool(node.test.value))
        )
        if is_constant_true:
            has_exit = any(
                isinstance(n, (ast.Break, ast.Return, ast.Raise))
                for n in ast.walk(node)
            )
            if not has_exit:
                self.warnings.append(
                    f"line {node.lineno}: `while True:` with no break/return/raise"
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._function_stack.append(node.name)
        recursive_calls = [
            n for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == node.name
        ]
        if recursive_calls:
            def _contains_recursive_call(n) -> bool:
                if n is None:
                    return False
                return any(
                    isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == node.name
                    for c in ast.walk(n)
                )

            # Collect all potential "leaf" expressions that could be a base case.
            # A leaf is: the value of a Return, or each branch of any IfExp
            # nested inside a Return value. If at least one such leaf does not
            # contain a recursive call, we accept it as a base case.
            def _leaves(expr):
                if expr is None:
                    yield None
                    return
                if isinstance(expr, ast.IfExp):
                    yield from _leaves(expr.body)
                    yield from _leaves(expr.orelse)
                else:
                    yield expr

            base_case_found = False
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return):
                    for leaf in _leaves(stmt.value):
                        if not _contains_recursive_call(leaf):
                            base_case_found = True
                            break
                if base_case_found:
                    break

            if not base_case_found:
                self.warnings.append(
                    f"line {node.lineno}: function `{node.name}` recurses with no base case "
                    f"(every return path contains a recursive call)"
                )
        self.generic_visit(node)
        self._function_stack.pop()


def verify_static_termination(code: str) -> VerifierResult:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return error("cs.static_termination", f"syntax error: {e}")
    linter = _TerminationLinter()
    linter.visit(tree)
    if linter.warnings:
        return mismatch("cs.static_termination",
                        "; ".join(linter.warnings),
                        {"warnings": linter.warnings})
    return confirm("cs.static_termination", "no obvious non-termination patterns")


# ----- Runtime checks ------------------------------------------------------

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "range": range, "reversed": reversed, "round": round, "set": set,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "RuntimeError": RuntimeError, "Exception": Exception,
    "True": True, "False": False, "None": None,
}


def _exec_function(code: str, function_name: str) -> Callable:
    """Execute the snippet in a restricted namespace and return the named function."""
    ns: Dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    # Allow math import explicitly (read-only)
    import math as _m
    ns["math"] = _m
    exec(compile(code, "<verifier>", "exec"), ns)
    fn = ns.get(function_name)
    if not callable(fn):
        raise NameError(f"function {function_name!r} not defined or not callable")
    return fn


def _resolve_call_args(case: Dict[str, Any]):
    """Return (args_tuple, kwargs_dict) from a test case.

    Accepts the canonical ``args`` / ``kwargs`` fields *and* the natural
    alias ``input``:
      - ``input`` as list/tuple -> splat into positional args
      - ``input`` as dict        -> use as keyword args
      - ``input`` as scalar      -> single positional arg
    Explicit ``args`` / ``kwargs`` always win over ``input`` if both present.
    """
    args = case.get("args")
    kwargs = case.get("kwargs")
    if args is None and kwargs is None and "input" in case:
        inp = case["input"]
        if isinstance(inp, (list, tuple)):
            args = list(inp)
            kwargs = {}
        elif isinstance(inp, dict):
            args = []
            kwargs = dict(inp)
        else:
            args = [inp]
            kwargs = {}
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    return tuple(args), dict(kwargs)


def verify_functional_correctness(spec: Dict[str, Any]) -> VerifierResult:
    code = spec.get("code")
    fn_name = spec.get("function_name")
    cases = spec.get("test_cases", [])
    if not code or not fn_name or not cases:
        return na("cs.functional_correctness")
    try:
        fn = _exec_function(code, fn_name)
    except Exception as e:
        return error("cs.functional_correctness", f"execution failure: {e}")
    failures = []
    for i, case in enumerate(cases):
        args, kwargs = _resolve_call_args(case)
        expected = case.get("expected")
        try:
            actual = fn(*args, **kwargs)
        except Exception as e:
            failures.append(f"case {i}: raised {type(e).__name__}: {e}")
            continue
        if actual != expected:
            failures.append(f"case {i}: f({args},{kwargs})={actual}, expected {expected}")
    if failures:
        return mismatch("cs.functional_correctness", "; ".join(failures),
                        {"failures": failures})
    return confirm("cs.functional_correctness", f"{len(cases)} test cases pass")


def verify_runtime_complexity(spec: Dict[str, Any]) -> VerifierResult:
    """Measure runtime at log-spaced input sizes and compare to claimed class.

    Spec:
      code: snippet defining the function
      function_name: name to call
      input_generator: snippet `def gen(n): return ...` returning the function's args (list)
      claimed_class: 'O(1)' | 'O(log n)' | 'O(n)' | 'O(n log n)' | 'O(n**2)' | 'O(n**3)'
      sizes: list of n values (default depends on claimed_class)
      tolerance: log-slope tolerance (default 0.40)
      target_seconds: minimum total measurement time per size (default 0.05)
    """
    code = spec.get("code")
    fn_name = spec.get("function_name")
    gen_code = spec.get("input_generator")
    claimed = (spec.get("claimed_class") or "").replace(" ", "").lower()
    tol = spec.get("tolerance", 0.40)
    target_s = spec.get("target_seconds", 0.05)
    if not code or not fn_name or not gen_code:
        return na("cs.runtime_complexity")

    # Default sizes adapted to claimed class — for fast classes need larger n
    default_sizes = {
        "o(1)": [1000, 10000, 100000, 1000000],
        "o(logn)": [1000, 10000, 100000, 1000000],
        "o(loglogn)": [1000, 10000, 100000, 1000000],
        "o(n)": [1000, 10000, 100000, 1000000],
        "o(nlogn)": [1000, 10000, 100000, 1000000],
        "o(n*logn)": [1000, 10000, 100000, 1000000],
        "o(n**2)": [100, 200, 400, 800, 1600],
        "o(n^2)": [100, 200, 400, 800, 1600],
        "o(n**3)": [20, 40, 80, 160],
        "o(n^3)": [20, 40, 80, 160],
    }
    sizes = spec.get("sizes") or default_sizes.get(claimed, [10, 100, 1000, 10000])

    try:
        fn = _exec_function(code, fn_name)
        gen = _exec_function(gen_code, "gen")
    except Exception as e:
        return error("cs.runtime_complexity", f"setup failure: {e}")

    times = []
    for n in sizes:
        try:
            args = gen(n)
        except Exception as e:
            return error("cs.runtime_complexity", f"input_generator(n={n}) failure: {e}")
        if not isinstance(args, (list, tuple)):
            args = [args]
        # Auto-tune iteration count: start with 1, double until total exceeds target_s
        repeats = 1
        while True:
            t0 = time.perf_counter()
            try:
                for _ in range(repeats):
                    fn(*args)
            except Exception as e:
                return error("cs.runtime_complexity",
                             f"function call at n={n} failed: {e}")
            elapsed = time.perf_counter() - t0
            if elapsed >= target_s or repeats >= 1_000_000:
                break
            # Estimate factor needed
            if elapsed > 0:
                factor = max(2, int(target_s / elapsed) + 1)
            else:
                factor = 10
            repeats *= factor
        per_call = elapsed / repeats
        times.append(max(per_call, 1e-9))

    # Fit log-log slope on the larger half of sizes (where overhead matters less)
    log_n = [math.log(n) for n in sizes]
    log_t = [math.log(t) for t in times]
    # use the upper half but at least 3 points
    cut = max(0, len(sizes) - max(3, len(sizes) // 2))
    xs = log_n[cut:]
    ys = log_t[cut:]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, ys))
    den = sum((xi - mean_x) ** 2 for xi in xs) or 1e-30
    slope = num / den

    expected_slopes = {
        "o(1)": 0.0, "o(logn)": 0.0, "o(loglogn)": 0.0,
        "o(n)": 1.0, "o(nlogn)": 1.0, "o(n*logn)": 1.0,
        "o(n**2)": 2.0, "o(n^2)": 2.0,
        "o(n**3)": 3.0, "o(n^3)": 3.0,
    }
    expected = expected_slopes.get(claimed)
    data = {"sizes": sizes, "times_s": times, "log_log_slope": slope,
            "claimed_class": claimed, "tolerance": tol}
    if expected is None:
        return error("cs.runtime_complexity", f"unrecognized claimed_class {claimed!r}", data)
    if abs(slope - expected) <= tol:
        return confirm(
            "cs.runtime_complexity",
            f"measured log-log slope {slope:.2f}, expected ~{expected:.1f} for {claimed} (tol {tol})",
            data,
        )
    return mismatch(
        "cs.runtime_complexity",
        f"measured log-log slope {slope:.2f}, expected ~{expected:.1f} for {claimed} (tol {tol})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CS_VERIFY") or {}

    if cv.get("code"):
        results.append(verify_static_termination(cv["code"]))
        if cv.get("test_cases") and cv.get("function_name"):
            results.append(verify_functional_correctness(cv))
        if cv.get("input_generator") and cv.get("claimed_class"):
            results.append(verify_runtime_complexity(cv))
        if cv.get("input_generator") and cv.get("claimed_space_class"):
            results.append(verify_space_complexity(cv))
        if cv.get("function_name") and cv.get("test_cases") and cv.get("trials"):
            results.append(verify_determinism(cv))

    if not results:
        results.append(na("computer_science", "no CS_VERIFY artifacts present"))
    return results


# ---------------------------------------------------------------------
# V4: space complexity, determinism
# ---------------------------------------------------------------------

def verify_space_complexity(spec):
    """Estimate peak memory delta at log-spaced input sizes via tracemalloc.

    spec: same shape as verify_runtime_complexity but with claimed_space_class.
    """
    import tracemalloc
    code = spec.get("code"); fn_name = spec.get("function_name")
    gen_code = spec.get("input_generator")
    claimed = (spec.get("claimed_space_class") or "").replace(" ", "").lower()
    tol = spec.get("tolerance", 0.40)
    if not code or not fn_name or not gen_code or not claimed:
        return na("cs.space_complexity")
    default_sizes = {
        "o(1)": [1000, 10000, 100000],
        "o(logn)": [1000, 10000, 100000],
        "o(n)": [1000, 10000, 100000],
        "o(nlogn)": [1000, 10000, 100000],
        "o(n**2)": [100, 200, 400, 800],
        "o(n^2)": [100, 200, 400, 800],
    }
    sizes = spec.get("sizes") or default_sizes.get(claimed, [100, 1000, 10000])
    try:
        fn = _exec_function(code, fn_name)
        gen = _exec_function(gen_code, "gen")
    except Exception as e:
        return error("cs.space_complexity", f"setup failure: {e}")
    peaks = []
    for n in sizes:
        try:
            args = gen(n)
            if not isinstance(args, (list, tuple)):
                args = [args]
        except Exception as e:
            return error("cs.space_complexity", f"input_generator(n={n}) failure: {e}")
        tracemalloc.start()
        try:
            fn(*args)
        except Exception as e:
            tracemalloc.stop()
            return error("cs.space_complexity", f"call at n={n} failed: {e}")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(max(peak, 1))
    # log-log slope of memory vs n
    log_n = [math.log(n) for n in sizes]
    log_p = [math.log(p) for p in peaks]
    cut = max(0, len(sizes) - max(3, len(sizes) // 2))
    xs = log_n[cut:]; ys = log_p[cut:]
    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(xs, ys))
    den = sum((xi - mx) ** 2 for xi in xs) or 1e-30
    slope = num / den
    expected_slopes = {"o(1)": 0.0, "o(logn)": 0.0, "o(n)": 1.0,
                       "o(nlogn)": 1.0, "o(n**2)": 2.0, "o(n^2)": 2.0}
    expected = expected_slopes.get(claimed)
    data = {"sizes": sizes, "peak_bytes": peaks, "log_log_slope": slope,
            "claimed_space_class": claimed, "tolerance": tol}
    if expected is None:
        return error("cs.space_complexity", f"unrecognized claimed_space_class {claimed!r}", data)
    if abs(slope - expected) <= tol:
        return confirm("cs.space_complexity",
                       f"measured slope {slope:.2f} ~ expected {expected:.1f} for {claimed}",
                       data)
    return mismatch("cs.space_complexity",
                    f"measured slope {slope:.2f} != expected {expected:.1f} for {claimed}",
                    data)


def verify_determinism(spec):
    """Run the function multiple times on each test_case and confirm identical output."""
    code = spec.get("code"); fn_name = spec.get("function_name")
    cases = spec.get("test_cases") or []
    trials = max(2, int(spec.get("trials", 3)))
    if not code or not fn_name or not cases:
        return na("cs.determinism")
    try:
        fn = _exec_function(code, fn_name)
    except Exception as e:
        return error("cs.determinism", f"setup failure: {e}")
    nondeterministic_cases = []
    for i, case in enumerate(cases):
        args, kwargs = _resolve_call_args(case)
        try:
            outs = []
            for _ in range(trials):
                outs.append(fn(*args, **kwargs))
        except Exception as e:
            return error("cs.determinism", f"case {i} raised: {e}")
        # Compare every output to the first
        first = outs[0]
        if any(o != first for o in outs[1:]):
            nondeterministic_cases.append({"index": i, "outputs_seen": [str(o) for o in outs]})
    data = {"trials": trials, "n_cases": len(cases),
            "nondeterministic": nondeterministic_cases}
    if nondeterministic_cases:
        return mismatch("cs.determinism",
            f"{len(nondeterministic_cases)}/{len(cases)} cases non-deterministic across {trials} trials",
            data)
    return confirm("cs.determinism",
        f"all {len(cases)} cases produced identical output across {trials} trials",
        data)
