"""Soil science verifier.

Deterministic checks on soil and crop calculations using public-domain
agricultural reference data (FAO, USDA NRCS, Cooperative Extension).

Checks:
  * soil_science.ph_suitability    — crop pH tolerance range check
  * soil_science.npk_requirement   — fertilizer N-P-K kg/hectare
  * soil_science.irrigation_req    — daily water requirement (mm/day)
  * soil_science.lime_requirement  — lime needed to raise pH (tonnes/ha)
  * soil_science.soil_texture      — sand+silt+clay triangle classification

SOIL_VERIFY packet shape (any subset):
    {
      "crop": "maize", "soil_ph": 6.2,
      "claimed_ph_suitable": true,

      "crop_npk": "maize", "area_hectares": 2.0,
      "claimed_n_kg": 320, "claimed_p_kg": 120, "claimed_k_kg": 140,

      "reference_et0_mm_per_day": 5.0, "crop_coefficient": 1.15,
      "claimed_etc_mm_per_day": 5.75,

      "current_ph": 5.5, "target_ph": 6.5, "soil_type": "clay_loam",
      "claimed_lime_t_per_ha": 4.0,

      "sand_pct": 40, "silt_pct": 40, "clay_pct": 20,
      "claimed_texture_class": "loam",
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


# ── Crop pH tolerance (public-domain, USDA / FAO) ────────────────────────────
# (min_ph, max_ph) preferred range
_CROP_PH: Dict[str, Tuple[float, float]] = {
    "maize": (5.8, 7.0), "corn": (5.8, 7.0),
    "wheat": (5.5, 7.5),
    "rice": (5.0, 6.5),
    "soybean": (6.0, 7.0), "soybeans": (6.0, 7.0),
    "potato": (4.8, 6.5), "potatoes": (4.8, 6.5),
    "tomato": (5.5, 7.5), "tomatoes": (5.5, 7.5),
    "cassava": (4.5, 7.5),
    "sorghum": (5.5, 7.5),
    "cotton": (5.8, 8.0),
    "groundnut": (5.5, 7.0), "peanut": (5.5, 7.0),
    "sunflower": (6.0, 7.5),
    "sugarcane": (5.0, 8.5),
    "banana": (5.0, 7.0),
    "coffee": (4.5, 6.0),
    "tea": (4.5, 6.0),
    "blueberry": (4.0, 5.5),
    "carrot": (5.8, 7.0), "carrots": (5.8, 7.0),
    "cabbage": (6.0, 7.5),
    "lettuce": (6.0, 7.0),
    "onion": (5.5, 7.0), "onions": (5.5, 7.0),
    "garlic": (5.5, 7.5),
    "barley": (6.0, 7.5),
    "oat": (5.5, 7.5), "oats": (5.5, 7.5),
}

# ── NPK reference (kg/ha for 1 tonne of grain yield, FAO guidelines) ─────────
# (N_kg_per_ha, P_kg_per_ha, K_kg_per_ha) per hectare for moderate yield
_CROP_NPK: Dict[str, Tuple[float, float, float]] = {
    "maize": (160, 60, 70), "corn": (160, 60, 70),
    "wheat": (120, 60, 60),
    "rice": (100, 50, 60),
    "soybean": (30, 60, 80), "soybeans": (30, 60, 80),
    "potato": (150, 80, 200), "potatoes": (150, 80, 200),
    "tomato": (120, 80, 150), "tomatoes": (120, 80, 150),
    "sorghum": (100, 50, 60),
    "cotton": (100, 50, 80),
    "groundnut": (20, 60, 60), "peanut": (20, 60, 60),
    "sugarcane": (200, 80, 300),
    "cassava": (80, 40, 120),
    "barley": (100, 50, 50),
}

# ── Soil texture classification (USDA triangle, simplified) ──────────────────
def _texture_class(sand: float, silt: float, clay: float) -> str:
    """Simplified USDA soil texture classification."""
    if clay >= 40:
        return "clay"
    if clay >= 27 and silt >= 40:
        return "silty_clay"
    if clay >= 27:
        if sand >= 45:
            return "sandy_clay"
        return "clay"
    if clay >= 20 and sand < 45 and silt < 28:
        return "clay_loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if silt >= 50 and clay < 27:
        return "silty_loam"
    if silt >= 28 and clay >= 7 and sand < 52:
        return "loam"
    if sand >= 85:
        return "sand"
    if sand >= 70:
        return "sandy_loam"
    if clay < 7 and silt < 50:
        return "sand"
    return "loam"

# ── Lime requirement (tonnes/ha) to raise pH, by soil type ───────────────────
# Source: Cooperative Extension lime requirement tables (public domain)
# Values are approximate: tonnes of agricultural limestone per ha per pH unit
_LIME_RATE: Dict[str, float] = {
    "sand": 1.5,
    "sandy_loam": 2.0,
    "loam": 2.5,
    "clay_loam": 3.5,
    "clay": 4.5,
    "silty_loam": 3.0,
    "silt": 2.8,
}


def verify_ph_suitability(spec: Dict[str, Any]) -> VerifierResult:
    """Check whether a soil pH falls within a crop's preferred range."""
    name = "soil_science.ph_suitability"
    crop = str(spec.get("crop", "")).lower().strip()
    ph = spec.get("soil_ph")
    claimed = spec.get("claimed_ph_suitable")
    if not crop or ph is None or claimed is None:
        return na(name)
    range_ = _CROP_PH.get(crop)
    if range_ is None:
        known = sorted(_CROP_PH.keys())
        return na(name, f"crop '{crop}' not in reference data. Known: {known}")
    try:
        phf = float(ph)
    except (TypeError, ValueError):
        return error(name, "soil_ph must be numeric")
    ph_min, ph_max = range_
    actually_suitable = ph_min <= phf <= ph_max
    data = {"crop": crop, "soil_ph": phf, "preferred_min": ph_min,
            "preferred_max": ph_max, "suitable": actually_suitable,
            "source": "USDA/FAO crop pH tolerance guidelines"}
    if bool(claimed) == actually_suitable:
        status = "suitable" if actually_suitable else "not suitable"
        return confirm(name, f"pH {phf} is {status} for {crop} (claim correct)", data)
    return mismatch(name,
                    f"pH {phf} is {'suitable' if actually_suitable else 'not suitable'} "
                    f"for {crop} — claim says {'suitable' if claimed else 'not suitable'}",
                    data)


def verify_npk_requirement(spec: Dict[str, Any]) -> VerifierResult:
    """Check NPK fertilizer requirement for a crop and area."""
    name = "soil_science.npk_requirement"
    crop = str(spec.get("crop_npk", "")).lower().strip()
    area = spec.get("area_hectares")
    claimed_n = spec.get("claimed_n_kg")
    claimed_p = spec.get("claimed_p_kg")
    claimed_k = spec.get("claimed_k_kg")
    if not crop or area is None:
        return na(name)
    if all(v is None for v in (claimed_n, claimed_p, claimed_k)):
        return na(name, "at least one of claimed_n_kg, claimed_p_kg, claimed_k_kg required")
    ref = _CROP_NPK.get(crop)
    if ref is None:
        return na(name, f"crop '{crop}' not in NPK reference data")
    try:
        af = float(area)
    except (TypeError, ValueError):
        return error(name, "area_hectares must be numeric")
    N_ref, P_ref, K_ref = ref
    actual_n, actual_p, actual_k = N_ref * af, P_ref * af, K_ref * af
    tol_pct = float(spec.get("tolerance_pct", 10.0))
    results_detail = []
    mismatches = []
    data = {"crop": crop, "area_ha": af,
            "reference_n_kg": actual_n, "reference_p_kg": actual_p, "reference_k_kg": actual_k,
            "tolerance_pct": tol_pct, "source": "FAO fertilizer guidelines"}
    for label, actual, claimed in [("N", actual_n, claimed_n), ("P", actual_p, claimed_p), ("K", actual_k, claimed_k)]:
        if claimed is None:
            continue
        try:
            cf = float(claimed)
        except (TypeError, ValueError):
            return error(name, f"claimed_{label.lower()}_kg must be numeric")
        tol = actual * tol_pct / 100.0
        if abs(actual - cf) <= tol:
            results_detail.append(f"{label}={actual:.1f} kg/ha ✓")
        else:
            mismatches.append(f"{label}: expected {actual:.1f} kg, claimed {cf:.1f} kg")
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(name, f"NPK for {crop} × {af} ha: {', '.join(results_detail)}", data)


def verify_irrigation_req(spec: Dict[str, Any]) -> VerifierResult:
    """ETc (mm/day) = ET0 * Kc  (FAO-56 method)"""
    name = "soil_science.irrigation_req"
    et0 = spec.get("reference_et0_mm_per_day")
    kc = spec.get("crop_coefficient")
    claimed = spec.get("claimed_etc_mm_per_day")
    if any(v is None for v in (et0, kc, claimed)):
        return na(name)
    try:
        et0f, kcf, c = float(et0), float(kc), float(claimed)
    except (TypeError, ValueError):
        return error(name, "reference_et0_mm_per_day, crop_coefficient, claimed_etc_mm_per_day must be numeric")
    actual = et0f * kcf
    tol = float(spec.get("tolerance_mm", max(0.05, actual * 0.02)))
    data = {"et0_mm_per_day": et0f, "crop_coefficient_kc": kcf,
            "actual_etc_mm_per_day": round(actual, 4), "claimed_etc": c,
            "formula": "ETc = ET0 × Kc (FAO-56)", "source": "FAO Irrigation and Drainage Paper 56"}
    if abs(actual - c) <= tol:
        return confirm(name, f"ETc = {actual:.4f} mm/day (matches claim)", data)
    return mismatch(name, f"ETc = {actual:.4f} mm/day, claimed {c}", data)


def verify_lime_requirement(spec: Dict[str, Any]) -> VerifierResult:
    """Lime needed (t/ha) = (target_ph - current_ph) * rate_for_soil_type"""
    name = "soil_science.lime_requirement"
    curr_ph = spec.get("current_ph")
    tgt_ph = spec.get("target_ph")
    soil_type = str(spec.get("soil_type", "loam")).lower().strip()
    claimed = spec.get("claimed_lime_t_per_ha")
    if any(v is None for v in (curr_ph, tgt_ph, claimed)):
        return na(name)
    rate = _LIME_RATE.get(soil_type)
    if rate is None:
        return na(name, f"soil_type '{soil_type}' not recognized. Use: {sorted(_LIME_RATE.keys())}")
    try:
        cpf, tpf, c = float(curr_ph), float(tgt_ph), float(claimed)
    except (TypeError, ValueError):
        return error(name, "current_ph, target_ph, claimed_lime_t_per_ha must be numeric")
    delta = tpf - cpf
    if delta <= 0:
        return na(name, f"target_ph ({tpf}) must be > current_ph ({cpf}) for liming")
    actual = delta * rate
    tol = float(spec.get("tolerance_t", max(0.1, actual * 0.10)))
    data = {"current_ph": cpf, "target_ph": tpf, "delta_ph": delta,
            "soil_type": soil_type, "rate_t_per_ha_per_ph_unit": rate,
            "actual_lime_t_per_ha": round(actual, 2), "claimed_lime_t_per_ha": c,
            "formula": "lime = (target_ph − current_ph) × rate",
            "source": "Cooperative Extension lime requirement tables"}
    if abs(actual - c) <= tol:
        return confirm(name, f"lime needed = {actual:.2f} t/ha (matches claim)", data)
    return mismatch(name, f"lime needed = {actual:.2f} t/ha, claimed {c}", data)


def verify_soil_texture(spec: Dict[str, Any]) -> VerifierResult:
    """Classify soil texture from sand/silt/clay percentages."""
    name = "soil_science.soil_texture"
    sand = spec.get("sand_pct")
    silt = spec.get("silt_pct")
    clay = spec.get("clay_pct")
    claimed = spec.get("claimed_texture_class")
    if any(v is None for v in (sand, silt, clay, claimed)):
        return na(name)
    try:
        sf, sif, clf = float(sand), float(silt), float(clay)
    except (TypeError, ValueError):
        return error(name, "sand_pct, silt_pct, clay_pct must be numeric")
    total = sf + sif + clf
    if abs(total - 100.0) > 1.0:
        return error(name, f"sand + silt + clay must sum to 100%, got {total:.1f}%")
    actual = _texture_class(sf, sif, clf)
    data = {"sand_pct": sf, "silt_pct": sif, "clay_pct": clf,
            "actual_texture_class": actual, "claimed_texture_class": claimed,
            "source": "USDA soil texture triangle"}
    if str(claimed).lower().strip() == actual:
        return confirm(name, f"soil texture = '{actual}' (matches claim)", data)
    return mismatch(name, f"soil texture = '{actual}', claimed '{claimed}'", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    sv = packet.get("SOIL_VERIFY") or {}
    if "crop" in sv and "soil_ph" in sv and "claimed_ph_suitable" in sv:
        results.append(verify_ph_suitability(sv))
    if "crop_npk" in sv and "area_hectares" in sv:
        results.append(verify_npk_requirement(sv))
    if "reference_et0_mm_per_day" in sv and "crop_coefficient" in sv and "claimed_etc_mm_per_day" in sv:
        results.append(verify_irrigation_req(sv))
    if "current_ph" in sv and "target_ph" in sv and "claimed_lime_t_per_ha" in sv:
        results.append(verify_lime_requirement(sv))
    if "sand_pct" in sv and "silt_pct" in sv and "clay_pct" in sv and "claimed_texture_class" in sv:
        results.append(verify_soil_texture(sv))
    if not results:
        results.append(na("soil_science", "no SOIL_VERIFY artifacts present"))
    return results
