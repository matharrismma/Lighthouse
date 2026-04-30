"""
verifiers/computer_science.py — Static analysis and functional correctness.
"""
from __future__ import annotations
import ast
import time
from typing import Any, Dict, List, Optional
from .base import VerifierResult


# ---------------------------------------------------------------------------
# Static termination check (AST-based)
# ---------------------------------------------------------------------------

class _TerminationVisitor(ast.NodeVisitor):
    """Detect obvious non-termination patterns."""

    def __init__(self, function_name: Optional[str] = None):
        self.function_name = function_name
        self.issues: List[str] = []
        self._in_fn = False
        self._fn_stack = []

    def visit_FunctionDef(self, node):
        self._fn_stack.append(node.name)
        self.generic_visit(node)
        self._fn_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_While(self, node):
        # Detect `while True` with no break
        is_true = (
            (isinstance(node.test, ast.Constant) and node.test.value is True) or
            (isinstance(node.test, ast.NameConstant) and node.test.value is True)
        )
        if is_true:
            has_break = any(isinstance(n, ast.Break)
                            for n in ast.walk(node))
            if not has_break:
                self.issues.append("Unconditional 'while True' with no break detected.")
        self.generic_visit(node)

    def visit_Call(self, node):
        # Detect immediate unconditional self-recursion: f(n) → f(n) or f(...) same level
        fn_name = None
        if isinstance(node.func, ast.Name):
            fn_name = node.func.id
        if fn_name and self._fn_stack and fn_name == self._fn_stack[-1]:
            # Check that this call is NOT inside an if/else guard
            # We do a rough check: if this is a direct statement (not guarded)
            # For simplicity: flag if this is the only statement in the function body
            # The AST visitor will encounter this — we mark it for review
            # We rely on _is_unguarded_recursion check
            pass
        self.generic_visit(node)


def _has_unguarded_recursion(tree: ast.AST, fn_name: str) -> bool:
    """
    Check if function body consists solely of a recursive call with no base case.
    Heuristic: if the only Return or Expr statement is a recursive call, flag it.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            body = node.body
            # If there's an If statement anywhere, assume there's a base case
            has_if = any(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(node))
            if has_if:
                return False
            # Check if every return/expr is a recursive call
            all_recursive = True
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return):
                    # Check if the return value contains a call to fn_name
                    if stmt.value is None:
                        all_recursive = False
                        break
                    calls = [n for n in ast.walk(stmt.value)
                             if isinstance(n, ast.Call) and
                             isinstance(n.func, ast.Name) and n.func.id == fn_name]
                    if not calls:
                        all_recursive = False
                        break
            return all_recursive
    return False


def verify_static_termination(code: str, function_name: Optional[str] = None) -> VerifierResult:
    name = "cs.static_termination"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return VerifierResult(name=name, status="ERROR", detail=f"Syntax error: {e}")

    visitor = _TerminationVisitor(function_name)
    visitor.visit(tree)

    # Detect unguarded recursion
    if function_name:
        if _has_unguarded_recursion(tree, function_name):
            visitor.issues.append(f"Unguarded recursion in '{function_name}': no base case detected.")
    else:
        # Check all functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _has_unguarded_recursion(tree, node.name):
                    visitor.issues.append(f"Unguarded recursion in '{node.name}'.")

    if visitor.issues:
        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Termination issues: {'; '.join(visitor.issues)}",
                              data={"issues": visitor.issues})
    return VerifierResult(name=name, status="CONFIRMED",
                          detail="No obvious non-termination patterns detected.")


# ---------------------------------------------------------------------------
# Functional correctness (sandboxed execution)
# ---------------------------------------------------------------------------

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr,
    "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "frozenset": frozenset,
    "getattr": getattr, "hasattr": hasattr, "hash": hash, "hex": hex,
    "id": id, "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "oct": oct, "ord": ord, "pow": pow,
    "print": print, "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "setattr": setattr, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "vars": vars, "zip": zip, "None": None, "True": True, "False": False,
}


def _exec_code(code: str, fn_name: str, test_cases: List[Dict]) -> VerifierResult:
    name = "cs.functional_correctness"
    namespace = {"__builtins__": _SAFE_BUILTINS}
    try:
        exec(compile(code, "<string>", "exec"), namespace)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR",
                              detail=f"Code execution error: {e}")

    fn = namespace.get(fn_name)
    if fn is None:
        return VerifierResult(name=name, status="ERROR",
                              detail=f"Function '{fn_name}' not found after exec.")

    failures = []
    for i, tc in enumerate(test_cases):
        args = tc.get("args", [])
        kwargs = tc.get("kwargs", {})
        expected = tc.get("expected")
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            failures.append(f"Case {i}: raised {type(e).__name__}: {e}")
            continue
        if result != expected:
            failures.append(f"Case {i}: f({args}) = {result!r}, expected {expected!r}")

    if not failures:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"All {len(test_cases)} test cases passed.",
                              data={"passed": len(test_cases)})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"{len(failures)}/{len(test_cases)} cases failed.",
                          data={"failures": failures})


def verify_functional_correctness(spec: Dict[str, Any]) -> VerifierResult:
    return _exec_code(
        spec["code"],
        spec["function_name"],
        spec.get("test_cases", [])
    )


# ---------------------------------------------------------------------------
# Runtime complexity estimation
# ---------------------------------------------------------------------------

_COMPLEXITY_CLASSES = {
    "O(1)":         lambda n: 1.0,
    "O(log n)":     lambda n: float(__import__("math").log2(max(n, 2))),
    "O(n)":         lambda n: float(n),
    "O(n log n)":   lambda n: n * float(__import__("math").log2(max(n, 2))),
    "O(n**2)":      lambda n: float(n ** 2),
    "O(n^2)":       lambda n: float(n ** 2),
    "O(n**3)":      lambda n: float(n ** 3),
    "O(2**n)":      lambda n: float(2 ** min(n, 30)),
}


def verify_runtime_complexity(spec: Dict[str, Any]) -> VerifierResult:
    name = "cs.runtime_complexity"
    try:
        code = spec["code"]
        fn_name = spec["function_name"]
        gen_code = spec["input_generator"]
        claimed_class = spec.get("claimed_class", "")
        sizes = spec.get("sizes", [10, 20, 40, 80])

        # Build generator
        gen_ns = {"__builtins__": _SAFE_BUILTINS}
        exec(compile(gen_code, "<string>", "exec"), gen_ns)
        gen_fn = gen_ns.get("gen")
        if gen_fn is None:
            return VerifierResult(name=name, status="ERROR",
                                  detail="No 'gen' function found in input_generator code.")

        # Build function
        fn_ns = {"__builtins__": _SAFE_BUILTINS}
        exec(compile(code, "<string>", "exec"), fn_ns)
        fn = fn_ns.get(fn_name)
        if fn is None:
            return VerifierResult(name=name, status="ERROR",
                                  detail=f"Function '{fn_name}' not found.")

        # Time function at each size
        runtimes = []
        for n in sizes:
            args = gen_fn(n)
            reps = max(1, min(100, 200 // max(n, 1)))
            start = time.perf_counter()
            for _ in range(reps):
                fn(*args)
            elapsed = (time.perf_counter() - start) / reps
            runtimes.append(elapsed)

        # Fit each complexity class and pick best
        import numpy as np

        x = np.array(sizes, dtype=float)
        y = np.array(runtimes, dtype=float)
        if y.max() == 0:
            y = y + 1e-12  # avoid zeros

        best_class = None
        best_r2 = -float("inf")
        for cls_name, cls_fn in _COMPLEXITY_CLASSES.items():
            model_y = np.array([cls_fn(n) for n in sizes], dtype=float)
            if model_y.max() == 0:
                continue
            model_y = model_y / model_y.max() * y.max()
            # R² of log-linear fit
            log_model = np.log(model_y + 1e-30)
            log_y = np.log(y + 1e-30)
            ss_res = np.sum((log_y - log_model) ** 2)
            ss_tot = np.sum((log_y - log_y.mean()) ** 2)
            r2 = 1 - ss_res / (ss_tot + 1e-30)
            if r2 > best_r2:
                best_r2 = r2
                best_class = cls_name

        data = {"claimed_class": claimed_class, "computed": best_class,
                "r2": float(best_r2), "sizes": sizes, "runtimes": runtimes}

        # Normalise for comparison
        def _norm(s):
            return s.replace(" ", "").replace("^", "**").upper()

        if _norm(best_class or "") == _norm(claimed_class):
            return VerifierResult(name=name, status="CONFIRMED",
                                  detail=f"Runtime grows as {best_class} (R²={best_r2:.3f}), matches claim.",
                                  data=data)

        # Allow some tolerance — if R² for claimed class is within 0.05 of best
        if claimed_class in _COMPLEXITY_CLASSES:
            cls_fn = _COMPLEXITY_CLASSES[claimed_class]
            model_y = np.array([cls_fn(n) for n in sizes], dtype=float)
            if model_y.max() > 0:
                model_y = model_y / model_y.max() * y.max()
                log_model = np.log(model_y + 1e-30)
                log_y = np.log(y + 1e-30)
                ss_res = np.sum((log_y - log_model) ** 2)
                ss_tot = np.sum((log_y - log_y.mean()) ** 2)
                claimed_r2 = float(1 - ss_res / (ss_tot + 1e-30))
                data["claimed_r2"] = claimed_r2
                if claimed_r2 >= best_r2 - 0.05:
                    return VerifierResult(name=name, status="CONFIRMED",
                                          detail=f"Claimed {claimed_class} fits with R²={claimed_r2:.3f}.",
                                          data=data)

        return VerifierResult(name=name, status="MISMATCH",
                              detail=f"Observed growth {best_class}, claimed {claimed_class}.",
                              data=data)

    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=str(e))


def run(packet: dict) -> list:
    results = []
    verify = packet.get("CS_VERIFY") or {}
    if not verify:
        return results
    code = verify.get("code", "")
    fn_name = verify.get("function_name")
    if code:
        results.append(verify_static_termination(code, fn_name))
    if code and fn_name and "test_cases" in verify:
        results.append(verify_functional_correctness(verify))
    if code and fn_name and "input_generator" in verify and "claimed_class" in verify:
        results.append(verify_runtime_complexity(verify))
    return results
