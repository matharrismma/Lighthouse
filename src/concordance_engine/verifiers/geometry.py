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


def verify_rectangle_properties(spec: Dict[str, Any]) -> VerifierResult:
    """A = l × w ;  P = 2(l + w).  Square is a special case (l = w)."""
    name = "geometry.rectangle"
    l = spec.get("rect_length") or spec.get("rect_l")
    w = spec.get("rect_width") or spec.get("rect_w")
    if l is None or w is None:
        return na(name)
    try:
        lf, wf = float(l), float(w)
    except (TypeError, ValueError):
        return error(name, "rect_length and rect_width must be numeric")
    if lf < 0 or wf < 0:
        return error(name, f"rectangle dimensions must be non-negative; got l={lf}, w={wf}")
    actual_area = lf * wf
    actual_perim = 2.0 * (lf + wf)
    rel_tol = float(spec.get("rel_tol") or 1e-4)
    mismatches: List[str] = []
    data: Dict[str, Any] = {
        "l": lf, "w": wf,
        "actual_area": actual_area, "actual_perimeter": actual_perim,
        "rule": "A = l × w ;  P = 2(l + w)",
    }
    ca = spec.get("claimed_rect_area")
    if ca is not None:
        try:
            caf = float(ca)
            data["claimed_rect_area"] = caf
            threshold = max(1e-6, rel_tol * actual_area) if actual_area > 0 else 1e-6
            diff = abs(actual_area - caf)
            data["area_diff"] = diff
            if diff > threshold:
                mismatches.append(f"area: actual {actual_area:.6f}, claimed {caf}")
        except (TypeError, ValueError):
            return error(name, "claimed_rect_area must be numeric")
    cp = spec.get("claimed_rect_perimeter")
    if cp is not None:
        try:
            cpf = float(cp)
            data["claimed_rect_perimeter"] = cpf
            threshold = max(1e-6, rel_tol * actual_perim) if actual_perim > 0 else 1e-6
            diff = abs(actual_perim - cpf)
            data["perimeter_diff"] = diff
            if diff > threshold:
                mismatches.append(f"perimeter: actual {actual_perim:.6f}, claimed {cpf}")
        except (TypeError, ValueError):
            return error(name, "claimed_rect_perimeter must be numeric")
    # Did the caller actually claim anything?
    if ca is None and cp is None:
        return na(name)
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"l={lf} w={wf} area={actual_area:.4f} perim={actual_perim:.4f} (matches claims)", data)


def verify_sphere_properties(spec: Dict[str, Any]) -> VerifierResult:
    """V = (4/3)πr³ ;  A = 4πr²."""
    import math
    name = "geometry.sphere"
    r = spec.get("sphere_radius")
    if r is None:
        return na(name)
    try:
        rf = float(r)
    except (TypeError, ValueError):
        return error(name, "sphere_radius must be numeric")
    if rf < 0:
        return error(name, f"sphere_radius must be non-negative; got {rf}")
    actual_vol = (4.0 / 3.0) * math.pi * rf**3
    actual_area = 4.0 * math.pi * rf**2
    rel_tol = float(spec.get("rel_tol") or 1e-4)
    mismatches: List[str] = []
    data: Dict[str, Any] = {
        "r": rf,
        "actual_volume": actual_vol, "actual_surface_area": actual_area,
        "rule": "V = (4/3)πr³ ;  A = 4πr²",
    }
    cv = spec.get("claimed_sphere_volume")
    if cv is not None:
        try:
            cvf = float(cv)
            data["claimed_sphere_volume"] = cvf
            threshold = max(1e-6, rel_tol * actual_vol) if actual_vol > 0 else 1e-6
            diff = abs(actual_vol - cvf)
            data["volume_diff"] = diff
            if diff > threshold:
                mismatches.append(f"volume: actual {actual_vol:.6f}, claimed {cvf}")
        except (TypeError, ValueError):
            return error(name, "claimed_sphere_volume must be numeric")
    ca = spec.get("claimed_sphere_surface_area")
    if ca is not None:
        try:
            caf = float(ca)
            data["claimed_sphere_surface_area"] = caf
            threshold = max(1e-6, rel_tol * actual_area) if actual_area > 0 else 1e-6
            diff = abs(actual_area - caf)
            data["area_diff"] = diff
            if diff > threshold:
                mismatches.append(f"surface area: actual {actual_area:.6f}, claimed {caf}")
        except (TypeError, ValueError):
            return error(name, "claimed_sphere_surface_area must be numeric")
    if cv is None and ca is None:
        return na(name)
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"r={rf} V={actual_vol:.4f} A={actual_area:.4f} (matches claims)", data)


def verify_cylinder_properties(spec: Dict[str, Any]) -> VerifierResult:
    """V = πr²h ;  A_lateral = 2πrh ;  A_total = 2πr² + 2πrh."""
    import math
    name = "geometry.cylinder"
    r = spec.get("cyl_radius")
    h = spec.get("cyl_height")
    if r is None or h is None:
        return na(name)
    try:
        rf, hf = float(r), float(h)
    except (TypeError, ValueError):
        return error(name, "cyl_radius and cyl_height must be numeric")
    if rf < 0 or hf < 0:
        return error(name, f"cylinder dimensions must be non-negative; got r={rf}, h={hf}")
    actual_vol = math.pi * rf**2 * hf
    actual_lat = 2.0 * math.pi * rf * hf
    actual_tot = 2.0 * math.pi * rf**2 + actual_lat
    rel_tol = float(spec.get("rel_tol") or 1e-4)
    mismatches: List[str] = []
    data: Dict[str, Any] = {
        "r": rf, "h": hf,
        "actual_volume": actual_vol,
        "actual_lateral_area": actual_lat,
        "actual_total_area": actual_tot,
        "rule": "V = πr²h ; A_lateral = 2πrh ; A_total = 2πr² + 2πrh",
    }
    cv = spec.get("claimed_cyl_volume")
    if cv is not None:
        try:
            cvf = float(cv)
            data["claimed_cyl_volume"] = cvf
            threshold = max(1e-6, rel_tol * actual_vol) if actual_vol > 0 else 1e-6
            diff = abs(actual_vol - cvf)
            data["volume_diff"] = diff
            if diff > threshold:
                mismatches.append(f"volume: actual {actual_vol:.6f}, claimed {cvf}")
        except (TypeError, ValueError):
            return error(name, "claimed_cyl_volume must be numeric")
    if cv is None:
        return na(name)
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"r={rf} h={hf} V={actual_vol:.4f} (matches claims)", data)


def verify_cube_properties(spec: Dict[str, Any]) -> VerifierResult:
    """V = s³ ; A = 6s²."""
    name = "geometry.cube"
    s = spec.get("cube_side")
    if s is None:
        return na(name)
    try:
        sf = float(s)
    except (TypeError, ValueError):
        return error(name, "cube_side must be numeric")
    if sf < 0:
        return error(name, f"cube_side must be non-negative; got {sf}")
    actual_vol = sf**3
    actual_area = 6.0 * sf**2
    rel_tol = float(spec.get("rel_tol") or 1e-4)
    mismatches: List[str] = []
    data: Dict[str, Any] = {
        "s": sf,
        "actual_volume": actual_vol, "actual_surface_area": actual_area,
        "rule": "V = s³ ; A = 6s²",
    }
    cv = spec.get("claimed_cube_volume")
    if cv is not None:
        try:
            cvf = float(cv)
            data["claimed_cube_volume"] = cvf
            threshold = max(1e-6, rel_tol * actual_vol) if actual_vol > 0 else 1e-6
            diff = abs(actual_vol - cvf)
            data["volume_diff"] = diff
            if diff > threshold:
                mismatches.append(f"volume: actual {actual_vol:.6f}, claimed {cvf}")
        except (TypeError, ValueError):
            return error(name, "claimed_cube_volume must be numeric")
    ca = spec.get("claimed_cube_surface_area")
    if ca is not None:
        try:
            caf = float(ca)
            data["claimed_cube_surface_area"] = caf
            threshold = max(1e-6, rel_tol * actual_area) if actual_area > 0 else 1e-6
            diff = abs(actual_area - caf)
            data["area_diff"] = diff
            if diff > threshold:
                mismatches.append(f"surface area: actual {actual_area:.6f}, claimed {caf}")
        except (TypeError, ValueError):
            return error(name, "claimed_cube_surface_area must be numeric")
    if cv is None and ca is None:
        return na(name)
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"s={sf} V={actual_vol:.4f} A={actual_area:.4f} (matches claims)", data)


# Ideal central (bond) angles of regular spatial arrangements — pure geometry,
# independent of any chemistry. The tetrahedral angle is arccos(-1/3) = 109.47°.
_COORD_ANGLES = {
    "linear": 180.0,
    "trigonal_planar": 120.0,
    "tetrahedral": math.degrees(math.acos(-1.0 / 3.0)),
    "octahedral": 90.0,
    "square_planar": 90.0,
}


def verify_coordination_geometry(spec: Dict[str, Any]) -> VerifierResult:
    """Central (bond) angle of a regular coordination geometry — e.g. the
    tetrahedral angle arccos(-1/3) = 109.47 deg. Pure geometry; co-confirms
    molecular_geometry.vsepr on the symmetry axis."""
    name = "geometry.coordination_angle"
    coord = spec.get("coordination")
    claimed = spec.get("claimed_central_angle_deg")
    if coord is None or claimed is None:
        return na(name)
    key = str(coord).strip().lower().replace(" ", "_").replace("-", "_")
    ideal = _COORD_ANGLES.get(key)
    if ideal is None:
        return na(name, f"central angle not tabulated for {coord!r}")
    try:
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_central_angle_deg must be numeric")
    if abs(c - ideal) <= 0.1:
        return confirm(name, f"{key} central angle = {ideal:.4f} deg (matches claim)",
                       {"ideal_central_angle_deg": ideal})
    return mismatch(name, f"{key} central angle = {ideal:.4f} deg, not {c}",
                    {"ideal_central_angle_deg": ideal})


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    gv = packet.get("GEOM_VERIFY") or {}
    if "coordination" in gv and "claimed_central_angle_deg" in gv:
        results.append(verify_coordination_geometry(gv))
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
    if (gv.get("rect_length") is not None or gv.get("rect_l") is not None) and (
        gv.get("rect_width") is not None or gv.get("rect_w") is not None
    ) and (
        gv.get("claimed_rect_area") is not None or gv.get("claimed_rect_perimeter") is not None
    ):
        results.append(verify_rectangle_properties(gv))
    if gv.get("sphere_radius") is not None and (
        gv.get("claimed_sphere_volume") is not None
        or gv.get("claimed_sphere_surface_area") is not None
    ):
        results.append(verify_sphere_properties(gv))
    if gv.get("cyl_radius") is not None and gv.get("cyl_height") is not None and gv.get("claimed_cyl_volume") is not None:
        results.append(verify_cylinder_properties(gv))
    if gv.get("cube_side") is not None and (
        gv.get("claimed_cube_volume") is not None or gv.get("claimed_cube_surface_area") is not None
    ):
        results.append(verify_cube_properties(gv))
    if not results:
        results.append(na("geometry", "no GEOM_VERIFY artifacts present"))
    return results
