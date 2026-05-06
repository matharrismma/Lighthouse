"""Architecture verifier (physical-substance + authority/trust grid axes).

Textbook and public-domain building code principles (IBC-style).
NOT jurisdiction-specific legal advice.

Checks:
  * architecture.floor_area_ratio   — FAR = total_floor_area / lot_area
  * architecture.occupant_load      — occupants = ⌈floor_area / load_factor⌉
  * architecture.stair_compliance   — IBC riser 102–178 mm, tread ≥ 279 mm
  * architecture.window_wall_ratio  — WWR = window_area / gross_wall_area
  * architecture.structural_load    — total = dead + live + snow

ARCH_VERIFY shape (any subset):
    {
      "total_floor_area_m2": 2000,
      "lot_area_m2": 1000,
      "claimed_far": 2.0,

      "floor_area_m2": 500,
      "occupant_load_factor_m2_per_person": 4.6,
      "claimed_occupant_count": 109,

      "riser_height_mm": 170,
      "tread_depth_mm": 280,
      "claimed_compliant": true,

      "window_area_m2": 150,
      "gross_wall_area_m2": 600,
      "claimed_wwr": 0.25,

      "dead_load_kPa": 3.5,
      "live_load_kPa": 2.4,
      "snow_load_kPa": 1.0,
      "claimed_total_load_kPa": 6.9,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_floor_area_ratio(spec: Dict[str, Any]) -> VerifierResult:
    """FAR = total_floor_area / lot_area"""
    name = "architecture.floor_area_ratio"
    tfa = spec.get("total_floor_area_m2")
    lot = spec.get("lot_area_m2")
    claimed = spec.get("claimed_far")
    if tfa is None or lot is None or claimed is None:
        return na(name)
    try:
        tfaf, lotf, c = float(tfa), float(lot), float(claimed)
    except (TypeError, ValueError):
        return error(name, "total_floor_area_m2, lot_area_m2, claimed_far must be numeric")
    if lotf <= 0:
        return error(name, f"lot_area_m2 must be positive, got {lotf}")
    if tfaf < 0:
        return error(name, f"total_floor_area_m2 must be non-negative, got {tfaf}")
    actual = tfaf / lotf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "FAR = total_floor_area / lot_area",
            "total_floor_area_m2": tfaf, "lot_area_m2": lotf,
            "actual_far": actual, "claimed_far": c, "diff": diff}
    if diff <= threshold:
        return confirm(name, f"FAR = {tfaf}/{lotf} = {actual:.6g} (matches claim {c})", data)
    return mismatch(name, f"actual FAR {actual:.6g}, claimed {c} (diff {diff:.6g})", data)


def verify_occupant_load(spec: Dict[str, Any]) -> VerifierResult:
    """occupants = ⌈floor_area / occupant_load_factor⌉ (IBC-style)"""
    name = "architecture.occupant_load"
    area = spec.get("floor_area_m2")
    factor = spec.get("occupant_load_factor_m2_per_person")
    claimed = spec.get("claimed_occupant_count")
    if area is None or factor is None or claimed is None:
        return na(name)
    try:
        areaf, factorf, c = float(area), float(factor), float(claimed)
    except (TypeError, ValueError):
        return error(name, "floor_area_m2, occupant_load_factor_m2_per_person, "
                           "claimed_occupant_count must be numeric")
    if factorf <= 0:
        return error(name, f"occupant_load_factor_m2_per_person must be positive, got {factorf}")
    if areaf < 0:
        return error(name, f"floor_area_m2 must be non-negative, got {areaf}")
    actual = math.ceil(areaf / factorf)
    data = {"formula": "occupants = ⌈floor_area / occupant_load_factor⌉",
            "floor_area_m2": areaf, "occupant_load_factor_m2_per_person": factorf,
            "actual_occupant_count": actual, "claimed_occupant_count": int(round(c)),
            "diff": abs(actual - c)}
    if actual == int(round(c)):
        return confirm(name,
                       f"⌈{areaf}/{factorf}⌉ = {actual} occupants (matches claim {int(round(c))})",
                       data)
    return mismatch(name,
                    f"actual ⌈{areaf}/{factorf}⌉ = {actual} occupants, claimed {int(round(c))}",
                    data)


def verify_stair_compliance(spec: Dict[str, Any]) -> VerifierResult:
    """IBC-style: riser 102–178 mm, tread depth ≥ 279 mm."""
    name = "architecture.stair_compliance"
    riser = spec.get("riser_height_mm")
    tread = spec.get("tread_depth_mm")
    claimed = spec.get("claimed_compliant")
    if riser is None or tread is None or claimed is None:
        return na(name)
    try:
        riserf, treadf = float(riser), float(tread)
    except (TypeError, ValueError):
        return error(name, "riser_height_mm and tread_depth_mm must be numeric")
    actual = (102 <= riserf <= 178) and (treadf >= 279)
    data = {"riser_height_mm": riserf, "tread_depth_mm": treadf,
            "actual_compliant": actual, "claimed_compliant": bool(claimed),
            "formula": "102 ≤ riser_mm ≤ 178 AND tread_mm ≥ 279",
            "standard": "IBC-style (public-domain textbook values; not jurisdiction-specific advice)",
            "riser_ok": 102 <= riserf <= 178,
            "tread_ok": treadf >= 279}
    if actual == bool(claimed):
        return confirm(name,
                       f"riser {riserf} mm, tread {treadf} mm → compliant={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"riser {riserf} mm, tread {treadf} mm → compliant={actual}, claimed {bool(claimed)}",
                    data)


def verify_window_wall_ratio(spec: Dict[str, Any]) -> VerifierResult:
    """WWR = window_area / gross_wall_area"""
    name = "architecture.window_wall_ratio"
    win = spec.get("window_area_m2")
    wall = spec.get("gross_wall_area_m2")
    claimed = spec.get("claimed_wwr")
    if win is None or wall is None or claimed is None:
        return na(name)
    try:
        winf, wallf, c = float(win), float(wall), float(claimed)
    except (TypeError, ValueError):
        return error(name, "window_area_m2, gross_wall_area_m2, claimed_wwr must be numeric")
    if wallf <= 0:
        return error(name, f"gross_wall_area_m2 must be positive, got {wallf}")
    if winf < 0:
        return error(name, f"window_area_m2 must be non-negative, got {winf}")
    actual = winf / wallf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "WWR = window_area / gross_wall_area",
            "window_area_m2": winf, "gross_wall_area_m2": wallf,
            "actual_wwr": actual, "claimed_wwr": c, "diff": diff}
    if diff <= threshold:
        return confirm(name, f"WWR = {winf}/{wallf} = {actual:.6g} (matches claim {c})", data)
    return mismatch(name, f"actual WWR {actual:.6g}, claimed {c} (diff {diff:.6g})", data)


def verify_structural_load(spec: Dict[str, Any]) -> VerifierResult:
    """Total load = dead_load + live_load + snow_load (simple superposition)."""
    name = "architecture.structural_load"
    dead = spec.get("dead_load_kPa")
    live = spec.get("live_load_kPa")
    claimed = spec.get("claimed_total_load_kPa")
    if dead is None or live is None or claimed is None:
        return na(name)
    try:
        df, lf, c = float(dead), float(live), float(claimed)
    except (TypeError, ValueError):
        return error(name, "dead_load_kPa, live_load_kPa, claimed_total_load_kPa must be numeric")
    snow_raw = spec.get("snow_load_kPa", 0)
    try:
        sf = float(snow_raw)
    except (TypeError, ValueError):
        return error(name, "snow_load_kPa must be numeric")
    actual = df + lf + sf
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual) if actual else abs_tol)
    data = {"formula": "total = dead + live + snow",
            "dead_load_kPa": df, "live_load_kPa": lf, "snow_load_kPa": sf,
            "actual_total_load_kPa": actual, "claimed_total_load_kPa": c, "diff": diff}
    if diff <= threshold:
        return confirm(name,
                       f"total = {df} + {lf} + {sf} = {actual:.6g} kPa (matches claim {c})",
                       data)
    return mismatch(name,
                    f"actual total {actual:.6g} kPa, claimed {c} kPa (diff {diff:.6g})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    av = packet.get("ARCH_VERIFY") or {}

    if all(av.get(k) is not None for k in ("total_floor_area_m2", "lot_area_m2", "claimed_far")):
        results.append(verify_floor_area_ratio(av))

    if all(av.get(k) is not None for k in ("floor_area_m2", "occupant_load_factor_m2_per_person",
                                            "claimed_occupant_count")):
        results.append(verify_occupant_load(av))

    if all(av.get(k) is not None for k in ("riser_height_mm", "tread_depth_mm", "claimed_compliant")):
        results.append(verify_stair_compliance(av))

    if all(av.get(k) is not None for k in ("window_area_m2", "gross_wall_area_m2", "claimed_wwr")):
        results.append(verify_window_wall_ratio(av))

    if all(av.get(k) is not None for k in ("dead_load_kPa", "live_load_kPa",
                                            "claimed_total_load_kPa")):
        results.append(verify_structural_load(av))

    if not results:
        results.append(na("architecture", "no ARCH_VERIFY artifacts present"))
    return results
