"""Construction / building verifier.

Deterministic checks on construction quantity and load calculations using
standard engineering formulas (public domain, no proprietary data).

Checks:
  * construction.concrete_volume  — V = length * width * depth
  * construction.rectangular_area — A = length * width
  * construction.circular_area   — A = π * r²
  * construction.rebar_weight    — W = length * unit_weight_kg_per_m
  * construction.wall_area       — A = perimeter * height - openings
  * construction.paint_coverage  — cans = area / coverage_per_can
  * construction.floor_tiles     — tiles = ceil(area / tile_area) * (1 + waste)
  * construction.beam_load       — uniform load intensity = total_load / span

CONSTR_VERIFY packet shape (any subset):
    {
      "length_m": 10, "width_m": 5, "depth_m": 0.15,
      "claimed_concrete_m3": 7.5,

      "claimed_rect_area_m2": 50.0,

      "radius_m": 3.5,
      "claimed_circle_area_m2": 38.48,

      "rebar_length_m": 100, "rebar_unit_weight_kg_per_m": 0.617,
      "claimed_rebar_weight_kg": 61.7,

      "perimeter_m": 30, "wall_height_m": 3, "openings_m2": 12,
      "claimed_wall_area_m2": 78.0,

      "paint_area_m2": 80, "coverage_m2_per_can": 10,
      "claimed_paint_cans": 8,

      "tile_area_m2": 50, "tile_size_m2": 0.25, "waste_factor": 0.10,
      "claimed_tile_count": 220,

      "total_load_kn": 120, "span_m": 6,
      "claimed_load_intensity_kn_per_m": 20.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_concrete_volume(spec: Dict[str, Any]) -> VerifierResult:
    """V = length * width * depth (cubic metres)"""
    name = "construction.concrete_volume"
    L = spec.get("length_m")
    W = spec.get("width_m")
    D = spec.get("depth_m")
    claimed = spec.get("claimed_concrete_m3")
    if any(v is None for v in (L, W, D, claimed)):
        return na(name)
    try:
        Lf, Wf, Df, c = float(L), float(W), float(D), float(claimed)
    except (TypeError, ValueError):
        return error(name, "length_m, width_m, depth_m, claimed_concrete_m3 must be numeric")
    if any(v <= 0 for v in (Lf, Wf, Df)):
        return error(name, "length_m, width_m, and depth_m must be positive")
    actual = Lf * Wf * Df
    tol = float(spec.get("tolerance_m3", max(0.001, actual * 0.005)))
    data = {"length_m": Lf, "width_m": Wf, "depth_m": Df,
            "actual_volume_m3": round(actual, 4), "claimed_volume_m3": c,
            "formula": "V = L × W × D"}
    if abs(actual - c) <= tol:
        return confirm(name, f"V = {actual:.4f} m³ (matches claim)", data)
    return mismatch(name, f"V = {actual:.4f} m³, claimed {c} m³", data)


def verify_rectangular_area(spec: Dict[str, Any]) -> VerifierResult:
    """A = length * width"""
    name = "construction.rectangular_area"
    L = spec.get("length_m")
    W = spec.get("width_m")
    claimed = spec.get("claimed_rect_area_m2")
    if any(v is None for v in (L, W, claimed)):
        return na(name)
    try:
        Lf, Wf, c = float(L), float(W), float(claimed)
    except (TypeError, ValueError):
        return error(name, "length_m, width_m, claimed_rect_area_m2 must be numeric")
    actual = Lf * Wf
    tol = float(spec.get("tolerance_m2", max(0.001, actual * 0.005)))
    data = {"length_m": Lf, "width_m": Wf,
            "actual_area_m2": round(actual, 4), "claimed_area_m2": c,
            "formula": "A = L × W"}
    if abs(actual - c) <= tol:
        return confirm(name, f"A = {actual:.4f} m² (matches claim)", data)
    return mismatch(name, f"A = {actual:.4f} m², claimed {c} m²", data)


def verify_circular_area(spec: Dict[str, Any]) -> VerifierResult:
    """A = π * r²"""
    name = "construction.circular_area"
    r = spec.get("radius_m")
    claimed = spec.get("claimed_circle_area_m2")
    if r is None or claimed is None:
        return na(name)
    try:
        rf, c = float(r), float(claimed)
    except (TypeError, ValueError):
        return error(name, "radius_m and claimed_circle_area_m2 must be numeric")
    if rf <= 0:
        return error(name, f"radius_m must be > 0, got {rf}")
    actual = math.pi * rf ** 2
    tol = float(spec.get("tolerance_m2", max(0.001, actual * 0.005)))
    data = {"radius_m": rf, "actual_area_m2": round(actual, 4), "claimed_area_m2": c,
            "formula": "A = π × r²"}
    if abs(actual - c) <= tol:
        return confirm(name, f"A = {actual:.4f} m² (matches claim)", data)
    return mismatch(name, f"A = {actual:.4f} m², claimed {c} m²", data)


def verify_rebar_weight(spec: Dict[str, Any]) -> VerifierResult:
    """W = rebar_length_m * unit_weight_kg_per_m"""
    name = "construction.rebar_weight"
    length = spec.get("rebar_length_m")
    uw = spec.get("rebar_unit_weight_kg_per_m")
    claimed = spec.get("claimed_rebar_weight_kg")
    if any(v is None for v in (length, uw, claimed)):
        return na(name)
    try:
        lf, uwf, c = float(length), float(uw), float(claimed)
    except (TypeError, ValueError):
        return error(name, "rebar_length_m, rebar_unit_weight_kg_per_m, claimed_rebar_weight_kg must be numeric")
    actual = lf * uwf
    tol = float(spec.get("tolerance_kg", max(0.01, actual * 0.005)))
    data = {"rebar_length_m": lf, "unit_weight_kg_per_m": uwf,
            "actual_weight_kg": round(actual, 3), "claimed_weight_kg": c,
            "formula": "W = length × unit_weight"}
    if abs(actual - c) <= tol:
        return confirm(name, f"rebar weight = {actual:.3f} kg (matches claim)", data)
    return mismatch(name, f"rebar weight = {actual:.3f} kg, claimed {c} kg", data)


def verify_wall_area(spec: Dict[str, Any]) -> VerifierResult:
    """Wall area = perimeter * height - openings"""
    name = "construction.wall_area"
    perim = spec.get("perimeter_m")
    height = spec.get("wall_height_m")
    openings = spec.get("openings_m2", 0)
    claimed = spec.get("claimed_wall_area_m2")
    if any(v is None for v in (perim, height, claimed)):
        return na(name)
    try:
        pf, hf, of, c = float(perim), float(height), float(openings), float(claimed)
    except (TypeError, ValueError):
        return error(name, "perimeter_m, wall_height_m, claimed_wall_area_m2 must be numeric")
    actual = pf * hf - of
    tol = float(spec.get("tolerance_m2", max(0.01, abs(actual) * 0.005)))
    data = {"perimeter_m": pf, "wall_height_m": hf, "openings_m2": of,
            "actual_wall_area_m2": round(actual, 4), "claimed_wall_area_m2": c,
            "formula": "wall_area = perimeter × height − openings"}
    if abs(actual - c) <= tol:
        return confirm(name, f"wall area = {actual:.4f} m² (matches claim)", data)
    return mismatch(name, f"wall area = {actual:.4f} m², claimed {c} m²", data)


def verify_paint_coverage(spec: Dict[str, Any]) -> VerifierResult:
    """Cans needed = ceil(area / coverage_per_can)"""
    name = "construction.paint_coverage"
    area = spec.get("paint_area_m2")
    coverage = spec.get("coverage_m2_per_can")
    claimed = spec.get("claimed_paint_cans")
    if any(v is None for v in (area, coverage, claimed)):
        return na(name)
    try:
        af, cf_cov, c = float(area), float(coverage), float(claimed)
    except (TypeError, ValueError):
        return error(name, "paint_area_m2, coverage_m2_per_can, claimed_paint_cans must be numeric")
    if cf_cov <= 0:
        return error(name, f"coverage_m2_per_can must be > 0, got {cf_cov}")
    actual = math.ceil(af / cf_cov)
    data = {"paint_area_m2": af, "coverage_m2_per_can": cf_cov,
            "actual_cans": actual, "claimed_cans": c,
            "formula": "cans = ceil(area / coverage_per_can)"}
    if actual == int(c):
        return confirm(name, f"{actual} cans needed (matches claim)", data)
    return mismatch(name, f"{actual} cans needed, claimed {c}", data)


def verify_floor_tiles(spec: Dict[str, Any]) -> VerifierResult:
    """Tiles = ceil(area / tile_size) * (1 + waste_factor)"""
    name = "construction.floor_tiles"
    area = spec.get("tile_area_m2")
    tile_size = spec.get("tile_size_m2")
    waste = spec.get("waste_factor", 0.10)
    claimed = spec.get("claimed_tile_count")
    if any(v is None for v in (area, tile_size, claimed)):
        return na(name)
    try:
        af, tsf, wf, c = float(area), float(tile_size), float(waste), float(claimed)
    except (TypeError, ValueError):
        return error(name, "tile_area_m2, tile_size_m2, claimed_tile_count must be numeric")
    if tsf <= 0:
        return error(name, f"tile_size_m2 must be > 0, got {tsf}")
    base_tiles = math.ceil(af / tsf)
    actual = math.ceil(base_tiles * (1 + wf))
    data = {"tile_area_m2": af, "tile_size_m2": tsf, "waste_factor": wf,
            "base_tiles": base_tiles, "actual_tile_count": actual, "claimed_tile_count": c,
            "formula": "tiles = ceil(area / tile_size) × (1 + waste)"}
    if actual == int(c):
        return confirm(name, f"{actual} tiles needed (matches claim)", data)
    return mismatch(name, f"{actual} tiles needed, claimed {c}", data)


def verify_beam_load(spec: Dict[str, Any]) -> VerifierResult:
    """Uniform load intensity = total_load / span"""
    name = "construction.beam_load"
    load = spec.get("total_load_kn")
    span = spec.get("span_m")
    claimed = spec.get("claimed_load_intensity_kn_per_m")
    if any(v is None for v in (load, span, claimed)):
        return na(name)
    try:
        lf, sf, c = float(load), float(span), float(claimed)
    except (TypeError, ValueError):
        return error(name, "total_load_kn, span_m, claimed_load_intensity_kn_per_m must be numeric")
    if sf <= 0:
        return error(name, f"span_m must be > 0, got {sf}")
    actual = lf / sf
    tol = float(spec.get("tolerance_kn_per_m", max(0.001, actual * 0.005)))
    data = {"total_load_kn": lf, "span_m": sf,
            "actual_intensity_kn_per_m": round(actual, 4), "claimed_intensity": c,
            "formula": "intensity = total_load / span"}
    if abs(actual - c) <= tol:
        return confirm(name, f"load intensity = {actual:.4f} kN/m (matches claim)", data)
    return mismatch(name, f"load intensity = {actual:.4f} kN/m, claimed {c}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CONSTR_VERIFY") or {}
    if "length_m" in cv and "width_m" in cv:
        if "depth_m" in cv and "claimed_concrete_m3" in cv:
            results.append(verify_concrete_volume(cv))
        if "claimed_rect_area_m2" in cv:
            results.append(verify_rectangular_area(cv))
    if "radius_m" in cv and "claimed_circle_area_m2" in cv:
        results.append(verify_circular_area(cv))
    if "rebar_length_m" in cv and "claimed_rebar_weight_kg" in cv:
        results.append(verify_rebar_weight(cv))
    if "perimeter_m" in cv and "wall_height_m" in cv and "claimed_wall_area_m2" in cv:
        results.append(verify_wall_area(cv))
    if "paint_area_m2" in cv and "claimed_paint_cans" in cv:
        results.append(verify_paint_coverage(cv))
    if "tile_area_m2" in cv and "claimed_tile_count" in cv:
        results.append(verify_floor_tiles(cv))
    if "total_load_kn" in cv and "span_m" in cv and "claimed_load_intensity_kn_per_m" in cv:
        results.append(verify_beam_load(cv))
    if not results:
        results.append(na("construction", "no CONSTR_VERIFY artifacts present"))
    return results
