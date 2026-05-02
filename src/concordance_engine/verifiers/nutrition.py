"""Nutrition verifier (biology umbrella, sibling to genetics + agriculture).

Deterministic checks against public-domain nutrition reference data:
macronutrient calorie math (4-4-9 cal/g for carb/protein/fat),
National Academies of Sciences Dietary Reference Intakes (DRI / RDA),
and basic energy-balance arithmetic.

All embedded reference data is public-domain or freely redistributable
(USDA / National Academies of Sciences DRI publications). No external
dataset download required.

Checks performed:

  * nutrition.macronutrient_calories
      Total calorie claim matches 4·carb_g + 4·protein_g + 9·fat_g
      (+ 7·alcohol_g if supplied) within tolerance.
  * nutrition.rda_compliance
      Claimed nutrient intake meets the RDA for a given age/sex group
      (or fails it). For a "deficient" claim, intake < RDA. For a
      "sufficient" claim, intake >= RDA.
  * nutrition.energy_balance
      Net calorie balance (intake - expenditure) matches claim, e.g.
      "1500 cal intake, 2000 cal expenditure → 500 cal deficit/day".
  * nutrition.bmi_classification
      BMI = weight_kg / height_m² in standard WHO bands:
      underweight (<18.5), normal (18.5-24.9), overweight (25-29.9),
      obese (≥30). Matches claim.

NUT_VERIFY packet shape (any subset of fields):
    {
      "calories_claimed": 500,
      "carb_g": 50, "protein_g": 30, "fat_g": 20, "alcohol_g": 0,
      "tolerance_kcal": 5,
      "nutrient": "vitamin_c", "intake_mg": 90, "age_sex_group": "adult_male",
      "claimed_status": "sufficient",
      "intake_kcal": 1500, "expenditure_kcal": 2000,
      "claimed_balance_kcal": -500,
      "weight_kg": 75, "height_m": 1.75,
      "claimed_bmi_class": "normal",
    }
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# Calorie content per gram (Atwater factors, public-domain USDA convention).
_CAL_PER_G_CARB = 4.0
_CAL_PER_G_PROTEIN = 4.0
_CAL_PER_G_FAT = 9.0
_CAL_PER_G_ALCOHOL = 7.0


# Selected RDAs from the National Academies' Dietary Reference Intakes
# (public-domain, government work). Units vary by nutrient — see the value
# tuple comment. Coverage is intentionally narrow: vitamin C, vitamin D,
# iron, calcium across adult male/female/pregnant/lactating + 9-13/14-18
# child/adolescent groups. Expand as use cases emerge.
_RDA_TABLE: Dict[str, Dict[str, float]] = {
    # vitamin C, mg/day
    "vitamin_c": {
        "child_9_13": 45,
        "adolescent_14_18_male": 75,
        "adolescent_14_18_female": 65,
        "adult_male": 90,
        "adult_female": 75,
        "pregnant": 85,
        "lactating": 120,
    },
    # vitamin D, IU/day
    "vitamin_d": {
        "adult_male": 600,
        "adult_female": 600,
        "adult_70plus": 800,
    },
    # iron, mg/day
    "iron": {
        "child_9_13": 8,
        "adolescent_14_18_male": 11,
        "adolescent_14_18_female": 15,
        "adult_male": 8,
        "adult_female_19_50": 18,
        "adult_female_51plus": 8,
        "pregnant": 27,
        "lactating": 9,
    },
    # calcium, mg/day
    "calcium": {
        "child_9_13": 1300,
        "adolescent_14_18": 1300,
        "adult_19_50": 1000,
        "adult_male_51_70": 1000,
        "adult_female_51_70": 1200,
        "adult_71plus": 1200,
    },
}


# WHO BMI classification bands (kg/m²). Public-domain.
def _bmi_class(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    if bmi < 25.0:
        return "normal"
    if bmi < 30.0:
        return "overweight"
    return "obese"


def verify_macronutrient_calories(spec: Dict[str, Any]) -> VerifierResult:
    """4·carb + 4·protein + 9·fat (+ 7·alcohol) within tolerance of claim."""
    name = "nutrition.macronutrient_calories"
    claimed = spec.get("calories_claimed")
    carb = spec.get("carb_g", 0)
    protein = spec.get("protein_g", 0)
    fat = spec.get("fat_g", 0)
    alcohol = spec.get("alcohol_g", 0)
    if claimed is None and not any(spec.get(k) is not None for k in ("carb_g", "protein_g", "fat_g")):
        return na(name)
    if claimed is None:
        return na(name, "calories_claimed missing")
    try:
        c = float(claimed)
        cg = float(carb or 0)
        pg = float(protein or 0)
        fg = float(fat or 0)
        ag = float(alcohol or 0)
    except (TypeError, ValueError):
        return error(name, f"non-numeric input: claimed={claimed!r}, carb={carb!r}, protein={protein!r}, fat={fat!r}")
    if cg < 0 or pg < 0 or fg < 0 or ag < 0:
        return error(name, "macronutrient grams cannot be negative")
    actual = (cg * _CAL_PER_G_CARB + pg * _CAL_PER_G_PROTEIN
              + fg * _CAL_PER_G_FAT + ag * _CAL_PER_G_ALCOHOL)
    tol = float(spec.get("tolerance_kcal", 5.0))
    diff = abs(actual - c)
    data = {"actual_kcal": actual, "claimed_kcal": c, "diff_kcal": diff,
            "carb_g": cg, "protein_g": pg, "fat_g": fg, "alcohol_g": ag,
            "tolerance_kcal": tol}
    if diff <= tol:
        return confirm(name,
                       f"{actual:.0f} kcal from {cg}g C + {pg}g P + {fg}g F"
                       f"{f' + {ag}g A' if ag else ''} matches claim {c:.0f} (diff {diff:.1f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"actual {actual:.0f} kcal != claimed {c:.0f} kcal (diff {diff:.1f} > tol {tol})",
                    data)


def verify_rda_compliance(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed sufficient/deficient status matches intake vs RDA."""
    name = "nutrition.rda_compliance"
    nutrient = (spec.get("nutrient") or "").lower().strip()
    group = (spec.get("age_sex_group") or "").lower().strip()
    intake = spec.get("intake_mg") if "intake_mg" in spec else spec.get("intake")
    claim = (spec.get("claimed_status") or "").lower().strip()
    if not nutrient or not group or intake is None or not claim:
        return na(name)
    if nutrient not in _RDA_TABLE:
        return na(name, f"no RDA data for {nutrient!r}")
    if group not in _RDA_TABLE[nutrient]:
        return na(name, f"no RDA for {nutrient} in group {group!r}")
    try:
        intake_v = float(intake)
    except (TypeError, ValueError):
        return error(name, f"intake must be numeric, got {intake!r}")
    if intake_v < 0:
        return error(name, f"intake cannot be negative ({intake_v})")
    rda = _RDA_TABLE[nutrient][group]
    sufficient = intake_v >= rda
    actual = "sufficient" if sufficient else "deficient"
    data = {"nutrient": nutrient, "group": group, "intake": intake_v,
            "rda": rda, "actual_status": actual, "claimed_status": claim}
    if claim == actual:
        return confirm(name,
                       f"{nutrient} intake {intake_v} vs RDA {rda} for {group}: "
                       f"{actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"{nutrient} intake {intake_v} vs RDA {rda} for {group}: "
                    f"{actual}, claimed {claim}",
                    data)


def verify_energy_balance(spec: Dict[str, Any]) -> VerifierResult:
    """Net intake - expenditure matches claimed daily balance."""
    name = "nutrition.energy_balance"
    intake = spec.get("intake_kcal")
    exp = spec.get("expenditure_kcal")
    claimed = spec.get("claimed_balance_kcal")
    if intake is None or exp is None or claimed is None:
        return na(name)
    try:
        i = float(intake)
        e = float(exp)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "intake_kcal / expenditure_kcal / claimed_balance_kcal must be numeric")
    if i < 0 or e < 0:
        return error(name, "intake/expenditure cannot be negative")
    actual = i - e
    tol = float(spec.get("tolerance_kcal", 5.0))
    diff = abs(actual - c)
    data = {"intake_kcal": i, "expenditure_kcal": e,
            "actual_balance_kcal": actual, "claimed_balance_kcal": c,
            "diff_kcal": diff, "tolerance_kcal": tol}
    if diff <= tol:
        return confirm(name,
                       f"balance = {i} - {e} = {actual} kcal (matches claim {c}, diff {diff:.1f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"balance = {i} - {e} = {actual} kcal, claimed {c} (diff {diff:.1f} > {tol})",
                    data)


def verify_bmi_classification(spec: Dict[str, Any]) -> VerifierResult:
    """BMI = weight_kg / height_m² classified per WHO bands."""
    name = "nutrition.bmi_classification"
    w = spec.get("weight_kg")
    h = spec.get("height_m")
    claim = spec.get("claimed_bmi_class")
    if w is None or h is None or claim is None:
        return na(name)
    try:
        wf = float(w)
        hf = float(h)
    except (TypeError, ValueError):
        return error(name, f"weight_kg / height_m must be numeric")
    if wf <= 0 or hf <= 0:
        return error(name, f"weight and height must be positive (got {wf}, {hf})")
    bmi = wf / (hf * hf)
    actual = _bmi_class(bmi)
    claim_norm = str(claim).lower().strip()
    data = {"weight_kg": wf, "height_m": hf, "bmi": bmi,
            "actual_class": actual, "claimed_class": claim_norm}
    if claim_norm == actual:
        return confirm(name,
                       f"BMI = {wf:.1f}kg / {hf:.2f}m² = {bmi:.1f} → {actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"BMI = {bmi:.1f} → {actual}, claimed {claim_norm}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    nv = packet.get("NUT_VERIFY") or {}

    if "calories_claimed" in nv:
        results.append(verify_macronutrient_calories(nv))
    if "nutrient" in nv and "claimed_status" in nv:
        results.append(verify_rda_compliance(nv))
    if "intake_kcal" in nv and "expenditure_kcal" in nv and "claimed_balance_kcal" in nv:
        results.append(verify_energy_balance(nv))
    if "weight_kg" in nv and "height_m" in nv and "claimed_bmi_class" in nv:
        results.append(verify_bmi_classification(nv))

    if not results:
        results.append(na("nutrition", "no NUT_VERIFY artifacts present"))
    return results
