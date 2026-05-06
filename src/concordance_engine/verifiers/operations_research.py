"""Operations Research verifier (grid axes: reasoning/conservation-balance/time-sequence).

Deterministic checks on LP feasibility, critical-path scheduling,
0-1 knapsack optimality, and assignment cost summation. All algorithms
are textbook / public-domain.

Checks:
  * operations_research.lp_feasibility   — does a point satisfy all linear constraints?
  * operations_research.critical_path    — minimum project makespan via CPM
  * operations_research.knapsack_01      — optimal 0-1 knapsack value via DP
  * operations_research.assignment_cost  — total cost of a worker→job assignment

OR_VERIFY packet shape (any subset):
    {
      "variable_values": {"x": 2.0, "y": 3.0},
      "constraints": [
        {"lhs_coeffs": {"x": 1.0, "y": 1.0}, "operator": "<=", "rhs": 10.0},
        {"lhs_coeffs": {"x": 1.0}, "operator": ">=", "rhs": 0.0}
      ],
      "claimed_feasible": true,

      "tasks": [
        {"id": "A", "duration": 3, "depends_on": []},
        {"id": "B", "duration": 5, "depends_on": ["A"]},
        {"id": "C", "duration": 2, "depends_on": ["A"]},
        {"id": "D", "duration": 4, "depends_on": ["B", "C"]}
      ],
      "claimed_makespan": 12,

      "items": [
        {"weight": 2, "value": 3},
        {"weight": 3, "value": 4},
        {"weight": 4, "value": 5}
      ],
      "capacity": 5,
      "claimed_optimal_value": 7,

      "assignment": [[0, 1], [1, 0]],
      "cost_matrix": [[9, 2], [6, 4]],
      "claimed_total_cost": 8,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


# ---------------------------------------------------------------------------
# LP feasibility
# ---------------------------------------------------------------------------

def verify_lp_feasibility(spec: Dict[str, Any]) -> VerifierResult:
    """Check whether variable_values satisfies all linear constraints."""
    name = "operations_research.lp_feasibility"
    var_vals  = spec.get("variable_values")
    constrs   = spec.get("constraints")
    claimed   = spec.get("claimed_feasible")
    if var_vals is None or constrs is None or claimed is None:
        return na(name)

    if not isinstance(var_vals, dict):
        return error(name, "variable_values must be a dict mapping variable name to float")
    if not isinstance(constrs, list):
        return error(name, "constraints must be a list of constraint dicts")

    eq_tol = 1e-6  # tolerance for equality constraints
    violated: List[Dict[str, Any]] = []

    try:
        values = {k: float(v) for k, v in var_vals.items()}
    except (TypeError, ValueError) as exc:
        return error(name, f"variable_values contains non-numeric entry: {exc}")

    for i, c in enumerate(constrs):
        lhs_coeffs = c.get("lhs_coeffs", {})
        op         = c.get("operator", "<=")
        rhs        = c.get("rhs", 0.0)
        try:
            lhs = sum(float(lhs_coeffs.get(var, 0.0)) * values.get(var, 0.0)
                      for var in lhs_coeffs)
            rhs_f = float(rhs)
        except (TypeError, ValueError) as exc:
            return error(name, f"constraint {i} contains non-numeric value: {exc}")

        if op == "<=":
            satisfied = lhs <= rhs_f + eq_tol
        elif op == ">=":
            satisfied = lhs >= rhs_f - eq_tol
        elif op == "==":
            satisfied = abs(lhs - rhs_f) <= eq_tol
        else:
            return error(name, f"constraint {i} has unknown operator {op!r}; use <=, >=, or ==")

        if not satisfied:
            violated.append({"constraint_index": i, "lhs": lhs, "operator": op, "rhs": rhs_f})

    actual_feasible = len(violated) == 0
    claimed_b = bool(claimed)

    data = {
        "variable_values":    var_vals,
        "num_constraints":    len(constrs),
        "violated_constraints": violated,
        "actual_feasible":    actual_feasible,
        "claimed_feasible":   claimed_b,
        "rule": "Point is feasible iff every constraint is satisfied within tolerance 1e-6",
    }
    if actual_feasible == claimed_b:
        return confirm(name, f"feasible={actual_feasible} (matches claim)", data)
    detail = f"feasible={actual_feasible}, claimed {claimed_b}"
    if violated:
        detail += f"; {len(violated)} violated constraint(s)"
    return mismatch(name, detail, data)


# ---------------------------------------------------------------------------
# Critical path method (CPM)
# ---------------------------------------------------------------------------

def _topological_sort(tasks: List[Dict[str, Any]]) -> Optional[List[str]]:
    """Kahn's algorithm; returns ordered list of task ids or None if cycle."""
    in_degree: Dict[str, int] = {}
    successors: Dict[str, List[str]] = {}

    for t in tasks:
        tid = t["id"]
        in_degree.setdefault(tid, 0)
        successors.setdefault(tid, [])
        for dep in (t.get("depends_on") or []):
            successors.setdefault(dep, [])
            in_degree[tid] = in_degree.get(tid, 0) + 1

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    order: List[str] = []
    while queue:
        tid = queue.pop(0)
        order.append(tid)
        for succ in successors.get(tid, []):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    if len(order) != len(in_degree):
        return None  # cycle detected
    return order


def verify_critical_path(spec: Dict[str, Any]) -> VerifierResult:
    """Compute minimum project makespan via CPM topological propagation."""
    name = "operations_research.critical_path"
    tasks   = spec.get("tasks")
    claimed = spec.get("claimed_makespan")
    if tasks is None or claimed is None:
        return na(name)

    if not isinstance(tasks, list) or len(tasks) == 0:
        return error(name, "tasks must be a non-empty list")

    # Validate and index tasks.
    task_index: Dict[str, Dict[str, Any]] = {}
    for t in tasks:
        tid = t.get("id")
        dur = t.get("duration")
        if tid is None or dur is None:
            return error(name, f"each task must have 'id' and 'duration'; got {t!r}")
        try:
            task_index[str(tid)] = {"id": str(tid), "duration": float(dur),
                                    "depends_on": [str(d) for d in (t.get("depends_on") or [])]}
        except (TypeError, ValueError) as exc:
            return error(name, f"task {tid!r} duration is non-numeric: {exc}")

    order = _topological_sort(list(task_index.values()))
    if order is None:
        return error(name, "task dependency graph contains a cycle")

    # Earliest-finish propagation.
    earliest_finish: Dict[str, float] = {}
    for tid in order:
        t = task_index[tid]
        deps = t["depends_on"]
        start = max((earliest_finish.get(d, 0.0) for d in deps), default=0.0)
        earliest_finish[tid] = start + t["duration"]

    actual_makespan = max(earliest_finish.values())
    tol = float(spec.get("tolerance_relative", 1e-3)) * max(1.0, abs(actual_makespan))

    data = {
        "tasks":            tasks,
        "topological_order": order,
        "earliest_finish":  earliest_finish,
        "actual_makespan":  actual_makespan,
        "claimed_makespan": claimed,
        "rule": "Makespan = max earliest-finish across all tasks (CPM)",
    }
    try:
        claimed_f = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_makespan must be numeric, got {claimed!r}")

    if abs(actual_makespan - claimed_f) <= tol:
        return confirm(name, f"makespan={actual_makespan} (matches claim)", data)
    return mismatch(name, f"makespan={actual_makespan}, claimed {claimed_f}", data)


# ---------------------------------------------------------------------------
# 0-1 Knapsack (dynamic programming, n ≤ 20)
# ---------------------------------------------------------------------------

def verify_knapsack_01(spec: Dict[str, Any]) -> VerifierResult:
    """Compute optimal 0-1 knapsack value via dynamic programming."""
    name = "operations_research.knapsack_01"
    items    = spec.get("items")
    capacity = spec.get("capacity")
    claimed  = spec.get("claimed_optimal_value")
    if items is None or capacity is None or claimed is None:
        return na(name)

    if not isinstance(items, list):
        return error(name, "items must be a list of dicts with 'weight' and 'value'")

    n = len(items)
    if n > 20:
        return na(name, f"knapsack DP limited to n≤20 items; got {n}")

    try:
        weights = [float(it["weight"]) for it in items]
        values  = [float(it["value"])  for it in items]
        cap     = float(capacity)
    except (KeyError, TypeError, ValueError) as exc:
        return error(name, f"items, capacity must be numeric: {exc}")

    # Integer-scaled DP (handle float weights by scaling if needed).
    # If all weights are integers, use integer DP; otherwise scale.
    if all(w == int(w) for w in weights) and cap == int(cap):
        cap_i = int(cap)
        w_i   = [int(w) for w in weights]
        # Standard 0-1 knapsack DP.
        dp = [0.0] * (cap_i + 1)
        for j in range(n):
            for c in range(cap_i, w_i[j] - 1, -1):
                dp[c] = max(dp[c], dp[c - w_i[j]] + values[j])
        actual_val = dp[cap_i]
    else:
        # Float weights: brute-force over 2^n subsets (n≤20 → ≤1M iterations).
        best = 0.0
        for mask in range(1 << n):
            total_w = 0.0
            total_v = 0.0
            for bit in range(n):
                if mask & (1 << bit):
                    total_w += weights[bit]
                    total_v += values[bit]
            if total_w <= cap + 1e-9:
                best = max(best, total_v)
        actual_val = best

    tol = float(spec.get("tolerance_relative", 1e-3)) * max(1.0, abs(actual_val))

    data = {
        "items":                items,
        "capacity":             capacity,
        "actual_optimal_value": actual_val,
        "claimed_optimal_value": claimed,
        "rule": "0-1 knapsack: choose subset of items maximising total value subject to weight ≤ capacity",
    }
    try:
        claimed_f = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_optimal_value must be numeric, got {claimed!r}")

    if abs(actual_val - claimed_f) <= tol:
        return confirm(name, f"optimal_value={actual_val} (matches claim)", data)
    return mismatch(name, f"optimal_value={actual_val}, claimed {claimed_f}", data)


# ---------------------------------------------------------------------------
# Assignment cost
# ---------------------------------------------------------------------------

def verify_assignment_cost(spec: Dict[str, Any]) -> VerifierResult:
    """Compute total cost of a worker→job assignment from a cost matrix."""
    name = "operations_research.assignment_cost"
    assignment   = spec.get("assignment")
    cost_matrix  = spec.get("cost_matrix")
    claimed      = spec.get("claimed_total_cost")
    if assignment is None or cost_matrix is None or claimed is None:
        return na(name)

    if not isinstance(assignment, list):
        return error(name, "assignment must be a list of [i, j] pairs")
    if not isinstance(cost_matrix, list):
        return error(name, "cost_matrix must be a list of lists (2D matrix)")

    try:
        total = 0.0
        pairs_used: List[Dict[str, Any]] = []
        for pair in assignment:
            i, j = int(pair[0]), int(pair[1])
            cost = float(cost_matrix[i][j])
            total += cost
            pairs_used.append({"i": i, "j": j, "cost": cost})
        claimed_f = float(claimed)
    except (IndexError, TypeError, ValueError) as exc:
        return error(name, f"invalid assignment or cost_matrix entry: {exc}")

    tol = float(spec.get("tolerance_relative", 1e-3)) * max(1.0, abs(total))

    data = {
        "assignment":        assignment,
        "pairs_with_costs":  pairs_used,
        "actual_total_cost": total,
        "claimed_total_cost": claimed_f,
        "rule": "total_cost = Σ cost_matrix[i][j] for each [i,j] in assignment",
    }
    if abs(total - claimed_f) <= tol:
        return confirm(name, f"total_cost={total} (matches claim)", data)
    return mismatch(name, f"total_cost={total}, claimed {claimed_f}", data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch all applicable OR checks for the OR_VERIFY block."""
    results: List[VerifierResult] = []
    ov = packet.get("OR_VERIFY") or {}

    if "variable_values" in ov and "constraints" in ov and "claimed_feasible" in ov:
        results.append(verify_lp_feasibility(ov))

    if "tasks" in ov and "claimed_makespan" in ov:
        results.append(verify_critical_path(ov))

    if "items" in ov and "capacity" in ov and "claimed_optimal_value" in ov:
        results.append(verify_knapsack_01(ov))

    if "assignment" in ov and "cost_matrix" in ov and "claimed_total_cost" in ov:
        results.append(verify_assignment_cost(ov))

    if not results:
        results.append(na("operations_research", "no OR_VERIFY artifacts present"))
    return results
