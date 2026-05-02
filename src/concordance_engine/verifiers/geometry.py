"""Geometry verifier (formal-reasoning ↔ physical-substance grid axis).

Triangle inequality, Pythagorean theorem, polygon angle sum, circle area
and circumference. Pure stdlib math; classical Euclidean public-domain
formulas.

Checks:
  * geometry.triangle_inequality        — three sides form valid triangle
  * geometry.pythagorean                 — right-triangle a² + b² = c²
  * geometry.polygon_interior_angle_sum  — (n-2)·180° for n-gon
  * geometry.circle_properties           — area = πr², circumference = 2πr

GEOM_VERIFY shape (any subset):
    {
      "tri_a": 3, "tri_b": 4, "tri_c": 5, "claimed_valid_triangle": true,

      "pyth_a": 3, "pyth_b": 4, "pyth_c": 5, "claimed_right_triangle": true,

      "polygon_n": 6, "claimed_interior_angle_sum_deg": 720,

      "circle_radius": 5.0,
      "claimed_circle_area": 78.5398,
      "claimed_circle_circumference": 31.4159,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_triangle_inequality(spec: Dict[str, Any]) -> VerifierResult:
    name = "geometry.triangle_inequality"
    a = spec.get("tri_a"); b = spec.get("tri_b"); c = spec.get("tri_c")
    claimed = spec.get("claimed_valid_triangle")
    if a is None or b is None or c is None or claimed is None:
        return na(name)
    try:
        af, bf, cf = float(a), float(b), float(c)
    except (TypeError, ValueError):
        return error(name, "side lengths must be numeric")
    if af <= 0 or bf <= 0 or cf <= 0:
        actual = False
    else:
        actual = (af + bf > cf) and (af + cf > bf) and (bf + cf > af)
    data = {"a": af, "b": bf, "c": cf, "actual_valid": actual,
            "claimed_valid": bool(claimed),
            "rule": "triangle iff each pair of sides sums > the third (and all > 0)"}
    if actual == bool(claimed):
        return confirm(name,
                       f"({af},{bf},{cf}) valid={actual} (matches claim)", data)
    return mismatch(name,
                    f"({af},{bf},{cf}) valid={actual}, claimed {bool(claimed)}",
                    data)


def verify_pythagorean(spec: Dict[str, Any]) -> VerifierResult:
    name = "geometry.pythagorean"
    a = spec.get("pyth_a"); b = spec.get("pyth_b"); c = spec.get("pyth_c")
    claimed = spec.get("claimed_right_triangle")
    if a is None or b is None or c is None or claimed is None:
        return na(name)
    try:
        af, bf, cf = float(a), float(b), float(c)
    except (TypeError, ValueError):
        return error(name, "sides must be numeric")
    if af <= 0 or bf <= 0 or cf <= 0:
        return error(name, "sides must be positive")
    # c is hypotenuse — must be the largest.
    sides_squared_sum = af * af + bf * bf
    c_squared = cf * cf
    rel_tol = float(spec.get("tolerance_relative", 1e-6))
    diff = abs(sides_squared_sum - c_squared)
    threshold = max(1e-9, rel_tol * c_squared)
    actual = (diff <= threshold) and (cf >= af and cf >= bf)
    data = {"a": af, "b": bf, "c": cf,
            "a_sq_plus_b_sq": sides_squared_sum,
            "c_sq": c_squared, "diff": diff,
            "actual_right_triangle": actual,
            "claimed_right_triangle": bool(claimed),
            "rule": "a² + b² = c² with c the hypotenuse"}
    if actual == bool(claimed):
        return confirm(name,
                       f"({af},{bf},{cf}) right-triangle={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"({af},{bf},{cf}) right-triangle={actual}, claimed {bool(claimed)}",
                    data)


def verify_polygon_angle_sum(spec: Dict[str, Any]) -> VerifierResult:
    name = "geometry.polygon_interior_angle_sum"
    n = spec.get("polygon_n")
    claimed = spec.get("claimed_interior_angle_sum_deg")
    if n is None or claimed is None:
        return na(name)
    try:
        nf = int(n)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "polygon_n must be int, claimed sum numeric")
    if nf < 3:
        return error(name, f"polygon must have at least 3 sides, got {nf}")
    actual = (nf - 2) * 180.0
    rel_tol = float(spec.get("tolerance_relative", 1e-6))
    diff = abs(actual - c)
    threshold = max(1e-6, rel_tol * actual)
    data = {"n": nf, "actual_sum_deg": actual, "claimed_sum_deg": c,
            "diff_deg": diff, "rule": "(n-2)·180°"}
    if diff <= threshold:
        return confirm(name,
                       f"{nf}-gon interior angle sum = {actual}° (matches claim)",
                       data)
    return mismatch(name,
                    f"{nf}-gon interior sum = {actual}°, claimed {c}",
                    data)


def verify_circle_properties(spec: Dict[str, Any]) -> VerifierResult:
    """Verify both area = πr² and circumference = 2πr if claimed."""
    name = "geometry.circle_properties"
    r = spec.get("circle_radius")
    a_claim = spec.get("claimed_circle_area")
    c_claim = spec.get("claimed_circle_circumference")
    if r is None or (a_claim is None and c_claim is None):
        return na(name)
    try:
        rf = float(r)
    except (TypeError, ValueError):
        return error(name, "radius must be numeric")
    if rf < 0:
        return error(name, "radius must be non-negative")
    rel_tol = float(spec.get("tolerance_relative", 1e-4))
    actual_area = math.pi * rf * rf
    actual_circ = 2.0 * math.pi * rf
    data: Dict[str, Any] = {
        "radius": rf,
        "actual_area": actual_area,
        "actual_circumference": actual_circ,
        "rule": "area = πr², circumference = 2πr",
    }
    mismatches: List[str] = []
    if a_claim is not None:
        try:
            ac = float(a_claim)
            data["claimed_area"] = ac
            diff = abs(actual_area - ac)
            threshold = max(1e-6, rel_tol * actual_area) if actual_area > 0 else 1e-6
            data["area_diff"] = diff
            if diff > threshold:
                mismatches.append(f"area: actual {actual_area:.6f}, claimed {ac}")
        except (TypeError, ValueError):
            return error(name, "claimed_circle_area must be numeric")
    if c_claim is not None:
        try:
            cc = float(c_claim)
            data["claimed_circumference"] = cc
            diff = abs(actual_circ - cc)
            threshold = max(1e-6, rel_tol * actual_circ) if actual_circ > 0 else 1e-6
            data["circumference_diff"] = diff
            if diff > threshold:
                mismatches.append(f"circumference: actual {actual_circ:.6f}, claimed {cc}")
        except (TypeError, ValueError):
            return error(name, "claimed_circle_circumference must be numeric")
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"r={rf} area={actual_area:.4f} circ={actual_circ:.4f} (matches claims)", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    gv = packet.get("GEOM_VERIFY") or {}
    if all(k in gv for k in ("tri_a", "tri_b", "tri_c", "claimed_valid_triangle")):
        results.append(verify_triangle_inequality(gv))
    if all(k in gv for k in ("pyth_a", "pyth_b", "pyth_c", "claimed_right_triangle")):
        results.append(verify_pythagorean(gv))
    if "polygon_n" in gv and "claimed_interior_angle_sum_deg" in gv:
        results.append(verify_polygon_angle_sum(gv))
    if "circle_radius" in gv and (
        "claimed_circle_area" in gv or "claimed_circle_circumference" in gv
    ):
        results.append(verify_circle_properties(gv))
    if not results:
        results.append(na("geometry", "no GEOM_VERIFY artifacts present"))
    return results
